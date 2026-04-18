"""Skill configuration persisted to cache/config.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Mode = Literal["auto", "official", "browser"]

DEFAULT_CONFIG = {
    "mode": "auto",
    # Shape: {"city": "...", "district": "..."}. Intentionally empty by
    # default — user sets this in their local (gitignored) cache/config.json
    # so personal location isn't baked into the distributed code.
    "default_location": {},
    "inbox_path": None,
    "inbox_rclone": None,
    "user_id": None,
}

VALID_MODES = {"auto", "official", "browser"}


@dataclass
class Config:
    mode: Mode = "auto"
    default_location: dict = field(default_factory=dict)
    inbox_path: str | None = None
    # When set, the OLX inbox lives on Google Drive (or any rclone remote)
    # rather than a synced local folder. Shape: {"remote": "olx-gdrive",
    # "path": "OLX"}. Takes precedence over inbox_path if both are set.
    inbox_rclone: dict | None = None
    user_id: str | None = None


def load_config(path: Path) -> Config:
    if not path.exists():
        cfg = Config()
        save_config(cfg, path)
        return cfg
    data = json.loads(path.read_text())
    if data.get("mode") not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {data.get('mode')!r}")
    return Config(
        mode=data["mode"],
        default_location=data["default_location"],
        inbox_path=data.get("inbox_path"),
        inbox_rclone=data.get("inbox_rclone"),
        user_id=data.get("user_id"),
    )


def save_config(cfg: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False))
