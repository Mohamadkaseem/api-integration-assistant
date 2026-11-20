"""Renders HandoverData as Markdown and as a Word document."""

import base64
import io
import json

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from app.handover.data import HandoverData

TRUST = {"spec": "verified (from spec)", "quoted": "quoted from document", "unverified": "UNVERIFIED"}


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    def esc(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "_None._"


def _code(text: str, lang: str = "") -> str:
    if not text:
        return ""
    try:
        if lang == "json" or text.strip()[:1] in "{[":
            text, lang = json.dumps(json.loads(text), indent=2, ensure_ascii=False), "json"
    except ValueError:
        pass
    return f"```{lang}\n{text}\n```"


def to_markdown(d: HandoverData) -> str:
    out = [f"# {d.project_name} — Developer Handover", "",
           f"**Source:** {d.source_app or '—'} · **Target:** {d.target_app or '—'} · **Status:** {d.status} · **Generated:** {d.generated_at}", ""]

    out += ["## 1. Overview", ""]
    if d.ai_summary:
        out += [d.ai_summary, ""]
    if d.summary:
        out += [f"**Use case:** {d.summary}", ""]
    out += ["**Business requirement (as given):**", "", f"> {d.requirement or '_Not written yet._'}", ""]
    if d.expected_outcome:
        out += [f"**Expected outcome:** {d.expected_outcome}", ""]
    if d.notes:
        out += [f"**Notes:** {d.notes}", ""]

    out += ["## 2. Trigger & workflow", "", f"**Trigger:** {d.trigger or '_Not defined._'}", ""]
    if d.steps:
        out += [_md_table(["#", "App", "Action", "Description", "Only when", "Waits for", "Endpoint"],
                          [[s.order, s.app, s.action, s.description, s.condition, s.waits_for,
                            s.endpoint_label or ("⚠ none documented" if s.match_status == "no_endpoint" else "—")] for s in d.steps]), ""]
        out += ["```mermaid", d.mermaid, "```", ""]
    else:
        out += ["_No steps designed yet._", ""]
    if d.conditions:
        out += ["**Conditions & business rules:**", _bullets(d.conditions), ""]
    if d.status_updates:
        out += ["**Status updates:**", _bullets(d.status_updates), ""]

    out += ["## 3. API endpoints", ""]
    if not d.endpoints:
        out += ["_No endpoints chosen yet._", ""]
    for i, e in enumerate(d.endpoints, start=1):
        out += [f"### 3.{i} {e.method} {e.path}", "",
                f"- **App:** {e.app} · **Used in step(s):** {', '.join(map(str, e.step_orders))} · **Trust:** {TRUST.get(e.verification, e.verification)}",
                f"- **URL:** `{e.full_url}`"]
        if e.summary:
            out.append(f"- **Purpose:** {e.summary}")
        if e.auth:
            out.append(f"- **Auth:** {e.auth}")
        out.append("")
        if e.parameters:
            out += [_md_table(["Parameter", "In", "Type", "Required", "Description"],
                              [[p.get("name"), p.get("location"), p.get("type", ""), "yes" if p.get("required") else "", p.get("description", "")] for p in e.parameters]), ""]
        if e.request_body:
            out += ["**Request body:**", "", _code(e.request_body.replace("[application/json]\n", "")), ""]
        for r in e.responses:
            out += [f"**Response {r['status']}** {r.get('description') or ''}", ""]
            if r.get("example"):
                out += [_code(r["example"]), ""]

    out += ["## 4. Authentication", "", "_Secrets are never included in this document._", ""]
    out += [_md_table(["App", "Source", "Details"], [[a.app, a.source, a.description] for a in d.authentication]) if d.authentication else "_No authentication information recorded._", ""]

    out += ["## 5. Field mapping", ""]
    if d.mappings:
        out += [_md_table(["Source", "Source field", "Target", "Target field", "Transformation", "Required", "Issue", "Evidence"],
                          [[m.source_app, f"`{m.source_field}`", m.target_app, f"`{m.target_field}`", m.transform, "yes" if m.required else "", m.issue, m.evidence] for m in d.mappings]), ""]
    elif d.data_to_transfer:
        out += ["Data identified in the requirement (field-level mapping not done yet):", "",
                _md_table(["Data", "From", "To", "Notes"], [[x["name"], x["from_app"], x["to_app"], x.get("notes", "")] for x in d.data_to_transfer]), ""]
    else:
        out += ["_No mappings yet._", ""]

    out += ["## 6. Error handling", "", _md_table(["Error", "Meaning", "Handling"], [[f"`{e.code}`", e.meaning, e.handling] for e in d.errors]), ""]

    out += ["## 7. Test cases", ""]
    out += [_md_table(["ID", "Test", "Preconditions", "Steps", "Expected result"],
                      [[t.id + (" (AI)" if t.source == "ai" else ""), t.title, t.preconditions, t.steps, t.expected] for t in d.test_cases]) if d.test_cases else "_Add workflow steps to generate test cases._", ""]

    if d.samples:
        out += ["## 8. Sample requests (from testing)", "", "_Captured in the Request Builder; secrets were masked when saved._", ""]
        for s in d.samples:
            out += [f"**{s.method}** `{s.url}` → **{s.status}** ({s.when})", ""]
            if s.request_body:
                out += [_code(s.request_body), ""]
            if s.response_body:
                out += ["Response:", "", _code(s.response_body), ""]

    out += ["## 9. Assumptions & open points", "", "**Assumptions:**", _bullets(d.assumptions), "", "**Open points:**", _bullets(d.open_points), ""]
    return "\n".join(out)


# ---------- Word ----------

def _cell_text(cell, text: str, bold: bool = False, size: int = 9) -> None:
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)


def _table(doc, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        _cell_text(table.rows[0].cells[i], h, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            _cell_text(cells[i], value)
    doc.add_paragraph()


def _code_para(doc, text: str) -> None:
    if not text:
        return
    try:
        if text.strip()[:1] in "{[":
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError:
        pass
    p = doc.add_paragraph()
    run = p.add_run(text[:4000])
    run.font.name = "Consolas"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)


def _bullet_list(doc, items) -> None:
    if not items:
        doc.add_paragraph("None.")
    for item in items:
        doc.add_paragraph(str(item), style="List Bullet")


def to_docx(d: HandoverData, diagram_png_base64: str | None = None) -> bytes:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.8)

    title = doc.add_heading(f"{d.project_name}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    doc.add_paragraph(f"Developer handover · Source: {d.source_app or '—'} · Target: {d.target_app or '—'} · Status: {d.status} · Generated: {d.generated_at}")

    doc.add_heading("1. Overview", level=1)
    if d.ai_summary:
        doc.add_paragraph(d.ai_summary)
    if d.summary:
        doc.add_paragraph().add_run("Use case: ").bold = True
        doc.paragraphs[-1].add_run(d.summary)
    p = doc.add_paragraph()
    p.add_run("Business requirement (as given): ").bold = True
    doc.add_paragraph(d.requirement or "Not written yet.", style="Intense Quote")
    if d.expected_outcome:
        p = doc.add_paragraph()
        p.add_run("Expected outcome: ").bold = True
        p.add_run(d.expected_outcome)

    doc.add_heading("2. Trigger & workflow", level=1)
    p = doc.add_paragraph()
    p.add_run("Trigger: ").bold = True
    p.add_run(d.trigger or "Not defined.")
    if diagram_png_base64:
        try:
            doc.add_picture(io.BytesIO(base64.b64decode(diagram_png_base64)), width=Inches(5.5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception:  # an unreadable image must not break the export
            doc.add_paragraph("(Diagram image could not be added.)")
    if d.steps:
        _table(doc, ["#", "App", "Action", "Description", "Only when", "Waits for", "Endpoint"],
               [[s.order, s.app, s.action, s.description, s.condition, s.waits_for,
                 s.endpoint_label or ("none documented" if s.match_status == "no_endpoint" else "—")] for s in d.steps])
    if d.conditions:
        doc.add_paragraph().add_run("Conditions & business rules").bold = True
        _bullet_list(doc, d.conditions)
    if d.status_updates:
        doc.add_paragraph().add_run("Status updates").bold = True
        _bullet_list(doc, d.status_updates)

    doc.add_heading("3. API endpoints", level=1)
    if not d.endpoints:
        doc.add_paragraph("No endpoints chosen yet.")
    for i, e in enumerate(d.endpoints, start=1):
        doc.add_heading(f"3.{i} {e.method} {e.path}", level=2)
        doc.add_paragraph(f"App: {e.app} · Step(s): {', '.join(map(str, e.step_orders))} · Trust: {TRUST.get(e.verification, e.verification)}")
        doc.add_paragraph(f"URL: {e.full_url}")
        if e.summary:
            doc.add_paragraph(f"Purpose: {e.summary}")
        if e.parameters:
            _table(doc, ["Parameter", "In", "Type", "Required", "Description"],
                   [[p.get("name"), p.get("location"), p.get("type", ""), "yes" if p.get("required") else "", p.get("description", "")] for p in e.parameters])
        if e.request_body:
            doc.add_paragraph().add_run("Request body").bold = True
            _code_para(doc, e.request_body.replace("[application/json]\n", ""))
        for r in e.responses:
            doc.add_paragraph().add_run(f"Response {r['status']} {r.get('description') or ''}").bold = True
            _code_para(doc, r.get("example") or "")

    doc.add_heading("4. Authentication", level=1)
    doc.add_paragraph("Secrets are never included in this document.")
    if d.authentication:
        _table(doc, ["App", "Source", "Details"], [[a.app, a.source, a.description] for a in d.authentication])
    else:
        doc.add_paragraph("No authentication information recorded.")

    doc.add_heading("5. Field mapping", level=1)
    if d.mappings:
        _table(doc, ["Source", "Source field", "Target", "Target field", "Transformation", "Req.", "Issue", "Evidence"],
               [[m.source_app, m.source_field, m.target_app, m.target_field, m.transform, "yes" if m.required else "", m.issue, m.evidence] for m in d.mappings])
    elif d.data_to_transfer:
        _table(doc, ["Data", "From", "To", "Notes"], [[x["name"], x["from_app"], x["to_app"], x.get("notes", "")] for x in d.data_to_transfer])
    else:
        doc.add_paragraph("No mappings yet.")

    doc.add_heading("6. Error handling", level=1)
    _table(doc, ["Error", "Meaning", "Handling"], [[e.code, e.meaning, e.handling] for e in d.errors])

    doc.add_heading("7. Test cases", level=1)
    if d.test_cases:
        _table(doc, ["ID", "Test", "Preconditions", "Steps", "Expected"],
               [[t.id + (" (AI)" if t.source == "ai" else ""), t.title, t.preconditions, t.steps, t.expected] for t in d.test_cases])
    else:
        doc.add_paragraph("Add workflow steps to generate test cases.")

    if d.samples:
        doc.add_heading("8. Sample requests (from testing)", level=1)
        doc.add_paragraph("Captured in the Request Builder; secrets were masked when saved.")
        for s in d.samples:
            doc.add_paragraph().add_run(f"{s.method} {s.url} → {s.status} ({s.when})").bold = True
            _code_para(doc, s.request_body)
            _code_para(doc, s.response_body)

    doc.add_heading("9. Assumptions & open points", level=1)
    doc.add_paragraph().add_run("Assumptions").bold = True
    _bullet_list(doc, d.assumptions)
    doc.add_paragraph().add_run("Open points").bold = True
    _bullet_list(doc, d.open_points)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
