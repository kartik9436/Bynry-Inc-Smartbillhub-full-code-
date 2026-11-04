# CR-161-BRC10 — Tenant custom fields become a complete platform capability: every ruled-in record type, every input route, every view screen

**Raised:** 2026-10-02, by the Product Owner, in chat. The ruling is the decision-log row
dated 2026-10-02 headed *"TENANT CUSTOM FIELDS BECOME A COMPLETE PLATFORM CAPABILITY …"*
(commit `aa4d30f8b`). It is quoted below, not paraphrased, and nothing in it is put back to
the PO (hard-won law 13) — including the approval-conflict question, which was minted and
answered in the same turn (R5, option C).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed for this branch by `CR-156-BRC10`
in `12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **161**
against the remote and `--verify 161` reported it free on every branch.
**Classification:** a **CHANGE** (`13-change-process.md` §1) for the programme — the product
did exactly what EP-TEN-09 agreed (eight record types, a fixed slot list) and the agreement
moved to sixteen record types and every route. **Wave W1 inside it is MAINTENANCE and every
W1 item is filed as a DEFECT** (`22-product-maintenance-process.md`): a System Admin can
define and place a field today, and Settings says things about it that are not true.

## 0 · What arrived, in the requester's words

> **R1** *"we will need all objects/tables and we need to make it available and wire it correctly"*

> **R2** *"so dont add on these - Plans / rate schedules … Books (ledger / journal entries) … Invoices"*

> **R3** (defaults after the exclusions, put to the PO and not objected to — Payments IN as
> capture-at-entry only; Readings, Work orders, Routes, Areas, Customers, Service requests IN):
> *"Out: the chart of accounts. - dont inlcude charts of acocunts"*

> **R4** *"dont we need input data mapping on which screen the data will be inputted"*

> **R5** put as *"When a service request is approved, the property already has 'Roof
> Material = Metal', but the request says 'Tile'. What happens?"* with A keep / B overwrite /
> C show both — PO: *"C · Show both and let the clerk pick when approving."* and, in the PO's
> own gap note, *"keep the existing value and show both side by side on the review page; the
> clerk picks"*.

> **R6** the agreed design, presented by the PO as four tables and adopted verbatim — copied
> in full below.

### R6 · Part 1 — Today vs. after the work
| # | Record type (Settings → "Applies to") | Has storage today | Server saves answers today | Screen shows input today | Works end to end today | After the work | Round | Kind of work |
|---|---|---|---|---|---|---|---|---|
| 1 | Accounts | ✅ | ✅ | ✅ | ✅ | ✅ + Account detail becomes editable | W1, W3 | Fix |
| 2 | Customer (person / company) | ✅ | ❌ | ❌ | ❌ Not offered in Settings | ✅ | W4 | New |
| 3 | Contacts | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 4 | Addresses (mailing) | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 5 | Service agreements | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 6 | Premises | ✅ | ❌ (import only) | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 7 | Units | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 8 | Service points | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 9 | Assets (meters, sub-meters, devices) | ✅ | ❌ | ❌ | ❌ | ✅ | W2, W3 | Fix |
| 10 | Work orders | ❌ | ❌ | ❌ | ❌ Not offered | ✅ | W4 | New |
| 11 | Readings | ❌ | ❌ | ❌ | ❌ Not offered | ✅ incl. reading import | W4 | New |
| 12 | Routes | ❌ | ❌ | ❌ | ❌ Not offered | ✅ | W4 | New |
| 13 | Areas | ❌ | ❌ | ❌ | ❌ Not offered | ✅ | W4 | New |
| 14 | Payments | ❌ | ❌ | ❌ | ❌ Not offered | ✅ Entered once, never editable | W5 | New, 🔒 human review |
| 15 | Service request (staff New Request) | ❌ | ❌ | ❌ | ❌ Not offered | ✅ Copied to the real records on approval | W6 | New |
| 16 | Portal new-service form | ❌ | ❌ | ❌ | ❌ | ✅ Only fields switched to "Ask the customer" | W7 | New |

### R6 · Part 2 — Where each one appears (the Placement choices Settings will offer)
| # | Applies to | Typed in (Input) on | Shown read-only (View) on | Who uses it | Rules that apply |
|---|---|---|---|---|---|
| 1 | Accounts | New Account wizard · New Connection Step 1 · Account detail (edit) | Account detail | Clerk | — |
| 2 | Customer | New Account wizard · New Connection Step 1 (owner) · Customer edit | Customer page · Account detail header | Clerk | — |
| 3 | Contacts | Add / edit contact (on Account detail) | Account detail → Contacts | Clerk | — |
| 4 | Addresses (mailing) | Mailing address form (New Account / Account detail) | Account detail | Clerk | Mailing address only; service addresses live on the premise |
| 5 | Service agreements | New Account wizard (services step) · Change plan | Account detail → Services | Clerk | Never used in pricing |
| 6 | Premises | Add Premises · Step 2 Details (+ shown on Step 3 Review) · Edit premise · New Connection Step 2 | Premise page · Premises list (optional column) | Clerk | — |
| 7 | Units | Add Premises (first unit) · Add unit · Edit unit | Premise page → Units tab | Clerk | — |
| 8 | Service points | Add Premises / Add unit (services) | Premise page → Units tab | Clerk | — |
| 9 | Assets | Add asset · Edit asset | Asset detail · Assets list (optional column) | Clerk / field staff | — |
| 10 | Work orders | New work order · Edit work order | Work order detail | Clerk / technician | — |
| 11 | Readings | Manual reading entry · Reading import (column mapping) | Reading detail / reading history | Clerk / meter reader | Never used in the bill calculation |
| 12 | Routes | Add / edit route | Route page | Clerk | — |
| 13 | Areas | Add / edit area | Area page | Clerk | — |
| 14 | Payments | Record payment (at entry only) | Payment detail | Cashier / clerk | Can't be corrected afterwards; never used to apply the payment to bills |
| 15 | Service request | Staff New Request | Request detail · Review / approval | Clerk / supervisor | On approval, copied to Customer / Account / Premises |
| 16 | Portal new-service form | Portal new-service form (applicant) | Staff Request detail | Customer → clerk | Off by default per field; a utility turns each one on |

Added in discussion: every import includes one column per custom field (premises, units,
assets, accounts, readings); account / customer / premises fields may also be placed on Staff
New Request and the Portal new-service form.

### R6 · Rules that hold everywhere
| Rule | What it means for the user |
|---|---|
| One utility only | Another utility never sees a utility's fields or answers, including on the portal |
| Max 10 active per record type | Switching a field off frees its slot |
| Field types | Text · Number · Date · Yes/No · List · Multi-select list |
| Never used in calculations | Captured, shown, searched and exported only; never affects a charge, tax, posting or payment allocation |
| Required means required only where it's typed in | A required field never blocks a screen that doesn't show it |
| Prints on a bill only when switched on | "Safe to print" is off by default |
| Shown on the portal only when switched on | "Ask the customer" is off by default |
| Can't be deleted, only switched off | Old answers are kept and return if the field is switched back on |
| The key can't be renamed | Exports and old bills keep working |

### R6 · Settings → Placement for one field (Roof Material, Premises)
| Screen | Choices offered | Example choice |
|---|---|---|
| Portal new-service form | Ask the customer / Don't ask | Ask the customer |
| Staff New Request | Input / Not shown | Input |
| New Connection · Step 2 Premise | Input / View / Not shown | Input |
| Add Premises · Step 2 Details | Input / Not shown (Step 3 Review lists answers automatically) | Input |
| Edit premise | Input / Not shown | Input |
| Premise page | View / Not shown | View |
| Premises list | Show as column / Not shown | Not shown |
| Request detail / review | View / Not shown | View |

### R6 · Three gaps (agreed fixes)
1. View-only with no input anywhere → warn "No screen collects this field"; allowed only when the field is fed by an import column.
2. Request detail always shows the request's copy of every intake field (account, customer, premises) read-only, so the reviewer sees what was typed before approving.
3. Approval conflict (RULED C): review shows Existing: Metal · Requested: Tile side by side; the EXISTING value is pre-selected; the clerk picks; the choice is audited; a key with no existing value is copied.

### R6 · Never custom-field entities
Plans, rate schedules, invoices, invoice lines, journal entries, journal lines, chart of accounts, any money screen.

**Worked example shown to the PO:** *Roof Material* on Premises — Ask the customer on the
portal, Input on Staff New Request, New Connection Step 2, Add Premises Step 2 and Edit
premise, View on the Premise page and Request detail, not a Premises list column. On approval
of a request saying **Tile** for a property already holding **Metal**, the review shows
*Existing: Metal · Requested: Tile* with Metal pre-selected.

## 1 · What signed statements move

| Statement | Where | What happens to it |
|---|---|---|
| **BR-TEN-046** — *"Entities: the eight property + commercial tables (B2 r17.2)"* | `04-docs/05-modules/01-tenancy/02-business-rules.md` · EP-TEN-09 §BR table · `apps/tenancy/models.CUSTOM_FIELD_ENTITIES` | **AMENDED 2026-10-02.** The list grows to the sixteen of Part 1, by wave; the NEVER list (R2 + R3) is written into the rule. The eight stay the only addressable entities until W4 adds the next ones with their storage. |
| **BR-TEN-052** — *"a fixed allow-list of eligible screen slots per entity (A1 IDs)"* | same file · EP-TEN-09 §2 "Eligible slots shipped in R2" · `apps/tenancy/custom_fields.ELIGIBLE_SLOTS` | **AMENDED 2026-10-02.** The allow-list becomes Part 2's screens, each declared ONCE with whether a screen renders it yet; **Settings offers only the rendered ones**; a slot is keyed by A1 id where the screen has one and by a plain code where it does not (Premise page, Edit premise, …). Every active field must have an input route (R4). |
| **BR-TEN-048** — *"never … payment allocation"* | same file | **UNCHANGED as a rule.** HOW it is enforced for Payments narrows: W5 lets a payment carry a value captured at entry (never editable), and G6's `apps/payments/` ban is opened for that one capture path only, under 🔒 human review. Not touched by W1. |
| **BR-TEN-049** — key immutable — **PROPOSED** | same file | **CONFIRMED** by the PO's Rules table: *"The key can't be renamed — Exports and old bills keep working"*. |
| **US-TEN-016 TC-6** — *"A required field placed only as View — save on that screen is not blocked"* | EP-TEN-09 | Generalised by the Rules table: *"Required means required only where it's typed in"* — a required field blocks only the screen it is placed on as Input. |

No ❄️ B4/B5 figure moves. No money path is touched by any wave except W5 (🔒).

## 2 · Status

**IN BUILD.** **W1 DONE — `2.456.0`, 2026-10-02** (code `474f7d23b`); **W5 DONE — `2.457.0`, 2026-10-02 (🔒 HUMAN-REVIEW-PENDING)**; **W4 DONE — `2.461.0`, 2026-10-02 (🔒 HUMAN-REVIEW-PENDING; New Connection Step 1's owner declared and not rendered, §8)**; **W6 DONE — `2.465.0`, 2026-10-02, code `d8d753d76` (🔒 HUMAN-REVIEW-PENDING; §9)**; **W7 DONE — `2.466.0`, 2026-10-02, code `16bc09376` (🔒 HUMAN-REVIEW-PENDING; §10)**.

## 3 · Impact

* **Code (W1):** `apps/tenancy/custom_fields.py` (the ONE shared slot list, input-route
  check, required-where-typed), `selectors.py` / `api.py` (serve the list), `services.py`
  (`validate_custom_data_for(…, screen=)`), `apps/customers/seams.py` + `services.py` (each
  door names its screen; Account detail merges an edit into the stored answers),
  `07-frontend/src/features/tenancy/SettingsCustomFields.tsx` (plain screen names by route,
  type help per type), `07-frontend/src/features/customers/AccountDetailPage.tsx` (custom
  fields editable on Account detail), the eleven catalogues.
* **Data:** none moved. Stored placements on a slot no screen renders yet are **kept** and
  carried through every placement save, so when W2/W3 render that screen the tenant's earlier
  choice takes effect; a stored key the list no longer declares at all is dropped on the
  field's next placement save.
* **Docs:** BR-TEN-046/049/052 (dated), EP-TEN-09's BR rows and slot table (stamped).
* **Gates:** a pytest pairs every rendered slot with the component call that renders it
  (fails if Settings offers a slot nothing renders, and if a screen renders a slot the list
  calls not-rendered); a pytest refuses every NEVER entity and asserts no money screen is a
  slot.
* **Lanes building now:** the exports-to-S3 lane (`tenancy/exports.py`, the export store,
  report delivery) — not touched.

## 4 · Waves

| Wave | What | Kind | Rollback | Status |
|---|---|---|---|---|
| **W1** | Settings honesty: offer only rendered slots from ONE served list · plain screen names grouped *Customer (portal) / Clerk input / Read-only view* with Part 2's exact choices · input-route check (R4, gap 1) · type help per type · required only where typed in · Account detail editable · the NEVER list enforced by test | defects | Revert the W1 commits; no data moved, stored placements untouched | **DONE** `2.456.0` |
| **W2** | Server saves answers for contacts, addresses, service agreements, premises, units, service points, assets (validate through `validate_custom_data_for(…, screen=)`) | defects | Revert; answers already written stay in `custom_data` and are harmless | not started |
| **W3** | Screens for those seven: each flips its slots to rendered **in the same commit as the screen**, which the pairing test enforces | defects | Revert the screen and its slot flip together | not started |
| **W4** | New entities: customers, work orders, readings (+ reading import), routes, areas — storage migrations 🔒 | change | Down-migration drops the empty `custom_data` columns only if no answers exist | **DONE** `2.461.0`, code `48ce95a43` (HUMAN-REVIEW-PENDING; §8) |
| **W5** | Payments, capture at entry, never editable; G6 opened for that one path | change, 🔒 human review | Revert; the column stays and is read by nothing | **DONE** `2.457.0`, code `e29ca6b56` (HUMAN-REVIEW-PENDING) |
| **W6** | Staff New Request + Request detail + approval copy with the R5 side-by-side pick (audited) | change | Revert; a request's own copy stays on the request | **DONE** `2.465.0`, code `d8d753d76` (HUMAN-REVIEW-PENDING; §9) |
| **W7** | Portal new-service form: only fields switched to *Ask the customer* | change | Revert; switch defaults off, so nothing shows | **DONE** `2.466.0`, code `16bc09376` (HUMAN-REVIEW-PENDING; §10) |

Import columns are folded into each record type's own wave (premises and units already
carry them today).

## 5 · W1 task table

| # | Task | Defect | Status |
|---|---|---|---|
| 1 | One shared slot list, served by the API; Settings offers only rendered slots; pairing test | `DEF-TEN-9153` | **DONE** `2.456.0` |
| 2 | Plain screen names by route, Part 2's choices, eleven catalogues | `DEF-TEN-9154` | **DONE** `2.456.0` |
| 3 | Input-route check with the import exception, tested both ways | `DEF-TEN-9155` | **DONE** `2.456.0` |
| 4 | Type help matches the type | `DEF-TEN-9156` | **DONE** `2.456.0` |
| 5 | Required only where typed in (prove the bug first) | `DEF-TEN-9157` | **DONE** `2.456.0` |
| 6 | Account detail: account fields placed Input become editable | `DEF-CUS-9158` | **DONE** `2.456.0` |
| 7 | NEVER entities refused; no money screen is a slot | — (test) | **DONE** `2.456.0` |
| 8 | New Connection Step 1 drops the account fields it shows (found while locating) | `DEF-CUS-9159` | **DONE** `2.459.0` (W3, customers lane — §7) |

## 6 · Close

### W1 — closed 2026-10-02, version `2.456.0`, code `474f7d23b`

**What a System Admin sees now.** Settings → Custom fields → Placement offers only the screens
that draw a field today — for an Accounts field, *New account* (Input / Not shown) and *Account
detail* (Input / View / Not shown), under the heading *Clerk input*; no screen id appears. A
Premises field (Roof Material) offers no screen yet and says *"Filled by import."*, because the
premises import carries it. *Applies to* offers Accounts, Premises and Units for a new field.
A field shown on a screen and collected nowhere is refused *"No screen collects this field."*.
The Type help reads *"Never used in any charge."* under Number only. A required field blocks
only the screen it is typed in on; Account detail's *Account setup* pencil edits the account
fields placed Input there.

**The shared slot list** (`apps/tenancy/custom_fields.SLOTS`, served by
`GET /settings/custom-fields/slots`):

| Record type | Rendered now (W1) | Declared, not yet rendered — the wave that flips it |
|---|---|---|
| Accounts | New account (S18, input) · Account detail (S21, input + view) | Staff New Request (W6) · Request detail (W6) · Portal new-service form (W7) |
| Contacts | — | Account detail → Contacts (W3) |
| Addresses (mailing) | — | New account mailing (W3) · Account detail mailing (W3) |
| Service agreements | — | New account services (W3) · Change plan (W3) · Account detail → Services (W3) |
| Premises | — (import-fed) | Portal (W7) · Staff New Request (W6) · New Connection Step 2 (W3) · Add Premises Step 2 (W3) · Edit premise (W3) · Premise page (W3) · Premises list column (W3) · Request detail (W6) |
| Units | — (import-fed) | Add Premises first unit · Add unit · Edit unit · Premise page → Units (all W3) |
| Service points | — | Add Premises services · Add unit services · Premise page → Units (all W3) |
| Assets | — | Add asset · Edit asset · Asset detail · Assets list column (all W3) |

W4's record types (customers, work orders, readings, routes, areas), W5's payments and W6's
service requests add their own rows with their entities. **A wave flips `rendered=True` in the
same commit as the screen that draws the slot** — `tests/test_cr161_w1_custom_field_settings.py`
pairs every `<CustomFields… entity=… screen=…>` in the front end with the list and fails on
either half alone — and adds the screen's name to the catalogues (`settings.customFields.screen.<name>`).

**Proof.**
* **Reproduced first**, in Chromium against a scratch PostgreSQL 16 database, before any code
  moved: Roof Material placed on S14/S15/S16 read *Screens = 3* and Add Premises showed nothing;
  the dialog said *Screen S14 / S15 / S16*; a view-only field saved; the Type help read *"A
  number here…"* under Pick one and Date; New Account answered **422 `custom_data.gate_code`
  required** with *"Some of this field's settings need fixing"* for a required field placed on
  no screen; the Account setup dialog had no Visit window control though Settings offered Input.
* **After**, the same steps (`10-scripts/cr161_w1_custom_field_settings_walkthrough.mjs`):
  **33 passed, 0 failed** — Roof Material counts 0 and offers *Filled by import.*; Visit window
  offers *New account* and *Account detail* grouped under *Clerk input*; Access note View-only is
  refused *No screen collects this field.*; Applies to lists Premises, Units, Accounts; Number
  alone carries the help; New Account **201** with `visit_window = Mornings` while Gate code is
  required and placed nowhere; the Account setup dialog sends exactly
  `{"custom_data":{"visit_window":"Afternoons"}}` and Account detail reads *Afternoons*; with
  every field deactivated, Account detail and its dialog show no custom section (zero-field
  tenant unchanged). Screenshots `cfw1_before_*.png` / `cfw1_after_*.png`, lane scratchpad.
* **Tests:** `tests/test_cr161_w1_custom_field_settings.py` 24/24 on SQLite **and 24/24 on
  PostgreSQL 16** (`config.settings.local`, a scratch test database; run as the `postgres` role
  because `sbh_b27` may not create a database — so the isolation case there proves the
  application's tenant filter and the cache key, not RLS FORCE, which the isolation suite owns);
  the placement and
  value suites 54/54 after their asset cases were made to stand in for W3 by a fixture that
  renders the asset slots, and four cases re-shaped for R4. **Six mutation reds** proved through
  pytest (a premises slot marked rendered; the Account detail control removed; required binding
  every definition; no input-route check; an edit replacing the blob; `invoices` as an entity) —
  each red on its own assertion, files restored byte-for-byte. vitest:
  `SettingsCustomFields.test.tsx` 24/24, `AccountPanelEdits.dom.test.tsx` 13/13 with **three
  mutation reds** (whole blob sent; help under every type; key printed as the label).
  `tsc --noEmit` clean, eslint clean on every touched file, G31 green after the Settings file
  joined the Route-B ledger.
* **Reds I did not cause, dated:** `test_be11_tc05` (the OpenAPI snapshot is stale for the
  exports lane's `exports/{job_id}/file` docstring, `9e298249d`, today — this lane committed only
  its own hunk), `test_be11_tc02` (the portal document routes, `5ac17a0e9`, CR-158) and
  `test_us_cus_001_tc1__the_list_renders_rows_and_an_honest_roll_up` (`by_status`, `35cbdb0d1`,
  2026-09-28). The `--changed` gate run's 41 red gates name no file this lane touched except G31,
  which this lane turned green.

**Rollback.** Revert `474f7d23b`. No data moved and no migration ran; a placement stored while
W1 was live is a plain key in the same map and reads the same under the old code.

**Not done in W1, on purpose.** New Connection's dropped values (`DEF-CUS-9159`) are W3's — the
commit plan and the metering owner-account payload are that wave's surface.

### W5 — closed 2026-10-02, version `2.457.0`, code `e29ca6b56` (🔒 HUMAN-REVIEW-PENDING)

**What a cashier sees.** With a payment field defined (Settings → Custom fields → *Applies to: Payments*,
placed *Input* on **Record payment** and *View* on **Payment detail** — the two screens are named, no id is
shown), Record payment draws it under *Your own fields*. *Drawer* required and left blank is refused —
*"This one is required."* under the field, *"Check the highlighted fields. Nothing was saved."*, the account
and the $120.00 still typed. *Drawer = 2* records the payment, and Payment detail shows **Drawer 2** in the
*This payment* panel with no control beside it; **Correct reference** does not offer it. A utility with no
payment fields sees Record payment exactly as before.

| # | Task | Status |
|---|---|---|
| 1 | `payments/0046` — `payments.custom_data jsonb NOT NULL DEFAULT '{}'`; `tenancy/0056` — `ck_custom_field_entity` admits `payments` | **DONE** `2.457.0` 🔒 |
| 2 | Written ONLY by `record_payment`'s INSERT, validated through `settings_seam.validate_entry_answers` → `tenancy.services.validate_custom_data_for`; NOT added to `payments/0014`'s allow lists (G131 green); UPDATE refused by the trigger, proved on PostgreSQL 16 in both branches | **DONE** |
| 3 | `payments` in `CUSTOM_FIELD_ENTITIES`; `SLOTS` gains Record payment (S35, Input) and Payment detail (S33, View), both rendered in the same commit as the screens (W1's pairing test green); BR-TEN-046 note and BR-TEN-048 enforcement sentence amended | **DONE** |
| 4 | G6 / DB-17 narrowed for `apps/payments/` to `custom_values.py`, `payments/0046` and seven named statements; self-test pins a read in allocation, deposit, refund, dunning and the ledger handoff, and a different statement in an allowed file | **DONE** |
| 5 | Exports / search | **NOT DONE, on purpose** — no payment export or search source carries the answers yet; BR-TEN-048 would allow it, nothing in W5's rows asks for it. A later wave adds it to `payments_dataset.py` through `custom_values` |

**How the server knows the answers were typed on Record payment** (a judgment call, decision log
2026-10-02): one endpoint serves Record payment and three doors that draw no custom fields. The Record
payment page always sends `custom_data` (`{}` when empty); the others never do. The key's presence names
the screen, so a required field binds on S35 and never on Take payment.

**Proof.**
* **Gate, red first through `run_gates.py`:** a read planted at the end of `apps/payments/allocation.py`
  (`getattr(object(), "custom_data", None)`) → G6 FAIL with `allocation.py:1160: DB-17 / BR-TEN-048`
  among 58 hits; plant removed (blob `bf3403b8b4…` identical to HEAD) → G6's DB-17 hits **0**, 57 hits
  left, every one pre-existing in files W5 did not touch. Self-test mutation: adding `allocation.py` to
  the allowed files, or allowing `allocate_payment(payment, custom_data=…)` in `services.py`, each makes
  the gate report itself BLIND.
* **Tests:** `tests/test_cr161_w5_payment_custom_fields.py` — 12 + 4 PG-only on SQLite; **15/15 on
  PostgreSQL 16** (the trigger refuses `UPDATE payments SET custom_data` on a cleared AND a processing
  payment; the column default is `'{}'::jsonb NOT NULL`; `sbh_rls_probe` under the other utility sees 0
  rows). Allocation of $120.00 across two open bills is identical with and without *Drawer = 2*. Four
  mutation reds (INSERT drops the answer; S35 stops naming its screen; every door treated as S35;
  detail serves nothing), each restored byte-for-byte. W1's suite 24/24 with its two pins widened for
  the payments slots. vitest `paymentCustomFields.dom.test.tsx` 4/4 with three mutation reds; the ten
  touched payment/Settings suites 122/122. `tsc` clean, eslint clean, G31 / G131 / G7 / G98 / G35 PASS.
* **Browser** (Chromium, `vite build --mode wolocal`, PostgreSQL 16 scratch database, dropped after):
  `10-scripts/cr161_w5_payment_custom_fields_walkthrough.mjs` **23 passed, 0 failed** — screenshots
  `cf5_1…cf5_7` in the lane scratchpad. On that database `UPDATE payments SET custom_data=…` answered
  *"BR-PAY-002 / hard rule 4: payment PY-261002-0084 is processing — only status and cleared_at may
  change …"*.
* **Golden:** `06-backend/tests/golden/` and `10-scripts/03-golden-verify.py` untouched.

**Rollback.** Revert the W5 code commit. The two migrations reverse cleanly while no payment field is
defined; once a utility has defined one, `tenancy/0056`'s reverse is refused by PostgreSQL rather than
silently losing it, and the column on `payments` is read by nothing after the revert.

### W2 + W3, metering and assets half (lane CF-W3b) — closed 2026-10-02, version `2.458.0`, code `ffd4aba2d`

Premises, units, service points and assets. Contacts, mailing addresses and service agreements
(and New Connection Step 1) are the customers lane's half of W2/W3 and are not touched here.

| # | Task | Defect | Status |
|---|---|---|---|
| 1 | Premises: create/update accept `custom_data` through metering's seam (`S16` both Add Premises doors · `NEW_CONNECTION_PREMISE` · `PREMISE_EDIT` · `None` for imports/seed); Add Premises Step 2 input + Step 3 recap; Edit premise; New Connection Step 2 (input for a new property, view for one on file); Premise page view; Premises list optional column | `DEF-MET-9226` | **DONE** `2.458.0` |
| 2 | Units: first unit on Add Premises, Add units (the pattern generator, `UNIT_ADD`, validated once at the review), Edit unit; Premise page → Units tab columns | `DEF-MET-9227` | **DONE** `2.458.0` |
| 3 | Service points: `service_point_custom_data` keyed by service code on unit creation (Add Premises first unit, Add units); a code the unit does not take is refused by name; Units tab column *Water: Front curb* | `DEF-MET-9173` | **DONE** `2.458.0` |
| 4 | Assets: `_validate_asset` validates through the assets seam (`S51`, `ASSET_EDIT`, `None` for the upload and the unit wizard's meter grid); Add asset (step 4 + review), Edit asset, Asset detail view, Assets list optional column; every asset sheet carries one column per field | `DEF-AST-9171` | **DONE** `2.458.0` |
| 5 | Imports: each custom cell judged by `validate_custom_data_for(screen=None)` (a bad one is the row's parse problem in words; a good one stored normalised); a custom column is never `required`; an update merges the file's answers into the stored ones | `DEF-MET-9172` | **DONE** `2.458.0` |

**The shared list.** Sixteen `SLOTS` rows flipped to rendered in the code commit, each beside the
component that draws it. `IMPORT_FED_ENTITIES` is now premises, units, assets, pinned to
`import_runs.CUSTOM_FIELD_ENTITY_BY_TARGET`. The pairing test also pairs table columns now
(`useCustomFieldColumns<Row>({ entity: "…", screen: "…" })`), so the two list slots are checked like the
rest. Kit additions, reused everywhere (B14 rule 43): `CustomFieldsAnswers` (a review recap from the same
registry the form read), `useCustomFieldColumns`, `customFieldErrors`, an optional `heading` on
`CustomFieldsInput/View` (a service's block names the service), and `FormModal.FieldErrorsScope` (a full-page
wizard marks a refused custom field on its own control).

**Proof.**
* **Reproduced first** at 2.456.0 in Chromium on a scratch PostgreSQL 16 database (`cf3b_walk`):
  `POST /premises` and `POST /units` with `custom_data` → 422 `metering.unknown_field`; `PATCH /assets/{id}` →
  422 `assets.unknown_field`; placement on S16 / Premise page → `slot_not_rendered`; Add Premises step 2 and
  the Premise page show no Roof Material (`cf3b_before_*.png`).
* **After**, `10-scripts/cr161_w3b_metering_assets_walkthrough.mjs`: **54 passed, 0 failed** — Roof Material
  (List: Metal / Tile / Shingle, required) placed with the PO's table; Placement offers the five premises
  screens by name; step 2 draws it, plus Gate code for the first unit and Valve location per service; Create
  with Roof Material blank is refused on that box only, address and gate code kept, Retry after choosing Metal
  creates it; step 3 lists *Roof Material Shingle* and *Unit 1 · Gate code 1200*; the Premise page reads Metal,
  the Units tab shows *4471* and *Electric: Front curb*; Edit premise changes it to Tile; no list column until
  switched to *Show as column*, then the column reads Tile; a premises CSV with a ROOF column maps although the
  field is required, loads *Shingle*, refuses *Purple*, loads the blank row; Edit asset types *Acme Meters*,
  Asset detail and the Assets list column show it; Six Rivers (no fields) sees an unchanged Add Premises.
  Screenshots `cf3b_after_*.png`.
* **Tests:** `tests/test_cr161_w3b_metering_assets_custom_fields.py` 19 + W1's 25 = **44/44 on SQLite and
  44/44 on PostgreSQL 16** (`config.settings.local`, run as `postgres`, so isolation there proves the
  application's tenant filter, not RLS FORCE). Mutation reds through pytest: a required custom column
  (`required_column_unmapped`), the cell judge removed, `custom_data` dropped from New Connection's door, the
  Assets list slot un-rendered (pairing test) — each red, each restored. vitest `CustomFieldsW3b.test.tsx` 7/7
  (red when every unit gets the first unit's answers); the eleven touched suites 328 passed + the asset edit
  census widened for `custom_data`. `tsc` clean, eslint clean, G31 / G98 PASS, G13 / G32 name nothing of this
  change.
* **Reds I did not cause, dated:** 40 in the import/asset/premises suites fail identically at the tip this
  lane started from (`8db4765fb`, run in a clean worktree): the asset-import fixture now seeds an electric meter
  on every unit (`AST.UNIT_SERVICE_FREE`), `create_premises` carries no `__wrapped__` for the legacy CSV
  importer, `size_class_name` on the registry row (`3bf716c90`, 2026-09-27), `premises.master_account`
  unclassified for the import (DEF-MET-5802's test), and `test_be11_tc02`.

**Not done, on purpose.** Edit unit does not edit a service point's answers (Part 2 row 8 places them on
creation only; a PATCH naming them is refused by name). Exports (CSV) carry no custom column yet — US-SHL-016's
CSV half, unchanged. A required field's blank on Add Premises lands on the wizard's failure card with *Retry*
rather than on the review step; the box is marked and nothing typed is lost.

**⚠ Register collision — REPAIRED 2026-10-02 by PO ruling.** These two property defects were filed under
the running numbers 9168 / 9169 with the MET segment, sharing their running numbers with `DEF-CUS-9168` / `DEF-CUS-9169`, which the
customers lane pushed minutes earlier (G17 *running-number shares*). This lane's first fix (`→ 9174/9175`, since
taken by `DEF-CUS-9174/9175`) needed the register-deletion override it was not permitted to use. The PO then ruled
(decision log 2026-10-02 *"SEVEN PO ANSWERS IN ONE MESSAGE"* item 4, *"A Give the two property ones the next free
numbers"*), and they are now **`DEF-MET-9226`** (Premises) and **`DEF-MET-9227`** (Units), every citation moved.

**Rollback.** Revert `ffd4aba2d`. No migration ran (every `custom_data` column already existed); answers
written while it was live stay in their jsonb columns and are read by nothing after the revert.

## 7 · W2 + W3, customers lane — accounts (New Connection), contacts, mailing addresses, service agreements

**DONE `2.459.0`, 2026-10-02.** Part 2 rows 1, 3, 4 and 5. The metering lane (premises, units,
service points, assets) records its own rows. Judgments: decision log 2026-10-02 *"Custom fields on the
customers record types …"*.

| # | Task | Defect | Status |
|---|---|---|---|
| C1 | New Connection Step 1's *Account details* reach the owner's account (`commitPlanOf` → owner `custom_data` → `create_owner_account` → the master door, slot `S18`) | `DEF-CUS-9159` | **DONE** `2.459.0` |
| C2 | Contacts: the Customer edit on Account detail (input) and the Customer group (view), slot `S21`; `PATCH /accounts/{id}/contact` merges; the account read serves each contact's answers | `DEF-CUS-9168` | **DONE** `2.459.0` |
| C3 | Mailing addresses: New Account's mailing block (`S18`, only while one is typed) and Account detail's mailing edit + group (`S21`); `POST /accounts` and `PATCH …/mailing-address` validate and merge | `DEF-CUS-9169` | **DONE** `2.459.0` |
| C4 | Service agreements: New Account's unit step (`S18`, written on every agreement the account opens; refused on a draft), Change plan's confirm step (`S23`, merged into every open agreement), Account detail's Services group (`S21` view, one block per agreement) | `DEF-CUS-9170` | **DONE** `2.459.0` |
| C5 | New Account sent no account fields when none were typed, so a required one drawn there was never checked (found while proving C3/C4) | `DEF-CUS-9191` | **DONE** `2.459.0` |

**What a System Admin sees now.** *Applies to* offers Contacts, Addresses and Service agreements. The
placement dialog offers *Account contacts* (Input / View), *New account mailing* and *Account mailing
address*, *New account services*, *Change plan* and *Account services* — six slots flipped to rendered in
`custom_fields.SLOTS` in the same commit as the screens, which the W1 pairing test enforces.

**Proof.**
* **Reproduced first** in Chromium against a scratch PostgreSQL 16 database (`cf3a_walk`): a Contacts,
  an Addresses and a Service agreements field each created 201, every placement refused
  (`slot_not_rendered` / `slot_not_eligible`), `PATCH …/contact` and `PATCH …/mailing-address` with
  `custom_data` answered 422 `customers.account.unknown_field`, the Customer edit drew nothing; a
  REQUIRED account field on New account left untouched opened the account 201 (`DEF-CUS-9191`).
* **After**, the same steps (`10-scripts/cr161_w3_customers_custom_fields_walkthrough.mjs`): **43 passed,
  0 failed** — the contact edit sends exactly the changed key and the Customer group shows it; a blank
  required *Preferred name* is refused 422 with the dialog open and the phone still typed; the mailing edit
  carries the note and the group shows it; New Account writes *Ring twice* on the mailing row and
  *12 months* on both agreements it opened, shown as *Water fields* / *Electric fields*; Change plan sends
  `service_custom_data` and every open agreement reads the new term; another utility's registry is not
  readable; with every field switched off Account detail and the Customer edit show nothing. New
  Connection pressed end to end (`po20260929_new_connect_press_create.mjs`, card tender): the owner's
  account `AC-2026-00017` holds `visit_window = CUSTOM-181900`, typed on Step 1. New Account with the
  required field untouched now answers 422 with every step's values still on screen.
* **Tests:** `tests/test_cr161_w3_customers_custom_fields.py` 16/16 on SQLite **and 16/16 on PostgreSQL 16**
  (`config.settings.pgtest`, as the `postgres` role — the isolation case proves the application's tenant
  filter and the registry cache key, not RLS FORCE); W1's suite 24/24 with its two pins moved to the W3
  state. **Four mutation reds** through pytest (the owner forward key renamed; the contact edit's screen
  set to none; the draft refusal disabled; the Change plan slot flipped back) and **two** through vitest
  (`commitPlanOf` without `custom_data`; the contact edit sending the whole blob), each red on its own
  assertion, files restored byte for byte. vitest `customersCustomFieldsW3.dom.test.tsx` 8/8 and eleven
  neighbouring files green one at a time.

**Rollback.** Revert the commit. No migration; answers already saved stay in their rows' `custom_data`
and nothing reads them.

## 8 · W4 — customers, work orders, readings, routes, areas (lane CF-W4) — closed 2026-10-02, version `2.461.0`, code `48ce95a43` (🔒 HUMAN-REVIEW-PENDING)

### Task table

| # | Task | Status |
|---|---|---|
| 1 | `tenancy/0057` — `ck_custom_field_entity` admits `customers`, `work_orders`, `meter_reads`, `routes`, `areas`; `areas.custom_data`. `metering/0067` — `custom_data` on `routes`, `work_orders`, `read_import_rows`, `meter_reads`. All `NOT NULL DEFAULT '{}'`; RLS unchanged | **DONE** `2.461.0` 🔒 |
| 2 | Each door validates through tenancy's one validator via its own module's seam; a door names its screen by sending the key; edits merge | **DONE** |
| 3 | Customers: New account customer step (`S18`) · Edit customer (`CUSTOMER_EDIT`) → account header customer block (`S21`) | **DONE** |
| 4 | Customers: New Connection Step 1 owner (`NEW_CONNECTION_OWNER`) | **DECLARED, NOT RENDERED** — the owner's answers would travel the NC commit path the NC lanes changed the same hour (`CR-162-BRC10`); left for the wizard lane, not offered by Settings meanwhile |
| 5 | Work orders: New work order (`WORK_NEW`) · Edit work order (`WORK_EDIT`, one audit row) → Work order detail (`WORK_DETAIL`) | **DONE** |
| 6 | Readings: + Add reading (`READ_ENTRY`, every register row) → reading detail (`S29`); S28 upload maps one column per field (key or label), a bad cell is a row error, the template gains the columns; corrections carry the answers | **DONE** |
| 7 | Routes: route wizard step 1 (`ROUTE_FORM`) → route page (`ROUTE_PAGE`) | **DONE** |
| 8 | Areas: Areas dialog (`AREA_FORM`) → a column on the Areas list (`AREA_LIST`) | **DONE** |
| 9 | Never in the bill: G6 / DB-17 absolute for `apps/rating/`, proved red on a planted read | **DONE** |
| 10 | Exports / search of the W4 answers | **NOT DONE, on purpose** — no W4 row asks for it; a later wave adds the columns to each dataset |

**Missing screens, reported rather than invented.** There is **no Customer page** (the PO's *"Customer page"*
View): a customer's answers show in the account page's customer block, which is the PO's other View screen
(*Account detail header*). There is **no Area page**: an area is a row of Settings → Reference data → Areas, so
the View is an optional column there. *Reading history* is the reading detail page; no history table gains a
column.

**What a clerk sees.** With *Seal number* defined on Readings (Input on *Add a reading*, View on *Reading
detail*), *+ Add reading* draws it under *Your own fields*; meter M-4021 posted at 16,202 kWh with
*Seal number S-2207* shows the answer on its page, and the usage is the same 120 kWh it would be without it. A
readings file with a *Seal number* column stages each row's answer. *Patrol day* on a route, *Warden* on an
area (a column of the Areas list), *Crew radio* on a work order and *Loyalty tier* on a customer each appear on
the screens the PO named. A utility with no fields sees every one of these screens unchanged.

**Proof.**
* **Tests:** `tests/test_cr161_w4_custom_fields.py` — 25 on SQLite (7 PG-only skipped) and **32/32 on
  PostgreSQL 16** (`config.settings.pgtest`): each column NOT NULL with default `'{}'::jsonb`; the CHECK
  admits the five and not `invoices`; `sbh_rls_probe` under the other utility counts 0 rows for a route's
  answer; the manual-entry and upload stage/post paths. **Seven backend mutation reds** (the post drops the
  answer; a route edit replaces instead of merging; every work-order door bound as New work order; the area
  dialog unnamed; the customer block ignored; the upload ignores its columns; a W4 slot unrendered) and
  **three vitest mutation reds** (`CustomFieldsW4.dom.test.tsx`, 6 cases: the counter read drops the answer;
  Edit customer sends the whole blob; New account drops the customer block's answers), each restored
  byte-for-byte. W1's pairing test 25/25 with the five types' screens.
* **Gate, red first:** a read planted at the end of `apps/rating/services.py` → G6's `run()` reports **58 hits,
  one of them `DB-17 … in the RATING path`**; plant removed (sha256 `de6dd784…` identical) → **57 hits, 0
  DB-17**, every one pre-existing in files W4 did not touch.
* **Browser** (Chromium, `vite build --mode wolocal`, PostgreSQL 16 scratch database `cf4_walk`, dropped
  after): `10-scripts/cr161_w4_custom_fields_walkthrough.mjs` — earlier runs failed on three walk-script faults
  (a backward counter value, a label the account page already uses, a re-run route value), each fixed in the
  script, none in the product; final run **54 passed, 0 failed**. Screenshots `cf4_01…cf4_19` in the lane scratchpad.
* tsc clean; eslint clean on every touched file; G31, G134, G7, G35, G42, G78, G85, G98 PASS.
* **Reds I did not cause:** G15 (803 English values, none of them W4 keys), G33 (10 refusals over six words,
  none of them W4 keys), G13, G40, G86 and the rest of the `--changed` list name files W4 did not touch.

**Rollback.** Revert `48ce95a43` and its follow-up. `metering/0067` reverses cleanly; `tenancy/0057`'s reverse
is refused by PostgreSQL once a W4 field is defined, rather than losing it. Answers already saved are read by
nothing after a revert.

## 9 · W6 — the staff service request (lane CF-W6) — closed 2026-10-02, version `2.465.0`, code `d8d753d76` (🔒 HUMAN-REVIEW-PENDING)

Part 2 row 15, gap 2 and gap 3 (R5, RULED C). Judgments: decision log 2026-10-02 *"Custom fields on the staff
service request (`CR-161-BRC10` W6, `2.465.0`)"*.

### Task table

| # | Task | Status |
|---|---|---|
| 1 | `customers/0076` — `service_requests.custom_data jsonb NOT NULL DEFAULT '{}'`, one blob per record type (`customers`, `accounts`, `premises`); RLS unchanged | **DONE** `2.465.0` 🔒 |
| 2 | `SLOTS`: Staff New Request (`REQUEST_NEW`, input) and Request detail (`REQUEST_DETAIL`, view) rendered for accounts and premises, and declared + rendered for customers; W1 pairing test green, only W7 still waiting | **DONE** |
| 3 | Capture: create/PATCH validate each type through `seams.validate_custom_data(…, screen="REQUEST_NEW")`, merge per key; a type outside the three refused by name; required holds the step and the SUBMIT, never a draft | **DONE** |
| 4 | Staff New Request: customer + account fields on step 1, property fields on step 2 (a panel only when a field is placed), step 4 lists the answers; refusals marked on the control | **DONE** |
| 5 | Request detail (Applicant tab): the request's own copy, read-only — every intake field whatever its Request detail choice (gap 2) | **DONE** |
| 6 | Approve: *Your own fields* — copy / conflict (*Existing: Metal · Requested: Tile*, Existing pre-selected) / already there / stays on request; the pick travels with the approval; copy inside the approval transaction; one audit row; premises through metering's `update_premises` | **DONE** |
| 7 | Carry answers into the account a move-in later opens and the premises a new-connection build later creates | **DONE** `2.467.5` — `DEF-CUS-9211`: the move-in, the owner-account doors and the New Connection commit carry the request's answers (decision log 2026-10-03) |

### What a clerk sees

With *Roof Material* (Metal / Tile / Shingle) placed *Input* on **New request** and *View* on **Request detail**
(Settings names both screens, no key printed), step 2 of New request draws a *Property fields* panel. The clerk
picks *Tile* and types *Gate code 4471*; step 4 lists both. The request's Applicant tab reads *Roof Material Tile ·
Gate code 4471*. On **Approve** for 2201 Cane Island Pkwy (`P-00002`, already *Metal*) the window shows *Your own
fields · Property P-00002*: *Gate code 4471 · added* and *Roof Material [Existing: Metal | Requested: Tile]* with
Existing chosen. Picking Tile and approving leaves the property reading *Tile* and *4471*; the request keeps its
own copy. A utility with no active fields sees New request, the request and Approve unchanged.

### Proof

* **Reproduced first** at `2.462.0` in Chromium on a scratch PostgreSQL 16 database (`cf6_walk`): the slot list
  served `REQUEST_NEW` / `REQUEST_DETAIL` with `rendered: false`; placing Roof Material there answered 422
  `slot_not_rendered`; the Placement dialog offered no request screen; New request step 1 drew nothing
  (`cf6_before_1_placement.png`, `cf6_before_2_new_request.png`, lane scratchpad).
* **Tests, red first:** `tests/test_cr161_w6_request_custom_fields.py` run against the tip before the change
  (`ad3bec69d`, a `git archive` copy): **15 of 16 red** (13 on `settings.customFields.invalid` — the placement
  refused; one `KeyError: 'custom_field_copy'`; the slot pin), the sixteenth (*a required field typed
  elsewhere never blocks the request*) green as the regression guard it is. After: **17/17 on PostgreSQL 16**
  (`config.settings.pgtest`, the column NOT NULL with default `'{}'::jsonb`) and 16 + 1 PG-only skipped on
  SQLite; W1's suite 25/25 on both. **Six backend mutation reds** through pytest (an unpicked conflict
  overwrites; no pre-selection; submit ignores a required answer; the occupier's account becomes the target;
  an edit replaces instead of merging — which SURVIVED the first draft of the test and was caught by adding a
  sibling key; approval stops copying) and **four vitest mutation reds** in `requestCustomFieldsW6.dom.test.tsx`
  (8 cases: Requested pre-selected; an edit re-sends the whole blob; Request detail ignores the intake fields;
  the pick not sent) — every file restored byte for byte (sha256 compared). Neighbouring suites: 194 backend
  (`test_cr094_approval_raises_the_job`, `test_cr031_service_request*`, `test_req03_four_steps_server`) and
  ~330 vitest across the capture, detail, approve and custom-field files, green; `ServiceRequestDetailPage.test`
  now renders the Applicant tab inside a QueryClient. `tsc` clean, eslint clean on every touched file.
* **Browser** (Chromium, `vite build --mode wolocal`, `cf6_walk` rebuilt from a template):
  `10-scripts/cr161_w6_request_custom_fields_walkthrough.mjs` **40 passed, 0 failed** — screenshots
  `cf6_1_placement` … `cf6_8_no_fields_new_request` in the lane scratchpad. The audit row read back:
  `{"kept": {}, "picks": {"premises": {"roof_material": "requested"}}, "copied": {"premises": {"target":
  "P-00002", "values": {"gate_code": "4471", "roof_material": "Tile"}}}, "waiting": {}}`.

### Rollback

Revert `d8d753d76`. `customers/0076` reverses by dropping the column: answers typed on requests are lost with
it, answers already copied onto a customer, account or premises stay there and are read as before.

## 10 · W7 — the customer portal's new-service form (lane CF-W7) — closed 2026-10-02, version `2.466.0`, code `16bc09376` (🔒 HUMAN-REVIEW-PENDING)

Part 2 row 16 (*"Portal new-service form (applicant) · Staff Request detail · Customer → clerk · Off by default
per field; a utility turns each one on"*), the *"Added in discussion"* line (*"account / customer / premises
fields may also be placed on … the Portal new-service form"*), the Roof Material table's *"Ask the customer /
Don't ask"*, and the Rules table: *one utility only, including on the portal* · *"Ask the customer" is off by
default* · *required only where it's typed in* · *never used in calculations* · *can't be deleted, only
switched off*.

### Reproduced first (tip `ccfd2bf5d`, `2.465.0`, Chromium, scratch PostgreSQL 16 `cf7_walk`)

* Placing *Roof Material* (Premises, Metal / Tile / Shingle) on the portal form: `PUT …/placement
  {"PORTAL_NEW_SERVICE": "input"}` answered **422 `settings.customFields.slot_not_rendered`**; the served slot
  list had **no** `PORTAL_NEW_SERVICE` row for premises (not rendered, not offered); the Placement dialog did not
  offer *Ask the customer* (`cf7_before_1_placement.png`, lane scratchpad).
* The portal's step 2 for 2201 Cane Island Pkwy drew no question (`cf7_before_2_portal_step2.png`); the draft
  read served no field list; `PUT …/applications/{token} {"custom_data": …}` answered **422
  `portal.application.fieldNotAccepted` `custom_data`**.
* Customers has no `PORTAL_NEW_SERVICE` slot at all, although the ruling names customer fields for the form.

### Defects filed before fixing

* `DEF-CUS-9214` — Request detail lists the request's copy only for fields placed on Staff New Request, so a
  field asked only on the portal would be on the request and invisible on its page (gap 2).
* `DEF-CWP-9215` — the portal form kit prints a field's error but neither ties it to the box nor announces it
  (accessibility questions 3 and 7).

### Task table

| # | Task | Status |
|---|---|---|
| 1 | `portal/0014` — `portal_application_drafts.custom_data jsonb NOT NULL DEFAULT '{}'` 🔒 | **DONE** `2.466.0` |
| 2 | `SLOTS`: `PORTAL_NEW_SERVICE` rendered for accounts and premises; declared + rendered for customers | **DONE** `2.466.0` |
| 3 | The draft serves ONLY the fields switched to *Ask the customer*, in a public shape (key, label, help, type, options, required) — never the placement map, an id, a *Don't ask* or switched-off field | **DONE** `2.466.0` |
| 4 | Draft save validates against ONLY the asked fields (an internal key is refused as an unknown one), merges per key; a draft saves with a required answer missing; Send is held naming the step | **DONE** `2.466.0` |
| 5 | Send hands the still-asked answers to customers' `create_from_portal(custom_data=…)`, which judges them again against the portal-asked fields and stores them on the request's own copy | **DONE** `2.466.0` |
| 6 | Portal screen: property questions on step 2, the applicant's on step 3, both restated on step 4; required marked, held, and the error on its box, tied and announced (`DEF-CWP-9215`) | **DONE** `2.466.0` |
| 7 | Request detail shows portal-typed answers read-only (`DEF-CUS-9214`); Approve copies them with the W6 pick | **DONE** `2.466.0` |

Judgments: decision log 2026-10-02 *"Custom fields on the customer portal's new-service form (`CR-161-BRC10` W7,
`2.466.0`)"*.

### What an applicant and a clerk see

Brazos Bend switches *Roof Material* (Metal / Tile / Shingle, required) to *Ask the customer* in Settings —
*New-service form* under *Customer (portal)*, starting on *Don't ask*. On the portal, step 2 for 2201 Cane
Island Pkwy draws *ABOUT THE PROPERTY · Roof Material \** with *Choose one*; leaving it blank says *Answer this
question.* on the box and holds Continue (*Answer the questions marked \*.*). She picks *Tile*; Check and send
reads *Roof Material Tile* under *The service*; Send gives a reference. The request's Applicant tab reads
*Roof Material Tile*; Approve against `P-00002` (already *Metal*) shows *Existing: Metal | Requested: Tile* with
Existing chosen; picking Tile makes the property read Tile. *Meter vault code* (Don't ask) is on neither the
screen nor the portal's API response; Pine Hill's portal shows neither field and cannot open the draft.

### The eight accessibility questions (`22-product-maintenance-process.md` §6), for the boxes W7 adds

| # | Answer |
|---|---|
| 1 Keyboard only | Yes — native `select`, `input` and checkbox controls in DOM order; Continue / Send are buttons. |
| 2 Focus visible | Yes — the kit's own controls, unchanged focus styling (no outline removed). |
| 3 Labels attached | Yes — `label for` on every box (a multi-select is a `fieldset` with `legend`); the box carries `aria-required`, and `aria-invalid` + `aria-describedby` naming its error line (`DEF-CWP-9215`). |
| 4 Headings | Unchanged page structure; each block is a section title under the step's one `h1`. |
| 5 Contrast | The kit's own tokens (`text-neutral-800`, `text-danger-700`), unchanged. |
| 6 Narrow / enlarged | Full-width boxes in the existing single column; no fixed widths added. Not measured at 320px in this wave. |
| 7 Announced | Yes — the error line is a polite live region present before it fills, so *Answer this question.* is read aloud when it appears. |
| 8 Money | Not a money step; nothing is charged, and Check and send restates every answer with a Change link. |

Residual, stated: the OLDER portal boxes are announced (the live region is in `FormField`) but not yet tied by
`aria-describedby` — `DEF-CWP-9215` is *partially fixed*; each takes the two props as it is next touched.

### Proof

* **Reproduced first** at `2.465.0` (above): 422 `slot_not_rendered`, no portal slot served, no question on the
  form, `custom_data` refused (`cf7_before_1_placement.png`, `cf7_before_2_portal_step2.png`, lane scratchpad).
* **Tests, red first:** `tests/test_cr161_w7_portal_custom_fields.py` against a `git archive` copy of the tip
  `ccfd2bf5d`: **17 of 18 red**, the eighteenth (*a required field not asked on the portal never blocks it*) green
  as the regression guard it is. After: **19/19 on PostgreSQL 16** (`config.settings.pgtest`) with W6's 17 beside
  it (36 passed), and 18 + 1 PG-only skipped on SQLite; W1 25/25 (its pairing test now reads
  `<ApplicationCustomFields entity=… screen=…>` and pins *nothing waits*); W1, W6, W7,
  `test_def_cwp_9163_9167_start_service` and `test_us_cwp_013_about_you` together 83 passed. **Mutation reds**
  (each file restored, sha256 compared): the public view serving the whole definition, and the customers door
  skipping the internal-key check, each turned its case red; front end — the box losing `aria-describedby`, the
  payload always carrying `custom_data`, and Request detail reading only New request — each turned its case red.
  `ApplicationCustomFields.dom.test.tsx` 7, `requestCustomFieldsW6.dom.test.tsx` 9; the portal, components,
  styles, i18n and tenancy vitest suites 223 files / 2894 passed. `tsc` clean, eslint clean on every touched file.
* **Browser** (Chromium, `vite build --mode wolocal`, scratch PostgreSQL 16 `cf7_walk`):
  `10-scripts/cr161_w7_portal_custom_fields_walkthrough.mjs` **49 passed, 0 failed** — screenshots `cf7_1` … `cf7_9`
  in the lane scratchpad. Audit row read back: `{"kept": {}, "picks": {"premises": {"roof_material": "requested"}},
  "copied": {"premises": {"target": "P-00002", "values": {"roof_material": "Tile"}}}, "waiting": {}}`.

### Rollback

Revert the W7 code commit. `portal/0014` reverses by dropping the draft column: answers typed on an unsent
portal form are lost with it; answers already sent stay on their service requests' own copy.
