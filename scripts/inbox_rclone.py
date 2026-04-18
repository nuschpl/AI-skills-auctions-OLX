"""Inbox backed by an rclone remote (Google Drive, etc.).

Model: **folder-per-listing**. Each auction is a subfolder under the
configured OLX root on Drive, containing its photos and an optional
``notes.txt`` with user-supplied hints for the drafting step. Folders
whose name starts with ``_`` (``_posted``, ``_drafts``, …) are ignored —
that's how the user archives published listings without the skill
re-offering them.

``list_listings(remote, path)`` returns :class:`RemoteListing` entries,
one per auction folder. ``load_listing(remote, path, name, dest)``
downloads the photos + notes for the chosen folder into *dest*.

The rclone binary is expected on PATH. Remote config lives in
``~/.config/rclone/rclone.conf``; we don't touch it from Python.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

IMAGE_SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".heic", ".webp")
NOTES_NAMES: tuple[str, ...] = ("notes.md", "notes.txt")

# Materialize Google Docs as Markdown on copy/lsjson. Preserves bullets
# and headings (useful when you write notes in Docs with structure),
# still degrades gracefully for tables/images. Native `.txt` files also
# match — we accept either name.
DRIVE_EXPORT: tuple[str, ...] = ("--drive-export-formats", "md")


@dataclass(frozen=True)
class RemoteItem:
    name: str
    size: int
    mtime: datetime
    id: str


@dataclass(frozen=True)
class RemoteListing:
    """One auction folder on the remote."""

    name: str
    mtime: datetime
    photos: tuple[RemoteItem, ...] = field(default_factory=tuple)
    notes: RemoteItem | None = None


def _run_rclone(args: list[str]) -> str:
    proc = subprocess.run(
        ["rclone", *DRIVE_EXPORT, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"rclone {' '.join(args)} exited {proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout


def _lsjson(remote: str, path: str) -> list[dict]:
    return json.loads(_run_rclone(["lsjson", f"{remote}:{path}"]))


def list_listings(remote: str, path: str) -> list[RemoteListing]:
    """List auction subfolders under ``<remote>:<path>``, newest first.

    Folders starting with ``_`` are skipped (reserved for archive bins
    like ``_posted`` / ``_drafts``). Folders with zero images are also
    skipped (treated as empty scaffolding).
    """
    out: list[RemoteListing] = []
    for entry in _lsjson(remote, path):
        if not entry.get("IsDir"):
            continue
        name = entry["Name"]
        if name.startswith("_"):
            continue
        items = _lsjson(remote, f"{path}/{name}")
        photos: list[RemoteItem] = []
        notes: RemoteItem | None = None
        for child in items:
            if child.get("IsDir"):
                continue
            cname = child["Name"]
            ri = RemoteItem(
                name=cname,
                size=int(child.get("Size", 0)),
                mtime=_parse_rclone_time(child.get("ModTime")),
                id=str(child.get("ID", "")),
            )
            lname = cname.lower()
            if lname in NOTES_NAMES:
                notes = ri
            elif any(lname.endswith(sfx) for sfx in IMAGE_SUFFIXES):
                photos.append(ri)
        if not photos:
            continue
        out.append(
            RemoteListing(
                name=name,
                mtime=_parse_rclone_time(entry.get("ModTime")),
                photos=tuple(sorted(photos, key=lambda x: x.mtime)),
                notes=notes,
            )
        )
    out.sort(key=lambda x: x.mtime, reverse=True)
    return out


def _parse_rclone_time(s: str | None) -> datetime:
    """rclone emits RFC3339 with nanoseconds; Python wants microseconds."""
    if not s:
        return datetime.fromtimestamp(0)
    if "." in s:
        head, _, tail = s.partition(".")
        frac = ""
        rest = ""
        for i, ch in enumerate(tail):
            if ch.isdigit():
                frac += ch
            else:
                rest = tail[i:]
                break
        frac = frac[:6].ljust(6, "0")
        s = f"{head}.{frac}{rest}"
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_listing(
    remote: str,
    path: str,
    name: str,
    dest: Path,
) -> tuple[list[Path], str | None]:
    """Download photos + optional notes for *name* into *dest*.

    Returns ``(photo_paths, notes_text_or_None)``. Uses a single
    ``rclone copy`` of the folder rather than per-file copies — for a
    typical 5-20 photo listing the folder copy is cheaper than N
    round-trips.
    """
    dest.mkdir(parents=True, exist_ok=True)
    _run_rclone(
        [
            "copy",
            f"{remote}:{path}/{name}",
            str(dest),
        ]
    )
    photos: list[Path] = []
    notes_text: str | None = None
    for child in sorted(dest.iterdir()):
        if child.is_dir():
            continue
        lname = child.name.lower()
        if lname in NOTES_NAMES:
            notes_text = child.read_text(encoding="utf-8").strip() or None
        elif any(lname.endswith(sfx) for sfx in IMAGE_SUFFIXES):
            photos.append(child)
    return photos, notes_text
