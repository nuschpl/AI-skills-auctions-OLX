"""Mode A: OAuth2 authorization_code + refresh_token flow against OLX.

Endpoints per the OLX Partner API v2 swagger
(``https://developer.olx.pl/swagger/v2/partner_api.yaml``,
``components.securitySchemes.access_token``):

    authorize: https://www.olx.pl/oauth/authorize/
    token:     https://www.olx.pl/api/open/oauth/token   (JSON body)

Token facts from the same doc: access token lives ``expires_in`` seconds
(86400 in examples); refresh token lives 30 days and is **rotated**
(a new one is issued at most once a day) — always persist the refresh
token the server returns.

OLX refuses ``localhost`` redirect URIs, so the registered callback is a
public bounce page (``docs/oauth-callback/index.html``, hosted at e.g.
``https://<your-domain>/olx/callback/``). That page hands ``?code=&state=`` to
the local listener started by :func:`run_authorize_flow`; if the handoff
fails, the user pastes the code into the terminal instead.

CLI::

    python -m scripts.auth_oauth          # one-time authorize → tokens.json
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AUTHORIZE_URL = "https://www.olx.pl/oauth/authorize/"
TOKEN_URL = "https://www.olx.pl/api/open/oauth/token"
DEFAULT_SCOPE = "v2 read write"
LISTENER_PORT = 8765


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float
    scope: str

    def expired(self, margin: int = 60) -> bool:
        return time.time() + margin >= self.expires_at


@dataclass(frozen=True)
class AppCredentials:
    client_id: str
    client_secret: str
    redirect_uri: str


def load_app_credentials(path: Path) -> AppCredentials:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Register an app at https://developer.olx.pl/ "
            'and save {"client_id", "client_secret", "redirect_uri"} there.'
        )
    d = json.loads(path.read_text())
    redirect_uri = d["redirect_uri"]
    u = urlparse(redirect_uri)
    if u.scheme != "https" or not u.netloc:
        # OLX only reports a mismatch after login; catch typos up front.
        raise ValueError(
            f"{path}: redirect_uri {redirect_uri!r} is not a valid https URL; "
            "it must match the app's registered redirect URI exactly"
        )
    return AppCredentials(
        client_id=str(d["client_id"]),
        client_secret=d["client_secret"],
        redirect_uri=redirect_uri,
    )


class TokenStore:
    def __init__(self, path: Path):
        self.path = path

    def save(
        self,
        *,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        scope: str,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "scope": scope,
        }))
        self.path.chmod(0o600)

    def load(self) -> Tokens | None:
        if not self.path.exists():
            return None
        d = json.loads(self.path.read_text())
        return Tokens(
            access_token=d["access_token"],
            refresh_token=d["refresh_token"],
            expires_at=float(d["expires_at"]),
            scope=d["scope"],
        )


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: list[str],
    state: str,
) -> str:
    q = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(scope),
        "state": state,
    })
    return f"{AUTHORIZE_URL}?{q}"


def parse_callback(text: str) -> tuple[str, str | None]:
    """Extract ``(code, state)`` from a pasted callback URL, query or bare code."""
    text = text.strip()
    query = urlparse(text).query if "://" in text else text
    params = parse_qs(query)
    if "code" in params:
        return params["code"][0], params.get("state", [None])[0]
    return text, None


def _post_token(body: dict) -> dict:
    r = requests.post(TOKEN_URL, json=body, timeout=15)
    if r.status_code >= 400:
        # OLX returns {"error", "error_description", "error_human_title"}.
        raise RuntimeError(f"OLX token endpoint {r.status_code}: {r.text[:300]}")
    return r.json()


def _save_response(d: dict, store: TokenStore, fallback: Tokens | None = None) -> Tokens:
    store.save(
        access_token=d["access_token"],
        refresh_token=d.get("refresh_token") or (fallback.refresh_token if fallback else ""),
        expires_at=time.time() + int(d["expires_in"]),
        scope=d.get("scope") or (fallback.scope if fallback else DEFAULT_SCOPE),
    )
    return store.load()  # type: ignore[return-value]


def exchange_code_for_tokens(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    store: TokenStore,
) -> Tokens:
    d = _post_token({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "scope": DEFAULT_SCOPE,
        "redirect_uri": redirect_uri,
    })
    return _save_response(d, store)


def refresh_tokens(
    *, client_id: str, client_secret: str, store: TokenStore
) -> Tokens:
    current = store.load()
    if current is None:
        raise RuntimeError("no tokens to refresh; run `python -m scripts.auth_oauth` first")
    d = _post_token({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": current.refresh_token,
    })
    return _save_response(d, store, fallback=current)


# ---------------------------------------------------------------------------
# Interactive one-time authorize
# ---------------------------------------------------------------------------


class _Listener:
    """Receives ``?code=&state=`` from the public bounce page via fetch()."""

    def __init__(self, port: int = LISTENER_PORT) -> None:
        self.port = port
        self.result: tuple[str, str | None] | None = None
        self._server: HTTPServer | None = None

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        listener = self

        class _H(BaseHTTPRequestHandler):
            def _cors(self) -> None:
                # The bounce page is an https origin calling http://localhost:
                # Chrome's Private Network Access preflight needs these.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Private-Network", "true")

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self._cors()
                self.send_header("Access-Control-Allow-Methods", "GET")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                params = parse_qs(urlparse(self.path).query)
                ok = "code" in params
                if ok:
                    listener.result = (params["code"][0], params.get("state", [None])[0])
                self.send_response(200 if ok else 400)
                self._cors()
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        return _H

    def start(self) -> None:
        self._server = HTTPServer(("127.0.0.1", self.port), self._handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


def run_authorize_flow(
    creds: AppCredentials,
    store: TokenStore,
    *,
    timeout: float = 180.0,
    open_browser: bool = True,
    input_fn: Callable[[str], str] = input,
) -> Tokens:
    """One-time user consent → tokens saved in *store*.

    Waits for the bounce page to hand the code to the local listener; on
    timeout asks the user to paste the code (or the whole callback URL).
    """
    state = secrets.token_urlsafe(16)
    url = build_authorize_url(
        client_id=creds.client_id,
        redirect_uri=creds.redirect_uri,
        scope=DEFAULT_SCOPE.split(),
        state=state,
    )
    listener = _Listener()
    listener.start()
    print(f"\nOpen this URL and click 'Zezwól':\n\n  {url}\n")
    if open_browser:
        webbrowser.open(url)
    try:
        deadline = time.monotonic() + timeout
        while listener.result is None and time.monotonic() < deadline:
            time.sleep(0.2)
    finally:
        listener.stop()

    if listener.result is None:
        code, got_state = parse_callback(
            input_fn("Paste the code (or the full callback URL) from the page: ")
        )
    else:
        code, got_state = listener.result
    if got_state is not None and got_state != state:
        raise RuntimeError("OAuth state mismatch — refusing the code")
    return exchange_code_for_tokens(
        code=code,
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        redirect_uri=creds.redirect_uri,
        store=store,
    )


def main() -> None:
    from scripts.config import APP_CREDENTIALS_PATH, TOKENS_PATH

    creds = load_app_credentials(APP_CREDENTIALS_PATH)
    tokens = run_authorize_flow(creds, TokenStore(TOKENS_PATH))
    print(f"Saved tokens to {TOKENS_PATH} (scope: {tokens.scope}).")


if __name__ == "__main__":
    main()
