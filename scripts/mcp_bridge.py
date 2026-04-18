"""Hand-off format between Python scripts and the Claude Code agent.

Python scripts cannot call MCP tools directly. When a Python flow needs
a UI action, it writes a JSON instruction file; the agent reads it,
executes the MCP calls, writes back a result file.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

BRIDGE_DIR = Path("cache/mcp_bridge")


def request(op: str, payload: dict) -> Path:
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    req_path = BRIDGE_DIR / f"{ts}.{op}.request.json"
    req_path.write_text(
        json.dumps({"op": op, "payload": payload}, ensure_ascii=False, indent=2)
    )
    return req_path


def await_result(req_path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    res_path = req_path.with_name(req_path.name.replace(".request.json", ".result.json"))
    t0 = time.time()
    while time.time() - t0 < timeout:
        if res_path.exists():
            return json.loads(res_path.read_text())
        time.sleep(1.0)
    raise TimeoutError(f"MCP bridge timed out waiting for {res_path}")
