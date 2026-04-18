"""Transport-agnostic OLX operation facade."""
from __future__ import annotations

from typing import Any

from scripts.capabilities import pick_transport


class OLX:
    def __init__(
        self, *, official, browser, mode: str = "auto", has_tokens: bool = False
    ):
        self._t = {"official": official, "browser": browser}
        self._mode = mode
        self._has_tokens = has_tokens

    def _pick(self, op: str):
        name = pick_transport(op, mode=self._mode, has_tokens=self._has_tokens)
        return self._t[name]

    def get_user(self) -> dict:
        return self._pick("get_user").get_user()

    def list_my_adverts(self):
        return self._pick("list_my_adverts").list_my_adverts()

    def list_my_adverts_detailed(self):
        """Active adverts with category metadata — used by `olx status`."""
        return self._pick("list_my_adverts_detailed").list_my_adverts_detailed()

    def delete_advert(self, ad_id: str) -> None:
        self._pick("delete_advert").delete_advert(ad_id)

    def create_advert(self, payload: dict) -> dict:
        return self._pick("create_advert").create_advert(payload)

    def upload_photo(self, path: str) -> dict:
        return self._pick("upload_photo").upload_photo(path)

    def apply_promotion(self, ad_id: str, package: str) -> Any:
        return self._pick("apply_promotion").apply_promotion(ad_id, package)

    def search_competitors(self, query: str, *, limit: int = 20):
        return self._pick("search_competitors").search_competitors(query, limit=limit)
