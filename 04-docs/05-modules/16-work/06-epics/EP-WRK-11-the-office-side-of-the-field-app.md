# EP-WRK-11 — The office side of the field app: finished jobs to accept, orders raised on site, alerts, a technician's handsets, and what the field said on the order

**Module:** work · **Wave:** phase **2** of `CR-070`, built under `CR-187-BRC10` · **Screens:** `Work-034` (new — *From the field*, badge `WRK-26`) · `Work-008` · `Work-024` · **Status:** built 2026-10-21 (web half; the server routes it calls already existed on the branch)

## Scope

**In:** the office screens the native field app needs, as its own walkthrough names them —
`08-qa/01-e2e/journeys/J-FLD-TWENTYFOUR-the-field-app-scenario-suite.md`, *"What the office
(web) side has to change"*, and `04-docs/05-modules/18-field-app/07-endpoints.md` §7:

| Office surface (Walkthrough §4) | Story | Where it is built |
|---|---|---|
| Office acceptance queue — *"Review and accept completed work; reopen or raise a follow-on; see what a partial left undone"* | `US-WRK-055` | `Work-034` · *Finished jobs* |
| Field-raised queue — *"Orders raised on site awaiting acceptance, with their photographs and position"* | `US-WRK-056` | `Work-034` · *Raised on site* |
| Alerts (N25, R28) — the dispatcher's list, and an alert sent from an order | `US-WRK-057` | `Work-034` · *Alerts* · `Work-008`'s *From the field* group |
| *"The office sees every device a technician uses"* (Security §4) and remote sign-out (R115) | `US-WRK-058` | `Work-024` · Overview · *Devices* |
| Work order detail — *"The four outcomes with their reasons"* and reopen versus follow-on (E2E-17/18) | `US-WRK-059` | `Work-008` · Overview · *From the field* |

**Out:** the dispatch board's handset axis, templates' photo and freshness settings,
readings review at route volume, crews' claim rights, timesheets, asset visit history and
the field-app button's repointing — the other rows of the same table, each its own story
when it is taken. **No server change** — every route below was on the branch before this
epic (`06-backend/apps/work/field_orders_api.py`, `field_api.py`, `api.py`).

⚠ **THERE IS NO DRAWING FOR ANY OF THESE SCREENS.** The field-app design names the office
surfaces in a table and draws none of them; neither the Work blueprint nor r10 carries
them (r10 predates the field app). The layout was therefore COMPOSED FROM THE KIT on
`Work-009`'s pattern — `PageHeader` with the Work strip, `SubTabs`, `DataTable` with
`FilterBar`, icon row actions, `FormModal` and `ConfirmDialog` — and is written down as
each story's §1 so the next lane builds the same thing. **The PO has not seen this
layout.** The skill's rule (*"draw it, show it, then build"*) could not be followed by a
build lane with no channel to the PO; this paragraph is the record of that, and the first
person to put the screen in front of the PO closes it.

⚠ **ONE TAB WITH THREE PANES, NOT THREE TABS — a judgment, recorded here (law 13: ours to
decide).** The Work strip already held nine tabs; twelve wraps at 1280 (the staff laptop
minimum, skill §6), and the strip is what a returning dispatcher reaches for first. The
three lists are one thing from the office's chair — what the HANDSETS sent back — so they
share *From the field*, beside *Approvals*, with a `SubTabs` strip (the kit's second-level
strip, already used by Billing and Reports). Each pane has its own address
(`/work/field`, `/work/field/raised`, `/work/field/alerts`) so a link survives a refresh.
*Raised on site* is a pane rather than a filter of *Finished jobs* because the rows are
different things: one has an outcome, steps left and a cost; the other has not been worked
and carries a position, a template version and a decision.

⚠ **`Work-009` (*Approvals*) IS NOT CHANGED.** It is a drawn screen (rule 41) with seven
drawn columns; the outcome, reason, blocker, steps left and cost could not join it without
breaking the drawing, so they are *Finished jobs*' columns. Both read the same population
(finished, unaccepted) and one Accept clears a row from both.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-034` Finished jobs | — (the route declares no `q`) | outcome (R4 word, counts from the server's `tally`) | completed, oldest first (server) | — | Order · Technician · Outcome · Reason · Blocked by · Steps left · Photos · Cost · Waiting | 👁 · ✓ · `…` (Reopen… · Raise follow-on…) | — | — |
| `Work-034` Raised on site | — | status (Pending · Accepted · Refused; starts on Pending) | raised, oldest first (server) | — | Order · Template · Where · Raised by · Raised · Position · Photos · Status | 👁 · ✓ · Refuse (danger) — pending rows only | — | — |
| `Work-034` Alerts | — | answer (Waiting · Overdue) | sent, newest first (server) | — | Alert · Order · Technician · Sent · Answer · Message | — | — | — |

## Stories

---
id: US-WRK-055
epic: EP-WRK-11
module: work
screens: [Work-034, Work-008]
wave: 2
status: built
blocked_by: []
depends_on: [US-WRK-003, US-WRK-053]
journeys: [J-FLD-TWENTYFOUR]
rules: [BR-FLD-00004, BR-FLD-00021, BR-FLD-00022, BR-WRK-007]
golden_tests: []
finance_calc: none
---
### US-WRK-055 — Finished jobs: review what the field said about every unaccepted job, then accept it, reopen it, or raise a linked follow-on

**1 · Details** — As **a dispatcher or supervisor**, I want **every finished job nobody has accepted, with its outcome, the reason, what blocked it, the steps it left undone, its photographs and its cost**, so that **I can accept good work, send a partial back, or raise the next visit — and see that *Waiting on someone* is not a failure** (E2E-04, -05, -06, -17, -18).

Layout (composed, not drawn — see the epic): the Work page head with the strip, *From the field* active; a sub-strip *Finished jobs · Raised on site · Alerts*, this pane first; the kit's table with `+ Filter` (Outcome, each option with the server's count). Columns: **Order** (the number, the job type muted under it) · **Technician** · **Outcome** (pill: Passed green · Partly done amber · Failed red · Waiting on someone blue) · **Reason** (as written, or an amber *Reason missing* pill) · **Blocked by** (*A person · A part · Access*, or what the handset sent) · **Steps left** (*2 of 5*) · **Photos** · **Cost** (two decimals) · **Waiting** (*2 days*) · actions **👁 ✓ …** (*Reopen…*, *Raise follow-on…*).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-FLD-00004` | Four outcomes; Failed is the work failing, Waiting on someone is being blocked by a person, a part or access | CONFIRMED (PO 2026-10-20/21) |
| `BR-FLD-00021` | A reconnect is a new work order, never a reopen | CONFIRMED (PO 2026-10-20/21) — the server refuses it by name; the form shows the server's sentence |
| `BR-FLD-00022` + PO 2026-10-21 | The office may reopen a job, **including one it has already accepted** (decision log 2026-10-21, item 11) | CONFIRMED — the screen does not pre-refuse; the server decides |
| `BR-WRK-007` | The queue is finished and unaccepted — a null, not a table | CONFIRMED |

**3 · Test Cases** (`07-frontend/src/features/work/field/FieldDeskPage.dom.test.tsx`)

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/work/field` | `GET /work/acceptance-queue?accepted=false&page=1&per=…`; `WO-4903` reads *D. Ortiz · Partly done · Reason missing · 2 of 5 · $138.42*; `WO-4917` reads *Waiting on someone · A part* and its reason; no order id in the text; the eye links to `/brazosbend/work/orders/{id}` |
| TC-2 | `+ Filter` → *Partly done* | a second request carries `outcome=partly_done`; the blocked row leaves |
| TC-3 | ✓ on a row | asked first (*Costs and readings are saved.*); confirm posts `/work-orders/{id}/accept` and nothing else |
| TC-4 · **negative** | `… → Reopen…`, submit empty | *Give a reason.*, nothing sent; with a reason, `POST /work-orders/{id}/come-back {decision: reopen, reason, key}` |
| TC-5 | `… → Raise follow-on…`, type *Reco* | templates searched by `q=Reco`; a DRAFT is never offered; submit posts `{decision: follow_on, template_id, reason}` |
| TC-6 | Empty queue | *Nothing to review* |

**4 · Test Data** — `WO-4903` Meter exchange · D. Ortiz · partly done · no reason · 3 of 5 steps · 4 photos · $138.42 preview · 2 days; `WO-4917` waiting on someone · a part · *Customer not home, gate locked* · $45.00. Tally: passed 7 · partly done 2 · failed 1 · waiting 3.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| outcome · reason · blocker · steps · photos | Finished jobs | R4, E2E-04/05/06 | `work_orders.outcome`, `.field_data`, `work_order_tasks`, `work_order_attachments` via `field_outcomes.outcome_record` | token · text · count | phone | the server's |
| cost | Finished jobs | `BR-WRK-051` | frozen report, or a preview from `costing.work_order_cost_lines` | decimal string, 2 dp | computed | none on screen |
| reopen / follow-on | dialogs | E2E-17/18 | `work_order_reopens` (`office_reopen` · `follow_on`) | row | user-input | reason required; template required for follow-on |

**6 · Acceptance** — **Given** a partial job with no reason, **when** the dispatcher opens *Finished jobs*, **then** the row says *Partly done · Reason missing · 2 of 5* — **and** *Reopen…* returns it to the field with every reading and photo kept.

**7 · Finance Calculation** — none. The cost is displayed, never computed or posted here (`OQ-WRK-1491`, ruled: posted nowhere).

**8 · Open Questions** — none. ⚠ The PO has not seen the composed layout (epic §Scope).

---
id: US-WRK-056
epic: EP-WRK-11
module: work
screens: [Work-034]
wave: 2
status: built
blocked_by: []
depends_on: [US-WRK-055]
journeys: [J-FLD-TWENTYFOUR]
rules: [BR-FLD-00023, BR-FLD-00024]
golden_tests: []
finance_calc: none
---
### US-WRK-056 — Raised on site: an order a technician raised on a handset waits for the office, who accepts it into dispatch or refuses it with a reason

⚠ **AMENDED 2026-10-31 (FB-028, PO — R23 SUPERSEDED).** The title above is kept as the story's name; the behaviour is now: the order is already ASSIGNED to the technician who raised it (every template, no office wait); this pane is a REVIEW list — *Accept* marks it seen (*"Marks it seen. It stays assigned."*), *Refuse* still cancels it with a reason, and the dispatcher may reassign it any time. An **Assigned to** column names who holds it now.

**1 · Details** — As **a dispatcher**, I want **the orders technicians raised on site, with where they stood, the photographs, the template version they used and who holds them now**, so that **nothing raised in the field surprises the office** (E2E-16; R23 superseded 2026-10-31 — the money decision is the job's own gated step).

Layout: pane two of `Work-034`, starting on the *Pending* filter. Columns: **Order** (+ an amber *Reconnect* pill) · **Template** (*Reconnect visit · v3*, or *v2 → v3* when the template moved between the handset and the server, R112) · **Where** (the premises' address) · **Raised by** · **Raised** · **Assigned to** (FB-028) · **Position** (*29.7604, -95.3698 ±8 m*) · **Photos** · **Status** · actions **👁**, and on a pending row **✓** and **Refuse** (danger).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-FLD-00023` | ~~A field-raised reconnect needs office approval; pending, never auto-scheduled~~ | **SUPERSEDED 2026-10-31 (PO, FB-028)** |
| `BR-FLD-00024` | The number is the server's | CONFIRMED |

**3 · Test Cases** (`FieldDeskPage.dom.test.tsx`)

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/work/field/raised` | `GET /work/field-raised?status=pending`; the row reads *Reconnect · Reconnect visit · v2 → v3 · 29.7604, -95.3698 ±8 m · R. Patel · 77 Cedar Ct*; no id in the text |
| TC-2 | ✓ | asked first (*Marks it seen. It stays assigned.* — FB-028); posts `{decision: accept}` |
| TC-7 | FB-028: a row whose order the office reassigned | **Assigned to** reads *Ray Ortiz*; never an id |
| TC-3 · **negative** | Refuse, empty reason | the commit is the danger tier; *Give a reason.*; nothing sent; then `{decision: refuse, reason}` |
| TC-4 | A decided row | no ✓ and no Refuse |
| TC-5 · **negative** | Nothing pending; clear the filter | the kit's *No results match these filters*; clearing sends `status=all` — never the server's silent default |
| TC-6 | No raises at all | *Nothing raised on site* |

**4 · Test Data** — `WO-5010` · Reconnect visit picked at v2, stamped v3 · 77 Cedar Ct · R. Patel · 2 photos · 29.7604, -95.3698 ±8 m · pending.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| status · decision reason | Raised on site | R23 | `work_field_raises.status`, `.decision_reason` | token · text | user-input | refuse needs a reason |
| position | Raised on site | FF-37 | `work_field_raises.lat`, `.lng`, `.accuracy_m` | degrees · metres | phone | — |
| template version | Raised on site | R112 | `.template_version_picked`, `.template_version_stamped` | integer | phone · server | — |

**6 · Acceptance** — **Given** a reconnect raised on site, **when** the dispatcher refuses it with a reason, **then** the order is canceled and keeps its number and history.

**7 · Finance Calculation** — none.

**8 · Open Questions** — none.

---
id: US-WRK-057
epic: EP-WRK-11
module: work
screens: [Work-034, Work-008]
wave: 2
status: built
blocked_by: []
depends_on: [US-WRK-055]
journeys: [J-FLD-TWENTYFOUR]
rules: [BR-FLD-00028, BR-FLD-00029]
golden_tests: []
finance_calc: none
---
### US-WRK-057 — Alerts: what was sent to which handset, whether it was answered, which emergencies went five minutes unanswered — and *Send alert…* from an order

**1 · Details** — As **a dispatcher**, I want **every alert, its kind, its order, its technician, when it went and whether it was answered**, so that **an unanswered emergency is in front of me, not lost** (R28, E2E-22).

Layout: pane three of `Work-034`. Columns: **Alert** (*Urgent job · Emergency · Schedule change · Dispatch message*) · **Order** (a link) · **Technician** · **Sent** · **Answer** (*Answered · Answered late · Waiting · Overdue · No answer needed*, plus a red *Dispatch told*) · **Message**. Filter: Answer (*Waiting · Overdue*). **No send button on this list** — every kind but a dispatch message names an order, so *Send alert…* is the action of the order page's *From the field* group, on an open job somebody holds: Kind (select) and Message (required for a dispatch message).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-FLD-00028` | An emergency must be acknowledged; five minutes and dispatch is told | CONFIRMED — the server keeps the clock; the screen reads `late` and never this PC's clock |
| `BR-FLD-00029` | Dispatch messages only | CONFIRMED |

**3 · Test Cases** (`FieldDeskPage.dom.test.tsx`, `fieldOfficePanels.dom.test.tsx`)

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/work/field/alerts` | `state=all`; the emergency reads *Overdue · Dispatch told*; the order is a link by its address; a dispatch message reads *No answer needed* |
| TC-2 | Filter *Overdue* | the server is asked `state=overdue` |
| TC-3 | No alerts | *No alerts · Send one from an order.* |
| TC-4 | *Send alert…* → Emergency | `POST /work/field-alerts {kind: emergency, work_order_id, key}` |
| TC-5 · **negative** | Dispatch message with no words | *Write the message.*; nothing sent |

**4 · Test Data** — `WO-4822` emergency to D. Ortiz, sent 14:00, due 14:05, unanswered, dispatch told at 14:05:30; a dispatch message *Depot closes at 4*.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| kind · message · answer | Alerts, the dialog | N25, R28 | `work_field_alerts` | token · text · timestamps | user-input · phone | message required for a dispatch message |

**6 · Acceptance** — **Given** an emergency nobody answered in five minutes, **when** the dispatcher opens *Alerts*, **then** it reads *Overdue · Dispatch told*.

**7 · Finance Calculation** — none.

**8 · Open Questions** — none.

---
id: US-WRK-058
epic: EP-WRK-11
module: work
screens: [Work-024]
wave: 2
status: built
blocked_by: []
depends_on: [US-WRK-021]
journeys: [J-FLD-TWENTYFOUR]
rules: [BR-WRK-059, BR-WRK-060]
golden_tests: []
finance_calc: none
---
### US-WRK-058 — A technician's handsets: every device they sign in on, and *Sign out this device* when one is lost

**1 · Details** — As **a supervisor**, I want **to see every handset a technician uses and sign one out**, so that **a lost tablet stops working on its next contact while nothing captured on it is thrown away** (Security §4, R113, R115).

Layout: a *Devices* group on the technician's Overview (`Work-024`). Columns: **Device** (its name, or *Unnamed device*) · **Platform** (*iPhone or iPad · Android device · Web browser*) · **Last seen** · **Alerts** (*On · Off*) · **Status** (*Signed in · Signed out*) · the row action, a power icon, *Sign out {device}*. Asked first in the **danger** tier: *Sign out Van 12 tablet?* — *Everyone on it is signed out. Unsent work is kept.* — *Sign out device*. Paged by the server (the kit's pager). The handset's own identifier and its push token are never shown.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| R115 / Security §4 | The office sees every device and can sign one out | CONFIRMED (field-app design, PO 2026-10-20/21) |
| R113 | Nothing captured is thrown away to resolve an auth problem | CONFIRMED — items from before the sign-out are HELD for review |
| `BR-WRK-059` · `BR-WRK-060` | A push token follows the signed-in technician; unsent work stays with who captured it | CONFIRMED |

**3 · Test Cases** (`fieldOfficePanels.dom.test.tsx`)

| TC | Scenario | Expected |
|---|---|---|
| TC-6 | Open a technician | `GET /work/technicians/d-ortiz/devices?page=1`; names, platforms, status; no identifier, no token digits, no row id |
| TC-7 | Sign out | asked first, danger tier, the consequence named; posts `/work/technicians/d-ortiz/devices/{id}/sign-out` |
| TC-8 | Already signed out | the action is disabled |
| TC-9 | No handsets | *No devices yet.* |

**4 · Test Data** — *Van 12 tablet* · Android · last seen 21 Oct 13:55 · alerts on · signed in; an unnamed iPhone, signed out.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| name · platform · last seen · signed out | Devices | Security §4 | `technician_devices` (via `mobile.devices_page`) | text · token · timestamps | phone · user-input | — |

**6 · Acceptance** — **Given** a lost shared tablet, **when** the supervisor signs it out, **then** everyone on it is signed out at its next contact — **and** its unsent work arrives and is held for review.

**7 · Finance Calculation** — none.

**8 · Open Questions** — none.

---
id: US-WRK-059
epic: EP-WRK-11
module: work
screens: [Work-008]
wave: 2
status: built
blocked_by: []
depends_on: [US-WRK-055]
journeys: [J-FLD-TWENTYFOUR]
rules: [BR-FLD-00004, BR-FLD-00021, BR-FLD-00022]
golden_tests: []
finance_calc: none
---
### US-WRK-059 — On the order: what the field said, and every time the job came back

**1 · Details** — As **a dispatcher**, I want **the order's own page to say what the field reported and every reopen or follow-on**, so that **a job that came back three times reads that way** (E2E-04, -17, -18).

Layout: one group, *From the field*, at the foot of `Work-008`'s Overview, **closed by default**, its action *Send alert…* beside the toggle on an open job somebody holds (`US-WRK-057`). Inside: **Field outcome** (Outcome · Reason · Blocked by — blocked jobs only · Steps done *3 of 5* · Photos · Cost with *Preview* or *Report v2*), then the steps left in order (*Required* marked); **Reopens and follow-ons** — *Follows WO-4800* when the job is itself a follow-on, then one line per event: *Reopened by technician · date · who*, the reason (a technician's in FF-36's words: *Wrong outcome · Missed a step · Photo or reading missing*), the note, and a follow-on's *New order WO-5001* as a link. An open job that never came back reads *No reopens or follow-ons yet.*

⚠ **WHY CLOSED BY DEFAULT, AND WHY NOT IN THE HEAD.** The head's buttons are drawn and asserted in order (images 03–11, rule 41), so *Send alert…* is this group's action rather than a fifth button. The group's two reads (`/outcome`, `/come-backs`) run when it is opened, because `recordedServerShapes.dom.test.tsx` refuses any order-page read with no recording of the real server's reply and these two routes have none yet (capturing them needs `10-scripts/cr168_capture_work_shapes.py` against a seeded PostgreSQL). When they are recorded, opening the group on a completed job is a one-word change (`defaultOpen`).

**2 · Business Rules** — as `US-WRK-055`.

**3 · Test Cases** (`fieldOfficePanels.dom.test.tsx`)

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Completed job, open the group | *Partly done · Ran out of seals · 3 of 5 · Seal the meter · Photo of the seal · $138.42 · Preview* |
| TC-2 | Its history | *Reopened by technician … Missed a step*; *Follow-on raised … New order WO-5001* (a link by address); *Follows WO-4800*; no id in the text |
| TC-3 | An open job | `/outcome` is never asked; *No reopens or follow-ons yet.* |
| TC-3b | Closed by default | nothing read until opened; *Send alert…* calls the order page |
| TC-3c | Nobody holds the job | no *Send alert…* |

**4 · Test Data** — as `US-WRK-055`; history: a technician reopen (*missed_step*) and an office follow-on to `WO-5001`; the job itself follows `WO-4800`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| events | Work-008 | E2E-17/18 | `work_order_reopens` (`kind`, `reason`, `note`, `at`, `by_user`, `follow_on_order`) | rows | user-input · phone | — |

**6 · Acceptance** — **Given** a job reopened by its technician and later followed on by the office, **when** the dispatcher opens its *From the field* group, **then** both read distinctly and the new order is one click away.

**7 · Finance Calculation** — none.

**8 · Open Questions** — none.
