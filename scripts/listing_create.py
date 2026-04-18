"""End-to-end create flow driver.

Imported by SKILL.md's create flow; contains only deterministic glue.
Photo description and interactive approval live agent-side in SKILL.md.
"""
from __future__ import annotations

from pathlib import Path

from scripts.auth_browser import (
    build_session_from_cookies,
    extract_tokens,
    load_chrome_cookies,
)
from scripts.auth_oauth import TokenStore
from scripts.config import CONFIG_PATH, Config, TOKENS_PATH, load_config
from scripts.inbox_rclone import RemoteListing, list_listings, load_listing
from scripts.olx_api import OLX
from scripts.photos import normalise_photo, strip_gps
from scripts.transports.browser import BrowserTransport
from scripts.transports.official import OfficialTransport


def build_olx() -> OLX:
    cfg = load_config(CONFIG_PATH)

    ts = TokenStore(TOKENS_PATH)
    has_tokens = ts.load() is not None
    official = OfficialTransport(token_store=ts) if has_tokens else None

    browser: BrowserTransport | None
    try:
        cookies = load_chrome_cookies()
        sess = build_session_from_cookies(cookies)
        tokens = extract_tokens(cookies)
        browser = BrowserTransport(session=sess, apollo_token=tokens["apollo_token"])
    except Exception:
        browser = None

    if official is None and browser is None:
        raise RuntimeError(
            "neither mode available: no OAuth tokens and no browser cookies"
        )

    return OLX(
        official=official,
        browser=browser,
        mode=cfg.mode,
        has_tokens=has_tokens,
    )


def source_listings(cfg: Config | None = None) -> list[RemoteListing]:
    """List auction folders from the configured rclone remote.

    Empty list when no rclone source is configured — caller should then
    fall back to ``inbox.scan_inbox(cfg.inbox_path)``.
    """
    cfg = cfg or load_config(CONFIG_PATH)
    if not cfg.inbox_rclone:
        return []
    remote = cfg.inbox_rclone["remote"]
    path = cfg.inbox_rclone["path"]
    return list_listings(remote, path)


def fetch_listing(
    name: str,
    dest: Path,
    cfg: Config | None = None,
) -> tuple[list[Path], str | None]:
    """Download auction *name* from the rclone remote into *dest*."""
    cfg = cfg or load_config(CONFIG_PATH)
    if not cfg.inbox_rclone:
        raise RuntimeError(
            f"inbox_rclone is not configured in {CONFIG_PATH}"
        )
    remote = cfg.inbox_rclone["remote"]
    path = cfg.inbox_rclone["path"]
    return load_listing(remote, path, name, dest)


def prepare_photos(paths: list[Path], work_dir: Path) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for p in paths:
        no_gps = strip_gps(p, out_path=work_dir / f"{p.stem}.nogps.jpg")
        resized = normalise_photo(no_gps, out_dir=work_dir)
        out.append(resized)
    return out


def publish(payload: dict, photos: list[Path]) -> dict:
    """Upload photos first (OLX needs filenames in the create payload), then post."""
    olx = build_olx()
    uploaded = [olx.upload_photo(str(p)) for p in photos]
    payload = {**payload, "images": _images_payload(uploaded)}
    return olx.create_advert(payload)


def _images_payload(uploaded: list[dict]) -> list[dict]:
    """OLX's create payload wants filename + rotation + width + height + url per image."""
    out = []
    for u in uploaded:
        entry = {
            "filename": u["filename"],
            "rotation": 0,
            "url": u["url"],
        }
        raw = u.get("raw") or {}
        # Apollo sometimes echoes width/height; pass them through when available.
        data = (raw.get("data") or {}) if isinstance(raw, dict) else {}
        if "width" in data:
            entry["width"] = data["width"]
        if "height" in data:
            entry["height"] = data["height"]
        out.append(entry)
    return out
