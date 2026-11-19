"""Works out what kind of documentation we received and sends it to the right reader.

  OpenAPI / Swagger (JSON or YAML)  -> openapi_parser  (code, verified)
  Postman collection (JSON)         -> postman_parser  (code, verified)
  PDF                               -> text -> AI extractor (quote-checked)
  Web page (HTML)                   -> text -> AI extractor (quote-checked)
  Anything else (plain text, JSON examples) -> AI extractor (quote-checked)
"""

import json
from collections.abc import Callable
from typing import Literal

import yaml

from app.ai.provider import AIProvider
from app.docs.ai_extractor import extract_with_ai
from app.docs.openapi_parser import is_openapi, parse_openapi
from app.docs.postman_parser import is_postman, parse_postman
from app.docs.text_extract import ExtractError, html_to_text, pdf_to_text
from app.docs.types import ParsedDoc

SourceType = Literal["openapi", "postman", "pdf", "html", "text"]
MIN_WEB_TEXT = 500


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _looks_like_html(text: str, content_type: str) -> bool:
    head = text.lstrip()[:200].lower()
    return "html" in content_type or head.startswith("<!doctype html") or head.startswith("<html")


def _try_structured(text: str, filename: str) -> dict | None:
    """Parse JSON, or YAML when it looks like an OpenAPI/Swagger file. None if neither."""
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    looks_yaml = filename.lower().endswith((".yaml", ".yml")) or any(
        line.startswith(("openapi:", "swagger:")) for line in text.splitlines()[:50]
    )
    if looks_yaml:
        try:
            # Safe loaders never run code embedded in YAML. The C version is ~10x faster when installed.
            loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
            data = yaml.load(text, Loader=loader)  # noqa: S506 - loader is always a *safe* loader
        except yaml.YAMLError as exc:
            raise ExtractError(f"This YAML file could not be read: {exc.__class__.__name__}.") from exc
        return data if isinstance(data, dict) else None
    return None


def import_documentation(
    data: bytes,
    *,
    filename: str = "",
    content_type: str = "",
    get_provider: Callable[[], AIProvider],
    source_label: str,
) -> tuple[ParsedDoc, SourceType]:
    if not data.strip():
        raise ExtractError("The document is empty.")

    if data[:5] == b"%PDF-":
        text, warnings = pdf_to_text(data)
        doc = extract_with_ai(get_provider(), text, source_label)
        doc.warnings = warnings + doc.warnings
        return doc, "pdf"

    text = _decode(data)

    structured = _try_structured(text, filename)
    if structured is not None:
        if is_openapi(structured):
            return parse_openapi(structured), "openapi"
        if is_postman(structured):
            return parse_postman(structured), "postman"

    if _looks_like_html(text, content_type):
        title, page_text = html_to_text(text)
        if len(page_text) < MIN_WEB_TEXT:
            raise ExtractError(
                "This web page contains almost no readable text - it is probably built with JavaScript. "
                "Open it in your browser and save it as PDF (Ctrl + P -> Save as PDF), or copy the text and paste it."
            )
        doc = extract_with_ai(get_provider(), page_text, source_label)
        doc.title = doc.title or title
        return doc, "html"

    return extract_with_ai(get_provider(), text, source_label), "text"
