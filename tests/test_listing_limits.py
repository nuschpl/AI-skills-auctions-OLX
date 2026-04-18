"""Tests for bucket lookup + summarise."""
from dataclasses import dataclass

from scripts.listing_limits import (
    BUCKETS,
    BucketStatus,
    is_hard_blocker,
    lookup,
    summarise,
)


@dataclass
class _Ad:
    id: str
    title: str
    category_id: int | None = None


def test_lookup_returns_bucket_for_known_category():
    b = lookup(4232)  # Akcesoria rowerowe, shared with Części + Odzież rowerowa
    assert b is not None
    assert b.id == "rowery_akcesoria"
    assert b.limit == 4
    assert b.window_days == 30


def test_lookup_unknown_returns_none():
    assert lookup(99999999) is None


def test_lookup_none_safe():
    assert lookup(None) is None  # type: ignore[arg-type]


def test_is_hard_blocker_false_for_soft_limit_category():
    assert is_hard_blocker(4232) is False


def test_summarise_groups_and_separates_unknowns():
    ads = [
        _Ad(id="1", title="Lampki przednie", category_id=4232),
        _Ad(id="2", title="Tylna lampka", category_id=4232),
        _Ad(id="3", title="Coś zupełnie innego", category_id=None),
        _Ad(id="4", title="Coś z nieznanej kategorii", category_id=777777),
    ]
    rows, unknowns = summarise(ads)

    assert len(rows) == 1
    row = rows[0]
    assert row.bucket.id == "rowery_akcesoria"
    assert row.used == 2
    assert row.remaining == 2  # limit 4, used 2
    assert row.over_limit is False
    assert set(row.titles) == {"Lampki przednie", "Tylna lampka"}

    assert len(unknowns) == 2
    assert {a.id for a in unknowns} == {"3", "4"}


def test_summarise_flags_over_limit():
    ads = [_Ad(id=str(i), title=f"acc-{i}", category_id=4232) for i in range(5)]
    rows, _ = summarise(ads)
    assert rows[0].used == 5
    assert rows[0].remaining == 0
    assert rows[0].over_limit is True


def test_bucket_status_remaining_never_negative():
    bs = BucketStatus(bucket=BUCKETS["rowery_akcesoria"], used=100)
    assert bs.remaining == 0
