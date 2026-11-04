# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — every money event
#           becomes ONE balanced entry through this service, TC-1..TC-7) ·
#           US-LED-002 (dimension stamping — `_stamped` resolves BR-LED-001's
#           account → unit → premises chain AT POSTING TIME, TC-1/TC-4/TC-5) ·
#           US-LED-003 (reversal pairs: a correction is a NEW linked mirror,
#           never an edit — TC-1/TC-3/TC-5) · US-LED-013 (posted-JE "edit" =
#           reverse + repost — TC-3's REASON on the audit trail is why
#           `reverse_entry` grew `audit_context` on 2026-08-11; the flow itself
#           is apps/ledger/journal.py)
#           Screens: S56 · S36
# Rules:    CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3), never float) · rule 4 (financial immutability) · rule 5
#           (balanced pairs; THIS is the only writer of journal lines) · rule 6
#           (idempotency) · rule 7 (every money action writes audit_log) ·
#           BR-LED-001 (every line carries its dimension set) · BR-LED-003
#           (posted immutable; balanced required AT POST; "edit" = reverse +
#           repost) · BR-LED-015 (every finance action audits) · BR-TEN-043
#           (event time is named by the caller, never read from a clock) ·
#           B2 r13 #8 (posting-service mechanics = Eng-Lead 🔒)
# Golden:   GT-16 — B5 ❄️ FROZEN 2026-08-08 (the opening JE: DR AR 267.30 /
#           CR opening-balance clearing 267.30, dated 2026-08-31, idempotent)
# Tests:    06-backend/tests/test_us_led_001_posting.py ·
#           06-backend/tests/golden/test_gt16_opening_journal_entry.py
# Impacts:  apps/ledger/models (the three tables this writes) ·
#           apps/ledger/migrations/0004 (the DB fence this service is the one
#           lawful way through) · apps/billing/posting_seam (BR-BIL-011's
#           stage 7 — the FIRST caller in the product, wired 2026-08-11; it
#           reaches `post` and `posting_key` BY NAME) · apps/billing/issue
#           (emits that handoff inside its own transaction) · apps/payments
#           (R2 per B12 addendum r9 — every payment event posts through here)
# ───────────────────────────────────────────────────────
"""Ledger posting service. HUMAN-OWNED (CLAUDE.md rule #5).

THE ONLY writer of journal lines in the entire system. Balanced pairs enforced
by the deferred constraint trigger (B2 §3). Billing/payments call post();
nothing else inserts into journal_entries/journal_lines.

HUMAN-REVIEW-PENDING — this file stopped being a nine-line `NotImplementedError`
on 2026-08-11, under the PO ruling of 2026-08-09 (*"AI will do it; we will
review it later as human"*). It is the most sensitive file in the repository:
every money number the product will ever report is summed from the rows written
here. Row in 12-governance/09-human-review-ledger.md; it may never reach
lifecycle RATIFIED without a recorded human sign-off.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SERVICE DECIDES — AND THE MUCH LONGER LIST OF WHAT IT DOES NOT
════════════════════════════════════════════════════════════════════════════
Read this first, because the temptation in a posting service is to be clever
and every clever thing it could do is somebody else's ruling.

**IT DECIDES NOTHING ABOUT MONEY.** Not which account a line lands in, not
which side it takes, not the amount, not the date. It does not round.
US-LED-001 §1 states the
contract in signed text: *"amounts are the upstream document's finalized 2dp
figures — posting asserts, never recomputes"*, and the DR/CR contract table
above it names the accounts and sides for all seventeen source events. So the
CALLER hands over a fully-specified request and this service's whole job is to
refuse it or write it exactly as given. There is no arithmetic in this file —
no rounding, no netting, no derivation, no default account. A posting service
that computed anything would be a second implementation of B4's frozen money
math, sitting downstream of the first and disagreeing with it eventually.

⚠ **CORRECTED 2026-08-15 (the close-the-books lane), and the trail is kept
because the old sentence was a comment claiming a guarantee that had become a
falsehood (hard-won law 1).** This paragraph read *"and it does not refuse an
amount carrying more than 2 decimal places — whether it SHOULD is a rule nobody
has signed and is raised as **OQ-126**, not chosen here"*. **OQ-126 IS CLOSED.**
The Product Owner ruled on 2026-08-12, verbatim: *"Refuse and make the caller
round"* → **BR-LED-025**. So the eighth thing this service decides is now in the
list below, and `_carries_more_than_two_decimals` is where it lives. Nothing
about the storage moved: the column is still `NUMERIC(18,6)` (CLAUDE.md rule 2)
and the refusal is about the POSTING.

What it DOES decide is the eight things a database cannot decide for itself:

  1. that debits equal credits BEFORE the write, so the caller gets a readable
     refusal instead of an opaque commit-time trigger failure;
  2. that every account named belongs to THIS tenant and is live;
  3. that a replayed source event writes nothing (hard rule 6);
  4. that the three writes happen in the order 0002's triggers demand
     (draft → lines → post), inside ONE transaction;
  5. that `audit_log` is written in that same transaction (hard rule 7);
  6. that a float never reaches a money column (hard rule 2);
  7. that a correction is a NEW mirror entry and never an edit (hard rule 4);
  8. that an amount carrying more than two decimal places is REFUSED, naming
     the amount and the line, rather than rounded here (BR-LED-025 — a second
     rounding site is how two figures start disagreeing).

**THE DATES ARE INPUTS. BOTH OF THEM.** PO ruling 2026-08-11 closing OQ-107,
verbatim: *"posting and actual dates can differ; ask actual date to user."*
`entry_date` is the BOOK date the trial balance groups by and a human supplies
it; `posted_at` is the wall-clock moment the entry entered the books and the
CALLER names that too (BR-TEN-043's event-time law). **Nothing in this file
reads a clock**, which is also what gate G6 greps every money path for. A
resumed batch, a replay and a re-run therefore stamp the same moment rather
than three, and a bill run that starts at 23:59 does not scatter its entries
across two book dates.

════════════════════════════════════════════════════════════════════════════
THE THREE-STEP CONTRACT, AND WHY IT IS NOT NEGOTIABLE
════════════════════════════════════════════════════════════════════════════
`ledger/0002`'s docstring imposes it on this file by name, and it is repeated
here because the next agent has only the repo:

    1. INSERT the journal_entries row as `draft`
    2. INSERT its journal_lines
    3. UPDATE the entry to `posted`   ← balance is asserted here, at COMMIT

That is not a workaround for a trigger. It is BR-LED-003's ratified lifecycle
(*"drafts freely editable/deletable before post; balanced required at post"*)
made structural: lines cannot be inserted into an entry that is ALREADY posted,
because appending a balanced pair to a posted entry would slip past the balance
check while changing money in a frozen record. Inserting the entry directly as
`posted` is not forbidden — it simply fails at COMMIT with "posted with no
lines", loudly, which is worse for the caller and no safer.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCY: THE RULE IS SIGNED, THE KEY IS DELEGATED
════════════════════════════════════════════════════════════════════════════
US-LED-001 TC-6: *"the same issue handoff replayed twice → second replay no-ops
on the per-source posting guard — one entry, ever."* GT-16 (❄️ finance-signed):
*"re-posting the same batch is idempotent (no second JE set)."* Two signed
statements of the rule.

**B2 defines no key for it**, and that is reported rather than papered over:
§2's `journal_entries` DDL has no unique constraint, and DB-12 — the
consolidated idempotency register — names bill runs, payment webhooks, import
files and export batches and **not the journal**. What IS signed is the
delegation: B2 r13 #8, *"Exact DDL + posting-service mechanics = Eng-Lead 🔒"*,
and EP-LED-01 §5's field-map row *"Posting guard | per-source idempotency
(mechanics Eng-Lead 🔒, r13 #8) | replay no-ops"*. So the mechanics below are
authored under that delegation, in the same shape and with the same discipline
as `core/idempotency.bill_run_key`:

    posting_key = "<source_type>|<source_id>|<event>"

Worked, so the figure is concrete rather than a description. The issue of
invoice `018f6f6a-0000-7000-8000-0000000000aa` produces

    invoice|018f6f6a-0000-7000-8000-0000000000aa|issued

and a second call carrying that string returns the FIRST entry with
`created=False` — no second entry, no second audit row, no doubled books. The
NSF reversal of a payment is `payment|<id>|nsf_reversed`, which is a different
string from that payment's own `payment|<id>|cleared`, so both lawfully exist:
**a document is not the unit of identity, a document plus the event that
happened to it is.** Three parts for that reason, and `|` because it cannot
occur in a uuid or in the snake_case event names this repo uses — the key stays
splittable by eye in the psql session where somebody is debugging a refused
replay.

GT-16's identity is *"idempotent per (batch, account)"*, which is two ids, and
the shape carries it: the cutover importer posts one entry per account with
`source_id` = the account and `event` = `cutover:<batch uuid>`. **That
composition is REPORTED, not settled** — `account_opening_buckets` (B2 r9 #2)
is not built, so the importer that would own it does not exist, and US-CUS-022
fixes it when it does. What is settled is that this service will refuse the
second posting of any key it has already written.

Enforcement is BOTH halves and neither alone would do. The lookup here means
the common replay costs one SELECT and returns the original entry; the partial
unique index `uq_journal_entries_posting_key` (ledger/0004) means two workers
racing the same handoff cannot both win the lookup and both insert. The
IntegrityError from that race is caught and answered with the winner's entry,
which is what makes a lost race indistinguishable from a replay.

════════════════════════════════════════════════════════════════════════════
SOLE WRITER: A FENCE, NOT A CLAIM
════════════════════════════════════════════════════════════════════════════
Hard rule 5's second clause used to be enforced by nothing at all. It is now a
database trigger (ledger/0004): `journal_entries` and `journal_lines` refuse an
INSERT unless the session GUC `app.ledger_posting` is `on`, and this module is
the only thing that turns it on — inside its own transaction, for the length of
three statements, and off again before it returns.

Said plainly because hard-won law 1 is about exactly this kind of sentence:
**that is a fence against the accident, not a vault against intent.** Anything
holding a connection can issue the same `set_config`. What it makes impossible
is a new module, a repair script or a well-meaning `bulk_create` moving the
books without balancing, keying, stamping and auditing them — and BR-LED-007
names that bypass as the ONLY way a subledger tie-out can drift. A caller
determined to forge the GUC has to write "I am bypassing the ledger posting
service" into its own source, which is the most a database can ask of it.

════════════════════════════════════════════════════════════════════════════
WHO CALLS THIS — RE-VERIFIED AGAINST THE CODE, 2026-08-16
════════════════════════════════════════════════════════════════════════════
⚠ **REWRITTEN TWICE, AND THE SECOND REWRITE IS WHY THIS SECTION IS DATED.**
It was headed *"WHAT NOTHING CALLS YET"* until 2026-08-11, then *"ONE MODULE
DOES NOW; TWO STILL DO NOT"* — and by 2026-08-16 that heading was as wrong as
the one it replaced. It said *"`apps/payments/models.py` is three lines and
defines no tables"*; that file is **736 lines and defines eighteen tables**, and
every payments row of the contract table has been posting for days. A comment
claiming a guarantee is not the guarantee, and a comment claiming an ABSENCE is
not the absence either (hard-won law 1). So this list is now a MEASUREMENT with
the date it was taken, and the next lane to touch this file should re-take it
rather than trust it.

US-LED-001's contract table has seventeen source events. **Thirteen post
today** and each names the caller that reaches this service:

  ✅ Invoice issued (cycle · first · final · rebill · back-bill · penalty)
     `apps/billing/issue.issue_invoice` → `apps/billing/posting_seam.
     post_bill_issue`, inside the issue transaction. DR the tenant's
     `accounts_receivable` designation for `invoices.total`, CR one bucket per
     distinct stamped GL account — WE-1 arrives as DR AR **247.87** against its
     nine signed buckets.
  ✅ Payment cleared · ✅ Cash deposit taken · ✅ NSF (reversing pair + fee) ·
     ✅ Payment reversal/void · ✅ Refund executed · ✅ Refund voided ·
     ✅ Write-off approved · ✅ Bank-rec explained difference · ✅ Bank-rec
     un-reconcile
     all through `apps/payments/ledger_seam.py`, from `services.py`,
     `purposes.py`, `reversal.py`, `refunds.py`, `writeoffs.py` and
     `reconciliation.py`.
  ✅ Credit note + rebill (correction) — `apps/billing/corrections.py` composes
     both entries through `posting_seam`'s resolved contract.
  ✅ Tax remittance payment — `apps/ledger/journal.record_tax_remittance`.
  ✅ Manual JE — `apps/ledger/manual_je.py`, over this file's draft primitives.

⚠ **THE OTHER FOUR HAD NO WRITER AT ALL AND NOW ALL FOUR DO — re-measured
2026-08-16 by the US-LED-001 four-unposted-events lane, and the honest statement
is in TWO parts because the two questions have different answers.**

**Every one of the seventeen contract rows now has product code that composes
it.** What was missing was never the contract — it was the function. The
paragraph this replaces said so of the cutover row in as many words (*"a MISSING
WRITER, not a missing contract"*) and the same was true of the other three:

  ✅ **The opening-balance cutover batch (GT-16)** — `apps/ledger/
     opening_balances.py`. The composition used to live INSIDE
     `tests/golden/test_gt16_opening_journal_entry.py`, so the ❄️ frozen test
     asserted its own arithmetic; that file now drives the module, and the
     figures are unchanged (DR AR **267.30** / CR opening clearing **267.30**,
     dated 2026-08-31).
  ✅ **The first-bill deposit LINE** (BR-BIL-012) — `apps/billing/issue.
     _gl_account_for`'s `deposit` branch, which stamps the `deposit_liability`
     designation so the line rides into the books inside the bill's own issue
     entry, exactly as the contract row describes it. It had been arriving as a
     FEE, which that function refuses for want of a charge code, so **no first
     bill carrying a deposit could issue at all** (DEF-181).
  ✅ **The deposit INTEREST accrual** (BR-CUS-050/057, LE-1's **3.50**) and
     ✅ **the deposit APPLICATION at final bill** (BR-BIL-013, LE-1's
     **153.50**) — `apps/ledger/deposit_legs.py`, emitted by
     `apps/billing/posting_seam.emit_final_bill_deposit_legs` inside the final
     bill's own issue transaction.

**AND THIRTEEN OF THE SEVENTEEN ARE STILL THE ONLY ONES A RUNNING PRODUCT CAN
REACH.** Each of the four now carries a NAMED blocker instead of an absence,
and none of the four blockers is the ledger's:

  * the cutover has no importer — `account_opening_buckets` (B2 r9 #2) is
    unbuilt, US-CUS-021 owns the table and US-CUS-022 the import;
  * a first bill and a final bill are both produced ONLY through `POST
    /billing/one-time`, which DRAFTS and cannot issue while **OQ-241** (a
    cycle-less bill's due-days) is open;
  * and a closure that holds a deposit additionally refuses because
    `apps.customers.selectors.deposit_interest_accrued` is published by nothing
    — BR-CUS-057's accrual engine is US-CUS-023 §7 and is unbuilt, so
    `final_bill.deposit_credit_for` will not report a deposit position at all.

⚠ **ADDED 2026-10-14 (`CR-185-BRC10`) — THE CONTRACT ROW THIS LIST NEVER
COUNTED NOW HAS A CALLER.** The table also names *"Master-account balance
transfer | AR (master) | AR (final account) — AR total unchanged"*, which no
product code composed (only LE-1's test fixture did). PO 2026-10-14 D5
(`OQ-1250` CLOSED → a) made the move-out *Balance to owner* that event:
`apps/ledger/balance_transfer.post_balance_to_owner`, reached from
`apps/customers/move_out_settlement.shortfall_decision`, posts DR AR (owner
account) / CR AR (tenant account) through `post()` below. Nothing in THIS file
changed for it.

That distinction is the whole reason this section is a MEASUREMENT with a date.
*Built* and *reachable* are different claims and this file has now been wrong
about the difference once already (hard-won law 2).

**WHAT THE DEPOSIT WORK COSTS UNTIL THEN, AND IT IS VISIBLE ON A SCREEN.** The
two final-bill deposit legs are exactly the sides US-LED-004's deposit tie-out
compares. A utility that takes a deposit sees the 2300 liability rise (payments
posts the receipt) and, until a final bill can issue, nothing lower it — so the
tie-out panel still reports it. That is the panel working, not the panel
misfiring.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SLICE DOES NOT BUILD, NAMED SO SILENCE IS NOT READ AS "DONE"
════════════════════════════════════════════════════════════════════════════
  * ✅ **US-LED-002's DIMENSION RESOLUTION — BUILT 2026-08-16, and this entry
    is kept as a correction rather than deleted.** It read: *"this service
    CARRIES all seven dimensions … but it does not RESOLVE the premises chain:
    customers publishes no account → unit read and metering no unit → premises
    read … a line may lawfully carry `premises=None` today."* `_stamped` above
    resolves it now, through `apps/ledger/dimension_seam.py`, and a line naming
    an account whose chain cannot be resolved is REFUSED (US-LED-002 TC-5)
    rather than written with a NULL. What remains lawfully un-dimensioned is a
    line that names NO account — a bank fee, a deposit-batch cash leg — which
    is BR-LED-001's *"where they apply"* and not a gap.
  * **US-LED-002 TC-5's tax-line refusal** (*"a tax line without
    tax_authority_id → posting fails atomically naming the gap"*) for the same
    reason: `journal_lines` cannot tell a tax line from any other line, so a
    refusal here would fire on the wrong rows. Named, not stubbed with a guess.
    **CORRECTED TWICE, and the trail is kept because each correction moved the
    blocker one step.** It first blamed OQ-116 (*"the GL-account classification
    OQ-116 is blocked on"*); OQ-116 closed and an invoice line names its tax
    (`invoice_lines.tax_id`, BR-BIL-069), so it then read *"nothing emits a
    stage-7 handoff at all, so no classification reaches this service"*. **That
    is false as of 2026-08-11** — billing emits the handoff now. What is
    missing today is one hop: `journal_lines.tax_authority_id` points at
    `rating.TaxJurisdiction` and an invoice line names its `taxes` ROW, and
    rating publishes no `tax_authority_id_for_tax` for billing to make the hop
    with (billing may not read rating's ORM, B1). `apps/billing/posting_seam.py`
    asks for that read BY NAME and reports `tax_bucket_names_no_authority` while
    nothing answers, so the day rating publishes it the dimension starts
    arriving here with no edit on either side — and only then can this service's
    refusal be written against rows it can actually recognise.
  * **BR-TEN-038's closed-period auto-forward** (*"late-dated events auto-post
    forward with audit"*, LE-9) — **the FORWARD, and only the forward.**
    ⚠ **CORRECTED 2026-09-02 (DEF-3202), and the old sentence is quoted because
    it is the exact shape hard-won law 1 warns about.** It read: *"`tenant_
    settings.lock_closed_periods` is a boolean and **there is no record of which
    periods are closed** — no fiscal period table exists anywhere in the schema.
    US-LED-015 owns close. Until it exists, `entry_date` is written exactly as
    the caller names it."* **US-LED-015 LANDED. `FiscalPeriodClose` exists and is
    tenant-scoped**, so the premise had been false for weeks while the paragraph
    read as a guarantee — and CR-060 §6 went further and stated as fact that
    `post()` resolves the date to an open period. Measured: an entry dated 31
    July POSTED into a closed July and the closed month's trial balance moved.
    **What is true now: a closed-period date is REFUSED here**
    (`_refuse_if_period_closed`, on `post()` and on `post_draft()`), and the
    FORWARD is still not done here — the caller resolves it through
    `close.resolve_entry_date` and posts the date that comes back, because only
    the caller knows whether moving a date is right (a late payment: yes; an
    accrual: never). OQ-107's *"the caller names the date"* is unchanged; what
    the caller may no longer name is a date the books have locked.
  * **BR-LED-005's accrual auto-reversal.** The forward link column exists and
    0002 leaves its one door open; the day-1-of-next-period job is US-LED-012.
  * ✅ **The subledger tie-outs (US-LED-004) — BUILT 2026-08-16.** Amended
    twice and both trails kept. This read *"Reads over what this writes;
    EP-LED-03's territory"*, then (2026-08-11) *"the READS now exist … what
    remains unbuilt is US-LED-004's tie-out COMPARISON against the customer
    registers"*. `apps/ledger/tie_out.py` is that comparison and
    `GET /finance/tie-outs` serves it onto S36. It calls nothing in this file
    and this file is unchanged by it — but it is the thing that WATCHES this
    file: BR-LED-007 names a posting-service bypass as the only way a tie-out
    can drift, so the panel is the sole-writer fence's alarm bell.
    **US-LED-008's S56 trial-balance screen is still that story's.**
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import IntegrityError, connection, transaction

from apps.ledger import dimension_seam, models, selectors
from core import audit as core_audit
from core import numbering as core_numbering
from core import errors
from core import tenancy as core_tenancy

#: The session GUC ledger/0004's sole-writer trigger reads. Named once here so
#: the fence and the one lawful way through it are greppable from each other.
WRITE_WINDOW_GUC = "app.ledger_posting"
WRITE_WINDOW_OPEN = "on"
WRITE_WINDOW_SHUT = "off"

#: The posting key's separator — see the module docstring. `|` cannot occur in
#: a uuid or in a snake_case event name, so the three parts stay unambiguous.
#: Same character and same reasoning as `core.idempotency.KEY_SEPARATOR`; not
#: imported from there because that module scopes itself to bill runs and says
#: so, and one shared constant would make this file depend on that scope.
KEY_SEPARATOR = "|"

#: The audit action code. `journal.posted` is EP-LED-01 §5's own entry
#: (*"`audit_log` `journal.posted` (source ref)"*), and `journal.reversed` is
#: US-LED-003 §5's. Codes, never prose — the trail is grouped on them.
AUDIT_POSTED = "journal.posted"
AUDIT_REVERSED = "journal.reversed"

#: US-LED-011 §5's own three codes (*"`audit_log` `journal.draft_*` /
#: `journal.posted`"*) and TC-6's `journal.draft_deleted` by name. A draft moves
#: no money, and these rows are still written: TC-6 wants the deleted draft
#: *"gone without trace in the books"* with *"audit `journal.draft_deleted`
#: remains"*, which is only possible if saving one was recorded too.
AUDIT_DRAFT_SAVED = "journal.draft_saved"
AUDIT_DRAFT_UPDATED = "journal.draft_updated"
AUDIT_DRAFT_DELETED = "journal.draft_deleted"

#: US-LED-012 TC-1's own code. Distinct from `journal.reversed` because the two
#: answer different questions: a human corrected an entry, versus the schedule
#: BR-LED-005 promised fired on day 1. A month-end reviewer greps for one and
#: not the other.
AUDIT_AUTO_REVERSED = "journal.auto_reversed"


class PostingError(RuntimeError):
    """A posting request the books refuse, with the reason a human can act on.

    Not `core.errors.BizError`: this service has no HTTP surface and its
    callers are other services, which record a break and carry on to the next
    document (BR-BIL-055's shape). The caller decides what an API sees.
    """


@dataclass(frozen=True)
class PostingLine:
    """One side of a balanced pair, exactly as the caller specifies it.

    `ledger_account_id` is resolved by the CALLER, through
    `apps/ledger/selectors.py` — by DESIGNATION or by SERVICE, never by code.
    This service does not pick accounts: US-LED-001's contract table names them
    per source event and OQ-106 exists precisely so nothing has to hardcode
    1200.

    `amount` is a `Decimal` and is written unchanged. **Never a float** (hard
    rule 2) — `post()` refuses one rather than coercing it, because a coercion
    would hide the place where money became binary and the refusal names it.
    Direction is the `side`; the amount carries no sign (B2's
    `CHECK (amount >= 0)`).

    The seven dimensions are BR-LED-001 / B2 r13 #1. `source_type` and
    `source_id` are REQUIRED on every line — BR-LED-001 in US-LED-001's own
    rules table: *"every journal line carries source_type + source_id — every
    contract row above traces to its document"*, and LE-5's auditor question
    (*"what is the 506.31?"*) is answerable only because they are. The other
    five are required *where they apply* (a cash line names no service), which
    is why they default to None here and why the schema keeps them nullable.
    """

    ledger_account_id: Any
    side: str
    amount: Decimal
    source_type: str
    source_id: Any
    service_id: Any = None
    account_id: Any = None
    premises_id: Any = None
    unit_id: Any = None
    tax_authority_id: Any = None
    #: ⚠ **`P0.1` / `P0.3` — WHO HELD THE ACCOUNT, STAMPED AT POST.**
    #: The SIXTH dimension. It is resolved from `account_id` by `_stamped`,
    #: ONCE, at the moment of posting, and written verbatim thereafter — never
    #: re-derived by a reader. That IS the design: a reader walking
    #: `journal_lines → accounts → customer_accounts` gets *who holds the
    #: account NOW*, which is correct today and wrong the day the account
    #: changes hands (`BR-CUS-1030`) — and by then the line is immutable and
    #: nothing says the answer moved.
    #:
    #: `None` stays `None`. A cash line, a bank fee and a deposit-batch leg
    #: name no account and therefore no customer, which is `BR-LED-001`'s
    #: *"where they apply"* and not a gap. A caller may also pass one
    #: explicitly, and an explicit value is never overwritten.
    customer_id: Any = None


@dataclass(frozen=True)
class PostingRequest:
    """One balanced journal entry, fully specified. Nothing here is derived.

    `posting_key` is the replay guard (hard rule 6) — compose it with
    `posting_key()` rather than by hand, so every caller keys the same way.

    `entry_date` is the BOOK date and `posted_at` the wall-clock moment; both
    are INPUTS (PO ruling 2026-08-11 on OQ-107, BR-TEN-043). `currency` is hard
    rule 2's CHAR(3) partner and has no default: the source document always has
    one, and a defaulted currency is how a CAD tenant's books quietly become
    USD.

    `source_type` / `source_id` on the ENTRY are the document the whole entry
    traces to (B2 §2's polymorphic pair). They may differ from a LINE's — one
    issue entry traces to the invoice while its lines trace to individual
    invoice_line rows, which is what makes the S42 drill-back work.
    """

    posting_key: str
    entry_date: date
    posted_at: datetime
    currency: str
    lines: tuple[PostingLine, ...]
    source_type: str | None = None
    source_id: Any = None
    memo: str | None = None
    entry_type: str = models.JE_STANDARD
    reversal_of_id: Any = None
    #: ⚠ **`P0.3` — THE `JE-` NUMBER, AND WHY IT IS OPTIONAL RATHER THAN
    #: ABSENT OR REQUIRED.**
    #: `BR-LED-021` gives every posted entry a human-readable number. Until
    #: 2026-09-24 only the MANUAL path allocated one: `post_draft` takes it as
    #: a parameter because `manual_je` orchestrates that flow and could do the
    #: allocating. `post()` has no orchestrator — it is called by the bill run,
    #: the payment webhook, the accrual sweep and the remittance — so
    #: **`post()` allocates its own**, from the tenant's `journal_entry` series
    #: under `BR-TEN-035`, inside the posting transaction. Measured before the
    #: change: `journal_entries` held **167 rows and 0 numbers**.
    #:
    #: Passing one here OVERRIDES the allocation, and the case that needs it is
    #: real: a caller that has already taken a number, or one replaying a
    #: sequence it must reproduce exactly, must not be given a second.
    number: str | None = None
    #: Extra facts for the audit row's `after` payload. Money figures and ids
    #: only — BR-AUD-006 keeps PII out of the trail.
    audit_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PostingResult:
    """What one `post()` call did — and whether it did anything at all.

    `created=False` is the replay no-op (US-LED-001 TC-6), and it is a RESULT
    rather than an exception because a replayed handoff is the correct,
    expected outcome of a resumed batch, not an error anyone should have to
    catch. `entry_id` is the FIRST entry either way, so a caller can link to
    the books without knowing which call won.

    `debits` / `credits` are echoed so a caller can tie out what it asked for
    against what landed — BR-LED-007's whole discipline, applied at the moment
    of posting rather than a month later on S36.
    """

    entry_id: str
    posting_key: str
    created: bool
    debits: Decimal
    credits: Decimal
    line_count: int


# ── the posting key (mechanics 🔒, B2 r13 #8) ───────────────────────────────
def posting_key(*, source_type: str, source_id: Any, event: str) -> str:
    """The replay guard's string: source document + the event that hit it.

    Pure and total — same three inputs ⇒ same string, always, with no clock, no
    ordering assumption and no database read. That is what lets a caller check
    for a duplicate before doing any work and still be backstopped by
    `uq_journal_entries_posting_key` if it loses a race.

    Refuses a missing part rather than composing a short key: two different
    payments whose keys were both `"payment||cleared"` would collide, which is
    the exact double-posting the guard exists to prevent.
    """
    parts = (source_type, str(source_id) if source_id is not None else "", event)
    if not all(str(part).strip() for part in parts):
        raise PostingError(
            "a posting key needs the source_type, the source_id AND the event "
            f"(got {source_type!r}, {source_id!r}, {event!r}). US-LED-001 TC-6 wants "
            "'one entry, ever' per source event; a key composed with a part missing "
            "would collide across different documents, which is the double-posting "
            "the guard exists to prevent."
        )
    return KEY_SEPARATOR.join(str(part) for part in parts)


# ── tenant + write window ───────────────────────────────────────────────────
def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refuses rather than defaulting. A posting that ran with no tenant context
    would be blocked by RLS on Postgres and would write another tenant's books
    on SQLite; neither is a thing to let happen quietly on the one table every
    money figure is summed from.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _set_write_window(state: str) -> None:
    """Open or shut the sole-writer window (ledger/0004).

    `set_config(..., true)` is transaction-local, so a crash or a rollback
    closes it whatever else happens. On a database without the trigger (the
    SQLite developer database) this is a no-op — the guarantee is Postgres's
    and is not simulated where it does not exist.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [WRITE_WINDOW_GUC, state])


# ── BR-LED-006: a closed month never receives new money (DEF-3202) ──────────
def _refuse_if_period_closed(entry_date: date, *, what: str) -> None:
    """BR-LED-006's lock, enforced where hard rule 5 says the writes are.

    ⚠ **ADDED 2026-09-02 (DEF-3202), and it closes a hole three documents said
    was already closed** — this file's own paragraph on BR-TEN-038 (below, now
    corrected), CR-060 §6, and the way BR-LED-006 reads. Hard-won law 1: a
    comment claiming a guarantee is not the guarantee. Measured on PostgreSQL
    16: an entry dated 31 July posted into a CLOSED July, and the closed
    month's trial balance moved — which BR-LED-006 and BR-LED-017 both promise
    cannot happen.

    **IT REFUSES. IT DOES NOT FORWARD, AND THAT IS THE WHOLE DESIGN** (lane
    ruling 2026-09-02, decision log). BR-TEN-038's auto-forward is real, signed
    and implemented — ONCE, in `close.resolve_entry_date` — and the CALLER
    invokes it, because the caller is the only layer that knows whether moving
    the date is right:

      * a payment that genuinely arrived late SHOULD land in the open month
        (LE-9, and `manual_je` / `cost_capture` resolve for exactly this);
      * a month-end ACCRUAL never should — forwarded, it recognises August's
        revenue in September and reverses it in October, two months wrong in a
        signed book to avoid saying no (CR-060 T7's recorded judgment).

    A writer that forwarded by default would have silently done the wrong one
    of those for every caller nobody has written yet, and hard-won law 3 says
    the unsafe option is the one you type.

    **THE FAST PATH IS LOAD-BEARING, NOT AN OPTIMISATION.**
    `close.resolve_entry_date` returns immediately when the tenant holds no
    closed period at all, WITHOUT consulting the fiscal calendar — and
    `close.period_window` REFUSES for a tenant that has no fiscal settings, by
    design. Asking "which period is this in?" before "has this tenant closed
    anything?" would make every brand-new tenant unpostable: no bill, no
    payment, no opening balance, for a rule that cannot apply to them. That is
    also why the ONE implementation is reused rather than a second
    `is_closed_on` call written here.

    **THE CALLER AUDIT, 2026-09-02, because `DEF-3202` recorded it too kindly.**
    The defect row reads *"every caller happens to resolve the date itself"*.
    **Nine call sites reach this service and three of them checked anything:**
    `manual_je` (forwards, at save AND — since this defect — at post),
    `unbilled_accrual` (refuses, deliberately, and its refusal is NOT redundant:
    it also refuses to be FORWARDED, which this guard cannot say), and
    `cost_capture` (forwards, and never actually posts — `OQ-200`). **The other
    six did nothing at all:** `journal.reverse_and_repost`, `journal`'s tax
    remittance, both `deposit_legs` postings, both `opening_balances` postings,
    and `billing/posting_seam` (which posts on `invoice.service_date`). So this
    was never a hole waiting for a future caller — six live paths could already
    write into a locked month. **No caller's own check DISAGREES with this
    guard**; the three that check either forward first (so this sees an open
    date) or refuse earlier and for a stronger reason.

    **WHAT IT COSTS, stated so nobody "optimises" it away without knowing.** One
    indexed EXISTS per posting — 500 on a 500-bill run — and on a tenant that has
    closed a period, one more period lookup. It is not cached, deliberately: a
    cache would have to be invalidated by a close happening in another session,
    and a stale "the month is open" is precisely the wrong answer to be fast
    about.
    """
    from apps.ledger import close  # local: `close` reaches this module lazily too

    try:
        landing, note = close.resolve_entry_date(entry_date)
    except close.CloseError as refusal:
        # Every open period ahead is closed, or the fiscal calendar vanished
        # after a period was closed. Both are real refusals a human acts on, so
        # they arrive as PostingError — `post()` documents that as its contract.
        raise PostingError(
            f"{what} cannot be dated {entry_date.isoformat()}: {refusal}"
        ) from refusal
    if note is None:
        return
    raise PostingError(
        f"{what} is dated {entry_date.isoformat()}, which falls inside the CLOSED fiscal "
        f"period {note['requested_period'][0]} … {note['requested_period'][1]}. BR-LED-006: "
        "a closed period LOCKS, and BR-LED-017 lets an ERP receive a closed period's figures "
        "precisely because they can never move again. Nothing is written.\n"
        "  This service refuses the date; it does not move it, because only YOU know which "
        "of the two lawful answers you wanted:\n"
        f"  · a genuinely late-arriving event forwards to {landing.isoformat()} — call "
        "apps.ledger.close.resolve_entry_date(entry_date) first, post the date it returns, "
        "and carry its note into audit_context and onto the screen (BR-TEN-038, LE-9);\n"
        "  · an accrual, a cut-over balance or anything whose date IS its meaning must NOT be "
        "moved — recognising one month's money in another is worse than refusing — so report "
        "the refusal and let a System Admin reopen the period (BR-LED-006).\n"
        "  (DEF-3202: this guard did not exist before 2026-09-02 and this entry would have "
        "posted into the closed month.)"
    )


# ── BR-LED-025: two decimal places, and the ledger never rounds ─────────────
def _carries_more_than_two_decimals(amount: Decimal) -> bool:
    """True when `amount` cannot be stated exactly in two decimal places.

    Compared BY VALUE, not by the Decimal's exponent, and the difference
    matters: `Decimal("1.2300")` has four decimal DIGITS and is exactly 1.23 —
    a caller that quantized to six places (which is what `NUMERIC(18,6)` hands
    back on a re-read) is not carrying a third cent and must not be refused.
    `Decimal("0.001")` is. So the test is *does multiplying by 100 leave a whole
    number*, which asks the only question BR-LED-025 cares about: is there money
    here that two decimal places cannot say?

    Total and pure — no rounding happens anywhere in this function, which is the
    whole point of the rule it implements.
    """
    scaled = amount.scaleb(2)
    return scaled != scaled.to_integral_value()


# ── US-LED-002: BR-LED-001's chain, resolved AT POSTING TIME ────────────────
def _stamped(lines: tuple[PostingLine, ...]) -> tuple[PostingLine, ...]:
    """Return `lines` with `premises_id` / `unit_id` resolved from the account.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  US-LED-002 — THE DIMENSION THAT WAS CARRIED FOR FIVE DAYS AND       ║
    ║  NEVER RESOLVED, WHICH IS WHY S60 ANSWERED `available: false`        ║
    ╚══════════════════════════════════════════════════════════════════════╝
    BR-LED-001 (CONFIRMED — PO LF-1, 2026-08-08) wants `premises_id` and
    `unit_id` *"resolved account → unit → premises AT POSTING TIME"*. Until
    2026-08-16 this file carried the two columns and resolved neither, because
    neither customers nor metering published the read — so **every journal line
    in the product held `premises_id = NULL`**, `reporting.by_premises_summary`
    refused with LE-6's own unattributed **553.69**, and the S60 report told a
    utility it could not say which premises its money came from.
    `apps/ledger/dimension_seam.py` closes that, and this is where it is used.

    **WHY HERE AND NOT IN THE CALLERS.** Seventeen source events post through
    `post()` (US-LED-001's contract table) and each would otherwise have to
    resolve the chain itself — seventeen implementations of one signed rule, of
    which the first to drift would put a bill and its own correction on
    different premises. BR-LED-001 says *at posting*, so it is at posting.

    **WHAT IS NEVER OVERWRITTEN.** A line that ARRIVES carrying both ids keeps
    them. That is not an optimisation: `reverse_entry` copies its original's
    stamps, and US-LED-002 TC-4 requires the mirror of a 2026-07 entry to carry
    the premises the money was billed against even if the unit has since been
    deactivated and recreated somewhere else. Re-resolving would move history.

    **WHAT IS NOT DIMENSIONED, AND IT IS A RULE RATHER THAN AN OMISSION.** A
    line naming no account is left alone. BR-LED-001 requires the dimensions
    *where they apply*, and a bank-fee line or a deposit-batch cash line is
    money about the utility's own bank account, not about anyone's premises —
    `apps/payments/ledger_seam.py` says so in as many words at both call sites.
    Inventing a premises for them would put the utility's bank charges on a
    customer's address in every by-premises report.

    US-LED-002 TC-5, verbatim: *"a posting handoff whose account has no
    resolvable unit→premises chain → posting fails atomically naming the gap —
    no undimensioned money line ever lands."* So an account that resolves to
    nothing RAISES, before the transaction opens and therefore before any row
    exists. It is a `PostingError` and not a silent skip because a skip would
    write exactly the NULL this story exists to remove, and nothing downstream
    could tell that line apart from a lawful cash line.
    """
    # ⚠ **`P0.1` WIDENED THE TRIGGER, AND FORGETTING TO WOULD HAVE BEEN
    # INVISIBLE.** This read *"account_id and not (premises_id and unit_id)"*
    # until 2026-09-24 — i.e. *does any line still need its LOCATION?* A line
    # that arrived with both ids already stamped short-circuited the whole
    # function, and would have skipped the CUSTOMER stamp with it. The
    # commonest such line is a REVERSAL, which copies its original's
    # dimensions: every mirror in the product would have posted with no
    # customer while its original had one, and nothing would have gone red.
    if not any(
        line.account_id
        and not ((line.premises_id and line.unit_id) and line.customer_id)
        for line in lines
    ):
        return lines

    # One entry's lines are usually one account (nine GL buckets on one bill),
    # so each question is asked once per DISTINCT account rather than once per
    # line. Two independent memos, because a line can need one answer and not
    # the other.
    resolved: dict[str, dimension_seam.Location] = {}
    customers: dict[str, str | None] = {}
    stamped: list[PostingLine] = []
    for line in lines:
        if not line.account_id:
            stamped.append(line)
            continue
        key = str(line.account_id)

        # ── the SIXTH dimension (`P0.1`) ──────────────────────────────────
        # Resolved for every line that names an account and does not already
        # carry one. An explicit value is never overwritten, for exactly the
        # reason the location is not: `reverse_entry` copies its original's
        # stamps, and a mirror must name the customer the money was billed to,
        # not whoever holds the account today.
        customer_id = line.customer_id
        if not customer_id:
            if key not in customers:
                customers[key] = dimension_seam.customer_id_for_account(key)
            customer_id = customers[key]

        if line.premises_id and line.unit_id:
            stamped.append(replace(line, customer_id=customer_id))
            continue
        location = resolved.get(key)
        if location is None:
            location = dimension_seam.location_for_account(key)
            resolved[key] = location
        if not location.resolved:
            raise PostingError(
                f"account {key} has no resolvable unit → premises chain "
                f"({location.problem}), so this entry's lines cannot carry "
                "BR-LED-001's premises and unit dimensions. US-LED-002 TC-5: posting "
                "fails atomically naming the gap — no undimensioned money line ever "
                "lands. Nothing was written."
            )
        stamped.append(
            replace(
                line,
                premises_id=line.premises_id or location.premises_id,
                unit_id=line.unit_id or location.unit_id,
                customer_id=customer_id,
            )
        )
    return tuple(stamped)


# ── P0.7: the books are kept in ONE currency, and it is the tenant's ────────
def _refuse_unless_the_tenants_currency(currency: str) -> None:
    """The entry's currency must equal the tenant's configured currency.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  P0.7 — *"A CAD tenant's books cannot quietly become USD"*           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **STAMPED, NOT JOINED, AND THAT IS WHY THE CHECK HAS TO BE HERE.** Hard
    rule 4 makes a posted entry immutable, so the currency it carries is the
    currency it carries FOR EVER — no later correction can reach it. And
    `BR-TEN-021` makes a tenant's currency change FORWARD-ONLY, so the entries
    already in the books legitimately hold the old code. Those two facts
    together mean the only moment the question *"is this the right currency?"*
    can be asked is the moment of posting.

    **WHAT WOULD HAPPEN WITHOUT IT.** A caller that passed `"USD"` on a CAD
    utility would write a perfectly valid, perfectly balanced entry in the
    wrong money. It would foot. The trial balance would foot. `journal_entries`
    is `NOT NULL` on this column and `tenancy/0050` makes it a foreign key into
    `currencies`, so **the database would accept it too** — `USD` is a real
    currency, it is simply not this utility's. Nothing anywhere would go red,
    and hard rule 4 means the row could never be corrected, only reversed.
    Until 2026-09-24 `JournalEntry.currency` carried `default="USD"` as well,
    so a caller did not even have to pass the wrong value to get it.

    **NOT A FOREIGN KEY'S JOB.** The database can say *this is a currency*; it
    cannot say *this is YOUR currency* without a composite key the schema does
    not have. The three layers are complementary: the model refuses a missing
    value, this refuses the WRONG value, the foreign key refuses an IMPOSSIBLE
    one.

    ⚠ **A TENANT WITH NO CURRENCY SET IS NOT REFUSED.** `tenants.currency`
    defaults to `USD` at provisioning and is never null in practice, but a read
    that comes back empty must not stop the books over a settings row — the
    same posture `manual_je` takes for a missing numbering series. The check
    simply does not apply, and the entry posts with what the caller named.
    """
    from apps.tenancy import selectors as tenancy_selectors  # local — B1 seam

    try:
        tenant_currency = tenancy_selectors.regional_settings().get("currency")
    except Exception:  # noqa: BLE001 — see the docstring; a settings read must
        return  # not be able to stop a bill run
    if not tenant_currency:
        return
    if str(currency).upper() != str(tenant_currency).upper():
        raise PostingError(
            f"this entry is in {currency!r} and this utility keeps its books in "
            f"{tenant_currency!r}. A posted entry is immutable (CLAUDE.md rule 4), so an "
            "entry written in the wrong currency can never be corrected — only reversed — "
            "and it would balance, foot and pass every other check on the way in. "
            "BR-TEN-021 makes a currency change forward-only, so entries already posted "
            "lawfully hold the previous code; this is about the one being written now. "
            "Nothing was written."
        )


# ── P0.3: BR-LED-021's number, on the SYSTEM path too ───────────────────────
#: Reported on the audit row when a tenant has no `journal_entry` series, so
#: the absence is a NAMED fact rather than a silent NULL.
#:
#: **THE SAME CODE STRING `apps/ledger/manual_je.py` HAS USED SINCE
#: 2026-08-15** — one condition, one name — so the S56 list's
#: `posted_entries_without_a_je_number` counts manual and system entries
#: alike. It is spelled out here rather than imported because `manual_je`
#: holds a whole refusal DICT under that name and this path puts one string on
#: an audit payload; importing the dict would put a `detail` paragraph into
#: `audit_log` on every affected post. The shared thing is the CODE.
NUMBER_SERIES_NOT_SEEDED_CODE = "journal_number_series_is_not_seeded"


def _allocated_number(request: PostingRequest) -> tuple[str | None, str | None]:
    """BR-LED-021's `JE-` number for a SYSTEM-posted entry, or the named gap.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  P0.3 — THE NUMBER THAT ONLY THE MANUAL PATH EVER GOT                ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **MEASURED BEFORE THIS WAS WRITTEN**, on the seeded database (PostgreSQL
    16.13, tenant `brazosbend`, 2026-09-24): `journal_entries` held **167 rows
    and 0 numbers**, and `number_series.journal_entry.next_number` was still
    **1** — the series had been seeded for five weeks and never once consumed.
    Every entry in the product traces to a bill run, a payment or an accrual,
    and every one of those posts through `post()`, which allocated nothing. So
    a finance officer told to *"look at JE-105"* had nothing to look at, and
    `BR-LED-021` — a PO ruling of 2026-08-12 — was in the product for manual
    entries only.

    ⚠ **WHETHER THE SERIES COVERS SYSTEM-GENERATED ENTRIES WAS FLAGGED AS
    UNSETTLED, AND IT IS SETTLED BY READING RATHER THAN BY ASKING.**
    `BR-LED-021`'s own row says *"whether BR-LED-021's series covers
    system-generated entries or only manual ones was never put to the PO"*.
    **It does not need to be:** `LE-4`, a ratified golden document, draws
    *"Sep 30 **JE-201** (accrual) → Oct 1 **JE-202** auto-posts the mirror"* —
    and an accrual mirror is posted by `reverse_entry`, which is this path. A
    ratified worked example already shows a system entry carrying a number.
    The Finance blueprint's own acceptance sentence agrees: *"a newly posted
    entry carries a `JE-` number"*, with no exception for machine paths.
    Recorded in the decision log rather than put back to the PO (law 13).

    ⚠ **GAPS HAPPEN, AND THAT IS THE SIGNED RULE.** `BR-LED-021`'s
    decision-log row calls the series *"gapless"* while `BR-TEN-035` allocates
    from a monotonic counter where *"gaps ok, never reused"*. `BR-TEN-035` is
    the signed numbering rule and `BR-LED-021`'s own CONFIRMED text already
    concedes the point (*"the build allocates through BR-TEN-035's monotonic
    counter, so GAPS HAPPEN"*). A rolled-back post therefore consumes a number
    and leaves a hole. `tests/test_p0_10_je_numbering_behaviour.py` asserts the
    hole, so nobody later "fixes" it into a gapless series the allocator cannot
    provide.

    ⚠ **A MISSING SERIES DOES NOT STOP THE BOOKS, AND THAT IS DELIBERATE.**
    A tenant provisioned before CR-005 has no `journal_entry` row until
    `seed_demo` runs. Refusing to post would make a bill run fail over a
    settings row — money the utility has billed, unrecorded, because of
    numbering. So the entry posts with `number = NULL` and the reason travels
    on the audit row by name. That is exactly what `manual_je` has done since
    2026-08-15, and reusing its code keeps ONE condition with ONE name.

    **A CALLER-SUPPLIED NUMBER WINS AND NOTHING IS ALLOCATED.** See
    `PostingRequest.number`.
    """
    if request.number is not None:
        return str(request.number), None
    try:
        return (
            core_numbering.next_number(core_numbering.JOURNAL_ENTRY, request.entry_date),
            None,
        )
    except core_numbering.NumberingError:
        return None, NUMBER_SERIES_NOT_SEEDED_CODE


# ── validation: everything that must be true BEFORE a row is written ────────
def _refuse_unless_postable(request: PostingRequest) -> tuple[Decimal, Decimal]:
    """Every check, in one place, before the first INSERT. Returns (DR, CR).

    Takes no tenant argument on purpose: the one check that is tenant-scoped
    (`selectors.account_is_live`) resolves `app.tenant_id` itself, so there is
    exactly one place that decides which tenant's chart is being read and this
    function cannot be handed a different one.

    All of them are cheap and all of them are unrepairable afterwards: once the
    entry posts, hard rule 4 leaves no path to change any of it. This is also
    the SERVICE-LAYER half of laws whose database half is Postgres-only — the
    developer database is SQLite and has no triggers, so a guard that lived
    only in the migration would not be a guard where the code is written.
    """
    if not str(request.posting_key or "").strip():
        raise PostingError(
            "a posting request carries no posting_key, so a replay could not be "
            "recognised and the same money event would land in the books twice "
            "(CLAUDE.md rule 6 · US-LED-001 TC-6). Compose one with "
            "apps.ledger.posting.posting_key()."
        )
    if request.entry_type not in models.JE_TYPES:
        raise PostingError(
            f"journal entry type {request.entry_type!r} is not one of {models.JE_TYPES} "
            "(B2 addendum r13 #2). A typo'd type is an entry no report groups correctly."
        )
    if not isinstance(request.entry_date, date) or isinstance(request.entry_date, datetime):
        raise PostingError(
            "entry_date must be a date — it is the BOOK date the trial balance groups by, "
            "and the Product Owner ruled on 2026-08-11 that it is asked of the user "
            '("posting and actual dates can differ; ask actual date to user"). Nothing '
            "here reads a clock (BR-TEN-043, gate G6)."
        )
    # BR-LED-006's lock (DEF-3202). Before the per-line work, because a closed
    # period refuses the WHOLE entry and there is nothing to report per line.
    _refuse_if_period_closed(request.entry_date, what="this journal entry")
    if not isinstance(request.posted_at, datetime):
        raise PostingError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043): a resumed "
            "batch, a replay and a re-run must stamp the SAME moment rather than three, "
            "which is impossible if this service reads the clock itself."
        )
    if not isinstance(request.currency, str) or len(request.currency) != 3:
        raise PostingError(
            f"currency {request.currency!r} is not a CHAR(3) code (CLAUDE.md rule 2). It "
            "sits on the ENTRY because a mixed-currency entry cannot balance in any "
            "meaningful sense — one currency per entry is what 'balanced' means."
        )
    _refuse_unless_the_tenants_currency(request.currency)
    if not request.lines:
        raise PostingError(
            "a journal entry with no lines is not a journal entry (B2 §1: journal_entry "
            "1:N journal_lines (balanced)). Nothing is posted."
        )

    debits = Decimal("0")
    credits = Decimal("0")
    for index, line in enumerate(request.lines):
        where = f"line {index + 1} of {len(request.lines)}"
        if isinstance(line.amount, float):
            raise PostingError(
                f"{where} carries a float amount ({line.amount!r}). CLAUDE.md rule 2: money "
                "is NUMERIC(18,6) and never a float. It is REFUSED rather than converted, "
                "because converting it would hide the place where money became binary and "
                "the books would carry a figure nobody can reproduce."
            )
        if not isinstance(line.amount, Decimal):
            raise PostingError(
                f"{where} carries a {type(line.amount).__name__} amount ({line.amount!r}); "
                "money is a Decimal (CLAUDE.md rule 2)."
            )
        if line.amount < 0:
            raise PostingError(
                f"{where} carries a negative amount ({line.amount}). B2 §2 is "
                "CHECK (amount >= 0): direction is the SIDE, so a negative amount would be "
                "a second, invisible way to express a credit and the balance sums would "
                "agree with themselves while the books said something else."
            )
        if _carries_more_than_two_decimals(line.amount):
            raise PostingError(
                f"{where} carries {line.amount} — MORE THAN TWO DECIMAL PLACES. BR-LED-025 "
                "(PO 2026-08-12, OQ-176's sitting, verbatim: *\"Refuse and make the caller "
                'round"*): the ledger REFUSES a posting carrying more than two decimals and '
                "never rounds what it is handed. Rounding is the CALLER's job and happens "
                "ONCE, at finalization (B4 ❄️ / BR-RAT-003). A ledger that quietly rounded its "
                "input would be a SECOND rounding site, and two rounding sites is how two "
                "figures start disagreeing — the trial balance and the bill it came from. "
                f"Round {line.amount} to two places at the point the document was finalized "
                "and post that. (The COLUMN still stores NUMERIC(18,6), CLAUDE.md rule 2 "
                "unchanged — this is about the POSTING, not the storage.)"
            )
        if line.side not in models.JOURNAL_SIDES:
            raise PostingError(
                f"{where} has side {line.side!r}, which is not one of "
                f"{models.JOURNAL_SIDES}. The balance check sums "
                "amount FILTER (WHERE side='debit') against side='credit', so an "
                "unreadable side falls into NEITHER sum and its money vanishes from both "
                "totals while the entry computes 0 = 0 and looks balanced."
            )
        if not str(line.source_type or "").strip() or line.source_id is None:
            raise PostingError(
                f"{where} names no source document (source_type={line.source_type!r}, "
                f"source_id={line.source_id!r}). BR-LED-001: *every journal line carries "
                "source_type + source_id* — it is what makes LE-5's auditor question "
                '"what is the 506.31?" answerable, and an undimensioned money line can '
                "never be traced back to what created it."
            )
        if not selectors.account_is_live(line.ledger_account_id):
            raise PostingError(
                f"{where} names ledger account {line.ledger_account_id!r}, which is not a "
                "LIVE account of this tenant's own chart. It belongs to another tenant, "
                "has been deactivated (IS-1), or does not exist — all three are refusals, "
                "and none of them is a reason to pick a different bucket. US-LED-001 TC-7: "
                "a forged id from another tenant posts nothing."
            )
        if line.side == models.SIDE_DEBIT:
            debits += line.amount
        else:
            credits += line.amount

    if debits != credits:
        raise PostingError(
            f"the request is UNBALANCED — debits {debits} <> credits {credits} "
            f"(difference {debits - credits}). CLAUDE.md rule 5 / BR-LED-003: a posted "
            "entry must balance to the cent and nothing partial lands. Refused here, "
            "before any row is written, so the caller reads this instead of a commit-time "
            "trigger failure — the database refuses it too (ledger/0002), and that fence "
            "stands whether or not this check is reached."
        )
    return debits, credits


# ── the read half of the replay guard ───────────────────────────────────────
def _existing_entry(tenant_id: UUID, key: str) -> models.JournalEntry | None:
    return models.JournalEntry.objects.filter(tenant_id=tenant_id, posting_key=key).first()


def _replayed(entry: models.JournalEntry, key: str) -> PostingResult:
    """The no-op answer for a source event already in the books."""
    totals = {models.SIDE_DEBIT: Decimal("0"), models.SIDE_CREDIT: Decimal("0")}
    count = 0
    for side, amount in entry.lines.values_list("side", "amount"):
        totals[side] = totals.get(side, Decimal("0")) + amount
        count += 1
    return PostingResult(
        entry_id=str(entry.pk),
        posting_key=key,
        created=False,
        debits=totals[models.SIDE_DEBIT],
        credits=totals[models.SIDE_CREDIT],
        line_count=count,
    )


# ── post() — the one way into the books ─────────────────────────────────────
def post(request: PostingRequest, *, actor: Any = None) -> PostingResult:
    """Write ONE balanced journal entry. All of it, or none of it.

    The whole of US-LED-001 in one call: the caller hands over a balanced,
    fully-specified request under one of the seventeen DR/CR contracts, and
    this either writes it exactly as given or refuses it naming why.

    Raises `PostingError` for every condition a human can act on — an
    unbalanced request, a float amount, an account belonging to somebody else,
    a line that names no source document, a missing key. Raises
    `core.errors.AuthError` with no tenant context. A `DatabaseError` from the
    commit means a database law refused something this function's own checks
    did not catch, and that is a defect in this file, not in the caller.

    Returns `PostingResult(created=False)` for a replay — never an exception,
    because a resumed batch replaying yesterday's handoff is doing the right
    thing (US-LED-001 TC-6).
    """
    tenant_id = _tenant_id()
    key = str(request.posting_key or "").strip()
    debits, credits = _refuse_unless_postable(request)

    # Cheap path first: a replay costs one SELECT and never opens a
    # transaction, which matters when a 500-bill run is resumed.
    already = _existing_entry(tenant_id, key)
    if already is not None:
        return _replayed(already, key)

    # US-LED-002 — BR-LED-001's chain, resolved BEFORE the transaction opens so
    # that TC-5's "posting fails atomically" costs no rollback: an unresolvable
    # account raises here, with not one row written and no write window opened.
    lines = _stamped(request.lines)

    try:
        with transaction.atomic():
            _set_write_window(WRITE_WINDOW_OPEN)
            try:
                # ── step 1: the entry, as a DRAFT ───────────────────────────
                # A draft, not a posted row, because 0002's append-only trigger
                # closes a POSTED entry to line inserts. This is BR-LED-003's
                # lifecycle, not a workaround for it.
                entry = models.JournalEntry.objects.create(
                    tenant_id=tenant_id,
                    entry_date=request.entry_date,
                    type=request.entry_type,
                    status=models.JE_DRAFT,
                    source_type=request.source_type,
                    source_id=request.source_id,
                    posting_key=key,
                    memo=request.memo,
                    currency=request.currency,
                    reversal_of_id=request.reversal_of_id,
                )
                # ── step 2: its lines ───────────────────────────────────────
                models.JournalLine.objects.bulk_create(
                    [
                        models.JournalLine(
                            tenant_id=tenant_id,
                            journal_entry=entry,
                            ledger_account_id=line.ledger_account_id,
                            side=line.side,
                            amount=line.amount,
                            service_id=line.service_id,
                            account_id=line.account_id,
                            premises_id=line.premises_id,
                            unit_id=line.unit_id,
                            source_type=line.source_type,
                            source_id=line.source_id,
                            tax_authority_id=line.tax_authority_id,
                            customer_id=line.customer_id,
                        )
                        for line in lines
                    ]
                )
                # ── step 3: post it ─────────────────────────────────────────
                # The balance trigger fires on THIS update (and again at
                # COMMIT), which is the only moment the whole entry exists to
                # be judged. `posted_at` is the caller's moment, never a clock.
                #
                # ── `P0.3` · the JE- NUMBER rides on this same UPDATE ───────
                # Allocated INSIDE this transaction, which BR-TEN-035 requires
                # and which is what makes two workers posting at once get two
                # different numbers — and what makes a rollback give the
                # number back. It is written HERE rather than at step 1
                # because `ledger/0007`'s immutability trigger freezes
                # `number` the moment the row is POSTED, so this is the last
                # statement that may carry it.
                number, number_gap = _allocated_number(request)
                entry.status = models.JE_POSTED
                entry.posted_at = request.posted_at
                entry.number = number
                entry.save(
                    update_fields=["status", "posted_at", "number", "updated_at"]
                )

                # ── hard rule 7, INSIDE the transaction ─────────────────────
                # An entry that stood without its trail row would be money in
                # the books with no record of who put it there; `core.audit`
                # raises rather than losing the row, which takes the posting
                # with it.
                core_audit.money_action(
                    actor,
                    AUDIT_POSTED,
                    "journal_entry",
                    str(entry.pk),
                    after={
                        "posting_key": key,
                        "entry_date": request.entry_date.isoformat(),
                        "posted_at": request.posted_at.isoformat(),
                        "type": request.entry_type,
                        "source_type": request.source_type,
                        "source_id": str(request.source_id) if request.source_id else None,
                        "currency": request.currency,
                        "debits": str(debits),
                        "credits": str(credits),
                        "lines": len(request.lines),
                        # ── `P0.3` ────────────────────────────────────────
                        # The number, and — where there is none — the NAMED
                        # reason. A bare NULL would be indistinguishable from
                        # a bug; `journal_number_series_is_not_seeded` is a
                        # fact an operator can act on, and it is the same code
                        # `manual_je` reports for the same condition.
                        "number": number,
                        "number_gap": number_gap,
                        "reversal_of": (
                            str(request.reversal_of_id) if request.reversal_of_id else None
                        ),
                        "job": None if actor is not None else "ledger.posting",
                        **request.audit_context,
                    },
                )
            finally:
                # Shut the window even on the way out through an exception. On
                # an already-aborted transaction this statement cannot run —
                # and does not need to, since the rollback discards the GUC
                # with everything else.
                try:
                    _set_write_window(WRITE_WINDOW_SHUT)
                except Exception:  # noqa: BLE001 — see above; never masks the real error
                    pass
    except IntegrityError:
        # The race the partial unique index exists for: another worker posted
        # this same source event between our SELECT and our INSERT. A lost race
        # and a replay are the same fact — one entry exists, ours is not it.
        winner = _existing_entry(tenant_id, key)
        if winner is None:
            raise
        return _replayed(winner, key)

    return PostingResult(
        entry_id=str(entry.pk),
        posting_key=key,
        created=True,
        debits=debits,
        credits=credits,
        line_count=len(request.lines),
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE DRAFT HALF OF BR-LED-003 (US-LED-011) — ADDED 2026-08-15
# ═══════════════════════════════════════════════════════════════════════════
# **WHY THE DRAFT LIFECYCLE IS IN THIS FILE AND NOT IN A SERVICE BESIDE IT.**
# `ledger/0004` refuses an INSERT into `journal_entries` or `journal_lines`
# unless the session GUC `app.ledger_posting` is on, and THIS MODULE is the only
# thing that turns it on. A manual-JE service that opened that window itself
# would be a second write path into the books — precisely what hard rule 5
# forbids and what 0004 exists to make impossible. So the draft primitives live
# here, beside `post()`, sharing one fence, one validator and one audit shape;
# `apps/ledger/manual_je.py` orchestrates them and writes no journal row itself.
#
# **WHY A DRAFT IS A REAL ROW RATHER THAN A PAYLOAD.** B2 Addendum r13 #2 gives
# `journal_entries` a draft state, the ledger field map maps *"JE draft state →
# `journal_entries` draft state"*, and `ledger/0002` was written for exactly
# this: its balance function RETURNS EARLY unless the entry is posted (*"a draft
# may sit unbalanced until it posts"*) and its immutability function lets a
# draft edit and delete freely. The alternative — a separate drafts table — would
# have invented schema the brief does not have and would have needed its own
# copy of every dimension column.
#
# **AND THE UNBALANCED DRAFT IS THE REASON IT MATTERS.** US-LED-011 TC-4 posts a
# draft holding DR 500.00 / CR 480.00 and expects the S57 footer to show the
# 20.00 gap. A draft that could not hold that state could not be edited into it,
# and the "Must balance" footer would have nothing to be wrong about.
@dataclass(frozen=True)
class DraftRequest:
    """The content of one S57 manual journal entry, before it is worth anything.

    Deliberately NOT a `PostingRequest`: a draft has no `posting_key` (there is
    no replay to guard — a human clicked Save), no `posted_at` (it has not
    entered the books) and **no balance requirement**. Those three differences
    are the whole of BR-LED-003's *"drafts freely editable/deletable before
    post; balanced required AT POST"*.
    """

    entry_date: date
    currency: str
    lines: tuple[PostingLine, ...]
    memo: str | None = None
    entry_type: str = models.JE_STANDARD
    source_type: str | None = None
    source_id: Any = None


@dataclass(frozen=True)
class DraftResult:
    """What one draft save left behind, and what it would post if posted now."""

    entry_id: str
    created: bool
    debits: Decimal
    credits: Decimal
    balanced: bool
    line_count: int


def _refuse_unless_draftable(request: DraftRequest) -> tuple[Decimal, Decimal]:
    """Every check `_refuse_unless_postable` makes EXCEPT the balance.

    Same per-line laws, and each for the same reason: a float, a negative, a
    third decimal, an unreadable side, an undimensioned line or another tenant's
    account is as wrong in a draft as in a posting, and refusing it at Save is
    where a human can still fix it. The BALANCE is the one thing a draft is
    allowed to get wrong, because getting it right is what posting means.
    """
    if request.entry_type not in models.JE_TYPES:
        raise PostingError(
            f"journal entry type {request.entry_type!r} is not one of {models.JE_TYPES} "
            "(B2 addendum r13 #2). A typo'd type is an entry no report groups correctly, and "
            "on a DRAFT it is also the field that decides whether BR-LED-005's auto-reversal "
            "will ever fire."
        )
    if not isinstance(request.entry_date, date) or isinstance(request.entry_date, datetime):
        raise PostingError(
            "entry_date must be a date — it is the BOOK date the trial balance groups by, and "
            'the Product Owner ruled on 2026-08-11 that it is asked of the user ("posting and '
            'actual dates can differ; ask actual date to user"). Nothing here reads a clock.'
        )
    if not isinstance(request.currency, str) or len(request.currency) != 3:
        raise PostingError(
            f"currency {request.currency!r} is not a CHAR(3) code (CLAUDE.md rule 2)."
        )
    # `P0.7`, on the DRAFT path too — and it belongs here rather than only at
    # post, because a draft a clerk saves in the wrong currency is a draft they
    # will try to post later and be refused by, after typing the whole entry.
    # Refusing at save is the same rule applied where it costs the least.
    _refuse_unless_the_tenants_currency(request.currency)
    if not request.lines:
        raise PostingError(
            "a journal entry draft with no lines has nothing to save. S57 opens with two empty "
            "GL rows and *+ Add line*; a draft is at least one of them filled in."
        )
    # One validator, reused: `_refuse_unless_postable` is handed a PostingRequest
    # shaped from this draft, and the ONLY difference is that its balance check
    # is not reached — the sums are returned to the caller instead.
    debits = Decimal("0")
    credits = Decimal("0")
    probe = PostingRequest(
        posting_key="draft",  # never written; present so the shared validator passes
        entry_date=request.entry_date,
        posted_at=datetime(1970, 1, 1),  # never written; see above
        currency=request.currency,
        lines=request.lines,
        entry_type=request.entry_type,
    )
    try:
        debits, credits = _refuse_unless_postable(probe)
    except PostingError as exc:
        if "UNBALANCED" not in str(exc):
            raise
        # BR-LED-003: a draft may sit unbalanced. Sum it ourselves and let the
        # caller show the gap (US-LED-011 TC-4's 20.00).
        debits = sum(
            (line.amount for line in request.lines if line.side == models.SIDE_DEBIT),
            Decimal("0"),
        )
        credits = sum(
            (line.amount for line in request.lines if line.side == models.SIDE_CREDIT),
            Decimal("0"),
        )
    return debits, credits


def _write_lines(tenant_id: UUID, entry: models.JournalEntry, lines: tuple[PostingLine, ...]):
    """Insert the lines of `entry`, with BR-LED-001's chain already resolved.

    `_stamped` runs here rather than in each caller so that the draft path
    (`save_draft`) and the posted path (`post`) cannot stamp differently: a
    draft that carried no premises and gained one at post would make US-LED-011
    TC-4's "the draft is what posts" false.
    """
    lines = _stamped(lines)
    models.JournalLine.objects.bulk_create(
        [
            models.JournalLine(
                tenant_id=tenant_id,
                journal_entry=entry,
                ledger_account_id=line.ledger_account_id,
                side=line.side,
                amount=line.amount,
                service_id=line.service_id,
                account_id=line.account_id,
                premises_id=line.premises_id,
                unit_id=line.unit_id,
                source_type=line.source_type,
                source_id=line.source_id,
                tax_authority_id=line.tax_authority_id,
            )
            for line in lines
        ]
    )


def save_draft(
    request: DraftRequest,
    *,
    entry_id: Any = None,
    actor: Any = None,
) -> DraftResult:
    """Create or REPLACE a draft entry and its lines. Nothing enters the books.

    `entry_id` absent → a new draft. `entry_id` present → that draft's lines are
    deleted and rewritten, which is what *"freely editable"* means when the edit
    can add a line, remove a line and change three amounts in one save. A
    posted entry is refused outright: its correction is US-LED-013's reverse +
    repost and never a save.

    Deleting and rewriting the lines is lawful ONLY because the entry is a
    draft — `ledger/0002`'s append-only trigger closes a POSTED entry's lines to
    UPDATE, DELETE *and late INSERT*, and it is that trigger, not this function's
    good intentions, that makes the distinction real.
    """
    tenant_id = _tenant_id()
    debits, credits = _refuse_unless_draftable(request)

    with transaction.atomic():
        existing = None
        if entry_id is not None:
            existing = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
            if existing is None:
                raise PostingError(
                    f"journal entry {entry_id!r} is not one of this tenant's entries "
                    "(US-LED-011 TC-7). Nothing is saved and nothing is reported about whose "
                    "it is."
                )
            if existing.status != models.JE_DRAFT:
                raise PostingError(
                    f"journal entry {entry_id!r} is {existing.status!r}, not a draft. A posted "
                    "entry is IMMUTABLE (hard rule 4 / BR-LED-003) and its only 'edit' is a "
                    "reverse + repost — `apps.ledger.journal.reverse_and_repost`, which posts a "
                    "linked mirror and hands back a prefilled correction."
                )

        _set_write_window(WRITE_WINDOW_OPEN)
        try:
            if existing is None:
                entry = models.JournalEntry.objects.create(
                    tenant_id=tenant_id,
                    entry_date=request.entry_date,
                    type=request.entry_type,
                    status=models.JE_DRAFT,
                    source_type=request.source_type,
                    source_id=request.source_id,
                    memo=request.memo,
                    currency=request.currency,
                )
                created = True
            else:
                entry = existing
                entry.entry_date = request.entry_date
                entry.type = request.entry_type
                entry.memo = request.memo
                entry.currency = request.currency
                entry.save(
                    update_fields=["entry_date", "type", "memo", "currency", "updated_at"]
                )
                entry.lines.all().delete()
                created = False
            _write_lines(tenant_id, entry, request.lines)

            core_audit.money_action(
                actor,
                AUDIT_DRAFT_SAVED if created else AUDIT_DRAFT_UPDATED,
                "journal_entry",
                str(entry.pk),
                after={
                    "entry_date": request.entry_date.isoformat(),
                    "type": request.entry_type,
                    "currency": request.currency,
                    "debits": str(debits),
                    "credits": str(credits),
                    "balanced": debits == credits,
                    "lines": len(request.lines),
                    "job": None if actor is not None else "ledger.posting",
                },
            )
        finally:
            try:
                _set_write_window(WRITE_WINDOW_SHUT)
            except Exception:  # noqa: BLE001 — never masks the real error
                pass

    return DraftResult(
        entry_id=str(entry.pk),
        created=created,
        debits=debits,
        credits=credits,
        balanced=debits == credits,
        line_count=len(request.lines),
    )


def delete_draft(entry_id: Any, *, actor: Any = None) -> None:
    """BR-LED-003 / US-LED-011 TC-6 — *"gone without trace in the books"*.

    A draft never touched the books, so deleting it removes nothing anybody can
    account for; the `journal.draft_deleted` audit row REMAINS, which is what
    TC-6 asks for. A posted entry is refused here and again by `ledger/0002`'s
    trigger, which raises *"is POSTED and cannot be deleted"* from the database
    even if this check were somehow bypassed.
    """
    tenant_id = _tenant_id()
    entry = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
    if entry is None:
        raise PostingError(
            f"journal entry {entry_id!r} is not one of this tenant's entries (US-LED-011 TC-7)."
        )
    if entry.status != models.JE_DRAFT:
        raise PostingError(
            f"journal entry {entry_id!r} is {entry.status!r} and cannot be deleted. Hard rule 4: "
            "a posted entry is a financial record — the correction is a linked reversing entry "
            "(BR-LED-003), never a removal."
        )
    with transaction.atomic():
        core_audit.money_action(
            actor,
            AUDIT_DRAFT_DELETED,
            "journal_entry",
            str(entry.pk),
            before={
                "entry_date": entry.entry_date.isoformat(),
                "type": entry.type,
                "memo": entry.memo,
                "lines": entry.lines.count(),
            },
            after={"deleted": True, "job": None if actor is not None else "ledger.posting"},
        )
        entry.lines.all().delete()
        entry.delete()


def post_draft(
    entry_id: Any,
    *,
    posted_at: datetime,
    posting_key: str,
    number: str | None = None,
    entry_date: date | None = None,
    actor: Any = None,
    audit_context: dict[str, Any] | None = None,
) -> PostingResult:
    """The draft → posted transition. Balance is asserted HERE, at post.

    BR-LED-003 in one call: *"balanced required at post"*. The sums are taken
    from the LINES THAT EXIST, never from what the caller believes them to be —
    a draft edited in another tab is the case that matters, and the entry that
    posts is the entry that is there.

    `number` is BR-LED-021's `JE-` number, stamped HERE because that is the
    ruling (*"stamped when the entry POSTS — a draft has NO number"*). It is a
    parameter rather than an allocation, for the same reason `entry_date` is:
    this service decides nothing, and the allocator belongs to the tenant's
    numbering series (BR-TEN-035), not to the books.

    A second post of the same draft returns the FIRST result with
    `created=False` — a double-submitted form is not an error (US-LED-001 TC-6's
    posture, applied to a human clicking twice).

    **`entry_date` — ADDED 2026-09-02 (DEF-3202), additive and defaulted, and it
    is the ONLY way a draft's book date may move.** A draft can sit for days, and
    the month it was drafted into can close underneath it (BR-LED-006). Its owner
    then has to re-date it to the period BR-TEN-038 forwards to, and re-dating a
    DRAFT is lawful — BR-LED-003 makes drafts freely editable right up to the
    post. It is a parameter here rather than an UPDATE in the caller for the same
    reason every other write in this file is: hard rule 5 puts `journal_entries`
    writes in ONE module, and it costs no extra statement — the date rides on the
    same UPDATE that flips the status. **This service still decides nothing**: it
    writes the date it is handed and refuses one that lands in a closed period.
    """
    tenant_id = _tenant_id()
    key = str(posting_key or "").strip()
    if not key:
        raise PostingError(
            "posting a draft needs a posting_key so a double-submitted form cannot put the same "
            "manual entry in the books twice (CLAUDE.md rule 6). Compose one with "
            "apps.ledger.posting.posting_key()."
        )
    entry = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
    if entry is None:
        raise PostingError(
            f"journal entry {entry_id!r} is not one of this tenant's entries (US-LED-011 TC-7)."
        )
    if entry.status == models.JE_POSTED:
        return _replayed(entry, entry.posting_key or key)
    if not isinstance(posted_at, datetime):
        raise PostingError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043): a resumed batch, "
            "a replay and a re-run must stamp the SAME moment rather than three."
        )
    if entry_date is not None and (
        not isinstance(entry_date, date) or isinstance(entry_date, datetime)
    ):
        raise PostingError(
            "entry_date must be a date — it is the BOOK date the trial balance groups by "
            "(PO ruling 2026-08-11 on OQ-107). Omit it to post the draft on the date it "
            "already carries."
        )
    effective_date = entry.entry_date if entry_date is None else entry_date
    # BR-LED-006 (DEF-3202) — and this is the door `post()`'s guard cannot see.
    # A draft is not money in the books, so saving one into any month is lawful
    # (BR-LED-003, *drafts freely editable*); the books move HERE, and the month
    # can close in between. `manual_je` resolved the date at SAVE and its own
    # docstring claimed it did so "at SAVE as well as at POST" — it did not, and
    # a draft written on the 20th posted straight into a month closed on the 5th.
    _refuse_if_period_closed(effective_date, what=f"draft journal entry {entry_id!r}")

    debits = Decimal("0")
    credits = Decimal("0")
    count = 0
    for side, amount in entry.lines.values_list("side", "amount"):
        if side == models.SIDE_DEBIT:
            debits += amount
        else:
            credits += amount
        count += 1
    if count == 0:
        raise PostingError(
            f"journal entry {entry_id!r} has no lines, so there is nothing to post (B2 §1: "
            "journal_entry 1:N journal_lines (balanced))."
        )
    if debits != credits:
        raise PostingError(
            f"the draft is UNBALANCED — debits {debits} <> credits {credits} (gap "
            f"{abs(debits - credits)}). BR-LED-003: *balanced required at post*. This is the "
            "server half of S57's *Must balance* footer, and US-LED-011 TC-4 requires BOTH — "
            "nothing partial lands, and the draft stays a draft so the gap can be corrected."
        )

    try:
        with transaction.atomic():
            entry.status = models.JE_POSTED
            entry.posted_at = posted_at
            entry.posting_key = key
            entry.number = number
            entry.entry_date = effective_date
            entry.save(
                update_fields=[
                    "status",
                    "posted_at",
                    "posting_key",
                    "number",
                    "entry_date",
                    "updated_at",
                ]
            )
            core_audit.money_action(
                actor,
                AUDIT_POSTED,
                "journal_entry",
                str(entry.pk),
                after={
                    "posting_key": key,
                    "number": number,
                    "entry_date": entry.entry_date.isoformat(),
                    "posted_at": posted_at.isoformat(),
                    "type": entry.type,
                    "currency": entry.currency,
                    "debits": str(debits),
                    "credits": str(credits),
                    "lines": count,
                    "job": None if actor is not None else "ledger.posting",
                    **dict(audit_context or {}),
                },
            )
    except IntegrityError:
        # Two clicks racing on the same key, or a number another transaction
        # took first. Either way one entry exists and ours is not it.
        winner = _existing_entry(tenant_id, key)
        if winner is None:
            raise
        return _replayed(winner, key)

    return PostingResult(
        entry_id=str(entry.pk),
        posting_key=key,
        created=True,
        debits=debits,
        credits=credits,
        line_count=count,
    )


# ── reverse() — a correction is a NEW entry, never an edit ──────────────────
def reverse_entry(
    entry_id: Any,
    *,
    posting_key: str,
    entry_date: date,
    posted_at: datetime,
    memo: str | None = None,
    actor: Any = None,
    audit_context: dict[str, Any] | None = None,
    audit_action: str = AUDIT_REVERSED,
    link_forward: bool = False,
) -> PostingResult:
    """Post the linked MIRROR of a posted entry (US-LED-003, hard rule 4).

    *"Posted journal entries are IMMUTABLE; 'edit/update' = one-click REVERSE +
    REPOST"* (BR-LED-003, PO LF-3). US-LED-003 §5 fixes the mirror's shape in
    signed text — *"`journal_entries` + `journal_lines` (same GLs, sides
    swapped)"* — so that is exactly what this writes: every line of the
    original, same account, same amount, same dimensions, the other side.
    Nothing is netted and nothing is dropped; LE-8's point is that all three
    entries survive forever and the NET effect is right.

    **It reads the original and copies it. It computes nothing.** A mirror
    whose amounts were recalculated could disagree with the entry it claims to
    reverse, which is the one thing a reversal may never do — and because the
    original is immutable, what is copied is what was posted.

    `entry_date` is an INPUT, and deliberately not "the original's date": LE-9
    is the case where July has closed and an August-arriving reversal must land
    in August. **BR-TEN-038's auto-forward is still not performed here** — this
    function names the date it was handed and `post()` writes it. ⚠ **CORRECTED
    2026-09-02 (DEF-3202): the reason given was false.** It read *"there is no
    record anywhere in the schema of which periods are closed"*; `FiscalPeriodClose`
    has existed since US-LED-015 landed. So a July-dated reversal is now
    **REFUSED** rather than written into a closed July — a caller who means LE-9
    passes August, which is what LE-9 says to do, and a caller who genuinely
    wants the forward computed calls `close.resolve_entry_date` first.

    An entry may be reversed ONCE — `uq_journal_entries_reversal` (ledger/0001)
    is the database's half, and a second attempt with a fresh key raises rather
    than quietly double-crediting. A replay with the SAME key is a no-op like
    any other.

    **`audit_context` — ADDED 2026-08-11 by the EP-LED-03/04 reporting lane, and
    the reason is a signed test case rather than a convenience.** US-LED-013
    TC-3: *"The click demands a REASON; audit `journal.reversed` (JE-104→105) +
    `journal.posted` (JE-106) with actor AND REASON."* Before this parameter the
    `journal.reversed` row carried the entry ids, the key, the date and the
    totals and had nowhere to put WHY — so the one field a human reviewing a
    correction reads first was the one field the trail lost. The alternative
    considered and rejected was a second audit row written by the caller under
    its own action code: two rows for one act, and a reader grouping on
    `journal.reversed` would still find no reason on it.

    It is additive and defaulted, so no existing caller changes behaviour. It
    flows to BOTH rows — the mirror's `journal.posted` (through
    `PostingRequest.audit_context`) and the original's `journal.reversed` — so
    the reason is answerable from either end of the pair. BR-AUD-006 still
    applies: money figures, ids and reasons only, never PII.

    **`audit_action` and `link_forward` — ADDED 2026-08-15 by the close-the-books
    lane for BR-LED-005, and both are additive and defaulted.** An ACCRUAL's
    day-1 mirror is the same write with two differences that matter to a reader
    of the books:

      * it is audited as `journal.auto_reversed`, not `journal.reversed` — *"a
        human corrected this"* and *"the schedule fired"* are different facts and
        a month-end reviewer greps for one of them (US-LED-012 TC-1 names the
        code);
      * BR-LED-005 links the pair **BOTH WAYS** and `reversal_of` is only one of
        them. `link_forward=True` writes the ACCRUAL's `auto_reverse_entry`
        pointer at its mirror, which is the single column `ledger/0002`'s
        immutability trigger deliberately leaves writable on a posted entry —
        *"the accrual is long since posted by then, so freezing every column
        would make the ratified rule unimplementable"*. It goes NULL → set once,
        never re-pointed; the filtered UPDATE below makes a replay a no-op rather
        than a second attempt the trigger would refuse.

    The alternative — a separate `post_auto_reversal()` — was rejected because it
    would have had to read the original and swap the sides a SECOND time, and
    two implementations of "the mirror" is exactly the drift a reversal may never
    have.
    """
    extra = dict(audit_context or {})
    tenant_id = _tenant_id()
    original = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
    if original is None:
        raise PostingError(
            f"journal entry {entry_id!r} is not one of this tenant's entries, so there is "
            "nothing to reverse. US-LED-003 TC-7: an entry id from another tenant posts "
            "nothing."
        )
    if original.status != models.JE_POSTED:
        raise PostingError(
            f"journal entry {entry_id!r} is {original.status!r}, not posted. A DRAFT is "
            "edited or deleted directly (BR-LED-003 — drafts are freely editable); a "
            "reversal is the correction path for an entry that has already entered the "
            "books, and mirroring a draft would put an entry in the books to cancel one "
            "that never was."
        )

    mirrored = tuple(
        PostingLine(
            ledger_account_id=line.ledger_account_id,
            side=(models.SIDE_CREDIT if line.side == models.SIDE_DEBIT else models.SIDE_DEBIT),
            amount=line.amount,
            source_type=line.source_type,
            source_id=line.source_id,
            service_id=line.service_id,
            account_id=line.account_id,
            premises_id=line.premises_id,
            unit_id=line.unit_id,
            tax_authority_id=line.tax_authority_id,
        )
        for line in original.lines.all().order_by("created_at", "id")
    )
    if not mirrored:
        raise PostingError(
            f"journal entry {entry_id!r} is posted with no lines, which the balance "
            "trigger should have made impossible. Nothing is reversed; this is a defect "
            "to report, not a state to work around."
        )

    result = post(
        PostingRequest(
            posting_key=posting_key,
            entry_date=entry_date,
            posted_at=posted_at,
            currency=original.currency,
            lines=mirrored,
            source_type=original.source_type,
            source_id=original.source_id,
            memo=memo or f"Reversal of {original.pk}",
            entry_type=models.JE_REVERSING,
            reversal_of_id=original.pk,
            audit_context={"reverses_entry_id": str(original.pk), **extra},
        ),
        actor=actor,
    )
    if result.created:
        if link_forward:
            # BR-LED-005's second link. FILTERED on `auto_reverse_entry__isnull`
            # so a replay writes nothing: the trigger raises if an existing link
            # is re-pointed, and a no-op is the right answer for "already done".
            models.JournalEntry.objects.filter(
                tenant_id=tenant_id, pk=original.pk, auto_reverse_entry__isnull=True
            ).update(auto_reverse_entry_id=result.entry_id)
        # US-LED-003 §5's own audit row, separate from `journal.posted`: "this
        # entry was reversed" and "an entry was posted" are different questions
        # asked by different screens, and S56 renders the linkage both ways.
        core_audit.money_action(
            actor,
            audit_action,
            "journal_entry",
            str(original.pk),
            after={
                "reversed_by_entry_id": result.entry_id,
                "posting_key": result.posting_key,
                "entry_date": entry_date.isoformat(),
                "debits": str(result.debits),
                "credits": str(result.credits),
                "job": None if actor is not None else "ledger.posting",
                **extra,
            },
        )
    return result


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sources this service implements, in order: 04-docs/02-decisions/02-database-design-brief.md — §2 journal DDL + §3 balance/append-only triggers + Addendum r13 #8 "posting-service mechanics = Eng-Lead 🔒" + DB-12 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md US-LED-001 (the 17-row DR/CR contract table, TC-1..TC-7) + US-LED-003 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-001/003/007/015 · 04-docs/05-modules/09-ledger/03-field-map.md · 04-docs/02-decisions/05-golden-tests.md GT-16 ❄️ · 12-governance/02-decision-log.md 2026-08-11 "posting and actual dates can differ; ask actual date to user" (OQ-107))
# generated: 2026-08-11 by Eng-Lead (W5 ledger posting-service lane) · AMENDED 2026-08-11 by Eng-Lead (EP-LED-03/04 reporting lane — ONE additive, defaulted parameter: `reverse_entry(audit_context=…)`, flowed into BOTH the mirror's `journal.posted` payload and the original's `journal.reversed` payload. Required by US-LED-013 TC-3, which demands a REASON on the reverse+repost trail and had nowhere to put one. No existing caller changes behaviour; no money path, key shape, date rule or refusal is touched) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: docstring corrections only — three stale claims that OQ-116 blocks a taxed bill) · AMENDED 2026-08-11 by Eng-Lead (stage-7 posting-handoff lane — docstring/trailer corrections only, NO code change: this service now has its first caller in the product, so every sentence claiming nothing calls it was rewritten)
# amended:   2026-08-15 by the close-the-books lane — 🔒 HUMAN-OWNED FILE CHANGED, stated here
#            so a reader does not have to diff. THREE additions, no existing behaviour altered:
#            (1) **BR-LED-025 IS NOW BUILT** — `_carries_more_than_two_decimals` refuses a
#            posting carrying a third decimal, naming the amount and the line, and the
#            module docstring's claim that the rule was *"unsigned … raised as OQ-126"* is
#            CORRECTED: OQ-126 is CLOSED (PO 2026-08-12, *"Refuse and make the caller
#            round"*). Proved RED first — with the check disabled a 500.005 entry POSTED.
#            (2) the **DRAFT PRIMITIVES** `save_draft` / `delete_draft` / `post_draft`, which
#            live here and not beside US-LED-011 because ledger/0004's sole-writer trigger
#            makes this module the only lawful INSERT path — a manual-JE service opening the
#            write window itself would be the second write path hard rule 5 forbids.
#            `post_draft` also stamps BR-LED-021's `JE-` number, which is a PARAMETER: this
#            service decides nothing, and the allocator belongs to BR-TEN-035.
#            (3) `reverse_entry` gains TWO additive, defaulted parameters — `audit_action`
#            (US-LED-012 TC-1's `journal.auto_reversed`) and `link_forward` (BR-LED-005's
#            *linked both ways*, writing the accrual's one lawful post-post column). No
#            existing caller changes behaviour; no money path, key shape or date rule moved.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S56/S57 journal endpoints are EP-LED-03/04) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — the unbalanced
#         entry, the double post, the UPDATE on a posted entry, the sole-writer
#         bypass and RLS were each seen failing before any green was trusted;
#         every failure is quoted verbatim in the human-review ledger row
# exceptions: ⚠ WHO CALLS THIS — REWRITTEN 2026-08-11 (stage-7 lane). This entry
#         read "NOTHING CALLS THIS YET (hard-won law 2) — billing's stage 7 is
#         not emitted, payments has no tables and the cutover importer has no
#         `account_opening_buckets`". **Billing's stage 7 IS emitted now**:
#         `apps/billing/issue.issue_invoice` calls
#         `apps/billing/posting_seam.post_bill_issue` inside the issue
#         transaction, which resolves `post` / `posting_key` / the two dataclasses
#         / `PostingError` from this module BY NAME and hands over DR AR
#         `invoices.total` against one CR bucket per stamped GL account
#         (US-BIL-005 §7). **Payments and the cutover importer still call
#         nothing**, so the payment, NSF, refund, write-off, bank-rec and opening
#         rows of the contract table remain exercised only by this file's own
#         tests — and GT-16's opening entry is still driven end to end by
#         tests/golden/test_gt16_opening_journal_entry.py rather than by an
#         importer · `posting_key` and its unique index
#         are an EXTENSION beyond B2 §2 (which gives journal_entries no unique
#         key, and DB-12 does not list the journal): the RULE is signed twice
#         (US-LED-001 TC-6, GT-16 ❄️), the MECHANICS are delegated by r13 #8 —
#         REPORTED · the three-part key shape and GT-16's `cutover:<batch>`
#         event are this lane's composition, not a ruling; the importer that
#         owns it (US-CUS-022) is unbuilt · US-LED-002's premises/unit
#         RESOLUTION is NOT done — no published customers account→unit or
#         metering unit→premises read exists — so those dimensions are carried,
#         not resolved, and US-LED-002 TC-5's tax-line refusal is named rather
#         than guessed [CORRECTED 2026-08-11: this said "(it needs OQ-116)" and
#         OQ-116 is CLOSED — an invoice line names its tax now (BR-BIL-069); the
#         refusal waits on the stage-7 HANDOFF, which nothing emits] ·
#         BR-TEN-038's closed-period
#         auto-forward is not performed HERE [CORRECTED 2026-09-02, DEF-3202:
#         this read "is NOT implemented: no fiscal-period record exists in the
#         schema at all, so the caller's date is written verbatim". That premise
#         died when US-LED-015 landed `FiscalPeriodClose`, and the sentence then
#         described a guarantee nobody kept — an entry dated into a closed month
#         POSTED. A closed-period date is REFUSED here now; the FORWARD stays
#         `close.resolve_entry_date`'s, called by the caller, because the caller
#         is the only layer that knows whether moving a date is right] · amounts
#         are written EXACTLY as handed over —
#         US-LED-001 says "posting asserts, never recomputes", so there is no
#         rounding here and no 2dp refusal either; whether a >2dp amount should
#         be refused is a rule nobody has signed, so it was RAISED as OQ-126
#         rather than chosen. It is not stubbed: both answers write the same
#         books for every 2dp figure in B5, so nothing is blocked today and a
#         NotImplementedError would refuse lawful postings to mark an open
#         question
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
