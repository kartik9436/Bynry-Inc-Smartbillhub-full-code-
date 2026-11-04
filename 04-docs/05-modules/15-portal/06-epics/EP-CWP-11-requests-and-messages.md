# EP-CWP-11 — Requests, messages and disputes

**Module:** portal (writes service requests) · **Wave:** release 3 ·
**Screens:** CWP-046 · CWP-048 · CWP-049 · CWP-051 … CWP-055 · CWP-067 ·
**Status:** draft

## Scope

**In:** the request hub, moving out, stopping service, tracking a request, the document
checklist, disputing a bill or a reading, asking a question, messages, and a visit booked
at the property.

**Out:** the guest request surface (`EP-CWP-03`, `EP-CWP-04`), the fees (`EP-CWP-09`).

⚠ **THIS IS THE PART OF THE PORTAL WITH THE MOST ALREADY BUILT BEHIND IT.** A service
request is a full record with **eleven states**, a document checklist that varies by
request type, fees that can be quoted and collected now or later, and a complete
transition history. **It was designed from the start expecting a channel called customer
portal — the record has a field for it and nothing has ever written that value.**

⚠ **THE CUSTOMER REACHES FOUR OF THE ELEVEN STATES AND NO MORE:** create a draft, submit,
answer a question, withdraw. **Approving, refusing, holding, routing and completing stay
with the utility — which is what keeps a self-serve form from becoming a way to grant
yourself a connection.**

⚠ **AND THE PORTAL CANNOT CORRECT ANYTHING.** An issued bill is immutable, corrections are
new rows, and only the ledger service writes to the books. **So every "fix this" is a
request a member of staff acts on, and the portal's job is to make that request precise
— not to pretend it can do the fixing.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-046 | — | — | Raised desc | — | Reference · What · Raised · Status | View (icon) | — | — |
| CWP-051 | — | — | — | — | — | Add a note · Withdraw | — | — |
| CWP-049 | — | — | — | — | Document · Why · Status | Upload (held) | — | — |
| CWP-053 | — | — | When desc | — | Message · About · When | View (icon) | Mark all read | — |

---
id: US-CWP-060
epic: EP-CWP-11
module: portal
screens: [CWP-046]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J40]
rules: [BR-CWP-075, BR-CWP-076, BR-CWP-080]
golden_tests: []
finance_calc: none
---
### US-CWP-060 — What do you need: six cards, named by what the customer wants

**1 · Details** — As **a customer**, I want **to ask for things in my own words**, so that
**I do not have to know what your system calls them**.

Six cards: **move out** — *close this account and settle up. We need eight days' notice* ·
**move to a new address** — *take your account with you. One request, both ends* · **add a
service** · **stop service for a while** · **report a problem** · **something else** —
*tell us in your own words and we will route it.* Below them, open requests with their
references and statuses.

⚠ **NAMED BY WHAT THE CUSTOMER WANTS, NOT BY WHAT THE SYSTEM CALLS IT.** Behind these six
sit the record's real job outcomes — a new connection, a move-in, a move-out, a transfer,
a disconnect — plus a catch-all a clerk categorises.

⚠ **AND THE *SOMETHING ELSE* CARD MATTERS:** without it, anything the six cards do not
cover **becomes a phone call.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-075` | ⚠ **AMENDED 2026-09-19** (`OQ-CUS-12486`) — the customer makes **three**: create a draft, submit, answer a question. *Withdraw* was the fourth and is retired, and the request has five states rather than eleven. Approving and refusing still stay with the utility, which is the rule's point and is unchanged. | **AMENDED 2026-09-19** (was CONFIRMED — blueprint §13 Figure 8) |
| `BR-CWP-076` | Every row carries channel `customer_portal` — ⚠ **the first rows in the product ever to carry it** | CONFIRMED — `CP-56` |
| `BR-CWP-080` | Moving out and stopping service are different, and the cards say which | CONFIRMED — blueprint `P32`, `P34` |
| — | Categories are **tenant-configurable** | CONFIRMED — the existing request record |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open the hub | Six cards in the customer's language, plus open requests with references |
| TC-2 | Pick *Move out* | Routes to `CWP-048`; on submit the row carries channel **Customer portal** |
| TC-3 · **negative** | ⚠ The channel value | Assert this is the **first** row in the fixture carrying `customer_portal`, proving the field was inert before |
| TC-4 | An open request needing documents | Shows `SR-26-0056 · Move out · 2 Sep · WE NEED TWO DOCUMENTS` (⚠ this row read *17 Sep* until 2026-09-04 — `DEF-CWP-3840`. §4 below says the request was **raised 2 September** and the capability matrix heads the column **Raised**; **17 September is the last day of service**, a fact about the move rather than about the request. The column is *Raised*, and it shows 2 September) |
| TC-5 · **negative** | A tenant with requests **switched off** | The hub is unreachable and the endpoint refuses |
| TC-6 · **negative** | No open requests | ⚠ An empty state naming what fills it, not a blank list |
| TC-7 · **tenant isolation** | The hub with a Pine Hill session | Pine Hill categories and requests only |
| TC-8 | A tenant that renamed a category | The renamed label shows — ⚠ read from configuration, never a hardcoded list |
| TC-9 · **negative** | *Something else*, free text | Lands as a request a clerk categorises; ⚠ nothing on the account changes |

**4 · Test Data** — Six cards for Pine Hill. Open request `SR-26-0056`, move out, 17 Sep
2026, raised 2 Sep 2026, *we need two documents*. A tenant with `requests_enabled =
false`. (⚠ **The two dates are two different facts and TC-4 conflated them until
2026-09-04 — `DEF-CWP-3840`.** *Raised 2 Sep* is what this list's **Raised** column shows;
*17 Sep* is the last day of service and belongs to the request's own detail screen.)

⊕ **AS BUILT (2026-09-04, shipped in `2.164.0`).** The list is `customers_seam.my_requests` — this tenant, the
channel, and **any phone one of this login's own accounts holds** — because a portal service
request carries **no account at all**: `create_from_portal` refuses the field by name under
`BR-CWP-026`. ⚠ **THIS SCREEN HAD ITS OWN VERSION OF THAT READ, MATCHING ON THE EMAIL, AND
IT WAS DELETED AT MERGE RATHER THAN KEPT** — two lanes in two worktrees each wrote it because
neither could see the other, and two reads of one fact are two answers
(`12-reuse-map.md`). A request a CLERK raised at the counter is invisible either way, the
body says so in `lists_only_portal_requests` and the screen says so in words, and whether
the list should widen is **`OQ-CWP-1680`** (OPEN — nothing is blocked and nothing is
stubbed). The cards live on `portal_settings.
request_errands` (migration `portal/0009`), a **second** column rather than
`quick_service_categories` read twice: those six are what a stranger with no account asks
for, these six are what a signed-in customer wants done to an account they hold. Four of the
six render **HELD** with their reason because `CWP-048`, the move-home form, the
add-a-service form and *ask us something* are not built — and the SERVER decides which,
in `selectors.ERRAND_ROUTE`, so the wave that builds `CWP-048` moves one map and not two.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| The six cards | CWP-046 | prototype-extracted | `service_request_category` | FK | reference-data | ⚠ Tenant-configurable |
| Reference | CWP-046 | prototype-extracted | `service_request.reference` | text | system-derived | Human reference |
| Channel | — | A5 | `service_request.channel` | enum | system-derived | ⚠ `customer_portal` |
| Status | CWP-046 | prototype-extracted | the eleven-state lifecycle | enum | system-derived | Shown in customer words |

**6 · Acceptance** — **Given** a signed-in customer, **when** they open the request hub,
**then** six cards describe what they might want in their own words, their open requests
show with references and plain statuses, and a request raised here is the first row in
the product carrying channel *Customer portal*.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-061
epic: EP-CWP-11
module: portal
screens: [CWP-048]
wave: 3
status: draft            # was `blocked`; OQ-1392 ruled 2026-09-04 — ask only
blocked_by: []
depends_on: [US-CWP-060]
journeys: [J40]
rules: [BR-CWP-080, BR-CWP-079]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-061 — Moving out or moving on, and it cannot be undone

**1 · Details** — As **a customer leaving**, I want **to close the account and settle up**,
so that **I get my deposit back and stop being billed**.

Leaving, last day of service, where the final bill goes, deposit held. A consequence box:
*we read your meter on 17 September · a final bill settles your deposit · **the account
closes. You cannot undo this.*** A panel naming the distinction: **moving out closes the
account and settles the deposit; stopping service leaves the account open — standing
charges keep running.** And a note that a move within the area is a **transfer**, which
keeps the history and the deposit.

⚠ **THE COMMIT IS THE DANGER TIER**, because closing an account cannot be undone from
here (B14).

⚠ **THE RIGHT-HAND PANEL NAMES A DISTINCTION THE PRODUCT ENFORCES AND CUSTOMERS ROUTINELY
GET WRONG.** Getting it wrong **costs a customer real money**, so it is stated **before**
the button rather than after.

⚠ **BLOCKED ON `OQ-1392`:** whether a customer may close their own account or only ask to.
**A move-out settles a deposit and issues a final bill, so self-serve means a mistaken
click has a refund at the end of it.** Build the request; stub the self-serve close.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-080` | ⚠ A move-out closes and settles; a disconnect leaves the account open and accruing | CONFIRMED — blueprint `P34`, `P38` |
| `BR-CWP-079` | Withdrawable until approved | CONFIRMED — `CP-56` |
| B14 | Destructive commits use the danger tier | CONFIRMED — B14 |
| `BR-CWP-082` | Whether a customer may close their own account | **OPEN — `OQ-1392`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Request a move-out for 17 Sep | `SR-26-0056` on a clerk's worklist with channel *Customer portal*, and the customer can withdraw it until it is approved |
| TC-2 | The consequence box | Names the meter read date, the deposit settlement, and **that it cannot be undone** |
| TC-3 · **negative** | ⚠ The distinction panel | States that stopping service leaves the account open with standing charges running. Assert the copy is present — this is the most expensive misunderstanding in the product |
| TC-4 · **negative** | Fewer than eight days' notice | Refused, naming the notice period |
| TC-5 · **negative** | The commit control | ⚠ Rendered in the **danger tier**, outlined and filled on hover — not the standard primary |
| TC-6 · **negative** | Call the self-serve **close** path | `NotImplementedError("OQ-1392")` — the request lands for a person until ruled |
| TC-7 | A move within the area | Offers a **transfer** instead, which keeps history and deposit |
| TC-8 · **negative** | Withdraw after approval | Refused |
| TC-9 · **tenant isolation** | A move-out with a Pine Hill session | Pine Hill's account only |
| TC-10 | The deposit figure | ⚠ `$150.00`, matching `CWP-065` and the final bill exactly |

**4 · Test Data** — Leaving `1408 Elm St · A`, last day 17 Sep 2026, final bill to
`91 Cedar Row, Austin TX 78704`, deposit held `$150.00`. Today 2 Sep, so 15 days' notice.
A seven-days-notice variant for TC-4.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Last day of service | CWP-048 | prototype-extracted | `service_request.effective_on` | date | user-input | ≥ 8 days' notice |
| Final bill goes to | CWP-048 | prototype-extracted | forwarding address on the request | text | user-input | ⚠ Also clears a bad-address flag |
| Deposit held | CWP-048 | prototype-extracted | `account.deposit_on_file` | numeric(18,4) → 2 | system-derived | Must match `CWP-065` |
| Kind | — | A5 | move-out vs disconnect vs transfer | enum | user-input | ⚠ Three different outcomes |

**6 · Acceptance** — **Given** a customer leaving on 17 September, **when** they send the
request, **then** a clerk sees it with channel *Customer portal*, the screen has already
told them the account closes and cannot be undone and that stopping service is a
different thing, and the self-serve close path raises `NotImplementedError("OQ-1392")`.

**7 · Finance Calculation** — No new arithmetic here; the settlement is `US-CWP-037`.
Worked: deposit `$150.00` held, settled on the final bill as `$63.40 − $150.00 − $3.20 =
−$89.80`, a refund. ⚠ **The deposit shown here must equal the deposit settled there.**

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1392` | Can a customer close their own account, or only ask to? | This story and the request surface | Product Owner | OPEN |

---
id: US-CWP-062
epic: EP-CWP-11
module: portal
screens: [CWP-052]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-060]
journeys: []
rules: [BR-CWP-080, BR-CWP-081]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-062 — Stop or restart service, and the screen names the cheaper option

**1 · Details** — As **a customer with a seasonal property**, I want **to stop the supply
for the winter**, so that **I am not paying for water I do not use** — and I want **to be
told if closing the account would be cheaper.**

Stop from, start again, why. A consequence box: *your supply is turned off on 1 November ·
**the account stays open** · standing charges keep running — about `$18.50` a month.* And
a panel: **would moving out be cheaper?** — five months of standing charges is about
`$92.50`; closing costs nothing but starting again costs a `$185.00` connection fee and a
new deposit. **For this property, stopping is cheaper.**

⚠ **A SCREEN THAT TELLS THE CUSTOMER THE CHEAPER OPTION, INCLUDING WHEN THE CHEAPER OPTION
IS TO LEAVE.** The comparison is arithmetic over figures the product already holds — the
standing charge on the plan and the connection fee on the tariff — **and it is the
difference between a portal that serves the utility and one that serves the customer.**

⚠ **IT ALSO PREVENTS THE MOST EXPENSIVE MISUNDERSTANDING IN THE PRODUCT: ASSUMING A
STOPPED SUPPLY STOPS THE BILL.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-080` | A disconnect leaves the account open and standing charges keep running | CONFIRMED — blueprint `P38` |
| `BR-CWP-081` | Where stopping is more expensive than closing, the screen says so, with both figures | CONFIRMED — blueprint `P38` |
| Inherited | Money to two decimals | hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Stop 1 Nov 2026, restart 1 Apr 2027 | The box says the supply goes off, **the account stays open**, and standing charges run at about `$18.50` a month |
| TC-2 | ⚠ **The comparison arithmetic** | Five months × `$18.50` = **about `$92.50`**, against a `$185.00` connection fee plus a new deposit to restart — so **stopping is cheaper** and the screen says so |
| TC-3 · **negative** | ⚠ A **nineteen**-month stop (this read *twelve* until 2026-09-03 — `DEF-CWP-3608`; `12 × $18.50 = $222.00` does NOT exceed `$335.00`, as §4 and §7 already said) | `19 × $18.50 = $351.50`, which **exceeds** `$185.00 + $150.00 = $335.00` — and the screen must then say **closing** is cheaper |
| TC-4 · **negative** | The copy | ⚠ Never implies the bill stops. Assert the phrase *"the account stays open"* is present |
| TC-5 · **negative** | Restart before stop | Refused |
| TC-6 · **tenant isolation** | The figures with a Pine Hill session | Pine Hill's standing charge and connection fee |
| TC-7 | A tenant whose standing charge differs | ⚠ The figures follow the **plan**, not a constant in the portal |
| TC-8 · **negative** | A service with **no** standing charge | The comparison says so rather than showing `$0.00` as a saving |

**4 · Test Data** — Stop 1 Nov 2026, restart 1 Apr 2027 — five months. Standing charge
`$18.50` a month → `$92.50`. Connection fee `$185.00`. New deposit `$150.00`. Reason *the
property is empty over winter*. Nineteen-month variant for TC-3: `$351.50` against `$335.00` — closing is cheaper.
(⚠ A twelve-month stop is `$222.00`, **less** than `$185.00 + $150.00 = $335.00`, so stopping is
still cheaper there; the crossover is `$335.00 ÷ $18.50 = 18.1`, so nineteen months is the
first that crosses it. TC-3 said *twelve* until 2026-09-03 — `DEF-CWP-3608`.)

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Stop from, start again | CWP-052 | prototype-extracted | `service_request.effective_on`, `resume_on` | date | user-input | Resume after stop |
| Standing charge | CWP-052 | prototype-extracted | base charge on the plan | numeric(18,4) → 2 | reference-data | ⚠ Read from the plan |
| Connection fee, deposit | CWP-052 | prototype-extracted | tariff and account type | numeric(18,4) → 2 | reference-data | Effective today |
| The recommendation | CWP-052 | GAP | the comparison | text | computed-display | ⚠ Names the cheaper option, either way |

**6 · Acceptance** — **Given** a customer stopping service for five months at a `$18.50`
monthly standing charge, **when** the screen opens, **then** it says the account stays
open, quotes about `$92.50` against a `$185.00` reconnection plus a new deposit, and
concludes that stopping is cheaper — and for a long enough stop it concludes the
opposite.

**7 · Finance Calculation** — Cost of stopping = months × standing charge. Cost of
closing and restarting = connection fee + new deposit.
Worked: `5 × $18.50 = $92.50` versus `$185.00 + $150.00 = $335.00` → **stopping is
cheaper.** Crossover: `$335.00 ÷ $18.50 = 18.1` months, so **from 19 months closing wins.**
⚠ **The recommendation must be computed, not hardcoded** — a screen that always says
*stopping is cheaper* is wrong for a long absence.

**8 · Open Questions** — None.

⊕ **AS BUILT (2026-09-04, shipped in `2.164.0`) — WHERE THE `$18.50` ACTUALLY COMES FROM, BECAUSE §5 NAMES THE
WRONG OBJECT.** §5 maps *Standing charge* to *"base charge on the plan"*. **The plan does not
own it.** `BR-RAT-088` (PO 2026-08-20, verbatim: *"the CHARGE CODE owns the base amount; a
plan displays it, never defines it"*) moved the source to the charge code, and
`gather._base_charge_for` is the single implementation of that precedence — the plan's own
`base_charge` column survives only so a **disagreement** between the two can be refused by
name. So the portal reads it through `apps.rating.seams.base_charge_for` with the account's
customer class, sums the account's **own** services, and carries any refusal as a REASON.
TC-7 (*"the figures follow the plan, not a constant in the portal"*) is unaffected and is
what the test moves the charge code to prove. The story's §5 row is stamped here rather than
edited, on the plan's §0 rule: **the code wins and the task says so** (`DEF-CWP-3703`'s
shape, one screen along).

⊕ **`size_class` IS PASSED AS `None`, AND THAT IS THE PRODUCT'S ANSWER RATHER THAN A
SHORTCUT.** `DEF-514` records that nothing in this product records a connection size, and
`base_charge_for`'s own docstring says an unscoped call *"gets the same answer a tenant with
one unscoped, flat base code would get — which is every tenant this product provisions
today"*. The day sizes are recorded, this call gains the argument.

⊕ **THE WRITE IS THE FIFTH SHAPE OF THE EXISTING SERVICE-REQUEST WRITE POINT**, at
`POST accounts/{id}/stop-or-restart/ask` — `write_points.py` is untouched, nothing is
disconnected, no service agreement ends and the response carries `supply_stopped: false` so
no confirmation screen can imply otherwise.

---
id: US-CWP-063
epic: EP-CWP-11
module: portal
screens: [CWP-051]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-060]
journeys: [J31, J40]
rules: [BR-CWP-078, BR-CWP-079, BR-CWP-024]
golden_tests: []
finance_calc: none
---
### US-CWP-063 — Track your request: the customer-visible half of the history

**1 · Details** — As **a customer who has asked for something**, I want **to see where it
is**, so that **I do not ring to check**.

A progress timeline — *you sent it · we picked it up · we need something from you · we
decide · final reading and bill · account closes* — with who and when. A details panel:
reference, last day of service, waiting on, open for. **Add a note** — and, until 2026-09-19, **withdraw**, which the PO has since removed from the customer's screen (`OQ-CUS-12486`).

⚠ **THE REFERENCE IS WHAT MAKES THIS SCREEN WORK SIGNED OUT** — the same read serves
`CWP-012`.

⚠ **INTERNAL ROUTING NOTES AND STAFF-ONLY COMMENTS STAY HIDDEN.** The record already
distinguishes a note meant for the customer from one that is not, **and that flag has been
sitting inert waiting for exactly this screen.**

⚠ **AND THE CONNECTION BEHIND AN APPLICATION IS SHOWN TOO** — its target activation date
and what it is waiting on, *"so an applicant stops ringing to ask which of the two it
is."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-078` | Transitions plus notes flagged customer-visible; **never internal routing comments** | CONFIRMED — `CP-25`. ⚠ **THE FLAG IS NO LONGER *inert* AND IS NOT FULLY WIRED EITHER — `DEF-CWP-3880`, amended 2026-09-05.** The READ honours it; the only writer that can raise it is `note_from_portal(customer_visible=True)`, the customer's OWN note on `CWP-051`. **The clerk has no way to flag one** — `add_note` passes nothing and `_event` defaults `internal=True` — so this rule's customer-visible half can only ever be the customer's own words. A build gap on a CONFIRMED rule, not a design |
| `BR-CWP-079` | ⚠ **SUPERSEDED 2026-09-19** (`OQ-CUS-12486`) — *withdrawable until approved* is withdrawn; a withdrawal is a refusal REASON now. The clause *withdrawing does not touch the account* still holds of the refusal that replaces it. | **SUPERSEDED 2026-09-19** (was CONFIRMED — `CP-56`) |
| `BR-CWP-024` | Signed out, it returns progress and never data | CONFIRMED — `CP-14` |
| `CP-52` | The connection behind an application, its target date and what it waits on | CONFIRMED — `CP-52` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `SR-26-0056` two days old | *You sent it · 2 Sep, 9:14am through the portal · We picked it up · 2 Sep, 2:40pm · Sarah at the office · We need something from you · 3 Sep* |
| TC-2 · **negative** | ⚠ An internal routing note on the same request | **Absent.** Assert the response body does not contain it |
| TC-3 | A customer-visible note asking for two documents | Present, in the clerk's words |
| TC-4 | ⚠ **SUPERSEDED 2026-09-19 — THERE IS NO WITHDRAW CONTROL.** It read: *Withdraw → The request ends; the account carries on as normal.* The PO closed the customer's door on `OQ-CUS-12486`: *"if customer dont want it - they will call and clark will refuse it. thats'it . keep it simple"*. **What replaces it:** the clerk refuses the request with reason `Applicant withdrew`, and the account still carries on as normal — that half of the promise is unchanged. | **Assert the ABSENCE:** `may_withdraw` is false in every state and the screen draws no withdraw control |
| TC-5 · **negative** | ⚠ **SUPERSEDED 2026-09-19 with TC-4.** It read: *Withdraw after approval → Refused with a plain sentence.* A withdrawal is refused from EVERY state now, not only after approval, because `withdraw` is no longer in `service_request.TRANSITIONS` at all. | **Assert the endpoint still refuses CLEANLY:** `POST requests/{reference}/withdraw` answers `BIZ_STATE` with `customers.serviceRequest.transitionNotAllowed` — a readable refusal, never a 500 |
| TC-6 · **negative** | The same reference **signed out** | Progress only — no name, no balance, no other reference |
| TC-7 · **tenant isolation** | `SR-26-0056` with an Oak Ridge session | Not found |
| TC-8 | An application with a connection behind it | Shows the connection's target activation date and what it waits on |
| TC-9 | *Open for* | Reads *1 day*, computed, not stored |
| TC-10 · **negative** | A **refused** request | ⚠ Shows the refusal **and its reason** — a refusal always carries one |

**4 · Test Data** — `SR-26-0056`, move out, `1408 Elm St · A`, raised 2 Sep 2026 9:14am
through the portal, picked up 2:40pm by *Sarah at the office*, 3 Sep *we need proof of
address and your landlord's consent*, decision *usually the same day the documents
arrive*, final reading and bill 17 Sep, account closes. One internal note *"route to
Tuesday crew, low priority"* that must not appear. A refused request with reason. A
connection `CN-26-0113` with target activation 21 Sep.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Timeline | CWP-051 | prototype-extracted | `service_request_transition` | — | system-derived | With actor and time |
| Notes | CWP-051 | prototype-extracted | `AccountNote` / request note where `customer_visible` | text | system-derived | ⚠ **The flag is the boundary** |
| Waiting on | CWP-051 | prototype-extracted | the request's blocking checklist | text | computed-display | — |
| Open for | CWP-051 | prototype-extracted | now − raised | integer | computed-display | Computed |
| Connection | CWP-051 | prototype-extracted | `Connection.target_activation_date`, waiting-on | — | system-derived | ⚠ Reaches no screen today |

**6 · Acceptance** — **Given** a move-out request a clerk has picked up and asked for
documents on, **when** the customer tracks it, **then** they see who picked it up and when
and what is needed — and the internal routing note on the same request appears nowhere in
the response.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — ⊕ **ONE, MINTED 2026-09-05: `OQ-CWP-1680` (OPEN).**
*What makes a request MINE when I am signed in?* `BR-CWP-010` intersects every
portal read with the session's account set **in the query**, and a service
request has no account column to intersect against — `create_from_portal`
*"links no account and changes none"* (`BR-CWP-026`). **Nothing is blocked and
nothing is stubbed:** the screen ships filtering on this tenant, the channel, and
**a phone one of this login's own accounts holds**, which is narrower than the
guest tracker's reference-plus-postcode. What it does not stop is two customers
of one utility sharing one telephone number.

⊕ **AS BUILT (2026-09-05, `2.163.0`).** `customers_seam._customer_visible_events`
**PROJECTS `service_request_reads.history_tab`** — the clerk's own read — rather
than walking `service_request_events` a second time (`12-reuse-map.md`).
⚠ **`BR-CWP-078` SPLITS THE ROWS IN TWO AND A FIRST DRAFT THAT DID NOT RETURNED A
LADDER WITH NO DATES ON ANY STEP:** every state row this product writes carries
`internal=True`, so *filter everything on the flag* left the timeline empty.
Transitions are always shown; a NOTE is shown only when the flag says so; and one
transition's clerk-written note IS shown — the refusal's, because `BR-CWP-077`
says the portal shows the reason. ⚠ **That reason is not on the row**:
`refuse_request` puts it on the timeline EVENT and `decision_reason` belongs to
`decide_outcome`, so `customers_seam.refusal_reason` reads both, the row first.
`service_request_events.internal` stops being a hardcode; the clerk still has no
way to mark a note customer-visible (`DEF-CWP-3880`).

---
id: US-CWP-064
epic: EP-CWP-11
module: portal
screens: [CWP-049]
wave: 3
status: blocked
blocked_by: []
depends_on: [US-CWP-063]
journeys: [J40]
rules: [BR-CWP-078]
golden_tests: []
finance_calc: none
---
### US-CWP-064 — Documents we need from you: the checklist is real, the upload box is not

**1 · Details** — As **a customer whose request is waiting on paperwork**, I want **to know
exactly what is needed and why**, so that **I bring the right things**.

A checklist: document, **why**, status — *Photo ID · to confirm who you are · RECEIVED 2
SEP* · *Proof of address · a tenancy agreement or a deed · NEEDED* · *Landlord's consent ·
you are not the owner · NEEDED*.

⚠ **THE CHECKLIST EXISTS AND THE DOOR DOES NOT.** Which documents a request needs is
already configured by request type and document type, and the storage rules — an
allow-list of formats, a tenant-configurable size cap, write-once retention for legal
documents — **are all signed** (a malware scan before acceptance was signed too and is now
SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`). **What was explicitly deferred
is letting a consumer be the one who uploads.**

⚠ **SO THE UPLOAD BOX IS NOT BUILT, AND THE REQUEST ENDS WITH "BRING IT TO THE OFFICE"** —
worse than the ideal, **and still better than a phone call.**

⚠ **DO NOT DRAW A LIVE UPLOAD CONTROL.** `BR-CWP-056`'s principle applies: a control that
does nothing is worse than a control that is honestly absent.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| — | The checklist is configured by request type and document type | CONFIRMED — the existing checklist |
| — | Consumer upload is **deferred by signed decision**; uploads stay staff-mediated | CONFIRMED — the document-storage signature |
| — | ⚠ The **why** column is shown, not just the document name | CONFIRMED — blueprint `P35` |
| `BR-CWP-078` | Only customer-visible notes appear | CONFIRMED — `CP-25`. ⚠ **The read is built and correct; what a clerk can PUT there is the gap — `DEF-CWP-3880`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A move-out needing three documents | All three listed with **why** each is needed and its status |
| TC-2 | A document already received | Reads `RECEIVED 2 SEP` and is viewable |
| TC-3 · **negative** | ⚠ The upload control | **Absent, with a sentence saying documents come to the office.** Assert no file input exists in the DOM |
| TC-4 · **negative** | Post a file to any portal endpoint | Refused — ⚠ no consumer upload route exists |
| TC-5 | A request type needing **no** documents | ⚠ The screen and its link are absent |
| TC-6 · **tenant isolation** | The checklist with a Pine Hill session | Pine Hill's configuration |
| TC-7 | A tenant that added a document type | It appears — read from configuration, not a hardcoded list |
| TC-8 · **negative** | The *why* for landlord's consent | Reads *"you are not the owner"* — the reason, not a code |

**4 · Test Data** — `SR-26-0056`. Photo ID, *to confirm who you are*, RECEIVED 2 Sep
2026. Proof of address, *a tenancy agreement or a deed*, NEEDED. Landlord's consent, *you
are not the owner*, NEEDED. A request type with an empty checklist.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Document, why, status | CWP-049 | prototype-extracted | the request's document checklist | — | reference-data | Configured per type |
| Received document | CWP-049 | prototype-extracted | `document` | — | system-derived | Viewable, served |
| Upload | — | deferred | **none** | — | — | ⚠ **No route. No control.** |

**6 · Acceptance** — **Given** a request waiting on two documents, **when** the checklist
opens, **then** each names what it is and why it is needed, the one already received says
so, and there is no upload control and no upload route — with a sentence telling the
customer where to bring them.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None to route. ⚠ **Consumer upload is a signed deferral, not an
open question.** Re-opening it is a change request, not a clarification.

---
id: US-CWP-065
epic: EP-CWP-11
module: portal
screens: [CWP-055]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-033, US-CWP-041]
journeys: [J38]
rules: [BR-CWP-042]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-065 — Dispute a bill or a reading: a marker, never an edit

**1 · Details** — As **a customer who thinks a bill is wrong**, I want **to question it and
have collection held**, so that **I am not chased while you look**.

What is wrong, the reason, and the customer's own reading today. A consequence box: *we
hold collection on `$142.18` · no late fee while we look · we answer within five working
days.* A panel: **while a bill is queried** — *the bill itself does not change. If we
agree, we issue a corrected one. Anything you do not dispute is still due on time.*

⚠ **THE DISPUTE IS A MARKER WITH A REASON, AND IT NEVER EDITS THE NUMBER IT QUESTIONS.**
That is exactly how the product already works: **a dispute is a claim about a reading
rather than a change to one**, and only a System Admin can clear it.

⚠ **AND IF THE UTILITY AGREES, THE OUTCOME IS A CORRECTED BILL — A NEW DOCUMENT — AND THE
DISPUTED ORIGINAL STAYS IN THE CUSTOMER'S LIST.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-042` | A correction is a **new** bill; the original stays and names its replacement | CONFIRMED — hard rule 4 |
| — | A dispute is a marker on the reading with a reason; only a System Admin clears it | CONFIRMED — the existing dispute |
| — | Collection is held on the disputed amount and **no late fee accrues on it** | CONFIRMED — blueprint `P41` |
| — | ⚠ Anything **not** disputed is still due on time | CONFIRMED — blueprint `P41` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Query `BL-2608-0141` over the 31 August reading | The bill in `CWP-027` gains *held while we look*; the reading in `CWP-034` shows a dispute marker |
| TC-2 · **negative** | ⚠ The bill itself | **Unchanged.** Assert `invoice.total` is still `$142.18` and no row was updated |
| TC-3 · **negative** | Late fees | ⚠ **None accrue on `$142.18`** while the dispute is open. Assert the fee clock is held on that amount |
| TC-4 · **negative** | A **second**, undisputed bill on the same account | ⚠ Still due on time, still accruing. Assert the hold is per amount, not per account |
| TC-5 | The utility agrees | A **corrected bill** is issued as a new document, and the disputed original stays in the list |
| TC-6 · **negative** | Try to clear the dispute from the portal | Refused — only a System Admin clears it |
| TC-7 · **tenant isolation** | A dispute with a Pine Hill session | Pine Hill's bill and reading |
| TC-8 | The customer's own reading today | Recorded on the dispute as evidence, ⚠ **not as a meter read** |
| TC-9 · **negative** | Dispute an already-disputed bill | Refused as already open, with its reference |
| TC-10 | Dispute ageing | The existing ageing applies; the customer sees *we answer within five working days* |

**4 · Test Data** — Bill `BL-2608-0141` `$142.18`. Questioning *the meter reading on 31
August*. Reason *the house was empty for two weeks*. Customer's own reading today
`153,190`. A second bill on the account that is not disputed.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| What is questioned | CWP-055 | prototype-extracted | the read or the invoice | uuid FK | user-input | — |
| Reason | CWP-055 | prototype-extracted | the dispute's reason | text | user-input | Required |
| Own reading | CWP-055 | prototype-extracted | evidence on the dispute | numeric | user-input | ⚠ **Not** a `meter_read` row |
| Hold | — | prototype-extracted | collection hold on the amount | numeric(18,4) → 2 | system-derived | ⚠ Per amount |

**6 · Acceptance** — **Given** a customer querying the 31 August reading on a `$142.18`
bill, **when** they send it, **then** collection is held on `$142.18` with no late fee,
the bill's own total is unchanged, the reading carries a dispute marker, and a second
undisputed bill on the same account is still due on time.

**7 · Finance Calculation** — No new arithmetic. Worked: `$142.18` held, `$0.00` late fee
accruing on it; if upheld, a corrected bill replaces it and the original stays with
`$0.00` owing. ⚠ **The hold is on the disputed amount only** — that is the finance-relevant
distinction.

**8 · Open Questions** — ⊕ **TWO, MINTED 2026-09-05, AND BOTH ARE THINGS THIS
STORY ASSERTS THAT THE PRODUCT CANNOT DO.**

* **`OQ-CWP-1681` (OPEN)** — *who puts `metering`'s dispute marker on the
  reading?* TC-1 says the reading shows one. `metering.services.dispute_read` is
  `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` under `BR-MET-035`, **holds the
  account out of the next bill run** (`BR-MET-024`) and is cleared only by a
  System Admin — so a customer reaching it would be a customer suspending their
  own billing on their own say-so, and it is not one of `BR-CWP-001`'s six
  kinds. **A clerk raises it after reading the request**, the shape `BR-CWP-066`
  already gives a payment plan, and the response says `reading_marked: false` on
  its face.
* **`OQ-CWP-1682` (OPEN)** — *does the consequence box print a hold the product
  cannot perform?* §1 promises *"we hold collection on `$142.18` · no late fee
  while we look"*. `BR-MET-133` clause 4 is BUILT and needs the DISPUTED AMOUNT,
  and **nothing in this product records one** — `OQ-420`, OPEN since
  2026-08-26, where `late_fee.ageable_portion` raises rather than choosing
  between two fallbacks **`$137.20` apart** on the rule's own `$184.20` bill.
  **Worked on this story's own figures:** under the box, `$0.00` of Maria's
  `$142.18` ages; under the product, the full `$142.18` keeps ageing and the
  `$5.00` minimum late fee applies on schedule.

⊕ **AS BUILT (2026-09-05, `2.163.0`).** TC-2 is the assertion the story exists
for and it is the strongest one in the file: the invoice row is compared **field
by field** before and after, not just its total. TC-4, TC-6, TC-7, TC-8 and TC-9
all hold. **TC-3's hold and TC-1's marker do not, and the screen says what the
code does instead** — a test asserts that **no catalogue in any of the eleven
languages** promises a hold, because a wording constraint on English is one
translation away from coming back in ten others. `J38` steps 5, 6 and 9 are
stamped with the same three gaps, so a lane booting a browser against that
journey does not read them as a broken build.

---
id: US-CWP-066
epic: EP-CWP-11
module: portal
screens: [CWP-054]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-060]
journeys: [J33]
rules: [BR-CWP-076]
golden_tests: []
finance_calc: none
---
### US-CWP-066 — Ask a question, attached to the bill it is about

**1 · Details** — As **a customer with a question**, I want **to attach it to the bill I
mean**, so that **the answer does not need a phone call to work out what I am asking**.

What is it about, which bill, tell us, an optional photo (held — TC-7). Beside it: *might answer it
now* — three published answers — and *or ring*, with the office and emergency numbers.

⚠ **ATTACHING THE QUESTION TO A SPECIFIC BILL IS WHAT MAKES IT ANSWERABLE.** A free-text
message with no context **becomes a phone call anyway.**

⚠ **AND EVERY ANSWER ENDS HERE.** *"A help page that dead-ends sends the reader to the
phone anyway, only crosser."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-076` | The row carries channel `customer_portal` | CONFIRMED — `CP-26` |
| — | The question arrives on a worklist **already naming the bill** | CONFIRMED — `CP-26` |
| `BR-CWP-093` | The *might answer it now* panel is absent when nothing is published | CONFIRMED — blueprint §16 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Ask about `BL-2608-0141` | The request reaches a clerk **already naming that bill**, and is trackable by reference on `CWP-051` |
| TC-2 | The signed-in version | ⚠ Knows the account already — *"we already know which account you are asking about"*, so nobody retypes an address |
| TC-3 · **negative** | No published answers | ⚠ The *might answer it now* panel is absent, not empty |
| TC-4 | Three published answers exist | Three suggestions, drawn from the answer store |
| TC-5 · **negative** | A question with no bill selected | Accepted as a general question and routed by category |
| TC-6 · **tenant isolation** | Ask with a Pine Hill session | Pine Hill's clerk worklist and answers |
| TC-7 | A photo | ⚠ **Held — consumer upload is a signed deferral** (PO 2026-08-08, DF-4: *consumer upload portal = v2*; `CR-068` §2b; `US-CWP-064`). The picker renders its sentence and **no file input**; a file posted to any portal endpoint is refused. After a re-sign: stored through the existing document store (this row read as built until 2026-09-03 — `DEF-CWP-3611`) |
| TC-8 · **negative** | The emergency number | Present, and distinct from the office number |

**4 · Test Data** — About *a bill*, bill `BL-2608-0141 · August · $142.18`, text *"My
August water is nearly double July and nobody has been at the house…"*. Suggested answers:
*Why is my bill higher than last month?*, *What does "estimated" mean on a reading?*, *How
do I check for a leak?*. Office `(512) 555-0148`, emergency `(512) 555-0100`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| What is it about | CWP-054 | prototype-extracted | `service_request.category` | FK | user-input | Tenant-configurable |
| Which bill | CWP-054 | prototype-extracted | ⚠ **NOT `service_request.invoice_id` — THAT COLUMN DOES NOT EXIST (`DEF-CWP-3881`, corrected in this cell 2026-09-05).** The bill NUMBER travels in `service_request.what_they_said`, behind the constant marker `customers_seam.DISPUTE_MARKER` / `QUESTION_MARKER` so the writer and the reader share one spelling. Adding a real `invoice_id` would be a customers→billing **cross-module FK**, which B2 §2 makes the reviewed interface set and not a lane's call | text (marked) | user-input | Must be in the account set |
| Tell us | CWP-054 | prototype-extracted | `service_request.notes` | text | user-input | Required |
| Suggestions | CWP-054 | GAP | published answers for the topic | — | reference-data | ⚠ Absent when none |

**6 · Acceptance** — **Given** a signed-in customer asking about their August bill,
**when** they send the question, **then** it reaches a clerk already naming
`BL-2608-0141`, is trackable by reference, and the screen offered three published answers
first — or none at all if the utility has written none.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None to route.

⊕ **AS BUILT (2026-09-05, `2.163.0`).** All eight cases hold, and TC-7's photo
box renders its sentence with **no file input** while the route table carries no
door to post one to — asserted over the ROUTE TABLE, which is the form of that
claim that cannot rot when a screen changes.

⚠ **§5's *which bill* MAPPED TO A COLUMN THAT DOES NOT EXIST — `DEF-CWP-3881`. THE MAPPING CELL ITSELF IS CORRECTED NOW (2026-09-05) AND NOT ONLY EXPLAINED UNDERNEATH**, because a §5 row is a build instruction and the next lane reads the TABLE, not the paragraph after it.**
`service_request.invoice_id` is not on the model, the same finding
`DEF-CWP-3701` recorded for `category`; adding one would be a customers→billing
**cross-module FK**, which B2 §2 makes the reviewed interface set and not a
lane's call. So the bill NUMBER travels in `what_they_said` — the column this
product already keeps *"the applicant's own words"* in, and the one the quick ask
and the payment-plan ask already use — behind a constant marker that the *you
have already queried this bill* read matches on, so the writer and the reader
share one spelling and a grep finds both.

⚠ **AND §5's *what is it about* IS THE SAME FINDING.** It types the category as a
tenant-configurable FK; there is neither column nor table, so the five topics are
a fixed list and the chosen LABEL goes into the clerk's sentence, exactly as
`CWP-010`'s quick asks do.

---
id: US-CWP-067
epic: EP-CWP-11
module: portal
screens: [CWP-053]
wave: 3
status: draft            # was `blocked`; OQ-1399 ruled 2026-09-04 — the portal is a convenience copy; post and email stay the delivery record
blocked_by: []
depends_on: [US-CWP-028]
journeys: [J47]
rules: [BR-CWP-084, BR-CWP-083]
golden_tests: []
finance_calc: none
---
### US-CWP-067 — Messages, and the portal as a fourth channel that WAITS

**1 · Details** — As **a customer**, I want **the things you have told me in one place**,
so that **I can catch up when I sign in**.

A list: message, what it is about, when — with unread rows marked and a *mark all read*
control. The bell in the shell carries the unread count.

⚠ **EVERY ROW HERE CORRESPONDS TO AN EVENT THE PRODUCT ALREADY DECLARES** — a bill ready, a
payment received, a correction, an instalment due, a notice sent, planned work. Around
thirty events exist in the catalogue, most aimed at the customer. **Adding the portal as a
fourth channel makes this list a by-product of machinery that already runs rather than a
new feature.**

⚠ **AND THE PORTAL IS THE ONE CHANNEL THAT WAITS.** Print, email and SMS **push**. The
portal only arrives **if someone comes looking** — so **it can never be the only channel
for anything with a deadline**, and it is *"a record that a message exists, not proof it
arrived."*

⚠ **BLOCKED ON `OQ-1399`.** Whether a notice may be **delivered** on it decides whether
the portal is a convenience layer or a system of record — **and that changes the audit,
the retention and the legal review of nearly every screen in the paying and requesting
sections.** Build the channel, the list and the read state; **stub any path that treats a
portal row as delivery.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-084` | ⚠ The portal **waits**. Never the only channel for a deadline; never proof of arrival | CONFIRMED — blueprint §19 Figure 13 |
| `BR-CWP-083` | Post and email remain the delivery record | CONFIRMED — `CR-068` `R4` |
| — | The channel is switchable per event on `CWP-025`, and turning it off stops the row appearing **while post still goes** | CONFIRMED — `CP-17` |
| `BR-CWP-088` | Whether a notice may be delivered on the portal | **OPEN — `OQ-1399`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Five messages, two unread | The bell reads `2`; opening *"Your August bill is ready — $142.18"* marks it read and the bell reads `1` |
| TC-2 | `CWP-025`'s *in the portal* column | A real switch on every row — ⚠ not a decorative one |
| TC-3 · **negative** | Turn the portal off for *Payment received* | ⚠ The row stops appearing here **and post still goes.** Assert the outbound row still names post |
| TC-4 · **negative** | ⚠ Any path that records a portal row as **delivery** of a notice | `NotImplementedError("OQ-1399")` |
| TC-5 · **negative** | A paperless customer who never signs in | ⚠ Post still went, and the notice's outcome names post. **A customer who does not sign in was never told** |
| TC-6 · **negative** | No messages | An empty state naming what fills it |
| TC-7 · **tenant isolation** | Messages with a Pine Hill session | Pine Hill's only |
| TC-8 | *Mark all read* | The bell reads zero and each row's read timestamp is set |
| TC-9 | A planned-work message | Appears **only** for accounts in the affected area (`US-CWP-011`) |

**4 · Test Data** — *Your August bill is ready — `$142.18`* about `BL-2608-0141`, 30 Aug,
**unread**. *We need two documents for your move-out* about `SR-26-0056`, 3 Sep,
**unread**. *Your payment of `$138.44` was received*, 12 Aug, read. *Water main work on
Elm St, 4–5 September*, 28 Aug, read. *Your June bill was corrected*, 12 Jul, read. 22
rows in total.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Message, about, when | CWP-053 | prototype-extracted | `outbound_message` + its subject | — | system-derived | Names the bill or request |
| Portal delivered | — | GAP | the portal's per-recipient message row, `delivered_at` (⚠ not a column on `outbound_message` — its docstring forbids it; `DEF-CWP-3612`) | timestamptz | system-derived | ⚠ **Queued and visible, never arrived** |
| Read | — | GAP | the same per-recipient row, `read_at` (⚠ not `outbound_message` — `DEF-CWP-3612`) | timestamptz | user-input | Drives the bell |
| The switch | CWP-025 | prototype-extracted | the notification rule catalogue | boolean | user-input | ⚠ Post cannot be switched off |

**6 · Acceptance** — **Given** two unread messages, **when** the customer opens one,
**then** the bell drops from two to one; **and given** the portal channel is switched off
for an event, **then** the row stops appearing here and post still goes; **and** any code
path that would treat a portal row as delivery of a notice raises
`NotImplementedError("OQ-1399")`.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1399` | Is the portal a channel a notice can be delivered on? | `CP-17`, `CP-49`, `CP-50`, this story, and release 3's shape | Product Owner | OPEN — ⚠ **answer before release 3 starts** |

---
id: US-CWP-068
epic: EP-CWP-11
module: portal
screens: [CWP-067]
wave: 3
status: blocked
blocked_by: [OQ-249]
depends_on: [US-CWP-063]
journeys: []
rules: [BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-068 — A visit is booked at the property

**1 · Details** — As **a customer**, I want **to know a crew is coming**, so that **I know
whether I need to be in**.

*"A meter exchange is booked for Tuesday 15 September, morning."* Whether anybody needs to
be in. And the same job shown as done once the crew closes it.

⚠ **A CUSTOMER CANNOT SEE THAT A CREW IS COMING, OR THAT ONE HAS BEEN.** The work order
exists — type, scope, which service, which asset, its state and outcome — **and reaches no
screen.**

⚠ **BLOCKED ON `OQ-249`, THE FIELD-WORK SCOPE QUESTION, WHICH IS OLDER THAN THIS MODULE**
and is the same dependency as `US-CWP-011`. Build the read and the screen against the
existing work order; **stub anything that depends on the unresolved field-work shape.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-093` | No visit, no screen and no link | CONFIRMED — blueprint §16 |
| — | Whether anybody needs to be in is stated | CONFIRMED — `CP-51` |
| — | The same job shows as done once closed | CONFIRMED — `CP-51` |
| — | The field-work module's scope | **OPEN — `OQ-249`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A meter exchange booked for 15 Sep, morning | *"A meter exchange is booked for Tuesday 15 September, morning"*, with whether anybody needs to be in |
| TC-2 | The crew closes it | ⚠ The **same** job shows as done, with its outcome — not a second row |
| TC-3 · **negative** | No visit booked | The screen and its link are absent |
| TC-4 · **negative** | A work order for **another** premises | Absent |
| TC-5 · **tenant isolation** | The visit with a Pine Hill session | Pine Hill's work orders |
| TC-6 · **negative** | Call anything depending on the unresolved field-work shape | `NotImplementedError("OQ-249")` |
| TC-7 | The linked request | Reachable from `CWP-051`, so a customer sees the visit against what they asked for |

**4 · Test Data** — Work order: meter exchange, `1408 Elm St · A`, water, asset
`88-40219`, booked Tuesday 15 Sep 2026 morning, *nobody needs to be in*. A closed variant
with its outcome. A work order at `22 Palm Ct` that must not appear.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Type, scope, service, asset | CWP-067 | prototype-extracted | `WorkOrder` | — | system-derived | ⚠ Reaches no screen today |
| Booked window | CWP-067 | prototype-extracted | `WorkOrder` schedule | date + part-day | system-derived | Plain English — *Tuesday morning* |
| Needs anybody in | CWP-067 | prototype-extracted | the work order's access requirement | boolean | system-derived | Stated either way |
| State and outcome | CWP-067 | prototype-extracted | `WorkOrder.state`, `outcome` | enum | system-derived | Same row when closed |

**6 · Acceptance** — **Given** a meter exchange booked for Tuesday morning, **when** the
customer opens the visit screen, **then** it names the day, the part of the day and
whether anybody needs to be in — and once the crew closes it the same job shows as done.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-249` | The field-work module's scope | `CP-51`, this story, `US-CWP-011` | Product Owner | OPEN — **older than this module** |
