# OLX Quick-Listing Skill — Design

**Date:** 2026-04-18
**Status:** Draft, pending implementation plan.

## Purpose

A Claude Code skill to create and manage OLX.pl listings quickly, minimising browser-UI automation in favour of direct HTTP API calls. The skill handles photo-driven listing drafts (vision analysis + competitor price research), publishing, listing management, and paid promotion packages. It evolves: the first time it encounters a new endpoint it drives the live browser via MCP; subsequent runs call the API directly using cookies pulled from the user's logged-in Chrome session.

## Non-goals

- Handling OLX Business / multi-account scenarios.
- Full-text posting from Claude mobile / web (they can only draft; publish always runs where the OAuth2 tokens live).
- Automatic promotion bidding or price auto-adjustment — user always confirms.

## Platform & Ingestion

- **Mode B (browser)**: Claude Code on whatever machine holds the logged-in OLX browser session. For this user, the Mac.
- **Mode A (official)**: Claude Code on any machine — once a refresh token is obtained it travels with the skill folder. Enables remote/scheduled triggers and headless runs (except initial OAuth2 consent and Mode-B-only ops like paid promotions).
- **Claude on Android** describes photos and drafts listings, but publishes always on whichever machine holds the active auth material.
- **User is on Android**, so photo ingestion uses **Google Drive**:
  - Drive folder: `OLX-Inbox/` (root of user's My Drive).
  - On Mac, synced by Google Drive for Desktop → `~/Library/CloudStorage/GoogleDrive-<YOUR_EMAIL>/My Drive/OLX-Inbox/` (exact path resolved at runtime; skill stores it in `cache/config.json` after first lookup).
  - From Android: Google Photos → Share → **Save to Drive** → choose OLX-Inbox. One tap per batch.
- **Skill behaviour:** `olx new` with no args scans the inbox folder, groups photos by EXIF timestamp bursts, prompts user to pick the set. Processed photos move to `OLX-Inbox/archive/<YYYY-MM-DD-HHMM>/` on success.
- **Text hints (optional):** user can drop a `note.txt` next to a batch (same timestamp or filename stem) with free-form notes — brand, size, defects, min price. The skill feeds it into draft generation.

## Mobile-Proactive Pre-Drafting (v2, deferred)

After the core skill is stable, an optional background daemon (`olx_watcher.py` run via `launchd`) watches the Drive folder. On new photo(s):

1. Vision describe via Anthropic API directly (bypassing Claude Code) → structured metadata.
2. Competitor search + price stats.
3. Save pre-draft to `cache/drafts/<timestamp>.json` including proposed title/price/category.
4. Push notification to the user's phone (Pushover, ntfy.sh, or a Telegram bot — TBD at implementation time).

Then when the user opens Claude Code and runs `olx new`, the skill shows ready pre-drafts for single-keypress approve-and-publish. **Publish always stays interactive and Mac-bound** — the daemon never posts on its own.

This is deferred out of v1 to avoid premature complexity; the core ingest-and-publish flow ships first.

## Transport Strategy

**Two first-class modes.** The skill is shareable — a new user picks whichever they can actually set up. Neither mode is "fallback" for the other; both are fully supported paths.

### Mode A — OAuth2 Partner API (`official`)

- **Flow**: `authorization_code` + `refresh_token`. One-time browser consent; refresh token lives ~30 days; access token auto-renews (1 hour).
- **Scopes**: `read:adverts write:adverts read:profile_package read:leads`.
- **Requires**: a developer-app approval at `developer.olx.pl` (can take days, may have account-type requirements).
- **Pros**: fast, legitimate, stable, TOS-compliant, portable across machines, rate-limited predictably.
- **Cons**: approval gate; scope-limited (paid promotions, some UI-only ops may not be exposed); individual-seller eligibility unconfirmed.
- **Storage**: `client_id`/`client_secret` in `cache/app_credentials.json`; tokens in `cache/tokens.json` (both gitignored, 600 perms).

### Mode B — Browser session (`browser`)

- **Flow**: Python `requests` with cookies extracted from the user's logged-in Chrome via `browser-cookie3`, with `mcp__Claude_in_Chrome__*` for UI-only ops and first-time XHR discovery.
- **Requires**: user logged into OLX in Chrome on the machine running the skill (the existing Google SSO session works).
- **Pros**: zero setup overhead, works for anyone with a browser login, covers UI-only ops that API doesn't (paid promotions), is the only path while API approval is pending.
- **Cons**: Machine-bound (cookies are local), fragile to OLX frontend changes, ToS-grey, may trigger anti-bot flows.
- **Storage**: session cookies cached in `cache/session.json`; refreshed from browser when stale.

### Selection

- `cache/config.json` stores `mode: "official" | "browser" | "auto"`, default `auto`.
- `auto` prefers `official` if `tokens.json` exists and is valid, falls back to `browser`.
- Users who never register a developer app set `mode: "browser"` and the skill never asks about OAuth.
- Advanced: an operation flagged API-only (e.g. future paid-promotion endpoint) or UI-only (current paid promotions) routes to the right mode regardless of preference, and the skill tells the user why.

### Architecture implication

`scripts/olx_api.py` exposes one interface (`create_advert`, `list_adverts`, `delete_advert`, …). Underneath, two implementations: `transports/official.py` and `transports/browser.py`. A thin `transport.py` router picks based on config + per-op capability table.

`references/capability-matrix.md` is the source of truth: for each operation, which modes support it, which is preferred, known limits. Updated as we discover things.

### Unknowns to resolve in implementation

- Whether individual (non-business) OLX accounts can register a developer app. Verified by actually completing the registration flow.
- Photo upload endpoint presence and shape in the Partner API.
- Paid promotion endpoints in the Partner API (assumed absent until proven — stays browser-mode-only).

## Skill Layout

```
~/.claude/skills/OLX/                   # symlink → $SKILL_ROOT (or plugin cache dir)
├── SKILL.md                            # entry instructions + decision flow
├── scripts/
│   ├── auth_oauth.py                   # Mode A: OAuth2 token lifecycle
│   ├── auth_browser.py                 # Mode B: Chrome cookie extraction
│   ├── transport.py                    # mode router, capability table
│   ├── transports/
│   │   ├── official.py                 # OAuth2 API implementation
│   │   └── browser.py                  # cookies + MCP implementation
│   ├── olx_api.py                      # operation interface (create_advert, …)
│   ├── photos.py                       # inbox scan, resize/compress, upload
│   ├── competitors.py                  # similar-listing search + price stats
│   ├── listing_create.py               # end-to-end create flow
│   ├── listing_manage.py               # list/edit/delete/renew
│   ├── promotions.py                   # promotion packages
│   └── bootstrap_dryrun.py             # the verified-post-and-delete flow
├── cache/                              # skill-local state (gitignored)
│   ├── endpoints.json
│   ├── categories.json
│   ├── user.json
│   └── drafts/                         # resume-safe in-progress listings
├── references/
│   ├── category-schemas/
│   ├── promotions.md
│   └── xhr-recordings/                 # captured HAR snippets
└── .venv/                              # gitignored
```

Dependencies: `requests`, `beautifulsoup4`, `Pillow`, `lxml`, `browser-cookie3` (optional, only needed for Mode B).

Auth modules:

- `scripts/auth_oauth.py` — OAuth2 token lifecycle for Mode A. First run: print authorize URL, wait for user to paste callback URL. Exchange → save tokens. Every subsequent call: load, refresh if expired, retry once on 401, re-consent on refresh failure.
- `scripts/auth_browser.py` — Cookie extraction from Chrome (or Firefox, via `browser-cookie3`), session validation, opening a login tab via MCP if cookies are stale.

Both expose an identical `get_session()` → `requests.Session` interface to the transport layer.

## Core Flows

### 1. `olx new` — create a listing

1. **Photo collection.** If arg paths given use them; otherwise scan `OLX-Inbox/` (non-archive). Group by EXIF timestamp bursts. Ask user to confirm the set.
2. **Vision analysis.** Main agent (not a subprocess) describes each photo: object type, brand, model, size/age range, colour, condition hints, visible defects. Combined into structured draft metadata.
3. **Competitor research.** `competitors.py` queries OLX search with 2–3 keyword variants derived from metadata. Pulls top ~20 active listings. Computes price p25/median/p75, common category attribute values, common title patterns. Presents summary + 3–5 example links.
4. **Draft proposal.** Agent proposes `{title, description, price, category_id, attributes, photos, location}` where `location` defaults to `config.default_location` from the user's local gitignored `cache/config.json`; if unset, the agent asks. Re-confirmed every run. User approves or edits field-by-field.
5. **Publish.** `listing_create.py` → create draft via API → upload photos → submit. Returns live URL + ad_id. Records `OLX-Inbox/archive/<ts>/` move.
6. Failure at any HTTP step falls back to browser MCP (same semantic step), records the XHR that succeeds, updates `endpoints.json`.

### 2. `olx manage` — my active ads

- List my ads (id, title, price, status, views, expiry) via API.
- Actions per ad: `edit`, `refresh (odśwież)`, `delete`, `stats`, `promote`.

### 3. `olx promote` — paid packages

- For a given ad_id, fetch available promotion packages + current prices.
- Apply selected package; confirm charge.
- Cache package metadata in `references/promotions.md`.

### 4. `olx bootstrap` — dry-run verification (run once, manually)

Posts a **dummy-but-realistic** item the agent picks (e.g. a low-value common accessory like a used IKEA LED bulb or similar, with real stock-style photo the user provides), in a plausible category, at a plausible price, location taken from `config.default_location` (or a neutral city/district if empty). Verifies live, captures the full XHR trail to `cache/endpoints.json` and `references/xhr-recordings/`, deletes within ~10 minutes. **No word "test" or placeholder copy** — description reads like any casual seller's.

Explicit rule: the first test is *not* run against the user's real helmet. Once bootstrap passes, the real helmet is a normal `olx new` flow.

## Confirmation Contract (always-confirm fields)

Every `olx new` re-confirms with the user before publish:

- Title
- Price
- Category
- Location (default from `config.default_location`)
- Photos (count + order)
- Description (shown in full)

The skill never auto-publishes without explicit approval.

## Credibility Rules

- No "test", "próba", "testowe", "lorem", placeholder, or emoji-only descriptions.
- Price within competitor p25–p75 band unless user overrides.
- Photos must be real photos of the described object.
- Description: 2–6 natural sentences, Polish, includes condition + dimensions/size where applicable, pickup/shipping note.

## Cache & Evolution

- `endpoints.json` — `{operation: {method, url, headers, body_template, discovered_at, last_ok_at}}`. Grows with every MCP-driven discovery.
- `categories.json` — cached category tree with id, name, parent, required/optional attribute ids & value sets. Refreshed on demand or if a create call fails on "unknown attribute".
- `user.json` — my user_id, default city, default delivery options, profile URL.

## Error Handling & Boundaries

- Refresh token invalid/revoked → print OAuth2 consent URL, wait for callback URL paste.
- Developer app not yet approved → skill uses Chrome MCP fallback transparently; logs a one-line notice per run.
- Captcha → stop, ask user to complete in the already-open tab, retry.
- Photo > 8 MB → auto-resize to max 4096px long edge, JPEG quality 88.
- Rate limit (429) → back off, switch to MCP path.
- API mismatch (field renamed, schema drift) → log to `cache/drift.log`, fall back to MCP, update wrapper.

## Testing / Verification

- `bootstrap_dryrun.py` is the end-to-end smoke test. Re-runnable.
- Unit tests only for pure functions in `photos.py` and `competitors.py` (price stats, resize). Network-touching code is exercised through `bootstrap_dryrun.py`, not mocked — mock tests against scraped APIs give false confidence.

## Open / Deferred

- Multi-account support — deferred.
- Cross-posting to Allegro Lokalnie / Vinted — deferred.
- Auto-renew cron — deferred until we see expiry patterns.
- Voice-memo hints from inbox — stubbed; transcription deferred.
