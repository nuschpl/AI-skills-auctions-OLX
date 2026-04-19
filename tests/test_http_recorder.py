"""Tests for scripts/http_recorder.py."""
import json
from pathlib import Path

import responses
import requests

from scripts.http_recorder import (
    RecordingSession,
    redact_token,
)

_FAKE_URL = "https://example.com/api/resource"

# ---------------------------------------------------------------------------
# RecordingSession — basic capture
# ---------------------------------------------------------------------------


@responses.activate
def test_recording_session_captures_url_method_status():
    responses.get(_FAKE_URL, json={"ok": True}, status=200)

    raw_session = requests.Session()
    rec = RecordingSession(raw_session, output_path=None)
    rec.get(_FAKE_URL)

    assert len(rec.records) == 1
    record = rec.records[0]
    assert record["url"] == _FAKE_URL
    assert record["method"].upper() == "GET"
    assert record["status_code"] == 200


@responses.activate
def test_recording_session_accumulates_multiple_records():
    responses.get(_FAKE_URL, json={}, status=200)
    responses.get(_FAKE_URL, json={}, status=404)

    raw_session = requests.Session()
    rec = RecordingSession(raw_session, output_path=None)
    rec.get(_FAKE_URL)
    rec.get(_FAKE_URL)

    assert len(rec.records) == 2
    assert rec.records[1]["status_code"] == 404


# ---------------------------------------------------------------------------
# RecordingSession — auth header redaction
# ---------------------------------------------------------------------------


@responses.activate
def test_recording_session_redacts_authorization_header():
    responses.get(_FAKE_URL, json={"ok": True}, status=200)

    raw_session = requests.Session()
    raw_session.headers["Authorization"] = (
        "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiJ1c2VyMTIzIn0.signature"
    )
    rec = RecordingSession(raw_session, output_path=None)
    rec.get(_FAKE_URL)

    record = rec.records[0]
    # The module redacts the entire Authorization header value to "[REDACTED]"
    auth_value = record.get("req_headers", {}).get("Authorization", "")
    assert "eyJ" not in auth_value, "JWT payload must not appear in the recording"


# ---------------------------------------------------------------------------
# redact_token
# ---------------------------------------------------------------------------


def test_redact_token_replaces_jwt():
    jwt = (
        "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiJ1c2VyMTIzIn0"
        ".somesignature"
    )
    result = redact_token(jwt)
    assert "eyJ" not in result
    assert "[REDACTED" in result


def test_redact_token_replaces_jwt_inside_string():
    raw = (
        "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiJ1c2VyMTIzIn0.sig"
    )
    result = redact_token(raw)
    assert "eyJ" not in result
    assert "[REDACTED" in result


def test_redact_token_leaves_non_jwt_untouched():
    plain = "hello world"
    assert redact_token(plain) == plain


def test_redact_token_handles_empty_string():
    assert redact_token("") == ""


# ---------------------------------------------------------------------------
# flush / save recording to disk
# ---------------------------------------------------------------------------


@responses.activate
def test_flush_produces_valid_json(tmp_path: Path):
    responses.get(_FAKE_URL, json={"ok": True}, status=200)
    responses.post(_FAKE_URL, json={}, status=201)

    raw_session = requests.Session()
    out_path = tmp_path / "recording.json"
    rec = RecordingSession(raw_session, output_path=out_path)
    rec.get(_FAKE_URL)
    rec.post(_FAKE_URL, json={})
    rec.flush()

    assert out_path.exists()
    with out_path.open() as f:
        data = json.load(f)

    # The file is wrapped: {"_meta": {...}, "records": [...]}
    assert "records" in data
    assert len(data["records"]) == 2


@responses.activate
def test_flush_records_include_expected_keys(tmp_path: Path):
    responses.get(_FAKE_URL, json={"ok": True}, status=200)

    raw_session = requests.Session()
    out_path = tmp_path / "recording.json"
    rec = RecordingSession(raw_session, output_path=out_path)
    rec.get(_FAKE_URL)
    rec.flush()

    with out_path.open() as f:
        data = json.load(f)

    first = data["records"][0]
    assert "url" in first
    assert "method" in first
    assert "status_code" in first
