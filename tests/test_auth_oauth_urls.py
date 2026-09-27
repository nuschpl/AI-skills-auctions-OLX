from urllib.parse import urlparse, parse_qs

from scripts.auth_oauth import build_authorize_url, parse_callback


def test_authorize_url_shape():
    url = build_authorize_url(
        client_id="abc",
        redirect_uri="https://example.com/olx/callback/",
        scope=["v2", "read", "write"],
        state="xyz",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.olx.pl"
    assert parsed.path == "/oauth/authorize/"
    q = parse_qs(parsed.query)
    assert q["client_id"] == ["abc"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://example.com/olx/callback/"]
    assert q["scope"] == ["v2 read write"]
    assert q["state"] == ["xyz"]


def test_parse_callback_accepts_full_url_query_or_bare_code():
    assert parse_callback("https://example.com/olx/callback/?code=C1&state=S") == ("C1", "S")
    assert parse_callback("code=C2&state=S") == ("C2", "S")
    assert parse_callback("  C3  ") == ("C3", None)
