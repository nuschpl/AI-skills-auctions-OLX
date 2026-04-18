"""Dummy-listing smoke test.

Posts a realistic, unrelated low-value item (bike light set), verifies the
live URL, captures XHR traces, then deletes the listing. Never uses the
word 'test'. Credibility rules enforced by keeping the payload identical
to a real seller's listing.

Invoke via SKILL.md `olx bootstrap` — the Claude Code agent drives the
Chrome MCP steps and this script orchestrates + verifies.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.mcp_bridge import await_result, request

DUMMY_LISTING = {
    "title": "Lampki rowerowe LED komplet, przód + tył, USB",
    "description": (
        "Sprzedam komplet lampek rowerowych LED — przednia biała i tylna "
        "czerwona, ładowane przez USB-C. Używane kilka razy, stan bardzo "
        "dobry, bez śladów użytkowania. Mocowanie gumką, pasuje na każdą "
        "kierownicę i sztycę. Odbiór osobisty Warszawa Śródmieście lub wysyłka "
        "InPost za pobraniem."
    ),
    "price": 35,
    "currency": "PLN",
    "category_hint": "Rowery > Akcesoria rowerowe",
    "location": {"city": "Warszawa", "district": "Śródmieście"},
    "condition": "used",
}


def run() -> dict:
    """Returns a report dict. Agent will print it."""
    report: dict = {"steps": []}

    req = request("bootstrap_create", {"listing": DUMMY_LISTING})
    report["steps"].append({"step": "create", "request": str(req)})
    result = await_result(req)
    report["steps"].append({"step": "create_result", "result": result})

    ad_url = result.get("ad_url")
    ad_id = result.get("ad_id")
    report["ad_url"] = ad_url
    report["ad_id"] = ad_id

    if not ad_id:
        report["status"] = "create_failed"
        return report

    from scripts.auth_browser import build_session_from_cookies, load_chrome_cookies
    cookies = load_chrome_cookies()
    sess = build_session_from_cookies(cookies)
    r = sess.get(ad_url, timeout=15)
    report["verify_status"] = r.status_code

    del_req = request("bootstrap_delete", {"ad_id": ad_id})
    del_result = await_result(del_req)
    report["steps"].append({"step": "delete_result", "result": del_result})

    captured = result.get("captured_xhr", [])
    Path("references/xhr-recordings").mkdir(parents=True, exist_ok=True)
    Path("references/xhr-recordings/bootstrap.json").write_text(
        json.dumps(captured, indent=2, ensure_ascii=False)
    )
    report["captured_count"] = len(captured)
    report["status"] = "ok" if del_result.get("deleted") else "delete_failed"
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
