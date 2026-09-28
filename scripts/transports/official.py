"""Mode A transport: OLX Partner API v2 (OAuth2).

Base URL and headers per the v2 swagger
(``https://developer.olx.pl/swagger/v2/partner_api.yaml``): every request
needs ``Authorization: Bearer <token>`` and ``Version: 2.0`` (without it
the API answers 400 "Missing required 'Version' header!").

Implemented so far: auth + ``get_user``. Advert CRUD is still to do; keep
``scripts.capabilities.CAPABILITIES`` in sync so "auto" mode never routes
to a stub. Photos: the Partner API has no upload endpoint — the advert
payload carries ``images: [{"url": ...}]`` that OLX downloads itself.
"""
from __future__ import annotations

import requests

from scripts.auth_oauth import AppCredentials, TokenStore, refresh_tokens
from scripts.transports.base import Advert, Transport

BASE = "https://www.olx.pl/api/partner"
API_VERSION = "2.0"


class OfficialTransport(Transport):
    def __init__(
        self,
        token_store: TokenStore,
        *,
        creds: AppCredentials | None = None,
    ):
        self.store = token_store
        self.creds = creds

    def _session(self) -> requests.Session:
        tokens = self.store.load()
        if tokens is None:
            raise RuntimeError(
                "no OAuth tokens; run `python -m scripts.auth_oauth` once"
            )
        if tokens.expired():
            if self.creds is None:
                raise RuntimeError(
                    "OAuth access token expired and no app credentials to "
                    "refresh it; check $OLX_SKILL_HOME/app_credentials.json"
                )
            tokens = refresh_tokens(
                client_id=self.creds.client_id,
                client_secret=self.creds.client_secret,
                store=self.store,
            )
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {tokens.access_token}"
        s.headers["Version"] = API_VERSION
        s.headers["Accept"] = "application/json"
        return s

    def get_user(self) -> dict:
        r = self._session().get(f"{BASE}/users/me", timeout=15)
        r.raise_for_status()
        return r.json()

    def list_my_adverts(self) -> list[Advert]:
        raise NotImplementedError("Partner API advert CRUD not implemented yet")

    def delete_advert(self, ad_id: str) -> None:
        raise NotImplementedError("Partner API advert CRUD not implemented yet")

    def create_advert(self, payload: dict) -> dict:
        raise NotImplementedError("Partner API advert CRUD not implemented yet")

    def upload_photo(self, path: str) -> dict:
        raise NotImplementedError(
            "Partner API has no upload endpoint; pass image URLs in the advert payload"
        )
