"""Opt-in HTTP request/response recorder for OLX skill development.

Wraps a ``requests.Session`` to transparently log every request and response
to a JSON file under ``references/xhr-recordings/``.  Tokens and other
sensitive values are redacted before saving.

Usage (dev/capture mode only — never in production runs):

    import os; os.environ["OLX_RECORD"] = "1"
    from scripts.http_recorder import RecordingSession
    import requests

    base_session = requests.Session()
    sess = RecordingSession(base_session, output_path=Path("references/xhr-recordings/session.json"))
    # …use sess exactly like a requests.Session…
    sess.flush()   # writes the file

Or use the context manager form:

    with RecordingSession.capture(base_session, label="apollo_token_hunt") as sess:
        sess.get("https://www.olx.pl/api/…")
    # file written on exit

Why this exists
---------------
Finding undocumented OLX endpoints (e.g. the apollo-tk mint endpoint)
required long Chrome MCP sessions.  Recording every HTTP exchange lets
future sessions just read ``references/xhr-recordings/`` instead of
re-running Chrome.

Recording format
----------------
Each file is a JSON object::

    {
      "_meta": {"label": "…", "captured_at": "…ISO…", "skill_root": "…"},
      "records": [
        {
          "seq": 1,
          "method": "POST",
          "url": "https://…",
          "req_headers": {"Authorization": "[REDACTED]", …},
          "req_body": "…or null…",
          "status_code": 200,
          "resp_headers": {"Content-Type": "application/json", …},
          "resp_body": "…",
          "elapsed_ms": 123
        },
        …
      ]
    }

Redaction rules
---------------
- Any header value that looks like a JWT (``eyJ…``) is replaced with
  ``"[REDACTED-JWT]"``.
- Authorization / Cookie / Set-Cookie header *values* are always redacted.
- Query-string parameters named ``token``, ``access_token``, ``code`` are
  redacted in the saved URL.
"""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-auth-token",
        "x-api-key",
        "x-access-token",
    }
)
_SENSITIVE_QS_PARAMS = frozenset({"token", "access_token", "code", "refresh_token"})


def redact_token(s: str) -> str:
    """Replace JWT-like strings (``eyJ…``) in *s* with ``[REDACTED-JWT]``."""
    return _JWT_RE.sub("[REDACTED-JWT]", s)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_HEADERS:
            out[k] = "[REDACTED]"
        else:
            out[k] = redact_token(v)
    return out


def _redact_url(url: str) -> str:
    """Redact sensitive query-string parameters in *url*."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    qs = parse_qsl(parts.query, keep_blank_values=True)
    redacted = [
        (k, "[REDACTED]" if k.lower() in _SENSITIVE_QS_PARAMS else v) for k, v in qs
    ]
    return urlunsplit(parts._replace(query=urlencode(redacted)))


def _redact_body(body: Any) -> Any:
    """Best-effort redaction of request / response body."""
    if body is None:
        return None
    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            return "<binary>"
        body = text
    if isinstance(body, str):
        return redact_token(body)
    if isinstance(body, dict):
        return {k: _redact_body(v) for k, v in body.items()}
    return body


# ---------------------------------------------------------------------------
# Core recorder
# ---------------------------------------------------------------------------


class RecordingSession:
    """A thin wrapper around ``requests.Session`` that records exchanges.

    Parameters
    ----------
    session:
        The underlying ``requests.Session`` to delegate all HTTP calls to.
    output_path:
        Where the JSON recording will be written.  Parent directories are
        created automatically.  Pass ``None`` to disable file writing (useful
        in unit tests that just want to inspect ``self.records``).
    label:
        Human-readable label stored in ``_meta`` of the recording file.
    auto_flush:
        Write the file after *every* request (safe for long sessions that
        might crash mid-way).  Default ``False`` — call :meth:`flush`
        explicitly, or use the context-manager form.
    """

    def __init__(
        self,
        session: requests.Session,
        output_path: Path | None = None,
        label: str = "unnamed",
        *,
        auto_flush: bool = False,
    ):
        self._session = session
        self.output_path = Path(output_path) if output_path else None
        self.label = label
        self.auto_flush = auto_flush
        self.records: list[dict] = []
        self._seq = 0

    # ------------------------------------------------------------------
    # Delegate attribute access to the underlying session
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        return getattr(self._session, name)

    # ------------------------------------------------------------------
    # HTTP verb shortcuts (same signature as requests.Session)
    # ------------------------------------------------------------------

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        self._seq += 1
        seq = self._seq
        t0 = time.monotonic()

        # Capture request body before sending
        req_body: Any = kwargs.get("json") or kwargs.get("data")

        resp = self._session.request(method, url, **kwargs)

        elapsed_ms = round((time.monotonic() - t0) * 1000)

        # Build record (all values redacted)
        req_headers = dict(self._session.headers)
        req_headers.update(kwargs.get("headers") or {})

        try:
            resp_body: Any = resp.json()
        except Exception:
            resp_body = resp.text[:4000] if resp.text else None

        record = {
            "seq": seq,
            "method": method.upper(),
            "url": _redact_url(url),
            "req_headers": _redact_headers(req_headers),
            "req_body": _redact_body(req_body),
            "status_code": resp.status_code,
            "resp_headers": _redact_headers(dict(resp.headers)),
            "resp_body": _redact_body(resp_body),
            "elapsed_ms": elapsed_ms,
        }
        self.records.append(record)

        if self.auto_flush:
            self.flush()

        return resp

    def get(self, url, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs) -> requests.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url, **kwargs) -> requests.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs) -> requests.Response:
        return self.request("DELETE", url, **kwargs)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Write the current recording to :attr:`output_path`.

        No-op if ``output_path`` is ``None``.
        """
        if self.output_path is None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_meta": {
                "label": self.label,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "record_count": len(self.records),
            },
            "records": self.records,
        }
        self.output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    @contextmanager
    def capture(
        cls,
        session: requests.Session,
        *,
        label: str = "capture",
        recordings_dir: Path | None = None,
    ):
        """Context manager that writes the recording on exit.

        Example::

            with RecordingSession.capture(sess, label="apollo_token_hunt") as rec:
                rec.get("https://www.olx.pl/…")
            # → references/xhr-recordings/apollo_token_hunt_<ts>.json
        """
        if recordings_dir is None:
            here = Path(__file__).resolve().parent.parent
            recordings_dir = here / "references" / "xhr-recordings"
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_label = re.sub(r"[^a-z0-9_-]", "_", label.lower())
        output_path = recordings_dir / f"{safe_label}_{ts}.json"
        rec = cls(session, output_path=output_path, label=label)
        try:
            yield rec
        finally:
            rec.flush()


# ---------------------------------------------------------------------------
# Convenience: wrap session if OLX_RECORD env var is set
# ---------------------------------------------------------------------------


def maybe_record(
    session: requests.Session,
    label: str = "session",
) -> requests.Session | RecordingSession:
    """Return a ``RecordingSession`` when ``OLX_RECORD=1`` is set, else *session*.

    Use this in transport constructors so recording is transparent::

        from scripts.http_recorder import maybe_record
        sess = maybe_record(build_session_from_cookies(cookies), label="browser_transport")
    """
    if os.environ.get("OLX_RECORD", "").strip() == "1":
        here = Path(__file__).resolve().parent.parent
        recordings_dir = here / "references" / "xhr-recordings"
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe = re.sub(r"[^a-z0-9_-]", "_", label.lower())
        path = recordings_dir / f"{safe}_{ts}.json"
        return RecordingSession(session, output_path=path, label=label, auto_flush=True)
    return session
