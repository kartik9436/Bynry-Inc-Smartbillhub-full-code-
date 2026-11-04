# Charge codes — the clerk's walk over every code (2026-10-01)

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

## The counts

| Phase | Codes | Add | DB after add | List + view | Update | DB after update | History | One row to billing | Schedule / plan / bill | GL set on Add | 2nd base refused |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Update every seeded code | 40 | — | — | — | 40 of 40 | 40 of 40 | 40 of 40 | 40 of 40 | 38 of 40 | — | — |
| Add a twin of every seeded code | 40 | 40 of 40 | 40 of 40 | 40 of 40 | — | — | — | 40 of 40 | — | 14 of 14 | 14 of 14 |
| New base code per service | 14 | 14 of 14 | 14 of 14 | 14 of 14 | 14 of 14 | 14 of 14 | 14 of 14 | 14 of 14 | 12 of 14 | 14 of 14 | — |

## What the walk found, and what was done

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

## Every code

| Phase | Code | Kind | Shape | Add | DB after add | List + view | Update | DB after update | History | One row to billing | Schedule / plan / bill | GL set on Add | 2nd base refused | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| update | `BASE-BAT` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 6.00 · Next change tile: $6.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00005: Oct 5.00×1=5.00 · Nov 6.00×1=6.00 · 16 Oct–15 Nov 2.58×1=2.58 + 3.00×1=3.00 (total 5.58) |
| update | `BASE-BB` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 31.00 · Next change tile: $31.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00009: Oct 30.00×1=30.00 · Nov 31.00×1=31.00 · 16 Oct–15 Nov 15.48×1=15.48 + 15.50×1=15.50 (total 30.98) |
| update | `BASE-E` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 13.00 · Next change tile: $13.00 · rate schedules reading it as base: 4; plans reached: 5 · bill preview AC-2026-00001: Oct 12.00×1=12.00 · Nov 13.00×1=13.00 · 16 Oct–15 Nov 6.19×1=6.19 + 6.50×1=6.50 (total 12.69) |
| update | `BASE-E-COM` | base | sized | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 6 → 7; changed E-1P-100  → 49.00 · Next change tile: $13.00 · rate schedules reading it as base: 4; plans reached: 5 · bill preview AC-2026-00047: Oct 120.00×1=120.00 · Nov 120.00×1=120.00 · 16 Oct–15 Nov 61.94×1=61.94 + 60.00×1=60.00 (total 121.94) |
| update | `BASE-E-IND` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 181.00 · Next change tile: $13.00 · rate schedules reading it as base: 4; plans reached: 5 · bill preview AC-2026-00050: Oct 180.00×1=180.00 · Nov 181.00×1=181.00 · 16 Oct–15 Nov 92.90×1=92.90 + 90.50×1=90.50 (total 183.40) |
| update | `BASE-FIRE` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 1.00 · Next change tile: $1.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00025: Oct in the per-size line 0.00/0.00 each = 0.00 · Nov in the per-size line 1.00/1.00 each = 3.00 · 16 Oct–15 Nov 0.00×1=0.00 + 1.50×1=1.50 (total 1.50) |
| update | `BASE-G` | base | sized | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 4 → 5; changed G-1000  → 16.00 · Next change tile: $16.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 6.00×1=6.00 · Nov 6.00×1=6.00 · 16 Oct–15 Nov 3.10×1=3.10 + 3.00×1=3.00 (total 6.10) |
| update | `BASE-S` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 10.00 · Next change tile: $10.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 9.00×1=9.00 · Nov 10.00×1=10.00 · 16 Oct–15 Nov 4.65×1=4.65 + 5.00×1=5.00 (total 9.65) |
| update | `BASE-SOL` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 1.00 · Next change tile: $1.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00005: Oct 0.00×1=0.00 · Nov 1.00×1=1.00 · 16 Oct–15 Nov 0.00×1=0.00 + 0.50×1=0.50 (total 0.50) |
| update | `BASE-SW` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 3.00 · Next change tile: $3.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 2.00×1=2.00 · Nov 3.00×1=3.00 · 16 Oct–15 Nov 1.03×1=1.03 + 1.50×1=1.50 (total 2.53) |
| update | `BASE-T` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 1.00 · Next change tile: $1.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00002: Oct in the per-size line 0.00 each = 0.00 · Nov in the per-size line 1.00 each = 3.00 · 16 Oct–15 Nov 0.00×1=0.00 + 1.50×1=1.50 (total 1.50) |
| update | `BASE-TH` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 21.00 · Next change tile: $21.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 20.00×1=20.00 · Nov 21.00×1=21.00 · 16 Oct–15 Nov 10.32×1=10.32 + 10.50×1=10.50 (total 20.82) |
| update | `BASE-W` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 9.00 · Next change tile: $9.00 · rate schedules reading it as base: 5; plans reached: 5 · bill preview AC-2026-00001: Oct 8.00×1=8.00 · Nov 9.00×1=9.00 · 16 Oct–15 Nov 4.13×1=4.13 + 4.50×1=4.50 (total 8.63) |
| update | `BASE-W-COM` | base | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 16.00 · Next change tile: $9.00 · rate schedules reading it as base: 5; plans reached: 5 · bill preview AC-2026-00047: Oct 15.00×1=15.00 · Nov 16.00×1=16.00 · 16 Oct–15 Nov 7.74×1=7.74 + 8.00×1=8.00 (total 15.74) |
| update | `AFTER-HRS` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 76.00 · fee preview 2026-10-15 → 75.00, 2026-11-15 → 76.00 |
| update | `BULK-WATER` | other | entered | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 0 → 0; changed no price · fee preview 2026-10-15 → 1250.00, 2026-11-15 → 1250.00 |
| update | `CC-EXPEDITE` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ❌ | — | — | rows 1 → 2; changed All sizes  → 46.00 · fee preview 2026-10-15 → —, 2026-11-15 → — · fee preview: before: refused — charge code 'CC-EXPEDITE' has no GL account, so a fee raised on it could never be issued (BR-BIL-010: *charge codes carry their own GL*). Refused HERE rather than at issue, so the message names the sc; after: refused — charge code 'CC-EXPEDITE' has no GL account, so a fee raised on it could never be issued (BR-BIL-010: *charge codes carry their own GL*). Refused HERE rather than at issue, so the message names the sc |
| update | `CC-METERTEST` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ❌ | — | — | rows 1 → 2; changed All sizes  → 61.00 · fee preview 2026-10-15 → —, 2026-11-15 → — · fee preview: before: refused — charge code 'CC-METERTEST' has no GL account, so a fee raised on it could never be issued (BR-BIL-010: *charge codes carry their own GL*). Refused HERE rather than at issue, so the message names the s; after: refused — charge code 'CC-METERTEST' has no GL account, so a fee raised on it could never be issued (BR-BIL-010: *charge codes carry their own GL*). Refused HERE rather than at issue, so the message names the s |
| update | `CC-REQFEE` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 26.00 · fee preview 2026-10-15 → 25.00, 2026-11-15 → 26.00 |
| update | `DAMAGE` | other | entered | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 0 → 0; changed no price · fee preview 2026-10-15 → 1250.00, 2026-11-15 → 1250.00 |
| update | `IMPACT` | other | entered | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 0 → 0; changed no price · fee preview 2026-10-15 → 1250.00, 2026-11-15 → 1250.00 |
| update | `INSPECT` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 31.00 · fee preview 2026-10-15 → 30.00, 2026-11-15 → 31.00 |
| update | `METER-TEST` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 26.00 · fee preview 2026-10-15 → 25.00, 2026-11-15 → 26.00 |
| update | `RE-READ` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 21.00 · fee preview 2026-10-15 → 20.00, 2026-11-15 → 21.00 |
| update | `RETURN-TRIP` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 31.00 · fee preview 2026-10-15 → 30.00, 2026-11-15 → 31.00 |
| update | `SAME-DAY` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 51.00 · fee preview 2026-10-15 → 50.00, 2026-11-15 → 51.00 |
| update | `SEASONAL` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 26.00 · fee preview 2026-10-15 → 25.00, 2026-11-15 → 26.00 |
| update | `TAP` | other | entered | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 0 → 0; changed no price · fee preview 2026-10-15 → 1250.00, 2026-11-15 → 1250.00 |
| update | `TEMP-SVC` | other | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 41.00 · fee preview 2026-10-15 → 40.00, 2026-11-15 → 41.00 |
| update | `CC-CONV` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 3.95 · fee preview 2026-10-15 → 2.95, 2026-11-15 → 3.95 |
| update | `CONN` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 46.00 · plan Residential Standard shows 45.00 · fee preview 2026-10-15 → 45.00, 2026-11-15 → 46.00 |
| update | `DISC` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 46.00 · plan Small Commercial shows 45.00 · fee preview 2026-10-15 → 45.00, 2026-11-15 → 46.00 |
| update | `HYDRANT` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 51.00 · fee preview 2026-10-15 → 50.00, 2026-11-15 → 51.00 |
| update | `LATE` | plan | penalty | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 0 → 1; changed All sizes  → 1.75%/6.00 · plan Industrial shows 1.50%/5.00 · plan Residential Standard shows 1.50%/5.00 · plan Small Commercial shows 1.50%/5.00 |
| update | `MOVE-OUT` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 21.00 · fee preview 2026-10-15 → 20.00, 2026-11-15 → 21.00 |
| update | `NSF` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 31.00 · plan Industrial shows 30.00 · plan Residential Standard shows 30.00 · plan Small Commercial shows 30.00 · fee preview 2026-10-15 → 30.00, 2026-11-15 → 31.00 |
| update | `PAPER` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 3.00 · fee preview 2026-10-15 → 2.00, 2026-11-15 → 3.00 |
| update | `RECON` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 76.00 · fee preview 2026-10-15 → 75.00, 2026-11-15 → 76.00 |
| update | `TAMPER` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 251.00 · plan Industrial shows 250.00 · fee preview 2026-10-15 → 250.00, 2026-11-15 → 251.00 |
| update | `TRANSFER` | plan | flat | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | rows 1 → 2; changed All sizes  → 16.00 · fee preview 2026-10-15 → 15.00, 2026-11-15 → 16.00 |
| add | `A-BASE-BAT` (twin of `BASE-BAT`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-BAT, Add refuses: "BASE-BAT already covers this class." · stored All sizes 5.00 · GL 4165 — the seeded BASE-BAT posts to 4165 · twin retired and BASE-BAT brought back |
| add | `A-BASE-BB` (twin of `BASE-BB`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-BB, Add refuses: "BASE-BB already covers this class." · stored All sizes 30.00 · GL 4145 — the seeded BASE-BB posts to 4145 · twin retired and BASE-BB brought back |
| add | `A-BASE-E` (twin of `BASE-E`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-E, Add refuses: "BASE-E already covers this class." · stored All sizes 12.00 · GL 4105 — the seeded BASE-E posts to 4105 · twin retired and BASE-E brought back |
| add | `A-BASE-E-COM` (twin of `BASE-E-COM`) | base | size | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-E-COM, Add refuses: "BASE-E-COM already covers this class." · stored E-1P-100 48.00, E-1P-200 72.00, E-1P-400 120.00, E-3P-200 96.00, E-3P-400 168.00, E-CT 456.00 · GL 4105 — the seeded BASE-E-COM posts to 4105 · twin retired and BASE-E-COM brought back |
| add | `A-BASE-E-IND` (twin of `BASE-E-IND`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-E-IND, Add refuses: "BASE-E-IND already covers this class." · stored All sizes 180.00 · GL 4105 — the seeded BASE-E-IND posts to 4105 · twin retired and BASE-E-IND brought back |
| add | `A-BASE-FIRE` (twin of `BASE-FIRE`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-FIRE, Add refuses: "BASE-FIRE already covers this class." · stored All sizes 0.00 · GL 4155 — the seeded BASE-FIRE posts to 4155 · twin retired and BASE-FIRE brought back |
| add | `A-BASE-G` (twin of `BASE-G`) | base | size | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-G, Add refuses: "BASE-G already covers this class." · stored G-1000 15.00, G-250 6.00, G-425 8.10, G-630 10.56 · GL 4140 — the seeded BASE-G posts to 4140 · twin retired and BASE-G brought back |
| add | `A-BASE-S` (twin of `BASE-S`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-S, Add refuses: "BASE-S already covers this class." · stored All sizes 9.00 · GL 4120 — the seeded BASE-S posts to 4120 · twin retired and BASE-S brought back |
| add | `A-BASE-SOL` (twin of `BASE-SOL`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-SOL, Add refuses: "BASE-SOL already covers this class." · stored All sizes 0.00 · GL 4150 — the seeded BASE-SOL posts to 4150 · twin retired and BASE-SOL brought back |
| add | `A-BASE-SW` (twin of `BASE-SW`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-SW, Add refuses: "BASE-SW already covers this class." · stored All sizes 2.00 · GL 4160 — the seeded BASE-SW posts to 4160 · twin retired and BASE-SW brought back |
| add | `A-BASE-T` (twin of `BASE-T`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-T, Add refuses: "BASE-T already covers this class." · stored All sizes 0.00 · GL 4130 — the seeded BASE-T posts to 4130 · twin retired and BASE-T brought back |
| add | `A-BASE-TH` (twin of `BASE-TH`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-TH, Add refuses: "BASE-TH already covers this class." · stored All sizes 20.00 · GL 4170 — the seeded BASE-TH posts to 4170 · twin retired and BASE-TH brought back |
| add | `A-BASE-W` (twin of `BASE-W`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-W, Add refuses: "BASE-W already covers this class." · stored All sizes 8.00 · GL 4115 — the seeded BASE-W posts to 4115 · twin retired and BASE-W brought back |
| add | `A-BASE-W-COM` (twin of `BASE-W-COM`) | base | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | ✅ | ✅ | beside the live BASE-W-COM, Add refuses: "BASE-W-COM already covers this class." · stored All sizes 15.00 · GL 4115 — the seeded BASE-W-COM posts to 4115 · twin retired and BASE-W-COM brought back |
| add | `A-AFTER-HRS` (twin of `AFTER-HRS`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 75.00 |
| add | `A-BULK-WATER` (twin of `BULK-WATER`) | other | entered | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored no price row |
| add | `A-CC-EXPEDITE` (twin of `CC-EXPEDITE`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 45.00 |
| add | `A-CC-METERTEST` (twin of `CC-METERTEST`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 60.00 |
| add | `A-CC-REQFEE` (twin of `CC-REQFEE`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 25.00 |
| add | `A-DAMAGE` (twin of `DAMAGE`) | other | entered | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored no price row |
| add | `A-IMPACT` (twin of `IMPACT`) | other | entered | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored no price row |
| add | `A-INSPECT` (twin of `INSPECT`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 30.00 |
| add | `A-METER-TEST` (twin of `METER-TEST`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 25.00 |
| add | `A-RE-READ` (twin of `RE-READ`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 20.00 |
| add | `A-RETURN-TRIP` (twin of `RETURN-TRIP`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 30.00 |
| add | `A-SAME-DAY` (twin of `SAME-DAY`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 50.00 |
| add | `A-SEASONAL` (twin of `SEASONAL`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 25.00 |
| add | `A-TAP` (twin of `TAP`) | other | entered | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored no price row |
| add | `A-TEMP-SVC` (twin of `TEMP-SVC`) | other | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 40.00 |
| add | `A-CC-CONV` (twin of `CC-CONV`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 2.95 |
| add | `A-CONN` (twin of `CONN`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 45.00 |
| add | `A-DISC` (twin of `DISC`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 45.00 |
| add | `A-HYDRANT` (twin of `HYDRANT`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 50.00 |
| add | `A-LATE` (twin of `LATE`) | plan | penalty | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 1.50%/5.00 |
| add | `A-MOVE-OUT` (twin of `MOVE-OUT`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 20.00 |
| add | `A-NSF` (twin of `NSF`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 30.00 |
| add | `A-PAPER` (twin of `PAPER`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 2.00 |
| add | `A-RECON` (twin of `RECON`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 75.00 |
| add | `A-TAMPER` (twin of `TAMPER`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 250.00 |
| add | `A-TRANSFER` (twin of `TRANSFER`) | plan | one | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | stored All sizes 15.00 |
| new | `NB-BAT` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-BAT first · stored BAT-10 8.00, BAT-15 11.00, BAT-20 14.00, BAT-5 5.00 · GL 4165 — Battery · changed BAT-5 → 6.00 · Next change tile: $6.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00005: Oct 8.00×1=8.00 · Nov 8.00×1=8.00 · 16 Oct–15 Nov 4.13×1=4.13 + 4.00×1=4.00 (total 8.13) |
| new | `NB-BB` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-BB first · stored BB-100 30.00, BB-1000 70.00, BB-500 50.00 · GL 4145 — Broadband · changed BB-100 → 31.00 · Next change tile: $31.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00009: Oct 30.00×1=30.00 · Nov 31.00×1=31.00 · 16 Oct–15 Nov 15.48×1=15.48 + 15.50×1=15.50 (total 30.98) |
| new | `NB-E-COM` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-E-COM first · stored E-1P-200 48.00, E-1P-400 120.00, E-3P-200 96.00, E-3P-400 168.00, E-CT 456.00 · GL 4105 — Electric base · changed E-1P-200 → 49.00 · Next change tile: $181.00 · rate schedules reading it as base: 4; plans reached: 5 · bill preview AC-2026-00047: Oct 120.00×1=120.00 · Nov 120.00×1=120.00 · 16 Oct–15 Nov 61.94×1=61.94 + 60.00×1=60.00 (total 121.94) |
| new | `NB-E-RES` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-E first · stored E-1P-100 12.00, E-1P-200 14.50, E-1P-400 22.00 · GL 4105 — Electric base · changed E-1P-100 → 13.00 · Next change tile: $49.00 · rate schedules reading it as base: 4; plans reached: 5 · bill preview AC-2026-00001: Oct 12.00×1=12.00 · Nov 13.00×1=13.00 · 16 Oct–15 Nov 6.19×1=6.19 + 6.50×1=6.50 (total 12.69) |
| new | `NB-FIRE` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-FIRE first · stored FL-2 12.00, FL-4 30.00, FL-6 60.00, FL-8 100.00 · GL 4155 — Fire · changed FL-2 → 13.00 · Next change tile: $13.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00025: Oct in the per-size line 12.00/60.00 each = 84.00 · Nov in the per-size line 13.00/60.00 each = 86.00 · 16 Oct–15 Nov 43.35×1=43.35 + 43.00×1=43.00 (total 86.35) |
| new | `NB-G` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-G first · stored G-1000 15.00, G-250 6.00, G-425 8.10, G-630 10.56 · GL 4140 — Gas · changed G-1000 → 16.00 · Next change tile: $16.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 6.00×1=6.00 · Nov 6.00×1=6.00 · 16 Oct–15 Nov 3.10×1=3.10 + 3.00×1=3.00 (total 6.10) |
| new | `NB-S` | base | flat | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-S first · stored All sizes 9.00 · GL 4120 — Sewer · changed All sizes → 10.00 · Next change tile: $10.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00001: Oct 9.00×1=9.00 · Nov 10.00×1=10.00 · 16 Oct–15 Nov 4.65×1=4.65 + 5.00×1=5.00 (total 9.65) |
| new | `NB-SOL` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-SOL first · stored SOL-P10 10.00, SOL-P3 3.00, SOL-P5 5.00, SOL-P8 8.00 · GL 4150 — Solar · changed SOL-P3 → 4.00 · Next change tile: $4.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00005: Oct 8.00×1=8.00 · Nov 8.00×1=8.00 · 16 Oct–15 Nov 4.13×1=4.13 + 4.00×1=4.00 (total 8.13) |
| new | `NB-SW` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | — | retired the seeded BASE-SW first · stored SW-APT 12.00, SW-COM-L 45.00, SW-COM-S 18.00, SW-DUP 3.50, SW-SF 2.00 · GL 4160 — Storm water · changed SW-APT → 13.00 · Next change tile: $13.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview (AC-2026-00001): Oct preview refused: This connection's size is not recorded. Record the connection's size.; Nov preview refused: This connection's size is not recorded. Record the connection's size.; 16 Oct–15 Nov preview refused: This connection's size is not recorded. Record the connection's size. |
| new | `NB-T-COM` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | stored CART-96 15.00, DUMP-2 40.00, DUMP-4 65.00, DUMP-6 90.00, DUMP-8 115.00 · GL 4130 — Trash · changed CART-96 → 16.00 · Next change tile: $16.00 · rate schedules reading it as base: 1; plans reached: 3 · no commercial account on trash could be billed (2 on the service) — the first one is refused: plan 01a0f9c9-746a-703c-b22e-b8d1a988c2d9 resolves to no tariff for any service in this run's scope. A bill with no services is not a $0.00 bill — it is a confi |
| new | `NB-T-RES` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-T first · stored CART-35 9.00, CART-64 12.00, CART-96 15.00, DUMP-2 null · GL 4130 — Trash · changed CART-35 → 10.00 · Next change tile: $10.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview AC-2026-00002: Oct in the per-size line 15.00 each = 45.00 · Nov in the per-size line 15.00 each = 45.00 · 16 Oct–15 Nov 23.23×1=23.23 + 22.50×1=22.50 (total 45.73) |
| new | `NB-TH` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | — | retired the seeded BASE-TH first · stored TH-T10 35.00, TH-T25 80.00, TH-T5 20.00, TH-T50 150.00 · GL 4170 — Thermal/Heat · changed TH-T5 → 21.00 · Next change tile: $21.00 · rate schedules reading it as base: 1; plans reached: 3 · bill preview (AC-2026-00001): Oct preview refused: This connection's size is not recorded. Record the connection's size.; Nov preview refused: This connection's size is not recorded. Record the connection's size.; 16 Oct–15 Nov preview refused: This connection's size is not recorded. Record the connection's size. |
| new | `NB-W-COM` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-W-COM first · stored W-1 22.00, W-112 28.00, W-2 60.00, W-34 15.00, W-4 150.00, W-58 15.00 · GL 4115 — Water base · changed W-58 → 16.00 · Next change tile: $16.00 · rate schedules reading it as base: 5; plans reached: 5 · bill preview AC-2026-00047: Oct 28.00×1=28.00 · Nov 28.00×1=28.00 · 16 Oct–15 Nov 14.45×1=14.45 + 14.00×1=14.00 (total 28.45) |
| new | `NB-W-RES` | base | sized | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | retired the seeded BASE-W first · stored W-1 11.50, W-2 34.00, W-34 8.00, W-58 8.00 · GL 4115 — Water base · changed W-58 → 9.00 · Next change tile: $16.00 · rate schedules reading it as base: 5; plans reached: 5 · bill preview AC-2026-00001: Oct 8.00×1=8.00 · Nov 9.00×1=9.00 · 16 Oct–15 Nov 4.13×1=4.13 + 4.50×1=4.50 (total 8.63) |
