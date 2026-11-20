"""Hide secrets before anything is saved or shown in history."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "••••••"
SECRET_NAME = re.compile(r"auth|token|secret|key|cookie|session|password|passwd|signature|credential", re.IGNORECASE)


def is_secret_name(name: str) -> bool:
    return bool(SECRET_NAME.search(name or ""))


def redact_pairs(pairs: list[dict]) -> list[dict]:
    """[{name, value, enabled}] -> same list with secret-looking values masked."""
    return [{**p, "value": MASK if is_secret_name(p.get("name", "")) and p.get("value") else p.get("value", "")} for p in pairs]


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: (MASK if is_secret_name(k) else v) for k, v in headers.items()}


def redact_url(url: str) -> str:
    """Mask secret-looking query parameters (e.g. ?api_key=...) and user:password@ in a URL."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        netloc = MASK + "@" + netloc.split("@", 1)[1]
    query = urlencode([(k, MASK if is_secret_name(k) else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)])
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


# Field names inside JSON / form bodies whose values are secrets (OAuth token responses, login bodies, ...).
SECRET_FIELD = re.compile(
    r"^(access_?token|refresh_?token|id_?token|token|auth_?token|client_?secret|secret|password|passwd|"
    r"api_?key|apikey|private_?key|authorization|cookie|session(_?id)?|signature)$",
    re.IGNORECASE,
)


def _mask_json(value):
    if isinstance(value, dict):
        return {k: (MASK if SECRET_FIELD.match(str(k)) and v not in (None, "") else _mask_json(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_json(v) for v in value]
    return value


def redact_body(text: str, known_secrets: list[str] | None = None) -> str:
    """Mask secrets in a request/response body before it is saved.

    1. Every secret value used for this request (token, password, key...) is replaced wherever it appears.
    2. JSON or form fields with secret names (access_token, refresh_token, client_secret, password...) are masked.
    """
    import json

    if not text:
        return text
    for secret in sorted({s for s in (known_secrets or []) if s and len(s) >= 4}, key=len, reverse=True):
        text = text.replace(secret, MASK)
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            return json.dumps(_mask_json(json.loads(text)), indent=2, ensure_ascii=False)
        except ValueError:
            return text
    if "=" in text and "\n" not in text.strip() and " " not in text.strip():
        pairs = parse_qsl(text, keep_blank_values=True)
        if pairs:
            return urlencode([(k, MASK if SECRET_FIELD.match(k) else v) for k, v in pairs])
    return text
