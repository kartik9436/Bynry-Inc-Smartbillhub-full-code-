# CR-168-BRC10 · lane PARTS — images 35–42 beside the build (`2.503.0`; the photographs' footer reads v2.501.0, the number held before push)

Walked by `10-scripts/cr168_parts_after_walk.mjs` on PostgreSQL 16 (`sbh_wparts`: migrate + `seed_demo` +
`load_sample_data --tenant brazosbend`), Chromium at 1440, signed in as Dana. **22 of 22 checks passed.**
Every photograph below was opened and read before it is cited.

| Image | Drawing | Build | Same? | Photograph |
|---|---|---|---|---|
| 35 Parts | *↑ Import parts · + Add part* top right; Register / Issue log; search; ▦; PART # · DESCRIPTION · CATEGORY · UNIT · UNIT COST · STATUS; no row action, no filter | the same head and segments; **NAME** for DESCRIPTION (ruling 32) and *Search part #, name…*; **+ Filter** (Category · Unit · Status) beside the search; an ACTIONS column — pencil (edit) and × (retire) or ⏻ (reactivate); *Issue log* is live (no *"Arrives with parts on jobs."*) | Differs on purpose: ruling 32 renames; P3.8–P3.11 add what the drawing does not draw, in the kit's shapes (rule 44) | `35-parts-parts.png` |
| 35 · retire | not drawn | *Retire VLV-GT1?* · *Crews can no longer pick it. Past jobs keep it.* · *Cancel* / *Retire part ✓* on the danger tier | built from the kit (`ConfirmDialog`) | `35b-parts-retire-confirm.png` |
| 35 · filters | not drawn | Status · Inactive → VLV-GT1 alone, *Status: Inactive ×* chip; Category · Meters → MTR-E1P, MTR-W100, MTR-W34, MTR-W58 | kit `FilterBar` | `35c-parts-filter-inactive.png`, `35d-parts-filter-meters.png` |
| 35 · Issue log | not drawn | WHEN · PART # · NAME · QUANTITY · ISSUED TO · JOB · PURPOSE — *10/04/2026 06:12 · SEAL-01 · Tamper seal · -2 each · — · WO-0041 · Meter exchange* | kit `DataTable` | `35e-parts-issue-log.png` |
| 36 Add a part | Part number* · **Name*** · Category · Unit of measure* (*How you count it — each, metre, box.*) · Unit cost* (*In dollars, like 92.40.*) · *Cancel* / *Add part ✓* | the same, in that order, with those words | Matches | `36-parts-add-a-part.png` |
| 36 · duplicate | not drawn | `mtr-w34` refused under Part number: *MTR-W34 is already in the register.* (the part named, case ignored) | — | `36b-parts-add-a-part-duplicate.png` |
| 36 · edit | not drawn | *Edit a part*, the part's own values (cost `41.50`), *Save part ✓*; saved `43.75` → stored `43.7500` | the Add form, filled (rule 43) | `36c-parts-edit-a-part.png` |
| 37 refused | *This is required.* under Part number, Name, Unit of measure; *Unit cost must be a number.*; *Fix 4 fields to continue.* | the same four sentences and the count; no *String must contain…* or *Invalid* | Matches | `37-parts-add-a-part-refused.png` |
| 38 Extract | four source cards, drop zone with the file, *Download a sample CSV*, the Category hint, mapping template, loads into Parts, batch label, Insert new only / Insert & update, *…Every other row is created.* | the same; the Insert-new-only sentence ends *Every other row is created.* (no numbering clause); the build also prints the Part # hint above the Category hint | Matches (one extra hint line, the runner's own) | `38-parts-import-parts-extract.png` |
| 39 Transform | SAMPLE VALUE MTR-W34 · Water meter 3/4" positive displacement · Meters · each · 118.00; Rows forward **5** | the same five samples; Rows in 5 · Duplicates dropped 0 · Rows forward 5 | Matches | `39-parts-import-parts-transform.png` |
| 40 Validate | 5 · 3 · 2 · 0 · 3; *Every part needs a name.*; rejects row 4 MTR-W58, row 5 | 5 · 3 · 2 · 0 · 3; *Every part needs a name.*; KEY MTR-W58 and TAPE-XL; row 4 fix *Import it as Insert & update. Or take the row out.*; no *blank in all 5 rows* box | Matches; the row-4 fix uses image 42's dashed words at both stages (one row, one sentence) | `40-parts-import-parts-validate.png` |
| 41 Load | Will create 3 · updated 0 · rejected 2 · Parts; rollback point; approval; *Download the 2 rows that failed*; *Commit load ✓* | the same; **the register held 10 parts before and after the dry run** | Matches | `41-parts-import-parts-load.png` |
| 42 Result | LOADED 3 · REJECTED 2 · FLAGGED 0; KEY MTR-W58, TAPE-XL; *Import it as Insert & update. Or take the row out.*; *Add how it is counted — each, ft, roll.* | the same; **after the load MTR-W34 is *Meters*, GSKT-STD and SEAL-01 *Consumables*** (10 → 13 parts) | Matches | `42-parts-import-parts-result.png` |

**Not as drawn, and why (none put to the PO):** the second column and the search box say *Name*, not
*Description* (ruling 32 renamed the field); the filters, row actions, retire confirm and the Issue log's
table are not in the drawings and are required by P3.8–P3.11 — they are the kit's own controls (B14 rule 44).
Rule 37: the drawn prices (`$118.00`) are illustrations; the walk used the round-1 file's figures.

**Found on the walk, filed, not fixed here:** `DEF-MET-9614` — committing the same file to the same target a
second time answers HTTP 500 (the idempotency constraint at the run's final save) instead of a refusal. `DEF-SHL-9615` — a server
refusal stays under its field after the value is retyped, until the next press (the kit's `FormModal`);
image 36's photograph is therefore taken on a fresh form.
