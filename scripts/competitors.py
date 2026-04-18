"""Parse OLX search result pages.

OLX renders listings with `data-cy="l-card"` on each card (2024-2026 markup).
The title sits in an `<h6>` or `<h4>`; the wider `[data-cy="ad-card-title"]`
wrapper element also contains the price, so we avoid it for the title.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class SearchResult:
    id: str
    title: str
    price: float
    url: str


_PRICE_RE = re.compile(r"(\d[\d\s]*)\s*zł", re.IGNORECASE)


def parse_search_html(html: str) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('[data-cy="l-card"]')
    out: list[SearchResult] = []
    for c in cards:
        a = c.select_one("a[href]")
        if not a:
            continue
        href = a.get("href", "")
        if href.startswith("/"):
            href = "https://www.olx.pl" + href
        # Prefer <h6>/<h4> (title-only) over [data-cy=ad-card-title] (title+price).
        title_el = c.select_one("h6, h4")
        if title_el is None:
            title_el = c.select_one('[data-cy="ad-card-title"]')
        title = title_el.get_text(strip=True) if title_el else ""
        price_el = c.select_one(
            '[data-testid="ad-price"], p.price'
        )
        price = 0.0
        if price_el:
            m = _PRICE_RE.search(price_el.get_text())
            if m:
                price = float(m.group(1).replace(" ", ""))
        ad_id = c.get("id") or a.get("data-id")
        if not ad_id:
            tail = href.rsplit("-", 1)[-1]
            ad_id = tail.split(".")[0]
        out.append(SearchResult(id=str(ad_id), title=title, price=price, url=href))
    return out
