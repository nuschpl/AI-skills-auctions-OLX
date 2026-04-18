"""Mode B: inherit session from a logged-in Chrome browser on this machine.

Two tokens matter:

- ``access_token`` cookie on ``.olx.pl`` — the main JWT used as
  ``Authorization: Bearer`` for OLX REST + GraphQL.
- ``apollo-tk`` cookie on ``.olx.pl`` — a short-lived JWT (``aud: Apollo``,
  ~1h TTL) used only for ``ireland.apollo.olxcdn.com`` photo uploads.
"""
from __future__ import annotations

from typing import Tuple

import requests

STATUS_URL = "https://www.olx.pl/api/v1/users/me/profile/extended/"
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def load_chrome_cookies(domain: str = ".olx.pl") -> dict[str, str]:
    """Extract cookies for *domain* from the local Chrome profile."""
    import browser_cookie3
    jar = browser_cookie3.chrome(domain_name=domain)
    return {c.name: c.value for c in jar if c.value}


def extract_tokens(cookies: dict[str, str]) -> dict[str, str | None]:
    """Pull the two bearer tokens out of a cookie dict."""
    return {
        "access_token": cookies.get("access_token"),
        "apollo_token": cookies.get("apollo-tk"),
    }


def build_session_from_cookies(
    cookies: dict[str, str],
    *,
    domain: str = ".olx.pl",
    access_token: str | None = None,
) -> requests.Session:
    """Build a requests session that mirrors a logged-in Chrome tab.

    If *access_token* is None it is read from ``cookies['access_token']``.
    The session sets it as a default ``Authorization: Bearer`` header
    because OLX's REST + GraphQL endpoints require it — the cookie alone
    is not enough.
    """
    sess = requests.Session()
    sess.headers["User-Agent"] = _DEFAULT_UA
    sess.headers["Accept-Language"] = "pl-PL,pl;q=0.9,en;q=0.8"
    for k, v in cookies.items():
        sess.cookies.set(k, v, domain=domain)
    token = access_token if access_token is not None else cookies.get("access_token")
    if token:
        sess.headers["Authorization"] = f"Bearer {token}"
    return sess


def is_session_valid(session: requests.Session) -> Tuple[bool, str | None]:
    try:
        r = session.get(STATUS_URL, timeout=10)
    except requests.RequestException:
        return False, None
    if r.status_code != 200:
        return False, None
    try:
        data = r.json()
    except ValueError:
        return False, None
    user_id = (data.get("data") or {}).get("id")
    return (user_id is not None), (str(user_id) if user_id else None)
