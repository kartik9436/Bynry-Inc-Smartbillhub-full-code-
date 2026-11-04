# One-time bill — redesign confirmed by the PO (2026-09-30)

Status: **CONFIRMED DESIGN, NOT BUILT.** The PO walked every table below in the
working chat session on 2026-09-30 and confirmed each (*"this is all correct"*,
*"this si correct"*, *"rest is all corect"*), and said *"don't fix anything yet"*.
The rulings behind it are in `12-governance/02-decision-log.md` under 2026-09-30.
Mock-up: https://claude.ai/artifact/DYnXV9VSuKxoRtXFhmFJrB (example data only).

It replaces the live `OneTimeBillTab.tsx` flow and the unfinished three-step
`OneTimeWizardShell`. Where it differs from the Billing blueprint's step count,
this is the PO's later word: *"i need 1 word step name not 2 - and workflow should
not be more than 3 or 4 steps"*.

## 1. Steps

| # | Step | Content |
|---|---|---|
| 0 | (kind cards) | Interim · First bill · Final · Catch-up · Penalty / theft · Fee |
| 1 | **Account** | **Searchable dropdown** (PO 2026-09-30: *"this si searchable dropdown"*) — type a name, account no. or address; each option shows name · status · account no. · address, the match highlighted, keyboard ↑ ↓ Enter; picking fills the result card. Then the kind's fields (§2) |
| 2 | **Services** | Services table (§3), readings and the kind's extras (§4), live total |
| 3 | **Review** | The bill as it will print, as a **table** (PO 2026-09-30: *"can you improve the Charge - maybe make it table"*): columns Service · Meter / asset · Charge (Usage, Base, Per cart, % of water, Deposit, Fee) · Quantity with unit · Rate · Amount; rows grouped by period (one group per missed period for catch-up and penalty; move-in charges and other charges as their own groups), each group with its subtotal; then subtotal, tax, total. Warnings, delivery; Save draft |
| 4 | **Send** | Total, due date, warnings, *"Final once sent. Changes need a credit note."*, a tick box *"I checked the amounts"* that unlocks **Send**; then the sent state (bill no., due date, delivery queued) |

Also drawn: a **problems state** (every problem at once, each on its field) and an
**already-billed state** (who billed this period and when, with a link).

## 2. Step 1 fields by kind

| Field | Interim | First | Final | Catch-up | Penalty | Fee |
|---|---|---|---|---|---|---|
| Account | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Period from / to | ✔ | ✔ (from = move-in date, prefilled) | ✔ (to = move-out date) | — | — | — |
| List of missed periods | — | — | — | ✔ (add rows) | ✔ (add rows) | — |
| Reason code — dropdown from Settings | — | — | — | ✔ | ✔ | — |
| Bill date — required, defaults to today | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Days to pay — defaults from the account's cycle | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Due date — shown, derived from the two above | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Charge code — dropdown, amount read-only | — | — | — | — | ✔ optional (e.g. Tamper $250) | ✔ required |

## 3. Services decision table

| Service example | Status badge | On the bill |
|---|---|---|
| Water (meter, reading entered) | Billed | Usage + base |
| Electric (meter, reading entered) | Billed | Usage + base |
| Trash (1 cart) | Billed · 1 cart | Count × (rate + base) — base per cart, ruled 2026-09-30 (`BR-RAT-090`) |
| Sewer | Billed · follows water — no service point | % line + base |
| Gas (no meter) | Not in service | **No line, $0** |
| Fire (no asset) | Not in service | **No line, $0** |
| A service the account didn't take | Not taken | No line; the clerk still sees it here |
| A service with no base charge set up | Billed · base $0.00 ⚠ | Usage + $0.00 base, warning |
| Two assets for one service | Billed · 2 | Counted: count × (rate + base) — 2 carts = 2 × ($15.00 + $3.00) = $36.00 (`BR-RAT-090`, 2026-09-30). Metered: one line per meter, each with its own tiers and base (`BR-BIL-1049`) |

## 4. Step 2 by kind

**Order and behaviour on screen (PO, 2026-09-30, on the mock-up):** *"services , Rates,
Move-in charges { deposites + fees} - they should be in this order and then readings -
can you make services , Rates, Move-in charges { deposites + fees} - collapable/expand"*,
and *"on step 2 - you ahve to show - rates for each service or meter as a sepearte table"*.
So step 2 runs **Services → Rates → Move-in charges (first bill only) → Readings →**
then Periods / Settlement / Evidence / Charge as the kind needs. The first three are
collapsible and open by default. **Rates** is one row per meter or billed service:
rate type · usage rate · base charge (code, or *Not set · $0.00* ⚠) · minimum · price
version (per period, with the split, for catch-up and penalty) · amount; services not in
service show *No rate used*, $0.00.

| Section / item | Interim | First bill | Final | Catch-up | Penalty / theft | Fee |
|---|---|---|---|---|---|---|
| Services table | ✔ | ✔ | ✔ | ✔ | ✔ | ✖ |
| Readings shown | ✔ | ✔ | ✔ | ✔ per missed period | ✔ read-only | ✖ |
| Reading rows | One per meter; 2 meters = 2 rows | One per meter | One per meter | Per meter per period | Per meter per period | — |
| Meter no. | Meter Reads | Meter Reads | Meter Reads | Meter Reads | Meter Reads | — |
| Previous reading | Last on file | Move-in reading; clerk types it if none | Last billed | Start of each period | Start of each period | — |
| Previous read date | Meter Reads | Move-in date | Meter Reads | Meter Reads | Meter Reads | — |
| New read date | Clerk; defaults to period end | Clerk; defaults to period end | Move-out date, fixed | Clerk, last period only | — | — |
| New reading | Clerk | Clerk | Final reading, required | Clerk for last period; earlier missing ones estimated | — (assessed reads from Meter Reads) | — |
| Usage | New − previous, with unit | New − move-in | Final − previous | Per period, with unit | Per period (assessed) | — |
| Reading status | Accepted / refusal on the row | Accepted / refusal | Accepted / refusal | Actual · Estimated · refusal | Assessed, not verifiable | — |
| Reading needed to continue | Yes, per meter | Yes, move-in + new | Yes, final | Last period only | No | — |
| Periods table | — | — | — | Period · days · price version · Actual/Estimated · split note | Same | — |
| Move-in charges | — | Deposit (asked − already paid) · Connection charge (CONN) | — | — | — | — |
| Settlement box | — | — | This bill + prior balance − deposit − interest = refund / left to pay / write-off; path: collect · payment plan · transfer | — | — | — |
| Evidence | — | — | — | — | What was found + optional photos | — |
| Charge line | — | — | — | — | Optional | Only content: code · name · amount · note |

Rules for every kind: a reading is saved through Meter Reads (`/read-batches`),
never by billing; a multi-register meter links to the full readings screen; no
reading row for a service with no meter, a counted service or sewer; estimated and
assessed reads are tagged on screen and on the bill.

## 5. Review gaps this design closes

| Gap | Fix |
|---|---|
| Days to pay never sent; bill date optional | Both captured; due date shown |
| No Send | Send step |
| Sewer with no service point billed $0 | Sewer follows water |
| No reading entry | Reading rows with previous reading and date |
| No charge code sent; Fee not offered | Charge-code dropdown; Fee kind |
| Reason code free text | Dropdown from Settings |
| Generic refusal text, one problem at a time, not on the field | Clear messages, all at once, each on its field |
| Not-taken services invisible | Shown in the services table |
| Missing base charge refuses the account | $0.00 + warning |
| Gas / fire with no asset refuses or bills a base | Not in service, no line |

## 6. Open questions (asked 2026-09-30, unanswered)

1. ~~Two meters on one metered service~~ — **ANSWERED 2026-09-30:** *"both meter
   should be build in metered case also - as a speearte line"* → option A: each meter
   its own line, own tiers, own base ($58.40 on the worked example; $29.20 today).
2. ~~Counted services~~ — **ANSWERED 2026-09-30: base per cart** (2 × ($15.00 + $3.00) = $36.00).
3. **Fee bill tax** — **ANSWERED 2026-09-30: yes**, a taxable charge code is taxed ($75.00 → $81.19 at 8.25%); `OQ-812` closed; needs a B4.2 ❄️ re-sign before code.
4. **Account with no service agreements** — **ANSWERED 2026-09-30: bill every connected service and show the clerk a warning.**
