"""Price statistics (pure, stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median, quantiles


@dataclass
class PriceStats:
    count: int
    min: float
    max: float
    median: float
    p25: float
    p75: float
    outliers: list[float]


def compute_stats(prices: list[float], *, iqr_multiplier: float = 1.5) -> PriceStats:
    if not prices:
        raise ValueError("prices must be non-empty")
    sorted_prices = sorted(prices)
    if len(sorted_prices) >= 4:
        q = quantiles(sorted_prices, n=4, method="inclusive")
        p25, _, p75 = q[0], q[1], q[2]
    else:
        p25 = sorted_prices[0]
        p75 = sorted_prices[-1]
    iqr = p75 - p25
    low = p25 - iqr_multiplier * iqr
    high = p75 + iqr_multiplier * iqr
    outliers = [p for p in sorted_prices if p < low or p > high]
    kept = [p for p in sorted_prices if p not in outliers]
    core = kept or sorted_prices
    return PriceStats(
        count=len(sorted_prices),
        min=min(core),
        max=max(core),
        median=median(core),
        p25=p25,
        p75=p75,
        outliers=outliers,
    )
