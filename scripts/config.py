"""Skill configuration and user-state paths.

User-specific state (config, tokens, scratch dirs, venv) lives under
``$OLX_SKILL_HOME`` — default ``~/.olx-skill/`` — **not inside the skill
repo**. Reason: when the skill is installed as a plugin, its directory
at ``~/.claude/plugins/cache/<marketplace>/<sha>/plugins/olx/skills/OLX``
is volatile (wiped/replaced on ``/plugin marketplace update``). Keeping
state per-user means the same config and tokens work against a dev
clone and a plugin install, and survive updates.

Layout under ``$OLX_SKILL_HOME``::

    config.json              — this Config dataclass, serialised
    tokens.json              — OAuth2 access/refresh tokens (mode=official)
    session.json             — browser-session cookie snapshot (mode=browser)
    app_credentials.json     — developer-app client id/secret
    mcp_bridge/              — Python↔agent request/result files
    scratch/                 — downloaded photos per listing draft
    venv/                    — Python venv with skill dependencies

Legacy state used to live under ``$SKILL_ROOT/cache/``; ``load_config``
migrates it on first read if the new location is empty.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Mode = Literal["auto", "official", "browser"]


def _home() -> Path:
    override = os.environ.get("OLX_SKILL_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".olx-skill"


OLX_SKILL_HOME = _home()
CONFIG_PATH = OLX_SKILL_HOME / "config.json"
TOKENS_PATH = OLX_SKILL_HOME / "tokens.json"
SESSION_PATH = OLX_SKILL_HOME / "session.json"
APP_CREDENTIALS_PATH = OLX_SKILL_HOME / "app_credentials.json"
BRIDGE_DIR = OLX_SKILL_HOME / "mcp_bridge"
SCRATCH_DIR = OLX_SKILL_HOME / "scratch"
VENV_PATH = OLX_SKILL_HOME / "venv"


DEFAULT_CONFIG = {
    "mode": "auto",
    # Shape: {"city": "...", "district": "..."}. Intentionally empty by
    # default — user sets this in their local config.json (under
    # $OLX_SKILL_HOME) so personal location isn't baked into distributed
    # code.
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


def _migrate_legacy_cache(target: Path) -> None:
    """If *target* is missing but an old ``cache/<name>.json`` exists
    next to SKILL.md, copy it once so users keep their existing config
    across the XDG migration.

    Called before writing a fresh default. No-op when *target* already
    exists or when the legacy file doesn't.
    """
    if target.exists():
        return
    # Only migrate when writing to the real CONFIG_PATH — tests using a
    # tmp_path should see pristine defaults, not whatever happens to be
    # in the caller's cwd.
    if target != CONFIG_PATH:
        return
    # Only config.json has a well-defined legacy location worth
    # migrating; tokens/session/credentials users can re-auth if needed.
    if target.name != "config.json":
        return
    legacy = Path("cache/config.json")  # resolved against cwd at call time
    if not legacy.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(legacy.read_text())


def load_config(path: Path | None = None) -> Config:
    """Load config from *path* (default: ``CONFIG_PATH``).

    If *path* is missing, migrate from the legacy ``cache/config.json``
    if present, else write the default and return it.
    """
    path = path or CONFIG_PATH
    _migrate_legacy_cache(path)
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


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False))
