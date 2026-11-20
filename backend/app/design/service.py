"""Design logic: candidates, validation of AI choices, documentation checks."""

import json
import re

from sqlmodel import Session, select

from app.design.types import DesignStep, Mapping
from app.models.api_doc import ApiDocument, ApiEndpoint

MAX_CANDIDATES = 400


def endpoint_label(ep: ApiEndpoint) -> str:
    return f"{ep.method} {ep.path}"


def endpoints_for_docs(session: Session, doc_ids: list[int]) -> list[tuple[ApiEndpoint, ApiDocument]]:
    if not doc_ids:
        return []
    docs = {d.id: d for d in session.exec(select(ApiDocument).where(ApiDocument.id.in_(doc_ids))).all()}
    rows = session.exec(select(ApiEndpoint).where(ApiEndpoint.document_id.in_(list(docs)))).all()
    return [(ep, docs[ep.document_id]) for ep in rows]


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def pick_candidates(pairs: list[tuple[ApiEndpoint, ApiDocument]], steps: list[DesignStep], limit: int = MAX_CANDIDATES):
    """Big specs (1,000+ endpoints) are cut down to the most relevant ones by simple word overlap."""
    if len(pairs) <= limit:
        return pairs
    wanted = set()
    for s in steps:
        wanted |= _words(f"{s.app} {s.action} {s.description}")

    def score(pair):
        ep, doc = pair
        return len(wanted & _words(f"{doc.app_name} {ep.path} {ep.summary}"))

    return sorted(pairs, key=score, reverse=True)[:limit]


def candidate_line(ep: ApiEndpoint, doc: ApiDocument) -> str:
    trust = {"spec": "verified", "quoted": "quoted", "unverified": "UNVERIFIED"}.get(ep.verification, ep.verification)
    return f"{ep.id} | {doc.app_name} | {ep.method} {ep.path} | {ep.summary[:120]} | {trust}"


def apply_choices(steps: list[DesignStep], choices, allowed: dict[int, ApiEndpoint]) -> list[DesignStep]:
    """Put the AI's endpoint choices on the steps - rejecting any ID that is not in our candidate list."""
    by_order = {c.step_order: c for c in choices}
    out = []
    for step in steps:
        choice = by_order.get(step.order)
        if step.match_status == "manual" or choice is None:
            out.append(step)
            continue
        if choice.endpoint_id and choice.endpoint_id in allowed:
            ep = allowed[choice.endpoint_id]
            out.append(step.model_copy(update={"endpoint_id": ep.id, "endpoint_label": endpoint_label(ep),
                                               "match_status": "matched", "match_note": choice.reason}))
        elif choice.endpoint_id:
            out.append(step.model_copy(update={"endpoint_id": None, "endpoint_label": "", "match_status": "no_endpoint",
                                               "match_note": "The AI proposed an endpoint that is not in your imported "
                                               "documentation, so it was rejected. Import the right docs or pick one manually."}))
        else:
            needs_api = step.action not in ("decide", "wait", "log")
            out.append(step.model_copy(update={"endpoint_id": None, "endpoint_label": "",
                                               "match_status": "no_endpoint" if needs_api else "unmatched",
                                               "match_note": choice.reason}))
    return out


def endpoint_doc(ep: ApiEndpoint, doc: ApiDocument) -> dict:
    return {
        "app": doc.app_name, "method": ep.method, "path": ep.path, "summary": ep.summary,
        "parameters": json.loads(ep.parameters_json), "request_body": ep.request_body[:8000],
        "responses": [{"status": r.get("status"), "example": (r.get("example") or "")[:6000]} for r in json.loads(ep.responses_json)[:4]],
    }


def _field_tokens(field: str) -> list[str]:
    """'properties.name' -> ['properties', 'name']; 'data[0].Account_Name' -> ['data', 'Account_Name']"""
    return [t for t in re.split(r"[.\[\]\s]+", field) if t and not t.isdigit()]


def check_mappings(mappings, docs_text_by_app: dict[str, str]) -> list[Mapping]:
    """A mapping is 'documented' only if BOTH field names appear in that app's endpoint documentation."""
    out = []
    for m in mappings:
        def found(app: str, field: str) -> bool:
            text = docs_text_by_app.get(app.strip().lower(), "")
            tokens = _field_tokens(field)
            return bool(text and tokens and re.search(r"(?<![\w])" + re.escape(tokens[-1]) + r"(?![\w])", text))

        documented = found(m.source_app, m.source_field) and found(m.target_app, m.target_field)
        out.append(Mapping(**m.model_dump(), evidence="documented" if documented else "assumed"))
    return out
