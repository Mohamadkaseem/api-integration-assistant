import json
from pathlib import Path

import pytest

from app.docs.importer import import_documentation
from app.docs.openapi_parser import SpecError, parse_openapi
from app.docs.postman_parser import parse_postman
from app.docs.text_extract import ExtractError, html_to_text, pdf_to_text

FIXTURES = Path(__file__).parent / "fixtures"


def no_ai():
    raise AssertionError("AI must not be used for machine-readable specs")


def make_pdf(text: str) -> bytes:
    """Build a tiny but valid one-page PDF containing `text` (no extra libraries needed)."""
    stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_openapi3_endpoints_auth_and_refs():
    doc = parse_openapi(json.loads((FIXTURES / "openapi3.json").read_text()))
    assert doc.title == "Demo Sign API"
    assert doc.base_urls == ["https://sign.example.com/api/v1"]
    by_key = {(e.method, e.path): e for e in doc.endpoints}
    create = by_key[("POST", "/requests")]
    assert create.verification == "spec"
    assert "recipient_email" in create.request_body  # nested $ref was resolved
    assert create.auth == "oauth"
    get = by_key[("GET", "/requests/{request_id}")]
    assert get.parameters[0].name == "request_id" and get.parameters[0].required  # path-level parameter
    assert {r.status for r in get.responses} == {"200", "404"}
    oauth = doc.auth_schemes[0]
    assert "tokenUrl=https://accounts.example.com/oauth/v2/token" in oauth.details
    assert "sign.requests.CREATE" in oauth.details
    assert any("other files" in w for w in doc.warnings)  # external $ref reported, not fetched


def test_swagger2_yaml_via_importer():
    data = (FIXTURES / "swagger2.yaml").read_bytes()
    doc, kind = import_documentation(data, filename="crm.yaml", get_provider=no_ai, source_label="crm.yaml")
    assert kind == "openapi"
    assert doc.base_urls == ["https://crm.example.com/v2"]
    assert doc.auth_schemes[0].details == "API key in header 'X-API-Key'"
    create = next(e for e in doc.endpoints if e.method == "POST")
    assert "Account_Name" in create.request_body


def test_postman_collection_without_leaking_secrets():
    data = (FIXTURES / "postman.json").read_bytes()
    doc, kind = import_documentation(data, filename="c.json", get_provider=no_ai, source_label="c.json")
    assert kind == "postman"
    assert [e.method for e in doc.endpoints] == ["POST", "GET"]
    upsert = doc.endpoints[0]
    assert upsert.path == "{{base_url}}/Accounts/upsert"
    assert upsert.summary == "Accounts / Upsert account"
    assert upsert.auth.startswith("bearer")
    assert upsert.responses[0].status == "200"
    get = doc.endpoints[1]
    assert {(p.name, p.location) for p in get.parameters} >= {("fields", "query"), ("id", "path")}
    everything = doc.model_dump_json()
    assert "SECRET-TOKEN-123" not in everything
    assert "SECRET-HEADER-456" not in everything


def test_not_a_spec_is_rejected():
    with pytest.raises(SpecError):
        parse_openapi({"hello": "world"})


def test_pdf_text_is_extracted():
    text, warnings = pdf_to_text(make_pdf("POST /api/v1/requests creates a signing request. " * 4))
    assert "POST /api/v1/requests" in text
    assert warnings == []


def test_scanned_pdf_without_text_is_explained():
    with pytest.raises(ExtractError, match="scanned"):
        pdf_to_text(make_pdf(""))


def test_html_to_text_drops_scripts_and_menus():
    title, text = html_to_text(
        "<html><head><title>Docs</title><script>var secret=1</script></head>"
        "<body><nav>Menu</nav><h1>Create request</h1><pre>POST /requests</pre></body></html>"
    )
    assert title == "Docs"
    assert "POST /requests" in text and "secret" not in text and "Menu" not in text


def test_javascript_only_page_gives_helpful_message():
    with pytest.raises(ExtractError, match="JavaScript"):
        import_documentation(b"<html><body><div id='app'></div></body></html>", get_provider=no_ai, source_label="x")


def test_self_referencing_schema_does_not_loop_forever():
    spec = {
        "openapi": "3.0.0", "info": {"title": "T"},
        "components": {"schemas": {"Node": {"type": "object", "properties": {"child": {"$ref": "#/components/schemas/Node"}}}}},
        "paths": {"/tree": {"post": {"requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Node"}}}},
                                     "responses": {"200": {"description": "OK"}}}}},
    }
    doc = parse_openapi(spec)
    assert "recursive" in doc.endpoints[0].request_body
