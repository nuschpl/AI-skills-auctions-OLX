"""Rendering smoke-tests for `olx status`.

The real entry point builds the OLX facade (cookies + token store);
those code paths are exercised elsewhere. Here we just pin the table
shape so a refactor of the formatter doesn't silently drop the
columns the user relies on.
"""
from dataclasses import dataclass

from scripts.listing_limits import summarise
from scripts.listing_status import render


@dataclass
class _Ad:
    id: str
    title: str
    category_id: int | None = None
    category_path: str | None = None


def test_render_includes_bucket_row_and_totals():
    ads = [
        _Ad(id="1", title="Lampki przednie", category_id=4232, category_path="Akcesoria rowerowe"),
        _Ad(id="2", title="Tylna lampka", category_id=4232, category_path="Akcesoria rowerowe"),
    ]
    rows, unknowns = summarise(ads)
    out = render(rows, unknowns, total_active=len(ads))

    assert "Aktywne ogłoszenia: 2" in out
    # Bucket label / numbers present
    assert "Rowery" in out
    assert "4" in out  # limit
    # Pointer to the cheat-sheet
    assert "references/olx-listing-limits.md" in out


def test_render_highlights_full_bucket():
    ads = [_Ad(id=str(i), title=f"a{i}", category_id=4232) for i in range(4)]
    rows, unknowns = summarise(ads)
    out = render(rows, unknowns, total_active=4)
    assert "FULL" in out


def test_render_flags_over_limit():
    ads = [_Ad(id=str(i), title=f"a{i}", category_id=4232) for i in range(5)]
    rows, unknowns = summarise(ads)
    out = render(rows, unknowns, total_active=5)
    assert "OVER LIMIT" in out


def test_render_lists_uncategorised():
    ads = [
        _Ad(id="1", title="Coś nieznanego", category_id=999999, category_path="Foo / Bar"),
    ]
    rows, unknowns = summarise(ads)
    out = render(rows, unknowns, total_active=1)
    assert "Uncategorised: 1" in out
    assert "Coś nieznanego" in out
    assert "Foo / Bar" in out
