import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from scripts import auth_oauth
from scripts.auth_oauth import AppCredentials, TokenStore, run_authorize_flow

CREDS = AppCredentials("id", "sec", "https://example.com/olx/callback/")
TOKEN_JSON = {"access_token": "AT", "refresh_token": "RT", "expires_in": 86400, "scope": "v2 read write"}


def _state_from_printed(capsys) -> str:
    out = capsys.readouterr().out
    url = next(w for w in out.split() if w.startswith("https://www.olx.pl/oauth/authorize/"))
    return parse_qs(urlparse(url).query)["state"][0]


def test_listener_handoff_exchanges_code(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(auth_oauth, "LISTENER_PORT", 18765)
    monkeypatch.setattr(auth_oauth._Listener.__init__, "__defaults__", (18765,))
    store = TokenStore(tmp_path / "t.json")
    result = {}

    def fake_bounce():
        # Wait for the flow to print the URL, then do what the bounce page does.
        for _ in range(50):
            try:
                state = _state_from_printed(capsys)
                break
            except StopIteration:
                time.sleep(0.05)
        requests.get(f"http://127.0.0.1:18765/callback?code=CODE&state={state}", timeout=5)

    with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
        rsps.add_passthru("http://127.0.0.1:18765")
        rsps.post(auth_oauth.TOKEN_URL, json=TOKEN_JSON)
        t = threading.Thread(target=fake_bounce)
        t.start()
        tokens = run_authorize_flow(CREDS, store, timeout=10, open_browser=False,
                                    input_fn=lambda _: pytest.fail("should not prompt"))
        t.join()
    assert tokens.access_token == "AT"
    assert store.load().refresh_token == "RT"


@responses.activate
def test_paste_fallback_after_timeout(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(auth_oauth._Listener.__init__, "__defaults__", (18766,))
    responses.post(auth_oauth.TOKEN_URL, json=TOKEN_JSON)
    tokens = run_authorize_flow(CREDS, TokenStore(tmp_path / "t.json"), timeout=0.1,
                                open_browser=False, input_fn=lambda _: "PASTED")
    assert tokens.access_token == "AT"
    assert '"code": "PASTED"' in responses.calls[0].request.body.decode()


def test_state_mismatch_is_refused(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(auth_oauth._Listener.__init__, "__defaults__", (18767,))
    with pytest.raises(RuntimeError, match="state mismatch"):
        run_authorize_flow(CREDS, TokenStore(tmp_path / "t.json"), timeout=0.1,
                           open_browser=False,
                           input_fn=lambda _: "https://example.com/olx/callback/?code=C&state=EVIL")


def test_load_app_credentials_rejects_malformed_redirect_uri(tmp_path):
    # Live failure: "https:/example.com/..." (one slash) made OLX answer
    # "The redirect URI provided is missing or does not match" after login.
    import json
    import pytest
    from scripts.auth_oauth import load_app_credentials

    p = tmp_path / "app_credentials.json"
    p.write_text(json.dumps({
        "client_id": "1", "client_secret": "s",
        "redirect_uri": "https:/example.com/olx/callback/",
    }))
    with pytest.raises(ValueError, match="redirect_uri"):
        load_app_credentials(p)
