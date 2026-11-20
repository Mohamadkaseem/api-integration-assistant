"""Collects everything the app knows about a project into one HandoverData object.

No AI is needed. Secrets are never included: authentication is described by type,
data centre and scopes only, and request samples come from the (already redacted)
request history.
"""

import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.ai.requirement_analyzer import RequirementAnalysis
from app.credentials.oauth import ZOHO_ACCOUNTS
from app.design.mermaid import build_mermaid
from app.design.types import DesignStep, Mapping
from app.models.analysis import AnalysisRecord
from app.models.api_doc import ApiDocument, ApiEndpoint
from app.models.credential import Credential
from app.models.design import IntegrationDesign
from app.models.handover import HandoverNotes
from app.models.project import Project
from app.models.request_log import RequestLog
from app.troubleshoot.rules import KNOWN


class EndpointSection(BaseModel):
    step_orders: list[int]
    app: str
    method: str
    path: str
    full_url: str
    summary: str
    verification: str
    auth: str
    parameters: list[dict]
    request_body: str
    responses: list[dict]


class AuthSection(BaseModel):
    app: str
    source: str          # "documentation" or "saved credential"
    description: str


class SampleRequest(BaseModel):
    method: str
    url: str
    status: str
    request_body: str
    response_body: str
    when: str


class ErrorGuide(BaseModel):
    code: str
    meaning: str
    handling: str


class TestCase(BaseModel):
    id: str
    title: str
    preconditions: str
    steps: str
    expected: str
    source: str = "generated"  # generated / ai


class HandoverData(BaseModel):
    project_name: str
    source_app: str
    target_app: str
    status: str
    generated_at: str
    requirement: str
    notes: str
    summary: str = ""
    ai_summary: str = ""
    trigger: str = ""
    expected_outcome: str = ""
    steps: list[DesignStep] = Field(default_factory=list)
    mermaid: str = ""
    conditions: list[str] = Field(default_factory=list)
    status_updates: list[str] = Field(default_factory=list)
    data_to_transfer: list[dict] = Field(default_factory=list)
    endpoints: list[EndpointSection] = Field(default_factory=list)
    authentication: list[AuthSection] = Field(default_factory=list)
    mappings: list[Mapping] = Field(default_factory=list)
    samples: list[SampleRequest] = Field(default_factory=list)
    errors: list[ErrorGuide] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_points: list[str] = Field(default_factory=list)
    has_analysis: bool = False
    has_design: bool = False


ZOHO_ERRORS = ["INVALID_TOKEN", "OAUTH_SCOPE_MISMATCH", "INVALID_DATA", "MANDATORY_NOT_FOUND", "DUPLICATE_DATA", "LIMIT_EXCEEDED", "INTERNAL_ERROR"]


def _full_url(base_urls: list[str], path: str) -> str:
    if path.startswith("http") or path.startswith("{{"):
        variables = {}
        for line in base_urls:
            if line.startswith("{{") and "=" in line:
                name, value = line.split("=", 1)
                variables[name.strip()] = value.strip()
        for name, value in variables.items():
            path = path.replace(name, value)
        return path
    base = next((u for u in base_urls if u.startswith("http")), "")
    return base.rstrip("/") + path


def generate_test_cases(steps: list[DesignStep], trigger: str, has_oauth: bool) -> list[TestCase]:
    """Test cases derived from the workflow: happy path, each decision branch, each wait, plus standard failures."""
    cases: list[TestCase] = []
    n = 0

    def add(title, pre, how, expected):
        nonlocal n
        n += 1
        cases.append(TestCase(id=f"TC-{n:02d}", title=title, preconditions=pre, steps=how, expected=expected))

    unconditional = [s for s in steps if not s.condition]
    add("Happy path", f"Trigger occurs: {trigger or 'start event'}",
        "Run the integration end to end with valid test data.",
        "All steps complete: " + "; ".join(f"{s.app} {s.action}" for s in unconditional[:8]) + ".")
    for s in steps:
        if s.condition:
            add(f"Branch: {s.condition}", f"Test data where '{s.condition}' is true.",
                "Run the integration.", f"Step {s.order} runs ({s.app}: {s.description}); the other branch does not.")
    for s in steps:
        if s.waits_for:
            add(f"Waiting for: {s.waits_for}", f"Step {s.order - 1 if s.order > 1 else s.order} completed.",
                f"Do not let '{s.waits_for}' happen within the expected time.",
                "The integration keeps waiting or times out as designed, and the record status shows it is pending; no later step runs.")
    add("Invalid data rejected", "Test record with a wrong data type or missing mandatory field.",
        "Run the integration.", "The target API returns a validation error (e.g. INVALID_DATA / MANDATORY_NOT_FOUND); it is logged with the field name and nothing partial is left behind.")
    add("Duplicate trigger", "The same source record triggers twice.", "Run the integration twice for the same record.",
        "No duplicate record is created in the target (update/upsert instead), and both runs are logged.")
    if has_oauth:
        add("Expired access token", "Access token expired; refresh token valid.", "Run the integration.",
            "A new access token is obtained automatically and the run succeeds.")
    add("Target API unavailable", "Target API returns 5xx or times out.", "Run the integration.",
        "The failure is logged and the run is retried later without creating duplicates.")
    return cases


def gather(session: Session, project_id: int) -> HandoverData:
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError(f"Project {project_id} not found")

    data = HandoverData(
        project_name=project.name, source_app=project.source_app, target_app=project.target_app, status=project.status.value,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), requirement=project.requirement, notes=project.notes,
    )

    record = session.exec(select(AnalysisRecord).where(AnalysisRecord.project_id == project_id).order_by(AnalysisRecord.id.desc())).first()
    analysis = RequirementAnalysis.model_validate_json(record.result_json) if record else None
    if analysis:
        data.has_analysis = True
        data.summary = analysis.summary
        data.trigger = f"{analysis.trigger.event} ({analysis.trigger.app}, detected by {analysis.trigger.detection})"
        data.expected_outcome = analysis.expected_outcome
        data.conditions = analysis.conditions
        data.status_updates = analysis.status_updates
        data.data_to_transfer = [d.model_dump() for d in analysis.data_to_transfer]
        data.assumptions = list(analysis.assumptions)
        answered = {c["question"] for c in json.loads(record.clarifications_json) if c.get("answer", "").strip()}
        data.open_points += [f"Open question: {q.question}" for q in analysis.clarification_questions if q.question not in answered]

    design = session.exec(select(IntegrationDesign).where(IntegrationDesign.project_id == project_id)).first()
    used_docs: dict[int, ApiDocument] = {}
    if design:
        data.has_design = True
        data.steps = [DesignStep(**s) for s in json.loads(design.steps_json)]
        data.trigger = design.trigger or data.trigger
        data.mappings = [Mapping(**m) for m in json.loads(design.mappings_json)]
        data.open_points += [f"Documentation needed: {m}" for m in json.loads(design.missing_docs_json)]

        # Endpoint sections - one per endpoint used, listing the steps that use it
        by_endpoint: dict[int, list[int]] = {}
        for s in data.steps:
            if s.endpoint_id:
                by_endpoint.setdefault(s.endpoint_id, []).append(s.order)
            elif s.match_status == "no_endpoint":
                data.open_points.append(f"Step {s.order} ({s.app}: {s.description}) has no documented endpoint yet.")
        for endpoint_id, orders in by_endpoint.items():
            ep = session.get(ApiEndpoint, endpoint_id)
            if ep is None:
                continue
            doc = session.get(ApiDocument, ep.document_id)
            used_docs[doc.id] = doc
            data.endpoints.append(EndpointSection(
                step_orders=orders, app=doc.app_name, method=ep.method, path=ep.path,
                full_url=_full_url(json.loads(doc.base_urls_json), ep.path), summary=ep.summary, verification=ep.verification,
                auth=ep.auth, parameters=json.loads(ep.parameters_json), request_body=ep.request_body[:6000],
                responses=[{"status": r.get("status"), "description": r.get("description", ""), "example": (r.get("example") or "")[:3000]}
                           for r in json.loads(ep.responses_json)[:4]],
            ))
            if ep.verification == "unverified":
                data.open_points.append(f"Endpoint {ep.method} {ep.path} is UNVERIFIED - confirm it in the official documentation.")
        for m in data.mappings:
            if m.evidence == "assumed":
                data.open_points.append(f"Mapping {m.source_field} → {m.target_field} is assumed (fields not found in the docs).")
    data.mermaid = build_mermaid(data.trigger, data.steps)

    # Authentication - from documentation and saved credentials (never secrets)
    for doc in used_docs.values():
        for scheme in json.loads(doc.auth_schemes_json):
            data.authentication.append(AuthSection(app=doc.app_name, source="documentation",
                                                   description=f"{scheme.get('name')} ({scheme.get('type')}) {scheme.get('details', '')}".strip()))
    apps = {a.lower() for a in (project.source_app, project.target_app, *(d.app_name for d in used_docs.values())) if a}
    has_oauth = False
    for cred in session.exec(select(Credential)).all():
        if cred.app_name.lower() not in apps and not any(a in cred.app_name.lower() for a in apps if a):
            continue
        public = json.loads(cred.public_json or "{}")
        if cred.type == "oauth2":
            has_oauth = True
            where = f"Zoho {public.get('data_center')} ({ZOHO_ACCOUNTS.get(public.get('data_center', ''), '')})" if public.get("provider") == "zoho" else public.get("token_url", "")
            desc = f"OAuth 2.0 via {where}; scopes: {public.get('scopes') or 'not recorded'}; header prefix '{public.get('token_prefix', 'Bearer')}'; access token refreshed automatically from a refresh token."
        elif cred.type == "api_key":
            desc = f"API key sent in {public.get('key_in')} '{public.get('key_name')}'."
        elif cred.type == "bearer":
            desc = f"Bearer token with prefix '{public.get('token_prefix', 'Bearer')}'."
        else:
            desc = "Basic authentication (username + password)."
        data.authentication.append(AuthSection(app=cred.app_name or cred.name, source=f"saved credential '{cred.name}' ({cred.environment})", description=desc))

    # Sample requests - the project's request history (already redacted when saved)
    for log in session.exec(select(RequestLog).where(RequestLog.project_id == project_id).order_by(RequestLog.id.desc()).limit(6)).all():
        req = json.loads(log.request_json)
        data.samples.append(SampleRequest(method=log.method, url=log.url, status=str(log.status_code or log.error_kind),
                                          request_body=(req.get("body") or "")[:3000], response_body=log.response_body[:3000],
                                          when=log.created_at.strftime("%Y-%m-%d")))

    # Error handling guide
    codes = ZOHO_ERRORS if any("zoho" in a for a in apps) else ["INVALID_TOKEN", "INVALID_DATA", "TOO_MANY_REQUESTS", "INTERNAL_ERROR"]
    for code in codes:
        title, _cat, explanation, _causes, suggestions, retryable = KNOWN[code]
        data.errors.append(ErrorGuide(code=code, meaning=f"{title}: {explanation}",
                                      handling=("Retry with backoff. " if retryable else "Do not retry blindly. ") + "; ".join(suggestions[:2])))

    data.test_cases = generate_test_cases(data.steps, data.trigger, has_oauth) if data.steps else []
    notes = session.exec(select(HandoverNotes).where(HandoverNotes.project_id == project_id)).first()
    if notes:
        data.ai_summary = notes.ai_summary
        data.test_cases += [TestCase(**t, source="ai") for t in json.loads(notes.ai_test_cases_json)]
    if not data.has_analysis:
        data.open_points.insert(0, "No requirement analysis yet - business summary, conditions and data items are missing.")
    if not data.has_design:
        data.open_points.insert(0, "No integration design yet - steps, endpoints and mappings are missing.")
    return data
