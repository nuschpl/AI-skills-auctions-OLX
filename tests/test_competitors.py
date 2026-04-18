from pathlib import Path

import pytest

from scripts.competitors import parse_search_html


@pytest.fixture
def search_html() -> str:
    return Path("tests/fixtures/search_kask.html").read_text(encoding="utf-8")


def test_parse_extracts_multiple_listings(search_html):
    listings = parse_search_html(search_html)
    assert len(listings) >= 10


def test_first_listing_has_all_fields(search_html):
    listings = parse_search_html(search_html)
    first = listings[0]
    assert first.id
    assert first.title
    assert "kask" in first.title.lower() or "rower" in first.title.lower()
    assert first.price > 0
    assert first.url.startswith("https://www.olx.pl")


def test_titles_do_not_contain_price_suffix(search_html):
    listings = parse_search_html(search_html)
    for l in listings[:5]:
        assert "zł" not in l.title, f"title {l.title!r} leaked the price"
