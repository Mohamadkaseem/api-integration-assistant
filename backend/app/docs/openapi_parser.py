"""Reads OpenAPI 3.x and Swagger 2.0 specifications with plain code (no AI).

Only local references ("#/components/...", "#/definitions/...") are resolved.
References to other files or URLs are left as-is and reported as a warning,
so we never fetch anything the user did not ask for.
"""

import json
from typing import Any

from app.docs.types import AuthScheme, Parameter, ParsedDoc, ParsedEndpoint, ResponseInfo, short

METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]
MAX_REF_DEPTH = 8


class SpecError(ValueError):
    pass


def is_openapi(data: Any) -> bool:
    return isinstance(data, dict) and ("openapi" in data or "swagger" in data) and isinstance(data.get("paths"), dict)


class _Resolver:
    def __init__(self, root: dict):
        self.root = root
        self.external_refs: set[str] = set()

    def resolve(self, node: Any, chain: tuple[str, ...] = ()) -> Any:
        """Replace {"$ref": "#/..."} with the referenced object, recursively.

        `chain` is the list of references we are currently inside. It stops loops
        (a schema that refers to itself) and very long reference chains.
        """
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                if not ref.startswith("#/"):
                    self.external_refs.add(ref)
                    return {"$ref": ref}
                if ref in chain:
                    return {"$ref": ref, "note": "refers to itself (recursive)"}
                if len(chain) >= MAX_REF_DEPTH:
                    return {"$ref": ref, "note": "nested too deeply - shortened"}
                target: Any = self.root
                for part in ref[2:].split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    if not isinstance(target, dict) or part not in target:
                        return {"$ref": ref, "note": "reference not found"}
                    target = target[part]
                return self.resolve(target, chain + (ref,))
            return {k: self.resolve(v, chain) for k, v in node.items()}
        if isinstance(node, list):
            return [self.resolve(v, chain) for v in node]
        return node


def _schema_text(schema: Any) -> str:
    if not schema:
        return ""
    return short(json.dumps(schema, indent=2, ensure_ascii=False), 6000)


def _type_of(schema: Any) -> str:
    if not isinstance(schema, dict):
        return ""
    kind = schema.get("type", "")
    if kind == "array" and isinstance(schema.get("items"), dict):
        return f"array of {schema['items'].get('type', 'object')}"
    fmt = schema.get("format")
    return f"{kind} ({fmt})" if kind and fmt else str(kind)


def _auth_schemes(spec: dict) -> list[AuthScheme]:
    raw = (spec.get("components") or {}).get("securitySchemes") or spec.get("securityDefinitions") or {}
    schemes = []
    for name, s in raw.items():
        if not isinstance(s, dict):
            continue
        kind = s.get("type", "")
        details = []
        if kind == "apiKey":
            details.append(f"API key in {s.get('in', '?')} '{s.get('name', '?')}'")
        if kind == "http":
            kind = f"http {s.get('scheme', '')}".strip()
        if kind == "basic":  # Swagger 2
            kind = "http basic"
        if s.get("type") == "oauth2":
            flows = s.get("flows") or {s.get("flow", "flow"): s}
            for flow_name, flow in flows.items():
                if isinstance(flow, dict):
                    parts = [flow_name]
                    for key in ("authorizationUrl", "tokenUrl", "refreshUrl"):
                        if flow.get(key):
                            parts.append(f"{key}={flow[key]}")
                    if flow.get("scopes"):
                        parts.append("scopes: " + ", ".join(list(flow["scopes"])[:15]))
                    details.append("; ".join(parts))
        if s.get("description"):
            details.append(short(s["description"], 500))
        schemes.append(AuthScheme(name=name, type=kind, details=" | ".join(details)))
    return schemes


def _base_urls(spec: dict) -> list[str]:
    if "servers" in spec:
        return [s["url"] for s in spec.get("servers") or [] if isinstance(s, dict) and s.get("url")]
    host = spec.get("host")
    if not host:
        return []
    schemes = spec.get("schemes") or ["https"]
    return [f"{scheme}://{host}{spec.get('basePath', '')}" for scheme in schemes]


def parse_openapi(spec: dict) -> ParsedDoc:
    if not is_openapi(spec):
        raise SpecError("This file is not an OpenAPI/Swagger specification (no 'openapi'/'swagger' and 'paths').")

    resolver = _Resolver(spec)
    info = spec.get("info") or {}
    doc = ParsedDoc(
        title=str(info.get("title", "")),
        version=str(info.get("version", "")),
        base_urls=_base_urls(spec),
        auth_schemes=_auth_schemes(spec),
    )
    global_security = spec.get("security")

    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        shared_params = path_item.get("parameters") or []
        for method in METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            op = resolver.resolve(op)
            params: list[Parameter] = []
            request_body = ""
            for p in resolver.resolve(shared_params) + (op.get("parameters") or []):
                if not isinstance(p, dict):
                    continue
                location = p.get("in", "unknown")
                if location == "body":  # Swagger 2 body parameter
                    request_body = _schema_text(p.get("schema"))
                if location == "formData":
                    location = "form"
                if location not in ("path", "query", "header", "cookie", "body", "form"):
                    location = "unknown"
                params.append(
                    Parameter(
                        name=str(p.get("name", "")),
                        location=location,
                        required=bool(p.get("required", location == "path")),
                        type=_type_of(p.get("schema") or p),
                        description=short(p.get("description", ""), 500),
                    )
                )
            body = op.get("requestBody")
            if isinstance(body, dict):
                for media_type, media in (body.get("content") or {}).items():
                    example = (media or {}).get("example")
                    content = example if example is not None else (media or {}).get("schema")
                    request_body = f"[{media_type}]\n" + _schema_text(content)
                    break

            responses = []
            for status, r in (op.get("responses") or {}).items():
                if not isinstance(r, dict):
                    continue
                example = ""
                for media in (r.get("content") or {}).values():
                    if isinstance(media, dict):
                        example = _schema_text(media.get("example") or media.get("schema"))
                        break
                if not example and r.get("schema"):  # Swagger 2
                    example = _schema_text(r["schema"])
                responses.append(ResponseInfo(status=str(status), description=short(r.get("description", ""), 500), example=example))

            security = op.get("security", global_security)
            auth = ", ".join(name for req in security or [] if isinstance(req, dict) for name in req) if security else ""

            doc.endpoints.append(
                ParsedEndpoint(
                    method=method.upper(),
                    path=str(path),
                    summary=short(op.get("summary") or op.get("operationId") or "", 300),
                    description=short(op.get("description", ""), 2000),
                    auth=auth,
                    parameters=params,
                    request_body=request_body,
                    responses=responses,
                    verification="spec",
                )
            )

    if resolver.external_refs:
        doc.warnings.append(
            f"{len(resolver.external_refs)} reference(s) point to other files and were not loaded, e.g. "
            f"{sorted(resolver.external_refs)[0]}"
        )
    if not doc.endpoints:
        doc.warnings.append("The specification contains no endpoints.")
    return doc
