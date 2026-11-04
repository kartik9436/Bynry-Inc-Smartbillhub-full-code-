# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (single payment entry — the payments row, both dates,
#           the PMT- number, idempotent submit) · US-PAY-006 (the allocation
#           WRITE path — `allocations` rows against open bills) · US-PAY-009
#           (NSF — the reversing row, its link to the original, the reason) ·
#           US-PAY-011 (refunds — the `refunds` table) · US-PAY-002 (the
#           payment PURPOSE model — `payments.plan_id`, the plan-down linkage
#           B2 leaves unanchored) · US-PAY-024 (autopay capture intents — the
#           `autopay_capture_intents` table, r12 #6)
#           Screens: S22 · S32 · S33 · S35 · S58
# Rules:    BR-PAY-002 (append-only once out of processing; a correction is a
#           reversing row, never an edit) · BR-PAY-003 (inbound payment
#           webhooks dedupe on webhook_key UNIQUE) · BR-PAY-012 (every payment
#           carries a purpose bill|deposit|plan_down|prepay; plan-down links to
#           its plan) · BR-PAY-015 (autopay v1 = capture INTENT, never a
#           charge) · BR-PAY-013 (NSF
#           — reversing row + reversed allocations; the ORIGINAL due date
#           stands) · BR-PAY-014 (refunds only from a real credit, Admin
#           approval, immutable row) · BR-PAY-021 (POSTING date ≠ CLEARING date
#           — always both) · BR-PAY-026 (method is a seeded, tenant-extensible
#           LOOKUP, not an enum) · BR-PAY-028 (idempotency: webhook_key UNIQUE;
#           key mechanics Eng-Lead 🔒) · BR-PAY-031 (reapply = reversing
#           allocation rows + new rows) · BR-PAY-037 (one user may initiate AND
#           approve in v1 — both acts recorded distinctly) · BR-TEN-035 (the
#           PMT- series allocates the number in-transaction) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money NUMERIC(18,6) + CHAR(3), never
#           float) · rule 4 (financial immutability) · rule 6 (idempotency)
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py ·
#           06-backend/tests/test_us_pay_009_nsf.py ·
#           06-backend/tests/test_us_pay_011_refunds.py ·
#           06-backend/tests/test_us_pay_002_purpose.py ·
#           06-backend/tests/test_us_pay_024_autopay_intents.py
# Impacts:  apps/payments/services.record_payment (the only inbound write path)
#           · apps/payments/reversal (writes the reversing rows) ·
#           apps/payments/refunds (writes `refunds`) ·
#           apps/payments/migrations/0001_w4_payment_core (this schema) ·
#           0002_rls_w4_and_immutability (the guarantees these classes cannot
#           give) · 0006_w4_reversal_and_refunds (the `refunds`
#           table, its RLS and its freeze; the reversal triple is applied by
#           0004 — see DEF-068) · apps/ledger/posting
#           (every cleared payment posts there, and reverse_entry unwinds it) ·
#           apps/billing (the invoices an allocation is written against)
# ───────────────────────────────────────────────────────
"""payments models — `payments` and `allocations`, from B2 §2 as redlined by
Addendum r12 (the PO-approved payments schema batch) and r14.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path
and both tables carry money. AI-authored 2026-08-11 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. This file implements signed schema and
invents none: every column below cites the line of B2 or of an addendum that
puts it there, and where signed law is silent the gap is an OQ, not a design
opportunity.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SLICE BUILDS — AND THE LONGER LIST OF WHAT IT DOES NOT
════════════════════════════════════════════════════════════════════════════
This is the **closed-loop foundation**: a payment can be recorded, allocated
against open bills, and posted to the books. That is two tables out of the
fourteen the payments module owns, and reading this file as "payments is built"
would be wrong in a way that costs a lane its afternoon.

NOT built here, each named with the epic that owns it:

  * `payment_methods` as B2 §2 spells it — the CUSTOMER's stored instrument
    (`brand_last4`, `is_autopay`). That is autopay's table (EP-PAY-07,
    BR-PAY-015) and it is not this. **The `payment_methods` TABLE NAME is
    already taken** by tenancy's seeded method LOOKUP (BR-TEN-036 / OQ-031
    closed the `payment_method_t` enum into a tenant-extensible table), which
    is what `Payment.method` points at — see the field's own note.
  * `write_offs` (EP-PAY-03) · `payment_plans` +
    `payment_plan_installments` (EP-PAY-05) · `deposit_batches` + `bank_lines`
    + the statement-import set (EP-PAY-06) · `payment_import_batches` +
    `payment_import_rows` (US-PAY-003) · `autopay_capture_intents` (EP-PAY-07)
    · collection state + `notice_history` (EP-PAY-04).
  * reapply (BR-PAY-031). The SCHEMA supports it — a reapply is a reversing
    allocation row plus a new one and both tables are append-only — but no
    service writes one.

**CORRECTED 2026-08-11 (hard-won law 1).** Until the NSF/refund lane this
docstring listed `refunds` among the tables that do not exist and said of NSF
(BR-PAY-013) and reversal (BR-PAY-011) that *"no service writes one"*. Both
sentences are now false: `Refund` is below, `payments` carries the three
reversal columns (`reverses_payment_id`, `reversal_reason`, `journal_entry_id`)
that migration 0004 applies (DEF-068 — a concurrent lane's
`makemigrations` swept them; the schema is right, the ownership is not), and `apps/payments/reversal.py` +
`apps/payments/refunds.py` are the services. What is STILL not built is named
in those two files' own docstrings rather than here, so one file owns each
claim: the NSF FEE line (BR-BIL-007 — billing owns the write and rating
publishes no charge-code read), `accounts.nsf_count` and the cash-only
privilege flag (customers' table, no seam, and the flag has no column at all),
and the collection-ladder re-entry (OQ-133).

════════════════════════════════════════════════════════════════════════════
THE TWO DATES ARE THE POINT (BR-PAY-021, r12 #1)
════════════════════════════════════════════════════════════════════════════
The PO ruled it explicitly on 2026-08-08 and it is the cardinal rule of this
module: **posting date ≠ clearing date, always both.**

    posted_at   when the RECORD entered the system. Billing consumes this one:
                a payment posted by the due date is ON TIME even if it clears
                later. USER-ENTERED, never the system clock (BR-PAY-033).
    cleared_at  when the MONEY was actually received. NSF, failure and bank
                reconciliation all hang off this one. NULL = still processing.

`received_at` — B2 §2's single pre-ruling date — is **deliberately not built**,
under the disposition B2 r14 #8 delegates by name (*"`received_at` vs
posted_at/cleared_at disposition = Eng-Lead 🔒"*). The PO's own words define
clearing as *"when money is actually received"*, so `received_at` and
`cleared_at` are two names for one fact; carrying both would put the same fact
in two columns and let one drift from the other, which is hard-won law 5 in
schema form. Recorded as a judgment call in 12-governance/02-decision-log.md.

════════════════════════════════════════════════════════════════════════════
IMMUTABILITY (hard rule 4) IS NOT ENFORCED BY THESE CLASSES
════════════════════════════════════════════════════════════════════════════
A Django model cannot refuse a `.save()`. The guarantee is the trigger pair in
`migrations/0002`, and it is stated here rather than claimed here — a model
docstring that promised immutability the schema did not have is precisely the
defect that produced hard-won law 1.

What 0002 enforces, so a reader of this file knows what the rows actually do:
a payment past `processing` accepts no UPDATE and no DELETE, ever; a payment
still `processing` may move only its `status` and `cleared_at`; an `allocations`
row accepts no UPDATE and no DELETE at any time (BR-PAY-031: reapply is
reversing rows plus new rows).

════════════════════════════════════════════════════════════════════════════
WHAT AN `allocations` ROW CANNOT SAY, AND WHY IT MATTERS (OQ-129)
════════════════════════════════════════════════════════════════════════════
B2 §2 gives `allocations` five columns — tenant, payment, invoice, amount, and
the timestamps — and **no line class**. Since the PO's ruling of 2026-08-11 an
allocation also has a WITHIN-invoice shape (usage+base → taxes → the
tenant-defined class → fees LAST), and the PO's stated reason for building that
breakdown was tax remittance: *how much of the tax on this bill has actually
been collected*. That figure is computed by `apps/payments/allocation.py` on
every allocation and **had nowhere to be stored**. It rode the `audit_log`
payload alone, which is a record and not a queryable position — and `audit_log`
is pruned on a retention schedule, so it was a record with an expiry date under
a tax filing. Raised as **OQ-129** rather than answered with an invented column.

⚠ **ANSWERED 2026-09-02 — `allocation_classes`, one child row per class**
(CR-060 C19 / task T7d, `payments/0015` + `0016`). The breakdown is now a stored,
queryable, append-only fact, and the collected-tax basis is READ from it instead
of being reported absent. **The two rulings that disagreed about a partial
payment's tax are not adjudicated by this** — C19 is explicit that recording the
breakdown *"makes the question moot"* rather than choosing a winner — because
whatever order a tenant sets, what the money actually met is written down
afterwards. The audit payload still carries it too, unchanged.
"""

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ── B2 §1 `payment_status` — SIX values since `CR-137-BRC07` ────────────────
# Not a lookup table: BR-TEN-036 turned the *tenant-extensible* enums into
# lookups (that is what happened to the METHOD, below) and this is not one of
# them. **A TENANT still cannot invent a payment state** — the immutability
# trigger, the ledger contract and the S33 action sets are all written against
# this tuple (A5 §Payment, flows §2), which is why it is closed at the database
# by `ck_payments_status`.
#
# ⚠ **THIS COMMENT READ *"the five values"* AND *"a tenant cannot invent a
# SIXTH payment state"* UNTIL 2026-09-23 (`CR-137-BRC07` `P3.5`), AND THE
# SECOND HALF WAS A CATEGORY ERROR RATHER THAN A STALE COUNT.** It fused two
# different facts: that the vocabulary is closed to TENANTS, which is still
# true and is the reason this is not a lookup, and the incidental number of
# values it happened to hold, which was never a rule. **`cancelled` is the
# sixth, added by the PLATFORM under the PO's approval of the payments
# blueprint phase 3** (2026-09-23, *"yes i like your plans lets do it"*) —
# the drawing's own words, p19: *"A sixth payment state … `ck_payments_status`
# is written against the five, so `cancelled` needs a migration that alters
# the CHECK."* Adding a value is a signed, platform-level act with a migration
# and a proof behind it; a tenant still cannot do it at all.
PAYMENT_PROCESSING = "processing"
PAYMENT_CLEARED = "cleared"
PAYMENT_FAILED = "failed"
PAYMENT_REVERSED = "reversed"
PAYMENT_POSTED = "posted"
#: ⚠ **A PAYMENT TAKEN BY MISTAKE, UNDONE BEFORE THE MONEY EVER SETTLED
#: (`CR-137-BRC07` `P3.5`/`P3.6`, `payments/0036`).** It is reachable from
#: `processing` and from nowhere else — a cleared payment is money that
#: arrived and is put right by a REVERSAL, never by a cancel.
#:
#: ⚠ **IT IS A FROZEN STATUS, AND THAT FOLLOWS RATHER THAN BEING CHOSEN
#: SEPARATELY.** `PAYMENT_FROZEN_STATUSES` below is *every status but
#: `processing`*, and `trg_payment_immutable` asks the same question as a
#: literal (`OLD.status <> 'processing'`), so the instant this value lands on
#: a row that row is append-only — no column may change but the two write-once
#: stamps and the three correctable references, and DELETE is refused in every
#: status. **Proved in both directions on PostgreSQL 16** by
#: `10-scripts/p3_cancel_state_and_trigger_readback.py`; nothing in the
#: default SQLite suite can show it (hard-won law 14).
PAYMENT_CANCELLED = "cancelled"
PAYMENT_STATUSES = (
    PAYMENT_PROCESSING,
    PAYMENT_CLEARED,
    PAYMENT_FAILED,
    PAYMENT_REVERSED,
    PAYMENT_POSTED,
    PAYMENT_CANCELLED,
)

#: B2 §1 `payment_type` — payment | credit | adjustment. Credits and
#: adjustments render as SIGNED rows on S33 (US-PAY-004 §5); whether the sign
#: lives on `amount` is B2's own O-4 residue and this slice writes only
#: `payment`, so nothing here depends on the answer.
PAYMENT_TYPE_PAYMENT = "payment"
PAYMENT_TYPE_CREDIT = "credit"
PAYMENT_TYPE_ADJUSTMENT = "adjustment"
PAYMENT_TYPES = (PAYMENT_TYPE_PAYMENT, PAYMENT_TYPE_CREDIT, PAYMENT_TYPE_ADJUSTMENT)

#: B2 Addendum r12 #2 / BR-PAY-012 — every payment carries a purpose, default
#: `bill`. All four values exist in the SCHEMA because the rule is CONFIRMED;
#: only `bill` has a write path in this slice (see services.record_payment,
#: which refuses the other three by name rather than pretending their linkage
#: happened).
PURPOSE_BILL = "bill"
PURPOSE_DEPOSIT = "deposit"
PURPOSE_PLAN_DOWN = "plan_down"
PURPOSE_PREPAY = "prepay"
PAYMENT_PURPOSES = (PURPOSE_BILL, PURPOSE_DEPOSIT, PURPOSE_PLAN_DOWN, PURPOSE_PREPAY)

#: The statuses past which the row is financial history (BR-PAY-002, B2 §3
#: *"payments (status<>'processing') … append-only"*). Named here so the model
#: layer, the service layer and the migration's trigger all read the same
#: sentence; the DATABASE is what enforces it.
#:
#: ⚠ **IT IS DERIVED, SO A NEW STATUS JOINS THE FROZEN SIDE BY DEFAULT AND
#: SILENTLY — WHICH IS WHY `P3.6` IS A PROOF TASK (`CR-137-BRC07`).** Adding
#: `cancelled` to the tuple above put it in here too, with no edit on this
#: line and no chance to think about it. That default is the RIGHT answer for
#: `cancelled` and it was checked rather than inherited: a cancelled payment
#: is a finished record of something that was taken and undone, and the next
#: status added might not want it. **Read `payments/0036`'s docstring before
#: adding a seventh.**
#:
#: ⚠ **AND THIS TUPLE IS NOT WHAT THE DATABASE READS.** `trg_payment_immutable`
#: (`payments/0002`, body currently from `payments/0033`) asks
#: `OLD.status <> 'processing'` as a **literal**, so the two agree by
#: construction rather than by a shared name — and a lane that changed this
#: derivation to exclude something would move the Python and leave the
#: database exactly where it was. The guarantee is the trigger; this is the
#: sentence the Python reads.
PAYMENT_FROZEN_STATUSES = tuple(s for s in PAYMENT_STATUSES if s != PAYMENT_PROCESSING)

# ── reversal reasons (S35 Reverse modal, EP-PAY-03 US-PAY-010 §5) ───────────
#: The four the prototype offers, verbatim. `nsf` is the one that routes to the
#: BR-PAY-013 machine (US-PAY-009); the other three are ordinary reversals.
#:
#: **This is NOT the lookup r14 #2 anchors.** B2 Addendum r14 #2 puts a
#: *"Reversal-reason lookup (reference data)"* in tenancy's seeded, extensible
#: family (BR-TEN-036), and tenancy has not built it. These four constants are
#: the PROTOTYPE's set held in code until that table exists, and the column is
#: plain text so the lookup can take it over without a data migration on the
#: reason values themselves. Reported in the reversal service's trailer rather
#: than left as a surprise for the lane that builds the lookup.
REVERSAL_REASON_NSF = "nsf"
REVERSAL_REASON_BANK_CHARGEBACK = "bank_chargeback"
REVERSAL_REASON_DATA_ENTRY_ERROR = "data_entry_error"
REVERSAL_REASON_CUSTOMER_DISPUTE = "customer_dispute"
REVERSAL_REASONS = (
    REVERSAL_REASON_NSF,
    REVERSAL_REASON_BANK_CHARGEBACK,
    REVERSAL_REASON_DATA_ENTRY_ERROR,
    REVERSAL_REASON_CUSTOMER_DISPUTE,
)

# ── refund status (B2 Addendum r2, WIDENED — see the Refund docstring) ──────
#: B2 r2's signed three. A refund that has been ISSUED has left the building:
#: a cheque is written or an ACH is queued, and the customer-credit account has
#: been drawn down.
REFUND_ISSUED = "issued"
REFUND_CLEARED = "cleared"
REFUND_VOID = "void"
#: The two states r12 #5's own columns require and r2 does not name. See the
#: `Refund` docstring for the argument; recorded as an Eng-Lead disposition in
#: 12-governance/02-decision-log.md, never as a silent widening.
REFUND_REQUESTED = "requested"
REFUND_APPROVED = "approved"
REFUND_STATUSES = (
    REFUND_REQUESTED,
    REFUND_APPROVED,
    REFUND_ISSUED,
    REFUND_CLEARED,
    REFUND_VOID,
)

#: BR-PAY-014 — *"check/ACH v1 (card refund with rails W7)"*. `card` is
#: deliberately ABSENT rather than present-and-refused: a value the column can
#: hold is a value some path can write, and the refusal a clerk sees names W7.
REFUND_METHOD_CHECK = "check"
REFUND_METHOD_ACH = "ach"
REFUND_METHODS = (REFUND_METHOD_CHECK, REFUND_METHOD_ACH)

# ── where the money came from (CR-132-BRC07 · CR-135-BRC07 P0.1) ────────────
#: The three values `payments.origin` may hold, spelled exactly as
#: `apps/payments/idempotency.py` spells the `<source>` segment of the
#: idempotency key. `ck_payments_origin` is the CHECK the payments blueprint's
#: `P0.1` asks for, and this tuple is where its vocabulary is written down once.
#:
#: ⚠ **THE BLUEPRINT NAMES THESE THREE `counter · digital · post` AND THE
#: STORED VALUES DELIBERATELY DO NOT MOVE.** PO ruling 2026-09-22, verbatim:
#: *"(a) One column — extend what we shipped — Rename or map the three values,
#: add the check the blueprint wants."* Both halves were offered; this is the
#: MAP, and the argument is in the decision log of 2026-09-22 under
#: *"THE SOURCE COLUMN KEEPS THE WORDS IT WAS BORN WITH"*. The short form is a
#: correctness point rather than a cost one: `transfer.py` writes `entry` for
#: **both legs of an internal transfer** and `reversal.py` writes it for a
#: bounce, and neither of those is money handed over at a counter. `entry`
#: says *a person keyed this row*, which is true of all of them; `counter`
#: would say *this was taken at a service desk*, which is false for three of
#: the five creation sites.
#:
#:     stored      the blueprint's word      what it means
#:     entry       Counter                   a person keyed it
#:     webhook     Digital                   it arrived over a wire
#:     import      Post                      it came in a file or a batch
#:
#: The right-hand column is a LABEL and belongs in the i18n catalogue with
#: every other label (B14 rule 31 — no database value is the visible value of
#: a field; `reversal_reason` already stores `bank_chargeback` and shows
#: *Bank chargeback*).
PAYMENT_ORIGIN_ENTRY = "entry"
PAYMENT_ORIGIN_WEBHOOK = "webhook"
PAYMENT_ORIGIN_IMPORT = "import"
#: ── THE FOURTH VALUE, AND IT IS A RULING'S CONSEQUENCE (`CR-174-BRC10`) ────
#: *A payment agent took it on the utility's behalf* — at a kiosk, a call
#: centre, on the agent's own web page or phone line — *and told us over the
#: wire.* US Payments (Prime) is the first.
#:
#: ⚠ **WHY NOT `webhook`, WHICH IS TRUE OF IT.** PO 2026-10-07 (D3), verbatim:
#: *"no; thUS payment is generleal integration we are doing and nothing to do
#: with Ann arbor"* — US Payments money must NOT enter `/partner/v1/receipts`
#: or the New World file, and that feed selects `origin = webhook` and is NOT
#: to be changed. `entry` (*a person keyed it*) and `import` (*a file or a
#: batch*) would both be false statements about this money. So the honest
#: answer is a fourth word, added to `ck_payments_origin` by `payments/0049`
#: — which is exactly what that CHECK exists to force: a new origin arrives
#: through a migration and a decision, never by an INSERT. Decision log
#: 2026-10-07, *"US PAYMENTS (PRIME) — THE BUILD'S OWN JUDGMENTS"* (J1).
PAYMENT_ORIGIN_AGENT = "agent"
#: `CR-174-BRC10` — where a customer stood when a payment AGENT took their
#: money. The specification's five words, lower-cased.
AGENT_CHANNELS = ("kiosk", "csr", "web", "ivr", "other")
AGENT_CHANNEL_OTHER = "other"
PAYMENT_ORIGINS = (
    PAYMENT_ORIGIN_ENTRY,
    PAYMENT_ORIGIN_WEBHOOK,
    PAYMENT_ORIGIN_IMPORT,
    PAYMENT_ORIGIN_AGENT,
)

# ── how a till was closed (CR-135-BRC07 P0.3) ───────────────────────────────
#: PO ruling 2026-09-22, verbatim: *"(b) A System Admin can close it, recorded
#: as a forced close"* — the answer to Dana, who opened a till on Monday at
#: 08:00, took **$1,240 in cheques**, went home at 17:00 without closing it and
#: was off sick on Tuesday.
#:
#: Two values, and the pair exists so the two PEOPLE stay distinguishable for
#: ever: on a forced close somebody other than the owner seals a drawer the
#: owner is accountable for, and `closed_by` is then not `owner`.
#:
#: ⚠ **A THIRD VALUE, `system`, ARRIVED WITH `P0.6` (CR-135-BRC07, 2026-09-22)
#: AND IT IS NOT A THIRD WAY A PERSON SEALS A DRAWER.** PO ruling of that date,
#: verbatim: *"we have to make process uniform for all hence we should geneate
#: system generated till"*. Four of the seven tenders — ACH, card, wire and
#: lockbox — never touch a counter, and `P0.6`'s guard is one sentence with no
#: tender-by-tender exception: **a deposit batch has a session.** So the money
#: that never passed through anybody's hands banks under a till that is openly
#: nobody's.
#:
#: **A system till has NO owner, NO service centre and NO closer**, and that is
#: the PO's own *"tell them apart by what they lack"* shape applied one step
#: on: pointing one at a real user would record that that person ran a till
#: they never sat at, which is exactly the invention the PO rejected as option
#: (b) for the legacy batches. `deposit_batch_events.actor` has said NULL = *a
#: job did this* since W5, so the vocabulary is already the module's.
#:
#: It is **born closed**, which is what keeps it off the *"who has not counted
#: their drawer"* list without that screen needing to know it exists —
#: `ix_counter_sessions_open` asks `closed_at IS NULL` and a system till never
#: answers. It is therefore never force-closed either: there is nothing open to
#: force and nobody to force it for.
COUNTER_CLOSE_COUNTED = "counted"
COUNTER_CLOSE_FORCED = "forced"
COUNTER_CLOSE_SYSTEM = "system"
COUNTER_CLOSE_KINDS = (COUNTER_CLOSE_COUNTED, COUNTER_CLOSE_FORCED, COUNTER_CLOSE_SYSTEM)
#: The two kinds a PERSON's till can be sealed with. Phase 2's counter screens
#: offer these; `system` is not on the list because a clerk cannot choose it.
COUNTER_CLOSE_KINDS_BY_A_PERSON = (COUNTER_CLOSE_COUNTED, COUNTER_CLOSE_FORCED)


class Payment(models.Model):
    """One payment (B2 §2 `payments`, as redlined by r12 #1/#2/#13 and r14 #4).

    **Append-only once out of processing** (BR-PAY-002 / hard rule 4). A
    reversal, an NSF and a reapply are all NEW rows; nothing edits this one.
    The trigger in `migrations/0002` is the guarantee — this class is not.

    Columns and where each comes from:

    * `account` — B2 §2, and one of the reviewed cross-module FKs (B2 §2's
      interface set: *account 1:N payments*).
    * `type` / `amount` / `currency` / `status` / `confirmation` /
      `webhook_key` — B2 §2 verbatim.
    * `method` — B2 §2 types it `payment_method_t`, an ENUM that no longer
      exists: r5 #20 and r16 #3 swapped the tenant-extensible enums for seeded
      LOOKUP tables (BR-TEN-036, OQ-031 closed), and BR-PAY-026's six seeds
      live in `tenancy.PaymentMethod`. Nullable exactly as B2 leaves it — a
      credit or an adjustment row carries no instrument.
    * `purpose` — r12 #2 / BR-PAY-012.
    * `posted_at` / `cleared_at` — r12 #1. See the module docstring.
    * `memo` — r14 #4.
    * `payment_no` — r12 #13 anchors the tenant PMT- series and EP-PAY-01 §5
      maps it here (*"minted at record, unique per tenant"*). NULLABLE with a
      PARTIAL unique index, the same shape and the same reason as
      `uq_invoices_no`: a unique index over a column that can legitimately be
      absent has to be partial, and the absence is real — a future import path
      that cannot reach the series must fail loudly rather than collide with
      every other numberless row. `services.record_payment` always mints one.
    * `deposit_batch_id` — B2 §2 declares this an FK to `deposit_batches`, a
      table EP-PAY-06 owns and this slice does not build. Shipped as a plain
      uuid column under the B11 F-3 deferred-FK convention, exactly as
      `invoice_lines.gl_account_id` waited for `ledger_accounts`. **Nothing
      writes it here**, and the trigger in 0002 does not open a door for it —
      the lane that builds batches opens that door deliberately and proves it
      RED first (see 0002's docstring, which names this).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    payment_no = models.TextField(null=True, blank=True)  # r12 #13, PMT- series
    type = models.TextField(default=PAYMENT_TYPE_PAYMENT)
    method = models.ForeignKey(  # r5 #20 swap: the lookup replaces B2's enum column
        "tenancy.PaymentMethod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="method_id",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3, never a float
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), hard rule 2
    status = models.TextField(default=PAYMENT_PROCESSING)
    purpose = models.TextField(default=PURPOSE_BILL)  # r12 #2 / BR-PAY-012
    confirmation = models.TextField(null=True, blank=True)  # check / confirmation #
    memo = models.TextField(null=True, blank=True)  # r14 #4
    #: ── the cheque, as a thing rather than as free text (CR-059 CS-30) ─────
    #: *"There is no cheque in this system. A cheque is an ordinary payment
    #: whose tender is `check` and whose number is typed into a free-text
    #: reference field."* These two give it a DATE and a DRAWER; its NUMBER
    #: stays in `confirmation` and that is deliberate — `confirmation` is one of
    #: the exactly three columns the PO opened to correction on 2026-09-02
    #: (hard rule 4, `payments/0014`), so a mistyped cheque number is fixable
    #: through `POST /payments/{id}/correct-reference` today. A fourth column
    #: holding the number would be a number nobody could ever correct, which is
    #: the very defect CS-34 was written for.
    #:
    #: Both NULL on every payment that is not a cheque. `cheque_date` being set
    #: is what makes a row a STRUCTURED cheque — `cheques.py` keys off it — and
    #: the service refuses a cheque date with no drawer bank, so the pair is
    #: never half-recorded.
    cheque_date = models.DateField(null=True, blank=True)
    drawer_bank = models.TextField(null=True, blank=True)
    #: The day this cheque may be BANKED (CR-059 CS-30's fourth rule: *"a cheque
    #: dated in the future is held out of the batch cut until its date, and
    #: named on the day it becomes bankable"*). NULL means bankable now, which
    #: is every cheque handed over dated today or earlier and every other tender.
    #:
    #: ⚠ It is NOT `cheque_date` under another name and must not be derived from
    #: it here: a utility may agree to hold a cheque past its own date, and a
    #: cheque dated last week is bankable today. The batch cut reads THIS column
    #: and nothing else, so the hold is one stated fact rather than an inference
    #: two places could make differently.
    bankable_from = models.DateField(null=True, blank=True)
    #: BR-PAY-021 — the record entered the system. NOT NULL: a payment with no
    #: posting date cannot be judged on-time, and billing consumes exactly this
    #: column. User-entered (BR-PAY-033), never a clock.
    posted_at = models.DateTimeField()
    #: BR-PAY-021 — the money actually arrived. NULL while processing.
    cleared_at = models.DateTimeField(null=True, blank=True)
    #: B2 §2 FK to `deposit_batches` (EP-PAY-06). Deferred-FK per B11 F-3.
    deposit_batch_id = models.UUIDField(null=True, blank=True)
    # ── WHICH TILL TOOK THIS MONEY (CR-136-BRC07 `P2.4`, `payments/0035`) ───
    #: The `counter_sessions` row this payment was taken into — one person's
    #: drawer, for one shift, at one counter window.
    #:
    #: ⚠ **NULLABLE, AND IT STAYS NULLABLE — PO RULING 2026-09-23.** Verbatim:
    #: *"(a) Refuse it. \"Start your counter first.\" One press, then take the
    #: money. It is the only option where every cash dollar belongs to
    #: somebody"*. **Three of the seven tenders pass through a person's hands
    #: — `cash`, `check`, `money_order` — and only those three are refused
    #: without an open till.** ACH, card, wire and lockbox never touch a
    #: counter, so a `NOT NULL` here would refuse **every one of those rows in
    #: the product**. The rule is *these three tenders, recorded by hand, need
    #: a till*, which is a SERVICE rule with four tenders' worth of exception
    #: and cannot be spelled as a column constraint (`BR-SHL-025` — the
    #: take-payment endpoint refusing is the enforcement, never a hidden
    #: button).
    #:
    #: ⚠ **IT IS NOT THE SAME QUESTION AS *which till did this money BANK
    #: under*.** That one is `deposit_batches.session` and is answered for
    #: EVERY payment, because `reconciliation._session_for` falls back to the
    #: day's system till — a till openly nobody's — for the four electronic
    #: tenders. This column is the narrower fact: *somebody's drawer held this*.
    #: Phase 2 changes `_session_for` to prefer THIS value and to go on
    #: answering the system till when it is NULL.
    #:
    #: ⚠ **A PLAIN UUID RATHER THAN A ForeignKey, AND THE BLUEPRINT'S STATED
    #: REASON FOR THAT IS WRONG — SEE `payments/0035` AND `DEF-PAY-6219`.**
    #: The drawing's outcome sentence reads *"A payment names its till. No ORM
    #: edge into another module"* and cites `B11 F-3`. **Neither applies.**
    #: `counter_sessions` is a PAYMENTS table (`apps/payments/
    #: counter_session_models.py`), so there is no module boundary to cross;
    #: and B11 F-3 is about a FORWARD FK breaking migration order, while
    #: `counter_sessions` has existed since `payments/0031` and this column
    #: arrives at `0035`. **The reason that does apply is the sibling column
    #: directly above**: `deposit_batch_id` answers the same *which container
    #: did this money land in* question about the same rows, is read beside
    #: this one on the same list (`P2.8`'s Source and Batch columns) and is a
    #: plain uuid. Two columns answering one question in two shapes is the
    #: *two places that can disagree* shape this module keeps filing.
    #:
    #: ⚠ **WHAT THAT COSTS, STATED RATHER THAN LEFT TO BE DISCOVERED: THERE IS
    #: NO REFERENTIAL INTEGRITY HERE.** Nothing in the database refuses a
    #: payment naming a till id that does not exist, and nothing stops a
    #: `counter_sessions` row being deleted out from under one — exactly as is
    #: already true of `deposit_batch_id`. The service that writes it is the
    #: only guard, and `P2.13` is the test that it writes the till the money
    #: was TAKEN at rather than the one that happened to be open at close.
    counter_session_id = models.UUIDField(null=True, blank=True)
    # ── WHICH PAYOUT CARRIED THIS MONEY (CR-139-BRC07 `P5.6`, `payments/0038`) ─
    #
    # ⛔ ═══ THE COLUMN THAT WAS HERE IS DROPPED — `payments/0044`,
    # `OQ-PAY-12608`, PO ruling 2026-09-24 ══════════════════════════════════
    # PO, verbatim: *"p7 (b) — nothing is lost, and the payment-row lock stays
    # exactly as it is"*. `settlement_id = models.UUIDField(null=True,
    # blank=True)` stood at the end of this block. **The whole of the reasoning
    # for it is kept below**, because a reader who meets `P5.6` in the
    # blueprint (p024, *"Null is Awaiting settlement"*) needs to find out why
    # the column is not here — and because that reasoning was sound and the
    # column still had to go.
    #
    # **Nothing could ever write it.** `payments_payment_immutable()` compares
    # a payment's whole row minus a short allow list, and `payments/0005`'s own
    # comment says *"a column added later is frozen the day it is created"* —
    # so it was settable only at INSERT, and a payout arrives after the row
    # exists. Measured on PostgreSQL 16.13, in every status, before anything
    # was written. Hard rule 4 says widening that allow list is a new PO
    # ruling; the PO dropped the column instead, and **the lock did not move**.
    #
    # **Nothing is lost.** `settlement_members` is the record;
    # `uq_settlement_members_payment` carries the same *at most one payout per
    # payment* rule, with the referential integrity this column never had; and
    # `settlements.awaiting_settlement_filter()` already answered the third
    # state from it, because the pointer was never readable either.
    # `test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone` is the
    # standing guard that it does not come back.
    # ═══════════════════════════════════════════════════════════════════════
    #
    # The `settlements` row this payment was paid out inside — one bank credit
    # from one processor, covering many payments, net of its fee.
    #
    # ⚠ **NULL IS A REAL STATE AND IT HAS A NAME: *Awaiting settlement*.** The
    # blueprint calls it *"the third state the requirement never named, made
    # real"*, and it is the commonest value in the table by a long way — every
    # payment taken at a counter, imported from a lockbox file or paid by
    # cheque is null here **forever**, because nobody pays those out to us. A
    # `NOT NULL` would refuse most of the product's rows, and a screen reading
    # this column must draw three states rather than two.
    #
    # ⚠ **A PLAIN UUID RATHER THAN A ForeignKey, AND THE REASON IS THE SIBLING
    # COLUMNS ABOVE — NOT A MODULE BOUNDARY.** `settlements` is a PAYMENTS
    # table (`apps/payments/settlement_models.py`), so nothing is crossed, and
    # it arrives in the same migration as this column so there is no order to
    # break either (B11 F-3 is about migration ORDER, which is `DEF-PAY-6219`'s
    # finding about the blueprint's stated reason for `counter_session_id`).
    # **What does apply is consistency**: `deposit_batch_id` and
    # `counter_session_id` answer the same *which container did this money land
    # in* question about the same rows and are both plain uuids, and a lane
    # holding a `Payment` with `.settlement` traversable and `.deposit_batch_id`
    # not would read that difference as meaning something.
    #
    # ⚠ **IT IS A DENORMALISED POINTER AND `settlement_members` IS THE RECORD.**
    # The membership carries the per-payment gross and fee; this column exists
    # so the payments list can print *Awaiting settlement* without a join. Two
    # places holding one fact can disagree, so there is exactly ONE writer —
    # `settlements.ingest_payout`, which writes both inside one transaction —
    # and `test_cr139_p5_2_pointer_and_member_agree` asserts they never differ.
    # There is **no referential integrity** here, exactly as there is none on
    # the two columns above; if that ever bites, the fix is an FK on all three
    # together rather than on this one alone.
    #: B2 §2 — inbound idempotency (hard rule 6, DB-12). The shape of the
    #: string is `apps/payments/idempotency.py`; the uniqueness is below.
    webhook_key = models.TextField(null=True, blank=True)
    # ── WHERE THIS MONEY CAME FROM (CR-132-BRC07, `payments/0029`) ──────────
    #: `entry` · `webhook` · `import` — the three ways a payment enters this
    #: product: a clerk typed it, a rail told us, or it arrived in a file.
    #:
    #: ⚠ **IT WAS A PREFIX INSIDE THE IDEMPOTENCY KEY UNTIL 2026-09-22 AND
    #: THAT IS WHY IT IS NOW A COLUMN** (PO ruling of that date, asked whether
    #: to filter the New World feed on it: *"or we might have to save the
    #: source seprately - and make it available to import and entry also"*).
    #: Three reasons, and none of them is tidiness:
    #:
    #:   1 **the key's job is preventing duplicates, not reporting.** Reading
    #:     `webhook_key.split("|")[0]` gives one field two meanings, and the
    #:     next person to change the key shape breaks a report nobody
    #:     connected to it. `webhook_key` is also NULL on every payment
    #:     recorded without an idempotency reference, so the derivation is
    #:     silently wrong for those rather than absent.
    #:   2 **there were already TWO half-answers** — the key prefix and
    #:     `payment_import_batches.source_kind` — which is the *two places
    #:     that can disagree* shape this product keeps meeting.
    #:   3 **counter and lockbox need it as much as online does.** Every
    #:     reconciliation question starts with *where did this money come
    #:     from*.
    #:
    #: ⚠ **WRITE-ONCE AT CREATION. Hard rule 4 — nothing updates it
    #: afterwards**, and `POST /payments/{id}/correct-reference` does not
    #: touch it: that endpoint's allow list is exactly `confirmation`, `memo`
    #: and `method_id` and widening it is a new ruling, not this one.
    origin = models.TextField(null=True, blank=True)
    #: ⚠ **TRUE WHEN THE VALUE WAS DERIVED BY THE BACKFILL RATHER THAN
    #: OBSERVED AT CREATION, AND IT IS HALF THE RULING.** PO 2026-09-22: the
    #: backfill *"is a DERIVATION, not an observed fact, and must be marked as
    #: one"*. Rows written before `payments/0029` took their origin from the
    #: key prefix where one existed and `entry` otherwise — a good guess and
    #: **not a record of what happened**. A report that cannot tell the two
    #: apart is a report that quietly presents an inference as evidence.
    #:
    #: Every row created since the migration carries `False`, written by the
    #: same statement that writes `origin`.
    origin_is_derived = models.BooleanField(default=False)
    # ── the reversal triple (migration 0004) ────────────────────────────────
    #: EP-PAY-03 US-PAY-009 §5, verbatim: the reversing row *"references
    #: original"*. B2 §2 gives `payments` no such column, and the DDL is
    #: delegated by name (r12 #17 / r14 #9 *"Exact DDL = Eng-Lead 🔒"*), so this
    #: implements a signed requirement rather than inventing one. A SELF-FK, so
    #: the pair lives in one table exactly as BR-PAY-002 describes it — *"a
    #: reversal = new reversing row"*, not a second table.
    #:
    #: `uq_payments_reverses` (below) makes it UNIQUE per tenant: **a payment is
    #: reversed ONCE.** That is the second of this flow's two idempotency
    #: guards and it catches a DIFFERENT fact from `webhook_key` — the key
    #: dedupes the same bank ADVICE arriving twice, this dedupes the same
    #: PAYMENT being bounced twice under two different advice ids. Both are
    #: asserted separately (tests/test_us_pay_009_nsf.py) because DEF-058 is
    #: what happens when one guard silently stands in for another.
    reverses_payment = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="reverses_payment_id",
        related_name="reversals",
    )
    #: One of `REVERSAL_REASONS`. Plain text, not an FK: the lookup r14 #2
    #: anchors is tenancy's and does not exist. See the constants above.
    reversal_reason = models.TextField(null=True, blank=True)
    #: ── THE BANK'S OWN RETURN CODE (`CR-174-BRC10`, `payments/0049`) ────────
    #: The Nacha code a payment agent's return notification carries — `R01`,
    #: `R02`, `R10` — kept BESIDE `reversal_reason` rather than in it, because
    #: `REVERSAL_REASONS` is a closed four-word set that decides what a bounce
    #: DOES (an NSF counts toward cash-only; a chargeback does not) and a
    #: bank's code is a fact about what the bank SAID. Widening the four words
    #: to Nacha's sixty-odd would turn a behaviour switch into a free-text
    #: column. HUMAN-REVIEW-PENDING (a 🔒 payments migration).
    #:
    #: ⚠ **ONLY ON A REVERSING ROW, AND THE DATABASE SAYS SO**
    #: (`ck_payments_return_code_on_reversal`). Written by the INSERT that
    #: creates the reversing row and by nothing else: it is on neither of
    #: `payments/0014`'s allow lists, so the immutability trigger refuses any
    #: later UPDATE (hard rule 4). NULL on every other row, and on a return
    #: that arrived without a code — which is a real answer, not a gap.
    return_code = models.TextField(null=True, blank=True)
    #: ── WHERE THE CUSTOMER WAS, WHEN AN AGENT TOOK IT (`CR-174-BRC10`) ──────
    #: `kiosk` · `csr` · `web` · `ivr` · `other` — one of `AGENT_CHANNELS`, and
    #: an agent's word nobody listed is `other` rather than a refusal (*"unknown
    #: → OTHER, never refuse"*). `terminal` is the agent's own machine number
    #: (`4471`), text because it is an identifier and not a quantity. Both NULL
    #: on every payment no agent took. Written at INSERT and frozen after, like
    #: every column outside `payments/0014`'s two allow lists (hard rule 4).
    #: The agent's raw message, kept whole on `payment_webhook_events.body`, is
    #: the record; these are what the payment's own page shows.
    channel = models.TextField(null=True, blank=True)
    terminal = models.TextField(null=True, blank=True)
    #: ── THE STORE PAYMENT NETWORK A FILE ROW NAMED (`payments/0054`) ───────
    #: PO 2026-10-30, Q6, verbatim: *"can you add network name as part of csv
    #: file / excel file do not add it on screen"*. The name (`Hy-Vee`,
    #: `CheckFreePay`) comes from the payments import's **Network** column and
    #: from nowhere else — no screen field writes it. A payment carrying one
    #: banks in that network's own daily deposit batch
    #: (`reconciliation.channel_for(network=…)` → `store:hy-vee`) and reads
    #: *"Store · Hy-Vee"* on the list and the payment page. NULL on every other
    #: payment, a lockbox row included, which keeps today's channel. A NAME, not
    #: an address or a person (hard rule 8, no PII). Written at INSERT and frozen
    #: after, like every column outside `payments/0014`'s allow lists (hard
    #: rule 4 — the trigger compares `to_jsonb(OLD)` whole, so a new column is
    #: frozen without touching the trigger).
    store_network = models.TextField(null=True, blank=True)
    #: ── PART of a payment came back (CR-059 CS-33, `payments/0019`) ────────
    #: True when this reversing row takes back LESS than the payment it
    #: reverses. It exists for the CONSTRAINT and not for a screen: a partial
    #: unique index over full reversals only (`uq_payments_full_reverses`) is
    #: what replaces `uq_payments_reverses`, so a payment may still carry at
    #: most ONE whole-amount reversal while carrying several partial ones.
    #:
    #: ⚠ **IT IS DERIVED AT INSERT AND NEVER READ AS THE TRUTH.** How much has
    #: been reversed is always Σ over the reversing rows — `reversal.
    #: reversed_so_far` — and this flag is a fact about ONE row, written by the
    #: one writer that creates it. A reader that trusted it instead of the sum
    #: would be one boolean away from letting a payment be reversed twice over.
    is_partial_reversal = models.BooleanField(default=False)
    #: ── the correction link (`CR-137-BRC07` `P3.7`, `payments/0037`) ───────
    #: The payments blueprint p19, verbatim: *"A self FK — the mirror of
    #: `reverses_payment`"*, outcome *"An adjustment names what it corrects
    #: instead of being related only in a clerk's memory."*
    #:
    #: **It is `reverses_payment`'s shape exactly** — `"self"`, `PROTECT`,
    #: nullable, `db_column` spelled out, a plural `related_name` — and it is
    #: NOT `reverses_payment`'s meaning. The pair below is the whole
    #: distinction and it is written out because a reader who conflates them
    #: will double-count money:
    #:
    #:   * **A REVERSAL takes money back.** It is a new row of the opposite
    #:     sign, it posts to the ledger, and the account balance moves.
    #:     `uq_payments_full_reverses` makes it at most ONCE per payment.
    #:   * **A CORRECTION says the same money was recorded wrongly.** The
    #:     original stands untouched — `P3.15` asserts it comes back
    #:     BYTE-IDENTICAL — and this column on the new row names the one it
    #:     puts right.
    #:
    #: ⚠ **AND THERE IS DELIBERATELY NO UNIQUE CONSTRAINT HERE, WHICH IS THE
    #: ONE PLACE THE MIRROR STOPS.** `payments/0014`'s own reasoning: *"a clerk
    #: who mistypes twice must be able to correct twice; a write-once reference
    #: would make the second typo permanent, which is the very failure CS-34
    #: was written about."* A payment is reversed once and may be corrected any
    #: number of times, so `uq_payments_full_reverses` has no counterpart and
    #: `ix_payments_corrects` (below) carries the reverse walk instead.
    #:
    #: ⚠ **IT IS WRITTEN AT INSERT AND NEVER UPDATED, SO HARD RULE 4's ALLOW
    #: LIST DOES NOT MOVE FOR IT** — the same sentence `moved_from_payment`
    #: already carries, and for the same reason: that allow list is about
    #: UPDATE and this column never takes one. `P3.8` is the guard.
    corrects_payment = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="corrects_payment_id",
        related_name="corrections",
    )
    #: ── money that arrived from ANOTHER account (CR-059 CS-8 + CS-32) ──────
    #: CS-32's *"Data. One nullable column on `payments` linking a moved payment
    #: to the one it came from. No change to any signed contract."* One column
    #: serves BOTH cross-account changes because both are the same fact from the
    #: receiving side — *this money was on another account a moment ago*:
    #:
    #:   * **CS-32 · a MOVED PAYMENT.** The source leg is a reversal of the
    #:     original (`reverses_payment` set, reason `data_entry_error`) and this
    #:     column on the destination row names the ORIGINAL — never the reversing
    #:     row — so S21 can render *"moved from PMT-…"* against the number the
    #:     customer was actually given.
    #:   * **CS-8 · a CREDIT TRANSFER.** The source leg is a new negative row and
    #:     this column on the destination row names it, so the pair is walkable
    #:     from either end (`related_name="moved_to"`).
    #:
    #: NULL on every payment that was recorded where it belongs, which is nearly
    #: all of them. It is written at INSERT and never updated, so hard rule 4's
    #: trigger allow-list (`payments/0014`, three columns and no more) does not
    #: move for it — that allow-list is about UPDATE and this column never takes
    #: one.
    moved_from_payment = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="moved_from_payment_id",
        related_name="moved_to",
    )
    #: ── the plan link (US-PAY-002 / BR-PAY-012, migration 0009) ────────────
    #: *"plan-down links to its plan"*. B2 §2 gives `payments` no such column
    #: and the field map records the gap as **P-12** (*"payment → plan/
    #: installment linkage columns … need their r12/Eng-Lead anchor named"*), so
    #: this implements a CONFIRMED rule under the standing *"Exact DDL =
    #: Eng-Lead 🔒"* delegation (r12 #17 / r14 #9) rather than inventing one.
    #:
    #: A real FK, not a deferred uuid: `payment_plans` is this module's own
    #: table (0007), so there is no boundary to defer across. NULL on every
    #: payment that is not a plan down payment — which is nearly all of them.
    plan = models.ForeignKey(
        "payments.PaymentPlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="plan_id",
        related_name="payments",
    )
    #: ── the ONE cheque this payment was part of (CR-059 CS-12 + CS-27) ────
    #: CS-12's *"Data. One new table plus RLS, and a **nullable** tender link on
    #: `payments`. The payment row is otherwise untouched — same immutability,
    #: same audit, same batch behaviour."*
    #:
    #: NULL on every payment somebody handed over on its own, which is nearly all
    #: of them. Set, it says *this money arrived as part of one tender that
    #: settled several accounts* — so S21 renders one cheque as one cheque and
    #: S33 groups the parts instead of showing three unrelated payments.
    #:
    #: **WRITTEN AT INSERT AND NEVER AFTERWARDS**, the same rule and the same
    #: reason as `moved_from_payment` and the three cheque columns: hard rule 4's
    #: trigger (`payments/0002`) refuses every column change on a row that is not
    #: `processing`, and the 2026-09-02 narrowing opened exactly `confirmation`,
    #: `memo` and `method_id` (`payments/0014`) — this column is not among them
    #: and does not need to be. A tender link written a statement later would be
    #: refused on every cleared payment, which is nearly all of them.
    tender = models.ForeignKey(
        "payments.PaymentTender",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="tender_id",
        related_name="payments",
    )
    #: The journal entry this payment left (B11 F-3 deferred-FK convention, the
    #: same shape as `deposit_batch_id` — `journal_entries` is the ledger's
    #: table and payments carries no import edge into it).
    #:
    #: **WRITE-ONCE, and it is the reason the NSF flow can exist at all.**
    #: `apps/ledger/posting.reverse_entry` — the mirror this product must use
    #: rather than hand-composing a compensating entry — takes an ENTRY ID, and
    #: the ledger publishes no read that turns a posting key or a source
    #: reference back into one. Without this column a bounce three weeks later
    #: has no way to name the entry it must unwind. `migrations/0002`'s own
    #: docstring names the shape used here: *"narrows it to write-once (the
    #: shape `ledger/0002` uses for `auto_reverse_entry_id`), and proves it RED
    #: first"* — NULL → set, once, and never re-pointed or cleared.
    journal_entry_id = models.UUIDField(null=True, blank=True)
    #: ── the utility's OWN fields, captured at entry (CR-161-BRC10 W5) ──────
    #: PO 2026-10-02, R3: *"Payments IN as capture-at-entry only"*, and Part 2
    #: row 14: *"Can't be corrected afterwards; never used to apply the payment
    #: to bills"*. A cashier answers e.g. *Drawer = 2* on Record payment (S35)
    #: and Payment detail (S33) shows it read-only.
    #:
    #: **WRITTEN AT INSERT AND NEVER AFTERWARDS**, for the reason every other
    #: write-once column on this row gives: the trigger compares the WHOLE row
    #: minus `payments/0014`'s allow list, this column is not on it and is not
    #: added to it, so a later UPDATE is refused in every status. **No
    #: allocation, deposit, refund, dunning or ledger path reads it**
    #: (BR-TEN-048) — G6 / DB-17 permits the token in this module only on the
    #: capture and display statements it names. `payments/0046` adds it.
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        constraints = [
            # B2 §2 `UNIQUE (tenant_id, webhook_key)` — "dedupe double webhook
            # delivery". Written literally: Postgres and SQLite both treat NULLs
            # as distinct, so the many rows carrying no key coexist without a
            # partial predicate and the signed DDL needs no deviation.
            models.UniqueConstraint(
                fields=["tenant", "webhook_key"], name="uq_payments_webhook_key"
            ),
            # r12 #13 — the PMT- number is unique per tenant. Partial, because
            # the column is nullable; see the class docstring.
            models.UniqueConstraint(
                fields=["tenant", "payment_no"],
                condition=Q(payment_no__isnull=False),
                name="uq_payments_no",
            ),
            # A typo'd status is a payment no action set can render and no
            # immutability trigger can classify — the same class of hole
            # `ck_journal_lines_side` closes for a journal line's side.
            #
            # ⚠ **SIX VALUES SINCE `payments/0036` (`CR-137-BRC07` `P3.5`).**
            # `cancelled` joined the tuple and this line did not move, because
            # the condition names the tuple rather than spelling the values —
            # which is the shape that made a sixth state one migration rather
            # than a hunt through the file.
            #
            # ⚠ **THE `DEF-PAY-6207` QUESTION, ASKED AND ANSWERED HERE RATHER
            # THAN ASSUMED.** A CHECK refuses a row only when its expression is
            # FALSE and **passes when the expression is NULL**, and this one
            # renders as `status = ANY (ARRAY[…])`, which is NULL for a NULL
            # status. **What closes that door is the COLUMN, not this
            # constraint:** `status` is `models.TextField(default=…)` with no
            # `null=True`, so PostgreSQL carries `attnotnull` on it and a NULL
            # never reaches the expression. That is asserted, by reading
            # `pg_attribute.attnotnull` back, in
            # `10-scripts/p3_cancel_state_and_trigger_readback.py` §1 — because
            # a door held shut by something OTHER than the guard you are
            # looking at is exactly the arrangement that breaks quietly when
            # somebody makes the column nullable for an unrelated reason.
            models.CheckConstraint(
                condition=Q(status__in=PAYMENT_STATUSES), name="ck_payments_status"
            ),
            models.CheckConstraint(condition=Q(type__in=PAYMENT_TYPES), name="ck_payments_type"),
            models.CheckConstraint(
                condition=Q(purpose__in=PAYMENT_PURPOSES), name="ck_payments_purpose"
            ),
            # ── P0.1, the payments blueprint's source CHECK (CR-135-BRC07) ──
            # *"A text column with a CHECK over counter | digital | post"* —
            # served over the values this column actually stores; see
            # `PAYMENT_ORIGINS` for why the words did not move.
            #
            # **NULL PASSES, AND THAT IS MEASURED RATHER THAN ASSUMED.** `P0.2`
            # asks for NOT NULL. `apps/integrations/management/commands/
            # seed_partner_morning.py:232` bulk-creates `Payment` rows and
            # passes no origin at all — a SIXTH creation site, where
            # `payments/0029`'s docstring counts four — so NOT NULL would fail
            # that command's INSERT on the day it was added. `DEF-PAY-6196`
            # holds it. The honest reading of a NULL here is *nobody told us*,
            # which is a real answer; a DEFAULT would turn it into a claim.
            #
            # What `P0.2`'s *"fails loudly rather than defaulting"* buys is the
            # FOURTH VALUE, and that is what this refuses: an INSERT of
            # `'cheque'` or `'lockbox'` is rejected by name, by the database,
            # on every path, rather than landing as an origin no filter can
            # find and no reconciliation can classify.
            models.CheckConstraint(
                condition=Q(origin__in=PAYMENT_ORIGINS) | Q(origin__isnull=True),
                name="ck_payments_origin",
            ),
            # ⚠ **`origin_is_derived` IS HALF THE PO's RULING AND THIS IS WHAT
            # KEEPS IT MEANINGFUL.** *TRUE* means *we inferred this*; with no
            # origin at all there is nothing to have inferred, so
            # `origin IS NULL AND origin_is_derived` is a row claiming to have
            # guessed nothing. It is refused rather than left as a state a
            # report would have to learn to ignore.
            models.CheckConstraint(
                condition=Q(origin__isnull=False) | Q(origin_is_derived=False),
                name="ck_payments_origin_derived_needs_a_value",
            ),
            # `CR-174-BRC10` — a bank's return code belongs to the row that
            # records the return, never to the payment that bounced (hard rule
            # 4 would freeze it there anyway) and never to an ordinary receipt.
            models.CheckConstraint(
                condition=Q(return_code__isnull=True) | Q(reverses_payment__isnull=False),
                name="ck_payments_return_code_on_reversal",
            ),
            models.CheckConstraint(
                condition=Q(channel__isnull=True) | Q(channel__in=AGENT_CHANNELS),
                name="ck_payments_agent_channel",
            ),
            # ⚠ **A payment is FULLY reversed once (CR-059 CS-33,
            # `payments/0019`). This constraint was `uq_payments_reverses` and
            # permitted exactly ONE reversal of any size** — which is what made
            # partial reversal impossible, and which CS-33 names as its own
            # blocker: *"the blocker is not the arithmetic, it is the index."*
            #
            # It is NARROWED rather than dropped. Every bounce that exists today
            # is a full reversal and is governed exactly as it was; what becomes
            # possible is a payment carrying several PARTIAL reversals summing
            # to no more than itself.
            #
            # **THE SUM IS NOT ENFORCED HERE AND CANNOT BE.** A unique index
            # cannot add up rows, so BR-PAY-884's total is the plpgsql trigger
            # `trg_payment_reversal_sum` (`payments/0019`) plus the service's own
            # `SELECT … FOR UPDATE` — two independent guards on one arithmetic
            # fact, which is the discipline `post_payment_cleared` already keeps
            # for a balanced pair.
            models.UniqueConstraint(
                fields=["tenant", "reverses_payment"],
                condition=Q(reverses_payment__isnull=False) & Q(is_partial_reversal=False),
                name="uq_payments_full_reverses",
            ),
            # A typo'd reason is a reversal no S35 filter can find and no NSF
            # router can classify — the same hole `ck_payments_status` closes.
            # NULL passes: an ordinary payment reverses nothing and states no
            # reason, and `Q(...__isnull=True)` is what makes that legal.
            models.CheckConstraint(
                condition=Q(reversal_reason__in=REVERSAL_REASONS) | Q(reversal_reason__isnull=True),
                name="ck_payments_reversal_reason",
            ),
            # US-PAY-002 / BR-PAY-012: only a `plan_down` payment names a plan.
            # Without this a bill payment could carry a plan link and the plan's
            # down payment would be whatever happened to point at it — the same
            # class of hole `ck_payments_purpose` closes for the purpose itself.
            models.CheckConstraint(
                condition=Q(plan__isnull=True) | Q(purpose=PURPOSE_PLAN_DOWN),
                name="ck_payments_plan_only_on_plan_down",
            ),
        ]
        indexes = [
            # B2 §4 `ix_payments_acct` — "account payment history". B2 leads the
            # third column with `received_at`, which this schema does not carry
            # (module docstring / r14 #8): the history a clerk reads is ordered
            # by POSTING date, which is also S33's default sort (EP-PAY-01
            # capability matrix, `posted_at desc`).
            models.Index(fields=["tenant", "account", "-posted_at"], name="ix_payments_acct"),
            # ⚠ **`CR-138-BRC07` `P4.5` PROPOSED A SECOND, COVERING INDEX HERE
            # — `(tenant, account, status, purpose) INCLUDE (amount)` — AND
            # THE MEASUREMENT REFUSED IT.** The debtor list's credit leg sums
            # essentially every payment row of the tenant, and PostgreSQL 16
            # correctly Seq Scans for that at 40,046 debtors whether or not
            # the index exists. The only statement that DID choose it already
            # had `ix_payments_acct` and ran in **0.227 ms**. See
            # `payments/0040`'s docstring for the four rejected indexes and
            # the paired runs that rejected them; do not re-add this one
            # without a plan that names it.
            # B2 §4 `ix_payments_status` — the S33 status tabs, verbatim.
            models.Index(fields=["tenant", "status"], name="ix_payments_status"),
            # CR-059 CS-8 + CS-32 — S21's *"moved to / moved from"* pair walks
            # the link from the SOURCE side, which is the direction the FK does
            # not index for free.
            models.Index(fields=["tenant", "moved_from_payment"], name="ix_payments_moved_from"),
            # `CR-137-BRC07` `P3.7` — the SAME judgment as the line above, for
            # the same reason, on a link with the same shape. The read is *"what
            # corrects this payment?"*, made from the corrected payment's own
            # page (`P3.1`'s `GET /payments/{id}` and `P3.4`'s history panel),
            # which walks the FK from the side it does not index for free.
            #
            # ⚠ **AND UNLIKE `reverses_payment` THERE IS NO UNIQUE CONSTRAINT TO
            # LEAN ON.** `uq_payments_full_reverses` is a partial unique index
            # over `(tenant, reverses_payment)`, so the reversal walk gets its
            # index as a side effect of a rule. A correction has no such rule —
            # a payment may be corrected more than once on purpose
            # (`payments/0014`) — so without this line the question is a
            # sequential scan of every payment the tenant has ever taken, which
            # at `NFR-5`'s largest modelled tenant is 40,000 accounts' worth.
            models.Index(fields=["tenant", "corrects_payment"], name="ix_payments_corrects"),
            # CR-059 CS-30 — the batch cut asks *"which cheques may be banked on
            # this day"* on every cut and S37 asks the complement. Without it
            # both are a sequential scan of every payment the tenant has taken.
            models.Index(fields=["tenant", "bankable_from"], name="ix_payments_bankable"),
            # CR-059 CS-12 — S33 groups the rows of ONE tender rather than
            # showing three unrelated payments, and the receipt for each part
            # names its siblings. Both walk this link from the TENDER side, which
            # is the direction the FK does not index for free.
            models.Index(fields=["tenant", "tender"], name="ix_payments_tender"),
            # CR-132-BRC07 — the New World feed selects `origin = webhook`
            # over a window, and a reconciliation question starts by asking
            # for one origin at a time. Tenant first, as every index on this
            # table is: RLS scopes every read and the tenant is always known.
            models.Index(fields=["tenant", "origin"], name="ix_payments_origin"),
            # ── CR-136-BRC07 `P2.5` · THE TILL'S OWN LIST ──────────────────
            # *"The till's own list reads it on every payment taken … the
            # running total stays cheap as a shift fills up."* Tenant first,
            # as every index on this table is.
            #
            # ⚠ **PARTIAL, AND THE MEASUREMENT IS IN `payments/0035` RATHER
            # THAN IN THIS COMMENT.** The short form: it is never larger, it
            # is 70% smaller at the share a real utility will actually carry,
            # and PostgreSQL provably uses it for `counter_session_id = $1`
            # **including under a generic plan** — which is the thing worth
            # checking, because a partial index the planner cannot use would
            # look thrifty and cost a sequential scan on every page load.
            models.Index(
                fields=["tenant", "counter_session_id"],
                condition=Q(counter_session_id__isnull=False),
                name="ix_payments_counter_session",
            ),
        ]


class Allocation(models.Model):
    """What one payment put against ONE invoice (B2 §2 `allocations`).

    **Append-only, always** — unlike `payments` there is no processing state to
    edit through. BR-PAY-031 is explicit: *"Reapply = reversing allocation rows
    + new rows, reason + audit; never edits"*, so a correction adds a negative
    row and a replacement row and this one stands untouched forever. The
    trigger in `migrations/0002` refuses UPDATE and DELETE outright.

    `amount` carries no CHECK against negatives, deliberately: B2 §2 declares
    none, and a reversing row is negative by construction (BR-PAY-031). The
    positive-only check belongs on the payment, not on the movement.

    `invoice` is the second reviewed cross-module FK (B2 §2: *payment N:M
    invoice via allocations*).

    ⚠ **THERE IS NO LINE-CLASS COLUMN ON THIS TABLE AND THERE STILL IS NOT** —
    the breakdown lives in `AllocationClass` below, one child row per class,
    since 2026-09-02 (CR-060 C19 / task T7d). This sentence read *"and one is
    not invented — see the module docstring and OQ-129"* until then, which was
    right while the question was open and is stale now that the disposition is
    recorded. The child shape is CR-060's own preference over four nullable
    columns, *"because the child row survives a fifth class being added"*.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, db_column="payment_id", related_name="allocations"
    )
    invoice = models.ForeignKey(  # ⚠ reviewed cross-module payments→billing (B2 §2)
        "billing.Invoice", on_delete=models.PROTECT, db_column="invoice_id"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "allocations"
        indexes = [
            # B2 §4 `ix_allocations_invoice` — "payment application", verbatim.
            # It is also the index the OPEN BALANCE read leans on: what a bill
            # still owes is its total minus the sum of these rows.
            models.Index(fields=["tenant", "invoice"], name="ix_allocations_invoice"),
            models.Index(fields=["tenant", "payment"], name="ix_allocations_payment"),
            # ⛔ **`CR-138-BRC07` `P4.5` — THE ONE INDEX THE MEASUREMENT KEPT.**
            # `ix_allocations_invoice` above is B2 §4's signed DDL and is NOT
            # replaced: this is the same key with `amount` in the PAYLOAD, so
            # the per-bill allocation sum the debtor list correlates on every
            # open invoice is answered by an **Index Only Scan** instead of an
            # index scan plus a heap fetch.
            #
            # Measured on real PostgreSQL 16 at **40,046 debtors**, paired and
            # interleaved (two rounds, median of 3 each, 2026-09-23) so the
            # box's own load falls on both arms:
            #
            #     without  12.047 s · 11.735 s      with  9.414 s · 8.847 s
            #
            # — about **−24%** on one page of fifty, and the plan shows why:
            # `Index Only Scan using ix_alloc_invoice_amount`, 12 statements'
            # worth, where it was `allocations_invoice_id_…` plus the heap.
            #
            # ⚠ **THE MIRROR INDEX ON `payment` WAS PROPOSED AND REFUSED.**
            # The credit leg joins the whole of `allocations` to the whole of
            # `payments` and PostgreSQL hash-joins two sequential scans, which
            # no per-payment index changes. `payments/0040` records the paired
            # run.
            models.Index(
                fields=["tenant", "invoice"],
                include=["amount"],
                name="ix_alloc_invoice_amount",
            ),
        ]


class AllocationClass(models.Model):
    """**WHICH KINDS OF CHARGE one allocation actually met** (CR-060 C19 / T7d).

    One row per line class an allocation reached, hanging off the `allocations`
    row it belongs to. `usage_base` 82.08 · `taxes` 12.69 · `fees` 5.00 for a
    payment that walked that far down BR-PAY-010's order and stopped.

    ════════════════════════════════════════════════════════════════════════
    THIS IS OQ-129's ANSWER MADE INTO A FACT, AND IT SETTLES NOTHING BY VOTE
    ════════════════════════════════════════════════════════════════════════
    Two signed rulings disagree about how a partial payment meets a bill's tax:
    `OQ-174` closed 2026-08-12 with *"a partial payment covers TAX FIRST"*, and
    `BR-PAY-010` (amended the same week, `OQ-129`) makes the within-bill sequence
    a **tenant setting** whose shipped default puts tax SECOND, after usage and
    base. On one $100.00 payment against a $247.87 bill carrying $20.97 of tax
    the two readings give **0.00, 12.69 or 20.97** collected — a 20.97 spread on
    a single bill, filed monthly with four authorities.

    CR-060 C19 rules the disposition and it is not to pick a winner:
    *"Recording the class breakdown ON the allocation row makes the question
    moot, and THAT is the disposition to write down rather than choosing a
    winner."* These rows are that record. **Whatever order a tenant chooses, what
    the money met is a stored fact afterwards** — so the collected-tax basis is
    read rather than re-derived, and the two rulings no longer need to agree.

    ════════════════════════════════════════════════════════════════════════
    APPEND-ONLY, LIKE ITS PARENT AND FOR THE SAME REASON
    ════════════════════════════════════════════════════════════════════════
    `allocations` accepts no UPDATE and no DELETE at any time (BR-PAY-031: a
    reapply is reversing rows plus new rows). A child that could be edited would
    be a back door into the same fact, so `payments/0016` gives this table the
    same trigger. **A reversing allocation carries a NEGATIVE breakdown**, the
    way its parent carries a negative amount, so the two always sum the same way.

    ⚠ **A CHILD ROW PER CLASS, NOT FOUR NULLABLE COLUMNS**, which is the option
    CR-060's own data note prefers: *"the child row survives a fifth class being
    added, which the tenant-defined class makes likely."* BR-PAY-038 already lets
    a tenant define a class of their own, so the set is open by rule.

    ⚠ **ONLY CLASSES THAT RECEIVED MONEY GET A ROW.** A class the payment never
    reached and a class it paid 0.00 are different facts and only the first one
    exists — the same rule `allocation.Allocation.by_class` states one level up,
    and the reason `applied_to_class` raises rather than answering zero.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.PROTECT,
        db_column="allocation_id",
        related_name="classes",
    )
    #: TEXT and not an enum, deliberately. BR-PAY-038 makes the fourth class
    #: TENANT-DEFINED, so the vocabulary is per-tenant data and a CHECK inlined
    #: at migration time would freeze one tenant's list into every database —
    #: the same trap `chart.GL_DESIGNATIONS` documents and pays for once a
    #: quarter. `apps/payments/allocation.py` validates against the tenant's own
    #: live class order on every write.
    line_class = models.TextField()
    #: CLAUDE.md rule 2 / DB-3 — 4 dp written on a NUMERIC(18,6) container,
    #: displayed at 2. No CHECK against negatives, for `Allocation.amount`'s
    #: reason: a reversing row is negative by construction (BR-PAY-031).
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "allocation_classes"
        constraints = [
            # One row per class per allocation. Two `taxes` rows on one
            # allocation would make the collected-tax figure depend on which one
            # a reader summed, which is the whole failure this table exists to
            # remove.
            models.UniqueConstraint(
                fields=["tenant", "allocation", "line_class"],
                name="uq_allocation_classes_line",
            ),
        ]
        indexes = [
            # The parent lookup — a drill-back from one allocation to what it met.
            models.Index(fields=["tenant", "allocation"], name="ix_alloc_classes_alloc"),
            # THE REMITTANCE READ. `apps/ledger/payments_seam.py` asks for one
            # class across a window of cleared payments, and without this it is a
            # sequential scan of every allocation the tenant has ever made.
            models.Index(fields=["tenant", "line_class"], name="ix_alloc_classes_class"),
        ]


class Refund(models.Model):
    """Money the utility pays BACK (B2 §2 `refunds`, + r12 #5 and r2).

    BR-PAY-014, CONFIRMED: *"Refunds only from a real credit balance; Admin
    approval; check/ACH v1 (card refund with rails W7); DR customer-credit / CR
    cash; immutable row + receipt"*.

    ════════════════════════════════════════════════════════════════════════
    THE STATUS SET IS WIDER THAN B2 r2 SIGNS, AND THAT IS ARGUED NOT ASSUMED
    ════════════════════════════════════════════════════════════════════════
    B2 Addendum r2 signs three values — `issued | cleared | void`. B2 Addendum
    **r12 #5** adds `requested_by` / `approved_by` / approval columns to this
    same table, and J15 steps 2–3 require the row to be VISIBLE in an approval
    queue between the request and the execution. A row cannot exist without a
    status, and none of r2's three is true of a refund nobody has approved yet:
    calling an unapproved request `issued` would put a cheque in the books that
    nobody wrote.

    So `requested` and `approved` are added under the standing *"Exact DDL =
    Eng-Lead 🔒"* delegation (r12 #17, r14 #9), r2's three keep their exact
    meanings, and the widening is recorded as a judgment call in
    12-governance/02-decision-log.md. **It moves no money figure**: the only
    state in which the customer-credit account is drawn down is `issued`, which
    is r2's own word for it.

    ════════════════════════════════════════════════════════════════════════
    WHY THE ROW HANGS OFF A *PAYMENT* AND WHAT THAT CANNOT EXPRESS (OQ-167)
    ════════════════════════════════════════════════════════════════════════
    B2 §2 is explicit: `payment_id uuid NOT NULL REFERENCES payments(id)`. So a
    refund is sourced to ONE payment's carried credit, which is exactly PE-9's
    shape — ACC-1042's $57.13 credit came from ONE $350.00 payment (PE-4) and
    the refund draws that payment's overpayment back.

    An account whose credit accumulated from TWO overpayments has a real credit
    balance that no single `payment_id` describes, and B2 gives this table no
    account column to say so. That is **OQ-167**, raised rather than answered:
    `apps/payments/refunds.py` serves the single-source case (the frozen one)
    and REFUSES the multi-source case by name.

    ════════════════════════════════════════════════════════════════════════
    IMMUTABILITY (hard rule 4) IS THE TRIGGER'S, NOT THIS CLASS'S
    ════════════════════════════════════════════════════════════════════════
    `refunds` is NOT one of the tables DB-4 freezes outright — B2 lists
    invoices/lines, payments, journal entries, credit notes, opening buckets and
    template versions, and this is none of them, which is what makes the r2
    status TRANSITIONS lawful in the first place. Migration 0004 freezes it
    deny-by-default anyway, with a short allow list holding only the transition
    columns: the amount, the currency, the payment, the method and the reference
    are frozen from the instant the row exists, and DELETE is refused in every
    status. **A void is a status move plus a REVERSING posting, never a
    removal** (US-PAY-011 TC-4).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ **NULLABLE SINCE 2026-09-03, AND THAT REVERSES A SIGNED SCHEMA
    #: STATEMENT (CR-059 CS-7, `payments/0018`).** B2 §2 types this column
    #: `uuid NOT NULL` and gives the table no account link at all, so a refund
    #: could name exactly ONE source payment. **The PO ruled on 2026-09-01
    #: (`OQ-195`, option (a)) that a refund belongs to the ACCOUNT**, closing a
    #: mechanism they had already ruled on 2026-08-12 (`OQ-167`): *"user can do
    #: a refund or issue a credit - it will be manula decision, provide a
    #: mecahnism to complete the tasks"*, worked on **$40.00 in June + $17.13 in
    #: July = $57.13 refunded as ONE cheque**.
    #:
    #: It stays as a column because it is still TRUE and useful whenever a
    #: refund really does draw one overpayment back — PE-9's $350.00 → $57.13 is
    #: exactly that — and a screen that can say *"this came from PMT-…"* is
    #: better than one that cannot. **What changed is that its absence is now
    #: lawful**, so every reader of it must survive a NULL: `refunds.py`'s
    #: `refund.payment.account_id` was the pattern that could not, and it now
    #: reads `account_id` below.
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        db_column="payment_id",
        related_name="refunds",
        null=True,
        blank=True,
    )
    #: ⚠ **NOT NULL, AND IT IS THE COLUMN THE RULING ADDS (CR-059 CS-7).** The
    #: refund's address. Every refund has one — including the ones that name a
    #: payment, where it is that payment's own account — so it is NOT NULL from
    #: the day it exists and `payments/0018` backfills every historic row from
    #: `payments.account_id` before it tightens the constraint.
    #:
    #: A reviewed cross-module FK, payments→customers, exactly as
    #: `payments.account_id` is (B2 §2's interface set). It is the column
    #: `POST /accounts/{id}/refunds` has been addressed by since 2026-09-01,
    #: when that route was built against this ruling before the schema could
    #: hold it — its own docstring records the anticipation.
    account = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="refunds",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    #: NOT in B2's four-column sketch of this table and added because hard rule
    #: 2 is unconditional: money is NUMERIC(18,6) **+ CHAR(3)**. A refund whose
    #: currency had to be inferred from its payment would be one join away from
    #: being inferred wrongly, and BR-TEN-042 locks the tenant to one currency
    #: precisely so the two can never legitimately differ.
    currency = models.CharField(max_length=3, default="USD")
    status = models.TextField(default=REFUND_REQUESTED)
    method = models.TextField(null=True, blank=True)  # r2: check|ach
    #: B2 r2's *"reference/check_no"* — cheque #10241 in PE-9.
    reference = models.TextField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)  # B2 §2
    memo = models.TextField(null=True, blank=True)
    # ── r12 #5, the approval columns, and BR-PAY-037's reason for two of each ──
    # *"the SAME user holding the approver role MAY initiate AND approve in v1 —
    # both acts recorded distinctly"*. Distinctly means four columns, not a flag:
    # J15 step 3 is Dana approving her own initiation and the audit trail IS the
    # control in v1, so who/when must survive on the row for both acts.
    requested_by_id = models.UUIDField(null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    #: BR-PAY-021's family, applied outbound: bank rec matches a refund on the
    #: side the money actually moved (US-PAY-011 TC-3).
    cleared_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(null=True, blank=True)
    #: Hard rule 6, widened outbound for the same reason `webhook_key` was
    #: widened inbound (OQ-127): S58's Record-refund modal has a submit button,
    #: and a double-clicked one would write two cheques against one credit.
    #: DB-12 does not name this table — the register lists bill runs, payment
    #: webhooks, imports and export batches — so this is a NEW key and it is
    #: declared here rather than smuggled in: composed by
    #: `apps/payments/idempotency.refund_key`.
    idempotency_key = models.TextField(null=True, blank=True)
    #: The two entries this refund left (B11 F-3 deferred FK, write-once each).
    #: The second exists only for a VOID and points at the mirror, so S58 can
    #: show both halves of a lost cheque without recomputing anything.
    journal_entry_id = models.UUIDField(null=True, blank=True)
    void_journal_entry_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "refunds"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=REFUND_STATUSES), name="ck_refunds_status"
            ),
            models.CheckConstraint(
                condition=Q(method__in=REFUND_METHODS) | Q(method__isnull=True),
                name="ck_refunds_method",
            ),
            # A refund pays money OUT and its sign lives in the posting, not in
            # the amount: `DR customer-credit / CR cash` of a NEGATIVE figure
            # would be a deposit wearing a refund's clothes.
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_refunds_amount_positive"),
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="uq_refunds_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "payment"], name="ix_refunds_payment"),
            # CR-059 CS-7 — the read S58 makes on every open: *"what has this
            # account had back?"* Since the PO's ruling of 2026-09-01 the ACCOUNT
            # is the refund's address, so this is now the primary lookup and
            # `ix_refunds_payment` above answers only the narrower question of
            # which refunds drew on ONE payment.
            models.Index(fields=["tenant", "account"], name="ix_refunds_account"),
            # S58's approval queue: everything this tenant has requested and not
            # yet issued, newest first.
            models.Index(fields=["tenant", "status", "-created_at"], name="ix_refunds_status"),
            # ⚠ **`CR-138-BRC07` `P4.5` PROPOSED `(tenant, account, status)
            # INCLUDE (amount)` HERE AND THE MEASUREMENT REFUSED IT.** The
            # debtor list subtracts the refunds that have LEFT the utility
            # (`issued`/`cleared`) as ONE grouped aggregate over the tenant,
            # and half of any real refunds table matches — so PostgreSQL Seq
            # Scans, correctly, and did so with the index present. Proved
            # rather than assumed: the fixture has one refund row, which
            # decides nothing, so 8,000 more were seeded across the four
            # statuses and the plan still read `Seq Scan on refunds`, **4.4 ms
            # of a 3.7-second page.** See `payments/0040`.
        ]


# ── autopay capture intents (US-PAY-024 / BR-PAY-015, r12 #6) ───────────────
#: The ONE status v1 writes, and r12 #6's own word for it. BR-PAY-015 is
#: explicit that *"real charging = rails (W7)"*, so there is no `captured`, no
#: `failed` and no `retrying`: a status set that can express a charge is a
#: status set some path will eventually be written against, and no charging path
#: may exist before the rails land. The FULFILLED state is deliberately not here
#: — it is COMPUTED from invoice settlement (BR-PAY-034, field-map P-7).
INTENT_AWAITING_RAILS = "awaiting_rails"
INTENT_STATUSES = (INTENT_AWAITING_RAILS,)


#: CR-060 C21 — the delivery's own lifecycle, which is NOT the payment's.
#: A delivery is received, then either accepted (it produced or matched a
#: payment) or refused (a bad signature, an account this tenant does not have,
#: an amount that cannot be parsed). `duplicate` is its own value rather than a
#: flavour of accepted, because *"we saw this before"* and *"we recorded money"*
#: are the two different things a person looking at this table needs to tell
#: apart.
WEBHOOK_RECEIVED = "received"
WEBHOOK_ACCEPTED = "accepted"
WEBHOOK_REFUSED = "refused"
WEBHOOK_DUPLICATE = "duplicate"
WEBHOOK_STATUSES = (
    WEBHOOK_RECEIVED,
    WEBHOOK_ACCEPTED,
    WEBHOOK_REFUSED,
    WEBHOOK_DUPLICATE,
)


class PaymentWebhookEvent(models.Model):
    """What a payment gateway TOLD this utility (CR-060 C21, `payments/0020`).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — webhook keys are a CLAUDE.md 🔒 path by
    name and this table is what stands between a provider's retry and a second
    payment on a customer's account.

    ⚠ **`payments` RECORDS MONEY; THIS RECORDS WHAT WAS SAID.** They are
    different facts and the difference is the whole reason the table exists:
    `uq_payments_webhook_key` already makes a redelivered callback write one
    payment, and it can say nothing at all about a callback that produced NO
    payment — a bad signature, an account this tenant does not have, an amount
    that will not parse. Those are the deliveries that cost a support call, and
    without a row they are indistinguishable from a provider that never called.

    **APPEND-ONLY except its processing outcome** (`payments/0020`'s trigger). A
    refused delivery may be retried and the result belongs on the row that
    recorded the attempt; the provider, the event id, the body and the moment it
    arrived are frozen from the instant the row exists.

    **NO SIGNATURE, NO SECRET, NO CARD NUMBER AND NO LAST FOUR.** The row says
    whether verification PASSED and never carries the material — a stored
    signature is a stored credential with extra steps. Card facts are absent
    because C21 is the INBOUND half (recording what a gateway says already
    happened) and `CR-059` CS-1, taking money from a card, is v2 and out of this
    release: a column only a charging path would fill is a column that invites
    one to be written.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `stripe`, `adyen`, … Plain text and not an enum: which gateways a utility
    #: uses is deployment configuration, and a CHECK inlined at migration time
    #: would freeze one deployment's list into every database.
    provider = models.TextField()
    #: THE GATEWAY'S OWN EVENT ID — the thing it repeats on a retry, and the
    #: half of this table's unique key that makes a redelivery a no-op.
    event_id = models.TextField()
    event_type = models.TextField(null=True, blank=True)
    status = models.TextField(default=WEBHOOK_RECEIVED)
    #: Whether the signature verified. **Never the signature itself.**
    signature_verified = models.BooleanField(default=False)
    #: The raw payload, so a failed delivery can be explained and replayed. It
    #: is why the RLS policy on this table matters as much as the one on
    #: `payments` — see the migration.
    body = models.JSONField(default=dict, blank=True)
    #: WHEN the delivery arrived, from the caller — never a clock (BR-TEN-043).
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    #: The payment this delivery produced or matched, if any. A deferred uuid
    #: and not an FK, the same shape as `deposit_batch_id`: a delivery may
    #: legitimately name no payment at all, and the row must survive being
    #: written before one exists.
    payment_id = models.UUIDField(null=True, blank=True)
    #: WHY, in a sentence a person can act on. The refusal reason for a refused
    #: delivery; what was matched for an accepted or duplicate one.
    outcome = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_webhook_events"
        constraints = [
            # ⚠ **INDEPENDENT OF `uq_payments_webhook_key`, DELIBERATELY
            # (DEF-058's lesson).** Two guards that catch the same fact on one
            # code path are ONE guard, and the day somebody changes the key
            # scheme is the day the other silently stops covering it. These two
            # answer different questions: this one is *"has this DELIVERY been
            # seen?"* and the other is *"has this PAYMENT been recorded?"*
            #
            # Per PROVIDER, because two gateways may both number an event `1`.
            models.UniqueConstraint(
                fields=["tenant", "provider", "event_id"],
                name="uq_payment_webhook_events_event",
            ),
        ]
        indexes = [
            # The one read a person makes: *"what has come in, and what could
            # not be processed?"*, newest first.
            models.Index(
                fields=["tenant", "status", "-received_at"], name="ix_pay_webhook_status"
            ),
        ]


class AutopayCaptureIntent(models.Model):
    """What autopay IS in v1: a promise recorded, never a charge (r12 #6).

    BR-PAY-015, CONFIRMED: *"Autopay v1 = capture-INTENT: enrollment + method
    stored; bill issue records intent dated the due date, visible on S32/S33;
    staff record the actual money; real charging = rails (W7)"*.

    **THE ROW IS THE W7 CONTRACT.** US-PAY-024 §1 says it in as many words —
    *"when rails land (W7), the dispatcher-side execution consumes these same
    intents"* — which is why `amount` and `scheduled_on` are stored rather than
    recomputed at charge time: what the customer was told would be drafted, and
    when, must survive a later change to the bill.

    `scheduled_on` is the invoice's DUE DATE and is never user-set (US-PAY-024
    §5). `invoice_id` is a deferred uuid rather than an FK for the B11 F-3
    reason `Payment.deposit_batch_id` gives — except in reverse: `invoices` is
    billing's and the reviewed cross-module FK set (B2 §2) contains
    payments→invoices only through `allocations`. Nothing here widens it.

    UNIQUE (tenant, invoice) is US-PAY-024 TC-6's idempotency: an issue retried
    after a crash writes ONE intent, not two, and the guarantee is the index
    rather than a SELECT-then-INSERT that two workers would both win.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    #: Deferred uuid — see the class docstring.
    invoice_id = models.UUIDField()
    #: The bill's TOTAL DUE at issue (US-PAY-024 §7: PE-12's 292.87).
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    currency = models.CharField(max_length=3, default="USD")  # hard rule 2
    #: BR-PAY-015 — *"dated the due date"*.
    scheduled_on = models.DateField()
    status = models.TextField(default=INTENT_AWAITING_RAILS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "autopay_capture_intents"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "invoice_id"], name="uq_autopay_intent_per_invoice"
            ),
            models.CheckConstraint(
                condition=Q(status__in=INTENT_STATUSES), name="ck_autopay_intent_status"
            ),
        ]
        indexes = [
            # The S32 chip and the S33 column: this tenant's open intents by the
            # day they are expected to draft.
            models.Index(
                fields=["tenant", "status", "scheduled_on"], name="ix_autopay_intent_open"
            ),
            models.Index(fields=["tenant", "account"], name="ix_autopay_intent_acct"),
        ]


# ── CR-059 CS-2 · the staged remittance import (US-PAY-003 · BR-PAY-023) ────
#: The batch walk. BR-PAY-023 names the shape verbatim — *"batch → per-row
#: validation → preview → commit"* — and the statuses are those four moments.
#: `discarded` is the fifth and it is not a failure: a clerk who uploads the
#: wrong file must be able to put it down, and the batch is KEPT for audit
#: rather than deleted (the same posture `read_import_batches` takes).
IMPORT_STAGED = "staged"
IMPORT_VALIDATED = "validated"
IMPORT_COMMITTED = "committed"
IMPORT_DISCARDED = "discarded"
IMPORT_STATUSES = (IMPORT_STAGED, IMPORT_VALIDATED, IMPORT_COMMITTED, IMPORT_DISCARDED)

#: The three per-row states BR-PAY-023 and the field map both name:
#: `clean | review | error`. **`review` is the whole point of the feature** —
#: it is where a row goes when we know something about it but not enough to
#: post money on it, and the rule that puts it there is CS-2's second: *"a row
#: that cannot be matched to an account with certainty is left unmatched for a
#: person; a name-and-amount heuristic never commits on its own."*
ROW_CLEAN = "clean"
ROW_REVIEW = "review"
ROW_ERROR = "error"
ROW_STATES = (ROW_CLEAN, ROW_REVIEW, ROW_ERROR)

#: HOW a row found its account, recorded on the row so a person can see it.
#: The order is the epic's priority order and it is not a preference:
#: `account_no` is the customer quoting OUR number, `invoice_no` is them quoting
#: a bill we issued, and `name_amount` is a GUESS — which is why it lands in
#: `review` and never in `clean`.
MATCH_ACCOUNT_NO = "account_no"
MATCH_INVOICE_NO = "invoice_no"
MATCH_NAME_AMOUNT = "name_amount"
MATCH_MANUAL = "manual"
MATCH_NONE = "none"
MATCH_METHODS = (
    MATCH_ACCOUNT_NO,
    MATCH_INVOICE_NO,
    MATCH_NAME_AMOUNT,
    MATCH_MANUAL,
    MATCH_NONE,
)


class PaymentImportBatch(models.Model):
    """One uploaded lockbox or CSV remittance file, STAGED (CR-059 CS-2).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — the file+tags idempotency key is a
    CLAUDE.md 🔒 path by name, and this table is what stands between a lockbox
    file lodged twice and a customer credited twice.

    ⚠ **NOTHING IS APPLIED ON UPLOAD, AND THAT IS THE FIRST OF CS-2's TWO NEW
    RULES.** *"A remittance import is staged: upload → validate → preview →
    commit; nothing is applied on upload"* — the same shape the meter-read
    import already uses (BR-PAY-023, BR-MET-012). No `payments` row exists
    before the commit, so a clerk who uploads the wrong file has changed no
    customer's balance and can simply discard the batch. A discarded batch is
    retained for audit and never appears as money.

    ⚠ **A CLEAN ONE-WAY WALK, ENFORCED IN THE DATABASE** (`payments/0021`'s
    trigger). Staged and validated batches are mutable — that is what staging
    IS; a committed one is frozen because it now names payments, and hard rule
    4 does not stop at the `payments` table when a staging row is the only
    record of which file created which payment.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `lockbox` or `csv` — how the file reached us, for the S33 batch column.
    #: Text and not an enum, the same posture `read_import_batches.source_kind`
    #: takes: which channels a utility uses is deployment reality.
    source_kind = models.TextField(default="lockbox")
    file_name = models.TextField(null=True, blank=True)
    #: SHA-256 hex of the exact bytes uploaded — **computed server-side, never
    #: accepted from a client.** One changed row is a different file, so a bank
    #: that re-sends a corrected file imports normally.
    file_hash = models.TextField(null=True, blank=True)
    #: 🔒 The TAG half of BR-PAY-028's file+tags key. See
    #: `lockbox.remittance_tag_fingerprint`, which is the single place it is
    #: computed and which states the tag choice and its one hole.
    tag_fingerprint = models.TextField(null=True, blank=True)
    #: The tags themselves, so a person reading the batch can see what the
    #: fingerprint was made of. A hash nobody can explain is not evidence.
    tags = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="uploaded_by"
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    #: The preview figures BR-PAY-023 asks for — matched / needs review / errors
    #: — denormalised at validate time so the S35 preview is one read. They must
    #: reconcile against the rows; `payment_import.validate_batch` is the only
    #: writer and recomputes all of them together.
    counts = models.JSONField(default=dict, blank=True)
    status = models.TextField(default=IMPORT_STAGED)
    committed_at = models.DateTimeField(null=True, blank=True)
    committed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="committed_by",
        related_name="committed_payment_import_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_import_batches"
        constraints = [
            # 🔒 DB-12 "file+tags imports": the structural half of BR-PAY-028.
            # **Scoped to COMMITTED batches**, exactly as
            # `uq_read_import_batches_idempotency` is and for the same reason:
            # OQ-044's closure blocks the COMMIT, not the staging. A clerk may
            # re-open the modal on the same file all morning; only a second
            # COMMIT is the double-post this prevents.
            models.UniqueConstraint(
                fields=["tenant", "file_hash", "tag_fingerprint"],
                condition=Q(status=IMPORT_COMMITTED, file_hash__isnull=False),
                name="uq_payment_import_batches_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_payment_import_batch_status"),
        ]


class PaymentImportRow(models.Model):
    """One cheque in the file, and what we could and could not tell about it.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — a committed row names a payment, and
    which file created which payment is a money fact.

    ⚠ **THE RAW COLUMNS ARE NOT DUPLICATION.** Every reference the file carried
    is kept exactly as the bank sent it, beside the value we made of it. A row a
    person has to work is a row where our reading was not good enough, and the
    first thing they need is what the file actually SAID — not our
    interpretation of it, which is the thing under suspicion.

    ⚠ **`account` IS NULLABLE AND THAT IS THE FEATURE.** CS-2's second new rule:
    *"a row that cannot be matched to an account with certainty is left
    unmatched for a person, and a name-and-amount heuristic never commits on its
    own."* A row matched only by name and amount carries `match_method =
    name_amount`, `match_state = review`, and its `account` filled in — so the
    person sees the suggestion — and the commit **skips it** until a person
    confirms. The suggestion is a suggestion until somebody says otherwise.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(
        PaymentImportBatch, on_delete=models.PROTECT, db_column="batch_id", related_name="rows"
    )
    row_no = models.IntegerField()

    # ── what the file said, verbatim ───────────────────────────────────────
    account_ref_raw = models.TextField(null=True, blank=True)
    invoice_ref_raw = models.TextField(null=True, blank=True)
    payer_name_raw = models.TextField(null=True, blank=True)
    amount_raw = models.TextField(null=True, blank=True)
    paid_on_raw = models.TextField(null=True, blank=True)
    reference_raw = models.TextField(null=True, blank=True)

    # ── what we made of it ─────────────────────────────────────────────────
    #: Money to 6 decimals in a lawful 18,6 container; what is WRITTEN obeys
    #: CLAUDE.md rule 2's four places and DISPLAYS at two.
    amount = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: The date the money arrived, from the FILE (BR-PAY-033: *"imports default
    #: it from file data where present"*). NULL where the file carried none —
    #: the PO's 2026-08-12 fallback to the recorded date is applied by the
    #: COMMIT, which is the only place that knows the recording moment, and is
    #: never written back over this column as though the file had said it.
    paid_on = models.DateField(null=True, blank=True)
    reference = models.TextField(null=True, blank=True)
    account = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
        related_name="payment_import_rows",
    )
    #: The bill the file named, when it named one and we could find it. A bare
    #: uuid rather than an FK for the reason `Allocation` already records for
    #: `invoice_id`: it is billing's row and this is a staging table.
    invoice_id = models.UUIDField(null=True, blank=True)
    match_method = models.TextField(default=MATCH_NONE)
    match_state = models.TextField(default=ROW_ERROR)
    #: One sentence saying what happened to this row, in the words a person
    #: reads. Both the parse failure and the match outcome land here.
    match_detail = models.TextField(null=True, blank=True)
    #: Set at commit. A bare uuid and not an FK, so a staged row can name a
    #: payment without a second write path into `payments`.
    payment_id = models.UUIDField(null=True, blank=True)
    #: Why this row did NOT become a payment when its batch was committed.
    #: BR-PAY-023's *"per-row errors skip with a report"* — this column is the
    #: report, and a row that skipped silently would be money nobody chased.
    commit_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_import_rows"
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_no"], name="uq_payment_import_rows"),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="ix_payment_import_rows_batch"),
            models.Index(
                fields=["tenant", "batch", "match_state"], name="ix_payment_import_rows_state"
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 phase 5 — THE CUSTOMER'S STORED INSTRUMENT (US-CWP-046 · BR-CWP-057)
# ═══════════════════════════════════════════════════════════════════════════

#: What the instrument IS. `bank` is a direct-debit mandate; `card` is a card.
INSTRUMENT_CARD = "card"
INSTRUMENT_BANK = "bank"
INSTRUMENT_KINDS = (INSTRUMENT_CARD, INSTRUMENT_BANK)

#: ⚠ `verified` IS BANK-ONLY (03-field-map.md §payments): a card is active the
#: moment the gateway tokenises it, a mandate is not active until the bank has
#: confirmed it. Collapsing the two would let a screen say a direct debit is
#: ready when the bank has not agreed to it.
INSTRUMENT_ACTIVE = "active"
INSTRUMENT_VERIFIED = "verified"
INSTRUMENT_EXPIRED = "expired"
INSTRUMENT_STATUSES = (INSTRUMENT_ACTIVE, INSTRUMENT_VERIFIED, INSTRUMENT_EXPIRED)

#: What the customer said this instrument may be used for. A list, because one
#: card is commonly both the autopay method and the one they pay ad hoc with,
#: and a boolean per purpose would need a migration for the third purpose.
INSTRUMENT_USE_AUTOPAY = "autopay"
INSTRUMENT_USE_ONE_OFF = "one_off"
INSTRUMENT_USES = (INSTRUMENT_USE_AUTOPAY, INSTRUMENT_USE_ONE_OFF)


class StoredPaymentInstrument(models.Model):
    """A card or a bank mandate a customer has saved — **a token, never a number**.

    `BR-CWP-057`, and it is the whole reason this table has the shape it has:
    the product **never holds a full card number**. What is stored is the
    gateway's token, the brand, the last four digits and an expiry. There is no
    column a card number would fit in, which is a stronger guarantee than a rule
    saying not to put one there.

    ⚠ **THE TABLE IS `stored_payment_instruments` AND NOT `payment_methods`,
    WHICH `B2` §2 SPELLS FOR THIS ROW.** That name has been taken since
    `OQ-031` closed the `payment_method_t` enum into a tenant-extensible lookup:
    `tenancy.PaymentMethod` holds it, and it is the seeded tender vocabulary —
    cash, cheque, card, bank transfer — that `Payment.method` points at on every
    payment row in the product. Renaming that to free the word would move a
    foreign key on a money table, on a seeded lookup, across every existing
    payment, to win a word. **Decision log 2026-09-05**, with both options and
    why this one was taken; `03-field-map.md`'s collision warning is answered
    there rather than left for the next lane to rediscover at `makemigrations`
    time — which is exactly what it warns about.

    ⚠ **IT HANGS OFF THE CUSTOMER, NOT THE ACCOUNT** (`03-field-map.md`
    §payments: `customer_id`). A landlord holding four accounts saves one card
    and pays any of them with it, and `CWP-039` carries no account id in its
    address for the same reason. An account-scoped instrument would make them
    add the same card four times.

    ⚠ **NO CHARGING PATH EXISTS HERE.** This table records what a customer
    saved; `apps/payments/gateway.py` is what asks a provider to charge it, and
    which provider that is belongs to the tenant's integration connection —
    never to this row. A `provider_key` column would be a second place that
    knows a tenant's payment provider, and the first place is the connection
    (PO ruling 2026-09-05: providers are integrations, one or two activated per
    utility).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    customer = models.ForeignKey(  # ⚠ reviewed cross-module payments→customers (B2 §2)
        "customers.Customer", on_delete=models.PROTECT, db_column="customer_id"
    )
    #: ⚠ THE GATEWAY'S TOKEN AND NOTHING ELSE. Opaque to this product: it is
    #: shown to nobody, matched on by nobody, and means nothing outside the
    #: provider that issued it.
    gateway_token = models.TextField()
    #: `Visa`, `Mastercard`, `Chase` — what a person recognises in a list.
    brand = models.TextField()
    #: ⚠ **THE ONLY DIGITS EVER STORED**, and four is the maximum a card scheme
    #: permits to be displayed. The four-character cap is the guard: a full
    #: number does not fit in this column.
    last_four = models.CharField(max_length=4)
    #: Card only. A mandate has no expiry, so both are null on a bank row.
    expires_month = models.SmallIntegerField(null=True, blank=True)
    expires_year = models.SmallIntegerField(null=True, blank=True)
    kind = models.TextField(choices=[(one, one) for one in INSTRUMENT_KINDS])
    status = models.TextField(
        choices=[(one, one) for one in INSTRUMENT_STATUSES], default=INSTRUMENT_ACTIVE
    )
    #: JSON rather than a Postgres array, for the reason `portal_settings`
    #: already records: the default test suite runs on SQLite, which has no
    #: array column, and a field that only exists on one vendor is a field half
    #: the tests cannot reach (law 14's shape).
    used_for = models.JSONField(default=list, blank=True)
    #: Removed by the customer. Soft, because a payment already taken on this
    #: instrument names it, and hard rule 4 forbids destroying what a payment
    #: points at.
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stored_payment_instruments"
        constraints = [
            #: One token per tenant. A gateway never issues the same token
            #: twice, so two rows carrying one token is a bug in us — most
            #: likely a double submit — and the index refuses it rather than
            #: leaving the customer two identical cards in a list.
            models.UniqueConstraint(
                fields=["tenant", "gateway_token"],
                condition=Q(deleted_at__isnull=True),
                name="uq_instrument_token_live",
            ),
            #: ⚠ A CARD CARRIES AN EXPIRY AND A MANDATE DOES NOT. Without this
            #: a bank row with a stray expiry renders as *expires 11/27* on a
            #: direct debit, which is a sentence nobody can act on.
            models.CheckConstraint(
                condition=(
                    Q(kind=INSTRUMENT_CARD, expires_month__isnull=False, expires_year__isnull=False)
                    | Q(kind=INSTRUMENT_BANK, expires_month__isnull=True, expires_year__isnull=True)
                ),
                name="ck_instrument_expiry_on_cards_only",
            ),
            #: `verified` is bank-only — see the status constants above.
            models.CheckConstraint(
                condition=~Q(kind=INSTRUMENT_CARD, status=INSTRUMENT_VERIFIED),
                name="ck_instrument_verified_is_bank_only",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="ix_instrument_customer"),
        ]

    def __str__(self) -> str:  # pragma: no cover - a debugging convenience
        return f"{self.brand} ●●●●{self.last_four}"



# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments DDL + Addenda r12/r14/r16 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments schema slice — the closed-loop foundation)
# amended:   2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03) — `Refund` added; `Payment` gains the reversal triple (`reverses_payment`, `reversal_reason`, `journal_entry_id`), `uq_payments_reverses` and `ck_payments_reversal_reason`. THREE CLAIMS IN THIS FILE WERE FALSIFIED AND REWRITTEN rather than left to rot (hard-won law 1): that `refunds` is not built, that "no service writes" an NSF or a reversal, and the class docstring's list of what a reversing row cannot say.
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [D and E CLOSED 2026-08-11 by the payments API lane: apps/payments/api.py serves POST /accounts/{id}/payments + GET /payments and 07-frontend/src/features/payments/ ships S33 and the Record modal. NEITHER COVERS THE NEW TABLE: `refunds` has no endpoint and S58 has no server — reported, not implied]
# gates: ruff✔ black✔ · makemigrations --check clean · migrate applied against a LIVE Postgres cluster · pytest tests/test_us_pay_001_record_payment.py · pytest tests/test_us_pay_009_nsf.py · pytest tests/test_us_pay_011_refunds.py · -m isolation on live Postgres (the catalog sweep names any table lacking RLS)
# exceptions: `received_at` (B2 §2) is NOT built — the disposition r14 #8
#         delegates to Eng-Lead, resolved in favour of BR-PAY-021's two dates
#         because the PO defines clearing as "when money is actually received"
#         and two columns for one fact drift. REPORTED, decision log 2026-08-11
#         · B2 §2's `payment_methods` (the customer's stored instrument) is NOT
#         built and its TABLE NAME is already tenancy's method lookup — the six
#         BR-PAY-026 seeds — which is what `method` points at
#         · `deposit_batch_id` is a plain uuid column, not an FK: `deposit_batches`
#         belongs to EP-PAY-06 and does not exist (B11 F-3 deferred-FK convention)
#         · `allocations` has NO line-class column because B2 declares none; the
#         within-invoice breakdown the PO ruled on 2026-08-11 therefore has
#         nowhere to be stored and rides the audit payload — OQ-129, raised
#         · eleven further payments tables (plans, batches, imports, intents,
#         collections, write-offs) are NOT built and are named in the module
#         docstring so silence is not read as "done"
#         · THE REFUND STATUS SET IS WIDER THAN B2 r2's SIGNED THREE. r2 signs
#         issued|cleared|void; r12 #5 adds requested_by/approved_by to the same
#         table and J15 needs the row visible between request and execution, so
#         `requested` and `approved` are added under the "Exact DDL = Eng-Lead
#         🔒" delegation. No money figure moves — only `issued` draws the credit
#         down. Recorded in the decision log, never a silent widening
#         · `refunds.currency` IS NOT IN B2's FOUR-COLUMN SKETCH and is added,
#         because hard rule 2 is unconditional (NUMERIC(18,6) + CHAR(3))
#         · `refunds.idempotency_key` IS A NEW KEY. DB-12's register does not
#         name this table; S58's submit button is why it exists, and it is
#         declared rather than smuggled
#         · A REFUND HANGS OFF ONE PAYMENT because B2 §2 says
#         `payment_id NOT NULL`. A credit accumulated from TWO overpayments has
#         no home in this shape — OQ-167, raised; the service refuses that case
#         · `reverses_payment_id` / `reversal_reason` / `journal_entry_id` are
#         NOT in B2 §2. The first two implement EP-PAY-03 §5's *"references
#         original"* under the Eng-Lead DDL delegation; the third is the only
#         way a bounce can name the entry `posting.reverse_entry` must unwind,
#         because the ledger publishes no key→entry read. All three are frozen
#         by 0002's deny-by-default trigger the day they exist; the third is
#         opened WRITE-ONCE by 0004 and proved RED
#         · [PURPOSE + AUTOPAY lane 2026-08-15] `Payment.plan` (migration 0009)
#         anchors field-map **P-12** — BR-PAY-012's *"plan-down links to its
#         plan"* had a CONFIRMED rule and no column. A real FK, because
#         `payment_plans` is this module's own table. `ck_payments_plan_only_on_
#         plan_down` keeps the link off every other purpose
#         · `AutopayCaptureIntent` (r12 #6) carries ONE status, `awaiting_rails`.
#         There is no `captured` and no `failed`: a status set that can express
#         a charge is one some path is eventually written against, and
#         BR-PAY-015 forbids a charging path before W7. The FULFILLED state is
#         COMPUTED from invoice settlement (BR-PAY-034 / field-map P-7), never
#         stored
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
