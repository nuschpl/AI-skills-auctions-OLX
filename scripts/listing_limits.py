"""OLX per-category listing limits — data + pure lookup logic.

Source: ``references/olx-listing-limits.md`` (OLX Regulamin Załącznik nr 3,
V41, obowiązuje od 2025-09-29). Re-check that doc if a publish fails
with a limit-related error; OLX revises numbers every few months.

This module is deliberately dependency-free so it can be imported by
the status verb, the create flow's hard-blocker guard, and tests
without dragging in the transports. All limits assume
``private_business="private"`` — we never post as a business.

Data model:

- :data:`BUCKETS` — bucket_id → :class:`Bucket`. Each bucket has a
  human-readable label, its cap, the window (days), and the set of
  ``category_id`` ints it absorbs. A handful of well-known shared
  buckets are encoded (Rowery accessories, Rowery bikes, Motoryzacja
  parts). Most categories are their own singleton bucket.
- :data:`HARD_BLOCKERS` — category_ids that are paid-only for privates.
  A ``create_advert`` call for one of these will be refused by OLX;
  surface a warning at draft time.
- :func:`lookup(category_id)` — returns the applicable Bucket (or
  ``None`` if not in the table), and whether it's a hard blocker.
- :func:`summarise(adverts)` — given a list of Adverts with
  ``category_id`` populated, groups them into buckets and returns a
  list of :class:`BucketStatus` rows for printing.

Coverage note. Only a small slice of the OLX category tree has known
``category_id`` integers in this codebase (the bike-light category 4232
from the bootstrap, plus whatever a status run discovers live). The
table below will grow as we learn IDs from real responses. Until then
:func:`lookup` returns ``None`` for unknown ids and the caller falls
back to the text cheat-sheet. That's the intended v1 behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Bucket:
    """A limit bucket: one or more category_ids sharing a single cap."""

    id: str
    label: str
    limit: int  # 0 = paid-only (hard blocker)
    window_days: int = 30
    category_ids: frozenset[int] = field(default_factory=frozenset)

    @property
    def is_hard_blocker(self) -> bool:
        return self.limit == 0


# --- Shared buckets with verified category IDs -----------------------------
#
# Bike-light category_id=4232 was captured in the bootstrap run. That
# category lives inside "Sport i Hobby / Rowery / Akcesoria rowerowe"
# which shares a cap-of-4 with Części rowerowe and Odzież i obuwie
# rowerowe. We only know one of the three IDs so far; add the rest as
# they surface live (a `myAds` response with category metadata will
# reveal them, as will the autocomplete XHR on the posting form).

# Note: category_ids below marked with `# unverified` are placeholders
# for where we expect the ID to land but haven't seen live data yet.
# Keep the list surgically small — guessing a wrong ID would silently
# misclassify listings. Prefer "unknown bucket" over "wrong bucket".

BUCKETS: dict[str, Bucket] = {
    # Sport i Hobby / Rowery ------------------------------------------------
    "rowery_akcesoria": Bucket(
        id="rowery_akcesoria",
        label="Rowery — akcesoria + części + odzież rowerowa (shared)",
        limit=4,
        window_days=30,
        category_ids=frozenset({4232}),  # Akcesoria rowerowe (from bootstrap)
    ),
    "rowery_bikes": Bucket(
        id="rowery_bikes",
        label="Rowery — kompletne rowery (shared, wszystkie typy)",
        limit=2,
        window_days=30,
        category_ids=frozenset(),  # IDs TBD; populate from live list_my_adverts
    ),
    # Motoryzacja / Części --------------------------------------------------
    "motoryzacja_czesci": Bucket(
        id="motoryzacja_czesci",
        label="Motoryzacja — części samochodowe + motocyklowe + opony + car audio + akcesoria (shared)",
        limit=1,
        window_days=30,
        category_ids=frozenset(),
    ),
}


# --- Singleton buckets (one category_id each) ------------------------------
#
# These are categories where the limit applies only to that category,
# with no sharing. Encoded sparsely: only ones we've either seen live
# or are high-value to warn about.

_SINGLETONS: list[tuple[str, str, int, int, frozenset[int]]] = [
    # (bucket_id, label, limit, window_days, category_ids)
    # Examples — extend as IDs are discovered:
    # ("elektronika_komputery_laptopy", "Elektronika / Komputery / Laptopy", 2, 30, frozenset({...})),
    # ("dom_meble_sofy", "Dom i Ogród / Meble / Sofy i kanapy", 2, 90, frozenset({...})),
]
for _id, _label, _lim, _win, _cats in _SINGLETONS:
    BUCKETS[_id] = Bucket(
        id=_id, label=_label, limit=_lim, window_days=_win, category_ids=_cats
    )


# --- Hard blockers (limit=0, paid-only) ------------------------------------
#
# If a draft resolves to one of these category_ids, the create call
# will be refused. We surface a warning before burning a posting
# attempt. The cheat-sheet lists these by name; populate IDs as we
# learn them.

HARD_BLOCKERS: frozenset[int] = frozenset()  # TODO: populate from live data


# --- Public API ------------------------------------------------------------


def lookup(category_id: int) -> Bucket | None:
    """Return the Bucket that owns *category_id*, or ``None`` if unknown."""
    if category_id is None:
        return None
    for bucket in BUCKETS.values():
        if category_id in bucket.category_ids:
            return bucket
    return None


def is_hard_blocker(category_id: int) -> bool:
    """True if posting to *category_id* will be refused as paid-only."""
    if category_id in HARD_BLOCKERS:
        return True
    b = lookup(category_id)
    return bool(b and b.is_hard_blocker)


@dataclass(frozen=True)
class BucketStatus:
    bucket: Bucket
    used: int
    titles: tuple[str, ...] = ()

    @property
    def remaining(self) -> int:
        return max(0, self.bucket.limit - self.used)

    @property
    def over_limit(self) -> bool:
        return self.used > self.bucket.limit


def summarise(adverts: Iterable) -> tuple[list[BucketStatus], list]:
    """Group *adverts* by bucket and return (rows, unknowns).

    *adverts* is any iterable of objects with ``category_id`` (int or
    None) and ``title`` (str) attributes — typically
    :class:`scripts.transports.base.Advert`.

    - *rows* is one :class:`BucketStatus` per bucket that has >=1 match,
      sorted by bucket id for stable output.
    - *unknowns* is the list of adverts whose category_id did not match
      any known bucket (caller can print "N uncategorised" and fall
      back to the cheat-sheet for those).
    """
    by_bucket: dict[str, list] = {}
    unknowns: list = []
    for ad in adverts:
        cat = getattr(ad, "category_id", None)
        b = lookup(cat) if cat is not None else None
        if b is None:
            unknowns.append(ad)
            continue
        by_bucket.setdefault(b.id, []).append(ad)

    rows = [
        BucketStatus(
            bucket=BUCKETS[bid],
            used=len(ads),
            titles=tuple(a.title for a in ads),
        )
        for bid, ads in sorted(by_bucket.items())
    ]
    return rows, unknowns
