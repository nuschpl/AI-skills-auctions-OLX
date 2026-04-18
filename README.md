# AI-skills-auctions-OLX

Wystawianie aukcji na OLX na podstawie folderu Google Drive ze zdjęciami i dokumentem tekstowym Notes który zawiera model wystawianego przedmiotu.

Claude Code skill for OLX.pl listing/management. Supports both the official
OAuth2 Partner API and a logged-in-browser session.

## Install

### Option A — via plugin marketplace (recommended for end users)

```
/plugin marketplace add nuschpl/AI-skills
/plugin install olx@AI-skills
```

### Option B — local clone (for developers / contributors)

```bash
git clone git@github.com:nuschpl/AI-skills-auctions-OLX.git
cd AI-skills-auctions-OLX
ln -s $PWD ~/.claude/skills/OLX   # makes the skill discoverable user-wide
```

The skill's setup check (first step of `SKILL.md`) creates the venv and installs dependencies under `$OLX_SKILL_HOME` (default `~/.olx-skill/venv`) the first time it runs — no manual setup needed. Tests run against that venv:

```bash
"$OLX_SKILL_HOME/venv/bin/pytest" -v        # or $HOME/.olx-skill/venv/bin/pytest
```

## First run

1. Ensure you are logged into OLX in Chrome (any account; Google SSO fine).
2. **Set up photo ingestion via rclone + Google Drive.** Follow
   [`docs/rclone-setup.md`](docs/rclone-setup.md) — creates an
   `Aukcje/OLX/` folder in your Drive and a read-only `olx-gdrive`
   rclone remote scoped to that folder. ~10 minutes, one-time.
3. Optionally register an app at https://developer.olx.pl/ and save
   credentials to `$OLX_SKILL_HOME/app_credentials.json` (default
   `~/.olx-skill/app_credentials.json`):
   ```json
   {"client_id": "...", "client_secret": "...", "redirect_uri": "..."}
   ```
4. In Claude Code: `olx bootstrap` to run the end-to-end smoke test (dummy
   listing + verify + delete). Already done once — only re-run if the
   captured endpoints stop working.

## Modes

- `official` — OAuth2 Partner API (needs approved developer app)
- `browser` — logged-in Chrome cookies + MCP for UI-only ops
- `auto` — prefers `official` if tokens exist, else `browser` (default)

Set with `scripts/config.py` or by editing `$OLX_SKILL_HOME/config.json`.

## Tests

```bash
"$OLX_SKILL_HOME/venv/bin/pytest" -v
```

## Docs

- **rclone + Drive setup (run this first):** [`docs/rclone-setup.md`](docs/rclone-setup.md)
- Context for picking up work: [`docs/CONTEXT.md`](docs/CONTEXT.md)
- OLX API/scraping reverse-engineering: [`references/olx-reverse-engineering.md`](references/olx-reverse-engineering.md)
- OLX per-category listing limits: [`references/olx-listing-limits.md`](references/olx-listing-limits.md)
- Design spec: `docs/superpowers/specs/2026-04-18-olx-skill-design.md`
- Decisions log: `docs/decisions.md`
- Implementation plan: `docs/superpowers/plans/2026-04-18-olx-skill-v1.md`
- Capability matrix: `references/capability-matrix.md`
