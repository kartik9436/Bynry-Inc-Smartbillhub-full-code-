# Portal reuse map — the read the Account details view already has

**PO ruling 2026-09-04, verbatim:** *"all the services that are required for
Consumer portal - you will find it same set of services, endpoints are already
available for Accounts - account details view"* — said in the same hour as
*"We are mainiting last 12 month usage details on account - you canuse it"*.

**This file is the map that ruling implies.** It exists because the principle on
its own did not stop the mistake: a lane concluded `metering` published no
per-account usage read, wrote a careful paragraph explaining why the home tile
would therefore be built from bill lines, and shipped it. The read had existed
since `CR-030` W3, two directories away, under a name the lane did not grep for.
**An absence in one folder was read as an absence in the product.**

⚠ **THE RULE IS STRONGER THAN *DO NOT DUPLICATE*.** A second read of the same
facts is a second ANSWER, and the two surfaces are a clerk and a customer
**arguing with each other on the phone**. The portal's job is the same facts in
a customer's words — never a second arithmetic.

⚠ **THE STAFF SCREEN ALREADY PRACTISES THIS**, and says so in its own words:
`07-frontend/src/features/customers/accountDetailTabs.tsx` records that its
Meters table reads `assets.selectors.assets_on_unit`, *"the same posture the
Bills tab takes with billing's S30 list and the Payments tab with payments'
S33: one implementation of what a meter IS"*. The portal is the third surface
on the same reads, not a fourth implementation.

## The map

`ACC-01` is the staff Account details screen. Each row is one of its tabs, the
read behind it, and the portal screen that must be built on that same read.

| ACC-01 tab | Backend read | Client function | Portal screen |
|---|---|---|---|
| **Usage** | `apps/metering/monthly_usage_reads.usage_payload(account_id, months=12\|24)` · `GET accounts/{id}/usage` | typed inline in `AccountUsageTab.tsx` | `CWP-033` usage (`US-CWP-040`) **and the home tile** (`US-CWP-025`) |
| **Overview** recent bills · **Bills** | `GET invoices?filters[account_id]=` (billing S30 list) · `GET invoices/{id}` | `getInvoices` · `getInvoice` | `CWP-027` bills (shipped) · `CWP-028` one bill (`US-CWP-033`) |
| **Payments** | payments S33 list · `GET accounts/{id}/payments` · `/open-bills` · `/collections` | `getPayments` · `getPaymentsSummary` | `CWP-041` payments (`US-CWP-048`) |
| **Payment plans** | `GET accounts/{id}/payment-plans` · **`/payment-plans/preview`** | `getPaymentPlans` | `CWP-042` ask (`US-CWP-051`) · `CWP-043` the plan (`US-CWP-052`) |
| **Credits / adjustments** | account credit notes | `getAccountCreditNotes` | — (no portal story yet) |
| **Meters** + its nested read log | `assets.selectors.assets_on_unit` · `GET assets/{id}` · `GET assets/{id}/reads` | `getAsset` · `getAssetReads` | `CWP-037` equipment (`US-CWP-043`) · `CWP-034` readings (`US-CWP-041`) |
| **Notes** | `GET accounts/{id}/notes` | `getAccountNotes` | — (`BR-CUS-035`: notes are one of the two tabs customers see; no story yet) |
| ⊕ **the ladder** — `S90` Disconnects, `S21`'s position | `customers.disconnect_reads.chips_for` (WHICH TIER) · `disconnects.ladder_state` · `open_case_for` + `case_payload` · `reconnection_terms` (the fee AND the deposit election) · `protections_for` (three lifetimes) | typed inline in `disconnectsTab` | `CWP-057` arrears (`US-CWP-057`) · `CWP-056` help paying (`US-CWP-058`) · `CWP-064` protections (`US-CWP-059`) |
| ⊕ **refunds** — `S58` | `payments.selectors.refund_row` (the row) · `refund_queue` (tenant-wide) | `getRefunds` (staff) | `CWP-045` money back (`US-CWP-056`) |
| ⊕ **the closing bill** — `S20` move-out settlement | `billing.final_bill.settle_final_bill(invoice)` (the whole settlement: deposit applied FIRST, then exactly one of refund / collect / plan / transfer / write-off, `BR-BIL-013`) · `customers.selectors.deposit_interest_accrued(account_id, as_of)` (❄️ `GT-61`) · `metering` closing read | typed inline in the move-out drawer | `CWP-032` your final bill (`US-CWP-037`) |
| ⊕ **level pay** — `S23` budget billing | `billing.budget_service.effective_level(account_id)` · `AccountBudgetStatus.variance_balance` (a CACHE — `account_budget_events` is the truth, and `recompute_balance` proves them equal) · `account_budget_events` for the year's changes | `getLevelPay` | `CWP-044` what level pay would cost (`US-CWP-054`) · `CWP-066` where it stands (`US-CWP-055`) |
| ⊕ **the price of stopping and starting** | `rating.seams.base_charge_for(...)` (the ONE precedence implementation — `BR-RAT-088`, the charge code owns the base) via `portal/seams/rating_seam.standing_charge_monthly` · `rating_seam.connection_fees` (reconnection) · the deposit election on `reconnection_terms` | `getStopOrRestart` | `CWP-052` stop or restart (`US-CWP-062`) |
| ⊕ **a customer's own service requests** | `customers.selectors` via `portal/seams/customers_seam.my_requests(tenant_id, phones=…)` + `contact_phones` + `documents_still_wanted` | `getRequestHub` | `CWP-046` what do you need (`US-CWP-060`) · `CWP-051` track a request (`US-CWP-063`) |
| **Documents** | ⚠ **NONE — the staff tab is a FRAME.** | — | `CWP-031` documents (`US-CWP-036`) |
| **Adjustments** | ⚠ **NONE — the staff tab is a FRAME.** | — | — |

⚠ **THE TWO FRAMES ARE THE EXCEPTION THAT PROVES THE RULE, AND THEY ARE
DELIBERATE.** `accountDetailTabs.tsx` draws Documents and Adjustments as real
column HEADINGS over one spanning cell carrying a stated absence, and its own
reason is worth quoting because the portal must not undo it: *"An empty
`<tbody>` is not the honest alternative — it asserts 'none', which on an
Adjustments tab reads as 'this account was never adjusted' and on a Documents
tab as 'nothing was ever filed'."* So **`US-CWP-036` genuinely has no read to
reuse** and must build one; that is a finding, not a licence to skip the
search everywhere else.

## How to use this

1. Find your portal screen in the last column. Read the backend read named
   beside it, end to end, including its docstring — several of them answer the
   story's design questions outright.
2. Read the staff screen built on it. The portal version is the **same facts in
   a customer's words**, not a second interpretation and never a second
   arithmetic.
3. Reach it from the portal through a seam in `apps/portal/seams/`, which calls
   the **published** function. A seam never reaches into another module's
   services or tables.
4. If your screen is not on this map, search before concluding there is nothing:
   `06-backend/apps/*/[a-z]*_reads.py` (six read models) and every account-scoped
   route in each module's `api.py`. **Search the OWNING module's side, not the
   caller's** — that is the whole lesson above.
5. If you still find nothing, say so explicitly in your report and name what you
   searched, so somebody can check it.

## What this map does NOT do

**No gate can enforce it.** A read written twice is two pieces of correct,
tested, green code — nothing in this repo can see the duplication, which is why
the check lives in `12-engineering-plan.md` r11 step 1 (PACKET) as a step a
person performs, and why this file exists to make that step cheap.

**It is a snapshot and it will rot.** Every row was read out of the code at
`eddc0859` on 2026-09-04 rather than out of a design document. A row that
disagrees with the code is wrong and the code wins — fix the row.

⚠ **AND STEP 4 EARNED ITS KEEP ON 2026-09-05 — THE ARREARS LANE'S FOUR SCREENS
WERE ON NO ROW, AND EVERY ONE OF THEM HAD A READ WAITING.** The two rows added
above are what that search found, and the near-miss is the useful part: the
portal's first draft of *which tier is this account on* compared `case.tier`
against `TIER_UNMAPPED` itself. **That would have been wrong and no test would
have caught it.** `TIER_UNMAPPED` is a COMPUTED value and is never stored; a case
at payments' five-day rung carries that rung's own name and a case that has sent
nothing carries NULL, and those are **two different absences** — *we cannot name
your rung* and *nothing has been sent to you*. `disconnect_reads.chips_for`
already told the two apart for the staff tab. Reading them as one would have told
a customer at the five-day notice that no notice had gone out, which is exactly
the *"clerk and customer arguing on the phone"* this file exists to prevent.

⚠ **WHAT THE SEARCH DID *NOT* FIND, NAMED SO SOMEBODY CAN CHECK** (step 5): no
module publishes **an account-scoped list of late fees charged** —
`apps/billing/late_fee` ASSESSES one and answers no history, and a late fee is an
invoice line carrying `decisions.DEFAULT_LATE_FEE_CHARGE_CODE`. `P43` draws *Late
fee added · 24 Aug · $8.25* as the third rung of the ladder; the step is omitted
and the reason travels in the response's `problems`. Searched:
`apps/billing/*.py`, `apps/payments/*.py`, every `*_reads.py`, and every
account-scoped route in `billing/api.py` and `payments/api.py`.

⚠ **AND FOUR MORE ROWS ON 2026-09-05, FROM THE ENDING LANE'S FOUR SCREENS —
WITH ONE THAT PROVES THE POINT HARDER THAN THE ARREARS NEAR-MISS ABOVE DID.**
`CWP-032` shows a customer their closing bill and gives back the deposit we
hold. Every figure on it is `settle_final_bill`'s, the same function that
settles the account for a clerk, because a customer and a counter clerk quoting
different closing figures is the whole of this file's argument. **Building it on
that read is what found `DEF-CWP-3842`: nothing in the product could settle a
deposit-holding account at all.** The interest engine had shipped the day
before, it refuses to guess which DAY to accrue to, and its only caller never
named one — so a $150.00 deposit against $63.40 of water produced no settlement
instead of *we owe you $86.60*. A second arithmetic in the portal would have
printed a plausible number, agreed with nothing, and left the clerk's side
broken for months. **A reused read fails loudly where a copied one fails
quietly**, and that is a better reason to reuse than tidiness.

⚠ **WHAT THIS LANE'S SEARCH DID *NOT* FIND, NAMED SO SOMEBODY CAN CHECK**
(step 5): no module publishes **the price of restarting a supply as one figure**
— `rating_seam.connection_fees` gives the reconnection fee and
`reconnection_terms` the deposit election, and whether a re-connection ALSO
re-charges a connection fee is not a fact any read holds. `CWP-052` therefore
compares stopping against staying only when both figures exist and **says on
screen that it cannot say** otherwise, rather than guessing. Searched:
`apps/rating/*.py` (every seam and `services.py`), `apps/customers/disconnect*`,
`apps/billing/one_time.py`, and every account-scoped route in `rating/api.py`
and `customers/api.py`.
