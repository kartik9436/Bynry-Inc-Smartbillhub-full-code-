# CR-176-BRC10 — Add units redesign, and the Units list's selection bar only once a unit is ticked

**Raised:** 2026-10-09 by the Product Owner, in chat (decision log row of 2026-10-09 that starts *"PO GO — BUILD THE ADD-UNITS REDESIGN"*).
**Status:** **BUILT — 2.564.0, 2026-10-09 (lane ADD-UNITS); rounds A `56f910789`, B `6ba820cfb`, C `03c46c194`, D the commit that closes `DEF-MET-10035`.**
**Branch:** `claude/charming-pascal-k7i2lr` (`BRC10`). `10-scripts/allocate.py cr` answered **176** against the remote at tip `42970b1b4`; `--verify 176` reported it free on every branch.
**Defect it carries:** `DEF-MET-10035` (four bugs on Add units, one on the Units list).
**Classification (`13-change-process.md` §1, `22-product-maintenance-process.md`):** a live screen redrawn end to end, so **MAINTENANCE** with Build's drawing step. The four reported bugs are DEFECTS; the redesign and the six rules are the PO's CHANGE.

## 0 · What arrived, in the requester's words (verbatim)

| | The PO, verbatim |
|---|---|
| The go | *"yes to all 3 - go for add units build - complet all these"* |
| Layout, row of three | *"Unit numbers - make it drop down and all 3 in 1 line"* |
| Layout, two or three rows | *"can you manage this in 2 or 3 rows"* |

The three questions it answers, each yes: (1) a unit's services are the building's, all ticked to start; (2) *Units* / *A common area* is a choice at the top; (3) a *These units* card on the right.

## 1 · The drawing

Eleven images taken from the approved mock-up at 1440 wide, committed under
`05-prototype/add-units-redesign-2026-10-09/images/` (listed in that folder's `IMAGES.txt`),
with the mock-up itself beside them (`add-units-redesign.html`; its *"What this design fixes"*
table, 19 rows, is the list of text and behaviour changes). The example data (101 Silver Creek Rd,
U-00013, plan names) is an illustration (B14 rule 37); the screen reads the real lookups.

## 2 · What is reversed, and what is NOT (step 2)

- **CR-089 U2's *"Or add a common area instead"* dropdown at the bottom** → a choice at the top (`BR-MET-1200`).
- **CR-089 E4's plain-case label `{seq}`** → `Unit {seq}` in each language's own word (decision log 2026-10-09, judgment 2).
- **`DEF-TEN-5840`'s bar at zero** → the bar only once a unit is ticked; *Select all {n}* comes with the first tick (judgment 1).
- **NOT reversed:** `Floor` is free text (decision log 2026-09-10); `Floor area` is on the add form (PO 2026-09-19); the plan picker shows every plan with a search (PO 2026-09-10); `← Units` in the head and `Cancel` in the footer (PO 2026-09-19); nothing written until the press, all or none; `BR-MET-1165` (numbers previewed, never held); the server's 3,000-per-run check (`BR-MET-005/038`, unchanged — no new cap, `NFR-5`). No frozen B4/B5 figure is touched; no money path.

## 3 · Reproduced first (maintenance step 1), on a local PostgreSQL 16 copy of the demo utility

At `88 Pine Vista` (Unit 1, Unit 2 on file), the shipped screen opened with *Start numbering at* **1** under *"Unit 1, Unit 2 are taken."*, *"Units to create: 0"* beside an empty *How many*, and the building card's owner as a bare *"Not recorded"*; the Units list read *"0 unit(s) selected"* with nothing ticked. *How many* in red on a valid value did NOT reproduce (no invalid mark on load or after typing 1). Mounted files: `07-frontend/src/features/metering/AddUnitsWizard.tsx` (route `premises/units/new`, `App.tsx`) and `UnitsListPage.tsx`.

**Blast radius.** `addUnitsRequest`, `BuildingStep`, `ReviewStep` and `resolvedUnitServices` had no consumer outside this file and its tests. `patternTotal` / `PATTERN_UNIT_CAP` are no longer imported from `AddPremisesWizard.tsx` (the other lane's file; nothing there changes). `units_pattern` staging is also used by `AddPremisesWizard`'s pattern mode: a label already on file is now a refusal naming it (with the next free start) instead of a row marked `duplicate_label`. `ServiceTags` is no longer used here (still used elsewhere). `CheckDropdown` and `Disclosure` each gain an opt-in mode (`every`, `panel`); every existing caller renders as before.

## 4 · Built

**Round A · server (commit `56f910789`).**
1. `GET /premises/{id}/units/next-free?count=&floors=&label_pattern=&start=` — the first start from which the whole run is free, and the run's taken labels for a given start (`BR-MET-1196`).
2. Staging a run that hits a label on file is refused naming the labels and the next free start (`metering.import.pattern_labels_taken`); one read of the taken set replaces one `exists()` per generated row.
3. The building read (`lends`) carries the master account's number and name (two batched statements, no ledger read).
4. A service the building does not offer is refused at staging, by name (`BR-MET-1198`).
5. A common-area run of more than one unit is refused (`BR-MET-1200`).
6. The premises search also matches the utility's reference and the City parcel.

**Round B · screen (commit `6ba820cfb`).** `AddUnitsWizard.tsx` rewritten to the drawing: *Building* (search · card · *Use this building* / *✓ Selected* / *Change building*; services dropdown, all ticked, *"From the building."*), *What to add* (*Units* / *A common area*; two rows of three), *Names & numbers* and *Plan & start* as closed sections with their state, *These units* on the right, a grouped Review with *Edit* on every row, *This will create*, one line *"Creates 3 units at …"* and *Create 3 units* / *Create common area*. New reusable component `components/PickBySearch.tsx` (B14 rule 43) — the same search-then-*Use this* shape as Owner on Add a premise, for that lane to converge on. Units list: the bar only once a unit is ticked. 53 strings in all eleven catalogues; 63 dead keys retired through `10-scripts/i18n_fanin.py`.

**Round C · proof (commit `03c46c194`).** See §5.

**Round D · records (the commit that closes `DEF-MET-10035` at 2.564.0).** Rules `BR-MET-1196`–`1201` in `04-docs/05-modules/04-metering/02-business-rules.md`; this record; `CHANGELOG.md`; version `2.564.0` (`allocate.py version --bump change`, verified free at push); `DEF-MET-10035` closed.

## 5 · Proof

- **Server:** `tests/test_cr176_add_units_redesign.py` — 12 cases; **9 red on the old code** (`AttributeError: no next_free_seq_start`, `DID NOT RAISE`, `None == 'Bramble Property Group'`), all green after; with `test_cr089_u2_add_units_details.py` **17 passed on PostgreSQL 16**.
- **Screen:** `AddUnitsRedesign.dom.test.tsx` (8, under the real route with a fetch fake) — **7 red on the old screen**, green after; `AddUnitsFrame.test.tsx` rewritten (29). `UnitsPage.test.tsx` and `UnitsMissingServicesFilter.dom.test.tsx` updated for the bar.
- **Browser:** `10-scripts/cr176_add_units_walkthrough.mjs` on a local stack (local API, local PostgreSQL 16, the seeded demo utility; every request to `127.0.0.1` but the webfont) — 32 checks, all pass; with `CREATE=1` three units were created at 88 Pine Vista as *Unit 3–5*, `U-00001`–`U-00003`, both services each — exactly what Review and the button said.

## 5b · Open, not this lane

- `DEF-MET-10036` — the legacy premises CSV commit (`importers.commit`, kind `premises_csv`) raises `AttributeError` (`create_premises` has no `__wrapped__`); `test_us_met_004_tc1`/`tc7` were red before this change.
- `DEF-MET-10037` — `metering.wizard.pattern.floors` reads as a floor SURFACE in fr-FR, it-IT, ja-JP (the premises wizard's key; Add units now reads its own).
- `components/PickBySearch.tsx` is built to be the shared search-then-*Use this* control; Owner on Add a premise (`CR-177-BRC10`) can converge onto it.

## 6 · Rollback

Redeploy the build before this one. The screen returns to the old wizard; units created meanwhile are ordinary units. The next-free endpoint is a read and goes with the build.
