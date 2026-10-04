# CLAUDE.md — project-level rules for this repo

This file is read automatically at session start. Rules here take precedence over defaults. Follow them.

## Public repo hygiene

This repo is public under the `nuschpl` handle. History contains only
`nuschpl <nuschpl@users.noreply.github.com>` commits and no personal data;
keep it that way.

- Commit as `nuschpl` (set per clone: `git config user.name nuschpl`,
  `git config user.email nuschpl@users.noreply.github.com`).
- **Before every push**, check the outgoing commits (`git log -p
  origin/<branch>..<branch>` — content, authors and messages) for
  personal data. Don't keep a list of the values anywhere; read them
  fresh from where they already live and grep for each:
  | Category | Source of the concrete value |
  |---|---|
  | real name, personal email | `git config --global user.name` / `user.email` |
  | own domain (OAuth callback) | `redirect_uri` in `$OLX_SKILL_HOME/app_credentials.json` |
  | home path | `$HOME` |
  | Google Drive folder id | `root_folder_id` of the rclone remotes in `inbox_rclone` |
  | home location, OLX city/district | `default_location` in `$OLX_SKILL_HOME/config.json` |
  | real OLX ad ids | Partner API `GET /adverts`, `listing.md` files on Drive |

  Also: `tests/fixtures/search_kask.html` must not grow past ~100 lines
  (scraped third-party seller data), and nothing under
  `references/xhr-recordings/` except redacted fixtures (cookies, tokens).
- Never `git push --all` / `--mirror`; push named branches only.
- If personal data does land in pushed history, the fix is a history
  rewrite + force-push (GitHub may keep cached views of the old commits).

## What lives where (user-specific state, never committed)

User state lives entirely **outside** this repo, under `$OLX_SKILL_HOME` (default `~/.olx-skill/`). Nothing here should be read-from or written-to by the skill at runtime:

- `$OLX_SKILL_HOME/config.json` — user's real `default_location` (city/district/landmark). Do not copy into the committed code.
- `$OLX_SKILL_HOME/tokens.json`, `session.json`, `app_credentials.json` — OAuth and browser-session secrets.
- `$OLX_SKILL_HOME/venv/` — Python dependencies for the skill. Re-created on first activation if missing.
- `$OLX_SKILL_HOME/scratch/`, `mcp_bridge/` — transient per-listing workspaces and agent ↔ Python bridge files.
- `references/xhr-recordings/*.har`, `*.json` (gitignored except `.gitkeep`, inside the repo) — captured live traffic, may contain cookies. Historical capture artifacts, not runtime state.

The legacy `$SKILL_ROOT/cache/` directory is migrated from on first run (`scripts.config.load_config` copies `cache/config.json` to `$OLX_SKILL_HOME/config.json` if the latter is missing) but is otherwise deprecated — new code must not read from or write to it.

## See also

- `README.md` — install instructions (marketplace + dev clone)
- `SKILL.md` — skill entry point (use-mode vs dev-mode routing at top)
- `docs/CONTEXT.md` — running-state checkpoint for picking up work
- `docs/decisions.md` — decision log
