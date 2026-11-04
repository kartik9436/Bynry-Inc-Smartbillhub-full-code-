# CR-180-BRC10: Fix a bill, revamped (One customer / Bulk, one "What was wrong" table, the bill by rate type)

**Raised:** 2026-10-12 by the Product Owner, in chat. Verbatim: *"Now we need to revamp bill correction"*, *"we need ot make it user friendly for user to do fix a bill"*.
**Confirmed:** *"all your task are correct"*, then *"please start fixing the changes create a CR if required ; during end to end walk if any bug arises please fix it"* (2026-10-12).
**Status:** **BUILT — RELEASED in 2.573.0 (2026-10-13).** Walked J-FIX-TWENTY: 19 of 20 scenarios, 22 defects fixed. **Bulk speed, `DEF-BIL-10091`, is FIXED (2026-10-13, not yet released):** bulk preview, Send and approve-and-issue run as background jobs with progress on screen (48 bills: 190 s → 19.5 s to work out, 195 s → 32.9 s to issue; each request answers in under 0.1 s). See the decision log, *BULK FIX A BILL RUNS IN THE BACKGROUND*.
**Branch:** `claude/serene-noether-71ie5b` (`BRC10`). `allocate.py cr` answered **180**.
**Classification (`13-change-process.md` §1):** a **CHANGE**. A live screen is redrawn end to end (maintenance's redesign case) **and** gains things no user can do today:
- several bills of one account in one case;
- a price mistake across runs;
- several corrections in one case;
- choosing the plan and version;
- a typed reading, deposit, discount and reprint values;
- saving at Send rather than at step 1.

**Drawing:** `05-prototype/fix-a-bill-2026-10-12/`, 23 images plus the mock-up HTML. **Build from the images (B14 rules 41/42/44).**
**Every PO instruction behind the shape:** decision log 2026-10-12, *FIX A BILL REVAMP*, items 1–12.
**End-to-end walk:** `08-qa/01-e2e/journeys/J-FIX-TWENTY-the-fix-a-bill-scenario-suite.md`, 20 scenarios with record checks.

## What is being reversed or superseded (step 2)
- **The step labels** *What and why · The correction · What it changes · Generate and send* (Billing blueprint §06, p129–p144) become **Bills · Fix · Check · Send**. The count stays at four.
- **The six scope kinds** (`single · date_range · run · cycle · plan · service`) become **One customer** (one bill · several months) and **Bulk** (a billing run · a price mistake). Plan and service survive only as a filter inside a run.
- **A reason picked from 18 tick boxes** becomes one table of correction rows. *What happens* is still derived, by the signed `BR-BIL-041` / `BR-BIL-042` (R > C > D), now across all rows.
- **The case is opened at step 1's Continue** becomes **opened at Send**. Steps 1–3 write nothing (`BR-BIL-014`: no money-bearing write before approval).
- **A ❄️ FROZEN B4/B5 figure is not touched.** No golden figure may move.

## The tasks (confirmed)

| # | Area | Task |
|---|---|---|
| F1–F2 | Screen | Bills step: two option cards, a sub-option dropdown, a searchable account box + account card, a bill list (radio / tick boxes) with totals, bulk run picker + "Only part of it", price mistake From–To + what was wrong, can't-be-corrected list |
| F3 | Screen | Fix step: ONE "What was wrong" table. Columns: what was wrong · item · billed · should be · apply to · bin icon. Plus Add a correction, the derived *What happens*, and Not done here |
| F4 | Screen | Old bill / new bill side by side, by service and rate type, then charge codes, discounts, deposits, taxes per authority and total; month tabs |
| F5–F6 | Screen | Bulk per-bill table with up/down apart; *What changes on the page* for reprint rows |
| F7 | Screen | Check: for the customer; existing bills; for finance (closed for the clerk, open for the approver) |
| F8 | Screen | Send: tick, Send for approval, waiting, Approve and issue, result |
| F9–F10 | Screen | Retire the old FixABillTab pieces; all strings in 11 catalogues |
| B1 | Server | One account's several bills in one case |
| B2 | Server | Price mistake scope: bills that used a rate / tax / charge code between two dates, across runs |
| B3 | Server | New table `correction_case_items`: one row per correction |
| B4 | Server | Re-price from the rows. Plan/version, schedule/version, tax rate, charge add/remove, discount add/remove, deposit, period dates/services, assessed usage, goodwill on the corrected bill. 🔒 rating math: HUMAN-REVIEW-PENDING |
| B5 | Server | Typed reading saved to Meter Reads and priced (as the one-time bill, 2.570.0) |
| B6 | Server | Reprint fields: field · was · becomes, reissued |
| B7 | Server | `POST /corrections/preview` writes nothing; the case is opened at Send |
| B8 | Server | Posting month per bill (closed → earliest open) and the new due date, served |
| B9 | Server | Approver served by name |
| B10 | Server | Approve and issue as one act |
| T1–T4 | Tests | Server cases red→green; money on PostgreSQL; screen tests; gates |
| E1–E5 | Walk | J-FIX-TWENTY (20 scenarios), with record checks on bills, ledger, delivery rows, payments, meter reads, audit |

## The contract between server and screen (written before either is built)

All routes sit under the tenant API prefix. Money is a decimal STRING; display is 2 places, unit prices up to 4.

**1. `GET /corrections/resolve`**: the bills a scope covers (exists; widened).
- `scope_kind=account`: `account_id` and repeated `invoice_ids` (one or many of that account's bills) **[NEW]**
- `scope_kind=run`: `bill_run_id`, optional `service_code` or `plan_id` (exists)
- `scope_kind=price_mistake`: `period_start`, `period_end`, `wrong_kind` (`rate` | `tax` | `charge`), `wrong_id` **[NEW]**

It answers the paged rows plus `totals` and `excluded[]` (drafts; bills already in an open case), as today.

**2. `POST /corrections/preview` [NEW — writes NOTHING]**

Body: `{ scope: {…as above…}, items: [ITEM, …] }`

ITEM: `{ reason, item, act?, value?, value2?, bill_ids: [..] | null }`. `bill_ids: null` means every bill in the scope.

| reason | item | act | value / value2 |
|---|---|---|---|
| `wrong_read` | meter (asset) id | — | correct reading |
| `theft_restated` | meter id | — | assessed usage |
| `wrong_plan` | plan id | — | plan version id |
| `wrong_rate` | rate schedule id | — | schedule version id |
| `wrong_tax` | tax authority code | — | rate % (string) |
| `missed_charge` | charge code | — | quantity |
| `charge_billed_in_error` | bill line key | — | — |
| `wrong_discount` | discount programme id | `add` \| `remove` | — |
| `wrong_deposit` | `DEP` | — | amount |
| `wrong_period_or_service` | `dates` or a service code | — | start / end date |
| `goodwill` | `credit` | — | amount |
| `customer_name`, `service_or_mailing_address`, `premises_or_unit_label`, `meter_number_or_read_dates`, `template_or_language` | the field | — | new value |

It answers:
- `correction_class` (`restatement` \| `credit_only` \| `document`), derived R > C > D;
- for one customer, per bill: the nine sections of `BR-BIL-044` (the lines grouped by service with `rate_type`, `qty`, `unit_price`, `amount`, plus charge codes, discounts, deposits, `tax_by_authority`), `posting_period`, `new_due_date`;
- for bulk, the aggregate with up and down apart, plus per-bill rows;
- `page_changes[]` for reprint items;
- `preview_hash`.

Refusals are by `message_key`: a draft, an open case, a reason not allowed for the scope, the back-bill window, a closed-period rule.

**3. `POST /corrections`**: opens the case at **Send**. Same body plus `preview_hash`. It refuses if the figures moved (`BR-BIL-044`), stores `correction_case_items`, and leaves status `pending_approval`.

**4. `POST /corrections/{id}/approve-and-issue` [NEW]**: approve plus execute in one act, for an approver.
- Execute per bill: credit note + new bill (`corrects_invoice_id`), two journal entries, the payments re-allocation plan executed by payments (new allocation rows), delivery rows queued (paper plus elected channels), audit rows.
- The answer reports per-bill `succeeded` / `failed` / `skipped_already_done`.

`/approve`, `/execute` and `/abandon` stay as they are. `the_gate.approved_by_name` and `initiated_by_name` are served by name **[NEW]**.

### Contract additions by the SCREEN lane (2026-10-12, written before the screen was built)

The drawing needs these facts and the four routes above did not name them. Field names are exact; the fixtures in `07-frontend/src/features/billing/fixABill/__fixtures__/` are shaped by them.

**A1. `GET /corrections/resolve`, widened further.**
- `scope_kind=account` takes `account_id` alone: no `invoice_ids` means every correctable bill of that account (the *Pick the bill* list). With `invoice_ids`, only those (the picked total).
- Each row adds `account_no` and `customer_name` (the bulk *Bills it covers* columns).
- `totals` adds `accounts` (*48 bills · 48 accounts*).
- `excluded[]`: `{ invoice_id, invoice_no | null, period_start, period_end, code }`, where `code` is `draft` or `open_case`. It feeds *Left out* and *"Nov 2026 is a draft"*.

**A2. `GET /corrections/options` [NEW, writes nothing].** It lists what the *What was wrong* row selects offer. It takes the same scope parameters as `resolve`; without them it answers only the tenant-wide lists.
```
{ plans:          [{ id, name, versions: [{ id, label, effective_from }] }],
  rate_schedules: [{ id, name, service_code, versions: [{ id, label, effective_from }] }],
  taxes:          [{ code, name, rate }],          // rate: a percent string, "2.000000"
  charge_codes:   [{ code, name, amount | null }], // base charges excluded
  discounts:      [{ id, name, version_label }],
  price_targets:  [{ kind: "rate"|"tax"|"charge", id, label }],   // the Bills step's price-mistake list
  // only with a scope:
  meters:         [{ asset_id, label, service_code, unit, billed_reading | null }],
  bill_lines:     [{ key, label }],                // what "a charge was billed in error" can remove
  billed: { plan_id | null, plan_version_id | null, tax_rates: { <code>: rate },
            deposit | null, fields: { <reprint reason>: current value | null } } | null }
```

**A3. `POST /corrections/preview` answer, in full.** Body adds `as_of`, plus optional `page` and `per`, which page `bills` for bulk (NFR-3).
```
{ correction_class: "restatement"|"credit_only"|"document"|null,   // null while items is empty
  scope_kind, currency, count, accounts,
  bills: [{ invoice_id, invoice_no, account_id, account_no, customer_name, period_start, period_end,
            was: DOC | null, becomes: DOC | null,       // documents for one customer; null on bulk rows
            credit_note: { lines: [{ key, label, amount }], total } | null,
            was_total, becomes_total, delta, paid | null, moves_to_new_bill | null, still_owed | null,
            posting_period | null /* "2026-10" */, new_due_date | null }],
  totals: { was, becomes, net, up: { count, amount }, down: { count, amount }, unchanged },
  customer: { name, account_no, owes_before, owes_after, refund | null,
              credit_notes, new_bills, reprints, channels: ["post"|"email"|"portal"], new_due_date | null } | null,
  bulk:     { credit_notes, new_bills, reprints, refunds | null, payments_moved, channels } | null,
  finance:  { entries: [{ entry: "credit_notes"|"new_bills", amount }],
              net, accounts: [{ code, name, change }], closed_through | null, earliest_open | null },
  page_changes: [{ field: <reprint reason>, was | null, becomes }],
  approver: { role_name, user_name | null },
  preview_hash, problems: [{ code, message_key, detail }] }

DOC = { invoice_no | null, plan_name | null, plan_version | null, currency,
        sections: [{ key, kind: "service"|"charges"|"discounts"|"deposits",
                     service_code | null, rate_type | null, total,
                     lines: [{ key, label, qty | null, unit | null, unit_price | null,
                               base | null, percent | null, amount }] }],
        subtotal, taxes: [{ key, label, rate, base, amount }], tax_total, total }
```
- A line `key` is stable across `was` and `becomes` (`water.tier2`, `charge.MTEST`, `tax.STATE`), so the screen lines the two sides up by key. A line on one side only shows as "—" on the other.
- `rate_type` is a code: `flat` · `tiered` · `seasonal` · `tou` · `tou_demand` · `demand` · `percent_of` · `flat_per_unit`.
- `qty`, `unit_price`, `base` and `percent` are decimal strings, and the screen formats them. `unit_price` shows up to 4 places (hard rule 2).

**A4. `POST /corrections` (at Send).** Body `{ scope, items, preview_hash, as_of }`. The case detail it answers, and `GET /corrections/{id}`, add:
- `items` (as sent);
- `preview` (the A3 answer the hash binds);
- `approval: { role_name, approver_name | null, initiated_by_name | null, sent_on | null, approved_by_name | null }`;
- `viewer_can_approve: boolean`, which the server decides. The screen never compares roles.

**A5. `POST /corrections/{id}/approve-and-issue`.** Body `{ preview_hash, on_date, issued_at }`. The answer is the case detail with `result`. Each `bills_detail` row adds `invoice_no`, `credit_note_no` and `rebill_invoice_no`, because an id is never shown (B14 rule 31).

**A6. The approver's *Send back*** is `POST /corrections/{id}/abandon` with the approver's reason. It closes the case and the clerk starts again. No new route.

## Version and rollback (step 7–8)
- **Version:** ships as one change bump, recorded at release.
- **Rollback:**
  - The old screen is replaced, not kept behind a flag.
  - The server routes are additive; the old routes keep working.
  - The new table is additive (one forward migration, reversible while empty).
  - No issued bill, credit note or journal entry is altered by this change.

## Server lane — what was built, and where it differs from the contract (2026-10-12)

**Built:** B1–B10 and A1–A5. Proof: `06-backend/tests/test_cr180_fix_a_bill_revamp.py`, 25 cases. They were written first and were RED on the untouched code. They are green on SQLite and on PostgreSQL 16. The last case checks every key the screen's fixtures read.

**Where the server differs from the text above, and why:**
1. **`as_of` is required on `POST /corrections/preview` and `POST /corrections`.** It is the business date for the back-bill window (BR-TEN-043). Billing has no reader for the tenant's today, and a server clock on a money path is refused (G6). A4 already lists it in the body.
2. **`approve-and-issue` also takes `on_date` and `issued_at`, required, exactly as `/execute` does.** A5 already lists them.
3. **`bills[].posting_period` is the month (`2026-10`), as A3 says.** The exact date is served beside it as `posting_date`, and the case's own posting date is kept for BR-BIL-045.
4. **`bills[].delta` on a credit-only bill is minus the goodwill (A3 / `PREVIEW_CREDIT`).** The pinned `impact` keeps the BILL's delta at 0.00. The PO ruled on 2026-08-11 that a goodwill credit does not touch the bill. Both figures are served, and the hash covers the impact.
5. **`excluded[].code` is `draft` or `open_case`, as A1 says.** When a clerk names a bill by hand, four more codes can appear: `already_corrected`, `void_bill`, `not_this_account` and `not_found`. Each is a different fact, so it is stated rather than folded into one of the two.
6. **A tax's `code` in A2 (`taxes[].code`, `billed.tax_rates`) is the tax's own key, not a short code.** `rating.taxes` has no code column, only a name. The screen sends that key back as the *wrong tax* row's `item`. It is a select value, never shown (B14 rule 31). The DOC key is `tax.<that key>`.
7. **Goodwill on a re-priced bill is NOT a negative line on the new bill.** It runs the signed concession (DR write-off, CR customer credit, tax excluded). The new bill's issue then draws it down with the released payment. A negative line would be refused at posting (OQ-152 allows a negative bucket only on the discount account), and the ruled account for a concession is write-off, not revenue. The preview shows it as `credit_note.lines[goodwill]`.
8. **`wrong_discount` with act `add` only confirms a discount that now reaches the bill.** The account's enrolment and the plan's binding are the two signed gates (BR-RAT-069/110). A programme the account is not enrolled in is refused by name: *enrol the account first*.
9. **`theft_restated` on a bill cut at a mid-month price change is refused.** Assessing usage per part is not built yet.
10. **`approver.user_name` / `approval.approver_name`** is set only when exactly one person in the tenant holds the approving role. Otherwise it is null.

**Found while building, fixed in this change:**
- A correction could not be posted into a closed month. The ledger refuses a closed date and expects the caller to post forward, but the credit note posted on the bill's service date and the rebill kept the cycle date. Both now post in the earliest open month (BR-BIL-045 / BR-TEN-038). J-FIX-TWENTY S11 depends on this.
- `bulk_corrections._execute_one` passed a `date` where `execute_credit_only` needs a `datetime`. Every class-C case run through the legacy loop raised `AttributeError`. The legacy loop also passes the bill's delta, which is 0.00 for a credit-only bill, as the goodwill amount, so it would refuse anyway. That second fault is NOT fixed here: item cases do not take that path, and the legacy C path is being retired with the old screen.
