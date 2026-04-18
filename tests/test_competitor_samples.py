"""Tests for competitor sample picking.

Focus: the picker anchors at the right price points, dedupes, and the
renderer produces a table the agent can paste into the draft.
"""
from scripts.competitor_samples import CompetitorSample, pick_samples, render
from scripts.competitors import SearchResult
from scripts.price_stats import compute_stats


def _mk(id: str, title: str, price: float) -> SearchResult:
    return SearchResult(id=id, title=title, price=price, url=f"https://olx.pl/{id}")


def test_pick_samples_covers_five_anchors_on_wide_distribution():
    results = [
        _mk(str(i), f"item {i}", float(p))
        for i, p in enumerate([20, 30, 45, 50, 55, 60, 65, 70, 80, 100])
    ]
    stats = compute_stats([r.price for r in results])

    samples = pick_samples(results, stats)
    labels = [s.label for s in samples]
    assert labels == ["min", "p25", "mediana", "p75", "max"]

    # Anchor prices should reflect the stats
    anchors_by_label = {s.label: s.anchor_price for s in samples}
    assert anchors_by_label["min"] == stats.min
    assert anchors_by_label["p25"] == stats.p25
    assert anchors_by_label["mediana"] == stats.median
    assert anchors_by_label["p75"] == stats.p75
    assert anchors_by_label["max"] == stats.max


def test_pick_samples_dedupes_collapsed_anchors():
    # Three results, all close in price — anchors should collapse to
    # unique listings, not repeat the same one under three labels.
    results = [
        _mk("a", "cheap", 20),
        _mk("b", "mid", 50),
        _mk("c", "expensive", 100),
    ]
    stats = compute_stats([20, 50, 100])
    samples = pick_samples(results, stats)
    seen = {s.result.id for s in samples}
    assert len(seen) == len(samples)  # no duplicates


def test_pick_samples_ignores_zero_and_negative_prices():
    results = [
        _mk("0", "no-price", 0),
        _mk("neg", "negative", -1),
        _mk("1", "real", 50),
    ]
    stats = compute_stats([50])
    samples = pick_samples(results, stats)
    assert len(samples) >= 1
    assert all(s.result.price > 0 for s in samples)


def test_pick_samples_tiebreak_prefers_lower_price_and_shorter_title():
    # Two listings with identical distance from target price; picker
    # should prefer the cheaper one, then the shorter title.
    results = [
        _mk("expensive-long", "A very verbose title for the item", 60),
        _mk("cheap-short", "Short title", 40),
    ]
    stats = compute_stats([40, 60])  # median = 50, equidistant
    samples = pick_samples(results, stats, anchors=(("mediana", "median"),))
    assert len(samples) == 1
    assert samples[0].result.id == "cheap-short"


def test_render_has_label_price_title_url():
    r = _mk("x", "Kask ABUS Smiley 3.0", 55)
    s = CompetitorSample(label="mediana", anchor_price=50.0, result=r)
    out = render([s])
    assert "mediana" in out
    assert "55 zł" in out
    assert "Kask ABUS Smiley 3.0" in out
    assert "https://olx.pl/x" in out


def test_render_empty_is_graceful():
    assert "brak" in render([]).lower()
