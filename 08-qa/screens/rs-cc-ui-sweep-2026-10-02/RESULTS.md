# Rate schedules and charge codes — B14 UI sweep, 2026-10-02

PO, 2026-10-02: *"can you fix rate schedule and charge code ralted uI issues"*.

Every screen below was photographed at 1440 (`<NN>-<screen>.png`) and **measured at 1440 and
1280** by `07-frontend/e2e/DEF-RAT-9101-rs-cc-sweep.spec.ts`; the raw numbers are in
`metrics.json`. Seeded tenant `brazosbend` (`seed_demo`), Chromium, build 2.440.x + this lane.

What each screen was checked for: page head with actions top-right (B14 rule 2), the wizard
footer (rule 3), no database ids (rule 31), text budgets (rules 32/33), a 32px title (rule 40),
spacing and kit (rule 44), one table type, icon row actions, two button sizes, Retire in the
danger tier, clipped text, sideways scroll at 1440 and 1280, and dates and money printed one way.

**Measured on all 35 screens:** title 32px on every one; no database id on any; no clipped text;
no `01/01/2000` after the fixes; page buttons in two heights only (35px and 40px; 58px is the
step rail, 19–29px are row icons, chips and the pager); dates in one shape, `MM/DD/YYYY`.

## Results

| # | Screen | Found | Fixed / status |
|---|---|---|---|
| 01 | Rate schedules list | *New rate schedule* was in a bar under the table, off-screen on a long list | **Fixed** `DEF-RAT-9101`: top-right beside History; opens the 3-step Add wizard |
| 01 | Rate schedules list | A row of service buttons (All · Water · Sewer …) | **Fixed** `DEF-RAT-9103`: Service is a group inside + Filter; an active one is a removable tag |
| 01 | Rate schedules list | `BASE-W` broke at its hyphen; *In force* pill wrapped to two lines | **Fixed** `DEF-RAT-9110` |
| 01 | Rate schedules list | Table scrolled sideways inside its frame at 1280 (needed 1048px of 960px) | **Fixed** `DEF-RAT-9112`: below 1440, Sizes and Plans start behind the Columns picker; the table is 960px at 1280. 1440 unchanged (all eleven columns) |
| 02 | Rate schedules list, + Filter open | The open panel gave the page a sideways scroll at 1280 | **Fixed** with `DEF-RAT-9112`: it was riding on the over-wide table; re-measured with the panel open, nothing passes the right edge |
| 03 | Rate schedules list, service filter | Service shows as the usual removable tag | clean |
| 04 | Rate schedules list, no results | — | clean |
| 05–08 | Rate schedule View details: Overview, Rates, Plans, Audit | Duplicate · Edit · Retire were in a bottom bar | **Fixed** `DEF-RAT-9101`: page head, top-right, Retire danger, on all four tabs |
| 06, 09 | Rate schedule Rates tab | From read "—" for a base price carried over from 2000-01-01 | **Fixed** `DEF-RAT-9102`: From is the later of the price's start and the version's start (08/01/2026 on the seeded schedules) |
| 06 | Rate schedule Rates tab | Usage prices print 4 decimals (`$4.0000`, `$0.0850`) where hard rule 2 says money displays at 2 | **Not decided — would contradict a ruling either way** (the drawings price per unit at 4, e.g. `$4.4096`; hard rule 2 says display 2). For the PO |
| 05 | Rate schedule View details | Header pill said *Active*; the list said *In force* for the same state | **Fixed** `DEF-RAT-9117`: *In force* in all eleven catalogues (header, list and Status filter) |
| 10 | Add, step 1 | — | clean: footer Cancel \| Continue, full width |
| 11 | Add, step 1 errors | — | clean |
| 12 | Add, step 2 | — | clean: Cancel \| Back · Continue |
| 13 | Add, step 3 | — | clean: Cancel \| Save draft · Back · Create rate schedule |
| 14 | Edit, step 1 | Step 1 heading *This edit* repeated as the field label under it | **Open** (copy, rule 33) — noted, not changed |
| 15–16 | Edit, steps 2–3 | **Edit could not leave step 1** on a schedule priced from one base code per class (seeded *Residential Water*: BASE-W and BASE-W-COM) — *Pick a base charge code* | **Fixed** `DEF-RAT-9111`: no single code is demanded for a saved per-class schedule; photos 15 and 16 now show steps 2 and 3. Observation: step 3's Prices table lists the residential code's rows only |
| 20 | Charge codes list | *New charge code* already top-right | clean for placement |
| 20 | Charge codes list | Table scrolled sideways inside its frame at 1280 (needed 1089px of 960px); codes like `AFTER-HRS` break at the hyphen | **Fixed** `DEF-RAT-9112`: below 1440, Priced by and GL account start behind the Columns picker. The hyphen break stays (a no-wrap fix made 1440 scroll and was reverted) |
| 21 | Charge codes list, + Filter open | As 02 | **Fixed** with `DEF-RAT-9112` |
| 22 | Charge codes list, no results | — | clean |
| 23–33 | Charge code View details: base, plan and other codes, every tab | Duplicate · Edit · Retire already in the page head | clean for placement |
| 23, 26, 27, 30, 31, 33 | Charge code Overview and Audit | Printed **01/01/2000** as a real date for every seeded code | **Fixed** `DEF-RAT-9109` |
| 23–44 | Charge code View details and wizard | Content sat 16px further left and higher than every other Plans & Rates screen | **Fixed** `DEF-RAT-9114` (page padding) |
| 23 | Charge code View details | *Edit* was the red primary button here and a plain button on rate-schedule View details | **Fixed** `DEF-RAT-9116`: plain, per CR-087 E1 |
| 40–41 | Charge code Add, step 1 | Continue stays disabled until a kind is chosen, so there is no empty-error state to photograph | clean |
| 42–44 | Charge code Edit, steps 1–3 | Footer was split: Cancel far left, Save draft floating mid-page, Save change at the left column's edge | **Fixed** `DEF-RAT-9104`: Cancel \| Save draft & exit · Back · Save change, full width |
| 44 | Charge code Edit, summary | *Effective* read "— · no end" | **Fixed in part** `DEF-RAT-9104`: shows the in-force price's own start; a seeded code's only start is the 2000-01-01 carry-over, so it still reads "—" until a date is typed |

## Counts

- **35 screens** photographed and measured; re-measured after the second round, **all 35 clean at 1440 and 1280**
  (no sideways scroll, no clipped text, no ids, no 01/01/2000).
- **14 issues fixed** across 11 defects (`DEF-RAT-9101` list and details, `9102`, `9103`, `9104` footer and summary,
  `9109`, `9110`, `9111`, `9112` lists and filter panel, `9114`, `9116`, `9117`).
- **Left with the coordinator for the PO:** 4-decimal usage prices; the Work order footer against B14 rule 11;
  several values in one filter (`OQ-306`). One copy note (Edit step 1's repeated *This edit*) and the hyphen break
  in charge codes stay open.

Not photographed: the error state of a list (it needs the server to fail; DOM tests cover it), and the saved states
(they write data; the wave-B shots `08-qa/screens/rate-schedules-waveB-2026-10-01/61-*`, `66-*`, `71-*` show them).
