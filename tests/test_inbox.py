import os
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from scripts.inbox import scan_inbox, group_by_burst


def _write(p: Path, mtime: datetime) -> None:
    Image.new("RGB", (100, 100)).save(p, format="JPEG")
    ts = mtime.timestamp()
    os.utime(p, (ts, ts))


def test_group_by_burst_clusters_close_timestamps():
    base = datetime(2026, 4, 18, 12, 0, 0)
    items = [
        (Path("a.jpg"), base),
        (Path("b.jpg"), base + timedelta(seconds=10)),
        (Path("c.jpg"), base + timedelta(minutes=30)),
        (Path("d.jpg"), base + timedelta(minutes=30, seconds=5)),
    ]
    groups = group_by_burst(items, gap_seconds=120)
    assert len(groups) == 2
    assert [p.name for p in groups[0]] == ["a.jpg", "b.jpg"]
    assert [p.name for p in groups[1]] == ["c.jpg", "d.jpg"]


def test_scan_inbox_returns_bursts(tmp_path: Path):
    base = datetime(2026, 4, 18, 12, 0, 0)
    _write(tmp_path / "a.jpg", base)
    _write(tmp_path / "b.jpg", base + timedelta(seconds=5))
    _write(tmp_path / "c.jpg", base + timedelta(hours=3))
    (tmp_path / "note.txt").write_text("hi")
    (tmp_path / "archive").mkdir()
    _write(tmp_path / "archive" / "old.jpg", base)

    bursts = scan_inbox(tmp_path)
    assert len(bursts) == 2
    assert [p.name for p in bursts[0]] == ["a.jpg", "b.jpg"]
    assert [p.name for p in bursts[1]] == ["c.jpg"]
