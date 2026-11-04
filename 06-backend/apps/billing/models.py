# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (S31 run wizard — bill_runs + the exclusions queue) ·
#           US-BIL-005 (issue: number, status, issued_at, template pin) ·
#           US-BIL-007 (S30 bill detail — the line table)
#           Screens: S30 · S31 · S31.2 · S31.3
#           Three further stories are deliberately NOT cited here — see the
#           docstring, which is where G10 does not read a name as a claim.
# Rules:    BR-BIL-004 (issued invoices are immutable; corrections are new
#           rows) · BR-BIL-005 (a run is idempotent) · BR-BIL-010 (GL stamped
#           at issue and frozen) · BR-BIL-015/023 (catch-up sub-runs; every
#           exclusion recorded with who/when/why) · BR-BIL-018/019 (bill types)
#           · BR-BIL-022 (number source/format) · BR-BIL-063 (allocated at
#           DRAFT creation — PO 2026-08-11) · BR-BIL-024
#           (due date = bill date + the cycle's due-days; the DUE date is
#           always derived, never typed — what a clerk types is the BILL date,
#           BR-BIL-070) · BR-BIL-070 (`bill_runs.bill_date` — the clerk's typed
#           date is stored and used; PO 2026-08-11, OQ-122 option A) ·
#           BR-TEN-043 (event-time law: a typed date is an argument, a clock is
#           never one) · BR-BIL-026 (template pinned at
#           issue) · BR-CUS-040 (a reprint renders the issued document, never
#           recomputes) · CLAUDE.md rule 2 (money NUMERIC(18,6) + CHAR(3)) ·
#           rule 3 (consumption carries its unit) · rule 4 (financial
#           immutability)
# Tests:    06-backend/tests/test_w3_billing_models.py
#           AMENDED 2026-08-11 (budget-billing lane): `account_budget_status`
#           + `account_budget_events` (Addendum r10 #5 · r12 #14 D-5), Rules +=
#           BR-BIL-017. The three budget story IDs are NOT added to the Story
#           line: this ships the TABLES, and US-BIL-018/019/020's test cases
#           live beside apps/billing/budget.py and budget_service.py, which is
#           where the work is — the same reasoning the docstring gives below
#           for the three run stories, and the same reasoning that made G10
#           catch this file over-claiming once already.
#           AMENDED 2026-08-11 (tenant custom-fields lane): US-BIL-028 —
#           `invoices.custom_snapshot` (B2 r17.3), Rules += BR-BIL-030's
#           custom half and BR-TEN-048. The story ID is NOT added to the
#           Story line above: this ships the COLUMN, and US-BIL-028's test
#           cases live in tests/test_us_bil_028_custom_snapshot.py beside
#           apps/billing/custom_snapshot.py, which is where the work is.
# Impacts:  apps/billing/services.py · apps/rating (engine output lands here) ·
#           apps/payments (allocation writes against these invoices) ·
#           apps/ledger W5 (gl_account_id resolves once that module exists)
# ───────────────────────────────────────────────────────
"""billing models — the invoice core, from B2 §2 as redlined by Addendum r10.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path
and these tables carry money. AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHICH STORIES THIS HEADER CITES, AND WHY THREE ARE MISSING. The draft-invoice
service (US-BIL-004), the catch-up sub-run flow (US-BIL-006) and the bills list
(US-BIL-025) all need these tables, and none of them is shipped here — this
slice ships SCHEMA. G10 reads a Trace-header US-ID as "this file ships that
story's test cases", so citing them would be a completion claim for work that
does not exist. It caught exactly that on the commit that made it, and then
caught the FIX too, because the first correction named the three IDs inside the
Trace block while explaining that it wasn't citing them. `late_fee.py` records
having made the identical mistake. The names live down here instead, where the
gate reads prose rather than a claim.

Schema law implemented here (signed, never invented):
- **B2 §2 billing** — `bill_runs` · `invoices` · `invoice_lines` ·
  `adjustments` · `credit_notes`, column for column.
- **Addendum r10 (PO-approved 2026-08-08)** — #1 `invoice_lines.gl_account_id`
  stamped at finalization · #3 `invoices.template_id` / `.template_version`
  pinned at issue · #7 `bill_runs` lifecycle + `parent_run_id` + scope +
  `bill_run_exclusions` · #12 `invoices.bill_type`.
- **B2 post-design confirmations (finance 2026-08-07)** — `invoice_lines.
  taxable`, the flag B4.2's tax base reads by KIND.
- **PO ruling 2026-08-11 (this session)** — `invoices.issued_snapshot`, below.

WHAT THIS SLICE IS NOT. r10 has fifteen items; this builds the invoice core and
stops. Templates (#4), budget billing (#5), the corrections workflow (#9),
balance transfer (#10), write-off (#11) and the outbound delivery queue (#8,
platform-wide per r12 #16) are their own waves. `template_id` and
`template_version` exist as plain columns here because r10 #3 pins them at
issue and an invoice issued before the template tables land must still record
WHICH template it was rendered with — a pin that waits for its table is a pin
that is missing exactly when it is needed.

────────────────────────────────────────────────────────────────────────────
THE SNAPSHOT — `invoices.issued_snapshot`, and why a live join is not enough
────────────────────────────────────────────────────────────────────────────
The PO ruled it in this session, in these words:

    "you have to keep lock data for that bill and save the instance"

A bill reprinted in December must show the customer name, the service address
and the plan **as they were in July**. Sarah marries and changes her name;
the apartment is renumbered; the plan is edited. Every one of those is a
legitimate change to live data, and every one of them silently rewrites
history if the reprint re-joins today's rows. The document a customer disputes
must be the document they received.

So at issue the invoice keeps its own copy of everything the document prints,
and `BR-CUS-040`'s "a reprint never recomputes" becomes structurally true
rather than a rule someone has to remember. Nothing reads through to
`accounts`, `units` or `rate_plans` to render an issued bill.

It is deliberately a JSON payload and not a set of columns: what a bill prints
is template-shaped and tenant-specific, and the alternative — a column per
printed field — puts a migration between the tenant and their own bill layout.

────────────────────────────────────────────────────────────────────────────
IMMUTABILITY (hard rule 4) is NOT enforced by these classes
────────────────────────────────────────────────────────────────────────────
A Django model cannot stop a `.save()`. The guarantee lives in the database
triggers `migrations/0002` installs, and in the service layer. Saying so here
because a model docstring claiming immutability that the schema did not have
is precisely the defect that produced hard-won law 1.
"""

from django.db import models
from django.db.models import Q

from apps.billing import budget
from core.dbfields import uuid7_pk

#: B2 §1 `invoice_status` — the five values, verbatim. Not a lookup table:
#: BR-TEN-036 turned the *tenant-extensible* enums into lookups, and this is
#: not one of them — a tenant cannot invent a sixth invoice state, because the
#: ledger and the immutability triggers are written against these five.
INVOICE_DRAFT = "draft"
INVOICE_ISSUED = "issued"
INVOICE_PAID = "paid"
INVOICE_VOID = "void"
INVOICE_CORRECTED = "corrected"
INVOICE_STATUSES = (
    INVOICE_DRAFT,
    INVOICE_ISSUED,
    INVOICE_PAID,
    INVOICE_VOID,
    INVOICE_CORRECTED,
)
#: The states past which nothing may be edited (BR-BIL-004). `draft` is the
#: only writable one; `corrected` and `void` are terminal readings of a bill
#: that WAS issued, so they are locked too — a correction is a new row.
INVOICE_LOCKED_STATUSES = (
    INVOICE_ISSUED,
    INVOICE_PAID,
    INVOICE_VOID,
    INVOICE_CORRECTED,
)

#: r10 #12 — BR-BIL-018/019.
#:
#: ⚠ **`fee` JOINED THIS TUPLE ON 2026-08-27 (DEF-708).** PO ruling, verbatim:
#: *"A customer can be reconnected $75 short - Make the fee a real charge — It
#: becomes a line that can be billed and paid, so the gate has something to
#: check."* Until then this vocabulary had no type for a bill whose whole
#: content is a tenant charge code, so the **$75.00** reconnection fee
#: BR-CUS-104 makes owed at the cut was recorded on the disconnect case and
#: **posted nowhere** — `mark_reconnecting` reads AR and admitted `A-11340` at
#: **$8,240.00** where **$8,315.00** was owed.
#:
#: A `fee` bill carries charge-code lines and nothing else: no plan, no tariff,
#: no usage, no proration and no tax pass (see `apps/billing/fee_bill.py`). It
#: is typed for what it is rather than as `cycle`, because a document kept for
#: seven years must not say it billed a period it never billed — the same
#: argument `one_time.KIND_INTERIM` makes in the other direction.
BILL_TYPES = ("cycle", "first", "final", "rebill", "backbill", "penalty", "fee")

#: **WHAT AN INVOICE LINE IS**, and until `CR-110-BRC04` phase 2 this
#: vocabulary existed ONLY as the comment on `InvoiceLine.kind` — six words
#: after a `#`, which nothing can read and nothing can check.
#:
#: ⚠ **A COMMENT IS NOT A VOCABULARY (hard-won law 1).** The partner
#: reference endpoint has to publish every code this product can put on a
#: payload *with its meaning*, and a list a lane retypes from a comment is a
#: seventh place for the set to drift. It is a tuple now, the column's comment
#: points at it, and `apps/integrations/reference.py` reads THIS — so a
#: seventh kind appears on a partner's reference pull with no endpoint change,
#: and fails a test if nobody wrote its meaning.
#:
#: The order is the one the column's comment carried, which is the order a
#: bill prints in: what the plan charges, what was used, what was added, what
#: the state takes, what was corrected, and the floor a tariff guarantees.
#: Not a DB CHECK and not a lookup — `B4`'s tax base and
#: `documents.SERVICE_LINE_KINDS` are written against these six, so a tenant
#: cannot invent a seventh (the same argument `INVOICE_STATUSES` makes).
LINE_KINDS = ("usage", "base", "fee", "tax", "adjustment", "minimum")

#: r10 #7 — the formalized run lifecycle.
RUN_STATUSES = ("draft", "previewing", "issuing", "completed", "failed", "cancelled")


class BillRun(models.Model):
    """One billing run over one cycle and period (B2 §2; r10 #7).

    `idempotency_key` is the BR-BIL-005 guarantee and is UNIQUE per tenant: a
    re-submitted run is refused with who/when/link rather than producing a
    second set of bills. The key's MECHANICS are Eng-Lead-owned (r10 #15); the
    column is the part that is schema.

    `bill_date` is the CLERK'S TYPED DATE and is new in `0011` — PO ruling
    2026-08-11 closing OQ-122, option A, verbatim *"A Store what they type and
    use it"* (BR-BIL-070). Before it, S31 step 1 asked for a bill date, the
    wizard POSTed it, and the server had nowhere to put it: the run priced at
    the CYCLE's date and the typed value vanished with no warning. Worked case
    the PO was shown: cycle 08-A dated 1 Aug, clerk types 3 Aug — the bill now
    prices at 3 Aug and falls due 24 Aug, where it used to price at 1 Aug and
    fall due 22 Aug.

    NULLABLE ON PURPOSE, and the null is a fact rather than a gap: it means
    *nobody typed one on this run*, and the cycle's own `bill_date` is what the
    run then uses (`runs.effective_bill_date`). A NOT NULL column would have
    needed a value invented for every run created before this migration, and
    the only value available to invent is a clock — which BR-TEN-043 and gate
    G6 both forbid in this path.

    ── `cycle` IS NULLABLE SINCE 0021, AND `scope_account` IS WHY ─────────────
    A ONE-TIME BILL HAS NO CYCLE. US-BIL-010..014 (first · final · ad-hoc ·
    back-bill · penalty) each bill ONE account over a window the clerk names,
    and `apps/billing/single.py` reported the consequence in its own trailer
    before this column moved: *"`bill_runs.cycle_id` is NOT NULL, so an ad-hoc
    run has no lawful row yet"*. Every one of the five engines takes a
    `bill_run` — stage 6 keys draft replacement on `(tenant, account, bill_run)`
    — so with no lawful row the five engines had no door at all.

    Pointing an ad-hoc run at *some* cycle was the alternative and it is worse
    in two specific ways: BR-BIL-005 keys a run on `(tenant, cycle, period)`, so
    a one-off bill for July would collide with July's real cycle run and be
    refused as a duplicate of it; and `bill_runs.cycle_id` is the column
    `selectors.invoice_list_queryset` filters an S30 cycle view on, so an ad-hoc
    bill would appear inside a cycle it was never part of.

    **NEITHER-NULL IS REFUSED BY THE DATABASE** (`ck_bill_runs_has_a_scope`): a
    run names a CYCLE or an ACCOUNT, always at least one of them. A run scoped
    to neither would bill an undefined population, and the constraint lives in
    Postgres rather than in a service because `runs.py` is not the only writer
    this table will ever have.

    `scope_account` is r10 #7's *"scope"* at single-account granularity — the
    half of that item `scope_services` does not carry. It records WHO the run
    was for, which matters most when a run produces no invoice at all: an
    inference from the bill has nothing to read in that case.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    cycle = models.ForeignKey(  # ⚠ cross-module FK → metering (reviewed set, B2 §2)
        "metering.Cycle",
        on_delete=models.PROTECT,
        db_column="cycle_id",
        # NULL on a one-time run (US-BIL-010..014). See the class docstring: a
        # first/final/interim/back-bill/penalty bill belongs to no cycle, and
        # `ck_bill_runs_has_a_scope` below is what stops the null meaning
        # "scoped to nothing".
        null=True,
        blank=True,
    )
    #: r10 #7's single-account SCOPE. Set on a one-time run and NULL on a cycle
    #: run — the two are different populations, not two spellings of one.
    #: ⚠ cross-module FK → customers (reviewed set, B2 §2), the same edge
    #: `bill_run_exclusions.account_id` already crosses.
    scope_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="one_time_bill_runs",
        db_column="scope_account_id",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    #: BR-BIL-070 (PO 2026-08-11, OQ-122 option A) — the bill date the clerk
    #: typed on S31 step 1. The run's SERVICE date (BR-RAT-007's pricing pivot)
    #: and BR-BIL-024's due date both derive from it when it is present. NULL =
    #: nothing was typed, and the cycle's date is used instead.
    bill_date = models.DateField(null=True, blank=True)
    #: CR-029 D9 (PO ruling 2026-08-23), verbatim: *"when we configure Cycle we
    #: are provideing default values; mostly it wil remain as it is but user can
    #: over ride them during billing"* — the OTHER half of the override
    #: `bill_date` above has carried since BR-BIL-070. The cycle keeps
    #: `cycles.due_days` as its DEFAULT and this is the run's override of it;
    #: `runs.effective_due_days` is the one place that precedence lives.
    #:
    #: ⚠ **D9 SUPERSEDES THE UPGRADED PROTOTYPE**, whose SET-07.3 / SET-07.4 /
    #: SET-07D footnotes read *"Bill and due dates belong to the run, not the
    #: cycle"*. They do not: the cycle provides them, the run may override.
    #:
    #: NULLABLE, AND THE NULL IS THE FACT: *nobody overrode the terms on this
    #: run* — which is true of every run created before this column, so no
    #: already-issued due date moves (CLAUDE.md rule 4). **ZERO IS NOT NULL**:
    #: due on the bill date is a lawful arrangement (BR-MET-009, `due_days ≥ 0`),
    #: so every read of this column tests `is None` and never truthiness.
    due_days = models.IntegerField(null=True, blank=True)
    #: OQ-342 (PO ruling 2026-08-23), verbatim: *"A: a real series (RUN-0001,
    #: like RT-001)"* — the run's own number, allocated from the `bill_run`
    #: series in `core.numbering.SERIES_CATALOG` at creation, in the run's own
    #: transaction (BR-TEN-035's allocation law).
    #:
    #: **WHY IT EXISTS.** The PO's SET-07D screenshot draws a Run column reading
    #: `RUN-0814` and the product could not produce one, so the runs list served
    #: null; a run could only be identified by its period, and two runs over one
    #: period — a re-run, a correction — were indistinguishable to anyone
    #: quoting them.
    #:
    #: **NULLABLE, AND THE NULL IS A FACT: this run predates the series.** The
    #: ruling is explicit that existing runs are NOT retro-numbered (*"a number
    #: that appears on a bill already sent is a different question"*), and
    #: CLAUDE.md rule 4 agrees. The uniqueness below is therefore PARTIAL.
    #:
    #: ⚠ **NOT PART OF THE IDEMPOTENCY KEY.** BR-BIL-005 makes a run unique on
    #: (tenant · cycle · period); adding the number would let the same
    #: cycle-period be billed twice by taking a fresh one — the identical
    #: reasoning that keeps `bill_date` and `due_days` out of the key.
    run_no = models.TextField(null=True, blank=True)
    status = models.TextField(default="draft")  # RUN_STATUSES (r10 #7)
    bill_type = models.TextField(default="cycle")  # BILL_TYPES (r10 #12)
    idempotency_key = models.TextField()  # BR-BIL-005 — unique per tenant
    # r10 #7 catch-up sub-runs: a child run re-bills a SUBSET of its parent's
    # held accounts, in the parent's period. Self-FK rather than a flag so the
    # lineage is queryable rather than reconstructed.
    parent_run = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, db_column="parent_run_id"
    )
    #: The services the run was scoped to (r10 #7). An UNCHECKED service is an
    #: explicit recorded choice, never a silent skip — US-BIL-001 §5 — so the
    #: scope is stored even when it is "all of them".
    scope_services = models.JSONField(null=True, blank=True)
    #: CR-051 task 9 — WHAT THE LAST FINDINGS PASS COUNTED, and nothing else.
    #:
    #: ⚠ **IT IS NOT A CACHE OF THE FINDINGS, AND THE DIFFERENCE IS THE WHOLE
    #: POINT.** `selectors.prepared_for` records, deliberately, that a prepare
    #: pass is *"recomputed on every call and cached nowhere"* — a clerk who
    #: fixes a plan and reloads must see the fix, and a cached case list would
    #: show them the world as it was when they opened the wizard. That stands:
    #: `GET /billing/runs/{id}/findings` still recomputes, unchanged.
    #:
    #: What lands here is the COUNTS the background findings job computed, with
    #: the job id that computed them, so a clerk who left the screen can be told
    #: *"the pass finished; it found 1,124 accounts, 6 blocked, 18 decisions"*
    #: without a second five-minute pass. Whether the case LISTS may be
    #: snapshotted too is `OQ-843` and is deliberately not decided here.
    findings_summary = models.JSONField(null=True, blank=True)
    #: ── `DEF-BIL-5255` · THE RUN'S STANDING ANSWERS (BR-BIL-1040) ──────────
    #: Screen 16's `DEFAULTS` group — *"the single biggest error-reducer in this
    #: redraw"* — where a clerk answers three recurring cases ONCE for the whole
    #: run instead of hundreds of times per account: *when there is no reading*,
    #: *when a bill looks unusually large*, *unusual days*.
    #:
    #: `{case_kind: choice}`, and BOTH halves of every pair are
    #: `apps.billing.decisions`' own vocabulary — `CHOICES_BY_CASE`. **There is
    #: deliberately no column per case and no CHECK listing the words**: the
    #: case list has grown twice this month (CR-038 W8 added seven, `DEF-BIL-5270`
    #: added `billing_continuity` on 2026-09-14), and a constraint spelling the
    #: choices out would be a SECOND copy of a vocabulary that already has one
    #: home — which `settings_families.py` records as the mistake that makes a
    #: tenant's screen and the engine's guard disagree in silence. `create_run`
    #: validates against `CHOICES_BY_CASE` and refuses an unknown pair.
    #:
    #: ⚠ **A DEFAULT IS NOT A DECISION, AND THE DISTINCTION IS WHAT KEEPS
    #: BR-BIL-015 INTACT.** The PO reaffirmed the no-pre-committed-default rule
    #: on 2026-08-26, verbatim: *"keep the rule — speed comes from the bulk
    #: button, not from decisions nobody made; an auditor asking 'who chose to
    #: estimate M-4412?' gets a name"*. This column is that name: the run
    #: carries `run_by`, `created_at` and an `audit_log` row naming the clerk who
    #: set these, so the auditor's question is answered by the RUN rather than
    #: unanswerable. Nothing here writes a `bill_run_decisions` row, and the
    #: per-account record stays exactly as append-only as it was.
    #:
    #: **NULLABLE, AND THE NULL IS A FACT: this run predates the group** — the
    #: same shape `bill_date` and `due_days` already carry, so no already-issued
    #: bill can move (CLAUDE.md rule 4). Going forward `create_run` always
    #: writes a COMPLETE map, resolved from the caller's choice or, where they
    #: named none, the tenant's own setting — never a literal (PO 2026-09-14,
    #: *"no hardcoding"*). Storing the RESOLVED value rather than reading the
    #: setting later is deliberate: a tenant who edits the setting between Scope
    #: and Check must not silently change a run already in flight, which is the
    #: same hazard BR-BIL-026 freezes the template against.
    case_defaults = models.JSONField(null=True, blank=True)
    #: ── 🔒 `DEF-BIL-8696` · SIGN OFF'S WHOLE-RUN SUMMARY, SAVED ─────────────
    #: `apps/billing/signoff.build_sign_off_summary`'s answer, saved with the
    #: KEY of every row it was read from (`signoff.inputs_key`). Served only
    #: while the key still matches; the first read after anything it was built
    #: from is written — a re-Calculate, a decision, a payment, a check row —
    #: builds it afresh. Written at the end of every Calculate, so Sign off
    #: opens on it (OQ-843 option C's shape: saved, and rebuilt the moment what
    #: it depends on changes). A copy of a read, never a record: nothing reads
    #: it but Sign off, and NULL means *build it now*.
    sign_off_snapshot = models.JSONField(null=True, blank=True)
    sign_off_snapshot_key = models.TextField(null=True, blank=True)
    #: ── `DEF-BIL-5255` · `Label this run` (screen 16 ④) ────────────────────
    #: The clerk's own name for this run — drawn as `September, after the water
    #: rate change`, and read back in screen 16's `ALREADY RUN FOR THIS CYCLE`
    #: table, whose `LABEL` column had nothing to render.
    #:
    #: It is NOT `run_no` and not a status. `run_no` (`RUN-0002`) is the series
    #: number a customer or an auditor quotes; this is the sentence that tells
    #: the clerk which of two runs over one period is which — the question
    #: `DEF-171` and `DEF-602` both end at, where every finished run reads
    #: *Draft* for ever and two runs over one period are indistinguishable to
    #: anyone quoting them. Free text, never parsed, never on a customer's bill.
    #:
    #: NULLABLE: nobody typed one. Not unique — two runs may honestly carry the
    #: same words, and a uniqueness rule on a human's note would refuse a run
    #: for a reason that is not about billing.
    label = models.TextField(null=True, blank=True)
    #: ── `CR-105-BRC03` · THE TEMPLATE DECIDED AT STEP 1 (BR-BIL-1041) ──────
    #: PO ruling 2026-09-14, verbatim: *"in this step 1 scope - you will ahve to
    #: also decide on billing template"*.
    #:
    #: ⚠ **DECIDING IS NOT STAMPING, AND THIS COLUMN IS THE DECIDING HALF.**
    #: `assemble_document` still stamps the template AND ITS VERSION onto each
    #: invoice at ISSUE and freezes it there (BR-BIL-026) — so a template edited
    #: between Scope and Send cannot change a bill a clerk already approved.
    #: This column records WHICH TEMPLATE the clerk chose; `issue` resolves
    #: WHICH VERSION of it was published at the moment of issue. **The freeze
    #: does not move**, and a version number is deliberately NOT stored here: a
    #: version pinned at Scope would be stale by Send on any tenant that
    #: publishes in between.
    #:
    #: **WHY IT MOVED FORWARD AT ALL**, and the argument is a field that already
    #: exists: `issue.IssuedRun.template_problems` counts *"distinct reasons a
    #: bill could not resolve its own template, with the number of bills each
    #: affected"*. A bill CAN fail to find one — and today that is discovered at
    #: issue, after Scope, after Check, after the clerk signed off. `create_run`
    #: refuses a template that does not exist in this tenant or has no PUBLISHED
    #: version, so the question is answerable at step 1.
    #:
    #: **NULL IS THE ORDINARY CASE AND NOT A GAP:** nobody pinned one, and
    #: BR-BIL-025's per-account chain — account override → category default →
    #: tenant fallback — runs exactly as it does today. A non-null value is the
    #: EXPLICIT pin `issue_run` already understands (`template_pin_explicit`),
    #: which governs the whole pass because a clerk typed it.
    #:
    #: ⚠ cross-module FK? **No** — `bill_templates` is billing's own table
    #: (`template_models.BillTemplate`, migration 0018), so this edge crosses
    #: nothing.
    template = models.ForeignKey(
        "billing.BillTemplate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pinned_bill_runs",
        db_column="template_id",
    )
    run_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="run_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_runs"
        indexes = [
            models.Index(fields=["tenant", "cycle", "period_start"], name="ix_bill_runs_period"),
            models.Index(fields=["tenant", "status"], name="ix_bill_runs_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"], name="uq_bill_runs_idempotency"
            ),
            # OQ-342 — a run number is unique per tenant, and PARTIAL because
            # every run created before the series carries NULL and those must
            # coexist. `import_runs` (metering 0014) took the identical shape.
            models.UniqueConstraint(
                fields=["tenant", "run_no"],
                condition=Q(run_no__isnull=False),
                name="uq_bill_runs_tenant_run_no",
            ),
            # A run is scoped to a CYCLE (the ordinary batch) or to ONE ACCOUNT
            # (US-BIL-010..014's one-time bills). Never to neither — a run with
            # no scope names no population, and the bills it produced could not
            # afterwards be explained by the row that produced them.
            #
            # ⚠ **NOT `XOR`, deliberately.** Both-set stays legal because a
            # catch-up sub-run (r10 #7 / BR-BIL-015) is scoped to its parent's
            # CYCLE *and* to the held accounts it re-bills, and forbidding that
            # shape here would rule on US-BIL-006's future with no story asking.
            # What the constraint forbids is the one case that is certainly
            # wrong.
            models.CheckConstraint(
                condition=Q(cycle__isnull=False) | Q(scope_account__isnull=False),
                name="ck_bill_runs_has_a_scope",
            ),
        ]


class BillRunExclusion(models.Model):
    """An account the run did NOT bill, and why — the pending-billing queue.

    r10 #7 (BR-BIL-015/023), and the PO confirmed the product behaviour in this
    session: *"anything excluded from a run drops into a 'pending billing'
    queue — Yes."*

    This is the difference between a run that billed 480 of 500 accounts and a
    run that billed 480 accounts. Without a row per exclusion, the twenty are
    invisible: nobody is told, nothing chases them, and they surface as a
    customer asking why they got no bill. Every exclusion therefore carries its
    reason, its actor and its time, and the queue IS this table filtered to
    exclusions with no later successful bill.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(BillRun, on_delete=models.PROTECT, db_column="bill_run_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    reason_code = models.TextField()  # reference data (r10 #13), tenant-extensible
    detail = models.TextField(null=True, blank=True)
    excluded_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="excluded_by"
    )
    #: Set when a later run (usually a catch-up sub-run) bills this account for
    #: the same period. NULL means still pending — which is what makes the
    #: queue a queue rather than a log.
    resolved_by_run = models.ForeignKey(
        BillRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_exclusions",
        db_column="resolved_by_run_id",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    #: BR-BIL-1054 *Leave for next cycle* (billing/0036): the row stays open and
    #: the first LATER run that bills the account closes it (`pending.
    #: resolve_for_run`) — that run bills from the last billed read, BR-BIL-1039.
    next_cycle_at = models.DateTimeField(null=True, blank=True)
    next_cycle_by_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_run_exclusions"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_bill_excl_account"),
            # The pending queue itself: unresolved rows, newest first.
            models.Index(
                fields=["tenant", "-created_at"],
                condition=Q(resolved_at__isnull=True),
                name="ix_bill_excl_pending",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bill_run", "account"], name="uq_bill_run_exclusions_once"
            ),
        ]


#: `bill_run_breaks.resolution` — NULL while the break is OUTSTANDING, and one
#: of these once it is not. BR-BIL-053 gives a break exactly two ways out and
#: names a third state in its own last clause (*"the run cannot enter phase 4
#: with an unresolved break row"*), so "outstanding" is the rule's word and not
#: an invented one.
BREAK_RESOLUTION_DRAFTED = "drafted"  # a later calculate pass drafted this account
#: ⚠ **BR-BIL-053 GIVES A BREAK TWO WAYS OUT AND THIS TABLE COULD RECORD ONLY
#: ONE (CR-051 task 6, 2026-08-31).** The rule's own words are *"allow user to
#: retry immediately by fixing the issue"* and, failing that, the account waits
#: for the catch-up sub-run. `drafted` above is the FIRST door. The second had
#: no value at all, so an account a clerk deliberately held — through a phase-3
#: mark-for-later, or through a holding DECISION, which is the live path
#: (`decisions.apply_decisions` → `runs.mark_for_later`) — left the run and its
#: break row stayed OUTSTANDING for ever. The clerk's work list then showed
#: rows for accounts already dealt with, which is the one thing a work list may
#: not do, and BR-BIL-053's last clause (*"the run cannot enter phase 4 with an
#: unresolved break row"*) would refuse a run that was ready.
BREAK_RESOLUTION_HELD = "held"  # the account left this run for the catch-up queue
#: DEF-BIL-8421 (clerk check F3, 2026-09-30) — a bill that broke at SEND and
#: went out on a later *Retry failed*. A third way out, and a different fact
#: from `drafted`: the draft always existed; what failed was the issue.
BREAK_RESOLUTION_ISSUED = "issued"
BREAK_RESOLUTIONS = (BREAK_RESOLUTION_DRAFTED, BREAK_RESOLUTION_HELD, BREAK_RESOLUTION_ISSUED)
#: The stage a SEND break is filed under — beside the pipeline's own stage
#: names, which are the calculation's. A send break is never re-DRAFTED: its
#: draft exists and its retry is a re-issue of that one bill.
BREAK_STAGE_SEND = "send"


class BillRunBreak(models.Model):
    """One account the CALCULATION could not draft — durable, per account, per run.

    ⚠ **THIS TABLE EXISTS BECAUSE THE BREAK LIST DID NOT SURVIVE A REFRESH.**
    `runs.CalculatedRun.breaks` was in memory only: `calculate_run` returned it
    and nothing persisted it, so `apps/billing/api.py` served the list from the
    POST that computed it and had to state, on every response, that there was
    no `GET .../breaks` because serving one would mean CALCULATING inside a
    read. A clerk who navigated away lost the exception list and kept the
    drafts — which is the worst of the two halves to lose, because the drafts
    are the ones that need no attention. CR-051 task 5.

    **WHAT A ROW SAYS**, and it is BR-BIL-053's own vocabulary: the account, the
    STAGE that failed by the pipeline's own name (BR-BIL-037/040), the machine
    reason it carries, the sentence a human reads, and whether *fix and retry
    now* is a button that could work. *"ACC-1201 failed"* sends a clerk hunting;
    *"ACC-1201 failed at measure-consumption: no usable read for gas"* is a
    minute's work.

    **ONE ROW PER (RUN, ACCOUNT), ENFORCED BY THE DATABASE** —
    `uq_bill_run_breaks_once`, the same shape `bill_run_exclusions` already
    uses. That is hard rule 6 where it cannot rot: a calculate that runs twice,
    a re-delivered Celery task, two clerks pressing the button at once — none of
    them can produce a second row for one account. The write is an upsert, so
    the SECOND pass over an account that broke differently updates the stage and
    reason rather than appending a contradiction.

    **`account_no` IS STORED, NOT JOINED.** It is the label the clerk reads, and
    it is stored as the RUN SAW IT: the break list must be readable without
    reaching into another module's tables (B1/G6 — billing publishes no
    by-id customers read), and a renumbered account should not silently retitle
    a break that was raised against the old number.

    **NOT AN IMMUTABLE FINANCIAL RECORD.** Hard rule 4 covers issued invoices,
    invoice lines, payments and journal entries. A break is a work item about a
    bill that does NOT exist, so `resolution` is updated in place exactly as
    `bill_run_exclusions.resolved_at` is — the precedent this table follows
    deliberately rather than minting a second convention for the same question.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        BillRun, on_delete=models.PROTECT, related_name="breaks", db_column="bill_run_id"
    )
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: The account number as the run saw it — see the docstring.
    account_no = models.TextField()
    #: The pipeline stage that failed, by its own name (BR-BIL-037/040).
    stage = models.TextField()
    #: The machine reason code (`runs.STAGE_BY_REASON`'s keys, `gather`'s codes).
    reason = models.TextField()
    #: The sentence the failure carried, whole and unedited (BR-SHL-020).
    detail = models.TextField(null=True, blank=True)
    #: Whether *fix and retry now* could work. `runs.NOT_RETRYABLE_HERE` decides.
    retryable = models.BooleanField(default=True)
    #: NULL = outstanding (BR-BIL-053). See `BREAK_RESOLUTIONS`.
    resolution = models.TextField(null=True, blank=True)
    #: The BE-07 job that last wrote this row, or NULL when calculate ran inline.
    #: Not an FK: `jobs` is tenancy's table and a break must not depend on a job
    #: record surviving archival (B2 §2 — the reviewed FK set does not include it).
    job_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_run_breaks"
        indexes = [
            models.Index(fields=["tenant", "bill_run"], name="ix_bill_break_run"),
            # The list a clerk actually opens: this run's OUTSTANDING breaks.
            models.Index(
                fields=["tenant", "bill_run", "stage"],
                condition=Q(resolution__isnull=True),
                name="ix_bill_break_outstanding",
            ),
        ]
        constraints = [
            # Hard rule 6 at the DB level — a job that runs twice cannot write
            # two rows for one account. See the docstring.
            models.UniqueConstraint(fields=["bill_run", "account"], name="uq_bill_run_breaks_once"),
        ]


#: The per-case decisions S31.3 offers (BR-BIL-015 / BR-BIL-003 / BR-BIL-007).
#: Each is a CHOICE a human made about one account in one run, and each changes
#: what that account is billed — so each is recorded, not merely acted on.
DECISION_CASES = (
    "missing_read",  # BR-BIL-015: estimate | hold | bill_without_service
    "late_fee",  # BR-BIL-003: apply | waive  (a waiver is always manual)
    "extra_charge",  # BR-BIL-007: a tenant charge code added to the bill
    "overcharge",  # BR-BIL-029: a draft over the guardrail — release | hold
    "no_usage",  # a zero-usage account the clerk chose to bill or hold
    # PO ruling 2026-08-11 on vacant / base-only accounts: *"this is decision
    # user make hence during pre billing process, you have to give option to
    # user to opt in or opt out of this decision."* BR-CUS-055 classes a
    # Vacation-hold or Suspended account as billable-base-only; the PO's
    # refinement is that whether this run actually bills them is the staff's
    # call at PREPARE time, shown on screen with the rest. So it is a recorded
    # decision like any other, not a silent consequence of a status class.
    "base_only_billing",  # include | exclude the base-only accounts this run
    # ── BR-BIL-301 (PO 2026-09-25, option (b)) — the plan sells this account a
    # service the property is NOT CONNECTED for. The bill prices it at `$0.00`
    # and says so on the document; THIS is the other half of the ruling, the
    # list a clerk works through. **It is a DECISION and not a BLOCK on
    # purpose:** the account is billable and the run will bill it — what a
    # human is being asked is whether the estate is right, which is a question
    # about data rather than about this bill. A block would stop a bill the PO
    # has expressly ruled must be produced.
    "service_not_connected",  # the estate is short a connection | bill it anyway
    # ── CR-038 W8 (2026-08-26) — the read-analysis cases, bringing S31's read
    # tabs to the prototype's eight categories (BIL-02.2). Each is a question
    # about a READ the run is about to price, asked per (account, service), and
    # every disposition is a recorded row with an actor on it — the PO
    # reaffirmed the no-pre-selected-default rule the same day: *"speed comes
    # from the bulk button, not from decisions nobody made; an auditor asking
    # 'who chose to estimate M-4412?' gets a name"*. The facts each case renders
    # are STORED metering facts (`rule_outcomes`, the estimation trio, the
    # multiplier, `days_since_prior`) — see apps/billing/read_analysis.py.
    "estimated_read",  # BR-MET-026..029: keep the estimate | replace_with_actual
    "high_usage",  # BR-MET-020 high (stored outcome): bill_as_is | investigate
    "low_usage",  # BR-MET-020 low (stored outcome): bill_as_is | investigate
    "days_threshold",  # BR-MET-121: prorate_to_cycle_days | wait_next_cycle | bill_as_is
    "meter_factor",  # BR-MET-056's shown math: confirm_factor | investigate
    "replacement",  # mid-cycle swap: prorate_both_segments | bill_as_is | investigate
    "true_up",  # BR-BIL-006 / GT-9 / WE-13 ❄: apply_next_bill | hold
)


class BillRunDecision(models.Model):
    """A staff decision taken during a run, and who took it.

    THE GAP THIS FILLS. The run's exception step (S31.3) asks a human to choose
    per account: estimate this read or hold the account or bill without the
    service; apply this late fee or waive it; add this charge code; release
    this over-guardrail draft or hold it. BR-BIL-015 sends a HOLD to
    `bill_run_exclusions` — and every other choice had nowhere to land. It
    would have changed the bill and left no trace of who decided or why.

    The PO stated the requirement directly on 2026-08-11: *"all the decisions
    are made on screen and recorded"*. Recorded is the operative word. A month
    later, "why was this account estimated instead of held?" has an answer with
    a name on it, and a customer disputing an estimated bill can be told who
    made that call and when.

    APPEND-ONLY, and deliberately so. Changing one's mind writes a NEW row
    superseding the old, the same shape the plan history uses: the run's
    decision trail is evidence, and evidence that can be edited is not
    evidence. `superseded_by` makes the current decision a query rather than a
    guess.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        BillRun, on_delete=models.PROTECT, related_name="decisions", db_column="bill_run_id"
    )
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: Which service the decision is about, when it is service-specific — a
    #: missing read is per service, and "bill without the service" is
    #: meaningless without naming which one.
    service = models.ForeignKey(
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    case = models.TextField()  # DECISION_CASES
    choice = models.TextField()  # estimate | hold | bill_without_service | apply | waive | ...
    #: Why. Free text, and REQUIRED for a waiver by BR-BIL-003 — the service
    #: layer enforces which cases demand one; the column holds it for all.
    reason = models.TextField(null=True, blank=True)
    #: What the choice was worth, where it has a value: the estimated quantity,
    #: the fee applied or waived, the charge added. Money and quantities keep
    #: six decimals like everywhere else (CLAUDE.md rule 2).
    amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit = models.TextField(null=True, blank=True)  # rule 3, when it is a quantity
    decided_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="decided_by"
    )
    #: PO ruling 2026-08-11: *"you will also need to give bulk option; if there
    #: are 500 or 1000 or 5000 bills to be generated and 1000 bills has late
    #: fees, it is impossible for user to do this manually account by account."*
    #:
    #: A bulk action is ONE human decision applied to N accounts, and both
    #: halves have to survive. Each account still gets its OWN row — its bill
    #: changed, so its trail must say so, and a later dispute is about one
    #: account. But the rows share a `bulk_action_id`, so the trail can also
    #: answer the different question: "was this considered individually, or was
    #: it one of a thousand?" Those are not the same fact and a single row
    #: cannot carry both.
    #:
    #: NULL means the decision was taken on that account alone.
    bulk_action_id = models.UUIDField(null=True, blank=True)
    #: Set when a LATER decision replaces this one. NULL = current. Append-only
    #: correction, never an UPDATE of the original (hard rule 4's reasoning,
    #: applied to a decision trail rather than to money).
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supersedes",
        db_column="superseded_by_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_run_decisions"
        indexes = [
            models.Index(fields=["tenant", "bill_run", "account"], name="ix_bill_dec_run_acct"),
            # "Show me that bulk action" — the 1,000 rows one click produced.
            models.Index(fields=["tenant", "bulk_action_id"], name="ix_bill_dec_bulk"),
            # The screen's own query: every live decision in this run.
            models.Index(
                fields=["tenant", "bill_run"],
                condition=Q(superseded_by__isnull=True),
                name="ix_bill_dec_current",
            ),
        ]


class BillRunRelease(models.Model):
    """The release gate — what the user was SHOWN, and that they authorised it.

    Phase 4 of the run the PO described on 2026-08-11, verbatim: *"then show
    the billing summary in how many accounts, how many bills generated, how
    much consumption and how much bill amount and various categories; take
    final confirm from user, compliance confirmation, emails, text mandates,
    auto pay mandates and then release the bills."*

    THIS ROW IS THE AUTHORISATION RECORD, NOT THE SCREEN — and since the PO's
    ruling of 2026-08-11 those are two different things (BR-BIL-056; decision
    log, same date).

    What was put to them, in their own worked figure: *"You approve 480 bills,
    $52,847.19. Two bills are voided next week. The screen still says 480 /
    $52,847.19, because that's what you approved."* Options: A keep frozen ·
    B recalculate live · C show both, side by side. THEY CHOSE B, so the
    phase-4 panel recalculates on every viewing and a voided bill leaves its
    figures.

    What this row does is the other half, and that did NOT change: it keeps the
    figures that were on screen at the moment of confirmation, and it is never
    rewritten. Hard rule 4 makes it append-only, and the ruling was about what
    the screen DISPLAYS, not about deleting evidence. So a reader who finds
    these stored columns disagreeing with a live screen is looking at the
    design, not a bug: "what did I authorise?" and "what do these bills total
    today?" are different questions, and each has its own answer here.

    The consequence worth carrying forward: after that ruling the SCREEN no
    longer answers the first question. THIS ROW IS THE ONLY THING THAT DOES —
    load-bearing evidence, not a stale cache, and nothing may drop it as
    redundant. Pinned by tests/test_us_bil_005_release_gate.py tc4 (the screen
    recalculates) and tc4b (this row does not).

    ⚠ Nothing in the database enforces that append-only guarantee. There is no
    immutability trigger on `bill_run_releases` and a blanket one is impossible
    — `released_at` is written later by design — so the guarantee is hard rule 4
    plus a single writer, asserted by test rather than by constraint. A trigger
    narrowed to the figure columns would close it; that is on the record as a
    recommendation, not a claim this docstring may make (hard-won law 1).

    The mandate counts stay as written. *"68 accounts have no email address"*
    is a fact about the moment of release, and counting it later counts the
    addresses added since. ⚠ The 2026-08-11 ruling was put about BILLS and
    AMOUNT and named neither these counts nor BR-BIL-059, so a re-opened run
    may show live bill figures beside a stored "68 of 1,122". Flagged in
    BR-BIL-059, not resolved here: a signature covers only what was shown.

    APPEND-ONLY. A run released twice — a catch-up sub-run, a resumed batch —
    writes a second row. Neither replaces the other, because both happened and
    both were authorised by someone.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        BillRun, on_delete=models.PROTECT, related_name="releases", db_column="bill_run_id"
    )
    #: What was on screen when they confirmed. A JSON payload rather than
    #: columns for the same reason `bill_payload` is: the category breakdown is
    #: tenant-shaped (their services, their account types), and a column per
    #: category would put a migration between a tenant and their own summary.
    #: Shape: {accounts, bills, consumption: [{service, quantity, unit}],
    #: amount, by_category: [...], delivery: {...}, autopay: {...},
    #: compliance: [...]}.
    #:
    #: This payload is what was shown AT SIGN-OFF. It is NOT what a later
    #: viewing of the run renders — that panel is recomputed from the run's
    #: current bills (BR-BIL-056, PO 2026-08-11 option B).
    summary = models.JSONField()
    #: Pulled OUT of the payload as columns because these four are what a
    #: person reads first and what an auditor asks for, and a query that has to
    #: open JSON to answer "how much did we bill on 1 July" is a query nobody
    #: writes. Money keeps six decimals + its currency (CLAUDE.md rule 2).
    account_count = models.IntegerField()
    bill_count = models.IntegerField()
    total_amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3)
    #: The confirmations the PO enumerated, each recorded as its own boolean so
    #: "they confirmed" can never be one undifferentiated tick. A release that
    #: went out without the compliance check is a different event from one that
    #: did, and only separate columns can say which happened.
    compliance_confirmed = models.BooleanField(default=False)
    email_mandate_confirmed = models.BooleanField(default=False)
    sms_mandate_confirmed = models.BooleanField(default=False)
    autopay_mandate_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="confirmed_by"
    )
    confirmed_at = models.DateTimeField()
    #: Set when the downstream batches finish (issue, documents, delivery).
    #: NULL means authorised but not yet released — the state a crash between
    #: phase 4 and phase 5 leaves behind, and the one a resume must recognise
    #: so it does not ask for authorisation twice.
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_run_releases"
        indexes = [
            models.Index(fields=["tenant", "bill_run"], name="ix_bill_release_run"),
            models.Index(
                fields=["tenant", "-confirmed_at"],
                condition=Q(released_at__isnull=True),
                name="ix_bill_release_pending",
            ),
        ]


class Invoice(models.Model):
    """A bill (B2 §2 `invoices`; r10 #3/#12).

    `service_date` drives which tariff version priced it (B2's own comment):
    "Historical invoices join the version where service_date ∈ [effective_from,
    effective_to). Never the current version." That is the 7-year
    reproducibility promise expressed as a column.

    Money is NUMERIC(18,6) with a CHAR(3) currency partner (CLAUDE.md rule 2).
    `total` is rounded to 2dp at finalization; the components stay at 6.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    bill_run = models.ForeignKey(
        BillRun, on_delete=models.PROTECT, null=True, blank=True, db_column="bill_run_id"
    )
    #: BR-BIL-022 (source and format: the tenant number series, default
    #: `BL-{YYMM}-{seq}`) · **BR-BIL-063 (timing): allocated when the DRAFT is
    #: created**, PO ruling 2026-08-11 — *"Give a running number always even for
    #: Draft; if not use thats okay we will lose it."* The gap cost was put to
    #: the PO and accepted on simplicity grounds: a re-run replaces its draft
    #: (BR-BIL-023) and allocates fresh numbers, so a 500-account run re-run
    #: three times spends 1,500 numbers on 500 bills.
    #:
    #: STILL NULLABLE, and deliberately. Nothing in this module now writes a
    #: draft without a number, but a NOT NULL here would make the column the
    #: enforcer of a rule the PO could revisit tomorrow, and it would refuse
    #: every historical row written under the previous reading. The partial
    #: unique index (`WHERE invoice_no IS NOT NULL`) stays for the same reason —
    #: it is now merely harmless rather than load-bearing, and removing it would
    #: let two numberless rows collide if one ever occurred.
    invoice_no = models.TextField(null=True, blank=True)
    bill_type = models.TextField(default="cycle")  # r10 #12
    service_date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField(null=True, blank=True)  # BR-BIL-024, derived
    status = models.TextField(default=INVOICE_DRAFT)
    subtotal = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    issued_at = models.DateTimeField(null=True, blank=True)
    #: r10 #3 — the template this bill was rendered with, PINNED at issue.
    #: Plain columns, not FKs. The original reason was that `bill_templates`
    #: did not exist yet and an invoice issued in the meantime must still
    #: record which template it used — a pin that waits for its table is
    #: missing exactly when needed.
    #: ⚠ **THAT REASON EXPIRED ON 2026-08-15 AND THE COMMENT SAID OTHERWISE
    #: UNTIL 2026-08-30.** `bill_templates` / `bill_template_versions` have
    #: existed since then, so these two columns are now loose by INERTIA, not
    #: by design, and nothing here says so. **The consequence is live: a
    #: migration that dropped the version row these name would raise no error,
    #: break no test, and go unnoticed until somebody asked for a reprint.**
    #: BR-NOT-025 is the rule that forbids it (a version any sent document
    #: points at is archived, never deleted); making these real foreign keys
    #: is the stronger fix and belongs with CR-048 task E9, which is where the
    #: two template systems are merged (OQ-842). Left as columns here because
    #: adding the constraint is a migration on `invoices` and is not this
    #: comment's to take.
    #: The exposure is LOWER on this side than on the notification side: a
    #: bill is locked at issue into `custom_snapshot` (BR-BIL-030) and a
    #: reprint renders that instance, so what an orphaned pin loses here is
    #: the provenance answer, not the document.
    template_id = models.UUIDField(null=True, blank=True)
    template_version = models.IntegerField(null=True, blank=True)
    #: BR-BIL-030, CONFIRMED (PO 2026-08-10) — "The bill is LOCKED at issue: a
    #: complete document instance is stamped, and reprint renders that instance
    #: forever." Everything the document displays: tenant identity, customer
    #: name, service address, premises/unit, account number, each meter with
    #: its prior and current read and unit, every line grouped by service,
    #: taxes, totals and messages. A reprint, a re-send and a dispute copy
    #: render from here and JOIN NOTHING LIVE (BR-CUS-040).
    #:
    #: ⚠ NAMED `bill_payload`, not `issued_snapshot`. The first cut of this
    #: model invented the second name while quoting BR-BIL-030's own ruling in
    #: its docstring — signed law names the column and the code did not follow
    #: it. Caught by the corrections lane reading the rule; renamed rather than
    #: left as a synonym, because a synonym is how two names for one thing
    #: start disagreeing.
    #:
    #: NULLABLE at DRAFT, required at ISSUE. BR-BIL-030 writes `NOT NULL`,
    #: which binds where the rule binds — at issue. A draft is discardable and
    #: may be replaced before it ever carries a payload, so the constraint is
    #: enforced by the issue trigger (migration 0007) rather than by the column,
    #: the same shape `invoice_no` has, though for a different reason: the
    #: payload's constraint binds at issue, while the number is now allocated at
    #: draft creation (BR-BIL-063).
    bill_payload = models.JSONField(null=True, blank=True)
    #: BR-BIL-030's partner. The payload is a CONTRACT, not a free-form blob:
    #: a renderer must know which shape it is looking at, and BR-BIL-035 makes
    #: v1 carry the balance-forward section whether or not a tenant renders it.
    payload_version = models.IntegerField(default=1)
    #: B2 r17.3 / US-BIL-028 / BR-BIL-030 — the tenant's own custom-field values
    #: as they stood when this bill was assembled. **STRING VALUES ONLY**, keys
    #: namespaced `<entity>.<key>`, `{}` when the tenant has defined none
    #: (US-BIL-028 TC-5: never null).
    #:
    #: WHY THE COLUMN EXISTS IN R2 WHEN NOTHING READS IT UNTIL R3. It is a
    #: ONE-WAY DOOR (B12 r7.2, verbatim): *"You cannot retroactively reconstruct
    #: what an account looked like six months ago. If R2 issues real invoices
    #: with no snapshot column, every invoice from that period is permanently
    #: unable to render custom fields — and the tempting repair is a live join
    #: to master data, which rewrites issued documents without ever running an
    #: UPDATE. Stamp early, render later."* The template variables that consume
    #: it are US-NOT-016, in R3.
    #:
    #: Strings only is STRUCTURAL, not stylistic (r17.3): a `number` field
    #: becomes `"1234"`, so arithmetic on it is impossible without an explicit
    #: parse that G6 can grep for. That is the half of BR-TEN-048 which does not
    #: depend on anyone's discipline. It also pins IS-8 formatting, so a 2029
    #: reprint renders as the 2026 original did.
    #:
    #: NOT NULL DEFAULT '{}' (r17.3, applied in migration 0009) and frozen by
    #: the same immutability trigger that freezes the money — see 0009, which
    #: had to re-emit `billing_invoice_immutable()` to name this column.
    custom_snapshot = models.JSONField(default=dict, blank=True)
    #: THE CORRECTION CHAIN'S REBILL LEG — **PO ruling 2026-08-12, OQ-120
    #: CLOSED**, verbatim: *"Nod to add the link on the new bill"*.
    #:
    #: The link lives on the REPLACEMENT and points back at what it replaces.
    #: The direction is the whole of the ruling and is not a preference: an
    #: issued invoice is immutable (BR-BIL-004, hard rule 4), so the ORIGINAL
    #: must not gain a value after issue — a column written onto a frozen row is
    #: the immutability rule failing open. A rebill, by contrast, learns what it
    #: replaces at the moment it is INSERTed, before it is anything at all.
    #:
    #: ⚠ THIS SUPERSEDES THE 2026-08-11 READING of the same OQ id (*"in Histrory
    #: log only - at account level"*), under which no column existed and the
    #: link was written only into `audit_log`. `apps/billing/corrections.py`
    #: still writes that audit row — it is hard rule 7 and is owed anyway — but
    #: the audit trail is no longer the ONLY carrier, because a panel cannot
    #: join to a log (BR-BIL-064: `release.summary_for` refused outright for
    #: want of exactly this column).
    #:
    #: NULL on every bill that replaces nothing, which is nearly all of them.
    #: Frozen after issue by the `0017` immutability trigger, and UNIQUE per
    #: original: one bill is replaced by at most one bill, so the chain is a
    #: chain and never a tree (BR-BIL-048).
    corrects_invoice = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="corrects_invoice_id",
        related_name="corrected_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoices"
        indexes = [
            models.Index(fields=["tenant", "account", "period_start"], name="ix_invoices_acct"),
            models.Index(fields=["tenant", "status", "due_date"], name="ix_invoices_due"),
            models.Index(fields=["tenant", "bill_run"], name="ix_invoices_run"),
            # BR-BIL-064's read: given a superseded original, find the bill that
            # replaced it. Without this index the phase-4 panel is a sequential
            # scan per superseded bill.
            models.Index(fields=["tenant", "corrects_invoice"], name="ix_invoices_corrects"),
        ]
        constraints = [
            # UNIQUE (tenant_id, invoice_no) from B2, made PARTIAL because a
            # draft carries no number and several NULLs must coexist.
            models.UniqueConstraint(
                fields=["tenant", "invoice_no"],
                condition=Q(invoice_no__isnull=False),
                name="uq_invoices_no",
            ),
            # ONE REPLACEMENT PER ORIGINAL (BR-BIL-048). Two bills claiming to
            # replace the same bill is a tree, and a tree has no "latest in the
            # chain" — the rule BR-BIL-048 states would have no referent. The
            # service layer already refuses (`corrections.
            # refuse_unless_latest_in_chain` plus `uq_correction_bill_in_flight`)
            # and this is the last-ditch guarantee under a race those two lose.
            # PARTIAL, because every uncorrecting bill carries NULL here.
            models.UniqueConstraint(
                fields=["tenant", "corrects_invoice"],
                condition=Q(corrects_invoice__isnull=False),
                name="uq_invoices_one_replacement",
            ),
            # A bill cannot replace itself. Cheap, and it turns a self-referential
            # loop from a panel that never terminates into an INSERT that fails.
            models.CheckConstraint(
                condition=~Q(corrects_invoice=models.F("id")),
                name="ck_invoices_corrects_not_self",
            ),
        ]


class InvoiceLine(models.Model):
    """One priced line (B2 §2 `invoice_lines`; r10 #1).

    `unit` is explicit whenever the line is usage-based — CLAUDE.md rule 3, and
    the reason `quantity` alone is never enough to reprint a bill.

    `taxable` is the B4.2 flag, but note what the ENGINE does with it: the tax
    base is selected by line KIND as well, so a fee arriving wrongly flagged
    taxable still cannot be taxed. The column records what the line was; it is
    not the whole of the rule.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="lines", db_column="invoice_id"
    )
    #: Denormalized per B2's own comment, for the (tenant, account, period)
    #: index — the read path every bills list and every aging report takes.
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    service = models.ForeignKey(  # r16 #3: the enum became the service catalog
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    tariff_version = models.ForeignKey(  # ⚠ cross-module FK → rating
        "rating.TariffVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="tariff_version_id",
    )
    charge = models.ForeignKey(  # ⚠ cross-module FK → rating
        "rating.Charge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="charge_id",
    )
    #: ⚠ cross-module FK → rating. **WHOSE TAX THIS LINE IS** — BR-BIL-069, the
    #: PO's ruling of 2026-08-11 closing OQ-116: *"For each atheority have
    #: separate account and tagging"*.
    #:
    #: A single tax charge is usually several taxes. On the reference $117.01
    #: bill the $8.30 is State of Texas 6.25% = $6.29 + Harris County 1.00% =
    #: $1.01 + City of Katy 1.00% = $1.00 over the $100.58 taxable base: three
    #: authorities, three debts, three returns to file. Without this column a
    #: tax line records only `kind='tax'`, its wording and its amount — so the
    #: $6.29 cannot be identified as Texas's, BR-BIL-010's stamp has nothing to
    #: resolve, and the whole bill refuses at issue. That refusal was correct: a
    #: guess here remits the wrong money to a tax authority.
    #:
    #: An FK and not a bare uuid, unlike `gl_account_id`: `taxes` is a table
    #: that EXISTS, in a module this table already carries two reviewed
    #: cross-module FKs into (`tariff_version`, `charge`). The B11 F-3
    #: deferred-uuid convention is for a target that has not been built yet, and
    #: it is not this. `PROTECT` for the same reason as its neighbours — a tax
    #: an issued bill points at is part of a financial record (IS-1
    #: deactivate-first; `taxes.deleted_at` is how a tenant retires one).
    #:
    #: NULL on every line that is not a tax line, and on a tax line whose rule
    #: stated a `rate_override` for a jurisdiction with no `taxes` row behind it
    #: — a real configuration gap that BR-BIL-010 reports at issue.
    tax = models.ForeignKey(
        "rating.Tax",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="tax_id",
    )
    #: r10 #1 / BR-BIL-010 — resolved from the account mapping AT ISSUE and
    #: frozen. Later mapping edits never re-stamp history. A plain uuid, not an
    #: FK: `ledger_accounts` is W5 and does not exist (the B11 F-3 deferred-FK
    #: convention this repo already uses for account_types and taxes).
    gl_account_id = models.UUIDField(null=True, blank=True)
    #: **THE METER (OR ASSET) THIS LINE WAS PRICED FOR** — PO ruling
    #: 2026-09-30: two meters on one metered service bill as two sets of lines,
    #: each on its own ladder with its own base, and a document must say which
    #: line is which meter. `assets.Asset.id`; `billing/0031`.
    #:
    #: ⚠ **A PLAIN UUID, NOT A FOREIGN KEY, AND DELIBERATELY.** B2 §2 makes a
    #: cross-module FK a REVIEWED interface, and build plan `DB1` names this
    #: one as needing that review. Until it is reviewed the column holds the id
    #: and the database does not police it — the `B11 F-3` deferred-FK shape
    #: `gl_account_id` above carried until `billing/0030`. Adding the
    #: constraint later is one `ALTER TABLE … ADD CONSTRAINT` (0030's shape).
    #:
    #: NULL on every line whose service carries one meter (every bill before
    #: the ruling), on tax and fee lines, and on counted lines, which are
    #: priced per SIZE group rather than per asset.
    asset_id = models.UUIDField(null=True, blank=True)
    #: PO ruling 2026-10-01 (`billing/0039`) — the chain this line was priced
    #: from, as VALUES at draft: account, unit, plan + version, rate schedule
    #: version, customer type, base code, and per size the count, base each,
    #: base total and price each. Values and not references, because a charge
    #: code's size rows are deleted and re-created on every edit. NULL on every
    #: line written before it and on tax/fee lines (hard rule 4: no backfill).
    pricing_trace = models.JSONField(null=True, blank=True)
    #: 🔒 `DEF-2430` / `DEF-BIL-5341` (`billing/0040`) — the PROGRAMME CODE a
    #: `discount` line was granted under (`CAP`), stamped by the engine and
    #: written HERE at draft with `tariff_version_id` and `charge_id`, for the
    #: same reason: it is a fact about what was priced, and issue only hands it
    #: to rating, which records the grant against the account's enrolment so a
    #: yearly cap and a budget count down. A CODE, not a foreign key: the code
    #: is what crosses the seam and what a discount is known by on every
    #: screen, and rating resolves the enrolment and the version from it on
    #: the bill's service date. NULL on every non-discount line and on every
    #: discount line written before it (hard rule 4: no backfill).
    discount_code = models.TextField(null=True, blank=True)
    kind = models.TextField()  # LINE_KINDS — the tuple above, not this comment
    description = models.TextField()
    quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit = models.TextField(null=True, blank=True)  # rule 3 — explicit on usage
    unit_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    taxable = models.BooleanField(default=False)  # B4.2 (finance 2026-08-07)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_lines"
        indexes = [
            models.Index(fields=["tenant", "invoice"], name="ix_invoice_lines_invoice"),
            models.Index(
                fields=["tenant", "account", "period_start"], name="ix_invoice_lines_acct"
            ),
            # DEF-BIL-8708 (billing 0037) — a line is UPDATED by its id at issue,
            # and the partitioned table's key leads with tenant_id, so without
            # this every GL stamp scanned the partition (68 ms a line at 40,000).
            models.Index(fields=["id"], name="ix_invoice_lines_id"),
        ]


#: `account_budget_status.status` — B2 r12 #14 item D-5 names `off_budget`
#: explicitly. Imported from `apps.billing.budget` rather than redefined so the
#: value set exists once (the module that owns the RULE owns the vocabulary).
BUDGET_STATUSES = budget.STATUSES

#: What an `account_budget_events` row records. Every one of these changes what
#: a customer pays or what they are owed, so every one leaves a row.
BUDGET_EVENT_ENROLLED = "enrolled"
BUDGET_EVENT_BILLED = "billed"  # one cycle bill: level vs actual, variance moved
BUDGET_EVENT_SETTLED = "settled"  # the annual true-up
BUDGET_EVENT_RELEVELED = "releveled"
BUDGET_EVENT_OVERRIDDEN = "overridden"
BUDGET_EVENT_REMOVED = "removed"  # a STAFF action; never an automatic drop-off
BUDGET_EVENTS = (
    BUDGET_EVENT_ENROLLED,
    BUDGET_EVENT_BILLED,
    BUDGET_EVENT_SETTLED,
    BUDGET_EVENT_RELEVELED,
    BUDGET_EVENT_OVERRIDDEN,
    BUDGET_EVENT_REMOVED,
)


class AccountBudgetStatus(models.Model):
    """One account's budget-billing position (B2 Addendum r10 #5).

    r10 #5 names the columns: *"`account_budget_status` (level, variance
    balance, last_leveled_at, settle_up_month, level_override + reason ±30%) +
    tenant budget settings"*, and r12 #14 item D-5 adds `status` incl.
    `off_budget`. The tenant settings half already exists — S69 / BR-BIL-017, in
    `apps.tenancy.settings_families.BUDGET_BILLING` — so nothing is duplicated
    here; this table holds only what is per-ACCOUNT.

    **`variance_balance` IS A CACHE, and `account_budget_events` is the truth.**
    US-BIL-019 TC-6 requires that the balance cannot be recomputed by editing it:
    *"the balance derives from bill events append-only"*. So every movement
    writes an event row and this column is the running total those rows produce.
    `apps.billing.budget_service.recompute_balance` is the derivation, and its
    test asserts the two agree — a cache nobody checks is a second source of
    truth waiting to disagree.

    **THERE IS NO `missed_count` COLUMN AND THAT IS THE RULE, NOT AN OMISSION.**
    PO ruling 2026-08-11, verbatim *"nodrop we chase for payments until write
    off"*: BR-BIL-017's two-missed-payments drop-off is SUPERSEDED, and the
    undefined "missed payment" it depended on became MOOT rather than answered.
    A column counting misses would be storage for a rule that no longer exists,
    and the next agent would wire something to it.

    `status = off_budget` remains reachable — by the S30 "Remove from budget"
    row action, which is a staff decision with a name and an audit row on it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    status = models.TextField(default=budget.STATUS_ENROLLED)  # BUDGET_STATUSES
    #: BR-BIL-017: the trailing-12-month average, whole dollars (WE-8: $242).
    #: Money keeps six decimals and its currency partner like every other money
    #: column here (CLAUDE.md rule 2) even though the VALUE is whole-dollar —
    #: the rounding is a rule about the figure, not a property of the column.
    level = models.DecimalField(max_digits=18, decimal_places=6)
    #: The per-account override (BR-BIL-017 as OQ-068 closed it: with reason,
    #: audited, bounded ±30% of computed). NULL = no override, and the account
    #: pays `level`. Kept ALONGSIDE `level` rather than overwriting it because
    #: the ±30% bound is measured against the COMPUTED level, so losing it would
    #: make the next override unvalidatable.
    level_override = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    level_override_reason = models.TextField(null=True, blank=True)
    currency = models.CharField(max_length=3)  # rule 2 partner
    #: WE-8's running balance. Positive = the levels collected more than the
    #: customer used (we owe them); negative = they used more than they paid.
    variance_balance = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    #: BR-BIL-017's cadence gate reads this (re-level each `relevel_cadence_months`).
    last_leveled_at = models.DateField(null=True, blank=True)
    #: The tenant's `settle_up_month`, COPIED onto the account at enrolment.
    #: Deliberately a copy and not a live read: a tenant moving their settle-up
    #: month in September must not silently move it for an account already
    #: mid-year (BR-TEN-043's config-forward law, J09 step 5).
    settle_up_month = models.IntegerField(null=True, blank=True)
    enrolled_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_budget_status"
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_budget_status"),
            models.Index(fields=["tenant", "settle_up_month"], name="ix_budget_settle_month"),
        ]
        constraints = [
            # US-BIL-018 TC-5: one active budget status per account. PARTIAL, so
            # an account removed from the programme can be enrolled again later
            # without deleting the row that records it was once on it.
            models.UniqueConstraint(
                fields=["tenant", "account"],
                condition=Q(status=budget.STATUS_ENROLLED),
                name="uq_budget_one_live_per_account",
            ),
        ]


class AccountBudgetEvent(models.Model):
    """APPEND-ONLY: every movement of a budget account's level or balance.

    US-BIL-019 TC-6 — *"Variance recomputed by editing the stored balance
    directly → Rejected; the balance derives from bill events append-only"* —
    is why this table exists. `account_budget_status.variance_balance` is the
    running total of `movement` over these rows; the rows are the record.

    NOT named in Addendum r10, which lists `account_budget_status` alone. It is
    an Eng-Lead DDL call under r10 #15 (*"Idempotency, keys, exact DDL =
    Eng-Lead-owned"*) and it is recorded as one in
    12-governance/02-decision-log.md, because the alternative — deriving a
    twelve-month balance from issued invoices at read time — cannot survive a
    re-level (the level in force when each bill issued governs it, BR-TEN-043)
    and cannot record an override at all.

    Hard rule 4's reasoning applied to a derivation trail rather than to money:
    a balance that can be edited is not a balance. Nothing UPDATEs these rows;
    a correction is a new row, and the 0013 trigger refuses anything else.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    budget_status = models.ForeignKey(
        AccountBudgetStatus,
        on_delete=models.PROTECT,
        related_name="events",
        db_column="account_budget_status_id",
    )
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: The bill this movement belongs to, when it has one. NULL for enrolment,
    #: an override and a re-level — those are decisions, not bills.
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, null=True, blank=True, db_column="invoice_id"
    )
    event = models.TextField()  # BUDGET_EVENTS
    #: The three columns WE-8 puts on every bill, kept per event so a bill's own
    #: row can reproduce what the customer was shown without re-deriving it from
    #: a level that may since have moved.
    level = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    actual = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: `level − actual` for a bill; the settled amount (signed) for a settle-up;
    #: 0 for a decision that moved no money.
    movement = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    balance_after = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3)  # rule 2 partner
    #: Required by BR-BIL-017 for an override; carried for every event because
    #: "why did this level change?" is the question a year-old row is asked.
    reason = models.TextField(null=True, blank=True)
    actor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_id"
    )
    #: BR-TEN-043: the BUSINESS date of the event, passed in by the caller.
    #: `created_at` is when the row was written and they are not the same fact —
    #: a bill run replayed for July writes July's event today.
    occurred_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_budget_events"
        indexes = [
            models.Index(
                fields=["tenant", "budget_status", "occurred_on"], name="ix_budget_ev_status"
            ),
            models.Index(fields=["tenant", "account"], name="ix_budget_ev_account"),
        ]
        constraints = [
            # Hard rule 6's shape applied to a bill run's replay: one BILLED
            # event per invoice. A re-run that re-drafts a bill must not move
            # the variance balance twice.
            models.UniqueConstraint(
                fields=["tenant", "invoice", "event"],
                condition=Q(invoice__isnull=False),
                name="uq_budget_event_once_per_invoice",
            ),
        ]


class Adjustment(models.Model):
    """A correction row. NEVER an UPDATE of the invoice (hard rule 4, B2's own
    comment on this table: "correction rows, never UPDATE the invoice")."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, null=True, blank=True, db_column="invoice_id"
    )
    direction = models.TextField()  # journal_side: debit increases | credit reduces
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    reason_code = models.TextField()  # reference data (r10 #13)
    gl_account_id = models.UUIDField(null=True, blank=True)  # deferred FK → W5
    approved_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="approved_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "adjustments"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_adjustments_account"),
            models.Index(fields=["tenant", "invoice"], name="ix_adjustments_invoice"),
        ]


class CreditNote(models.Model):
    """A credit against an issued invoice — GT-6's subject.

    `original_invoice` REFERENCES the source rather than modifying it, which is
    B2's own stated reason ("references the source, per immutability").

    ════════════════════════════════════════════════════════════════════════
    `amount` IS NEVER POSITIVE — THE SIGN IS A CONSTRAINT, NOT A CONVENTION
    ════════════════════════════════════════════════════════════════════════
    **DEF-085.** This column shipped with no stated direction and TWO WRITERS
    STORING OPPOSITE ONES: `corrections.execute_credit_only` wrote
    `-25.000000` and the older correction fixtures wrote `+25.00`. Nothing
    refused either. Then money code started READING it — the release panel nets
    the sign-off total — and a signed Σ over the two conventions read **$272.30
    on a run where the customer owes $222.30**: the credit ADDED itself to the
    bill instead of coming off. The panel survived only because it summed
    MAGNITUDES per row and applied the direction once, which is a reader
    compensating for an unconstrained column — and, as DEF-085 puts it, *"how
    the next reader gets it wrong"*.

    **THE DIRECTION, ruled here as the engineering call the defect row names
    (2026-08-15, BR-BIL-074):** a credit note's amount is stored **NEGATIVE**,
    because a credit REDUCES what the customer owes and *"negative reads
    naturally as a credit against the bill"*. Both live writers already wrote it
    that way; the constraint makes it the only thing that can be written.

    **IT IS `<= 0`, NOT `< 0`, and the zero is deliberate.** A class-R
    restatement credits the ORIGINAL TOTAL in full (`execute_restatement`), and
    a $0.00 bill is a real document this product issues (BR-BIL-041/043 discuss
    exactly that case). Refusing a zero would make a legitimate correction of a
    zero-total bill impossible in order to tidy a sign that zero does not have.

    **NO SIGNED FIGURE MOVES.** GT-6 is *$25.00 credit against a $247.30 invoice
    → the customer owes $222.30*, and it is reached from `-25.000000` exactly as
    it was: the magnitude is what GT-6 states and the direction is what the
    column now guarantees. ❄️ untouched.

    **AND THE ROW ITSELF IS STILL IMMUTABLE (hard rule 4).** Once `issued_at` is
    set, `billing/0002`'s trigger freezes `amount`, `currency`, the account and
    the source, so this constraint can only ever be satisfied at INSERT — the
    sign cannot be "corrected" afterwards, by a migration or by anything else.
    `0020_credit_note_sign` therefore REFUSES to install itself over rows that
    violate it rather than UPDATE-ing history into shape; the reasoning is in
    that migration's own docstring.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    original_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="original_invoice_id",
    )
    # ⚠ **RULED, AND THIS COLUMN NOW HAS A WRITER (CR-059 CS-37, 2026-09-02).**
    # This comment read *"Timing UNRULED for credit notes … nothing writes this
    # column yet, so the question is asked there rather than answered here"*,
    # and it was true for three weeks: every credit note in the product carried
    # `credit_note_no: null` while the tenant's **Credit memo #** series sat
    # seeded and unused (`core/numbering.py:101`, default `CM-{0000}` at `:317`).
    # The visible cost was a finance user reading a raw UUID on the bill-run
    # sign-off panel, which B14 rule 31 forbids outright.
    #
    # CS-37 rules the timing in one sentence: a credit note **takes its number
    # from the tenant's Credit memo series at creation, in the same transaction
    # as the row, and never afterwards.** Both writers live in
    # `corrections.py` — `execute_credit_only` and `execute_restatement` — and
    # both call `corrections._allocate_credit_note_no`, which is where the
    # reasoning lives.
    #
    # **HISTORIC ROWS KEEP A NULL NUMBER AND ARE NOT BACK-FILLED.** The row
    # freezes at issue (the `0002` trigger), so a migration that rewrote history
    # would be exactly the thing the freeze is there to prevent. A screen meeting
    # a null shows the bill it was raised against and the date — never the id.
    credit_note_no = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    reason = models.TextField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "credit_notes"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_credit_notes_account"),
            models.Index(fields=["tenant", "original_invoice"], name="ix_credit_notes_source"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "credit_note_no"],
                condition=Q(credit_note_no__isnull=False),
                name="uq_credit_notes_no",
            ),
            # DEF-085 / BR-BIL-074 — the sign convention, at the column, where
            # every reader and every future writer meets it. See the class
            # docstring for why it is `<= 0` and not `< 0`.
            models.CheckConstraint(
                condition=Q(amount__lte=0),
                name="ck_credit_notes_amount_not_positive",
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 billing DDL + Addendum r10, the PO-approved billing schema batch — · 07-billing/06-epics/EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md · 07-billing/03-field-map.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by Eng-Lead (W3 billing schema slice) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `InvoiceLine.tax` — the cross-module FK that lets a tax line name its authority (migration 0010)) · AMENDED 2026-08-11 by Eng-Lead (OQ-122 typed-bill-date lane — BR-BIL-070: `BillRun.bill_date`, the clerk's typed date, migration 0011) · AMENDED 2026-08-11 by story-coder (budget-billing lane — Addendum r10 #5 `AccountBudgetStatus` + the append-only `AccountBudgetEvent` US-BIL-019 TC-6 requires, migrations 0012/0013). NO `missed_count` column: the PO's "nodrop we chase for payments until write off" (2026-08-11) SUPERSEDES BR-BIL-017's two-miss drop-off, so storage for it would be storage for a rule that no longer exists
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the migration's trailer — these classes and 0001 ship together
# exceptions: builds the INVOICE CORE of Addendum r10; **r10 #5 budget billing
#         landed 2026-08-11 and is no longer in the not-started list below**.
#         Templates (#4), corrections workflow (#9), balance transfer
#         (#10), write-off (#11) and the platform-wide delivery queue (#8/r12
#         #16) are their own waves and are NOT started here · gl_account_id and
#         template_id/template_version are plain uuid columns because
#         `ledger_accounts` (W5) and `bill_templates` (r10 #4) do not exist —
#         the B11 F-3 deferred-FK convention · IMMUTABILITY IS NOT IN THESE
#         CLASSES: a Django model cannot refuse a .save(), so hard rule 4 lives
#         in the 0002 triggers and the service layer, and is stated here rather
#         than implied by the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
