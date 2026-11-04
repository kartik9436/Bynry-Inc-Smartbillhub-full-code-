#!/usr/bin/env python3
"""ccwalk_results_md — write RESULTS.md for the charge-code walk from its results.json.

`10-scripts/charge_codes_walk33.mjs` records one row per code (results.json);
this turns them into the page the PO reads: the counts per check, what was
found and fixed, what is left for the PO, and the per-code table.

    python 10-scripts/ccwalk_results_md.py 08-qa/screens/charge-codes-walk33-2026-10-01
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COLS = [
    ("add", "Add"),
    ("dbAdd", "DB after add"),
    ("view", "List + view"),
    ("update", "Update"),
    ("dbUpdate", "DB after update"),
    ("history", "History"),
    ("oneRow", "One row to billing"),
    ("impact", "Schedule / plan / bill"),
    ("gl", "GL set on Add"),
    ("refusedSecondBase", "2nd base refused"),
]

HEAD = """# Charge codes — the clerk's walk over every code (2026-10-01)

The PO asked for every charge code to be added and updated through the screens as a clerk would,
with the database, the change history, the one price billing reads and the effect on rate schedules,
plans and bills checked each time — and for a new base code on each of the eleven services, by
customer type and asset size, with real figures.

**How it was walked.** `10-scripts/charge_codes_walk33.mjs`, Chromium at 1440, a private PostgreSQL 16
database: `seed_demo`, all eleven services switched on, `load_sample_data`. The database half is
`10-scripts/ccwalk_charge_code_db_check.py`, which asks the real `charge_prices.price_on_date` — the one
lookup every bill uses. Today on the database is **10/01/2026**; adds are dated 10/01/2026; every update
is dated **11/01/2026**, so the old price must end **10/31/2026**; the one-row lookup is asked for
**10/15/2026** and **11/15/2026**. Bill checks are one-time bill previews: a fee bill dated 10/15 and 11/15
for plan and other codes; for a base code an interim bill over October, over November and over
16 October – 15 November (cut at the price change: 16/31 of October's base plus 15/30 of November's).

**How many codes.** The PO said 33. A utility with all eleven services switched on holds **40**: 14 base
(one per service, plus class variants for electric and water), 11 plan and 15 other. All 40 were walked,
plus **14 new base codes**, one per service and Residential / Commercial for water, electric and trash.
"""

FOUND = """## What the walk found, and what was done

| Defect | What the clerk saw | Done |
|---|---|---|
| `DEF-RAT-8826` | `RE-READ` repriced $20.00 → $21.00 from 11/01/2026 still billed **$20.00** on a fee bill dated 11/15. Every plan and other code did the same. A code priced only by customer class could not be raised as a fee at all. | **Fixed** (2.436.8): a fee bill charges the price in force on its own date, for the account's class. Walked again: 23 of 25 fee bills priced the right figure on both dates; the other 2 refuse by design (below). |
| `DEF-RAT-8827` | Editing `LATE` (1.50%, minimum $5.00) to 1.75% / $6.00 *from 11/01/2026* changed every overdue customer's fee **the same day** and kept no record of the old figures. | **Fixed** (2.436.8): the change is a dated row from 11/01; $542.10 overdue pays $8.13 until 10/31 and $9.49 from 11/01. |
| `DEF-RAT-8834` | `NSF` ($30.00) and `TAMPER` ($250.00) opened on View and Edit with a **blank percent and minimum**; saving turned the $30.00 fee into a 0.25% rule that a fee bill then refused. | **Fixed** (2.436.8): a flat penalty shows and saves its amount. Walked again: NSF $30.00 → $31.00 from 11/01, still a flat fee. |
| `DEF-RAT-8836` | PO's screenshot — Edit `BASE-BAT` ($5.00 → $6.00): the Prices table read **Asset —**. | **Fixed** (2.436.11): a one-amount base on a service with sizes names its asset (*Behind-the-meter battery*) and reads *All sizes*, on step 2, Review and View details; sewer keeps "—". Photographed: `DEF-RAT-8836-BASE-BAT-*.jpg`. |
| `DEF-RAT-8825` | A typed *entered when used* amount ($1,250.00 for TAP) was dropped by the one-time bill. | Already fixed on the branch by the wave C lane (30f8dc40f) before this walk's fix landed; closed against it. Walked: TAP, IMPACT, DAMAGE, BULK-WATER bill $1,250.00 on both dates. |
| `DEF-RAT-8833` | A rate schedule that names no customer class showed only the **first base code by code** on its Rates tab: the industrial electric schedule read *From BASE-E $12.00* while its industrial account is billed BASE-E-IND $180.00. | **Fixed** (2.437.4, coordinator decision): such a schedule lists every live base code of its service, one row per class, each naming its class and code. Display only — billing unchanged. |
| `DEF-RAT-8843` | Add drew a penalty only as a percent and a minimum, so `NSF` $30.00 and `TAMPER` $250.00 could be edited but not added. | **Fixed** (2.437.4): *Priced by* offers *One amount* for a penalty. Walked: `A-NSF` $30.00 and `A-TAMPER` $250.00 added as flat fees. |
| `DEF-RAT-8844` | Add priced a base on a service with sizes only by size, so `BASE-W` $8.00 *All sizes* came back as every size at $8.00. | **Fixed** (2.437.4): *Priced by* offers *Size* or *All sizes*; *All sizes* stores ONE *All sizes* row. Per size stays the other choice. |
| `DEF-RAT-8845` | A second live base code for the same service and class saved with no warning, and every bill for that class then stopped (*"2 base charge codes for water"*). | **Fixed** (2.437.4): the save is refused, naming the live code — *"BASE-W already covers this class."* Bringing a retired base back is checked the same way. Nothing already stored was changed. |
| `DEF-RAT-8846` | After a price change from 11/01 the Rates tab read *Next change: None*; the new price showed nowhere until 11/01. | **Fixed** (2.437.4): Next change reads e.g. *$9.00 from 11/01/2026*, and each Rates row carries its own next price. |
| `DEF-RAT-8847` | A base code added through Add had **no GL account**, where the seeded ones post to the service's base revenue account. | **Fixed** (2.437.4): it starts on that account (water: 4115 Water base); the clerk can still change it. |

| `DEF-RAT-9011` | Found by this re-run's own photograph: on Industrial Electric at 1440 the Next change tile read *$181.00 from* over a date cut to *11/01/202*, and with three base codes listed it did not say whose price it was. | **Fixed** (2.437.6): the amount is the tile's value and *from 11/01/2026 · BASE-E-IND* the line beneath it (the code is named only when the tab lists more than one). Re-photographed: every `*-U4-schedule-rates.jpg`. |

## Ruled by the PO today — being built by another lane

**A bill cut at one code's price change now splits ONLY that service** (PO, 2026-10-01). In the
16 Oct – 15 Nov example only water moved ($8.00 → $9.00), so water is split and electric stays
$12.00. This walk's bill previews were taken before that build lands, so on a two-service bill they
still show the unchanged service split too (electric $6.19 + $6.00 = $12.19). Not changed here.

## By design, not faults

* **A sized storm-water or thermal base holds every account whose connection has no recorded size**
  (*"This connection's size is not recorded."*) — the ruled behaviour (`DEF-RAT-8822`); the sample
  accounts record no storm-water or thermal size, so those two new codes could not be billed here.
* **Fire priced twice when the base uses the line prices.** The sample fire schedule already charges
  $12.00 / $60.00 per line; a base at the same figures (as asked) makes a 2×2" + 1×6" property pay
  $84.00 twice. A walk-data choice, not a product fault.

* `CC-EXPEDITE` and `CC-METERTEST` are sample codes started with **no GL account** on purpose
  (`payments/counter_receipts`), so a fee bill refuses them by name. Their prices update correctly.
* A size kept on the screen and left blank is stored as a row **with no amount** — *not served* — and
  bills $0.00 with a warning (`NB-T-RES` DUMP-2).

## A red the walk did not cause

`tests/test_def_cus_6050_reconnection_figure.py::tc3` is red on the branch tip with and without this
walk's changes (`DID NOT RAISE DisconnectRuleError`, checked on both).
"""


def tick(value):
    return "✅" if value is True else "❌" if value is False else "—"


def main() -> None:
    out_dir = Path(sys.argv[1])
    rows = json.loads((out_dir / "results.json").read_text())
    order = sorted(rows.values(), key=lambda r: ({"update": 0, "add": 1, "new": 2}.get(r.get("phase"), 3), r.get("kind") or "", r["code"]))
    lines = [HEAD, "## The counts", "", "| Phase | Codes | " + " | ".join(label for _k, label in COLS) + " |", "|---|---|" + "---|" * len(COLS)]
    for phase, label in (("update", "Update every seeded code"), ("add", "Add a twin of every seeded code"), ("new", "New base code per service")):
        group = [r for r in order if r.get("phase") == phase]
        cells = []
        for key, _label in COLS:
            passed = sum(1 for r in group if r.get(key) is True)
            failed = sum(1 for r in group if r.get(key) is False)
            cells.append("—" if passed + failed == 0 else f"{passed} of {passed + failed}")
        lines.append(f"| {label} | {len(group)} | " + " | ".join(cells) + " |")
    lines += ["", FOUND, "## Every code", ""]
    lines.append("| Phase | Code | Kind | Shape | " + " | ".join(label for _k, label in COLS) + " | Notes |")
    lines.append("|---|---|---|---|" + "---|" * len(COLS) + "---|")
    for r in order:
        code = f"`{r['code']}`" + (f" (twin of `{r['twinOf']}`)" if r.get("twinOf") else "")
        notes = " · ".join(r.get("notes") or []).replace("|", "/").replace("\n", " ")
        lines.append(f"| {r.get('phase')} | {code} | {r.get('kind')} | {r.get('shape') or '—'} | " + " | ".join(tick(r.get(k)) for k, _l in COLS) + f" | {notes} |")
    lines.append("")
    (out_dir / "RESULTS.md").write_text("\n".join(lines))
    print(f"wrote {out_dir / 'RESULTS.md'} ({len(order)} rows)")


if __name__ == "__main__":
    main()
