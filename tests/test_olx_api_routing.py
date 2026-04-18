from unittest.mock import MagicMock
from scripts.olx_api import OLX


def test_list_my_adverts_routes_to_browser_when_no_tokens():
    browser = MagicMock()
    browser.list_my_adverts.return_value = []
    official = MagicMock()
    api = OLX(official=official, browser=browser, mode="auto", has_tokens=False)
    api.list_my_adverts()
    browser.list_my_adverts.assert_called_once()
    official.list_my_adverts.assert_not_called()


def test_list_my_adverts_routes_to_official_in_auto_with_tokens():
    browser = MagicMock()
    official = MagicMock()
    official.list_my_adverts.return_value = []
    api = OLX(official=official, browser=browser, mode="auto", has_tokens=True)
    api.list_my_adverts()
    official.list_my_adverts.assert_called_once()
    browser.list_my_adverts.assert_not_called()


def test_apply_promotion_always_browser():
    browser = MagicMock()
    official = MagicMock()
    api = OLX(official=official, browser=browser, mode="official", has_tokens=True)
    api.apply_promotion("a1", "top")
    browser.apply_promotion.assert_called_once_with("a1", "top")
    official.apply_promotion.assert_not_called()
