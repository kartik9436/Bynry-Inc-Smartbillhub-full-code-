# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (deposit batches — day × method, the DEP- code, the S37
#           list) · US-PAY-021 (the bank-statement import + its file idempotency
#           and the `bank_lines` it persists) · US-PAY-022 (the S40 reconcile
#           modal's reason + GL difference record) · US-PAY-023 (the S39 batch
#           detail: the append-only trail and the reconciled LOCK)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-004 (a reconciled batch LOCKS; Unreconcile is the only
#           reversal) · BR-PAY-019 (bank rec: statement import, auto-match on
#           amount + date ± a finance setting, every exception explained with a
#           reason AND a GL) · BR-PAY-021 (posting date ≠ clearing date) ·
#           BR-PAY-025 (batches group day × method, the day is the POSTING day
#           per RQ-5/BR-REP-013, numbered from the tenant DEP- series) ·
#           BR-PAY-028 (idempotency — the import batch keys on file+tags) ·
#           BR-PAY-035 ("Force match anyway" is permanently SUPERSEDED) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3), never float) · rule 4 (financial immutability) · rule 6
#           (idempotency)
# Tests:    06-backend/tests/test_us_pay_020_023_bank_rec.py
# Impacts:  apps/payments/reconciliation.py (the ONLY write path for every table
#           below) · apps/payments/lockbox.py (the file kernel that fills
#           `bank_lines`) · apps/payments/migrations/0004_w5_deposit_batches_bank_rec
#           (this schema) · 0005_rls_w5_bankrec_and_lock (the guarantees these
#           classes cannot give) · apps/payments/models.Payment.deposit_batch_id
#           (the membership column, opened write-once by 0005)
# ───────────────────────────────────────────────────────
"""Deposit batches and bank reconciliation — the six tables EP-PAY-06 needs.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering, idempotency keys and
money rounding are CLAUDE.md 🔒 paths and every table here carries money.
AI-authored 2026-08-11 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

**WHY THESE CLASSES ARE NOT IN `apps/payments/models.py`.** They belong there and
they are not there for one reason: another lane held that file while this one was
written (the NSF/refund path), and two lanes editing one models module is how a
migration graph forks. They are ordinary payments models — `app_label` is
`payments`, the tables are payments' own, and `apps/payments/apps.py` imports this
module so the app registry sees them. Merging this file into `models.py` later is a
move, not a redesign. REPORTED rather than done quietly.

════════════════════════════════════════════════════════════════════════════
WHAT IS TRANSCRIBED FROM SIGNED SCHEMA, AND WHAT IS DELEGATED MECHANICS
════════════════════════════════════════════════════════════════════════════
`deposit_batches` and `bank_lines` are **B2 §2 verbatim** — every column below
that appears there is transcribed with its type, and none is invented.

Four tables are NOT in B2 §2 and each names the line that puts it there:

  * `bank_accounts` — B2 **r14 #1**, *"Tenant bank-account registry (deposit-slip
    + rec target)"*, owned by payments per r16 #6's owner map. S38 step 1 selects
    one ("Chase Operating ••4021") and a statement cannot be imported without
    saying which bank sent it.
  * `bank_statement_imports` — B2 **r12 #10**, *"Bank statement imports + match-rule
    config"*. It carries the file's SHA-256 and the file+tags idempotency key
    (BR-PAY-028; US-PAY-021 TC-5: a re-imported statement is BLOCKED naming who
    imported it, when, and linking to it).
  * `bank_rec_resolutions` — the r12 #10 family's *"reason-coded difference record
    + `ledger_accounts` ref"* (payments field map §6). One row per explanation of
    one difference; BR-PAY-019 requires a reason AND a GL on every one.
  * `deposit_batch_events` — US-PAY-023 §5's *"append-only batch events
    (created/matched/flagged/resolved/reconciled/unreconciled — r12 #10 family,
    DDL 🔒 #17)"*. The S39 reconciliation trail.

r12 #17 is the delegation those four rest on: *"Exact DDL, keys, dispatcher
mechanics = Eng-Lead 🔒 as always."*

════════════════════════════════════════════════════════════════════════════
THE DAY A BATCH BELONGS TO IS THE **POSTING** DAY (BR-PAY-025 · RQ-5)
════════════════════════════════════════════════════════════════════════════
`deposited_on` is the physical drawer day — the day the money was taken over the
counter — and NOT the day the bank credits it. That is the PO's own ruling RQ-5,
carried by BR-PAY-025 (*"day = POSTING date per RQ-5/BR-REP-013"*) and by
BR-REP-013 (*"Deposit batch 'day' = POSTING date (physical drawer day); bank
clears later"*), and journey J14 step 4 states it in the same words.

**EP-PAY-06's US-PAY-020 said `cleared_at` and had a test case asserting it.** That
epic text was stale — written before RQ-5 — and it is corrected in this commit
with a defect row (DEF-065). Written here because a reader who meets the two
sentences in the wrong order would implement the wrong day, and the two differ by
however long the bank takes.

The ±3-day match tolerance (BR-PAY-019, a finance setting) is what absorbs the
gap: J14 takes the money on **8 Aug** and the statement lands on **11 Aug**.

════════════════════════════════════════════════════════════════════════════
THE LOCK IS A DATABASE TRIGGER, NOT A CLAIM MADE HERE (hard-won law 1)
════════════════════════════════════════════════════════════════════════════
BR-PAY-004: *"Reconciled deposit batches lock; Unreconcile is the only
reversal."* A Django model cannot refuse a `.save()`, so the guarantee is the
trigger pair in `migrations/0005` and this docstring only describes it:

  * a `reconciled` batch accepts NO column change except `status` moving back to
    `unmatched` (the Unreconcile path) — totals and the code are frozen;
  * `deposit_batch_events` accepts no UPDATE and no DELETE, ever;
  * `bank_rec_resolutions` likewise — an explanation of a money difference is
    financial history the moment it is written;
  * `bank_lines` may take a batch link ONCE (NULL → a batch) and never re-point;
  * and `payments.deposit_batch_id` is opened write-once by the same migration —
    the door `payments/0002` deliberately shut and told this lane to open.

The membership consequence is stated rather than left to be discovered: a payment
joins exactly one batch, forever. **No regroup path exists** (US-PAY-020 TC-5
mentions "audited regroup events" and nothing ratifies their shape), and a batch
cut on the wrong day cannot be re-cut. Reported, not invented.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT BUILT HERE, NAMED SO SILENCE IS NOT READ AS "DONE"
════════════════════════════════════════════════════════════════════════════
  * `payment_import_batches` / `payment_import_rows` — the LOCKBOX REMITTANCE
    import (US-PAY-003, BR-PAY-023). A different file, a different direction:
    that one creates `payments`, this one reads a BANK's statement. Named because
    `apps/payments/lockbox.py` serves both file families and says so.
  * The match-rule config beyond the date tolerance. r12 #10 pairs "imports" with
    "match-rule config"; the one ratified parameter is
    `bank_match_date_tolerance_days` (BR-PAY-019, seeded 3), which already lives
    on S71 Finance controls and is read through `apps/payments/settings_seam.py`.
    No second copy is stored on these tables.
  * ~~A reason-code LOOKUP~~ — **BUILT 2026-09-01 (CS-18 / CR-059 task 46).**
    This bullet read *"nothing ratifies a catalogue of them … seeding a
    vocabulary is reported, not invented"*, and CS-18 is the ruling that asks
    for it, so it is no longer invention: `BankRecDifferenceReason` below is the
    seeded, tenant-extensible list and `reconciliation._canonical_reason` checks
    every explanation against it. B2 r14 #2's lookup remains the REVERSAL reason
    family and is a different list.

⚠ **THE FOUR ADDITIONS OF 2026-09-01, CR-059 WAVE W8, EACH BY ITS SPEC:**
  * `bank_statement_imports.opening_balance` / `.closing_balance` (CS-14, task
    43) — nullable, never backfilled;
  * `bank_rec_resolutions.batch` becomes nullable and `.bank_line` arrives
    (CS-16, task 44) — a resolution may hang off a LINE;
  * `bank_rec_match_sets` + `bank_rec_match_members` (CS-17, task 45) — the PO's
    2026-08-12 many-to-one ruling, twenty days late;
  * `bank_rec_difference_reasons` (CS-18, task 46).

**So this file now holds TEN tables, not six**, and the header sentence above
still says six. It is left as written because it is a true statement about what
EP-PAY-06 needed; this note is the correction a reader needs beside it.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.dbfields import uuid7_pk

# ── B2 §1 `batch_status` — the four values, verbatim ────────────────────────
# Not a lookup table and not tenant-extensible: the lock trigger, the S37 status
# tabs and the reconcile path are all written against exactly these four.
BATCH_IN_TRANSIT = "in_transit"  # cut, and the bank has not shown it yet
BATCH_UNMATCHED = "unmatched"  # a statement is in and this batch is not tied
BATCH_MATCHED = "matched"  # a bank line is linked; the difference may be 0
BATCH_RECONCILED = "reconciled"  # LOCKED (BR-PAY-004)
BATCH_STATUSES = (BATCH_IN_TRANSIT, BATCH_UNMATCHED, BATCH_MATCHED, BATCH_RECONCILED)

#: US-PAY-023 §5's own list of trail events, in the order a batch meets them.
#: Codes rather than prose — the trail is grouped and filtered on them, and the
#: S39 event log renders each one with its payload.
EVENT_CREATED = "created"
EVENT_REGROUPED = "regrouped"  # members added to a batch that already existed
EVENT_MATCHED = "matched"  # a bank line was linked (auto or by a human)
EVENT_FLAGGED = "flagged"  # linked, and the amounts differ — S40 owes an answer
EVENT_RESOLVED = "resolved"  # a difference was explained with reason + GL
EVENT_RECONCILED = "reconciled"
EVENT_UNRECONCILED = "unreconciled"
BATCH_EVENTS = (
    EVENT_CREATED,
    EVENT_REGROUPED,
    EVENT_MATCHED,
    EVENT_FLAGGED,
    EVENT_RESOLVED,
    EVENT_RECONCILED,
    EVENT_UNRECONCILED,
)

#: ── CS-18 (CR-059 task 46) · THE SEEDED DIFFERENCE REASONS ─────────────────
#: The single ratified source for `bank_rec_difference_reasons`, held HERE and
#: NOT in `lookup_defaults.json` — the `premises_types` / BR-MET-034 precedent
#: (apps.tenancy.services SEED_LIST_OWNERS says so in its own comment): one
#: source cannot drift from a second copy, and the fixture deliberately carries
#: no entries for this list.
#:
#: **WHAT IS IN IT AND WHY EACH IS HERE.** The first two are the codes this
#: module already writes and its tests already assert — `processor_fee` is
#: `derive_processor_fee`'s own default and `bank_fee` is PE-11's ❄️ −5.00 —
#: so seeding them means no explanation already written becomes unreadable. The
#: rest are CS-16's own three examples of a line that is not a deposit of ours
#: (*"a customer paying the bank directly, an interest credit, a bank error"*)
#: plus the two causes CS-18 names as the point of reporting on cause at all
#: (*"how much was processor fees this quarter, how much was error"*).
#:
#: ⚠ **THE CONTENT IS A LANE JUDGMENT, NOT A RATIFIED VOCABULARY.** CS-18 rules
#: that the list EXISTS, is seeded and is tenant-extensible; it enumerates
#: nothing. Recorded in 12-governance/02-decision-log.md as a judgment with its
#: reasoning. Every row seeds `is_system=True`, so BR-TEN-036 keeps it from
#: being deleted and BR-TEN-034 leaves deactivate as the way to stop offering
#: one — which is what a utility that calls it something else does.
SEED_DIFFERENCE_REASONS: tuple[tuple[str, str], ...] = (
    ("processor_fee", "Card processor fee"),
    ("bank_fee", "Bank charge"),
    ("bank_interest", "Interest the bank credited"),
    ("customer_paid_bank_direct", "Customer paid the bank directly"),
    ("bank_error", "Bank error"),
    ("deposit_error", "Our own deposit or keying error"),
    # `cash_short` was ALREADY in use before this list existed — US-PAY-022
    # TC-6's cash drawer is short 80.00 and explains 60.00 of it. A vocabulary
    # that omitted a reason the product already writes would have made an
    # existing signed test unrunnable, which is how a "new list" quietly becomes
    # a regression. Found by running that test, not by reading the spec.
    ("cash_short", "Cash drawer short or over"),
    ("returned_item", "Returned item"),
    ("timing_difference", "Timing — banked in a different period"),
)


class BankAccount(models.Model):
    """One bank account of this tenant (B2 r14 #1, the rec target).

    S38 step 1's select — *"Chase Operating ••4021"* — and the tag half of the
    statement import's idempotency key. `mask` is the last digits a human
    recognises and is deliberately NOT the account number: nothing in this
    product needs the full number, and B2 §6's PII posture is that a column you
    do not store is a column that cannot leak.

    **No GL account hangs off this row.** The prototype's accounting hand-off
    card offers the bookkeeper a deposit account, and which ledger account a
    bank account maps to is a real question with no ratified answer; the
    reconciliation posting resolves `cash` BY DESIGNATION instead (OQ-110's
    closure), which is one account per tenant. Reported in
    `apps/payments/reconciliation.py`, not modelled on a guess.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()  # "Chase Operating"
    mask = models.TextField(null=True, blank=True)  # "4021" — display only
    active = models.BooleanField(default=True)  # deactivate, never delete (BR-TEN-034 shape)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_accounts"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uq_bank_accounts_name"),
        ]


class DepositBatch(models.Model):
    """One day's takings in one method (B2 §2 `deposit_batches`, verbatim).

    Columns and where each comes from — B2 §2 for all seven, with two notes:

    * `method` — B2 §2 types it `payment_method_t`, an ENUM that no longer
      exists: r5 #20 and r16 #3 swapped the tenant-extensible enums for seeded
      LOOKUP tables (BR-TEN-036, OQ-031 closed). Same swap `payments.method`
      already made, and pointing at the same table, so a batch and its members
      can never disagree about what a "check" is.
    * `recorded_total` — Σ of the member payments' amounts, system-derived and
      **never hand-edited** (US-PAY-020 §5). PE-10, ❄️ frozen: checks
      292.87 + 142.30 + 36.22 = **471.39**; cash 105.36 + 16.42 = **121.78**.
      An assertion, not a rounding event — the members are finalized 2dp
      figures (US-PAY-020 §7).
    * `bank_total` — what the BANK said, stamped from the matched `bank_lines`
      row at match time. NULL until a statement arrives, which is what the S37
      "pending" column renders.

    ⚠ **RE-KEYED 2026-09-22 BY `P0.6` — A BATCH IS ONE TILL AND ONE TENDER.**
    Until then the structural key was `UNIQUE (tenant, deposited_on, method)`,
    the grouping half of BR-PAY-025: *"deposit batches group day × method"*.
    The PO superseded that half on 2026-09-22 (decision log, *"(a) Payments and
    ledger together"*), and the replacement is
    `UNIQUE (tenant, session, method) WHERE session_id IS NOT NULL`.

    **Why a till and not a day:** a day × method batch is the whole utility's
    takings, so at a two-counter office Dana's `$1,240` of cheques and Sam's
    `$880` are one row that neither clerk can be held to. One per till makes
    each drawer answerable for its own deposit, and the day still ties to
    `$2,120`.

    **Why the tender stays in the key:** a bank credits cash and cheques
    separately and they clear on different days, so a single `$1,240` line
    could never be reconciled against a statement. Dana's shift taking `$600`
    cash and `$640` cheques is ONE till, TWO tenders and therefore **two
    batches** (PO, `OQ-PAY-12577` (a)).

    ⚠ **THE KEY IS PARTIAL, AND THE `WHERE` IS THE PO'S RULING RATHER THAN AN
    OPTIMISATION.** *"A batch with no session is one banked the old way"* — the
    batches banked before the re-key have no session and nothing is written to
    them, because `BR-PAY-004` locks a reconciled batch and a marker would be
    an UPDATE. A partial key that ignores them is only safe because **no new
    row may join that population**, which `trg_deposit_batch_needs_session`
    (`payments/0033`) enforces AT THE DATABASE rather than assuming.

    B2 §2 declares `UNIQUE (tenant_id, code)`; that one is here too and it is
    no longer a rendering of the same facts — since `P0.6` the code is
    ALLOCATED from the tenant's `deposit_batch` series, so it is an independent
    guarantee rather than a weaker echo of the grouping key.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `DEP-260922-0001` — ALLOCATED from the tenant's `deposit_batch` series
    #: since `P0.6` (PO ruling 2026-09-22, *"(b) Put it in Settings today —
    #: DEP-260922-0001 — Settings → Numbering, like every other number"*).
    #: ⚠ Batches banked BEFORE that read `DEP-260808-CHK` (PE-10, ❄️ frozen)
    #: and keep it: hard rule 4 freezes a financial record, and two shapes of
    #: code is the same two-populations answer the PO gave for the sessions.
    code = models.TextField()
    #: ── `P0.6` · WHOSE TILL THIS DEPOSIT CAME OUT OF ───────────────────────
    #: NULL means *banked the old way, before tills existed* — the absence IS
    #: the fact (PO ruling 2026-09-22, option (d)). Nothing may create a new
    #: batch without one; `trg_deposit_batch_needs_session` refuses it.
    #:
    #: Electronic money — ACH, card, wire, lockbox — names that day's SYSTEM
    #: till, which has no owner and no service centre. So this column answers
    #: *who is accountable for this deposit* with a person, with "nobody, it
    #: arrived over a wire", or with "nobody, and it predates tills" — three
    #: different answers that a single nullable FK keeps apart.
    session = models.ForeignKey(
        "payments.CounterSession",
        on_delete=models.PROTECT,
        db_column="session_id",
        related_name="deposit_batches",
        null=True,
        blank=True,
    )
    #: ⚠ **NULLABLE SINCE 2026-10-21 (`CR-186-BRC10`, `payments/0051`), AND
    #: NULL MEANS "ALL TENDERS".** PO: *"this is one batch only - it will ahve
    #: 1 batch ID not 2"* for a till's cash and cheques. A batch made after the
    #: change is one per till or channel per day and carries no tender; its
    #: per-tender totals are read from its members (`tender_totals`). Batches
    #: banked before it keep the single tender they were cut for.
    method = models.ForeignKey(  # r5 #20 swap: the lookup replaces B2's enum column
        "tenancy.PaymentMethod",
        on_delete=models.PROTECT,
        db_column="method_id",
        null=True,
        blank=True,
    )
    #: DB-3 money. Σ members; `services.record_payment` never writes it and no
    #: endpoint accepts it.
    recorded_total = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    bank_total = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    status = models.TextField(default=BATCH_IN_TRANSIT)
    #: BR-PAY-025 / RQ-5 — the POSTING day (the drawer day), never the clearing
    #: day. See the module docstring; EP-PAY-06 said clearing and was stale.
    deposited_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "deposit_batches"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_deposit_batches_code"),
            # BR-PAY-025's grouping key, as amended 2026-09-22 by `P0.6`. See
            # the class docstring for why it is one till × one tender and why
            # the `WHERE` is the PO's ruling rather than a tuning choice.
            models.UniqueConstraint(
                fields=["tenant", "session", "method"],
                condition=Q(session__isnull=False),
                name="uq_deposit_batches_session_method",
            ),
            # `CR-186-BRC10` — ONE all-tenders batch per till or channel-day.
            # The legacy key above still guards the per-tender batches banked
            # before 2026-10-21; NULL methods never collide under it.
            models.UniqueConstraint(
                fields=["tenant", "session"],
                condition=Q(session__isnull=False, method__isnull=True),
                name="uq_deposit_batches_session_all_tenders",
            ),
            models.CheckConstraint(
                condition=Q(status__in=BATCH_STATUSES), name="ck_deposit_batches_status"
            ),
        ]
        indexes = [
            # B2 §4 `ix_deposit_batches_status` — "unmatched batches", verbatim.
            models.Index(fields=["tenant", "status"], name="ix_deposit_batches_status"),
            # S37's default sort (EP-PAY-06 capability matrix: deposited_on desc).
            models.Index(fields=["tenant", "-deposited_on"], name="ix_deposit_batches_day"),
        ]


# ── `P2.10` · WHEN A BATCH IS BANKABLE — ONE EXPRESSION, FOUR READERS ───────
#
# The blueprint's own word, from the "What it changes" table on p059: at Close,
# *"The batch becomes BANKABLE. It **is** the deposit batch, so it appears on
# Finance → Deposits ready to be matched"*. At Start that same table changes
# nothing on Deposits — it lists only the `Start counter` control.
#
# ⚠ **`P0.6` MADE THAT SENTENCE FALSE BY MAKING THE BATCH EARLIER.** Before the
# re-key a batch was CREATED at the cut, so every batch that existed was, by
# construction, a sealed day's takings. Since the re-key the batch exists from
# the moment the till OPENS, and `bankrec_read.batch_queryset` filtered on
# `tenant_id` alone — so Dana's drawer appears on Finance → Deposits at 08:55,
# statused `in_transit` (*"cut, and the bank has not shown it yet"*), counted
# into the In-transit tile, and matchable. **Measured on 2026-09-23** against a
# seeded till: `DEP-260923-9001`, `$612.50`, Dana's till still open, served in
# the list and folded into `in_transit_total`.
#
# **What that costs if it ships:** `auto_match` scans every `in_transit` batch,
# so a statement line could tie itself to a drawer still taking money; and
# `reconcile_batch` would LOCK it (`BR-PAY-004`) while the clerk goes on taking
# money into it, after which `recorded_total` can never agree with the bank
# again. Nothing in this file could see that, because nothing here knew a
# session could be open.
#
# **Why one expression and not a test at each site.** It has EIGHT readers —
# the Deposits list · its KPI strip · S38 step 2's hand-match picker · the
# `needs_a_look` classifier behind it · the reconciliation statement's
# *deposits in transit* · `auto_match`'s candidate scan · and the two human
# write paths — and `CR-136-BRC07` §3.2 rules the identical shape for
# *Not counted*:
#
# ⚠ **THE COUNT WAS FOUR UNTIL 2026-09-23 AND FOUR WAS WRONG, WHICH IS THE
# ARGUMENT FOR THE EXPRESSION RATHER THAN AGAINST IT.** The first draft of
# `P2.10` narrowed the list and `auto_match`, guarded the two write paths, and
# left three further reads of this same population filtering on `status` alone
# — the field this whole rule exists to say cannot answer the question. They
# were found by grepping for the remaining `BATCH_IN_TRANSIT` filters, not by
# any check. **If you add a read of the in-transit population, it reads this.**
# *"one derived expression with four readers … Write it once"* (B14 rule 43).
# A Python mirror of the same rule is a second copy free to drift, so the
# single-row question is asked of the DATABASE through this same `Q`.
#
#: The three populations this keeps apart, and why each answers as it does:
#:
#:   * `session_id IS NULL` — banked BEFORE tills existed (PO 2026-09-22,
#:     option (d): *"a batch with no session is one banked the old way"*).
#:     Bankable: it was cut from cleared money and no drawer is open behind it.
#:   * a SYSTEM till — born CLOSED (`reconciliation._system_session`), so ACH,
#:     card, wire and lockbox are bankable from their first moment and this
#:     rule is invisible to them. That is the same property that keeps them off
#:     the supervisor's list, reused rather than restated.
#:   * a PERSON's till — bankable exactly when somebody sealed it, by a count
#:     (`counted`) or by a supervisor (`forced`). `closed_at` is the fact,
#:     never `close_kind`: a forced close has no count and its money is still
#:     the bank's to receive.
BANKABLE = Q(session__isnull=True) | Q(session__closed_at__isnull=False)


def bankable(queryset):
    """Narrow a `DepositBatch` queryset to the batches whose till is sealed.

    The caller supplies the tenant scoping (hard rule 1) and this adds the one
    condition, so no queryset in this repo reaches a batch without a tenant on
    it merely because it wanted this filter.
    """
    return queryset.filter(BANKABLE)


def is_bankable(batch) -> bool:
    """The SAME expression, asked of ONE row — evaluated in the database.

    ⚠ **Deliberately a query rather than `batch.session_id is None or
    batch.session.closed_at is not None`.** That Python line is the identical
    rule written a second time in a second language, and the day `BANKABLE`
    gains a clause the two would answer differently on a money path. This costs
    one indexed lookup on a write path that is already writing.

    **It fails CLOSED.** With no `app.tenant_id` set the RLS policy matches no
    row, this answers False, and the write is refused — which is the safe
    direction for a guard on matching and reconciling.
    """
    return bankable(type(batch).objects.filter(tenant_id=batch.tenant_id, pk=batch.pk)).exists()


class DepositBatchEvent(models.Model):
    """One line of the S39 reconciliation trail — append-only, never truncated.

    US-PAY-023 §5 names the shape and the events; r12 #17 delegates the DDL.
    The trail is the SINGLE source of "who reconciled this and when": there is
    deliberately no `reconciled_by` column on the batch, because two records of
    one fact drift and the header can read the trail (hard-won law 5, applied
    to a column instead of a file).

    `detail` carries the figures of the event (money as STRINGS, the same
    discipline the audit payload uses) so the S39 log can render *"Flagged
    –$100 difference"* without re-deriving anything from rows that have since
    moved on.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    batch = models.ForeignKey(
        DepositBatch, on_delete=models.PROTECT, db_column="batch_id", related_name="events"
    )
    event = models.TextField()
    actor = models.ForeignKey(  # NULL = a job cut it (the audit row names which)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="actor_user_id",
    )
    #: BR-TEN-043 — the caller names the moment; nothing here reads a clock.
    occurred_at = models.DateTimeField()
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "deposit_batch_events"
        constraints = [
            models.CheckConstraint(
                condition=Q(event__in=BATCH_EVENTS), name="ck_deposit_batch_events_event"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch", "occurred_at"], name="ix_batch_events_batch"),
        ]


class BankStatementImport(models.Model):
    """One statement file, imported once (B2 r12 #10 · BR-PAY-028 file+tags).

    The idempotency shape is the one `read_import_batches` already uses and is
    NOT re-invented: `file_hash` is the SHA-256 of the exact bytes uploaded and
    `tag_fingerprint` is the digest of the step-1 tags (bank account + statement
    period). The pair carries a UNIQUE index, so a race that beats the
    service-layer check still cannot double-import a statement — US-PAY-021
    TC-5: *"Same statement file re-imported → Blocked … who/when/link shown; no
    duplicate bank_lines."*

    `imported_by` and `imported_at` exist for exactly that message: a refusal
    that cannot name who did it first is a refusal a clerk cannot act on.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, db_column="bank_account_id"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    file_name = models.TextField(null=True, blank=True)
    file_hash = models.TextField()  # SHA-256 hex, computed server-side
    tag_fingerprint = models.TextField()  # 🔒 the tag half of the file+tags key
    line_count = models.IntegerField(default=0)
    #: ── CS-14 (CR-059 task 43) · WHAT THE BANK SAID THE ACCOUNT HELD ──────
    #: The statement's own opening and closing figures, captured on S38 step 1
    #: beside the account and period it already asks for. They are what makes a
    #: reconciliation PROVABLE: today the books and the bank are compared batch
    #: by batch and never AS TOTALS, so "the bank rec is done" is a claim nobody
    #: can check. `bankrec_read.reconciliation_statement` is the read that
    #: compares them.
    #:
    #: ⚠ **BOTH ARE NULLABLE AND NOTHING BACKFILLS THEM** (CS-14: *"Two nullable
    #: columns, backfilled by nobody — an import made before the change simply
    #: has no balances and says so"*). A statement imported before 2026-09-01
    #: has NULL in both, and the period read serves `None` for every figure that
    #: depends on them rather than `0.00`: a bank balance nobody recorded is not
    #: a bank balance of zero (DEF-127's lesson, and CS-13 shipped it again).
    #: DB-3 money, `NUMERIC(18,6)`, signed — an overdrawn account is negative.
    opening_balance = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    imported_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="imported_by",
    )
    imported_at = models.DateTimeField()  # BR-TEN-043 — an input, never a clock
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_statement_imports"
        constraints = [
            # 🔒 DB-12 "file+tags imports" — the structural half of BR-PAY-028.
            models.UniqueConstraint(
                fields=["tenant", "file_hash", "tag_fingerprint"],
                name="uq_bank_statement_imports_idempotency",
            ),
        ]


class BankLine(models.Model):
    """One line of a bank statement (B2 §2 `bank_lines`, verbatim + its file).

    `deposit_batch` is B2 §2's own nullable link and it is what "matched" means:
    NULL is either "not looked at yet" or S38's fourth tile, *"Not in our
    system"*. `statement_import` is r12 #10's addition — a line has to know
    which file it arrived in, or a re-import cannot be told from a correction.

    `posted_on` is the BANK's date. Matching compares it against the batch's
    `deposited_on` (the drawer day) inside the tenant's tolerance — which is
    the only reason a drawer day and a bank day can tie at all.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    statement_import = models.ForeignKey(
        BankStatementImport,
        on_delete=models.PROTECT,
        db_column="statement_import_id",
        related_name="lines",
    )
    deposit_batch = models.ForeignKey(
        DepositBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="deposit_batch_id",
        related_name="bank_lines",
    )
    posted_on = models.DateField()
    reference = models.TextField(null=True, blank=True)  # 'CHECK DEPOSIT 4410'
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3
    line_no = models.IntegerField(null=True, blank=True)  # 'Aug 1–6 · line 18' (S39)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_lines"
        constraints = [
            # One bank line ties at most one batch and one batch at most one
            # line — the "one-to-one" half of BR-PAY-019's matching rule, made
            # structural. Grouped matching (many-to-one) is NOT ruled: the PO's
            # OQ-144 closure answered the FEE question and not the combined-
            # credit one, which is raised as OQ-161 rather than assumed.
            models.UniqueConstraint(
                fields=["tenant", "deposit_batch"],
                condition=Q(deposit_batch__isnull=False),
                name="uq_bank_lines_batch",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "statement_import"], name="ix_bank_lines_statement"),
            models.Index(fields=["tenant", "posted_on"], name="ix_bank_lines_posted"),
        ]


class BankRecResolution(models.Model):
    """One explanation of one difference — reason + GL, or it does not exist.

    BR-PAY-019 (CONFIRMED): every exception is worked *"with reason + GL"*, and
    BR-PAY-035 makes the prototype's **"Force match anyway" permanently
    SUPERSEDED** — no unexplained residual ever reconciles. So this row is not
    a note attached to a reconcile; it is the thing that makes one possible,
    and the invariant `Σ amounts = bank_total − recorded_total` is asserted in
    `apps/payments/reconciliation.py` before a batch may move.

    **`amount` IS SIGNED, and that is deliberate.** The difference is
    `bank − recorded`, so the card day of the PO's ruling is **−147.50** and
    each explanation of it is negative. A bank line LARGER than the batch (bank
    interest) is positive. Direction is the sign here and the SIDE in the books
    — `journal_lines` cannot carry a negative amount (B2 §2's
    `CHECK (amount >= 0)`), so the posting flips it into a debit or a credit and
    this column stays the arithmetic that has to foot.

    `gl_account_id` is a plain uuid rather than an FK to `ledger_accounts`, the
    same deferred-FK convention (B11 F-3) `invoice_lines.gl_account_id` uses;
    the service validates it against the LEDGER'S OWN read (a live account of
    this tenant's chart) rather than trusting a constraint that would tie two
    modules' migration graphs together.

    `journal_entry_id` is the entry this resolution rode into the books on. It
    is written in the same transaction as the reconcile; a resolution with no
    entry would be an explanation nobody posted.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ── CS-16 (CR-059 task 44) · NULLABLE SINCE 2026-09-01 ────────────────
    #: A resolution used to be able to hang off a BATCH and nothing else, so a
    #: bank line that is genuinely not a deposit of ours — a customer paying the
    #: bank directly, an interest credit, a bank error — could only be left
    #: alone, **and it sat there forever with nothing said about it**. Exactly
    #: one of `batch` and `bank_line` is set; the database check below is the
    #: guarantee, not this comment.
    batch = models.ForeignKey(
        DepositBatch,
        on_delete=models.PROTECT,
        db_column="batch_id",
        related_name="resolutions",
        null=True,
        blank=True,
    )
    #: CS-16's whole change. The row already carried the signed amount, the
    #: reason, the GL account, the note and the author — **only its parent was
    #: fixed**, which is the spec's own sentence.
    bank_line = models.ForeignKey(
        "payments.BankLine",
        on_delete=models.PROTECT,
        db_column="bank_line_id",
        related_name="resolutions",
        null=True,
        blank=True,
    )
    #: BR-PAY-019's "reason". **A CODE FROM THE TENANT'S OWN LIST SINCE CS-18**
    #: (CR-059 task 46) — `bank_rec_difference_reasons`, seeded and
    #: tenant-extensible, deactivated and never deleted like every other
    #: reference list. The column stays TEXT rather than an FK for the reason
    #: `payments.method` did not: a resolution is financial history the instant
    #: it is written (the append-only trigger in migration 0005), so the code it
    #: was explained under must survive the row being deactivated or renamed.
    #: `note` below is still free text and is where the DETAIL goes.
    reason_code = models.TextField()
    gl_account_id = models.UUIDField()  # deferred FK to ledger_accounts (B11 F-3)
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # DB-3, SIGNED
    note = models.TextField(null=True, blank=True)  # S40's audit note
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="actor_user_id",
    )
    journal_entry_id = models.UUIDField(null=True, blank=True)
    #: ── LBX-05 (DEF-PAY-10694) · G3 RULED 2026-10-30 ─────────────────────
    #: The reversing payment row a RETURNED statement line was matched to.
    #: PO, verbatim: *"Q1. May a bank-statement line that isn't a deposit post
    #: to the books?-A"*. Set only on a line-parented row (the check below),
    #: and at most once per reversal (the partial unique below): one bank
    #: return is one reversal, and a reversal is never matched twice.
    reversal_payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        db_column="reversal_payment_id",
        related_name="bank_line_matches",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_rec_resolutions"
        constraints = [
            # CS-16: a resolution explains ONE thing. Two parents would make the
            # tie-out ambiguous (is this amount part of the batch difference or
            # of the line's?) and no parent would be an explanation of nothing.
            models.CheckConstraint(
                condition=(
                    Q(batch__isnull=False, bank_line__isnull=True)
                    | Q(batch__isnull=True, bank_line__isnull=False)
                ),
                name="ck_bank_rec_resolutions_one_parent",
            ),
            # LBX-05 — a match to a reversal is a LINE's, never a batch's.
            models.CheckConstraint(
                condition=Q(reversal_payment__isnull=True) | Q(bank_line__isnull=False),
                name="ck_bank_rec_resolutions_reversal_on_line",
            ),
            # LBX-05 — one explanation per statement line, in the DATABASE as
            # well as in `resolve_bank_line`, so two clerks racing one line
            # cannot both post it.
            models.UniqueConstraint(
                fields=["tenant", "bank_line"],
                condition=Q(bank_line__isnull=False),
                name="uq_bank_rec_resolutions_line",
            ),
            # LBX-05 — a reversal is matched to ONE returned line.
            models.UniqueConstraint(
                fields=["tenant", "reversal_payment"],
                condition=Q(reversal_payment__isnull=False),
                name="uq_bank_rec_resolutions_reversal",
            ),
            # LBX-05 — one journal entry explains ONE line: a bank fee posted on
            # a Reverse and then claimed by a statement line cannot be claimed
            # by a second line (the fee is in the books once).
            models.UniqueConstraint(
                fields=["tenant", "journal_entry_id"],
                condition=Q(bank_line__isnull=False, journal_entry_id__isnull=False),
                name="uq_bank_rec_resolutions_line_entry",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="ix_bank_rec_resolutions_batch"),
            models.Index(fields=["tenant", "bank_line"], name="ix_bank_rec_resolutions_line"),
        ]


class BankRecMatchSet(models.Model):
    """CS-17 (CR-059 task 45) — MANY lines to one batch, and one to many.

    **RULED, NOT PROPOSED.** PO 2026-08-12 closing `OQ-161`, verbatim:
    *"Build many-to-one matching"*. Worked on the PO's own figures:
    `DEP-260805-CHK` **$2,840.00** and `DEP-260805-ACH` **$14,280.00** are banked
    the same afternoon and the bank posts ONE credit of **$17,120.00**. Under the
    one-to-one link that money can never be reconciled by anybody, ever — no
    tolerance setting and no fee line ties it — so $17,120 sits in undeposited
    funds and the month's "bank rec current" checklist item is false.

    ════════════════════════════════════════════════════════════════════════
    THE SET'S TOTALS MUST BE **EXACTLY** EQUAL — CS-17's OWN NEW RULE
    ════════════════════════════════════════════════════════════════════════
    CS-17, verbatim: *"A match may be a set; the set's totals must be equal and
    every member's date within tolerance."* Exact equality, and NOT the tenant's
    `bank_match_amount_tolerance` that the 1:1 matcher uses, for a reason worth
    stating: on ONE pair a few cents of slack has exactly one place to go (the
    difference the clerk then explains with a reason and a GL), and in a set of
    five members there is no ruled way to apportion it across them. So the
    tolerance stays where a difference has an owner, and a set that does not
    foot is refused by name rather than tied and argued about later. At the
    seeded default of 0 the two rules agree anyway.

    ════════════════════════════════════════════════════════════════════════
    WHY THE 1:1 COLUMN SURVIVES BESIDE THIS TABLE
    ════════════════════════════════════════════════════════════════════════
    `bank_lines.deposit_batch_id` is B2 §2's own column, it is WRITE-ONCE by the
    trigger in migration 0005, and every batch reconciled since 2026-08-11 was
    tied through it. Dropping it would rewrite settled financial history to make
    room for a new shape. So the set is the SECOND way to tie, used when either
    side has more than one member, and the two can never both hold: `match_set`
    refuses a line or a batch already tied the other way, and `match_bank_line`
    refuses one already in a set.

    ════════════════════════════════════════════════════════════════════════
    A SET IS WRITE-ONCE, LIKE THE LINK IT SITS BESIDE
    ════════════════════════════════════════════════════════════════════════
    There is no dissolve path and no status column. That is not an omission: the
    1:1 match has been write-once since the day it was written (*"Re-pointing it
    would move a batch onto a different bank line without touching the batch at
    all"*), Unreconcile is BR-PAY-004's only way back from a reconcile, and
    inventing a dissolve verb here would be this lane ratifying a rule nobody
    ruled. REPORTED rather than invented — a set tied wrongly is a question for
    the PO, exactly as a batch cut on the wrong day is.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: Σ of the member lines' amounts, which by the rule above is also Σ of the
    #: member batches' recorded totals. Stamped at match time so the S39 panel
    #: can show what the set tied at without re-deriving it from rows that have
    #: since been reconciled. DB-3 money.
    matched_total = models.DecimalField(max_digits=18, decimal_places=6)
    #: BR-TEN-043 — the caller names the moment; nothing here reads a clock.
    matched_at = models.DateTimeField()
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="actor_user_id",
    )
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_rec_match_sets"
        indexes = [
            models.Index(fields=["tenant", "matched_at"], name="ix_bank_rec_match_sets_when"),
        ]


class BankRecMatchMember(models.Model):
    """One bank line, or one deposit batch, inside a `BankRecMatchSet`.

    ONE table rather than two link tables, and exactly one of the two FKs is set
    (the check constraint is the guarantee). Two tables would let a set exist
    with members on one side only and no single query could say so.

    The two partial UNIQUE indexes are the structural half of CS-17's *"no
    forcing"*: a bank line belongs to at most one set and a batch to at most
    one, so a clerk cannot spend the same $17,120.00 credit twice by tying it
    into a second set. They are the set-shaped twin of `uq_bank_lines_batch`.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    match_set = models.ForeignKey(
        BankRecMatchSet, on_delete=models.PROTECT, db_column="match_set_id", related_name="members"
    )
    bank_line = models.ForeignKey(
        "payments.BankLine",
        on_delete=models.PROTECT,
        db_column="bank_line_id",
        related_name="match_members",
        null=True,
        blank=True,
    )
    batch = models.ForeignKey(
        DepositBatch,
        on_delete=models.PROTECT,
        db_column="batch_id",
        related_name="match_members",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_rec_match_members"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(bank_line__isnull=False, batch__isnull=True)
                    | Q(bank_line__isnull=True, batch__isnull=False)
                ),
                name="ck_bank_rec_match_members_one_side",
            ),
            models.UniqueConstraint(
                fields=["tenant", "bank_line"],
                condition=Q(bank_line__isnull=False),
                name="uq_bank_rec_match_members_line",
            ),
            models.UniqueConstraint(
                fields=["tenant", "batch"],
                condition=Q(batch__isnull=False),
                name="uq_bank_rec_match_members_batch",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "match_set"], name="ix_bank_rec_match_members_set"),
        ]


class BankRecDifferenceReason(models.Model):
    """CS-18 (CR-059 task 46) — the difference reasons, as a real list.

    **Why it exists.** The reason on a resolution was FREE TEXT, so no two
    clerks describe the same difference the same way and nobody can report on
    cause — *how much was processor fees this quarter, how much was error*. This
    module's own docstring has said so since the day it was written (*"a
    reason-code LOOKUP … seeding a vocabulary is reported, not invented"*);
    CS-18 is the ruling that asks for it, so it is no longer invention.

    **It is an ordinary S8 reference list**, the shape `bank_accounts` already
    set (BR-SHL-035: *"new reference data = a new card + its config, never a new
    layout"*), so NO new screen ID is minted. Deactivated and never deleted:
    `bank_rec_resolutions.reason_code` is append-only financial history, so a
    reason that stops being offered must still resolve on every explanation
    already written under it.

    **`default_gl_account_id` is a CONVENIENCE, never the control.** BR-PAY-019
    requires a reason AND a GL on every difference; this column lets S40
    pre-select the account a reason usually posts to (a processor fee → 6800
    Bank fees) and the resolution still stores its own `gl_account_id`, checked
    live against the ledger's chart at reconcile time. A pre-selection that
    became the stored value would put a deactivated account into the books
    months after somebody changed the list. Deferred FK (B11 F-3), exactly as
    `payment_methods.clearing_gl_account_id` is.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    #: NULL = the tenant has mapped no default account for this reason, which is
    #: a real state and the SEEDED state for every row: the ❄️ signed chart's
    #: numbers are not constants in this repo (DEF-067) and a fixture cannot know
    #: a tenant's own account ids. S40 then asks for the account, which is what
    #: BR-PAY-019 requires anyway.
    default_gl_account_id = models.UUIDField(null=True, blank=True)  # DEFERRED FK → ledger
    is_system = models.BooleanField(default=False)  # BR-TEN-036 — a seeded row is not deletable
    active = models.BooleanField(default=True)  # BR-TEN-034 — deactivate, never delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_rec_difference_reasons"
        constraints = [
            # BR-TEN-030 — identity is unique per tenant, case-insensitively.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("code"),
                name="uq_bank_rec_diff_reasons_code_ci",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "active"], name="ix_bankrec_diff_reason_live"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@b6e4c19 (sha1[:7] of the five sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments DDL + Addenda r12 #10/#13/#17, r14 #1, r16 #6 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md §6 · 04-docs/05-modules/08-payments/07-pre-session-model.md §7 PE-10/PE-11)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — model classes) E=deferred(no UI; S37–S40 are unbuilt and REPORTED, not claimed) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean · migrate applied against a LIVE Postgres cluster · pytest tests/test_us_pay_020_023_bank_rec.py · -m isolation on live Postgres (the catalog sweep names any table lacking RLS)
# exceptions: (1) these classes live OUTSIDE apps/payments/models.py because
#         another lane held that file; `apps/payments/apps.py` imports this
#         module so the registry sees them. A move, not a redesign — REPORTED
#         (2) `bank_accounts`, `bank_statement_imports`, `bank_rec_resolutions`
#         and `deposit_batch_events` are NOT in B2 §2: they are r14 #1, r12 #10
#         and US-PAY-023 §5 respectively, authored under r12 #17's DDL delegation
#         (3) UNIQUE (tenant, deposited_on, method) on `deposit_batches` and
#         UNIQUE (tenant, deposit_batch) on `bank_lines` are this lane's
#         structural halves of BR-PAY-025's grouping and BR-PAY-019's one-to-one
#         matching. Both go BEYOND B2 §2's single `UNIQUE (tenant_id, code)` —
#         REPORTED
#         (4) there is NO `reconciled_by` column: the trail is the single source
#         of that fact (hard-won law 5 applied to a column)
#         (5) NO regroup path exists — a payment joins one batch forever, because
#         `payments.deposit_batch_id` is opened WRITE-ONCE by migration 0005 and
#         nothing ratifies a regroup event's shape (US-PAY-020 TC-5 mentions one)
#         (6) ⚠ SUPERSEDED 2026-09-01 (CS-18 / CR-059 task 46 → the reason CATALOGUE IS built: `BankRecDifferenceReason`, seeded from `SEED_DIFFERENCE_REASONS` above). Kept rather than deleted because it is the record of how long BR-PAY-019's "a reason" went un-enumerable
#         (7) [2026-09-01, CR-059 W8] `bank_lines.deposit_batch_id` is NOT dropped although CS-17 says "replace the single line-to-batch link with a match set": it is B2 §2's own column, it is write-once by migration 0005, and every batch reconciled since 2026-08-11 was tied through it. The SET is a second way to tie and each door refuses a member the other holds. Judgment recorded in 12-governance/02-decision-log.md
#         (8) [2026-09-01] a match SET has no dissolve path and no status column, in the database or the service — CS-17 rules the set IN and rules nothing about undoing one
#         (9) [2026-09-01] the content of `SEED_DIFFERENCE_REASONS` is a LANE JUDGMENT: CS-18 rules that the list exists, is seeded and is tenant-extensible, and enumerates nothing. Eight rows, every one `is_system`, recorded with its reasoning in the decision log
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
