import time
from pathlib import Path

import responses

from scripts.auth_oauth import (
    TOKEN_URL,
    TokenStore,
    exchange_code_for_tokens,
    refresh_tokens,
)


@responses.activate
def test_exchange_code_saves_tokens(tmp_path: Path):
    responses.post(
        TOKEN_URL,
        json={
            "access_token": "AT",
            "refresh_token": "RT",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read:adverts write:adverts",
        },
        status=200,
    )
    store = TokenStore(tmp_path / "tokens.json")
    tokens = exchange_code_for_tokens(
        code="c",
        client_id="id",
        client_secret="sec",
        redirect_uri="http://localhost/cb",
        store=store,
    )
    assert tokens.access_token == "AT"
    assert tokens.refresh_token == "RT"
    assert store.path.exists()
    loaded = store.load()
    assert loaded.access_token == "AT"


@responses.activate
def test_refresh_tokens_updates_access(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    store.save(
        access_token="OLD",
        refresh_token="RT",
        expires_at=time.time() - 10,
        scope="read:adverts",
    )
    responses.post(
        TOKEN_URL,
        json={
            "access_token": "NEW",
            "refresh_token": "RT2",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read:adverts",
        },
        status=200,
    )
    tokens = refresh_tokens(client_id="id", client_secret="sec", store=store)
    assert tokens.access_token == "NEW"
    assert tokens.refresh_token == "RT2"
