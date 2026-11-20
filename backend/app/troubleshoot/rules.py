"""Built-in error knowledge base - explains API errors instantly, without AI.

It reads the response body, pulls out error codes, messages and field names in
the formats used by Zoho, HubSpot, OAuth servers and most REST APIs, and matches
them against known errors. Anything it does not recognise falls back to an
explanation of the HTTP status code.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["auth", "permission", "validation", "not_found", "conflict", "rate_limit", "server",
                   "network", "redirect", "method", "unknown"]


class Diagnosis(BaseModel):
    title: str
    category: Category
    explanation: str
    likely_causes: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error_code: str = ""          # e.g. INVALID_DATA, invalid_grant
    error_message: str = ""       # the server's own message
    fields: list[str] = Field(default_factory=list)  # fields named in the error (e.g. Account_Name)
    retryable: bool = False       # worth simply retrying later?
    matched: str = ""             # which rule matched (for transparency)


class ExtractedError(BaseModel):
    codes: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    expected_types: list[str] = Field(default_factory=list)
    hubspot_category: str = ""


FIELD_KEYS = ("api_name", "field", "fieldName", "field_name", "param", "parameter", "name", "property", "propertyName", "path")


def extract(body: str) -> ExtractedError:
    """Collect codes, messages and field names from a JSON error body (any common shape)."""
    out = ExtractedError()
    try:
        data = json.loads(body) if body.strip()[:1] in ("{", "[") else None
    except ValueError:
        data = None
    if data is None:
        text = body.strip()
        if text:
            out.messages.append(text[:500])
        return out

    def walk(node, depth=0):
        if depth > 6:
            return
        if isinstance(node, dict):
            for key in ("code", "error", "error_code", "errorCode", "subCategory", "type"):
                value = node.get(key)
                if isinstance(value, str) and value and len(value) < 80 and value not in out.codes:
                    out.codes.append(value)
            if isinstance(node.get("category"), str):
                out.hubspot_category = out.hubspot_category or node["category"]
            for key in ("message", "error_description", "detail", "description", "msg"):
                value = node.get(key)
                if isinstance(value, str) and value and value not in out.messages:
                    out.messages.append(value[:500])
            details = node.get("details") if isinstance(node.get("details"), dict) else {}
            context = node.get("context") if isinstance(node.get("context"), dict) else {}

            def add_field(value):
                values = value if isinstance(value, list) else [value]
                for v in values:
                    if isinstance(v, str) and v and len(v) < 100 and v not in out.fields:
                        out.fields.append(v)

            # Error details/context name the field explicitly (Zoho: details.api_name, HubSpot: context.propertyName)
            for source in (details, context):
                for key in FIELD_KEYS:
                    if key in source:
                        add_field(source[key])
            # Directly on the error object, only unambiguous field keys
            for key in ("field", "fieldName", "field_name", "propertyName", "api_name"):
                if key in node:
                    add_field(node[key])
            if isinstance(details.get("expected_data_type"), str):
                out.expected_types.append(details["expected_data_type"])
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node[:50]:
                walk(item, depth + 1)

    walk(data)
    # Field names quoted inside messages, e.g. "Invalid value for field 'Phone'"
    for message in out.messages:
        for match in re.findall(r"(?:field|property|parameter)\s+['\"`]([A-Za-z_][\w.]*)['\"`]", message, re.IGNORECASE):
            if match not in out.fields:
                out.fields.append(match)
    return out


# ---------- Known error codes ----------
# code -> (title, category, explanation, causes, suggestions, retryable)

KNOWN: dict[str, tuple[str, str, str, list[str], list[str], bool]] = {
    # Zoho (CRM and other Zoho APIs share many codes)
    "INVALID_DATA": ("Invalid value for a field", "validation",
        "The server understood the request, but a value you sent is not acceptable for that field.",
        ["Wrong data type (text where a number, date or lookup ID is expected)",
         "Picklist value that does not exist in the target system", "A record ID that does not exist",
         "Date/time in the wrong format (Zoho expects yyyy-MM-dd and yyyy-MM-ddTHH:mm:ss±HH:mm)"],
        ["Check the field named in the error and its expected data type", "For picklists, use one of the exact allowed values",
         "For lookups, send the related record's ID (e.g. {\"id\": \"...\"}), not its name"], False),
    "MANDATORY_NOT_FOUND": ("Required field missing", "validation",
        "A field that the target system requires was not included in the request.",
        ["The field is mandatory in the module layout", "The field name is misspelled (API names are case-sensitive)"],
        ["Add the field named in the error to the request body", "Use the field's API name, e.g. Last_Name, not the label"], False),
    "DUPLICATE_DATA": ("Duplicate record", "conflict",
        "A record with the same unique value already exists.",
        ["A field marked 'unique' (or the duplicate-check field) already has this value"],
        ["Update the existing record instead (its ID is usually in the error details)",
         "Or use the upsert endpoint with duplicate_check_fields"], False),
    "INVALID_TOKEN": ("Access token not accepted", "auth",
        "The access token is invalid or expired.",
        ["The token expired (Zoho access tokens last 1 hour)", "The token belongs to a different data centre",
         "Wrong Authorization format - Zoho expects 'Zoho-oauthtoken <token>'"],
        ["Use a saved OAuth credential so the token is refreshed automatically", "Check the API domain matches the account's data centre (e.g. zohoapis.in)"], False),
    "AUTHENTICATION_FAILURE": ("Authentication failed", "auth",
        "The server could not authenticate the request.",
        ["Missing or malformed Authorization header", "Token from another data centre or organisation"],
        ["Select the saved credential in the Auth tab", "Check the token prefix (Zoho-oauthtoken for Zoho)"], False),
    "OAUTH_SCOPE_MISMATCH": ("Token lacks the required scope", "permission",
        "The access token is valid, but it was not granted permission for this API.",
        ["The scopes chosen when generating the code do not cover this module or action"],
        ["Generate a new code including the needed scope (e.g. ZohoCRM.modules.ALL) and Reconnect the credential"], False),
    "NO_PERMISSION": ("No permission", "permission",
        "The user behind the token is not allowed to do this.",
        ["The Zoho user's role/profile lacks access to the module or field"],
        ["Ask an administrator to grant the permission, or use a user with access"], False),
    "INVALID_MODULE": ("Unknown module", "not_found",
        "The module name in the URL does not exist.",
        ["Module API name misspelled (e.g. 'Account' instead of 'Accounts')", "Custom module referenced by label instead of API name"],
        ["Use the module's API name - list them with GET /crm/v3/settings/modules"], False),
    "INVALID_URL_PATTERN": ("Wrong URL", "not_found",
        "The URL path does not match any API endpoint.",
        ["Typo in the path or wrong API version", "Wrong domain for the data centre"],
        ["Compare the URL with the documentation, including the version (e.g. /crm/v3/)"], False),
    "INVALID_REQUEST_METHOD": ("Wrong HTTP method", "method",
        "This endpoint does not accept the HTTP method you used.",
        [], ["Check the documented method (e.g. POST to create, PUT to update in Zoho CRM)"], False),
    "REQUIRED_PARAM_MISSING": ("Required parameter missing", "validation",
        "A required query or body parameter is missing.",
        [], ["Add the parameter named in the error (check the endpoint's documentation)"], False),
    "LIMIT_EXCEEDED": ("Limit exceeded", "rate_limit",
        "You hit an API limit (too many records, calls or credits).",
        ["Daily API credit limit reached", "Too many records in one request (Zoho CRM: max 100 per insert/update)"],
        ["Send fewer records per request", "Wait and retry later"], True),
    "TOO_MANY_REQUESTS": ("Too many requests", "rate_limit",
        "You are sending requests faster than allowed.", [], ["Wait a moment and retry; add delays between calls"], True),
    "INTERNAL_ERROR": ("Server-side error", "server",
        "The server had an internal problem.", [], ["Retry after a short wait", "If it repeats, simplify the request to find the trigger"], True),
    # OAuth (token endpoints)
    "invalid_code": ("Authorization code invalid or expired", "auth",
        "The one-time authorization code was rejected.", ["Code already used or expired (Zoho Self Client codes last 3-10 minutes)"],
        ["Generate a new code and use it straight away"], False),
    "invalid_client": ("Client ID or secret rejected", "auth",
        "The OAuth server did not accept the client credentials.", ["Wrong Client ID/Secret", "Client registered in another Zoho data centre"],
        ["Copy the Client ID and Secret again", "Select the correct data centre"], False),
    "invalid_grant": ("Refresh token or code no longer valid", "auth",
        "The grant (refresh token or code) is revoked, expired or already used.", [], ["Reconnect the credential"], False),
    "invalid_scope": ("Invalid scope", "permission", "A requested scope does not exist for this app.", [], ["Check scope names in the API docs"], False),
}

# HubSpot uses "category" values
HUBSPOT = {
    "VALIDATION_ERROR": "INVALID_DATA",
    "OBJECT_NOT_FOUND": "_404",
    "CONFLICT": "DUPLICATE_DATA",
    "MISSING_SCOPES": "OAUTH_SCOPE_MISMATCH",
    "INVALID_AUTHENTICATION": "INVALID_TOKEN",
    "EXPIRED_AUTHENTICATION": "INVALID_TOKEN",
    "RATE_LIMITS": "TOO_MANY_REQUESTS",
}

STATUS: dict[int, tuple[str, str, str, list[str], list[str], bool]] = {
    400: ("Bad request", "validation", "The server rejected the request as malformed or invalid.",
          ["Invalid JSON or wrong field names", "Missing required fields or parameters", "Wrong data types"],
          ["Read the error message in the response body", "Compare the body with the documentation's example"], False),
    401: ("Not authenticated", "auth", "The request has no valid credentials, or the token expired.",
          ["Missing Authorization header", "Expired or wrong token", "Wrong token prefix (e.g. Zoho needs 'Zoho-oauthtoken')"],
          ["Select a saved credential in the Auth tab", "Use Test connection on the credential"], False),
    403: ("Forbidden", "permission", "You are authenticated, but not allowed to do this.",
          ["Missing OAuth scope", "User role lacks permission", "Feature not available in the plan/edition"],
          ["Check the scopes on the credential", "Try with an administrator user"], False),
    404: ("Not found", "not_found", "The URL or the record does not exist.",
          ["Typo in the path", "Wrong API version or domain", "Record ID does not exist (or was deleted)"],
          ["Check the URL against the documentation", "Check the record ID"], False),
    405: ("Method not allowed", "method", "This URL does not accept this HTTP method.", [], ["Use the method from the documentation"], False),
    406: ("Not acceptable", "validation", "The server cannot return the requested format.", [], ["Remove or fix the Accept header"], False),
    409: ("Conflict", "conflict", "The request conflicts with the current state (often a duplicate).", [], ["Update the existing record instead"], False),
    413: ("Request too large", "validation", "The request body is too big.", [], ["Send fewer records per request"], False),
    415: ("Unsupported content type", "validation", "The server does not accept the body format you sent.",
          ["JSON sent without 'Content-Type: application/json'", "Form data sent where JSON is expected (or the reverse)"],
          ["Choose the right Body type (JSON / Form)"], False),
    422: ("Unprocessable data", "validation", "The body is well-formed but contains invalid values.", [], ["Check each field against the documentation"], False),
    429: ("Rate limited", "rate_limit", "Too many requests in a short time.", [], ["Wait (see the Retry-After header) and retry"], True),
    500: ("Server error", "server", "Something went wrong on the server.", [], ["Retry later; if it repeats, simplify the request"], True),
    502: ("Bad gateway", "server", "A server in between failed.", [], ["Retry in a moment"], True),
    503: ("Service unavailable", "server", "The service is down or overloaded.", [], ["Retry later"], True),
    504: ("Gateway timeout", "server", "The server took too long.", [], ["Retry later; request fewer records"], True),
}

NETWORK = {
    "blocked": ("Request blocked by the app", "network", "The app refused to send this request for safety.",
                [], ["Use a public https:// URL. For local test servers set ALLOW_PRIVATE_NETWORK_REQUESTS=true in backend/.env"]),
    "dns": ("Server name not found", "network", "The domain name could not be found.",
            ["Typo in the domain", "Wrong data-centre domain (e.g. zohoapis.com vs zohoapis.in)", "No internet connection"], ["Check the domain"]),
    "timeout": ("No answer in time", "network", "The server did not answer within 30 seconds.", [], ["Retry; request fewer records"]),
    "connection": ("Could not connect", "network", "The connection to the server failed.", ["Server down", "Firewall or VPN blocking", "Wrong port"], ["Check the URL and your connection"]),
    "invalid": ("Request not sent", "validation", "The request itself is invalid (e.g. body is not valid JSON).", [], ["Fix the problem shown and send again"]),
}


def _from(entry, **extra) -> Diagnosis:
    title, category, explanation, causes, suggestions, *rest = entry
    return Diagnosis(title=title, category=category, explanation=explanation, likely_causes=list(causes),
                     suggestions=list(suggestions), retryable=bool(rest[0]) if rest else False, **extra)


def diagnose(status_code: int | None, body: str = "", error_kind: str = "", error_message: str = "",
             method: str = "", headers: dict[str, str] | None = None) -> Diagnosis:
    # No status code AND no response body = the server never answered (network problem).
    # No status code but a pasted body = the user just didn't type the status: read the body.
    if status_code is None and (error_kind or not (body or "").strip()):
        entry = NETWORK.get(error_kind or "connection", NETWORK["connection"])
        return _from(entry, error_message=error_message, matched=f"network:{error_kind}")

    info = extract(body or "")
    message = info.messages[0] if info.messages else ""
    common = dict(error_message=message, fields=info.fields)

    for code in info.codes:
        key = code if code in KNOWN else code.upper() if code.upper() in KNOWN else None
        if key:
            diagnosis = _from(KNOWN[key], error_code=code, matched=f"code:{key}", **common)
            if info.expected_types:
                diagnosis.likely_causes.insert(0, f"Expected data type: {info.expected_types[0]}")
            break
    else:
        mapped = HUBSPOT.get(info.hubspot_category)
        if mapped and mapped in KNOWN:
            diagnosis = _from(KNOWN[mapped], error_code=info.hubspot_category, matched=f"hubspot:{info.hubspot_category}", **common)
        elif status_code is None:
            diagnosis = Diagnosis(
                title="Error response", category="unknown", matched="body-only",
                explanation="The error code was not recognised. Adding the status code (e.g. 400) gives a better explanation.",
                suggestions=["Read the server's message below", "Use 'Explain with AI' for a deeper look"], **common,
            )
        elif mapped == "_404" or status_code in STATUS:
            entry = STATUS.get(404 if mapped == "_404" else status_code)
            diagnosis = _from(entry, error_code=info.codes[0] if info.codes else "", matched=f"status:{status_code}", **common)
        elif 300 <= status_code < 400:
            location = (headers or {}).get("location", "")
            diagnosis = Diagnosis(title="Redirect", category="redirect", matched="status:3xx",
                                  explanation=f"The server points to another URL{': ' + location if location else ''}.",
                                  suggestions=["Send the request to the new URL (often http→https or a regional domain)"])
        elif status_code >= 500:
            diagnosis = _from(STATUS[500], matched="status:5xx", **common)
        elif status_code >= 400:
            diagnosis = _from(STATUS[400], matched="status:4xx", **common)
        else:
            return Diagnosis(title="No error", category="unknown", explanation=f"Status {status_code} means the request succeeded.",
                             matched="status:ok", **common)

    if status_code == 429 and headers and headers.get("retry-after"):
        diagnosis.suggestions.insert(0, f"The server asks you to wait {headers['retry-after']} seconds (Retry-After).")
    if info.fields:
        diagnosis.suggestions.insert(0, f"Look at: {', '.join(info.fields[:5])}")
    return diagnosis
