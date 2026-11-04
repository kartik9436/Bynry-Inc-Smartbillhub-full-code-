# EP-CUS-11 — Parked wizard drafts, on each flow's own tab (`S17.2`)

**Module:** customers (product name: Accounts) · **Wave:** CR-035 (`2.51.0`) · **Screens:** S17.2 (the parked-drafts panel on Move-ins · Move-outs · Transfers · Disconnects · New connects) · **Status:** draft

> ⛔ **RE-POINTED, NOT WITHDRAWN — CR-035 · AMENDMENT 1, PO 2026-08-26.** This
> epic was written HOURS before the ruling and describes the behaviour as a
> **ninth Accounts tab**. Verbatim: *"We dont need seperate tab for this - this
> will be directly on each request Request, Connect, Move IN move Out, Trasnfr,
> Disconnect - seperate queue not reequired"*, then **"yyes"**.
>
> **The behaviour is keeping its home rather than disappearing**, so this epic
> and its story keep theirs. Read every *"tab"* below as **the panel pinned above
> that flow's own worklist** (`07-frontend/src/features/customers/
> parkedDrafts.tsx`, mounted five times by `AccountsListPage`). Four statements
> are now FALSE and are corrected here rather than rewritten away — the rest of
> the epic, including every acceptance criterion, is unchanged and still passes:
>
> | Said below | True since 2026-08-26 |
> |---|---|
> | *"the ninth tab of `AccountsListPage`"*, `WaitingOnTab.tsx` | **`parkedDrafts.tsx`**, a panel on five tabs. `WaitingOnTab.tsx` is DELETED; the strip is back to B18 §4's eight |
> | *"a mine/everyone switch"*, `?mine=1` | **Withdrawn.** The ruling *"dissolves the mine-versus-everyone's question entirely"* — BR-SHL-048's *"the clerk's own list"* meant **there and nowhere else**, not a filter. Every parked draft for the flow shows, with **who parked it** on the row |
> | *"eight columns"* + the column-preference key | **No table at all** — a pinned list of draft rows, so no paging, no sort control and no column chooser, and therefore **no `screenId` and no column preference**. `table.S17.waiting-on.columns` is shipped and now **orphaned; it is left stored and unread** (A1 addendum) |
> | *"an empty state with a disabled CTA"* | **The panel is ABSENT when its flow has nothing parked.** An empty block standing permanently on five tabs teaches a clerk to scroll past the place a warning will appear; the tab's own empty state already covers "there is nothing here" |
>
> **And one requirement the amendment ADDED, which this epic could not have had:
> the tab's count must not lie.** The panel renders **outside the tab's table**,
> so the list keeps the server's record count; the parked figure is stated
> separately on the panel in words (*"1 parked · not started yet"*) beside a
> sentence saying it is not in the list below. Proved in
> `parkedDrafts.dom.test.tsx` (*"THE COUNT DOES NOT LIE: three move-ins stay
> three with a draft parked"*) and clicked in
> `10-scripts/render-checks/cr035-park-clickthrough.mjs` (35/35).
>
> **The asymmetry that made this the whole risk, recorded once:** a parked
> **service request** is the SAME ROW annotated — `waiting_on`, `park_note`,
> `remind_on`, `parked_at`, `parked_by` are COLUMNS on
> `customers.ServiceRequest` — so the **Requests** tab needed no change at all
> and got none. A parked move-in, move-out, transfer, disconnect or new connect
> is **not a row at all**, which is why `wizard_parks` had to exist. Two kinds
> of thing, drawn as two kinds of thing.

> ⚠ **THIS EPIC WAS WRITTEN AFTER THE CODE, AND SAYS SO — hard-won law 8, the
> same posture EP-CUS-08 takes.** The tab shipped on **2026-08-26** in `2.51.0`
> with both halves built — `apps/tenancy/wizard_parks.py` + `wizard_parks_api.py`
> behind `GET/POST /wizard-parks` and `GET/PATCH/DELETE /wizard-parks/{id}`,
> `WaitingOnTab.tsx` mounted as the ninth tab of `AccountsListPage` — and **no
> screen id and no story owned it**. The source file filed the finding itself:
> *"**A story and a screen id are OWED** — hard-won law 8, and it is stated
> rather than quietly skipped."* This epic and A1's `S17.2` addendum close it.
>
> **Every acceptance criterion below is RECOVERED FROM WHAT EXISTS** and checked
> against the test that asserts it. Where CR-035 step 6 asks for something the
> code does not do, §8 records it as NOT BUILT with what tracks it. Nothing here
> is an aspiration.

## Scope

**In:** the read-and-discard worklist of **parked wizard drafts** — CR-035 step 6
row 5, verbatim: *"one 'Waiting on' surface with the reason, the note, the reminder
date and the **age**, which is the only thing that stops a draft sitting forever."*
Eight columns, a mine/everyone switch, two standing notes, a `Resume` link into the
flow's own wizard and a danger-tier `Discard`. An **embedded tab** inside
`AccountsListPage` owning no query string (DEF-664).

**Out:** the **park control itself** (built in `WizardFrame.tsx`, CR-035 step 6 row 3
— the panel, the nine reasons, the note and the reminder date) · the **resume**
rehydration inside each wizard (step 6 row 4, each wizard's own file) · the
**store, service and API** (step 6 rows 1–2, `apps/tenancy/`, tenancy-hosted) ·
**reminder DELIVERY** — `remind_on` is stored and nothing sends it (**DEF-758**),
and the screen says so rather than drawing a bell · a **KPI strip** · **search**,
**filters** and **sorting** (the contract serves none) · **export** · any surface
outside this tab: BR-SHL-048 confines a parked draft to this list *"and nowhere
else in the product"*.

**Tables:** **`wizard_parks` only**, and it is **tenancy-hosted, not
customers-owned** — five flows across two modules park into it, so parking it in
either would put half the rows in a module that does not own them
(`models.WizardPark`: *"hosting ≠ owning"*, the `user_preferences` / `bell_events`
posture). This screen therefore reads through **tenancy's own service**
(`wizard_parks.list_parks` / `row_dict`) and crosses no other module: **there is no
join to `accounts`, `units` or `premises` and there cannot be one** — BR-SHL-048 (a)
gives the table no foreign key to reach them by.

## Capability matrix (B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| **S17.2** `ACC-01` (tab) | **NONE.** The CR-035 contract serves no `q`, so `searchFields` is absent and **no box renders at all** (BR-SHL-010). ⚠ Deliberately no `searchPlaceholder` either — a B14 rule 19 prompt declared for a control that does not exist is a dead catalogue key (G18) | **NONE declared.** The one view choice — **mine / everyone** — is a two-state `Button` with `aria-pressed`, *not* a table filter: the filter bar serialises `f.<name>` into the URL (BR-SHL-011) and this tab owns no query string (DEF-664) | **Newest first**, fixed by the server (`list_parks` orders `-parked_at`). The footnote states it: *"Newest first — the longest wait is at the bottom of the list."* | **NONE** — `list_parks` takes no `sort` and no column is declared `sortable` | **Default (8, all visible):** WAITING ON · WORK · FOR · STEP · NOTE · REMIND ON · WAITING · ACTIONS. **Available: none extra** — every column is something the draft itself recorded | **TWO.** `Resume` (icon **LINK**, B14 r15 — middle-click matters on a worklist) → the flow's own wizard at `?parked=&step=`. `Discard` (icon button, **danger tier**, B14 r6) → confirms first (IS-6), then `DELETE` | **NONE** | **NONE** |

## Stories

---
id: US-CUS-031
epic: EP-CUS-11
module: customers
screens: [S17.2]
wave: 0                  # CR-035 (`2.51.0`) — outside B12's W0–W8 numbering
status: ready
blocked_by: []
depends_on: []           # ⚠ NOT US-CUS-004. The real upstream is CR-035's STORE, PORT and RESUME
                         # (step 6 rows 1-4), and NO STORY OWNS ANY OF THEM — they shipped in 2.51.0
                         # storyless, which is the same law-8 gap this epic closes for the LIST half
                         # only. Naming US-CUS-004 (the move-in wizard, still `draft`) would invent a
                         # dependency that is not one AND make a `ready` story depend on a draft.
                         # The three missing stories are REPORTED in §8.
journeys: []             # no journey reaches a parked draft; J26 stops at the service request's own park
rules: [BR-SHL-010, BR-SHL-011, BR-SHL-012, BR-SHL-013, BR-SHL-025, BR-SHL-034, BR-SHL-046, BR-SHL-047, BR-SHL-048]
golden_tests: []         # no money is computed, displayed or stored on this screen
finance_calc: none
---
### US-CUS-031 — The Waiting-on list: eight columns about drafts that are not records, and an age that is the whole feature

**1 · Details** — As a **billing clerk**, I want the Accounts screen's **Waiting on** tab to list every job I parked half-finished — what I am waiting for, my note, the day to chase it and **how long it has been sitting** — so that *"in practical life all these requests do not close in a day"* (PO, CR-035) stops meaning *abandoned*.

**Entry:** S17 Accounts → tab **Waiting on**, addressable as `/{tenant}/accounts?tab=waiting-on`. The URL matters and is not decoration: it is what a reminder will link to on the day one is actually sent, and it is where a wizard's own `onParked` navigates today. **Exit:** `Resume` → the flow's own wizard route carrying `?parked=<id>&step=<n>`; `Discard` → back to this list, one row shorter.

**What it calls:** `GET /wizard-parks?mine=1` → `apps/tenancy/wizard_parks_api.wizard_parks` → `wizard_parks.list_parks(flow=None, mine_user_id=…)`, serialised by `row_dict`. `DELETE /wizard-parks/{id}` → `wizard_parks.discard`. Both gated `AdminOrClerk` at the view **and** re-gated `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` at the service (defence in depth, BR-SHL-025) — **an Executive can neither read this list nor park**.

**⛔ IT IS NOT A LIST OF ACCOUNTS, AND EVERY COLUMN CHOICE FOLLOWS FROM THAT.** BR-SHL-048 (a): *"no report, ageing bucket or occupancy query can reach a parked draft by joining to it."* So there is deliberately **no `Account`, no `Unit status`, no `Balance`** — a frontend lookup off `subject_ref` would be that forbidden join with extra steps. The `FOR` cell prints **the words the clerk saw when they parked**, which is also what keeps the list readable after a premise has been renamed. The proof is asserted as a **network trace**, not a code review: the tab's only tenant-scoped call is the draft store.

**⚠ THE AGE IS THE FEATURE.** BR-SHL-048 (c) accepts a cost in writing and names its only mitigation: *"a parked move-out is invisible, so the account KEEPS BILLING … the remind-on date and the age on the 'Waiting on' list are what stop a draft sitting forever."* So `age_days` is the **SERVER's** figure (`wizard_parks.age_days`, `floor((now − parked_at)/86 400)`, negatives clamped) and never the browser's clock — two clerks in two time zones must not read different ages off one row. The same arithmetic is `parkAgeDays` in `WizardFrame.tsx`, because one figure rendered twice by two implementations eventually disagrees by a day.

**⛔ AND NO THRESHOLD IS INVENTED.** It would be one line to paint a row red at fourteen days, and fourteen is a rule nobody made: BR-SHL-047's unit-blocking limit is **MOOT** under BR-SHL-048 (c) and no replacement limit was ruled. The screen shows the number and refuses nothing.

**⛔ NOTHING SENDS THE REMINDER, AND THE SCREEN SAYS SO (DEF-758).** `remind_on` is a date this product stores and does not act on — there is no email, SMS or print adapter in this release. A bell, or a *"reminder sent"* claim, would be hard-won law 1 wearing an icon. A standing note above the table says what the date **is** good for (reading this list) and implies no delivery.

**⚠ MINE BY DEFAULT, EVERYONE ONE CONTROL AWAY — and both halves are the ruling.** BR-SHL-048 names *"the clerk's own 'Waiting on' list"*, so the tab opens on `?mine=1`. It does not stop there, because this product is for **a team of 10–20 staff serving up to 40,000 accounts** (ICP ruling 2026-09-06; the premise read *"1–2 staff serving under 3,000 connections"* until then): a draft parked by the colleague who is out today, invisible to the one covering the desk, is precisely the draft that sits forever. ⚠ **THE RULING STRENGTHENS THIS DESIGN RATHER THAN WEAKENING IT, WHICH IS WHY THE CONCLUSION IS UNCHANGED.** The argument was never about the number being small — it is that work parked by one person must be reachable by another — and **at 10–20 staff instead of 2 it matters more, not less**: with two people the covering clerk knows what the other was doing, and with twenty they do not. ⚠ **What DOES need re-reading at the new size is the LIST ITSELF**, because *"everyone one control away"* means a query across every clerk's drafts at a utility 13× larger than the one this was written for — it must stay paginated and tenant-indexed (`NFR-3`, `NFR-30`), and it is not exempt from the caution in `DEF-PAY-4221`.

**⚠ A NINTH TAB WHERE B18 §4 DRAWS EIGHT.** B18 predates CR-035 by ten days and could not have drawn a surface for a store that did not exist; **B18 §4 and §5 are amended, dated, rather than left disagreeing with the product** (see the amendment note in B18 §4). The placement argument — five of the eight tabs are exactly the five parkable flows, and *the place a clerk resumes work is the place they started it* — is `WaitingOnTab.tsx` §1.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-048 | **A parked wizard changes nothing until it is executed.** PO 2026-08-26, verbatim: *"Option A - Unitl move in executed, no records updates."* **(a)** no FK to the record it names — ids are COPIED values · **(b)** re-validated at execution, never trusted from the park · **(c)** BR-SHL-047's unit-blocking half is MOOT, and the accepted cost is that a parked move-out is invisible. | **CONFIRMED** — PO 2026-08-26 (CR-035, closing DEF-746) |
| BR-SHL-046 | **ONE declared step list** drives the wizard's bar, this list's `STEP` column and where a resume lands. A skipped step keeps its number. Hence `2 of 5` for a move-in and `4 of 6` for a move-out, each counted against its **own** flow's list — never a shared constant. | CONFIRMED |
| BR-SHL-047 | Every wizard parks, move-out included (PO 2026-08-24, verbatim *"Park it"*). CR-035 is what makes it true for the five that had the control and no store. Its **open unit-blocking half is superseded** by BR-SHL-048 (c). | CONFIRMED · half SUPERSEDED |
| BR-SHL-010 | A capability that is not declared is not rendered — which is why there is **no search box** and **no sort glyph**: the contract serves neither. | CONFIRMED |
| BR-SHL-011 | The URL grammar clamps and never errors (`stepFromParam`). ⚠ **This embedded list owns no query string** — DEF-664's deliberate trade; the tab id `?tab=waiting-on` is the **Accounts page's**, not this table's. | CONFIRMED · the embedded exception **PROPOSED** (DEF-664) |
| BR-SHL-012 | The framework owns the empty / loading / failed states, and **a failed read never renders the empty state** — which would assert *"you have none"*. | CONFIRMED |
| BR-SHL-013 | Column preferences key on the screen id. ⚠ Here the stored key is **`table.S17.waiting-on.columns`** (`tableTypes`' two-tables-one-screen convention, `SET-05`/`SET-05.cycles`) while the A1 ticket id is **`S17.2`**. Both are printed in A1's addendum; the key is **not renamed**, because renaming it orphans every saved column set. | CONFIRMED · the two-name split **REPORTED** |
| BR-SHL-025 | A control that cannot act is **disabled carrying its reason**. The empty state's `Park a job` CTA is exactly that: a live button would have to invent a destination and answer *which of the five?* — a question nothing on this screen asked. | CONFIRMED |
| BR-SHL-034 | ONE date formatter, in the tenant's own format — `REMIND ON` renders through `DateCell`, never a raw ISO string. | CONFIRMED |
| B14 r6 / r15 / r20 / r21 | Danger tier on a destructive commit · **icons** with accessible names for row actions (`Resume` a **LINK**, not a button) · one table type · Tailwind utilities and **no stylesheet class** (G31). | RATIFIED |
| CLAUDE.md hard rules 1, 4, 7 *(cited, not restated)* | Tenant scoping under RLS `FORCE` (proved cross-tenant, both API and RLS probe) · **hard rule 4 has nothing to say here** — a half-typed form is not an issued invoice, a payment or a journal line, which is *why* a draft may be freely edited and discarded · every park, resume, update and discard writes `audit_log`, **with no applicant PII in the payload**. | CONFIRMED — hard rules |

**3 · Test Cases**

*(Backend: `06-backend/tests/test_cr035_wizard_parks.py`. Frontend: `07-frontend/src/features/customers/WaitingOnTab.dom.test.tsx`. Rendered proof: `10-scripts/render-checks/cr035-park-clickthrough.mjs` (30 checks) and `cr035-resume-clickthrough.mjs` (11), real Chromium over the real `vite build`.)*

| TC | Scenario | Expected | Asserted by |
|---|---|---|---|
| TC-1 | A clerk opens Accounts → **Waiting on** with one parked draft | All eight columns render: the reason as a pill, the flow, the subject label, `n of m`, the note, the reminder date in the tenant's format, the age in days, and the two icon actions | FE *"renders the reason, the note, the reminder date, the step and the AGE"* · RC *"the reason / the note / the age / the step is on the row"* |
| TC-2 *(the BR-SHL-048 (a) case)* | The tab is mounted and its network is recorded | The **only** tenant-scoped list call is `GET /wizard-parks`. **No `/units/…`, no `/accounts?f.unit_id=…`, no `/premises/…`** — a draft is invisible to the rest of the product by construction, not by every future author remembering to exclude it | FE *"it asks the store and NOTHING ELSE — no unit, no account, no join"* · RC *"the list called the draft store and nothing else"* (the call list is printed) |
| TC-3 | `STEP` for a move-in parked at 2, and a move-out parked at 4 | `2 of 5` and `4 of 6` — each counted against its **own** flow's declared list, and a **skipped** move-out step still keeps its number (BR-SHL-046) | FE *"counts a move-in against five and a new connect against nine"* · *"a SKIPPED step is still one of the six"* · RC *"counted against the move-in's OWN five steps"* |
| TC-4 | `Resume` is clicked | It is an icon **LINK** with an accessible name, pointing at the flow's own route: `/{tenant}/transfers/new?parked=park-1&step=1`. The wizard lands on **step 1 as the ACTIVE step**, with what was typed back in **editable inputs**, and the steps ahead **still locked** — resume unlocks nothing (BR-SHL-048 (b)) | RC *"Resume opens the flow's own wizard with `?parked=`"* · *"it lands on the step it was parked at"* · *"the steps ahead are STILL LOCKED"* · *"it is in an INPUT, editable, not printed as read-only text"* |
| TC-5 *(BR-SHL-048 (b))* | A resumed draft renders the product's state | The wizard **re-reads the product from the draft's COPIED unit id** (`GET /accounts?per=200&f.unit_id=u-12`) rather than trusting the park — everything in a draft was true on the day it was parked | RC *"the product was RE-READ from the draft's copied unit id"* |
| TC-6 *(destructive)* | `Discard` is clicked | It is **danger tier** and **confirms first** (IS-6), and the confirm names what is lost — the clerk's own typing — and says **nothing else changes**. On confirm the row `DELETE`s and really goes: the store returns **0 rows**, and the list falls back to its empty state | FE *"Discard CONFIRMS first, names what is lost, and then DELETEs"* · BE `test_cr035_consequence_c__discard_really_deletes` · RC *"the draft is gone from the store — 0 row(s)"* |
| TC-7 | The two standing notes | The screen says out loud that **a parked job has changed nothing** *(a parked move-in has not taken its unit; a parked move-out has not stopped its bills)* and that **no reminder is sent**. Both sit above the table, because each is true of every row | FE *"says out loud that a parked job has changed nothing, and that no reminder is sent"* · RC *"the screen says a parked job has changed nothing"* |
| TC-8 | The mine/everyone switch | Opens on **mine** (`?mine=1`), and one press re-queries for everyone's. It is a two-state button with `aria-pressed`, **not** a URL filter | FE *"opens on MINE and offers everyone's"* · BE `test_cr035__list_filters_by_flow_and_by_mine` |
| TC-9 *(negative — the honest-dash set)* | A draft with no subject, no note, no reminder, and one whose `parked_at` is null | Each renders **`—`**, which means **none**. ⛔ Never an empty cell, never `null days` — `age_days` is nullable and an interpolated null would print *"null days"* on the one column this feature turns on | FE *"a row with no note and no reminder renders NONE, never an empty cell or `null days`"* |
| TC-10 *(negative)* | `waiting_on` holds a value the nine do not have (a service request's own vocabulary reaches the same column) | It **still renders**, verbatim. The nine are what the SCREEN OFFERS; the column stores what was chosen, and closing the vocabulary would give one list two incompatible contracts for one column | FE *"`waiting_on` is FREE TEXT on the wire"* · BE `test_cr035__waiting_on_is_free_text_and_is_not_a_closed_vocabulary` |
| TC-11 *(negative)* | The tenant has nothing parked | The empty state renders with a **disabled** `Park a job` CTA carrying its reason — *"Jobs are parked from inside a wizard, not from here"* (BR-SHL-025 / law 2) | FE *"the empty state offers no live CTA"* |
| TC-12 *(negative)* | `GET /wizard-parks` fails | The failure state renders with a retry — **never** the empty state (BR-SHL-012) | `DataTable`'s own contract; ⛔ **no case in `WaitingOnTab.dom.test.tsx` asserts it for THIS tab** — **OWED** |
| TC-13 *(law 2)* | `/{tenant}/accounts?tab=waiting-on` is opened through the application's own route table | The tab strip mounts the list and it **calls** the endpoint — the tab is not merely built | FE *"mounts through the APPLICATION's own route table and tab strip"* |
| TC-14 *(isolation — API)* | A second tenant reads, patches and deletes another tenant's park id | **404 on every verb**, and its own list is empty | BE `test_cr035_isolation__another_tenant_cannot_see_read_patch_or_delete` |
| TC-15 *(isolation — RLS)* | The same, under the non-superuser probe role with `app.tenant_id` set to the other tenant | The row is **invisible at the database**, not merely filtered in Python | BE `test_cr035_isolation_rls__a_parked_draft_is_invisible_across_tenants` |
| TC-16 *(role)* | An Executive opens the tab and tries to park | **Neither read nor write** — the service re-gates below the view | BE `test_cr035__an_executive_can_neither_read_nor_park` |
| TC-17 *(audit — hard rule 7)* | Park, resume, update, discard | Four `audit_log` rows, and **no applicant PII in any payload** | BE `test_cr035__park_resume_update_and_discard_are_all_audited` · `test_cr035__no_applicant_pii_reaches_an_audit_payload` |
| TC-18 *(the whole-database case)* | One park is written | **Exactly one row in the whole database changes.** No account, no occupancy, no unit status, no bill — BR-SHL-048 in one assertion | BE `test_cr035__parking_writes_exactly_one_row_in_the_whole_database` |
| TC-19 *(the seeded fixture)* | A tenant seeded with sample data opens the tab on a demo | It is **not empty**: one parked move-in, with a reason, a note, a reminder date and a **visible age in days**. And the seeding writes **no account, no service agreement, no occupancy** — the unit it names still reads **vacant** | BE `test_cr035_fixture__the_seeded_draft_changes_nothing` (see §4) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** (`brazos`) for the suites; the demo fixture is the sample-data estate (`core/sample_fixture.py`).

**The seeded draft, and every value is quoted rather than chosen** (CR-035 step 6 row 6 — *"a seeded parked example, so the screen is not empty on a demo"*):

| Field | Value | Where it comes from |
|---|---|---|
| flow | `move_in` | B18 §5.5.7 draws the row as a move-in draft |
| subject | **`3450 Oak Ridge Dr · Unit 1`** = `SCW-U-207` | `CR030_SERVICE_REQUESTS['osei-move-in'].address_unit_as_given`, and it is the **one seeded unit that is VACANT and must stay vacant** — it is what makes `SR-26-0039` resolve `served_vacant` |
| step | **1 of 5** | `W5_MOVE_INS['mvi-osei'].step` — *"her move-in is `Waiting` at step 1"* |
| waiting_on | **`documents`** | `CR030_SERVICE_REQUESTS['osei-move-in'].waiting_on`, verbatim — and one of B18 §4.2's nine |
| park_note | *"Photo ID and the signed agreement still to come — chased 21 Aug."* | the same fixture row, verbatim |
| remind_on | tenant today **+ 2 days** | the same fixture row's `remind_on_days: 2`, verbatim |
| age | **5 days** | ⚠ the ONE derived value, and it is derived from a bound the design states: B18 §5.5.1's `OLDEST · 6 days · Alvarez, Rosa` caps any other in-flight move-in at ≤ 6, so 5 is the oldest a second draft can be while that drawn KPI stays true. **Stated as derived, not drawn** |

**⚠ THE FIXTURE IS PROVED BY A CHECK IT DOES NOT WRITE BOTH SIDES OF.** The premises-services defect hid for weeks because the seeder wrote both halves by hand so they always agreed. Here the seeder writes **one row**, and the vacancy of `SCW-U-207` is read back through **the product's own selector** (`services.active_account_for_unit`) rather than from anything the seeder recorded. **RED-proved 2026-08-26:** a scratchpad copy whose seeder also called `create_account` on the same unit failed TC-19 and the vacancy case (`assert {…'Osei, Grace'…} is None`), and the product itself then refused the replay with `BIZ-STATE customers.account.unit_already_occupied` (BR-CUS-017).

⚠ **AND ONE CLAIM THAT WAS CHECKED AND FOUND FALSE, CORRECTED RATHER THAN LEFT STANDING (law 1).** An earlier draft of this story said an *independent* suite would catch it. It would not: `test_cr031_service_request.py::test_a_served_vacant_unit_fits_a_move_in` builds its own premises and unit and never reads the sample estate, and `test_w5_move_in_out_cases.py::test_task_5_11…` reads `W5_BLOCKERS`, not the database. **`SCW-U-207`'s vacancy — which `core/sample_fixture.py` calls load-bearing for `SR-26-0039` — is asserted nowhere else in the repository.** That is a gap in the ESTATE's coverage, not in this fixture, and it is **REPORTED**.

**⛔ WHAT IS NOT SEEDED, AND WHY.** B18 §5.5.7 draws a **second** draft (`Alvarez, Rosa`, `2 of 5`, deposit *carried $153.50*). It is **not** seeded: the drawing gives it **no park reason**, its linked `SR-26-0044` carries `waiting_on: None`, and `wizard_parks` has a CHECK constraint refusing an empty `waiting_on` — *"a row with no reason is a park that forgot the only thing it is for"*. Seeding it would mean **inventing the one thing the park exists to record**. Recorded here rather than tuned away.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `WAITING ON` (identity) | S17.2 col 1 | CR-035 step 6 r5 · B18 §4.2's nine | `wizard_parks.waiting_on` | text, **free** | user-input | **never empty** (CHECK `ck_wizard_parks_waiting_on`); ≤120 chars; an unknown code renders verbatim |
| `WORK` | col 2 | CR-035 step 6 r1 | `wizard_parks.flow` | enum of 5 | user-input | CHECK `ck_wizard_parks_flow` — a typo cannot create a sixth flow nothing can resume |
| `FOR` | col 3 | BR-SHL-048 (a) | `wizard_parks.subject_label` — **denormalised on purpose** | text ≤200 | computed-display | empty → **`—`**; never joined, never re-read |
| *(not a column)* | — | BR-SHL-048 (a) | `wizard_parks.subject_ref` — **COPIED ids**, `{"unit_id": …}` | jsonb ≤32 KiB | user-input | resume looks them up; **nothing joins to them** |
| `STEP` | col 4 | BR-SHL-046 | `wizard_parks.step` | int ≥1 | system-derived | clamped to the flow's own list length, never an error (BR-SHL-011) |
| `NOTE` | col 5 | B18 §4.2 (*"an optional note"*) | `wizard_parks.park_note` | text ≤2000, nullable | user-input | `null` **and** `""` both render `—` |
| `REMIND ON` | col 6 | BR-SHL-047 | `wizard_parks.remind_on` | date, nullable | user-input | a date already past is **accepted** — it is a chase date, not a deadline; ⛔ **nothing sends it** (DEF-758) |
| `WAITING` | col 7 | BR-SHL-048 (c) | **not stored** — `wizard_parks.age_days(parked_at)` | int days | computed-display | the **SERVER's** figure; nullable → `—`, never `null days`; **no threshold, no tone** |
| `ACTIONS` | col 8 | B14 r15 / r6 | — | — | — | `Resume` a LINK; `Discard` danger + confirm (IS-6) |
| *(not a column)* | — | hard rule 1 · BR-SHL-048 | `wizard_parks.tenant_id`, `.parked_by` | FK | system-derived | **the only two real FKs the table has** — `parked_by_name` is therefore a lawful join, unlike anything in `subject_ref` |
| Column preference key | S17.2 | BR-SHL-013 | `user_preferences` key **`table.S17.waiting-on.columns`** | jsonb | system-derived | identity column unhideable; **deliberately not renamed to `S17.2`** |
| Page / search state | S17.2 | BR-SHL-011 · **DEF-664** | ⛔ **GAP — nowhere.** Component state only | — | user-input | does not survive a reload |
| Audit | — | hard rule 7 | `audit_log` — `wizard_park.parked` · `.resumed` · `.updated` · `.discarded` | — | system-derived | **no applicant PII in the payload** |

**6 · Acceptance**

1. Accounts → **Waiting on** lists every parked draft in the tenant with its reason, note, reminder date, step and **age in days**, newest first, and the footnote says so.
2. The tab's only tenant-scoped call is the draft store — **no account, unit or premises is read** (BR-SHL-048 (a)), proved as a recorded network trace and not by review.
3. `Resume` opens the flow's **own** wizard at the parked step with what was typed still editable, the steps ahead still locked, and the product **re-read** from the copied ids (BR-SHL-048 (b)).
4. `Discard` is danger tier, confirms first, names that it throws away typing and **nothing else**, and really deletes.
5. The screen states, above the table, that **a parked job has changed nothing** and that **no reminder is sent** — neither absence is left for a clerk to discover.
6. It opens on the clerk's own drafts and offers everyone's in one press.
7. A tenant seeded with sample data opens the tab and **sees a row** with a plausible reason, a reminder date and a visible age — and the seeding has created **no account, no occupancy and no bill**.
8. Cross-tenant: 404 at the API and invisible at the database; an Executive can neither read nor park.

**7 · Finance Calculation** — **N/A: no money is computed, displayed or stored on this screen.** That is BR-SHL-048 in another form — a parked wizard computes no money, and B18 §4.3 forbids one holding any: *"never hold money in a parked step. A deposit taken is a payment row, not wizard state — a container restart must not lose it."* The nearest a draft comes to a figure is a **deposit amount typed into `values`**, which is a draft of a form and never a financial record; **hard rule 4's immutability governs issued invoices, payments and journal lines and has nothing to say about it.** No golden test is cited and none should be.

**8 · Open Questions and what is NOT built**

| # | What | Tracked by |
|---|---|---|
| 1 | **Reminder DELIVERY.** `remind_on` is stored and nothing sends it — no email, SMS or print adapter in this release. The screen states the absence; it is not this story's to build | **DEF-758** |
| 2 | **No ageing limit.** BR-SHL-047's unit-blocking limit is MOOT (BR-SHL-048 (c)) and **no replacement was ruled**, so nothing anywhere refuses or flags an old draft. The age column and a date a human reads are the entire mitigation | **OWED — a PO question** |
| 3 | **No KPI strip**, where B18 §4.1 ① asks every tab for exactly five tiles. The only figures worth a tile (*how many are waiting*, *the oldest wait*) are true of the **whole store** while the payload answers for a **page** — a tile would be a page-scoped number wearing a total's clothes | REPORTED in `WaitingOnTab.tsx` exceptions |
| 4 | **No search and no sort**, where B18 §4.1 ② asks every tab for both plus a column selector. The CR-035 contract serves neither `q` nor `sort`; BR-SHL-010 means the controls do not render. The **column selector does** | REPORTED — a contract widening, not a screen fix |
| 5 | **TC-12 is not asserted for this tab** — that a failed read renders the failure state and never the empty one holds by `DataTable`'s construction and by no case of this suite | **OWED** |
| 6 | **Two names for one surface** — `S17.2` in tickets, `S17.waiting-on` in the stored preference key. Both are printed in A1's addendum; the split is real and is reported rather than resolved by a rename that would orphan saved column sets | REPORTED (A1 addendum) |
| 7 | **CR-035's other five parts own NO story** — the `wizard_parks` store, its service and API, the `wizardParkPort()` switch and the five wizards' resume all shipped in `2.51.0` with no `US-` id claiming them. This epic closes law 8 for the LIST only; three or four more stories are **OWED** | **OWED — reported by this epic** |
| 8 | **Sitting inside `AccountsListPage` costs the URL** — page and search state do not survive a reload, the same trade every embedded tab makes | **DEF-664** |
