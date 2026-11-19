"""Safely download a documentation page from a URL the user typed.

Protection against SSRF ("server-side request forgery"): a malicious link could
try to make our backend call things inside your own network, such as your
router (192.168.x.x), other programs on your computer (localhost) or cloud
metadata services (169.254.169.254). We therefore:

  * allow only http:// and https:// URLs without embedded usernames/passwords,
  * look up the server's IP addresses and refuse anything that is not a public
    internet address,
  * follow redirects ourselves and check every hop the same way,
  * cap download size and time.

Known limitation (acceptable for a personal tool): a DNS server could return a
different address between our check and the actual connection ("DNS rebinding").
"""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx2

MAX_BYTES = 30 * 1024 * 1024  # 30 MB (some official specs are very large)
TIMEOUT_SECONDS = 20.0
MAX_REDIRECTS = 5
USER_AGENT = "MyAPIIntegrationAssistant/0.4 (documentation fetcher)"


class UnsafeURLError(ValueError):
    """The URL is not allowed (private network, wrong scheme, ...)."""


class FetchError(ValueError):
    """The URL is allowed but downloading failed."""


@dataclass
class FetchedDocument:
    url: str  # final URL after redirects
    content: bytes
    content_type: str


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"Cannot find the server '{host}'. Check the address.") from exc
    return sorted({info[4][0] for info in infos})


def check_url_is_public(url: str, resolve=_resolve) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http:// and https:// links are allowed.")
    if parts.username or parts.password:
        raise UnsafeURLError("Links containing a username or password are not allowed.")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("This link has no server name.")
    if host.lower() in ("localhost",) or host.lower().endswith((".localhost", ".local", ".internal")):
        raise UnsafeURLError("Links to your own computer or local network are not allowed.")
    for address in resolve(host):
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError(
                f"'{host}' points to a private or local network address ({ip}). "
                "Only public internet documentation can be fetched."
            )


def fetch_document(url: str, resolve=_resolve, transport: httpx2.BaseTransport | None = None) -> FetchedDocument:
    current = url.strip()
    with httpx2.Client(
        follow_redirects=False,  # we follow redirects ourselves, checking each one
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,application/yaml,text/plain,application/pdf,*/*;q=0.5"},
        transport=transport,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            check_url_is_public(current, resolve)
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("The server sent a redirect without a target.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(f"The server answered with status {response.status_code}.")
                    declared = int(response.headers.get("content-length") or 0)
                    if declared > MAX_BYTES:
                        raise FetchError("The document is larger than 30 MB.")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise FetchError("The document is larger than 30 MB.")
                        chunks.append(chunk)
                    return FetchedDocument(
                        url=current,
                        content=b"".join(chunks),
                        content_type=response.headers.get("content-type", "").split(";")[0].strip().lower(),
                    )
            except httpx2.TimeoutException as exc:
                raise FetchError("The server took too long to answer (over 20 seconds).") from exc
            except httpx2.HTTPError as exc:
                raise FetchError(f"Download failed: {exc.__class__.__name__}.") from exc
    raise FetchError("Too many redirects.")
