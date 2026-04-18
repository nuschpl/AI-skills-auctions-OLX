from urllib.parse import urlparse, parse_qs
from scripts.auth_oauth import build_authorize_url


def test_authorize_url_shape():
    url = build_authorize_url(
        client_id="abc",
        redirect_uri="http://localhost:8765/callback",
        scope=["read:adverts", "write:adverts"],
        state="xyz",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.olx.pl"
    assert parsed.path == "/oauth/authorize"
    q = parse_qs(parsed.query)
    assert q["client_id"] == ["abc"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["http://localhost:8765/callback"]
    assert q["scope"] == ["read:adverts write:adverts"]
    assert q["state"] == ["xyz"]
