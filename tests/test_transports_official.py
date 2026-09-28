import time

import responses

from scripts.auth_oauth import TOKEN_URL, AppCredentials, TokenStore
from scripts.transports.official import BASE, OfficialTransport


def _store(tmp_path, *, expires_in: float) -> TokenStore:
    store = TokenStore(tmp_path / "tokens.json")
    store.save(
        access_token="AT",
        refresh_token="RT",
        expires_at=time.time() + expires_in,
        scope="v2 read write",
    )
    return store


def test_base_is_partner_api_v2():
    # Swagger v2 `servers`: https://www.olx.pl/api/partner
    assert BASE == "https://www.olx.pl/api/partner"


@responses.activate
def test_get_user_sends_bearer_and_version_header(tmp_path):
    responses.get(f"{BASE}/users/me", json={"data": {"id": 1}})
    t = OfficialTransport(_store(tmp_path, expires_in=3600))
    assert t.get_user() == {"data": {"id": 1}}
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer AT"
    # Partner API answers 400 "Missing required 'Version' header!" without it.
    assert req.headers["Version"] == "2.0"


@responses.activate
def test_expired_token_is_refreshed_with_app_credentials(tmp_path):
    store = _store(tmp_path, expires_in=-10)
    responses.post(
        TOKEN_URL,
        json={"access_token": "AT2", "refresh_token": "RT2", "expires_in": 86400},
    )
    responses.get(f"{BASE}/users/me", json={"data": {"id": 1}})
    creds = AppCredentials(client_id="1", client_secret="s", redirect_uri="https://x/cb")
    t = OfficialTransport(store, creds=creds)
    t.get_user()
    assert responses.calls[1].request.headers["Authorization"] == "Bearer AT2"
    assert store.load().refresh_token == "RT2"
