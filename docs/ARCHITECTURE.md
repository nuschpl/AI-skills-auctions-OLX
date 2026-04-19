# OLX Skill — Architecture

Single-page overview. For decisions with rationale see `decisions.md`;
for session state see `CONTEXT.md`; for HTTP endpoint details see
`references/olx-reverse-engineering.md`.

---

## 1. Big picture

```
User / Claude agent
       │
       ▼
  scripts/olx_api.py  ←─── OLX facade (single entry point for all verbs)
       │
       ├── CapabilityRouter (scripts/capabilities.py)
       │     resolves: which transport can do this operation?
       │
       ├── BrowserTransport  (scripts/transports/browser.py)
       │     auth:   Chrome cookies + localStorage (see §3)
       │     ops:    create / list / delete / upload_photo / search
       │
       └── OfficialTransport (scripts/transports/official.py)
             auth:   OAuth2 Partner API (OLX developer app — needs approval)
             ops:    create / list / delete  [upload_photo: NotImplementedError]
```

`auto` mode (default) prefers `OfficialTransport` when tokens exist,
falls back to `BrowserTransport`.

---

## 2. Module map

```
scripts/
  olx_api.py          — OLX facade + verb routing (new / manage / status / promote)
  capabilities.py     — CapabilityMatrix: maps (operation, transport) → bool
  config.py           — load_config(), OLXConfig dataclass, SCRATCH_DIR / TOKENS_PATH etc.
  auth_browser.py     — Chrome cookie extraction, session builder, validity probe
  auth_oauth.py       — OLX Partner API OAuth2 (authorize URL, token exchange, refresh)
  auth_cognito.py     — Cognito PKCE flow (pl-idp.login.olx.com), browser-free refresh
  http_recorder.py    — opt-in HTTP recorder (OLX_RECORD=1), writes xhr-recordings/
  transports/
    base.py           — Transport ABC, Advert dataclass
    browser.py        — BrowserTransport (cookie-based)
    official.py       — OfficialTransport (Partner API)
  listing_create.py   — olx new: photo sourcing, rclone adapter, create flow
  listing_manage.py   — olx manage: list + delete
  listing_status.py   — olx status: active ads vs. per-category limits
  listing_limits.py   — BUCKETS, HARD_BLOCKERS, limit lookup
  promotions.py       — olx promote (Chrome MCP only, NotImplementedError for API)
  competitors.py      — HTML parser for search results
  competitor_samples.py — price ladder builder (min/p25/median/p75/max)
  price_stats.py      — compute_stats()
  photos.py           — strip_gps(), normalise_photo()
  inbox.py            — local-disk photo inbox scanner
  inbox_rclone.py     — rclone-backed Drive inbox (default)
  bootstrap_dryrun.py — DUMMY_LISTING runner (dev/test only)
  mcp_bridge.py       — file-based IPC for Chrome MCP agent hand-off

references/
  olx-reverse-engineering.md   — auth stack, all HTTP endpoints, gotchas
  olx-listing-limits.md        — per-category free limits (Załącznik nr 3 V41)
  xhr-recordings/bootstrap.json — live capture: create + upload + deactivate
  xhr-recordings/              — future captures land here (OLX_RECORD=1)
```

---

## 3. Auth stack (fully decoded 2026-04-19)

```
Google OAuth2 (OIDC, federated)
       │
       ▼
AWS Cognito  Pool: eu-west-1_dUjFuvTf4
             Hosted UI: pl-idp.login.olx.com    ← OLX-branded domain
             Client ID: 6j7elk01p32o648o1io8lvhhab
             Scopes:    openid profile email offline_access
       │ issues: id_token (≈1400 ch), access_token (≈1075 ch), refresh_token (≈3228 ch)
       ▼
OLX frontend  (auth0-spa-js SDK, audience "default")
  localStorage: @@auth0spajs@@::<client_id>::default::<scopes>
    → body.access_token   Cognito access_token  (NOT sent to OLX APIs)
    → body.refresh_token  long-lived, used for silent refresh
    → body.id_token       Cognito id_token      (used as Bearer by OLX APIs)
  cookies on .olx.pl:
    access_token   = Cognito id_token   (token_use: id)  ← OLX misnames this
    apollo-tk      = short-lived Apollo CDN JWT (aud: Apollo, ≈205 ch, TTL ≈1h)
    auth_state     = opaque session marker
```

**Key subtlety:** the OLX cookie named `access_token` is a Cognito
**id_token**, not an access token. Its `token_use` claim is `"id"`.
OLX's backend validates it as Bearer. Don't confuse the two.

### Auth sources by method

| Method | Token source | Notes |
|---|---|---|
| `auth_browser.py` (current default) | Chrome on-disk SQLite (`browser_cookie3`) | Stale if Chrome is running; misses in-memory refresh |
| `auth_applescript.py` (TODO) | Chrome localStorage via AppleScript JS | Always fresh; needs *Allow JavaScript from Apple Events* once |
| `auth_cognito.py` (new) | `$OLX_SKILL_HOME/cognito_tokens.json` | Browser-free after one `run_pkce_flow()` |

### apollo-tk (status 2026-04-19)

Short-lived CDN JWT for `ireland.apollo.olxcdn.com` photo uploads.
**Mint endpoint unknown** — it does NOT appear in cookies from page
loads. Likely triggered by the photo upload UI interaction in the
posting form. Next step: run `OLX_RECORD=1` during a real photo upload
to capture the mint request automatically.

Workaround until resolved: open `https://www.olx.pl/d/nowe-ogloszenie/`
in Chrome and click the photo upload area before running `olx new`.

---

## 4. Data flow: `olx new`

```
1. load_config()             → OLXConfig
2. resolve photo set         → list[Path] (rclone or local inbox)
3. fetch_listing(slug)       → (photos: list[Path], notes_text: str|None)
4. vision + notes            → structured draft (Claude in-context)
5. competitor search         → price ladder (p25/median/p75)
6. user approval             → approved payload dict
7. photos.strip_gps + normalise_photo
8. BrowserTransport.upload_photo × N  → list of Apollo filenames
9. BrowserTransport.create_advert    → {id, url}
10. print ad URL + remind user to rename Drive folder
```

Steps 8–9 require both `access_token` (Bearer for posting-services)
and `apollo-tk` (Bearer for ireland.apollo.olxcdn.com). If apollo-tk
is missing, step 8 raises `RuntimeError("apollo_token missing")`.

---

## 5. Key external hosts

| Host | Used for | Auth |
|---|---|---|
| `www.olx.pl/api/v1/users/me/profile/extended/` | session validity probe | Bearer access_token |
| `production-graphql.eu-sharedservices.olxcdn.com/graphql` | list / deactivate ads | Bearer access_token |
| `posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers` | create advert | Bearer access_token + postingId header |
| `ireland.apollo.olxcdn.com/v1/temp-files` | photo upload | Bearer apollo-tk |
| `pl-idp.login.olx.com/oauth2/token` | Cognito token refresh (PKCE) | client_id + code/refresh_token |
| `pl-idp.login.olx.com/oauth2/authorize` | PKCE authorization URL | — |

---

## 6. File layout for state / config

All runtime state is under `$OLX_SKILL_HOME` (default `~/.olx-skill/`),
never inside the skill repo. This lets the skill work identically from a
dev clone and from a plugin install.

```
~/.olx-skill/
  config.json          — OLXConfig (mode, default_location, inbox_rclone, …)
  venv/                — editable install of this skill (pip install -e .)
  cognito_tokens.json  — Cognito PKCE tokens (chmod 0o600)
  scratch/<slug>-<ts>/ — downloaded photos, cleaned up after run
```

Repo-local state (gitignored or auto-generated):
```
references/xhr-recordings/  — HTTP captures (OLX_RECORD=1)
cache/                       — DEPRECATED, kept only for legacy migration
olx_skill.egg-info/          — setuptools, never committed
```

---

## 7. Testing approach

- **No live network in tests.** All HTTP mocked via `responses` library.
- **No Chrome in tests.** `browser_cookie3` calls are patched.
- **No real files.** `tmp_path` fixtures for disk I/O.
- Run: `pytest tests/` — currently **87 tests** in ~0.7 s.
- Pattern file: `tests/test_transports_browser.py` (most complete example).

---

## 8. What stays browser-only (permanent)

- **Paid promotions** (`olx promote`): OLX Partner API doesn't expose
  promotion packages. Chrome MCP is the only path. `apply_promotion`
  raises `NotImplementedError` until a live capture populates it.
- **Photo upload workaround**: if apollo-tk can't be obtained via API,
  the skill falls back to requiring a one-time Chrome interaction.
