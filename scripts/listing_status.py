"""`olx status` — show how many active listings the user has versus limits.

Runnable as a script:

    .venv/bin/python -m scripts.listing_status

Builds the OLX facade the same way `listing_create.build_olx` does,
fetches the active adverts with category metadata, then groups them
against :mod:`scripts.listing_limits`. Prints a plain text table + a
pointer to ``references/olx-listing-limits.md`` for the full rules.

Design notes:

- This is a **read-only** verb. Nothing writes to OLX.
- If the transport's detailed query fails (OLX schema mismatch), the
  fallback returns adverts without category_id and every row lands in
  "Uncategorised". The user still gets a useful active-count view.
- The buckets table is deliberately sparse (see
  :mod:`scripts.listing_limits`). Most adverts will show up as
  Uncategorised until we've captured enough category_ids from live
  responses. That's by design — silent misclassification is worse
  than honest "unknown".
"""
from __future__ import annotations

import sys

from scripts.listing_limits import BUCKETS, summarise
from scripts.listing_create import build_olx


def render(rows, unknowns, *, total_active: int) -> str:
    lines: list[str] = []
    lines.append(f"Aktywne ogłoszenia: {total_active}")
    lines.append("")

    if rows:
        lines.append("Per-bucket usage (against OLX V41 limits):")
        lines.append("")
        header = f"  {'bucket':<52} {'used':>5} {'limit':>6} {'left':>5}  window"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))
        for r in rows:
            warn = ""
            if r.over_limit:
                warn = "  OVER LIMIT"
            elif r.remaining == 0:
                warn = "  FULL"
            elif r.remaining == 1:
                warn = "  (1 slot left)"
            win = f"{r.bucket.window_days}d"
            label = r.bucket.label
            if len(label) > 52:
                label = label[:49] + "..."
            lines.append(
                f"  {label:<52} {r.used:>5} {r.bucket.limit:>6} {r.remaining:>5}  {win}{warn}"
            )
        lines.append("")

    if unknowns:
        lines.append(f"Uncategorised: {len(unknowns)}")
        lines.append(
            "  (category_id unknown or not yet in the bucket table — see"
        )
        lines.append(
            "   references/olx-listing-limits.md and cross-check manually)"
        )
        for ad in unknowns:
            title = ad.title if len(ad.title) <= 70 else ad.title[:67] + "..."
            cat = ad.category_path or "?"
            lines.append(f"    [{ad.id}] {title}   (cat: {cat})")
        lines.append("")

    lines.append(
        "Pełna tabela limitów: references/olx-listing-limits.md"
    )
    lines.append(
        "Limit window: rolling (N dni od ostatniego publish w kategorii),"
    )
    lines.append(
        "nie miesiąc kalendarzowy. Private listings only."
    )
    return "\n".join(lines)


def main() -> int:
    olx = build_olx()
    ads = olx.list_my_adverts_detailed()
    rows, unknowns = summarise(ads)
    print(render(rows, unknowns, total_active=len(ads)))

    # Non-zero exit if any bucket is at or over its limit — lets us
    # chain `olx status && olx new` in scripts later.
    if any(r.remaining == 0 for r in rows):
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
