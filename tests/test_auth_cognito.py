"""Tests for scripts/auth_cognito.py."""
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import responses

from scripts.auth_cognito import (
    TOKEN_URL,
    CLIENT_ID,
    CognitoTokenStore,
    build_pkce_authorize_url,
    exchange_code,
    refresh_tokens,
)

_REDIRECT_URI = "http://localhost:8765/callback"
_TOKEN_ENDPOINT = TOKEN_URL  # "https://pl-idp.login.olx.com/oauth2/token"

# ---------------------------------------------------------------------------
# build_pkce_authorize_url
# ---------------------------------------------------------------------------


def test_build_pkce_authorize_url_contains_required_params():
    url, _code_verifier = build_pkce_authorize_url(redirect_uri=_REDIRECT_URI)
    parsed = urlparse(url)
    q = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert q["client_id"] == [CLIENT_ID]
    assert q["identity_provider"] == ["Google"]
    assert "code_challenge" in q
    assert q["code_challenge_method"] == ["S256"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == [_REDIRECT_URI]


def test_build_pkce_authorize_url_returns_unique_code_verifier():
    _, verifier1 = build_pkce_authorize_url(redirect_uri=_REDIRECT_URI)
    _, verifier2 = build_pkce_authorize_url(redirect_uri=_REDIRECT_URI)
    assert verifier1 != verifier2


def test_build_pkce_authorize_url_custom_port():
    url, _ = build_pkce_authorize_url(redirect_uri=_REDIRECT_URI, port=9999)
    assert url.startswith("https://")


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


@responses.activate
def test_exchange_code_sends_correct_grant_type():
    responses.post(
        _TOKEN_ENDPOINT,
        json={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600},
        status=200,
    )
    result = exchange_code(
        code="mycode",
        redirect_uri=_REDIRECT_URI,
        code_verifier="myverifier",
    )
    assert result["access_token"] == "AT"

    sent = responses.calls[0].request
    body = dict(pair.split("=") for pair in sent.body.split("&"))
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "mycode"
    assert body["code_verifier"] == "myverifier"


@responses.activate
def test_exchange_code_posts_to_token_endpoint():
    responses.post(
        _TOKEN_ENDPOINT,
        json={"access_token": "AT2", "refresh_token": "RT2", "expires_in": 3600},
        status=200,
    )
    exchange_code(code="x", redirect_uri=_REDIRECT_URI, code_verifier="v")
    assert responses.calls[0].request.url == _TOKEN_ENDPOINT


# ---------------------------------------------------------------------------
# refresh_tokens
# ---------------------------------------------------------------------------


@responses.activate
def test_refresh_tokens_sends_correct_grant_type():
    responses.post(
        _TOKEN_ENDPOINT,
        json={"access_token": "NEW", "refresh_token": "RT2", "expires_in": 3600},
        status=200,
    )
    result = refresh_tokens(refresh_token="old-rt")
    assert result["access_token"] == "NEW"

    sent = responses.calls[0].request
    body = dict(pair.split("=") for pair in sent.body.split("&"))
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == "old-rt"


# ---------------------------------------------------------------------------
# CognitoTokenStore — save / load round-trip
# ---------------------------------------------------------------------------


def test_cognito_token_store_save_and_load_round_trip(tmp_path: Path):
    store = CognitoTokenStore(home=tmp_path)
    expires_at = time.time() + 3600
    store.save({
        "access_token": "AT",
        "id_token": "IT",
        "refresh_token": "RT",
        "expires_at": expires_at,
    })
    assert store.path.exists()
    loaded = store.load()
    assert loaded["access_token"] == "AT"
    assert loaded["id_token"] == "IT"
    assert loaded["refresh_token"] == "RT"
    assert loaded["expires_at"] == expires_at


def test_cognito_token_store_save_derives_expires_at_from_expires_in(tmp_path: Path):
    store = CognitoTokenStore(home=tmp_path)
    before = time.time()
    store.save({"access_token": "AT", "expires_in": 3600})
    loaded = store.load()
    assert loaded["expires_at"] >= before + 3600 - 1


# ---------------------------------------------------------------------------
# CognitoTokenStore — needs_refresh
# ---------------------------------------------------------------------------


def test_cognito_token_store_needs_refresh_true_when_expired(tmp_path: Path):
    store = CognitoTokenStore(home=tmp_path)
    store.save({"access_token": "OLD", "expires_at": time.time() - 10})
    assert store.needs_refresh() is True


def test_cognito_token_store_needs_refresh_true_within_margin(tmp_path: Path):
    # Default margin is 120 s; token expires in 30 s — inside the margin
    store = CognitoTokenStore(home=tmp_path)
    store.save({"access_token": "ALMOST", "expires_at": time.time() + 30})
    assert store.needs_refresh() is True


def test_cognito_token_store_needs_refresh_false_when_fresh(tmp_path: Path):
    store = CognitoTokenStore(home=tmp_path)
    store.save({"access_token": "FRESH", "expires_at": time.time() + 7200})
    assert store.needs_refresh() is False


def test_cognito_token_store_needs_refresh_true_when_no_file(tmp_path: Path):
    store = CognitoTokenStore(home=tmp_path)
    assert store.needs_refresh() is True
