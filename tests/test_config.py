from pathlib import Path
import json
import pytest
from scripts.config import Config, load_config, save_config, DEFAULT_CONFIG


def test_default_config_has_required_keys():
    assert set(DEFAULT_CONFIG.keys()) == {
        "mode", "default_location", "inbox_path", "inbox_rclone", "user_id"
    }
    assert DEFAULT_CONFIG["mode"] == "auto"
    # default_location is intentionally empty in the distributed config; the
    # real value lives in the user's $OLX_SKILL_HOME/config.json.
    assert DEFAULT_CONFIG["default_location"] == {}


def test_load_creates_default_when_missing(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    assert cfg.mode == "auto"
    assert cfg.default_location == {}
    assert cfg_path.exists()


def test_save_and_reload_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = Config(
        mode="browser",
        default_location={"city": "Kraków", "district": "Podgórze"},
        inbox_path="/tmp/OLX-Inbox",
        user_id="u123",
    )
    save_config(cfg, cfg_path)
    reloaded = load_config(cfg_path)
    assert reloaded == cfg


def test_load_rejects_invalid_mode(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "mode": "invalid",
        "default_location": {},
        "inbox_path": None,
        "user_id": None,
    }))
    with pytest.raises(ValueError, match="mode must be one of"):
        load_config(cfg_path)


def test_inbox_rclone_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = Config(inbox_rclone={"remote": "olx-gdrive", "path": "OLX"})
    save_config(cfg, cfg_path)
    reloaded = load_config(cfg_path)
    assert reloaded.inbox_rclone == {"remote": "olx-gdrive", "path": "OLX"}
