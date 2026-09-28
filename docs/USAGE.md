# Using the OLX skill

Runs in **Claude Code** — the terminal CLI or the *Code* tab of Claude
Desktop. It needs this Mac's tools: a Python venv in `$OLX_SKILL_HOME`,
an rclone remote for Google Drive, and a browser logged into OLX. It is
not meant for Cowork or plain chat.

Invoke it with `/OLX <verb>` (or just say "wystaw na OLX …"). The skill
is global: it works from a session started in any folder. The folder
only decides where session history is stored and which project
hooks/CLAUDE.md apply — so pick **one fixed folder for OLX sessions**
and always start there. Maintainers: use this repo's folder, so fixes
made mid-listing land in git directly.

## Scenario A — photos from the phone (Drive first, default)

1. On the phone, take photos and upload them to Drive under
   `Aukcje/OLX/<slug>/` (one folder per item). Optionally add
   `notes.txt` (or a Google Doc) with facts the photos don't show:
   model/SKU, size, purchase date, flaws, your own experience with the
   item. Receipts may sit there too — they are read for facts, never
   uploaded to OLX.
2. On the Mac: Claude Desktop → *Code* → new session in your OLX folder.
3. `/OLX olx new <slug>` (or `/OLX olx new` to pick from a list).
4. The skill: downloads the folder → describes the photos → prices it
   against competitors (price ladder) → proposes title, price, category,
   location, description, photos → you approve/edit **each field**.
5. Publish (browser transport today; Partner API when implemented).
   The ad goes to OLX moderation ("Oczekujące").
6. The skill writes `listing.md` (the as-published record) into the
   Drive folder and, with your OK, moves the folder to
   `_posted/<slug>-<adid>/`.

## Scenario B — photos in a local folder (planned)

1. Start a session in your OLX folder: `/OLX olx new ~/path/to/photos`.
2. The skill proposes a `<slug>`, uploads the originals (and any notes)
   to `Aukcje/OLX/<slug>/` via the write remote, so Drive stays the
   single source of truth.
3. From there it is Scenario A step 4 onwards.

Status: not implemented as a helper yet (see TODO). Until then the
agent may upload with `rclone copy` to the write remote and then run
Scenario A.

## Scenario C — the skill misbehaves mid-listing

Say so ("to jest błąd skilla"). The agent switches to dev mode for that
problem: reproduce → regression test → fix in this repo → commit →
resume the listing. Listing data (photos, descriptions, ad ids, your
location) never goes into git; it lives in `$OLX_SKILL_HOME` and Drive.

## Scenario D — test exactly as other users will (marketplace install)

Your everyday setup (symlink `~/.claude/skills/OLX` → this repo) is not
what others get. They install the plugin from the marketplace. To test
that path without disturbing your setup, use an **isolated Claude Code
profile** in a terminal:

```bash
export CLAUDE_CONFIG_DIR=~/.claude-olx-test   # separate settings, plugins, skills, history
export OLX_SKILL_HOME=~/.olx-skill-test       # separate skill state (config, tokens, venv)
claude                                        # log in once for this profile
```

Inside that session:

```
/plugin marketplace add nuschpl/AI-skills
/plugin install olx@AI-skills
/OLX olx status
```

The test profile has no symlinked skill, so only the plugin copy is
loaded — exactly the user experience (first-run setup, missing config,
docs). Notes:

- Release candidate before publishing: point the test profile at a
  local clone of the marketplace repo (`/plugin marketplace add
  <path-to-local-AI-skills-clone>`) whose submodule is checked out at
  the commit you want to test; after changing it run `/plugin
  marketplace update` and reinstall. Check `/plugin` help for the
  exact syntax of your Claude Code version.
- The Desktop app's Code tab uses the default profile; run the test
  profile from the terminal.
- Don't enable the plugin in your everyday profile while the symlink
  exists: you'd get two copies (`/OLX` and `/olx:OLX`) that drift.
- Publishing for others = push this repo (after the PII check in
  CLAUDE.md) → bump the submodule in the marketplace repo → push it.
