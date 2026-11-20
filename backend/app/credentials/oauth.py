"""OAuth 2.0 helpers: Zoho (all data centres) and any standard OAuth 2.0 provider.

Two ways to connect:
  * Code exchange - paste a one-time authorization code. For Zoho this is the
    "Self Client" flow in the Zoho API Console (no redirect URL needed).
  * Browser sign-in - the app opens the provider's consent page; after you approve,
    the provider redirects back to OAUTH_REDIRECT_URI with a code.
Both end by storing a refresh token (encrypted) and a short-lived access token.
"""

import time
from urllib.parse import urlencode

import httpx2
from pydantic import BaseModel

from app.security.url_fetch import FetchError, UnsafeURLError, _resolve, check_url_is_public

# Zoho data centres -> accounts server (from Zoho's multi-DC docs; also used by Activepieces' Zoho pieces)
ZOHO_ACCOUNTS = {
    "com": "https://accounts.zoho.com",
    "eu": "https://accounts.zoho.eu",
    "in": "https://accounts.zoho.in",
    "com.au": "https://accounts.zoho.com.au",
    "jp": "https://accounts.zoho.jp",
    "ca": "https://accounts.zohocloud.ca",
}

TIMEOUT = 20.0


class OAuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Plain-language explanations for the most common OAuth error codes.
ERROR_HELP = {
    "invalid_code": "The authorization code is invalid or expired. Zoho Self Client codes are valid only for the "
    "few minutes you chose and can be used once - generate a new code and paste it straight away.",
    "invalid_client": "The Client ID or Client Secret is wrong - or, for Zoho, the client belongs to a different data "
    "centre than the one selected (e.g. created on zoho.in but connecting via zoho.com).",
    "invalid_client_secret": "The Client Secret is wrong. Copy it again from the API console.",
    "invalid_redirect_uri": "The redirect URL is not registered for this client. Add exactly the redirect URL shown "
    "in the app to the client's authorized redirect URIs.",
    "redirect_uri_mismatch": "The redirect URL is not registered for this client. Add exactly the redirect URL shown "
    "in the app to the client's authorized redirect URIs.",
    "invalid_grant": "The refresh token or code is no longer valid (revoked, expired, or already used). Connect again.",
    "access_denied": "Access was denied on the consent screen.",
    "invalid_scope": "One of the requested scopes is not valid for this app. Check the scope names in the API docs.",
    "unsupported_grant_type": "The token server does not accept this grant type.",
}


def explain(code: str, fallback: str = "") -> str:
    return ERROR_HELP.get(code, fallback or f"The OAuth server returned the error '{code}'.")


class TokenResult(BaseModel):
    access_token: str
    refresh_token: str = ""
    expires_at: float = 0           # unix time
    api_domain: str = ""            # Zoho tells us which API host to use
    scope: str = ""


def token_url_for(public: dict) -> str:
    if public.get("provider") == "zoho":
        return ZOHO_ACCOUNTS[public.get("data_center", "com")] + "/oauth/v2/token"
    return public.get("token_url", "")


def authorize_url_for(public: dict) -> str:
    if public.get("provider") == "zoho":
        return ZOHO_ACCOUNTS[public.get("data_center", "com")] + "/oauth/v2/auth"
    return public.get("auth_url", "")


def build_authorize_url(public: dict, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": public.get("scopes", ""),
        "state": state,
    }
    if public.get("provider") == "zoho":
        params.update({"access_type": "offline", "prompt": "consent"})  # needed for Zoho to issue a refresh token
    return authorize_url_for(public) + "?" + urlencode(params)


def _post_token(url: str, form: dict, client_id: str, client_secret: str, auth_method: str,
                transport: httpx2.BaseTransport | None, resolve) -> dict:
    from app.core.config import get_settings

    if not get_settings().allow_private_network_requests:  # same switch as the Request Builder
        try:
            check_url_is_public(url, resolve)
        except (UnsafeURLError, FetchError) as exc:
            raise OAuthError("bad_token_url", f"Token URL not allowed: {exc}") from exc
    auth = None
    if auth_method == "basic":
        auth = (client_id, client_secret)
    else:
        form = {**form, "client_id": client_id, "client_secret": client_secret}
    try:
        with httpx2.Client(timeout=TIMEOUT, transport=transport) as client:
            response = client.post(url, data=form, auth=auth, headers={"Accept": "application/json"})
    except httpx2.HTTPError as exc:
        raise OAuthError("network", f"Could not reach the token server ({exc.__class__.__name__}).") from exc
    try:
        data = response.json()
    except ValueError:
        raise OAuthError("bad_response", f"The token server answered {response.status_code} with non-JSON content.")
    # Zoho returns errors with HTTP 200 and an "error" field, so check the body, not just the status.
    if "error" in data or response.status_code >= 400:
        code = str(data.get("error", f"http_{response.status_code}"))
        raise OAuthError(code, explain(code, str(data.get("error_description", ""))))
    if not data.get("access_token"):
        raise OAuthError("no_access_token", "The token server did not return an access token.")
    return data


def _to_result(data: dict, previous_refresh: str = "") -> TokenResult:
    return TokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token") or previous_refresh,
        expires_at=time.time() + float(data.get("expires_in") or 3600),
        api_domain=data.get("api_domain", ""),
        scope=data.get("scope", ""),
    )


def exchange_code(public: dict, secret: dict, code: str, redirect_uri: str | None,
                  transport: httpx2.BaseTransport | None = None, resolve=_resolve) -> TokenResult:
    form = {"grant_type": "authorization_code", "code": code.strip()}
    if redirect_uri:
        form["redirect_uri"] = redirect_uri
    data = _post_token(token_url_for(public), form, secret.get("client_id", ""), secret.get("client_secret", ""),
                       public.get("client_auth_method", "post"), transport, resolve)
    result = _to_result(data)
    if not result.refresh_token:
        raise OAuthError(
            "no_refresh_token",
            "Connected, but no refresh token was returned, so the connection would stop working after the access "
            "token expires. For Zoho, generate a new code (Self Client) - codes give a refresh token only the first time "
            "per scope set; for other providers, make sure 'offline access' is requested.",
        )
    return result


def refresh(public: dict, secret: dict, transport: httpx2.BaseTransport | None = None, resolve=_resolve) -> TokenResult:
    if not secret.get("refresh_token"):
        raise OAuthError("no_refresh_token", "This credential has no refresh token yet. Connect it first.")
    data = _post_token(token_url_for(public), {"grant_type": "refresh_token", "refresh_token": secret["refresh_token"]},
                       secret.get("client_id", ""), secret.get("client_secret", ""),
                       public.get("client_auth_method", "post"), transport, resolve)
    return _to_result(data, previous_refresh=secret["refresh_token"])
