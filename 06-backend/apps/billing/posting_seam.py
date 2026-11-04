# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-009 (the balanced posting handoff contract — *"per issued
#           bill, {invoice id, account, service_date, per-GL bucket sums, AR
#           total, currency} consumed ONLY by the ledger posting service"*) ·
#           US-BIL-005 (issue — stage 7 runs inside its transaction)
#           Screens: S56 · S31 step 6
# Rules:    BR-BIL-010 (every line's GL account is stamped AT ISSUE — this
#           handoff READS that stamp and resolves nothing a second time) ·
#           BR-BIL-011 (one bill = one balanced JE, DR AR total / CR per-GL
#           buckets; billing EMITS and writes no journal line) · BR-BIL-037
#           stage 7 (post-to-ledger — emits only) · BR-BIL-055 (a break never
#           blocks the run) · BR-LED-001 (every journal line carries its
#           dimension set) · BR-TEN-043 (event time is named by the caller,
#           never read from a clock) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money NUMERIC(18,6) + CHAR(3), never float) · rule 4
#           (financial immutability) · rule 5 (ONLY the ledger posting service
#           writes journal lines) · rule 6 (idempotency) · rule 7 (audit)
# Golden:   EP-BIL-01 US-BIL-005 §7 / US-BIL-009 §7 — CONFIRMED (WE-1, workbook
#           verbatim): DR 1200 AR 247.87 / CR 4100 88.60 · 4105 12.00 · 4110
#           39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–2203
#           20.97 · 4200 5.00 · B5 GT-16 ❄️ (the same service, the same key)
# Tests:    06-backend/tests/test_us_bil_009_posting_handoff.py
# Impacts:  apps/billing/issue.issue_invoice (calls this inside the issue
#           transaction — stage 7) · apps/ledger/posting.post (the owner of the
#           books, resolved BY NAME — billing never imports the ledger) ·
#           apps/ledger/selectors.gl_account_id_for_designation (the AR account)
# ───────────────────────────────────────────────────────
"""billing → ledger SEAM: the balanced posting handoff a bill emits at issue.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this runs INSIDE `issue.issue_invoice`'s
transaction and decides which GL buckets the money of an immutable financial
record lands in (CLAUDE.md 🔒 "ledger posting" + rule 4). AI-authored 2026-08-11
under the PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

⚠ **THAT WAS TRUE WHEN IT WAS WRITTEN AND IS NOT TRUE NOW — CORRECTED 2026-08-28
(hard-won law 1: a paragraph claiming the ABSENCE of a guarantee is as dangerous
as one claiming it).** This paragraph read *"THIS FILE MATCHES NO GLOB IN
`10-scripts/gates/human_owned.txt`, so G7 does not read the markers above"*, and
reported the line for the daily PO batch rather than self-granting it — which was
the correct posture, and the PO granted it: `10-scripts/gates/human_owned.txt`
carries `06-backend/apps/billing/posting_seam.py` today, so **G7 DOES read the
markers above** and this file is guarded. A reader checking whether anything here
is unwatched would have been sent to the wrong answer.

╔══════════════════════════════════════════════════════════════════════════╗
║  BILLING EMITS. THE LEDGER WRITES. NOTHING IN THIS FILE TOUCHES A        ║
║  JOURNAL TABLE, AND NOTHING IN IT COMPUTES A MONEY FIGURE.               ║
╚══════════════════════════════════════════════════════════════════════════╝

BR-BIL-011, verbatim: *"One bill = one customer document + N GL-coded invoice
lines + one balanced journal entry (DR AR total / CR per-GL buckets); ledger
posting service is the sole writer."* This module is billing's half of that
sentence and stops exactly where the sentence does. It reads the ISSUED
invoice and its already-stamped lines, groups the line amounts by the GL account
BR-BIL-010 froze onto each of them, and hands the result to
`apps.ledger.posting.post` — resolved BY NAME, at call time, so billing never
imports the ledger (B1) and the sole-writer fence in `ledger/0004` stays the
only door into `journal_entries` / `journal_lines`.

────────────────────────────────────────────────────────────────────────────
EVERY AMOUNT IS COPIED. NOTHING IS COMPUTED, ROUNDED, NETTED OR PLUGGED
────────────────────────────────────────────────────────────────────────────
The one discipline that matters here, because a second implementation of the
money is exactly what a handoff is tempted to become:

  * **The AR debit is `invoices.total`** — the stored header figure, read, not
    re-derived. US-LED-001's contract row says *"1200 AR invoice total"* and
    US-LED-001 §1 says *"posting asserts, never recomputes"*.
  * **Each credit bucket is Σ of the stamped line amounts for one GL account.**
    Addition of `Decimal`s that were finalized once, half-up to 2dp, by
    `apps/rating/pricing/stages/finalize` (BR-RAT-003, B4.4 ❄️). **There is no
    rounding in this file**, no `quantize`, no `float`, no re-rate: the money
    was settled at pricing and frozen at issue, and touching it here would put
    a second rounding event downstream of the frozen one.
  * **If DR ≠ Σ CR the handoff is REFUSED, naming the delta.** Never a
    balancing plug, never a rounding line, never "post the difference to
    somewhere". A bill whose own lines do not foot to its own total is a defect
    upstream of this point, and the honest thing a posting handoff can do about
    it is to say so and post nothing (BR-BIL-032's tie-out, US-BIL-007 TC-5's
    *"nothing partial issues"*).

Worked, so the shape is concrete rather than described — US-BIL-005 §7 /
US-BIL-009 §7, CONFIRMED, WE-1 verbatim: a bill of 15 stamped lines totalling
**247.87** emits ONE entry — DR 1200 AR **247.87** against nine credit buckets
(4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120
**15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200
**5.00**), which sum to 247.87 to the cent. Fifteen lines, nine buckets: a
bucket is NOT an invoice line, and the count differing is the point of the word
"bucket".

**The prior balance is NOT posted.** §7 again, verbatim: *"prior balance 45.00
is already in AR from its own bill; total due 292.87 is presentation, not
posting."* So this handoff carries current charges only, and a reader who
expects 292.87 in the books is reading a presentation figure.

────────────────────────────────────────────────────────────────────────────
THE GL ACCOUNT IS READ, NEVER RESOLVED AGAIN
────────────────────────────────────────────────────────────────────────────
`issue.gl_stamps_for_lines` already asked the ledger (and rating, for a tax
line's authority account) and wrote the answer to `invoice_lines.gl_account_id`,
where a database trigger froze it. This module reads that column and nothing
else. Resolving it a second time would be a second implementation of BR-BIL-010
that could disagree with the frozen stamp — and the stamp is the one that is on
the customer's bill and in every report, so the books would be the copy that was
wrong.

The ONE account this handoff does resolve is the debit side: the tenant's
**`accounts_receivable` designation**, through `apps.ledger.selectors.
gl_account_id_for_designation`. It is resolved rather than hardcoded for the
reason OQ-106's closure gives — a utility may renumber AR from 1200 to 1150 —
and it is REFUSED when the tenant has designated no AR account, because a bill
posted with its debit side missing is not a bill that can be posted at all.

────────────────────────────────────────────────────────────────────────────
IDEMPOTENCY: THE LEDGER'S KEY, COMPOSED BY THE LEDGER'S FUNCTION
────────────────────────────────────────────────────────────────────────────
Hard rule 6. `apps.ledger.posting.posting_key(source_type="invoice",
source_id=<invoice id>, event="issued")` — resolved by name like everything
else here, and NOT re-composed as an f-string on this side of the boundary. Two
callers composing "the same" key by hand is how a replay guard stops guarding.

A replay therefore returns the FIRST entry with `created=False`, writes nothing,
and is the correct outcome of a resumed release rather than an error anybody has
to catch. The partial unique index `uq_journal_entries_posting_key` is the other
half, for two workers racing the same bill.

────────────────────────────────────────────────────────────────────────────
WHERE THIS RUNS: INSIDE THE ISSUE TRANSACTION, AND WHY THAT IS NOT OPTIONAL
────────────────────────────────────────────────────────────────────────────
`issue.issue_invoice` calls this after the status has moved to `issued` and
before the transaction closes. **A bill and its journal entry are ONE fact.**

The alternative — post afterwards, outside — produces the two states nothing can
repair. An issued, immutable bill with no journal entry is revenue that exists
on a customer's document and nowhere in the books, and hard rule 4 leaves no
path to add it later. A journal entry whose bill rolled back is worse: money in
the trial balance that no document explains, which is precisely the drift
BR-LED-007 exists to detect and S36 renders in red.

That decision reverses this module's own predecessor argument, and the argument
is recorded rather than erased: `issue.py` used to say that emitting here would
put *"two money events with different failure modes in one transaction"*. It
would — and the answer is that they are not two events. One bill issuing IS the
money event; the journal entry is where that event is recorded. Splitting them
buys independence of failure at the price of a state with no repair.

AFTER the status moves rather than before, for the same reason the delivery
queue is written there: the entry's `source_id` is an invoice that exists, and
posting a draft's money would put a number in the books for a document that may
still break on a GL stamp two lines further down.

────────────────────────────────────────────────────────────────────────────
THE REFUSAL IS TRANSLATED (DEF-047's LESSON), SO ONE BAD BILL IS ONE BREAK
────────────────────────────────────────────────────────────────────────────
`apps.ledger.posting.PostingError` is the LEDGER's vocabulary. `issue_run`
catches `BillingRuleError` and nothing else, so an untranslated refusal would
kill a run of five hundred bills over one unpostable one — exactly what
BR-BIL-055 forbids and what DEF-047 already cost this repo once, at the rating
seam. `PostingRefused` is a `BillingRuleError`, so one unpostable bill is one
named break in the break list and the other 499 go out.

────────────────────────────────────────────────────────────────────────────
WHAT THIS HANDOFF CANNOT SAY YET — NAMED, NOT ASSUMED HANDLED
────────────────────────────────────────────────────────────────────────────
Carried on every result as `POSTING_UNAVAILABLE` / `problems`, so a caller never
has to infer an absence and a reviewer never has to take this docstring's word
for it (hard-won law 1):

  * **A BUCKET NAMES THE INVOICE, NOT ONE INVOICE LINE.** BR-LED-001 requires
    `source_type` + `source_id` on every journal line and this supplies
    `invoice` + the invoice id — because §7's bucket is a SUM over lines and
    cannot name one of them. `apps/ledger/models.JournalLine` comments that an
    issue entry's lines trace to individual `invoice_line` rows (US-LED-002
    TC-1); with WE-1's 15 lines and 9 buckets those two statements cannot both
    describe the same rows. The finance-signed §7 bucket shape wins, and LE-5's
    drill-back (*"what is the 506.31?"*) still answers: the journal line names
    the invoice, and `invoice_lines.gl_account_id` carries the same GL, so the
    lines behind a bucket are one join away. **REPORTED for the human review,
    not resolved here** — a per-line entry would be a different §7.
  * **PREMISES AND UNIT ARE NOT RESOLVED** (US-LED-002). BR-LED-001 wants them
    *"resolved account → unit → premises AT POSTING TIME"*; customers publishes
    no account → unit read and metering no unit → premises read, so the lines
    carry `None` — which `apps/ledger/posting.py` explicitly permits today and
    names as the same gap from its own side.
  * **A TAX BUCKET NAMES NO AUTHORITY.** `journal_lines.tax_authority_id` points
    at `rating.TaxJurisdiction`, and an invoice line names its `tax_id`, not its
    jurisdiction. Rating publishes no `tax_authority_id_for_tax`, and billing may
    not read rating's ORM (B1), so the dimension is left NULL and the gap is
    reported. The seam asks for the read BY NAME (`TAX_AUTHORITY_READ`): the day
    rating publishes it, this starts carrying it with no edit here.
  * **A NEGATIVE BUCKET IS REFUSED, NOT FLIPPED — OQ-152.** A discount is a
    negative charge rule (BR-RAT-043, OQ-055 closed), so a GL bucket summing
    below zero is a reachable state; §7 says buckets are CREDITS and says
    nothing about a credit that is really a debit. Posting a negative credit is
    impossible (B2 §2 is `CHECK (amount >= 0)`) and flipping it to a debit of
    the absolute value is a money decision nobody has signed. So it refuses,
    naming OQ-152, rather than choosing (prime directive).

    ⚠ **AMENDED 2026-08-28 — ONE CASE IS NOW SIGNED, AND IT IS THE CASE THAT
    MADE THIS REACHABLE.** The PO ruled that a discount posts to a GL code OF
    ITS OWN, in a category of its own: *"you will need differnt GL code for
    these - dont keep them in same, create differnt category as required and
    keep them in it"*. So a negative bucket **on the tenant's
    `discount_contra_revenue` account** is emitted as a DEBIT of its absolute
    value — standard contra-revenue, and OQ-152's own option (a) — and a
    negative bucket on **any other account** still refuses with exactly the
    sentence above. **Neither ruling supersedes the other.** OQ-152 says a
    negative CREDIT may not be invented; the 2026-08-28 ruling removes the only
    case that reachably produced one, because a discount no longer lands in the
    service's account at all.

────────────────────────────────────────────────────────────────────────────
A DISCOUNTED BILL, WORKED — THE ENTRY A FINANCE PERSON READS
────────────────────────────────────────────────────────────────────────────
The frozen GT-1 bill (electric usage **82.08** + base **18.50** = **100.58**)
with a **10.00** goodwill reduction. `invoices.total` is **90.58**:

    DR  accounts receivable                90.58
    DR  customer discounts (contra-revenue) 10.00
    CR  electric usage                     82.08
    CR  electric base                      18.50
                                          ------
    debits 100.58                 credits 100.58

The revenue accounts state what electricity actually sold for, and the 10.00
the utility gave away is its own readable figure. Netted into the service's own
account the same bill reports **72.08** of electric revenue that was never
earned at that price, and the discount disappears from every report — which is
the one thing BR-RAT-068's *"subsidy granted is reportable"* exists to prevent.

The BILL's own tie-out is unchanged and is the SIGNED sum:
82.08 + 18.50 − 10.00 = 90.58 = `invoices.total`. See `PostingBucket
.signed_amount`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.billing.exceptions import BillingRuleError

#: The ledger's posting service, named once so the contract is greppable from
#: BOTH sides of the boundary — the same discipline as `issue.GL_REVENUE_READ`
#: and `delivery_seam.QUEUE_WRITE`. `apps.ledger.posting`, not
#: `apps.ledger.services`: the posting service is deliberately its own module
#: (its docstring and `services.py`'s both say so), and naming the real home is
#: how the two sides stay findable from each other.
POSTING_MODULE = "ledger"
POSTING_KIND = "posting"
POSTING_WRITE = "post"  # (PostingRequest, actor=…) -> PostingResult
POSTING_KEY = "posting_key"  # (source_type, source_id, event) -> str
POSTING_REQUEST_TYPE = "PostingRequest"
POSTING_LINE_TYPE = "PostingLine"
POSTING_REFUSAL_TYPE = "PostingError"

#: The ledger's own vocabulary for the two sides. Repeated here rather than
#: imported for the reason `delivery_seam.SOURCE_INVOICE` gives: billing must not
#: import the ledger (B1), and these strings are the CONTRACT, not an
#: implementation detail. The owner validates both against `models.JOURNAL_SIDES`
#: and refuses an unreadable side loudly, so a typo here fails at the call.
SIDE_DEBIT = "debit"
SIDE_CREDIT = "credit"

#: The AR account this handoff debits — BY DESIGNATION, never by number. The
#: chart is tenant-customizable (US-LED-005) and a utility may renumber AR from
#: 1200 to 1150, which is the whole reason OQ-106 was raised and the reason the
#: ledger publishes this read.
AR_DESIGNATION = "accounts_receivable"
#: PO ruling 2026-08-12 (OQ-105/OQ-168): a goodwill or concession credit debits
#: **a separate write-off account**, never the original service revenue. The
#: chart carries exactly one write-off designation — 6900, seeded as "Bad debt",
#: finance-signed — so this uses it rather than minting an account, which would
#: need a finance re-sign. See `_write_off_account_id` for what that shares.
WRITE_OFF_DESIGNATION = "write_off"
#: Settled 2026-08-11 — a goodwill credit is raised on the ACCOUNT.
CREDIT_BALANCE_DESIGNATION = "customer_credit_balance"
#: PO ruling 2026-08-15 (OQ-142): the budget-billing variance gets **its own
#: account**. Verbatim: *"Create seperate account"*.
#:
#: ⚠ **THIS DESIGNATION HAS NO ACCOUNT BEHIND IT YET, AND THAT IS DELIBERATE.**
#: It is a TWELFTH designation against the eleven the PO confirmed on 2026-08-11
#: (OQ-110), and the account it needs is an addition to B5 line 74 — ❄️ FROZEN,
#: finance-signed 2026-08-08 — so it needs a finance re-sign via HUMAN-GUIDE §6
#: on the same route the 4160/4170 revenue codes and the concession account took.
#: B5 is never edited inline.
#:
#: **Why this one REFUSES while `write_off` falls back.** The concession ruling
#: had a lawful predecessor to land on — concessions and bad debt used to share
#: 6900, so resolving to the existing designation kept the books defensible while
#: the signature was pending. There is no such predecessor here. Receivables was
#: option (a) and was DECLINED (it is the ageing-bucket problem the ruling exists
#: to fix); `unbilled_ar` 1210 was option (b) and was also declined, and it is a
#: poor fit besides — a budget bill IS billed, it is merely not fully asked for.
#: So an unclaimed designation refuses BY NAME rather than posting money into a
#: bucket that is silently wrong and expensive to unpick later.
#:
#: Safe to ship refusing: the settle-up fires at TRUE-UP, six or twelve months
#: after enrolment, so no tenant reaches it in the first months after deploy.
#: When the signature lands this is ONE designation to claim, not a code change
#: at every call site.
BUDGET_VARIANCE_DESIGNATION = "budget_variance"
#: PO ruling 2026-08-28 (closing DEF-536): a discount posts to **a GL code of
#: its own, in a category of its own**. Verbatim: *"you will need differnt GL
#: code for these - dont keep them in same, create differnt category as required
#: and keep them in it"*.
#:
#: ⚠ **THIS IS THE ONE ACCOUNT ON WHICH A NEGATIVE BUCKET IS LAWFUL**, and it is
#: lawful because it stops being negative: it is emitted as a **DEBIT of the
#: absolute value**, which is what contra-revenue means. Every other account's
#: negative bucket still refuses by name (OQ-152, closed 2026-08-12 —
#: *"a bill whose GL bucket sums below zero REFUSES to issue"*). The two rulings
#: COMPOSE: OQ-152 says a negative CREDIT bucket may not be invented, and the
#: 2026-08-28 ruling removes the only case that reachably produced one. Neither
#: is superseded and the refusal below is not weakened.
#:
#: The chart seeds **4300 Customer discounts (contra-revenue)** carrying this
#: designation (`apps/ledger/chart.py`, `signed=False`, awaiting the
#: HUMAN-GUIDE §6 finance re-sign of the CODE — the ruling itself is signed).
#: Resolved by DESIGNATION and never by the number, like every account here.
DISCOUNT_DESIGNATION = "discount_contra_revenue"
DESIGNATION_MODULE = "ledger"
DESIGNATION_READ = "gl_account_id_for_designation"  # (designation) -> id | None

#: The rating read that would say WHICH AUTHORITY a tax line's money is owed to
#: — `journal_lines.tax_authority_id` points at `rating.TaxJurisdiction` and an
#: invoice line names its `taxes` row, not its jurisdiction.
#:
#: Contract, for the lane that publishes it:
#:
#:     apps.rating.selectors.tax_authority_id_for_tax(tax_id) -> str | None
#:
#: Asked by name and answered by nothing today, so a tax bucket carries no
#: authority and says so on the result. Not derived from the account code, not
#: parsed out of the description: that was option D of OQ-116 and the PO
#: declined it.
TAX_AUTHORITY_MODULE = "rating"
TAX_AUTHORITY_READ = "tax_authority_id_for_tax"

#: The three parts of the replay key (hard rule 6). `event` is the thing that
#: happened to the document, which is why it is not just the invoice id: a
#: future credit note or void of the same bill is a DIFFERENT event and must be
#: allowed to post — see `apps/ledger/posting.py`'s own worked explanation.
SOURCE_INVOICE = "invoice"
EVENT_ISSUED = "issued"

#: The ledger module that composes US-LED-001's two FINAL-BILL deposit rows.
#: Resolved BY NAME at call time like everything else here — billing never
#: imports the ledger (B1) — and named once so the contract is greppable from
#: both sides of the boundary.
#:
#: **Both sides of both entries are ledger DESIGNATIONS** (`deposit_liability`,
#: `deposit_interest_expense`, `accounts_receivable`), so the COMPOSITION lives
#: in `apps/ledger/deposit_legs.py` rather than here: billing contributes the
#: figures and the document, and contributes nothing at all to the accounts.
#: That is the opposite split from the issue entry above, whose credit buckets
#: can only be built from billing's own stamped lines.
DEPOSIT_LEGS_KIND = "deposit_legs"
DEPOSIT_INTEREST_WRITE = "post_deposit_interest_accrued"
DEPOSIT_APPLIED_WRITE = "post_deposit_applied"

#: `apps.ledger.reporting.ar_positions` — what each customer account owes, Σ'd
#: from the books (DEF-127). Read AFTER the bill's own entry has posted, so it
#: is the CLOSING position BR-BIL-013 settles against: the PO closed OQ-158 on
#: 2026-08-12 with *"everything outstanding"*, so it is the whole receivable and
#: never this bill alone.
AR_POSITIONS_KIND = "reporting"
AR_POSITIONS_READ = "ar_positions"

#: The bill type whose issue discharges a deposit. BR-BIL-013 settles the
#: deposit ONCE, on the final bill; applying it to an ordinary cycle bill would
#: credit the customer once a month for the length of their tenancy.
BILL_TYPE_FINAL = "final"

#: What the posting handoff does NOT carry, on every result — the same
#: discipline as `issue.ISSUE_UNAVAILABLE` and `delivery_seam.
#: DELIVERY_UNAVAILABLE`.
POSTING_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "bucket_names_the_invoice_not_the_invoice_line",
        "br_ref": "BR-LED-001 · US-BIL-005 §7",
        "detail": "every journal line carries `source_type='invoice'` + the invoice id, "
        "because §7's bucket is a SUM over lines (WE-1: 15 stamped lines → 9 buckets) and "
        "cannot name one of them. `apps/ledger/models.JournalLine` comments that an issue "
        "entry's lines trace to individual `invoice_line` rows (US-LED-002 TC-1); the two "
        "statements cannot both describe these rows, and the finance-signed bucket shape "
        "wins. The drill-back still answers — `invoice_lines.gl_account_id` carries the "
        "same GL, so the lines behind a bucket are one join away.",
    },
    {
        "code": "premises_and_unit_dimensions_not_resolved",
        "br_ref": "BR-LED-001 · US-LED-002",
        "detail": "BR-LED-001 wants premises and unit *resolved account → unit → premises "
        "at posting time*. Customers publishes no account → unit read and metering no "
        "unit → premises read, so both dimensions are NULL on every line of this handoff. "
        "The ledger names the same gap from its own side; US-LED-002 is the story.",
    },
    {
        "code": "prior_balance_and_total_due_are_not_posted",
        "br_ref": "BR-BIL-011 · US-BIL-005 §7",
        "detail": "this is not an omission, it is the ruling: §7 verbatim — *prior balance "
        "45.00 is already in AR from its own bill; total due 292.87 is presentation, not "
        "posting*. The handoff carries CURRENT CHARGES only (WE-1: 247.87), so a reader "
        "expecting the bill's TOTAL DUE in the books is reading a presentation figure.",
    },
)


class PostingRefused(BillingRuleError):
    """The books refused this bill, in BILLING's vocabulary (DEF-047's lesson).

    A subclass of `BillingRuleError` so `issue_run`'s per-bill catch sees it and
    records ONE break — the ledger's `PostingError` would sail straight through
    that catch and take the other 499 bills with it, which is the failure
    BR-BIL-055 forbids and DEF-047 already cost this repo once at the rating
    seam.

    Declared as a class rather than raised as a bare `BillingRuleError` so a
    caller that wants to tell "the books said no" from "this draft is not
    issuable" can, without matching on prose.
    """


@dataclass(frozen=True)
class PostingBucket:
    """One GL account's share of a bill — §7's *"Σ stamped lines per GL"*.

    `amount` is the SUM of `invoice_lines.amount` for the lines this bill
    stamped with `gl_account_id`. Nothing else: not re-rated, not re-rounded,
    not re-derived from quantity × price.

    `service_id` and `tax_authority_id` are BR-LED-001 dimensions and are
    carried ONLY when every line in the bucket agrees on them — two services
    mapped by their tenant to one revenue account produce a bucket that names no
    single service, and naming either would be a guess written into an immutable
    record. `line_count` travels so a reviewer can see that a bucket of 88.60 is
    three lines rather than one.
    """

    gl_account_id: str
    amount: Decimal
    service_id: Any = None
    tax_authority_id: Any = None
    line_count: int = 0
    #: WHICH SIDE this bucket posts on. `credit` for every bucket this handoff
    #: has ever built — §7 is *"DR AR total / CR per-GL buckets"* — and `debit`
    #: for exactly one case: the DISCOUNT account, whose lines sum below zero
    #: because a reduction is a negative line (BR-RAT-068). PO ruling
    #: 2026-08-28. On a debit bucket `amount` is the ABSOLUTE value, because
    #: the ledger cannot take a negative amount at all (B2 §2 is
    #: `CHECK (amount >= 0)`) — the sign is carried by the side, which is what
    #: a side is for. `signed_amount` below is the figure that ties out against
    #: `invoices.total`.
    side: str = SIDE_CREDIT

    @property
    def signed_amount(self) -> Decimal:
        """This bucket's contribution to the BILL's own total.

        A credit bucket contributes `+amount`; a debit bucket contributes
        `-amount`, because it is money the bill did NOT ask the customer for.
        The tie-out `Σ signed_amount == invoices.total` is therefore the same
        arithmetic it was before the discount ruling, on a bill without one —
        which is why every ❄️ B5 figure and every existing fixture is untouched.
        """
        return -self.amount if self.side == SIDE_DEBIT else self.amount


@dataclass(frozen=True)
class BillPosting:
    """What one bill left in the books — and what it could not say.

    `created=False` is the REPLAY (hard rule 6, US-LED-001 TC-6): the entry was
    already there, this call wrote nothing, and that is the correct outcome of a
    resumed release rather than an error. `entry_id` is the first entry either
    way, so a caller can link to the books without knowing which call won.

    `debits` / `credits` are echoed from the ledger's own result so the caller
    can tie out what it asked for against what landed — BR-LED-007's discipline
    applied at the moment of posting rather than a month later on S36.
    """

    invoice_id: str
    entry_id: str
    posting_key: str
    created: bool
    debits: Decimal
    credits: Decimal
    buckets: tuple[PostingBucket, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    unavailable: tuple[dict[str, Any], ...] = field(default=POSTING_UNAVAILABLE)
    #: The FINAL bill's two extra entries — US-LED-001's *"Deposit interest
    #: accrual"* and *"Deposit application at final bill"*. Empty on every other
    #: bill type, and empty on a final bill for an account that holds no
    #: deposit. Each names the two designations it moved, so a caller can tie
    #: out DR 2300 / CR 1200 without re-reading the journal.
    deposit_legs: tuple[Any, ...] = ()


def _resolve(module: str, attribute: str, kind: str) -> Any:
    """The owning module's attribute, or None while it has not published one.

    getattr at CALL time — the idiom `gather.py`, `issue.py`, `release.py`,
    `delivery_seam.py` and `apps/metering/seams.py` all use. No import statement
    binds billing to the ledger's internals, the boundary is greppable from both
    sides by name, and nothing here needs re-wiring when the owner moves.

    Unlike its siblings this one does NOT require a callable: the contract it
    resolves includes two dataclasses and an exception class as well as two
    functions, and `PostingRequest` is not callable-shaped in the way a selector
    is. Every caller below checks what it got.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    return getattr(target, attribute, None)


def _ledger_contract() -> dict[str, Any]:
    """Every part of the posting contract, resolved in one place, or REFUSE.

    Half a published interface is not an interface (`delivery_seam` says the
    same about its own owner): a deployment where `post` exists but
    `PostingRequest` does not is one where this seam would build something the
    owner cannot read. Named individually in the refusal so a reader of the
    break list knows which half is missing.
    """
    found = {
        POSTING_WRITE: _resolve(POSTING_MODULE, POSTING_WRITE, POSTING_KIND),
        POSTING_KEY: _resolve(POSTING_MODULE, POSTING_KEY, POSTING_KIND),
        POSTING_REQUEST_TYPE: _resolve(POSTING_MODULE, POSTING_REQUEST_TYPE, POSTING_KIND),
        POSTING_LINE_TYPE: _resolve(POSTING_MODULE, POSTING_LINE_TYPE, POSTING_KIND),
        POSTING_REFUSAL_TYPE: _resolve(POSTING_MODULE, POSTING_REFUSAL_TYPE, POSTING_KIND),
    }
    missing = [name for name, value in found.items() if value is None]
    if missing:
        raise BillingRuleError(
            f"apps.{POSTING_MODULE}.{POSTING_KIND} publishes no {' / '.join(sorted(missing))}, "
            "so this bill's balanced posting handoff cannot be emitted (BR-BIL-011). Billing "
            "may not write journal lines itself (CLAUDE.md rule 5) and an issued bill is "
            "immutable — a bill committed with no journal entry is revenue on a customer's "
            "document and in no ledger account, permanently, because hard rule 4 leaves no "
            "path to add the entry later.",
            br_ref="BR-BIL-011",
        )
    return found


def _ar_account_id() -> str:
    """The tenant's `accounts_receivable` account — BY DESIGNATION, or REFUSE.

    Never the number 1200. The chart is tenant-customizable (US-LED-005) and a
    utility may renumber AR; OQ-106 exists because the posting service could not
    find "the AR account" without writing a code into Python, and the PO's
    closure made a designation an ATTRIBUTE the ledger resolves.

    A tenant that has designated no AR account cannot issue, and that is the
    correct answer rather than a harsh one: the debit side of every bill in the
    product goes there, so the gap is one chart edit on S56 and it blocks
    exactly one thing until someone makes it.
    """
    read = _resolve(DESIGNATION_MODULE, DESIGNATION_READ, "selectors")
    account_id = read(AR_DESIGNATION) if callable(read) else None
    if not account_id:
        raise BillingRuleError(
            f"no live ledger account carries the {AR_DESIGNATION!r} designation, so this "
            "bill's posting handoff has no debit side (BR-BIL-011 — DR AR / CR the per-GL "
            "buckets). The account is resolved by DESIGNATION and never by number, because "
            "a tenant may renumber AR (PO ruling 2026-08-11, OQ-106); a human designates one "
            "on the GL mapping page. Nothing here picks a bucket for the receivable.",
            br_ref="BR-BIL-011",
        )
    return str(account_id)


def write_off_account_id() -> str:
    """The tenant's `write_off` account — the DEBIT side of a goodwill credit.

    **PO ruling 2026-08-12 (OQ-105 / OQ-168), verbatim: _"a separate write-off
    account"_.** Worked on GT-6's frozen shape: a **$25.00** goodwill credit
    against a **$247.30** invoice leaves the customer owing **$222.30** under any
    of the three readings that were on the table — what the ruling decides is
    where the utility's side of it lands. It does NOT reverse the original
    service revenue, so a month's revenue stays the revenue that was billed and
    the concessions are visible as their own figure.

    **RESOLVED BY DESIGNATION, NEVER BY THE NUMBER 6900** — the same rule as AR
    above, for the same reason: a tenant may renumber their chart (OQ-106).

    ⚠ **WHAT THIS SHARES, STATED RATHER THAN HIDDEN.** The finance-signed chart
    carries ONE write-off designation and it is seeded as **"Bad debt"**. A
    goodwill concession and an uncollectable debt are not the same business
    event — one is a decision to give, the other a failure to collect — and they
    will now sum into a single figure. Using the signed account is the right
    default (minting a second needs a finance re-sign, and inventing one inline
    is forbidden), but if the utility wants concessions reported apart from bad
    debt that is a chart change, and it is raised as **OQ-187** rather than left
    for somebody to discover in a year-end review.
    """
    read = _resolve(DESIGNATION_MODULE, DESIGNATION_READ, "selectors")
    account_id = read(WRITE_OFF_DESIGNATION) if callable(read) else None
    if not account_id:
        raise BillingRuleError(
            f"no live ledger account carries the {WRITE_OFF_DESIGNATION!r} designation, so a "
            "goodwill credit has no debit side. The PO ruled on 2026-08-12 that a concession "
            "debits a separate write-off account rather than reversing service revenue; the "
            "account is resolved by DESIGNATION and never by number, and a human designates one "
            "on the GL mapping page. Nothing here picks an account for it.",
            br_ref="BR-BIL-014",
        )
    return str(account_id)


def credit_balance_account_id() -> str:
    """The tenant's `customer_credit_balance` account — the CREDIT side.

    Settled since 2026-08-11: a goodwill credit is raised on the ACCOUNT rather
    than against the bill, and 2400 `customer_credit_balance` is one of the
    eleven ruled designations. Resolved by designation for the same reason as
    every other account here.
    """
    read = _resolve(DESIGNATION_MODULE, DESIGNATION_READ, "selectors")
    account_id = read(CREDIT_BALANCE_DESIGNATION) if callable(read) else None
    if not account_id:
        raise BillingRuleError(
            f"no live ledger account carries the {CREDIT_BALANCE_DESIGNATION!r} designation, so a "
            "goodwill credit has nowhere to land. The credit is raised on the ACCOUNT (PO ruling "
            "2026-08-11), which needs an account a human has designated on the GL mapping page.",
            br_ref="BR-BIL-014",
        )
    return str(account_id)


def budget_variance_account_id() -> str:
    """The tenant's `budget_variance` account — or REFUSE, naming the re-sign.

    **PO ruling 2026-08-15, OQ-142 CLOSED.** Verbatim: *"Create seperate
    account"*, choosing the third of three options: leave the variance in
    receivables, use the already-signed `unbilled_ar` 1210, or mint its own.

    **THE PROBLEM THE ACCOUNT SOLVES, with the ❄️ frozen WE-8 figures.** July
    recognises **292.87** of revenue and asks the customer for **242.00**,
    leaving **50.87** standing. That 50.87 is not revenue (counted), not tax
    (taken) and not an arrear — the customer paid exactly what we asked, and the
    late fee and dunning ladder are already stopped from reaching them. But it
    still landed in the **1–30 ageing bucket**, where a budget variance is
    indistinguishable from a delinquency on every ageing report the product
    prints. Across a year the balance runs **−50.87 → −40.27 → +2.98**, so it can
    end as money the utility OWES while sitting in a bucket that says the
    customer is behind. Its own account is the only one of the three options that
    makes that readable.

    **WHY IT REFUSES TODAY AND WHY THAT IS NOT A STUB.** The question is ANSWERED
    — this is not `NotImplementedError`, and nothing here is waiting on a
    decision. What it waits on is a SIGNATURE: the account is an addition to B5
    line 74, which is ❄️ frozen and finance-signed, so it takes the HUMAN-GUIDE §6
    re-sign route. Until a human designates one, posting the variance anywhere
    else would be silently wrong, and the two "anywhere else"s were both
    explicitly declined by the ruling. See `BUDGET_VARIANCE_DESIGNATION`.
    """
    read = _resolve(DESIGNATION_MODULE, DESIGNATION_READ, "selectors")
    account_id = read(BUDGET_VARIANCE_DESIGNATION) if callable(read) else None
    if not account_id:
        raise BillingRuleError(
            f"no live ledger account carries the {BUDGET_VARIANCE_DESIGNATION!r} designation, so a "
            "budget-billing settle-up has nowhere to land. The Product Owner ruled on 2026-08-15 "
            'that the variance gets its OWN account ("Create seperate account"), which is an '
            "addition to the finance-signed chart and needs a finance re-sign via HUMAN-GUIDE §6 "
            "before it can be designated. Receivables and unbilled AR were both offered and both "
            "declined, so this refuses rather than posting the money to either of them.",
            br_ref="BR-BIL-017",
        )
    return str(account_id)


def _discount_account_id() -> str | None:
    """The tenant's `discount_contra_revenue` account, or None. **Never raises.**

    **PO ruling 2026-08-28, closing DEF-536.** Verbatim: *"you will need
    differnt GL code for these - dont keep them in same, create differnt
    category as required and keep them in it"*.

    Resolved by DESIGNATION and never by the number 4300 — the same rule as AR,
    for the reason OQ-106's closure gives: a tenant may renumber their chart,
    and `US-LED-005` says they own it.

    **Called only when a bucket actually sums below zero**, so an ordinary bill
    issues with no extra read and a tenant who has configured no discount never
    meets this.

    ⚠ **IT ANSWERS None RATHER THAN REFUSING, AND THE REASON IS THE MESSAGE A
    CLERK READS.** The refusal for an unmapped discount designation belongs at
    `issue._gl_account_for`, which resolves the SAME designation to stamp the
    line a few lines earlier in the same transaction and names it in full. If
    this function refused instead, a bill whose ELECTRIC REVENUE bucket went
    negative on a tenant with no discount account would be refused with a
    sentence about discounts — a real gap reported as the wrong one, which is
    the shape DEF-127 already cost this repo once. Answering None sends every
    bucket this cannot place to the OQ-152 refusal below, which is the true
    statement about it.
    """
    read = _resolve(DESIGNATION_MODULE, DESIGNATION_READ, "selectors")
    account_id = read(DISCOUNT_DESIGNATION) if callable(read) else None
    return str(account_id) if account_id else None


def posting_buckets(invoice: Any, lines: list[Any]) -> tuple[PostingBucket, ...]:
    """§7's *"CR per-GL buckets = Σ stamped lines per GL"* — read, never derived.

    Groups the ALREADY-STAMPED lines by `gl_account_id` and sums their amounts.
    The GL account is BR-BIL-010's stamp, frozen onto the line moments earlier by
    `issue.gl_stamps_for_lines`; resolving it again here would be a second
    implementation of that rule sitting downstream of the first, and the two
    would disagree eventually — with the books holding the copy that was wrong.

    Bucket ORDER is the order the accounts first appear among the lines, which
    is the invoice's own line order. Stable, so a re-run of the same bill builds
    the same entry in the same order and a diff of two runs is readable.

    Refuses, and each refusal is a thing no handoff may paper over:

    * **a line with no stamp** — it would have to be dropped or bucketed under
      NULL, and either one silently changes the bill's total in the books;
    * **a negative bucket** — OQ-152, see the module docstring. Not flipped to a
      debit, because that is a money rule nobody has signed. ⚠ **EXCEPT ON THE
      TENANT'S `discount_contra_revenue` ACCOUNT**, where the PO signed exactly
      that on 2026-08-28: the bucket is emitted as a DEBIT of its absolute
      value. The account is resolved by designation and ONLY when a negative
      bucket actually appears, and the resolve answers None rather than
      refusing — see `_discount_account_id` for why the refusal belongs at
      `issue._gl_account_for` instead.
    """
    order: list[str] = []
    sums: dict[str, Decimal] = {}
    services: dict[str, set[Any]] = {}
    taxes: dict[str, set[Any]] = {}
    counts: dict[str, int] = {}
    # CR-197-BRC10 / DEF-BIL-10648 — which buckets hold ONLY discount lines.
    only_discounts: dict[str, bool] = {}
    authority = _resolve(TAX_AUTHORITY_MODULE, TAX_AUTHORITY_READ, "selectors")

    for index, line in enumerate(lines):
        gl_account_id = getattr(line, "gl_account_id", None)
        if not gl_account_id:
            raise BillingRuleError(
                f"line {index + 1} of {len(lines)} ({getattr(line, 'description', '')!r}) "
                "carries no GL account, so it cannot be placed in a posting bucket "
                "(BR-BIL-010 / BR-BIL-011). The stamp is written at issue and frozen with "
                "the money; a handoff that dropped this line would post a total smaller "
                "than the bill the customer received, and one that bucketed it under NULL "
                "would put revenue in no account at all.",
                br_ref="BR-BIL-010",
            )
        key = str(gl_account_id)
        if key not in sums:
            order.append(key)
            sums[key] = Decimal("0")
            services[key] = set()
            taxes[key] = set()
            counts[key] = 0
            only_discounts[key] = True
        only_discounts[key] = only_discounts[key] and getattr(line, "kind", None) == "discount"
        # Σ of figures FINALIZED once at pricing (BR-RAT-003, B4.4 ❄️). Addition
        # of Decimals and nothing else: no quantize, no float, no re-rate.
        sums[key] += line.amount
        services[key].add(getattr(line, "service_id", None))
        taxes[key].add(getattr(line, "tax_id", None))
        counts[key] += 1

    # Resolved ONCE, and only when a negative bucket actually appears — an
    # ordinary bill costs no extra read, and a tenant who has never configured
    # a discount never needs the designation.
    discount_account_id: str | None = None
    if any(sums[key] < 0 for key in order):
        discount_account_id = _discount_account_id()

    buckets = []
    for key in order:
        amount = sums[key]
        side = SIDE_CREDIT
        if amount < 0:
            # ⚠ CR-197-BRC10 / DEF-BIL-10648: a discount may now post to ITS OWN
            # account (the one the GL mapping list gives it) rather than only to
            # the designation's. The PO's 2026-08-28 rule is about the DISCOUNT —
            # *"a reduction posts to a GL code of its own, as a debit"* — not about
            # which account carries the designation, so a bucket made ONLY of
            # discount lines is that same lawful case. Any other negative bucket
            # is still OQ-152's refusal, unchanged.
            if (
                discount_account_id is not None and key == str(discount_account_id)
            ) or only_discounts.get(key):
                # PO ruling 2026-08-28 — the one lawful negative bucket, and it
                # is lawful because it stops being negative. A discount posts to
                # its OWN account (never netted into the service's revenue), and
                # on that account the sum of the reduction lines is a DEBIT of
                # the absolute value. Standard contra-revenue, and OQ-152's own
                # option (a). Worked on the frozen GT-1 bill with a 10.00
                # reduction: CR 82.08 usage + CR 18.50 base against DR 90.58 AR
                # + DR 10.00 discount — both sides 100.58.
                side = SIDE_DEBIT
                amount = -amount
            else:
                raise BillingRuleError(
                    f"GL account {key} sums to {amount} on this bill — a NEGATIVE posting "
                    "bucket. §7 makes the buckets CREDITS (DR AR / CR per-GL buckets) and says "
                    "nothing about a credit that is really a debit; the ledger cannot take it "
                    "either (B2 §2 is `CHECK (amount >= 0)`). Flipping the side and posting the "
                    "absolute value is a money rule NOBODY HAS SIGNED, so it is raised as "
                    "**OQ-152** rather than chosen here. ⚠ THE ONE CASE THAT IS SIGNED IS A "
                    "DISCOUNT: the PO ruled on 2026-08-28 that a reduction posts to a GL code "
                    "of its own, and a negative bucket on THAT account becomes a debit. This "
                    "bucket is not that account, so nothing here chooses a side for it.",
                    br_ref="BR-BIL-011",
                )
        service_ids = {value for value in services[key] if value is not None}
        tax_ids = {value for value in taxes[key] if value is not None}
        tax_authority_id = None
        if callable(authority) and len(tax_ids) == 1:
            tax_authority_id = authority(next(iter(tax_ids)))
        buckets.append(
            PostingBucket(
                gl_account_id=key,
                amount=amount,
                # ONE service or none. Two services a tenant mapped to one
                # revenue account produce a bucket that names neither, because
                # naming one would be a guess frozen into the books.
                service_id=next(iter(service_ids)) if len(service_ids) == 1 else None,
                tax_authority_id=tax_authority_id,
                line_count=counts[key],
                side=side,
            )
        )
    return tuple(buckets)


def _refuse_unless_balanced(invoice: Any, buckets: tuple[PostingBucket, ...]) -> Decimal:
    """DR AR = Σ CR buckets, asserted against the STORED total. Or refuse.

    Returns the AR debit — `invoices.total`, read off the row, because
    US-LED-001's contract row is *"1200 AR invoice total"* and its §1 is
    *"posting asserts, never recomputes"*. The comparison is between two figures
    that came from different places (the header the engine wrote, and the sum of
    the lines it wrote beside it), which is the only reason the check can catch
    anything at all.

    **The delta is NAMED and nothing is plugged.** A balancing line would make
    the entry balance while making the books wrong, and it would do it silently
    on every affected bill in a run of five hundred.
    """
    total = invoice.total
    # SIGNED, so a DEBIT bucket subtracts. On every bill without a discount
    # `signed_amount` IS `amount` and this line is the arithmetic it has always
    # been — which is why no ❄️ B5 figure and no existing fixture moves. On a
    # discounted bill the identity that has to hold is the bill's own:
    # CR 82.08 + CR 18.50 − DR 10.00 = 90.58 = `invoices.total`. The full
    # journal entry balances at 100.58 on both sides, which is the DEBIT side's
    # arithmetic (AR + the discount bucket) and is asserted by the ledger.
    credited = sum((bucket.signed_amount for bucket in buckets), Decimal("0"))
    if not buckets:
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} produced no posting "
            "buckets, so there is nothing to credit against its AR debit (BR-BIL-011). A "
            "journal entry with one side is not a journal entry.",
            br_ref="BR-BIL-011",
        )
    if credited != total:
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} does not foot: its "
            f"stored total is {total} and its stamped lines sum to {credited} across "
            f"{len(buckets)} GL bucket(s) — a difference of {total - credited}. The handoff "
            "is REFUSED and nothing is posted. Nothing here plugs the delta into a "
            "balancing line: the entry would balance and the books would be wrong, silently, "
            "on every affected bill of the run. DR AR = Σ CR buckets is BR-BIL-011's "
            "*balanced by construction*, and when the construction does not hold the honest "
            "output is this sentence (BR-BIL-032's tie-out).",
            br_ref="BR-BIL-011",
        )
    return total


def _closing_position(account_id: Any) -> Decimal:
    """What this account owes across ALL its bills, Σ'd from the books.

    Read AFTER the final bill's own entry has posted, so the figure INCLUDES it
    — which is the base BR-BIL-013 settles against. The PO closed OQ-158 on
    2026-08-12 with *"everything outstanding"*, and `final_bill.settle_final_bill`
    already builds its remainder the same way (`invoice.total + prior_balance`).
    Taking it from the ledger here rather than adding two numbers means the
    figure the deposit is applied against is the figure the BOOKS hold, so the
    entry cannot disagree with the trial balance it is about to move.

    **An unreadable position REFUSES.** `ar_positions` answers `available:
    False` when the tenant has designated no AR account, and its own docstring
    warns that reading the empty dict as zeros re-opens DEF-127. A zero here
    would make every deposit look larger than the position and send every
    closure down OQ-248's refusal — a real gap reported as the wrong one.
    """
    read = _resolve(POSTING_MODULE, AR_POSITIONS_READ, AR_POSITIONS_KIND)
    payload = read(account_ids=[account_id]) if callable(read) else None
    if not payload or not payload.get("available"):
        reasons = "; ".join(
            str(gap.get("code")) for gap in ((payload or {}).get("unavailable") or ())
        )
        raise PostingRefused(
            "this account's closing position could not be read from the books"
            + (f" ({reasons})" if reasons else "")
            + ", so its deposit cannot be applied (BR-BIL-013). The deposit settles against "
            "*everything outstanding* (PO 2026-08-12, OQ-158) and that figure is Σ over the "
            "AR account; an unreadable Σ is not zero, and treating it as zero would refuse "
            "every closure as an over-credit (DEF-127's shape, one module along).",
            br_ref="BR-BIL-013",
        )
    return payload["positions"].get(str(account_id), Decimal("0"))


def emit_final_bill_deposit_legs(
    invoice: Any,
    *,
    posted_at: datetime,
    actor: Any = None,
) -> tuple[Any, ...]:
    """US-LED-001's two FINAL-BILL deposit rows, emitted at issue. Or nothing.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE MONEY THAT WAS COMPUTED AND BOOKED BY NOTHING                   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `apps/billing/final_bill.py` has computed both of these since 2026-08-11 —
    `deposit_credit_for` returns the principal and BR-CUS-057's interest, and
    `settle` applies their sum before any settlement path is chosen — and
    **nothing posted either of them**. A utility that took a **$150.00** deposit
    watched the 2300 liability rise when payments booked the receipt and watched
    nothing lower it at closure. The trial balance still footed, because the
    entry was never made at all, on either side.

    ❄️ Worked, WE-7 / GT-23 and LE-1 §7, on the bill this fires for:

        DR  6950 deposit interest expense      3.50
        CR  2300 customer deposit liability    3.50
        DR  2300 customer deposit liability  153.50
        CR  1200 accounts receivable         153.50

    leaving the deposit liability at **0.00** (150.00 + 3.50 − 153.50) and
    **135.90** standing in AR against Case B's 289.40 of charges.

    **WHY AT ISSUE, INSIDE THE SAME TRANSACTION.** BR-BIL-013 applies the
    deposit and its interest *FIRST*, before any settlement path is chosen — so
    the discharge is caused by the final bill and not by the staff choice that
    follows it. Emitting it here makes a final bill and its deposit legs ONE
    fact: the alternative leaves an issued, immutable bill whose deposit is
    still outstanding in the books, and a later run would have to find it.

    **ORDER IS THE RULE, NOT A PREFERENCE.** The interest is accrued BEFORE the
    application, because the application discharges principal *plus* interest —
    a liability that has not yet been raised cannot be discharged, and posting
    them the other way round would take the 2300 balance negative between the
    two entries.

    **EVERY OTHER BILL TYPE EMITS NOTHING**, and an account with no deposit
    emits nothing. `deposit_credit_for` answers zero for an account with no
    deposit WITHOUT consulting the unbuilt interest engine, so an ordinary
    move-out is untouched by any of this.

    ⚠ **AN ACCOUNT THAT HOLDS A DEPOSIT CANNOT CLOSE TODAY, AND THAT REFUSAL IS
    NOT THIS FUNCTION'S** (hard-won law 2 — say what does not work).
    `deposit_credit_for` refuses whenever a deposit exists and
    `apps.customers.selectors.deposit_interest_accrued` is unpublished, which it
    is: BR-CUS-057's accrual engine is US-CUS-023 §7 and is unbuilt. That
    refusal predates this lane and is deliberately not softened here — applying
    the principal alone would keep WE-7's **$3.50** of the customer's money on a
    bill that foots perfectly, on an account nobody will look at again. So this
    function makes a final bill REFUSE TO ISSUE rather than issue with its
    deposit permanently unbooked, which is the safe direction of the same gap.
    """
    if getattr(invoice, "bill_type", None) != BILL_TYPE_FINAL:
        return ()

    from apps.billing import final_bill  # local — see `_resolve`'s note on B1

    account_id = getattr(invoice, "account_id", None)
    # ⚠ **`DEF-BIL-8313` — THE DAY THE INTEREST ACCRUES TO IS NAMED, AND IT IS
    # THE BILL'S OWN `period_end`, THE MOVE-OUT DAY.** This asked with no day
    # until 2026-09-30; the accrual engine answers None for a day nobody named
    # (gate G6 keeps a wall clock off a money path), `deposit_credit_for`
    # refused by name, and every final bill for an account holding a deposit
    # was refused at Send. `period_end` is the day the preview's deposit row
    # and `settle_final_bill` both read (BR-CUS-056: *"the OUTGOING account
    # pays the move day, so `period_end` IS `moved_out_on`"*), so the legs
    # posted here and the settlement the clerk saw are ONE accrual. A bill
    # carrying no `period_end` still passes None and still refuses.
    credit = final_bill.deposit_credit_for(account_id, getattr(invoice, "period_end", None))
    if not credit.exists:
        return ()
    if credit.currency and credit.currency != invoice.currency:
        raise PostingRefused(
            f"the deposit is held in {credit.currency!r} and this final bill is in "
            f"{invoice.currency!r}. Money never changes currency between the two (CLAUDE.md "
            "rule 2), and an entry built from both would put a figure with no name into the "
            "books.",
            br_ref="BR-BIL-013",
        )

    interest_write = _resolve(POSTING_MODULE, DEPOSIT_INTEREST_WRITE, DEPOSIT_LEGS_KIND)
    applied_write = _resolve(POSTING_MODULE, DEPOSIT_APPLIED_WRITE, DEPOSIT_LEGS_KIND)
    refusal_type = _resolve(POSTING_MODULE, POSTING_REFUSAL_TYPE, POSTING_KIND)
    if not callable(interest_write) or not callable(applied_write):
        raise PostingRefused(
            f"apps.{POSTING_MODULE}.{DEPOSIT_LEGS_KIND} publishes no "
            f"{DEPOSIT_INTEREST_WRITE} / {DEPOSIT_APPLIED_WRITE}, so this final bill's "
            "deposit legs cannot be emitted (US-LED-001's contract table, rows *Deposit "
            "interest accrual* and *Deposit application at final bill*). Billing may not "
            "write journal lines itself (CLAUDE.md rule 5), and an issued bill is immutable "
            "— a closure committed with its deposit unbooked leaves the customer's money "
            "in the books for ever with no path to discharge it (hard rule 4).",
            br_ref="BR-BIL-013",
        )

    common = {
        "account_id": account_id,
        "source_type": SOURCE_INVOICE,
        "source_id": invoice.pk,
        # The BOOK date is the bill's own `service_date`, for the same reason
        # the issue entry's is: a June closure issued on 3 July discharges its
        # deposit in JUNE, in the period the tenancy ended.
        "entry_date": invoice.service_date,
        "posted_at": posted_at,
        "currency": invoice.currency,
        "actor": actor,
    }
    legs: list[Any] = []
    try:
        accrued = interest_write(
            interest=credit.interest,
            memo=f"Deposit interest — bill {getattr(invoice, 'invoice_no', None) or invoice.pk}",
            **common,
        )
        if accrued is not None:
            legs.append(accrued)
        applied = applied_write(
            credit=credit.total,
            closing_position=_closing_position(account_id),
            memo=f"Deposit applied — bill {getattr(invoice, 'invoice_no', None) or invoice.pk}",
            **common,
        )
        if applied is not None:
            legs.append(applied)
    except refusal_type as refusal:  # the ledger's vocabulary → billing's
        raise PostingRefused(
            "the books refused this final bill's deposit, so it did not issue and nothing "
            f"was posted (BR-BIL-013): {refusal}",
            br_ref="BR-BIL-013",
        ) from refusal
    return tuple(legs)


#: 🔒 `DEF-BIL-10069` — the ledger's ONE implementation of BR-TEN-038's
#: closed-period forward (`apps.ledger.close.resolve_entry_date`), read by
#: name like every other ledger read in this file.
CLOSE_KIND = "close"
CLOSE_RESOLVE = "resolve_entry_date"


def forward_for(service_date: Any) -> tuple[Any, dict[str, Any] | None]:
    """`(the date the books will take, the forward note or None)` for a
    one-time bill's service date — BR-TEN-038, read through the ledger.

    Used twice, and that is the point: by `_book_date` when the bill issues and
    by the one-time bill's step 1 to say *"August is closed. Posts to
    October."* before the clerk drafts anything. One read, so the sentence on
    the screen and the date in the books cannot disagree. A ledger that
    publishes no reader answers `(service_date, None)` — the date the bill has
    always posted on."""
    resolve = _resolve(POSTING_MODULE, CLOSE_RESOLVE, CLOSE_KIND)
    if resolve is None or service_date is None:
        return service_date, None
    return resolve(service_date)


def _book_date(invoice: Any) -> tuple[Any, dict[str, Any] | None]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10069` — the date this bill's entry is
    BOOKED on.

    **The bill's `service_date`, as the docstring below states — except for a
    ONE-TIME bill (a run with no cycle) whose month the books have closed.**
    PO 2026-10-12, decision log *"ONE-TIME BILL ACROSS A MID-PERIOD RATE
    CHANGE"*: *"a closed month posts forward under BR-TEN-038 as corrections
    do, service period unchanged"* (*"Okay"*). Until that ruling the ledger's
    lock (`_refuse_if_period_closed`, DEF-3202) refused the issue outright, so a
    one-time bill for August could not be sent once August was closed. Worked:
    a bill for 1–31 Aug with August and September closed books on **1 Oct**,
    the first day of the earliest open period; the bill still says 1–31 Aug.

    ⚠ **A CYCLE RUN IS NOT FORWARDED, DELIBERATELY.** The ledger refuses rather
    than forwards because only the caller knows whether moving a date is right,
    and the ruling covered the one-time bill; a cycle run billing a closed
    month keeps refusing by name, as it did."""
    landing, note = forward_for(invoice.service_date)
    if note is None:
        # The month is open — every bill on every tenant that has closed nothing
        # stops here, on the ledger's own one-EXISTS fast path.
        return invoice.service_date, None
    # 🔒 `CR-180-BRC10` B8 — **A CORRECTION'S NEW BILL POSTS FORWARD TOO.** The
    # ruling this function quotes says *"a closed month posts forward under
    # BR-TEN-038 as corrections do"*, and BR-BIL-045 names it for a correction
    # in terms: *"a closed July posts to the earliest open period"*. But a
    # rebill's run copies the ORIGINAL's cycle, so the cycle test below kept it
    # on the closed date and the ledger refused it — so no bill whose month had
    # closed could be corrected at all (J-FIX-TWENTY S11). The credit note
    # reversing it forwards the same way (`corrections.post_credit_note_
    # reversal`), so both entries land in one month and the Check step names it.
    if getattr(invoice, "bill_type", None) == "rebill":
        return landing, note
    run = getattr(invoice, "bill_run", None)
    if run is None or getattr(run, "cycle_id", None) is not None:
        # A cycle run keeps the service date, and the ledger refuses it by name.
        return invoice.service_date, None
    return landing, note


def post_bill_issue(
    invoice: Any,
    *,
    lines: list[Any],
    posted_at: datetime,
    actor: Any = None,
) -> BillPosting:
    """Stage 7 (BR-BIL-037) — emit ONE balanced entry for ONE issued bill.

    Called from inside `issue.issue_invoice`'s transaction, after the status has
    moved, so a bill and its journal entry commit together or not at all.

    `lines` are the SAME line objects issue just stamped — passed in rather than
    re-queried so the handoff reads the stamps this issue wrote (and adds no
    query to a run of five hundred bills).

    `posted_at` is the wall-clock moment the entry entered the books and is a
    PARAMETER, never a clock read (BR-TEN-043, gate G6): a resumed batch, a
    replay and a re-run must stamp the same moment rather than three. Callers
    pass the bill's own `issued_at`.

    **The BOOK date is the bill's `service_date`**, and that is a reading of the
    handoff contract rather than a choice made here: US-BIL-009 §1 states the
    handoff as *"{invoice id, account, service_date, per-GL bucket sums, AR
    total, currency}"* — `service_date` is the only date in it. So a June bill
    issued on 3 July books in JUNE, with the revenue in the period that earned
    it. Worked: the WE-1-shaped fixture has `service_date` 30 Jun 2026 and
    `issued_at` 3 Jul 2026, and its entry is dated **2026-06-30**. The two dates
    differing is exactly the case the PO ruled on when closing OQ-107 —
    *"posting and actual dates can differ"* — and it is flagged in this file's
    human-review row because §7 does not restate it.

    Raises `PostingRefused` (a `BillingRuleError`) for everything a human can
    act on — an unbalanced bill, an unstamped line, no AR designation, a ledger
    that publishes nothing, a negative bucket. The caller records one break and
    carries on to the next bill (BR-BIL-055); it never rolls the run back, and
    it never issues the bill anyway.
    """
    contract = _ledger_contract()
    post = contract[POSTING_WRITE]
    compose_key = contract[POSTING_KEY]
    request_type = contract[POSTING_REQUEST_TYPE]
    line_type = contract[POSTING_LINE_TYPE]
    refusal_type = contract[POSTING_REFUSAL_TYPE]

    ar_account_id = _ar_account_id()
    buckets = posting_buckets(invoice, lines)
    ar_debit = _refuse_unless_balanced(invoice, buckets)
    book_date, forward_note = _book_date(invoice)

    # Hard rule 6, composed by the OWNER's function and never as an f-string on
    # this side: two modules composing "the same" key by hand is how a replay
    # guard stops guarding.
    try:
        key = compose_key(source_type=SOURCE_INVOICE, source_id=invoice.pk, event=EVENT_ISSUED)
    except refusal_type as refusal:  # the ledger's vocabulary → billing's
        raise PostingRefused(
            f"bill {getattr(invoice, 'invoice_no', None) or invoice.pk} could not be keyed "
            f"for posting, so its handoff was not emitted (CLAUDE.md rule 6): {refusal}",
            br_ref="BR-BIL-011",
        ) from refusal

    #: BR-LED-001's two mandatory dimensions on EVERY line, plus the account.
    #: The bucket names the INVOICE, not one invoice line — see the module
    #: docstring, and `POSTING_UNAVAILABLE`.
    common = {
        "source_type": SOURCE_INVOICE,
        "source_id": invoice.pk,
        "account_id": getattr(invoice, "account_id", None),
    }
    posting_lines = [
        line_type(ledger_account_id=ar_account_id, side=SIDE_DEBIT, amount=ar_debit, **common)
    ]
    posting_lines.extend(
        line_type(
            ledger_account_id=bucket.gl_account_id,
            # CREDIT for every bucket §7 describes; DEBIT for the discount
            # account alone (PO ruling 2026-08-28). `bucket.amount` is already
            # the absolute value on a debit bucket — the ledger's
            # `CHECK (amount >= 0)` takes no negative figure and the sign is the
            # side's job.
            side=bucket.side,
            amount=bucket.amount,
            service_id=bucket.service_id,
            tax_authority_id=bucket.tax_authority_id,
            **common,
        )
        for bucket in buckets
    )

    try:
        result = post(
            request_type(
                posting_key=key,
                # The BOOK date — US-BIL-009 §1's handoff carries `service_date`
                # and no other date. See this function's docstring — and
                # `_book_date` for the ONE case it moves (`DEF-BIL-10069`).
                entry_date=book_date,
                posted_at=posted_at,
                currency=invoice.currency,
                lines=tuple(posting_lines),
                source_type=SOURCE_INVOICE,
                source_id=invoice.pk,
                memo=f"Bill {getattr(invoice, 'invoice_no', None) or invoice.pk} issued",
                audit_context={
                    "invoice_no": getattr(invoice, "invoice_no", None),
                    "bill_run_id": (
                        str(invoice.bill_run_id) if getattr(invoice, "bill_run_id", None) else None
                    ),
                    "gl_buckets": len(buckets),
                    # BR-TEN-038 — the closed month and where the entry landed,
                    # into `audit_log` with the posting (hard rule 7). Absent
                    # (None) on every bill whose month is open.
                    "period_closed_forward": forward_note,
                },
            ),
            actor=actor,
        )
    except refusal_type as refusal:  # the ledger's vocabulary → billing's
        raise PostingRefused(
            f"the books refused bill {getattr(invoice, 'invoice_no', None) or invoice.pk}, so "
            f"it did not issue and nothing was posted (BR-BIL-011): {refusal}",
            br_ref="BR-BIL-011",
        ) from refusal

    problems: list[dict[str, Any]] = []
    # Reported when the BILL carries tax and NOT ONE bucket could name the
    # authority behind it — which is every taxed bill today, and stops being any
    # of them the moment rating publishes the read. The condition is written on
    # those two facts rather than on "some bucket has no authority", because a
    # revenue bucket legitimately has none and would make this fire forever.
    taxed = any(getattr(line, "tax_id", None) for line in lines)
    if taxed and not any(bucket.tax_authority_id for bucket in buckets):
        problems.append(
            {
                "code": "tax_bucket_names_no_authority",
                "br_ref": "BR-LED-001 · US-LED-002 TC-5",
                "detail": f"apps.{TAX_AUTHORITY_MODULE}.selectors.{TAX_AUTHORITY_READ} is not "
                "published, so a tax bucket carries no `tax_authority_id`. The line names its "
                "`taxes` row and `journal_lines.tax_authority_id` points at the JURISDICTION "
                "behind it; billing may not read rating's ORM to make that hop (B1). The "
                "remittance-by-authority report (LE-3) reads this dimension, so it is left "
                "NULL and reported rather than inferred from the account code.",
            }
        )
    # US-LED-001's two FINAL-BILL deposit rows, AFTER the bill's own entry —
    # the deposit is applied against the CLOSING position, which does not exist
    # until this bill is in the books. Same transaction, so a final bill and the
    # discharge of its deposit commit together or not at all.
    deposit_legs = emit_final_bill_deposit_legs(invoice, posted_at=posted_at, actor=actor)

    return BillPosting(
        invoice_id=str(invoice.pk),
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        debits=result.debits,
        credits=result.credits,
        buckets=buckets,
        problems=tuple(problems),
        deposit_legs=deposit_legs,
    )


# ── THE SAME THREE ENTRIES, SHOWN BEFORE THEY ARE WRITTEN ───────────────────
#
# `CR-108` wave 1. Everything below this line COMPUTES and writes NOTHING: no
# journal table is touched, no posting key is minted, and `post` is never
# called. It exists because the One-time bill's step 3 draws *Impact on your
# books* ABOVE the button that writes — *"showing the three entries before the
# button means the clerk is not the last person to find out what the bill did
# to the ledger"* — and a clerk shown an impact that the posting then refuses
# has been shown a lie.

#: The two events a FINAL bill posts besides its own issue, and the reason
#: there are three keys on one document rather than one: they are three
#: distinct EVENTS on one invoice, so a resumed run replays all three and
#: writes none of them twice. The key itself is composed by the LEDGER at issue
#: (`compose_key(source_type, source_id, event)`) and cannot exist here — a
#: preview has no invoice id to key on, which is exactly what makes it a
#: preview.
EVENT_DEPOSIT_INTEREST_ACCRUED = "deposit_interest_accrued"
EVENT_DEPOSIT_APPLIED = "deposit_applied"
#: OQ-248 (A, 2026-09-30) — the leftover deposit credited to customer credit.
#: A PREVIEW row only: the ledger writes it inside the `deposit_applied` entry.
EVENT_DEPOSIT_REFUNDED = "deposit_refunded"

#: Both sides of both deposit entries, as ledger DESIGNATIONS. Named here for
#: the reason `DEPOSIT_LEGS_KIND` gives: the composition is the ledger's, and
#: billing names the designations only so a clerk can be shown which two
#: accounts move before they move.
DEPOSIT_LIABILITY_DESIGNATION = "deposit_liability"
DEPOSIT_INTEREST_DESIGNATION = "deposit_interest_expense"

#: What the PREVIEW cannot say, on every result — `POSTING_UNAVAILABLE`'s own
#: discipline one step earlier.
PREVIEW_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "issue_entry_credit_side_is_not_split_until_issue",
        "br_ref": "BR-BIL-010 · US-BIL-009 §7",
        "detail": "the bill's issue entry credits one bucket per GL account, and each "
        "bucket is Σ of the lines STAMPED with that account at issue (BR-BIL-010). The "
        "stamp does not exist until the draft does, and resolving it here would be a "
        "second implementation of that rule sitting upstream of the first — "
        "`posting_buckets` refuses to re-resolve it downstream for the identical "
        "reason. So the credit side is shown as what it is, revenue by service plus tax "
        "payable, and the split appears on the issued bill.",
    },
)


@dataclass(frozen=True)
class PreviewedAccount:
    """One side of one previewed entry — the account a clerk READS, never its id.

    `code` and `name` come from `ledger.account_labels`, which is the read
    DEF-937 published after the Charges tab printed a uuid under a column
    headed ACCOUNTING CODE. B14 rule 31 is the standing rule: no database id is
    ever the visible value of a field, so `account_id` is carried for a caller
    that needs to link and is never the thing shown.
    """

    designation: str
    account_id: str | None
    code: str | None
    name: str | None


@dataclass(frozen=True)
class PreviewedEntry:
    """One entry this bill WOULD post. A shape, not a promise it will.

    `event` is the catalogue key the screen renders into words — the wording is
    the front end's (B14 rule 35: a catalogue is written in its own language,
    never translated from an English string an API sent it).

    `credit` is None on the issue entry alone, where the credit side is many
    buckets that do not exist yet — see `PREVIEW_UNAVAILABLE`.
    """

    event: str
    amount: Decimal
    debit: PreviewedAccount | None = None
    credit: PreviewedAccount | None = None
    #: True for the issue entry: the credit side is per-GL and is resolved when
    #: the lines are stamped. A screen renders one phrase rather than a blank.
    credit_is_per_gl: bool = False


@dataclass(frozen=True)
class PreviewedPosting:
    """What this bill would do to the books — or the named reason it refuses.

    THREE OUTCOMES AND NOT TWO, which is the whole value of the panel:

      * **posts** — `posts=True`, the entries are listed;
      * **nothing to post** — `posts=False` with no refusal: a bill of zero
        either way moves no account, and an entry of 0.00 / 0.00 on every
        closure is noise in the one ledger a bookkeeper reads line by line;
      * **refuses** — `refused=True` with a named `detail`. ⚠ The deposit
        over-credit case is NO LONGER one of these: OQ-248 closed 2026-09-30
        (option A) and a deposit worth more than the closing position now
        posts the excess to customer credit (`EVENT_DEPOSIT_REFUNDED`).
    """

    posts: bool
    currency: str
    entries: tuple[PreviewedEntry, ...] = ()
    refused: bool = False
    reason: str | None = None
    detail: str | None = None
    #: The closing position the deposit is applied against, and the deposit
    #: itself — carried so a refusal a screen renders can show the arithmetic
    #: rather than assert it.
    closing_position: Decimal | None = None
    deposit_total: Decimal | None = None
    unavailable: tuple[dict[str, Any], ...] = PREVIEW_UNAVAILABLE


def _previewed_account(
    designation: str, labels: dict[str, Any], ids: dict[str, Any]
) -> PreviewedAccount:
    """One designation resolved to what a clerk reads, or to a stated blank.

    An unmapped designation comes back with `account_id=None` rather than
    raising: the panel's job is to show the gap, and a tenant who has not
    designated an account has something to fix on their GL-mapping screen. The
    POSTING still refuses at issue — `_ar_account_id` says so by name — which
    is the layer where refusing is correct.
    """
    account_id = ids.get(designation)
    label = labels.get(str(account_id)) if account_id else None
    return PreviewedAccount(
        designation=designation,
        account_id=str(account_id) if account_id else None,
        code=(label or {}).get("code"),
        name=(label or {}).get("name"),
    )


def preview_bill_entries(
    *,
    bill_type: str,
    charges: Decimal,
    currency: str,
    deposit: Any = None,
    closing_position: Decimal | None = None,
) -> PreviewedPosting:
    """The entries this bill would post, computed and **written nowhere**.

    ⚠ **IT IS A READ OF DESIGNATIONS AND A COMPARISON OF TWO NUMBERS, AND IT IS
    DELIBERATELY NOTHING ELSE.** Only the ledger posting service writes journal
    lines (CLAUDE.md hard rule 5) and nothing here approaches one: no
    `posting_key` is composed, no `post` is called, no `ledger` write is
    resolved at all. The two reads it makes — `designation_map` and
    `account_labels` — are the two the GL-mapping settings screen already makes.

    **THE ONE COMPARISON IS THE LEDGER'S OWN, NOT A COPY OF ITS JUDGMENT.**
    `post_deposit_applied` refuses when `credit > closing_position`; this asks
    the identical question of the identical two figures, and the figures are the
    caller's rather than this function's — `charges` comes from
    `runs.price_account` (named for the row the blueprint draws, and named
    `charges` rather than `total` because `one_time`'s BR-BIL-020 guard refuses
    a parameter a caller could read as *the figure to bill*) and
    `closing_position` from
    `final_bill.settle_closing_position`, which is the composition PO ruling
    OQ-158 requires. Nothing here adds two numbers together.

    ⚠ **WHAT IT CANNOT PROMISE, AND THE PANEL MUST NOT IMPLY OTHERWISE:** a
    preview that says *posts* is saying these three events are the shape of the
    handoff, not that issue will succeed. An unstamped line, an unmapped service
    revenue account or a negative bucket each refuse at issue (`posting_buckets`)
    and none of them is visible before the lines are stamped. That absence is on
    `PREVIEW_UNAVAILABLE` rather than in prose only.

    ❄️ Worked, WE-7 Case B and LE-1 §7, which is the bill p115 draws:
    charges **289.40**, a deposit of **150.00** principal plus **3.50** interest.
    Three entries — DR 6950 / CR 2300 **3.50**, DR 2300 / CR 1200 **153.50**,
    DR 1200 / CR revenue+tax **289.40** — leaving the deposit liability at 0.00
    and **135.90** standing in AR. Case A (OQ-248, closed 2026-09-30, option A):
    **142.30** of charges against the same **153.50** credit applies **142.30**
    to AR and shows **11.20** as a `deposit_refunded` entry to customer credit.
    """
    deposit_total = Decimal(str(getattr(deposit, "total", 0) or 0))
    deposit_interest = Decimal(str(getattr(deposit, "interest", 0) or 0))
    has_deposit = bool(getattr(deposit, "exists", False)) and deposit_total != 0

    # ⚠ **OQ-248 CLOSED 2026-09-30 (PO, option A: *"A for deposit refund"*).**
    # This answered `refused` when the deposit exceeded the closing position,
    # and J70 E3 ($150.00 against $103.67) was refused at Send. The ledger now
    # settles what is owed and credits the rest to customer credit, so the
    # preview shows the same split `post_deposit_applied` writes — the same
    # comparison of the same two figures, never a second judgment.
    owed = deposit_total
    refunded = Decimal("0")
    if bill_type == BILL_TYPE_FINAL and has_deposit and closing_position is not None:
        owed = max(min(deposit_total, closing_position), Decimal("0"))
        refunded = deposit_total - owed

    if charges == 0 and not has_deposit:
        # Not an error and not an empty list standing in for one: a bill that
        # moves no money moves no account either.
        return PreviewedPosting(
            posts=False,
            currency=currency,
            reason="nothing_to_post",
            closing_position=closing_position,
            deposit_total=deposit_total if has_deposit else None,
        )

    ids_read = _resolve(DESIGNATION_MODULE, "designation_map", "selectors")
    labels_read = _resolve(DESIGNATION_MODULE, "account_labels", "selectors")
    ids = ids_read() if callable(ids_read) else {}
    wanted = [
        ids.get(name)
        for name in (
            AR_DESIGNATION,
            DEPOSIT_LIABILITY_DESIGNATION,
            DEPOSIT_INTEREST_DESIGNATION,
            CREDIT_BALANCE_DESIGNATION,
        )
    ]
    labels = labels_read(wanted) if callable(labels_read) else {}

    receivable = _previewed_account(AR_DESIGNATION, labels, ids)
    entries: list[PreviewedEntry] = []

    if bill_type == BILL_TYPE_FINAL and has_deposit:
        liability = _previewed_account(DEPOSIT_LIABILITY_DESIGNATION, labels, ids)
        # ORDER IS THE RULE, NOT A PREFERENCE — `emit_final_bill_deposit_legs`
        # states it: the interest is accrued BEFORE the application, because the
        # application discharges principal PLUS interest, and a liability that
        # has not been raised cannot be discharged.
        if deposit_interest != 0:
            entries.append(
                PreviewedEntry(
                    event=EVENT_DEPOSIT_INTEREST_ACCRUED,
                    amount=deposit_interest,
                    debit=_previewed_account(DEPOSIT_INTEREST_DESIGNATION, labels, ids),
                    credit=liability,
                )
            )
        if owed:
            entries.append(
                PreviewedEntry(
                    event=EVENT_DEPOSIT_APPLIED,
                    amount=owed,
                    debit=liability,
                    credit=receivable,
                )
            )
        if refunded:
            # OQ-248 (A): the leftover, owed back to the customer. Posted in the
            # same ledger entry as the application; shown as its own row so a
            # clerk sees where the refund sits.
            entries.append(
                PreviewedEntry(
                    event=EVENT_DEPOSIT_REFUNDED,
                    amount=refunded,
                    debit=liability,
                    credit=_previewed_account(CREDIT_BALANCE_DESIGNATION, labels, ids),
                )
            )

    if charges != 0:
        entries.append(
            PreviewedEntry(
                event=EVENT_ISSUED,
                amount=charges,
                debit=receivable,
                credit=None,
                credit_is_per_gl=True,
            )
        )

    return PreviewedPosting(
        posts=bool(entries),
        currency=currency,
        entries=tuple(entries),
        closing_position=closing_position,
        deposit_total=deposit_total if has_deposit else None,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-009@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-02-invoice-gl.md US-BIL-009 §1/§7 + EP-BIL-01-bill-run.md
#         US-BIL-005 §7 · 07-billing/02-business-rules.md BR-BIL-010/011/037 ·
#         07-billing/03-field-map.md; plus the ledger's half —
#         09-ledger/06-epics/EP-LED-01 US-LED-001's contract table row *"Invoice
#         issued | 1200 AR invoice total | per-GL buckets from stamped lines"*)
# generated: 2026-08-11 by Eng-Lead (stage-7 posting-handoff lane — the wire
#         between apps/billing/issue.py and apps/ledger/posting.py, which were
#         both complete and connected by nothing)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a seam module; S56's journal reads are EP-LED-03/04) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_009_posting_handoff.py — the four
#         guards named in the task were each proved RED before any green was
#         trusted (the handoff not emitted, an unbalanced handoff accepted, a
#         double-issue posting twice, a posting failure not rolling back the
#         issue); every measured failure is quoted verbatim in
#         12-governance/09-human-review-ledger.md
# exceptions: (1) BILLING EMITS, THE LEDGER WRITES. No journal table is touched
#         here and no money figure is computed: the AR debit is `invoices.total`
#         read off the row and each bucket is Σ of already-finalized line
#         amounts. There is no rounding, no quantize and no float in this file.
#         (2) A BUCKET NAMES THE INVOICE, NOT ONE INVOICE LINE — §7's bucket is a
#         SUM (WE-1: 15 lines → 9 buckets), so BR-LED-001's per-line
#         `source_type`/`source_id` is satisfied with `invoice` + the invoice id.
#         `apps/ledger/models.JournalLine`'s comment says an issue entry's lines
#         trace to individual `invoice_line` rows; both cannot describe these
#         rows and the finance-signed bucket shape wins. REPORTED on every result
#         and in the review-ledger row, not resolved by this lane.
#         (3) THE BOOK DATE IS `invoices.service_date` — US-BIL-009 §1 states the
#         handoff as {invoice id, account, service_date, per-GL bucket sums, AR
#         total, currency} and service_date is the only date in it. A June bill
#         issued 3 July books in June. Flagged for the human review because §7
#         does not restate it.
#         (4) PREMISES/UNIT ARE NOT RESOLVED (US-LED-002 — no published
#         account→unit or unit→premises read) and A TAX BUCKET NAMES NO AUTHORITY
#         (rating publishes no `tax_authority_id_for_tax`; the seam asks for it BY
#         NAME so it starts carrying it with no edit here). Both ride the result.
#         (5) A NEGATIVE BUCKET REFUSES, NAMING **OQ-152** — a discount is a
#         negative charge rule (BR-RAT-043), §7 makes buckets credits, and
#         flipping the side is a money rule nobody signed. Refused rather than
#         stubbed with `NotImplementedError`, for the reason issue.py gives about
#         its own gaps: a stub crashes the batch where a named BillingRuleError
#         lets the run record one break and carry on (BR-BIL-055).
#         ⚠ AMENDED 2026-08-28 (DEF-536, PO ruling "you will need differnt GL
#         code for these"): a negative bucket ON THE TENANT'S
#         `discount_contra_revenue` ACCOUNT is now emitted as a DEBIT of the
#         absolute value — OQ-152's own option (a), now signed. Every OTHER
#         account's negative bucket still refuses with the same sentence, and
#         OQ-152 is not superseded: it is the case that made the state reachable
#         that has moved, not the rule.
#         (6) ⚠ STALE AS OF 2026-08-28 AND CORRECTED IN THE DOCSTRING. This read
#         "THIS FILE MATCHES NO GLOB IN 10-scripts/gates/human_owned.txt, so G7
#         does not read its HUMAN-OWNED marker"; the line was reported for the PO
#         batch, the PO granted it, and the glob is there now. G7 reads this file.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
