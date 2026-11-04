# Walk — asset Age on Meters, Sub-meters and Behind the meter, 2026-10-17

`DEF-AST-10178` · PO ruling 2026-10-17, *"this is all corect"* (decision log *"ASSET AGE ON
METERS, SUB-METERS AND BEHIND-THE-METER LISTS"*). The defect stays **open** for the
coordinator to close at release.

**Set-up.** Private copy `smartbillhub_astage` (`createdb -T smartbillhub`, dropped
afterwards). Backend `runserver` on **8026** (local settings, this branch), SPA
`vite build --mode compose` served by `server.mjs` on **8106**. Staff Dana Whitfield,
Brazos Bend (America/Chicago), 1440px, real today **10/17/2026**. Script:
`10-scripts/walk_asset_age_2026_10_17.mjs`; every tab opened with `f.status=all&sort=age`.

**The six worked examples, set up on the copy by editing dates** (the copy holds none of
the PO's own rows, so existing Brazos assets stand in; two were renumbered on the copy only):

| Worked example | Copy row | Edited on the copy |
|---|---|---|
| 334556 installed 09/12/2026 | `E-5000` → **334556** | install 2026-09-12 |
| SM-7040 installed 01/15/2026 | **SM-7040** | install 2026-01-15 |
| AST-04413 bought 03/01/2024, never installed | **AST-04413** (a meter here) | purchase 2024-03-01 |
| AST-00010 entered 10/02/2026 | `BAT-0904` → **AST-00010** (behind the meter) | created 2026-10-02 15:00 UTC, no install/purchase |
| installed 05/01/2010, life 15 | **M-4022** | install 2010-05-01, life 15 |
| installed 2012, retired 06/30/2025 | **E-5001** | install 2012-05-15, retired 2025-06-30, stage Retired |

## What the screen shows

| Tab | Row | Installed | Age | PO's figure |
|---|---|---|---|---|
| Meters | 334556 | Sep 2026 | **1 mo** | 1 mo ✓ |
| Sub-meters | SM-7040 | Jan 2026 | **9 mos** | 9 mos ✓ |
| Meters | AST-04413 | — | **2 yrs 7 mos** · *from purchase* | 2 yrs 7 mos · from purchase ✓ |
| Behind the meter | AST-00010 | — | **15 days** · *from record* | 15 days · from record ✓ |
| Meters | M-4022 | May 2010 | **16 yrs 5 mos** · *Past life*, in red | 16 yrs 5 mos · Past life ✓ |
| Meters | E-5001 (Retired) | May 2012 | **13 yrs 1 mo** — stopped at 06/30/2025 | 13 yrs 1 mo ✓ |

Behind the meter now has an **Installed** column, immediately before Age.

**Sort, oldest ↔ newest, on every tab** (start date; ascending = oldest first):

- Meters ▲: M-4022 (16 yrs 5 mos) · E-5001 (13 yrs 1 mo) · AST-04414 · AST-04412 · M-4021 ·
  AST-04413 6th. Meters ▼: M-5099 (6 days, from record) · 334556 (1 mo) · W-5101 …
- Sub-meters ▲: M-7204 (1 yr 9 mos) first, SM-7040 (installed ten days after the rest) 10th of
  10. ▼: SM-7040 first.
- Behind the meter ▲: BF-3301 (1 yr 9 mos) first, AST-00010 9th of 9. ▼: AST-00010
  (15 days) · BF-0002 (4 mos, from purchase) · CART-0099 …

Shots: `meters-age-asc.png` (Past life in red, the retired meter, *from purchase*),
`meters-age-desc.png` (334556, *from record*), `sub_meters-age-asc.png`,
`sub_meters-age-desc.png`, `behind_the_meter-age-asc.png`, `behind_the_meter-age-desc.png`
(Installed column, *from record*, *from purchase*). Full read-back: `walk-output.txt`.

## The download

Pressing Download on this machine answers *"The export didn't finish. File storage is not
set up."* (`meters-download-notice.png`): exports go to S3 only and a local run has no
bucket — the same for every list, nothing to do with this change. So the Meters file was
built by `10-scripts/walk_asset_age_export_2026_10_17.py`, which runs the export job's own
path (`params_from_payload` → `select` → `row_stream` → `write_csv`) for the payload the
Meters tab sends (`tab=meters`, `status=all`, `sort=age`, `asc`) and stops before the
upload. `meters-download.csv`, 118 rows, new columns
`age_start, age_from, age_years, age_months, age_days, past_life`:

```
M-4022    … 2010-05-01,install,16,5,16,true
E-5001    … 2012-05-15,install,13,1,15,false
AST-04413 … 2024-03-01,purchase,2,7,16,false
334556    … 2026-09-12,install,0,1,5,false
M-5099    … 2026-10-11,record,0,0,6,false
```

The file's first rows are M-4022, E-5001, AST-04414 — the same oldest-first order as the screen.

## Seen and not fixed

At 1440px the status pill is clipped on Meters and Behind the meter (*Installe…*,
*Invent…*). This walk did not shoot the base build, so how much of that predates the change
is not measured — but Age adds one column on every tab and Behind the meter gets two
(Installed and Age), so it cannot have helped. Which column gives way is a layout call for
the coordinator.
