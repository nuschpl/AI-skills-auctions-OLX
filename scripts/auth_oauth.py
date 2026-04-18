"""Mode A: OAuth2 authorization_code + refresh_token flow against OLX.

Endpoints per OLX developer docs:
    authorize: https://www.olx.pl/oauth/authorize
    token:     https://api.olxgroup.com/oauth/v1/token

URLs can be overridden per-call if OLX moves them.
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://www.olx.pl/oauth/authorize"
TOKEN_URL = "https://api.olxgroup.com/oauth/v1/token"


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float
    scope: str

    def expired(self, margin: int = 60) -> bool:
        return time.time() + margin >= self.expires_at


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


def _basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def exchange_code_for_tokens(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    store: TokenStore,
) -> Tokens:
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        headers={"Authorization": _basic_auth(client_id, client_secret)},
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    expires_at = time.time() + int(d["expires_in"])
    store.save(
        access_token=d["access_token"],
        refresh_token=d["refresh_token"],
        expires_at=expires_at,
        scope=d.get("scope", ""),
    )
    return store.load()  # type: ignore[return-value]


def refresh_tokens(
    *, client_id: str, client_secret: str, store: TokenStore
) -> Tokens:
    current = store.load()
    if current is None:
        raise RuntimeError("no tokens to refresh; run the authorize flow first")
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": current.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Authorization": _basic_auth(client_id, client_secret)},
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    expires_at = time.time() + int(d["expires_in"])
    store.save(
        access_token=d["access_token"],
        refresh_token=d.get("refresh_token", current.refresh_token),
        expires_at=expires_at,
        scope=d.get("scope", current.scope),
    )
    return store.load()  # type: ignore[return-value]
