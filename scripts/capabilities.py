"""Capability matrix: which transport modes support which operations.

Each op maps to a set of supported modes. `pick_transport` resolves the
concrete mode to use given the user's preference and available auth.
"""
from __future__ import annotations

from typing import Literal

Mode = Literal["official", "browser"]

# "official" is listed only for ops OfficialTransport actually implements.
# In "auto" mode the router prefers official as soon as OAuth tokens exist,
# so advertising a stub here would break a working browser path. Add
# "official" to an op in the same commit that implements it.
CAPABILITIES: dict[str, set[Mode]] = {
    "apply_promotion": {"browser"},
    "create_advert": {"browser"},
    "delete_advert": {"browser"},
    "edit_advert": {"browser"},
    "get_categories": {"browser"},
    "get_user": {"official", "browser"},
    "list_my_adverts": {"browser"},
    # Category-aware listing: only the browser transport's GraphQL
    # query returns category metadata.
    "list_my_adverts_detailed": {"browser"},
    "search_competitors": {"browser"},
    # Partner API has no upload endpoint: images go into the advert
    # payload as public URLs. Never add "official" here.
    "upload_photo": {"browser"},
}


class UnsupportedOperationError(ValueError):
    pass


def pick_transport(
    op: str,
    *,
    mode: str,
    has_tokens: bool,
) -> Mode:
    """Pick the transport to use for *op*.

    - If the op supports only one mode, that wins regardless of *mode*.
    - If mode is explicit ("official" or "browser"), use it if supported, else error.
    - If mode is "auto", prefer "official" when tokens exist, else "browser".
    """
    if op not in CAPABILITIES:
        raise UnsupportedOperationError(f"unknown operation {op!r}")
    supported = CAPABILITIES[op]
    if len(supported) == 1:
        return next(iter(supported))
    if mode in ("official", "browser"):
        if mode not in supported:
            raise UnsupportedOperationError(
                f"operation {op!r} not supported in {mode!r} mode"
            )
        return mode  # type: ignore[return-value]
    if has_tokens and "official" in supported:
        return "official"
    if "browser" in supported:
        return "browser"
    return next(iter(supported))
