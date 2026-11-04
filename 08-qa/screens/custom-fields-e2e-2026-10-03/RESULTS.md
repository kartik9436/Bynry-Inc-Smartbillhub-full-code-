# Custom fields — the one end-to-end walk (2026-10-03)

**What it is.** The PO's instruction of 2026-10-02 (*"we ahve to do it"*): one utility sets up a field on every
record type through Settings, then uses every field in the order a utility lives; a second utility must see none
of it (*"you ahve to ensure utility isolation - we dont want these field to appear on other utility screens"*);
and the SEU mapping is tried as a third, TEST-ONLY utility (*"use this only for testing purpose dont set it
up"* — created at run time in the scratch database through Settings, never seeded, never a fixture).

**How.** `10-scripts/cf_e2e_walk.mjs` (+ its phase modules `cf_e2e_walk_*.mjs`), Chromium against a real API and
PostgreSQL 16 (`seed_demo` + `load_sample_data --tenant brazosbend` + `seed_portal_demo` + a scratch provisioning
of `seu-test`), front end `vite build --mode wolocal`, build **2.467.5** (which includes this lane's 2.467.3).
Tables below are rendered from the walk's own `results.json` by `10-scripts/cf_e2e_walk_report.mjs`, never
retyped. Screenshots `cfe2e_p<phase>_<step>.png` in the lane scratchpad; every one checked non-blank by size,
and a sample of every phase opened by eye.

| Utility | Role |
|---|---|
| A — Brazos Bend | one field on each of the 14 record types (+ a "Don't ask" field), every type used: Text, Number, Date, Yes/No, Pick one, Pick several |
| B — Pine Hill | the isolation side; holds its OWN `roof_material` (options Clay, Thatch) for the same-name case |
| C — SEU test | the PO's 13 fields, exactly as defined (labels, types, options with their punctuation, help text, none required) |

### Utility A (Brazos Bend) — one field per record type

| Record type | set up | typed | shown | imported | off/on | isolation |
|---|---|---|---|---|---|---|
| accounts | PASS | PASS | PASS | **FAIL** | — | PASS |
| customers | PASS | PASS | PASS | — | — | PASS |
| contacts | PASS | PASS | PASS | — | — | PASS |
| addresses | PASS | PASS | PASS | — | — | PASS |
| service_agreements | PASS | PASS | PASS | — | — | PASS |
| premises | PASS | PASS | PASS | PASS | PASS | PASS |
| units | PASS | PASS | PASS | PASS | — | PASS |
| service_points | PASS | PASS | PASS | — | — | PASS |
| assets | PASS | PASS | PASS | PASS | — | PASS |
| work_orders | PASS | PASS | PASS | — | — | PASS |
| meter_reads | PASS | PASS | PASS | PASS | — | PASS |
| routes | PASS | PASS | PASS | — | — | PASS |
| areas | PASS | PASS | PASS | — | — | PASS |
| payments | PASS | PASS | PASS | — | — | PASS |
| service_request | — | PASS | PASS | — | — | PASS |
| portal | — | PASS | PASS | — | — | PASS |

### Isolation (must pass) — utility B (Pine Hill) against A and SEU

| Record type | screens | API | writes | direct reads | same-name | DB | settings rules |
|---|---|---|---|---|---|---|---|
| accounts | PASS | PASS | PASS | PASS | PASS | PASS | — |
| customers | PASS | PASS | PASS | PASS | PASS | PASS | — |
| contacts | PASS | PASS | PASS | PASS | PASS | PASS | — |
| addresses | PASS | PASS | PASS | PASS | PASS | PASS | — |
| service_agreements | PASS | PASS | — | PASS | PASS | PASS | — |
| premises | PASS | PASS | PASS | PASS | PASS | PASS | — |
| units | PASS | PASS | PASS | PASS | PASS | PASS | — |
| service_points | PASS | PASS | PASS | PASS | PASS | PASS | — |
| assets | PASS | PASS | PASS | PASS | PASS | PASS | — |
| work_orders | PASS | PASS | PASS | PASS | PASS | PASS | — |
| meter_reads | PASS | PASS | PASS | PASS | PASS | PASS | — |
| routes | PASS | PASS | PASS | PASS | PASS | PASS | — |
| areas | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| payments | PASS | PASS | PASS | PASS | PASS | PASS | — |
| service_request | PASS | PASS | PASS | PASS | PASS | PASS | — |
| portal | PASS | PASS | PASS | PASS | PASS | PASS | — |

### Settings rules

| Rule · utility | pass |
|---|---|
| brazosbend · 11th refused | PASS |
| brazosbend · off frees a slot | PASS |
| brazosbend · no delete | PASS |
| brazosbend · key not renamed | PASS |
| brazosbend · view-only warns | PASS |
| seu-test · 10th accepted, 11th refused | PASS |
| pine-hill · 11th refused | PASS |
| pine-hill · off frees a slot | PASS |
| pine-hill · no delete | PASS |
| pine-hill · key not renamed | PASS |
| pine-hill · view-only warns | PASS |

### SEU test (13 fields, PO's own definitions)

| Field | set up | route 1 · clerk | New Connection step | edit screen | route 2 · portal | Staff New Request | copied on approval | view · Account detail / Premise page | view · Request detail |
|---|---|---|---|---|---|---|---|---|---|
| Name on DTE Bill | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DTE Account Number | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DTE Meter Number | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Budgetwise Enrolled | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Main Electric Panel Location | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Roof Age | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Number of Stories | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Roof Material | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Roof Shading | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Generator on Site | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Generator Model | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| EV Charged on Site | PASS | **FAIL** | PASS | PASS | PASS | **FAIL** | **FAIL** | PASS | PASS |
| Appliances | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

### Bills

| Rule | Settings | stamp | preview | code |
|---|---|---|---|---|
| Safe to print | PASS | PASS | — | — |
| never a total | — | — | — | PASS |

**824 checks, 819 passed, 5 failed.**

| Failed check | Detail |
|---|---|
| p5 · the accounts import's MAPS TO list offers Contract ref | {"target":"accounts","columns":[{"target":"unit_ref","label":"Unit","kind":"unit_ref","required":true,"transforms":[]},{"target":"account_no","label":"Account # (your own)","kind":"text","required":tr |
| p9 · FINDING · New Connection step 2 holds a blank required Roof Material | ← Accounts NEW CONNECT The units Step 3 of 5 · Units 1 Customer 2 Premise 3 Units 4 Charges 5 Review SERVICES HERE 1 of 2 SERVICE POINTS 0 METERS TO FIT 0 WORK ORDERS 0 will be written Common selectio |
| p18 · SEU route 1: EV Charged on Site stored exactly as typed | undefined vs false |
| p20 · SEU New Request holds EV Charged on Site exactly |  |
| p20 · SEU seu_request: the property holds EV Charged on Site exactly as entered | undefined vs false |

### What the matrix cells mean

* **typed** — the field draws on every screen its placement names, the answer saves, a blank REQUIRED answer is
  refused on that screen with the rest of the form kept, and a required field never blocks a screen that does not
  show it. **shown** — every read-only place (detail page, list column, Request detail). **imported** — the import
  column (premises, units, assets, readings, accounts). **off/on** — switched off it leaves every input screen and
  the stored answer stays; switched on it returns.
* **Isolation** — *screens*: 37 of B's screens and dialogs drawn and their text searched for every one of A's and
  SEU's labels, keys and answers, each screenshot `cfe2e_p16_B_*`; *API*: 37 of B's reads (definitions, slots, the
  registry per record type, every record list/detail, import mappings, the three sample CSVs, the readings
  template, the anonymous portal form) searched as raw JSON, with `custom_data` blobs and registry rows parsed for
  keys; *writes*: B posting A's keys on every create/edit door (premises, unit, account, contact, mailing, customer,
  asset, route, area, work order, payment, reading batch, A's own Add Premises payload replayed, import mapping, New
  Request, portal) refused 422 and nothing stored (read back from the database); *direct reads*: B asking for
  nine of A's records by id answers 404 at B's address and 403/404 at A's; *same name*: B's own `roof_material`
  (Clay, Thatch), A's (Metal, Tile, Shingle) and SEU's (8 options) each see only their own options and answers;
  *DB*: `FORCE ROW LEVEL SECURITY` on all 18 tables holding definitions or answers, and as `sbh_rls_probe`
  (NOSUPERUSER NOBYPASSRLS) with `app.tenant_id` = B **0** of A's rows are visible in every one — while the same
  query with `app.tenant_id` = A sees every one of A's rows, so the zero is not a probe that sees nothing.
* `service_agreements · writes` is "—": no door writes an agreement's answers on its own; they ride New Account
  and Change plan, whose account-level doors are covered under *accounts*.
* **Bills · preview** is "—" on purpose: the one-time bill preview refuses every seeded account on this database
  (`billing.oneTime.err.noBillingCycle` / `nothingPriced`), and a refused preview proves nothing either way, so it
  is recorded and not counted. "Never a total" rests on the code check (no rating, ledger, allocation or billing
  file reads `custom_data` except the one stamp module, which returns text only) and on the reading quantity being
  identical with and without its answer (phase 11).
* The PostgreSQL suites, run under `config.settings.pgtest`: the tenant-isolation suite (RLS half under
  `sbh_rls_probe`) and every custom-field suite — **215 passed, 1 failed, 1 skipped**; the one failure is a stale
  test from before this lane (below).

### SEU — wording and behaviour

| Check | Result |
|---|---|
| All 13 set up through Settings → Custom fields → + Add custom field, then Placement | PASS — keys derived as expected (`name_on_dte_bill` … `appliances`) |
| Option lists, in the given order, exact wording ("0–5", "Light (under 25%)", "Flat / membrane", "Don't know", "None of these") | PASS on Settings, Add Premises, Edit premise, New Connection step 2, Staff New Request and the portal; nothing changed or truncated |
| Help text ("As printed on DTE bill", "From your DTE bill" ×2, "Years since last replaced", "Only if you have one", "Tick all that apply") under its box | PASS on staff screens and on the portal |
| Premises at 9 active: a 10th accepted, an 11th refused on screen | PASS |
| Multi-select keeps several ticks including "None of these"; the tenant's own option order is kept | PASS |
| Yes/No shows as a clear Yes / No on view screens | PASS when answered; a **No** cannot be typed by a clerk (see DEF-SHL-9240) |
| Route 2, first-time applicant at a NEW address: portal → Approve as New connection → the build in New Connection → Create → the property holds all 9; the move-in → the new account holds all 4 | PASS (DEF-CUS-9211, fixed in 2.467.5 by another lane, re-proved here) |
| Route 3, first-time applicant at an address on file: Staff New Request → Request detail → Approve as move-in → the property holds the 9, the account the move-in opens holds the 4 | PASS except EV Charged on Site = No (DEF-SHL-9240) |

### Defects found by this walk

| Defect | Where | What a user saw | Status |
|---|---|---|---|
| DEF-CUS-9235 | New Account | A required own field (Contract ref) left blank: Continue let the clerk on; Create failed with "Check the highlighted fields" and nothing was highlighted | **Fixed in 2.467.3** — the step now holds and says "Fill in: Contract ref." |
| DEF-TEN-9234 | Settings → Custom fields → Edit | No "Safe to print" switch — no field could ever be put on a bill from the screen | **Fixed in 2.467.3** — the switch, off by default, Edit only |
| DEF-MET-9233 | Premises / units / asset import → "Download a sample CSV" | The sample had no column for the utility's own fields (the mapping offered them) | **Fixed in 2.467.3** — one column per active field, label header, empty cell; still recognised as the standard template |
| DEF-MET-9239 | Accounts import | No column for Accounts (or Customer/Contacts) fields, though the PO named accounts among the imports | **Fixed in 2.467.15** — one column per active Accounts field: on the MAPS TO list, in the sample, judged per row in words, written on create, merged on update (phase 5 re-run: 17 passed) |
| DEF-SHL-9240 | Every staff screen with a Yes/No field | A single tick box: an untouched box saves nothing, so "No" cannot be recorded, the view shows a blank, and a New Request "No" never reaches the property | **Fixed in 2.467.13** — a Yes / No pick with nothing chosen, as on the portal (coordinator decision, B14 rule 44); phases 0, 2, 7, 18–20 re-run: 406 passed, 0 failed |
| DEF-CUS-9242 | New Connection step 2 | A blank required premises field (Roof Material) lets Continue through to Units, nothing named | **Open — reported, not fixed**: New Connection step files are being edited by two other lanes |
| (DEF-CUS-9211) | Approve for a first-time applicant | Account / customer / new-property answers stayed "waiting" on the request for ever | Fixed in 2.467.5 by another lane while this walk ran; this walk's routes 2 and 3 re-prove it |

### Failures this lane did not cause (dated)

| Red | Since | Note |
|---|---|---|
| `test_cr161_w4_custom_fields.py::test_w4__each_record_type_offers_the_pos_screens_and_no_invented_page` | 2026-10-02 22:19, `d8d753d76` (W6 added the customers New Request / Request detail / portal slots ten minutes after the test's last edit, `cd5d27f4f`) | the test's expected slot list is stale; red on SQLite and PostgreSQL |
| `test_cr028_mapping_templates.py` (2 cases: 8 templates where 7 expected) | 2026-09-22, `c8bce7c8a` (an eighth import target, payments) — the test was last edited 2026-09-07 | red at the tip before this lane's change (checked by running the tip's `import_runs.py`) |
| `test_def962_def963_assets_template.py::test_def935__a_service_with_no_unit_on_file_is_REJECTED_AT_STAGE_3` | red at tip `3ffa094e0` before this lane's change | the row's problem now reads "M-4001 is not a number this utility has issued" where "sewer" is expected |
| `manage.py seed_portal_demo` stops at the end with `VAL-003 customers.deposit.planAsksNone` | the refusal came with `39d6ee638` (2.348.0) | both portal utilities and their sample data were planted before it stopped; the walk did not need the rest |
| One-time bill preview refuses every seeded Brazos Bend account (`noBillingCycle` or `nothingPriced`) | not dated by this lane | observed only; it is why the bill "preview" cell is "—" |

### Known gap, not failed

Exports and search do not carry custom fields yet (agreed as not built; not walked).
