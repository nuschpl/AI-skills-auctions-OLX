import pytest
from scripts.capabilities import (
    CAPABILITIES,
    pick_transport,
    UnsupportedOperationError,
)


def test_capabilities_covers_required_ops():
    required = {
        "create_advert", "list_my_adverts", "delete_advert",
        "edit_advert", "get_categories", "get_user",
        "search_competitors", "apply_promotion", "upload_photo",
    }
    assert required.issubset(CAPABILITIES.keys())


def test_pick_transport_auto_prefers_official_when_tokens_exist():
    assert pick_transport("list_my_adverts", mode="auto", has_tokens=True) == "official"


def test_pick_transport_auto_falls_back_to_browser_without_tokens():
    assert pick_transport("list_my_adverts", mode="auto", has_tokens=False) == "browser"


def test_pick_transport_browser_mode_uses_browser():
    assert pick_transport("list_my_adverts", mode="browser", has_tokens=True) == "browser"


def test_pick_transport_unknown_op_raises():
    with pytest.raises(UnsupportedOperationError):
        pick_transport("teleport", mode="auto", has_tokens=True)


def test_pick_transport_browser_only_op_routes_to_browser_even_in_official_mode():
    # apply_promotion is browser-only in v1
    assert pick_transport("apply_promotion", mode="official", has_tokens=True) == "browser"
