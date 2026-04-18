"""Mode B transport: logged-in browser cookies + public-surface endpoints.

Endpoints were reverse-engineered from a live bootstrap dry-run; the
canonical capture lives in ``references/xhr-recordings/bootstrap.json``.

Three hosts are involved:

- ``www.olx.pl`` — REST, used for the session-validity probe only.
- ``production-graphql.eu-sharedservices.olxcdn.com`` — GraphQL endpoint
  for ``Ads`` (list) and ``UpdateAd`` (deactivate = end listing).
- ``posting-services.prd.01.eu-west-1.eu.olx.org`` — REST endpoint for
  ``POST /api/v2/offers`` (create).
- ``ireland.apollo.olxcdn.com`` — photo CDN; uploads use a *separate*
  short-lived Apollo JWT (the ``apollo-tk`` cookie), not the main
  ``access_token``.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import requests

from scripts.transports.base import Advert, Transport

STATUS_URL = "https://www.olx.pl/api/v1/users/me/profile/extended/"
GRAPHQL_URL = "https://production-graphql.eu-sharedservices.olxcdn.com/graphql"
CREATE_URL = "https://posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers"
UPLOAD_URL = "https://ireland.apollo.olxcdn.com/v1/temp-files"
APOLLO_FILE_URL_TEMPLATE = "https://ireland.apollo.olxcdn.com/v1/files/{filename}/image"

# The bootstrap capture pulled OLX's frontend query verbatim, which
# declares five extra boolean variables ($isActiveAds, $isDesktop,
# $hasStr, $isUnpaidAds, $isFinishedAds) used by `@include`/`@skip`
# directives in their full UI query. We don't use any of those
# directives here, so the OLX GraphQL server 400s the operation with
# "Variable $... is never used". Only the four variables the operation
# actually references are declared.
_ADS_QUERY = """query Ads($limit: Int, $offset: Int, $filters: MyAdsAdsFiltersInput, $sorting: MyAdsAdSortingInput) {
  myAds {
    ads(limit: $limit, offset: $offset, filters: $filters, sorting: $sorting) {
      totalCount
      items {
        id
        title
        price
        status
      }
    }
  }
}"""

# Extended variant that also asks for category. Kept separate so the
# base `list_my_adverts` stays stable if OLX changes the category edge
# name — `list_my_adverts_detailed` can fall back cleanly.
#
# Field naming is a best-guess from common GraphQL-over-REST schemas
# (no category shape is shown in the bootstrap capture). If the live
# run returns a `Cannot query field 'category'` error we'll adjust
# here; the caller is already defensive about missing category_id.
_ADS_QUERY_WITH_CATEGORY = """query AdsDetailed($limit: Int, $offset: Int, $filters: MyAdsAdsFiltersInput, $sorting: MyAdsAdSortingInput) {
  myAds {
    ads(limit: $limit, offset: $offset, filters: $filters, sorting: $sorting) {
      totalCount
      items {
        id
        title
        price
        status
        category {
          id
          name
        }
      }
    }
  }
}"""

_UPDATE_AD_MUTATION = """mutation UpdateAd($adId: Int, $action: MyAdsAction) {
  myAds {
    updateAd(adId: $adId, action: $action) {
      adId
      status
      message
      activateResult {
        status
        code
      }
    }
  }
}"""

_POSTING_HEADERS = {
    "content-type": "application/json",
    "X-Client": "DESKTOP",
    "Accept-Language": "pl",
    "X-Platform-Type": "mobile-html5",
    "X-Platform": "d",
    "accept": "*/*",
}

_GRAPHQL_HEADERS = {
    "content-type": "application/json",
    "accept": "*/*",
    "accept-language": "pl",
    "x-client": "DESKTOP",
    "site": "olxpl",
}


class BrowserTransport(Transport):
    def __init__(
        self,
        session: requests.Session,
        *,
        user_id: str | None = None,
        apollo_token: str | None = None,
    ):
        self.session = session
        self.user_id = user_id
        self.apollo_token = apollo_token

    def get_user(self) -> dict:
        r = self.session.get(STATUS_URL, timeout=15)
        r.raise_for_status()
        d = r.json()["data"]
        return {
            "id": d["id"],
            "city": (d.get("city") or {}).get("name"),
            "raw": d,
        }

    def _graphql(self, operation_name: str, query: str, variables: dict) -> dict:
        r = self.session.post(
            GRAPHQL_URL,
            json={"operationName": operation_name, "query": query, "variables": variables},
            headers=_GRAPHQL_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            msg = "; ".join(e.get("message", "?") for e in data["errors"])
            raise RuntimeError(f"graphql {operation_name} error: {msg}")
        return data["data"]

    def list_my_adverts(self) -> list[Advert]:
        data = self._graphql(
            "Ads",
            _ADS_QUERY,
            {
                "limit": 50,
                "offset": 0,
                "filters": {"query": "", "status": "ACTIVE"},
                "sorting": {"field": "createdAt", "direction": "desc"},
            },
        )
        items = (data.get("myAds") or {}).get("ads", {}).get("items", [])
        return [
            Advert(
                id=str(x["id"]),
                title=x["title"],
                price=float(x.get("price") or 0),
                status=str(x.get("status", "unknown")).lower(),
            )
            for x in items
        ]

    def list_my_adverts_detailed(self) -> list[Advert]:
        """Same as ``list_my_adverts`` but asks for category metadata.

        Falls back to the plain query if the server rejects the
        ``category`` field — we only know the name of that edge
        best-effort and OLX may rename it. Callers (the status verb)
        should treat missing ``category_id`` as "uncategorised".
        """
        try:
            data = self._graphql(
                "AdsDetailed",
                _ADS_QUERY_WITH_CATEGORY,
                {
                    "limit": 50,
                    "offset": 0,
                    "filters": {"query": "", "status": "ACTIVE"},
                    "sorting": {"field": "createdAt", "direction": "desc"},
                },
            )
        except (RuntimeError, requests.HTTPError):
            # Category edge name was wrong (or OLX GraphQL 400'd the
            # whole request) — fall back to plain listing so status
            # still prints, just with everything uncategorised.
            return self.list_my_adverts()

        items = (data.get("myAds") or {}).get("ads", {}).get("items", [])
        out: list[Advert] = []
        for x in items:
            cat = x.get("category") or {}
            cat_id = cat.get("id")
            try:
                cat_id_int = int(cat_id) if cat_id is not None else None
            except (TypeError, ValueError):
                cat_id_int = None
            out.append(
                Advert(
                    id=str(x["id"]),
                    title=x["title"],
                    price=float(x.get("price") or 0),
                    status=str(x.get("status", "unknown")).lower(),
                    category_id=cat_id_int,
                    category_path=cat.get("name"),
                )
            )
        return out

    def delete_advert(self, ad_id: str) -> None:
        """End a listing (OLX's DEACTIVATE action — equivalent to user-initiated delete)."""
        self._graphql(
            "UpdateAd",
            _UPDATE_AD_MUTATION,
            {"adId": int(ad_id), "action": "DEACTIVATE"},
        )

    def create_advert(self, payload: dict) -> dict:
        body = {
            "brand": "olxpl",
            "lang": "pl",
            "private_business": "private",
            "components_data": {
                "reposting": {"action": "ad_posted", "data": '{"reposting":false}'}
            },
            **payload,
        }
        headers = {
            **_POSTING_HEADERS,
            "postingId": str(uuid.uuid4()),
        }
        r = self.session.post(CREATE_URL, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json().get("data") or {}
        return {
            "id": data.get("id"),
            "url": data.get("url"),
            "title": data.get("title"),
            "raw": data,
        }

    def upload_photo(self, path: str) -> dict:
        if not self.apollo_token:
            raise RuntimeError(
                "apollo_token missing — read the 'apollo-tk' cookie and pass it to BrowserTransport"
            )
        data = Path(path).read_bytes()
        r = self.session.post(
            UPLOAD_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {self.apollo_token}",
                "Content-Type": "image/jpeg",
            },
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        filename = (body.get("data") or {}).get("filename")
        if not filename:
            raise RuntimeError(f"upload returned no filename: {body}")
        return {
            "filename": filename,
            "url": APOLLO_FILE_URL_TEMPLATE.format(filename=filename),
            "raw": body,
        }

    def search_competitors(self, query: str, *, limit: int = 20):
        from scripts.competitors import parse_search_html

        q = query.replace(" ", "-")
        r = self.session.get(
            f"https://www.olx.pl/oferty/q-{q}/",
            timeout=15,
        )
        r.raise_for_status()
        return parse_search_html(r.text)[:limit]

    def apply_promotion(self, ad_id: str, package: str):
        raise NotImplementedError(
            "apply_promotion: drive via Chrome MCP — "
            "endpoint mapping happens during first manual run"
        )
