# Walk — solar bills the sum of installed kW (DEF-RAT-10220, DEF-BIL-10221), 2026-10-17

Private copy `smartbillhub_solarkw` (from `smartbillhub`, dropped afterwards), API on 8031, SPA on 8111
(`vite build --mode compose`). 8000/8080 untouched.

## The PO's setup, reproduced
Brazos Bend: Solar switched on (capacity basis); size class **SOL-P47.84 · Solar Panal 47.84** added through
the Settings lookup service; schedule **Municipal Solar PV**, FLAT, **$14.00 per `KW`** (the tenant's unit list
already holds `kW`, unique ignoring case, so `KW` was written on the schedule itself — the spelling the PO's draft
printed); two PV assets on Unit 1 of a new premises — **PV-00001 (SOL-P47.84)** and **PV-00002 (SOL-P10)**;
account **AC-2026-00057**, one-time bill (Interim) for 09/01–09/30/2026.

## Before — base build `9f45ba8dc`
| Screen | Shows |
|---|---|
| `before-one-time-draft.png` | **$28.00** — the panels COUNTED: 2 × $14.00 |

## After — this branch (migration `tenancy/0064` applied to the copy)
| Step | Screenshot | Shows |
|---|---|---|
| Back-fill | (SQL) | SOL-P10 **10.0000**, BAT-20 **20.0000**, SW-APT **6.0000**; W-2 and the tenant's SOL-P47.84 stay blank |
| No capacity on the tenant size | `after-nocap-one-time-step2.png` | refused: **"PV-00001: size has no capacity."** (`billing.check.capacityUnknownAssets`, `installed_capacity_undetermined`) |
| Settings list | `settings-1-list-capacity-column.png` | a **Capacity** column; SOL-P47.84 reads **—** |
| Edit | `settings-2-edit-dialog-capacity-field.png` | captured the instant the dialog opened, before `/settings/services` answered: the service picker reads *None* and no capacity field yet (the picker's existing behaviour; the field follows the service). `settings-3` is the same dialog a moment later — **Solar**, **Capacity (kW)*** |
| Blank refused | `settings-3-blank-capacity-refused.png` | **"Enter the capacity in kW."** |
| Saved | `settings-4-saved-47-84-kw.png` | row reads **47.84 kW** |
| One-time bill, services + rates | `after-cap-one-time-step2.png` | **Billed · 57.84 kW**, *2 assets · PV-00001, PV-00002*, $14.00 per KW, **$809.76** |
| Review | `after-cap-one-time-step3-review.png` | line **57.84 kW × $14.00 = $809.76**, total due **$809.76** |
| Rate form | `rateform-flat-per-kw-warning.png` | Solar · kW · Flat → **"Priced per kW. Consider Capacity."**; gone on Capacity |

## Found by the walk — DEF-BIL-10221
The first AFTER pass priced **$809.76** correctly, but the Services row above it read **"2 KW · PV-00001,
PV-00002"** and **"Billed · 2 KW"** — the asset count labelled with the price unit. Filed, red-first tests
(backend `test_tc12…`, frontend `servicesInstalled.test.tsx`), fixed, re-walked: the screenshot above is the
re-walk (the first pass's screenshot was overwritten by it).

## Noticed, not changed
The list's *Used by* reads **0** for SOL-P47.84 although PV-00001 carries it — the size-class handler has no live used-by seam (pre-existing; not this defect).

## Not walked
The bill-run Check pane and the move-out draft: both serve the same refusal fields
(`message_key`/`message_params`) the one-time bill showed; covered by the backend tests, not by a click.
