# CLAUDE.md — project-level rules for this repo

This file is read automatically at session start. Rules here take precedence over defaults. Follow them.

## History hygiene — DO NOT re-import the old commit tree

On 2026-04-18 the public history was rewritten into a single orphan commit (`002b2d9 Initial public release` authored by `nuschpl <nuschpl@users.noreply.github.com>`). The old history is preserved **locally only** for cherry-picking individual safe changes forward:

```
main                    ← clean orphan, matches GitHub
pre-public-cleanup      ← snapshot of pre-scrub history (contains PII, never push)
old-main-with-history   ← intermediate scrub point (contains PII, never push)
```

### DON'Ts — these operations would undo the history rewrite or leak PII

- **DO NOT** `git merge pre-public-cleanup` or `git merge old-main-with-history` into `main`. A merge pulls in the whole old history as ancestors of `main`, which reintroduces the old PII-laden commits (old authors, old file states, old commit messages) on top of the clean orphan — exactly what the rewrite removed. Merging makes GitHub visible history balloon back to the pre-rewrite state on the next push.
- **DO NOT** `git rebase pre-public-cleanup main` or the inverse. Rebase replays commits; every replay reintroduces the old content into the working tree at each intermediate step, and the rewritten commits keep the old author metadata.
- **DO NOT** `git push origin pre-public-cleanup` or `old-main-with-history`. These branches are local-only snapshots. Pushing them exposes the PII the force-push was meant to remove.
- **DO NOT** `git push --mirror` or `git push --all`. These push all local refs, including the preservation branches.
- **DO NOT** `git pull` without checking: if the remote ever force-pushes back, a naive pull can create a merge commit re-attaching old history.
- **DO NOT** restore files blindly with `git checkout pre-public-cleanup -- .` (note the dot). That dumps the entire old tree into `main`'s working directory. Check out only the specific files you reviewed (see workflow below).

### Cherry-pick workflow — port old work forward safely

When you need something from the pre-rewrite history, cherry-pick **one commit or one file at a time** with review:

```bash
cd "$SKILL_ROOT"

# 1. See what's in the old history that's not on main:
git log --oneline pre-public-cleanup ^main

# 2. Inspect a candidate commit:
git show <sha>

# 3. Pull it in — pick one variant:

# Variant A — whole commit, clean diff:
git checkout main
git cherry-pick <sha>
# Then: grep the resulting diff for PII patterns before pushing:
#   (patterns: see $OLX_SKILL_HOME/PRIVATE-NOTES.md, local only)
#   plus scraped third-party data (search_kask.html-style fixtures).
git diff HEAD~1 | less

# Variant B — only specific files, when the commit mixes safe + unsafe:
git checkout pre-public-cleanup -- path/to/safe/file
# Sanitise in place with Edit tool, then:
git add path/to/safe/file
git commit -m 'Bring <feature> forward from old history'

# 4. When everything useful has been ported, drop the backups:
git branch -D pre-public-cleanup old-main-with-history
```

### What counts as "PII" in this repo

Before pushing any commit derived from the old history, grep for categories of things (kept generic here on purpose — the specific strings are in your local, uncommitted scrub-patterns note):

- Author's real first/last name or personal email (previously present in commit metadata and spec headers)
- Author's personal Google Drive folder id (28+ char base64-ish string in a Drive URL)
- Specific OLX listing id from the bootstrap dry-run (a 10-digit integer)
- OLX numeric city/district codes matching author's neighbourhood
- "City, District" strings naming author's neighbourhood
- Absolute home path fragments under `/Users/` (code should use `$SKILL_ROOT`-relative references)
- `tests/fixtures/search_kask.html` ballooning past ~100 lines — the old scraped version carried third-party seller names/ids
- Anything under `references/xhr-recordings/` that is not a redacted fixture (real cookies, session tokens)

These categories are scrubbed on `main` as of `002b2d9`. Re-introducing any of them via cherry-pick is a regression.

### What lives where (user-specific state, never committed)

- `cache/config.json` (gitignored) — user's real `default_location` (city/district/landmark). Do not copy into the committed code.
- `cache/app_credentials.json`, `cache/tokens.json`, `cache/session.json` (gitignored) — OAuth and browser-session secrets.
- `references/xhr-recordings/*.har`, `*.json` (gitignored except `.gitkeep`) — captured live traffic, may contain cookies.

## See also

- `README.md` — install instructions (marketplace + dev clone)
- `SKILL.md` — skill entry point (use-mode vs dev-mode routing at top)
- `docs/CONTEXT.md` — running-state checkpoint for picking up work
- `docs/decisions.md` — decision log
