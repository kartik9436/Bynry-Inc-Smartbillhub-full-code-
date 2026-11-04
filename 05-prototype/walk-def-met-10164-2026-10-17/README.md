# Walk — Premises and Units lists show Created + Age, 2026-10-17

`DEF-MET-10164` · PO ruling 2026-10-17 (decision log *"PREMISES AND UNITS LISTS SHOW
CREATED + AGE; IMPORT MAY CARRY THE ORIGINAL CREATED DATE"*, and the lane's *"AS BUILT"*
entry beneath it). The defect stays **open** for the coordinator to close at release.

**Set-up.** Private copy `smartbillhub_mv10164` (`createdb -T smartbillhub`, at the tip's
migrations, dropped afterwards). Backend `runserver` on **8022** (local settings, this
branch, `JOBS_EAGER=true`, exports to a private S3 emulator on 5022), SPA
`vite build --mode compose` served by `server.mjs` on **8102**. Staff Dana Whitfield
(System Admin), Brazos Bend, Chromium 1440px. Tenant zone America/Chicago, date format
MM/DD/YYYY. "Today" on the copy is **10/17/2026**. Script:
`10-scripts/walk_def_met_10164_2026_10_17.mjs` (`STEP=W1…W10`).

| # | Scenario | Figure seen | Result | Shots |
|---|---|---|---|---|
| W1 | Premises list before / after | Before (the running main app, without this branch): `PREMISE · ADDRESS · TYPE · UNITS · SERVICES · MASTER A/C · ON THE MAP · STATUS · ACTIONS`. After: `… · STATUS · CREATED · AGE · ACTIONS`; P-00001 `10/11/2026 · 6 days` | PASS | `w1-premises-before.png`, `w1-premises-after.png` |
| W2 | Sort Premises by Created, both ways; same via Age | Created ▲ (`?sort=created&dir=asc`): P-00081 `03/14/1996 · 30 yrs 7 mos`, P-00082 `07/04/1999 · 27 yrs 3 mos`, P-00083 `06/01/2001 · 25 yrs 4 mos`. Created ▼: P-00080 `10/17/2026 · 0 days`, P-00079 `10/11/2026 · 6 days`. The Age header sends the same `sort=created` and gives the same two orders; both headers show the sort arrow | PASS | `w2-premises-created-oldest-first.png`, `w2-premises-created-newest-first.png`, `w2-premises-age-header-oldest-first.png`, `w2-premises-age-header-newest-first.png` |
| W3 | Units list: Created + Age, sort both ways | Columns `… · STATUS · CREATED · AGE · ACTIONS`. ▲: Apt 1A U-00003 `06/01/2015 · 11 yrs 4 mos` first. ▼: Apt 1B U-00004 `10/17/2026 · 0 days` first | PASS | `w3-units-list.png`, `w3-units-created-oldest-first.png`, `w3-units-created-newest-first.png` |
| W4 | New premise on screen today, then New unit under it | Add a premise wizard → *Create premise* → **P-00080** 4417 Walk Created Ln `10/17/2026 · 0 days`. Add units → *Create 1 unit* → **U-00002** `10/17/2026 · 0 days` (the wizard's own first unit U-00001 also reads `0 days`) | PASS | `w4-new-premise-today.png`, `w4-new-unit-today.png` |
| W5 | Import 3 premises: `03/14/1996`, blank, `2001-06-01` (ISO) | Insert, 3 loaded. 101 Silver Creek Rd (Katy) **`03/14/1996 · 30 yrs 7 mos`** — the PO's worked figure; 102 `10/17/2026 · 0 days` (import day); 103 `06/01/2001 · 25 yrs 4 mos` | PASS | `w5-stage-0…4.png`, `w5-imported-premises-list.png` |
| W6 | Refusals: a future date and `14/03/1996` | Stage 3 rejects row 1 *"Date is in the future. Use today or an earlier date."* and row 2 *"14/03/1996 is not MM/DD/YYYY. Use MM/DD/YYYY."*; row 3 loads: 203 Refusal Way `05/05/2005 · 21 yrs 5 mos`. Receipt offers *Download the 2 rows that failed* | PASS | `w6-stage-2.png` (rejects), `w6-stage-4.png`, `w6-refusals-list.png` |
| W7 | Units import with an old Created | Under P-00081 (building `03/14/1996 · 30 yrs 7 mos`): Apt 1A U-00003 **`06/01/2015 · 11 yrs 4 mos`** — its own age, younger than its building; Apt 1B (blank) `10/17/2026 · 0 days` | PASS | `w7-stage-0…4.png`, `w7-units-own-age.png` |
| W8 | Re-import an existing premise number with only a new Created | File `Premise ID,Created / P-00082,07/04/1999`, *Insert & update* → P-00082 `07/04/1999 · 27 yrs 3 mos`. On the copy: address, city, status, owner and `updated_at` unchanged. Audit (premise page, Audit log tab): *Dana Whitfield · Created at · 2026-10-17T16:16:29… → 1999-07-04T00:00:00-05:00 · Run no IMP-261017-08*. **First attempt failed** — the header `Premise ID` mapped to nothing, so the file read as a lone Created column and stage 2 refused it for a missing address; fixed in this branch (`premise id` / `unit no` / `unit id` aliases) and re-walked | PASS (after fix) | `w8-stage-0…4.png`, `w8-reimport-date-corrected.png`, `w8-premise-audit-tab.png` |
| W9 | Download from both lists includes Created | Premises CSV header ends `…,status,created_at`; first row `P-00081,101 Silver Creek Rd,…,1996-03-14T00:00:00-06:00`. Units CSV ends `…,status,created_at`; `U-00003,P-00081,Apt 1A,…,2015-06-01T00:00:00-05:00` | PASS | `w9p-export-ready.png`, `w9u-export-ready.png` |
| W10 | Created cannot be edited | Edit premise fields: Street address · City · State · ZIP · Import reference · Property type · City limits · Utility services · Master a/c · Managed by · Area · Sub-area. Edit unit: Unit label · Unit type · Floor · Floor area · Services · This is a common area · Plan. **No Created field on either**; a `created_at` sent to either edit endpoint leaves the stamp unchanged (test) | PASS | `w10p-edit-form-no-created.png`, `w10u-edit-form-no-created.png` |
| W11 | A second utility does not see or affect the first's dates | **Not walkable on this copy: it holds one utility (Brazos Bend, 84 premises).** Covered by `test_another_utility_cannot_correct_this_utilitys_date` on PostgreSQL: Lonestar Ridge re-imports Brazos Bend's own premise number with `03/14/1996` → row refused (the number is not on file for that utility) and Brazos Bend's Created is unchanged | PASS (by test) | — |

**Noticed, not changed.** On the Age header ▲ means *oldest record first* (it is the
Created sort), so the arrow points the opposite way to the age figures. Recorded in the
decision log's as-built entry; a different arrow would be a second sort name.
