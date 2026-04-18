import pytest
from scripts.price_stats import PriceStats, compute_stats


def test_stats_basic():
    prices = [50, 60, 70, 80, 90, 100, 110, 120, 130, 140]
    s = compute_stats(prices)
    assert s.count == 10
    assert s.median == 95.0
    assert s.p25 == 72.5
    assert s.p75 == 117.5
    assert s.min == 50
    assert s.max == 140


def test_stats_ignores_outliers():
    prices = [60, 65, 70, 75, 80, 10000]
    s = compute_stats(prices, iqr_multiplier=1.5)
    assert s.outliers == [10000]
    assert 60 <= s.median <= 80


def test_stats_raises_on_empty():
    with pytest.raises(ValueError):
        compute_stats([])
