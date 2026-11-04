# EP-CWP-10 — Plans, level pay, credits and arrears

**Module:** portal (reads payments and collections) · **Wave:** release 4 ·
**Screens:** CWP-042 … CWP-045 · CWP-056 · CWP-057 · CWP-063 · CWP-064 · CWP-066 ·
CWP-079 · **Status:** draft

## Scope

**In:** a plan the customer asks for, the whole plan record on screen, a plan the utility
offered and the customer's signature on it, level pay and where it stands, credits and
refunds in flight, the collections ladder with what it would cost, the three hardship
routes, and the protections already holding the account.

**Out:** paying an instalment (`EP-CWP-09`).

⚠ **THESE CARRY THE HIGHEST STAKES IN THE PORTAL.** *"A customer who cannot pay is the one
most likely to be sitting in front of it at midnight"*, and the product already has a
careful, regulated answer for them — a ladder of notices, three kinds of protection, and
a plan that holds while it is kept. **None of it is currently explained to the person it
protects.**

⚠ **AND THESE SIT AHEAD OF PAYMENTS DELIBERATELY.** A customer who can see the ladder, ask
for a plan and reach the hardship routes **is better served whether or not the money can
be taken online yet.**

⚠ **TWO THINGS THE PORTAL MUST NEVER DO:** grant a protection itself — every one needs a
person and a document — and **imply a hold is permanent when it has an expiry date.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-042 | — | — | Due | — | Due · Amount | — | — | — |
| CWP-043 | — | — | Instalment | — | Instalment · Due · Amount · Status | — | — | Agreement |
| CWP-063 | — | — | Due | — | Due · Amount | — | — | Agreement |
| CWP-066 | — | — | Month | — | — | — | — | CSV |
| CWP-057 | — | — | Date | — | — | — | — | — |

---
id: US-CWP-051
epic: EP-CWP-10
module: portal
screens: [CWP-042]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J41]
rules: [BR-CWP-062, BR-CWP-063, BR-CWP-066]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-051 — Ask for a payment plan, and the last instalment carries the rounding

**1 · Details** — As **a customer who cannot pay in one go**, I want **to spread it**, so
that **late fees stop and my supply is not cut**.

Spread it over — between two and twelve months. First payment on. Something up front,
optional, which lowers each instalment. An instalment table with a total. A consequence
box: *five payments of `$22.03`, then one of `$22.05` · late fees stop while you keep to
it · miss two and the plan ends.*

⚠ **THE UNEVEN LAST INSTALMENT IS DELIBERATE AND MUST BE SHOWN.** Dividing a balance into
equal parts leaves a remainder; the product puts it **on the final payment** rather than
silently absorbing a cent — **and a customer comparing the plan against their bank
statement will notice.**

⚠ **THE WORDING IS *ASK FOR*.** Whether a customer may self-serve a plan or must have it
approved is the utility's appetite, not ours — `OQ-1391`.

⚠ **AND THE BLUEPRINT'S OWN FIGURE HERE WAS WRONG AND IT CORRECTED ITSELF.** Its
consequence box read *"six payments of `$22.03`, then one of `$22.05`"* — seven payments
totalling `$154.23` — **beside its own table of six instalments totalling `$132.20`**.
**It is FIVE of `$22.03` and one of `$22.05`.** Use the corrected figures.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-062` | The remainder goes on the **final** instalment, and the screen shows it | CONFIRMED — blueprint `P28`; existing instalment arithmetic |
| `BR-CWP-063` | A plan holds the arrears; **new bills still arrive and still have to be paid** | CONFIRMED — blueprint `P29` |
| `BR-CWP-066` | A plan is GRANTED BY A CLERK; a customer may only ASK | **CONFIRMED 2026-09-04 — `OQ-1391` closed, option (a)** |
| — | Between two and twelve months | CONFIRMED — blueprint `P28` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `$172.20` overdue, six months, `$40.00` up front | ⚠ **Five instalments of `$22.03` and a final `$22.05`, totalling `$132.20`** |
| TC-2 | ⚠ **The arithmetic** | `(172.20 − 40.00) = 132.20`; `132.20 ÷ 6 = 22.0333…`; five at `$22.03` = `$110.15`; final `132.20 − 110.15 = $22.05`. ⚠ **The instalments must sum to exactly the amount covered** |
| TC-3 · **negative** | The consequence box | ⚠ Says **five** payments then one — not six then one. Assert the count in the copy matches the table |
| TC-3a · **negative**, ADDED 2026-09-04 | ⚠ **The box must NOT say *"miss two and the plan ends"*** | The blueprint's own bullet promises it; **the PO ruled the opposite on 2026-08-11** — *"nodrop we chase for payments until write off"* — and that ruling is implemented AS AN ABSENCE and tested (`record_missed_instalment` returns `active` on the tenth miss; `apps/payments/plans.py` has no `void`, no `defaulted`, no `missed_count`). **Worked: two misses would end Maria's plan and make `$66.11` fall due at once under the blueprint; under this product the plan is still active and `$22.03` is still due on 14 February.** The collision is **`OQ-CWP-1720`**, OPEN. Until it is answered the box says what the code does — *if you miss a payment we get in touch; the plan stays open* — and a test asserts no catalogue of the eleven says a plan ends |
| TC-4 · **negative** | Thirteen months | Refused, naming the two-to-twelve range |
| TC-5 · **negative** | Up front greater than the balance | Refused |
| TC-6 · **negative** | Up front equal to the balance | Refused — there is nothing left to spread |
| TC-7 | A balance that divides exactly — `$120.00` over six | Six of `$20.00`; ⚠ **no odd final instalment invented** |
| TC-8 · **negative** | A tenant with plans **switched off** | The screen is unreachable and the endpoint refuses |
| TC-9 · **tenant isolation** | Preview a plan with a Pine Hill session | Pine Hill's balance and settings only |
| TC-10 · **negative** | Call the self-serve activation path | ⚠ **A REFUSAL NOW, NOT A STUB.** `OQ-1391` closed 2026-09-04: the clerk grants a plan and the customer may only ask, so no activation path exists for a customer to reach. The case asserts the refusal rather than a `NotImplementedError` waiting on a ruling |
| TC-11 · **negative** | ⚠ Late-fee suspension where the tenant's setting leaves it **off** | The box says fees **still apply** — it must not promise they stop |

**4 · Test Data** — Overdue `$172.20`. Up front `$40.00`. Six months from 14 Sep 2026.
Instalments: `14 Sep $22.03`, `14 Oct $22.03`, `14 Nov $22.03`, `14 Dec $22.03`,
`14 Jan 2027 $22.03`, `14 Feb 2027 $22.05`. **Total `$132.20`.** Exact-division case
`$120.00` over six. A tenant with `suspend_late_fees = false`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Spread over | CWP-042 | prototype-extracted | `payment_plan.term_months` | smallint | user-input | 2–12 |
| First payment on | CWP-042 | prototype-extracted | `payment_plan.first_due_on` | date | user-input | — |
| Up front | CWP-042 | prototype-extracted | `payment_plan.down_payment` | numeric(18,4) → 2 | user-input | < balance |
| Instalments | CWP-042 | prototype-extracted | `payment_plan_instalment` | numeric(18,4) → 2 | computed-display | ⚠ Remainder on the last |
| Late-fee suspension | CWP-042 box | prototype-extracted | `payment_plan.suspend_late_fees` | boolean | reference-data | ⚠ **Per plan**, not global |

**6 · Acceptance** — **Given** `$172.20` overdue and `$40.00` offered up front over six
months, **when** the preview loads, **then** it shows five instalments of `$22.03` and a
final `$22.05` totalling `$132.20`, the consequence box says **five** then one, and where
the tenant leaves late-fee suspension off it says fees still apply.

**7 · Finance Calculation** — Amount covered = balance − down payment. Base instalment =
truncate(covered ÷ term, 2). Final instalment = covered − (base × (term − 1)).
Worked: `172.20 − 40.00 = 132.20`; `132.20 ÷ 6 = 22.0333…` → base `$22.03`;
`22.03 × 5 = 110.15`; final `132.20 − 110.15 = $22.05`. **Σ = `$132.20`.** ✓
Existing, tested instalment arithmetic — this screen **previews** it and must not
recompute it independently.

⚠ **AMENDED 2026-09-04 (wave M build lane): THE WORD *truncate* ABOVE DESCRIBES THE ENGINE AND
DOES NOT RE-SPECIFY IT, AND A LANE THAT IMPLEMENTED IT LITERALLY WOULD HAVE CONTRADICTED A ❄️
FROZEN FIGURE.** `apps/customers/payment_plan.build_schedule` rounds **half-up** through
`core.money.finalize`, not by truncation. On this story's figures the two agree —
`22.0333… → 22.03` either way — so nothing here moves. On ❄️ **GT-47**'s they do not:
`217.30 ÷ 6 = 36.2166…` is **`36.22`** half-up and `36.21` truncated, and `36.22` is the frozen
figure. The sentence stands as a DESCRIPTION; the engine is the specification, which is what the
next line of this section already says.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1391` | Can a customer give themselves a payment plan, or must a person approve it? | `CP-21`, `CP-23`, this story, `US-CWP-058` | Product Owner | **CLOSED 2026-09-04 → `BR-CWP-066`** — the clerk grants it; the customer may only ask. *"These are special cases"* declines *self-serve within limits* permanently rather than deferring it |

---
id: US-CWP-052
epic: EP-CWP-10
module: portal
screens: [CWP-043]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-051]
journeys: [J41]
rules: [BR-CWP-063, BR-CWP-064]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-052 — Your payment plan, whole — not a monthly summary of it

**1 · Details** — As **a customer on a plan**, I want **the whole record**, so that **I can
reconcile it against my bank statement**.

Instalments with due date, amount and status — *paid on time*, *paid late*, *due in 9
days*, *to come* — and **the payment that cleared each one**. The down payment. The
cadence. A *while the plan holds* panel and a warning about missing two.

⚠ **THE RIGHT-HAND PANEL IS THE PART CUSTOMERS GET WRONG.** **A plan holds the arrears; it
does not pause the current month's bill**, and the product enforces exactly that
distinction. **Saying it here, plainly, is cheaper than the call that comes when the next
bill arrives on top of the plan.**

⚠ **AND FOUR THINGS THE BACK OFFICE HOLDS ABOUT A PLAN REACH NO SCREEN TODAY:** the down
payment after step one, the cadence, whether it takes payment automatically, and **which
payment paid which instalment** — so a customer cannot reconcile a plan against a bank
statement at all.

⚠ **A FINISHED PLAN DISAPPEARS FROM THE PORTAL TODAY. IT MUST NOT.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-063` | A plan holds the arrears; new bills still arrive and still have to be paid | CONFIRMED — blueprint `P29` |
| `BR-CWP-064` | ⚠ Late-fee and disconnection suspension are a **per-plan election**. On a plan where the clerk left it off, the panel must say fees still apply | CONFIRMED — `CP-40` |
| — | Which payment paid which instalment is shown | CONFIRMED — `CP-40` |
| — | A closed plan stays visible | CONFIRMED — `CP-40` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A plan three of six paid | Six rows with statuses *paid on time*, *paid on time*, *paid late*, *due in 9 days*, *to come*, *to come* |
| TC-2 | ⚠ Instalment 2 | Names **the payment that cleared it**, so the customer can match it to their statement |
| TC-3 | The down payment | `$40.00 paid up front` shown — ⚠ so the instalments do not look as though they came from nowhere |
| TC-4 | The cadence | Reads *monthly* from the record, ⚠ **not assumed** |
| TC-5 · **negative** | A plan with `suspend_late_fees = false` | ⚠ The panel says **fees still apply** rather than *no late fees*. This is the case the blueprint singles out as *worse than a blank space* |
| TC-6 | The hold panel | *No late fees on the amount in the plan · no disconnection for that debt · **new bills still arrive and still have to be paid*** |
| TC-7 · **negative** | Two missed instalments | The plan ends and **the whole remaining balance falls due**, and the screen says so before it happens |
| TC-7a · **negative**, ADDED 2026-09-04 | ⚠ **AND TC-7 ABOVE IS WHAT THIS PRODUCT DOES NOT DO** | See `OQ-CWP-1720`, OPEN. `test_us_cwp_052_your_plan.py` asserts the ABSENCE instead: two misses leave the plan `active` and `live`, `closed_on` stays null, and the product holds no machinery that could end it. A test asserting the blueprint's behaviour would be asserting a promise the code does not keep |
| TC-8 · **negative** | A **closed** plan | ⚠ Still reachable, marked closed with its close date — not vanished |
| TC-9 · **tenant isolation** | The plan with a Pine Hill session | Pine Hill's plan only |
| TC-10 | Autopay on the plan | Shown from `autopay_enabled` on the plan row, ⚠ which reaches no screen today |

**4 · Test Data** — Plan over six months, `$40.00` up front, monthly.
`1 of 6 · 14 Sep · $22.03 · PAID ON TIME` (payment `PAY-26-09011`) ·
`2 of 6 · 14 Oct · $22.03 · PAID ON TIME` (`PAY-26-10004`) ·
`3 of 6 · 14 Nov · $22.03 · PAID LATE` (`PAY-26-11077`) ·
`4 of 6 · 14 Dec · $22.03 · DUE IN 9 DAYS` · `5 of 6 · 14 Jan 2027 · $22.03 · TO COME` ·
`6 of 6 · 14 Feb 2027 · $22.05 · TO COME`. A second plan with
`suspend_late_fees = false`. A closed plan from 2025.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Instalment, due, amount | CWP-043 | prototype-extracted | `payment_plan_instalment` | — | system-derived | — |
| Status | CWP-043 | prototype-extracted | derived from due date and payment | enum | computed-display | *Paid late* is distinct from *paid on time* |
| Which payment paid it | CWP-043 | prototype-extracted | `paid_payment`, `paid_posted_on` | uuid FK, date | system-derived | ⚠ **Reaches no screen today** |
| Down payment | CWP-043 | prototype-extracted | `payment_plan.down_payment` | numeric(18,4) → 2 | system-derived | ⚠ Shown, not only at creation |
| Cadence | CWP-043 | prototype-extracted | `payment_plan.cadence` | enum | system-derived | ⚠ Read, never assumed monthly |
| Suspensions | CWP-043 | prototype-extracted | `suspend_late_fees`, `suspend_disconnect` | boolean | system-derived | ⚠ Per plan |
| Closed | CWP-043 | prototype-extracted | `payment_plan.closed_on`, `status` | — | system-derived | Stays visible |

**6 · Acceptance** — **Given** a plan three of six paid with `$40.00` up front, **when**
the plan screen opens, **then** it shows the down payment, the cadence read from the
record, the payment that cleared each paid instalment, and — where the clerk left
late-fee suspension off — that fees still apply.

**7 · Finance Calculation** — No new arithmetic; reads the instalment schedule.
Worked: `$40.00` up front + `5 × $22.03` + `$22.05` = **`$172.20`**, the amount the plan
covers. ⚠ **That total must equal the arrears the plan was raised against**, and a test
asserting it is what catches a plan that silently covers the wrong figure.

**8 · Open Questions** — None. ⚠ `OQ-1391` blocks *asking* for a plan, not *viewing* one
the utility raised.

---
id: US-CWP-053
epic: EP-CWP-10
module: portal
screens: [CWP-063]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-052]
journeys: [J42]
rules: [BR-CWP-065, BR-CWP-063]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-053 — A plan the utility has offered you, and your signature on it

**1 · Details** — As **a customer a clerk has built a plan for**, I want **to see it and
accept it**, so that **it starts without a telephone call**.

*"Pine Hill has offered you a plan. Sarah at the office set this up on 2 September. It
starts when you accept it."* The plan, the instalments, what accepting does, and three
controls in this order: **Accept this plan · Ask for different terms · Decline.**

⚠ **THIS IS THE SCREEN THE BLUEPRINT'S WHOLE §17 AUDIT WAS WRITTEN FOR.** A plan record
moves `proposed → agreement_sent → active → closed`, and the product is explicit that
**a plan activates on the customer's signature alone, not the clerk's.** So
`agreement_sent` means one thing: **offered, waiting on the customer** — and that is the
only state where the customer has something to do. **Three of the four states are drawn
and this one was not.**

⚠ **UNTIL THIS SCREEN EXISTS, THE UTILITY RAISES A PLAN AND THE PERSON IT IS FOR CANNOT
SEE IT, CANNOT ACCEPT IT, AND HEARS ABOUT IT ONLY IF SOMEBODY RINGS THEM.**

⚠ **THE BUTTON ORDER MATTERS:** accepting is one press, and *ask for different terms* is a
**route rather than a dead end**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-065` | A plan activates on the **customer's** signature alone | CONFIRMED — `CP-39`; blueprint §17 Figure 12 |
| — | The offer has an expiry; after it, the office must set it up again | CONFIRMED — blueprint `P49` |
| `BR-CWP-063` | New bills still arrive and still have to be paid | CONFIRMED — blueprint `P29` |
| — | Nothing happens until the customer accepts | CONFIRMED — blueprint `P49` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A plan at `agreement_sent` | The screen opens naming *Sarah at the office* and the date, and the plan covers `$172.20` with `$40.00` already received |
| TC-2 | Accept | ⚠ The row moves `agreement_sent → active` **with the customer's signature date on it**, and `CWP-043` opens showing instalment 1 of 6 as *to come* |
| TC-3 · **negative** | Do nothing | ⚠ The plan stays `agreement_sent`. **Nothing activates on the clerk's action alone** |
| TC-4 · **negative** | Accept after the offer expires on 16 September | Refused with *"the office has to set it up again"* |
| TC-5 | Decline | The plan closes; the arrears are untouched and the ladder resumes |
| TC-6 | *Ask for different terms* | Raises a request that reaches a clerk — ⚠ **not a dead end and not a silent no-op** |
| TC-7 · **negative** | A delegate with See only | Cannot accept. ⚠ **A signature is the holder's** |
| TC-8 · **tenant isolation** | The offer with a Pine Hill session | Pine Hill's plan only |
| TC-9 | The consequence panel | *Late fees stop on the `$172.20` while you keep to it · no disconnection for that debt · **new bills still arrive** · miss two and the plan ends* |
| TC-10 | The agreement document | Downloadable, and it is the **existing** agreement document class |

**4 · Test Data** — Plan offered 2 Sep 2026 by *Sarah Miller*. Covers `$172.20` overdue.
`$40.00` paid up front, already received. Six monthly instalments from 14 Sep: five at
`$22.03`, final `$22.05`, total `$132.20`. **Offer stands until 16 September 2026.**

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Who set it up, when | CWP-063 | prototype-extracted | the plan's creating actor | text, date | system-derived | A person's name, never a user id |
| Status | — | prototype-extracted | `payment_plan.status` | enum | system-derived | `agreement_sent` is the state this screen exists for |
| Signature date | — | GAP | `payment_plan.customer_signed_on` | timestamptz | user-input | ⚠ **Activation depends on it** |
| Offer expiry | CWP-063 | GAP | `payment_plan.offer_expires_on` | date | reference-data | Refuses acceptance after |
| Agreement | CWP-063 | prototype-extracted | `document` where kind = agreement | — | system-derived | Existing class |

**6 · Acceptance** — **Given** a clerk has built a plan that sits waiting for a signature,
**when** the customer opens the offer and accepts it, **then** the plan becomes active
with their signature date on it and instalment 1 of 6 reads *to come* — and doing nothing
leaves it waiting, because the clerk's action alone never activates it.

**7 · Finance Calculation** — Reads the same instalment arithmetic as `US-CWP-051`.
Worked: `$172.20` covered, `$40.00` received, `5 × $22.03 + $22.05 = $132.20`.
⚠ **The figures on the offer must be byte-identical to the plan that activates** — a
customer who accepts one schedule and receives another is the worst outcome on this
screen.

**8 · Open Questions** — None. ⚠ `OQ-1391` does **not** block this story: a plan the
**utility** offered needs no ruling on customer self-service.

---
id: US-CWP-054
epic: EP-CWP-10
module: portal
screens: [CWP-044]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: []
rules: [BR-CWP-054]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-054 — Level pay: pay the same amount every month

**1 · Details** — As **a customer whose August bill hurts**, I want **the same amount every
month**, so that **a hot summer does not surprise me**.

*"We average your year and settle up once."* Last twelve months, the monthly average, the
rounded level, and what you would pay. A chart of bills against the level. A consequence
box: *every bill reads `$125.00` · we check the figure twice a year · June settles the
difference, up or down.*

⚠ **LEVEL PAY IS GENUINELY FINISHED BEHIND THE COUNTER AND HIDDEN FROM THE PERSON IT
HELPS.** Eligibility months, the rounding of the level, the re-level cadence and bound,
the settle-up month and the drop-off rule are **all configured settings today.** **This
screen is a view over machinery that already runs.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-054` | The level, the variance and the settle-up month are shown | CONFIRMED — `CP-46` |
| — | Eligibility, rounding, re-level cadence and settle-up month are **tenant settings**, read not assumed | CONFIRMED — the existing budget billing |
| Inherited | Money displays to two decimals | hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Twelve months totalling `$1,501.09` | Average `$125.09`, **rounded to `$125.00`**, and *you would pay `$125.00`* |
| TC-2 | ⚠ **The rounding** | `$1,501.09 ÷ 12 = $125.0908…`; the level is `$125.00` **by the tenant's rounding setting**, not by a rule in the portal |
| TC-3 · **negative** | An account with **fewer** months than the eligibility setting | Not offered, with the reason in words |
| TC-4 · **negative** | An already-enrolled account | ⚠ Routed to `CWP-066`, not offered enrolment again |
| TC-5 | The chart | Bars are what was billed; the line is `$125.00` |
| TC-6 · **negative** | A tenant whose settle-up month is not June | The box names **that** month, read from the setting |
| TC-7 · **tenant isolation** | Eligibility with a Pine Hill session | Pine Hill's settings and history only |
| TC-8 | *This month, either way* | Shows the level beside what this month would otherwise be |

**4 · Test Data** — Last twelve months `$1,501.09`. Monthly average `$125.09`. Rounded
level `$125.00`. Settle-up month June. Re-level twice a year. An account with four months
of history for TC-3.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Last twelve months | CWP-044 | prototype-extracted | billed totals | numeric(18,4) → 2 | computed-display | — |
| Monthly average, level | CWP-044 | prototype-extracted | budget-billing level | numeric(18,4) → 2 | computed-display | ⚠ Rounded by the **tenant's** setting |
| Settle-up month | CWP-044 | prototype-extracted | tenant setting | text | reference-data | ⚠ Named, not hardcoded to June |

**6 · Acceptance** — **Given** twelve months totalling `$1,501.09`, **when** the level-pay
screen opens, **then** it shows an average of `$125.09` rounded to a level of `$125.00`
and names the tenant's own settle-up month.

**7 · Finance Calculation** — Level = round(Σ last twelve billed ÷ 12) by the tenant's
rounding rule. Worked: `$1,501.09 ÷ 12 = $125.0908…` → `$125.00`. Existing, configured
arithmetic; **read, not recomputed.**

**8 · Open Questions** — None.

---
id: US-CWP-055
epic: EP-CWP-10
module: portal
screens: [CWP-066]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-054]
journeys: []
rules: [BR-CWP-054]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-055 — Where your level pay stands

**1 · Details** — As **a customer on level pay**, I want **to know what it is really
costing**, so that **June does not surprise me**.

Three tiles — you pay each month, you are ahead or behind by, settles up in. A chart of
paid against used. A *what happens in June* panel. A CSV export. And every re-levelling
with what actually happened that year.

⚠ **AN ENROLLED CUSTOMER HAS NO SCREEN AT ALL TODAY** — not their level, not the variance
building up, not the settle-up month. `CWP-044` is the **joining** screen; this is the
one that was missing.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-054` | The level, the variance and the settle-up, plus each re-levelling and what happened | CONFIRMED — `CP-46` |
| Inherited | Money to two decimals; a variance may be either sign | hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Enrolled since 1 Jan 2026 at `$125.00` | *You pay `$125.00` · you are `$47.30` ahead · June settles up* |
| TC-2 · **negative** | A customer **behind** by `$47.30` | Reads *behind*, and the June panel says it is **added** to that bill |
| TC-3 | Each re-levelling | Listed with its actual, its movement and the balance after |
| TC-4 · **negative** | A level with an **override** and a reason | The override is shown; ⚠ the internal reason code is not |
| TC-5 · **negative** | A customer **not** on level pay | Routed to `CWP-044`; this screen is absent |
| TC-6 · **tenant isolation** | Standing with a Pine Hill session | Pine Hill only |
| TC-7 | The variance sign | ⚠ *Ahead* and *behind* in words — never a bare signed number |
| TC-8 | CSV | Each row carries the month, what was paid and what was used |

**4 · Test Data** — Level `$125.00` since 1 Jan 2026. Variance `$47.30` **ahead**.
Settle-up June. One re-levelling in the record with its actual and its movement. A
behind-by-`$47.30` variant.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Level, variance, settle-up month | CWP-066 | prototype-extracted | `AccountBudgetStatus` | numeric(18,4) → 2, text | system-derived | ⚠ Reaches no screen today |
| Each re-levelling | CWP-066 | prototype-extracted | `AccountBudgetEvent` | — | system-derived | With actual, movement and balance after |
| Override and reason | CWP-066 | prototype-extracted | `AccountBudgetStatus.override*` | — | system-derived | ⚠ The value, not the internal code |

**6 · Acceptance** — **Given** a customer paying `$125.00` a month who is `$47.30` ahead,
**when** the standing screen opens, **then** it says so in words, names June as the
settle-up month, and lists each re-levelling with what happened that year.

**7 · Finance Calculation** — Variance = Σ paid − Σ billed since enrolment.
Worked: `$47.30` ahead means paid exceeds used by that amount, and June's bill is reduced
by it. Existing, tested arithmetic; **read.**

**8 · Open Questions** — None.

⊕ **AS BUILT (2026-09-04, shipped in `2.164.0`).** The level is `budget_service.effective_level` (the override if
there is one, else the computed level), the variance is `variance_balance` — a CACHE whose
truth is the append-only `account_budget_events` — and each re-levelling is an event row read
out with its actual, its movement and the balance after. **This screen carries none of
`CWP-044`'s figures**: no trailing total, no monthly average, no *you would pay*, because
those answer *what would I pay if I joined* and repeating them here would be a second
arithmetic over one fact. One test asserts this screen's `$125.00` against the JOINING
screen's own read on the same account, so the two cannot drift into two `$125.00`s that stop
being equal; another asserts the variance against `budget_service.recompute_balance`, so a
portal that ever started summing events itself would go red. **`ahead` and `behind` travel as
a DIRECTION beside a positive size** (TC-7) and the catalogue writes the sentence.
**`level_override_reason` is not on the wire at all** (TC-4): the test asserts its absence
from the body AND that the column still holds it, so a reader can tell *withheld* from *lost*.

---
id: US-CWP-056
epic: EP-CWP-10
module: portal
screens: [CWP-045]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J40]
rules: [BR-CWP-047, BR-CWP-060]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-056 — Credits and refunds in flight, and they are different things

**1 · Details** — As **a customer owed money**, I want **to know whether it is coming back
or coming off**, so that **I stop asking**.

Two halves. **A refund on its way** — raised, approved, sent, cleared, each with its date.
**Credits on the account** — what, when, amount, and which bill they were used on. And
one line that does the work: *a credit comes off your next bill. A refund is money sent
back.*

⚠ **CREDIT AND REFUND ARE DIFFERENT THINGS AND CUSTOMERS USE THE WORDS
INTERCHANGEABLY**, so the screen has to separate them.

⚠ **AND IT MUST NEVER SHOW A CREDIT FIGURE IT CACHED, BECAUSE A CREDIT THAT WAS REAL ON
TUESDAY CAN BE SPENT BY THURSDAY.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-047` | ⚠ The credit figure is **re-read on every load**, never cached | CONFIRMED — `CP-27` |
| `BR-CWP-060` | The refund names the method it is going back to | CONFIRMED — `CP-10` |
| — | The refund lifecycle is raised → approved → issued → cleared or voided, role-gated at each step | CONFIRMED — the existing lifecycle |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A refund at *approved* | *Raised · 18 Sep `$89.80` after your final bill · Approved · 19 Sep by the office · Sent · 21 Sep · Cleared usually within ten working days* |
| TC-2 | Two credits of `$25.88` | Both listed with their date and the bill they were used on |
| TC-3 · **negative** | ⚠ Spend a credit between two loads | The second load shows the **new** figure. Assert no cache |
| TC-4 · **negative** | A **voided** refund | Shown as voided, ⚠ not removed |
| TC-5 · **negative** | The separating sentence | Present and unambiguous — a screen that calls both *"money back"* is the defect |
| TC-6 · **tenant isolation** | The screen with a Pine Hill session | Pine Hill only |
| TC-7 · **negative** | No credits and no refunds | ⚠ The screen and its link are absent |
| TC-8 | A refund from a card payment | Names *"to the card ending 8812"* (`US-CWP-049`) |

**4 · Test Data** — Refund `$89.80`: raised 18 Sep, approved 19 Sep by the office, sent
21 Sep by cheque `#10241` to `91 Cedar Row`, clearing within ten working days. Credits:
goodwill from a reading dispute, `$25.88`, 12 Jul 2026, used on `BL-2607-0139`; overcharge
corrected, `$25.88`, 12 Jul 2026, used on `BL-2607-0139`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Refund state and dates | CWP-045 | prototype-extracted | the refund lifecycle | enum, date | system-derived | Four states |
| Credit, when, amount, used on | CWP-045 | prototype-extracted | credit notes and their allocations | numeric(18,4) → 2 | computed-display | ⚠ **Re-read every load** |

**6 · Acceptance** — **Given** a refund approved on 19 September and two credits of
`$25.88`, **when** the screen opens, **then** the refund's four steps show with their
dates, the credits show with the bill they were used on, and one sentence separates a
credit that comes off the next bill from a refund that is money sent back.

**7 · Finance Calculation** — No new arithmetic. Worked: `$89.80` refund from the final
bill; `2 × $25.88 = $51.76` of credit already applied to `BL-2607-0139`. ⚠ **The refund
figure must equal `US-CWP-037`'s settlement.**

**8 · Open Questions** — None.

---
id: US-CWP-057
epic: EP-CWP-10
module: portal
screens: [CWP-057, CWP-079]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J43]
rules: [BR-CWP-091, BR-CWP-092, BR-CWP-051]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-057 — What happens if this is not paid: the ladder, and what it would cost

**1 · Details** — As **a customer behind on a bill**, I want **to know exactly what happens
next and what it will cost**, so that **I can stop it**.

*"`$412.60` is overdue by 19 days."* A timeline of what has already happened and what is
coming — due, reminder sent, late fee added, first notice sent, final notice, supply
disconnected. Beside it, **what it would cost**: owed now, reconnection fee, new deposit,
**if it goes that far**. And two controls: **ask for a plan**, pay.

⚠ **THE MOST UNCOMFORTABLE SCREEN IN THE PORTAL, AND THE MOST USEFUL.** Everything on the
timeline is already decided by configured settings — reminder cadence, notice tier days,
the plan-notice window. **Showing the total cost of letting it run, next to a button that
stops it, is the whole argument for putting collections in front of the customer instead
of only in front of the clerk.**

⚠ **AND IT READS THIS ACCOUNT'S OWN CASE, NOT THE CADENCE SETTINGS.** The customer's own
disconnection record carries the tier reached, the date a cut is scheduled for, the
reconnection fee, **which services would be cut** and what happens to the deposit — 28
fields, and *"the single most consequential record about them is the one they cannot
see."*

⚠ **A RUNG THE TIER VOCABULARY CANNOT NAME IS RENDERED AS AN ABSENCE, NEVER ROUNDED.**
Showing a customer at the five-day notice as though they were at the ten-day one **moves
the date they think they have.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-092` | ⚠ An unmapped tier renders as an **absence**, never rounded to the nearest | CONFIRMED — `CP-42`; the code returns `TIER_UNMAPPED` |
| — | The ladder is read from **this account's case**, not from cadence settings | CONFIRMED — `CP-42` |
| `BR-CWP-091` | A hold stops a disconnection, not the debt | CONFIRMED — blueprint `P50` |
| `BR-CWP-051` | A write-off shows amount and date, never its reason | CONFIRMED — `CP-47` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `$412.60` overdue 19 days, first notice sent 1 Sep | The timeline shows due 14 Aug, reminder 21 Aug, late fee `$8.25` on 24 Aug, first notice 1 Sep, final notice *around 15 Sep*, disconnection *no earlier than 25 Sep* |
| TC-2 | ⚠ **The cost arithmetic** | Owed `$412.60` + reconnection `$95.00` + new deposit `$150.00` = ***if it goes that far `$657.60`*** |
| TC-3 · **negative** | ⚠ A customer at the **five-day** notice, which has no tier chip | The tier renders as an **absence**. Assert the screen does **not** show the ten-day tier's date |
| TC-4 · **negative** | The timeline | ⚠ Built from **this account's `DisconnectCase`**, not from the tenant's cadence. Assert two accounts at different tiers show different dates |
| TC-5 | Which services would be cut | Named from the case |
| TC-6 · **negative** | An account with a protection in force | The timeline shows the hold and **why it is paused** |
| TC-7 · **tenant isolation** | The ladder with a Pine Hill session | Pine Hill's case only |
| TC-8 | *Ask for a plan* | Reaches `CWP-042` carrying the `$412.60` |
| TC-9 · **negative** | A write-off on the account | Its amount and date show; ⚠ **no reason code in the response** |
| TC-10 · **negative** | An account **not** overdue | The screen and its link are absent |

**4 · Test Data** — `22 Palm Ct`, `$412.60` overdue by 19 days. Due 14 Aug 2026. Reminder
sent 21 Aug by email and post. Late fee `$8.25` added 24 Aug. First notice sent 1 Sep by
post. Final notice around 15 Sep, delivered by hand or tracked post. Disconnection no
earlier than 25 Sep. Reconnection fee `$95.00`. New deposit `$150.00`. **If it goes that
far `$657.60`.** A second account at the five-day notice with `TIER_UNMAPPED`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Overdue amount, days | CWP-057 | prototype-extracted | the balance read + oldest due date | numeric(18,4) → 2, integer | computed-display | — |
| The timeline | CWP-057 | prototype-extracted | `AccountCollectionState` + `NoticeHistory` | — | system-derived | ⚠ This account's, not the cadence |
| Tier | CWP-057 | prototype-extracted | `AccountCollectionState.tier` | enum | system-derived | ⚠ `TIER_UNMAPPED` renders as absence |
| Cut date, services, reconnection fee, deposit outcome | CWP-057 | prototype-extracted | `DisconnectCase` (28 fields) | — | system-derived | ⚠ Reaches no screen today |
| If it goes that far | CWP-057 | prototype-extracted | owed + reconnection + new deposit | numeric(18,4) → 2 | computed-display | Sum of three shown figures |

**6 · Acceptance** — **Given** an account `$412.60` overdue by 19 days with a first notice
already sent, **when** the overdue screen opens, **then** it shows the real timeline from
that account's own case, states that letting it run costs `$657.60`, and offers a plan
beside it — and a customer at an unmapped tier is shown an absence rather than somebody
else's date.

**7 · Finance Calculation** — If it goes that far = amount owed + reconnection fee + new
deposit. Worked: `$412.60 + $95.00 + $150.00 = $657.60`.
All three are configured settings read from the tenant and the case; **the sum is the only
arithmetic and it must equal the three displayed figures.**

⚠ **AMENDED 2026-09-05 (wave L1 build lane): THE `$150.00` DEPOSIT HAS NO SOURCE IN THIS
PRODUCT, SO THE SCREEN SHOWS `$507.60` AND STATES THE GAP.** The sentence above says all
three are *"configured settings read from the tenant and the case"*. **Two of them are.**
`apps/customers/disconnects.reconnection_terms` reads the tenant's own `CC-RECON` charge
for the fee and records `new_deposit_required` as **True, False or None** — and it carries
**no deposit amount at all**, deliberately: `DSC-02.4` says only *"Nothing is held, so a
new deposit is required to reconnect"* and the module states in its own words that
*"Nothing collects that new deposit and nothing posted the application."* The one deposit
figure this product holds is `rating.PlanDepositRule.amount`, which prices a **NEW
CONNECTION** for a class of customer, and nothing says a reconnection asks the same.

So `GET accounts/{id}/arrears` serves `owed $412.60` + `reconnection_fee $95.00` as a
**`subtotal` of `$507.60`** with `parts_missing: ["new_deposit"]`, and **there is no field
on the wire a screen could label *if it goes that far***, because a total that silently
omits a deposit is a total the customer discovers is wrong at the counter. A `$0.00` would
have passed every other check in this repo. **`OQ-CWP-1600` is OPEN** with three options;
`tests/test_us_cwp_057_059_arrears.py::…tc2…` asserts the absence and was proved RED by
making the deposit a `$0.00`. §4's `$657.60` and §6's acceptance sentence stand as the
figures to re-assert the day that question closes.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-CWP-1600` | What does a new deposit cost to get reconnected — and is it the same figure a new customer pays? | The DEPOSIT LINE of the *what it would cost* panel and its total. The screen, the timeline, the tier absence, the fee, the write-off and both controls all ship | Product Owner | **OPEN** — added 2026-09-05, see §7's amendment |

---
id: US-CWP-058
epic: EP-CWP-10
module: portal
screens: [CWP-056]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-057]
journeys: [J43]
rules: [BR-CWP-089, BR-CWP-090]
golden_tests: []
finance_calc: none
---
### US-CWP-058 — Help paying: three doors, and one of them is not a door

**1 · Details** — As **a customer who cannot pay**, I want **the options in front of me**,
so that **I do not have to know what to ask for**.

*"There are three things we can do. Ask before the final notice and all three stay
open."* **Spread it out** — a plan. **Someone here is unwell** — a doctor's certificate,
*"it has an expiry date and it is not permanent"*. **Level out next year** — level pay.
Then a line: *between 1 December and 1 March nobody is disconnected in this state,
whatever they owe. **You do not have to ask for that.***

⚠ **THREE DOORS, AND ONE OF THEM IS NOT A DOOR AT ALL.** The weather moratorium is a window
**the regulator sets** — nobody applies for it — so it is **stated as a fact rather than
offered as an action.**

⚠ **AND THE MEDICAL CERTIFICATE WORDING CARRIES ITS EXPIRY**, because a customer who
believes a hold is permanent **stops paying and is disconnected the week it lapses.** That
sentence exists in the product already and needs to reach the person it is about.

⚠ **THE PORTAL MAY NEVER GRANT A PROTECTION ITSELF.** Every one needs a person and a
document.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-089` | The portal never grants a protection; each needs a person and a document | CONFIRMED — blueprint §14 Figure 9 |
| `BR-CWP-090` | ⚠ Three different lifetimes, three different sentences. Never imply a hold is permanent | CONFIRMED — blueprint §14, `P50` |
| `BR-CWP-066` | A plan is GRANTED BY A CLERK; a customer may only ASK | **CONFIRMED 2026-09-04 — `OQ-1391` closed, option (a)** |
| — | The moratorium is stated as a fact with **no button** | CONFIRMED — blueprint `P42` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An account `$412.60` overdue | Three cards: a plan over up to twelve months, a certificate route, and level pay |
| TC-2 · **negative** | ⚠ The moratorium | Stated as a fact, `1 December` to `1 March`, **with no button** — assert no control exists |
| TC-3 · **negative** | ⚠ The certificate card | Says **in words** that the hold expires and is not permanent |
| TC-4 · **negative** | Submit a certificate through the portal | ⚠ It becomes a **request a person judges**; assert no protection row is created by the form |
| TC-5 · **negative** | ⚠ Uploading the certificate | Not possible — consumer upload is deferred. The route ends with *bring it to the office* |
| TC-6 · **negative** | A tenant with plans switched off | The plan card is absent and its endpoint refuses; the other two remain |
| TC-7 · **tenant isolation** | The screen with a Pine Hill session | Pine Hill's moratorium dates and settings |
| TC-8 · **negative** | An account **past** the final notice | ⚠ **AMENDED 2026-09-05 — ALL THREE STAY OPEN AND THE SCREEN SAYS TIME IS SHORT.** The original expectation was *"the screen says which routes are still open"*, and **measured, none of them closes**: `record_protection` has no tier gate, `BR-CWP-066` lets a clerk grant a plan at any tier, and level pay is unrelated to the ladder. Closing a door the product would still open turns a frightened customer away from help they can still get. Built as `still_open: true` on all three with `past_final_notice: true` beside them; the collision with `P42`'s drawn sentence is **`OQ-CWP-1601`**, OPEN |
| TC-9 · **negative** | Call plan self-activation | ⚠ **AMENDED 2026-09-05 — A REFUSAL, NOT A STUB.** `OQ-1391` CLOSED 2026-09-04 (`BR-CWP-066`, option (a)): the clerk grants a plan and the customer may only ask, **so no activation path exists for a customer to reach and a stub would be a door.** This row read `NotImplementedError("OQ-1391")` while `US-CWP-051` TC-10 in this same file already said the opposite; `US-CWP-051` is right and this is corrected to match it |

**4 · Test Data** — Account `$412.60` overdue. Moratorium `1 December 2026` to
`1 March 2027`, set by the regulator. Plan over up to twelve months. Medical certificate
route. Level pay route. A past-final-notice variant.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| The three routes | CWP-056 | prototype-extracted | plans, protections, budget billing | — | reference-data | Gated by the tenant's switches |
| Moratorium window | CWP-056 | prototype-extracted | the moratorium record's start and end | date | reference-data | ⚠ **Read from the record**, not written in prose |
| Certificate route | CWP-056 | prototype-extracted | a service request | — | user-input | ⚠ Never creates a protection |

**6 · Acceptance** — **Given** an account `$412.60` overdue, **when** the help-paying screen
opens, **then** it offers a plan, a certificate route and level pay, states the
moratorium as a fact with no button, says in words that a certificate hold expires — and
nothing on the screen grants a protection.

**7 · Finance Calculation** — N/A. ⚠ The plan figures come from `US-CWP-051`.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1391` | Can a customer give themselves a payment plan? | The plan card's behaviour | Product Owner | **CLOSED 2026-09-04 → `BR-CWP-066`** — the clerk grants it; the customer may only ask. ⚠ **THIS ROW READ *OPEN* UNTIL 2026-09-05** while the same question's row under `US-CWP-051` in this very file already said CLOSED; corrected here rather than left, and TC-9 below is amended with it |
| `OQ-CWP-1601` | Does any hardship route close once the final notice has gone out? | Nothing. All three are offered at every tier | Product Owner | **OPEN — non-blocking**, added 2026-09-05. `P42`'s *"ask before the final notice and all three stay open"* reads as though something closes after it, and **nothing in this product closes any of them**: `record_protection` has no tier gate, a clerk may grant a plan at any tier, and level pay is unrelated to the ladder. **Worked:** an account `$412.60` overdue that has had its 48-hour certified letter can still be granted a plan, still have a certificate accepted and still join level pay. Built as `still_open: true` on all three with `past_final_notice: true` carrying the urgency, because **closing a door the product would still open turns a frightened customer away from help they can still get** |

---
id: US-CWP-059
epic: EP-CWP-10
module: portal
screens: [CWP-064]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-058]
journeys: [J43]
rules: [BR-CWP-090, BR-CWP-091]
golden_tests: []
finance_calc: none
---
### US-CWP-059 — What is protecting your supply: three lifetimes, three sentences

**1 · Details** — As **a customer with a hold on the account**, I want **to know what is
protecting me and until when**, so that **I am not cut off the week it lapses**.

Three cards, each with its own shape. **A doctor's certificate** — holding now, since,
**ends on**, and *"this is not permanent. On 1 December the hold lifts and the account
carries on where it left off. Send a new certificate before then if it is still needed."*
**Your payment plan** — holding now, **ends on no date**, because it is not a period: *"it
holds while the plan is current, and it lifts the day an instalment is missed."*
**Winter moratorium** — starts 1 December, until 1 March, set by the regulator, **no
button.** Then one warning across all three: *a hold stops a disconnection. It does not
stop the debt.*

⚠ **THE PRODUCT ALREADY ENFORCES ALL THREE LIFETIMES** — a medical certificate **must**
carry an end date, a plan hold **must not**, a moratorium carries both a start and an end.
**§14 states as a rule that the customer must be told the expiry in words, and until this
screen there was nowhere for those words to go.**

⚠ **THE MIDDLE CARD IS THE ONE THAT SAVES MONEY.** A customer who believes a plan hold is
permanent **stops paying and is cut the week it lapses.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-090` | ⚠ Three lifetimes, three sentences. A certificate has an end date; a plan hold has none and lifts on a missed instalment; a moratorium is a fixed window nobody applies for | CONFIRMED — blueprint §14, `P50`; the three enforced lifetimes |
| `BR-CWP-091` | A hold stops a disconnection, **not the debt** — interest and the balance carry on | CONFIRMED — blueprint `P50` |
| `BR-CWP-089` | The portal shows protections; it never grants one | CONFIRMED — blueprint §14 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A certificate holding since 14 Aug, ending 30 Nov | *"A doctor's certificate is holding your supply until 30 November"*, and **in words** that it is not permanent |
| TC-2 · **negative** | ⚠ The plan hold | Carries **no date** and says instead that it ends the day an instalment is missed. Assert no expiry date is invented for it |
| TC-3 | The moratorium | `1 December 2026` to `1 March 2027`, read from the record, **with no button** |
| TC-4 · **negative** | ⚠ A certificate with **no end date** in the data | Refused upstream by the product's own rule — *a certificate with no end date is a permanent exemption nobody signed.* This screen must not render one |
| TC-5 | The warning | *A hold stops a disconnection. It does not stop the debt.* Present on the screen, not only in help |
| TC-6 · **negative** | An account with **no** protection | ⚠ The screen and its link are absent — not three empty cards |
| TC-7 · **negative** | A protection already **lifted** | Shown as lifted with its date, not silently removed |
| TC-8 · **tenant isolation** | The screen with a Pine Hill session | Pine Hill's protections and moratorium dates |
| TC-9 · **negative** | A state whose moratorium dates change | ⚠ The sentence follows the **record**. Assert changing the record changes the screen — the blueprint's own `P42` states the window in prose and this story fixes that |

**4 · Test Data** — Medical certificate holding since 14 Aug 2026, **ends 30 Nov 2026**.
Payment-plan hold, holding while the plan is kept, **no end date**. Winter moratorium
`1 Dec 2026` – `1 Mar 2027`, regulator-set. A lifted protection from 2025. An account with
none.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Kind, effective from, expires on, lifted on | CWP-064 | prototype-extracted | `AccountProtection` | enum, date | system-derived | ⚠ Reaches no screen today |
| Plan hold | CWP-064 | prototype-extracted | derived from the plan being active and current | — | computed-display | ⚠ **Carries no end date** |
| Moratorium window | CWP-064 | prototype-extracted | the moratorium record's start **and** end | date | reference-data | ⚠ Read, never in prose |

**6 · Acceptance** — **Given** an account held by a certificate ending 30 November and a
current payment plan, **when** the protections screen opens, **then** the certificate
names its end date and says in words it is not permanent, the plan hold carries no date
and says it lifts on a missed instalment, the moratorium is stated with no button, and one
line says a hold stops a disconnection but not the debt.

**7 · Finance Calculation** — N/A. ⚠ **The debt continues underneath and the screen says
so** — that sentence is the finance-relevant content.

**8 · Open Questions** — None.
