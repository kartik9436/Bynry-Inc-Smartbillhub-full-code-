# Walk — three billing fixes from the combined walk, 2026-10-14

Fixes for `DEF-CUS-10154`, `DEF-BIL-10155` and `DEF-BIL-10156`, each found by the
combined walk (`05-prototype/combined-walk-2026-10-14/README.md`, steps 4 and 7) and
each reproduced first, then walked again in the browser after the fix.

**Set-up.** Branch tip `776452d06` (2.581.1) plus this lane's commits. Private copy
`smartbillhub_fixmv` (`createdb -T smartbillhub`, migrated to the tip, dropped
afterwards). Backend on **8016** (`runserver`, local settings) under a scratch launcher
that shifts `django.utils.timezone.now` by N days (not committed — the combined walk's
method); the SPA built locally (`vite build --mode walk`, same-origin) and served by
`server.mjs` on **8096**. Tenant Brazos Bend, Dana Whitfield (System Admin) and Sam
Reyes (Billing Clerk); passwords set on the copy only. Utility days: **10/12** (move-out),
**10/14** (reopen), **11/02** (closing reads, the October run, the Mill Pond move-outs).
Scripts reused: `def_cus_10093_move_out_final_draft_walkthrough.mjs`,
`cr181_returning_customer_walk.mjs`, `combined_walk_2026_10_14_add_reads.mjs`; the bill
run was driven screen by screen.

## 1 · DEF-CUS-10154 — a reopened account is billed from the day after its final bill

**Decision (coordinator, engineering; decision log *"A REOPENED ACCOUNT'S NEXT BILL
STARTS THE DAY AFTER ITS FINAL BILL"*):** the final bill stays a valid bill for the
earlier tenancy and may still be sent; the reopened account's next bill starts the day
after the final bill's period end, draft or sent; a cancelled draft leaves the cycle's
normal start.

| Step (screens) | Before the fix (combined walk) | After the fix (this walk) |
|---|---|---|
| Move-out 10/12, W-5021 1,802, E-5021 3,937, *Collect* (`A1-*`) | BL-2610-000251 **$205.38** draft, 10/01–10/12 | the same: **BL-2610-000251 $205.38 · Draft** |
| Reopen 10/14, *Carry it* $168.18 (`A2-*`) | MVI, same number | the same: AC-2026-00022 reopened, $168.18 carried |
| Closing reads 10/31, E-5021 4,300, W-5021 1,806 (`A3-*`) | — | posted through Reads |
| October run, RUN-0003, CY-007 10/01–10/31 (`A4-1` … `A4-6`) | Viktor not flagged; billed 10/01–10/31 | Viktor not flagged (`A4-3`: the two *Gap or overlap* rows are AC-2026-00012 and AC-2026-00054, as before); **45 bills sent** |
| Viktor's October bill (`A4-7`) | **BL-2611-000269 $292.15**, 10/01–10/31, 1,123 kWh, 15 kgal from the 09/29 reads | **BL-2611-000269 $78.41**, **10/13–10/31**, **363 kWh** (4,300 − 3,937) and **4 kgal** (1,806 − 1,802), base $12.00 + $8.00 × 18/31 = $6.97 + $4.65 |
| The final draft (`A4-8`) | still a live draft over the same days | still **Draft, 10/01–10/12, $205.38**, Approve / Cancel draft offered — it no longer overlaps anything |

No day and no unit of usage is on two bills. (The run's total, $17,958.49, is not
comparable with the combined walk's $18,995.01: this copy has no step-2 high reading and
only Viktor's closing reads were posted.)

## 2 · DEF-BIL-10155 — Apt 101 can move out after the October bill

Reproduced first on the copy, engine level (`final_bill.preview_final_bill`, period from
11/01): keyed W-5040 2,545, SM-7040 10, E-5040 8,430, M-MASTER-01 *Estimate* →
`priced: false`, *values_missing · water · estimate_no_history · M-MASTER-01, SM-7040,
W-5040* — the walk's failure.

**Why:** the water point on Apt 101 holds the unit meter W-5040, its sub-meter SM-7040
and the building's master M-MASTER-01. The reads seam took the latest reading across
ALL of them, and the keyed overlay laid the LAST meter keyed on the point over the row —
so a never-read sub-meter (no prior) or the master's estimate (no history) became "the"
water reading and refused the draft.

**Fix:** `assets.billing_asset_ids_for_service_point` — a unit's service is measured by
its own meter (category *meters*, meter type not *master*); a sub-meter or the master
beside it is not, and a point with nothing else still bills from whatever stands on it.
Metering's reads seam and its keyed overlay both ask it, and the bulk Check primes it
from the rows it already reads.

After, in the browser on 11/02 (`B2-*`): the same four answers on step 2 → step 3 priced,
*water 8 kgal* (2,545 − 2,537), *sewer 7.2 kgal @ $5.00* (90%), final bill **$112.15**,
prior $887.29 → **Short by $999.44** → *Tie it back* → Complete → **BL-2611-000298
$112.15 · Draft**. A meter the bill does price still blocks: with W-5040 left blank the
preview still says *reading needed* (test, below).

## 3 · DEF-BIL-10156 — Apt 104's final bill prices the unit's own meter (money)

Reproduced first on the copy (with the walk's 10/31 sub-meter readings, SM-7043 5 and
SM-7201 5): keyed W-5043 2,645, SM-7043 7, SM-7201 6 → water **1 kgal** (0.32 + 0.65 +
0.03) — SM-7201's 5 → 6, the walk's figure.

After, in the browser on 11/02, with **no** workaround readings (`B1-*`): keyed W-5043
2,645, E-5043 +60, SM-7043 7, SM-7201 6 → step 3 water **6 kgal** (0.32 + 0.65 + 5.03),
**sewer 5.4 kgal @ $5.00 = $27.00**, final bill **$87.15** (was $20.95 with 1 kgal and
0.9 kgal), prior $342.26 → **Short by $429.41** → *Tie it back* → Complete →
**BL-2611-000297 $87.15 · Draft**. Read back from the database: the draft's lines are
the same figures, and `bill_payload.services` names **W-5043's 11/02 reading (2,645)**
for water — the unit meter, as the October cycle bill did.

## Tests (red first, then green)

| Test | Before the fix | After |
|---|---|---|
| `tests/test_def_cus_10154_reopen_after_final_draft.py` (4) | 2 red: billed through `None` (draft ignored); no shared marker | 4 green |
| `tests/test_def_bil_10155_10156_unit_meter_prices_the_service.py` (4) | 4 red: *estimate_no_history*; 1 kWh priced ($0.12) not 60; *estimate_no_history* where a missing *reading* belongs; no billing-meter read | 4 green |

Both files green on SQLite and on PostgreSQL 16 (`--ds=config.settings.pgtest
--create-db`).

The copy was dropped and both servers stopped after the walk.
