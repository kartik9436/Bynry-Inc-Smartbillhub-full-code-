# Walk — Account age and Aging on the Accounts list, 2026-10-17

`DEF-CUS-10180` (Account age) · `DEF-CUS-10181` (Aging reads bills) — filed as
`DEF-CUS-10165` / `DEF-CUS-10166` and renumbered to the coordinator's reservation.
Decision log 2026-10-17, *"ACCOUNT AGE ON THE ACCOUNTS LIST; AGING STAYS MONEY AND IS
FIXED TO READ BILLS"* (PO: *"this si all correct - fix it"*). Both defects stay open for
the coordinator to close at release.

**Set-up.** Private copy `smartbillhub_accage` (`createdb -T smartbillhub`, already at
the tip's migrations; dropped afterwards). Backend `runserver` on **8027** (local
settings, this branch), SPA `vite build --mode compose` served by `server.mjs` on
**8107**. Staff Dana Whitfield, Brazos Bend, Chromium 1440px.
`10-scripts/walk_account_age_2026_10_17_prep.py --apply` shaped the copy:
`A-12048` pending activation with no Opened date; `AC-2026-00051` reopened (Opened
10/14/2026, Closed cleared — what the CR-181 reopen writes); `AC-2026-00001`'s oldest
issued bill moved to fall due **08/01/2026**. `--import` loaded a two-row file through the
one import runner (run `IMP-261017-03`): `A-2012-OLD` Opened `03/01/2012` (the tenant's
own MM/DD/YYYY) **loaded**, `A-FUTURE` Opened `01/15/2027` **refused** — *"Opened date
2027-01-15 is in the future."* `AC-2026-00042` was already closed (09/30/2026).
Scripts: `10-scripts/walk_account_age_2026_10_17.mjs`, `…_import.mjs`.

## Results — PASS (one environment limit, below)

| Shot | What it shows |
|---|---|
| `1-account-age-column.png` | **Account age** column next to **Aging**, Opened date beneath each age; `A-2012-OLD` **14 yrs 7 mos · 03/01/2012** |
| `2-sort-oldest-first.png` | Account age ▲: `A-2012-OLD` 14 yrs 7 mos → `A-11720` 7 yrs 6 mos (04/01/2019) → `A-11512` 5 yrs 11 mos → … |
| `3-sort-newest-first.png`, `3b-…-bottom.png`, `sort-desc-rows.txt` | Account age ▼: `AC-2026-00051` 3 days first; the last three rows `A-11720`, `A-2012-OLD`, then `A-12048` **Not opened** (78 rows) |
| `4-closed-account.png` | `AC-2026-00042` **1 mo · closed 09/30/2026** — stopped at its Closed date |
| `5-pending-not-opened.png` | `A-12048` **Not opened** |
| `6-reopened-restarted.png` | `AC-2026-00051` **3 days · 10/14/2026** |
| `7-imported-2012.png` | `A-2012-OLD` **14 yrs 7 mos · 03/01/2012** |
| `8-bill-77-days-overdue.png` | `AC-2026-00001`, bill due 08/01/2026 unpaid: Aging **61–90 days past** (hover: 77 days past due). Before this change the cell read only migrated buckets, and this account has none |
| `9-aging-filter-61-90.png` | Filter 61–90 returns exactly three: `A-11812`, `A-11455` (67 days), `AC-2026-00001` (77 days) — all bill-only |
| `10-aging-sort-desc.png` | Aging ▼: three 90+ (`A-12103` 138 days from its migrated opening, `A-11721`, `A-11340` 97), then the three 61–90, then 31–60, then Current; nothing owed last |
| `12-imports-tab.png`, `12b-import-run.png` | `IMP-261017-03 · legacy-accounts-2012.csv · in 2 · loaded 1 · rejected 1` |
| `11-download-requested.png`, `11b-download-outcome.png`, `accounts-download.csv` | The new Download control on the Accounts toolbar. See the limit below |

**The download, and the one thing this sandbox cannot show.** Pressing Download started
the job and the server **built the file — 78 rows** (`export … built accounts, 78 row(s)`
in the backend log) — then refused to PUBLISH it: `DOCUMENT_STORAGE_BUCKET is not set`
(exports live in S3 in every environment, DEF-MET-4954). The screen says *"The export
didn't finish. File storage is not set up."* No server on this host has storage
configured. `accounts-download.csv` was written by the prep script's `--csv` mode through
the kernel's own `row_stream` + `write_csv`, so its bytes are the job's. Header:
`account_no,name,premise,balance,last_bill,status,ageing,ageing_days_past_due,opened_at,closed_at,account_age`;
e.g. `AC-2026-00001,…,61-90,77,2026-08-01,,P2M` · `A-2012-OLD,…,2012-03-01,,P14Y7M` ·
`AC-2026-00042,…,2026-08-01,2026-09-30,P1M` · `A-12048,…,Pending activation,,,,,` (blank age).

Servers stopped by PID; 8000 and 8080 left running; the copy dropped.
