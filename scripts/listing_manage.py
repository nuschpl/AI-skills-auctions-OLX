"""List/delete flow glue."""
from __future__ import annotations

from scripts.listing_create import build_olx


def list_mine() -> str:
    olx = build_olx()
    items = olx.list_my_adverts()
    if not items:
        return "(no active ads)"
    lines = []
    for a in items:
        lines.append(f"{a.id}\t{a.status}\t{a.price:>6.0f} zł\t{a.title}")
    return "\n".join(lines)


def delete(ad_id: str) -> None:
    olx = build_olx()
    olx.delete_advert(ad_id)


if __name__ == "__main__":
    print(list_mine())
