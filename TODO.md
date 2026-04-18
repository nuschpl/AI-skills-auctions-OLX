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
