# Asset upload fix — confirmed columns and build plan (2026-09-30)

Status: **CONFIRMED BY THE PO; BUILT 2026-09-30 IN 2.411.0** (asset-upload lane — U1–U15;
U14's browser journey `08-qa/01-e2e/journeys/J71-…` was WALKED 2026-09-30 at 1440 and 1280 — all
seven walk steps pass after two fixes in 2.411.1 (`DEF-AST-8360` receipt, `DEF-AST-8361` picker),
one defect filed outside the upload files (`DEF-MET-8362`), results at the foot of J71;
the `$36.00` worked figure in U12 waits on base-per-asset, `DEF-BIL-8095`, so U12 asserts the
COUNT of 2). Rule: `BR-AST-541`. From a tester's report that the devices
sheet cannot set Service or Size (*"it won't work with the devices sheet, and it never
can. That sheet has no Service or Size column, and a re-import skips those fields on
existing assets"*). Rulings: the 2026-09-30 asset-upload rows in
`12-governance/02-decision-log.md`. PO on the tables below: *"these are all correct +
all these tasks are good"*.

Legend: **Match key** finds the existing asset (blank = create) · **Insert only** set on
create, never by re-upload (moving an asset is the Reassign screen) · **Insert and
update** set on create and overridden by re-upload (PO: *"we need to override it in
case of upload"*) · 💲 billing-affecting: logged old → new, forward-only from the next
bill (BR-AST-012), and listed per asset in the upload's result file.

## Meters — 19 columns, 6 groups, 1 required

| # | Group | Column | Req | New | Mode |
|---|---|---|---|---|---|
| 1 | Identity | Meter number (existing only) | | | Match key |
| 2 | | External reference | | | Insert and update |
| 3 | | Serial number | | | Insert and update |
| 4 | Location | Unit | | | Insert only |
| 5 | Service and billing | Service | ✔ | | Insert and update 💲 |
| 6 | | Connection size | | | Insert and update 💲 |
| 7 | | Unit of measure | | ✅ | Insert and update 💲 |
| 8 | | Multiplier | | | Insert and update 💲 |
| 9 | | Net metering | | ✅ | Insert and update 💲 |
| 10 | Meter details | Meter type | | | Insert and update |
| 11 | | Read method | | | Insert and update |
| 12 | | Register digits | | ✅ | Insert and update |
| 13 | | Manufacturer | | | Insert and update |
| 14 | | Model | | | Insert and update |
| 15 | Dates | Install date | | | Insert and update |
| 16 | | Certification due | | | Insert and update |
| 17 | | Warranty end | | | Insert and update |
| 18 | Purchase | Supplier | | | Insert and update |
| 19 | | Purchase cost | | | Insert and update |

## Sub-meters — 21 columns, 6 groups, 2 required (no Connection size — ruled)

| # | Group | Column | Req | New | Mode |
|---|---|---|---|---|---|
| 1 | Identity | Sub-meter number (existing only) | | | Match key |
| 2 | | External reference | | | Insert and update |
| 3 | | Serial number | | | Insert and update |
| 4 | Location | Unit | | | Insert only |
| 5 | | Parent / master meter | ✔ | | Insert only |
| 6 | Service and billing | Service | ✔ | | Insert and update 💲 |
| 7 | | Unit of measure | | ✅ | Insert and update 💲 |
| 8 | | Multiplier | | | Insert and update 💲 |
| 9 | | Allocation share % | | | Insert and update 💲 |
| 10 | | Allocation rule | | ✅ | Insert and update 💲 |
| 11 | | Loss tolerance % | | ✅ | Insert and update |
| 12 | Meter details | Meter type | | | Insert and update |
| 13 | | Read method | | | Insert and update |
| 14 | | Register digits | | ✅ | Insert and update |
| 15 | | Manufacturer | | | Insert and update |
| 16 | | Model | | | Insert and update |
| 17 | Dates | Install date | | | Insert and update |
| 18 | | Certification due | | | Insert and update |
| 19 | | Warranty end | | | Insert and update |
| 20 | Purchase | Supplier | | | Insert and update |
| 21 | | Purchase cost | | | Insert and update |

## Behind the meter (devices) — 19 columns, 6 groups, 2 required

| # | Group | Column | Req | New | Mode |
|---|---|---|---|---|---|
| 1 | Identity | Device number (existing only) | | | Match key |
| 2 | | Device type | ✔ | | Insert only |
| 3 | | External reference | | | Insert and update |
| 4 | | Serial number | | | Insert and update |
| 5 | Location | Premises | | | Insert only |
| 6 | | Unit | | | Insert only |
| 7 | | Parent / linked meter | | ✅ | Insert only |
| 8 | Service and billing | Service | ✔ | ✅ | Insert and update 💲 |
| 9 | | Size | | ✅ | Insert and update 💲 |
| 10 | | Unit of measure / capacity unit | | ✅ | Insert and update 💲 |
| 11 | | Export capacity (kW) | | | Insert and update 💲 |
| 12 | Device details | Manufacturer | | | Insert and update |
| 13 | | Model | | | Insert and update |
| 14 | Dates and testing | Install date | | | Insert and update |
| 15 | | Test frequency (months) | | | Insert and update |
| 16 | | Next test due | | | Insert and update |
| 17 | | Warranty end | | | Insert and update |
| 18 | Purchase | Supplier | | | Insert and update |
| 19 | | Purchase cost | | | Insert and update |

Blank Unit of measure = the service's default unit (`tenancy.services.SERVICE_DEFAULT_UOMS`).
Blank Size loads the asset; a per-size schedule then says by name that no size is recorded.

## Tasks

| # | Area | Task |
|---|---|---|
| U1 | Records | Defects filed for each missing column set and the re-upload skip; `BR-AST-034` (template list + re-upload override), `BR-AST-012` (kept: audit, forward-only), the devices Size reversal of 2026-08-28 |
| U2 | Backend | Columns in the order above, required flags, samples (`metering/import_runs.py` `ASSETS_*_COLUMNS`) |
| U3 | Backend | Header aliases ("UOM", "Net metered", "Digits", "Parent meter", …) |
| U4 | Backend | Row checks, all problems at once: service sold by the utility; size from THAT service's list; UoM allowed for the service; allocation rule from its list; register digits 4–10; loss tolerance 0–100%; parent exists and is the same service |
| U5 | Backend | A device attaches to its service's service point on the unit; no such point → row refused by name ("Unit has no Trash service") |
| U6 | Backend | Create saves unit of measure, net metering, register digits, allocation rule, loss tolerance, size, parent link |
| U7 | Backend | **Re-upload OVERRIDES** the insert-and-update columns, 💲 ones included — audited old → new, forward-only, listed in the result file (supersedes the "fill only when empty" draft, PO 2026-09-30) |
| U8 | Backend | Result file shows the new fields and every 💲 change old → new |
| U9 | Frontend | Labels, help and group names for the new columns, eleven languages |
| U10 | Frontend | Asset add/edit screens carry the same fields |
| U11 | Data | Sample sheets regenerated for the three templates |
| U12 | Tests | One per new column, RED first; device with Service counted (2 carts = $36.00); wrong-service size refused; blank UoM defaults; three problems in one row all shown; re-upload override audited and forward-only |
| U13 | Tests | PostgreSQL: 250 devices uploaded and the unit billed |
| U14 | Browser | Template → fill → upload → carts and fire lines on the unit → bill preview counts them |
| U15 | Close | Version bump on each defect; tell the tester the build |

**Order:** U1 → U2–U8 → U9–U11 → U12–U14 → U15. **U5 lands before or with the one-time
bill's "no asset = not in service" (build plan B2)**, or uploaded carts and fire lines drop off bills.
