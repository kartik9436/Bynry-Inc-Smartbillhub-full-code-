# EP-CWP-02 — Quick pay for a guest

**Module:** portal · **Wave:** release **5** · **Screens:** CWP-002 · CWP-003 · CWP-004 ·
**Status:** draft

## Scope

**In:** the three-step guest payment — find the bill, check and pay, done — and the
idempotent webhook behind it.

**Out:** the signed-in pay flow (`EP-CWP-09`), stored methods, autopay.

⚠ **EVERY SCREEN IN THIS EPIC SHIPS BEFORE RELEASE 5, HELD.** Payment gateways are a
later stage (`CR-068` `R2`); the Pay control appears in its normal place, **disabled,
carrying its reason** (`R3`). **Never hidden, and never live-but-inert.**

⚠ **AND THE HARDEST HALF IS ALREADY BUILT.** Recording, allocating, reversing and
receipting a payment are finished and tested; `bank_chargeback` is already one of four
recorded reversal reasons and a payment may be reversed exactly once by a unique
constraint. **This is an integration, not a rebuild.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-002 | — | — | — | — | — | — | — | — |
| CWP-003 | — | — | — | — | — | — | — | — |
| CWP-004 | — | — | — | — | — | — | — | Receipt · email |

---
id: US-CWP-003
epic: EP-CWP-02
module: portal
screens: [CWP-002]
wave: 5
status: ready
blocked_by: []
depends_on: [US-CWP-002]
journeys: [J30]
rules: [BR-CWP-018, BR-CWP-019, BR-CWP-023]
golden_tests: []
finance_calc: none
---
### US-CWP-003 — Find the bill on a number and a postcode

**1 · Details** — As **somebody holding a paper bill**, I want **to find it with two
facts printed on it**, so that **I can pay without an account**.

Two fields: bill number and the postcode of the service address. Both are on the paper
the person is holding. A help panel says where the number is — *top right, above the due
date, starts with BL*.

⚠ **THE POSTCODE IS NOT SECURITY THEATRE.** A bill number alone is a short sequential
string; the pair is what stops the form being a way to enumerate accounts.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-018` | A bill number proves someone is holding the bill, not who they are | CONFIRMED — `CR-068` `R7` |
| `BR-CWP-019` | The lookup answers **amount owing and a masked name** and nothing else | CONFIRMED — `CR-068` `R7` |
| `BR-CWP-023` | Five wrong pairs locks the form fifteen minutes | CONFIRMED — `CP-37` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `BL-2608-0141` + `78702` | Step 2 opens with `$142.18` owing |
| TC-2 · **negative** | `BL-2608-0141` + `78704` (wrong postcode) | Refused, and the response is **byte-identical** to TC-3's — a different message would confirm the bill number exists |
| TC-3 · **negative** | `BL-9999-9999` + `78702` (no such bill) | Same refusal as TC-2 |
| TC-4 · **negative** | A **paid** bill, `BL-2607-0139` + `78702` | Opens showing `$0.00` owing and **no Pay control** — not a refusal, because the holder is entitled to know it is paid |
| TC-5 · **negative** | A **voided** bill | Reads *"cancelled"* and offers no payment |
| TC-6 · **tenant isolation** | Pine Hill's `BL-2608-0141` + `78702` submitted on `/oak-ridge` | Refused. Bill numbers are per tenant and the tenant is resolved from the path first |
| TC-7 | A **corrected** bill, `BL-2606-0137` | Reads *"replaced by BL-2606-0147"* and directs payment at the replacement |

**4 · Test Data** — `BL-2608-0141` · `1408 Elm St · A` · `78702` · issued 30 Aug · due
14 Sep · `$142.18` owing. Paid: `BL-2607-0139`, `$138.44`, `$0.00` owing. Corrected:
`BL-2606-0137` `$154.90` → replaced by `BL-2606-0147` `$129.02`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Bill number | CWP-002 | prototype-extracted | `invoice.number` | text | user-input | ⚠ The **human** reference, never the row id (B14 rule 31) |
| Postcode | CWP-002 | prototype-extracted | `premises.postcode` | text | user-input | Matched against the **service** address, not the postal address |
| Amount owing | CWP-003 | prototype-extracted | derived from `invoice` less allocations | numeric(18,4) → display 2 | computed-display | ⚠ Re-read every load, never cached |

**6 · Acceptance** — **Given** a visitor holding bill `BL-2608-0141`, **when** they enter
it with postcode `78702`, **then** step 2 shows `$142.18` owing — and **when** either
fact is wrong, **then** the refusal is identical whether the bill exists or not.

**7 · Finance Calculation** — Amount owing = issued total less allocations to date.
Worked: `$142.18 − $0.00 = $142.18`. Stored to four decimals, displayed to two. No GT —
this is a read of existing arithmetic.

**8 · Open Questions** — None. `PQ-09` was ruled 2026-09-02 (`CR-068` `R7`).

---
id: US-CWP-004
epic: EP-CWP-02
module: portal
screens: [CWP-003]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-003, US-CWP-006]
journeys: [J30]
rules: [BR-CWP-019, BR-CWP-020, BR-CWP-021, BR-CWP-057, BR-CWP-058]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-004 — Check and pay, and the masked name that makes it safe

**1 · Details** — As **somebody holding a bill**, I want **to confirm it is the right one
and pay it**, so that **I do not have to ring the office or create an account**.

Shows the bill number, the service address, **`Billed to M. A••••••`**, the due date and
the amount. Then card or bank fields, an optional email for the receipt, and a
consequence box: *pays `$142.18` against this bill · does not create an account · shows
you a reference to keep*.

⚠ **THE MASKED NAME IS THE MOST IMPORTANT DETAIL ON THIS SCREEN.** Whoever holds the
bill can confirm they have the right one **without the page disclosing who lives there**
— a bill goes astray, gets photographed, gets left in a hallway. **Showing the balance is
fine; showing the customer is not.**

⚠ **HELD UNTIL RAILS.** Nothing in the product can charge a card. The control is visible,
disabled, and says so.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-020` | Masked name is first initial plus masked surname — `M. A••••••` | CONFIRMED — blueprint `G3` |
| `BR-CWP-021` | A guest sees an amount and a status, never a person | CONFIRMED — blueprint §20 |
| `BR-CWP-056` | The Pay control appears, disabled, carrying its reason | CONFIRMED — `CR-068` `R3` |
| `BR-CWP-057` | A stored instrument is a gateway token with a brand and last four | CONFIRMED — blueprint `P25` |
| `BR-CWP-058` | The screen shows where the payment will land before it commits | CONFIRMED — blueprint `P24` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open step 2 for `BL-2608-0141` | *Billed to* reads **`M. A••••••`**. The response body contains **no other field** of the customer record — not the full name, not the email, not the phone |
| TC-2 | Rails absent (today) | The Pay control renders **in its normal place, disabled**, with its reason. It is **not** hidden and **not** clickable |
| TC-3 · **negative** | Force a click on the disabled control | No payment row, no audit row, no gateway call |
| TC-4 · **negative** | A surname of one character, *"M. O"* | Masks without revealing length — the mask is fixed-width, not one dot per letter |
| TC-5 · **tenant isolation** | Request step 2 with Pine Hill's bill number under `/oak-ridge` | Refused before any customer row is read |
| TC-6 | Once rails exist: pay `$142.18` | One payment row, allocated by the tenant's rule, one audit entry naming the **guest channel**, one receipt document, and **no account created** |
| TC-7 · **negative** | Once rails exist: the gateway times out | The screen says so and **no payment row is written on an unknown outcome** — a zero is a claim nobody can make |

**4 · Test Data** — Customer *Maria Alvarez* → masked `M. A••••••`. Bill
`BL-2608-0141`, `$142.18`, due 14 Sep 2026. Card `Visa ••••8812 · expires 11/27`.
Receipt email `d.okafor@example.com` (⚠ deliberately **not** the customer's own address —
a guest may be a neighbour).

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Billed to (masked) | CWP-003 | prototype-extracted | derived from `customer.display_name` | text | computed-display | ⚠ Masked **server-side**. Never send the full name and mask in the browser |
| Card number, expiry, CVC | CWP-003 | prototype-extracted | **none** | — | user-input | ⚠ **Never stored.** Posted to the gateway, which returns a token |
| Receipt email | CWP-003 | prototype-extracted | `payment.receipt_email` | citext | user-input | Optional. Used only to send this receipt |
| Amount | CWP-003 | prototype-extracted | `payment.amount` | numeric(18,4) | computed-display | Display 2 |

**6 · Acceptance** — **Given** a visitor holding `BL-2608-0141`, **when** step 2 opens,
**then** it reads `$142.18` owing and `Billed to M. A••••••` and discloses nothing else
about the account; **and** the Pay control is visible, disabled and carries its reason
until rails exist.

**7 · Finance Calculation** — Payment amount = amount owing at the moment of commit,
re-read rather than carried from step 1. Worked: `$142.18`. Allocation is the tenant's
rule (oldest first by default) and the screen shows the result **before** the commit
because afterwards the row cannot be edited, only reversed (hard rule 4). No new GT — the
allocation arithmetic is already golden-tested.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1394` | Who pays the card fee — absorbed, surcharged or bank-only? | The fee line on this screen | Product Owner | **CLOSED 2026-09-04** |

⚠ **THIS ROW READ `OPEN` UNTIL 2026-09-05 AND IT WAS STALE BY A DAY** — corrected by the
`US-CWP-004` build lane at step 0 of the r11 process (*"was this ruled since the doc I am
about to build from was written?"*). Leaving it would have sent this screen's lane to a
`NotImplementedError` on a question that had an answer. It is the same staleness
`DEF-GOV-3929` records on the other side: a lane put the closed question back to the
Product Owner and was told *"I already confirm this"*.

**THE RULING WAS A FOURTH ANSWER, NOT ONE OF THE THREE OFFERED.** The register offered
absorbed, surcharged or bank-only as exclusive options; the PO took the first two together
and made them a setting — verbatim: *"we have to give both the options so far some
utilities abosrb it other pass it to customer ; so we have to flexible and create a flag
somewhere to on and off it"*.

**WHAT THIS SCREEN DOES ABOUT IT, AND IT IS STILL NO FEE LINE.** Beta ships with the
switch defaulting to **ABSORB** (there is no real fee in a sandbox), so `CWP-003` draws no
fee line and the consequence box promises exactly what the person pays — `$142.18` against
`BL-2608-0141`. ⚠ **THE SWITCH IS NOT A BOOLEAN:** turning surcharge ON obliges the fee to
be COMPUTED from the processor's schedule, DISCLOSED before the commit (*"a customer paying
`$142.18` must see the surcharge and the new total before they press, never after"*) and
CHECKED against the customer's state. None of the three is possible without a real
processor, and **where the switch lives is a `payments` setting rather than a portal one**
— the same fee applies at the counter — so it is not built here.
`guest_api._no_surcharge_is_lawful_here` therefore REFUSES rather than guessing on the day
the setting arrives: a surcharge undisclosed before the commit is the one thing the ruling
forbids by name.

---
id: US-CWP-005
epic: EP-CWP-02
module: portal
screens: [CWP-004]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-004, US-CWP-017]
journeys: [J30, J35]
rules: [BR-CWP-028]
golden_tests: []
finance_calc: none
---
### US-CWP-005 — Paid: a reference to keep, and the offer of a login

**1 · Details** — As **a guest who has just paid**, I want **a reference and a receipt**,
so that **I have proof without an account** — and I want **the option of a login, not the
demand for one**.

Shows `PAID`, the amount, a reference `PAY-26-08841`, the timestamp, the bill it went
against, and the method. Then a download and an *email it to me*. Then an enrolment
offer: *we already know your account and your email; you would add a password.*

⚠ **THIS IS THE SINGLE BEST MOMENT IN THE PRODUCT TO OFFER AN ACCOUNT, AND THE ONLY ONE
THAT COSTS NOTHING.** The visitor has just succeeded and the account is already
identified. **Note what it must not do:** it does not create the login silently, and it
does **not withhold the receipt** until they take it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-028` | Every guest flow ends on a reference, offers to send it, and can be looked up with it | CONFIRMED — blueprint §7 |
| `BR-CWP-029` | Enrolment attaches a password to a person already on file | CONFIRMED — `CR-068` `R1` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Complete a guest payment | `PAY-26-08841` on screen, with the amount, the bill and the method |
| TC-2 | Press *email it to me* having given no email at step 2 | Prompts for one. **The receipt is already downloadable without it** |
| TC-3 · **negative** | Do not take the enrolment offer, then reload | The receipt is still reachable by reference. **No credential row was created** |
| TC-4 · **negative** | Take the enrolment offer | It routes to `CWP-017` — *prove it is you* — and **does not skip the one-time code** because a payment just succeeded |
| TC-5 · **tenant isolation** | Look up `PAY-26-08841` under `/oak-ridge` | Not found |
| TC-6 | The receipt document | It is the **document class that already exists**, not a page the portal renders |

**4 · Test Data** — Reference `PAY-26-08841`, paid 2 Sep 2026 9:47am, `$142.18`, against
`BL-2608-0141`, method `Card ending 8812`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Reference | CWP-004 | prototype-extracted | `payment.reference` | text | system-derived | ⚠ The human reference. **Never the row id** |
| Receipt | CWP-004 | prototype-extracted | `document` where kind = receipt | — | system-derived | The existing document class |

**6 · Acceptance** — **Given** a guest has just paid `$142.18`, **when** the done screen
opens, **then** it shows reference `PAY-26-08841` and a downloadable receipt, offers a
login without creating one, and the receipt is available whether or not they take the
offer.

**7 · Finance Calculation** — N/A. The figure is the payment just recorded.

**8 · Open Questions** — None.

---
id: US-CWP-006
epic: EP-CWP-02
module: portal
screens: []
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-004]
journeys: [J30]
rules: [BR-CWP-059, BR-CWP-061]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-006 — An idempotent inbound payment webhook

**1 · Details** — As **the utility**, I want **the same settlement arriving twice to
change nothing**, so that **a gateway retry never takes a customer's money twice**.

The gateway **will** retry. The schema already reserves the unique key that makes a
repeat harmless (hard rule 6, B2 unique keys).

⚠ **VERIFY BEFORE BUILDING.** The blueprint says `payments/webhooks.py` is *"one
docstring line, no handler reads the key"*. **That was true at 2.125.4 and is false
now** — it is **577 lines with 15 tests as of 2026-09-03**, built as `CR-060` C21. This
story may be largely done; §8 of the module overview says why no status here is
trusted.

⚠ **AND IT MUST BE PROVED ON POSTGRESQL, NOT ON THE SUITE'S SQLITE.** A handler that
catches a duplicate and carries on is the exact shape of hard-won law 14: a failed
statement poisons the whole Postgres transaction, SQLite has no aborted-transaction
state, and the naive version passes the entire suite green and loses data in production.
**A nested `transaction.atomic()` savepoint is the only option, and the comment must say
so or the next lane will simplify it away.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-059` | Idempotent on the reserved key: the same settlement twice leaves one payment row | CONFIRMED — `CP-09`, hard rule 6 |
| `BR-CWP-061` | A bounced payment is a **new negative row**, never an edit | CONFIRMED — hard rule 4 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | One settlement | One payment row, one allocation, balanced journal pair |
| TC-2 | **The same settlement twice** | Still **one** payment of `$142.18`. `CWP-041` shows one row, not two |
| TC-3 · **negative** | The same event twice **concurrently** | One row. ⚠ Proved by the unique constraint, not by a read-then-write check |
| TC-4 · **negative** | A settlement for an unknown reference | Refused and recorded. **No payment row, and the response does not reveal whether the reference exists** |
| TC-5 · **negative** · **PostgreSQL** | A batch where row 2 of 3 violates a constraint | Rows 1 and 3 commit, row 2 is reported. ⚠ **Run under `DJANGO_SETTINGS_MODULE=config.settings.local` against real PostgreSQL** — the default suite cannot see this class of bug |
| TC-6 · **tenant isolation** | A settlement whose reference belongs to another tenant | Refused. `app.tenant_id` is set from the webhook's own tenant resolution, never from the payload |
| TC-7 | A reversal carrying the same identifier as the payment it reverses | ⚠ **Not mistaken for a duplicate of it.** Two rows: the payment, and the reversal above it |

**4 · Test Data** — Settlement `STL-2609-0031` → `$142.18` against `BL-2608-0141`,
idempotency key `pay_26_08841`. Replay: the identical body. Reversal `STL-2609-0032`
carrying the same `pay_26_08841` with a reversal flag.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Idempotency key | — | B2 | `payment.idempotency_key` | text | integration | ⚠ **Unique per tenant.** Already reserved by the schema |
| Settlement amount | — | prototype-extracted | `payment.amount` | numeric(18,4) | integration | ⚠ **Check the units.** Minor units against decimal is *"a hundredfold error in the direction nobody notices until a customer calls"* |
| Reversal reason | — | B2 | `payment_reversal.reason` | enum | integration | `bank_chargeback` is already one of the four |

**6 · Acceptance** — **Given** a settlement for `$142.18` has been processed, **when** the
gateway sends the identical event again, **then** the account still shows one payment of
`$142.18`, the books still balance, and `CWP-041` shows one row — proved against real
PostgreSQL.

**7 · Finance Calculation** — No new arithmetic. Allocation and the balanced pair are
existing, golden-tested behaviour; this story guarantees they run **once**.

**8 · Open Questions** — None. ⚠ But `R-8 q4` in `CR-069` — whether webhooks are signed
with the merchant secret, a separate signing key or a shared code — **is answered only in
part** (*"there will be some code"*), and a signature over the body and a code in the
payload are not the same thing on a money path. **Confirm which before trusting
`payments.webhook_key` as provisioned.**
