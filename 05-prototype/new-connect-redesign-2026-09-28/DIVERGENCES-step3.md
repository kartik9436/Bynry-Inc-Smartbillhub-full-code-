# Step 3 · Units — the built screen beside its three drawings

**Photographs:** `built-2026-09-29/step3-units-1440.png` · `step3a-add-row-1440.png` ·
`step3b-add-work-order-1440.png` · `step3-units-1280.png`, taken in Chromium against a
booted stack by `10-scripts/cr150_step3_units_walkthrough.mjs` (11 observations, 0
failures). **Nothing here is silent**: every difference between the drawing and the
built screen is written down, with why.

B14 rule 44 decides most of them — *the drawing says WHAT is on the screen and how it
is arranged; our UI standard says HOW it is built*, and the standard wins every time.
B14 rule 37 decides the rest — every figure on a drawing is an illustration.

| # | The drawing | The built screen, and why |
|---|---|---|
| 1 | `step3a-add-row.png` and `step3b-add-work-order.png` are titled *"…after Add row"* and were commissioned as *"screens"* | **NEITHER IS A DIALOG**, and both drawings say so themselves — *"Nothing opens on top of the screen"* and *"Also in place, at the bottom of the table."* Decision log answer 13(e) rules it. Both add a row in place, and the walk asserts `role="dialog"` is absent after each. **BUILT AS DRAWN.** |
| 2 | Both add-screens ring the new row in red | **NOT BUILT.** Both frames are explainers titled *"The new row"* and the outline points at the row the prose is about; nothing says the product draws it. `TableArray`'s own exception E1 records the same for the kit. |
| 3 | A **`Qty`** column, badged NEW | **NOT BUILT.** `OQ-CUS-12770` is OPEN and decides whether a charge's quantity is typed or counted; **it multiplies a price on a real invoice**, and `CR-150-BRC09` §5 forbids building it until the PO rules. The walk asserts its ABSENCE, so the day it is built somebody has to come back here. |
| 4 | Prose under *Apply to all*, under the table, the *Occupancy options: …* line, and the *Filled in for you / Waiting on you* pair | **NOT BUILT.** Every one is RATIONALE, which B14 rule 33 gives **zero words on screen** and says is removed rather than shortened. *"Required before Continue. Rows stay editable."* is an INSTRUCTION at six words a sentence and **is** built. |
| 5 | Units 2 and 15 drawn folded, unit 1 open | **BUILT AS DRAWN**: the first group is open and the rest are folded, each one press from open. No row is unreachable. |
| 6 | Column headings in mixed case — *Unit · Kind · Service …* | Rendered in **small caps**, which is the kit's table header (B14). The WORDS and their ORDER are the PO's, exactly; the casing is the standard's, and rule 44 gives it the win. |
| 7 | Every figure — 4 of 4, 12, 3, 4, `Water 1"`, `10/15/2026`, units 1, 2, 15, `Jonas Janssen` | **ILLUSTRATIONS** (rule 37). Every count on the built screen is computed from the rows in front of the person. The photograph shows `0 of 2`, `0`, `0`, `0 will be written` because the walk starts a fresh build. |
| 8 | The stepper runs **1–5** | The photograph shows **eight**. The step list is `newConnectShared.NEW_CONNECT_STEPS` and belongs to the MODEL lane, which is folding it; step 3 is index 3 and id `units` either way. **Not this lane's to change, and named here rather than left to be noticed.** |
| 9 | A unit row with no service | Shows **one empty row, ready to type**. `EditableTable` draws its groups only while the row list is non-empty, so without it a build with no services chosen would render the table's empty state and **every unit would disappear**, taking the duplicate-label refusal (`DEF-MET-6111`) with it. **The first `+ Add row` on such a unit turns that placeholder into the typed row rather than leaving two empty rows** — the walk asserts the count over two presses and says so. |
| 10 | The `Completes` tick | Rendered and **disabled with its reason** (`BR-SHL-025`), because `BR-WRK-013` makes the flag the template's own — on gas the completing job is the light-up and never the meter set. The drawn control is kept; what is refused is a power the drawing could be read as offering. |
| 11 | *Applies to* offers whole build · one unit · one service point | **All three are built.** It decides which GROUP the row sits in and nothing else: `commitPlanOf` sends `{template_id, template_version}` per order and no unit, so writing one into the payload would be a value the commit never reads. |

## One defect this lane shipped and fixed, found here and nowhere else

The common selection **printed its heading twice**, one panel inside another with two
borders, because the table was wrapped in `TableArray` — the kit's FRAME — while
already sitting inside a panel that had the heading. Twenty-three DOM cases, a green
`tsc` and clean eslint all passed over it. It now composes `EditableTable`, the kit's
TABLE, directly. That is hard-won law 6 in one line: no gate reads rendered output.

## The absorbed-field audit

`step3-absorbed-field-audit.md`, beside this file — 20 fields from *Map services* and
13 from *Work orders*, each with where it now lives, and the two that are deliberately
not built said plainly.
