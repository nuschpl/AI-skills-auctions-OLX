"""Mode A transport: OAuth2 Partner API.

Minimal v1: auth-layer integration + get_user. Full advert CRUD against
the Partner API is deferred to a separate plan (blocked on developer-app
approval and swagger access).
"""
from __future__ import annotations

import requests

from scripts.auth_oauth import TokenStore, refresh_tokens
from scripts.transports.base import Advert, Transport

BASE = "https://api.olxgroup.com"


class OfficialTransport(Transport):
    def __init__(
        self,
        token_store: TokenStore,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.store = token_store
        self.client_id = client_id
        self.client_secret = client_secret

    def _session(self) -> requests.Session:
        tokens = self.store.load()
        if tokens is None:
            raise RuntimeError("no tokens; run OAuth2 authorize first")
        if tokens.expired() and self.client_id and self.client_secret:
            tokens = refresh_tokens(
                client_id=self.client_id,
                client_secret=self.client_secret,
                store=self.store,
            )
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {tokens.access_token}"
        s.headers["Accept"] = "application/json"
        return s

    def get_user(self) -> dict:
        r = self._session().get(f"{BASE}/partner/users/me", timeout=15)
        r.raise_for_status()
        return r.json()

    def list_my_adverts(self) -> list[Advert]:
        raise NotImplementedError(
            "deferred: needs developer-app approval + swagger"
        )

    def delete_advert(self, ad_id: str) -> None:
        raise NotImplementedError("deferred")

    def create_advert(self, payload: dict) -> dict:
        raise NotImplementedError("deferred")

    def upload_photo(self, path: str) -> dict:
        raise NotImplementedError("deferred")
