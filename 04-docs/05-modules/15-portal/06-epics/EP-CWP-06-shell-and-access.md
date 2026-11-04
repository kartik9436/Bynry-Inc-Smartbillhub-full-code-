# EP-CWP-06 — The shell, the account set, and delegated access

**Module:** portal · **Wave:** release 2 (delegates: release 4) ·
**Screens:** CWP-020 … CWP-026 · CWP-065 · CWP-076 … CWP-079 · **Status:** draft

## Scope

**In:** the shell every signed-in screen sits inside, the balance read nothing currently
publishes, the home page, the multi-account view, adding an account, editable details,
delegated access, the account facts that are held and never shown, and the four phone
screens.

**Out:** bills (`EP-CWP-07`), usage (`08`), money (`09`, `10`), requests (`11`).

⚠ **THE BALANCE READ IS THE FIRST THING TO BUILD IN THE WHOLE MODULE.** The blueprint
calls it *"the single most-requested number in the whole product"* and *"the number every
screen leans on and nothing currently publishes"*. An account's credit only reaches the
wire attached to a step that has already happened; **there is no read that answers what
this account owes right now.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-022 | — | — | — | — | — | — | — | — |
| CWP-023 | Accounts | All · Owing · On a plan | Address | Address · Balance | Address · Services · Next due · Balance · Status | View · Pay (icons) | Pay several | — |
| CWP-024 | — | — | — | — | — | — | — | — |
| CWP-025 | — | — | — | — | Event · Post · Email · Text · In the portal | — | — | — |
| CWP-026 | — | — | Person | — | Person · Accounts · Can access · Ends · Status | Edit · Remove (icons) | — | — |
| CWP-065 | — | — | — | — | — | — | — | — |

---
id: US-CWP-023
epic: EP-CWP-06
module: portal
screens: [CWP-076, CWP-077, CWP-078, CWP-079]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021, US-CWP-024]
journeys: [J36, J37]
rules: [BR-CWP-008, BR-CWP-010, BR-CWP-013]
golden_tests: []
finance_calc: none
---
### US-CWP-023 — The portal shell: the utility's branding, an account switcher, six tabs

**1 · Details** — As **a signed-in customer**, I want **one consistent frame**, so that
**switching account reloads everything against it and I never wonder which account I am
looking at**.

Header: the utility's name in its own colours, the current account in a switcher, a Help
link, a messages bell with its unread count, an avatar. Six tabs: **Home · Bills · Usage
· Payments · Requests · My details**.

⚠ **THE FOUR PHONE SCREENS ARE THIS SHELL AT A NARROW WIDTH, NOT FOUR SEPARATE
SCREENS.** `CWP-076`–`CWP-079` are home, pay, a reading and overdue — *"the balance and
one button"*, *"two fields, one consequence box"*, *"the customer is standing at the
meter"*, *"three ways out"*. **`CR-068` never numbered them**; they are numbered here.

⚠ **AND THE SWITCHER IS THE ONE CONTROL THAT CAN LEAK ACROSS ACCOUNTS.** Changing it must
re-scope **every** tab, and the scope is applied in the query, never by the screen.

⚠ **B14 RULE 21.** `07-frontend/src/portal/` is new code. **Add it to
`07-frontend/src/styles/route-b-migrated.txt` in this story's first commit** or every
Tailwind utility in the module renders as **nothing at all** while `tsc`, eslint and every
`toContain("flex")` assertion pass.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-008` | The session holds a set of accounts, never a customer id | CONFIRMED — blueprint §20 |
| `BR-CWP-010` | Every query filtered on tenant **and** account set, in the query | CONFIRMED — blueprint §20 rule 4 |
| `BR-CWP-013` | The set is flat; a master account is one more entry | CONFIRMED — blueprint §20 Figure 17 |
| Inherited | Icons for row actions, one table type, two button sizes, descriptions at 80% | B14 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Sign in as a householder | Header reads *Pine Hill Water & Power* in `#EC3013`, switcher reads `1408 Elm St · A`, six tabs render |
| TC-2 | A landlord picks `22 Palm Ct` from the switcher | **Every** tab reloads against `22 Palm Ct`. ⚠ Assert Bills, Usage, Payments and Requests all change — not just the one in view |
| TC-3 · **negative** | Force the switcher to an account **not** in the set | Refused server-side. ⚠ The switcher is a convenience; the guard is the query |
| TC-4 · **negative** | A householder with one account | The switcher renders as a **label, not a control**. An empty dropdown is worse than no dropdown |
| TC-5 · **tenant isolation** | Oak Ridge's branding while holding a Pine Hill session | Refused; the shell never renders another tenant's brand |
| TC-6 | Narrow viewport | `CWP-076`–`CWP-079` render — balance and one button above everything else |
| TC-7 · **negative** | Grep the portal source for a Tailwind utility | Every file using one is listed in `route-b-migrated.txt`. ⚠ Prove `g31` goes RED on a file that is not |
| TC-8 | Two unread messages | The bell reads `2`; opening one leaves it reading `1` |

**4 · Test Data** — Tenant `pine-hill`. Householder session: one entry, `1408 Elm St ·
A`. Landlord session: four flat entries — `1408 Elm St · A`, `· B`, `· Common areas`
(master), `22 Palm Ct`. Two unread messages. Out-of-set account `ACC-99999-Z`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Utility name, colours, logo | header | prototype-extracted | `tenant.*` | — | reference-data | Read-only; edited in Company → Profile |
| Current account | switcher | prototype-extracted | `portal_session.account_set` | jsonb | system-derived | ⚠ Must be **in** the set |
| Unread count | bell | prototype-extracted | the portal's per-recipient message row, `read_at IS NULL` (⚠ not a column on `outbound_message` — its docstring forbids it; `DEF-CWP-3612`) | integer | computed-display | Per account set |
| Avatar initials | header | prototype-extracted | derived from `customer.display_name` | text | computed-display | ⚠ Initials only — B14 rule 31 forbids an id, and a full name here is noise |

**6 · Acceptance** — **Given** a landlord signed in with four accounts, **when** they
choose `22 Palm Ct` in the switcher, **then** all six tabs reload against that account,
an account outside the set is refused server-side, and the portal's files are on the
migrated list so its utilities actually render.

**7 · Finance Calculation** — N/A. The balance in the header comes from `US-CWP-024`.

**8 · Open Questions** — None.

---
id: US-CWP-024
epic: EP-CWP-06
module: portal
screens: [CWP-022, CWP-023, CWP-076]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J36, J37]
rules: [BR-CWP-015, BR-CWP-047]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-024 — A balance read, per account and totalled across a login

**1 · Details** — As **every screen in the portal**, I want **one balance read I can
trust**, so that **the number a customer sees is the same number everywhere**.

Two reads: the balance for one account, and the total across the set — **totalled for
information, never merged into one invoice.**

⚠ **BUILD THIS FIRST.** The blueprint names it *"the first thing to build"* twice.
Nothing in the product answers *"what is this account's balance right now"*.

⚠ **NEVER CACHED.** A credit that was real on Tuesday can be spent by Thursday. Every
screen re-reads it on load.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-047` | Published per account and totalled, re-read every load, **never cached** | CONFIRMED — `CP-05`, `CP-27` |
| `BR-CWP-015` | Balances are shown separately and never merged into one invoice | CONFIRMED — blueprint `P9` |
| Inherited | Stored to four decimals, displayed to two | hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Account with one issued unpaid bill | `$142.18`, and *"Due 14 Sep · in 12 days"* |
| TC-2 | The landlord's four accounts | `$142.18 + $0.00 + $318.04 + $412.60` = **`$872.82`**, presented as four rows and a total |
| TC-3 · **negative** | An account with a **partly** paid bill — `$142.18` billed, `$40.00` paid | Balance `$102.18`. ⚠ The bill is **neither paid nor unpaid** and the read must not round it to either |
| TC-4 · **negative** | An account carrying an unspent **credit** of `$25.88` | The credit reduces the balance, and the figure is **re-read** rather than served from a cache |
| TC-5 · **negative** | A **draft** bill inside a bill run | ⚠ **Invisible to the balance.** The portal sees nothing above the issued bill |
| TC-6 · **negative** | A **corrected** bill and its replacement | Counted **once** — the replacement — never both |
| TC-7 · **tenant isolation** | The totalled read with a Pine Hill session | Sums Pine Hill accounts only. ⚠ Proved with an identically-numbered Oak Ridge account in the fixture |
| TC-8 | A **voided** bill | Excluded |

**4 · Test Data** — `1408 Elm St · A`: `BL-2608-0141` `$142.18` issued, unpaid → balance
`$142.18`. `· B`: nothing owing → `$0.00`. `· Common areas`: `$318.04`. `22 Palm Ct`:
`$412.60`, overdue 19 days. Total **`$872.82`**. Partial-payment case: `$142.18` billed
less `$40.00` → `$102.18`. Credit case: two credits of `$25.88`. A draft bill of `$99.99`
that must not appear. Corrected pair `BL-2606-0137` `$154.90` → `BL-2606-0147` `$129.02`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Balance | CWP-022, CWP-023, CWP-076 | GAP — **nothing publishes it** | derived: issued invoices less allocations less unspent credits | numeric(18,4) → 2 | computed-display | ⚠ Issued only; never cached |
| Next due date | CWP-022 | prototype-extracted | earliest unpaid `invoice.due_on` | date | computed-display | Rendered as *"in 12 days"* alongside the date |
| Total across the set | CWP-023 | GAP | sum of the per-account reads | numeric(18,4) → 2 | computed-display | ⚠ **Information only** |

**6 · Acceptance** — **Given** a landlord with four accounts owing `$142.18`, `$0.00`,
`$318.04` and `$412.60`, **when** the accounts screen loads, **then** it shows four rows
totalling `$872.82` without merging them; **and given** a bill of `$142.18` with `$40.00`
paid against it, **then** the balance reads `$102.18` and the bill is shown as neither
paid nor unpaid.

**7 · Finance Calculation** — Balance = Σ(issued invoice totals) − Σ(allocations) −
Σ(unspent credits), per account, over **issued, non-void** invoices only, taking the
replacement of a corrected pair.
Worked: `$142.18 − $40.00 − $0.00 = $102.18`.
Worked (set): `$142.18 + $0.00 + $318.04 + $412.60 = $872.82`.
Stored to four decimals, displayed to two, **rounded only at display** (B4).
⚠ **This story should carry a golden test.** It is new arithmetic on a money path that
every screen leans on, and B4/B5 are frozen — so the figure goes to finance through
HUMAN-GUIDE §6 rather than being asserted by a lane and called signed.

**8 · Open Questions** — None. ⚠ But **the GT for this read does not exist yet**, and
only 14 of the 61 signed golden tests are engine-verified. **Do not describe this
arithmetic as golden-tested until a test in `06-backend/tests/golden/` runs it.**

---
id: US-CWP-025
epic: EP-CWP-06
module: portal
screens: [CWP-022, CWP-076]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-024, US-CWP-023]
journeys: [J36]
rules: [BR-CWP-093, BR-CWP-095]
golden_tests: []
finance_calc: none
---
### US-CWP-025 — Portal home: one number, one date, one button

**1 · Details** — As **a customer who visits four to twelve times a year**, I want **the
answer to *do I owe anything and by when* above everything else**, so that **I can leave
in thirty seconds**.

Four tiles — balance, last bill, last payment, usage this month. A *needs your attention*
panel. Three recent bills. A twelve-month chart. A service summary. A tip slot.

⚠ **A PANEL WITH NOTHING IN IT RENDERS AS NOTHING**, not as an empty box saying *"no
items"*. Same for the tip slot: today the only tip aimed at the home page is switched off
and runs December to February, **so the slot is not there and nobody can tell it was.**

⚠ **THE ATTENTION PANEL IS THE PORTAL'S ONLY PROACTIVE SURFACE**, and it is fed by events
the product **already declares** — a bill ready, a payment failed, an instalment coming
up, a notice sent.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-093` | Nothing empty ever appears | CONFIRMED — blueprint §16 Figure 11 |
| `BR-CWP-095` | One tip per screen, on and in season, top of list wins; no tip ⇒ no slot | CONFIRMED — `CP-32` |
| `BR-CWP-047` | The balance is re-read, never cached | CONFIRMED — `CP-05` |
| Inherited | Consumption carries its unit — `4,820 gal`, never `4,820` | hard rule 3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An account owing `$142.18` due 14 Sep | Balance tile reads `$142.18` with *"Due 14 Sep · in 12 days"*; the attention panel offers *Pay $142.18* |
| TC-2 · **negative** | An account owing nothing, with nothing due and no reading window | ⚠ The attention panel is **absent**, not an empty box |
| TC-3 · **negative** | No tip is live for the home page today | ⚠ The slot is **absent**. Assert the DOM has no tip container at all |
| TC-4 | A tip that is on and in season | One tip, and **only one** — where two match, the top of the list wins |
| TC-5 · **negative** | A trash-only account with no meter | ⚠ No usage tile and **no empty chart**. The screen says the service is not measured |
| TC-6 · **tenant isolation** | Home with a Pine Hill session | Only Pine Hill bills, payments and tips |
| TC-7 | The usage tile | Reads `4,820 gal` — ⚠ **with its unit**, never a bare number |
| TC-8 | A reading window open 2–6 September | The panel offers *Send a reading*, and **only** while the window is open |

**4 · Test Data** — Balance `$142.18` due 14 Sep 2026 (today 2 Sep). Last bill
`$142.18`, issued 30 Aug. Last payment `$138.44`, 12 Aug, bank transfer. Usage `4,820
gal`, 18% above last August. Recent bills `BL-2608-0141` DUE, `BL-2607-0139` PAID,
`BL-2606-0147` PAID. Reading window 2–6 Sep. Home-page tip: *"Leave a tap dripping
overnight when it freezes"* — **off**, and Dec–Feb, so not shown. Trash-only account for
TC-5.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Balance | CWP-022 | GAP | the balance read | numeric(18,4) → 2 | computed-display | Live |
| Last bill, Last payment | CWP-022 | prototype-extracted | `invoice`, `payment` | — | system-derived | Most recent of each |
| Usage this month | CWP-022 | prototype-extracted | monthly usage per service | numeric + unit | computed-display | ⚠ Unit always shown |
| Attention items | CWP-022 | prototype-extracted | the notification rule catalogue | — | system-derived | ⚠ Absent when empty |
| Tip | CWP-022 | GAP | `tip` where on, in season, target = portal home | text | reference-data | At most one |

**6 · Acceptance** — **Given** an account owing `$142.18` due in twelve days, **when** the
home page opens, **then** the first thing on it is that number and that date with a Pay
control beside them; **and given** nothing needs attention and no tip is live, **then**
neither the panel nor the tip slot exists in the page at all.

**7 · Finance Calculation** — N/A. Every figure is a read from `US-CWP-024` or from
existing bill and payment records.

**8 · Open Questions** — None.

---
id: US-CWP-026
epic: EP-CWP-06
module: portal
screens: [CWP-023]
wave: 2
status: draft            # was `blocked`; OQ-1397 ruled 2026-09-04 — no, a landlord does not see a tenant's bill; the flat set is what ships
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J37]
rules: [BR-CWP-013, BR-CWP-014, BR-CWP-015, BR-CWP-016]
golden_tests: []
finance_calc: proposed
---
### US-CWP-026 — All my accounts: four balances, totalled, never merged

**1 · Details** — As **a landlord or manager**, I want **every account on one screen with
a total**, so that **I know which unit drove which bill**.

A searchable, filterable table — address, services, next due, balance, status — with
*Total owing* above it and row actions as **icons**. A master account over common areas
reads as one more row, labelled *"Billed to you as owner"*, beside rows labelled
*"Tenant billed"*.

⚠ **A LANDLORD IS A FIRST-CLASS CASE, NOT AN EDGE CASE.** The data model already joins
one customer to many accounts and already understands a master account over shared
supply. **The portal only has to render what the model permits.**

⚠ **AND IT MUST NOT SILENTLY MERGE THE BALANCES**, because each account is billed on its
own.

⚠ **RULED 2026-09-04: `OQ-1397` IS CLOSED AND THE ANSWER IS NO** (PO: *"(a) no"*). Whether
a landlord may see a **tenant's** bill has a legal answer that varies by state; this screen
was drawn as though the answer were no, and it now IS no. **Flat is not a temporary safety
posture any more — it is the product**, which matters because the reasoning that made it
safe (*adding access later is a change; taking it away after a landlord has had it is a
complaint*) no longer has to be re-argued by every lane that reads this story.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-013` | The set is flat; the master is one more entry and confers nothing | CONFIRMED — blueprint §20 Figure 17 |
| `BR-CWP-014` | What makes a master different is that it is billed to the landlord. **A billing fact, not a permission** | CONFIRMED — blueprint §20 Figure 17 |
| `BR-CWP-015` | Shown separately, totalled for information, never merged | CONFIRMED — blueprint `P9` |
| `BR-CWP-016` | A landlord sees the accounts they hold and **never a tenant's** | **CONFIRMED 2026-09-04 — `OQ-1397`, option (a)** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A landlord with four accounts | Four rows, *Total owing* **`$872.82`**, and **four separate balances** |
| TC-2 | The common-areas row | Labelled *"Billed to you as owner"*; the others *"Tenant billed"* |
| TC-3 · **negative** | ⚠ The **tenants' own** accounts | **Not in the table and not in the total.** Assert the response body names four account ids and no fifth |
| TC-4 · **negative** | Request a tenant's account id directly with the landlord's session | Refused. ⚠ The master confers nothing |
| TC-5 · **negative** | A single-account householder | One row, no total line — ⚠ a total of one number is noise |
| TC-6 · **tenant isolation** | The table with a Pine Hill session | Pine Hill accounts only |
| TC-7 | Filter *Owing* | Three rows; `· B` at `$0.00` drops out |
| TC-8 · **negative** | Call the landlord's common-area reconciliation read | ⚠ **THE CASE CHANGED WHEN `OQ-1397` CLOSED.** It refuses — but on **FINANCE**, not on an open question: the reconciliation arithmetic is `finance_calc: proposed` (§7), and a lane implements signed law rather than inventing it. The message names *not finance-signed* and **carries no `OQ-` id at all**, because a stub citing a closed question is stale the moment it is written (G8 clause A) |

**4 · Test Data** — Customer *Maria Alvarez* / *Alvarez Properties*, four accounts:
`1408 Elm St · A` `$142.18` DUE 14 Sep, tenant billed · `· B` `$0.00` CLEAR · `· Common
areas` `$318.04` DUE 14 Sep, **master, billed to owner** · `22 Palm Ct` `$412.60`
OVERDUE 19 DAYS. Total **`$872.82`**. Two tenant accounts at `1408 Elm St · A` and `· B`
that must not appear.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Service address | CWP-023 | prototype-extracted | `premises` + `unit` | text | system-derived | ⚠ The address, never the account id |
| Billed to | CWP-023 | prototype-extracted | `account.is_master_common_area` | boolean | system-derived | Renders the two labels |
| Balance | CWP-023 | GAP | the balance read | numeric(18,4) → 2 | computed-display | Per account |
| Total owing | CWP-023 | GAP | sum over the set | numeric(18,4) → 2 | computed-display | ⚠ Information only |
| Master vs sub-meter reconciliation | CWP-023 | GAP | `metering.submeter_reconciliation` | — | computed-display | ⚠ **Stubbed on FINANCE** — the arithmetic is not signed |

**6 · Acceptance** — **Given** a landlord holding four accounts including a common-areas
master, **when** the accounts screen loads, **then** four rows total `$872.82` without
merging, the master is labelled as billed to them, and the tenants' own accounts appear
neither in the table nor in the total.

**7 · Finance Calculation** — Total owing = Σ of the per-account balance reads.
Worked: `$142.18 + $0.00 + $318.04 + $412.60 = $872.82`. **PROPOSED, not signed** — the
reconciliation figure (master meter against the sum of sub-meters, and the difference the
landlord is billed for) is `CP-54` and is stubbed **because the arithmetic is not
finance-signed**, which is what `OQ-1397`'s closure did NOT settle. ⚠ **THE ACCESS LINE IS
OURS AND IS DECIDED** (decision log 2026-09-04, so no lane re-asks it): when this is built
the landlord sees the master read, the **aggregate** of the sub-meters and the difference
they are billed for — and **never a per-tenant figure**. An aggregate is what makes the
landlord's own bill explicable; a per-unit consumption line is the tenant's business and
reads across `BR-CWP-016`.

**8 · Open Questions** — **None.**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1397` | Does a landlord see a tenant's bill? | ~~`CP-54`~~ · whether the account set may ever widen | Product Owner | ⚠ **CLOSED 2026-09-04 — (a), no.** It did NOT unblock `CP-54`: that read waits on a finance signature, which is a different gate |

---
id: US-CWP-027
epic: EP-CWP-06
module: portal
screens: [CWP-020]
wave: 2
status: ready              # UNBLOCKED 2026-09-04 — OQ-CWP-1562 CLOSED. BR-CWP-001 now names `account_link` as kind ⑥, filed as DEF-CWP-3768 rather than as a change: the blueprint always specified this write in BR-CWP-009 and the *four* never counted it
blocked_by: []
depends_on: [US-CWP-017, US-CWP-018]
journeys: [J37]
rules: [BR-CWP-009, BR-CWP-033, BR-CWP-039]
golden_tests: []
finance_calc: none
---
### US-CWP-027 — Add another account to this login

**1 · Details** — As **somebody who holds more than one account**, I want **to add them to
one login**, so that **I stop keeping four passwords**.

Account number and postcode, as on enrolment. A consequence panel: *adds `1408 Elm St ·
C` to your list · sends a code to that account's contact · **nothing is combined — bills
stay separate***.

⚠ **THE CODE GOES TO THE ACCOUNT BEING ADDED, NOT TO THE PERSON ADDING IT.** Otherwise
anyone with one account and a stolen bill number collects a second.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-009` | The set grows only from a customer-to-account link or a delegate grant | CONFIRMED — blueprint §20 Figure 16 |
| `BR-CWP-033` | The code goes to a contact already held **on that account** | CONFIRMED — blueprint `P3`, `P6` |
| `BR-CWP-039` | A consequence panel before the commit | CONFIRMED — B14 |
| `BR-CWP-015` | ⚠ Nothing is combined; bills stay separate | CONFIRMED — blueprint `P6` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `ACC-10519-C` + `78702`, code verified | The account joins the set and the switcher lists five |
| TC-2 · **negative** | Right number, wrong postcode | Refused, identically to an unknown number |
| TC-3 · **negative** | The code sent to the **adding** user's contact | ⚠ Wrong. Assert the outbound row's destination is the **added** account's contact |
| TC-4 · **negative** | An account already in the set | Refused as already held |
| TC-5 · **negative** | An account with no contact on file | Dead-ends into *ring the office* |
| TC-6 · **tenant isolation** | An Oak Ridge account number | Refused |
| TC-7 | After adding | ⚠ Bills, balances and payments stay **separate**. Assert no merged invoice exists |

**4 · Test Data** — Adding `ACC-10519-C` (`1408 Elm St · C`, postcode `78702`, contact
`(512) 555-9037`) to a session already holding four. Already-held `ACC-10432-A`.
No-contact account `ACC-10777-A`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Account number | CWP-020 | prototype-extracted | `account.number` | text | user-input | Human reference |
| Postcode | CWP-020 | prototype-extracted | `premises.postcode` | text | user-input | Service address |
| The new link | — | B2 | `customer_account_link` | row | system-derived | ⚠ Many-to-many, **already exists** |

**6 · Acceptance** — **Given** a landlord already holding four accounts, **when** they add
`ACC-10519-C` with its postcode and verify the code that went to **that account's** own
contact, **then** it joins the set, the switcher lists five, and no balance or bill is
combined.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-028
epic: EP-CWP-06
module: portal
screens: [CWP-024, CWP-025]
wave: 2
status: ready              # UNBLOCKED 2026-09-04 — OQ-CWP-1562 CLOSED, option (a). BR-CWP-001 names `contact_detail` as kind ⑤ and BR-CWP-103 records where the portal's security lives: at the door
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J45, J47]
rules: [BR-CWP-026, BR-CWP-086, BR-CWP-087]
golden_tests: []
finance_calc: none
---
### US-CWP-028 — My details: what a customer may edit, and what they may not

**1 · Details** — As **a customer**, I want **to fix my own email, phone and postal
address**, so that **my bills reach me** — and I want **to be told plainly why I cannot
change my name here**.

Editable: email, mobile, postal address. **Not** editable: the legal name and the account
holder, each offering a request instead. Alongside: password changed date, code channel,
devices signed in, and *sign out everywhere*.

`CWP-025` is the preferences grid — **post · email · text · in the portal**, per event,
with **post reading ALWAYS**, the paperless consent with the date it was agreed, and a
language picker offering **the two languages the portal supports** — ⚠ **AMENDED
2026-09-07, AND IT READ *"across eleven catalogues"* UNTIL THEN (`DEF-CWP-4442`,
`BR-CWP-106`).** PO, verbatim: *"currently in drop down show only 2 elnglish and
spanish"*. The bundle still carries eleven catalogues and draws every one of them; what
narrowed is what a customer may PICK, and the two are different questions kept in
different places on purpose. A reader whose account already says German sees German
listed as a third option and keeps reading German — nobody's stored choice was reset.

⚠ **AMENDED 2026-09-05, TWICE, AND BOTH BY THE BUILD RATHER THAN BY A RULING.**
**(1) IT IS SIX DOCUMENT KINDS AND NOT FOUR.** This paragraph said *bills, receipts,
notices and plan letters*, which was the floor on 2026-08-29 and was widened by the PO
on 2026-08-30 — *"don't switch of print for any document it is awayls on"* — to six:
`invoice`, `payment`, `notice`, `plan`, **`account`** (confirmations, including a
deposit acknowledgement) and **`move`** (the move-in welcome and the final-bill letter).
`notifications.CHANNEL_FLOOR_BY_SOURCE` is the single statement of it and the screen
reads that dict rather than a list of its own, so the next widening reaches the grid
without anybody editing a screen.

⚠ **(2) *PER EVENT* IS THE DRAWING AND NOT THE STORE (`DEF-CWP-3860`, `OQ-CWP-1660`).**
This product holds **three facts** — `accounts.paperless` adds email,
`accounts.sms_reminders` adds text, and print is the floor under both — not forty-eight
cells. §5 below points the per-event cell at the *notification rule catalogue*, which is
`notification_rules`: **one row per event per TENANT by unique constraint**, so a
customer saving there would change what every other customer of that utility receives.
**So the screen draws the six rows, puts ONE switch per movable channel above them, and
says in a line that the choice covers everything** — a control that looked per-row and
behaved account-wide is hard-won law 2 with better manners. `OQ-CWP-1660` asks whether a
per-event customer store should exist at all; nothing was invented meanwhile.

⚠ **WHAT A CUSTOMER MAY EDIT IS DELIBERATELY NARROW.** Email, phone and postal address
are contact details. **A legal name and the account holder are not** — those identity
fields are encrypted and are what a deposit carry-forward and a duplicate check are
decided on. **Letting a portal rewrite them puts a money decision behind an unverified
form.**

⚠ **AND THE ALWAYS-PRINT COLUMN IS A RULE, NOT A BUG.** The screen must show it honestly
rather than offering an off switch that quietly does nothing.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-026` | Name and account holder are refused with a route into a request | CONFIRMED — blueprint `P10` |
| `BR-CWP-087` | Paperless is a recorded consent with its wording version and a way to withdraw | CONFIRMED — `CR-068` `R5` |
| Inherited | **Print is the floor** on bills, receipts, notices and plan letters | CONFIRMED — `CR-068` `R4` |
| `BR-CWP-086` | Post that came back shows **above** the address field, and fixing it clears the flag | CONFIRMED — `CP-50` |
| Hard rule 7 | Every change writes an audit entry naming the actor | CONFIRMED — CLAUDE.md |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Change the mobile and save | The new value on reload, **and an audit entry naming Maria Alvarez as the actor** |
| TC-2 · **negative** | Post a new legal name to the endpoint | Refused, with the request route named. ⚠ Assert `customer.last_name` is unchanged |
| TC-3 · **negative** | Try to switch **post** off for *Your bill* | Refused **by name**, at the ENDPOINT (`BR-CWP-002`) and not only on the screen. The grid renders `ALWAYS` as a CHIP — not a disabled toggle, which still reads as *somebody could turn this off* |
| TC-4 | Switch **email** off | Accepted — that one genuinely can be switched off. ⚠ **AMENDED 2026-09-05:** this case read *off for `Payment received`* and there is no per-event store to switch (`DEF-CWP-3860`, `OQ-CWP-1660`); the switch is one answer covering all six kinds, and the screen says so above the grid |
| TC-5 · **negative** | Withdraw paperless | The consent row gains `withdrawn_on` and is **not deleted** |
| TC-6 · **negative** | A consent displayed with a future date | ⚠ Impossible by constraint. The blueprint shipped one nineteen days ahead of its own *today* |
| TC-7 · **tenant isolation** | Save details with a Pine Hill session | Only Pine Hill's customer row is touched |
| TC-8 | Two returned letters on the account | *"Two letters came back from this address"* **above** the address field; correcting the address clears it |
| TC-9 | The language picker | Eleven locales; the chosen one is the variant the next document is rendered with |
| TC-10 · **negative** | ⚠ Changes reach **every account on this login** | Stated on the screen, and asserted: one save, four accounts updated |

**4 · Test Data** — *Maria Alvarez*, `m.alvarez@example.com`, `(512) 555-4218`, postal
same as service address, password changed 4 Mar 2026, signed in on 2 devices. Paperless
agreed 21 Sep **2025** (⚠ deliberately in the past). Language `Español (México)`. Two
`DeliveryReturnEvent` rows and `bad_address = true`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Email, Mobile | CWP-024 | prototype-extracted | `customer_contact.*` | text | user-input | Editable |
| Postal address | CWP-024 | prototype-extracted | `customer.postal_address` | text | user-input | Editable |
| Name | CWP-024 | prototype-extracted | `customer.last_name` | text | — | ⚠ **Read-only.** Offers a request |
| Channels | CWP-025 | prototype-extracted | ⚠ **NOT the notification rule catalogue** (`DEF-CWP-3860`) — that is `notification_rules`, the TENANT's row, one per event per tenant. The customer's own choice is `customers.accounts.paperless` (adds email) and `.sms_reminders` (adds text) | boolean ×2 | user-input | ⚠ Post refuses to switch off on **all six** floor classes, by name, at the endpoint |
| Paperless consent | CWP-025 | GAP | `portal_consent` | row | user-input | Withdrawal writes, never deletes |
| Language | CWP-025 | prototype-extracted | `customer.locale` | text | user-input | ⚠ **One of TWO offered — `en` or `es`** (`BR-CWP-106`, PO 2026-09-07; this said *One of eleven* until then). **Nothing validates the stored value against that list**, deliberately: accounts already hold `de` and `hi` and are not reset, so the column still accepts any of the twelve seeded codes and the picker adds the reader's own where it is neither |
| Returned post | CWP-024 | prototype-extracted | `DeliveryReturnEvent`, `account.bad_address` | — | system-derived | Shown above the address |

**6 · Acceptance** — **Given** a signed-in customer, **when** they change their mobile,
**then** it saves, shows on reload and writes an audit entry naming them; **and when**
they attempt a name change, **then** it is refused with a request offered; **and** post
cannot be switched off for a bill.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — ⚠ **AMENDED 2026-09-05 (`DEF-CWP-3860`). THIS READ *"None"*
WHILE §1 AND §5 ABOVE CITED AN OPEN QUESTION THREE TIMES.**

`OQ-CWP-1660` — **OPEN**: where a customer's per-event channel preference should live,
or whether one answer for every document is the right product. **Nothing is blocked and
`CWP-025` shipped**: the grid, the two switches, the language picker (**two languages
since 2026-09-07**, `BR-CWP-106` — this read *"across eleven catalogues"*) and the
recorded consent are all live, and the screen states in a line above the grid that the
choice covers everything we send. What is open is only whether the
forty-eight cells `08-screen-layouts.md` draws should ever have a store behind them.

⚠ **A STORY WHOSE §8 SAYS *None* IS READ AS A STORY WITH NOTHING OUTSTANDING**, which is
how the next lane meets a settled screen and a live question in the same file and
believes the first. §8 is the field the prime directive reads; leaving it at *None*
while the body carries the warning puts the two halves of one fact in two places and
trusts the reader to find the second.

---
id: US-CWP-029
epic: EP-CWP-06
module: portal
screens: [CWP-026]
wave: 4
status: deferred            # OQ-1396 ruled 2026-09-04 — delegate access does not ship; term and revocation are UNASKED, not answered
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J44]
rules: [BR-CWP-017, BR-CWP-009]
golden_tests: []
finance_calc: none
---
### US-CWP-029 — People with access: a permission set, an expiry, and their own audit actor

**1 · Details** — As **an account holder**, I want **to give somebody access without
giving them my password**, so that **my bookkeeper can pay a bill and still cannot close
my account**.

A table — person, accounts, can access, ends, status — with the holder shown as `HOLDER`
and no expiry. Invite by email with a permission set and an end date. A note: *every
action taken by someone you invited is recorded under their name, not yours.*

⚠ **THIS SCREEN IS WHAT REPLACES A SHARED PASSWORD**, which is what customers do today in
its absence.

⚠ **AND IT FIXES AN AUDIT PROBLEM THE PRODUCT WOULD OTHERWISE INHERIT.** Without named
delegates, every portal action by a family member or a bookkeeper is recorded as **the
account holder** — and the audit trail is quietly wrong on exactly the accounts where a
dispute is most likely.

⚠ **BLOCKED ON `OQ-1396`:** how long access may run and who may revoke it. Build the
record, the permission set and the expiry **column**; stub the **policy**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-017` | Four fixed portal roles, not a permission builder | CONFIRMED — blueprint §20 |
| `BR-CWP-009` | A delegate grant is one of exactly two things that may add to a set | CONFIRMED — blueprint §20 Figure 16 |
| Hard rule 7 | The audit entry names the **delegate** | CONFIRMED — CLAUDE.md; `CP-04` |
| — | Permissions may **never** include closing the account, changing the owner, or moving out | CONFIRMED — blueprint `P7`, `P12` |
| — | How long access may run, and who may revoke it | **OPEN — `OQ-1396`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Invite `accounts@kestrel.example` to *Common areas* with See and Download, ending 30 Jun 2027 | The row reads *"Common areas · See · Download · 30 Jun 2027 · Invited"* |
| TC-2 | The invitee downloads the common-areas bill and adds a note to an open request — both within *See · Download* (⚠ this read *pays a bill* until 2026-09-03, `DEF-CWP-3607`: Kestrel's set holds no *Pay*, and *Pay* itself is held until release 5) | ⚠ **The audit entry names Kestrel Bookkeeping, not Maria Alvarez** |
| TC-3 · **negative** | An invitee tries to close the account | Refused. Assert the permission set cannot contain `close_account` at all |
| TC-4 · **negative** | A **non-holder** tries to invite | Refused — only the holder invites |
| TC-5 · **negative** | An invitee tries to invite | Refused |
| TC-6 · **negative** | An expired delegate acts | Refused on **their very next request**, not on their next nightly anything |
| TC-7 | Remove a delegate | The row moves to `ended` and **stays on the record** |
| TC-8 · **tenant isolation** | An invite naming an account outside the granter's set | Refused |
| TC-9 · **negative** | Call the retention/revocation policy | `NotImplementedError("OQ-1396")` |

**4 · Test Data** — Holder *Maria Alvarez*, all four accounts, `HOLDER`, no end date.
`J. Alvarez` `j.alvarez@example.com`, all four, See · Pay, ends 31 Dec 2026, `ACTIVE`.
`Kestrel Bookkeeping` `accounts@kestrel.example`, Common areas, See · Download, ends 30
Jun 2027, `INVITED`.

**5 · Data Fields / Mapping** — See `03-field-map.md` § `portal_delegate`. The field that
carries the whole point: `audit_actor_id`.

**6 · Acceptance** — **Given** a holder who invites a bookkeeper with See and Download on
the common-areas account only, **when** the bookkeeper acts, **then** the audit entry
names the bookkeeper; **and** they cannot close the account, cannot invite anybody, and
are refused on their next request the moment their access ends.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1396` | How long may a delegate hold access, and who may revoke it? | The retention policy on this screen | Product Owner | OPEN |

---
id: US-CWP-030
epic: EP-CWP-06
module: portal
screens: [CWP-021]
wave: 4
status: deferred            # OQ-1396 ruled 2026-09-04 — delegate access does not ship; term and revocation are UNASKED, not answered
blocked_by: []
depends_on: [US-CWP-029]
journeys: [J44]
rules: [BR-CWP-039]
golden_tests: []
finance_calc: none
---
### US-CWP-030 — Accept an invitation, stated in both directions

**1 · Details** — As **somebody invited to help**, I want **to see exactly what I can and
cannot do before I accept**, so that **I know the limits of what I am taking on**.

*M. Alvarez has asked you to help with an account.* Then the account, **what you would be
able to do**, **what you would not be able to do**, when access ends, and Accept or
Decline.

⚠ **SAYING WHAT THE INVITEE CANNOT DO IS WHAT MAKES THIS SAFE TO OFFER.** An agent who
can pay but cannot close an account is a much smaller risk than a shared password —
**which is what customers do today in the absence of this screen.**

⚠ **THE INVITEE MAY NOT BE SIGNED IN, AND MAY NOT BE A CUSTOMER AT ALL.** The token read
and the accept therefore sit **outside** the account set, which is why they are their own
two endpoints.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-039` | Both directions stated before the commit | CONFIRMED — blueprint `P7` |
| `BR-CWP-009` | Accepting adds one entry to the invitee's set and nothing more | CONFIRMED — blueprint §20 |
| `BR-CWP-004` | The invitee gets a **portal** credential, never a staff role | CONFIRMED — `CR-068` `R1` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open a valid invitation | Names the account, *See bills · Pay · Download receipts*, and **explicitly** *Close the account · Change the owner · Move out* as things they could **not** do, and *Access ends 31 Dec 2026* |
| TC-2 | Accept, having no login | Routes into enrolment, then the account appears in **their** set — ⚠ and in nobody else's |
| TC-3 · **negative** | Decline | The delegate row moves to `ended`; no entry is added |
| TC-4 · **negative** | Accept twice | The second is refused |
| TC-5 · **negative** | An invitation the holder revoked before it was accepted | Refused with a plain sentence |
| TC-6 · **negative** | An invitation past its end date | Refused |
| TC-7 · **tenant isolation** | A Pine Hill token opened under `/oak-ridge` | Refused |
| TC-8 · **negative** | Guess a token | ⚠ Tokens are unguessable and single-use; assert length and entropy, and that a used token is dead |

**4 · Test Data** — Invitation from *M. Alvarez* for `1408 Elm St · A`, permissions See ·
Pay · Download, ends 31 Dec 2026. A revoked invitation and an expired one.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Token | — | GAP | short-lived store keyed to `portal_delegate` | text | system-derived | Single use, unguessable |
| What you would / would not be able to do | CWP-021 | prototype-extracted | `portal_delegate.permissions` | text[] | computed-display | ⚠ **Both lists rendered from one field** — the negative list is the complement, not separate copy |

**6 · Acceptance** — **Given** a bookkeeper who was invited, **when** they open the
invitation, **then** it states what they could do and what they could not, and when
access ends; **and when** they accept, **then** exactly one account joins their own set.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — `OQ-1396`, as `US-CWP-029`.

---
id: US-CWP-031
epic: EP-CWP-06
module: portal
screens: [CWP-065]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J36]
rules: [BR-CWP-049, BR-CWP-053]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-031 — Your account: the deposit we hold, the exemption that lapses, the history

**1 · Details** — As **a customer**, I want **the facts about my account that are not on a
bill**, so that **I know you are holding my money and when my exemption runs out**.

Four panels: **the deposit we hold** — amount, date taken, interest so far, and that it
comes back at closing; **your services** — each with the date it started and what it is
billed on; **how you are billed** — the plan, since when, and what came before; and **tax
exempt** — from what, certificate on file, and the date it runs out.

⚠ **THE DEPOSIT IS THE ONE THAT STINGS.** `$150.00` of the customer's money, taken in
2021, **visible on the day it is quoted and on the day it comes back, and invisible for
the five years in between.**

⚠ **AND THE TAX PANEL SAVES A CALL.** An exemption that lapses silently turns into a
bigger bill and a complaint. The certificate's expiry **is already stored**, and the
customer is messaged **thirty days before**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-049` | The deposit is shown **while it is held** — amount, date, interest | CONFIRMED — `CP-43` |
| `BR-CWP-053` | A tax exemption shows its expiry, and the customer is messaged thirty days before | CONFIRMED — `CP-45` |
| `CP-53` | Service, plan and move history — since when each service has been on, which plan applies and since when | CONFIRMED — `CP-53` |
| `BR-CWP-052` | ⚠ The **credit tier** is held back on purpose and must not appear here | CONFIRMED — blueprint §17 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An account with a deposit taken 4 Mar 2021 | *"We are holding `$150.00`, taken on 4 March 2021"*, interest `$3.20`, and that it returns at closing **with** interest |
| TC-2 · **negative** | The deposit panel | ⚠ States it is **not** money off a bill in the meantime. A customer who thinks it is stops paying |
| TC-3 | Services | Water and Sewer since 4 Mar 2021, Trash since 1 Jun 2024, each with what it is billed on — meter, share of water, `96 gal` cart |
| TC-4 | Plan history | *Residential Standard* since 1 Jan 2026, and *before that Residential Basic* |
| TC-5 | Tax exemption | *"You are exempt from state utility tax until 31 March 2027"* and that a reminder comes a month before |
| TC-6 · **negative** | Thirty days before the expiry | A **message**, not a bigger bill |
| TC-7 · **negative** | The response body | ⚠ Contains **no** `credit_tier`, **no** `match_tier`, **no** `match_basis`. Asserted on the body, because those three are held back on purpose |
| TC-8 · **negative** | An account with **no** deposit | The panel is **absent**, not `$0.00` |
| TC-9 · **tenant isolation** | The read with a Pine Hill session | Pine Hill's account only |

**4 · Test Data** — Deposit `$150.00`, taken 4 Mar 2021, interest to date `$3.20`.
Services: Water 4 Mar 2021 (meter), Sewer 4 Mar 2021 (share of water), Trash 1 Jun 2024
(`96 gal` cart). Plan *Residential Standard* since 1 Jan 2026, previously *Residential
Basic*. Tax exempt from state utility tax, certificate on file, runs out 31 Mar 2027.
Account opened 4 Mar 2021, moved in, transferred from `91 Cedar Row`. An internal
`credit_tier` of `B2` that must not surface.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Deposit held, taken on | CWP-065 | prototype-extracted | `account.deposit_on_file`, `deposit_received_on` | numeric(18,4) → 2, date | system-derived | Absent when none |
| Interest so far | CWP-065 | prototype-extracted | accrued deposit interest | numeric(18,4) → 2 | computed-display | — |
| Services and start dates | CWP-065 | prototype-extracted | `ServiceAgreement` | — | system-derived | Per service point |
| Plan and since when | CWP-065 | prototype-extracted | `UnitPlanAssignment` | — | system-derived | ⚠ Its **version** and the reason stay internal |
| Tax exemption and expiry | CWP-065 | prototype-extracted | `account.tax_exempt` + certificate | — | system-derived | Reminder at −30 days |
| ~~Move history~~ | CWP-065 | prototype-extracted | ⚠ **`MoveRecord` DOES NOT EXIST AND NEVER HAS** (`DEF-CWP-3767`) | — | — | ⚠ **NOT BUILT.** A move IS recorded — a `service_requests` row with `outcome='move_in'` — but that row carries **no `account_id`**, and the reverse link `origin_service_request_id` is described in the model's own comment as *"it does not exist yet"*. So an account cannot be walked back to the move that opened it. The panel says `accounts.opened_at` — *this account opened on 4 March 2021* — and stops there. **A lane must not match `outcome_ref` by string: that is a join on prose, on a screen that tells a customer what happened to their account** |
| Credit tier | — | blueprint §17 | `account.credit_tier` | — | — | ⚠ **NEVER SHOWN** |

**6 · Acceptance** — **Given** an account with a deposit taken in 2021 and an exemption
expiring 31 Mar 2027, **when** the account screen loads, **then** it reads that `$150.00`
is held with `$3.20` interest and returns at closing, that the exemption runs out on that
date with a reminder a month before — and the response carries no credit tier and no
match confidence.

**7 · Finance Calculation** — Deposit interest is existing, configured accrual; this
screen **reads** it and must not recompute. **A figure here that disagrees with the final
bill is the defect this test exists to catch.**

⚠ **THE `$3.20` IN §4 IS NOT REPRODUCIBLE AND THE TEST DELIBERATELY DOES NOT ASSERT IT.**
`BR-CUS-057` is `principal × rate ÷ 100 × completed months ÷ 12`, and `150.00 × 0.02 × N
÷ 12` reaches `3.20` for no whole `N`; the engine's own worked figures are **`22.25` at
89 months** (❄️ `GT-61`, FROZEN) and **`3.50` at 14**. So `test_us_cwp_031_your_account.py`
asks the SIGNED ENGINE what the figure is for the fixture's dates and asserts the screen
agrees with it. **A hard-coded `3.20` would have made the test agree with this story and
disagree with the money**, which is the exact failure the sentence above is warning about
— one level up.

⚠ **AND `None` IS A REAL ANSWER.** `deposit_interest_accrued` answers `None` when it
cannot compute, and BOTH callers that settle real money fail CLOSED on that rather than
paying principal alone. The screen says *the interest is not worked out yet* and never
`$0.00`.

**8 · Open Questions** — None.
