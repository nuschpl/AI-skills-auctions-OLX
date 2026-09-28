# rclone + Google Drive setup for OLX skill

One-time setup. After this, the skill reads auction photos straight from
Google Drive via rclone — no local sync, no Google Drive for Desktop,
no iCloud. You drop photos into a folder on Drive from your phone; the
skill sees them on the Mac.

Audience: fresh Mac, or someone re-doing this setup on another machine.
Takes ~10 minutes end-to-end.

## Overview

Three layers, each set up separately:

| Layer | Where | What you do |
|---|---|---|
| 1. Drive folders | Google Drive (browser) | Create `Aukcje/OLX/` and grab the folder ID from the URL |
| 2. rclone remote | Terminal (`rclone config`) | Create a read-only remote `olx-gdrive` pinned to the `Aukcje` folder |
| 3. Skill config | Terminal (Python) | Save `inbox_rclone` to `$OLX_SKILL_HOME/config.json` (default `~/.olx-skill/config.json`) |

**If Kopia is already using rclone on this Mac:** don't worry. We create
a *new* remote block (`[olx-gdrive]`), Kopia's `[gdrive]` remote stays
untouched. They coexist in `~/.config/rclone/rclone.conf`.

---

## Step 1 — Create the Drive folders (browser)

1. Open <https://drive.google.com/> in the account where your auction
   photos will live (typically the same account your phone's Google
   Photos backs up to).
2. In **My Drive**, create a top-level folder named **`Aukcje`**.
   - "My Drive" → right-click → New folder → `Aukcje`.
3. Open `Aukcje`, and inside it create a subfolder **`OLX`**.
4. **Grab the `Aukcje` folder ID.** Click on `Aukcje` to open it, then
   look at the URL bar. It looks like:
   ```
   https://drive.google.com/drive/folders/<YOUR_AUKCJE_FOLDER_ID>
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                          this is the folder ID
   ```
   Copy that ID — you'll paste it into `rclone config` in step 2.

### Folder-per-listing convention

Inside `Aukcje/OLX/`, each item you want to sell gets its **own
subfolder**. The skill walks the subfolders; underscore-prefixed
folders (`_posted`, `_drafts`, …) are **reserved for you** and ignored.

Recommended structure:

```
Aukcje/OLX/
  kask-junior-blue/              ← one auction
    IMG_20260418_103022.jpg
    IMG_20260418_103045.jpg
    notes.txt                    ← optional, see below
  rower-kross-level/             ← another auction
    ...
  _posted/                       ← move folders here after publishing
  _drafts/                       ← stuff you're still preparing
```

**Slug guidelines:** lowercase, Polish-without-diacritics, hyphens
instead of spaces. The slug is only a label — it doesn't have to match
the eventual listing title.

### `notes.txt` (optional, per auction folder)

Plain text, freeform. First line = brand/model/size headline, rest =
free bullets. The skill reads it as trusted user-supplied hints and
merges it with what vision sees.

Example:

```
Giro Scamp Jr, rozmiar XS (49-53 cm), kolor niebieski
- Kupiony 2024 za 180 zł w Decathlonie
- Używany ~10 razy, stan bardzo dobry
- Małe zarysowanie z tyłu (widoczne na IMG_...3045)
- Cena wywoławcza: 90 zł, odbiór osobisty lub wysyłka InPost
```

Don't put anything in here you wouldn't want paraphrased into a public
listing (home address specifics, serial numbers, etc.).

### Uploading from an Android phone

1. Open Google Photos → select the photos for one auction.
2. Share → **Save to Drive** → destination: `My Drive/Aukcje/OLX/` →
   create a new folder (the slug) → Save.

Or, if you took photos specifically for OLX: use the Drive app
directly and upload them into a pre-created subfolder.

---

## Step 2 — Configure the rclone remote (console)

### 2a. Install rclone (if not already present)

```bash
brew install rclone
rclone version   # sanity check, should print v1.6+ or newer
```

If Kopia is already running on this Mac, you very likely already have
rclone — skip the brew install.

### 2b. Create the `olx-gdrive` remote

We use `rclone config` interactively. The key non-default answers:

- **name:** `olx-gdrive`
- **storage:** `drive` (Google Drive)
- **client_id / client_secret:** leave **blank** — we don't need a
  private OAuth client for the modest traffic this skill generates.
  (Kopia uses its own client for throughput; that's a separate remote.)
- **scope:** `drive.readonly` (we only ever read; the skill never
  writes to Drive — archiving is a manual folder rename in the UI).
- **root_folder_id:** paste the `Aukcje` folder ID from step 1.
- **service_account_file:** leave blank.
- **Edit advanced config:** `n`.
- **Use auto config:** `y` — opens a browser for Google OAuth consent;
  approve with the same Google account that owns the `Aukcje` folder.
- **Configure as a Shared Drive:** `n` (it's a personal Drive folder).

Full interactive run:

```bash
rclone config
# n  (New remote)
# name> olx-gdrive
# Storage> drive          (or the number for Google Drive)
# client_id>              (leave blank, press Enter)
# client_secret>          (leave blank, press Enter)
# scope> drive.readonly   (or the number for "drive.readonly")
# service_account_file>   (leave blank)
# Edit advanced config? n
# Use auto config? y      → browser opens, approve with your Google account
# Configure as a Shared Drive? n
# y  (Yes, this is OK)
# q  (Quit config)
```

Then **manually add `root_folder_id`** to pin the remote to the
`Aukcje` folder. Open `~/.config/rclone/rclone.conf` in your editor
and add the `root_folder_id` line under the `[olx-gdrive]` section:

```ini
[olx-gdrive]
type = drive
scope = drive.readonly
token = {"access_token":"...","refresh_token":"...","expiry":"..."}
root_folder_id = <YOUR_AUKCJE_FOLDER_ID>
```

(The `token` line is auto-populated by `rclone config` — leave it
alone.)

### 2c. Verify

```bash
rclone lsd olx-gdrive:           # should list "OLX" (and any other
                                 #   subfolders of Aukcje)
rclone ls  olx-gdrive:OLX        # lists files/folders under OLX
rclone lsd olx-gdrive:OLX        # lists just the auction subfolders
```

Expected shape:

```
$ rclone lsd olx-gdrive:
          -1 2026-04-18 10:22:33         0 OLX

$ rclone lsd olx-gdrive:OLX
          -1 2026-04-18 11:02:00         0 kask-junior-blue
          -1 2026-04-18 11:15:00         0 _posted
```

If you see `ERROR : : error listing: directory not found` — the
`root_folder_id` is wrong or the OAuth account doesn't have access to
that folder. Re-check both.

---

## Step 3 — Point the skill at the remote

Save `inbox_rclone` into `$OLX_SKILL_HOME/config.json`. One-liner:

```bash
cd "$SKILL_ROOT"  # e.g. ~/.claude/skills/OLX or your local clone
"$OLX_SKILL_HOME/venv/bin/python" -c "
from scripts.config import load_config, save_config
cfg = load_config()
cfg.inbox_rclone = {'remote': 'olx-gdrive', 'path': 'OLX'}
save_config(cfg)
"
```

Expected output includes:

```json
  "inbox_rclone": {
    "remote": "olx-gdrive",
    "path": "OLX"
  },
```

That's it. Next `olx new` will walk `olx-gdrive:OLX`, list the
subfolders (skipping `_*`), and ask you to pick one.

---

## Security & isolation notes

- **Read-only scope.** Even if the skill has a bug, it cannot modify
  or delete anything in your Drive. `scope = drive.readonly` is
  enforced at Google's OAuth layer, not just in our code.
- **Folder-pinned.** `root_folder_id` constrains rclone to the
  `Aukcje` subtree. The skill cannot see or touch anything else in
  your Drive — not other folders, not your documents, nothing.
- **Token storage.** rclone stores the OAuth refresh token in
  `~/.config/rclone/rclone.conf` (plain JSON). Treat that file as a
  secret: it grants read-only Drive access to anyone who reads it.
  macOS file permissions (`0600`) are the default protection.
- **Revocation.** If you ever want to cut the skill off: either
  delete the `[olx-gdrive]` block from `rclone.conf`, or revoke the
  "rclone" app at <https://myaccount.google.com/permissions>.

## Troubleshooting

**`directory not found` on `rclone lsd olx-gdrive:`** — wrong
`root_folder_id`, or the OAuth'd account doesn't own/have access to
`Aukcje`. Check both.

**`oauthutil: failed to get token: ... invalid_grant`** — the token
expired or was revoked. Run `rclone config reconnect olx-gdrive:` to
re-authenticate.

**"Can't see my new auction folder"** — Drive sometimes caches listings.
Try `rclone lsd olx-gdrive:OLX --drive-pacer-min-sleep=100ms` or wait
30 seconds. Also: make sure the folder isn't named with a leading
underscore (those are skipped by design).

**Want to verify nothing's cached/stale:** `rclone about olx-gdrive:`
hits the API live and shows quota.

## Why not Google Drive for Desktop?

Considered and rejected. Downsides:

- Pulls the entire Drive or a configured root onto the Mac; awkward to
  scope tightly to one folder.
- Sync timing is opaque — "is that file downloaded yet?" is a real
  question during a listing run.
- Bloats the filesystem with mirrored photos we only need once.
- On-demand-only mode (files stream on open) is flaky enough to be a
  footgun during an interactive `olx new`.

rclone lets us (a) scope to one folder via `root_folder_id`, (b) see
exactly when a file is fetched, (c) keep zero mirror on disk — only
the photos for the auction currently being drafted land in
`$OLX_SKILL_HOME/scratch/`.

## Why a separate remote from Kopia?

Kopia's `[gdrive]` remote is configured for backup throughput: its
own `client_id`/`client_secret` (you registered those with Google for
higher rate limits), full `drive` scope, not pinned to any folder.
Reusing it would mean (a) giving the OLX skill full Drive access
unnecessarily, and (b) coupling two unrelated tools to one OAuth grant.
Separate remote = separate trust domain = safer and easier to reason
about.

## Optional: a write-capable remote for listing records

The skill writes `listing.md` (the as-published record) into each
listing folder. That needs write access, which the read-only remote
above deliberately lacks. Add a second remote pinned to the same folder
and name it in config:

```bash
rclone config create olx-gdrive-rw drive scope=drive root_folder_id=<YOUR_AUKCJE_FOLDER_ID>
# browser opens once for Google consent
```

```json
"inbox_rclone": {"remote": "olx-gdrive", "path": "OLX", "write_remote": "olx-gdrive-rw"}
```

`root_folder_id` is a convenience, not a security boundary: a `drive`
scope token can reach the whole Drive. Reads stay on the read-only
remote; the skill uses the write remote only for `copyto
--ignore-existing` of `listing.md` and, with explicit per-run OK, moves
into `_posted/`.
