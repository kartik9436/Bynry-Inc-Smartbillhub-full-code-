# Rate schedules wave C — every service × every method, walked as a clerk (2026-10-01)

`CR-157-BRC10` wave C. PO, verbatim: *"we ahve 11 utility servcies and 5 types of rates - please do real combination … all combinations for all 11 services and some combinations for custoemr types - do end to end web walk - ensure they are saved corrected - do udpated on these rates scheduled and see the ya re correcyly reflected in plans, one saved the action and imapct on ther areas should be measured and it should work properly"*.

Walk: `10-scripts/rate_schedule_wave_c_walk.mjs` (Chromium 1440×1100, tenant `brazosbend`, private PostgreSQL 16 database copied from `sbh_six74_seeded` and migrated to the tip). Database and billing probe: `10-scripts/rswalk_probe.py`. Raw per-row record: `rswalk_state.json`. This table: `10-scripts/rswalk_results.py rswalk_state.json`. Two photographs per row in `matrix/`.

## The matrix — 94 rows, written before the run

**Where the allowed methods come from in the code — every method on every service:**
- `06-backend/apps/rating/services.py` `TARIFF_MODELS` = flat, tiered, time_of_use, demand, seasonal, capacity, percent_of_service. `_validate_version_fields` takes `model` through `_choice(payload, "model", TARIFF_MODELS, …)`; `_validate_schedule_identity` checks only that the service is enabled. The one service rule inside a structure is that a percent schedule's basis is not itself.
- `07-frontend/src/features/rating/RateScheduleWizard.tsx` `structureOptions()`: the Structure dropdown is `TARIFF_MODELS` for every service (*Base only* drawn disabled, image 41). `RateScheduleThreeStep.tsx` does not filter it by service.
- What a service DOES narrow: the unit (`scheduleUomOptions`) and the base charge code (the service's `is_base` codes). Both were taken as the screen offers them.

**Rows:** 11 services (electric, water, gas, sewer, trash, storm water, solar, broadband, thermal/heat, battery, fire) × 7 methods at *Every class* = **77**, plus **17** customer-class rows: Residential and Commercial for water (flat, tiered, seasonal), electric (flat, time of use, demand) and trash (flat, capacity), sewer percent Residential, and every other class the seed has once — Industrial (electric demand), Agricultural (gas flat), Institutional (water tiered), Municipal (sewer flat), Builder or developer (trash tiered), Government (storm water flat). **Total 94.**

**Per row, through the screens:** Add in three steps (two base rows with a minimum per size — the preview account's meter size first — and the method's usage pricing), effective 10/01/2026 → list row and the four View details tabs → database → **Change the rate** from 11/01/2026 → **Fix an error** on the version in force → Audit tab and `audit_log` → the plan (the `Residential Standard (Elm St)` plan's slot for the service is pointed at the schedule, the plan screen read, then put back) → a **one-time interim bill preview** for AC-2026-00001 (meters W-58 ×2, E-1P-100, CART-96) for October (before the change) and November (after), from committed reads (water 1 + 5 kgal, then 2 + 10; electric 500, then 600 kWh, on-peak 150 / 180, off-peak 350 / 420, peak 12.5 / 14.0 kW; gas 40 / 50 ccf; sewer 4 / 5 kgal) — typed readings in part 1, committed reads from part 2, for every service.

**Setup the walk does as a clerk would on Settings:** switches on storm water, solar, thermal/heat and battery; mints a base charge code for each service that has none (`BASE-G-WC`, `BASE-SW-WC`, `BASE-SOL-WC`, `BASE-BB-WC`, `BASE-TH-WC`, `BASE-BAT-WC`, `BASE-FIRE-WC`, `BASE-E-COM` for Commercial electric, `BASE-T-SZ` priced for carts only, for image 51).

**What each check means:** *DB* — one `tariff_versions` row from 10/01 with no end, the method's own rows right (`rate_tiers`, `rate_size_rows` with both minimums, `rate_seasons`, `time_of_use_windows` with the register set from the window, `capacity_rates`, `demand_rate_config`), and `selectors.in_force_version` returns exactly that version on 10/15. *Change* — the old version ends 10/31, the new starts 11/01 with the new price and the same per-size minimums, nothing overlaps, `in_force_version` picks old on 10/15 and 10/31 and new on 11/01 and 11/15. *Fix* — a correcting version with the original's dates and the corrected price; the original kept, `superseded_by` set; the November version untouched. *History* — the Audit tab shows both the change's *What changed* and the fix's reason, and `audit_log` holds at least three rows. *One version to billing* — `selectors.pricing_inputs` (billing's one projection) answers the corrected version on 10/15 and the new one on 11/15, and hands the engine the size's minimum. *Plan impact* — the plan screen names the schedule and shows the 11/01/2026 change. *Bill preview* — the preview names exactly one version, the right one, for each period, and its amount equals quantity × price, with the per-size minimum topping it up; *n/a* where no account can be billed on that shape (below).

## Passes per check

| Check | ok | FAIL | n/a | of 94 |
|---|---|---|---|---|
| Add (three steps) | 94 | 0 | 0 | 94 |
| Database after Add | 94 | 0 | 0 | 94 |
| Change the rate | 94 | 0 | 0 | 94 |
| Fix an error | 94 | 0 | 0 | 94 |
| History (Audit tab + `audit_log`) | 94 | 0 | 0 | 94 |
| One version to billing (+ minimum per size) | 94 | 0 | 0 | 94 |
| Plan impact (plan screen) | 94 | 0 | 0 | 94 |
| Bill preview, before and after the 11/01 change | **73** | **21** | **0** | 94 |

Re-measured 2026-10-02 on the tip with seasonal pricing (`2.437.1`) and every fix below in, `RSW_REBILL=1 RSW_TODAY=2026-10-01` (the schedules' own day; the run crossed midnight). **Every row is now billed — none is n/a.** Part 1 (2026-10-01) read 22 ok · 4 FAIL · 68 n/a.

**The 21 bill FAILs are three product findings, each filed, and nothing else:**
- **14 — time of use and demand on a service read from no meter** (trash, storm water, solar, broadband, thermal/heat, battery, fire × time of use and demand). Billing refuses every bill, correctly: such a service never has on-peak, off-peak or peak-demand reads. **`DEF-RAT-9015`, fixed in `2.437.7`**: the save now refuses both on Structure where the utility's billing basis for the service is not *metered*, and the dropdown shows them as *needs meter reads* (photographed: `matrix/def-rat-9015-structure-trash.png`, `…-electric.png`). These 14 schedules were saved before the fix, so they still exist and still refuse at billing; a new one cannot be saved.
- **6 — one cent over the minimum** (electric time of use, Every class and Residential; solar flat, tiered, seasonal, capacity — October only). Electric: on-peak 150 kWh × $0.1867 = $28.005 → **$28.01** and off-peak 350 × $0.1195 = $41.825 → **$41.83** on the bill, but the minimum top-up is measured against the unrounded $69.83, so it adds $10.17 and the bill reads **$80.01 against an $80.00 minimum**. Solar: 1 kW × $0.075 prints $0.08 and the top-up adds $4.93 → $10.01. **`DEF-RAT-9013`, filed, not fixed** — the rounding order is frozen money math (`apply_charges.py` says the comparison is unrounded and that the ambiguity was *"REPORTED, not resolved"* because no signed figure told the two apart; this is the first figure that does). It needs a finance ruling.
- **1 — a percent of another service charged once per meter** (water at 38% of electric). The account has two water meters and each carries the whole 38% of 500 kWh = 190 kgal × $4.4096 = $837.82, so October bills **$1,691.64 where charging it once — each meter keeping its own $8.00 base and $15.00 minimum — gives $860.82** (November $2,397.18 against $1,213.59). **`DEF-BIL-9014`, filed, not fixed** — a billing money path, and the answer is a choice between two rulings (charge a percent once per service, or refuse a percent schedule on a service read from meters).

**Seasonal (blocked in part 1 by `DEF-RAT-8832`, built on the tip):** all 12 seasonal rows bill, expected = got — electric $80.00 / $80.00, water $43.25 / $71.80, Commercial water $35.25 / $61.50, gas $47.50 / $61.50, sewer $25.20 / $33.00, trash $25.00, storm water $25.85 / $28.25, broadband $4,619.00 / $5,519.00, thermal/heat $11.30 / $11.35, battery $25.00 / $28.00, fire $23.50 / $25.00 (solar's one cent is `DEF-RAT-9013` above). ⚠ The walk's seasonal schedules have one *All year* season, so they prove a seasonal schedule bills and changes, **not** the split of a period that crosses a season boundary; that is GT-34 on the seasonal lane's commit (usage $82.72, total $103.67).

**What made every row billable (all in the private walk database, `10-scripts/rswalk_billable_setup.py`):** the account takes every service its unit is connected for; sewer is read from its own meter (Settings › Services, *metered*); a gas meter (G-250, ccf), a sewer meter (no size), a fire line (FL-2), storm-water, solar, thermal, battery assets at the first size each schedule prices, and the broadband modem sized BB-100; storm water 6 ERU and thermal 5 tons recorded on the unit (those two are summed from the unit, not the asset — without it their line read 0); committed reads on 09-30, 10-31 and 11-30 for every meter, with on-peak, off-peak and peak-demand registers. October bills Oct 1–31, November Nov 1–30, nothing typed. The Elm St plan's gas slot is the walk's ccf schedule (the seeded therm schedule cannot price a ccf meter — refused by name, correctly), and for the water-as-a-percent row its sewer slot prices the sewer meter (the seeded sewer is a percent of water's usage, which a percent-priced water does not have).

**Bill figures (expected = got):** electric flat $80.00 / $80.00 (500 kWh × $0.1195 topped up to the 100 A minimum); electric demand $197.25 (500 × $0.1195 + 12.5 kW × $11.00 = $59.75 + $137.50) / November $233.20; water time of use $48.38 / $81.23; water demand $67.80 / $105.90; gas flat $47.50 (40 ccf × $0.95 + $9.50 base) / $61.50; sewer flat $25.20 / $33.00, time of use $27.90 / $37.20, demand $31.80 / $40.70; storm water $25.85 (6 ERU × $3.10 + $7.25) / $28.25; thermal $11.30 (5 tons × $0.06 + $11.00) / $11.35; battery $25.00 (5 kW × $3.80 + $6.00) / $28.00; fire $23.50 (one 2" line $11.50 + $12.00 base, on one line) / $25.00. **Broadband $4,619.00** is the walk's own price, not a defect: broadband sums its Mbps, so BB-100 is 100 × $45.99 + $20.00 — the walk typed a monthly package price as a per-Mbps price.

**Version numbers (coordinator decision, law 13 — `DEF-RAT-9003`, fixed in `2.437.3`):** a number never changes once shown. Versions are numbered in the order they were saved, so correcting October's v1 after November's v2 was scheduled leaves November as **v2** and the correction is **v3 · Fixes v1** (photographed: `matrix/def-rat-9011-next-change-electric-demand-industrial.png` — *In force v3*, *Next change v2 · 11/01/2026*). This supersedes part 1's judgment (a) below, which numbered by position.

**`DEF-RAT-9011`** (Next change tile overflowing and not naming whose base price it shows) was fixed on the tip by the charge-code lane in `2.437.6` before this lane reached it; re-checked on three of the walk's schedules at 1440 — the tile fits (`matrix/def-rat-9011-next-change-*.png`).

## Defects the walk found

| Defect | What the clerk saw | State |
|---|---|---|
| `DEF-RAT-8830` | Step 2: picking a smaller size in a new base row moved the row above the others and dropped focus; a minimum typed into the bottom row landed on another size (CART-96 saved $60.00, DUMP-2 none) | **fixed** |
| `DEF-RAT-8829` | Fix an error with a change already scheduled: the wizard said *v2 (corrected)* for a correction of v1 | **fixed** |
| `DEF-RAT-8835` | Edit: the Base charge code field read *Search codes* over a schedule naming BASE-W | **fixed** |
| `DEF-BIL-8831` | One-time bill refused for a TOU / demand schedule with a glued sentence | **fixed** |
| `DEF-RAT-8840` | The Rate schedules tab printed a paragraph no drawing has | **fixed** |
| `DEF-RAT-8841` | Step 2 Time of use: Window and Days squeezed to *On-* / *We* | **fixed** |
| `DEF-RAT-8832` | Every bill on a Seasonal schedule refused | **fixed by the seasonal lane** (`2.437.1`) — 12 of 12 seasonal rows bill |
| `DEF-RAT-8842` | The list is 1,188px in a 1,120px column at 1440; Retire cut off | open — the kit gap `DEF-SHL-5378` |
| `DEF-RAT-9003` | Correcting v1 after v2 was scheduled renumbered November to v3 | **fixed** (`2.437.3`) |
| `DEF-RAT-9015` | Time of use / Demand saved for a counted service; every bill refused | **fixed** (`2.437.7`) |
| `DEF-RAT-9013` | A bill held up to a minimum reads one cent over it ($80.01 / $80.00) | open — finance ruling (frozen money math) |
| `DEF-BIL-9014` | A percent of another service charged on each meter ($1,691.64 for $860.82) | open — a ruling between two answers |

**Part 1's judgment (a) is superseded:** it numbered a correction by position, so correcting v1 after v2 moved the scheduled one to v3; the coordinator ruled that a shown number never moves (`DEF-RAT-9003`).

**Reds this lane did not cause, dated:** `tests/test_br_met_143_register_units.py::test_the_seeded_meter_carries_a_multiplier_of_one_when_the_units_match` fails on the tip's own `services.py` (checked by swapping this lane's file out, 2026-10-01) — two more seeded meters than it lists. Part 1's list: `test_def_bil_8287` census (2 cases, `DEF-BIL-8807`, since `bd94c047e`); front-end censuses `ConfirmDialogTier`, `selectionToolbarWiring`, `regionalReachesTheScreen`, `serviceNamespace`.

## Per row

| # | Service | Method | Class | Add | DB | Change the rate | Fix an error | History | One version to billing | Plan impact | Bill preview | Bill figure expected/got | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | electric | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 2 | electric | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 93.24/93.24 |  |
| 3 | electric | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 80.00/80.01 · after 89.05/89.05 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 4 | electric | demand | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 197.25/197.25 · after 233.20/233.20 |  |
| 5 | electric | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 6 | electric | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 7 | electric | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 8 | water | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 43.25/43.25 · after 71.80/71.80 |  |
| 9 | water | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 43.25/43.25 · after 76.11/76.11 |  |
| 10 | water | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 48.38/48.38 · after 81.23/81.23 |  |
| 11 | water | demand | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 67.80/67.80 · after 105.90/105.90 |  |
| 12 | water | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 43.25/43.25 · after 71.80/71.80 |  |
| 13 | water | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 43.25/43.25 · after 71.80/71.80 |  |
| 14 | water | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 860.82/1691.64 · after 1213.59/2397.18 | DEF-BIL-9014: the percent is charged on each of 2 meters; expected once |
| 15 | gas | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 47.50/47.50 · after 61.50/61.50 |  |
| 16 | gas | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 57.13/57.13 · after 69.83/69.83 |  |
| 17 | gas | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 53.74/53.74 · after 67.95/67.95 |  |
| 18 | gas | demand | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 75.00/75.00 · after 94.50/94.50 |  |
| 19 | gas | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 47.50/47.50 · after 61.50/61.50 |  |
| 20 | gas | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 47.50/47.50 · after 61.50/61.50 |  |
| 21 | gas | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.73/11.73 · after 14.79/14.79 |  |
| 22 | sewer | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.20/25.20 · after 33.00/33.00 |  |
| 23 | sewer | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.20/25.20 · after 33.00/33.00 |  |
| 24 | sewer | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 27.90/27.90 · after 37.20/37.20 |  |
| 25 | sewer | demand | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 31.80/31.80 · after 40.70/40.70 |  |
| 26 | sewer | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.20/25.20 · after 33.00/33.00 |  |
| 27 | sewer | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.20/25.20 · after 33.00/33.00 |  |
| 28 | sewer | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 17.40/17.40 · after 33.00/33.00 |  |
| 29 | trash | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 30 | trash | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 31 | trash | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 32 | trash | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 33 | trash | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 34 | trash | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 35 | trash | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 37.20/37.20 · after 84.00/84.00 |  |
| 36 | storm_water | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.85/25.85 · after 28.25/28.25 |  |
| 37 | storm_water | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 26.81/26.81 · after 28.81/28.81 |  |
| 38 | storm_water | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 39 | storm_water | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 40 | storm_water | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.85/25.85 · after 28.25/28.25 |  |
| 41 | storm_water | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.85/25.85 · after 28.25/28.25 |  |
| 42 | storm_water | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 14.66/14.66 · after 24.80/24.80 |  |
| 43 | solar | flat | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 10.00/10.01 · after 10.00/10.00 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 44 | solar | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 10.00/10.01 · after 10.00/10.00 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 45 | solar | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 46 | solar | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 47 | solar | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 10.00/10.01 · after 10.00/10.00 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 48 | solar | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 10.00/10.01 · after 10.00/10.00 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 49 | solar | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 10.00/10.00 · after 10.00/10.00 |  |
| 50 | broadband | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 4619.00/4619.00 · after 5519.00/5519.00 |  |
| 51 | broadband | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 6186.26/6186.26 · after 6231.26/6231.26 |  |
| 52 | broadband | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 53 | broadband | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 54 | broadband | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 4619.00/4619.00 · after 5519.00/5519.00 |  |
| 55 | broadband | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 4619.00/4619.00 · after 5519.00/5519.00 |  |
| 56 | broadband | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 133.98/133.98 · after 289.95/289.95 |  |
| 57 | thermal_heat | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.30/11.30 · after 11.35/11.35 |  |
| 58 | thermal_heat | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.30/11.30 · after 11.35/11.35 |  |
| 59 | thermal_heat | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 60 | thermal_heat | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 61 | thermal_heat | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.30/11.30 · after 11.35/11.35 |  |
| 62 | thermal_heat | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.30/11.30 · after 11.35/11.35 |  |
| 63 | thermal_heat | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 11.15/11.15 · after 11.35/11.35 |  |
| 64 | battery | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 28.00/28.00 |  |
| 65 | battery | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 28.00/28.00 |  |
| 66 | battery | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 67 | battery | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 68 | battery | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 28.00/28.00 |  |
| 69 | battery | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 28.00/28.00 |  |
| 70 | battery | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 15.12/15.12 · after 27.60/27.60 |  |
| 71 | fire | flat | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 23.50/23.50 · after 25.00/25.00 |  |
| 72 | fire | tiered | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 23.50/23.50 · after 25.00/25.00 |  |
| 73 | fire | time_of_use | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 74 | fire | demand | Every class | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before —/refused · after —/refused | DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them |
| 75 | fire | seasonal | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 23.50/23.50 · after 25.00/25.00 |  |
| 76 | fire | capacity | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 23.50/23.50 · after 25.00/25.00 |  |
| 77 | fire | percent_of_service | Every class | ok | ok | ok | ok | ok | ok | ok | ok | before 39.36/39.36 · after 76.80/76.80 |  |
| 78 | electric | flat | Commercial | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 79 | electric | flat | Residential | ok | ok | ok | ok | ok | ok | ok | ok | before 80.00/80.00 · after 80.00/80.00 |  |
| 80 | electric | time_of_use | Residential | ok | ok | ok | ok | ok | ok | ok | **FAIL** | before 80.00/80.01 · after 89.05/89.05 | DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling) |
| 81 | electric | demand | Commercial | ok | ok | ok | ok | ok | ok | ok | ok | before 197.25/197.25 · after 233.20/233.20 |  |
| 82 | electric | demand | Industrial | ok | ok | ok | ok | ok | ok | ok | ok | before 197.25/197.25 · after 233.20/233.20 |  |
| 83 | water | flat | Commercial | ok | ok | ok | ok | ok | ok | ok | ok | before 35.25/35.25 · after 61.50/61.50 |  |
| 84 | water | flat | Residential | ok | ok | ok | ok | ok | ok | ok | ok | before 35.25/35.25 · after 61.50/61.50 |  |
| 85 | water | tiered | Institutional | ok | ok | ok | ok | ok | ok | ok | ok | before 43.25/43.25 · after 76.11/76.11 |  |
| 86 | water | tiered | Residential | ok | ok | ok | ok | ok | ok | ok | ok | before 35.25/35.25 · after 65.81/65.81 |  |
| 87 | water | seasonal | Commercial | ok | ok | ok | ok | ok | ok | ok | ok | before 35.25/35.25 · after 61.50/61.50 |  |
| 88 | gas | flat | Agricultural | ok | ok | ok | ok | ok | ok | ok | ok | before 47.50/47.50 · after 61.50/61.50 |  |
| 89 | sewer | flat | Municipal | ok | ok | ok | ok | ok | ok | ok | ok | before 25.20/25.20 · after 33.00/33.00 |  |
| 90 | sewer | percent_of_service | Residential | ok | ok | ok | ok | ok | ok | ok | ok | before 17.40/17.40 · after 33.00/33.00 |  |
| 91 | trash | flat | Residential | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 92 | trash | tiered | Builder or developer | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 93 | trash | capacity | Commercial | ok | ok | ok | ok | ok | ok | ok | ok | before 25.00/25.00 · after 25.00/25.00 |  |
| 94 | storm_water | flat | Government | ok | ok | ok | ok | ok | ok | ok | ok | before 25.85/25.85 · after 28.25/28.25 |  |

| Check | ok | FAIL | n/a | of |
|---|---|---|---|---|
| Add | 94 | 0 | 0 | 94 |
| DB | 94 | 0 | 0 | 94 |
| Change the rate | 94 | 0 | 0 | 94 |
| Fix an error | 94 | 0 | 0 | 94 |
| History | 94 | 0 | 0 | 94 |
| One version to billing | 94 | 0 | 0 | 94 |
| Plan impact | 94 | 0 | 0 | 94 |
| Bill preview | 73 | 21 | 0 | 94 |

## The 71 drawings

Each `NN-name.built.png` sits beside `NN-name.reference.png` (copied from `05-prototype/rate-schedules-2026-10-01/images/`), photographed at 1440 wide and the content's full height, after the footer lane's one bottom bar (`DEF-RAT-8824`) and this lane's fixes. Figures in the drawings are illustrations (B14 rule 37); spacing, type and components are our UI standard's (rule 44); the PO moved every page button into one bottom bar (*differs — ruled*), and Edit stays a secondary button (CR-087 E1, *differs — ruled*). **Inspected** = the pair was opened and read side by side by this lane; *template* = the same screen template as an inspected pair of the same row, photographed in the same run and not opened one by one.

**Count: 62 match (the bottom bar and Edit's tier ruled), 9 differ. 28 pairs inspected one by one, 43 by template.**

| # | Drawing | Verdict | How | Inspected |
|---|---|---|---|---|
| 01 | List · all | matches | Columns, chips, counts, status pills, row icons as drawn; the explainer paragraph is gone (`DEF-RAT-8840`). Differs only as ruled (New rate schedule in the bottom bar) — and `DEF-RAT-8842`: the Retire icon is clipped at 1440 (fixed in the kit 2026-10-01, `3a135b4e8`; `08-qa/screens/table-width-2026-10-01/`) | yes |
| 02 | List · water | **differs** | A scheduled change is also written into the Effective cell as a boxed note (*Change scheduled — effective 11/01/2026*) beside the drawn *Scheduled* pill; kept for US-RAT-004 TC-3 | yes |
| 03 | List · sewer | **differs** | as 02 | yes |
| 04 | List · electric | **differs** | as 02 | template |
| 05 | List · trash | **differs** | as 02 | template |
| 06 | List · battery | **differs** | as 02 | template |
| 07 | List · no results | matches | *No schedule found.* under the drawn header row | yes |
| 08 | W-RES · Overview | matches | Kicker, pill, band, four tiles, Details and Billing rules as drawn; buttons in the bottom bar (ruled) | yes |
| 09 | W-RES · Rates | matches | *From* reads — for a base price that has always applied (backfilled 2000-01-01) | yes |
| 10 | W-RES · Plans | matches | Plan · Code · Customer class · Status · Units | yes |
| 11 | W-RES · Audit | matches | Version · Effective from/to · Filed as · What changed · By · Status; corrected row *Corrected*, as image 15 | yes |
| 12 | SEWER · Overview | matches | | template |
| 13 | SEWER · Rates | matches | *All sizes*, *One amount* | yes |
| 14 | SEWER · Plans | matches | | template |
| 15 | SEWER · Audit | matches | *v1 Corrected*, *v2 In force*, as drawn | yes |
| 16 | BATT · Overview | matches | | template |
| 17 | BATT · Rates | matches | Sizes read the tenant's names (5 kW, not BAT-5) | yes |
| 18 | BATT · Plans | matches | | template |
| 19 | BATT · Audit | matches | | template |
| 20 | E-TOU · Overview | matches | | template |
| 21 | E-TOU · Rates | matches | Window · Days · Starts · Ends · Register · Price | yes |
| 22 | E-TOU · Plans | matches | | template |
| 23 | E-TOU · Audit | matches | | template |
| 24 | E-DEM · Overview | matches | | template |
| 25 | E-DEM · Rates | matches | | template |
| 26 | E-DEM · Plans | matches | | template |
| 27 | E-DEM · Audit | matches | | template |
| 28 | W-SEAS · Overview | matches | | template |
| 29 | W-SEAS · Rates | matches | | template |
| 30 | W-SEAS · Plans | matches | | template |
| 31 | W-SEAS · Audit | matches | | template |
| 32 | TRASH · Overview | matches | | template |
| 33 | TRASH · Rates | matches | | template |
| 34 | TRASH · Plans | matches | | template |
| 35 | TRASH · Audit | matches | | template |
| 36 | SEW-PCT · Overview | matches | | template |
| 37 | SEW-PCT · Rates | matches | Of service · Percent, as drawn | yes |
| 38 | SEW-PCT · Plans | matches | | template |
| 39 | SEW-PCT · Audit | matches | | template |
| 40 | Add 1 · details | matches | Six fields in two rows of three and the aside; Cancel in the bottom bar (ruled) | yes |
| 41 | Add 1 · structure open | **differs** | A native dropdown cannot be photographed open: the field is shown focused. *Base only* is offered disabled with its reason, as drawn (checked in the DOM tests) | yes |
| 42 | Add 1 · code picker | **differs** | The picker lists the code alone (*BASE-W*), not *BASE-W · Water base charge*; every water code is offered, not only the class's | yes |
| 43 | Add 1 · errors | matches | *Add a name.*, *Pick a base charge code.* under their fields; the frame also repeats the first refusal under Continue | yes |
| 44 | Add 2 · flat | matches | | template |
| 45 | Add 2 · tiered | matches | Base rates per size with minimums, tier ladder, + Add row | yes |
| 46 | Add 2 · time of use | matches | After `DEF-RAT-8841`: Window, Days, times, Register and Price all readable; the selects clip their last letter at 1440, as the drawing clips its times | yes |
| 47 | Add 2 · demand | **differs** | Four columns, not five: there is no *Power factor below* threshold to type — the demand config stores a power-factor rate only, captured and not billed (BR-RAT-014) | yes |
| 48 | Add 2 · seasonal | matches | Season · Starts · Ends · Price, *Repeats every year.* | yes |
| 49 | Add 2 · capacity | matches | Asset reads *Cart / Dumpster*; size names clip in a narrow select | yes |
| 50 | Add 2 · percent | **differs** | The usage half is the existing percent editor (Usage/Charge, Percentage, Based on, Price per unit), not the drawn two-column table — wave B kept it because the table cannot carry BR-RAT-1030's basis | yes |
| 51 | Add 2 · unpriced size | matches | *Not priced* on the dumpster row and *1 of 1 not priced. Billed $0.00 with a warning.* | yes |
| 52 | Add 2 · every size used | matches | + Add row disabled, *Every size is used.* | yes |
| 53 | Add 3 · review flat | matches | | template |
| 54 | Add 3 · review tiered | matches | Schedule, Prices, When, Regulator filing; the usage table sits in its own panel under Prices | yes |
| 55 | Add 3 · review TOU | matches | | template |
| 56 | Add 3 · review demand | matches | | template |
| 57 | Add 3 · review seasonal | matches | | template |
| 58 | Add 3 · review capacity | matches | | template |
| 59 | Add 3 · review percent | matches | | template |
| 60 | Add 3 · date error | matches | *Pick a date.* | template |
| 61 | Add 3 · saved | matches | *New schedule created.* | template |
| 62 | Edit · change 1 | matches | After `DEF-RAT-8835` the Base charge code field reads BASE-W, as drawn (it read *Search codes* before) | yes |
| 63 | Edit · change 2 | matches | | template |
| 64 | Edit · change 3 | matches | | template |
| 65 | Edit · change reason error | matches | *Add what changed.* | template |
| 66 | Edit · change saved | matches | *… saved as new version.* | template |
| 67 | Edit · correct 1 | matches | | template |
| 68 | Edit · correct 2 | matches | | template |
| 69 | Edit · correct 3 | matches | | template |
| 70 | Edit · correct reason error | matches | *Add a reason.* | template |
| 71 | Edit · correct saved | matches | Aside *Version v1 (corrected)* after `DEF-RAT-8829`, as drawn | yes |
