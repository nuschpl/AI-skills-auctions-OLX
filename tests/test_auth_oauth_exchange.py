import json
import time
from pathlib import Path

import pytest
import responses

from scripts.auth_oauth import (
    DEFAULT_SCOPE,
    TOKEN_URL,
    AppCredentials,
    TokenStore,
    exchange_code_for_tokens,
    load_app_credentials,
    refresh_tokens,
)


def test_token_url_is_partner_api_v2():
    # Per developer.olx.pl swagger (partner_api.yaml, components.securitySchemes)
    assert TOKEN_URL == "https://www.olx.pl/api/open/oauth/token"
    assert DEFAULT_SCOPE == "v2 read write"


@responses.activate
def test_exchange_code_saves_tokens(tmp_path: Path):
    responses.post(
        TOKEN_URL,
        json={
            "access_token": "AT",
            "refresh_token": "RT",
            "expires_in": 86400,
            "token_type": "bearer",
            "scope": "v2 read write",
        },
        status=200,
    )
    store = TokenStore(tmp_path / "tokens.json")
    tokens = exchange_code_for_tokens(
        code="c",
        client_id="id",
        client_secret="sec",
        redirect_uri="https://example.com/olx/callback/",
        store=store,
    )
    assert tokens.access_token == "AT"
    assert tokens.refresh_token == "RT"
    assert store.path.exists()
    assert store.load().access_token == "AT"

    body = json.loads(responses.calls[0].request.body)
    assert body == {
        "grant_type": "authorization_code",
        "client_id": "id",
        "client_secret": "sec",
        "code": "c",
        "scope": "v2 read write",
        "redirect_uri": "https://example.com/olx/callback/",
    }


@responses.activate
def test_refresh_tokens_updates_access_and_rotated_refresh(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(
        access_token="OLD",
        refresh_token="RT",
        expires_at=time.time() - 10,
        scope="v2 read write",
    )
    responses.post(
        TOKEN_URL,
        json={
            "access_token": "NEW",
            "refresh_token": "RT2",
            "expires_in": 86400,
            "token_type": "bearer",
            "scope": "v2 read write",
        },
        status=200,
    )
    tokens = refresh_tokens(client_id="id", client_secret="sec", store=store)
    assert tokens.access_token == "NEW"
    assert tokens.refresh_token == "RT2"
    body = json.loads(responses.calls[0].request.body)
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == "RT"


def test_token_store_is_owner_only(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(access_token="a", refresh_token="r", expires_at=1.0, scope="v2")
    assert oct(store.path.stat().st_mode & 0o777) == "0o600"


def test_load_app_credentials(tmp_path: Path):
    p = tmp_path / "app_credentials.json"
    p.write_text(json.dumps({
        "client_id": "123",
        "client_secret": "s",
        "redirect_uri": "https://example.com/olx/callback/",
    }))
    creds = load_app_credentials(p)
    assert creds == AppCredentials(
        client_id="123", client_secret="s",
        redirect_uri="https://example.com/olx/callback/",
    )


def test_load_app_credentials_missing_file_explains(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="developer.olx.pl"):
        load_app_credentials(tmp_path / "nope.json")
