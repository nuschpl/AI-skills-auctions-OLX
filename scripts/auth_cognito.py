"""OLX Cognito PKCE authentication flow.

OLX uses AWS Cognito (Pool: eu-west-1_dUjFuvTf4) with Google as the
federated identity provider. Because this is a public client (no
client_secret), authentication uses the PKCE extension:

    1.  A random ``code_verifier`` is generated locally.
    2.  Its SHA-256 hash (``code_challenge``) is embedded in the
        authorization URL that the user opens in their browser.
    3.  The browser authenticates with Google through Cognito's hosted UI
        and then redirects to ``http://localhost:<port>/callback?code=...``.
    4.  A temporary HTTP server on ``port`` captures that redirect.
    5.  The ``code`` is exchanged at the token endpoint together with the
        original ``code_verifier`` – Cognito verifies the pair instead of
        a client secret.
    6.  Tokens (access, refresh, id) are returned and can be persisted via
        ``CognitoTokenStore``.

Refresh tokens are long-lived; call ``refresh_tokens()`` before the
access token expires to obtain a fresh set without user interaction.

Endpoints
---------
    authorize:  https://pl-idp.login.olx.com/oauth2/authorize
    token:      https://pl-idp.login.olx.com/oauth2/token
    issuer:     https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_dUjFuvTf4

Usage (manual flow)
-------------------
    from scripts.auth_cognito import run_pkce_flow
    tokens = run_pkce_flow()          # opens browser, waits for redirect

Usage (headless refresh)
------------------------
    from scripts.auth_cognito import CognitoTokenStore, refresh_tokens
    store = CognitoTokenStore()
    if store.needs_refresh():
        tokens = refresh_tokens(store.load()["refresh_token"])
        store.save(tokens)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# ---------------------------------------------------------------------------
# Cognito / OLX constants
# ---------------------------------------------------------------------------

AUTHORIZE_URL = "https://pl-idp.login.olx.com/oauth2/authorize"
TOKEN_URL = "https://pl-idp.login.olx.com/oauth2/token"
CLIENT_ID = "6j7elk01p32o648o1io8lvhhab"
SCOPE = "openid profile email offline_access"


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _generate_code_verifier() -> str:
    """Return a cryptographically random URL-safe base64 string (no padding).

    Length is 43–128 characters as required by RFC 7636.
    """
    # 32 random bytes → 43-char base64url (no padding) — well within bounds.
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _code_challenge(verifier: str) -> str:
    """Return ``BASE64URL(SHA256(ASCII(code_verifier)))`` per RFC 7636 §4.2."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_pkce_authorize_url(
    redirect_uri: str,
    port: int = 8765,
) -> tuple[str, str]:
    """Build the Cognito PKCE authorization URL.

    Parameters
    ----------
    redirect_uri:
        The URI Cognito will redirect to after the user authenticates.
        Typically ``http://localhost:<port>/callback``.
    port:
        Informational only; the port is embedded in *redirect_uri* by the
        caller.  Kept for API symmetry with ``run_pkce_flow``.

    Returns
    -------
    (url, code_verifier)
        ``url`` is the authorization URL to open in the browser.
        ``code_verifier`` must be kept in memory until ``exchange_code`` is
        called.
    """
    code_verifier = _generate_code_verifier()
    challenge = _code_challenge(code_verifier)
    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "identity_provider": "Google",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    url = f"{AUTHORIZE_URL}?{params}"
    return url, code_verifier


def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict:
    """Exchange an authorization code for tokens.

    Posts to the Cognito token endpoint with ``grant_type=authorization_code``
    and the PKCE ``code_verifier``.  No client secret is required.

    Returns
    -------
    dict with keys: ``access_token``, ``refresh_token``, ``id_token``,
    ``expires_in``, ``token_type``.
    """
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def refresh_tokens(refresh_token: str) -> dict:
    """Obtain a fresh token set using a Cognito refresh token.

    Parameters
    ----------
    refresh_token:
        The ``refresh_token`` value from a previous ``exchange_code`` or
        ``refresh_tokens`` call.

    Returns
    -------
    dict with at least ``access_token``, ``id_token``, ``expires_in``.
    Cognito does **not** rotate the refresh token on refresh, so the same
    ``refresh_token`` stays valid until it expires or is revoked.
    """
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Local redirect-capture server
# ---------------------------------------------------------------------------


class _CallbackServer:
    """Minimal HTTP server that captures ``?code=`` from the OAuth2 redirect."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.code: Optional[str] = None
        self.error: Optional[str] = None
        self._server: Optional[HTTPServer] = None

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        callback_server = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                if "code" in params:
                    callback_server.code = params["code"][0]
                    body = b"<html><body><h2>Authenticated.</h2><p>You may close this tab.</p></body></html>"
                    self.send_response(200)
                elif "error" in params:
                    callback_server.error = params.get("error_description", params["error"])[0]
                    body = b"<html><body><h2>Authentication failed.</h2></body></html>"
                    self.send_response(400)
                else:
                    body = b"<html><body><h2>Unexpected request.</h2></body></html>"
                    self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:  # silence access log
                pass

        return _Handler

    def start(self) -> None:
        self._server = HTTPServer(("127.0.0.1", self.port), self._make_handler())
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()

    def wait_for_code(self, timeout: float = 120.0) -> str:
        """Block until a code arrives or *timeout* elapses.

        Raises
        ------
        TimeoutError
            If no callback was received within *timeout* seconds.
        RuntimeError
            If the provider returned an error.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.code:
                return self.code
            if self.error:
                raise RuntimeError(f"OAuth2 error from provider: {self.error}")
            time.sleep(0.2)
        raise TimeoutError(
            f"No OAuth2 callback received within {timeout:.0f} s. "
            "Did you open the URL in your browser?"
        )


# ---------------------------------------------------------------------------
# Full interactive flow
# ---------------------------------------------------------------------------


def run_pkce_flow(port: int = 8765) -> dict:
    """Run the full interactive PKCE flow and return a token dict.

    Steps
    -----
    1.  Generate a PKCE pair.
    2.  Print the authorization URL – the user must open it in a browser.
    3.  Start a local HTTP server on ``port`` to catch the redirect.
    4.  Wait up to 120 s for the callback.
    5.  Exchange the code for tokens.
    6.  Return the token dict (``access_token``, ``refresh_token``,
        ``id_token``, ``expires_in``).
    """
    redirect_uri = f"http://localhost:{port}/callback"
    url, code_verifier = build_pkce_authorize_url(redirect_uri, port=port)

    server = _CallbackServer(port)
    server.start()

    print(
        "\n--- OLX Cognito login ---\n"
        "Open the following URL in your browser:\n\n"
        f"  {url}\n\n"
        "Waiting for the redirect callback (up to 120 s)…\n"
    )

    try:
        code = server.wait_for_code(timeout=120.0)
    finally:
        server.stop()

    print("Code received – exchanging for tokens…")
    tokens = exchange_code(code, redirect_uri, code_verifier)
    print("Tokens obtained successfully.")
    return tokens


# ---------------------------------------------------------------------------
# Token store
# ---------------------------------------------------------------------------


class CognitoTokenStore:
    """Persist Cognito tokens to ``$OLX_SKILL_HOME/cognito_tokens.json``.

    The file is stored with mode 0o600 (owner-read/write only).

    Parameters
    ----------
    home:
        Override the base directory.  Defaults to ``$OLX_SKILL_HOME`` or
        ``~/.olx-skill`` when the env var is absent.
    """

    def __init__(self, home: Optional[Path] = None) -> None:
        if home is None:
            override = os.environ.get("OLX_SKILL_HOME")
            home = Path(override).expanduser() if override else Path.home() / ".olx-skill"
        self._path = home / "cognito_tokens.json"

    @property
    def path(self) -> Path:
        return self._path

    def save(self, token_dict: dict) -> None:
        """Persist *token_dict* to disk.

        Adds an ``expires_at`` timestamp (``time.time() + expires_in``) if
        ``expires_in`` is present in *token_dict* but ``expires_at`` is not.
        """
        data = dict(token_dict)
        if "expires_in" in data and "expires_at" not in data:
            data["expires_at"] = time.time() + int(data["expires_in"])
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))
        self._path.chmod(0o600)

    def load(self) -> Optional[dict]:
        """Return the stored token dict, or ``None`` if no file exists."""
        if not self._path.exists():
            return None
        return json.loads(self._path.read_text())

    def needs_refresh(self, margin_s: int = 120) -> bool:
        """Return ``True`` when the stored access token will expire within
        *margin_s* seconds (or is already expired / not present).
        """
        data = self.load()
        if data is None:
            return True
        expires_at = data.get("expires_at")
        if expires_at is None:
            # No expiry info – assume refresh is needed.
            return True
        return time.time() + margin_s >= float(expires_at)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    token_dict = run_pkce_flow()
    store = CognitoTokenStore()
    store.save(token_dict)
    print(f"Tokens saved to {store.path}")
