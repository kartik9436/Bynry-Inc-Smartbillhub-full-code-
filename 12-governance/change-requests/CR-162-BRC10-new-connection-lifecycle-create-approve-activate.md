# CR-162-BRC10 — New Connection lifecycle: what Create makes, and how a request is approved and activated

**Raised:** 2026-10-02, by the Product Owner, in chat, as part of the New Connection
programme (decision-log row of 2026-10-02 headed *"NEW CONNECTION — THE PO'S
SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*, commit `56eb54ba9`). That row is the
ruling; nothing it settles is put back to the PO (hard-won law 13).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **162**
against the remote and `--verify 162` reported it free on every branch.
**Lane:** NC-A (the lifecycle). Sibling lanes own the rest of the programme: NC-B the
Charges, Documents, Messages and Work tabs, Raise work order and Add fees; NC-C the
five-step wizard screens; a defect lane the Done screen.
**Classification:** a **CHANGE** (`13-change-process.md` §1). The product did what
`BR-CUS-1114` (2.442.0) and `BR-MET-116` said; the PO moved the agreement.

## 0 · What arrived, in the requester's words

> *"Q1–Q8 as recommended, go"* (the eight answers in the decision-log row above)

> *"premises is not yet active - it will be activated at the time of approval of new conenct request"*

> *"we are creating master acocunt on Premsies and not on unit that is out rule"* ·
> *"Owner customer record = master account - we discussed this before"* ·
> *"regular account on these unit wil be created using move in that is correct"*

> **Q1** — the master account is decided by PREMISES TYPE, not by how many units are
> entered: apartment complex, commercial building, mixed-use and any type able to hold
> several units get a master account (and the owner customer) even with one unit entered —
> created PENDING at Create, ACTIVE on approval; a single-family home gets none.

> **Q2** — a gate inspection that has not passed blocks activation of its unit; every other
> open work order only warns.

> **Q3** — a To-do tab replaces Mark/Close outstanding; Release → Resume.

> (added the same day, with "go") *"in to do also keep notes - allow user to add notes"*

### The items this CR carries (numbering from the coordinator's list)
1 Premises created Pending · 2 master account by premises type [Q1] · 5 Approve with the
work-order check, the warning and the gate [Q2] · 6 status changes on approval · 7 Add unit ·
8 Add service as a proper form · 9 To-do tab, Release → Resume [Q3] · 27 premises at Create,
Pending · 34 master Pending until approval · 35 the account page's Build panel action ·
36 Units tab columns · 38 activation per unit/service · 48 notes on the To-do tab.

### Received after "go", the same day, and built (verbatim)

> Premises-type setting — *"when we say premises type has account type - master or regular
> attached … then when you create account dont you want to use this field when you are creating
> accounts"* · *"we will need this on screen in setting so user can provide the it and set it"*.

> Build tab — *"when we have new connect request -we are traking the progress from detail of new
> connect hense as shown in screenshot build ta on premises is not required ;when premises is in
> pending status and if you have new connect request asoscaiated to it then you can show link for
> request to improve interaction"*.

> Notes — *"in to do also keep notes - allow user to add notes"*.

> Move-in before approval — first *"this will not ahppen sicne presies and unit is still in pending
> status"*, then **ruled B**: *"B: allow it. The account opens, but billing waits until the unit is
> activated"*, confirmed *"this is correct"* on the worked comparison.

## 1 · Status

**DONE — version `2.460.0`.** The thirteen judgments where the rulings stopped are the decision-log row
of 2026-10-02 headed *"`CR-162-BRC10` — THE NEW CONNECTION LIFECYCLE"*; the plain-English review
sentence and the 🔒 files are the review-ledger row of the same date.

## 2 · What changed, item by item (before → after)

| # | Before | After |
|---|---|---|
| 1, 27 | The property a build created was born **Active** (the wizard already created it at Create, not at draft start — `DEF-2961` was the API door only). | Born **Pending** (`premises.status`, one of its four existing values); **Active** on the build's first activation. An address already on file keeps its status. |
| 2 (Q1) | 2.442.0 counted the units entered: Haustin Towers (apartment, 1 unit) got no master account. | Each premises type carries an **Account type** (`premises_types.account_kind`, `metering/0066`), seeded Master for apartment complex, commercial building, mixed-use, mobile-home park, government building and Regular for single-family; **required, no default** on a new type; a column on Settings; *Applies to new premises only.* on edit. Every master door reads it through `customers.services.master_account_allowed_at_premises`; an unanswered type falls back to the two-home count. The wizard copies the type's answer onto the draft (`NewConnectWizard` → `buildOpensOwnerMaster`); the property's Common areas tab and the request page read the server's own answer. |
| 34, T2-11 | The owner's master account opened **Active** at Create — and the property never named it (`DEF-MET-9201`: *Master a/c: Needs an owner* beside a live master account, found by this walk). | Opens Active, takes the charges inside the commit, then is **held Pending** (`hold_new_master_pending`); **Active** on the first activation. Its customer reads its status through it. `create_owner_account` now declares it on the premises (`BR-MET-1181`'s writer) where the premises names none. |
| 5, 6, 38 (Q2) | *"Activate units — Nothing can activate a build yet"*; `transition_service` had no caller. | **Approve** (header) and **Activate / Activate selected / Activate all ready** (Units tab) open one dialog; `POST /connections/{id}/activate` (`metering.connection_activation`): service → Activated via `transition_service`, assets → Installed and dated (`assets.services.install_build_assets`), unit Active when all its services are, premises + master Active on the first, request Partly activated / Activated, messages fired, one transaction, idempotent, audited. Gate not passed blocks its unit; other open orders warn and stay pending; open to-dos listed. Refused on a draft, cancelled or held build. |
| 36, T2-13 | Kind / Asset type / Size / Qty / Work order empty (three lists joined by label; assets served with no service or size). | One server read (`GET /connections/{id}/activation`): Unit, Unit type, Utility service, Asset type, Size, Qty, Asset ID with its stage, Work order, State, Activate. The commit now keeps `units[].unit_type` (validated by `BR-MET-084`). |
| 35, T2-12 | The account page's Build panel had a dead *Activate units*. | **Removed** with the property's Build tab (PO). A Pending property / master account links to the request. |
| 7 | — | **Add unit** (label, unit type, services) → `POST /connections/{id}/units`. No meter or plan is fitted (the unit's page does both). |
| 8 | *Add service* opened an inline chooser. | A proper form (service + unit or *Whole build*). The inline chooser (`BuildAddServicePrompt`) had no caller left and is deleted. |
| 9, 48 (Q3) | *Mark / Close outstanding* in the More menu; no notes. | **To-do tab**: to-dos and notes, newest first, who/when, *Mark done*, *Reopen*, author-only *Edit note* (audited, no delete); notes in `connection_todos.kind` (`metering/0065`). Overview: *To-dos open: 2*. *Release* → **Resume**. |
| ruled B | A move-in before approval would have billed from the move-in date. | Allowed; the days before activation are dark days in `BR-CUS-103`'s sense (`customers.activation_windows`, joining `service_off_windows` and the bulk Check's prime) — no money math changes; the account says *Billing starts once the unit activates.*; cancelling the build lists the accounts open on its units and closes none. |

## 3 · Proof

- **Red first (law 7), each guard broken in place and its test run:** type rule → 2 failed (`master_needs_two_units` raised for the apartment, the single-family build DID NOT RAISE); master hold → `'active' == 'pending_activation'`; gate → `None == 'WO-0003'`; billing waits → `[] == [(2026-10-05, None, ['battery','solar'])]`; assets install → `0 == 2`; the warning → DID NOT RAISE. Each restored byte-for-byte and re-run green.
- **`DEF-MET-9201`, red first:** `assert 'None' == '01a0fe37-95c9-…'` (the premises' `master_account_id` after an apartment build), green after the fix; 15 neighbouring suites that call `create_owner_account` re-run one at a time, every red among them dated below.
- **`tests/test_cr162_new_connection_lifecycle.py` — 17 passed on SQLite; 16 passed on PostgreSQL 16** (`--ds=config.settings.pgtest`, before the unit-type case was added; superuser connection, so row-level security is not what this run proves). Touched suites green one at a time: `test_portal_request_to_active` 16, `test_br_cus_1114_master_only_multi_unit` 5, `test_w6_commit_orders_and_owner` 8, `test_def_cus_8020_8021_the_create_button` 7, `test_def_met_6110_6111_refusal_on_its_step` 11, `test_cr056_w1_account_on_the_address` 7, `test_br_met_1181_premises_master_account` 25, `test_br_cus_068_master_accounts` 9, `test_def_met_5844_add_premises_owner_account` 13.
- **Gates:** `eslint` (G98) clean after removing the dead `BuildAddServicePrompt` import; G31 PASS; G13, G32 and G33 print the same findings on this branch as on `14702b724` (the tip before this lane) — this lane added 17 refusal sentences, none over six words (572 over, before and after); G15 0 missing keys. Golden engine tests `tests/golden` 25 passed, 1 xfailed, untouched.
- **Front end:** `tsc` clean; vitest one file at a time — BuildDetailTabs 32, BuildDetailPage 16, PremisesPage 65, AccountDetailPage 107, SettingsReferenceData 45, NewConnectsTab 50, ParkedBuildFinishesItself 11, buildViews 29, buildRecordPanels 19, buildRecordHolds 5, AddServiceChoice 10, BuildDetailDialogs 10.
- **Chromium walk** (`10-scripts/cr162_new_connection_lifecycle_walkthrough.mjs`, `vite build --mode wolocal`, PostgreSQL 16 scratch DB `nca_walk`, dropped at the end): Settings shows *Account type* (Apartment complex = Master account, Single-family = Regular account); adding *Mobile home park* with no answer → *Choose the account type.*; saved with Master. G Trade Tower (apartment, 2 units, electric + water): property Pending with *Open request*, no Build tab; master account *Pending activation* with the link; Units tab columns; Unit 1's orders complete → Approve → *Ready to activate: 2* and *2 of 4 not complete: WO-0047, WO-0048* → *Activate what is ready* → **Partly activated** (CON-26-0131), Unit 1 Active, meters M-00007 and M-00008 **Installed**, property Active, master account AC-2026-00055 Active; the rest complete → *Activate all ready* → **Activated**; To-do tab note above to-do. 8 Wren Lane (single-family, CON-26-0132): no master account, property Pending with its link. **21 checks, all pass** (second run; the first run's one failure was the walk's own regex reading run-together page text, fixed to ask for the request link and the status word instead). Screenshots `nca_01`–`nca_14`, each opened.
- **Dated reds this lane did not cause** (each red on the tip before this lane's commit): `test_cr056_w5_new_connect_premises` tc23e/tc23f (`identity_kind_required`, since `6c722aeb1` 2026-09-01); `test_w6_connections::…gate_flag_is_stamped…` (`work.order.template_not_published`, since `4b1090ed0` 2026-09-05); `test_def_236…every_declared_list_has_a_card` (`owner_categories`, `bank_rec_difference_reasons`); `test_new_connect_step7_messages::…letter_that_asks_for_money…` (`quote_total` no longer recorded, since `d7a40eea5` 2026-09-28). `test_br_met_040_common_area::…unplanned_unit` (`NotFoundError` in `resolution_shadow._premises_facts`), `test_cr040_b7_estate_money_shape` 3 cases, `test_def_cus_6135…` 2 cases (`park_row() missing 'today' and 'zone'`), `test_us_wrk_002_doors::…no_common_area_gets_no_master_account_by_name` (`identity_kind_required`) — each run on `14702b724` with the same result. Gates: G17 (9168/9169 taken by two CR-161 lanes), G67, G106 — none names a file of this lane.

## 4 · Handed to the sibling lanes (not built here, on purpose)

- **Step 5's three messages still queue at Create** (`queue_on_commit`); the approval now fires them too (never twice). Moving the Create-time queueing and the *When = On approval* wording is the Messages lanes' (NC-B tab, NC-C wizard).
- **The wizard does not yet send `units[].unit_type`** — the commit keeps it when it does (NC-C item 15).

## 5 · Version and rollback

**`2.460.0`** (`allocate.py version --bump change`, verified at push). **Rollback:** redeploy 2.459.1's
code and `manage.py migrate metering 0064` (drops `connection_todos.kind` and
`premises_types.account_kind`; export notes first — they would read as to-dos). Builds created on
2.460.0 keep a Pending property and master account until activated by hand.
