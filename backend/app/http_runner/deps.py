"""Network dependencies shared by routes that call external servers.

Tests replace these with a mock server and a fake DNS resolver.
"""

import httpx2

from app.security.url_fetch import _resolve


def get_transport() -> httpx2.BaseTransport | None:
    """The real network (None = default httpx2 transport)."""
    return None


def get_resolver():
    return _resolve
