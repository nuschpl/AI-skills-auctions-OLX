"""Promotion packages (Mode B only in v1).

`BrowserTransport.apply_promotion` raises NotImplementedError until the
first `olx promote` run captures the XHR trail.
"""
from __future__ import annotations

from scripts.listing_create import build_olx


def apply(ad_id: str, package: str) -> dict:
    olx = build_olx()
    return olx.apply_promotion(ad_id, package)
