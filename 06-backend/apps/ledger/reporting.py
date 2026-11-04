# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (S36 Revenue & AR — the KPI strip and panels, all
#           dimension-derived, every header basis-labeled) · US-LED-009 (S59
#           account ledger report — full source vocabulary + running balance) ·
#           US-LED-010 (S60 by-premises summary — billed/collected/owed) ·
#           US-LED-014 (S41 dual-basis remittance — billed vs collected per
#           authority) · US-LED-013 (the S56 journal-entry list, BR-LED-012's
#           IS-5 capability row — the reverse+repost ACT is apps/ledger/journal)
#           Screens: S36 · S59 · S60 · S41 · S56
# Rules:    BR-LED-016 (S36 KPI strip: revenue, collected, AR, aging — all
#           dimension-derived) · BR-LED-010 (account ledger: dated
#           charges/payments + running balance) · BR-LED-011 (by-premises
#           billed/collected/owed) · BR-LED-013 (remittance per authority:
#           billed vs collected vs remitted vs outstanding) · BR-LED-002 (BOTH
#           bases always computed) · BR-LED-001 (the dimension set) ·
#           BR-LED-007 (subledger tie-outs; any drift is a red flag) ·
#           BR-REP-001 (every money number labels its date basis) · BR-REP-002
#           (read-models over journal-line dimensions, never a side-maintained
#           number) · BR-REP-008 (Type = the FULL source vocabulary) ·
#           BR-REP-009 (collection %) · BR-REP-011 (DSO) · BR-REP-014
#           (collections count BILL-purpose payments only) · BR-LED-012 (the
#           journal list carries the full IS-5 capability row) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6),
#           never float) · rule 5 (only the posting service writes; this module
#           writes NOTHING)
# Golden:   LE-1 trial balance 598.69 = 598.69 · LE-2 revenue-by-service ·
#           LE-3 remittance 47.38 billed / 20.97 collected · LE-6 by-premises ·
#           GT-51..GT-60 (the LE-n allocation, 05-golden-tests.md ❄️)
# Tests:    06-backend/tests/test_us_led_007_revenue_ar.py ·
#           06-backend/tests/test_us_led_009_account_ledger.py ·
#           06-backend/tests/test_us_led_010_by_premises.py ·
#           06-backend/tests/test_us_led_014_remittance.py ·
#           06-backend/tests/test_us_led_013_reverse_repost.py
# Impacts:  apps/ledger/posting.py (READ ONLY — this module reports on what that
#           service wrote and calls nothing on it) · apps/ledger/selectors.py
#           (designation → account) · apps/ledger/chart.py (the 2200 series) ·
#           the S56 trial-balance screen and the S36 tie-out panel, both of
#           which must CONSUME `gl_totals` / `ar_control` here rather than
#           re-derive them — named in the docstring by story, deliberately NOT
#           by US-ID in this header, because G10 reads a Trace-header US-ID as
#           "this file ships that story's test cases" and neither story ships
# ───────────────────────────────────────────────────────
"""The ledger's READ model — every reported money figure, derived once.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides what every finance
screen in the product SAYS the books contain. AI-authored 2026-08-11 under the
PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md. It is
not on the G7 glob list yet and that is REPORTED, not silently accepted — a
marker no gate reads is hard-won law 1 written into a money path.

════════════════════════════════════════════════════════════════════════════
THE ONE RULE THIS FILE EXISTS TO KEEP
════════════════════════════════════════════════════════════════════════════
**A REPORT NEVER RECOMPUTES MONEY. IT READS WHAT WAS POSTED.**

Every figure below is a SUM over `journal_lines` of entries whose status is
`posted`. Nothing here re-rates, re-rounds, apportions, nets, estimates or
falls back to a register when the books are silent. BR-REP-002 states the law
(*"read-models over journal-line dimensions … never a side-maintained
number"*), and BR-LED-016 restates it for the S36 strip specifically
(*"revenue, collected, AR, aging buckets — all dimension-derived"*).

The failure this prevents is not theoretical and it has a name: two numbers for
the same thing. A KPI computed from `invoices` and a trial balance computed from
`journal_lines` agree on the day they are written and disagree the first time a
bill issues without posting, a posting is reversed, or a correction lands. Then
a clerk has to decide which screen is lying, and BR-LED-007's drift detection —
the only thing that can catch a posting-service bypass — is looking at the wrong
pair of numbers. So there is exactly one derivation of "billed", one of "AR",
one of "revenue by service", and the trial balance and the KPI strip are the
same query grouped differently.

════════════════════════════════════════════════════════════════════════════
THE SECOND RULE, ADDED 2026-08-15: ONE CURRENCY, OR NO NUMBER (DEF-081)
════════════════════════════════════════════════════════════════════════════
**NO FIGURE HERE IS EVER SUMMED ACROSS TWO CURRENCIES.** Every Σ in this file
asks `_one_currency` over exactly the lines it is about to add, and REFUSES with
`MixedCurrencyBook` when they disagree.

This is arithmetic, not policy: 100 USD + 100 CAD is not 200 of anything, for
the same reason kWh is never added to kgal (hard rule 3, one column over). The
danger is entirely in how ordinary the result looks — every finance screen in
the product would render it beside a currency symbol, correct to six decimal
places and wrong about what money it is.

It became reachable because `apps/ledger/posting.py` takes `currency` as a
REQUIRED PER-ENTRY input and defaults nothing, so nothing at the posting
boundary stops a tenant holding USD and CAD entries side by side; DEF-075 is the
hole that let a tenant with issued bills change its currency at 200 OK, and any
tenant that did so while it was open can hold a mixed book today. The one-off
sweep for such tenants is `10-scripts/def081_currency_sweep.py`.

**AND THE CURRENCY IS NOW DERIVED, NOT LABELLED.** Every result dict carries a
`currency` key holding the CHAR(3) the figures actually ARE, read off the
entries summed. Before this, `apps/ledger/api.py` labelled each figure with the
TENANT's declared code — which is a LABEL and not a derivation, and would have
put a confident USD sign on a mixed total (`apps/ledger/wire.py` says so in its
own trailer). `journal_entry_list` is the deliberate exception and refuses
nothing; its docstring says why.

**WHEN THE BOOKS CANNOT ANSWER, THIS MODULE SAYS SO.** Every result carries an
`unavailable` tuple in the shape `apps/billing/posting_seam.POSTING_UNAVAILABLE`
established: a `code`, a `br_ref`, the `detail` in prose, and — where a
neighbouring module would have to publish a read — that read named in full so
the day it exists the gap closes with no edit on either side. A `None` figure
with a named reason is a report a finance officer can act on. A plausible zero
is not.

════════════════════════════════════════════════════════════════════════════
WHAT THE BOOKS CANNOT ANSWER TODAY — THE FOUR REAL GAPS, MEASURED
════════════════════════════════════════════════════════════════════════════
Named here rather than discovered per function, because between them they
decide how much of EP-LED-03 is buildable at all.

**1 · ⚠ CLOSED SINCE 2026-08-16, AND THIS GAP WENT ON DESCRIBING ITSELF AS OPEN
UNTIL 2026-09-03 IN THE VERY FILE THAT COMPUTES THE FIGURE (`DEF-2345`,
completing `DEF-3382`, which reached two of seven places).**

**WHAT THIS SAID, AND IT WAS TRUE WHEN WRITTEN:** *"`premises_id` and `unit_id`
are NULL on every journal line in the product. Not 'usually', not 'for some
sources' — nothing anywhere passes either dimension … So US-LED-010's
by-premises summary cannot be built from the ledger today, and
`by_premises_summary()` below returns `available=False` with the amount at stake
rather than an empty table."*

**WHAT IS TRUE NOW.** **US-LED-002 LANDED 2026-08-16.** `apps/ledger/posting.py`
resolves account → unit → premises AT POSTING TIME and **refuses a line that
names a customer account and cannot resolve one**, so the stamp is not merely
present, it is enforced where it applies. `by_premises_summary()` below has
grouped on it ever since and foots to LE-6's **500 Main St 247.87 · Oak Grove
16.42 · Marina Bay 289.40 = 553.69** — the same **553.69** that used to be the
refusal's measurement. It no longer returns `available=False` for this reason.

**WHY THE PARAGRAPH IS CORRECTED RATHER THAN DELETED.** The clause under it is
still live law and is the reason the stamp exists at all: resolving the chain AT
READ TIME was considered and REFUSED, because it is precisely the defect
US-LED-010 TC-5 tests for (*"a unit deactivated + recreated mid-period →
historical lines keep their STAMPED premises/unit — the report is stable"*). A
read-time join moves last year's money the day a unit is re-assigned, and
BR-MET-046's chain guarantee is about the STAMP, not about the join. Delete the
paragraph and the next lane meets a group-by with no record of what it rejected.

⚠ **WHAT IS STILL GENUINELY ABSENT IS NARROWER AND IT IS NOT THIS GAP:** a line
that lawfully carries NO premises — a bank fee, a deposit-batch cash leg (see
`apps/ledger/posting._stamped`) — still exists and always will. That is why
`by_premises_summary` reports `unattributed_billed` / `unattributed_collected`
beside its table instead of dropping the money, and it is why a trial balance
narrowed to one premises **cannot foot** (see `trial_balance`'s own note).

**2 · WHICH BILL A PAYMENT MET IS NOT IN THE BOOKS.** A payment entry credits
AR in one lump with `source_id` = the PAYMENT (`apps/payments/ledger_seam.py`),
so the journal knows cash reduced AR by 292.87 and does NOT know that 247.87 of
it met this period's bill and 45.00 an earlier one. That is what
`allocations` records, in payments.

Consequence, stated with both signed figures because they are different numbers
and both are CONFIRMED: the **Collected COLUMN** — total cash that landed
against AR — IS derivable and is LE-6's *"collected 446.37 (292.87 + 153.50)"*.
The **collection % NUMERATOR** is not: BR-REP-009 defines it as *"cash applied
to bills IN PERIOD"*, which US-LED-007 §7 works to **401.37** and **72.49%** by
excluding exactly the 45.00 prior-period application. This module publishes the
column and reports the percentage as unavailable, naming the read.

**3 · TAX INSIDE A PAYMENT IS NOT IN THE BOOKS — BUT IT IS NOW IN PAYMENTS, AND
THE COLLECTED COLUMN READS IT (⚠ CHANGED 2026-09-02, CR-060 C19 / task T7d).**
BR-LED-002's collected basis is *"tax inside cleared payments via allocation"*.
This paragraph read *"an `allocations` row names a payment, an invoice and an
amount — and no line class… a PARTIAL payment needs a rule saying whether it
meets tax pro-rata, last, or first, and nobody has signed one. Raised, not
chosen."*

**The class breakdown now has a home** — `allocation_classes`, payments/0015,
one child row per class written in the same transaction as its parent — so what
a payment met is a stored fact and the column is produced rather than refused.
**It is still not an adjudication of the partial-payment argument**: `OQ-174`
(*"tax first"*) and `BR-PAY-010` (a tenant-set order, tax second by default)
still disagree, and C19's ruling is that recording the breakdown *"makes the
question moot"*. Whatever order a tenant set is what their money walked.

**Two things this module owns, and both are stated rather than assumed.** The
per-authority split of ONE bill's collected tax is BR-LED-794, this lane's
judgment, in the decision log: proportional to what each authority was billed on
that same bill, exact whenever the bill's tax was met in full (LE-3's signed
**20.97**), and always summing to the money that came in. And the figure is a
**FLOOR** while any allocated money carries no breakdown — everything allocated
before 2026-09-02, and credit applications and releases, which never run the
class walk. `GAP_COLLECTED_IS_A_FLOOR` names it and
`totals.allocated_without_breakdown` measures it.

**The BOOKS still hold no tax dimension on a payment entry**, which is what the
first half of this heading says and is unchanged: the journal's payment entry
credits AR in one lump. The collected basis is answered from the payments
register, and the report says so.

**4 · `tax_authority_id` IS NULL ON EVERY TAX LINE — AND IT DOES NOT MATTER FOR
THE BILLED BASIS.** Rating publishes no `tax_authority_id_for_tax`
(`apps/billing/posting_seam.TAX_AUTHORITY_READ` asks for it by name and nothing
answers). But the PO's ruling of 2026-08-11 (BR-BIL-069) makes the dimension
unnecessary for the per-authority SPLIT: *"For each atheority have separate
account and tagging"*, and B5 line 74 ❄️ gives the series — *"2200-series Tax
payable per authority (tenant authorities mint their own)"*. **The authority's
own 2200-nn ledger account IS its identity in the books**, so
`remittance_by_authority()` groups by account and reproduces LE-3's
State 13.87 · County 2.22 · City 4.44 · PUC 0.44 with no dimension at all.
What the missing dimension costs is the AUTHORITY NAME as rating knows it; the
account's own name — typed by the tenant at
`apps.ledger.services.create_tax_authority_account` — is what this reports.

════════════════════════════════════════════════════════════════════════════
BASIS LABELS ARE DATA, NOT DECORATION (BR-REP-001)
════════════════════════════════════════════════════════════════════════════
*"every KPI/report header labels its basis — no unlabeled money number
anywhere."* So `basis` travels ON every figure group this module returns, not in
a caption a screen may forget to render. Two values and they are not
interchangeable:

  * **POSTING** — the `journal_entries.entry_date` book date. Billed, revenue,
    AR, aging, collection %. Everything on S36 and S60.
  * **CLEARING** — the date cash was confirmed. BR-PAY-021 matches bank
    statements on it; `apps/payments/ledger_seam.py` books the payment entry ON
    it. ⚠ US-LED-014's collected basis WAS clearing-based until 2026-10-21; the
    PO moved it to the payment's POSTING date when `cleared` came to mean
    *reconciled with the bank* (`DEF-PAY-10321`, decision log *"Two CR-186
    follow-up rulings"* item 2), so the collected column is labelled `posting`.

**AND CLEARING IS NOT THE SAME AS REALISED.** PO ruling 2026-08-11 closing
OQ-143, verbatim: *"Cash is received but undeposted in such case payment will
say csah but ledger will say undeposited - until bank record and reconcilaition
confirm it it is not realised."* The books implement it in two steps — receipt
debits **1010 Undeposited funds**, reconciliation moves it to **1000 Cash** —
so a cash-basis figure summed off the `cash` designation counts what the BANK
confirmed and a figure summed off `undeposited_funds` counts what a clerk keyed.
`cash_position()` below returns both, separately, and never adds them into one
"cash" number. A report that did would tell a utility it has money in the bank
that is sitting in a drawer.

════════════════════════════════════════════════════════════════════════════
LE-1 IS RESTATED BY THE SAME RULING, AND THIS MODULE REPORTS THE RESTATEMENT
════════════════════════════════════════════════════════════════════════════
The ledger workbook's LE-1 books the customer payment to *"1000 Cash (150.00 +
292.87) 442.87"*. Under the OQ-143 ruling the receipt leg lands in 1010 and only
reconciliation moves it, so a July book where the payment has not been banked
reads **1000 Cash 150.00 · 1010 Undeposited 292.87** — same 442.87, two rows.
The payments lane REPORTED this (`apps/payments/ledger_seam.py`, *"LE-1 IS THE
CASUALTY AND IT IS NAMED"*); this module is the first thing that would RENDER
the difference, so it is repeated here. **The TOTALS are untouched: 598.69 =
598.69 either way**, which is why nothing frozen moved and why the tie-out in
`trial_balance()` holds across the restatement.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES NOT BUILD
════════════════════════════════════════════════════════════════════════════
  * **No writes of any kind.** Not one INSERT, not one UPDATE. The remittance
    JE of US-LED-014 is a WRITE and lives in `apps/ledger/journal.py`, which
    calls the posting service (CLAUDE.md rule 5).
  * **No API and no screens.** S36/S41/S59/S60 have no endpoints and no
    frontend; the module's own `D`/`E` checklist marks say so. Building screens
    over `by_premises_summary`'s refusal would be building a page that renders
    nothing (hard-won law 2), which is why the read half ships first and honest.
  * **No downloads (IS-11).** BR-REP-018's CSV/PDF contract, the money-export
    audit row (BR-LED-015) and the filename grammar are a separate half.
  * **US-LED-008's trial-balance SCREEN** — the dimension expansion and the
    export. `gl_totals()` here is the derivation that story must consume.
    ⚠ **THE PREMISES FILTER IS NO LONGER BLOCKED AND THIS LINE SAID IT WAS
    UNTIL 2026-09-03 (`DEF-2345`).** It read *"the screen is not built and the
    premises filter cannot be until gap 1 closes"*; **gap 1 closed on
    2026-08-16** and the filter is BUILT — `trial_balance(premises_id=…)` and
    `journal_entry_list(premises_id=…)`, CR-060 C24. What is still outstanding
    on this bullet is the dimension EXPANSION and the export, not the filter.
  * **US-LED-004's tie-out COMPUTATION.** `ar_control()` publishes the AR
    control total the panel needs; comparing it against the customer registers
    is that story's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.ledger import billing_seam, chart, dimension_seam, journal, models, payments_seam, selectors, tenancy_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import order_terms

ZERO = Decimal("0")

#: CR-060 C19 / BR-LED-794 — the ONE place this module rounds. A collected-tax
#: share apportioned across a bill's authorities is quantized here, half-up, and
#: nowhere else: BR-LED-025 makes the ledger refuse more than 2 dp at posting and
#: BR-REP-002 makes a report read money rather than re-derive it, so a second
#: rounding site in this file would be a report inventing a cent.
TWO_PLACES = Decimal("0.01")

#: BR-REP-001's two values, as DATA on every figure group. Repeated as strings
#: rather than imported from payments: a basis label is the reports contract,
#: not payments' vocabulary, and the ledger carries no import edge outward.
BASIS_POSTING = "posting"
BASIS_CLEARING = "clearing"

#: BR-REP-008's FULL source vocabulary, verbatim: *"bill · payment · adjustment
#: · refund · deposit · write-off · opening · remittance · manual JE ·
#: transfer"*. Ten values and the report shows all ten — *"so the report foots
#: to the AR tie-out (nothing invisible)"*.
TYPE_BILL = "bill"
TYPE_PAYMENT = "payment"
TYPE_ADJUSTMENT = "adjustment"
TYPE_REFUND = "refund"
TYPE_DEPOSIT = "deposit"
TYPE_WRITE_OFF = "write-off"
TYPE_OPENING = "opening"
TYPE_REMITTANCE = "remittance"
TYPE_MANUAL_JE = "manual JE"
TYPE_TRANSFER = "transfer"

SOURCE_VOCABULARY: tuple[str, ...] = (
    TYPE_BILL,
    TYPE_PAYMENT,
    TYPE_ADJUSTMENT,
    TYPE_REFUND,
    TYPE_DEPOSIT,
    TYPE_WRITE_OFF,
    TYPE_OPENING,
    TYPE_REMITTANCE,
    TYPE_MANUAL_JE,
    TYPE_TRANSFER,
)

#: `journal_lines.source_type` → BR-REP-008's word for it.
#:
#: ⚠ **THIS COMMENT SAID *"the strings the FOUR posting callers actually write
#: today"* UNTIL 2026-09-25 AND THERE ARE ELEVEN (`DEF-LED-6702`).** It named
#: four files, and a claim about four files is a claim nothing re-checks — which
#: is hard-won law 1 in the place a clerk reads the consequence, because an
#: unmapped source renders RAW on the S56 Journal's SOURCE column. **Counted,
#: not estimated**, over the modules that post to the books:
#:
#:   * **17 distinct `source_type` strings are written** by 11 files —
#:     `invoice` (billing/posting_seam) · `credit_note` (billing/corrections) ·
#:     `counter_receipt`, `counter_session`, `deposit_batch`, `payment`,
#:     `refund`, `write_off` (payments/ledger_seam) · `manual_je`,
#:     `journal_entry` (ledger/manual_je) · `opening_balance`
#:     (ledger/opening_balances) · `remittance` (ledger/journal + close) ·
#:     `allowance_for_doubtful_accounts` (ledger/allowance) · `depreciation`
#:     (ledger/depreciation) · `supplier_invoice` (ledger/cost_capture) ·
#:     `unbilled_revenue_accrual` (ledger/unbilled_accrual) ·
#:     `unpaid_cost_accrual` (ledger/unpaid_cost_accrual).
#:   * **This map holds 15 keys.** Ten are written today; four
#:     (`invoice_line`, `adjustment`, `deposit`, `transfer`) are US-LED-001's
#:     contract-table entries for sources not yet wired and are kept.
#:   * **SIX WRITTEN STRINGS STILL HAVE NO KEY** and render raw on the Journal
#:     today: `counter_session`, `allowance_for_doubtful_accounts`,
#:     `depreciation`, `supplier_invoice`, `unbilled_revenue_accrual`,
#:     `unpaid_cost_accrual`. **They are NOT mapped here, deliberately**:
#:     BR-REP-008's vocabulary is ten words and five of those six have no word
#:     in it at all — a depreciation charge and a supplier invoice are not a
#:     bill, a payment or an adjustment — so choosing one would be inventing a
#:     signed rule rather than implementing it. **`OQ-LED-12657`**, OPEN, and
#:     `tests/test_def_led_6702_counter_receipt_source.py` pins the SIX so a
#:     lane that maps one without an answer goes red and is told which.
#:
#: ⚠ **`counter_session` HAS A WORD ON SCREEN SINCE 2026-10-12 AND STILL NO KEY
#: HERE (`DEF-LED-10074`).** The PO named it — *Counter session* — and the word
#: lives in the screen's catalogue (`finance.journal.sourceCode.counter_session`,
#: eleven languages) because the ruling named a LABEL, not which of BR-REP-008's
#: ten GROUPS a drawer difference totals under. So the grouping is untouched,
#: `test_def_led_6702_counter_receipt_source.py` still pins six unmapped here,
#: and `test_def_led_10074_every_journal_source_has_a_word.py` pins the FIVE
#: that still have no word anywhere (`OQ-LED-12657`).
#:
#: **An unmapped value is NOT silently bucketed** — see `source_vocabulary_for`.
SOURCE_TYPE_TO_VOCABULARY: dict[str, str] = {
    "invoice": TYPE_BILL,
    "invoice_line": TYPE_BILL,
    "credit_note": TYPE_ADJUSTMENT,
    "adjustment": TYPE_ADJUSTMENT,
    "payment": TYPE_PAYMENT,
    "deposit_batch": TYPE_PAYMENT,
    # `DEF-LED-6702` — a counter receipt is a PAYMENT taken at the counter, and
    # `apps/payments/ledger_seam.py` has written this string on every one since
    # counter receipts shipped. It reached the Journal's SOURCE column as the
    # raw code `counter_receipt` on six or more live rows (B14 rule 32: no
    # internal code in clerk-facing copy).
    #
    # ⚠⚠ **IT MUST NEVER JOIN `CASH_SOURCE_TYPES`, AND THAT IS A MONEY RULE
    # RATHER THAN A PREFERENCE.** That tuple means *"cash met a RECEIVABLE"*. A
    # counter receipt posts cash against customer CREDIT — DR 1010 / CR 2400 —
    # and never touches AR, so adding it there would move `collected` and the
    # billed-and-collected figures on `revenue_and_ar` **while looking, in the
    # diff, exactly like this copy fix**. A case asserts it is absent, by name.
    "counter_receipt": TYPE_PAYMENT,
    "refund": TYPE_REFUND,
    "deposit": TYPE_DEPOSIT,
    "write_off": TYPE_WRITE_OFF,
    "opening_balance": TYPE_OPENING,
    "remittance": TYPE_REMITTANCE,
    "manual_je": TYPE_MANUAL_JE,
    "journal_entry": TYPE_MANUAL_JE,
    "transfer": TYPE_TRANSFER,
}

#: The `source_type` values that mean "a bill was issued". Billed-in-period is
#: Σ AR debits from these, which is US-LED-007 TC-1's *"Billed 553.69 = Σ issued
#: invoice postings"* — not `Σ invoices.total`, which is the parallel query
#: BR-REP-002 forbids.
BILL_SOURCE_TYPES = ("invoice", "invoice_line")

#: The `source_type` values that mean "cash met a receivable". Deposit
#: APPLICATION (BR-BIL-013) reaches AR under `invoice`, so it is not here; it is
#: identified by the deposit-liability leg — see `revenue_and_ar`.
CASH_SOURCE_TYPES = ("payment", "deposit_batch")


# ── the gaps, in the shape apps/billing/posting_seam.py established ─────────
#: ⚠ REWRITTEN 2026-08-16 (US-LED-002 lane) and the OLD TEXT IS QUOTED IN THE
#: TRAILER, because a gap sentence that outlives its gap is hard-won law 1 in
#: the place a finance officer reads. It used to open *"every journal line in
#: the product carries premises_id = NULL"* — that was true for five days and
#: is false now: `apps/ledger/posting._stamped` resolves the chain at posting
#: time. What remains true, and is the ONLY thing this code may now claim, is
#: that a PERIOD can still have no premises-bearing AR line.
GAP_PREMISES_DIMENSION = {
    "code": "premises_and_unit_dimensions_never_stamped",
    "br_ref": "BR-LED-001 · BR-LED-011 · US-LED-002",
    "detail": "no AR line in this period carries a premises, so there is nothing to group "
    "on. Since 2026-08-16 the posting service resolves account → unit → premises on every "
    "line that names an account (BR-LED-001, *resolved AT POSTING TIME*), so a period billed "
    "from that day forward has the dimension. Two things still produce this answer and they "
    "are different facts: the period had no AR activity at all, or its entries were posted "
    "BEFORE the dimension existed — and those lines keep premises_id = NULL for ever, because "
    "a posted journal line is immutable (hard rule 4) and there is no lawful UPDATE that "
    "could backfill it. Resolving the chain HERE, at read time, stays refused: US-LED-010 "
    "TC-5 requires a historical line to keep its STAMPED premises so a unit deactivated and "
    "recreated mid-period leaves the report stable, and a read-time join moves last year's "
    "money the day a unit is re-assigned.",
    "wanted_reads": (),
}

#: The ACCOUNT LEDGER's own residue, split out of GAP_PREMISES_DIMENSION on
#: 2026-08-16. S59 used to report "the dimension is never stamped" because that
#: was true; what was ALWAYS true, and is all that is true now, is narrower: the
#: report offers no premises PARAMETER. A14 r2 gives S59 one and US-LED-009 §8
#: records it as unserved. Keeping the old sentence here would tell a clerk the
#: books hold no premises while S60 shows them a table of premises.
GAP_PREMISES_FILTER_NOT_OFFERED = {
    "code": "premises_filter_is_not_offered_on_this_report",
    "br_ref": "BR-LED-010 · US-LED-009 §8 · A14 r2",
    "detail": "A14 r2 gives the account ledger a premises filter and this report does not "
    "accept one. The dimension itself EXISTS on the lines since 2026-08-16 (US-LED-002), so "
    "the filter is now buildable and is US-LED-009's to build; it is reported rather than "
    "quietly accepted, because a parameter that took a premises and changed nothing would "
    "make the report LOOK filtered, which is the worse failure.",
    "wanted_reads": (),
}

#: Emitted BESIDE a real table, never instead of one: money in the window that
#: no premises claims. It is quantified on the response (`unattributed_billed` /
#: `unattributed_collected`) so the footer and the table can disagree openly
#: rather than the table quietly being short.
GAP_PREMISES_RESIDUE = {
    "code": "some_money_in_this_period_carries_no_premises",
    "br_ref": "BR-LED-011 · US-LED-002 · hard rule 4",
    "detail": "the table below shows every premises the books can attribute, and some of "
    "this period's AR movement carries no premises at all — the two `unattributed_*` figures "
    "on this response are how much. The lawful causes are entries posted before 2026-08-16 "
    "(immutable, so they can never be backfilled) and AR lines that legitimately name no "
    "customer account. The table's footer therefore does NOT equal the S36 KPI strip for such "
    "a period, and that difference is stated here rather than reconciled away.",
    "wanted_reads": (),
}

#: CR-060 C24 — emitted ONLY when a trial balance is narrowed to one premises.
#:
#: ⚠ **A NARROWED TRIAL BALANCE USUALLY FOOTS, AND THAT IS EXACTLY WHY ITS
#: FOOTING IS NOT A VERDICT.** The first draft of this constant asserted the
#: opposite — *"a filtered trial balance does not foot"* — and **the test written
#: to prove it went RED against the signed LE-1 month**: all three of LE-6's
#: properties foot when narrowed (500 Main St 446.37 = 446.37, Marina Bay 289.40,
#: Oak Grove 16.42), because `posting._stamped` resolves the chain from the
#: ACCOUNT and both legs of a receipt name the same customer account, so both
#: legs carry the same property. **0 of that month's 28 journal lines carry no
#: property at all.** The reasoning is corrected here rather than quietly
#: adjusted, because the wrong version is the one a reader would otherwise
#: reconstruct.
#:
#: **WHAT IS ACTUALLY TRUE: A NARROWED TABLE FOOTS SOMETIMES, AND THE TWO CASES
#: ARE INDISTINGUISHABLE FROM THE OUTSIDE.** It does NOT foot when the filter
#: cuts an entry in half, and there are two lawful ways that happens:
#:   * a line naming NO account is never stamped — a bank fee, a deposit-batch
#:     cash leg (`posting._stamped`: *"money about the utility's own bank
#:     account, not about anyone's premises"*), so an entry mixing one of those
#:     with a stamped line splits under the filter;
#:   * one entry can legitimately span TWO properties — `models.JournalLine`
#:     says so of a master-account transfer — and either half then leaves the
#:     other outside.
#:
#: **SO `balanced` IS `None` HERE, AND `False` IS THE VALUE THAT WOULD LIE.**
#: `False` is a specific and serious claim in this module: BR-LED-007 makes it
#: mean the posting service was bypassed, and `trial_balance`'s own docstring
#: says the arithmetic is then the finding. On a narrowed table a mismatch means
#: *either* that or an ordinary split entry, and this module cannot tell which —
#: so it says so instead of picking. `True` would be no better: a narrowed table
#: that happens to foot has proved nothing about the books, only about the
#: slice. DEF-127's shape one column over — a verdict nobody can compute must
#: not render as one somebody computed.
GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT = {
    "code": "footing_is_not_a_verdict_on_a_trial_balance_narrowed_to_one_premises",
    "br_ref": "BR-LED-001 · BR-LED-007 · CR-060 C24 · DEF-127",
    "detail": "this trial balance is narrowed to one property, so whether it foots says "
    "nothing about the books. An entry balances across ALL its lines, and this table holds "
    "only the lines carrying this property: an entry the filter cuts in half — one with a "
    "bank fee or a deposit-batch cash leg, which name no property by rule, or a transfer "
    "spanning two properties — leaves its other half outside. Most narrowed tables DO foot, "
    "because both legs of a receipt name the same customer account and are stamped alike, "
    "and that is precisely why footing cannot be read as proof. `balanced` is therefore "
    "served as null rather than true or false: false is BR-LED-007's posting-service bypass "
    "and would send somebody hunting a fault that is not there, and true would claim a proof "
    "nobody performed. `difference` remains the true arithmetic of the rows shown. The "
    "unfiltered report is where footing is a verdict.",
    "wanted_reads": (),
}

GAP_ALLOCATION_PERIOD = {
    "code": "which_bill_a_payment_met_is_not_in_the_books",
    "br_ref": "BR-REP-009 · BR-LED-016",
    "detail": "a payment entry credits AR in ONE lump with source_id = the payment, so the "
    "books record that cash reduced AR and not WHICH bill it met. BR-REP-009 defines "
    "collection % as *cash applied to bills IN PERIOD ÷ billed in period*, which US-LED-007 "
    "§7 works to 401.37 / 72.49% by excluding a 45.00 prior-period application. The "
    "period-attribution lives in payments' `allocations`. The COLUMN — total cash landed "
    "against AR, LE-6's 446.37 — is derivable and is reported; the PERCENTAGE is not, and is "
    "reported as None rather than as a plausible number computed off the column.",
    "wanted_reads": (
        "apps.payments.selectors.allocated_to_invoices_issued_between("
        "start: date, end: date) -> Decimal",
    ),
}

# ⚠ **RETIRED 2026-09-02 (CR-060 C19 / task T7d) — NOT REWORDED, RETIRED.**
# `GAP_TAX_INSIDE_A_PAYMENT` reported that the collected basis *"is not
# derivable"* because *"an `allocations` row names a payment, an invoice and an
# amount and carries NO LINE CLASS"*. **That sentence describes a limit that no
# longer holds:** `allocation_classes` (payments/0015) records the breakdown on
# every allocation, in the same transaction as its parent, so what a payment met
# is a stored fact. C19 asks for exactly this treatment in as many words — *"its
# refusal text is RETIRED, not reworded, because it describes a limit that will
# no longer hold"* — and a reworded version would leave a screen telling a
# finance officer the figure cannot be produced while the column beside it
# produced it.
#
# The paragraph is kept HERE, in the past tense, because the reason matters
# (hard-won law 1) and because two signed rulings still disagree about how a
# partial payment meets tax: `OQ-174` closed 2026-08-12 with *"a partial payment
# covers TAX FIRST"* and `BR-PAY-010` makes the sequence a tenant setting whose
# default puts tax second. **Neither is adjudicated by this change and neither
# needs to be** — whatever order a tenant set is the order their money walked,
# and the walk is now written down.
#
# WHAT REPLACES IT is `GAP_COLLECTED_IS_A_FLOOR` below, which is a smaller and
# TRUE statement: some allocated money carries no breakdown and never will.
GAP_COLLECTED_IS_A_FLOOR = {
    "code": "collected_tax_omits_allocations_with_no_class_breakdown",
    "br_ref": "BR-LED-002 · BR-LED-794 · CR-060 C19",
    "detail": "the collected column reads what each payment actually met inside each bill "
    "(payments/0015, `allocation_classes`). Three kinds of allocated money carry no such "
    "breakdown and are NOT in the figure: everything allocated before 2026-09-02, because the "
    "breakdown was computed and kept only in the audit trail, which is pruned and cannot be "
    "backfilled; and the application or release of an account CREDIT, neither of which runs "
    "through the class order at all. The amount left out is on this response as "
    "`allocated_without_breakdown`. The collected figure is therefore a FLOOR — the tax we can "
    "prove was collected, never more — and a return filed on it under-remits rather than "
    "over-remits.",
    "wanted_reads": (),
}

#: The S71 rule page the per-authority basis is kept on, and the key it is kept
#: under. Named as constants so the contract is greppable from BOTH sides of the
#: boundary — the discipline `apps/ledger/tenancy_seam.py` uses for its two
#: tenancy reads.
REMITTING_BASIS_FAMILY = "finance-controls"
REMITTING_BASIS_KEY = "tax_remitting_basis_by_authority"


def _remitting_basis_by_authority() -> dict[str, str]:
    """Which basis this tenant FILES on, per authority — `{account code: basis}`.

    PO ruling 2026-08-12, verbatim: *"E Remit on what you BILLED, not what you
    collected - this is also correct"*. Both bases are legitimate and the choice
    is the customer's, per authority, exactly as BR-LED-002 has said since it was
    confirmed. Until 2026-08-12 the choice had nowhere to live, which is what the
    `per_authority_remitting_basis_is_not_stored` problem code below reported;
    it now lives on the S71 Finance-controls rule page.

    The key is the authority's own 2200-nn GL ACCOUNT CODE, because the PO ruled
    on 2026-08-11 (BR-BIL-069) that each authority has its own account — so the
    account IS the authority in the books, and it is the label this very report
    puts on the row.

    Resolved BY NAME at call time (B1/BR-TEN-013: the ledger never touches
    tenancy's ORM), and tenant-scoped by tenancy's own read under RLS FORCE
    (hard rule 1) — this function issues no query.

    An UNREADABLE setting comes back EMPTY, which reports every authority as
    unset. That direction is deliberate and is the opposite of the seam
    convention elsewhere in this module's neighbours, so it is stated rather
    than assumed: this is a READ-ONLY report and its whole contract is that a
    figure it cannot stand behind is reported as unavailable with a reason
    (`unavailable`), never guessed and never raised in a finance officer's face.
    "the tenant has not chosen" and "we could not read the choice" both mean the
    report must not claim a basis — and the report already has an honest way to
    say exactly that.

    ⚠ WHERE THIS BELONGS. `apps/ledger/tenancy_seam.py` is this module's
    tenancy seam and this read is the same shape as its `service_gl_attributes`.
    It is here rather than there because that file is outside this lane's
    territory; moving it is one edit with no caller change, and it is REPORTED
    rather than done quietly (hard-won law 1).
    """
    try:
        tenancy_selectors = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover — the module exists in this repo
        return {}
    read = getattr(tenancy_selectors, "settings_family", None)
    if not callable(read):  # pragma: no cover — defensive
        return {}
    values = read(REMITTING_BASIS_FAMILY)
    chosen = values.get(REMITTING_BASIS_KEY) or {}
    if not isinstance(chosen, dict):  # pragma: no cover — tenancy validates the shape
        return {}
    return {
        str(code): str(basis)
        for code, basis in chosen.items()
        if str(basis) in journal.REMITTING_BASES
    }


def _remitting_basis_gap(unset: tuple[str, ...]) -> dict[str, Any]:
    """The authorities this tenant has not yet said which basis they file on.

    HISTORY, kept because the reason matters (hard-won law 1). Until 2026-08-12
    this was a static gap and its detail read *"r13 #3 places it on
    `tax_remittances` (DDL 🔒) and that table does not exist … So which basis an
    authority remits ON is unknown"*. That WAS true: the choice had no home
    anywhere in the product, so every row came back `remitting_basis=None` and
    the whole table was declared unavailable. The PO closed it on 2026-08-12 —
    *"E Remit on what you BILLED, not what you collected - this is also
    correct"* — and the setting now lives on the S71 Finance-controls page.

    What remains is not a missing table but a missing DECISION, per authority,
    and the gap now names exactly which ones. It clears when every authority on
    the report has a basis, and it does NOT clear on the first save: LE-3 has
    four authorities and TC-2 rules on two of them, so a code that went quiet
    then would hide City and PUC.
    """
    return {
        "code": "per_authority_remitting_basis_is_not_stored",
        "br_ref": "BR-LED-002 · PO ruling 2026-08-12",
        "authorities": unset,
        "detail": "BR-LED-002: *a per-authority setting picks the remitting basis*. Since the "
        "PO's ruling of 2026-08-12 that setting EXISTS — it is "
        f"`{REMITTING_BASIS_KEY}` on the S71 Finance-controls page, keyed by the authority's "
        "own 2200-nn account code — and this tenant has not yet chosen one for "
        f"{list(unset)}. BOTH bases are still computed and reported for them, with "
        "`remitting_basis=None`. Nothing here picks one: LE-3 has State on COLLECTED and "
        "County on BILLED, so a default would be wrong for one of them on the first month.",
        "wanted_reads": (),
    }


#: The shape when there is not even an authority to choose for — no 2200-nn
#: account has been minted, so there is nothing to rule on yet.
GAP_REMITTING_BASIS_SETTING = _remitting_basis_gap(())

GAP_AGING_NEEDS_DUE_DATES = {
    "code": "aging_buckets_need_invoice_due_dates_and_opening_buckets",
    "br_ref": "BR-CUS-048 · BR-LED-016 · BR-REP-008",
    "detail": "a journal line carries no due date, so the Current/31–60/61–90/90+ split cannot "
    "be summed out of the books. BR-CUS-048's imported opening buckets *age forward from the "
    "cutover as-of date* and `account_opening_buckets` (B2 r9 #2) is not built either. The AR "
    "TOTAL the buckets must sum to IS derivable and is reported (`still_owed`), so a screen "
    "can render the total and show the split as unavailable rather than rendering four "
    "confident zeros.",
    "wanted_reads": (
        "apps.billing.selectors.open_invoice_due_dates() -> tuple[tuple[str, date, Decimal], ...]",
        "apps.customers.selectors.opening_buckets_as_of() -> …  # US-CUS-022, GT-16",
    ),
}

# ═══════════════════════════════════════════════════════════════════════════
# Finance blueprint p018 `P5.8` — THE REFERENCE COLUMN'S REMAINING GAP
# ═══════════════════════════════════════════════════════════════════════════
#: The journal `source_type`s that name a DOCUMENT — something printed, posted
#: or handed over, which therefore ought to carry a number a customer could
#: quote back. Everything else the vocabulary knows (`opening_balance`,
#: `adjustment`, `write_off`, a manual entry) is a movement in the books with
#: no document behind it, so an empty Reference on one of those is CORRECT and
#: must never be reported as a gap.
#:
#: ⚠ **THIS LIST IS THE SCREEN'S HALF OF `_DOCUMENT_SOURCES` IN
#: `apps/integrations/seams/ledger.py`, PLUS THE ONE THAT IS STILL MISSING.**
#: The first three resolve today; `refund` is here precisely BECAUSE it cannot,
#: which is what makes a refund row report an absence instead of passing for an
#: opening balance.
DOCUMENT_SOURCE_TYPES: frozenset[str] = frozenset(
    {"invoice", "credit_note", "payment", "refund"}
)

#: Reported ONLY when the page actually holds a document row this product could
#: not name. ⚠ **MEASURED ON THE DEMO TENANT, 2026-09-24, PostgreSQL 16.13:**
#: of 167 posted entries, `invoice` 80 and `payment` 66 and `credit_note` 1
#: resolve to a printed number, 19 `opening_balance` entries are not documents
#: at all, and exactly ONE is a real gap — a `refund`, because `refunds` has no
#: number column of any kind. That number arrives with `P3.3`; nothing here
#: invents one.
GAP_DOCUMENT_HAS_NO_NUMBER = {
    "code": "some_documents_carry_no_printed_number_yet",
    "br_ref": "BR-LED-010 · A14 r2",
    "detail": "a bill, a credit note and a payment each carry a printed number and the "
    "Reference column now shows it. A refund does not have one — `refunds` carries no number "
    "column, so there is nothing to print and nothing is invented; the number arrives with the "
    "refund numbering work. The cell is left empty rather than filled with the internal "
    "identifier, which is what it used to hold.",
    "wanted_reads": ("apps.payments.selectors.refund_numbers_for(ids) -> dict[str, str]",),
}

GAP_TAX_AUTHORITY_NAME = {
    "code": "authority_identity_is_the_gl_account_not_the_jurisdiction_row",
    "br_ref": "BR-BIL-069 · B5 line 74 ❄️",
    "detail": "`journal_lines.tax_authority_id` is NULL on every line — rating publishes no "
    "`tax_authority_id_for_tax` and `apps/billing/posting_seam.py` reports the gap on every "
    "bill. The per-authority SPLIT does not need it: the PO ruled on 2026-08-11 that each "
    "authority has its own account (*For each atheority have separate account and tagging*) "
    "and B5 line 74 ❄️ gives the series, so the 2200-nn account IS the authority in the books. "
    "What is missing is the authority's name AS RATING KNOWS IT; the label reported here is "
    "the ledger account's own name, typed by the tenant when the account was minted.",
    "wanted_reads": (
        "apps.rating.selectors.tax_authority_id_for_tax(tax_id) -> str | None",
    ),
}


def source_vocabulary_for(source_type: str | None) -> tuple[str, bool]:
    """BR-REP-008's word for a `source_type`, and whether it was recognised.

    Returns `(label, mapped)`. An UNKNOWN source_type comes back as itself with
    `mapped=False` rather than as "other" or "adjustment", because BR-REP-008's
    whole point is that the report *foots to the AR tie-out — nothing
    invisible*. A source this module has never heard of is money it must still
    show; bucketing it under a familiar word would hide a new posting contract
    inside an old column and the ledger would foot while the report lied about
    what it was made of.
    """
    if not source_type:
        return ("", False)
    label = SOURCE_TYPE_TO_VOCABULARY.get(source_type)
    if label is None:
        return (str(source_type), False)
    return (label, True)


# ── tenant scope (CLAUDE.md rule 1) ─────────────────────────────────────────
def _tenant_id() -> UUID:
    """No tenant table is READ without `app.tenant_id` either.

    RLS `FORCE` makes this the database's law on Postgres; the explicit filter
    below makes it hold on the SQLite developer database too, where a report
    that ran with no tenant context would happily sum two utilities' books into
    one trial balance.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _posted_lines(
    *,
    start: date | None = None,
    end: date | None = None,
    premises_id: Any = None,
) -> Any:
    """Journal lines of POSTED entries, this tenant's, in the book-date window.

    ⚠ **`premises_id` NARROWS TO THE STAMP AND NEVER JOINS (CR-060 C24).** It
    filters `journal_lines.premises_id`, the value the posting service wrote at
    posting time, for the reason gap 1 in the module header records: a read-time
    account → unit → premises join moves last year's money the day a unit is
    re-assigned, which is the defect US-LED-010 TC-5 exists to catch. A line
    lawfully carrying NO premises — a bank fee, a deposit-batch cash leg — is
    EXCLUDED by this filter rather than counted as unattributed, because the
    caller asked for one property's lines and that line is not one of them.
    **What that costs is stated at each caller, and for the trial balance it is
    the footing itself.**

    `status='posted'` is not a filter, it is the definition of the books.
    BR-LED-003 makes a draft *"worthless until posted"*, so a report that
    included drafts would show a finance officer money that no auditor can see
    and that any clerk can still delete.

    The window is on `journal_entries.entry_date` — the BOOK date — which is
    BR-REP-001's POSTING basis. `posted_at` is the wall-clock moment and is
    deliberately never the filter: LE-9's payment dated Jul 30 and arriving Aug 7
    belongs to whichever period its entry_date says, and a report keyed on
    posted_at would move July's total every time a late entry arrived.
    """
    rows = models.JournalLine.objects.filter(
        tenant_id=_tenant_id(), journal_entry__status=models.JE_POSTED
    )
    if start is not None:
        rows = rows.filter(journal_entry__entry_date__gte=start)
    if end is not None:
        rows = rows.filter(journal_entry__entry_date__lte=end)
    if premises_id is not None:
        rows = rows.filter(premises_id=premises_id)
    return rows


def _designated_account_id(designation: str) -> str | None:
    """The tenant's account for a designation — by NAME, never by number.

    Wrapped rather than called inline so every read in this module goes through
    one place and none of them can drift into `code == "1200"`, which is the
    latent misposting `apps/ledger/chart.py` exists to prevent and OQ-106 was
    raised over.
    """
    return selectors.gl_account_id_for_designation(designation)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-081 — ONE CURRENCY, OR NO NUMBER. THE GUARD EVERY Σ IN THIS FILE ASKS.
# ═══════════════════════════════════════════════════════════════════════════
#: The `journal_entries` column that carries CLAUDE.md rule 2's other half. It
#: is on the ENTRY and not the line (`apps/ledger/models.py`: *"a mixed-currency
#: entry cannot balance, so one currency per entry is what balanced means"*), so
#: a per-line read reaches it through the FK and this constant is the one place
#: that spelling lives.
CURRENCY_FIELD = "journal_entry__currency"

#: The `unavailable` problem code a caller sees when it catches the refusal and
#: chooses to render a reason rather than an error page. Named as a constant
#: because a screen and a test both match on it.
MIXED_CURRENCY_CODE = "the_lines_being_summed_carry_more_than_one_currency"


class MixedCurrencyBook(errors.BizError):
    """Σ is refused: the posted lines under this figure are not one currency.

    **DEF-081, and it is arithmetic before it is policy.** 100 USD + 100 CAD is
    not 200 of anything. It is not a rounding error, not an approximation and
    not a number a human can correct downstream — it is a quantity with no unit,
    exactly as kWh + kgal is (hard rule 3, the same law one column over). Every
    finance screen in this product would then render it beside a currency symbol
    and it would look completely ordinary.

    **Why this became reachable.** `apps/ledger/posting.py` takes `currency` as
    a REQUIRED PER-ENTRY input and defaults nothing, so nothing at the posting
    boundary stops a tenant holding USD and CAD entries side by side. That was
    theoretical while one tenant = one currency held — and DEF-075 is precisely
    the hole that let a tenant with issued bills change its currency at 200 OK.
    Any tenant that did so while that defect was open can hold a mixed book now,
    which is why the guard is here and not merely "prevented upstream".

    **Raised, never returned as a figure.** `ar_control` and `accounts_owing`
    answer with a bare `Decimal` and a bare `int`; there is nowhere in either to
    put a reason, and this module's whole contract is that a figure it cannot
    stand behind is never rendered. So the refusal is an exception and it is a
    CATALOG one — `BIZ_STATE`, which the error handler already turns into a
    409 envelope with `params` naming the codes found. No endpoint had to grow a
    `try` for this and none did.

    **What stays available on purpose:** `journal_entry_list`. It lists entries
    one per row and each row's debit/credit is that ONE entry's own — nothing is
    summed across two currencies there, and it is the only surface on which a
    finance officer can SEE which entries carry the foreign code and go fix
    them. A guard that darkened every ledger screen would leave no way to
    diagnose the state it is complaining about.
    """

    def __init__(self, codes: tuple[str, ...], *, figure: str) -> None:
        self.codes = codes
        self.figure = figure
        #: The same fact in this module's `unavailable` shape, so a caller that
        #: prefers to render a reason in place of a number has one ready-made
        #: and does not compose a second wording of the same finding.
        self.gap = {
            "code": MIXED_CURRENCY_CODE,
            "br_ref": "CLAUDE.md rule 2 · BR-LED-007 · DEF-081",
            "detail": f"{figure} sums posted journal lines whose entries carry "
            f"{len(codes)} different currencies ({', '.join(codes)}). There is no lawful "
            "addition: money is NUMERIC(18,6) *and* CHAR(3), and one code plus a different "
            "code is a number with no name. Refused rather than summed — the sum would be "
            "rendered beside a currency symbol on every finance screen and would look "
            "entirely ordinary. Find the entries on the S56 journal list, which stays "
            "available for exactly this, and correct them with a reversal (hard rule 4: the "
            "correction is new rows, never an edit).",
            "currencies": codes,
            "wanted_reads": (),
        }
        super().__init__(
            errors.BIZ_STATE,
            br_ref="BR-LED-007",
            params={"currencies": ", ".join(codes), "figure": figure},
        )


def currencies_in(rows: Any) -> tuple[str, ...]:
    """The distinct CHAR(3) codes the entries behind `rows` carry, sorted.

    Public because the same question is worth asking from outside — a one-off
    sweep of live tenants (`10-scripts/def081_currency_sweep.py`) asks it, and a
    screen may want to name the codes without triggering the refusal.
    """
    return tuple(
        sorted(
            {
                str(code)
                for code in rows.values_list(CURRENCY_FIELD, flat=True).distinct()
                if code
            }
        )
    )


def _one_currency(rows: Any, *, figure: str) -> str | None:
    """The single currency of `rows`, or the refusal — asked BEFORE any Σ.

    **The guard is over exactly the lines the caller is about to add**, never
    over the tenant's whole book, and that is deliberate in both directions:

      * a tenant with one stray CAD entry in March can still be shown a correct
        February trial balance, because February's lines are all USD;
      * and a per-ACCOUNT report (`account_ledger`) is not refused because some
        OTHER customer's account holds the foreign entries.

    `None` — no posted lines at all — is not a refusal. An empty book has no
    currency and no total to get wrong; the figure is 0.00 and always was.
    """
    codes = currencies_in(rows)
    if len(codes) > 1:
        raise MixedCurrencyBook(codes, figure=figure)
    return codes[0] if codes else None


# ═══════════════════════════════════════════════════════════════════════════
# THE PRIMITIVE — Σ per GL account. Everything else is this, grouped.
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class GlTotal:
    """One GL account's debit and credit totals for a window.

    BOTH sides are kept un-netted. A same-account transfer (LE-1's master
    transfer moves 135.90 between two AR accounts) writes a debit AND a credit
    to `1200`; netting at this level would report it as nothing happening, and
    the trial balance's own footer needs the gross sides to foot at all.
    """

    account_id: str
    code: str
    name: str
    type: str
    debit: Decimal
    credit: Decimal
    #: The CHAR(3) these totals ARE, DERIVED from the entries summed — not the
    #: tenant's declared code (DEF-081: *the API layer labels each figure with
    #: the TENANT's declared CHAR(3), which is a LABEL, not a derivation*). None
    #: only when nothing posted. A default keeps every existing constructor call
    #: valid; the one in this module always passes it.
    currency: str | None = None

    @property
    def net_debit(self) -> Decimal:
        return self.debit - self.credit

    @property
    def net_credit(self) -> Decimal:
        return self.credit - self.debit


def gl_totals(
    *,
    start: date | None = None,
    end: date | None = None,
    source_types: tuple[str, ...] = (),
    premises_id: Any = None,
) -> tuple[GlTotal, ...]:
    """Σ `journal_lines` per `ledger_accounts` row, ordered by code.

    **THE derivation.** US-LED-008's S56 trial balance must consume this rather
    than write its own — one implementation of "what is in account 1200", so a
    screen and a KPI can never disagree. `source_types` narrows to entries from
    named sources, which is what makes "billed" (invoice-sourced AR debits)
    expressible without a second query shape.

    **DEF-081: it asks `_one_currency` before it adds anything.** This is THE
    derivation, so a guard here covers every figure built on it; the callers ask
    again over their own narrower row sets, which is not redundant — each one
    sums a different slice and each slice must be one currency in its own right.

    **`premises_id` NARROWS THE SAME DERIVATION AND DOES NOT FORK IT (C24).**
    BR-REP-002's whole point is one query grouped differently, so a property
    filter is an argument here and never a second function: a screen filtering
    by property and a screen not filtering by property read the same code, and
    the two cannot drift into disagreeing about what account 1200 holds.
    """
    rows = _posted_lines(start=start, end=end, premises_id=premises_id)
    if source_types:
        rows = rows.filter(journal_entry__source_type__in=source_types)
    currency = _one_currency(rows, figure="the GL account totals")
    buckets: dict[str, dict[str, Any]] = {}
    for account_id, code, name, type_, side, amount in rows.values_list(
        "ledger_account_id",
        "ledger_account__code",
        "ledger_account__name",
        "ledger_account__type",
        "side",
        "amount",
    ):
        bucket = buckets.setdefault(
            str(account_id),
            {
                "code": code,
                "name": name,
                "type": type_,
                models.SIDE_DEBIT: ZERO,
                models.SIDE_CREDIT: ZERO,
            },
        )
        bucket[side] += amount
    return tuple(
        GlTotal(
            account_id=account_id,
            code=bucket["code"],
            name=bucket["name"],
            type=bucket["type"],
            debit=bucket[models.SIDE_DEBIT],
            credit=bucket[models.SIDE_CREDIT],
            currency=currency,
        )
        for account_id, bucket in sorted(
            buckets.items(), key=lambda item: item[1]["code"]
        )
    )


def _opening_balances(
    *, start: date | None, premises_id: Any = None
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Every account's NET DEBIT position on the day before `start`.

    ⚠ **`premises_id` MUST BE PASSED HERE WHENEVER IT IS PASSED TO THE MOVEMENT,
    AND FORGETTING IT IS A MONEY ERROR OF THE SAME FAMILY AS THE OFF-BY-ONE
    BELOW (CR-060 C24).** The opening column exists to make
    `opening + movement = closing` hold per account. Narrow the movement to one
    property and leave the opening at the whole book and that identity breaks on
    every account the property ever touched — the screen would show a property's
    month opening with the entire utility's position. Both halves read the same
    stamp or neither does.

    **CR-060 C4.** *"Every accountant reads a trial balance as
    position-then-movement-then-position; without the opening column they cannot
    tie this month to last month's signed statement without exporting."*

    ⚠ **THE WINDOW IS STRICTLY BEFORE `start`, AND THE OFF-BY-ONE HERE IS A
    MONEY ERROR RATHER THAN A ROUNDING ONE.** `_posted_lines(end=X)` filters
    `entry_date__lte=X`, so the opening query asks for `start - 1 day`. Passing
    `start` itself would count the first day of the period TWICE — once in the
    opening position and once again in the movement — and every account that
    posted on the 1st would fail `opening + movement = closing` by exactly that
    day's activity, which is the one identity this column exists to give a
    bookkeeper.

    **A CUMULATIVE TRIAL BALANCE HAS NO OPENING AND THAT IS ZERO, NOT NULL.**
    `start=None` is the all-time position (the form that makes the AR row equal
    S36's *Still owed*), so there is nothing before it: the caller reads a
    missing account out of this dict as `ZERO`. C4's own proof says so —
    *"opening on a fresh chart is ZERO, not null"* — and a null there would
    render as an absence on a screen whose whole job is to state a position.

    **THE CURRENCY GUARD IS ASKED OVER THESE LINES IN THEIR OWN RIGHT** (DEF-081,
    and `_one_currency`'s own docstring says why each slice must be asked
    separately). An opening balance summed across two currencies is a false
    statement about what an account held on the first of the month, and it is
    the figure last month's signed statement is about to be compared against.
    """
    if start is None:
        return {}, None
    rows = _posted_lines(end=start - timedelta(days=1), premises_id=premises_id)
    currency = _one_currency(rows, figure="the opening balances")
    buckets: dict[str, dict[str, Any]] = {}
    for account_id, code, name, type_, side, amount in rows.values_list(
        "ledger_account_id",
        "ledger_account__code",
        "ledger_account__name",
        "ledger_account__type",
        "side",
        "amount",
    ):
        bucket = buckets.setdefault(
            str(account_id),
            {"code": code, "name": name, "type": type_, "net": ZERO},
        )
        bucket["net"] += amount if side == models.SIDE_DEBIT else -amount
    return buckets, currency


def _former_codes(account_ids: set[str]) -> dict[str, str]:
    """`{account id: the code before its latest change}` — `CR-196-BRC10`.

    Only accounts whose code has changed appear. Read from the account's own
    `code_history`, never from `audit_log`, which is pruned (OQ-1340).
    """
    if not account_ids:
        return {}
    answer: dict[str, str] = {}
    for pk, history in models.LedgerAccount.objects.filter(
        tenant_id=_tenant_id(), pk__in=account_ids
    ).values_list("pk", "code_history"):
        if history:
            answer[str(pk)] = history[-1].get("old_code")
    return answer


def trial_balance(
    *,
    start: date | None = None,
    end: date | None = None,
    premises_id: Any = None,
) -> dict[str, Any]:
    """The period's trial balance, and whether it FOOTS.

    ⚠ **`premises_id` NARROWS EVERY COLUMN, INCLUDING THE OPENING, AND TURNS
    `balanced` INTO `null` (CR-060 C24).** Read
    `GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT` for the whole argument, including
    the measurement that corrected its first draft. The short form: balance is a
    property of an ENTRY, a narrowed table holds only some of each entry's
    lines, and although most narrowed tables DO foot, a mismatch is
    indistinguishable from BR-LED-007's posting-service bypass. So neither
    `true` nor `false` is a statement this module can stand behind here.

    **The opening column is narrowed by the SAME filter**, because C4's identity
    `opening + movement = closing` is per account and would otherwise compare one
    property's month against the whole utility's position.

    LE-1 verbatim: *"Totals 598.69 | 598.69 ✔"*. `balanced` is asserted here
    rather than assumed, and it is the anchor every other figure in this module
    ties to — constraint of the lane and of BR-LED-007 both: if a report and the
    posted books disagree by a cent, the arithmetic is the finding.

    **EACH ROW CARRIES ITS ACCOUNT'S NET BALANCE, ON ONE SIDE.** That is what a
    trial balance IS, and LE-1 is the proof: the AR account took 734.59 of
    debits and 582.27 of credits in the month, and LE-1's table shows one figure
    — *"1200 AR | 152.32"* — in the debit column. Footing the GROSS sides
    instead would total 1334.46 = 1334.46: true, balanced, and not the signed
    number. Both views come from the same `gl_totals` rows, so there is still
    exactly one derivation; only the presentation differs, and the gross sides
    stay reachable for the callers that need them (a same-account transfer wrote
    two rows and nets to nothing).

    A zero-net account is KEPT rather than filtered out — LE-1 lists *"2300
    Deposit liability (150.00 + 3.50 − 153.50) | 0.00"*, and an account that
    took money and gave it all back is a line a finance officer expects to see.

    **It cannot be "fixed" here.** An unbalanced period can only mean a
    posting-service bypass (BR-LED-007), and this function's job is to say so
    with the delta, never to plug it. There is no client-side rebalancing
    anywhere in EP-LED-03 and US-LED-008 TC-5 exists to keep it that way.
    """
    rows = gl_totals(start=start, end=end, premises_id=premises_id)
    opening_by_account, opening_currency = _opening_balances(start=start, premises_id=premises_id)
    presented = []
    debits = ZERO
    credits = ZERO
    opening_total = ZERO
    closing_total = ZERO
    moved: set[str] = set()
    for row in rows:
        net = row.net_debit
        debit_side = net if net > ZERO else ZERO
        credit_side = -net if net < ZERO else ZERO
        debits += debit_side
        credits += credit_side
        opening = opening_by_account.get(str(row.account_id), {}).get("net", ZERO)
        closing = opening + net
        opening_total += opening
        closing_total += closing
        moved.add(str(row.account_id))
        presented.append(
            {
                "account_id": row.account_id,
                "code": row.code,
                "name": row.name,
                "type": row.type,
                "debit": debit_side,
                "credit": credit_side,
                "gross_debit": row.debit,
                "gross_credit": row.credit,
                # CR-060 C4 — position · movement · position, per account.
                "opening": opening,
                "closing": closing,
            }
        )
    # ⚠ **AN ACCOUNT THAT HELD MONEY ON THE 1st AND MOVED NOT AT ALL IS STILL ON
    #   THIS REPORT, AND LEAVING IT OFF WOULD BE THE DEFECT C4 IS FIXING.**
    #   `gl_totals` buckets the lines INSIDE the window, so before the opening
    #   column existed an untouched account was correctly invisible — it has no
    #   movement to show. With an opening column, invisible means *"this account
    #   holds nothing"*, which is a claim about a BALANCE rather than about
    #   activity: a 2300 deposit liability carrying 4,000.00 into a quiet month
    #   would vanish from the one report an auditor ties to last month's signed
    #   statement. So the row set is the UNION of moved and open, and the two
    #   movement columns read 0.00 for the half that did not move.
    for account_id, bucket in opening_by_account.items():
        if account_id in moved or bucket["net"] == ZERO:
            continue
        opening_total += bucket["net"]
        closing_total += bucket["net"]
        presented.append(
            {
                "account_id": account_id,
                "code": bucket["code"],
                "name": bucket["name"],
                "type": bucket["type"],
                "debit": ZERO,
                "credit": ZERO,
                "gross_debit": ZERO,
                "gross_credit": ZERO,
                "opening": bucket["net"],
                "closing": bucket["net"],
            }
        )
    # One order for the whole table, `gl_totals`' own (by code). A report whose
    # opening-only rows landed in a block at the bottom would read as a second
    # table nobody asked for.
    presented.sort(key=lambda entry: entry["code"] or "")
    # CR-196-BRC10 Q1 A (PO 2026-10-29) — *"the Sep GL report shows the new code
    # '(formerly 4150)'"*. The code itself is already the new one (every line
    # reaches it through the account id); this adds the code it carried before
    # its latest change, read from the account in ONE query, and nothing else.
    former = _former_codes({str(entry["account_id"]) for entry in presented})
    for entry in presented:
        entry["former_code"] = former.get(str(entry["account_id"]))
    return {
        "basis": BASIS_POSTING,
        "period": {"start": start, "end": end},
        # DEF-081 — the CHAR(3) these totals actually are, derived from the
        # entries summed. `gl_totals` already refused a mixed window before this
        # line ran, so every row agrees and one code describes the whole table.
        # None means the window posted nothing, which is a real answer.
        #
        # ⚠ The OPENING slice answers when the window itself is empty: a month
        # in which nothing posted still has positions carried into it, and
        # labelling those `None` would strip the currency off the only figures
        # on the report.
        "currency": rows[0].currency if rows else opening_currency,
        "rows": tuple(presented),
        "total_debit": debits,
        "total_credit": credits,
        # CR-060 C4's identity, FOOTED rather than asserted: Σ opening +
        # (total_debit − total_credit) = Σ closing, and it holds row by row too.
        "total_opening": opening_total,
        "total_closing": closing_total,
        "difference": debits - credits,
        # ⚠ CR-060 C24 — `None`, never `False`, on a narrowed table. See
        # GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT: balance is a property of an
        # ENTRY, a property filter takes a SUBSET of each entry's lines, and
        # `False` here is BR-LED-007's posting-service bypass.
        "balanced": None if premises_id is not None else debits == credits,
        # The property this table was narrowed to, echoed so a screen renders
        # what it actually asked for rather than what it believes it asked for.
        "premises_id": str(premises_id) if premises_id is not None else None,
        "unavailable": (
            (GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT,) if premises_id is not None else ()
        ),
    }


def ar_control(*, as_of: date | None = None) -> Decimal:
    """The AR control total — Σ debits − credits on the `accounts_receivable`
    account, all time up to `as_of`.

    US-LED-004's tie-out panel compares THIS against Σ account balances
    (BR-LED-007: *"AR GL = Σ account balances; ANY drift = red flag"*). Published
    here so the panel has one number to compare and does not grow a second
    derivation of "the AR GL".

    Cumulative, never period-scoped: what a utility is owed is every unpaid
    charge ever made, not this month's movement. LE-1's **152.32** is exactly
    that — 45.00 + 553.69 + 135.90 debits against 153.50 + 135.90 + 292.87
    credits.

    **DEF-081 — this one RAISES and cannot do anything else.** It answers with a
    bare `Decimal`, so there is no slot for a reason and no honest value to
    return: an AR control total summed across two currencies is the single
    figure BR-LED-007's tie-out compares the whole customer register against, so
    a wrong one here reports drift that is not there or hides drift that is.
    """
    account_id = _designated_account_id(chart.AR)
    if account_id is None:
        return ZERO
    rows = _posted_lines(end=as_of).filter(ledger_account_id=account_id)
    _one_currency(rows, figure="the AR control total")
    total = ZERO
    for side, amount in rows.values_list("side", "amount"):
        total += amount if side == models.SIDE_DEBIT else -amount
    return total


def cash_position(
    *, start: date | None = None, end: date | None = None
) -> dict[str, Any]:
    """Realised cash and undeposited cash — SEPARATELY, and never summed.

    PO ruling 2026-08-11 closing OQ-143, verbatim: *"Cash is received but
    undeposted in such case payment will say csah but ledger will say
    undeposited - until bank record and reconcilaition confirm it it is not
    realised."*

    `realised` is Σ movement on the **cash** designation (1000) — money the bank
    has confirmed, because `apps/payments/reconciliation.py` is the only thing
    that debits it for a customer receipt. `undeposited` is Σ movement on
    **undeposited_funds** (1010) — money a clerk keyed and nobody has banked.

    They are returned as two keys and there is no third key adding them up. A
    cash-basis report that counted the second as cash would tell a utility it
    has money in the bank that is sitting in a drawer, and would do it in the
    one report an auditor reads first.
    """

    def _net(designation: str) -> Decimal:
        account_id = _designated_account_id(designation)
        if account_id is None:
            return ZERO
        rows = _posted_lines(start=start, end=end).filter(ledger_account_id=account_id)
        # DEF-081 — per DESIGNATION, because the two are reported separately and
        # a tenant could hold a clean USD 1000 Cash beside a mixed 1010.
        _one_currency(rows, figure=f"the {designation} cash position")
        total = ZERO
        for side, amount in rows.values_list("side", "amount"):
            total += amount if side == models.SIDE_DEBIT else -amount
        return total

    return {
        "basis": BASIS_CLEARING,
        "currency": _one_currency(
            _posted_lines(start=start, end=end), figure="the cash position"
        ),
        "realised": _net(chart.CASH),
        "undeposited": _net(chart.UNDEPOSITED_FUNDS),
        "note": "PO 2026-08-11 (OQ-143): undeposited money is NOT realised until the bank "
        "record and reconciliation confirm it. These two are never added together.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-007 — S36 Revenue & AR
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ServiceRevenueRow:
    """One row of the S36 *Revenue by service* table (LE-2's slice).

    `usage` and `base_and_fees` split on WHICH ACCOUNT the money landed in —
    the tenant's `revenue_account` vs `base_revenue_account` for that service
    (BR-BIL-010's optional split, resolved through
    `apps/ledger/selectors.revenue_account_id_for_service`). Not on a line
    "kind": a kind is billing's vocabulary and the journal does not carry it.

    `tax` and `collected` are None with a reason on the result — tax lines carry
    no `service` dimension and cash carries no invoice attribution. LE-2 states
    the revenue slice and states no per-service tax, which is consistent: the
    signed example does not claim the split this module cannot make.
    """

    service_id: str | None
    service_code: str | None
    usage: Decimal
    base_and_fees: Decimal
    total_billed: Decimal


def revenue_by_service(
    *, start: date, end: date, include_enabled_zero_rows: bool = False
) -> tuple[ServiceRevenueRow, ...]:
    """Revenue lines of the period, grouped by the `service` dimension (LE-2).

    LE-2 verbatim: *"WE-1 alone: Electric 100.60 (usage 88.60 + base 12.00) ·
    Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar capacity 40.00 · Late fee
    5.00 = 226.90 ✔. Same query grouped by premises → LE-6; by authority → LE-3.
    One dimension set, every slice."* This is that query.

    **Rows with `service_id=None` are KEPT and labelled None, not dropped.**
    `apps/billing/posting_seam.PostingBucket` carries a service only when every
    line in the bucket agrees on one (two services mapped by their tenant to one
    revenue account produce a bucket that names none), and a late fee is charged
    to an ACCOUNT rather than to a service. Dropping those rows would make the
    table foot to less than the period's revenue — the exact silent shortfall
    BR-REP-002 is about.

    ⚠ **`include_enabled_zero_rows` DRAWS EVERY SERVICE THE TENANT SELLS, EVEN
    ONE THAT BILLED NOTHING (`DEF-LED-6718`).** Product Owner, on deployed
    v2.351.84: *"revenue by services is not shown - we should show revenue for
    all active utility services."* They were looking at a Services table holding
    ONE row — the unnamed bucket — and read it as a broken screen.

    This function groups MOVEMENT, so a service with none has no group and
    therefore no row, and *"this service billed nothing"* and *"this tenant does
    not sell this service"* arrive on the wire as the same silence. With the
    flag, the tenant's ENABLED set (`tenancy_seam.enabled_service_codes`, the
    same read the chart seed is built from — never a literal list, which is
    hard-won law 2's eleventh service) is unioned in at `0`, and the two facts
    become distinguishable.

    **It is OPT-IN and defaults to False on purpose.** Two other callers read
    this function — `apps/ledger/finance_exports` (the by-service CSV extract)
    and the dashboard's service mix — and neither asked for zero rows.
    Zero-filling them too would change a CSV somebody reconciles and a chart's
    slice count on one screen's authority. `revenue_and_ar` passes True;
    changing the others is their own decision with their own reporter.

    ⚠ **IT ADDS ROWS AND MOVES NO FIGURE.** A zero row sums to zero, so the
    period's revenue is identical with the flag and without it — which is what
    makes it safe to hand to the S36 table whose Total is now summed from its
    own rows (`DEF-LED-6717`).
    """
    # ⚠ **`type__in`, NOT `type="revenue"` — AND THAT IS THE WHOLE OF CR-061's
    # COST IN THIS MODULE (PO ruling 2026-09-01, *"no, you cannot file discount
    # under revenue"*).**
    #
    # This line read `ledger_account__type="revenue"` until that ruling, and it
    # was correct then for a reason that stopped being true the moment the
    # discount account was re-typed: `4300 Customer discounts` WAS a revenue
    # account, so its DEBIT was picked up here and correctly reduced the
    # reported figure. Re-file it as `contra_revenue` and leave this literal
    # alone and the line simply leaves the query — **the S36 revenue table, the
    # *Revenue by service and rate* report and the dashboard's service mix all
    # report 100.58 where the books hold 90.58 on the frozen GT-1 bill with a
    # 10.00 discount.** Ten dollars of revenue the utility never earned, on a
    # journal entry that did not move by a cent, and no gate in this repo would
    # have said a word.
    #
    # **THIS IS THE ONLY PLACE IN THE PRODUCT THAT FILTERS ON AN ACCOUNT TYPE
    # RATHER THAN PRINTING ONE**, measured across `apps/` for CR-061: `gl_totals`,
    # `trial_balance`, the accounting export, `finance_api` and the chart list
    # all carry the string through as a LABEL and do no arithmetic with it, so a
    # new type value shows up in them and changes no figure. The tuple is
    # declared in `models` beside the vocabulary itself, so that adding a seventh
    # type puts this question in front of whoever adds it.
    #
    # **THE SIGN NEEDS NO SPECIAL CASE and must not grow one.** Two lines below,
    # `signed` is `+amount` on a credit and `-amount` on a debit — which is
    # already exactly right for contra-revenue, because a contra-revenue account
    # carries a debit balance and a debit here is a reduction. A branch on
    # `type` would be a second implementation of a rule the SIDE already states.
    revenue_lines = _posted_lines(start=start, end=end).filter(
        ledger_account__type__in=models.REVENUE_REPORTING_TYPES
    )
    # DEF-081 — a revenue table that added USD sales to CAD sales would show a
    # utility a service line it never earned, per service, and foot perfectly.
    _one_currency(revenue_lines, figure="revenue by service")
    movements: dict[tuple[str | None, str | None], list[tuple[str, Decimal]]] = {}
    for service_id, service_code, account_id, side, amount in revenue_lines.values_list(
        "service_id", "service__code", "ledger_account_id", "side", "amount"
    ):
        key = (str(service_id) if service_id else None, service_code)
        signed = amount if side == models.SIDE_CREDIT else -amount
        movements.setdefault(key, []).append((str(account_id), signed))

    out: list[ServiceRevenueRow] = []
    for (service_id, service_code), entries in movements.items():
        # The usage/base split resolves ONCE per service, from the TENANT's own
        # pointer (`tenant_services.revenue_account` / `.base_revenue_account`),
        # never from the chart's default — a tenant may re-point either (PO
        # 2026-08-11, OQ-115). `base=True` FALLS BACK to the usage account when
        # the chart has no split (BR-BIL-010: Sewer, Trash, Gas and Broadband
        # carry one account each), so the two ids can be equal — in which case
        # every cent is usage revenue and there is nothing to split.
        base_account_id = (
            selectors.revenue_account_id_for_service(service_code, base=True)
            if service_code
            else None
        )
        usage_account_id = (
            selectors.revenue_account_id_for_service(service_code, base=False)
            if service_code
            else None
        )
        split_exists = bool(base_account_id) and base_account_id != usage_account_id
        usage = ZERO
        base = ZERO
        for account_id, signed in entries:
            if split_exists and account_id == base_account_id:
                base += signed
            else:
                usage += signed
        out.append(
            ServiceRevenueRow(
                service_id=service_id,
                service_code=service_code,
                usage=usage,
                base_and_fees=base,
                total_billed=usage + base,
            )
        )
    if include_enabled_zero_rows:
        seen = {row.service_code for row in out if row.service_code is not None}
        for code in tenancy_seam.enabled_service_codes():
            if code in seen:
                continue
            out.append(
                ServiceRevenueRow(
                    # The catalog id, so a zero row carries the SAME identity a
                    # row with movement carries and nothing but the figures
                    # tells them apart. `None` when the catalog has no such
                    # code — a tenancy fault, not a reason to drop the service
                    # off a screen that is supposed to list what is sold.
                    service_id=tenancy_seam.service_id_for_code(code),
                    service_code=code,
                    usage=ZERO,
                    base_and_fees=ZERO,
                    total_billed=ZERO,
                )
            )
    return tuple(
        sorted(out, key=lambda row: (row.service_code or "~", row.service_id or ""))
    )


def revenue_and_ar(
    *, start: date, end: date, ytd_start: date | None = None
) -> dict[str, Any]:
    """S36's KPI strip and panels, entirely out of journal-line dimensions.

    BR-LED-016: *"S36 KPI strip: revenue, collected, AR, aging buckets — all
    dimension-derived."* Every figure below is a sum over posted journal lines;
    NONE of them is a query over `invoices`, `payments` or `accounts.balance`.
    US-LED-007 TC-5 is precisely the test that a cache figure can never render
    here: there is no code path in this module that reads one.

    Worked against LE-1 / US-LED-007 §7, so the numbers are concrete:

        billed          553.69   Σ AR debits from invoice-sourced entries
                                 (247.87 + 16.42 + 289.40)
        collected_cash  446.37   Σ AR credits from cash + deposit application
                                 (292.87 payment + 153.50 deposit) — LE-6's
                                 own KPI strip figure
        collection_pct  None     BR-REP-009 wants 401.37 ÷ 553.69 = 72.49%, and
                                 the 401.37 needs the allocations read
        still_owed      152.32   the AR control total = the tie-out figure
        written_off     0.00     Σ debits to the write_off designation; nothing
                                 posts a write-off yet and the honest answer to
                                 "how much was written off" is zero, not absent

    `ytd_start` is the fiscal year's first day for the *Written off YTD* KPI.
    It is an INPUT because periods are COMPUTED from fiscal settings and never
    stored (BR-TEN-022), and this module may not guess a tenant's fiscal year.
    """
    # DEF-081, asked ONCE for the strip's whole window before any figure is
    # summed. Every KPI below is a subset of these lines, so one currency here
    # means one currency in each of them — and the code that comes back is what
    # the strip's amounts ARE, published on the result so the API can stop
    # LABELLING them with the tenant's declared code and start reading the
    # derived one. `ar_control` and `accounts_owing` are cumulative rather than
    # windowed and ask their own, wider question for themselves.
    currency = _one_currency(
        _posted_lines(start=start, end=end), figure="the Revenue & AR KPI strip"
    )

    ar_account_id = _designated_account_id(chart.AR)
    deposit_account_id = _designated_account_id(chart.DEPOSIT_LIABILITY)
    write_off_account_id = _designated_account_id(chart.WRITE_OFF)

    billed = ZERO
    collected_cash = ZERO
    deposit_applied = ZERO
    if ar_account_id is not None:
        ar_rows = _posted_lines(start=start, end=end).filter(
            ledger_account_id=ar_account_id
        )
        for side, amount, entry_source in ar_rows.values_list(
            "side", "amount", "journal_entry__source_type"
        ):
            if side == models.SIDE_DEBIT and entry_source in BILL_SOURCE_TYPES:
                billed += amount
            elif side == models.SIDE_CREDIT and entry_source in CASH_SOURCE_TYPES:
                collected_cash += amount
        # A deposit APPLICATION (BR-BIL-013) credits AR under the invoice's own
        # source_type, so it cannot be told apart by source. It is identified by
        # its OTHER leg: the deposit liability being debited in the same entry.
        # BR-REP-009 is explicit that *applied deposits count as collected*.
        if deposit_account_id is not None:
            application_entries = set(
                _posted_lines(start=start, end=end)
                .filter(ledger_account_id=deposit_account_id, side=models.SIDE_DEBIT)
                .values_list("journal_entry_id", flat=True)
            )
            if application_entries:
                for amount in (
                    _posted_lines(start=start, end=end)
                    .filter(
                        ledger_account_id=ar_account_id,
                        side=models.SIDE_CREDIT,
                        journal_entry_id__in=application_entries,
                    )
                    .values_list("amount", flat=True)
                ):
                    deposit_applied += amount

    written_off = ZERO
    if write_off_account_id is not None:
        # Its own window (`ytd_start`..`end`) is WIDER than the strip's, so it
        # asks its own DEF-081 question rather than borrowing the answer above.
        write_off_rows = _posted_lines(start=ytd_start, end=end).filter(
            ledger_account_id=write_off_account_id
        )
        _one_currency(write_off_rows, figure="written off year-to-date")
        for side, amount in write_off_rows.values_list("side", "amount"):
            written_off += amount if side == models.SIDE_DEBIT else -amount

    still_owed = ar_control(as_of=end)
    return {
        "basis": BASIS_POSTING,
        "period": {"start": start, "end": end},
        "currency": currency,
        "kpis": {
            "billed": billed,
            # LE-6's own KPI-strip figure: *"collected 446.37 (292.87 +
            # 153.50)"*. The COLUMN, which is total cash landed against AR.
            "collected": collected_cash + deposit_applied,
            "collected_from_cash": collected_cash,
            "collected_from_applied_deposits": deposit_applied,
            # BR-REP-009's percentage needs the period attribution the books do
            # not hold. None, with the reason on `unavailable` — never
            # collected ÷ billed, which would be a DIFFERENT ratio wearing the
            # ruled one's name (446.37 ÷ 553.69 = 80.62%, not 72.49%).
            "collection_pct": None,
            "still_owed": still_owed,
            "accounts_owing": accounts_owing(as_of=end),
            "dso": None,
            "written_off_ytd": written_off,
        },
        # `DEF-LED-6718` — S36 draws every ACTIVE service, zero-filled, so a
        # quiet month reads as a quiet month and not as a broken screen.
        "revenue_by_service": revenue_by_service(
            start=start, end=end, include_enabled_zero_rows=True
        ),
        "aging": None,
        "cash": cash_position(start=start, end=end),
        "adjustments": adjustments_panel(start=start, end=end),
        "tie_out": {"ar_control": still_owed, "computed_by": "US-LED-004 (not built)"},
        "unavailable": (
            GAP_ALLOCATION_PERIOD,
            GAP_AGING_NEEDS_DUE_DATES,
            {
                "code": "dso_needs_twelve_months_of_billed",
                "br_ref": "BR-REP-011",
                "detail": "DSO = (AR ÷ billed last 12 months) × 365, rolling, posting basis. "
                "The formula is derivable from this module — `revenue_and_ar` over a "
                "twelve-month window gives the denominator — and it is left None rather than "
                "computed off a PARTIAL history: a tenant three months into the product would "
                "get a DSO computed on three months and labelled as twelve, which reads as a "
                "collections crisis that is not happening. The caller supplies the window it "
                "actually has, or the KPI stays blank.",
                "wanted_reads": (),
            },
            {
                "code": "per_service_tax_and_collected_columns",
                "br_ref": "BR-LED-001 · BR-REP-009",
                "detail": "the prototype's Revenue-by-service table has Tax and Collected "
                "columns. A tax line carries no `service` dimension (tax is owed to an "
                "AUTHORITY, and BR-BIL-069 gives it its own account, not a service), and cash "
                "carries no invoice attribution — so neither column can be summed out of the "
                "books. LE-2 states the revenue slice and states no per-service tax, which is "
                "the signed example agreeing with the schema.",
                "wanted_reads": (),
            },
        ),
    }


#: What a caller sees instead of a figure when this tenant has designated no AR
#: account. **Not zero.** A tenant with no `accounts_receivable` designation has
#: a book that cannot be asked what anybody owes, which is a different sentence
#: from "nobody owes anything" and has a different fix (one chart edit on S56).
#: DEF-127 is what the other reading costs: a customer owing 108.88 was told
#: 0.00 on the account screen because the number came from somewhere that had
#: never been filled and answered zero rather than refusing.
GAP_NO_AR_DESIGNATION = {
    "code": "no_account_carries_the_accounts_receivable_designation",
    "br_ref": "BR-BIL-010 · BR-LED-007 · OQ-106",
    "detail": "this tenant has designated no AR account, so the books hold no receivable and "
    "cannot say what any customer owes. Reported rather than answered 0.00: a plausible zero "
    "on an account screen tells a customer in arrears that they are square (DEF-127). One "
    "chart edit on S56 fixes it; nothing here picks an account by number "
    "(apps/ledger/chart.py — *code reads the DESIGNATION, never the NUMBER*).",
    "wanted_reads": (),
}


def ar_positions(
    *, account_ids: Any = None, as_of: date | None = None, with_held_credit: bool = False
) -> dict[str, Any]:
    """WHAT EACH CUSTOMER ACCOUNT STILL OWES — Σ over the AR account, per account.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-127 — THE FIGURE NO SURFACE IN THE PRODUCT COULD STATE          ║
    ╚══════════════════════════════════════════════════════════════════════╝
    On 2026-08-15 a browser measured account `E2E-10001` holding an ISSUED,
    UNPAID bill of **108.88**. The books agreed — `1200 AR` debit **108.880000**
    — and `GET /finance/revenue-ar` answered `still_owed 108.880000`. `GET
    /accounts` answered `balance 0.000000`, because customers served
    `accounts.balance`, a CACHE (BR-CUS-015) that **nothing in this product has
    ever written**. So the S17 header read *Outstanding $0.00* and the row read
    *$0.00*, and a customer who owed money was told they owed nothing.

    The fix is not to start writing the cache. It is this function: the
    per-account slice of the SAME Σ `ar_control` publishes as the tie-out total,
    so the account row, the account header and the finance KPI are one
    derivation grouped three ways and CANNOT disagree. BR-REP-002 states the law
    — *"read-models over journal-line dimensions … never a side-maintained
    number"* — and a side-maintained number nobody maintains is its worst case.

    **THIS IS THE DERIVATION `accounts_owing` COUNTS**, and that is why that
    function now calls this one rather than repeating the loop. Two copies of
    "what this account owes" is the failure this whole module exists to prevent,
    and having them inside one file would be no better than having them in two.

    `account_ids` narrows to the accounts a caller is about to render (an S17
    page), which is also what scopes the DEF-081 currency question to exactly
    the lines being added. `None` means every account with an AR line, which is
    what `accounts_owing` asks.

    **AN ACCOUNT WITH NO AR LINE IS ABSENT FROM `positions`, AND THAT IS 0.00.**
    Once the tenant HAS an AR account, "nothing was ever posted for this
    customer" is a real, derived answer. What is NOT an answer is the case above
    it: no AR designation at all ⇒ `available=False`, `positions` is EMPTY and
    the caller must say it cannot tell. `GAP_NO_AR_DESIGNATION` carries the
    reason. A caller that reads an empty dict as zeros re-opens DEF-127; the
    flag is there so it does not have to guess which of the two it is holding.

    Money moves DEBIT-POSITIVE, exactly as `ar_control` and `account_ledger`
    both already read it: a charge raises what is owed, a payment lowers it, and
    a credit balance is a NEGATIVE position rather than a missing one.

    ⚠ **`with_held_credit=True` ADDS `2400 Customer credit balances` TO THE SAME
    Σ, PER ACCOUNT — `DEF-PAY-10707`, 2026-10-30.** Money paid beyond the bill
    is booked DR undeposited / CR 1200 for what met bills / **CR 2400 for the
    rest** (`payments.ledger_seam`, BR-PAY-012), so the 1200 slice alone reads
    a customer who paid **$170.00 on $165.00** as **0.00** — true of the
    receivable and false of the account, which is **$5.00 in credit**. The
    account screen asked the receivable and showed the clerk nothing to refund.
    With the flag the answer is **−5.0000**: the account's net position in the
    books, signed, negative meaning the utility holds the customer's money.
    It is the ledger's figure on purpose rather than payments' subledger credit
    subtracted from it: `credit.apply_credit_at_issue` re-points a carried credit
    onto a new bill and posts nothing, so after it the 2400 line still holds the
    $5.00 the subledger says is spent — 1200 + 2400 is right in BOTH states,
    1200 − subledger credit would double-count it. A deposit is never in it:
    a deposit-purpose payment credits `deposit_liability`, not 2400
    (US-PAY-002 TC-1). **OFF BY DEFAULT**: `ar_control`'s tie-out,
    `accounts_owing` and the debtor counts ask about the RECEIVABLE and must not
    move. A tenant with no 2400 designation reads the AR slice alone — nothing
    was ever credited there, so there is nothing to add.
    """
    ar_account_id = _designated_account_id(chart.AR)
    if ar_account_id is None:
        return {
            "basis": BASIS_POSTING,
            "as_of": as_of,
            "currency": None,
            "positions": {},
            "available": False,
            "unavailable": (GAP_NO_AR_DESIGNATION,),
        }
    ledger_account_ids = [ar_account_id]
    if with_held_credit:
        credit_account_id = _designated_account_id(chart.CUSTOMER_CREDIT_BALANCE)
        if credit_account_id is not None:
            ledger_account_ids.append(credit_account_id)
    rows = _posted_lines(end=as_of).filter(
        ledger_account_id__in=ledger_account_ids, account_id__isnull=False
    )
    if account_ids is not None:
        rows = rows.filter(account_id__in=[str(value) for value in account_ids])
    # DEF-081 — over exactly the lines about to be added, per this module's own
    # rule. A per-account Σ looks safe and is not: a customer whose CAD credit
    # cancelled their USD charge would read 0.00 while owing every cent of it.
    currency = _one_currency(rows, figure="what these accounts owe")
    positions: dict[str, Decimal] = {}
    for account, side, amount in rows.values_list("account_id", "side", "amount"):
        key = str(account)
        positions[key] = positions.get(key, ZERO) + (
            amount if side == models.SIDE_DEBIT else -amount
        )
    return {
        "basis": BASIS_POSTING,
        "as_of": as_of,
        # DEF-099 / CLAUDE.md rule 2 — the CHAR(3) these figures ARE, derived
        # from the entries summed rather than labelled from the tenant's
        # declared code. A money figure never leaves this module without it.
        "currency": currency,
        "positions": positions,
        "available": True,
        "unavailable": (),
    }


#: CR-185 D5's posting key ends in this event (`balance_transfer.posting_key_for`).
#: Spelled here rather than imported so a READ never imports the posting path.
_BALANCE_TO_OWNER_KEY_SUFFIX = "|balance_to_owner"


def balance_to_owner_moves(
    *,
    start: date | None = None,
    end: date | None = None,
    account_ids: Any = None,
) -> tuple[dict[str, Any], ...]:
    """EVERY BALANCE MOVED FROM A TENANT TO AN OWNER, AS THE BOOKS HOLD IT.

    `DEF-REP-10158` / `DEF-REP-10159` (2026-10-14). CR-185 D5 moves a departing
    tenant's residue to the owner as ONE journal entry, AR to AR
    (`balance_transfer.post_balance_to_owner`), and touches no bill and no
    allocation. Two reports read BILLS and so never saw it: the owner summary
    (bills only) and receivables by service (open bills). This is the read both
    now take, so the move is stated from the entry itself and never re-derived
    from the tie-back promise in customers.

    One row per (tenant account, owner account): `{from_account_id,
    to_account_id, amount, entry_date}` — `amount` is what left the tenant's AR
    and reached the owner's, NETTED over the window, so a reversal mirror of the
    entry (which carries the same source) cancels it rather than being missed.
    `entry_date` is the latest book date among the netted entries. Rows that net
    to zero are dropped. The window is the BOOK date (`_posted_lines`), POSTING
    basis. `account_ids` narrows to moves whose OWNER is one of them.

    WRITES NOTHING. Empty when the tenant has no AR designation — the AR lines
    cannot be told apart from any other then, and `ar_positions` already says so.
    """
    ar_account_id = _designated_account_id(chart.AR)
    if ar_account_id is None:
        return ()
    rows = (
        _posted_lines(start=start, end=end)
        .filter(ledger_account_id=ar_account_id, source_type="transfer", account_id__isnull=False)
        .filter(
            Q(journal_entry__posting_key__endswith=_BALANCE_TO_OWNER_KEY_SUFFIX)
            | Q(journal_entry__reversal_of__posting_key__endswith=_BALANCE_TO_OWNER_KEY_SUFFIX)
        )
        .values_list("source_id", "account_id", "side", "amount", "journal_entry__entry_date")
    )
    # source_id IS the tenant account (the entry's own source); the line on the
    # other account is the owner. Signed so the tenant's CREDIT is a move out.
    # The tenant's own line is the balancing half of the same entry and adds
    # nothing the owner's line does not already say.
    moved: dict[tuple[str, str], Decimal] = {}
    dated: dict[tuple[str, str], date] = {}
    for source, account, side, amount, entry_date in rows:
        source_key, account_key = str(source), str(account)
        if account_key == source_key:
            continue
        signed = amount if side == models.SIDE_DEBIT else -amount
        key = (source_key, account_key)
        moved[key] = moved.get(key, ZERO) + signed
        if key not in dated or entry_date > dated[key]:
            dated[key] = entry_date
    wanted = None if account_ids is None else {str(value) for value in account_ids}
    out = []
    for (source_key, owner_key), amount in sorted(moved.items()):
        if amount == ZERO:
            continue
        if wanted is not None and owner_key not in wanted:
            continue
        out.append(
            {
                "from_account_id": source_key,
                "to_account_id": owner_key,
                "amount": amount,
                "entry_date": dated[(source_key, owner_key)],
            }
        )
    return tuple(out)


def accounts_owing(*, as_of: date | None = None) -> int:
    """How many ACCOUNTS carry a net AR debit — the strip's *"184 accounts"*.

    Derivable, and one of the few dimension facts that is: `account_id` IS
    stamped on every line billing and payments post
    (`apps/billing/posting_seam.py` passes the invoice's account,
    `apps/payments/ledger_seam.py` the payment's). Lines with no account
    dimension are excluded from the COUNT and their money still shows in
    `still_owed`, so the two figures answer different questions honestly rather
    than one of them silently reshaping the other.

    **IT COUNTS `ar_positions` AND DERIVES NOTHING OF ITS OWN** (DEF-127). The
    per-account Σ used to live here as a private loop; the account screens need
    the same figure, and the day the two were written twice is the day the S17
    row and the S36 KPI could disagree about one customer. The DEF-081 currency
    guard rides along in there for the same reason.
    """
    return sum(1 for balance in ar_positions(as_of=as_of)["positions"].values() if balance > ZERO)


def adjustments_panel(*, start: date, end: date) -> dict[str, Any]:
    """S36's *Adjustments & credits* panel — from the books, not a register.

    Credits and debits are Σ over entries whose source is an adjustment or a
    credit note. Both read **0.00** today and that is the truthful answer rather
    than a gap: no caller posts an adjustment or a credit note yet (billing
    posts issue only), so nothing has moved.

    **THE LATE-FEE LINE IS `None`, AND THE REASON IS A RULE THIS MODULE OBEYS.**
    The prototype's panel has a *Late fees applied* row and the seed chart has
    **4200 Late-fee revenue** — but 4200 carries **no designation**, because the
    PO ruled ELEVEN and reserved nothing (OQ-110, 2026-08-11). So the only ways
    to find it are the two this repo forbids: by the NUMBER `4200`
    (`apps/ledger/chart.py`: *"Code reads the DESIGNATION. Code never reads the
    NUMBER"* — the latent misposting OQ-106 was raised over) or by the NAME,
    which is worse, since a tenant may rename the account and the panel would
    silently read 0.00 forever. A late fee also carries no `service` dimension
    (a fee is charged to an ACCOUNT), so there is no third route.

    The figure is therefore reported as unavailable, naming the twelfth
    designation that would answer it. Nothing here invents one — *"a posting with
    no home is an OQ row, not a new designation"*.

    The *pending approval* count is a billing register read: a count of things
    that have NOT reached the books, which is by definition not a ledger
    question.
    """
    credits = ZERO
    debits = ZERO
    rows = _posted_lines(start=start, end=end).filter(
        journal_entry__source_type__in=("adjustment", "credit_note")
    )
    currency = _one_currency(rows, figure="the adjustments & credits panel")
    for side, amount in rows.values_list("side", "amount"):
        if side == models.SIDE_CREDIT:
            credits += amount
        else:
            debits += amount
    return {
        "basis": BASIS_POSTING,
        "currency": currency,
        "credits_issued": credits,
        "debits_posted": debits,
        "late_fees_applied": None,
        "net": debits - credits,
        "pending_approval": None,
        "unavailable": (
            {
                "code": "late_fee_revenue_has_no_designation",
                "br_ref": "BR-LED-016 · OQ-110 (PO 2026-08-11) · BR-BIL-008",
                "detail": "the panel's *Late fees applied* row cannot be summed. The seed chart "
                "has 4200 Late-fee revenue and it carries NO designation — the PO ruled ELEVEN "
                "and reserved nothing — so the account is reachable only by its NUMBER (which "
                "`apps/ledger/chart.py` forbids: *code reads the DESIGNATION, never the "
                "NUMBER*, the misposting OQ-106 was raised over) or by its NAME, which a tenant "
                "may change, after which the panel would read 0.00 forever and say nothing. A "
                "late fee carries no `service` dimension either, since a fee is charged to an "
                "ACCOUNT. Reported rather than matched on a mutable string; a twelfth "
                "designation is a PO ruling, not a line of code here.",
                "wanted_reads": (),
            },
            {
                "code": "pending_approval_count_is_not_a_ledger_fact",
                "br_ref": "BR-REP-002",
                "detail": "an adjustment awaiting approval has not been posted, so it is not "
                "in the books and this module cannot count it. The panel links out; the count "
                "belongs to the billing/adjustments read-model.",
                "wanted_reads": (
                    "apps.billing.selectors.adjustments_pending_approval() -> int",
                ),
            },
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-009 — S59 Account ledger report
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class AccountLedgerRow:
    """One dated movement on a customer's receivable, with its running balance.

    `charge` and `payment` are the AR leg's two directions, never a signed
    amount — the same discipline `journal_lines.side` enforces, carried into the
    report so a reader never has to work out what a minus sign meant.

    `type_mapped=False` means BR-REP-008's vocabulary has no word for this
    line's source and the raw source_type is showing through. That is a visible
    defect by design: *nothing invisible*.
    """

    entry_date: date
    type: str
    type_mapped: bool
    reference: str | None
    description: str | None
    charge: Decimal
    payment: Decimal
    running_balance: Decimal
    entry_id: str
    source_type: str | None
    source_id: str | None


#: `P2.2` — **THE ACCOUNT LEDGER DECLINES SORT, AND IT IS RIGHT TO.** A
#: running balance is `r_n = r_{n-1} + charge_n - payment_n` (US-LED-009 §7,
#: CONFIRMED): it is defined BY the row order, so re-ordering the rows by
#: amount does not re-sort the column, it DESTROYS it — every figure in it
#: becomes a partial sum of a sequence nobody asked for, and the last one
#: stops being what the customer owes. Sort is PER-DATASET, not universal,
#: and this dataset's answer is an empty tuple rather than a missing key: a
#: screen reads it and draws no carets.
ACCOUNT_LEDGER_SORTS: tuple[str, ...] = ()


def account_ledger(
    account_id: Any, *, start: date, end: date, page: int = 1, per: int | None = None
) -> dict[str, Any]:
    """US-LED-009 — the account's AR movements, dated, with a running balance.

    BR-LED-010: *"account + premises + date range → dated charges/payments/
    adjustments + running balance → PDF/CSV"*, and BR-REP-008 makes the Type
    column carry the FULL source vocabulary so the report foots to the AR
    tie-out.

    **THE RUNNING BALANCE IS THE STORY'S OWN FORMULA AND NOTHING ELSE.**
    US-LED-009 §7, CONFIRMED: *"r_n = r_{n−1} + charge_n − payment_n"*, worked
    for ACC-1042 as `45.00 + 247.87 = 292.87; 292.87 − 292.87 = 0.00 ✔`. The
    opening row is the account's AR position at `start`, summed from every
    posted line BEFORE the window — so a report starting mid-history opens where
    the books left off rather than at zero.

    **ONLY THE AR LEG APPEARS.** A payment entry has three lines (undeposited
    debit, AR credit, maybe a customer-credit credit) and all three carry the
    account dimension; listing them all would show the customer paying twice.
    What a customer's ledger tracks is their RECEIVABLE, so the rows are the
    lines that hit the `accounts_receivable` account.

    Refuses `start > end` rather than answering an empty report — US-LED-009
    TC-6: *"never an empty-but-plausible report"*.

    ════════════════════════════════════════════════════════════════════════
    IT PAGES IN SQL SINCE `P2.12` (`CR-142-BRC07`), AND IT DOES NOT SORT
    ════════════════════════════════════════════════════════════════════════
    `window = list(_ar_lines(...))` materialised every AR line in the window.
    Bounded by ONE account and a date range, which is what the old comment
    here argued — and a commercial account on a monthly statement run is not
    the case that breaks it: a year's ledger for a campus with forty service
    points is thousands of rows, and a statement RUN asks for every account in
    turn. `NFR-3` has no exemption for *probably small*, so `per` cuts the page
    in SQL and `per=None` stays the default so every existing caller is
    unchanged.

    **THE RUNNING BALANCE SURVIVES THE PAGE, AND THAT IS THE WHOLE DIFFICULTY.**
    `r_n = r_{n-1} + charge_n - payment_n` is cumulative, so page 2 cannot
    start at the opening balance — it starts where page 1 left off. That
    carry-forward is a SQL aggregate over the rows BEFORE the offset, in the
    same total order the page is cut in, so row 51's balance is identical
    whether it was read on page 2 or in an unpaged run. `page_opening_balance`
    is published beside `opening_balance` because they are the same figure only
    on page one, and a statement that printed the window's opening over page
    two would be a document that does not add up.

    **`totals` IS THE WHOLE WINDOW AND NEVER THE PAGE** — two SQL sums — so the
    closing balance a clerk reads is what the account owes, not what the fifty
    rows in front of them come to.

    ⚠ **NO `sort` PARAMETER, DELIBERATELY** — `ACCOUNT_LEDGER_SORTS` is `()`
    and says why. Adding one is not a feature, it is a way to print a column of
    wrong money.
    """
    if start > end:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.range_inverted",
            params={"from": str(start), "to": str(end)},
        )
    ar_account_id = _designated_account_id(chart.AR)
    if ar_account_id is None:
        return {
            "basis": BASIS_POSTING,
            "account_id": str(account_id),
            "period": {"start": start, "end": end},
            "opening_balance": ZERO,
            "page_opening_balance": ZERO,
            "rows": (),
            "totals": {"charges": ZERO, "payments": ZERO, "closing_balance": ZERO},
            "sorts": ACCOUNT_LEDGER_SORTS,
            "page": 1,
            "per": per,
            "total": 0,
            "unavailable": (
                {
                    "code": "no_account_carries_the_accounts_receivable_designation",
                    "br_ref": "BR-BIL-010 · OQ-106",
                    "detail": "this tenant has designated no AR account, so there is no "
                    "receivable to report on. One chart edit on S56 fixes it; nothing here "
                    "picks an account by number.",
                    "wanted_reads": (),
                },
                GAP_PREMISES_FILTER_NOT_OFFERED,
            ),
        }

    def _ar_lines(**window: Any) -> Any:
        return (
            _posted_lines(**window)
            .filter(ledger_account_id=ar_account_id, account_id=account_id)
            .order_by(
                "journal_entry__entry_date",
                "journal_entry__created_at",
                "created_at",
                "id",
            )
        )

    # DEF-081 — over THIS customer's AR lines from the beginning of the books to
    # `end`, because the opening balance sums everything before the window and
    # the running balance carries it forward. Scoped to the one account on
    # purpose: another customer's foreign entries are not this report's problem
    # and must not darken a statement that is itself entirely lawful.
    currency = _one_currency(
        _ar_lines(end=end), figure="this account's ledger and running balance"
    )

    opening = ZERO
    for side, amount in _ar_lines(end=_day_before(start)).values_list("side", "amount"):
        opening += amount if side == models.SIDE_DEBIT else -amount

    # ── the window, in SQL: its size, its two sums, and the page ────────────
    money = DecimalField(max_digits=18, decimal_places=6)

    def _movement(queryset: Any) -> tuple[Decimal, Decimal]:
        """(charges, payments) over `queryset` — two sums, ONE statement."""
        sums = queryset.aggregate(
            charges=Coalesce(
                Sum("amount", filter=Q(side=models.SIDE_DEBIT)),
                Value(ZERO, output_field=money),
                output_field=money,
            ),
            payments=Coalesce(
                Sum("amount", filter=Q(side=models.SIDE_CREDIT)),
                Value(ZERO, output_field=money),
                output_field=money,
            ),
        )
        return (sums["charges"] or ZERO, sums["payments"] or ZERO)

    in_window = _ar_lines(start=start, end=end)
    total_rows = in_window.count()
    charges, payments = _movement(in_window)

    if per is None:
        served_page = 1
        offset = 0
    else:
        # `BR-SHL-011` — clamp, never error.
        per = max(1, int(per))
        last_page = max(1, -(-total_rows // per))
        served_page = min(max(1, int(page)), last_page)
        offset = (served_page - 1) * per

    # ⚠ **THE CARRY-FORWARD, AND IT IS WHY THIS REPORT CAN BE PAGED AT ALL.**
    # The rows before the offset are summed in SQL, in the SAME total order the
    # page is cut in (`_ar_lines` orders by entry date, then created_at, then
    # id — a total order, so no row can straddle a page boundary). Page one
    # sums nothing and the two openings are the same figure.
    if offset:
        prior_charges, prior_payments = _movement(in_window[:offset])
        page_opening = opening + prior_charges - prior_payments
    else:
        page_opening = opening

    # ── P5.8 — the Reference column reads a DOCUMENT NUMBER ─────────────────
    # The PAGE's rows are walked once into memory, so the two seam reads can be
    # asked for the whole page at a time rather than per row.
    page_queryset = in_window.select_related("journal_entry")
    window = list(
        page_queryset if per is None else page_queryset[offset : offset + per]
    )
    wanted: dict[str, set[str]] = {}
    for row in window:
        source_type = row.source_type or row.journal_entry.source_type
        if source_type and row.source_id:
            wanted.setdefault(str(source_type), set()).add(str(row.source_id))
    document_numbers = dict(billing_seam.document_numbers_for(wanted))
    document_numbers.update(payments_seam.document_numbers_for(wanted))

    running = page_opening
    rows: list[AccountLedgerRow] = []
    unnamed_documents: set[str] = set()
    for row in window:
        entry = row.journal_entry
        source_type = row.source_type or entry.source_type
        label, mapped = source_vocabulary_for(source_type)
        charge = row.amount if row.side == models.SIDE_DEBIT else ZERO
        payment = row.amount if row.side == models.SIDE_CREDIT else ZERO
        running = running + charge - payment
        # ⚠ **AN UNRESOLVED DOCUMENT IS `None`, NEVER THE UUID** — B14 rule 31,
        # and it is the whole of `P5.8`. Until today this field carried
        # `str(row.source_id)`, so every row of this report printed a primary
        # key at a clerk. A fallback to the id would keep that breach alive
        # under the name of its own fix, which is the shape hard-won law 1
        # names: a field claiming to hold a document number and holding an id.
        reference = None
        if source_type and row.source_id:
            reference = document_numbers.get((str(source_type), str(row.source_id)))
            if reference is None and str(source_type) in DOCUMENT_SOURCE_TYPES:
                unnamed_documents.add(str(source_type))
        rows.append(
            AccountLedgerRow(
                entry_date=entry.entry_date,
                type=label,
                type_mapped=mapped,
                reference=reference,
                description=entry.memo,
                charge=charge,
                payment=payment,
                running_balance=running,
                entry_id=str(entry.pk),
                source_type=source_type,
                source_id=str(row.source_id) if row.source_id else None,
            )
        )
    return {
        "basis": BASIS_POSTING,
        "account_id": str(account_id),
        "period": {"start": start, "end": end},
        "currency": currency,
        "opening_balance": opening,
        #: Where THIS PAGE's running balance starts. The same figure as
        #: `opening_balance` on page one and on an unpaged read; different on
        #: every page after that, which is exactly the fact a statement header
        #: must not get wrong.
        "page_opening_balance": page_opening,
        "rows": tuple(rows),
        "totals": {
            # ⚠ **THE WINDOW'S, NEVER THE PAGE'S.** Two SQL sums over every AR
            # line in `[start, end]`, so `closing_balance` is what the account
            # owes and not what fifty rows come to.
            "charges": charges,
            "payments": payments,
            "closing_balance": opening + charges - payments,
        },
        "sorts": ACCOUNT_LEDGER_SORTS,
        "page": served_page,
        "per": per,
        "total": total_rows,
        "vocabulary": SOURCE_VOCABULARY,
        # ⚠ **THE REFERENCE GAP IS NOW CONDITIONAL AND IT IS A DIFFERENT GAP.**
        # It used to say the Reference column holds a uuid because billing and
        # payments publish nothing; both publish now (`P5.8`) and the column
        # holds the printed number. What is left is narrower and is only ever
        # said when the page actually holds an instance of it — a document kind
        # this product cannot yet put a number on. Announcing it over a page of
        # perfectly numbered rows would be an apology for nothing, which is how
        # a stated absence stops being read (`DEF-CWP-3925`'s shape: a refusal
        # that outlives what it refused over).
        "unavailable": tuple(
            gap
            for gap in (
                GAP_PREMISES_FILTER_NOT_OFFERED,
                (GAP_DOCUMENT_HAS_NO_NUMBER if unnamed_documents else None),
                GAP_AGING_NEEDS_DUE_DATES,
            )
            if gap is not None
        ),
    }


def _day_before(day: date) -> date:
    """The last book date BEFORE the window — where the opening row is summed to.

    A separate function rather than an inline subtraction because the opening
    balance is the one figure in `account_ledger` that depends on the window's
    EDGE, and an off-by-one here double-counts or loses the first day's
    movement in a report whose whole job is to foot.
    """
    return day - timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════════════
# `CR-142-BRC07` `P2.15` · `BR-REP-043` — THE UNIT'S RUNNING RECORD
# ═══════════════════════════════════════════════════════════════════════════

#: A page of a unit statement held a line with no customer stamped on it, so
#: the Occupant cell is EMPTY on that row rather than filled with a guess.
#:
#: ⚠ **CONDITIONAL, AND SAID ONLY WHEN THE PAGE ACTUALLY HOLDS ONE.**
#: `GAP_DOCUMENT_HAS_NO_NUMBER` records the reasoning one report over: a stated
#: absence announced over a page with no instance of it is an apology for
#: nothing, and that is how a gap stops being read (`DEF-CWP-3925`'s shape — a
#: refusal that outlives what it refused over).
GAP_OCCUPANT_NOT_STAMPED = {
    "code": "some_lines_carry_no_occupant",
    "br_ref": "BR-REP-043 · US-LED-002",
    "detail": (
        "Some lines on this page were posted before the books recorded WHO held "
        "the account, so their Occupant cell is empty. The figures are unaffected "
        "— the money is dimensioned by unit either way. The name is not guessed "
        "from today's holder, because a unit outlives its tenants and that would "
        "put the current occupant's name on a former occupant's charges."
    ),
    "wanted_reads": (),
}

#: A unit statement is a running record, so it declines sort for the reason
#: `ACCOUNT_LEDGER_SORTS` declines it: the running balance is DEFINED by the row
#: order, and re-ordering does not re-sort that column, it destroys it.
UNIT_LEDGER_SORTS: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnitLedgerRow:
    """One dated movement against a UNIT, with its running balance and occupant.

    Every field but `occupant` and `account_label` is `AccountLedgerRow`'s, and
    deliberately so: `BR-REP-043` says the subject scopes the SET and **the
    grain of a row does not change**. A unit statement is not a different
    document, it is the same document about a different set.
    """

    entry_date: date
    type: str
    type_mapped: bool
    reference: str | None
    description: str | None
    charge: Decimal
    payment: Decimal
    running_balance: Decimal
    entry_id: str
    source_type: str | None
    source_id: str | None
    #: WHO HELD THE ACCOUNT WHEN THIS LINE WAS POSTED — never today's holder.
    occupant: str | None
    #: Which of the unit's accounts the line was posted against. A unit with two
    #: tenancies has two account numbers over one window, and a reader tracing a
    #: figure needs to know which. `account_no`, never the uuid (B14 rule 31).
    account_label: str | None


def unit_ledger(
    unit_id: Any, *, start: date, end: date, page: int = 1, per: int | None = None
) -> dict[str, Any]:
    """`P2.15` — one UNIT's AR movements, dated, with a running balance.

    **`BR-REP-043` (PO ruling 2026-09-27), verbatim: *"we can do based on
    regualr account, master account, premises, units, customer id"*, and asked
    again about this one specifically, *"yes; i can generate statement for
    Unit"*.** The subject scopes the SET; the grain of a row does not change.

    ════════════════════════════════════════════════════════════════════════
    WHY THIS IS A SEPARATE READ MODEL AND NOT `account_ledger` WITH A FILTER
    ════════════════════════════════════════════════════════════════════════
    **A UNIT OUTLIVES ITS TENANTS.** `account_ledger` opens on ONE account and
    every figure it strikes — the opening balance above all — is that account's.
    A unit's window can span a move-out, so its rows belong to two or more
    accounts and its opening balance is the sum over all of them. Handing
    `account_ledger` a unit filter would produce an opening balance for one
    account and rows for several: a document that does not add up, which is the
    one thing a statement may never be.

    **IT IS DIMENSIONED BY THE STAMP, NEVER BY A JOIN.** `journal_lines.unit_id`
    is written at posting time by `dimension_seam.location_for_account`. Walking
    `accounts → units` instead would re-attribute every historical line the day
    an account moves, which is `US-LED-002` TC-4's argument for the premises
    column and is the same argument here.

    ⚠ **THE OCCUPANT COLUMN APPEARS ON THIS SUBJECT AND NO OTHER**, because it
    is only here that one document's rows can belong to different people. It
    reads `journal_lines.customer_id` — the holder AT POSTING — so a statement
    spanning a move-out NAMES BOTH OCCUPANTS and puts neither one's name on the
    other's money.

    ⚠ **`occupants` IS OVER THE WINDOW, NEVER THE PAGE.** The head names who the
    statement is about, and a head computed from the page would name one
    occupant on page one and another on page two of one document. It is a
    separate `DISTINCT` over the whole window, for the same reason `totals` is.

    ⚠ **NO ADDRESS IS READ FOR THE UNIT — HARD RULE 8.** *A unit refines a
    premises by LABEL, not by address.* The head carries the unit's LABEL and
    the PREMISES' address, walked through `dimension_seam`, and this function
    declares no address of its own.

    **PAGING, THE CARRY-FORWARD AND THE TOTALS ARE `account_ledger`'S, EXACTLY.**
    `per` cuts the page in SQL (`NFR-3`), the rows before the offset are summed
    in SQL in the same total order so row 51's balance is identical whether it
    was read on page two or unpaged, and `totals` is the WINDOW's. There is no
    cap (`NFR-5`).

    Refuses `start > end` rather than answering an empty report (US-LED-009
    TC-6: *"never an empty-but-plausible report"*).
    """
    if start > end:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.range_inverted",
            params={"from": str(start), "to": str(end)},
        )

    unit_label = dimension_seam.unit_labels([unit_id]).get(str(unit_id))
    premises_id, premises_problem = dimension_seam._premises_of(str(unit_id))
    premises_label = (
        dimension_seam.premises_labels([premises_id]).get(str(premises_id))
        if premises_id
        else None
    )

    def _head(**rest: Any) -> dict[str, Any]:
        """The fields every return shares — so a refusal still says WHERE it is."""
        return {
            "basis": BASIS_POSTING,
            "unit_id": str(unit_id),
            "unit_label": unit_label,
            # ⚠ Hard rule 8: the ADDRESS is the premises', walked to. The unit
            # declares none and this dict carries none of its own.
            "premises_id": premises_id,
            "premises_label": premises_label,
            "period": {"start": start, "end": end},
            "sorts": UNIT_LEDGER_SORTS,
            **rest,
        }

    ar_account_id = _designated_account_id(chart.AR)
    if ar_account_id is None:
        return _head(
            opening_balance=ZERO,
            page_opening_balance=ZERO,
            rows=(),
            occupants=(),
            totals={"charges": ZERO, "payments": ZERO, "closing_balance": ZERO},
            page=1,
            per=per,
            total=0,
            unavailable=(
                {
                    "code": "no_account_carries_the_accounts_receivable_designation",
                    "br_ref": "BR-BIL-010 · OQ-106",
                    "detail": "this tenant has designated no AR account, so there is no "
                    "receivable to report on. One chart edit on S56 fixes it; nothing here "
                    "picks an account by number.",
                    "wanted_reads": (),
                },
            ),
        )

    def _ar_lines(**window: Any) -> Any:
        return (
            _posted_lines(**window)
            .filter(ledger_account_id=ar_account_id, unit_id=unit_id)
            .order_by(
                "journal_entry__entry_date",
                "journal_entry__created_at",
                "created_at",
                "id",
            )
        )

    currency = _one_currency(
        _ar_lines(end=end), figure="this unit's ledger and running balance"
    )

    # The opening position: every posted AR line against this UNIT before the
    # window, whichever account carried it. Summed across tenancies on purpose —
    # a unit's opening balance is the unit's, not the sitting tenant's.
    opening = ZERO
    for side, amount in _ar_lines(end=_day_before(start)).values_list("side", "amount"):
        opening += amount if side == models.SIDE_DEBIT else -amount

    money = DecimalField(max_digits=18, decimal_places=6)

    def _movement(queryset: Any) -> tuple[Decimal, Decimal]:
        sums = queryset.aggregate(
            charges=Coalesce(
                Sum("amount", filter=Q(side=models.SIDE_DEBIT)),
                Value(ZERO, output_field=money),
                output_field=money,
            ),
            payments=Coalesce(
                Sum("amount", filter=Q(side=models.SIDE_CREDIT)),
                Value(ZERO, output_field=money),
                output_field=money,
            ),
        )
        return (sums["charges"] or ZERO, sums["payments"] or ZERO)

    in_window = _ar_lines(start=start, end=end)
    total_rows = in_window.count()
    charges, payments = _movement(in_window)

    if per is None:
        served_page = 1
        offset = 0
    else:
        per = max(1, int(per))  # BR-SHL-011 — clamp, never error.
        last_page = max(1, -(-total_rows // per))
        served_page = min(max(1, int(page)), last_page)
        offset = (served_page - 1) * per

    if offset:
        prior_charges, prior_payments = _movement(in_window[:offset])
        page_opening = opening + prior_charges - prior_payments
    else:
        page_opening = opening

    # ⚠ **THE WINDOW'S OCCUPANTS, IN THE ORDER THEY APPEAR** — one DISTINCT over
    # the whole window, never over the page. `.distinct()` on a values_list of
    # the ordered queryset would drag the ORDER BY columns into the DISTINCT, so
    # the ids are gathered and de-duplicated in insertion order instead, which
    # is a walk over ids and not over money.
    window_customer_ids: list[str] = []
    seen: set[str] = set()
    for value in in_window.values_list("customer_id", flat=True):
        if value is None:
            continue
        key = str(value)
        if key not in seen:
            seen.add(key)
            window_customer_ids.append(key)

    page_queryset = in_window.select_related("journal_entry")
    window = list(page_queryset if per is None else page_queryset[offset : offset + per])

    wanted: dict[str, set[str]] = {}
    for row in window:
        source_type = row.source_type or row.journal_entry.source_type
        if source_type and row.source_id:
            wanted.setdefault(str(source_type), set()).add(str(row.source_id))
    document_numbers = dict(billing_seam.document_numbers_for(wanted))
    document_numbers.update(payments_seam.document_numbers_for(wanted))

    # Batched over the PAGE's id sets, never per row.
    customer_names = dimension_seam.customer_labels(
        window_customer_ids + [row.customer_id for row in window if row.customer_id]
    )
    account_numbers = dimension_seam.account_labels(
        {row.account_id for row in window if row.account_id}
    )

    running = page_opening
    rows: list[UnitLedgerRow] = []
    unnamed_documents: set[str] = set()
    occupant_missing = False
    for row in window:
        entry = row.journal_entry
        source_type = row.source_type or entry.source_type
        label, mapped = source_vocabulary_for(source_type)
        charge = row.amount if row.side == models.SIDE_DEBIT else ZERO
        payment = row.amount if row.side == models.SIDE_CREDIT else ZERO
        running = running + charge - payment
        reference = None
        if source_type and row.source_id:
            reference = document_numbers.get((str(source_type), str(row.source_id)))
            if reference is None and str(source_type) in DOCUMENT_SOURCE_TYPES:
                unnamed_documents.add(str(source_type))
        occupant = (
            customer_names.get(str(row.customer_id)) if row.customer_id else None
        )
        if occupant is None:
            occupant_missing = True
        rows.append(
            UnitLedgerRow(
                entry_date=entry.entry_date,
                type=label,
                type_mapped=mapped,
                reference=reference,
                description=entry.memo,
                charge=charge,
                payment=payment,
                running_balance=running,
                entry_id=str(entry.pk),
                source_type=source_type,
                source_id=str(row.source_id) if row.source_id else None,
                occupant=occupant,
                account_label=(
                    account_numbers.get(str(row.account_id)) if row.account_id else None
                ),
            )
        )

    return _head(
        currency=currency,
        opening_balance=opening,
        page_opening_balance=page_opening,
        rows=tuple(rows),
        # ⚠ THE HEAD'S OWN ANSWER TO *"whose statement is this?"*, and on a
        # window spanning a move-out it holds MORE THAN ONE NAME. That is the
        # PO's worked case and it is asserted by name in the tests.
        occupants=tuple(
            customer_names[key] for key in window_customer_ids if key in customer_names
        ),
        totals={
            "charges": charges,
            "payments": payments,
            "closing_balance": opening + charges - payments,
        },
        page=served_page,
        per=per,
        total=total_rows,
        vocabulary=SOURCE_VOCABULARY,
        unavailable=tuple(
            gap
            for gap in (
                (GAP_OCCUPANT_NOT_STAMPED if occupant_missing else None),
                (GAP_DOCUMENT_HAS_NO_NUMBER if unnamed_documents else None),
                GAP_AGING_NEEDS_DUE_DATES,
                # The unit could not be walked to a premises, so the head has no
                # address. SAID rather than left blank: an empty address line is
                # indistinguishable from a unit that has none.
                (
                    {
                        "code": "unit_does_not_resolve_to_a_premises",
                        "br_ref": "BR-MET-1161 · hard rule 8",
                        "detail": (
                            "This unit does not resolve to a premises, so the "
                            "statement head carries no address. A unit declares no "
                            "address of its own; it refines a premises by label."
                        ),
                        "wanted_reads": (premises_problem,),
                    }
                    if premises_problem is not None
                    else None
                ),
            )
            if gap is not None
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-010 — S60 By-premises summary
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class PremisesRow:
    """One premises' billed / collected / owed, summed from stamped lines."""

    premises_id: str
    name: str | None
    billed: Decimal
    collected: Decimal
    owed: Decimal


def by_premises_summary(*, start: date, end: date) -> dict[str, Any]:
    """US-LED-010 — billed / collected / owed per premises (BR-LED-011).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS FUNCTION REFUSED FOR FIVE DAYS AND THE TRAIL IS KEPT           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    It used to return `available=False` and the money it could not attribute —
    LE-1's **553.69** — because **every journal line in the product carried
    `premises_id = NULL`**: US-LED-002's stamping was unbuilt, so there was
    nothing to group on. Three answers were possible and two were defects (an
    EMPTY table reads as *no activity this period*; ONE row labelled
    *Unassigned* holding the whole book sorts, exports and reads like a premises
    and is a finding disguised as data), so the third shipped and said so.

    **US-LED-002 LANDED 2026-08-16.** `apps/ledger/posting.py` now resolves
    account → unit → premises at posting time, so the group-by US-LED-010 §5
    describes — *"Σ journal lines per premises (posting basis)"* — is what this
    function is. LE-6's figures are assertable: **500 Main St 247.87 · Oak Grove
    16.42 · Marina Bay 289.40**, footing to the same **553.69** that used to be
    the refusal's measurement.

    **THE GROUPING IS ON THE STAMP AND NOTHING IS JOINED AT READ TIME.**
    US-LED-010 TC-5 is a structural test on this function's own source for
    exactly that reason: a read-time account → unit → premises join moves LAST
    YEAR'S money the day a unit is re-assigned, and BR-MET-046's chain guarantee
    is about the stamp. The only outward call here is
    `dimension_seam.premises_labels`, which puts a NAME beside an id already
    written on the row — it can change a label and can never move a figure.

    **`unattributed_*` DID NOT GO AWAY, and must not.** Lines that lawfully
    carry no premises still exist (a bank fee, a deposit-batch cash leg — see
    `apps/ledger/posting._stamped`), and money the table cannot show is reported
    beside it rather than silently missing from the footer. On the LE-1 month
    those figures are **0.00**, which is a derived answer rather than a default.
    """
    strip = revenue_and_ar(start=start, end=end)
    ar_account_id = _designated_account_id(chart.AR)
    if ar_account_id is None:
        return {
            "basis": BASIS_POSTING,
            "period": {"start": start, "end": end},
            "currency": strip["currency"],
            "available": False,
            "rows": (),
            "kpis": {"premises": 0, "billed": ZERO, "collected": ZERO, "owed": ZERO},
            "unattributed_billed": strip["kpis"]["billed"],
            "unattributed_collected": strip["kpis"]["collected"],
            "unavailable": (GAP_NO_AR_DESIGNATION,),
        }

    window = _posted_lines(start=start, end=end).filter(ledger_account_id=ar_account_id)
    # A deposit APPLICATION credits AR under the invoice's own source_type, so
    # it is identified by its other leg exactly as `revenue_and_ar` does. One
    # derivation, two groupings — BR-REP-002's whole point.
    deposit_account_id = _designated_account_id(chart.DEPOSIT_LIABILITY)
    application_entries: set[Any] = set()
    if deposit_account_id is not None:
        application_entries = set(
            _posted_lines(start=start, end=end)
            .filter(ledger_account_id=deposit_account_id, side=models.SIDE_DEBIT)
            .values_list("journal_entry_id", flat=True)
        )

    billed: dict[str, Decimal] = {}
    collected: dict[str, Decimal] = {}
    unattributed_billed = ZERO
    unattributed_collected = ZERO
    for premises, side, amount, entry_source, entry_id in window.values_list(
        "premises_id", "side", "amount", "journal_entry__source_type", "journal_entry_id"
    ):
        key = str(premises) if premises else None
        if side == models.SIDE_DEBIT and entry_source in BILL_SOURCE_TYPES:
            if key is None:
                unattributed_billed += amount
            else:
                billed[key] = billed.get(key, ZERO) + amount
        elif side == models.SIDE_CREDIT and (
            entry_source in CASH_SOURCE_TYPES or entry_id in application_entries
        ):
            if key is None:
                unattributed_collected += amount
            else:
                collected[key] = collected.get(key, ZERO) + amount

    # OWED is cumulative as of `end`, like `ar_control` and `ar_positions` — a
    # premises owes what the books say it owes, not what this window moved.
    owed: dict[str, Decimal] = {}
    for premises, side, amount in (
        _posted_lines(end=end)
        .filter(ledger_account_id=ar_account_id, premises_id__isnull=False)
        .values_list("premises_id", "side", "amount")
    ):
        key = str(premises)
        owed[key] = owed.get(key, ZERO) + (
            amount if side == models.SIDE_DEBIT else -amount
        )

    keys = sorted(set(billed) | set(collected) | set(owed))
    names = dimension_seam.premises_labels(keys)
    rows = tuple(
        PremisesRow(
            premises_id=key,
            name=names.get(key),
            billed=billed.get(key, ZERO),
            collected=collected.get(key, ZERO),
            owed=owed.get(key, ZERO),
        )
        for key in sorted(keys, key=lambda value: (names.get(value) or "", value))
    )
    return {
        "basis": BASIS_POSTING,
        "period": {"start": start, "end": end},
        # DEF-081 — taken from the strip rather than re-derived: `revenue_and_ar`
        # above already asked, and already refused, over this same window. Two
        # derivations of one currency is the same defect BR-REP-002 forbids for
        # money, one column across.
        "currency": strip["currency"],
        "available": bool(rows),
        "rows": rows,
        "kpis": {
            "premises": len(rows),
            "billed": sum((row.billed for row in rows), ZERO),
            "collected": sum((row.collected for row in rows), ZERO),
            "owed": sum((row.owed for row in rows), ZERO),
        },
        "unattributed_billed": unattributed_billed,
        "unattributed_collected": unattributed_collected,
        "unavailable": (
            (GAP_PREMISES_RESIDUE,)
            if rows and (unattributed_billed or unattributed_collected)
            else ()
            if rows
            else (GAP_PREMISES_DIMENSION,)
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-014 — S41 dual-basis remittance
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class AuthorityRemittanceRow:
    """One authority's four columns — BR-LED-013's *billed · collected ·
    remitted · outstanding* — plus which basis it remits on.

    The authority IS the 2200-nn ledger account (BR-BIL-069 + B5 line 74 ❄️).
    `code` and `name` are the tenant's own, typed when they minted it.

    ⚠ **`collected` AND `outstanding_collected` CARRY FIGURES SINCE 2026-09-02**
    (CR-060 C19 / task T7d). This paragraph read *"are None with a reason… the
    honest way to honour a rule you cannot yet execute is to show the slot, name
    what is missing, and refuse to fill it with the other basis's number"*, and
    that was right for as long as an `allocations` row carried no line class.
    `allocation_classes` (payments/0015) records what each payment met, so
    BR-LED-002's *"BOTH bases always computed"* is now executed rather than
    honoured in the breach.

    They are still `None` — never 0.00 — when payments publishes no such read at
    all, which is the old behaviour kept as the fallback. And the figure is a
    FLOOR while any allocated money in the window carries no breakdown; how much
    is on the response as `allocated_without_breakdown`, and
    `GAP_COLLECTED_IS_A_FLOOR` names it.

    `remitting_basis` is the tenant's OWN answer — `billed` or `collected`,
    kept per authority on the S71 Finance-controls page since the PO's ruling
    of 2026-08-12. It DEFAULTED to None for every authority because the choice
    had nowhere to live; it is None now only where this tenant has not made it,
    and the report says which ones those are. It is never seeded: LE-3 has State
    on collected and County on billed in the same month, so a shipped default is
    wrong for one of them in its first month.
    """

    account_id: str
    code: str
    name: str
    billed: Decimal
    collected: Decimal | None
    remitted: Decimal
    outstanding_billed: Decimal
    outstanding_collected: Decimal | None
    remitting_basis: str | None = None
    # (billed, collected). Collected is POSTING-dated since 2026-10-21
    # (`DEF-PAY-10321`, PO ruling) — it was the clearing date before.
    bases: tuple[str, str] = (BASIS_POSTING, BASIS_POSTING)

    # ── OQ-1190, PO ruling 2026-08-31 ────────────────────────────────────
    # *"(a) Add a per-authority subtotal to the bill and the finance screens"*.
    # The row above is the authority's money AS THE BOOKS HOLD IT, keyed on the
    # 2200-nn account; these four are the SAME authority's money AS THE BILLS
    # CHARGED IT, split by `invoice_lines.tax_id` and named the way rating names
    # it. They are two derivations of one debt and they are shown side by side
    # rather than reconciled — `GAP_TAX_AUTHORITY_NAME` is precisely that the
    # books cannot name an authority, so a screen that showed only one of these
    # could never surface a disagreement between them.
    #
    #: The authority AS RATING KNOWS IT — *"Bexar County Tax Office"*, against
    #: the account's own name *"Tax payable — Local · Bexar County"*, which is
    #: what the tenant typed when they minted the account. `None` when billing
    #: could not answer, or when TWO authorities post to one account, which is a
    #: chart fault a picked name would hide (BR-BIL-069 gives each its own).
    authority_name: str | None = None
    #: Σ of the ROUNDED tax lines (B4.4) across exactly the bills the books
    #: counted for this account. `None` — never zero — when billing published no
    #: read; zero is a real answer meaning *"those bills charged this authority
    #: nothing"* and the two must not be confused.
    billed_from_bills: Decimal | None = None
    #: How many tax LINES and how many BILLS are behind that figure, so a clerk
    #: filing a return can see whether it is one bill or nine hundred.
    bill_line_count: int | None = None
    bill_count: int | None = None
    #: `billed_from_bills - billed`, STATED and never corrected. Non-zero means
    #: the bills and the books disagree about what one authority is owed, which
    #: is exactly the fact a return has to be filed against.
    billed_delta: Decimal | None = None
    #: THE VERDICT IS THE SERVER'S, not a string comparison on the client. PO
    #: ruling 2026-08-30 (R1–R7): the document displays what the server
    #: resolved. `money()` serialises to six places, so a screen testing
    #: `delta == "0.00"` would be false on every agreeing row — a check that can
    #: only fail, which is the mirror of the check that cannot. `None` when
    #: there is no bill-side figure to compare.
    bills_agree: bool | None = None
    #: Problem codes for this row alone — the shape `unavailable` uses for the
    #: table.
    problems: tuple[str, ...] = ()




#: OQ-1190 — two authorities posting to ONE 2200-nn account. BR-BIL-069 gives
#: each authority its own, so this is a chart fault; the row keeps its money and
#: loses its NAME, because naming one of the two would file the other's return.
GAP_TWO_AUTHORITIES_ONE_ACCOUNT = "two_tax_authorities_share_one_liability_account"

#: OQ-1190 — the books credited this account from bills, and none of those bills
#: has a tax line stamped with a tax id that resolves to it. Stated, never
#: silently shown as zero.
GAP_NO_BILL_SIDE_FOR_ACCOUNT = "no_bill_side_tax_lines_resolve_to_this_account"


def _tax_by_authority_for_accounts(
    bills_behind: dict[str, set[str]],
) -> dict[str, dict[str, Any]]:
    """Per 2200-nn account: the authority's NAME and the bills' own subtotal.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  OQ-1190 — PO 2026-08-31: the per-authority subtotal on FINANCE too   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Verbatim: *"(a) Add a per-authority subtotal to the bill and the finance
    screens"*. The bill half is `apps/billing/selectors._taxes_by_authority`;
    this is the finance half, and it is the SAME derivation — billing loops the
    same tax lines with the same `money.finalize`, so the figure a clerk reads
    on S41 and the figure they read on the bill cannot disagree.

    **THE JOIN IS THE STAMPED ACCOUNT, NEVER A NAME MATCH.** Each bucket billing
    returns carries `liability_account_id` — `invoice_lines.gl_account_id` as it
    was stamped at issue (BR-BIL-010) — so a bucket lands on the row whose
    account the bill actually credited. Matching *"Bexar County Tax Office"*
    against *"Tax payable — Local · Bexar County"* would be a guess, and
    `GAP_TAX_AUTHORITY_NAME` exists because those two strings are genuinely
    different facts.

    **AN ACCOUNT WITH NO BILL-SIDE ANSWER KEEPS ITS FIGURE ABSENT.** Not zero:
    `subtotal` stays `None` and a problem code says which absence it is —
    billing published no read, or no tax line stamped with a resolving tax id.
    A column silently filled with zero would read as *"this authority is owed
    nothing"* on a screen a return is filed from.
    """
    per_account: dict[str, dict[str, Any]] = {}
    every_bill = {bill for bills in bills_behind.values() for bill in bills}
    answer = billing_seam.tax_by_authority_for_invoices(tuple(sorted(every_bill)))
    if answer is None:
        # Billing has not published the read. EVERY row says so and no row
        # carries a figure — the check that cannot fail is the one that quietly
        # copies the other column across.
        return {
            key: {
                "authority_name": None,
                "subtotal": None,
                "line_count": None,
                "problems": (billing_seam.TAX_BY_AUTHORITY_UNAVAILABLE,),
            }
            for key in bills_behind
        }

    by_account: dict[str, dict[str, Any]] = {}
    for bucket in answer.get("authorities", ()):
        account_id = bucket.get("liability_account_id")
        if account_id is None:
            # A bucket whose own lines named two accounts, or none. It cannot be
            # placed on a row, and placing it on the wrong one is worse than
            # leaving it off — the bill's own screen still shows it.
            continue
        row = by_account.setdefault(
            account_id,
            {"names": set(), "subtotal": ZERO, "line_count": 0},
        )
        if bucket.get("authority"):
            row["names"].add(bucket["authority"])
        row["subtotal"] += Decimal(str(bucket.get("subtotal") or "0"))
        row["line_count"] += int(bucket.get("line_count") or 0)

    for key, bills in bills_behind.items():
        found = by_account.get(key)
        if found is None:
            # ⚠ DEF-LED-6707 — NO BILLS AT ALL IS A ZERO, NOT AN ABSENCE. The
            # docstring's "an account with no bill-side answer keeps its figure
            # absent" was written for an account billing FAILED on, and this
            # branch was swallowing a second, completely different case: a
            # window in which NO BILL CHARGED THIS AUTHORITY ANYTHING. There is
            # nothing missing there — the bills are all in view and none of them
            # touched this account — so `0.00` is the true answer and *Not
            # available* is a lie about a fact we hold. It is the same reasoning
            # `remittance_by_authority`'s no-accounts branch already states in
            # its own words about `billed_from_bills`.
            if not bills:
                per_account[key] = {
                    "authority_name": None,
                    "subtotal": ZERO,
                    "line_count": 0,
                    "problems": (),
                }
                continue
            per_account[key] = {
                "authority_name": None,
                "subtotal": None,
                "line_count": None,
                "problems": (GAP_NO_BILL_SIDE_FOR_ACCOUNT,),
            }
            continue
        names = found["names"]
        per_account[key] = {
            "authority_name": next(iter(names)) if len(names) == 1 else None,
            "subtotal": found["subtotal"],
            "line_count": found["line_count"],
            "problems": (GAP_TWO_AUTHORITIES_ONE_ACCOUNT,) if len(names) > 1 else (),
        }
    return per_account


def remittance_by_authority(*, start: date, end: date) -> dict[str, Any]:
    """US-LED-014 — the dual-basis table, one row per tax-payable account.

    BR-LED-002 (CONFIRMED, PO LF-2): *"BOTH bases always computed (billed = tax
    on issued bills; collected = tax inside cleared payments via allocation);
    per-authority setting picks the remitting basis; remittance payment = JE
    draining the authority's liability."*

    **BILLED, worked against LE-3, is fully derivable and needs no dimension.**
    Each authority has its own 2200-nn account (BR-BIL-069, PO 2026-08-11), so
    the billed basis is Σ CREDITS to that account from invoice-sourced entries:
    LE-3's July is State **13.87** · County **2.22** · City **4.44** · PUC
    **0.44** = **20.97** for WE-1, and **47.38** across all three bills.

    **REMITTED is Σ DEBITS to the same account from remittance-sourced entries**
    — the JE that drains the liability, written by
    `apps/ledger/journal.record_tax_remittance` through the posting service.
    Reading it out of the books rather than out of a `tax_remittances` register
    is deliberate: the register does not exist yet (r13 #3), and when it does,
    the books remain the number that has to be right.

    ⚠ **COLLECTED IS A FIGURE SINCE 2026-09-02 (CR-060 C19 / task T7d).** This
    paragraph read *"COLLECTED is None, with the reason attached… an
    `allocations` row carries no line class, so tax inside a cleared payment is
    only knowable for an invoice covered IN FULL"*. `allocation_classes`
    (payments/0015) now records what every payment met inside every bill, in the
    same transaction as the allocation, so the collected basis is READ.

    **AND THE PARTIAL-COVERAGE ARGUMENT IS NOT SETTLED BY US.** Two signed
    rulings still disagree — `OQ-174` (2026-08-12) says a partial payment covers
    TAX FIRST; `BR-PAY-010` makes the sequence a TENANT SETTING whose shipped
    default puts tax second. Neither is overturned here and neither needs to be:
    whatever order a tenant set is the order their money walked, and the walk is
    written down afterwards. That is CR-060 C19's own disposition — *"recording
    the breakdown makes the question moot"*.

    **ONE APPORTIONMENT IS OURS AND IT IS BR-LED-794**, recorded in the decision
    log with its worked figure: payments records tax as ONE class, so a bill's
    collected tax is split across the authorities THAT BILL charged in
    proportion to what each was billed on it. It is exact whenever the bill's
    tax was met in full — LE-3's signed **20.97** case — and it always sums to
    the money that actually came in.

    **OUTSTANDING is therefore given per basis**, never as one number. A single
    `outstanding` column would have to pick a basis, and LE-3's whole point is
    that State remits on collected while County remits on billed — a default
    would be wrong for one of them in the first month it ran.

    **AND WHICH BASIS EACH AUTHORITY FILES ON IS NOW STATED, not left open.**
    PO ruling 2026-08-12: *"E Remit on what you BILLED, not what you collected -
    this is also correct"* — both bases are legitimate and the choice is the
    customer's. Until that ruling this table showed a utility both figures and
    had nowhere to record which one they file on, which is what the
    `per_authority_remitting_basis_is_not_stored` problem code reported. The
    choice now lives on the S71 Finance-controls page keyed by the authority's
    own 2200-nn account code, this function reads it (`basis_of` below) and puts
    it on the row, and the problem code is reported only for the authorities
    still to be ruled on — naming them, so a first save cannot quietly hide the
    two nobody has decided yet.
    """
    accounts = {
        str(row.id): row
        for row in models.LedgerAccount.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True
        )
        # CR-196-BRC10 5b — code OR minted slot, so a renamed authority stays.
        if chart.is_tax_payable_account(row.code, row.seed_key)
    }
    if not accounts:
        return {
            "basis": {"billed": BASIS_POSTING, "collected": BASIS_POSTING},
            "period": {"start": start, "end": end},
            "currency": None,
            "rows": (),
            # `billed_from_bills` is ZERO and not None here for a reason worth
            # naming: no tax-payable account exists, so *"the bills charged no
            # authority anything"* is a true answer rather than a missing one.
            "totals": {
                "billed": ZERO,
                "collected": None,
                "remitted": ZERO,
                "billed_from_bills": ZERO,
            },
            "unavailable": (GAP_COLLECTED_IS_A_FLOOR, GAP_REMITTING_BASIS_SETTING),
        }

    # PO ruling 2026-08-12 — which basis this tenant FILES on, per authority.
    # Read once for the whole table: a per-row read would be one query per
    # authority for a value that is one document.
    basis_of = _remitting_basis_by_authority()

    billed: dict[str, Decimal] = {key: ZERO for key in accounts}
    remitted: dict[str, Decimal] = {key: ZERO for key in accounts}
    authority_lines = _posted_lines(start=start, end=end).filter(
        ledger_account_id__in=list(accounts)
    )
    # DEF-081 — this table is what a utility FILES from. A tax liability summed
    # across two currencies is remitted to a real revenue authority in one of
    # them, and the shortfall is discovered by the authority, not by us.
    currency = _one_currency(
        authority_lines, figure="the per-authority remittance table"
    )
    # OQ-1190 — THE BILLS BEHIND EACH ACCOUNT'S CREDITS. Collected from the very
    # same rows the `billed` column is summed from, so the two figures cannot be
    # taken over different sets of bills: whatever the window, the basis and the
    # void/corrected treatment turn out to be, they are identical on both sides
    # because there is one selection, here.
    bills_behind: dict[str, set[str]] = {key: set() for key in accounts}
    # CR-060 C19 / task T7d — the same credits, kept PER BILL as well as summed.
    # BR-LED-794 splits a bill's collected tax across the authorities that bill
    # charged, in proportion to what each was billed ON THAT BILL, so the split
    # is taken from these rows rather than from a second read: one selection,
    # here, exactly as the OQ-1190 note above says about the billed column.
    billed_per_bill: dict[str, dict[str, Decimal]] = {key: {} for key in accounts}
    for account_id, side, amount, source, source_id in authority_lines.values_list(
        "ledger_account_id",
        "side",
        "amount",
        "journal_entry__source_type",
        "journal_entry__source_id",
    ):
        key = str(account_id)
        if source in BILL_SOURCE_TYPES and side == models.SIDE_CREDIT:
            billed[key] += amount
            if source_id is not None:
                bill = str(source_id)
                bills_behind[key].add(bill)
                billed_per_bill[key][bill] = billed_per_bill[key].get(bill, ZERO) + amount
        elif source == "remittance" and side == models.SIDE_DEBIT:
            remitted[key] += amount

    # ONE CALL ACROSS THE WHOLE TABLE, not one per authority — a monthly return
    # window holds every bill of the month and a per-row call would re-read them
    # once per authority.
    bill_side = _tax_by_authority_for_accounts(bills_behind)

    # ═══════════════════════════════════════════════════════════════════════
    # ⚠ DEF-LED-6705 — WHAT IS STILL OWED IS A BALANCE, NEVER A PERIOD DELTA
    # ═══════════════════════════════════════════════════════════════════════
    # `outstanding_billed` READ `billed - remitted` over the REQUESTED WINDOW,
    # while the `tie_out` below has always been `gl_totals(end=end)` — start
    # `None`, so inception-to-date. The tie-out block's own comment claimed the
    # two were "summed from the same rows here, which is the point — one
    # derivation cannot drift from itself"; they were two different selections
    # and the comment was hard-won law 1 exactly (*a comment claiming a
    # guarantee is not the guarantee*). Measured on the seeded tenant at tip
    # c81a4f651, window 2026-09-01..30: the table footed to **0.00** and the
    # tie-out beside it on the same screen said **600.26**. The PO saw the same
    # screen say **−65.00** and **266.75**.
    #
    # **THE BALANCE IS THE RIGHT NUMBER AND THE DELTA WAS THE WRONG ONE.**
    # BR-LED-007 is *"tax payable = remittance outstanding"* — what a utility
    # still owes an authority is everything it has ever been charged and not yet
    # handed over, which does not become untrue because the report window starts
    # after the bill. The delta also could not see the two movements the books
    # carry and neither column names: a credit note debiting the liability, and
    # a remittance settling tax billed BEFORE the window — which is what made
    # the PO's *Still owed* go NEGATIVE (DEF-LED-6708).
    #
    # So it is taken from `gl_totals(end=end)`, the call the tie-out is already
    # made of, and the two now genuinely ARE one derivation rather than a
    # sentence saying so. `test_def_led_6705_tie_out_foots.py` asserts it over a
    # window that excludes every posting, where the old code differed by the
    # whole liability.
    # CR-196-BRC10 5b — the same test as the account list above, by id: a
    # `gl_totals` row carries the code and not the slot, and retired tax
    # accounts must stay in the tie-out exactly as they did when this read the
    # code prefix.
    tax_ids = {
        str(pk)
        for pk in models.LedgerAccount.objects.filter(tenant_id=_tenant_id())
        .filter(selectors.tax_payable_q())
        .values_list("pk", flat=True)
    }
    balance_to_date = {
        str(total.account_id): total.net_credit
        for total in gl_totals(end=end)
        if str(total.account_id) in tax_ids
    }

    # ═══════════════════════════════════════════════════════════════════════
    # THE COLLECTED BASIS — CR-060 C19 / task T7d. It used to be `None`.
    # ═══════════════════════════════════════════════════════════════════════
    # BR-LED-002 requires BOTH bases always and this one was reported absent for
    # a true reason: an `allocations` row carried no line class, so *"how much
    # of this bill's tax has actually been paid"* was not a fact anybody held.
    # `payments/0015` gives it one. `apps/ledger/payments_seam` reads it — ONE
    # call for the whole table, over exactly the bills the billed column was
    # summed from, so the two columns can never be taken over different sets.
    every_bill = tuple(sorted({bill for bills in bills_behind.values() for bill in bills}))
    collected_side = payments_seam.collected_tax_by_invoice(
        invoice_ids=every_bill, start=start, end=end
    )
    # Each bill's TOTAL billed tax, across every authority it charged — the
    # denominator BR-LED-794 apportions on.
    tax_per_bill: dict[str, Decimal] = {}
    for per_bill in billed_per_bill.values():
        for bill, amount in per_bill.items():
            tax_per_bill[bill] = tax_per_bill.get(bill, ZERO) + amount

    collected: dict[str, Decimal | None] = {key: None for key in accounts}
    if collected_side.collected is not None:
        collected = {key: ZERO for key in accounts}
        # ── BR-LED-794, APPLIED PER BILL AND NOT PER AUTHORITY ──────────────
        # The loop is over BILLS rather than over authorities, and the reason is
        # the rule's own third clause: *"it only ever divides money that was
        # genuinely collected, so the authority figures always sum to the
        # recorded collected total"*. That is a GUARANTEE, and a guarantee needs
        # the whole bill in view at once — rounding each authority's share
        # independently makes a cent appear or vanish, which on a tax return is
        # a figure nobody can reconcile and which no per-authority loop could
        # ever notice. A comment claiming a guarantee is not the guarantee
        # (hard-won law 1), so the arithmetic is arranged to make it true.
        for bill, whole in tax_per_bill.items():
            paid = collected_side.collected.get(bill)
            if paid is None or paid == ZERO:
                # No tax money met this bill in this window. A real 0.00 share
                # for every authority it charged, not an absence.
                continue
            if whole <= ZERO:  # pragma: no cover — a credit with no billed tax
                continue
            shares = {
                key: per_bill[bill]
                for key, per_bill in billed_per_bill.items()
                if bill in per_bill
            }
            if len(shares) == 1:
                # The bill charged ONE authority, so nothing is apportioned at
                # all and the figure is exact by construction.
                collected[next(iter(shares))] += paid
                continue
            # EXACT WHENEVER THE BILL'S TAX WAS MET IN FULL — `paid == whole`
            # makes each share `billed_here`, which is LE-3's signed 20.97 case
            # and the ordinary one. Rounded ONCE per share, half-up, at this
            # finalization (BR-RAT-003 / BR-LED-025).
            rounded: dict[str, Decimal] = {}
            remainders: list[tuple[Decimal, str]] = []
            for key, billed_here in shares.items():
                exact = paid * billed_here / whole
                down = exact.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                rounded[key] = down
                remainders.append((exact - down, key))
            # THE RESIDUAL CENT (or two), given to the largest remainder first —
            # the standard apportionment tie-break, deterministic on the account
            # id so two runs of the same month produce the same return.
            residual = paid - sum(rounded.values(), ZERO)
            step = TWO_PLACES if residual > ZERO else -TWO_PLACES
            remainders.sort(key=lambda item: (item[0], item[1]), reverse=residual > ZERO)
            index = 0
            while residual != ZERO and remainders:
                key = remainders[index % len(remainders)][1]
                rounded[key] += step
                residual -= step
                index += 1
            for key, amount in rounded.items():
                collected[key] += amount

    rows = tuple(
        AuthorityRemittanceRow(
            account_id=key,
            code=account.code,
            name=account.name,
            billed=billed[key],
            collected=collected[key],
            remitted=remitted[key],
            # DEF-LED-6705 — the BOOKS' balance for this authority at `end`,
            # every movement included, not `billed - remitted` over the window.
            outstanding_billed=balance_to_date.get(key, ZERO),
            # ⚠ AND THIS ONE IS STILL A WINDOW FIGURE, DELIBERATELY AND NOT BY
            # OVERSIGHT. A collected-basis balance is `collected to date −
            # remitted to date`, and collected-to-date means apportioning every
            # payment this utility has ever cleared across every bill it has
            # ever issued — `payments_seam.collected_tax_by_invoice` takes the
            # invoice ids as a tuple, so at the top of the ICP that is one call
            # carrying every bill of every month (NFR-3's shape). It is NOT
            # rendered: `RemittancePage`'s *Still owed* column and its footer
            # both draw the BILLED basis, which is the one BR-LED-007 ties to
            # the books. Converting it is `DEF-LED-6705`'s remaining half and it
            # needs a seam that takes a window rather than a bill list.
            outstanding_collected=(
                None if collected[key] is None else collected[key] - remitted[key]
            ),
            # The tenant's own choice, or None where they have not made one.
            # Never a default: LE-3 puts State on collected and County on billed
            # in the same month, so a shipped basis is wrong for one of them.
            remitting_basis=basis_of.get(account.code),
            # OQ-1190 — the same authority's money as the BILLS charged it.
            authority_name=bill_side.get(key, {}).get("authority_name"),
            billed_from_bills=bill_side.get(key, {}).get("subtotal"),
            bill_line_count=bill_side.get(key, {}).get("line_count"),
            bill_count=len(bills_behind.get(key, ())),
            billed_delta=(
                None
                if bill_side.get(key, {}).get("subtotal") is None
                else bill_side[key]["subtotal"] - billed[key]
            ),
            bills_agree=(
                None
                if bill_side.get(key, {}).get("subtotal") is None
                else bill_side[key]["subtotal"] == billed[key]
            ),
            problems=tuple(bill_side.get(key, {}).get("problems", ())),
        )
        for key, account in sorted(accounts.items(), key=lambda item: item[1].code)
    )
    unset_authorities = tuple(row.code for row in rows if row.remitting_basis is None)
    return {
        "basis": {"billed": BASIS_POSTING, "collected": BASIS_POSTING},
        "period": {"start": start, "end": end},
        "currency": currency,
        "rows": rows,
        "totals": {
            "billed": sum((row.billed for row in rows), ZERO),
            # `None` when ANY row's collected figure is absent — a partial sum
            # under a column heading a return is filed from reads as the whole
            # and is not, which is the discipline `billed_from_bills` below
            # already states in its own words.
            "collected": (
                None
                if any(row.collected is None for row in rows)
                else sum((row.collected or ZERO for row in rows), ZERO)
            ),
            "remitted": sum((row.remitted for row in rows), ZERO),
            "outstanding_billed": sum((row.outstanding_billed for row in rows), ZERO),
            "outstanding_collected": (
                None
                if any(row.outstanding_collected is None for row in rows)
                else sum((row.outstanding_collected or ZERO for row in rows), ZERO)
            ),
            # CR-060 C19 — how much allocated money in this window carried no
            # class breakdown, so the floor is a number rather than a caveat.
            "allocated_without_breakdown": collected_side.allocated_without_breakdown,
            "allocations_without_breakdown": collected_side.allocations_without_breakdown,
            # OQ-1190 — the bill-sourced column's own total, and ONLY when every
            # row has a figure. A partial sum under a column heading is worse
            # than no sum: it reads as the whole and is not, and a finance
            # officer would file a return from it. `None` when any authority's
            # bill-side figure is absent, and the row itself says which.
            "billed_from_bills": (
                None
                if any(row.billed_from_bills is None for row in rows)
                else sum((row.billed_from_bills or ZERO for row in rows), ZERO)
            ),
        },
        # BR-LED-007: *"tax payable = remittance outstanding"*. The S36 tie-out
        # compares the GL balance against this; both are summed from the same
        # rows here, which is the point — one derivation cannot drift from
        # itself.
        # BR-LED-007: *"tax payable = remittance outstanding"*. DEF-LED-6705 —
        # this is now summed from `balance_to_date`, the SAME dict each row's
        # `outstanding_billed` is taken from, so the screen cannot print two
        # different answers to one question again. It was the second half of a
        # sentence that used to claim this and was not true.
        "tie_out": {"tax_payable_gl": sum(balance_to_date.values(), ZERO)},
        "unavailable": (
            # Reported only while some allocated money in this window carries no
            # breakdown, or payments publishes no read. A gap that never cleared
            # would be noise a finance officer learns to scroll past — the same
            # reasoning the remitting-basis gap below already carries.
            *(
                (GAP_COLLECTED_IS_A_FLOOR,)
                if collected_side.collected is None
                or collected_side.allocations_without_breakdown
                else ()
            ),
            *(
                (
                    {
                        "code": payments_seam.COLLECTED_UNAVAILABLE,
                        "br_ref": "BR-LED-002 · BR-TEN-013",
                        "detail": "the payments module publishes no read of which charge "
                        "classes a payment met, so the collected basis cannot be produced on "
                        "this deployment and is reported absent rather than filled with the "
                        "billed figure — which would have a utility remit tax on money nobody "
                        "has paid.",
                        "wanted_reads": (
                            "apps.payments.selectors.collected_by_class_for_invoices("
                            "invoice_ids, *, line_class, start, end)",
                        ),
                    },
                )
                if collected_side.collected is None
                else ()
            ),
            # Reported only while an authority has no chosen basis — and it
            # names them. A gap that never cleared would be noise a finance
            # officer learns to scroll past.
            *((_remitting_basis_gap(unset_authorities),) if unset_authorities else ()),
            GAP_TAX_AUTHORITY_NAME,
            {
                "code": "filing_history_has_no_home",
                "br_ref": "BR-LED-019 · B2 Addendum r13 #3",
                "detail": "BR-LED-019 (CONFIRMED): *remittance records carry a filing "
                "CONFIRMATION REF + receipt file attachment (auditor artifact)*. "
                "`tax_remittances` (r13 #3) does not exist, so neither the confirmation ref "
                "nor the receipt has a column. `apps/ledger/journal.record_tax_remittance` "
                "posts the balanced JE and puts the confirmation ref in the entry MEMO and the "
                "audit payload — both append-only and both auditable — and REFUSES to accept a "
                "receipt file, because inventing a home for a signed field is worse than not "
                "having one.",
                "wanted_reads": (),
            },
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — the S56 journal-entry list (BR-LED-012's IS-5 capability row)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class JournalEntryRow:
    """One row of the S56 journal list — EP-LED-04's capability matrix.

    *"JE # · Date · Type · Memo · Source · Debit · Credit · Status / +Links
    (reversal-of / auto-reverse), Posted by"*.

    `reversed_by_entry_id` and `reversal_of_entry_id` are BOTH carried because
    r13 #2 gives the pair two links and US-LED-013 TC-2 renders both directions:
    JE-104 shows as *reversed*, JE-105 as *the reversal, linked*. One column
    cannot answer both questions.
    """

    entry_id: str
    #: The entry's OWN CHAR(3) (DEF-081). A row's debit and credit are that one
    #: entry's lines and nothing else, so unlike every Σ in this module they are
    #: always lawful — and this column is what lets a finance officer looking at
    #: a refused trial balance SEE which entries carry the foreign code. It has
    #: NO default on purpose: this list is the diagnostic surface for a mixed
    #: book, and a column that could silently be None would be the one thing on
    #: the page a reader must not have to wonder about.
    currency: str | None
    #: BR-LED-021 (PO 2026-08-12, OQ-176 — *"Approve a JE- series"*). The
    #: matrix's own first column, and it now has a source. `None` on a DRAFT by
    #: ruling (*"a draft has NO number"*) and on a posted entry whose tenant has
    #: no `journal_entry` number series row — the second case is named in
    #: `unavailable`, the first is simply what a draft is.
    number: str | None
    entry_date: date
    type: str
    status: str
    memo: str | None
    source_type: str | None
    source_label: str
    source_mapped: bool
    debit: Decimal
    credit: Decimal
    balanced: bool
    reversal_of_entry_id: str | None
    reversed_by_entry_id: str | None
    auto_reverse_entry_id: str | None
    posted_at: Any
    #: Record links (PO 2026-10-19) — `journal_entries.source_id`, the polymorphic
    #: reference B2 §2 pairs with `source_type`. It lets the Source cell OPEN the
    #: bill, payment or refund the entry was posted from. Never a visible value
    #: (B14 rule 31): the screen builds an address from it and prints the word.
    source_id: str | None = None


# ── The journal's SORT vocabulary (`P1.18`, Finance blueprint p020 item 6) ──
#
# The drawing puts a `⇅` on exactly TWO columns — ENTRY NO. and DATE — so those
# are the two a clerk can sort by, and nothing else is offered.
#
# ⚠ **`number` DOES NOT ORDER BY `number`, AND THAT IS THE WHOLE POINT.** The
# PO ruled the entry-number format on 2026-09-23 — *"you need je-MMDDYY- nnnn
# like this otherwise it will not work"* — which renders `JE-{MM}{DD}{YY}-{0000}`.
# `MMDDYY` does not sort chronologically as TEXT: `JE-011526-0001` precedes
# `JE-020325-0001` and is ELEVEN MONTHS OLDER. The blueprint calls this *"one
# consequence to build around rather than to ask about"*. So the Entry no.
# column sorts by `entry_date` then by the row's own sequence, never by the
# rendered string, and `test_def_led_6493_journal_pages_in_sql.py` pins it so a
# later lane "simplifying" this to `order_by("number")` goes red instead of
# silently reordering the journal.
#
# ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN.** A page is a window over an ORDER;
# if the order is not total, two rows that compare equal may swap between page 1
# and page 2 and a clerk sees one row twice and another never. `created_at` is
# not unique under a bulk insert, so `id` closes both tuples — the tiebreak
# `core.pagination.order_terms` refuses to add silently.
JOURNAL_SORTS: tuple[str, ...] = ("entry_date", "number")
JOURNAL_DEFAULT_SORT = "entry_date"
JOURNAL_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "entry_date": ("entry_date", "created_at", "id"),
    "number": ("entry_date", "created_at", "id"),
}

#: How many ids a reported gap may put on the wire. `NFR-3` again, one layer in:
#: an unbounded id list inside a bounded page is the same breach wearing the
#: fix's clothes — at the top of T5 that is 40,000 UUIDs beside fifty rows. The
#: COUNT is exact and travels beside them, so nothing is understated.
GAP_ID_SAMPLE = 50


def journal_entry_list(
    *,
    start: date | None = None,
    end: date | None = None,
    entry_type: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    premises_id: Any = None,
    ledger_account_id: Any = None,
    sort: str | None = None,
    direction: str = "desc",
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """BR-LED-012 — the journal list, with the links first-class.

    ⚠ **THE TWO NEWEST FILTERS SELECT ENTRIES BY WHAT THEIR *LINES* CARRY, AND
    THE ROW IS STILL THE WHOLE ENTRY (CR-060 C24 · C23).** `premises_id` and
    `ledger_account_id` both ask *"which entries have a line like this?"* and
    then show those entries in full — debit and credit totals over ALL their
    lines, not over the matching ones.

    **That is deliberate and it is the opposite of `trial_balance`'s choice**,
    for a reason worth stating once: a trial balance is a table of SUMS, so
    narrowing it must narrow the sums or the figures would be about rows the
    filter excluded. This is a list of ENTRIES, and half an entry is not an
    entry — a row whose debit and credit came from a subset of its lines would
    show `balanced: false` on entries that balance perfectly, which is the same
    false alarm C24's trial-balance note refuses one function up.

    **`ledger_account_id` IS C23's cheaper half and it is what a clerk's click
    actually means.** C23 asks to open a trial-balance line to the entries behind
    it; the row a clerk clicks IS a chart account, this list already sits on the
    same screen, and answering it here needs no new read model, no new route and
    no new serializer. The alternative considered and not taken was
    `journal_entry_detail(entry_id)` — a second read model returning one entry —
    which is a larger surface for a smaller question, and the screens lane
    recommended this shape for the same reason. **It stays honest about scope:
    this filter says WHICH ENTRIES TOUCHED THE ACCOUNT, and it does not say what
    each entry contributed TO that account. That second figure is the dimension
    expansion, which is still unbuilt** (see the module header's own list).

    *"drafts, posted entries, reversals and links are all first-class visible"*
    (US-LED-013 §1). Default sort is `entry_date desc`, which is the epic's
    capability matrix verbatim.

    **DRAFTS ARE INCLUDED HERE AND NOWHERE ELSE IN THIS MODULE.** Every money
    figure above filters `status='posted'` because a draft is not in the books;
    this list is the one surface whose job is to show that a draft EXISTS so
    somebody can finish or delete it. The `status` column is what keeps the two
    facts apart, and `debit`/`credit` on a draft row are what it WOULD post —
    with `balanced` saying whether it may (BR-LED-003: *balanced required at
    post*).

    Two columns of the matrix are NOT filled and are reported rather than left
    blank — see `unavailable`: the **JE #** (no numbering series exists for
    journal entries) and **Posted by** (the actor lives in `audit_log`, not on
    the entry).

    **DEF-081 — THIS IS THE ONE READ IN THE MODULE THAT NEVER REFUSES A MIXED
    BOOK, AND THAT IS THE DESIGN.** Every figure elsewhere is a Σ ACROSS entries
    and is refused when the entries disagree on currency. A row here is ONE
    entry: its debit and credit are that entry's own lines, in that entry's own
    currency, which the row now carries. So nothing here can be summed wrongly —
    and this becomes the only surface on which a finance officer whose trial
    balance just refused can find WHICH entries carry the foreign code and
    reverse them. A guard that darkened every ledger screen at once would leave
    no way to diagnose the state it was complaining about. `currencies` on the
    result names the distinct codes in the filtered set, so the screen can say
    so in a banner without counting rows.

    ⚠ **`limit` TAKES THE PAGE IN SQL, AND OMITTING IT MEANS EXACTLY WHAT IT
    ALWAYS MEANT (`DEF-LED-6493` · `NFR-3` · `P1.8`).** Until 2026-09-24 this
    function built EVERY matching entry and `apps/ledger/api.py` handed the
    result to `paginate_queryset`, which has to have the whole list before it
    can slice it. The wire response was bounded — which is what 11b G5 checks —
    and the query was not, so at the top of T5 that is **40,000 entries built to
    draw fifty**. Measured on the unfixed code: **67 statements over 60 entries
    and 307 over 300**, one per entry.

    **With `limit`, `rows` is ONE PAGE and `total` is the whole filtered count**
    (a `COUNT(*)`, so a clerk on page 1 of 40,000 is told there are 40,000
    without 40,000 rows being built). **Without it, `rows` is everything and
    `total` equals `len(rows)`** — eleven existing callers read this function as
    the whole answer and not one of them changes.

    ⚠ **THREE FACTS ON THIS RESULT ARE ABOUT THE FILTERED SET AND NOT ABOUT THE
    PAGE, AND EACH WOULD HAVE BROKEN SILENTLY.** `total`, `currencies` (DEF-081's
    mixed-book banner) and the `posted_entries_without_a_je_number` gap are all
    computed in SQL over the WHOLE set. Derived from the page instead, the same
    screen would state a different fact about one book depending on which page a
    clerk stopped on — the banner would go quiet on page 2, and the gap would
    count fifty rows on page 1 and ten on page 4.

    ⚠ **AND THE REVERSAL MIRROR IS BATCHED, WHICH IS WHERE THE PER-ROW COST
    ACTUALLY WAS.** `entry.reversed_by.first()` inside the row loop is one
    statement PER ROW — visible in the measurement above as 307-over-300 — so
    bounding the page alone would have left fifty statements per screen instead
    of one. The mirror for the whole page is now read in a single
    `reversal_of_id__in` query.

    ⚠ **NO CAP IS INTRODUCED ANYWHERE (`NFR-5`).** `limit` is what the CALLER
    asked for, `offset` is where they asked to start, and neither refuses a row
    that exists. There is no maximum account count, no maximum entry count and
    nothing here that would have to be REMOVED when T4 arrives.
    """
    entries = models.JournalEntry.objects.filter(tenant_id=_tenant_id())
    if start is not None:
        entries = entries.filter(entry_date__gte=start)
    if end is not None:
        entries = entries.filter(entry_date__lte=end)
    if entry_type:
        entries = entries.filter(type=entry_type)
    if status:
        entries = entries.filter(status=status)
    if source_type:
        entries = entries.filter(source_type=source_type)
    # CR-060 C24 / C23 — select the ENTRY by what its LINES carry. Both read the
    # stamp written at posting time and neither joins account → unit → premises
    # at read time, for the reason gap 1 in the module header records.
    #
    # ⚠ `lines__…` on a to-many relation would DUPLICATE an entry once per
    # matching line, so a screen would show the same journal entry three times
    # because three of its lines named the property. The subquery form asks the
    # existence question once per entry, which is the question being asked.
    if premises_id is not None:
        entries = entries.filter(
            pk__in=models.JournalLine.objects.filter(
                tenant_id=_tenant_id(), premises_id=premises_id
            ).values("journal_entry_id")
        )
    if ledger_account_id is not None:
        entries = entries.filter(
            pk__in=models.JournalLine.objects.filter(
                tenant_id=_tenant_id(), ledger_account_id=ledger_account_id
            ).values("journal_entry_id")
        )
    if search:
        # The matrix's search fields are *"JE #, memo"*, and since BR-LED-021
        # (PO 2026-08-12, OQ-176) BOTH exist. A clerk told to "look at JE-105"
        # types exactly that; before the series was approved this box could only
        # match the memo, and the reason was reported on every response.
        #
        # `DEF-LED-10071` J1 (PO 2026-10-12, *"J1 - this is good add cutomer
        # name to search"*) — the same box ALSO finds an entry when ANY of its
        # lines belongs to a matching account number, customer number, customer
        # name, premises address or unit label. The line match is the
        # `premises_id` filter's own shape above: an existence question asked
        # once per ENTRY through a `pk__in` subquery, so an entry with three
        # matching lines is one row, and the row's debit and credit are still
        # totalled over ALL its lines below. Every leg is a lazy subquery from
        # the owning module (`dimension_seam.journal_line_search`), so this is
        # still one SQL statement and the page is still taken in SQL (`NFR-3`).
        line_match = models.JournalLine.objects.filter(tenant_id=_tenant_id()).filter(
            dimension_seam.journal_line_search(search)
        )
        entries = entries.filter(
            Q(number__icontains=search)
            | Q(memo__icontains=search)
            | Q(pk__in=line_match.values("journal_entry_id"))
        )
    # `P1.18` — the ordering, from the two-name vocabulary above. `number` maps
    # to the DATE terms on purpose; see `JOURNAL_SORT_COLUMNS`.
    entries = entries.order_by(
        *order_terms(
            sort,
            direction,
            columns=JOURNAL_SORT_COLUMNS,
            default=JOURNAL_DEFAULT_SORT,
        )
    )

    # ── The three whole-set facts, in SQL, BEFORE the page is taken ──────────
    # Each of these is a statement about the FILTERED SET. Computed from `rows`
    # after a slice they would each become a statement about fifty arbitrary
    # entries, and every one of them would still look right on a fixture.
    total = entries.count()
    # ⚠ `.order_by()` WITH NO ARGUMENT IS LOAD-BEARING AND ITS ABSENCE IS
    # SILENT. Django puts an ordered queryset's ORDER BY columns into the
    # SELECT, so `DISTINCT` then collapses on (currency, entry_date, …) and
    # nothing collapses at all: the first draft of this line returned
    # `('USD','USD','USD','USD','USD','USD','USD','USD','USD')` for a
    # nine-entry single-currency book, and the mixed-currency BANNER would have
    # fired on every screen in the product. Clearing the ordering is what makes
    # DISTINCT mean what it reads as.
    currencies = tuple(
        sorted(
            code
            for code in entries.order_by().values_list("currency", flat=True).distinct()
            if code
        )
    )
    missing_number = entries.filter(status=models.JE_POSTED).filter(
        Q(number__isnull=True) | Q(number="")
    )
    unnumbered_total = missing_number.count()
    # BOUNDED (`NFR-3`): the exact COUNT travels, and a sample of the ids does.
    unnumbered = tuple(
        str(value) for value in missing_number.values_list("pk", flat=True)[:GAP_ID_SAMPLE]
    )

    # ── The page, in SQL ────────────────────────────────────────────────────
    if limit is not None:
        start_at = max(offset or 0, 0)
        entries = entries[start_at : start_at + max(limit, 0)]

    page_ids = [entry.pk for entry in entries]

    totals: dict[str, dict[str, Decimal]] = {}
    for entry_id, side, amount in models.JournalLine.objects.filter(
        tenant_id=_tenant_id(), journal_entry_id__in=page_ids
    ).values_list("journal_entry_id", "side", "amount"):
        bucket = totals.setdefault(
            str(entry_id), {models.SIDE_DEBIT: ZERO, models.SIDE_CREDIT: ZERO}
        )
        bucket[side] += amount

    # r13 #2 gives the reversal pair TWO links and both travel. This is the read
    # that used to be `entry.reversed_by.first()` INSIDE the row loop — one
    # statement per row, which is where 307-statements-over-300 came from.
    mirrors: dict[Any, Any] = dict(
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), reversal_of_id__in=page_ids
        ).values_list("reversal_of_id", "pk")
    )

    rows: list[JournalEntryRow] = []
    for entry in entries:
        bucket = totals.get(
            str(entry.pk), {models.SIDE_DEBIT: ZERO, models.SIDE_CREDIT: ZERO}
        )
        label, mapped = source_vocabulary_for(entry.source_type)
        mirror = mirrors.get(entry.pk)
        rows.append(
            JournalEntryRow(
                entry_id=str(entry.pk),
                currency=entry.currency,
                number=entry.number,
                entry_date=entry.entry_date,
                type=entry.type,
                status=entry.status,
                memo=entry.memo,
                source_type=entry.source_type,
                source_label=label,
                source_mapped=mapped,
                debit=bucket[models.SIDE_DEBIT],
                credit=bucket[models.SIDE_CREDIT],
                balanced=bucket[models.SIDE_DEBIT] == bucket[models.SIDE_CREDIT],
                reversal_of_entry_id=(
                    str(entry.reversal_of_id) if entry.reversal_of_id else None
                ),
                reversed_by_entry_id=str(mirror) if mirror is not None else None,
                auto_reverse_entry_id=(
                    str(entry.auto_reverse_entry_id)
                    if entry.auto_reverse_entry_id
                    else None
                ),
                posted_at=entry.posted_at,
                source_id=str(entry.source_id) if entry.source_id else None,
            )
        )
    # BR-LED-021 CLOSED OQ-176 and the JE # column now has a source. What can
    # still be missing is narrower and is reported only when it is TRUE: a
    # POSTED entry with no number means this tenant has no `journal_entry`
    # number-series row, so `apps/ledger/manual_je.py` posted it and reported
    # the gap instead of faking a number. A DRAFT with no number is not a gap —
    # it is the ruling (*"a draft has NO number"*).
    #
    # ⚠ **COUNTED OVER THE WHOLE FILTERED SET, NOT OVER THE PAGE** — computed
    # above, in SQL, before the slice. Counted from `rows` this would report
    # fifty on page 1 and ten on page 4 of the same book, so the same screen
    # would state a different fact about one tenant depending on where a clerk
    # stopped scrolling.
    gaps: list[dict[str, Any]] = []
    if unnumbered_total:
        gaps.append(
            {
                "code": "posted_entries_without_a_je_number",
                "br_ref": "BR-LED-021 · BR-TEN-035",
                "detail": "the S56 matrix opens with a JE # column and LE-8 names three entries "
                "JE-104 / JE-105 / JE-106. The `JE-` series is APPROVED (PO 2026-08-12, OQ-176) "
                "and `journal_entries.number` carries it, but "
                f"{unnumbered_total} posted entries here carry none: this tenant has no "
                "`journal_entry` row in `number_series`, so the allocator had nothing to "
                "allocate from. Provisioning seeds a series row per entry in "
                "`apps.tenancy.services.SERIES_DEFAULTS` and that map has no journal entry — "
                "the same gap `apps/metering/services.py` reports as `numbering_series_missing` "
                "for premises. A number is NEVER faked, and a posted entry cannot be numbered "
                "afterwards (hard rule 4).",
                "wanted_reads": (
                    "apps.tenancy.services.SERIES_DEFAULTS[core.numbering.JOURNAL_ENTRY]",
                ),
                # The COUNT is exact and the ids are a bounded SAMPLE of it
                # (`GAP_ID_SAMPLE`). A screen that needs every id filters the
                # list to them; a response that carried 40,000 UUIDs beside
                # fifty rows would be `NFR-3` breached inside its own fix.
                "entry_count": unnumbered_total,
                "entry_ids": unnumbered,
            }
        )
    # ⚠ **`posted_by_is_in_audit_log_not_on_the_entry` WAS APPENDED HERE
    # UNCONDITIONALLY UNTIL 2026-09-25, AND IT IS REMOVED (`DEF-LED-6643`).**
    #
    # It carried no catalogue key, so `gapSentence` fell through to
    # `finance.gap.unknown` and **every Journal and every Trial balance in the
    # product printed "The books will not state this. The reason has no wording
    # yet." — twice on one screen**, to every clerk, forever. It was not
    # conditional on anything: there was no state in which it did not fire.
    #
    # **It is removed rather than given words, because it is not an absence a
    # clerk ever meets.** It described the *Posted by* column of the S56
    # capability matrix — a column **no screen in this product offers**
    # (`grep -rn 'posted_by' 07-frontend/src/features/ledger` returns nothing).
    # A stated absence is for a figure a reader went looking for and did not
    # find; this was a note to a reviewer about an optional column, and B14
    # rule 33 puts RATIONALE — why a control is absent — at zero words on
    # screen.
    #
    # **Nothing about the product changed and nothing is hidden.** No actor
    # column exists on `journal_entries`, deliberately: the trail is
    # `audit_log`'s job (BR-LED-012, CLAUDE.md rule 7), every posting writes a
    # `journal.posted` row naming who did it, and joining the two is an audit
    # read this module does not make because B1 forbids reaching into another
    # module's table. That reasoning lives here, which is where a reason
    # belongs. **The day a screen offers a Posted-by column, this gap comes
    # back — with a catalogue key, which is what it never had.**
    return {
        "basis": BASIS_POSTING,
        "rows": tuple(rows),
        # The WHOLE filtered count, from a `COUNT(*)`. Without a `limit` it is
        # `len(rows)` by construction, which is what every existing caller has
        # always been able to compute for itself.
        "total": total,
        # DEF-081 — the distinct codes present in the FILTERED SET.
        # ⚠ **THIS WAS DERIVED FROM `rows` UNTIL 2026-09-24 AND A PAGE WOULD
        # HAVE BROKEN IT SILENTLY.** The banner exists so a finance officer
        # whose trial balance just refused can find the foreign-currency
        # entries; derived from fifty rows it goes quiet on page 2 and the one
        # screen that could diagnose the refusal stops mentioning it.
        "currencies": currencies,
        "unavailable": tuple(gaps),
    }



# ══════════════════════════════════════════════════════════════════════════
# S56's OTHER HALF — ONE ENTRY, ITS LINES, AND THAT THEY BALANCE
# ══════════════════════════════════════════════════════════════════════════
# `04-docs/01-spec/11b-api-audit.md` line 436 names S56 **"Journal list +
# detail"** and gives it two routes — `GET /ledger/journal-entries` and
# `GET /ledger/journal-entries/{id}` — with *"lines expand to dimensions"*.
# The list shipped 2026-08-11. The detail did not, and `apps/ledger/api.py`'s
# own exception (1) has said so ever since: *"there is no read model for an
# entry's LINES with their dimensions … the read that closes it is named:
# `apps.ledger.reporting.journal_entry_detail(entry_id)`"*. The Finance
# blueprint's gap register carries the same finding as **G3**, ⛔, *"no read —
# journal_api.py is DELETE-only"*, and p020 item 7 draws the `👁` anyway.
#
# This is that function, under the name that exception chose for it.


@dataclass(frozen=True)
class JournalLineRow:
    """One side of the pair, with the five dimensions BR-LED-001 stamps on it.

    ⚠ **EVERY DIMENSION IS AN (id, label) PAIR AND THE SCREEN SHOWS THE LABEL**
    — B14 rule 31, *no database id is ever the visible value of a field*. The id
    travels because a screen may want to LINK on it; `DET-LED-6661` is what
    happens when one is printed instead.

    ⚠ **A LABEL MAY BE `None` WHILE ITS ID IS SET, AND THAT IS NOT THE SAME AS
    THE DIMENSION BEING ABSENT.** An id with no label is a row this product
    could not read a name for — a premises since deleted, a module read not
    published. The caller renders the dimension as present-and-unnamed rather
    than dropping the line, for the reason `dimension_seam.premises_labels`
    gives: a journal entry that quietly lost a line would stop balancing on
    screen while balancing perfectly in the books.

    `amount` is NON-NEGATIVE and `side` carries the direction, exactly as
    `journal_lines` stores it (B2 §2). There is one way to express a credit.
    """

    line_id: str
    ledger_account_id: str
    account_code: str | None
    account_name: str | None
    side: str
    amount: Decimal
    service_id: str | None
    service_label: str | None
    account_id: str | None
    account_label: str | None
    premises_id: str | None
    premises_label: str | None
    unit_id: str | None
    unit_label: str | None
    tax_authority_id: str | None
    tax_authority_label: str | None


#: The detail's own gap: a line names a tax authority and this module can put no
#: NAME beside it. It reuses `GAP_TAX_AUTHORITY_NAME`'s reasoning rather than
#: restating it, and it is reported ONLY when a line on this entry actually
#: carries one — a gap sentence that fires on every entry is `DEF-LED-6643`.
GAP_ENTRY_HAS_NO_LINES = {
    "code": "this_entry_has_no_lines",
    "br_ref": "BR-LED-003 · hard rule 5",
    "detail": "this entry carries no journal lines at all. A posted entry cannot reach that "
    "state — `apps/ledger/posting.py` writes the pair in one transaction and refuses an "
    "unbalanced set — so it is a DRAFT that was saved with its composer empty, which "
    "BR-LED-003 permits and which cannot be posted. Nothing is hidden and nothing is "
    "inferred: the entry exists, it has no sides, and it does not balance.",
    "wanted_reads": (),
}


def journal_entry_detail(
    entry_id: Any,
    *,
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """11b §2.10 / A1 S56 — one entry, its lines, and whether the two sides agree.

    **READ-ONLY, AND THE SHAPE SAYS SO.** Hard rule 4 makes a posted entry
    immutable for ever and BR-LED-003 makes the only correction a reverse +
    repost, which writes two NEW entries. Nothing here returns an editable
    field, a version token or an `updated_at`, because a detail that looked
    amendable would teach a clerk the books can be amended.

    ⚠ **`balanced` IS COMPUTED OVER THE WHOLE ENTRY, IN SQL, BEFORE THE PAGE IS
    TAKEN.** This is `journal_entry_list`'s own hardest-won lesson one level in:
    `total`, `currencies` and the unnumbered gap are whole-set facts there, and
    `debit`, `credit` and `balanced` are whole-ENTRY facts here. Derived from
    the page instead, a 120-line entry would report *"does not balance"* on
    page 1 and *"does not balance"* differently on page 2, of an entry that
    balances perfectly — the single most alarming false statement this screen
    could make.

    ⚠ **THE LINES PAGE (`NFR-3`), AND NOTHING ASSUMES A SMALL ENTRY.** A bill
    run posts one entry per invoice today, but a summary export JE
    (`BR-LED-017`, one JE per closed period) is one entry over a whole month of
    a utility's revenue, and at the top of T5 that is not a shape to guess at.
    `limit` slices in SQL and `line_total` is a `COUNT(*)` over all of them, so
    a clerk on page 1 is told how many there are without them all being built.
    **Omitting `limit` returns every line and `line_total == len(lines)`**,
    which is what every caller that wants the whole entry already means.

    ⚠ **NO CAP IS INTRODUCED (`NFR-5`).** `limit` is what the caller asked for
    and nothing here refuses a line that exists.

    ⚠ **`number` MAY BE `None` AND THAT IS A FACT, NOT A GAP TO FILL.** An
    opening-balance entry has no document number and never will; a DRAFT has no
    number by BR-LED-021's ruling (*"a draft has NO number"*); and a posted
    entry whose tenant has no `journal_entry` series row carries none for ever,
    because hard rule 4 freezes the column at post. All three travel as `None`.
    **A number is never composed here.** An invented one could not be withdrawn.

    Raises `errors.NotFoundError` for an id that is not one of THIS tenant's
    entries — a deny-as-not-found, so a forged id from another tenant is
    indistinguishable from one that never existed (rule 1, US-LED-002 TC-7).
    """
    tenant_id = _tenant_id()
    entry = (
        models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=str(entry_id)).first()
    )
    if entry is None:
        # ⚠ **DENY AS NOT FOUND, NEVER AS FORBIDDEN (HR-1 / G4).** An entry id
        # from another tenant and an id that never existed must be
        # byte-identical on the wire, or the 404 itself tells a stranger which
        # of our tenants holds which entry. `deny_as_not_found` records the
        # attempt server-side as a BR-AUD-018 row and serialises nothing.
        raise errors.deny_as_not_found("BR-TEN-003")

    lines_qs = models.JournalLine.objects.filter(
        tenant_id=tenant_id, journal_entry_id=entry.pk
    )

    # ── The whole-ENTRY facts, in SQL, BEFORE the page ──────────────────────
    # Each is a statement about the ENTRY. Computed from a slice they would each
    # become a statement about however many lines a clerk happened to be
    # looking at, and every one of them would still look right on a fixture.
    line_total = lines_qs.count()
    sides: dict[str, Decimal] = {models.SIDE_DEBIT: ZERO, models.SIDE_CREDIT: ZERO}
    for side, amount in lines_qs.values_list("side", "amount"):
        if side in sides:
            sides[side] += amount
    debit = sides[models.SIDE_DEBIT]
    credit = sides[models.SIDE_CREDIT]

    # ⚠ THE ORDER IS TOTAL. `id` closes the tuple for the reason
    # `JOURNAL_SORT_COLUMNS` records: a page is a window over an ORDER, and if
    # two lines compare equal they may swap between pages and a clerk sees one
    # twice and another never. Debits before credits is how every accountant
    # reads an entry, and `ledger_account_id` groups the sides consistently.
    page = lines_qs.order_by("side", "ledger_account_id", "id")
    if limit is not None:
        start_at = max(offset or 0, 0)
        page = page[start_at : start_at + max(limit, 0)]
    line_rows = list(page)

    # ── The labels, BATCHED over the page's id sets (never per line) ─────────
    account_ids = {row.ledger_account_id for row in line_rows}
    chart_labels: dict[str, tuple[str | None, str | None]] = {
        str(pk): (code, name)
        for pk, code, name in models.LedgerAccount.objects.filter(
            tenant_id=tenant_id, pk__in=account_ids
        ).values_list("pk", "code", "name")
    }
    premises_labels = dimension_seam.premises_labels(
        {row.premises_id for row in line_rows if row.premises_id}
    )
    customer_account_labels = dimension_seam.account_labels(
        {row.account_id for row in line_rows if row.account_id}
    )
    unit_labels = dimension_seam.unit_labels(
        {row.unit_id for row in line_rows if row.unit_id}
    )
    service_labels = _service_labels({row.service_id for row in line_rows if row.service_id})

    lines: list[JournalLineRow] = []
    for row in line_rows:
        code, name = chart_labels.get(str(row.ledger_account_id), (None, None))
        lines.append(
            JournalLineRow(
                line_id=str(row.pk),
                ledger_account_id=str(row.ledger_account_id),
                account_code=code,
                account_name=name,
                side=row.side,
                amount=row.amount,
                service_id=str(row.service_id) if row.service_id else None,
                service_label=(
                    service_labels.get(str(row.service_id)) if row.service_id else None
                ),
                account_id=str(row.account_id) if row.account_id else None,
                account_label=(
                    customer_account_labels.get(str(row.account_id))
                    if row.account_id
                    else None
                ),
                premises_id=str(row.premises_id) if row.premises_id else None,
                premises_label=(
                    premises_labels.get(str(row.premises_id)) if row.premises_id else None
                ),
                unit_id=str(row.unit_id) if row.unit_id else None,
                unit_label=unit_labels.get(str(row.unit_id)) if row.unit_id else None,
                tax_authority_id=(
                    str(row.tax_authority_id) if row.tax_authority_id else None
                ),
                # The AUTHORITY is the 2200-nn ledger account in the books
                # (BR-BIL-069 + B5 line 74 ❄️), so the account's own name is the
                # only name this module honestly has. Where the column is NULL —
                # which `GAP_TAX_AUTHORITY_NAME` records is every line today —
                # the dimension is simply absent and nothing is reported about
                # a fact the line does not carry.
                tax_authority_label=name if row.tax_authority_id else None,
            )
        )

    label, mapped = source_vocabulary_for(entry.source_type)
    mirror = (
        models.JournalEntry.objects.filter(tenant_id=tenant_id, reversal_of_id=entry.pk)
        .values_list("pk", flat=True)
        .first()
    )

    gaps: list[dict[str, Any]] = []
    if line_total == 0:
        gaps.append(dict(GAP_ENTRY_HAS_NO_LINES))

    return {
        "entry": JournalEntryRow(
            entry_id=str(entry.pk),
            currency=entry.currency,
            number=entry.number,
            entry_date=entry.entry_date,
            type=entry.type,
            status=entry.status,
            memo=entry.memo,
            source_type=entry.source_type,
            source_label=label,
            source_mapped=mapped,
            debit=debit,
            credit=credit,
            balanced=debit == credit,
            reversal_of_entry_id=(
                str(entry.reversal_of_id) if entry.reversal_of_id else None
            ),
            reversed_by_entry_id=str(mirror) if mirror is not None else None,
            auto_reverse_entry_id=(
                str(entry.auto_reverse_entry_id) if entry.auto_reverse_entry_id else None
            ),
            posted_at=entry.posted_at,
            source_id=str(entry.source_id) if entry.source_id else None,
        ),
        "lines": tuple(lines),
        "line_total": line_total,
        "unavailable": tuple(gaps),
    }


def _service_labels(ids: Any) -> dict[str, str]:
    """`{service_id: "Electric"}` — tenancy's own name for a stamped service.

    Read through `tenancy.Service` rather than through a seam because the
    service catalogue is PLATFORM data, not tenant data: `tenancy_seam` exists
    for the tenant's GL attributes and enabled set, and neither answers *"what
    is this service called"* for a service id already stamped on an immutable
    line. A service that cannot be read is nameless, never a dropped line.
    """
    keys = {str(value) for value in ids if value is not None}
    if not keys:
        return {}
    service_model = import_module("apps.tenancy.models").Service
    return {
        str(pk): str(name or code)
        for pk, code, name in service_model.objects.filter(pk__in=keys).values_list(
            "pk", "code", "name"
        )
    }

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e3b0c44 (sources this read-model derives from, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-007/009/010 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-014 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-001/002/007/010/011/013/016 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002/008/009/011/014 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1/LE-2/LE-3/LE-6 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ + the GT-51..60 allocation · 12-governance/02-decision-log.md 2026-08-11 OQ-143 "until bank record and reconcilaition confirm it it is not realised" + BR-BIL-069)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane — EP-LED-03 read half + US-LED-014's read half)
# amended:   2026-08-12 by story-coder (tenant-settings lane) — 🔒 HUMAN-OWNED FILE CHANGED,
#            stated here because the G7 markers above are unchanged and a reader must not have
#            to diff to learn that. ONE report gained a fact it could not previously state:
#            `remittance_by_authority` now reads the tenant's per-authority remitting basis
#            (`_remitting_basis_by_authority`) and reports it on each row, on the PO's ruling of
#            2026-08-12 (*"E Remit on what you BILLED, not what you collected - this is also
#            correct"*). NO FIGURE MOVED — billed, collected, remitted, outstanding and the
#            tie-out are byte-for-byte what they were, and `tests/test_us_led_014_remittance.py`
#            + `tests/test_us_led_ledger_api.py` were run unchanged to prove it (55 passed).
#            The `per_authority_remitting_basis_is_not_stored` problem code is KEPT — the string
#            two suites assert on — but it is now reported only while an authority is still
#            unset and it NAMES the ones that are. Its old detail said the setting had no home
#            because `tax_remittances` does not exist; that sentence is now history and is kept
#            AS history, in the past tense, on `_remitting_basis_gap` (hard-won law 1). This
#            module still writes nothing and still computes no money.
# amended:   2026-08-15 by the close-the-books lane — 🔒 HUMAN-OWNED FILE CHANGED. ONE column
#            and one problem code: `JournalEntryRow.number` carries BR-LED-021's `JE-` number
#            (PO 2026-08-12, OQ-176 CLOSED), the list's `search` now matches the NUMBER as
#            well as the memo — which is what EP-LED-04's *"JE #, memo"* always asked for —
#            and the blanket `journal_entries_have_no_number` gap is REPLACED by the narrower
#            `posted_entries_without_a_je_number`, reported only when a POSTED entry actually
#            lacks one (a DRAFT lacking one is the ruling, not a gap). NO MONEY FIGURE MOVED:
#            no summation, filter or basis label was touched.
# amended:   2026-08-15 by the money-correctness lane (DEF-081) — 🔒 HUMAN-OWNED FILE CHANGED.
#            **NO FIGURE IN THIS MODULE IS EVER AGAIN SUMMED ACROSS TWO CURRENCIES.** Every Σ
#            asks `_one_currency` over exactly the lines it is about to add and raises
#            `MixedCurrencyBook` (a CATALOG `BIZ_STATE` → 409, so no endpoint grew a try/except)
#            when they disagree; `journal_entry_list` deliberately does NOT refuse, because it
#            lists one entry per row and is the only surface on which the offending entries can
#            be FOUND. Every result dict also gained a `currency` key holding the code the
#            figures actually ARE, DERIVED from the entries summed — `apps/ledger/api.py` had
#            been labelling them with the TENANT's declared code, which its own docstring called
#            *a LABEL, not a derivation*. NO SIGNED FIGURE MOVED: LE-1 still foots 598.69 =
#            598.69, AR 152.32, billed 553.69, and the 81 existing ledger cases were re-run
#            unchanged on live PostgreSQL to prove it. RED-PROVED on a genuinely mixed book
#            (LE-1 plus one balanced 100.00 CAD bill posted through the real posting service):
#            with the guard removed the trial balance answered `total_debit
#            Decimal('698.690000') == total_credit Decimal('698.690000'), balanced True`, billed
#            `Decimal('653.690000')` and the AR control `Decimal('252.320000')` — balanced,
#            plausible, and not money. 11 of the 14 new cases went RED, the headline one with
#            `Failed: DID NOT RAISE MixedCurrencyBook`.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S36/S41/S59/S60 have no endpoints) E=deferred(no-frontend-half — 07-frontend/src/features/ledger and .../reports are a README each) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — FIVE mutations of this module, each written, RUN and quoted verbatim in the human-review row: (1) `still_owed` rewired to Σ accounts.balance — the cache and the KPI became one wrong number (`assert Decimal('4000.000000') != Decimal('4000')`) while the books said 152.32; (2) `cash_position` summing undeposited into realised (`assert Decimal('442.870000') == Decimal('150.00')`); (3) `by_premises_summary` returning one "Unassigned" row holding 553.69; (4) the collected remittance column filled with the BILLED figure (`assert Decimal('47.380000') is None`); (5) `account_ledger` dropping the transfer leg, which broke the AR tie-out (`assert Decimal('135.900000') == Decimal('0')`). A SIXTH, on apps/ledger/journal.py, mutated the "edit" to UPDATE a posted entry and was run on a LIVE POSTGRES cluster, where the database refused it
# exceptions: THIS MODULE IS NOW ON THE G7 GLOB LIST (added 2026-08-11 by the
#         orchestrating session). The line here read "NOT ON THE G7 GLOB LIST …
#         the glob is the only thing missing", which was true when this lane
#         wrote it and stopped being true the moment the glob went in — corrected
#         rather than left to rot, because a trailer describing a guard state the
#         repo has left is hard-won law 1 inside the guard system itself. The
#         lane was right not to add it alone (editing 10-scripts/gates/
#         human_owned.txt is a process event — B12 r2 "who watches the
#         watchers"); the marker and the repo-relative review-ledger row were
#         re-verified present before the glob was added · FOUR figures the
#         stories name are returned as None with a
#         named reason rather than computed: collection % (BR-REP-009 needs the
#         allocations period attribution), DSO (BR-REP-011 needs twelve months
#         that a young tenant does not have), the aging buckets (no due date on a
#         journal line; `account_opening_buckets` unbuilt) and the collected tax
#         basis (no line class on an allocation — OQ-129 — and no signed
#         partial-coverage apportionment) · ⚠ **THIS CLAUSE SAID US-LED-010
#         RETURNS available=False BECAUSE premises_id AND unit_id ARE NULL ON
#         EVERY JOURNAL LINE — CORRECTED 2026-09-03 (`DEF-2345`). US-LED-002
#         LANDED 2026-08-16** and `by_premises_summary` returns LE-6's three
#         rows (500 Main St 247.87 · Oak Grove 16.42 · Marina Bay 289.40,
#         footing to 553.69). What did NOT change is the clause under it, which
#         is live law: resolving the chain at READ time is the defect US-LED-010
#         TC-5 tests for, and money that lawfully carries no premises is still
#         returned as a quantified figure beside the table rather than dropped ·
#         the Reference
#         column shows a source UUID where A14 wants a document number; the
#         per-source-type number reads are asked for BY NAME · LE-1's *"1000
#         Cash 442.87"* row is RESTATED by the PO's OQ-143 ruling into 1000
#         150.00 + 1010 292.87 — same total, two rows, and 598.69 = 598.69 is
#         untouched; REPORTED here because this module is the first thing that
#         would render the difference
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
