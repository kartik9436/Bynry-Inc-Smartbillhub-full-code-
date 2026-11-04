# CR-094-BRC01 · lane H — the counter application fee posts to payments, the ledger and the finance books

**Date** 2026-09-15 · **Branch** `claude/gifted-johnson-top7zn` · **Kind of work** 🔒 money path
(ledger posting · money rounding · a cross-module money flow) · **Status** HUMAN-REVIEW-PENDING

---

## 1 · The commitment, quoted

`12-governance/02-decision-log.md`, the row of 2026-09-15 beginning *"RULED: THE COUNTER FEE
POSTS."* The PO was shown **Sarah Miller paying $25.00 cash at the counter on 12 May against
receipt `RCP-26-4471`**, and a four-row table proving that the money sat on the service-request
row and appeared in **payments: nothing · ledger: nothing · finance screens: nothing**.

> *"payemnt should show in payments, in ledge and in fiannce books"*
>
> *"when it is approved you can attached it to account - if it is refuse then it is application
> fees non refundable - it stya in books"*
>
> *"if it is ask more then it stays in all 3 places in payment, in ledger and in finance"*

And, earlier the same day, on the counter form:

> *"we need to allow to take payment detials, card detial scheck details here curerntly is is not
> taking inputs"*

## 2 · The pages read AS IMAGES, and at what scale

B14 rule 42 — a screen is built from the drawing as an image; extracted text is an index, never
the specification. Two pages, both already rendered at **scale 2** in
`…/scratchpad/acct/`:

| Page | Read with | What it settled for this lane |
|---|---|---|
| `p079.png` | the Read tool, scale 2 | Step 5 `Taking the money` entire: the quote table, `Fee timing`, `Method` (Cash · Card · Cheque), `Amount taken`, `Receipt number`, the `Payment summary` and its signed `Outstanding`. The red note *"This takes money and posts nothing. No journal line, no invoice, no account — there is no account yet."* And the sentence that became the idempotency rule: *"Collecting twice is refused by name. The same receipt number again answers with what is already recorded; a DIFFERENT one on a request that has already been collected is refused and names the receipt it already holds."* |
| `p085.png` | the Read tool, scale 2 | The Refuse modal — *"The $25.00 already collected stays collected"*, and the red panel *"Refusing does not undo the money … holding `$25.00` that may have to be given back — both visible, because a refusal that silently wrote off a receipt is how a cash drawer stops reconciling."* And the Ask-for-more dialog: *"It stays open and stops waiting on you"*, *"The request becomes More info — open, not refused"*. |

No higher scale was needed; every figure and every sentence above was legible at 2.

## 3 · What was superseded, stated rather than assumed

**p079's red note — HALF reversed, HALF still binding and still enforced.**
*Posts nothing* is reversed by the ruling. **No invoice and no customer account** survives: there
is genuinely neither at capture and nothing in this lane creates one. A balanced pair needs
neither.

**p085's hedge — WITHDRAWN.** *"holding `$25.00` that may have to be given back"*. It does not
have to be given back; the application fee is non-refundable. The same panel's other half is the
reasoning this lane acts on and it stands.

**The ruling row's own `1000 Cash` — AMENDED BY THIS LANE, and the ruling row is stamped in
place rather than edited away.** See §5.

## 4 · Before and after

| | Before (branch tip `f34f71ee`) | After |
|---|---|---|
| `collect_fee($25.00, cash, RCP-26-4471)` | Writes six columns on `service_requests`. Its own docstring said *"Nothing posts to the ledger either."* | Writes the same six columns **and** one `counter_receipts` row **and** one balanced journal entry, in the same transaction |
| The $25.00 in the ledger | absent | `DR 1010 Undeposited funds 25.0000 · CR 2400 Customer credit balances 25.0000` |
| The $25.00 in payments | absent | `GET /counter-receipts`, with a `held` total that should agree with `2400` |
| Refusing the request | The money stayed on the request row and nowhere else | `DR 2400 25.0000 · CR the charge code's revenue account 25.0000`; `1010` still holds the cash; `2400` nets to zero |
| Approving the request | ditto | the identical pair |
| Ask for more | ditto | **nothing** — no entry made, none reversed |
| Card detail at the counter | not captured at all | `card_last4`, `card_brand`, `card_auth_code`. **Never the card number** |
| Cheque detail at the counter | not captured at all | `cheque_no`, `drawer_bank`, `cheque_date` |

## 5 · The three judgments, and where each is recorded

Each has its own row in `12-governance/02-decision-log.md` dated 2026-09-15, written **before** the
code that depends on it (step W).

**(a) The receipt is a `counter_receipts` row in payments, not a `Payment` with a blank account.**
Measured first: `apps/payments` reads `account_id` in **161 places across 40 files**, 27 of them
`select_related`/`values` clauses that would start yielding a `None` nobody has branched for; 6
more reads of a payment's account live in billing, ledger, customers and portal. It is a reviewed
cross-module FK under B2 §2 and widening it is a one-way door. The shape chosen is already in
payments one table along — `payment_import_rows`, money that has arrived and cannot yet be
attached, with a `commit_error` column for exactly the reason `release_error` exists here.

**(b) The collection debits the tender's clearing account, else `1010 Undeposited funds` — not
`1000 Cash`.** The PO named no account this morning; `1000` was the ruling row's rendering. It
collides with the PO's own ruling of **2026-08-11 closing `OQ-143`**: *"Cash is received but
undeposted in such case payment will say csah but ledger will say undeposited - until bank record
and reconcilaition confirm it it is not realised."* It is also the tenant's own configuration —
all seven of Brazos Bend's payment methods point `clearing_gl_account_id` at `1010`. And it is
arithmetic: the receipt becomes a `Payment` when an account exists, a deposit batch cut afterwards
posts `DR 1000 / CR 1010` for its members, and debiting `1000` at collection would credit `1010`
for money it never held — cash counted twice, with both sides of the trial balance still footing.
**The 2026-09-15 ruling row is stamped in place with a dated ⚠ pointer**; its wrong sentence is
left visible, because it has been read and cited.

**(c) The release is what was collected, capped at what was quoted.** `4xxx` is money earned;
`2400` is money held. $30.00 handed over against a $25.00 application fee earns **$25.0000** and
leaves **$5.0000** a liability, visible on the trial balance and on the row as `held_remaining`.
Earning it would be the mirror of the defect p085 warns about.

## 6 · What was published, with its worked example

**`POST /service-requests/{id}/fee-collection`** — two new optional objects. A body that sends
neither behaves exactly as it did yesterday.

```json
{
  "amount": "25.00",
  "method": "cash",
  "receipt_no": "RCP-26-4471",
  "card":   {"last4": "4242", "brand": "visa", "auth_code": "A19422"},
  "cheque": {"number": "10241", "bank": "First National", "date": "2026-05-12"}
}
```

`_tender_detail` is an **allow list, not a pass-through**: a client sending
`{"number": "4242424242424242"}` under `card` has it dropped at the boundary rather than stored.

**`fee_total_to_collect(request_id)["counter_receipt"]`** — the read-back, served from payments:

```json
{
  "id": "01a0…", "source_ref": "SR-26-0048", "receipt_no": "RCP-26-4471",
  "amount": "25.0000", "currency": "USD", "method": "cash", "method_name": "Cash",
  "card_last4": null, "card_brand": null, "card_auth_code": null,
  "cheque_no": null, "drawer_bank": null, "cheque_date": null,
  "taken_at": "2026-05-12T10:30:00+00:00",
  "state": "held", "collection_entry_id": "01a0…",
  "released_at": null, "earned_amount": null, "held_remaining": "25.0000",
  "revenue_postings": [], "release_entry_id": null, "release_error": null,
  "payment_id": null
}
```

Money is a **string at four places**; display rounds to two and that is `MoneyCell`'s job
(hard rule 2). `source_ref` and `receipt_no` are what a screen renders — B14 rule 31, no database
id is ever a visible value.

**`GET /counter-receipts?f.state=held`** — paginated (`NFR-3`), ordered by when the money was
taken, with `totals: {taken, held, currency, count}` and `states` alongside the DRF envelope.

## 7 · The proof

| Check | Result |
|---|---|
| `pytest tests/test_cr094_counter_receipt_posts.py --reuse-db` (sqlite) | **16 passed, 3 skipped** — the three skips are the `requires_postgres` cases: the law-14 savepoint, the RLS scoping and the freeze trigger, none of which EXISTS on sqlite |
| The same file on **real PostgreSQL** (`DJANGO_SETTINGS_MODULE=config.settings.local`, its own `test_sbh_laneh_…` database, never the shared one) | **19 passed, nothing skipped** — the only run in which the savepoint, the RLS policy and the freeze trigger exist at all |
| The tie-out, by account CODE and figure | collection `DR 1010 25.0000 / CR 2400 25.0000`, debits = credits; refusal `DR 2400 25.0000 / CR 4600 25.0000`; afterwards `1010` still holds **25.0000**, `2400` nets to **0.0000**, revenue **−25.0000** |
| Over-collection | $30.00 taken against a $25.00 quote → earned **25.0000**, `held_remaining` **5.0000**, `2400` still **−5.0000** |
| Replay (hard rule 6), both guards **separately** | the same receipt again through `collect_fee`: one row, one entry. Payments' own guard called directly: one row, one entry. A different receipt number: refused, naming the one it holds |
| Ask for more | one entry (the collection), state still `held`, `2400` still carrying 25.0000 |
| Tenant isolation (PostgreSQL, through the NON-superuser probe role) | another tenant sees **none** of these rows, and `assert_no_foreign_rows_anywhere` finds none anywhere. A plain ORM query inside `tenant_ctx` runs as the superuser and bypasses RLS, so an assertion made that way would be vacuous |
| The freeze trigger (PostgreSQL) | rewriting `amount` or `receipt_no` is refused naming hard rule 4; `DELETE` is refused naming *"never deleted"*; and the nine release columns still move, so the guard is not a wall |
| Regression | `test_cr031_service_request.py`, `…_api.py`, `test_cr094_service_request_messages.py`, `test_cr094_approval_raises_the_job.py`, `test_us_cwp_050_fees.py`, `test_us_pay_001_record_payment.py` — **157 passed, 5 failed, 5 skipped**; all five failures dated to another lane, see §9 |
| Gates (`run_gates.py --changed`) | 126 verdicts, 50 red. **Not one finding names a file this lane authored.** `G119` did name `service_request_service.py` and is fixed — §9 |
| `ruff` · `black` | clean on every file this lane authored. The SHARED files were already not black-clean at the tip, so only this lane's own new files were formatted: reformatting a shared file would publish a whole-file diff over three live lanes |

**Every guard proved RED first, in pytest, one break at a time** — the six failures
are quoted verbatim in the test file's own docstring.

⚠ **TWO OF THE SIX PASSED THE FIRST TIME THEY WERE BROKEN, AND THAT IS THE PART
WORTH READING.** Law 7's second habit is not hypothetical:

* Deleting `release_counter_receipt`'s `state != HELD` early return left
  `test_a_second_terminal_outcome_posts_nothing` **green**, because the LEDGER's
  posting key refuses the second entry — so the entry COUNT never moves. The
  count was measuring the ledger's guard while claiming to measure the service's.
  What the early return protects is the ROW: without it a second refusal rewrites
  `released_at` to today and the books say the $25.00 was earned on a date no
  entry was made. The assertion is now the DATE, and it goes red.
* Deleting payments' replay branch left `test_a_replayed_collection_posts_once`
  **green**, because that case goes through `collect_fee`, which has an
  idempotency guard of its own on `service_requests.fee_receipt_no` and returns
  before payments is reached. `DEF-058` is exactly this — one guard silently
  standing in for another — so the two are asserted separately now and
  `test_payments_own_replay_guard_holds_when_called_directly` calls payments
  directly. Broken, it fails with the UNIQUE constraint.

## 8 · What was NOT built, and why

* **The attach to an account — `DEF-PAY-5394`.** `approve()` raises WORK and opens no account;
  `customers.Account` carries no link back to a request. `payments.counter_receipts.
  attach_to_account` exists and is tested, and **has no production caller**, which is reported
  rather than counted as built (hard-won law 2). The MONEY half of the ruling is complete without
  it.
* **A finance SCREEN for the counter takings.** `GET /counter-receipts` serves the rows and no
  page mounts it yet. The ledger half of *"in ledge and in fiannce books"* needs no new screen —
  the entry is on the journal, the trial balance and the GL detail for `1010` and `2400` the
  minute it is taken.
* **`CC-REQFEE` as a real charge code.** It is in the sample fixture and in **no tenant's**
  catalogue — Brazos Bend holds 28 codes and that is not one of them. Seeding it and pointing it
  at an account is the tenant's act and CR-066's table is the PO's. Reported, not filled.
* **The capture screen's card and cheque controls** — lane D owns `ServiceRequestCapturePage.tsx`
  this wave and builds to §6 above.

## 9 · Reds this lane did not cause, each dated

**Five regression failures, all in the identity-columns lane's territory.**
`test_br_cus_092_the_ssn_is_captured_and_the_rest_stay_refused`,
`test_us_cus_024_tc9_an_identifier_field_is_refused_by_name`,
`test_the_detail_states_what_it_cannot_answer`, and the two list-ordering cases.
Dated with `git log -S`: `24bcc674`, 2026-09-15, *"The date of birth and the
driving licence are captured on a service request"* — the applicant tab's payload
and the `SERVICE_REQUEST_UNAVAILABLE` list both moved and those tests did not.
Nothing this lane touched is in any of the failing assertions.

**`G119` shadowed-definitions — RED on a file this lane edits, and FIXED.**
`_clean_unit_count` was defined **twice** in `service_request_service.py`, at
lines 392 and 434, before this lane's first commit (both counts are 2 at
`62a81b3f`). Two lanes added the identical function on the same day —
`b87b9655` and `e4092d3e`, 2026-09-15 — and the bodies are byte-identical apart
from trailing blank lines, so deleting the first is provably a no-op. Python
binds the LAST definition silently, and the day the two copies stop agreeing is
the day a clerk's unit count is validated by whichever one was pasted second.
Filed as **`DEF-CUS-5408`** against the two commits that caused it; `G119` was
red before and answers `PASS` after, run through `run()` rather than
`__main__` — the path `run_gates` actually uses.

**`openapi/schema.json` was stale at the tip and this lane's regeneration
repairs three other lanes' endpoints with its own.** `billing/print-sets/bills`
(`07d1fb37`, lane J), `premises/picker` and
`service-requests/{id}/approval-preview` all landed today without the export
being re-run. The file is generated from the code, so regenerating publishes the
truth about committed code rather than anybody's in-flight work.

**A tenant-wide row count passed on sqlite and failed on PostgreSQL, and the
reason is worth writing down.** Two replay cases counted `CounterReceipt` rows
for the whole tenant. Under `config.settings.local` the sample-data plant runs
eagerly, and `apps/customers/sample_data.py:2316` calls `collect_fee` itself —
so the demo utility now legitimately carries counter receipts of its own, and
the count was measuring the fixture rather than the guard. Both assertions are
scoped to the SOURCE now. ⚠ **The same fact has a product consequence and it is
intended: seeding the sample utility now writes a counter receipt and posts a
balanced journal entry for its `RCP-26-4471`,** which is the ruling applied to
the demo rather than a side effect of it.

**`makemigrations --check` reports one pending RATING migration that is not
this lane's** — a constraint churn on `discountversion`, dated to `ac3bd496`,
2026-09-10. `payments` reports none, which is what proves `0027` covers the new
model completely.
