# Context for future Claude sessions

Read this first when picking up work on the OLX skill. Keeps assumptions and constraints in one place so the next session doesn't re-derive them.

## Where things are

- Skill source: this repo (`$SKILL_ROOT`).
- Symlinked activation point: `~/.claude/skills/OLX/` → this directory (or installed as a plugin; see `README.md`).
- Public on GitHub at `nuschpl/AI-skills-auctions-OLX`.

## Design & decisions — read before proposing changes

1. `docs/superpowers/specs/2026-04-18-olx-skill-design.md` — the spec, including the two-mode transport decision and what v1 explicitly defers.
2. `docs/superpowers/plans/2026-04-18-olx-skill-v1.md` — the task-by-task plan that produced v1.
3. `docs/decisions.md` — running log of every decision with rationale and what each rules out.
4. `references/olx-reverse-engineering.md` — **read before touching `scripts/transports/browser.py` or `auth_browser.py`**. Full notes on the OLX REST + GraphQL + Apollo surfaces, two-token auth model, form-fill quirks, and gotchas learned from the live bootstrap capture. Raw fixtures: `references/xhr-recordings/bootstrap.json`.
5. `references/olx-listing-limits.md` — per-category free-listing limits (Załącznik nr 3, V41). Consult in the drafting step so the user sees the limit next to the proposed category, and so the skill refuses to attempt free-publish into paid-only categories (motoryzacja/nieruchomości sprzedaż, praca, usługi, rasowe psy/koty, etc.).

If something about the architecture looks off, it's probably a deliberate tradeoff documented there.

## State of v1

35 unit tests pass. What's implemented:

- Config, capability matrix/router, pure photo utilities, inbox scanner, price stats, OAuth2 auth layer (URL build + code exchange + refresh), browser-mode auth (Chrome cookie extract + session validate), transport base + browser skeleton (get_user / list / delete), OLX facade, competitor search, bootstrap harness (Python side), SKILL.md entry point, manage + promote glue, Mode A stub.

What's **deliberately blocked** on a live run and should NOT be filled in from docs:

- ~~`scripts/transports/browser.py::create_advert` and `upload_photo` — NotImplementedError.~~ **Resolved 2026-04-18.** Filled in from a live `olx bootstrap` capture (posted → verified → deactivated dummy bike-light listing, ad id 999999999). The endpoints, auth model, and gotchas are documented in `references/olx-reverse-engineering.md`; raw request/response fixtures in `references/xhr-recordings/bootstrap.json`. The "don't guess from docs" rule still applies to anything *else* that's labeled NotImplementedError.

What's **deferred to a later plan**:

- Mode A (OAuth2) advert CRUD endpoints — blocked on OLX developer-app approval.
- Background pre-drafting daemon (v2).
- claude.ai drafter integration (v2 nice-to-have).
- Auto-renew cron, multi-account, cross-posting.

## Non-negotiables (baked into SKILL.md)

- Location default comes from `cache/config.json::default_location` (user-configured locally; gitignored). Confirmed every run, not silent.
- Bootstrap dummy listing is NEVER the user's real inventory (first run uses a realistic bike-light set the skill picks).
- No "test", "próba", "lorem", placeholders, emoji-only copy in any listing.
- GPS always stripped from photos before upload.
- Publish requires explicit per-field user approval (title/price/category/location/description/photos).

## Transport model (two first-class modes, not fallback)

- `official` — OAuth2 Partner API. Needs approved developer app. Portable (token lives in `$OLX_SKILL_HOME/tokens.json`, not Mac-bound).
- `browser` — logged-in Chrome cookies + `mcp__Claude_in_Chrome__*` for UI-only ops. Mac-bound (cookies local). Required permanently for paid promotions (API doesn't expose them).
- `auto` — prefers `official` if tokens exist, else `browser`. Default.

Shareability was a user requirement: requiring everyone to get OLX dev-app approval was rejected. Both modes must stay supported.

## Photo ingestion (Android-first, rclone-backed)

**Decided 2026-04-18:** photos live on Google Drive under `Aukcje/OLX/`
and are accessed via a dedicated **rclone remote** (`olx-gdrive`,
read-only, `root_folder_id` pinned to the `Aukcje` folder). No local
sync. Kopia's `[gdrive]` remote is untouched.

rclone remote config (user's `~/.config/rclone/rclone.conf`):

```
[olx-gdrive]
type = drive
scope = drive.readonly
root_folder_id = <YOUR_AUKCJE_FOLDER_ID>   # Aukcje
```

Persisted in `$OLX_SKILL_HOME/config.json` as
`inbox_rclone = {"remote": "olx-gdrive", "path": "OLX"}`. When this is
set it takes precedence over `inbox_path`.

### Folder-per-listing layout (user-facing)

```
Aukcje/OLX/
  kask-junior-blue/           ← one auction = one subfolder
    IMG_*.jpg
    notes.txt                 ← optional, freeform hints to the AI
  _posted/                    ← user moves folders here after publish
  _drafts/                    ← anything the user is still preparing
```

Rules:
- Subfolders prefixed with `_` are **ignored** by the skill.
- `notes.txt` is **optional**; first line = headline hint
  (brand/model/size), rest = free bullets. Not schema'd — fed as
  trusted context into the drafting step alongside vision output.
- Archive is **manual** (user renames into `_posted/<slug>-<adid>/`).
  The skill does not write to the remote (scope is read-only).

### Adapter

`scripts/inbox_rclone.py` wraps `rclone lsjson` + `rclone copy` via
subprocess. Currently lists files directly under a given path (flat
mode used for one-offs like bootstrap). **Folder-per-listing
subfolder discovery + `notes.txt` pickup is the next TODO** — see
"Resuming `olx new`" below.

## Running it

- Setup (one-time): see `README.md`.
- All verbs (`olx new`, `olx manage`, `olx promote`) work against the
  real OLX site via browser mode (tokens extracted from Chrome).
- Bootstrap has already been run (2026-04-18) — endpoints are in
  `scripts/transports/browser.py`, reverse-engineering notes are in
  `references/olx-reverse-engineering.md`. Do NOT re-bootstrap unless
  the captured endpoints stop working.

## Resuming `olx new` (checkpoint 2026-04-18 EOD)

When the user reissues `olx new`, pick up here:

1. **Read config.** `load_config()` (defaults to `$OLX_SKILL_HOME/config.json`). If
   `cfg.inbox_rclone` is set (it is), prefer the rclone source over
   `cfg.inbox_path`.
2. **List auction folders.** `rclone lsjson olx-gdrive:OLX` →
   filter `IsDir=true`, drop any `Name` starting with `_`.
3. **If user passed a slug/path**, jump to step 5 with that folder.
   Otherwise present the list and ask them to pick.
4. **Per-folder contents.** `rclone lsjson olx-gdrive:OLX/<slug>` →
   image files (by suffix) + optional `notes.txt`.
5. **Download to a scratch dir.** `$OLX_SKILL_HOME/scratch/<slug>-<ts>/`.
   Per-file `rclone copy` (one call per image, one for `notes.txt`
   if present). `notes.txt` → read into memory as `notes_text`.
6. **Continue with the normal create flow** (photos.py → vision draft
   → competitor search → user approval → publish). When drafting,
   feed `notes_text` as a separate labeled section so vision output
   and user hints stay distinguishable in the proposed draft.
7. **No archive move.** Remote is read-only; remind the user at the
   end to rename the folder into `_posted/<slug>-<adid>/` themselves
   (print the exact suggested name).

Pending code work to make the above real (not done yet):
- Extend `scripts/inbox_rclone.py` with `list_auction_folders(remote,
  path)` (subfolders, skip `_*`) and
  `list_folder_contents(remote, path, subfolder)` returning
  `(images: list[RemoteItem], notes: str | None)`.
- Wire `scripts/listing_create.py` / SKILL.md's create flow to
  prefer `inbox_rclone` when set.
- Tests for the new adapter methods (subprocess-mocked, responses-
  style — see `tests/test_transports_browser.py` pattern).

## OLX Partner API quick facts

- Developer portal: https://developer.olx.pl/
- Docs: https://developer.olxgroup.com/
- Authorize: `https://www.olx.pl/oauth/authorize`
- Token: `https://api.olxgroup.com/oauth/v1/token`
- Flow: `authorization_code` + `refresh_token` (access 1h, refresh ~30d)
- Scopes: `read:adverts write:adverts read:leads read:profile_package`
- App approval is manual and can take days.
- Paid promotions and (possibly) photo upload are not in the public docs — browser mode covers them.
