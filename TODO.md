# OLX skill — TODO

Living list. If something here is done, delete the line (don't tick it).
Grouped by whether the work needs a live OLX/Chrome/Drive session.

## Blocked on a live run

- [ ] **First real `olx status` shakedown.** Run it once active listings
      exist. Two branches:
      - If GraphQL `category { id name }` works → capture new
        `category_id`s and grow `scripts/listing_limits.BUCKETS`.
      - If OLX rejects the `category` field → fix
        `_ADS_QUERY_WITH_CATEGORY` in `scripts/transports/browser.py`
        with the actual field name from the error.
- [ ] **Real helmet listing via `olx new`.** End-to-end run through the
      Drive → vision → draft → publish pipeline. Bootstrap only proved
      the dummy bike-light path.
- [ ] **`olx manage` regression check.** List + delete against the real
      account. GraphQL DEACTIVATE has been exercised via bootstrap but
      not from the `manage` verb itself.
- [ ] **Populate `HARD_BLOCKERS`** in `scripts/listing_limits.py`.
      Currently an empty frozenset. Fill in the `category_id`s for
      Motoryzacja sprzedaż, Nieruchomości sprzedaż, Praca, Usługi,
      Wypożyczalnia, Psy/Koty rasowe as they surface from live
      responses or the posting-form autocomplete XHRs.
- [ ] **`olx promote` endpoint mapping.** `apply_promotion` still
      raises `NotImplementedError`. Needs a live promotion purchase
      capture run via Chrome MCP; record XHRs to
      `references/xhr-recordings/promotions.json`.

## Lessons from live helmet run 2026-04-19

Real first `olx new` took **~1h** instead of ~5 min. Root cause: the
browser transport was designed around `browser_cookie3`, which returns
the **stale** `access_token` from Chrome's on-disk cookie jar while the
live OLX SPA is silently refreshing the token via auth0's SDK into
`localStorage`. Every downstream step fell over once the 401 surfaced.

Fix the skill so this flow Just Works next time:

- [ ] **Replace `browser_cookie3` with AppleScript JS extraction** as
      the primary auth source. Write a new `scripts/auth_applescript.py`
      that reads the fresh `access_token` from
      `localStorage['@@auth0spajs@@::6j7elk01p32o648o1io8lvhhab::default::openid profile email offline_access'].body.access_token`
      and the `apollo-tk` cookie via `document.cookie`. The skill
      setup check should instruct the user to enable
      *View → Developer → Allow JavaScript from Apple Events* in Chrome
      once, and probe it (catch the "JavaScript through AppleScript is
      turned off" error, render the exact menu path, wait for retry).
      Keep `auth_browser.py` as a fallback for when AppleScript is off,
      but prefer AppleScript when the cookie-derived session 401s.
- [ ] **Treat `browser_cookie3` as a liveness check, not a session
      source.** When `is_session_valid` returns False but the cookie is
      present, it almost certainly means the cookie is stale — fall
      through to the AppleScript path instead of asking the user to
      "re-login". Bonus: detect "Expired token" in the 401 body and
      jump straight to the fresh-token path.
- [ ] **`olx_api.OLX` builder needs a factory.** Today callers must
      hand-wire `BrowserTransport(session=..., apollo_token=...)` +
      `OfficialTransport()` + mode. Add `OLX.from_config()` that:
      1. reads config, 2. resolves tokens (AppleScript → cookie →
      prompt), 3. builds the right transports, 4. returns a ready
      facade. The live run wasted ~10 min re-discovering constructor
      signatures and capability wiring.
- [ ] **`from scripts.config import paths` — this doesn't exist.** The
      SKILL.md "Create flow" step 1 tells the agent to write exactly
      that, but `config.py` exports `SCRATCH_DIR` (etc.) as module
      constants, not a `paths` object. Either add a `paths` facade to
      `config.py` or fix SKILL.md. The mismatch burned time on an
      ImportError in the first 5 minutes.
- [ ] **`pyproject.toml` package discovery was broken.** Running
      `pip install -e .` failed with "Multiple top-level packages
      discovered in a flat-layout: ['cache', 'references']" because
      setuptools auto-discovery picked up sibling dirs that aren't
      Python packages. Added `[tool.setuptools.packages.find]
      include = ["scripts*"]` in this run — verify it stays there and
      add a `tests/test_packaging.py` that does an editable install in
      a throwaway venv to catch regressions.
- [x] **Record an "auth refresh" recipe in
      `references/olx-reverse-engineering.md`.** Done 2026-04-19: full
      Cognito stack documented (pool eu-west-1_dUjFuvTf4, hosted UI
      pl-idp.login.olx.com, client_id 6j7elk01p32o648o1io8lvhhab,
      access_token cookie = Cognito id_token). See the "Full stack"
      section in that file.
- [ ] **Teach the skill to survive the Chrome MCP JWT block.** The MCP
      JS tool replaces JWT-shaped return values with `"[BLOCKED: JWT
      token]"`, so any "read a token via MCP" path is dead. SKILL.md
      should explicitly say: for token reads, use AppleScript (not
      MCP), and make the fallback chain honest about it.
- [ ] **Photo upload via browser form is a dead end.** I tried, in
      order: `mcp__Claude_in_Chrome__file_upload` (returns "Not
      allowed" regardless of path, even for `/tmp/…`); direct
      `DataTransfer` + native `change` event injection (React doesn't
      pick up the synthetic change); `fetch('http://127.0.0.1:…')`
      from the OLX page to serve photos locally (blocked by Chrome
      Private Network Access even with
      `Access-Control-Allow-Private-Network: true`; Chrome 98+
      requires a preflight handshake that fails silently as a
      timeout); calling the React fiber's `onChange` prop with a mock
      synthetic event (ran without error but didn't mutate component
      state). Document in SKILL.md that the **only** working publish
      path is: extract tokens → upload photos from Python directly to
      `ireland.apollo.olxcdn.com/v1/temp-files` → POST create to
      `posting-services.prd.01.eu-west-1.eu.olx.org/api/v2/offers`.
      Don't even attempt the form-fill path in `olx new`.
- [ ] **`scripts.listing_create.fetch_listing` needs a test with a
      real rclone remote.** It worked, but I had to re-derive the
      signature (`fetch_listing(slug, scratch_dir) → (paths,
      notes_text)`) from reading source. Add a docstring example and
      a one-line mention in SKILL.md step 1.
- [ ] **Cleanup helper for scratch dirs.** `olx new` leaves the
      downloaded-and-normalised photos in `$OLX_SKILL_HOME/scratch/
      <slug>-<ts>/`. Add a `paths.cleanup_scratch(age_days=7)` called
      at the end of each run.
- [ ] **Kill the bootstrap `cache/` directory.** `cache/config.json`
      still exists alongside `$OLX_SKILL_HOME/config.json`; the
      migration docstring says it'll be removed, but it's still
      there, confusing the "where does config live" question.
- [ ] **Local-HTTP-server photo workaround was a rabbit hole.** I
      spent real time building a CORS+PNA-compliant server to serve
      photos to the browser; Chrome killed it anyway. Add a negative
      hint to SKILL.md: "If you find yourself writing a local HTTP
      server, stop — the browser can't fetch from it."
- [ ] **Rename Drive folder post-publish.** Remote is read-only, so
      `olx new` currently just prints a suggested rename. For this run
      the user needs to manually move
      `Aukcje/OLX/Kask-rozowy/` → `Aukcje/OLX/_posted/Kask-rozowy-<adid>/`.
      Consider promoting the rename to use a Drive API write token
      instead of a read-only rclone remote, gated on explicit opt-in.
- [ ] **Post-publish moderation status.** `create_advert` returns
      success + a live URL but the ad actually goes into `WAITING`
      moderation. During moderation the public URL renders as
      "Ogłoszenie nieaktualne" with no photos, which looks broken to
      the user. Fix: after `create_advert`, poll the `Ads` GraphQL
      query (no status filter, find by `id`) to report the real
      status (WAITING / ACTIVE / MODERATED / DISABLED). Render a
      success message like "Opublikowane — status: WAITING
      (moderacja OLX, zwykle 15 min – 2h)." Don't hand the user a
      naked URL implying it's live.
- [ ] **`MyAdsAdStatus` enum values.** Confirmed via 400 responses:
      `ACTIVE`, `MODERATED`, `UNPAID`, `WAITING`, `FINISHED` exist;
      `LIMITED` / `OUTDATED` / `ALL` do not. Update
      `scripts/transports/browser.py` filters and drop any code that
      references the non-existent ones.
- [ ] **Drop the `createdTime`/`validToTime` fields from `_ADS_QUERY`.**
      The GraphQL server rejects them with a suggestion of
      `createdAt` — so the real field names are `createdAt` /
      `validToAt` (probably). Next live run: probe each one, confirm
      the shape, and wire them into `Advert`.

## Session 2026-04-19 — auth deep-dive findings

- [x] **Cognito PKCE auth** (`scripts/auth_cognito.py`). Endpoints confirmed
      live. `run_pkce_flow()` + `CognitoTokenStore` implemented. One-time
      browser login → browser-free refresh_token flow forever after.
- [x] **HTTP request recorder** (`scripts/http_recorder.py`). `OLX_RECORD=1`
      env var wraps `BrowserTransport` session transparently. Writes to
      `references/xhr-recordings/<label>_<ts>.json` with token redaction.
- [ ] **Capture `apollo-tk` mint endpoint.** Session confirmed: apollo-tk is
      NOT in Chrome cookies unless the user recently used the photo upload UI.
      Simple page GETs don't trigger it. To find the endpoint: run
      `OLX_RECORD=1` during a real `olx new` with photos — the recorder will
      capture the mint call automatically. Until then,
      `BrowserTransport.upload_photo` will raise if apollo-tk is absent.
      Workaround: open `https://www.olx.pl/d/nowe-ogloszenie/` in Chrome,
      click the photo upload area (don't upload anything), then re-run.

## Live run 2026-09-27 (Easywalker Jackey XL stroller)

- [ ] **Headless competitor search (403).** `BrowserTransport.search_competitors`
      (`GET /oferty/q-…/` via `requests`) now gets `403` from OLX
      anti-bot; plain `curl` with a browser UA too. Session token in
      the facade was also long expired (exp 2026-04). Goal: make it
      work headless again (candidates: `/api/v1/offers/?query=` with
      proper headers/cookies, curl_cffi TLS impersonation, headless
      Playwright). Interim: browser-pane fallback documented in
      SKILL.md step 3. Add a regression test once fixed.
- [ ] **PKCE login is dead (WAF 403).** `run_pkce_flow()` authorize URL
      (`pl-idp.login.olx.com/oauth2/authorize`, localhost redirect)
      returns 403 even in a real Chrome — WAF, not redirect_mismatch.
      No `~/.olx-skill/cognito_tokens.json` was ever saved, so there is
      no refresh token. Chrome's on-disk `access_token` cookie is ~160
      days stale. Need another bootstrap: read fresh token (and refresh
      token if present) from the live olx.pl tab (AppleScript JS /
      extension), or headless Cognito via `cognito_idp.py` with
      WAF-accepted headers.
- [ ] **Posting-form facts (stroller run, via Claude in Chrome).** Web
      form caps photos at **8** (5 MB each) → drafting step must pick 8
      and say so. Form now AI-prefills description/params from title +
      main photo (buzzwordy) — always overwrite the textarea. Location
      again defaulted to "Katowice, Kostuchna". Przesyłka OLX is on by
      default; XL bucket (Poczta Polska 60×60×70, DPD) auto-checks when
      the XL accordion is expanded. Ad landed in "Oczekujące" (moderation).
- [ ] **Partner API work paused mid-way** (2026-09-27): `auth_oauth.py`
      rewritten to swagger v2 (token URL `https://www.olx.pl/api/open/oauth/token`,
      JSON body, scope `v2 read write`, bounce-page flow) + tests green;
      `OfficialTransport` CRUD not started. Partner API takes images as
      **public URLs only** (no upload endpoint) — needs a photo host
      decision. App "nusch OLX Lister" awaiting OLX approval; callback
      the registered public callback URL ← `docs/oauth-callback/index.html`.
- [ ] **`source_listings` ignores non-image files.** Receipt
      (`PARAGON_*.PDF`) in the listing folder wasn't surfaced or
      fetched. Surface PDFs as "documents" (purchase date/price are
      useful for the description) but never upload them to OLX.

## Wiring that doesn't need a live run

- [ ] **Hard-blocker guard in `olx new`.** `listing_limits.is_hard_blocker()`
      exists but isn't called from the drafting step. Warn the user
      before `create_advert()` if the resolved `category_id` is a
      hard blocker (free publish will be refused).
- [ ] **Pre-publish bucket pre-check.** In `olx new`, after category
      is chosen, call `olx status` silently and warn if publishing
      would push the relevant bucket past its cap
      (`scripts.listing_limits.summarise` with a synthetic "+1" ad).
- [ ] **Push to a private GitHub repo.** Currently local-only
      (no `origin`). When ready, `gh repo create ... --private
      --source=. --remote=origin --push`.

## Deferred (v2+)

- [ ] **Mode A (OAuth2) advert CRUD.** Blocked on OLX developer-app
      approval. `scripts/transports/official.py` `create_advert` /
      `list_my_adverts` / `delete_advert` / `upload_photo` all raise
      `NotImplementedError: deferred`.
- [ ] Background pre-drafting daemon.
- [ ] claude.ai drafter integration (nice-to-have).
- [ ] Auto-renew cron.
- [ ] Multi-account support.
- [ ] Cross-posting (OLX + other marketplaces).
