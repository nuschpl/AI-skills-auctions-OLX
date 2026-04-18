import responses
import requests
from scripts.auth_browser import (
    build_session_from_cookies,
    is_session_valid,
    STATUS_URL,
)


def test_build_session_sets_cookies():
    cookies = {"PHPSESSID": "abc", "user_id": "123"}
    sess = build_session_from_cookies(cookies, domain=".olx.pl")
    assert sess.cookies.get("PHPSESSID", domain=".olx.pl") == "abc"
    assert sess.cookies.get("user_id", domain=".olx.pl") == "123"
    assert "Mozilla" in sess.headers["User-Agent"]


@responses.activate
def test_is_session_valid_true_on_200_with_user():
    responses.get(STATUS_URL, json={"data": {"id": "u123"}}, status=200)
    sess = requests.Session()
    ok, user = is_session_valid(sess)
    assert ok is True
    assert user == "u123"


@responses.activate
def test_is_session_valid_false_on_401():
    responses.get(STATUS_URL, status=401)
    sess = requests.Session()
    ok, user = is_session_valid(sess)
    assert ok is False
    assert user is None
