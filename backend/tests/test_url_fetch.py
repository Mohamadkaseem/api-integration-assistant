import httpx2
import pytest

from app.security.url_fetch import FetchError, UnsafeURLError, check_url_is_public, fetch_document


def public(_host):
    return ["93.184.216.34"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/doc",
        "http://localhost:8000/api/projects",
        "http://user:pass@example.com/",
        "http://printer.local/",
    ],
)
def test_bad_urls_are_refused(url):
    with pytest.raises(UnsafeURLError):
        check_url_is_public(url, resolve=public)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.1", "169.254.169.254", "::1", "fd00::1"])
def test_private_addresses_are_refused(address):
    with pytest.raises(UnsafeURLError, match="private or local"):
        check_url_is_public("https://innocent-looking.example.com/docs", resolve=lambda _h: [address])


def test_public_url_is_downloaded():
    transport = httpx2.MockTransport(lambda req: httpx2.Response(200, headers={"content-type": "application/json; charset=utf-8"}, content=b'{"openapi": "3.0.0"}'))
    doc = fetch_document("https://docs.example.com/openapi.json", resolve=public, transport=transport)
    assert doc.content == b'{"openapi": "3.0.0"}'
    assert doc.content_type == "application/json"


def test_redirect_into_private_network_is_blocked():
    def handler(request):
        if request.url.host == "docs.example.com":
            return httpx2.Response(302, headers={"location": "http://internal.example.com/admin"})
        return httpx2.Response(200, content=b"secret admin page")

    def resolve(host):
        return ["10.1.2.3"] if host == "internal.example.com" else ["93.184.216.34"]

    with pytest.raises(UnsafeURLError):
        fetch_document("https://docs.example.com/start", resolve=resolve, transport=httpx2.MockTransport(handler))


def test_server_errors_are_explained():
    transport = httpx2.MockTransport(lambda req: httpx2.Response(404))
    with pytest.raises(FetchError, match="404"):
        fetch_document("https://docs.example.com/missing", resolve=public, transport=transport)
