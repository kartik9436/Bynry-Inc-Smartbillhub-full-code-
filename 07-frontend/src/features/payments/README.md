# features/payments — recording money and reading the ledger

Docs: `04-docs/05-modules/08-payments/`.

Shipped here: **S33 · Record payments** (US-PAY-004) at
`/{tenant}/payments/record`, the **S22/S35 Record payment modal** (US-PAY-001)
that opens from it, and — from 2026-08-15 — **S32 · Summary** (US-PAY-005) and
**S34 · Outstandings** (US-PAY-013) with the write-off (US-PAY-012) and
collections-run (US-PAY-014) actions on it. ~~S32 and S34 are named on screen as
arriving with their own epics.~~ All three tabs of the prototype's Payments page
call a real endpoint now; no tab renders an *arrives with* panel.

> **Why this folder existed with one line in it until 2026-08-11.** The payments
> write path landed that morning, complete and tested: `services.record_payment`
> takes a payment, allocates it across the customer's open bills oldest-first
> (BR-PAY-010, GT-7 frozen), writes the `allocations` rows, posts DR cash / CR AR
> to the ledger and audits every step — nineteen passing tests — and
> `apps/payments/api.py` was a one-line docstring, so **no human being could
> record a payment**. Hard-won law 2 at feature scale. This lane built the two
> endpoints and this screen together.

---

## The API — served, and written down here because nothing else states it

Both routes are **SERVED** as of 2026-08-11 (`apps/payments/api.py`,
`config/urls.py`). The paths are not invented here: `POST /accounts/{id}/payments`
is A11 §S22's own row and `GET /payments` is A11 §S33's, both audited in
`04-docs/01-spec/11b-api-audit.md` §1.

| Route | Screen | Contract row |
|---|---|---|
| `POST /accounts/{id}/payments` | S22 · S35 Record payment | 11b §1 (STALE payload, **regenerated** — see below) |
| `GET /payments` | S33 ledger · S21 Payments tab (`f.account_id`) | 11b §1 (**OK**, amended) |

**No PUT/PATCH/DELETE exists on a payment anywhere** — BR-PAY-002 / HR-4 / 11b
G8. Both views declare exactly one verb, so a forged one is 405 before any
handler body runs. A correction is a new reversing row (US-PAY-010).

⚠ **THAT LAST SENTENCE ENDED *"…with an endpoint that does not exist yet"* UNTIL
2026-09-01 AND IT IS NO LONGER TRUE (hard-won law 1).** `POST /payments/{id}/reverse`
landed with CR-059 task 15 and this folder calls it — see *The bounce and the
refund* below.

### `POST /accounts/{id}/payments` — the regenerated payload

11b marks A11's original `amount, method, apply_to` **STALE**: it contradicts
BR-PAY-021 (posting date ≠ clearing date, both always), BR-PAY-033 (the posting
date is USER-ENTERED, never the system clock), BR-PAY-012 (every payment carries
a purpose) and BR-PAY-022 (reference + allocation choice). The entry-point
PLACEMENT was never stale — BR-CUS-037 puts it on the account. This is the
regeneration:

| Field | Rule | Notes |
|---|---|---|
| `amount` | A2 §S22 `> 0` | decimal **string**; a float is REFUSED, never converted (CLAUDE.md #2) |
| `posted_at` | BR-PAY-021 · BR-PAY-033 | **required.** The user's date. The server stamps no clock — gate G6 bans one in this path |
| `cleared_at` | BR-PAY-021 | absent/null = still `processing`: the money has not arrived. A legal state, not a missing value |
| `method` | BR-PAY-026 | a tenant lookup **code**; an unknown or deactivated one is refused |
| `confirmation` · `memo` | BR-PAY-022 · r14 #4 | optional |
| `purpose` | BR-PAY-012 | defaults `bill`. ~~the other three are refused BY NAME~~ **SUPERSEDED 2026-08-15 — `apps/payments/purposes.py` built all four linkages and both record forms now offer all four; a refusal now means THIS account cannot take that purpose (no deposit position, no live plan), not that the product cannot** |
| `apply_to` + `targets[]` | BR-PAY-001 · BR-PAY-010 | the staff allocation instruction, passed straight through to the allocator |
| `idempotency_key` | BR-PAY-028 | **required** — see below |
| `currency` | BR-TEN-042 | optional; must equal the account's, never converted |

**`idempotency_key` is required and that refusal is the point.**
`record_payment` stores no key when the caller names none, and a double submit
then records two payments. Generating one server-side would produce a different
string on the second submit and dedupe nothing while looking as though it had —
so the only honest options are "require it" and "take the money twice".

**A replay answers `200` with the ORIGINAL payment and `created: false`**, not
409. 11b §3 G7 makes a duplicate a 409 for the four operations it enumerates
(bill runs, read/payment **imports**, webhooks, tenant provisioning); a staff
double-click is none of them. BR-PAY-028's own field-map row reads *"duplicate
submit → single row"*, US-PAY-001 TC-6's expected outcome is "One row only", and
G7's list already contains the same shape (`POST /tenants` — *"repeat returns
existing tenant"*). A 409 toast for a button that worked is a wrong answer a
clerk would act on.

### `GET /payments` — the S33 ledger

Request params are BR-SHL-011's grammar, unchanged: `q`, `sort`, `dir`, `page`,
`per`, `f.<name>`. The response is the standard DRF page envelope plus **two**
extra members, exactly as `GET /invoices` carries its roll-up:

* `totals` — US-PAY-004 TC-1's *"totals row per current filter"*. Its money
  member is `null` (with `amount_unavailable` naming the case) when the filter
  matched nothing, when the rows span more than one currency, or when any signed
  credit/adjustment row is in the set — B2's own O-4 residue leaves that sign
  open, so summing one could be wrong by twice the row.
* `methods` — the tenant's LIVE method list (BR-PAY-026 / BR-REP-006). The S33
  method FILTER and the S22 method PICKER read this one list, so the two can
  never offer different vocabularies. It is served here because
  `GET /lookups/payment_methods` **404s on this deployment**: payments is the
  content owner of that reference list (BR-TEN-031) and has registered no lookup
  handler. Reported.

| Row field | Column / derivation | Notes |
|---|---|---|
| `payment_no` | `payments.payment_no` | the PMT- series, minted at record (BR-TEN-035). Nullable in the schema, so the cell renders a stated absence for a null |
| `posted_at` / `cleared_at` | same columns | **both, always** (BR-PAY-021). `cleared_at: null` renders as *processing*, never as a blank date |
| `method` / `method_name` | `payments.method_id` → the tenant lookup | code + display name; both null on a row with no instrument |
| `applied_to[]` | read-model over `allocations` → billing's invoice numbers | **all** of them; the number is read through the seam, and a null number still carries its amount |
| `applied_total` | Σ of this payment's allocation rows | exact; nothing is re-rounded |
| `deposit_batch_id` | — | **always null.** `deposit_batches` is EP-PAY-06's table and nothing writes the column |
| `receipt_no` | — | **always null.** BR-PAY-024's receipt queue is US-PAY-025's and is not built; a number here would name a receipt nobody sent |

Sorts (`PAYMENT_SORTS`): `posted_at`, `cleared_at`, `amount`, `account`,
`status` — the capability row verbatim, default **`posted_at` desc**.
Filters (`PAYMENT_FILTERS`): `type`, `method`, `status`, `purpose`,
`account_id`, `posted_from`, `posted_to`, `cleared_from`, `cleared_to`.
Search (IS-3): account #, customer name, confirmation #.

---

## Screens

| File | Screen | Story |
|---|---|---|
| `PaymentsPage.tsx` | S33 · Payments (three tabs; Record payments is built) | US-PAY-004 |
| `PaymentsPage.tsx` → `RecordPaymentModal` | S22 · S35 Record payment | US-PAY-001 |
| `PaymentsPage.tsx` → `ReversePaymentModal` | S35 · Reverse a payment (CR-059 P2) | US-PAY-009 |
| `RefundsPage.tsx` | S58 · Refunds, `/finance/refunds` (CR-059 P3) | US-PAY-011 |
| `paymentsShared.tsx` | routes, tabs, vocabularies, the honest cells | both |

---

## What the prototype draws that this screen does not — and one place it is right

Hard-won law 6 says diff the running app against `05-prototype/` and report
**both** directions.

**Where this screen deviates, and the rule that outranks the prototype:**

* **No bulk toolbar** ("3 selected · $988.70 total" → Reverse · Reapply to bill
  · Send receipts · Post to QuickBooks). Every one is another story's write
  endpoint and none exists; three of the four are additionally **blocked on PO
  decisions that have not been made** (OQ-132..137 in
  `12-governance/12-payments-decision-batch.md`). A checkbox column selecting
  rows for nothing is worse than no checkbox column.
* **No row-action menu** (View · Reverse · Reapply · Send receipt · Refund) —
  same reason. There is no payment DETAIL route either: no contract row defines
  one, and the only thing a detail would add over the row is *what the payment
  paid*, which is on the row already as `applied_to`.
* **No "Import lockbox" / "Post adjustment" / "Issue credit" header actions.**
  US-PAY-003's staged import is unbuilt and its posting-date semantics are
  **OQ-131, blocking**; the adjustment and credit family is US-CUS-013's.
* **No CSV export.** `POST /exports` registers no `payments` resource, and
  BR-SHL-010 keeps an undeclared capability unrendered.
* ~~**No date-range filters on screen**, although the server accepts four of
  them: the shared FilterBar renders option lists only, and an empty select
  where a date range belongs narrows nothing while looking as though it had.~~
  **SUPERSEDED 2026-09-03 — `CR-059` `CS-40`, `DEF-3504`.** The Product Owner,
  walking all four Record payments tabs: *"I cannot filter payment by date"*.
  The reason above was true and had stopped being about payments: the server
  accepted all four params and `PAYMENT_FILTERS` had always declared them, and
  the gap was one missing kind on a SHARED type. A sibling lane widened
  `TableFilterConfig` with a `dateRange` descriptor and taught `FilterBar` to
  draw it in the same `+ Filter ▾` panel; this screen now declares **two**
  ranges — posted and cleared — and a clerk who sets 1–31 August narrows the
  rows, the count and the total together, because all three come off the one
  filtered response. The range survives a refresh through the request state's
  existing round trip. **It is written out rather than deleted (hard-won law 1:
  the next reader must meet the fact, not a gap where a claim used to be).**
* **The Record modal shows no "Current balance".** The prototype prints
  `$247.30` at the top of the form. `accounts.balance` is customers' CACHED
  column and this payment does not update it (B1 / DB-16), so the figure would
  be stale in the one moment it mattered.
* **Two of BR-PAY-001's four allocation choices render DISABLED with their
  reason.** "A specific bill" and "Split across bills" need a picker of the
  account's OPEN bills with what each still owes, and no endpoint serves that
  position — `GET /invoices` serves the ISSUED total, which after a partial
  payment is not what the bill owes (PE-2: issued $247.87, still open $47.87).
  **OQ-154**, raised.
* **The single "Payment date" field is replaced by two.** BR-PAY-021 is the
  cardinal rule of this module and the PO ruled on it again on 2026-08-11:
  *"posting and actual dates can differ; ask actual date to user."*
* **The method list has no "Lockbox" option.** BR-PAY-026 supersedes it:
  lockbox is an intake CHANNEL (BR-PAY-023), and the row's method comes from the
  instrument.
* **The third tab reads "Outstandings", not "Outstandings (184)".** The count
  is a live aggregate over the S34 read-model (US-PAY-013) and nothing computes
  it; a hardcoded 184 would be a figure about a tenant's debtors that no row
  supports.

**Where the prototype is right and this screen is behind:**

* **The prototype opens the Payments page on "Record payments"**
  (`payTab: 'record'`, prototype line 6204). This screen opens on **Summary**,
  because the ratified sidebar (BR-SHL-001 / `SHELL_NAV`) maps the parent path
  `/payments` to Summary — and a sidebar item that lands somewhere other than
  its own label says is a worse defect than a landing tab. So the first thing a
  clerk sees under Payments is a panel saying the summary is not built. Changing
  the sidebar is a ratified-nav change and belongs in the PO batch; **reported**
  rather than taken.
* **The prototype's S33 has a `Summary` tab with real KPIs** (Today $18,420 · 84
  payments · method mix · failed · collections). Every figure is computable from
  data the product now has, and none of it is built here: US-PAY-005 owns it.

---

## What a clerk sees after recording

The modal closes, a toast fires, and a **result panel** stays on the page. It
shows the PMT- number, the amount, what was applied, what was carried as credit
(BR-PAY-010 / PE-4's $57.13), and **each bill the money met with its figure** —
all through `MoneyCell`, none of it recomputed in the browser. It then states
two things most screens leave implicit:

* whether the payment **reached the books** (`posted_to_ledger`) — CLAUDE.md
  rule 5, said as a fact rather than implied by the absence of an error;
* what did **not** happen, from the server's own `problems[]` codes: no receipt
  was queued (BR-PAY-024, unbuilt) and the account's cached balance was not
  updated (customers' column, B1). A clerk who expects a receipt to go out needs
  to read that before the customer asks.


## 2026-08-15 — the two unbuilt tabs now have servers (payments visible-half lane)

> ⚠ **THE FIRST PARAGRAPH BELOW IS NO LONGER TRUE, AND IT IS KEPT because the
> five rules under it still are.** Both tabs were WIRED the same day by the
> payments frontend lane — `SummaryTab.tsx` (S32) and `OutstandingsTab.tsx`
> (S34) are the callers, the record forms gained BR-PAY-012's purpose picker,
> and the write-off and collections-run routes have a human path to them. What
> that lane found and left behind is in **§ 2026-08-15 (later)** at the end of
> this file. Read both.

**S32 Summary and S34 Outstandings each have a complete, tested backend and NO
CALLER ON THIS SCREEN.** `PaymentsPage.tsx` still renders the *awaiting* panel
for both tabs. That is hard-won law 2 in its purest form — every figure exists,
every test passes, and a clerk sees nothing — so it is written down here rather
than left for someone to discover.

What to call, and what comes back:

    GET  /api/{tenant}/outstandings?as_of=YYYY-MM-DD
         { as_of, rows[], totals{accounts, owed, dso_days}, ageing[], problems[] }
         rows: account_id · account_no · customer_name · balance (4dp STRING) ·
               days_late · bucket · open_bills · last_payment_on ·
               notice_summary · collection_tier · next_step_due · plan_status ·
               autopay · bad_address
         ageing: one tile per bucket — current | 1-30 | 31-60 | 61-90 | 90+ —
               each { bucket, amount, accounts, share }

    GET  /api/{tenant}/payments/summary?as_of=YYYY-MM-DD
         { as_of, today{amount,count,average}, method_mix[], failed[],
           collections{accounts_owing,total_owed,write_offs_ytd},
           chips{autopay_scheduled,returned_mail}, problems[] }

    GET  /api/{tenant}/autopay-intents[?f.account_id=…]   → { rows[] }
    POST /api/{tenant}/write-offs                          → 201, no money moved
    POST /api/{tenant}/write-offs/{id}/approve             → posts DR/CR
    POST /api/{tenant}/collections/run                     → the S34 bulk action

**Five rules for whoever builds these tabs:**

1. **`as_of` is REQUIRED on both reads.** The API deliberately holds no clock
   (a test asserts the source contains none), because a business day belongs to
   the utility and the tenant timezone cannot be chosen yet (OQ-153 / DEF-082).
   Send the browser's date, exactly as the Record form pre-fills its posting
   date.
2. **Money arrives at FOUR decimals and shows at TWO.** Use `MoneyCell`. Nothing
   on this screen formats money itself.
3. **`average` and `share` and `dso_days` can be `null`, and null is not zero.**
   A day with no payments has no average; a bucket in an empty ledger has no
   share; DSO is BR-REP-011's and reports own it. Render the A18 zero-state
   sentence, never `$0.00`.
4. **Render `problems[]`.** Both bodies carry them and each names something the
   product genuinely cannot answer yet — an unpaid bill with no due date, the
   medical-hold column, the DSO tile. A screen that drops them is the comment
   that claims a guarantee (hard-won law 1).
5. **There is NO autopay retry and no charge action anywhere** (BR-PAY-015). The
   prototype's *Retry autopay* is superseded; the Failed panel routes to a fresh
   recording or to the account.

---

## 2026-08-15 (later) — the tabs are wired (payments FRONTEND visible-half lane)

Every route the section above lists now has a caller, and the two record forms
send BR-PAY-012's purpose. What follows is what the next agent needs and cannot
get from the code alone.

| File | Screen | Story |
|---|---|---|
| `SummaryTab.tsx` | S32 · Summary | US-PAY-005 |
| `OutstandingsTab.tsx` | S34 · Outstandings | US-PAY-013 |
| `OutstandingsTab.tsx` → `WriteOffModal` · `WriteOffResultPanel` | S35 · Write off | US-PAY-012 |
| `OutstandingsTab.tsx` → `CollectionsRunPanel` | S34 bulk | US-PAY-014 |
| `PaymentsPage.tsx` → `RecordPaymentModal` (purpose) | S33 · S35 | US-PAY-002 |
| `customers/AccountActions.tsx` → `RecordPaymentModal` (purpose) | S22 | US-PAY-002 |

### THREE THINGS THE SERVER OWES THESE SCREENS

1. ⚠ **`GET /outstandings` AND `GET /payments/summary` SERVE MONEY WITH NO
   CURRENCY CODE.** Every amount on both bodies — balances, ageing tiles, the
   day's takings, the method mix, write-offs YTD — is a bare 4dp decimal string
   with no CHAR(3) beside it, and `MoneyCell` cannot render one without the
   other (CLAUDE.md rule 2). The screens read the tenant's code off
   `GET /payments` (`totals.currency`, else a row's `currency`) under
   BR-TEN-042's one-currency lock, and render **a stated absence** when the
   tenant has taken no payment at all. **Assuming `USD` was refused**: it prints
   a wrong symbol on a Canadian tenant's books, which is the reasoning
   `endpoints.ts` already records for `RevenueArResponse.currency`. *The fix is
   a `currency` member on both bodies.* It also costs a whole `GET /payments`
   request on two tabs that otherwise need none.
2. ⚠ **THERE IS NO `GET /write-offs` AT ALL** — `apps/payments/api.py` declares
   the collection route POST-only. BR-PAY-020 puts APPROVAL in Finance (S36) and
   **no screen can list what is waiting**, because the only write-off ids a
   browser holds are the ones it has just created. So the Approve control sits
   beside the request on S34, and S36 renders a panel saying the queue cannot be
   listed (`finance.writeOffs.noQueue`). A list route turns that panel into the
   real queue with no other change.
3. **`POST /collections/run` has no scheduled caller** and says so on every
   response (`no_scheduled_caller`). The S34 bulk action is the ONLY thing that
   advances the ladder on this deployment. That is rendered, not hidden.

### FIVE THINGS THAT ARE DELIBERATE AND WILL LOOK WRONG

* **The selected total on S34 is summed IN THE BROWSER.** No endpoint totals a
  selection and US-PAY-013 TC-4 asks for the figure, so `sumDecimalStrings`
  (paymentsShared) adds the 4dp strings **as BigInt on the NUMERIC(18,6) grid** —
  never a float, never a re-round — and hands a decimal string to `MoneyCell`.
  It returns `null` rather than skipping a value it cannot parse. The S32
  method-mix tie-out ("Σ = 100%") uses the same function on the served shares,
  so a month whose rounded shares add to 99.9 **shows 99.9**.
* **`as_of` is a visible field on both tabs**, pre-filled with the browser's day
  and never sent implicitly. That is rule 1 above taken literally.
* **S34 has NO per-row action menu.** The prototype's row select offers Send
  disconnect / Payment plan / Record payment / Write off; two have no endpoint,
  one is another story's wizard, and the fourth is on the bulk toolbar. Four of
  the six BULK actions render DISABLED with their reason (BR-SHL-025) rather
  than being hidden.
* **A write-off is one request PER ACCOUNT**, in a loop, at each account's own
  balance — `writeoffs.py` says why: one row spanning four accounts could not
  post four balanced entries or close four plans (US-PAY-012 TC-3).
* **The prototype's write-off GL picker (6100 / 6110) is not offered.** The
  posting picks finance's designated bad-debt account through the ledger seam;
  a picker here would let a clerk post bad debt where finance did not designate
  it. *"Send to collections agency"* and *"flag for a future deposit"* are not
  offered either — no ratified rule (field-map P-4/P-5), and the `reason` column
  carries a CHECK constraint that refuses the first outright.

### THREE CATALOGUE KEYS WERE DELETED, and each had become a lie

`payments.form.purposeNote` said the other three purposes were refused by name —
`apps/payments/purposes.py` built all three. `payments.arrives.summary` and
`payments.arrives.outstandings` described tabs that are now built. A dead key is
dead weight translated eleven times (G18 direction A), and a key whose sentence
is false is worse than dead.

### WHAT IS STILL NOT BUILT ON THESE TWO TABS

Reminders and disconnect notices (US-PAY-015 — no endpoint), the payment-plan
wizard (US-PAY-017), the field visit (no ratified rule at all), the CSV export
of either tab (`POST /exports` registers neither resource, BR-SHL-010), the
S34 class filter and free-text search (the endpoint accepts neither — it takes
`f.bucket` and `f.bad_address` only), and `GET /autopay-intents`, which is
served with no caller because the S32 chip is a COUNT that rides on the summary.

---

## 2026-09-01 — the bounce and the refund (CR-059 tasks 16 and 18)

Two screens, and both of them had a **finished, tested engine behind a door that
opened the day before**. Hard-won law 2 for the sixth and seventh time in this
module.

### S33 · S21 — Reverse a payment (P2, CS-5)

`reverse_payment` had been complete since 2026-08-11 and **twenty-one live
payment endpoints reached none of it**; `POST /payments/{id}/reverse` landed on
2026-09-01 (task 15) and this is its caller.

The row action lives on **`PaymentsTable`**, not on the page, and that is
deliberate: `AccountDetailPage` embeds the same table scoped by `f.account_id`,
so **S33 and the account's Payments tab get the control from one implementation**
rather than from two that can drift on a money path.

Four things this screen refuses to do, each for a rule:

* **It does not hide Reverse from a Billing Clerk.** `BR-PAY-1070` makes
  reversing Admin-only in the SERVICE, so the clerk who takes the cheque cannot
  record its return — and BR-SHL-025 says a control that cannot act renders
  **disabled with its reason**, never missing.
* **It does not offer a reason picker.** `reversal.SUPPORTED_REASONS` is
  `(nsf,)` and the other three of BR-PAY-011's four are refused by name until
  CS-31 lands. One option in a select is a control that teaches nothing and
  grows a second option the day somebody forgets why.
* **It does not draw the locked-batch refusal CS-5 asks for.** `OQ-134` closed
  on 2026-08-12: a bounce inside a reconciled batch is lawful. A test asserts the
  sentence and the batch code appear nowhere on the modal.
* **It does not print a bill's id.** `reopened[]` carries `invoice_id` and no
  number, so each re-opened bill is matched back to the row's own `applied_to`
  and an unmatchable one states the absence (B14 rule 31).

`PE-7`, on the screen: a **292.87** cheque comes back, the reversing row is
**−292.87**, and **292.87** goes back on BL-2607-018311 (**45.00**) and
BL-2608-018410 (**247.87**). The customer's **30.00** returned-cheque fee is
billing's charge code and every result says it was not added.

### S58 — Refunds (P3, CS-6 · CS-7)

`/finance/refunds`, an **eighth Finance tab**, on the write-off queue's
precedent: `BR-PAY-014` puts money going OUT in the Finance area exactly as
`BR-PAY-020` does for write-offs, and the prototype draws no refunds screen
anywhere.

**The whole lifecycle had no frontend caller of any kind.** The approval queue
`GET /refunds` has been mounted since 2026-08-28 and **could never have held a
row**, because nothing in the product could RAISE a refund — only the demo
seeder called `request_refund`.

Five acts, five gates, every one mirrored from the service and never widened:

| Act | Who | What it moves |
|---|---|---|
| Raise | Admin or Clerk | nothing — the row exists so the queue has something to show |
| Approve | Admin | nothing — `BR-PAY-014`'s gate on the money |
| Issue | Admin | **DR 2400 / CR 1000. This is where the money leaves.** |
| Mark cleared | Admin or Executive | nothing — *a bank fact, not an approval* |
| Void | Admin | a reversing posting; the credit comes back by exactly what left |

⚠ **THE CREDIT FIGURE IS NEVER CACHED BETWEEN TWO ACTS.** Every step answers with
`credit_position_after` computed inside its own transaction and the screen renders
that and keeps none — CS-6's own *watch for*: *a credit real on Tuesday can be
gone by Thursday, and the money moves on Thursday.*

`PE-9`, on the screen: **57.13** raised against an account as cheque **#10241**,
approved, issued, credit to **0.00**; clearing five days later posts nothing.

**What it cannot say, and does not guess — `DEF-2392`.** No route publishes an
account's credit position (it reaches the wire only as `credit_position_after`,
after the fact), and `selectors.refund_row` carries a `payment_id` and no
account — which may not be printed. So the refundable figure is shown AFTER each
act rather than before the amount, the cheque number identifies a queue row, and
the screen states the gap. *"Built from 40.00 (June) + 17.13 (July)"* is CS-7
(task 60, contracts) and is why the raise form still collects the payment behind
the credit.

### And one panel that had to go first — `DEF-3030`

S33 rendered a live panel in eleven languages saying that reversing a payment and
issuing a refund *"are not built"* and that two decisions the PO *"has not made
yet"* were open. All three clauses were false; both doors had landed and both
questions were ruled on 11 and 12 August. It would have sat on the same page as
the Reverse control above it. Deleted, in all eleven catalogues, and the
developer-facing twin in `api/endpoints.ts` corrected rather than deleted.

**The shape is the lesson, not the sentences:** an absence claim that names no
route rots silently every time a backend lane opens a door, and no gate in this
repo reads rendered output. The two panels left on that tab each name what they
wait for.
