# J-PAY-chase-the-morning — one clerk, one hour: filter to over sixty days · open the worst of them · read what was already tried · take a part payment

---
id: JPAYCHASEMORNING
tier: 1
rules: [BR-PAY-029, BR-PAY-032, BR-PAY-017, BR-PAY-1125, BR-LED-025, BR-TEN-043, BR-SHL-011, BR-SHL-025]
stories: [US-PAY-013, US-PAY-014, US-PAY-015, US-PAY-001]
---

<!-- `CR-138-BRC07` phase 4 `P4.22`, authored 2026-09-23 by LANE P4-TESTS.

     ⚠ **THE FILE IS NAMED FOR ITS ID AND THAT IS A RULE RATHER THAN A STYLE.**
     `G12` check 3 matches a browser spec to a journey BY FILENAME and the
     catalogue names files after ids, so a file called `J-PAY-chase-the-morning…`
     declaring `id: J-PAY-chase-the-morning` would be unreachable by the only
     mechanism that ever activates a journey — and the id itself is not a
     journey id under `G12`'s grammar (`^[JT][A-Za-z0-9]*(?:-\d+)?$`).
     `JPAYCOUNTERSHIFT` set the convention on 2026-09-23: the human name is the
     TITLE line, the id is the squeezed form, the filename carries the id.

     ⚠ **EVERY FIGURE BELOW WAS MEASURED, NOT PLANNED.**
     `10-scripts/cr138_p4_journeys_readback.py` performs this walk on real
     PostgreSQL 16 and prints what each step leaves. `J19` is in this catalogue
     as the warning: it was written from a plan, and on 2026-08-15 it went red
     at step 1 — *not on a wrong figure, on the absence of anything to click*
     (`DEF-112`). -->

**Intent.** The phase's own *what a clerk can newly do*, walked: **search, sort,
filter and page the debtor list — none of which worked before `P4.7` — then
open one debtor, a screen the list had never had, and act.** It is the journey
the whole of phase 4 exists to make possible.

**Fixture.** Tenant brazos-bend, business day **2026-09-23** (`BR-TEN-043`: an
argument, never a clock — re-running this on any date prints these same
figures). Measured on two databases, **the same walk at two tenant sizes**:

| | `sbh_clone_p4walk` | `sbh_clone_p4perf40` |
|---|---|---|
| accounts | **2,072** | **40,072** |
| debtors | **2,046** | **40,046** |
| over 60 days | **2** (`61-90`) + **0** (`90+`) | **2** (`61-90`) + **40,000** (`90+`) |
| page 1 of the filtered list | **2 rows** | **50 rows** |

⚠ **THE SECOND COLUMN IS THE TOP OF THE ICP AND IT IS THE POINT.** `CLAUDE.md`
puts T5 at 40,000 accounts. Before `P4.1` this list materialised every open
invoice and sorted in Python: **61.539 s at 40,046 debtors against a
`GUNICORN_TIMEOUT` of 60** — the debtor screen did not load at the ceiling the
product is sold at. It is one page of fifty now, cut in SQL.

| # | Step · what she does | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Opens **Debtors** (7·1) and clicks the **OVER 60 DAYS** ageing card | One `GET /outstandings?f.bucket=` per band, **paged, filtered and sorted in SQL**. Measured at 2,046 debtors: `61-90` → **2 accounts**, `90+` → **0**. At 40,046: `61-90` → **2**, `90+` → **40,000**, page 1 still **50 rows** | The tile is the two TAIL bands added and never a subtraction; the chip asks the server for one band at a time. The page serves `per` rows whatever the tenant holds — `10-scripts/cr138_p4_debtor_cost.py --check` records **12–13 statements at both sizes** | **NFR-3** · BR-PAY-029 |
| 2 | The list is already **worst first**, so the top row is the one to open | Measured both sizes, identically: **`AC-2026-00004` · `1202.400000` · 63 days late** | ⚠ **THE SORT IS THE SERVER'S.** `defaultSort` is `{balance, desc}` and the read honours it in SQL; the browser re-sorting the page would order fifty rows and call it the worst fifty | **BR-PAY-029** |
| 3 | Clicks the account number and lands on **the debtor** (7·2) | `GET /debtors/{account_no}` — **one call** for the bills, the ladder state and the trail. Measured: balance **1202.400000**, oldest unpaid bill **2026-07-22**, **2** open bills | ⚠ **THE ADDRESS CARRIES THE ACCOUNT NUMBER, NOT THE ID** — `/…/payments/debtors/AC-2026-00004`. B14 rule 31 governs what a utility user can READ and an address bar is the most visible field a screen has | **B14 rule 31** · BR-PAY-032 |
| 4 | Reads **what was already tried** | The notice trail, **paged in SQL** (`notice_history_page`, LIMIT/OFFSET) with its `COUNT(*)` beside it. Measured on this account: **0 rows, count 0** — *"nothing recorded"* | ⚠ **AN EMPTY TRAIL AND AN UNKNOWN TRAIL READ DIFFERENTLY.** Zero rows with a zero count is *nobody has chased this customer*; the trail is the only unbounded read on this screen and it is the one that is paged | **NFR-3** · J4 step 2 |
| 5 | Reads **what would happen next** | The ladder position, whole. Measured on this clone: `current_tier` **null**, `runs` **null** | ⚠ **`runs: null` IS *THIS DEPLOYMENT CANNOT SAY*, AND IT IS NOT *no*.** The clone stores no ladder balance floor, so `thresholds_unset` is the honest answer and the screen prints *Cannot say yet*. A build that drew null as *will not send* would tell a clerk the opposite of the truth | **BR-PAY-017** · BR-SHL-025 |
| 6 | Takes a **part payment** at the counter | Measured against the position above: **300.60** of **1202.400000**, leaving **901.800000** | ⚠ **TWO DECIMALS, BECAUSE THE LEDGER INSISTS.** `BR-LED-025` (PO 2026-08-12, verbatim *"Refuse and make the caller round"*) refuses a posting carrying more than two — and it refuses the whole payment with it. `300.6000` is fine; `300.6009` is not a smaller problem, it is no payment at all | **BR-LED-025** · hard rule 2 |
| 7 | **INVARIANCE** — the same walk at twenty times the tenant | Every figure in steps 2–6 is **byte-identical** between the 2,046-debtor and the 40,046-debtor database; only the counts in step 1 move | ⚠ **THAT IS THE WHOLE `NFR-3` CLAIM, STATED AS A JOURNEY.** A clerk's morning does not get slower because the utility grew. `cr138_p4_debtor_cost.py --check` is the machine half and `10-scripts/cr138_p4_18_statement_record.jsonl` is where both sizes are recorded | **NFR-3 · NFR-5** |

---

## What a browser can actually drive, as of 2026-09-23 — and where this walk STOPS

**Steps 1 to 5 are drivable end to end.** 7·1 is on `DataTable` since `P4.7`,
7·2 exists since `P4.8`, and `10-scripts/cr138_p4_debtor_screens_walkthrough.mjs`
opens both against a running stack.

⚠ **STEP 1's FILTER IS NOT ASKED OF THE SERVER YET, AND THE DIFFERENCE MATTERS
AT 40,000.** `GET /outstandings` *can* page, sort, band, filter and count in
SQL — `P4.1` — and **screen 7·1 does not ask it to**: `OutstandingsTab` still
runs `clientPage` over the rows the server sent whole. That is `DEF-PAY-6271`,
and it is why this walk's step 1 is measured through the READ rather than
through the screen. **The journey above is what the server can serve today; the
screen catches up when that defect closes.**

⚠ **STEP 6 IS A DESCRIPTION, NOT A WRITE, AND THE READBACK SAYS SO.** Recording
a payment posts a balanced journal pair and an audit row. A readback that left
those behind on a shared clone would make the next run's figures differ from the
ones in this file, which is the one thing a measured journey may not do.
`tests/test_us_pay_001_*` owns the write.

### Two things this walk proved that nothing had asserted

1. **The filtered page is the same size at 2,046 debtors and at 40,046.**
   Measured: `90+` holds **0** accounts on one database and **40,000** on the
   other, and page 1 holds **2** and **50** — `per`, never the tenant. The
   statement count is **12–13 at both**, recorded in
   `10-scripts/cr138_p4_18_statement_record.jsonl`.
2. **A debtor with NO trail and a debtor whose trail could not be read are
   different screens.** This account has `history: []` with `history_count: 0`
   and `runs: null`, which the product draws as *"nothing recorded"* and
   *"Cannot say yet"* — two different sentences for two different facts. A
   build that collapsed them would let a clerk believe an unchased customer had
   been chased and stopped.
