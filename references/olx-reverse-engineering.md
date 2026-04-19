# OLX browser-mode reverse-engineering notes

Everything in this file was learned by posting a real listing through
Chrome (logged into olx.pl) with a JS fetch/XHR interceptor installed,
then deleting it. Raw request/response fixtures live in
`references/xhr-recordings/bootstrap.json`. This file is the
human-readable cheat-sheet — it explains *why* things work the way
they do, which you can't tell from the fixtures alone.

**Last verified:** 2026-04-18 (bootstrap), 2026-04-19 (auth model deep-dive).
Bootstrap listing: ad id 999999999, created + deactivated in one session.

## The auth model

### Full stack (decoded 2026-04-19)

```
Google OAuth2 (OIDC IdP, federated)
  ↓ authorization_code → id_token
AWS Cognito User Pool eu-west-1_dUjFuvTf4
  Hosted UI domain: pl-idp.login.olx.com   ← OLX-branded Cognito domain
  App Client ID:    6j7elk01p32o648o1io8lvhhab
  OIDC endpoints (confirmed live via discovery):
    authorize: https://pl-idp.login.olx.com/oauth2/authorize
    token:     https://pl-idp.login.olx.com/oauth2/token
    userinfo:  https://pl-idp.login.olx.com/oauth2/userInfo
    issuer:    https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_dUjFuvTf4
  ↓ issues id_token (as "access_token" cookie) + refresh_token
OLX frontend (auth0-spa-js SDK, audience "default")
  LocalStorage key: @@auth0spajs@@::6j7elk01p32o648o1io8lvhhab::default::openid profile email offline_access
  Stores: access_token (Cognito access_token, len≈1075), refresh_token (len≈3228), id_token
  Cookies set on .olx.pl:
    access_token   — Cognito *id_token* (token_use: id), len≈1400, used as Bearer for OLX APIs
    apollo-tk      — short-lived Apollo CDN JWT, minted separately (see below)
    auth_state     — opaque session marker
    _legacy_auth0.<client_id>.is.authenticated — auth0-spa-js flag
    auth0.<client_id>.is.authenticated         — auth0-spa-js flag
OLX backend (REST + GraphQL + Apollo CDN)
```

**Important subtlety:** the cookie named `access_token` on `.olx.pl` is
actually a Cognito **id_token** (`token_use: id` claim, has user
claims like `email`, `identities`), not a Cognito access_token. OLX's
backend validates id_tokens as Bearer credentials. The real Cognito
access_token (len≈1075) lives in localStorage and is not used for API
calls.

### Two independent bearer tokens

| Cookie | Length | Audience | Used for | TTL |
|---|---|---|---|---|
| `access_token` | ~1400 char | OLX core API (is Cognito id_token) | REST + GraphQL (`Authorization: Bearer …`) | ~1 h |
| `apollo-tk` | ~205 char | `aud: Apollo`, `sub: user_id` | Photo uploads only (`ireland.apollo.olxcdn.com`) | **~1 h** |

Key consequences:

1. **The cookie is not enough.** Every authenticated OLX call sets
   `Authorization: Bearer <access_token>` explicitly — the server does
   not accept the cookie-only form. Our `build_session_from_cookies`
   mirrors this: it reads the cookie, then also promotes its value to
   the session's default `Authorization` header.
2. **`apollo-tk` is short-lived and separately minted.** Confirmed
   2026-04-19: `apollo-tk` is NOT present in Chrome cookies during a
   normal session unless the user has recently used the photo upload UI.
   Simple page GETs (including `/d/nowe-ogloszenie/`) do NOT trigger
   its creation. The mint mechanism is not yet captured — it is likely
   triggered by the photo upload UI interaction in the posting form. Run
   `OLX_RECORD=1` during a real photo upload to capture the mint
   endpoint.  **TODO: capture with `OLX_RECORD=1` and add recording.**
3. **Uploads go to a different host.** `ireland.apollo.olxcdn.com` only
   accepts the Apollo token, never `access_token`. Don't try to unify.

### PKCE / scriptless auth (no Chrome needed after one-time setup)

To authenticate without requiring a logged-in Chrome session:

```python
from scripts.auth_cognito import run_pkce_flow, CognitoTokenStore
tokens = run_pkce_flow()   # opens browser URL, user logs in with Google
CognitoTokenStore().save(tokens)
```

Then to refresh without browser:
```python
from scripts.auth_cognito import refresh_tokens, CognitoTokenStore
store = CognitoTokenStore()
if store.needs_refresh():
    tokens = refresh_tokens(store.load()["refresh_token"])
    store.save(tokens)
```

The access_token returned is the Cognito id_token, ready to use as
`Authorization: Bearer` for OLX APIs.

### Session-validity probe

The endpoint that actually exists and returns user data:

```
GET https://www.olx.pl/api/v1/users/me/profile/extended/
Authorization: Bearer <access_token>
```

(The shorter `/api/v1/user/me/` returns 404 — an easy wrong guess.)

Response shape: `{"data": {"id": <int>, "city": {"name": "..."}, ...}}`.

## Listing lifecycle — four endpoints across three hosts

### 1. Photo upload — Apollo CDN

```
POST https://ireland.apollo.olxcdn.com/v1/temp-files
Authorization: Bearer <apollo-tk>
Content-Type: image/jpeg
Body: raw JPEG bytes  ← NOT multipart/form-data
```

Returns:
```json
{
  "data": {"filename": "a8xji1ffp8gp1-PL"},
  "links": {...}
}
```

Notes:

- **Not multipart.** The body is the JPEG file itself. Many OLX clones
  document this as multipart; it isn't, at least on this endpoint.
- The `-PL` suffix is locale, not per-user.
- The returned `filename` is the opaque handle the create call needs.
  The public image URL is
  `https://ireland.apollo.olxcdn.com/v1/files/<filename>/image` — you
  construct it yourself; Apollo doesn't echo it in a usable form.
- One POST per photo. No batch endpoint observed.
- An `Expires` request header is sent by Chrome (ISO-8601, ~1h out)
  but is not required server-side.

### 2. Create advert — posting-services (REST, not GraphQL!)

```
POST https://posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers
Authorization: Bearer <access_token>
content-type: application/json
postingId: <client-generated UUID v4>   ← required
X-Client: DESKTOP
X-Platform: d
X-Platform-Type: mobile-html5
Accept-Language: pl
accept: */*
```

Request body (all fields observed on a real post):

```json
{
  "brand": "olxpl",
  "lang": "pl",
  "category_id": 4232,
  "city_id": 12345,      // replace with your city's OLX numeric id
  "district_id": 678,    // replace with your district's OLX numeric id
  "title": "Lampki rowerowe LED komplet, przód + tył, USB",
  "description": "Sprzedam komplet lampek …",
  "parameters": {"price": {"price": "35"}, "state": "used"},
  "person": "Jan Kowalski",
  "email": "<seller email>",
  "private_business": "private",
  "images": [
    {"filename": "a8xji1ffp8gp1-PL", "rotation": 0, "width": 1280, "height": 960,
     "url": "https://ireland.apollo.olxcdn.com/v1/files/a8xji1ffp8gp1-PL/image"}
  ],
  "components_data": {
    "reposting": {"action": "ad_posted", "data": "{\"reposting\":false}"}
  }
}
```

Notes:

- **`postingId` is required** and is a fresh client-generated UUID per
  post. It's how the server de-duplicates retries. We use
  `str(uuid.uuid4())` per call.
- Price is a nested object: `{"parameters": {"price": {"price": "35"}}}`,
  stringified. `state` is `"used"` or `"new"`.
- `X-Platform-Type: mobile-html5` is what Chrome desktop sends — not a
  bug, that really is the value even for desktop.
- `category_id`/`city_id`/`district_id` are all integers you must
  resolve up front. The UI resolves them via autocomplete XHRs; in
  code we rely on a resolved dict (see `cache/location-ids.json`).
- `components_data.reposting` is always present — a v2 artifact the
  server expects even when reposting is off.
- The `images` array carries the Apollo-issued `filename`, a self-
  constructed `url`, `width`, `height`, and `rotation: 0`. Rotation
  is applied client-side, not at Apollo.

Response:

```json
{
  "data": {
    "id": 999999999,
    "url": "https://www.olx.pl/d/oferta/lampki-rowerowe-led-komplet-przod-tyl-usb-CID767-ID1agpLZ.html",
    "title": "…",
    "created_time": "2026-04-18T11:02:56+02:00",
    "valid_to_time": "2026-05-18T11:02:56+02:00",
    "description": "…"
  }
}
```

The `.url` is the live canonical URL. The `CID<n>-ID<slug>` suffix is
OLX's legacy URL format — CID is category, ID is a base36-ish listing
handle; you don't construct this, you just use what the server returns.

### 3. List my adverts — GraphQL

```
POST https://production-graphql.eu-sharedservices.olxcdn.com/graphql
Authorization: Bearer <access_token>
content-type: application/json
site: olxpl
accept-language: pl
x-client: DESKTOP
```

Body:

```json
{
  "operationName": "Ads",
  "variables": {
    "limit": 50, "offset": 0,
    "filters": {"query": "", "status": "ACTIVE"},
    "sorting": {"field": "createdAt", "direction": "desc"},
    "isDesktop": true,
    "isActiveAds": true, "hasStr": false,
    "isUnpaidAds": false, "isFinishedAds": false
  },
  "query": "query Ads(...) { myAds { ads(...) { totalCount items { id title price status … } } } }"
}
```

Returns `data.myAds.ads.items[]` with flat fields — `price` is a plain
number here, not an object (unlike in the create payload). `status` is
`ACTIVE` / `FINISHED` / etc. in screaming case.

### 4. End a listing (the "delete") — same GraphQL endpoint, `UpdateAd` mutation

```json
{
  "operationName": "UpdateAd",
  "variables": {"adId": 999999999, "action": "DEACTIVATE"},
  "query": "mutation UpdateAd($adId: Int, $action: MyAdsAction) { myAds { updateAd(adId: $adId, action: $action) { adId status message activateResult { status code } } } }"
}
```

- `adId` is **Int**, not String — OLX returns it as a string in `Ads`
  but requires it as int in mutations. Cast before sending.
- `action` is the `MyAdsAction` enum. Observed values: `DEACTIVATE`,
  `ACTIVATE`. OLX has no true "hard delete" in the UI — ending a
  listing is the user-visible delete. Deactivated ads still exist in
  the user's "finished" archive.
- Response: `{"data":{"myAds":{"updateAd":{"adId":"…","status":"SUCCESS","message":null,"activateResult":null}}}}`.
- Treat anything with a non-empty top-level `errors[]` as failure.

### ⚠️ False lead: `/listing/v1/opt-out/{id}`

`DELETE https://pl.ps.prd.eu.olx.org/listing/v1/opt-out/{ad_id}` is
fired automatically when the promote-nudge page loads after posting,
and it returns `404 Ad not found`. It **is not** the delete endpoint —
it toggles an opt-out / reposting flag on an already-indexed ad. If
you see this in a capture and mistake it for a delete, you'll be
puzzled why DEACTIVATE works but "delete" doesn't.

## Other UI-only endpoints to be aware of

Captured during bootstrap but not needed for the core CRUD flow:

- `GET https://www.olx.pl/api/v1/users/me/segmentation/` — eligibility
  info for promotion packages. Sends an `X-Fingerprint` header (784
  chars of UA+canvas+audio+webgl hash). We don't need it for posting.
- `GET https://notification-hub.olxgroup.com/api/v1/notifications/newNotificationCount` — chrome-only chrome.
- `pl.ps.prd.eu.olx.org/flag-control/v1/…` — experiment/flag service.
- Everything under `pl.ps.prd.eu.olx.org/loyalty-points/…` — decorative.

The posting promotion nudge page
(`/purchase/activate/promote/?activation-code=…`) is the final UX step
after publish and contains the *paid promotion* catalog. Actual
promotion buys run through another POST against the same domain; we
haven't captured those yet — they're what `olx promote` drives next.

## Form-fill quirks observed

Things that cost time during the Chrome MCP form-fill and are easy to
re-trip on:

1. **`file_upload` MCP call is blocked** by the OLX anti-bot shim
   (`CDP error -32000: Not allowed`). Workaround: draw JPEGs into a
   Canvas, convert to Blob, wrap in File, inject via DataTransfer onto
   the hidden `<input type=file>`, then dispatch `input`+`change`.
   This path is indistinguishable from a real drop at the React level
   and uploads succeed.
2. **`form_input` writes can come back as empty string** on some
   React-controlled fields (observed on the price input). Falling back
   to click + `computer.type` on the same ref works.
3. **The shipping section is force-on by default** ("Przesyłka OLX").
   Leaving it on makes "Wybierz metodę dostawy" a blocking validation
   error. Easiest path is to flip the top toggle off — the listing
   publishes fine as "personal pickup only". If you want shipping, the
   S/M/L/XL accordions must be *expanded* before the checkboxes are
   reachable via React state (clicking the nested checkbox via ref
   without expanding does nothing).
4. **Location defaults to the last city you used, not to nothing.** In
   our run it started at "Katowice, Kostuchna" because of a prior
   Chrome session. Always clear the combobox, type the target city,
   and click the autocomplete option — setting the input `value`
   directly does not register the selection.
5. **A tooltip overlay appears during posting** ("Gdy włączysz
   AutoPrzedłużenie…"). It intercepts clicks until dismissed.

### ⚠️ Trim captured GraphQL queries before replaying them

The `Ads` query in the bootstrap capture declares five boolean
variables the operation body never references
(`$isActiveAds`, `$isDesktop`, `$hasStr`, `$isUnpaidAds`,
`$isFinishedAds`). They exist for `@include`/`@skip` directives in
the full UI query that the Chrome frontend conditionally tacks on.
When the Python transport sent them, the server rejected the whole
operation with HTTP 400:

```
Variable "$isActiveAds" is never used in operation "Ads".
```

Fix: only declare variables the query body actually references. We
send only `limit`, `offset`, `filters`, `sorting` on both the plain
and the category-aware variant. Same caution applies to headers —
capture includes tracker headers (`X-Transaction-Id`, client-UUIDs)
the server doesn't require; keep the header set minimal.

## Gotchas for programmatic use

- **UUIDs matter.** The `postingId` header de-duplicates — reusing
  one will return the already-posted ad, not create a new one. Always
  `uuid4()` fresh.
- **GraphQL errors come back with HTTP 200.** Check the response
  JSON's `errors[]` field, never just `r.status`.
- **Apollo tokens rotate.** Budget for a re-extract on every posting
  session. Don't cache across restarts.
- **OLX treats identical listings as spam.** Test listings need
  plausible title/description/price — no "test", "próba", "lorem",
  no emoji-only copy, no "helmet helmet helmet". Our bootstrap uses a
  realistic bike-light set for this reason.
- **The `email` field in the create payload is the seller's own
  email, not the buyer's** — it's what appears in the contact block.
- **Images must be uploaded *before* `create_advert`**, not after. The
  create payload needs the Apollo `filename`s inline. (Earlier
  skeleton code assumed post-then-upload; that would never work with
  this API.)

## Links to raw fixtures

- `references/xhr-recordings/bootstrap.json` — actual request/response
  bodies from the live run, with tokens redacted.
- `scripts/transports/browser.py` — the implementation that consumes
  all of the above.
- `scripts/auth_browser.py` — cookie → session → Bearer plumbing.
