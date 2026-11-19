"""Reads Postman Collection v2.0 / v2.1 files with plain code (no AI)."""

import json
from typing import Any

from app.docs.types import AuthScheme, Parameter, ParsedDoc, ParsedEndpoint, ResponseInfo, short

MAX_ITEMS = 2000


def is_postman(data: Any) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("item"), list):
        return False
    info = data.get("info") or {}
    return "_postman_id" in info or "postman" in str(info.get("schema", ""))


def _text(value: Any) -> str:
    if isinstance(value, dict):  # description objects: {"content": "...", "type": "text/markdown"}
        return str(value.get("content", ""))
    return str(value or "")


def _url_parts(url: Any) -> tuple[str, list[Parameter]]:
    """Return (path-or-raw-url, query/path parameters)."""
    if isinstance(url, str):
        return url, []
    if not isinstance(url, dict):
        return "", []
    raw = str(url.get("raw", ""))
    path = url.get("path")
    if isinstance(path, list):
        host = url.get("host")
        host_text = ".".join(host) if isinstance(host, list) else str(host or "")
        shown = (host_text + "/" if host_text else "/") + "/".join(str(p) for p in path)
    else:
        shown = raw.split("?")[0] or raw
    params = [
        Parameter(name=str(q.get("key", "")), location="query", description=_text(q.get("description")),
                  required=not q.get("disabled", False))
        for q in url.get("query") or []
        if isinstance(q, dict)
    ]
    params += [
        Parameter(name=str(v.get("key", "")), location="path", required=True, description=_text(v.get("description")))
        for v in url.get("variable") or []
        if isinstance(v, dict)
    ]
    return shown, params


def _auth_text(auth: Any) -> str:
    if not isinstance(auth, dict) or not auth.get("type"):
        return ""
    kind = auth["type"]
    # Never copy values (they may contain real tokens) - only which keys are used.
    details = auth.get(kind)
    keys = []
    if isinstance(details, list):
        keys = [str(d.get("key")) for d in details if isinstance(d, dict) and d.get("key")]
    return f"{kind}" + (f" ({', '.join(keys)})" if keys else "")


def _body_text(body: Any) -> tuple[str, list[Parameter]]:
    if not isinstance(body, dict):
        return "", []
    mode = body.get("mode")
    if mode == "raw":
        return short(body.get("raw", ""), 6000), []
    if mode in ("urlencoded", "formdata"):
        fields = [
            Parameter(name=str(f.get("key", "")), location="form", type=str(f.get("type", "")),
                      description=_text(f.get("description")))
            for f in body.get(mode) or []
            if isinstance(f, dict)
        ]
        return "", fields
    if mode == "graphql":
        return short(json.dumps(body.get("graphql"), indent=2), 6000), []
    return "", []


def parse_postman(data: dict) -> ParsedDoc:
    info = data.get("info") or {}
    doc = ParsedDoc(title=str(info.get("name", "")), version=str(info.get("version", "")))

    collection_auth = _auth_text(data.get("auth"))
    if collection_auth:
        doc.auth_schemes.append(AuthScheme(name="collection", type=collection_auth.split(" ")[0], details=collection_auth))
    for var in data.get("variable") or []:
        if isinstance(var, dict) and "url" in str(var.get("key", "")).lower():
            doc.base_urls.append(f"{{{{{var.get('key')}}}}} = {var.get('value', '')}")

    count = 0

    def walk(items: list, inherited_auth: str, folder: str) -> None:
        nonlocal count
        for item in items:
            if count >= MAX_ITEMS or not isinstance(item, dict):
                continue
            auth = _auth_text(item.get("auth")) or inherited_auth
            if isinstance(item.get("item"), list):  # a folder
                walk(item["item"], auth, f"{folder}{item.get('name', '')} / ")
                continue
            request = item.get("request")
            if isinstance(request, str):
                request = {"method": "GET", "url": request}
            if not isinstance(request, dict):
                continue
            method = str(request.get("method", "GET")).upper()
            if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                continue
            path, params = _url_parts(request.get("url"))
            params += [
                # Header names only; values may be secrets.
                Parameter(name=str(h.get("key", "")), location="header", description=_text(h.get("description")))
                for h in request.get("header") or []
                if isinstance(h, dict)
            ]
            body, form_fields = _body_text(request.get("body"))
            responses = [
                ResponseInfo(status=str(r.get("code", "")), description=str(r.get("name", "")), example=short(r.get("body", ""), 4000))
                for r in item.get("response") or []
                if isinstance(r, dict)
            ]
            doc.endpoints.append(
                ParsedEndpoint(
                    method=method,
                    path=path,
                    summary=short(f"{folder}{item.get('name', '')}", 300),
                    description=short(_text(request.get("description")), 2000),
                    auth=_auth_text(request.get("auth")) or auth,
                    parameters=params + form_fields,
                    request_body=body,
                    responses=responses,
                    verification="spec",
                )
            )
            count += 1

    walk(data["item"], collection_auth, "")
    if count >= MAX_ITEMS:
        doc.warnings.append(f"Only the first {MAX_ITEMS} requests were imported.")
    if not doc.endpoints:
        doc.warnings.append("The collection contains no requests.")
    return doc
