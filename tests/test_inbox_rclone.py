"""Tests for the rclone-backed inbox adapter."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.inbox_rclone import (
    DRIVE_EXPORT,
    RemoteListing,
    list_listings,
    load_listing,
)


def _rclone_result(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_list_listings_skips_underscore_and_empty(monkeypatch):
    """Folders starting with `_` and folders with no images are dropped."""

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        # first lsjson: list the root
        if args[-1] == "olx-gdrive:OLX":
            return _rclone_result(json.dumps([
                {"Name": "kask-junior", "IsDir": True, "ModTime": "2026-04-18T10:00:00Z"},
                {"Name": "_posted", "IsDir": True, "ModTime": "2026-04-18T09:00:00Z"},
                {"Name": "empty-scaffold", "IsDir": True, "ModTime": "2026-04-17T09:00:00Z"},
                {"Name": "stray.txt", "IsDir": False, "ModTime": "2026-04-18T09:00:00Z"},
            ]))
        # listing contents
        if args[-1] == "olx-gdrive:OLX/kask-junior":
            return _rclone_result(json.dumps([
                {"Name": "IMG_1.jpg", "IsDir": False, "Size": 1024,
                 "ModTime": "2026-04-18T10:01:00Z", "ID": "abc"},
                {"Name": "IMG_2.jpg", "IsDir": False, "Size": 2048,
                 "ModTime": "2026-04-18T10:02:00Z", "ID": "def"},
                {"Name": "notes.md", "IsDir": False, "Size": 64,
                 "ModTime": "2026-04-18T10:03:00Z", "ID": "ghi"},
            ]))
        if args[-1] == "olx-gdrive:OLX/empty-scaffold":
            return _rclone_result(json.dumps([
                {"Name": "readme.pdf", "IsDir": False, "Size": 99,
                 "ModTime": "2026-04-17T09:01:00Z", "ID": "zzz"},
            ]))
        raise AssertionError(f"unexpected rclone call: {args}")

    with patch("subprocess.run", side_effect=fake_run):
        result = list_listings("olx-gdrive", "OLX")

    assert len(result) == 1
    listing = result[0]
    assert listing.name == "kask-junior"
    assert [p.name for p in listing.photos] == ["IMG_1.jpg", "IMG_2.jpg"]
    assert listing.notes is not None and listing.notes.name == "notes.md"
    # drive-export flag is injected before every command
    for c in calls:
        assert c[:3] == ["rclone", *DRIVE_EXPORT]


def test_list_listings_sorts_newest_first(monkeypatch):
    def fake_run(args, **kwargs):
        if args[-1] == "olx-gdrive:OLX":
            return _rclone_result(json.dumps([
                {"Name": "old", "IsDir": True, "ModTime": "2026-01-01T00:00:00Z"},
                {"Name": "new", "IsDir": True, "ModTime": "2026-04-18T00:00:00Z"},
            ]))
        if args[-1].endswith(":OLX/old") or args[-1].endswith(":OLX/new"):
            return _rclone_result(json.dumps([
                {"Name": "a.jpg", "IsDir": False, "Size": 1,
                 "ModTime": "2026-01-01T00:00:00Z", "ID": ""},
            ]))
        raise AssertionError(args)

    with patch("subprocess.run", side_effect=fake_run):
        result = list_listings("olx-gdrive", "OLX")

    assert [l.name for l in result] == ["new", "old"]


def test_list_listings_no_notes(monkeypatch):
    def fake_run(args, **kwargs):
        if args[-1] == "olx-gdrive:OLX":
            return _rclone_result(json.dumps([
                {"Name": "hat", "IsDir": True, "ModTime": "2026-04-18T00:00:00Z"},
            ]))
        return _rclone_result(json.dumps([
            {"Name": "pic.jpg", "IsDir": False, "Size": 10,
             "ModTime": "2026-04-18T00:00:00Z", "ID": ""},
        ]))

    with patch("subprocess.run", side_effect=fake_run):
        result = list_listings("olx-gdrive", "OLX")

    assert result[0].notes is None


def test_load_listing_reads_notes_and_photos(tmp_path: Path):
    """load_listing materializes the folder via rclone copy, then classifies."""

    def fake_run(args, **kwargs):
        # simulate rclone copy by dropping files into the dest dir
        dest = Path(args[-1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "IMG_1.jpg").write_bytes(b"x")
        (dest / "IMG_2.jpg").write_bytes(b"y")
        (dest / "notes.md").write_text(
            "# Giro Scamp Jr, rozmiar XS\n- Używany 10 razy\n",
            encoding="utf-8",
        )
        return _rclone_result("")

    with patch("subprocess.run", side_effect=fake_run):
        photos, notes = load_listing(
            "olx-gdrive", "OLX", "kask-junior", tmp_path / "work"
        )

    assert sorted(p.name for p in photos) == ["IMG_1.jpg", "IMG_2.jpg"]
    assert notes is not None
    assert notes.startswith("# Giro Scamp Jr")


def test_load_listing_handles_missing_notes(tmp_path: Path):
    def fake_run(args, **kwargs):
        dest = Path(args[-1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "only.jpg").write_bytes(b"x")
        return _rclone_result("")

    with patch("subprocess.run", side_effect=fake_run):
        photos, notes = load_listing(
            "olx-gdrive", "OLX", "x", tmp_path / "work"
        )

    assert [p.name for p in photos] == ["only.jpg"]
    assert notes is None


def test_rclone_failure_raises(tmp_path: Path):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=[], returncode=3, stdout="", stderr="directory not found"
        )

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="directory not found"):
            list_listings("olx-gdrive", "OLX")
