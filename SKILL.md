---
name: OLX
description: Create, manage, and promote OLX.pl listings. Supports both the OAuth2 Partner API and a logged-in Chrome session. Use when the user says "sell on OLX", "wystaw na OLX", "olx new", "olx manage", "olx promote", or hands over photos of an item to list.
---

# OLX Quick-Listing Skill

**Skill root resolution**: `$SKILL_ROOT` = the absolute directory containing this `SKILL.md` file. You (Claude) know that path from the skill-loading context — export it at session start and use it everywhere below:

```bash
export SKILL_ROOT="<absolute path of the directory containing this SKILL.md>"
cd "$SKILL_ROOT"
```

Typical values:
- Local checkout/symlink: `~/src/Claude/skills/OLX/` or similar
- Installed as plugin: `~/.claude/plugins/cache/<marketplace>/<sha>/plugins/olx/skills/OLX/`

All commands below assume `$SKILL_ROOT` is set and is the working directory.

## Use mode vs. dev mode — read first

This repo is both an installed skill and its own development project. Pick the right mode before acting:

- **Use mode** (default). User wants to list, manage, or promote an item. Proceed with the flows below.
- **Dev mode**. User says things like "popraw skill", "zmień skill OLX", "dodaj do skilla", "olx dev", "refactor OLX", "napisz test dla…", or reports a bug in the skill itself. **Do NOT create a listing.** Instead: read `TODO.md`, then `docs/CONTEXT.md` and `docs/decisions.md`, and treat the task as code changes to this repo (tests live in `tests/`, run with `.venv/bin/pytest`).

If the request is ambiguous (e.g. "OLX nie działa"), ask one clarifying question before choosing a mode.

## Setup check (run first on every activation)

```bash
cd "$SKILL_ROOT"
[ -x .venv/bin/python ] || python3.13 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

Load config:
```bash
.venv/bin/python -c "from scripts.config import load_config; from pathlib import Path; import json; print(json.dumps(load_config(Path('cache/config.json')).__dict__, default=str, ensure_ascii=False, indent=2))"
```

**Photo source resolution** (in priority order):

1. If `inbox_rclone` is set (current setup: `{"remote": "olx-gdrive",
   "path": "OLX"}`), use the rclone adapter — see "Create flow" below.
   User keeps photos on Google Drive under `Aukcje/OLX/<slug>/`; skill
   reads via `rclone lsjson`/`copy` through the read-only `olx-gdrive`
   remote. **This is the default.** See `docs/CONTEXT.md` → "Resuming
   `olx new`" for the exact steps.
2. Else if `inbox_path` is set, use the local-sync scanner.
3. Else ask the user how they want to supply photos. If they want the
   Drive/rclone path but haven't configured it yet, point them at
   [`docs/rclone-setup.md`](docs/rclone-setup.md) — it walks through
   the browser steps (create `Aukcje/OLX/` folders, grab folder ID),
   the console steps (`rclone config` creating `olx-gdrive` with
   `scope=drive.readonly` and `root_folder_id`), and how to save
   `inbox_rclone` into `cache/config.json`. Don't try to walk them
   through it verbally — hand them the doc.

## Setup docs (point user here if anything's missing)

- [`docs/rclone-setup.md`](docs/rclone-setup.md) — one-time Drive +
  rclone setup for photo ingestion (browser + console steps).
- [`docs/CONTEXT.md`](docs/CONTEXT.md) — running-state checkpoint;
  read on session start to pick up where the previous session left off.
- [`references/olx-reverse-engineering.md`](references/olx-reverse-engineering.md)
  — OLX REST/GraphQL/Apollo endpoints, auth model, Chrome form-fill
  quirks. Consult before touching `scripts/transports/browser.py`.
- [`references/olx-listing-limits.md`](references/olx-listing-limits.md)
  — per-category limits (free listings per 30 days), paid-only
  categories, shared buckets. Consult during the drafting step so
  the user sees the applicable limit next to the proposed category.

## Verb routing

- `olx new [paths…]` → create flow below
- `olx manage` → list + delete
- `olx status` → active listings vs. per-category limits (read-only)
- `olx promote <ad_id>` → promotion packages (always via Chrome MCP)
- `olx bootstrap` → dummy-listing verification run
- `olx oauth` → run the OAuth2 authorize + exchange flow

## Create flow (`olx new`)

1. **Resolve photo set.**
   - If paths passed, use them.
   - Else if `config.inbox_rclone` is set (the default):
     - `from scripts.listing_create import source_listings, fetch_listing`
     - `source_listings()` → `list[RemoteListing]` (newest-first;
       subfolders starting with `_` are skipped; native Google Docs are
       auto-exported as Markdown via `--drive-export-formats md`, so
       they land as `notes.md`).
     - Show the slugs + photo counts; user picks one (or passes it as
       `olx new <slug>`).
     - `photos, notes_text = fetch_listing(slug, Path("cache/scratch/<slug>-<ts>"))`
       — one `rclone copy` materializes the whole folder. `notes_text`
       is the contents of `notes.md` (or `notes.txt`) when present
       (trusted hint; headings/bullets in Markdown preserved), else
       `None`.
   - Else if `config.inbox_path` is set: `from scripts.inbox import
     scan_inbox`; scan it, show EXIF-time bursts, let user pick.

2. **Describe photos.** Use your own vision capability (in-conversation).
   Extract per photo: object type, brand, model/size markers, colour,
   condition, visible defects. Merge into one structured draft. If a
   `notes.txt` was present in the source folder, treat it as trusted
   user-supplied hints: use it to fill brand/model/size gaps the vision
   missed, and surface it back in the proposed draft as a separate
   labeled "From your notes" section so the user can see which facts
   came from vision vs. from them.

3. **Competitor search.** Build 2–3 query variants. Call
   `OLX.search_competitors(q)` for each. Merge, dedupe by URL, filter
   aggressively to items that actually match brand + model (a loose
   query will pull in generic "kask" or "rower" hits — drop them).
   Compute stats via `scripts.price_stats.compute_stats`.

   Then present a **price-ladder table of sample auctions** so the
   user can manually judge where their price should sit, not just
   eyeball one number. Use
   `scripts.competitor_samples.pick_samples(results, stats)` —
   it returns one closest-match auction per key anchor
   (**min / p25 / mediana / p75 / max**, all excluding IQR outliers),
   deduped. `render(samples)` gives a paste-ready table:

   ```
   min       25 zł  |  Kask rowerowy dziecięcy Abus Smiley 3.0
                       https://www.olx.pl/d/oferta/...CID767-ID1a4bZA.html
   p25       45 zł  |  Kask Abus smiley
                       https://www.olx.pl/d/oferta/...CID767-ID1aeITs.html
   mediana   60 zł  |  Kask ABUS Smiley 2.0 - 50-55 cm różowy
                       https://www.olx.pl/d/oferta/...
   ...
   ```

   Include this table in the draft proposal alongside the single-line
   `median / p25–p75` band — the band gives the number, the table
   gives the positioning.

3a. **Surface listing limit.** Look up the proposed category in
    [`references/olx-listing-limits.md`](references/olx-listing-limits.md)
    and include the applicable limit in the draft (e.g. "limit 4 na
    30 dni, łączony z Części rowerowe i Odzież i obuwie rowerowe").
    If the category is in the paid-only list (Motoryzacja sprzedaż,
    Nieruchomości sprzedaż, Praca, Usługi, Wypożyczalnia, Psy/Koty
    rasowe etc.), warn the user up front: free publish will be
    refused by OLX; they'd need a paid post.

4. **Propose draft.** Render:
```
Tytuł: …
Cena: … zł (median konkurencji: …, p25–p75: …)
Kategoria: …
Lokalizacja: <config.default_location>  ← re-confirm every run
Opis:
…
Zdjęcia (N): …
```
Ask the user to approve/edit each of {title, price, category, location,
description, photos}. Accept free-form edits.

5. **Normalise photos.** `scripts.photos.strip_gps`, then `normalise_photo`.

6. **Publish.** `OLX.create_advert(payload)`. If browser transport raises
   `NotImplementedError`, fall back to Chrome MCP (see Bootstrap flow
   below). Record each captured XHR.

7. **Archive.**
   - If `inbox_path` source: move processed photos to
     `inbox_path/archive/<YYYY-MM-DD-HHMM>/`.
   - If `inbox_rclone` source: the remote is **read-only**. Print a
     suggested rename instead, e.g. "rename `Aukcje/OLX/<slug>/` →
     `Aukcje/OLX/_posted/<slug>-<adid>/` in Drive when you have a
     minute." Do not attempt to move it via rclone.

8. **Return URL.** Print the live ad URL to the user.

## Status (`olx status`)

Read-only: shows active listings bucketed against the V41 per-category
limits. Run it before `olx new` when the user has been posting a lot,
so they know a publish won't bounce off a full bucket.

```bash
.venv/bin/python -m scripts.listing_status
```

What it does:

1. Builds the OLX facade (same path as `olx new`).
2. Calls `OLX.list_my_adverts_detailed()` — extended GraphQL `Ads`
   query with category metadata. If OLX rejects the category field,
   falls back to the plain list and everything shows as
   "Uncategorised" (still useful: total active count).
3. Groups ads by known bucket (`scripts.listing_limits.BUCKETS`)
   and prints `used / limit / left` per bucket, plus any
   uncategorised rows for manual review against
   [`references/olx-listing-limits.md`](references/olx-listing-limits.md).

Exit code `2` when any bucket is full — so `olx status && olx new`
can short-circuit.

**Growing the bucket table:** when status shows an unknown
`category_id` on a listing the user cares about, look the category up
in the cheat-sheet and add the ID to `scripts/listing_limits.BUCKETS`
(or `_SINGLETONS`). Prefer "unknown bucket" over guessed mappings —
silent misclassification is worse than a visible gap.

## Agent discipline (avoid these common mistakes)

Lessons baked in from earlier live runs. Re-read before starting any
`olx new` session.

1. **Don't bypass the skill's own helpers.** If you need to list/download
   from the rclone remote, call `scripts.listing_create.source_listings()`
   and `fetch_listing()` — not raw `rclone` in a bash loop. If a helper is
   missing for what you need, add it; don't work around it in an ad-hoc
   shell command.
2. **Investigate value-adding features, but require certainty before
   claiming them.** Features like FidLock magnetic buckles, MIPS safety
   liners, In-Mold construction, brushless motors etc. genuinely move
   buyers — a listing that mentions them when they're real reads
   sharper than one that omits them. So you **should** actively ask
   "does this unit have X?" for every feature that matters to this
   product category; a listing that ignores real selling points is a
   weaker listing. But the answer has to be *known*, not inferred from
   a plausible-looking photo. Three acceptable paths to certainty, in
   order of preference:
   1. **Visible proof in the photos** — a logo, embossed marking,
      sticker, or model number you can quote verbatim. Brand names
      and size stickers belong here too: quote them when present,
      mark them "nie widać na zdjęciach" when absent.
   2. **Deep web research on the exact SKU/model** — e.g. look up
      "ABUS Smiley 3.0 AKU-03 features" against the manufacturer site
      or a reputable retailer, and confirm whether the feature is
      present on *this* variant (not just "available in the product
      line"). Note the source in your reasoning so the user can audit.
   3. **Ask the user** — if the unit could ship with or without the
      feature (variant-dependent) and research doesn't settle it, ask
      directly: "Czy ten egzemplarz ma FidLock / MIPS / …?".
   Do **not** commit a feature to the draft on the basis of "the brand
   *sells* a variant with it" or "the buckle *looks like* it could
   be". Canonical trap: **FidLock**. ABUS ships Smiley 3.0 with both a
   standard side-release buckle and a FidLock variant; visually they
   can be mistaken. Only claim FidLock when one of the three paths
   above confirms it — otherwise drop it from the draft or describe
   neutrally ("standardowa klamra zatrzaskowa"). Same discipline for
   MIPS, In-Mold vs. hardshell, brushless-vs-brushed, "komplet pudełko
   + instrukcja", etc.
3. **Mine the SKU before declaring "unknown".** Product codes in
   `notes.md` (e.g. "AKU-03", "ABUS SKU 87231") often encode size or
   variant. Look them up (or ask the user to confirm) before writing
   "size not visible in photos" in the draft.
4. **Re-read current docs at session start.** CONTEXT.md and the
   references/ directory evolve between sessions. What you remember
   from a prior run ("notes.txt is optional") may have been superseded
   ("notes.md via --drive-export-formats md, preserves Markdown
   structure"). Trust the files, not your memory.
5. **When replicating a captured HTTP request, prune it.** The OLX
   bootstrap capture mirrors what Chrome sends — that's more than what
   the server requires. GraphQL operations that declare variables they
   don't reference are rejected with
   `"Variable $... is never used"` (HTTP 400). Only send variables the
   query body actually uses; only send headers the server cares about.
6. **Live failures are skill bugs, not retry candidates.** If a verb
   raises unexpectedly (400, 401, schema mismatch), fix the skill
   code + add a regression test before re-running the user's ad
   through it. Don't loop on a broken path hoping the next attempt
   will work.
7. **GPS + credibility rules in the next section are non-negotiable**
   — no "test"/"próba" placeholders, no emoji-only copy, price inside
   competitor p25–p75 unless the user overrides, location re-confirmed
   every run.

## Description style — find the practical advantages

The user's voice: **concrete, practical, no buzzwords.** The description
should answer two questions in plain Polish, in this order:

1. **Why would anyone want this *kind* of product at all?** Not
   marketing-speak — the genuine practical reasons people choose this
   model/category over a no-name alternative. Think like the buyer's
   spouse asking "czy warto?". For a kids' bike helmet: low weight on a
   child's neck, an insect-net in the vents so bees don't sting mid-
   ride, a fit dial that grows a size or two with the child, In-Mold
   construction = lighter and better impact absorption than cheap ABS
   shells. For a power drill: brushless motor = longer runtime on a
   battery; specific chuck size; weight vs. torque tradeoff. For a
   board game: playtime per session, player count sweet spot, what
   makes it replayable.
2. **Why this specific unit?** Condition, completeness (box? manual?
   accessories?), what's visible in the photos, any honest flaws,
   pickup.

Write 3–6 natural sentences total across both questions. Keep it
readable, not a bullet list. Cite **specific features** the product
actually has (check the model page if unsure) — don't invent generic
selling points. If a feature is a common myth for the brand but not
on this specific model, skip it; the user will spot it and correct
you.

Hard lines:

- No marketing buzzwords ("premium", "rewelacyjny", "polecam",
  "okazja", "stan idealny" when it's not).
- No emoji-only or emoji-heavy copy.
- No superlatives unless true and checkable ("najlżejszy w klasie"
  — only if you can back it up).
- Every practical-advantage claim should be about a feature the model
  actually has. When in doubt, leave it out rather than embellish.

Include, always: size/dimensions, condition (in plain Polish —
"bardzo dobry", "lekkie ślady użytkowania", not marketing grades),
and the pickup line (from `config.default_location` in `cache/config.json` unless user says otherwise).

## Credibility rules (apply to every publish)

- No "test", "próba", "lorem", placeholder, or emoji-only copy.
- Price within competitor p25–p75 unless user overrides — **with one
  caveat:** if the exact model+size you're listing clearly trades
  higher than the category median (e.g. current generation vs.
  predecessor both in the same search), show the user both numbers
  and propose a price anchored on the exact-match subset, not the
  broad median. The competitor sample ladder (step 3) is the tool
  for spotting this.
- Description follows the "Description style" section above.
- Real photos.
- Strip GPS before upload.

## Bootstrap (`olx bootstrap`)

Drives `scripts/bootstrap_dryrun.py`. Posts a dummy bike-light set defined
in `DUMMY_LISTING` — **never the user's real helmet**, verifies live,
captures every XHR, then deletes within ~10 minutes.

Python writes MCP request files to `cache/mcp_bridge/<ts>.bootstrap_create.request.json`.
You (the agent) must:

1. Read the request file.
2. Drive Chrome MCP:
   - `mcp__Claude_in_Chrome__navigate` to `https://www.olx.pl/d/nowe-ogloszenie/`
   - `mcp__Claude_in_Chrome__form_input` for title/description/price/category
   - Throughout, call `mcp__Claude_in_Chrome__read_network_requests` to
     capture every `olx.pl/api/` XHR (URL, method, headers, body, response status)
   - `mcp__Claude_in_Chrome__find` + click "Opublikuj", capture the redirect URL
3. Write result to `<ts>.bootstrap_create.result.json` with shape:
```json
{"ad_id": "…", "ad_url": "https://www.olx.pl/d/oferta/…", "captured_xhr": [...]}
```
4. Wait for the `bootstrap_delete` request, then drive the delete UI.
   Write result: `{"deleted": true, "captured_xhr": [...]}`.

After the run, use the captured XHRs to fill in
`BrowserTransport.create_advert` and `upload_photo`.

## Promote (`olx promote <ad_id>`)

Mode B only in v1. Drive Chrome MCP to the promotion panel for *ad_id*,
list available packages, ask user which to buy, confirm charge, execute.
Record XHRs to `references/xhr-recordings/promotions.json`. Update
`references/promotions.md` with any new packages observed.

## Troubleshooting

- **Cookies not found** (`browser-cookie3` error): user must be logged
  into OLX in Chrome on this Mac. Open `https://www.olx.pl/konto/` via
  `mcp__Claude_in_Chrome__navigate` and ask user to log in.
- **Session invalid** (401 from `/api/v1/user/me/`): same as above.
- **Rate limited** (429): back off 60s, switch to Chrome MCP path.
