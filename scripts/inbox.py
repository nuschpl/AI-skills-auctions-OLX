"""Inbox: scan a photo dump folder and group by EXIF/mtime bursts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.photos import read_taken_at

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def scan_inbox(folder: Path, *, gap_seconds: int = 120) -> list[list[Path]]:
    """Return bursts of photos in *folder* (non-recursive, ignoring `archive/`)."""
    items: list[tuple[Path, datetime]] = []
    for p in folder.iterdir():
        if p.is_dir():
            continue
        if p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        ts = read_taken_at(p)
        if ts is None:
            continue
        items.append((p, ts))
    return group_by_burst(items, gap_seconds=gap_seconds)


def group_by_burst(
    items: list[tuple[Path, datetime]],
    *,
    gap_seconds: int,
) -> list[list[Path]]:
    items = sorted(items, key=lambda x: x[1])
    bursts: list[list[Path]] = []
    current: list[Path] = []
    last: datetime | None = None
    for p, ts in items:
        if last is None or (ts - last).total_seconds() <= gap_seconds:
            current.append(p)
        else:
            bursts.append(current)
            current = [p]
        last = ts
    if current:
        bursts.append(current)
    return bursts
