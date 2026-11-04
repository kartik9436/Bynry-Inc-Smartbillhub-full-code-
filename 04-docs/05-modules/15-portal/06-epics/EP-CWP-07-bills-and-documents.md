# EP-CWP-07 — Bills, documents and the explainer

**Module:** portal (reads billing) · **Wave:** release 2 (explainer: 4; notices: 3) ·
**Screens:** CWP-027 … CWP-032 · CWP-068 · **Status:** draft

## Scope

**In:** the bill list, one bill line by line, the issued PDF, the comparison that explains
why a bill moved, the document register, the final bill, the statement question, and
every notice sent or deliberately not sent.

**Out:** paying any of it (`EP-CWP-09`), disputing it (`EP-CWP-11`).

⚠ **A BILL IN THIS PRODUCT IS FIVE STATES AND ONE OF THEM — `issued` — CAN NEVER BE
EDITED.** A correction is a **new** bill that points back at the old one. The portal has
to make that visible rather than hide it, **because a customer who has been sent two
documents for one month needs to know which one to pay.**

⚠ **AND THE PORTAL SEES NOTHING ABOVE THE ISSUED LINE.** Draft bills, bill-run breaks,
decisions and exclusions are invisible to it — they record how the utility reached a
number, not what the customer owes.

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-027 | Bills | All · Unpaid · This year | Issued desc | Bill · Period · Amount | Bill · Period · Issued · Due · Usage · Amount · Owing · Status | View · Print (icons) | — | Download all · Pay |
| CWP-028 | — | — | — | — | Line · Quantity · Rate · Amount | — | — | PDF |
| CWP-031 | Documents | All · Bills · Receipts · Letters | Sent desc | Sent | Document · Kind · Sent · How | View · Print (icons) | — | Download a year |
| CWP-068 | — | — | Sent desc | — | Notice · Date · Channel · Outcome | View | — | — |

---
id: US-CWP-032
epic: EP-CWP-07
module: portal
screens: [CWP-027]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-024]
journeys: [J36]
rules: [BR-CWP-041, BR-CWP-042, BR-CWP-043]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-032 — Your bills, and owing is a separate column from amount

**1 · Details** — As **a customer**, I want **every bill with what it was and what is
still owed on it**, so that **I know which one to pay**.

A table: bill number, period, issued, due, usage, **amount**, **owing**, status. A
corrected row stays in place, greyed, reading *"Replaced by BL-2606-0147"*.

⚠ **OWING IS A SEPARATE COLUMN FROM AMOUNT, AND THAT DISTINCTION IS THE WHOLE TABLE.** A
`$142.18` bill with `$40.00` paid against it **is not a paid bill and not an unpaid
one.**

⚠ **AND THE CORRECTED ROW IS NEVER DELETED.** Deleting the original would break the
immutability the ledger depends on. **The list is where the wording does the work:
*replaced by BL-2606-0147*, not a silently changed number.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-041` | The portal sees nothing above the issued bill | CONFIRMED — blueprint §10 Figure 5 |
| `BR-CWP-042` | A corrected bill and its replacement both stay, the original naming the replacement | CONFIRMED — the existing correction chain |
| `BR-CWP-043` | Owing is its own column | CONFIRMED — blueprint `P13` |
| Inherited | Money displays to two decimals; consumption carries its unit | hard rules 2, 3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Four bills, one due | `BL-2608-0141` reads `$142.18` amount, `$142.18` owing, **DUE IN 12 DAYS** |
| TC-2 | A part-paid bill — `$142.18` with `$40.00` against it | Amount `$142.18`, owing `$102.18`, and the status is **neither PAID nor DUE** but part-paid |
| TC-3 | The corrected pair | `BL-2606-0137` shows greyed, `$154.90`, owing `$0.00`, **CORRECTED**, reading *"Replaced by BL-2606-0147"* — and the replacement is its own row |
| TC-4 · **negative** | A **draft** bill inside a live bill run | ⚠ **Absent from the table entirely** |
| TC-5 · **negative** | A **voided** bill | Reads *"cancelled"*, owing `$0.00`, still downloadable |
| TC-6 · **negative** | A new customer with no bills | ⚠ An **empty state that says what is missing and what fills it** — never a blank table (B14) |
| TC-7 · **tenant isolation** | The list with a Pine Hill session | Pine Hill bills only. ⚠ Proved with an identically-numbered Oak Ridge bill in the fixture |
| TC-8 | Usage column | `4,820 gal` — with the unit |
| TC-9 | Filter *Unpaid* | Only rows with owing greater than zero; the part-paid row **is** included |

**4 · Test Data** — `BL-2608-0141` 1–31 Aug, issued 30 Aug, due 14 Sep, `4,820 gal`,
`$142.18`, owing `$142.18`, DUE. `BL-2607-0139` 1–31 Jul, `4,090 gal`, `$138.44`, owing
`$0.00`, PAID. `BL-2606-0147` 1–30 Jun, `3,760 gal`, `$129.02`, PAID. `BL-2606-0137` the
same period, `$154.90`, CORRECTED, replaced by `BL-2606-0147`. `BL-2605-0131` May,
`3,410 gal`, `$121.55`, PAID. Part-paid case: `$142.18` less `$40.00`. A draft of
`$99.99` that must not appear.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Bill | CWP-027 | prototype-extracted | `invoice.number` | text | system-derived | ⚠ The human reference (B14 rule 31) |
| Period, Issued, Due | CWP-027 | prototype-extracted | `invoice.period_*`, `issued_on`, `due_on` | date | system-derived | — |
| Usage | CWP-027 | prototype-extracted | consumption for the period | numeric + unit | computed-display | ⚠ Unit always |
| Amount | CWP-027 | prototype-extracted | `invoice.total` | numeric(18,4) → 2 | system-derived | — |
| Owing | CWP-027 | GAP | `invoice.total` less allocations | numeric(18,4) → 2 | computed-display | ⚠ **Separate from amount** |
| Replaced by | CWP-027 | prototype-extracted | the correction chain | text | system-derived | The replacement's **number**, not its id |

**6 · Acceptance** — **Given** an account with five bills including a corrected pair,
**when** the list loads, **then** amount and owing are separate columns, the part-paid
bill is neither paid nor due, the corrected original stays greyed naming its replacement,
and no draft bill appears.

**7 · Finance Calculation** — Owing = `invoice.total` − Σ allocations against it.
Worked: `$142.18 − $40.00 = $102.18`. Displayed to two decimals, stored to four. Reads
existing allocation arithmetic; no new formula.

**8 · Open Questions** — None.

---
id: US-CWP-033
epic: EP-CWP-07
module: portal
screens: [CWP-028]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-032]
journeys: [J36, J38]
rules: [BR-CWP-044]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-033 — One bill, line by line, grouped by service, every unit named

**1 · Details** — As **a customer**, I want **to see what I was charged for**, so that
**I can add it up myself and reach the same total**.

Lines grouped by service — **WATER · SEWER · TRASH · TAXES AND FEES** — each with
quantity, rate and amount. Then a summary: charges before tax, tax, total. A side panel:
brought forward, this bill, paid since, owing. And the readings behind the bill, with how
each was taken.

⚠ **UP TO ELEVEN SERVICES CAN APPEAR ON ONE BILL**, which is why grouping is structural
rather than cosmetic.

⚠ **EVERY USAGE LINE CARRIES ITS UNIT EXPLICITLY** — a hard rule, not a nicety, and it is
why the quantity column never shows a bare number.

⚠ **AND THE LINES SHOWN ARE THE ROUNDED ONES.** Money is stored to four decimals and
displayed to two; **a customer adding up the lines must reach the total.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-044` | Grouped by service; every usage line carries its unit | CONFIRMED — blueprint `P14`; hard rule 3 |
| Inherited | Money 4 decimals stored, 2 displayed; **round only at display** | CONFIRMED — hard rule 2, B4 |
| `BR-CWP-041` | No draft, no bill-run internals | CONFIRMED — blueprint §10 |
| `BR-CWP-071` | The readings behind the bill show **how they were taken** | CONFIRMED — blueprint `P14`, `P20` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `BL-2608-0141` | Water `$18.50 + $17.80 + $34.12`, Sewer `$35.67`, Trash `$22.00`, tax `$5.42`, regulatory fee `$8.67` |
| TC-2 | ⚠ **The arithmetic check** | Charges before tax `$128.09`, tax `$14.09`, total **`$142.18`** — and `$128.09 + $14.09 = $142.18` **exactly**, from the displayed figures |
| TC-3 | Tiered usage | *first 2,000 gal* at `$8.90 / 1,000 gal` = `$17.80`; *2,001–5,000 gal* — `2,820 gal` at `$12.10 / 1,000 gal` = `$34.12` |
| TC-4 · **negative** | Any quantity cell | ⚠ **Never a bare number.** `2,000 gal`, `1 cart`, `4,820 gal` — asserted on every row |
| TC-5 · **negative** | A bill with a service the customer no longer has | The historical line still shows; the bill is immutable |
| TC-6 · **negative** | A bill with eleven services | All eleven group correctly, including fire, which **counts** — one 6" line and two 2" lines reads `$60.00 + 2 × $12.00` on two lines. ⚠ **LAYOUT SUPERSEDED 2026-09-30, AMOUNT UNCHANGED** — PO ruling 2026-09-30, *"per service"* (decision log *"ONE-TIME BILL: SIX ANSWERS"* (5)): a counted service prints ONE line per service, count and sizes in its quantity/description, so this becomes **one fire line of `$84.00`**, not two. Re-checked on the code 2026-09-30 under base-per-asset: still **`$84.00`** (`tests/test_cr063_c3_fire_priced.py`, fire carries no base — decision log 2026-09-30 *"FIRE'S `$84.00` DOES NOT MOVE"*). **The one-line layout is NOT BUILT yet** (`07-billing/14-bulk-bill-run-changes.md` row 5); until it is, the code still prints two lines and `tc2b` asserts two. |
| TC-7 · **tenant isolation** | `BL-2608-0141` with an Oak Ridge session | Refused |
| TC-8 | The readings panel | `31 Jul 148,220` and `31 Aug 153,040`, and *"Both taken by a reader. Neither was estimated."* |
| TC-9 | Brought forward / paid since | `$0.00` and `$0.00`, owing `$142.18` |

**4 · Test Data** — `BL-2608-0141`, 1–31 August, issued 30 Aug, due 14 Sep.
Water: monthly service charge `$18.50`; usage first `2,000 gal` at `$8.90/1,000 gal` =
`$17.80`; usage `2,001–5,000 gal`, `2,820 gal` at `$12.10/1,000 gal` = `$34.12`.
Sewer: share of water used, `4,820 gal` at `$7.40/1,000 gal` = `$35.67`.
Trash: cart collection, `96 gal` cart, `1 cart` at `$22.00/cart` = `$22.00`.
State utility tax `4.25%` = `$5.42`; regulatory fee `$8.67`.
Charges before tax `$128.09`; tax `$14.09`; **total `$142.18`**.
Readings: `148,220` on 31 Jul, `153,040` on 31 Aug, both read by a meter reader.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Line description | CWP-028 | prototype-extracted | `invoice_line.description` | text | system-derived | Grouped by service |
| Quantity | CWP-028 | prototype-extracted | `invoice_line.quantity` + `unit` | numeric + text | system-derived | ⚠ **Unit mandatory** |
| Rate | CWP-028 | prototype-extracted | `invoice_line.unit_price` | numeric(18,6) → display | system-derived | Shown per its unit — `$8.90 / 1,000 gal` |
| Amount | CWP-028 | prototype-extracted | `invoice_line.amount` | numeric(18,4) → 2 | system-derived | — |
| Taxable | — | B2 | `invoice_line.is_taxable` | boolean | system-derived | Drives the tax group |
| Readings this bill | CWP-028 | prototype-extracted | `meter_read` feeding the period | — | system-derived | ⚠ With the **method** |

**6 · Acceptance** — **Given** bill `BL-2608-0141`, **when** it opens, **then** its lines
group by service, every quantity carries its unit, and the displayed lines add to
`$128.09` before tax and `$142.18` after — the same total the bill and the balance show.

**7 · Finance Calculation** — Displays existing invoice-line arithmetic and **must not
recompute it**. The check that matters is additive consistency: Σ(displayed line amounts)
= displayed subtotal, and subtotal + displayed tax = displayed total.
Worked: `18.50 + 17.80 + 34.12 + 35.67 + 22.00 = 128.09`; `128.09 + 5.42 + 8.67 =
142.18`. ⚠ **This is where B4's round-at-display rule is visible to a customer**, and a
penny of disagreement here is a support call.

**8 · Open Questions** — None. ⚠ Two of the three services on this fixture are **not
metered** — sewer is priced as a share of water and trash on the cart — which is
`BR-CWP-073` and matters on `CWP-033`.

---
id: US-CWP-034
epic: EP-CWP-07
module: portal
screens: [CWP-029]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-033]
journeys: [J36]
rules: [BR-CWP-045]
golden_tests: []
finance_calc: none
---
### US-CWP-034 — The bill as it was printed

**1 · Details** — As **a customer**, I want **the document you actually sent me**, so that
**what I see matches what is in my drawer**.

*"Exactly as it was printed and posted on 30 August."* Download and print.

⚠ **THE PDF IS THE LEGAL ARTEFACT AND THE SCREEN ABOVE IT IS A CONVENIENCE.** The
document is rendered from the template version **pinned to the bill at the moment it was
issued**, so a template redesigned next year does not silently rewrite last year's bills.

⚠ **THE PORTAL SERVES THAT SAME FILE. IT MUST NEVER RE-RENDER ONE OF ITS OWN.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-045` | Serves the issued file from its pinned template; never re-renders | CONFIRMED — blueprint `P15` |
| Inherited | Legal-class documents are held write-once for seven years | the document register |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Download `BL-2608-0141` | ⚠ **Byte-identical** to the file the bill run produced |
| TC-2 · **negative** | Redesign the tenant's bill template, then re-download | ⚠ **Unchanged.** The old bill still renders on its pinned version |
| TC-3 · **negative** | Change the tenant's logo, then re-download | Unchanged |
| TC-4 · **negative** | A bill whose document is missing from storage | A plain sentence and a route to ask, **not a re-render and not a 500** |
| TC-5 · **tenant isolation** | The document URL with an Oak Ridge session | Refused |
| TC-6 | A bill issued in Spanish | The pinned template **including its language variant** |
| TC-7 · **negative** | An invitee with Download permission | Allowed. One with only See | Refused |

**4 · Test Data** — `BL-2608-0141`'s rendered PDF, template `bill-v3`, pinned at issue on
30 Aug 2026. A `bill-v4` template published 1 Sep 2026 that must not affect it. A
Spanish-rendered bill on `bill-v3-es`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| The document | CWP-029 | prototype-extracted | `document` where kind = bill | bytes | system-derived | ⚠ Served, never regenerated |
| Pinned template version | — | prototype-extracted | `invoice.template_version` | text | system-derived | Includes the language variant |

**6 · Acceptance** — **Given** a bill issued on template `bill-v3`, **when** the tenant
publishes `bill-v4` and the customer downloads the old bill again, **then** the file is
byte-identical to what was posted in August.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-035
epic: EP-CWP-07
module: portal
screens: [CWP-030]
wave: 4
status: ready
blocked_by: []
depends_on: [US-CWP-033]
journeys: [J38]
rules: [BR-CWP-046]
golden_tests: []
finance_calc: proposed
---
### US-CWP-035 — Why this bill is different, and the lines must sum to the difference

**1 · Details** — As **a customer whose bill went up**, I want **the reason broken down**,
so that **I do not ring to ask**.

*"Why August cost `$3.74` more."* Four lines against last month, each with its own
figure. Then a comparison against the same month last year. Then a plain sentence about
what a jump usually is, and two routes — send a reading, query this bill.

⚠ **THE SINGLE BIGGEST DEFLECTOR OF PHONE CALLS IN THE BLUEPRINT, AND IT DOES NOT EXIST
IN ANY FORM TODAY.** Every ingredient is stored — the prior period's usage, the days in
each period, the rate version that applied, the discount that ended — **but nothing
assembles them into a difference.**

⚠ **IT IS ARITHMETIC OVER EXISTING READS, NOT A NEW SOURCE OF TRUTH, AND IT MUST NEVER
DISAGREE WITH THE BILL IT EXPLAINS.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-046` | The component lines must sum **exactly** to the stated difference | CONFIRMED — `CP-24` |
| — | The explainer never disagrees with the bill; it is a view, not a source | CONFIRMED — blueprint `P16` |
| Inherited | Round only at display | B4 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open the explainer for `BL-2608-0141` | *"Why August cost `$3.74` more"* |
| TC-2 | ⚠ **The arithmetic check, and it is the point of the story** | The four lines `+$8.83`, `$0.00`, `+$4.29`, `−$9.38` sum to **exactly `+$3.74`**, which is `$142.18 − $138.44` |
| TC-3 · **negative** | Perturb any component | The sum no longer matches and **the test fails**. ⚠ A tolerance here would defeat the whole story |
| TC-4 · **negative** | A bill that went **down** | Reads *"cost less"* with the signs reversed, and still sums |
| TC-5 · **negative** | The **first** bill on an account | ⚠ No comparison is offered at all — not a comparison against zero |
| TC-6 · **negative** | A period of different length | The days-in-period component appears as its own line rather than being absorbed |
| TC-7 · **tenant isolation** | The explainer with an Oak Ridge session | Refused |
| TC-8 | Against last August | `4,090 gal` → `4,820 gal`, rate unchanged |
| TC-9 · **negative** | A month where a **rate version** changed | The rate component is its own line, from the version that applied — not from today's tariff |

**4 · Test Data** — July `BL-2607-0139` `$138.44`, `4,090 gal`. August `BL-2608-0141`
`$142.18`, `4,820 gal`. Components: used more water `+$8.83`; trash cart charge unchanged
`$0.00`; a summer discount ended `+$4.29`; lower tax on a smaller sewer share `−$9.38`.
**Difference `+$3.74`.** Last August: `4,090 gal`, rate unchanged. A first-bill account
for TC-5.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Difference | CWP-030 | GAP | this total less the prior total | numeric(18,4) → 2 | computed-display | ⚠ Must equal Σ components |
| Usage component | CWP-030 | GAP | prior vs current consumption × the rate that applied | numeric(18,4) → 2 | computed-display | Uses the **rate version of the period** |
| Discount component | CWP-030 | GAP | discounts effective in each period | numeric(18,4) → 2 | computed-display | — |
| Days-in-period component | CWP-030 | GAP | period lengths | numeric(18,4) → 2 | computed-display | Its own line when they differ |
| Tax component | CWP-030 | GAP | tax on each period | numeric(18,4) → 2 | computed-display | — |

**6 · Acceptance** — **Given** July at `$138.44` and August at `$142.18`, **when** the
explainer opens, **then** it reads *"Why August cost `$3.74` more"* and its four lines
`+$8.83`, `$0.00`, `+$4.29`, `−$9.38` add to exactly `$3.74`.

**7 · Finance Calculation** — Difference = current total − prior total, decomposed into
usage, discount, period-length and tax components, **each computed against the rate
version effective in its own period**.
Worked: `$142.18 − $138.44 = $3.74`; `+8.83 + 0.00 + 4.29 − 9.38 = +3.74`. ✓
⚠ **PROPOSED, not signed.** This is **new arithmetic on a money path** and B4/B5 are
frozen, so the decomposition rule goes to finance through **HUMAN-GUIDE §6** before any
figure here is called signed. **A lane must not ratify its own formula.**

**8 · Open Questions** — None. ⚠ But the decomposition **rule** is a finance judgment,
not an engineering one: which components exist, and in what order they are attributed
when two move at once. Raise it with the figure above rather than choosing.

---
id: US-CWP-036
epic: EP-CWP-07
module: portal
screens: [CWP-031]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J36, J47]
rules: [BR-CWP-083, BR-CWP-045]
golden_tests: []
finance_calc: none
---
### US-CWP-036 — Documents and letters: what we sent, when, and by which route

**1 · Details** — As **a customer**, I want **everything you have sent me in one list**,
so that **"I never got it" has an answer**.

Document, kind, sent date, and **how** — *Post · Email*, *Email*, *Post*. Filters for
bills, receipts and letters. A *download a year* control.

⚠ **"I NEVER GOT IT" IS THE SECOND MOST COMMON CALL**, and outbound messages already keep
their rendered document — **so this list is a filtered read of a table that exists.**

⚠ **AND POST AND EMAIL REMAIN THE DELIVERY RECORD.** The portal is a convenience copy and
must show what was sent, when, and by which route.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-083` | Post and email remain the delivery record; the portal shows the record | CONFIRMED — `CR-068` `R4` |
| `BR-CWP-045` | Documents are served, never re-rendered | CONFIRMED — blueprint `P15` |
| Inherited | Legal-class documents write-once for seven years | the document register |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An account with 41 documents | Page 1 of 9, newest first, with kind and route on every row |
| TC-2 | A bill sent both ways | Route reads *Post · Email* |
| TC-3 | A receipt sent by email only | Route reads *Email* |
| TC-4 · **negative** | A new account with nothing sent | ⚠ An empty state naming what will fill it — the commonest first impression the portal makes |
| TC-5 · **negative** | A document the customer may not see — an internal letter | Absent |
| TC-6 · **tenant isolation** | The list with a Pine Hill session | Pine Hill documents only |
| TC-7 | *Download a year* | One archive of that year's documents, each the **issued** file — **BUILT 2026-09-08, `CR-085` `CPB-15`.** A zip, twelve calendar months including this one, one entry per kept document byte for byte. Nothing is merged: the artefacts are of more than one media type and a merged file would be a document the customer was never sent (`BR-CWP-045`) |
| TC-8 · **negative** | A notice that was **skipped** and produced no document | ⚠ **Not here** — it has no document. It appears on `CWP-068`, which is `US-CWP-039`, and that split is deliberate |
| TC-9 | **A RECEIPT OR A LETTER WHOSE COPY WE KEPT** (added 2026-09-08, `CR-085` `CPB-14`, `DEF-CWP-4697`) | The row hands it over, at `GET portal/documents/{number}/file`. ⚠ Until this landed the control was refused on EVERY non-bill row with the words *"We kept no copy of this."*, **which is false about every one whose copy we did keep** |
| TC-10 · **negative** | A document with no minted number (a notice, an account letter) | Held, and the reason is the true one: *Use Download a year instead*. ⚠ It is addressed by the number on the paper and never by a row id (B14 rule 31), so a document with none cannot be fetched one at a time — an honest limit, and the reason TC-7's archive is not merely a convenience |
| TC-11 · **negative** | A document we genuinely kept no copy of | Held, *"We kept no copy of this."* — the same sentence, now TRUE, and absent from the archive with the count saying **4 of 5** rather than the archive quietly being short |
| TC-12 · **negative** | A stored copy whose bytes no longer hash to the record | Refused BY NAME — *"We cannot vouch for this copy."* — and never softened into *no copy kept* (`BR-NOT-027`), and never a 500 (`DEF-CWP-4699`) |

**4 · Test Data** — Bill for August, 30 Aug 2026, Post · Email. Receipt for `$138.44`,
12 Aug 2026, Email. Bill for July, 30 Jul 2026, Post · Email. *Your June bill was
corrected*, 12 Jul 2026, Post. Payment plan agreement, 3 Mar 2026, Post · Email. 41 rows
in total.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Document | CWP-031 | prototype-extracted | `document.title` | text | system-derived | Plain English, never a filename (B14 rule 31) |
| Kind | CWP-031 | prototype-extracted | `document.kind` | enum | system-derived | Bill · Receipt · Letter · Agreement |
| Sent | CWP-031 | prototype-extracted | `outbound_message.sent_on` | date | system-derived | — |
| How | CWP-031 | prototype-extracted | `outbound_message.channel` | enum[] | system-derived | ⚠ Every route it went by |

**6 · Acceptance** — **Given** an account with 41 documents, **when** the list opens,
**then** each row names the document in plain English, its kind, when it was sent and by
which route — and a notice that was never sent is not here, because it has no document.
**AND (added 2026-09-08, `CR-085` wave 3): every row whose copy we kept can be TAKEN
AWAY**, not only the bills; the year's archive is one file; and a row we cannot serve says
which of the two reasons it is.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-037
epic: EP-CWP-07
module: portal
screens: [CWP-032]
wave: 3
status: ready
blocked_by: []
depends_on: [US-CWP-031, US-CWP-061]
journeys: [J40]
rules: [BR-CWP-048, BR-CWP-049]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-037 — Your final bill, where the deposit comes back

**1 · Details** — As **a customer moving out**, I want **the last bill with my deposit
settled**, so that **I know what I owe or what is coming back**.

*"For 1–17 September, up to the reading taken on the day you left."* Then settling up:
service to 17 September, deposit held, interest on the deposit, and **we owe you**. Then
what happens next, and the closing reading with a *query this reading* route.

⚠ **THE FINAL BILL IS WHERE A DEPOSIT COMES BACK, AND IT IS THE LAST CHANCE TO QUERY A
READING CHEAPLY.** Once the final bill is settled the account closes and a correction
becomes a much slower business — **so the screen says that before the customer leaves.**

⚠ **IT CAN END IN A NEGATIVE BALANCE, WHICH IS A REFUND AND NOT A CREDIT TO CARRY
FORWARD**, because there is no next bill to carry it to.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-048` | A negative final balance is a **refund**, never a carried credit | CONFIRMED — blueprint `P18` |
| `BR-CWP-049` | The deposit and its accrued interest are settled here | CONFIRMED — `CP-43` |
| Inherited | Move-out settlement, deposit interest and final billing already exist | the existing move-out |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Move-out on 17 Sep with a `$150.00` deposit | Service `$63.40`, deposit `−$150.00`, interest `−$3.20`, **we owe you `$89.80`** |
| TC-2 | ⚠ **The arithmetic** | `$63.40 − $150.00 − $3.20 = −$89.80`, presented as *we owe you `$89.80`* |
| TC-3 · **negative** | A final bill where service **exceeds** the deposit | Reads as an amount **owed**, with a Pay control — not *we owe you* with a negative sign |
| TC-4 · **negative** | The `$89.80` | ⚠ Raised as a **refund**, not written as a credit on a closed account. Assert a refund row exists and no credit note does |
| TC-5 | The deposit figures | ⚠ Match `CWP-065` exactly — `$150.00` held since 4 Mar 2021 with `$3.20` interest |
| TC-6 · **negative** | An account with **no** deposit | The deposit lines are absent, not `$0.00` |
| TC-7 · **tenant isolation** | The final bill with an Oak Ridge session | Refused |
| TC-8 | The closing reading | `154,310`, taken 17 Sep by a reader, `1,270 gal` used since 1 Sep, with a query route |
| TC-9 · **negative** | Query the closing reading **after** settlement | The route is gone, and the screen says a correction is slower now |

**4 · Test Data** — Final period 1–17 September 2026. Service to 17 Sep `$63.40`. Deposit
held `$150.00`, taken 4 Mar 2021, interest `$3.20`. **We owe you `$89.80`.** Refund goes
to `91 Cedar Row, Austin TX 78704`; allow ten working days. Closing reading `154,310`
taken 17 Sep by a reader; `1,270 gal` since 1 Sep.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Service to date | CWP-032 | prototype-extracted | final `invoice.total` | numeric(18,4) → 2 | system-derived | — |
| Deposit held, interest | CWP-032 | prototype-extracted | `account.deposit_on_file` + accrual | numeric(18,4) → 2 | system-derived | ⚠ Must equal `CWP-065` |
| We owe you | CWP-032 | prototype-extracted | the settlement result | numeric(18,4) → 2 | computed-display | ⚠ A **refund**, not a credit |
| Closing reading | CWP-032 | prototype-extracted | `meter_read` on the move-out date | numeric + unit | system-derived | With its method |

**6 · Acceptance** — **Given** a move-out on 17 September with `$63.40` of service and a
`$150.00` deposit earning `$3.20`, **when** the final bill opens, **then** it reads *we
owe you `$89.80`*, raises a refund rather than a credit, and offers one last route to
query the closing reading.

**7 · Finance Calculation** — Settlement = service to the closing reading − deposit held
− accrued interest.
Worked: `$63.40 − $150.00 − $3.20 = −$89.80` → **refund `$89.80`**.
Existing, tested move-out settlement; this screen **reads** it. ⚠ **The figures must
agree with `US-CWP-031`'s deposit panel** — a disagreement between the two is the defect
both stories test for.

**8 · Open Questions** — None. ⚠ Whether the customer may **initiate** the move-out is
`OQ-1392` and belongs to `US-CWP-061`; this story is the bill that results either way.

⊕ **AS BUILT (2026-09-04, shipped in `2.164.0`) — AND BUILDING IT FOUND THAT NO FINAL BILL COULD SETTLE AT ALL
ON AN ACCOUNT HOLDING A DEPOSIT (`DEF-CWP-3842`).** `billing.final_bill.settle_account`
asked `deposit_credit_for` for an accrual without naming the day it accrues to;
`deposit_interest_accrued` answers `None` to that by design (G6 keeps a wall clock out of a
money path), so the settlement refused BY NAME on every deposit-holding account — which at a
utility that takes deposits is every residential one. `settle_final_bill` now passes
`as_of=invoice.period_end`, the move-out day, read off the bill rather than off a clock.
**Worked on the fixture:** `$63.40` service against `$150.00` held since 4 March 2021 at a
seeded 0% rate → `$0.00` interest (a real answer, not a refusal) → remainder **`−$86.60`**,
path **refund**, automatic. §4's `$3.20` is what a 2%-rate tenant earns; the test asserts the
ARITHMETIC rather than the literal, because a literal would assert the engine's answer back
at it.

⊕ **THE SCREEN COMPUTES NOTHING.** Every figure is `settle_final_bill`'s — the same function
that settles the account for a clerk — and TC-5's *must equal `CWP-065`* is asserted on ONE
account in ONE run, field by field, rather than trusted. **The sign is the server's**: `-89.80`
renders as `-$89.80` under the words *We owe you*, and no `Math.abs` appears on the screen.
`BR-CWP-048`'s *refund, never a credit* is the engine's own `path`, not a reading of the sign.

---
id: US-CWP-038
epic: EP-CWP-07
module: portal
screens: [CWP-031, CWP-041]
wave: 3
status: draft            # was `blocked`; OQ-1395 ruled 2026-09-04 — a real statement document, with an opening and closing figure that ties to the balance
blocked_by: []
depends_on: [US-CWP-036]
journeys: [J36]
rules: [BR-CWP-047]
golden_tests: []
finance_calc: none
---
### US-CWP-038 — A statement, or the transaction list named as one

**1 · Details** — As **a business customer's bookkeeper**, I want **one document covering
a date range**, so that **I can file it**.

⚠ **BLOCKED, AND THE BLOCK IS A REAL ABSENCE RATHER THAN A PREFERENCE.** *"There is no
statement document in this product. A bill is not a statement."* Either the transaction
list becomes the statement and we say so, or a statement gets built. **`OQ-1395`.**

Implement to the boundary: the date-range read over bills, payments, credits and
adjustments — which is `US-CWP-036` plus `US-CWP-048` — and stub the **document** as
`raise NotImplementedError("OQ-1395")`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-047` | ⚠ It must open with a brought-forward and close with a carried-forward that **matches the balance read** | CONFIRMED — `CP-28` |
| — | Whether the transaction list **is** the statement, or a statement is built | **OPEN — `OQ-1395`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Pick 1 January to 30 June | The read returns every bill, payment, credit and adjustment in the window, in date order |
| TC-2 · **negative** | Request the **document** | `NotImplementedError("OQ-1395")` — ⚠ the id in the code |
| TC-3 | ⚠ **The tie-out, once ruled** | Opens with a brought-forward and closes with a carried-forward that **equals** the balance read on the closing date |
| TC-4 · **negative** | A window with no activity | An honest empty result, not a zero-row document |
| TC-5 · **negative** | A window spanning a **corrected** bill | The pair appears as two rows, correction and replacement, and the carried-forward counts it once |
| TC-6 · **tenant isolation** | The read with an Oak Ridge session | Refused |

**4 · Test Data** — 1 Jan – 30 Jun 2026: bills `BL-2601`…`BL-2606-0147`, payments
including the bounced `#10174` pair, two credits of `$25.88`. Carried-forward on 30 Jun
must equal that date's balance read.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Brought / carried forward | CWP-031 | GAP | the balance read at each boundary | numeric(18,4) → 2 | computed-display | ⚠ Must tie to `US-CWP-024` |
| The document | — | GAP | **none yet** | — | — | ⚠ **Stubbed on `OQ-1395`** |

**6 · Acceptance** — **Given** a customer picking 1 January to 30 June, **when** they ask
for a statement, **then** the underlying read returns every transaction in order and the
document request raises `NotImplementedError("OQ-1395")` — because whether this list *is*
the statement has not been decided.

**7 · Finance Calculation** — N/A until ruled. ⚠ The tie-out above **is** the arithmetic
that matters, and it is a reason to answer `OQ-1395` rather than build twice.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1395` | What does the portal count as a statement? | `CP-28`, this story | Product Owner | OPEN |

---
id: US-CWP-039
epic: EP-CWP-07
module: portal
screens: [CWP-068]
wave: 3
status: draft            # was `blocked`; OQ-1399 ruled 2026-09-04 — the portal is a convenience copy; post and email stay the delivery record
blocked_by: []
depends_on: [US-CWP-036]
journeys: [J47]
rules: [BR-CWP-083, BR-CWP-084, BR-CWP-085, BR-CWP-086]
golden_tests: []
finance_calc: none
---
### US-CWP-039 — Every notice sent, and every notice deliberately not sent

**1 · Details** — As **a customer**, I want **to see the notice that never reached me**,
so that **I am not disconnected over a letter you could not deliver**.

A list of notices with type, tier, channel and **outcome** — including
*"Final notice · 15 Sep · post · **not sent, no forwarding address**"*.

⚠ **THE NOTICE THAT WAS SKIPPED IS THE ONE THE CUSTOMER MOST NEEDS TO KNOW ABOUT, AND IT
IS THE ONE THAT IS INVISIBLE TODAY** — because a skipped notice produced **no document**,
so `CWP-031` cannot show it. **That is why this is its own screen.**

⚠ **BLOCKED ON `OQ-1399`, THE ONE TO ANSWER FIRST.** A disconnection notice has legal
delivery requirements; a portal message is not proof of delivery, and *"treating it as one
would be the most consequential mistake available here"*. It decides whether the portal
is a convenience layer or a **system of record** — which changes the audit, the retention
and the legal review of nearly every screen in the paying and requesting sections.

Implement to the boundary: read `NoticeHistory` and render every outcome including the
skips. **Stub any path that would treat a portal row as delivery** as
`raise NotImplementedError("OQ-1399")`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-085` | A notice deliberately not sent is shown, with its reason | CONFIRMED — `CP-49` |
| `BR-CWP-084` | ⚠ The portal **waits**; it is a record that a message exists, never proof it arrived | CONFIRMED — blueprint §19 Figure 13 |
| `BR-CWP-083` | Post and email remain the delivery record | CONFIRMED — `CR-068` `R4` |
| `BR-CWP-086` | Returned post shows above the address field and clears when fixed | CONFIRMED — `CP-50` |
| `BR-CWP-088` | Whether a notice may be **delivered** on the portal | **OPEN — `OQ-1399`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Three notices, one skipped | All three listed. The skip reads *"Final notice · 15 Sep · post · not sent, no forwarding address"* |
| TC-2 · **negative** | The skipped notice on `CWP-031` | ⚠ **Absent there** — it has no document. The split between the two screens is the point |
| TC-3 · **negative** | A message the product **could not send** | Shown with `unavailable` and its reason |
| TC-4 · **negative** | Any code path that records a portal row as **delivery** of a notice | `NotImplementedError("OQ-1399")` |
| TC-5 | Two returned letters | `CWP-024` shows them above the address field; correcting the address clears the flag |
| TC-6 · **tenant isolation** | The list with a Pine Hill session | Pine Hill notices only |
| TC-7 · **negative** | A customer who is paperless and **never signs in** | ⚠ Post still went. Assert the notice's outcome names post, not the portal |
| TC-8 · **negative** | An empty notice history | The screen and its link are absent |

**4 · Test Data** — Reminder sent 21 Aug by email and post. First notice sent 1 Sep by
post. **Final notice 15 Sep, post, not sent — no forwarding address.** Two
`DeliveryReturnEvent` rows and `bad_address = true`. A paperless customer who has not
signed in since enrolment.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Notice type, tier | CWP-068 | prototype-extracted | `NoticeHistory.notice_type`, `tier` | enum | system-derived | ⚠ An unmapped tier renders as an **absence** (`BR-CWP-092`) |
| Channel | CWP-068 | prototype-extracted | `NoticeHistory.channel` | enum | system-derived | — |
| Outcome, skip reason | CWP-068 | prototype-extracted | `NoticeHistory.outcome`, `skip_reason` | enum, text | system-derived | ⚠ **The skip is the most visible row** |
| Portal delivered / read | — | GAP | the portal's per-recipient message row — `delivered_at`, `read_at` (⚠ not columns on `outbound_message`; its docstring forbids them — `DEF-CWP-3612`) | timestamptz | system-derived | ⚠ **Queued and visible, never arrived** |

**6 · Acceptance** — **Given** a final notice that was never posted because there is no
forwarding address, **when** the notices screen opens, **then** that row is the most
visible thing on it with its reason — and any path that would treat a portal row as
delivery of a notice raises `NotImplementedError("OQ-1399")`.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1399` | Is the portal a channel a notice can be delivered on? | `CP-17`, `CP-49`, `CP-50`, this story, and the shape of release 3 | Product Owner | OPEN — ⚠ **the one to answer first**, before release 3 starts |
