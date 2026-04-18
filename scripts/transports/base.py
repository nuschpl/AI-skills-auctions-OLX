"""Abstract transport interface. Concrete classes: official, browser."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Advert:
    id: str
    title: str
    price: float
    status: str
    # Category metadata is optional because the baseline `Ads` GraphQL
    # query doesn't request it. The "detailed" variant
    # (`list_my_adverts_detailed`) populates these; the status verb
    # uses them to bucket listings against the limits table.
    category_id: int | None = None
    category_path: str | None = None


class Transport(ABC):
    @abstractmethod
    def get_user(self) -> dict: ...
    @abstractmethod
    def list_my_adverts(self) -> list[Advert]: ...
    def list_my_adverts_detailed(self) -> list[Advert]:
        """Like `list_my_adverts` but also populates `category_id`/`category_path`.

        Concrete transports override this when they can. The default
        falls back to the plain listing so callers don't crash on a
        transport that hasn't implemented detail yet — they'll just see
        every ad as "uncategorised" in the status output.
        """
        return self.list_my_adverts()
    @abstractmethod
    def delete_advert(self, ad_id: str) -> None: ...
    @abstractmethod
    def create_advert(self, payload: dict) -> dict: ...
    @abstractmethod
    def upload_photo(self, path: str) -> dict: ...
