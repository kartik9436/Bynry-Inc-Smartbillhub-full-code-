# EP-CWP-09 — Paying, methods and autopay

**Module:** portal (reads and writes payments) · **Wave:** release **5**
(payment history: release 2) · **Screens:** CWP-038 … CWP-041 · CWP-050 · CWP-077 ·
**Status:** draft

## Scope

**In:** paying a bill, stored methods, autopay, the payment history, why a control is
refused, refunds to the original method, and collecting a connection fee.

**Out:** guest quick pay (`EP-CWP-02`), plans and level pay (`EP-CWP-10`).

⚠ **THE ONE SENTENCE THAT MATTERS MOST IN THE WHOLE BLUEPRINT:** *"There is no way to take
a customer's money in this product."* Autopay records a **promise**, not a charge. There
is no table holding a card or bank detail. **A portal whose central promise is "pay your
bill" needs that built, and it is the largest single piece of work in here.**

⚠ **AND EVERYTHING DOWNSTREAM OF THE GATEWAY IS ALREADY FINISHED AND TESTED.** Recording,
allocating oldest-first by the tenant's rule, reversing, receipting, the balanced pair in
the books, a bounced payment reversing as a new negative row, the bills it paid
re-opening at their own due dates, the late-fee clock never resetting. **Three dashed
boxes, and everything after them is done. This is an integration, not a rebuild.**

⚠ **`CWP-041` — the payment history — SHIPS IN RELEASE 2**, because it reads what staff
already recorded and needs no rails at all.

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-038 | — | — | — | — | Bill · Owing · Paying | — | — | — |
| CWP-039 | — | — | Added desc | — | Method · Added · Used for · Status | Edit · Remove (icons) | — | — |
| CWP-040 | — | — | Date | — | Date · Expected · Status | — | — | — |
| CWP-041 | Payments | All · This year | Date desc | Date · Amount | Date · How · Reference · Applied to · Amount · Status | View · Receipt (icons) | — | CSV |

---
id: US-CWP-045
epic: EP-CWP-09
module: portal
screens: [CWP-038, CWP-077]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-024, US-CWP-006]
journeys: [J30]
rules: [BR-CWP-056, BR-CWP-058, BR-CWP-059]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-045 — Pay now, and where the payment will land, before it commits

**1 · Details** — As **a customer**, I want **to pay and see which bill it settles**, so
that **I am not surprised by where a partial payment went**.

Three steps: how much — the whole balance, just this bill, or another amount; how you are
paying; confirm. A **where it will go** panel showing bill, owing and paying. A
consequence box: *takes `$142.18` from Chase `••••4021` · clears the August bill in full ·
emails you a receipt.*

⚠ **THE "WHERE IT WILL GO" PANEL IS NOT DECORATION.** Payments are allocated by a rule the
utility configures, so a customer paying a partial amount **needs to see which bill it
lands on before they commit** — because afterwards the payment row **cannot be edited,
only reversed** (hard rule 4).

⚠ **STEP THREE IS A CONFIRMATION THE CUSTOMER CAN SCREENSHOT.**

⚠ **AND THE ONE CASE THAT MUST NEVER WRITE A ROW:** a gateway timeout. **A zero is a claim
nobody can make.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-058` | The screen shows where the payment will land before it commits | CONFIRMED — blueprint `P24` |
| `BR-CWP-056` | The Pay control appears, disabled, carrying its reason, until rails land | CONFIRMED — `CR-068` `R3` |
| `BR-CWP-059` | The webhook is idempotent on the reserved key | CONFIRMED — `CP-09` |
| Inherited | Payments are never updated or deleted; a correction is a new row | hard rule 4 |
| Inherited | Every money action writes an audit entry naming the actor | hard rule 7 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Rails absent (today) | ⚠ The Pay control renders **in its normal place, disabled**, with its reason. It is not hidden and it is not clickable |
| TC-2 · **negative** | Force the disabled control | No payment row, no audit row, no gateway call |
| TC-3 | Once rails exist: pay the whole balance `$142.18` | One payment row, allocated to `BL-2608-0141`, one audit entry naming Maria Alvarez, one receipt, and `CWP-041` shows *Cleared* the same minute |
| TC-4 | Pay **another amount** of `$40.00` against a `$142.18` bill | ⚠ The panel shows it landing on `BL-2608-0141` **before** the commit, and afterwards the bill reads owing `$102.18` |
| TC-5 · **negative** | Two open bills, pay `$40.00` | ⚠ The panel shows **oldest first, by the tenant's rule**, and the screen never guesses a different order |
| TC-6 · **negative** | ⚠ The gateway **times out** | The screen says so and **no payment row is written**. Assert zero rows — an unknown outcome is not a zero |
| TC-7 · **negative** | Retry after a timeout | ⚠ Carries the **same** idempotency key generated **before** the first request left, so a debit that already happened is never taken twice |
| TC-8 · **tenant isolation** | Pay against a bill outside the account set | Refused before any money moves |
| TC-9 · **negative** | An account marked **cash-only** | The control is disabled with *"we cannot take card or bank payments on this account"* — ⚠ a reason, not a control that does nothing |
| TC-10 | A delegate with Pay permission pays | The audit entry names **the delegate** |

**4 · Test Data** — Balance `$142.18`, bill `BL-2608-0141` owing `$142.18`. Methods:
`Chase ••••4021` (bank, VERIFIED), `Visa ••••8812` (card, expires 11/27). Partial case
`$40.00`. Two-bill case: `BL-2607-0139` `$18.00` owing and `BL-2608-0141` `$142.18`.
Cash-only account `ACC-10908-A` with `cash_only_no_autopay = true`. Idempotency key
`pay_26_08841`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Amount | CWP-038 | prototype-extracted | `payment.amount` | numeric(18,4) → 2 | user-input | ≤ balance for *whole balance*; any positive for *another amount* |
| Method | CWP-038 | prototype-extracted | `payment_method.id` | uuid FK | user-input | Must belong to this customer |
| Where it will go | CWP-038 | prototype-extracted | the tenant's allocation rule, previewed | — | computed-display | ⚠ **Previewed, then applied by the same rule** |
| Idempotency key | — | B2 | `payment.idempotency_key` | text | system-derived | ⚠ Generated and stored **before the request leaves** |
| Actor | — | hard rule 7 | `audit_log.portal_actor_id` | uuid | system-derived | The delegate where one acted |

**6 · Acceptance** — **Given** a customer with a `$142.18` balance, **when** they choose
to pay `$40.00`, **then** the screen shows it landing on the August bill before they
commit, and afterwards that bill reads owing `$102.18`; **and given** the gateway times
out, **then** no payment row exists and a retry carries the same key.

**7 · Finance Calculation** — The portal computes **nothing**. The amount is the balance
read (`US-CWP-024`) or a customer-entered figure; allocation is the tenant's configured
rule, oldest first by default, already golden-tested.
Worked: `$142.18` paid clears `BL-2608-0141` in full, owing `$0.00`. `$40.00` paid leaves
owing `$102.18`.
⚠ **The preview and the applied allocation must come from the SAME rule**, and a test
that asserts the preview matches the outcome is the one that stops them drifting.

**8 · Open Questions** — None on this screen; the card-fee question belongs to
`US-CWP-046`.

---
id: US-CWP-046
epic: EP-CWP-09
module: payments
screens: [CWP-039, CWP-040]
wave: 5
status: draft            # was `blocked`; OQ-1394 ruled 2026-09-04 — absorb AND surcharge, behind a per-tenant switch; the fee is disclosed before the commit
blocked_by: []
depends_on: [US-CWP-022]
journeys: [J30]
rules: [BR-CWP-057, BR-CWP-040]
golden_tests: []
finance_calc: proposed
---
### US-CWP-046 — Your payment methods: a token, never a card number — and why a control is refused

**1 · Details** — As **a customer**, I want **my saved card and bank account listed
safely**, so that **I do not retype them** — and **when a control will not work, I want
the reason on it.**

A table: method, added, used for, status. A note: *we never hold your full card number.
Your bank or card company holds it and gives us a token — that is why we can only ever
show the last four digits.*

⚠ **THE NOTE IS A DESIGN REQUIREMENT, NOT REASSURANCE COPY.** A stored instrument must be
a **token from the gateway with a brand and a last four** — a utility with one or two
staff cannot carry the compliance burden of holding real card numbers, and the schema
notes describing this table describe exactly that shape.

⚠ **CHANGING OR REMOVING A METHOD REQUIRES A FRESH CODE**, because it is the one action
that redirects money (`US-CWP-022`).

⚠ **AND EVERY REFUSED CONTROL CARRIES ITS REASON.** An account marked cash-only, or with a
bounce count, sees autopay disabled **with words on it** — never a control that silently
does nothing, which `BR-CWP-056` forbids.

⚠ **BLOCKED ON `OQ-1394`:** who pays the card fee — absorbed, surcharged or bank-only. **It
changes this screen and in some states is regulated.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-057` | A token with a brand and last four. **Never a full card number** | CONFIRMED — blueprint `P25` |
| `BR-CWP-040` | Step-up before a method is added, changed or removed | CONFIRMED — blueprint §3 |
| `BR-CWP-056` | A refused control is visible, disabled, and carries its reason | CONFIRMED — `CR-068` `R3`; `CP-48` |
| — | Who pays the card fee | **OPEN — `OQ-1394`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Two saved methods | `Chase ••••4021` bank VERIFIED, used for autopay and one-off; `Visa ••••8812` card expiring 11/27, ACTIVE |
| TC-2 · **negative** | ⚠ The stored row | Contains a **token, a brand and four digits** and nothing else. Assert no column holds more than four digits of a card |
| TC-3 · **negative** | Add a method without a fresh code | Refused (`US-CWP-022`) |
| TC-4 · **negative** | An account marked **cash-only** | Autopay disabled with *"we cannot take card or bank payments on this account"* on it |
| TC-5 · **negative** | An account with two bounces | The reason names the bounces, and the control is disabled rather than absent |
| TC-6 · **negative** | An **expired** card | Status reads expired and it cannot be selected for a payment |
| TC-7 · **tenant isolation** | The list with a Pine Hill session | Pine Hill methods only |
| TC-8 · **negative** | A delegate with See only | Cannot add or remove; a delegate may manage **its own** method only |
| TC-9 · **negative** | Call any card-fee computation | `NotImplementedError("OQ-1394")` |

**4 · Test Data** — `Chase ••••4021`, bank, added 4 Mar 2026, autopay and one-off,
VERIFIED. `Visa ••••8812`, card, added 2 Jun 2026, expires 11/27, one-off, ACTIVE.
Cash-only account `ACC-10908-A`. Bounced account with `nsf_count = 2`. An expired card
`Visa ••••4417` expiring 08/26.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Gateway token | — | schema notes | `payment_method.gateway_token` | text | integration | ⚠ Encrypted at rest via `core/crypto.py` |
| Brand, last four | CWP-039 | prototype-extracted | `payment_method.brand`, `last_four` | text, char(4) | integration | ⚠ **The only digits stored** |
| Used for | CWP-039 | prototype-extracted | `payment_method.used_for` | text[] | user-input | — |
| Refusal reason | CWP-039, CWP-040 | prototype-extracted | `account.cash_only_no_autopay`, `nsf_count` | boolean, integer | system-derived | ⚠ Rendered as words, five or six of them (B14 rule 33) |
| Card fee | CWP-039 | GAP | **none** | — | — | ⚠ **Stubbed on `OQ-1394`** |

**6 · Acceptance** — **Given** a customer with a saved card and bank account, **when** the
methods screen opens, **then** it shows brand and last four only, adding or removing one
demands a fresh code, and on a cash-only account autopay is visibly disabled with the
reason written on it.

**7 · Finance Calculation** — ⚠ **PROPOSED and blocked.** Whether a card fee is absorbed,
surcharged or bank-only decides whether a fee line exists on `CWP-038` at all, what it is
computed from, and whether it is lawful in the customer's state. **No figure here is ours
to choose** — `OQ-1394`.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1394` | Who pays the card fee — absorbed, surcharged or bank-only? | The fee line on `CWP-038` and `CWP-039`, and `CP-08` | Product Owner | OPEN — ⚠ **regulated in some states** |

---
id: US-CWP-047
epic: EP-CWP-09
module: portal
screens: [CWP-040]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-046]
journeys: []
rules: [BR-CWP-056, BR-CWP-058]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-047 — Autopay: an intent that already exists, waiting for a charge that does not

**1 · Details** — As **a customer**, I want **my bill taken automatically**, so that **I
stop remembering it**.

Take it from, how much — the whole balance or a ceiling — and when: **always the due
date, and it cannot be changed**. A consequence box: *takes the balance on each due date ·
emails you three days before · stops if a payment bounces twice.* And a *next few* table
showing the scheduled amount and status.

⚠ **THE SCHEDULED ROW IS REAL.** Issuing a bill **already** writes an intent dated the due
date, carrying **the amount the customer was told**, and it stays fixed even if the bill
is later corrected. **When rails arrive, that intent is what gets executed** — so this
screen is mostly waiting on one integration rather than on new thinking.

⚠ **AND TODAY THE SWITCH WOULD BE A PROMISE NOBODY CAN KEEP.** Enrolment is recorded, an
intent is written, and **there is no path in the product that charges anything.** The
control is visible, disabled and says so.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-056` | Visible, disabled, carrying its reason — never live-but-inert | CONFIRMED — `CR-068` `R3` |
| — | The intent stores the amount and date **as the customer was told**, so a later correction does not silently change what is taken | CONFIRMED — the existing autopay intent |
| — | Autopay is taken **on the due date** and the date is not customer-settable | CONFIRMED — blueprint `P26` |
| Inherited | Payments are never edited; a bounce is a new negative row | hard rule 4 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Today, with no rails | The *Turn autopay on* control is **disabled with its reason**, and the *next few* table still shows the real intent |
| TC-2 | An issued bill of `$142.18` due 14 Sep | The intent row reads `14 Sep 2026 · $142.18 · SCHEDULED` |
| TC-3 | An unbilled future month | Reads `14 Oct 2026 · — · NOT BILLED YET` — ⚠ not an estimate |
| TC-4 · **negative** | ⚠ The bill is **corrected** after the intent is written | The intent still carries **the amount the customer was told**. Assert it did not silently follow the correction |
| TC-5 · **negative** | Try to set a date other than the due date | Refused; the screen offers no such control |
| TC-6 · **negative** | Two bounces | Autopay stops, and the screen says why |
| TC-7 · **negative** | A cash-only account | The control is disabled with the cash-only reason |
| TC-8 · **tenant isolation** | The intents shown | This account's only |
| TC-9 | A ceiling of `$200.00`, balance `$240.00` | ⚠ The utility **rings** rather than taking it — the screen says *"or set a ceiling and we will ring you above it"* |

**4 · Test Data** — Method `Chase ••••4021`. Amount: the whole balance. Next few:
`14 Sep 2026 $142.18 SCHEDULED`, `14 Oct 2026 — NOT BILLED YET`. Correction case:
`BL-2608-0141` `$142.18` intent, then corrected to `$138.00` — the intent stays
`$142.18`. Ceiling case `$200.00` against a `$240.00` balance.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Take it from | CWP-040 | prototype-extracted | `payment_method.id` | uuid FK | user-input | — |
| How much / ceiling | CWP-040 | prototype-extracted | autopay enrolment | numeric(18,4) → 2 | user-input | Above the ceiling, the utility rings |
| When | CWP-040 | prototype-extracted | the bill's `due_on` | date | system-derived | ⚠ **Not settable** |
| Scheduled intent | CWP-040 | prototype-extracted | the existing autopay intent | numeric(18,4) → 2 | system-derived | ⚠ **Frozen at issue** |

**6 · Acceptance** — **Given** an issued bill of `$142.18` due 14 September, **when** the
autopay screen opens, **then** the scheduled row reads that amount and date, the switch
is visibly disabled with its reason, and correcting the bill afterwards does not change
what the intent says.

**7 · Finance Calculation** — No new arithmetic. The intent's amount is the figure the
customer was told at issue, which is existing behaviour and **deliberately does not
follow a later correction** — so the customer is never charged an amount they were not
shown.

**8 · Open Questions** — None. ⚠ Blocked only by rails.

---
id: US-CWP-048
epic: EP-CWP-09
module: portal
screens: [CWP-041]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J36]
rules: [BR-CWP-061, BR-CWP-050, BR-CWP-051]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-048 — Payments and receipts, and a bounce is two rows

**1 · Details** — As **a customer**, I want **everything I have paid, with receipts**, so
that **I can reconcile against my bank statement**.

A table: date, how, reference, applied to, amount, status. Receipts as row actions. A CSV
export.

⚠ **A BOUNCED CHEQUE APPEARS AS TWO ROWS, AND THAT IS CORRECT RATHER THAN CONFUSING.**
Nothing in this product edits a payment; **a reversal is a new negative row against the
original**, which is why the customer sees both. **The wording has to carry it —
*returned by the bank*, sitting directly above the payment it undoes.**

⚠ **AND THE MONEY LIST IS ALSO WHERE ADJUSTMENTS AND WRITE-OFFS APPEAR.** A goodwill
adjustment of `−$25.88` shows with its date and a plain-English reason. **A write-off
shows its amount and date and NEVER its reason code** — the amount belongs to the
customer; *bankruptcy* or *deceased, no estate* does not.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-061` | A bounce is two rows — the payment and the reversal above it | CONFIRMED — blueprint `P27`; hard rule 4 |
| `BR-CWP-050` | An adjustment appears with its date and a plain-English reason | CONFIRMED — `CP-44` |
| `BR-CWP-051` | A write-off shows its amount and date and **never its reason code** | CONFIRMED — `CP-47`; blueprint §17 |
| Inherited | Money displays to two decimals | hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Five payments including a bounce | Newest first, each with method, reference and the bill it went to |
| TC-2 | ⚠ **The bounce** | **Two rows**: `2 Jul · Cheque #10174 · Returned by the bank · −$129.02 · BOUNCED` sitting **directly above** `2 Jul · Cheque #10174 · BL-2606-0147 · $129.02 · REVERSED` |
| TC-3 · **negative** | Try to edit a payment through any portal route | ⚠ No such route exists. Assert the endpoint set contains no update or delete for a payment |
| TC-4 | A goodwill adjustment | `−$25.88` with its date and a plain reason |
| TC-5 · **negative** | A write-off of `$84.20` | Shows *written off* with the date. ⚠ Assert the response body contains **no reason code** |
| TC-6 | A write-off **reversal** | Its own row, ⚠ **not a deletion of the first** |
| TC-7 · **negative** | An account with no payments | An empty state naming what fills it |
| TC-8 · **tenant isolation** | The list with a Pine Hill session | Pine Hill payments only |
| TC-9 | A receipt | The existing document class, served not re-rendered |
| TC-10 | A cheque payment | Shows the **cheque number** as its reference — a human reference, never a row id |
| TC-11 · **negative** | A payment whose confirmation was later corrected | ⚠ Shows the corrected value. The old value lives only in `audit_log`, which is pruned — so **this screen must not be described as a permanent record of the old value** (`OQ-1340`) |

**4 · Test Data** — 12 Aug 2026, bank transfer, `Chase ••••4021`, `BL-2607-0139`,
`$138.44`, CLEARED. 14 Jul, cheque `#10188`, `BL-2606-0147`, `$129.02`, CLEARED. 2 Jul,
cheque `#10174`, *returned by the bank*, `−$129.02`, BOUNCED. 2 Jul, cheque `#10174`,
`BL-2606-0147`, `$129.02`, REVERSED. 13 Jun, card `Visa ••••8812`, `BL-2605-0131`,
`$121.55`, CLEARED. 31 rows in total. Adjustment `−$25.88`, goodwill, reading dispute, 12
Jul. Write-off `$84.20` on 12 May with reason `customer_bankruptcy` that must not surface.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Date, How | CWP-041 | prototype-extracted | `payment.received_on`, `method` | date, enum | system-derived | — |
| Reference | CWP-041 | prototype-extracted | `payment.confirmation` | text | system-derived | ⚠ Cheque number or masked instrument — never a row id |
| Applied to | CWP-041 | prototype-extracted | allocation → `invoice.number` | text | system-derived | *Returned by the bank* on a reversal |
| Amount | CWP-041 | prototype-extracted | `payment.amount` | numeric(18,4) → 2 | system-derived | Negative on a reversal |
| Write-off reason | — | blueprint §17 | `WriteOff.reason` | — | — | ⚠ **NEVER SHOWN** |

**6 · Acceptance** — **Given** a cheque that bounced, **when** the payments list opens,
**then** it shows two rows — the reversal reading *returned by the bank* directly above
the payment it undoes — and a write-off shows its amount and date with no reason code
anywhere in the response.

**7 · Finance Calculation** — No new arithmetic. Reads existing payments, reversals,
adjustments and write-offs.
Worked: `$129.02` paid, then `−$129.02` reversed, net `$0.00` — and `BL-2606-0147`
re-opens at **its own** due date with the late-fee clock unreset, which is existing,
tested behaviour this screen must not contradict.

**8 · Open Questions** — None new. ⚠ **`OQ-1340` is relevant and is OPEN**: whether an
audit row recording a corrected payment reference is exempt from retention pruning. Until
it is answered, **no screen, document or docstring may describe this list as a permanent
record of a corrected value.**

⚠ **AMENDED 2026-09-04 (wave G build lane): THE QUESTION IS `OQ-1340`, NOT `OQ-1330`.**
`OQ-1330` is a real and different question — whether a utility may switch off the check that a
reading's unit matches what the tariff prices in — so the citation did not dangle, **it pointed
at somebody else's question**, which is `DEF-2804`'s shape exactly. `CLAUDE.md` hard rule 4
carried the same misprint until 2026-09-14, when `DEF-GOV-5229` corrected it and §8 above
with it; the register, `amendments.py`, the
migration and `CR-063` task 41 all say `OQ-1340` and are right. **The constraint itself is
unchanged and stands:** the list is not a record of the value a correction replaced.

---
id: US-CWP-049
epic: EP-CWP-09
module: payments
screens: [CWP-045]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-046]
journeys: [J40]
rules: [BR-CWP-060]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-049 — Refunds returned to the method the money came in on

**1 · Details** — As **a customer owed money**, I want **it back the way I paid**, so that
**I am not waiting on a cheque I never asked for**.

The refund timeline reads *"Sent · 21 Sep · to the card ending 8812"* rather than a cheque
number, **when that is how the money came in**.

⚠ **THE REFUND LIFECYCLE IS FULLY BUILT** — raised, approved, issued, cleared or voided,
with a role gate on each step. **What is new is returning it to the original method**,
which needs rails.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-060` | A refund returns to the method the money came in on, and the timeline names it | CONFIRMED — `CP-10` |
| Inherited | A refund is a new row; nothing is edited | hard rule 4 |
| `BR-CWP-048` | A negative final balance is a refund, never a carried credit | CONFIRMED — blueprint `P18` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Money came in by card, refund issued | Timeline reads *"Sent · 21 Sep · to the card ending 8812"* |
| TC-2 | Money came in by **cheque** | Timeline names the cheque, `#10241`, and the address it went to |
| TC-3 · **negative** | Money came in by card, but the card has **expired** | ⚠ Falls back to a cheque **and the timeline says so** — never silently to a dead card |
| TC-4 · **negative** | Money came in across **two** methods | The refund names the split, or names the rule that chose one — ⚠ never a bare *"sent"* |
| TC-5 · **negative** | A voided refund | Shown as voided; ⚠ **not removed from the timeline** |
| TC-6 · **tenant isolation** | The refund with a Pine Hill session | Pine Hill only |
| TC-7 | The four lifecycle steps | Raised, approved, sent, cleared — each with its date, and *"usually within ten working days"* where not yet cleared |

**4 · Test Data** — Refund `$89.80` from the final bill: raised 18 Sep, approved 19 Sep
*by the office*, sent 21 Sep, cleared *usually within ten working days*. Card case
`Visa ••••8812`; cheque case `#10241` to `91 Cedar Row, Austin TX 78704`. Expired-card
case `Visa ••••4417`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Refund state and dates | CWP-045 | prototype-extracted | the refund lifecycle | enum, date | system-derived | Four states, role-gated |
| Destination | CWP-045 | prototype-extracted | `payment_method` of the original payment | text | computed-display | ⚠ Falls back with a stated reason |

**6 · Acceptance** — **Given** a customer refunded `$89.80` who originally paid by card,
**when** the refunds screen opens, **then** the timeline says it went to the card ending
8812 — and where the card has expired it says a cheque was sent instead.

**7 · Finance Calculation** — No new arithmetic. Worked: the `$89.80` from
`US-CWP-037`'s settlement, returned in full. ⚠ **The refund amount must equal the final
bill's settlement figure**, and a test asserting the two agree is what stops the two
screens drifting.

**8 · Open Questions** — None.

---
id: US-CWP-050
epic: EP-CWP-09
module: portal
screens: [CWP-050]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-014, US-CWP-045]
journeys: [J32]
rules: [BR-CWP-058]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-050 — Collecting a connection fee

**1 · Details** — As **an applicant whose request was approved**, I want **to pay the fees
and get the work started**, so that **I am not waiting on a counter visit**.

A fee table: fee, when, amount — with a **waived** fee still on the list, struck through.
Then *to pay now* and *on your first bill*. A note: *work starts once the fees are paid.
The deposit is returned when you close the account, with interest.*

⚠ **A WAIVED FEE STAYS ON THE LIST, STRUCK THROUGH.** The record keeps a **waiver** rather
than deleting the line, which is what lets a customer see they were **let off** rather
than wonder whether they were quoted correctly.

⚠ **AND THE DEPOSIT IS NOT TAKEN NOW.** It lands on the first bill — *"pay-now-or-later
is already a property of the request"*.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-058` | The consequence is shown before the commit | CONFIRMED — blueprint `P24`, `P36` |
| — | A waived fee is struck through, never deleted | CONFIRMED — blueprint `P36` |
| — | Collect-now-or-later is a property of the request | CONFIRMED — the existing fee model |
| `BR-CWP-056` | The Pay control appears disabled until rails | CONFIRMED — `CR-068` `R3` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An approved request with fees due | New connection `$185.00`, meter installation `$150.00`, security deposit `$150.00` *on your first bill*, account set-up `$25.00` **waived** |
| TC-2 | ⚠ **The arithmetic** | *To pay now* = `$185.00 + $150.00` = **`$335.00`**; *on your first bill* = `$150.00`. ⚠ The waived `$25.00` is in **neither** |
| TC-3 | The waived fee | ⚠ **Still listed, struck through** — not absent |
| TC-4 | Once rails exist: pay `$335.00` | The request moves out of *fees due*, and ⚠ **the `$150.00` deposit still shows as due on the first bill rather than being taken now** |
| TC-5 · **negative** | Rails absent | The control is disabled with its reason; the fee table is fully readable |
| TC-6 · **negative** | Pay a partial amount | Refused — fees are collected in full before work starts |
| TC-7 · **tenant isolation** | The fee page with an Oak Ridge session | Refused |
| TC-8 · **negative** | A request **not yet approved** | The page is not reachable; fees are quoted after approval |

**4 · Test Data** — Request `SR-26-0061`, approved, fees due. New connection `$185.00`
before we start. Meter installation `$150.00` before we start. Security deposit `$150.00`
on the first bill. Account set-up `$25.00` **waived**. To pay now **`$335.00`**.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Fee, when, amount | CWP-050 | prototype-extracted | request fees | numeric(18,4) → 2 | system-derived | *Before we start* or *on your first bill* |
| Waived | CWP-050 | prototype-extracted | the fee's waiver | boolean + reason | system-derived | ⚠ Struck through, **kept** |
| To pay now | CWP-050 | prototype-extracted | Σ of *before we start* fees, excluding waived | numeric(18,4) → 2 | computed-display | Must match `CWP-008`'s quote |

**6 · Acceptance** — **Given** an approved application with a waived set-up fee, **when**
the fees screen opens, **then** the waived fee is listed struck through, *to pay now*
reads `$335.00`, and paying it leaves the `$150.00` deposit still showing as due on the
first bill.

**7 · Finance Calculation** — To pay now = Σ(fees where timing = before we start **and
not waived**).
Worked: `$185.00 + $150.00 = $335.00`. Waived `$25.00` excluded. Deposit `$150.00`
deferred to the first bill.
⚠ **This must equal the figure quoted on `CWP-008` before the customer applied.** A
disagreement between the quote and the invoice is the defect both stories test for.

**8 · Open Questions** — None.
