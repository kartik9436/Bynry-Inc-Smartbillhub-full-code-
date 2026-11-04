# The money audit — what Finance, Billing, Payments and Charges still need
### PO ruling 2026-08-17, verbatim

> *"You will ahve to check all pending items related to Finance, Accounting,
> Billing , Payments, Charges etc - related to this and - cross verify do we
> need anything else to be set in this settings that we will use later but not
> covered"*

*"this"* is **CR-008 · SET-11 Settings → Accounting**, captured the same day.

This file exists because the answer is bigger than a chat reply and the next
agent will not have that reply. Hard-won law 10: *the test is not "was a decision
made" — it is "would the next agent, with only the repo, build the same thing?"*

**Method: from the CODE outward, never from the design inward.** Four CRs have
now each proved that a gap list derived from a screenshot overstates. Every
finding below was read in the source; the eight load-bearing ones were then
**re-verified independently** before being put to the PO, and the file:line is
given so the next reader can do the same rather than trust this page.

---

## Part 0 · Three things in CR-008 itself are out of date

**These change what CR-008 costs. Correct them before sizing it.**

### 1. `GET /ledger/accounts` IS served. CR-008's headline blocker is closed.

**VERIFIED:** `apps/ledger/chart_api.py:482` — `path("ledger/accounts", accounts)`,
plus the item, deactivate and reactivate routes, mounted at `config/urls.py:116`.
There is also already a **screen**: `07-frontend/src/features/ledger/ChartOfAccountsPanel.tsx`,
on the Finance → General Ledger page — add, rename, re-point a designation,
deactivate-first.

**So CR-008 Tab 1 is not a build.** It is a *move* (Finance → Settings) plus the
two genuinely new pieces: the QuickBooks sync and the CSV import. That is a large
difference in cost and it changes what the CR is.

**And three screens are still refusing on the strength of the expired claim:**
`SettingsAccountingTab.tsx` derives "no chart" from a 404 that no longer happens;
`ChargeCodesTab.tsx:533` renders its GL field read-only saying *"the ledger
module is not built"*; `TaxesFeesTab.tsx:282` does the same for the tax GL cell.
**Hard-won law 1, aged:** a comment claiming an absence is not the absence.

### 2. The bank match tolerance in code is a DATE tolerance. The AMOUNT match is exact.

**VERIFIED:** `apps/payments/reconciliation.py:999` and `bankrec_read.py:609`
both match on `batch.recorded_total == line.amount`. There is **no amount
tolerance of any size anywhere in the product.**

So r10's *"$0.05"* is not a figure we would be *changing* — it is **new
behaviour** that loosens an exact-equality match on money. That is a finance
decision, not a settings control. (`bank_match_date_tolerance_days`, default 3,
already exists and is already on screen — that is the tolerance that is real.)

### 3. ⚠ "Write-off threshold" already exists and means something else entirely.

**This one will cause a real mistake if CR-008 is built as drawn. VERIFIED.**

`apps/tenancy/settings_families.py:504` —
`Param("write_off_threshold_amount", DECIMAL, "5", "BR-BIL-013", minimum=0, maximum=50)`.
Default **$5.00, capped at $50**. That is BR-BIL-013's **small-balance automatic
write-off at a final bill** — the utility stops chasing $2.40 residues.

The **manual collections write-off** (`apps/payments/writeoffs.py`) has **no
amount threshold at all**: every write-off of any size needs an approval, and
the file says so itself — *"the two must not be confused in a bad-debt report"*
(lines 89–92).

r10 draws *"write-off approval at $5,000, second approver above $25,000"* on the
Finance-controls card. **Putting a $5,000 field beside a $50-capped field named
almost identically is how a utility ends up certain they set one when they set
the other.** Two different rules, two different names, or one of them does not
ship.

---

## Part 1 · The five that would actually stop a real utility going live

Ranked. **None of the first four is blocked on a ruling. Three of them are small.**

### 1. A bill carrying ANY fee cannot be issued. Ever.

**VERIFIED, and it is unconditional** — `apps/billing/issue.py:885` is literally
`if kind == "fee": raise BillingRuleError(...)`. No branch, no condition.

Fee lines are really produced (`decisions.py:513`, `first_bill.py:361`) and
`issue` is atomic, so **nothing partial goes out.** The moment a customer's bill
carries a late fee, an NSF fee, a connection fee, a reconnect fee or an
after-hours call-out, **the whole bill refuses.**

**The cause is one level below where CR-008 is looking.** CR-008 assumes the
problem is an *unmapped charge code* — hence the "GAP banner". The real problem
is that the invoice **line does not carry the charge code at all**: stage 6
leaves `charge_id` NULL and nothing anywhere in the billing module ever assigns
it (`charge_id` appears only in reads and filters). **So even a perfectly mapped
charge code cannot be resolved.** Building the GAP banner on top of this yields a
screen that reports everything mapped while every fee bill still refuses.

**This is DEF-181's twin.** That defect fixed exactly this refusal for the
*deposit* line on 2026-08-16 by giving deposits their own designation; the
**fee** half of the same branch was left. Filed as **DEF-201**.

*Not a settings gap — a billing/rating seam fix. Not blocked (BR-BIL-010 already
rules it). Size: medium.*

### 2. Nobody can enter the deposit amounts the utility charges. **DEF-202**

`plan_deposit_rules` is a real table with real validation
(`apps/rating/services.py:621`) and `POST/PUT /rate-plans` accepts
`deposit_rules`. The plan wizard's deposit block **posts nothing** —
`PlanWizard.tsx:905` renders an `ArrivesWithField` whose stated reason is *"that
catalog belongs to the unbuilt customers module and no endpoint serves it."*

**That reason expired.** `account_types` is served today
(`apps/customers/lookups.py:224`), registered in `LOOKUP_LISTS`, with its own
Settings card. So a utility taking a **$150 deposit from every new residential
customer** has nowhere to type $150.

*Belongs on Plans & Rates, NOT SET-11. Rule is CONFIRMED (BR-RAT-020/023). Small.*

### 3. The utility's own bank accounts cannot be created. **DEF-203**

`apps/payments/bankrec_models.py:162` defines `BankAccount`. **The only place in
the entire repo that creates one is a test** (`tests/test_us_pay_020_023_bank_rec.py:180`).
No route, no seeder, no screen.

Bank reconciliation (S38) picks a bank account in step 1, and no real tenant can
ever have one — so **bank rec cannot run for any real utility.**

*Belongs on SET-11 Tab 3 beside the tenders. Not blocked. Small–medium.*

### 4. Two ruled money figures are stored, validated, read by the live engine — and no screen can set them. **DEF-204**

**VERIFIED by diffing the two registries field by field.**
`settings_families.py` COLLECTIONS has **10** parameters; `settingsRulePages.ts`
COLLECTIONS_PAGE draws **8**. Neither missing string appears anywhere in
`07-frontend/src`. The two missing ones are **the money ones**:

* **`ladder_balance_floor_amount`, seeded $25.00** (line 453) — *"a $2.40 unpaid
  balance earns no fee, no $8.00 certified letter and no notice."* The PO ruled
  it per-utility on 2026-08-12 **precisely because** *"$38 vs $180 average-bill
  utilities"* cannot share one number. Read live by `collections_read.py:152`.
* **`partial_payment_pause_percent`, seeded 25%** (line 460) — whether a partial
  payment pauses the collections ladder. $150 against $948 is 15.8% and does not
  pause; at 25% it would take $237.00.

**DEF-097 is marked `fixed` in the register and only its storage half was ever
built.** Its own title says *"have no storage"* — storage was the fix, and the
screen was never added. The row is corrected as part of this audit.

A third, `back_bill_segment_estimate_source`, is the same shape (FINANCE_CONTROLS
8 backend vs 7 on screen) but **is honestly flagged in `settingsRulePages.ts:569`**
— so it is a known deferral, not a silent one.

*Belongs on the existing S70 Collections card. Not blocked. Small — three rows
plus i18n.*

### 5. The late-fee floor and the collections floor are two copies of one number. **DEF-205**

`apps/billing/late_fee.py:233` hardcodes `LATE_FEE_BALANCE_FLOOR = Decimal("25.00")`
as the default of `assess_late_fee(balance_floor=…)`, and **no caller anywhere
passes the tenant's setting into it.**

OQ-157 is **CLOSED** — *"the floor is a PER-UTILITY SETTING with $25.00 as the
seeded default (PO 2026-08-12)"* — so the ruling exists and one of its two
consumers was never wired to it.

**In plain English:** a utility that raises its floor to $50 would stop *chasing*
$30 debts while still *charging late fees* on them. The two numbers agree today
only because both happen to be $25.

*Not blocked. Small — but it is a money path, so it wants a review-ledger row.*

---

## Part 2 · Settings a real utility needs that no CR has put anywhere

| # | In plain English | Evidence | Where it belongs | Blocked? | Size |
|---|---|---|---|---|---|
| 6 | **"Accrual or cash" is already a control on screen and NOTHING reads it.** Pick "cash" on Regional and every journal still posts at bill issue. | `models.py:164` `accounting_method`; settable via `SettingsRegionalTab.tsx`; seeded `"accrual"`. **Every reader is tenancy's own storage/validation** — zero in `apps/ledger` or `apps/billing`. **VERIFIED.** | **This IS CR-008's money question #2, and CR-008 does not know the field exists.** Do not draw a second control. | Blocked — nobody has ruled what cash-basis posting *does* | Large if honoured; **small if the honest move is to remove the control** |
| 7 | **"Lock periods once closed" is a switch that does nothing.** A closed period locks either way. | `apps/ledger/close.py:339`, in its own words: *"THE TOGGLE IS NOT CONSULTED, AND THAT IS FLAGGED… What a CLOSED period should do while the toggle is OFF was never ruled."* | Regional, where it already is. SET-11 must not draw a second. | Blocked — unruled, **PO only** | Small |
| 8 | **Who may reopen a closed period is fixed in code as System Admin; r10 offers a three-way choice.** | `close.py:98` per OQ-033's closure. Also: the ruled role set is System Admin · Billing Clerk · Executive — there is **no** "Finance admin" and no "Owner". | SET-11 Tab 3 — but the control as drawn cannot be honoured | Blocked — reversing OQ-033 needs a ruling | Small (control) / medium (a real role) |
| 9 | **Journal entries are stamped `USD` whatever currency the tenant set.** | `apps/ledger/journal.py:542` `currency="USD"`, whose own comment reads *"a defaulted currency is how a CAD tenant's books quietly become USD"*; same at `opening_balances.py:79`. Tenant currency **is** settable and forward-only-locked. | No new setting — the ledger must read the one that exists | Not blocked | Small (money path → review-ledger row) |
| 10 | **An adjustment/credit reason code has no GL account.** A utility cannot say where a "billing error" credit posts vs a "goodwill" one. | `ReasonCode` = code · name · is_system · active. `tenancy/services.py` trailer: *"reason_codes carries no default_gl_account_id … because no ledger_accounts table exists to FK"* — **that table exists now.** US-TEN-010 §5 already specified the column. | **SET-11 Tab 2 — a FIFTH mapping section CR-008 does not list** | Partly — which reason posts where is unruled | Medium |
| 11 | **A tender carries no cash/clearing account, no settlement lag and no fee.** | `models.py:505` `PaymentMethod` = code · name · is_system · active, and nothing else. | Already CR-008 Tab 2 §3 — noted so sizing knows the table has **no columns at all** for it | Not blocked | Medium (schema + screen) |
| 12 | **Nothing stores where a tax authority remits TO, on what form, or how often.** | `apps/rating/models.py:481` `remit_to`, `filing_frequency`, `filing_form` exist and are marked `PROPOSED-SCHEMA`. The per-authority *remitting basis* (billed vs collected) IS on screen and IS wired. | S13 Taxes & Fees, not SET-11 | Not blocked | Small |

---

## Part 3 · The pending-items sweep

### 3a · Open questions touching money — six actually block something

Most money OQs are non-blocking and the code refuses **by name** rather than
guessing, which is the design working. These six are the ones that matter:

| OQ | What is genuinely unanswered | Blocks a Settings surface? |
|---|---|---|
| **OQ-142** budget-billing settle-up | Answered ("a separate account") but **stuck behind a finance re-signature of the ❄️ frozen chart.** Posting refuses by name until then | Yes — the account cannot appear in any GL mapping |
| **OQ-241 / 242** one-time bills | A bill with no cycle has no due-days and no proration denominator. A $184.20 move-out final could be due 27 Aug, 5 Sep or the day it prints; a 20-day window **over-charges $13.49** on base today | Yes — likely a due-days default needing a home |
| **OQ-234** season-crossing periods | ⚠ Read *"A 15 Sep–14 Oct bill prices at one season, not pro-rata: **$21.60 vs the workbook's $24.16** on one line"* until 2026-10-01. **CLOSED 2026-09-07 and BUILT 2026-10-01 (`DEF-RAT-8832`):** the period splits by calendar days, on-peak $14.08 + $10.08 = **$24.16**, WE-18 usage $82.72, total $103.67 (GT-34 engine-verified) | No |
| **OQ-233** weekday vs weekend TOU | The meter reports one on-peak number; a tenant can configure two prices for it. **$26.40 / $13.20 / $21.24** — three defensible answers | Yes — the editor offers a price nothing can apply |
| **OQ-248** deposit bigger than the final bill | **$153.50** deposit against **$142.30** owed leaves AR at **−$11.20** and nothing can pay it out | No |
| **OQ-246** trash has no meter | A flat unmetered service blocks the whole account: **$18.00 × 48 accounts × 2 periods = $1,728** reaching no customer today | Yes — likely an "unmetered" flag on Settings → Services |

**Non-blocking but money-visible, and worth the PO's eye:** OQ-217 (⚠ CLOSED 2026-10-01 — the whole account since the last bill, BR-BIL-1065; what the
"previous balance − payments" lines mean — total right either way, two middle
lines move) · OQ-215 (does a goodwill credit make this bill say **$222.30** or
**$247.30** — same books, different piece of paper) · OQ-226 ✅ **CLOSED 2026-09-23 — the PO kept v1 and re-affirmed
`BR-PAY-037`** (*"allow it - we are dealing with smaller utilites they dont have
too many people"*); a clerk holding the approver role can still approve their own
write-off, deliberately, with both acts recorded separately — on the prototype's
own debtor that is **$948.20** under one name, and it is now ratified rather
than pending · OQ-238 (base charge typed in two places — this is what made **every bill
print $0.00 for base**, DEF-154) · OQ-195 (a refund against a credit built from
**$40.00 + $17.13 = $57.13** cannot be expressed by the signed schema).

### 3b · Open defects in billing / payments / ledger / rating — 22 rows

**The ones that touch money a customer sees:**

* **DEF-161** (critical) — a plan with any non-metered service cannot be billed. *OQ-246's other half.*
* **DEF-179** (major) — five money cells on the deposit and bank screens **turn an absent amount into $0.00**; the backend deliberately refuses to send a zero and the screen puts one back.
* **DEF-180** (major) — Fix-a-bill and the Report viewer coerce money with `String()`, printing **"undefined USD"**. DEF-151's shape on two screens nobody has clicked.
* **DEF-136** (major) — HEAD's backend suite is **RED** on a bill-read contract test asserting the old credit-note sign.
* **DEF-171** (major) — a bill run that issued every bill still reads `draft`.
* **DEF-069** (major) — an NSF bounce cannot increment `accounts.nsf_count`; the column exists, the seam does not.
* **DEF-098** (major) — the BILLED lock on a meter read is never applied.
* **DEF-139** (medium) — **two different derivations of "what this account owes" exist and nothing compares them.**
* **DEF-119** (major) — three of the five period-close checklist items can never read complete.
* **DEF-130** (major) — plan-assignment and rate-schedule histories are write-only over HTTP (GET → 405).

**`built-not-wired` class specifically** (law 2's category): DEF-049 · DEF-098 ·
DEF-100 · DEF-130 · DEF-069 · DEF-079 · DEF-125 · DEF-106.

**Two register rows were themselves stale, and both are corrected by this audit:**

* **DEF-100** was `open` ("`GET /write-offs` cannot exist"). **It is served** —
  `apps/payments/api.py:550` is `@api_view(["GET", "POST"])` and its docstring
  cites DEF-100 as fixed. **VERIFIED.**
* **DEF-097** was `fixed`. **Only the storage half shipped** — Part 1 item 4.

### 3c · `raise NotImplementedError` in the money modules — only three, and one is not a gap

The money code is markedly cleaner here than the docs imply; every other refusal
is a named `BillingRuleError`/`PaymentRuleError`, which is the better shape.

* `apps/payments/credit.py:376` → **OQ-195.** A customer owed **$57.13** built
  from a $40.00 June overpayment and a $17.13 July one cannot be refunded;
  single-source refunds work.
* `apps/ledger/cost_api.py:603` → **OQ-204.** The Download control on S74 renders
  disabled with the server's own reason. Nothing else affected.
* `apps/rating/engine.py:454` → **not a gap.** The superseded pre-B5 entry point,
  refusing on purpose so an old caller fails loudly.

### 3d · Blocked stories in the four money modules — none live

Every `status: blocked` / `blocked_by` hit is historical text kept for the record
(EP-RAT-07 was unblocked 2026-08-10). One propagation debt:
`07-billing/09-po-input-sheet.md:121` records that `EP-BIL-02-invoice-gl.md:203`
still lists `blocked_by: [OQ-076]` for a question the registry closed.

### 3e · Money items deferred or unclosed in CR-002..CR-007

* **CR-004** (`2.4.0`) — **not complete**: 6 lists BUILT-NOT-PROVEN (never clicked
  through, which is the PO's own bar), 2 not started. Money-relevant: **Import
  mappings** — the ETL column maps SET-11 Tab 1's CSV import would reuse — ship
  deliberately **empty for every tenant**.
* **CR-006** — CAPTURED, not started. Its cycle wizard carries three money fields
  with no home: **bill date offset, due date offset, "late fee trigger date."**
  ⚠ **The late-fee trigger overlaps `late_grace_days` on the S66 Billing-defaults
  page.** Resolve before either is built or there will be two homes for when a
  late fee starts.
* **CR-005** (`2.5.0`) — BUILT-NOT-CLOSED. **OQ-250** (counter pad minimum —
  affects `DEP-`, `ADJ-` and write-off series) and **OQ-252** (a backdated number
  under a restart is refused by name) are both open money-document numbering.
* **CR-007** (`2.7.0`) — the money-facing templates that still **refuse to
  render**: write-off notice · refund issued · payment failed/NSF · deposit
  received & applied · autopay · move-out final bill (OQ-254) · all three
  disconnect tiers (OQ-253, **BLOCKING**).

### 3f · Human review owed

Of **109** ledger rows covering the four money modules: **38** ratified under the
2026-08-11 blanket, **37** `VERIFIED-UNRATIFIED`, **33** `HUMAN-REVIEW-PENDING`.
The pending set includes the files a finance reviewer would most want:
`ledger/deposit_legs.py` · `ledger/opening_balances.py` · `ledger/chart_api.py`
(the very chart CRUD CR-008 Tab 1 is about) · `payments/refunds.py` ·
`payments/reversal.py` · `payments/reconciliation.py` · `billing/budget.py` ·
`billing/posting_seam.py`.

---

## Part 4 · Already covered — do NOT report these as gaps

Each was checked; each exists, is stored, is validated and is reachable on screen.

* **Five rule pages, 47 parameters** — read validation & estimation (13), billing
  defaults (9: late %, late minimum, grace days, grace mode, minimum bill,
  overcharge guardrail, between-bill allocation order, within-bill allocation
  class order, deposit interest rate), budget billing (7), collections & notices
  (8 of 10 — gap #4), finance controls (7 of 8 — gap #4). **Finance controls
  already renders inside the Accounting tab**, per the PO's *"this is moved to
  accounting tab"*.
* **Fiscal calendar** — FY start month, FY start day, accounting method, close
  cadence, close day, lock-closed-periods: all on Regional. **SET-11 Tab 3 must
  not draw a second copy.**
* **Per-authority tax remitting basis** (billed vs collected) — stored, on screen,
  and deliberately seeded EMPTY because any default is wrong for one authority in
  month one.
* **Currency, number/date/time format, timezone, language, first day of week** —
  Regional, forward-only-locked with a confirm.
* **20 reference lists** including charge codes, tax jurisdictions, reason codes,
  payment methods, UoMs, import mappings, account types/statuses.
* **Service → revenue account and service → base-revenue account** — Accounting
  tab, live, writing through `PUT /settings/services/<code>`.
* **Tax authority → 2200-series liability account** — on `taxes.liability_gl_account_id`,
  editable on S13. The PO **declined** a second ledger-side table, so SET-11's tax
  section must point at S13, never duplicate it.
* **Bill template / messages / footer** — Settings → Configure → Templates; the
  S91–S96 designer was **cut by PO ruling 2026-08-16**.
* **Number formats** for Bill #, Payment #, Adjustment #, Deposit #, Write-off #
  — SET-08, shipped `2.5.0`.
* **Credit auto-apply at issue and autopay capture-intent** — these were first
  read as unwired and that reading was **wrong**: `apps/billing/issue.py:1426`
  calls both. Recorded because a stale docstring in `payments/credit.py` still
  says *"NOTHING CALLS `apply_credit_at_issue`"* and will mislead the next reader
  the same way.

---

## The short version

**CR-008's three money questions are real. Its two stated blockers are not** —
the chart of accounts is served and already has a screen, and the write-off
threshold it wants to add already exists meaning something else entirely.

Meanwhile the money half's actual go-live blockers are in **no CR at all**:

1. a bill with a late fee on it **cannot be issued**,
2. **deposit amounts have nowhere to be typed**,
3. the **utility's bank accounts cannot be created**, and
4. two ruled money figures were **stored on 2026-08-15 and never given a screen**,
   while the defect that found them is marked `fixed`.

**None of those four is blocked on a ruling. Three of the four are small.**

---

## Lifecycle

* generated: 2026-08-17, money audit lane, at PO request
* method: code-outward; the eight load-bearing findings independently re-verified
  before being reported
* status: VERIFIED-UNRATIFIED — the findings are facts about the code; **what to
  do about items 6, 7, 8 and Part 0 item 3 is the PO's**
* defects filed from this audit: DEF-201 · DEF-202 · DEF-203 · DEF-204 · DEF-205
  · DEF-206; register corrections to DEF-097 and DEF-100
