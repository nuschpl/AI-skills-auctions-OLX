# OLX Skill — Decisions & Learnings

Running log, most recent at top. Each entry: what we decided, why, and what it rules out.

---

## 2026-04-18 — v1 implementation landed; Task 14 live-run deferred

**Decision.** All v1 tasks implemented and tested except Task 14 (live
bootstrap run). 35 unit tests pass. Task 14 requires a human-in-the-loop
Chrome MCP session — it's the step where we actually post a dummy listing,
capture XHRs, then delete, so it can't run autonomously in a one-shot
implementation pass.

**Why skip.** Posting a real listing (even a dummy one) is a visible,
rate-limited action that needs the user to drive Chrome MCP with their
logged-in session. Safer and more honest to hand off than to attempt it
unattended.

**Rules out.** Blocking v1 completion on live traffic.

**Next action.** User runs `olx bootstrap` in a Claude Code session with
Chrome MCP enabled; the agent follows SKILL.md's Bootstrap section to
drive the browser, capture XHRs, and delete. Captured endpoints populate
`BrowserTransport.create_advert` and `upload_photo`.

---

## 2026-04-18 — Python 3.13 instead of 3.11

**Decision.** Target Python 3.13 (user's homebrew has 3.13.12, no 3.11).

**Why.** Avoid installing another Python version just for this skill.

**Rules out.** Dependencies that don't yet support 3.13 (none observed
for the current dep set: requests, beautifulsoup4, lxml, Pillow,
browser-cookie3, piexif, pytest, pytest-mock, responses).

---

## 2026-04-18 — OLX search HTML parser notes

**Observed markup (2026-04-18).** Each result card has
`[data-cy="l-card"]` at the root. Title sits in `<h6>`. Price in
`[data-testid="ad-price"]`. The wrapper `[data-cy="ad-card-title"]`
wraps BOTH title and price elements — don't use it for the title alone.
Card id on the root div matches the OLX advert id.

**Implication.** Parser prefers `<h6>`/`<h4>` for title, falls back to
the `ad-card-title` wrapper only if no heading found.

---

## 2026-04-18 — Two first-class transport modes

**Decision.** The skill ships with two equal transport modes: `official` (OAuth2 Partner API) and `browser` (cookies from Chrome + MCP for UI-only ops). Mode picked via `cache/config.json`, default `auto`.

**Why.** Skill is shareable. Requiring the OAuth2 path would block anyone without an approved developer app. Requiring the browser path would block anyone wanting a portable, headless, stable setup. Both have real merit for different users and different operations.

**Rules out.** "Chrome MCP as fallback only" framing. Chrome mode stays permanent — it's also the only known path for paid promotion packages.

**Implications.** Operation interface (`olx_api.py`) has one signature per op, two implementations behind it. Capability matrix in `references/capability-matrix.md` tracks which mode supports what.

---

## 2026-04-18 — OAuth2 Partner API discovered

**Decision.** Pivot from "Chrome cookies only" to having OAuth2 as a first-class path.

**Why.** OLX publishes `api.olxgroup.com` with `authorization_code` + `refresh_token` flow, scopes `read:adverts write:adverts read:profile_package read:leads`. Refresh token ~30 days, access token 1 hour. Legit, fast, portable, TOS-compliant.

**Rules out.** Framing the skill as inherently Mac-bound or inherently fragile. Also rules out `browser-cookie3` as a hard dependency.

**Known gaps in the API (assumed until proven).** Paid promotion packages, possibly photo upload. These stay in Mode B until confirmed.

**Unknowns.** Whether individual-seller accounts can register a developer app. Eligibility verified by walking the registration flow.

**Sources.**
- <https://developer.olx.pl/articles/getting-access-to-api>
- <https://developer.olxgroup.com/docs/authorization-flow>
- <https://developer.olxgroup.com/docs/making-requests-to-the-api>

---

## 2026-04-18 — Android ingestion via Google Drive

**Decision.** Photos captured on Android land in `My Drive/OLX-Inbox/`. Mac reads via Google Drive for Desktop sync (`~/Library/CloudStorage/GoogleDrive-<email>/My Drive/OLX-Inbox/`). `olx new` with no args scans that folder, groups by EXIF bursts, prompts for the set.

**Why.** User is on Android, not iPhone — iCloud Drive path ruled out. User already has a Google account (same as OLX SSO), Drive is one-tap share from Photos, Mac sync is native.

**Rules out.** iCloud Drive, Dropbox, AirDrop, Syncthing (heavier setup), Telegram bot (daemon overhead).

**Deferred.** A background pre-drafting daemon (`olx_watcher.py` via `launchd`) that runs vision + competitor search the moment new photos arrive, pushes a notification to the phone. Added in v2.

---

## 2026-04-18 — Claude-on-claude.ai as optional "drafter", not in v1

**Decision.** v1 does not integrate with claude.ai's Drive connector. Mobile drafting uses Claude mobile directly (attach photo, get draft text); no Drive roundtrip required for v1.

**Why.** Drive connector is read-mostly; writing a draft file back would be manual copy-paste. The v2 Mac daemon autodrafts in the background anyway, making the claude.ai path redundant for the common case. Keep it on a v2 nice-to-have list for edge cases where the user wants to hand-craft a listing from the phone.

**Rules out.** A hard dependency on claude.ai. The skill stands alone on Claude Code.

---

## 2026-04-18 — Location default: per-user, confirm every run

**Decision.** Default location lives in the user's local, gitignored `cache/config.json` (`default_location` key) — not in committed code. Every `olx new` re-prompts to confirm before publish, alongside title, price, category, photos, description. No silent auto-publish.

**Why.** User request. Listings are public commitments; cheap confirmation beats silent mistakes. Keeping the default out of the distributed code also avoids leaking the author's neighbourhood when the skill is shared publicly.

---

## 2026-04-18 — Dummy-but-realistic item for bootstrap, not the real helmet

**Decision.** The first publish/verify/delete test uses an unrelated dummy item (a common low-value object the agent picks, with a real photo the user provides). The user's real helmet is posted later via the normal `olx new` flow.

**Why.** User requested separating test-run credibility risk from a listing they care about. Also means the bootstrap run can be rerun after changes without burning through real inventory.

**Credibility rules.** No "test", "próba", "lorem", placeholder, or emoji-only copy. Price in competitor p25–p75 band. Real photo. 2–6 natural Polish sentences.

---

## 2026-04-18 — Category-schema-per-category, discovered lazily

**Decision.** Category tree cached in `cache/categories.json`. Per-category required/optional attribute definitions pulled on demand when a listing is drafted in that category, cached under `references/category-schemas/<category_id>.json`.

**Why.** 8000+ OLX categories, precomputing all schemas is wasteful and the schemas drift. Lazy fetch, long-lived cache, refresh on schema-mismatch error.

---

## 2026-04-18 — Photo normalisation

**Decision.** Photos auto-resized to max 4096px long edge, JPEG quality 88, max 8 MB. EXIF kept for ordering, stripped of GPS before upload.

**Why.** OLX upload limits + avoid leaking home coordinates in listings.

---

## Open questions parked for implementation

- Mode-A photo upload endpoint (shape? chunked? auth?) — checked against live swagger at implementation time.
- Whether individual-seller accounts get approved for a developer app (and how long it takes).
- Paid promotion package API — try to find; if absent, Mode-B-only permanently.
- Does `browser-cookie3` work against Chrome on Sequoia with the current keychain-encrypted cookies — test during Mode B implementation.
- Rate limits on Mode A (documented?), anti-bot thresholds on Mode B (empirical).
