# Maintaining the OLX skill

How the pieces fit together for the maintainer. For end-user flows see
[USAGE.md](USAGE.md); for the running checkpoint see
[CONTEXT.md](CONTEXT.md).

## Where things live

```
<dev-root>/OLX/                  this repo (git) — code, docs, tests
~/.claude/skills/OLX  ─symlink─▶ <dev-root>/OLX      how Claude Code loads it (global /OLX)
<dev-root>/AI-skills/            clone of the public marketplace repo
  plugins/olx/skills/OLX         git submodule pinned to a commit of this repo
$OLX_SKILL_HOME (~/.olx-skill)   user state, never in git:
  config.json                      mode, default_location, inbox_rclone
  app_credentials.json, tokens.json   Partner API app + OAuth tokens (0600)
  venv/  scratch/  mcp_bridge/  bootstrap_photos/
Google Drive  Aukcje/OLX/<slug>/ source of truth per listing
  photos, notes.txt, receipts      input (receipts never uploaded to OLX)
  listing.md                       as-published record, written after publish
  _posted/<slug>-<adid>/           archive after publish
```

- **One source of truth for code: this repo.** The marketplace plugin
  is only a distribution channel. In the maintainer's everyday Claude
  Code profile the plugin stays **disabled** (`claude plugin disable
  olx@AI-skills`), otherwise two copies load and the plugin one lags.
- **One source of truth for listings: Drive.** Local scratch dirs are
  disposable; transcripts are not a record.
- **rclone remotes:** `inbox_rclone.remote` — read-only (`drive.readonly`),
  used for all reads; `inbox_rclone.write_remote` — `scope=drive`, same
  `root_folder_id`, used only for `listing.md` (`copyto
  --ignore-existing`) and, with explicit OK, moves into `_posted/`.
  See [rclone-setup.md](rclone-setup.md).

## Sessions

The skill is global, so a session may start in any folder. The folder
decides where Claude Code stores session history and which project
hooks/CLAUDE.md apply. Use **one fixed folder** for OLX sessions; this
repo is the natural choice because fixes made mid-listing then land in
git directly. Avoid starting in a parent folder whose hooks use relative
paths — the skill `cd`s into `$SKILL_ROOT`, and a relative hook path
then stops resolving and blocks every tool call.

## Transports

Two first-class paths, developed in parallel until their differences are
mapped (see [decisions.md](decisions.md)):

| | browser | official (Partner API v2) |
|---|---|---|
| Auth | logged-in OLX session (Cognito tokens from the browser) | OAuth2, one-time consent → refresh token (rotated, 30 days) |
| Base | www.olx.pl GraphQL/REST (reverse-engineered) | `https://www.olx.pl/api/partner`, header `Version: 2.0` |
| Photos | upload to OLX CDN | public URLs in the payload (host = open decision, TODO) |
| Status | publish works | `get_user` only; CRUD to do |

`scripts/capabilities.py` lists `official` only for ops that
`OfficialTransport` implements — `auto` mode prefers official as soon
as tokens exist, so a stub listed there would break the browser path.
Add `official` to an op in the same commit that implements it.

## Fixing the skill mid-listing

Live failures are skill bugs, not retry candidates (SKILL.md "Agent
discipline"): reproduce → regression test → fix → `pytest` → commit →
resume the listing. Listing data never enters git.

## Git hygiene (public repo)

- Author: `nuschpl <nuschpl@users.noreply.github.com>`, set per clone
  (`git config user.name/user.email`). Commits made before that was set
  may carry a real name — rewrite them before pushing.
- Before any push run the PII checklist in [../CLAUDE.md](../CLAUDE.md):
  real ad ids, own domain, home paths, Drive folder ids, location. Keep
  such values in an untracked local note, not in tracked files.
- Never push the local-only history snapshot branches (CLAUDE.md).

## Release to users

1. Push the skill commit to this repo (after the PII check).
2. In the marketplace clone: bump the submodule to that commit, commit,
   push (see the marketplace README).
3. Verify as an end user in an isolated profile:
   ```bash
   export CLAUDE_CONFIG_DIR=~/.claude-olx-test OLX_SKILL_HOME=~/.olx-skill-test
   claude
   /plugin marketplace add nuschpl/AI-skills
   /plugin install olx@AI-skills
   /OLX olx status
   ```
   For a release candidate, add a local marketplace clone path instead
   of `nuschpl/AI-skills`. Desktop's Code tab uses the default profile —
   run the test profile from a terminal.
