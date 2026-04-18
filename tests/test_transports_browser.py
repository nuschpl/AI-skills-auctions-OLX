import json
import responses
import requests
from scripts.transports.browser import (
    BrowserTransport,
    STATUS_URL,
    GRAPHQL_URL,
    CREATE_URL,
    UPLOAD_URL,
)


@responses.activate
def test_get_user_returns_id_and_city():
    responses.get(
        STATUS_URL,
        json={"data": {"id": "u123", "city": {"name": "Placeholder City"}}},
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    u = t.get_user()
    assert u["id"] == "u123"
    assert u["city"] == "Placeholder City"


@responses.activate
def test_list_my_adverts_uses_graphql_ads_query():
    responses.post(
        GRAPHQL_URL,
        json={
            "data": {
                "myAds": {
                    "ads": {
                        "totalCount": 2,
                        "items": [
                            {"id": "a1", "title": "Kask", "price": 80, "status": "ACTIVE"},
                            {"id": "a2", "title": "Rower", "price": 600, "status": "ACTIVE"},
                        ],
                    }
                }
            }
        },
        status=200,
    )
    t = BrowserTransport(session=requests.Session(), user_id="u123")
    items = t.list_my_adverts()

    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert body["operationName"] == "Ads"
    assert body["variables"]["filters"]["status"] == "ACTIVE"

    assert len(items) == 2
    assert items[0].id == "a1"
    assert items[0].title == "Kask"
    assert items[0].price == 80

    # Regression: OLX GraphQL 400s the whole operation with
    # "Variable $... is never used" when the query declares variables
    # it doesn't reference. Keep the variables we send tightly scoped
    # to what the query body actually uses.
    assert set(body["variables"].keys()) == {"limit", "offset", "filters", "sorting"}


@responses.activate
def test_delete_advert_sends_graphql_deactivate_mutation():
    responses.post(
        GRAPHQL_URL,
        json={"data": {"myAds": {"updateAd": {"adId": "999999999", "status": "SUCCESS", "message": None, "activateResult": None}}}},
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    t.delete_advert("999999999")

    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert body["operationName"] == "UpdateAd"
    assert body["variables"]["adId"] == 999999999
    assert body["variables"]["action"] == "DEACTIVATE"


@responses.activate
def test_delete_advert_raises_on_graphql_error():
    responses.post(
        GRAPHQL_URL,
        json={"errors": [{"message": "Ad not found"}]},
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    import pytest
    with pytest.raises(RuntimeError, match="Ad not found"):
        t.delete_advert("999")


@responses.activate
def test_create_advert_posts_payload_to_posting_services():
    responses.post(
        CREATE_URL,
        json={"data": {"id": 999999999, "url": "https://www.olx.pl/d/oferta/foo-ID1.html", "title": "Foo"}},
        status=200,
    )
    payload = {
        "title": "Lampki rowerowe LED komplet, przód + tył, USB",
        "description": "Opis bardzo długi...",
        "category_id": 4232,
        "city_id": 12345,
        "district_id": 678,
        "parameters": {"price": {"price": "35"}, "state": "used"},
        "person": "Jan Kowalski",
        "email": "seller@example.com",
        "private_business": "private",
        "images": [{"filename": "abc-PL", "rotation": 0, "width": 1280, "height": 960, "url": "https://ireland.apollo.olxcdn.com/v1/files/abc-PL/image"}],
    }
    t = BrowserTransport(session=requests.Session())
    result = t.create_advert(payload)

    assert result["id"] == 999999999
    assert result["url"].startswith("https://www.olx.pl/d/oferta/")

    assert len(responses.calls) == 1
    sent = json.loads(responses.calls[0].request.body)
    # Must include the OLX-mandated defaults
    assert sent["brand"] == "olxpl"
    assert sent["lang"] == "pl"
    # User-supplied fields preserved
    assert sent["title"] == payload["title"]
    assert sent["images"] == payload["images"]
    # postingId header is required by posting-services and must be a UUID
    headers = dict(responses.calls[0].request.headers)
    assert "postingId" in headers
    assert len(headers["postingId"]) == 36
    assert headers["X-Client"] == "DESKTOP"


@responses.activate
def test_upload_photo_posts_raw_jpeg_with_apollo_bearer(tmp_path):
    responses.post(
        UPLOAD_URL,
        json={"data": {"filename": "abc123-PL"}, "links": {}},
        status=201,
    )
    jpeg = tmp_path / "p.jpg"
    jpeg.write_bytes(b"\xff\xd8\xff\xe0FAKE_JPEG_BYTES\xff\xd9")

    t = BrowserTransport(session=requests.Session(), apollo_token="APOLLO_JWT")
    result = t.upload_photo(str(jpeg))

    assert result["filename"] == "abc123-PL"
    assert result["url"] == "https://ireland.apollo.olxcdn.com/v1/files/abc123-PL/image"

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer APOLLO_JWT"
    assert req.headers["Content-Type"] == "image/jpeg"
    # Body must be the raw JPEG bytes, not multipart
    assert req.body == b"\xff\xd8\xff\xe0FAKE_JPEG_BYTES\xff\xd9"


def test_upload_photo_without_apollo_token_raises(tmp_path):
    import pytest
    jpeg = tmp_path / "p.jpg"
    jpeg.write_bytes(b"x")
    t = BrowserTransport(session=requests.Session())
    with pytest.raises(RuntimeError, match="apollo"):
        t.upload_photo(str(jpeg))


@responses.activate
def test_list_my_adverts_detailed_populates_category():
    responses.post(
        GRAPHQL_URL,
        json={
            "data": {
                "myAds": {
                    "ads": {
                        "totalCount": 1,
                        "items": [
                            {
                                "id": "42",
                                "title": "Lampki LED",
                                "price": 35,
                                "status": "ACTIVE",
                                "category": {"id": 4232, "name": "Akcesoria rowerowe"},
                            },
                        ],
                    }
                }
            }
        },
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    items = t.list_my_adverts_detailed()

    assert len(items) == 1
    assert items[0].category_id == 4232
    assert items[0].category_path == "Akcesoria rowerowe"

    body = json.loads(responses.calls[0].request.body)
    assert body["operationName"] == "AdsDetailed"
    assert "category" in body["query"]


@responses.activate
def test_list_my_adverts_detailed_falls_back_on_category_field_error():
    # First call (detailed) fails with GraphQL error; transport must
    # fall back to the plain Ads query so status can still run.
    responses.post(
        GRAPHQL_URL,
        json={"errors": [{"message": "Cannot query field 'category'"}]},
        status=200,
    )
    responses.post(
        GRAPHQL_URL,
        json={
            "data": {
                "myAds": {
                    "ads": {
                        "totalCount": 1,
                        "items": [
                            {"id": "99", "title": "Coś", "price": 1, "status": "ACTIVE"},
                        ],
                    }
                }
            }
        },
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    items = t.list_my_adverts_detailed()

    assert len(items) == 1
    assert items[0].id == "99"
    assert items[0].category_id is None


@responses.activate
def test_list_my_adverts_detailed_falls_back_on_http_400():
    # OLX may reject the whole detailed query with HTTP 400 (not a
    # GraphQL 200+errors shape). Fallback must still kick in.
    responses.post(GRAPHQL_URL, json={"message": "bad request"}, status=400)
    responses.post(
        GRAPHQL_URL,
        json={
            "data": {
                "myAds": {
                    "ads": {
                        "totalCount": 1,
                        "items": [
                            {"id": "99", "title": "Coś", "price": 1, "status": "ACTIVE"},
                        ],
                    }
                }
            }
        },
        status=200,
    )
    t = BrowserTransport(session=requests.Session())
    items = t.list_my_adverts_detailed()

    assert len(items) == 1
    assert items[0].id == "99"
    assert items[0].category_id is None  # fallback: no category info
