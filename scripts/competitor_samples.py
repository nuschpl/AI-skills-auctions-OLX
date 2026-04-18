"""Pick a handful of competitor listings anchored at key price points.

Used in the drafting step of ``olx new`` so the user can manually eyeball
the pricing landscape before committing to a number. The agent computes
stats with :func:`scripts.price_stats.compute_stats`, then hands the
same ``SearchResult`` list + stats here to get a render-friendly table.

Design:

- We anchor at the stats' **min**, **p25**, **median**, **p75**, and
  **max** (all computed from the *core* distribution, i.e. with IQR
  outliers already stripped).
- For each anchor we pick the result whose price is closest to it
  (ties → lower price, then shorter title — stable, readable output).
- Each result shows up at most once even if several anchors resolve
  to the same listing (common when ``count`` is small). Fewer rows is
  better than duplicates.
- The output preserves anchor order (cheapest → most expensive) so
  the user reads the price ladder top-down.

Why not just "show 3-5 random examples"? The point is **positioning**:
the user wants to see where their candidate price sits in the
distribution. A min / p25 / median / p75 / max slice answers that
in one glance; random samples don't.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from scripts.competitors import SearchResult
from scripts.price_stats import PriceStats


@dataclass(frozen=True)
class CompetitorSample:
    label: str  # "min", "p25", "mediana", "p75", "max"
    anchor_price: float  # the stat value we aimed for
    result: SearchResult


# Anchor ordering drives the output ordering. "core-min" and "core-max"
# refer to the distribution with IQR outliers stripped — see
# :func:`scripts.price_stats.compute_stats`.
_DEFAULT_ANCHORS: tuple[tuple[str, str], ...] = (
    ("min", "min"),
    ("p25", "p25"),
    ("mediana", "median"),
    ("p75", "p75"),
    ("max", "max"),
)


def pick_samples(
    results: Sequence[SearchResult],
    stats: PriceStats,
    *,
    anchors: Sequence[tuple[str, str]] = _DEFAULT_ANCHORS,
) -> list[CompetitorSample]:
    """Pick one result per price anchor, deduped and price-sorted.

    *anchors* is a list of ``(label, stats_attr)`` pairs — label is the
    human-facing tag; stats_attr is the attribute on :class:`PriceStats`
    to use as the target price. Override only if you want a non-default
    slice of the distribution (e.g. drop max to keep the table short).
    """
    priced = [r for r in results if r.price and r.price > 0]
    if not priced:
        return []

    seen_ids: set[str] = set()
    out: list[CompetitorSample] = []
    for label, attr in anchors:
        target = getattr(stats, attr)
        # Closest price to the anchor, tiebreak: lower price, shorter title.
        best = min(
            priced,
            key=lambda r: (abs(r.price - target), r.price, len(r.title)),
        )
        if best.id in seen_ids:
            continue
        seen_ids.add(best.id)
        out.append(CompetitorSample(label=label, anchor_price=float(target), result=best))

    # Keep anchor-ordering (cheapest → most expensive); it matches how
    # _DEFAULT_ANCHORS is laid out and reads as a price ladder.
    return out


def render(samples: list[CompetitorSample]) -> str:
    """Render samples as a plain-text table the agent can paste into the draft."""
    if not samples:
        return "(brak dopasowanych aukcji konkurencji)"
    lines = []
    # Compact single-line per sample: label + actual price + short title + url
    for s in samples:
        title = s.result.title
        if len(title) > 55:
            title = title[:52] + "..."
        lines.append(
            f"  {s.label:<8} {int(s.result.price):>4} zł  |  {title}\n"
            f"                    {s.result.url}"
        )
    return "\n".join(lines)
