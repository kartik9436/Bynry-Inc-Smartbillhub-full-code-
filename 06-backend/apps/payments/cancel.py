# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.2 — `POST /payments/{id}/cancel`, *"the only
#           genuinely missing logic in the module"*. Blueprint
#           `05-prototype/06 Payments Page Blueprint.pdf` 2·3d (p043–p044) and
#           the act table on p050. The drawing's question, verbatim: *"I just
#           took that from the wrong person. Undo it."*
# Story:    US-PAY-004 (§1 *"Cancel only while processing"*; TC-2 *"actions
#           restricted to View/Cancel"*)   Screens: S33 · S35 · 2·2
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money stored
#           to 4dp, never a float) · hard rule 4 (financial immutability — a
#           cancel writes a STATUS and a NEW ROW and does not widen the allow
#           list; `payments/0014` is untouched, which is `P3.8`) · hard rule 5
#           (only the ledger posting service writes journal lines — and there
#           is nothing here for it to write) · hard rule 6 (idempotency) ·
#           hard rule 7 (every money action writes `audit_log`) · hard-won law
#           14 (SAVEPOINT / PostgreSQL) · BR-PAY-002 (append-only once out of
#           `processing`) · BR-PAY-021 (posting vs clearing — a payment that
#           never cleared is CANCELLED, not reversed) · BR-PAY-884 (the sum of
#           every reversal against one payment may never exceed it) ·
#           BR-TEN-035 (the reversing row takes its own `PMT-` number)
# Tests:    06-backend/tests/test_cr137_p3_detail_cancel_receipt.py
#           (+ `P3.13` and `P3.14`, wave 2, assert this by status and at the
#           trigger)
# Impacts:  apps/payments/detail_api.py (the door) ·
#           apps/payments/payment_detail.action_availability (renders the
#           refusal BEFORE the click, BR-SHL-025) · apps/payments/reversal.py
#           (`_original`'s refusal at line 496 has pointed here since
#           2026-08-11 and now points at something that exists)
# ───────────────────────────────────────────────────────
"""A payment taken by mistake, undone — **without breaking immutability**.

╔══════════════════════════════════════════════════════════════════════════╗
║  AMENDED 2026-10-21 (`CR-186-BRC10`): CANCEL IS FROM `posted`.            ║
╚══════════════════════════════════════════════════════════════════════════╝
PO, verbatim: *"if payment is cancled then it will not be considered;
reconciled ayment cannot be cancelled; cleared payment cannot be cancled ; in
those cases refunds or credits will be issued"*, ruled as *"Statuses are
`posted` → `cleared`, plus `cancelled` (only from `posted`)"*.

Every new payment is `posted` at entry, **applied to its bills and journalled
at once**, so a posted payment HAS allocations and an entry — the "nothing to
unpost" argument below was true of `processing` and is not true of `posted`.
A posted cancel therefore writes, in ONE transaction:

    payments     the original `posted` → `cancelled` (hard rule 4's door,
                 `payments/0051`), and ONE reversing row (negative, its own
                 `PMT-` number, status `cancelled`, linked by
                 `reverses_payment_id`) — exactly as before;
    allocations  one NEGATIVE mirror per allocation the original wrote, with
                 its per-class rows negated byte for byte, so every bill it
                 met re-opens by exactly what it took (hard rule 4: new rows);
    journal      the ledger's own MIRROR of the original entry
                 (`ledger_seam.reverse_payment_entry`, event `cancelled`),
                 dated the cancel date forwarded out of a closed period — a
                 balanced pair (hard rule 5), the holding account and AR back
                 where they were;
    deposit      the batch is re-footed when it is still open, and the
                 cancelled member leaves its total (`reconciliation.
                 banked_members`); a batch already MATCHED to a bank line
                 refuses the cancel rather than changing a tied total;
    audit_log    `payment.cancelled` on both rows (hard rule 7).

A `cleared` payment — its batch reconciled with the bank — is REFUSED, and the
refusal names a refund or a credit, which is what the PO ruled corrects it. A
legacy `processing` row (written before 2026-10-21) keeps the original path
below, unchanged: it never posted, so there is nothing to mirror.

WHAT WAS HERE BEFORE THIS FILE
══════════════════════════════
Nothing, and the whole product knew it. `reversal._original` refuses an
uncleared payment in these words, and has since 2026-08-11:

    *"a payment that has not cleared is CANCELLED instead (US-PAY-004 TC-2),
    which is a status move on a processing row and not a reversal."*

`payments/0002`'s DELETE refusal says the same thing to anybody who reaches the
database directly: *"Cancel on a processing payment is a status move, not a
removal."* **Both sentences pointed at a state that did not exist and an
endpoint nobody had written.** US-PAY-004 §1 has asked for the control since the
story was signed — *"status-dependent row actions … Cancel only while
processing"* — and TC-2 names the action set a clerk should see.

╔══════════════════════════════════════════════════════════════════════════╗
║  CANCEL IS NOT REVERSE, AND THAT IS THE WHOLE OF THIS FILE.              ║
╚══════════════════════════════════════════════════════════════════════════╝
The blueprint states the split on p044 and it is worth quoting rather than
paraphrasing, because the two words are what a clerk confuses:

    *"**Cancel** is for money that never cleared — the mistake is minutes old,
    in an open batch, and nothing has reached the bank. **Reverse** is for money
    that arrived and went back: a bounce, a chargeback. Hard rule 4 means
    neither deletes anything; both write new rows."*

So a `cleared` payment is REFUSED here, by name, and the refusal names Reverse.
`reversal.py` refuses `processing` and names Cancel. **Each door refuses into the
other**, which is what makes the pair legible from either side; a lane that
widened one of them would break a sentence the other door already says.

WHAT IT WRITES — AND WHAT IT DELIBERATELY DOES NOT
══════════════════════════════════════════════════
p050's act table, verbatim: **Cancel · "A reversing row; the original stands" ·
"A reversing pair" · "The bill re-opens · the ladder may restart · the counter
total drops"**. Three of those four are built here. The fourth is not, and the
reason is measured rather than chosen:

    payments    the ORIGINAL moves `processing` → `cancelled`. That is the one
                transition `trg_payment_immutable` already permits on a
                processing row (`mutable` holds `status`), and the instant it
                lands the row falls into the trigger's frozen branch and can
                never move again. **Nothing else about the original changes.**
    payments    ONE new row, amount NEGATIVE, `reverses_payment_id` → the
                original, its own `PMT-` number, status `cancelled`.
    audit_log   `payment.cancelled` on BOTH rows (hard rule 7), carrying the
                reason and the clerk's note.
    allocations NOTHING — and this is not an omission. See below.
    journal     NOTHING — and this is not an omission either. See below.

⚠ **THERE IS NO BALANCED PAIR TO REVERSE, BECAUSE A PROCESSING PAYMENT NEVER
POSTED ONE.** `services.record_payment` returns before `_allocate_and_post` when
`cleared_at is None`, and says so on every such result:

    *"the payment carries no clearing date, so it is `processing`: the money has
    not arrived. It meets no bill and posts nothing — US-LED-001's contract row
    is 'Payment CLEARED → DR cash / CR AR'."*

So a processing payment has **no allocations** and a **NULL `journal_entry_id`**.
Composing a compensating entry here would be inventing a posting for money that
never reached the books — and hard rule 5 puts journal lines in the ledger
posting service's hands alone, which has nothing to mirror. The result carries
`NOTHING_TO_UNPOST` and `NO_BILL_REOPENED` saying so, rather than a screen
implying a bill moved.

**That is the drawing's own logic followed one step further, not a departure
from it.** p044 says in as many words that Cancel and Reverse *"are two
different acts to the ledger"*; the act table's ledger column describes the
general shape of undoing a payment, and for the only status Cancel is allowed in
the shape has no ledger half. ⚠ **AND THE DRAWING'S OWN EXAMPLE IS THE OTHER
CASE** — p043 cancels `PMT-2609-000418`, which p035 draws as **Cleared** with a
clearing date and a bill it paid off. Two frames of one blueprint drawing the
same fact differently is exactly what B14 rule 37 settles: *build the shape they
agree on*. They agree on Cancel refusing cleared money (p044) and the task board
agrees (`P3.13`: *"refused on `cleared` and the clerk is pointed at Reverse"*).
**FILED as `OQ-PAY-12603`** so the PO rules on the counter-cash case rather than
this file deciding it silently — a counter payment taken in cash is `cleared` the
same minute, so *"I just took that from the wrong person"* at a window reaches
**Reverse** today, not Cancel.

WHY A REVERSING ROW AT ALL, WHEN THE STATUS MOVE ALREADY SAYS IT
════════════════════════════════════════════════════════════════
Because **the day's cash total is netted by rows, not filtered by status.**
`selectors.payments_totals` sums every `type='payment'` row the filter matched
and looks at no status at all — that is deliberate and documented there (a
reversed payment nets against its own reversing row). A cancel that moved only
the status would leave a cancelled **$158.10** sitting in the day's takings, and
the drawer would be short by exactly that. **The reversing row is what makes
*"the counter total drops"* true**, and it is the same mechanism a bounce
already uses, so there is one rule rather than two.

IDEMPOTENCY IS THE STATUS ITSELF (hard rule 6)
══════════════════════════════════════════════
A double-click, a retried request and an impatient refresh all arrive at a row
that is now `cancelled`, and this returns the FIRST cancel with `created:
false` — a **200**, never a 409, on `account_payments`' argument: *"a 409 toast
for a button that worked is a wrong answer a clerk would act on."*

**No key table and no `idempotency_key` are needed, and that is stronger rather
than weaker.** A key guards one submit; the status guards every path there will
ever be, including a second clerk on a second machine. The lost race is closed
by `SELECT … FOR UPDATE` on the original before the status is read, and by
`trg_payment_immutable` underneath it: a second UPDATE finds `OLD.status =
'cancelled'` and the database refuses it.

⚠ **THE LOCK DOES NOTHING ON SQLITE, WHICH IS WHERE THE WHOLE SUITE RUNS**
(hard-won law 14 — `config/settings/test.py` hardcodes in-memory SQLite). The
concurrent case is proved on real PostgreSQL; a test on the default suite would
pass with the lock deleted.

THE SIXTH STATE LANDED WHILE THIS WAS BEING WRITTEN, AND THE GUARD STAYS
════════════════════════════════════════════════════════════════════════
`cancelled` is `P3.5`, and it is **on the branch**: `payments/0036` widens
`ck_payments_status` to six words and `models.PAYMENT_CANCELLED` exists. This
file was built against its absence and `_sixth_state_or_refuse` is what stood in
for it; **the guard is kept rather than deleted**, because what it refuses is a
database whose migrations have not been applied — a developer tier, a half-run
deploy — and there the CHECK's own error is a `CheckViolation` that reaches a
clerk as nothing at all, and on PostgreSQL poisons the whole transaction
besides (hard-won law 14).

⚠ **`payments/0036` CONFIRMS THIS FILE'S TWO ASSUMPTIONS RATHER THAN LEAVING
THEM ASSUMED, AND IT PROVED BOTH ON A POSTGRESQL CLONE:** *"The cancel MOVE is
permitted — `processing → cancelled` reaches the trigger's still-processing
branch, where `status` is on the `mutable` allow list"*, and *"The cancelled ROW
is frozen — the next statement against it takes `OLD.status = 'cancelled'`,
fails `<> 'processing'`, and is refused."* Neither half needed an edit to the
trigger, which is why `P3.8` holds: **hard rule 4's allow list does not move for
this.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import errors
from core import numbering
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: The sixth state. **ONE HOME, AND IT IS `models.py`** — `P3.5` landed it and
#: this reads it. The `getattr` fallback is kept for a tree whose migrations
#: have not been applied, where `_sixth_state_or_refuse` then refuses by name
#: rather than letting the CHECK raise something nobody can read.
CANCELLED = getattr(models, "PAYMENT_CANCELLED", "cancelled")

#: `audit_log.action` — hard rule 7. The catalogue holds the words; this is the
#: CODE (B14 rule 35, and `payment.recorded` / `payment.reversed` beside it).
AUDIT_CANCELLED = "payment.cancelled"
AUDIT_ENTITY = "payment"

#: Why a clerk cancelled, as the drawing's *Why* dropdown offers them (p043).
#: ⚠ **NOT `models.REVERSAL_REASONS`, AND NEVER FOLDED INTO IT.**
#: `ck_payments_reversal_reason` is written against the four S35 bounce reasons;
#: a cancel is a staff correction on money that never arrived and shares none of
#: them. Conflating the two vocabularies is the exact confusion this whole phase
#: exists to undo, and it would put `wrong_account` in a filter labelled *why the
#: bank returned it*.
CANCEL_REASON_WRONG_ACCOUNT = "wrong_account"
CANCEL_REASON_WRONG_AMOUNT = "wrong_amount"
CANCEL_REASON_DUPLICATE = "duplicate"
CANCEL_REASON_NOT_TAKEN = "not_taken"
CANCEL_REASONS = (
    CANCEL_REASON_WRONG_ACCOUNT,
    CANCEL_REASON_WRONG_AMOUNT,
    CANCEL_REASON_DUPLICATE,
    CANCEL_REASON_NOT_TAKEN,
)

# ── the refusal codes, one per reason a cancel cannot happen ────────────────
#: The one a clerk meets most, and the one that must name Reverse.
REFUSED_CLEARED = "cancel_refused_cleared_use_reverse"
REFUSED_FROZEN = "cancel_refused_status_is_final"
REFUSED_ALREADY = "cancel_refused_already_cancelled"
REFUSED_IS_A_REVERSAL = "cancel_refused_row_is_a_reversal"
REFUSED_SIXTH_STATE_ABSENT = "cancel_refused_state_not_migrated"
REFUSED_MONEY_IS_POSTED = "cancel_refused_money_already_posted"
#: `DEF-PAY-10016` — the money cleared AND has already been reversed (a return,
#: a chargeback, a clerk's Reverse). *"Reverse it instead"* would offer a second
#: reversal of money already taken back.
REFUSED_ALREADY_REVERSED = "cancel_refused_already_reversed"
#: CR-186-BRC10 — the deposit this payment banks in is tied to a bank line, so
#: cancelling would change a total the bank has already agreed.
REFUSED_BATCH_MATCHED = "cancel_refused_batch_matched"

#: The ledger event of a posted cancel's mirror — `payment|<uuid>|cancelled`.
EVENT_CANCELLED = "cancelled"

#: What a POSTED cancel did, on its result (`CR-186-BRC10`).
ENTRY_REVERSED = "payment_entry_reversed"
BILLS_REOPENED = "bills_reopened"

#: Outcome codes on the RESULT — statements about what cancelling did NOT have
#: to do, so a screen never implies a bill moved. Codes, not sentences.
NOTHING_TO_UNPOST = "no_entry_to_reverse_payment_never_posted"
NO_BILL_REOPENED = "no_bill_reopened_payment_met_none"


@dataclass(frozen=True)
class CancelledPayment:
    """What a cancel did, for the screen that is about to redraw the payment."""

    payment_id: str
    payment_no: str | None
    #: False on a REPLAY — the payment was already cancelled and this call
    #: wrote nothing (hard rule 6).
    created: bool
    status: str
    amount: str
    currency: str
    #: The reversing row, by the NUMBER a clerk reads (B14 rule 31).
    reversing_payment_no: str | None = None
    reversing_payment_id: str | None = None
    reason: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=())


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def refusal_for(payment: models.Payment) -> str | None:
    """Why this payment cannot be cancelled — as a CODE — or `None`.

    ⚠ **PURE, AND SHARED WITH THE SCREEN ON PURPOSE.** `payment_detail
    .action_availability` calls exactly this, so the reason a clerk is shown
    BEFORE the click (BR-SHL-025) and the reason the service gives AFTER it can
    never be two different answers. A screen that worked the rules out for
    itself would be a second copy of them, free to drift.

    The order is the order a clerk meets the cases in, and `REFUSED_CLEARED` is
    first among the frozen statuses because it is the one that has a next step.
    """
    if payment.reverses_payment_id is not None:
        return REFUSED_IS_A_REVERSAL
    status = payment.status
    if status == CANCELLED:
        return REFUSED_ALREADY
    if status == models.PAYMENT_CLEARED:
        if models.Payment.objects.filter(
            tenant_id=payment.tenant_id, reverses_payment_id=payment.pk
        ).exists():
            return REFUSED_ALREADY_REVERSED
        return REFUSED_CLEARED
    if status == models.PAYMENT_POSTED:
        # CR-186-BRC10 — the one status a new payment can be cancelled from.
        if payment.pk is not None and models.Payment.objects.filter(
            tenant_id=payment.tenant_id, reverses_payment_id=payment.pk
        ).exists():
            return REFUSED_ALREADY_REVERSED
        if _batch_is_tied(payment):
            return REFUSED_BATCH_MATCHED
        return None
    if status != models.PAYMENT_PROCESSING:
        return REFUSED_FROZEN
    # Processing, and therefore unposted by construction — but MEASURED rather
    # than assumed. A processing row that somehow carries an entry or an
    # allocation is a bug upstream, and cancelling it would leave a bill closed
    # against money nobody is going to receive. Refused, loudly.
    if payment.journal_entry_id is not None or payment.allocations.exists():
        return REFUSED_MONEY_IS_POSTED
    return None


def _batch_is_tied(payment: models.Payment) -> bool:
    """Is this payment's deposit batch already matched to the bank, or locked?"""
    if payment.deposit_batch_id is None:
        return False
    from apps.payments import bankrec_models as bankrec
    from apps.payments import reconciliation

    return (
        bankrec.DepositBatch.objects.filter(tenant_id=payment.tenant_id, pk=payment.deposit_batch_id)
        .exclude(status__in=reconciliation.OPEN_BATCH_STATUSES)
        .exists()
    )


def uncleared_payments_for_account(account_id: Any) -> tuple[dict[str, Any], ...]:
    """Every payment of this account still `processing` — money recorded and
    not yet arrived — each with `refusal_for`'s answer. Read-only.

    ⚠ **PUBLISHED FOR `customers.move_in_cancel` (`DEF-CUS-9789`), AND IT ADDS
    NO PATH.** A cancelled move-in calls off the cheque or card it took at the
    counter through `cancel_payment` below — the same act a clerk presses on
    the payment — because a refund must never pay out money that has not
    arrived (`deposit_release.deposit_still_held`) and a closed account must
    not keep money it will never use. Worked (M1): $175.00 by check 2041,
    recorded as $150.00 deposit + $25.00 connection, both processing → both
    called off, nothing refunded, nothing posted (a processing payment never
    posted, see the module docstring).

    Reversing rows are not listed: they are not payments a person took.
    `refusal` is the CODE `refusal_for` answers, so the caller can refuse the
    whole act BEFORE writing anything rather than meet the refusal halfway.
    """
    rows = (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            # ⚠ CR-186-BRC10: `processing` ONLY — the rows written before
            # 2026-10-21. A `posted` payment is money taken and applied, so a
            # cancelled move-in REFUNDS it (the PO's signed J6 statement of
            # 2026-10-06, "a refund REQUEST, not a payout") exactly as it did
            # a cleared one; widening this would silently call off money the
            # customer handed over. Decision log 2026-10-21, PAY-CORE item 10.
            status=models.PAYMENT_PROCESSING,
            reverses_payment__isnull=True,
        )
        .order_by("posted_at", "created_at", "id")
    )
    return tuple(
        {
            "payment_id": str(payment.pk),
            "payment_no": payment.payment_no,
            "amount": payment.amount,
            "currency": payment.currency,
            "purpose": payment.purpose,
            "confirmation": payment.confirmation,
            "refusal": refusal_for(payment),
        }
        for payment in rows
    )


def _sixth_state_or_refuse() -> None:
    """`P3.5`'s state, checked before anything is written.

    ⚠ **WITHOUT THIS, THE FAILURE IS A RAW DATABASE ERROR.** `ck_payments_status`
    was written against five values until `payments/0036`, so an UPDATE setting
    `cancelled` comes back as a `CheckViolation` naming a constraint — which on
    PostgreSQL also poisons the whole transaction (hard-won law 14) and reaches a
    clerk as nothing at all. 0036 is on the branch, so this passes in any
    migrated tree; it is kept for one that is not.
    """
    if CANCELLED in models.PAYMENT_STATUSES:
        return
    raise PaymentRuleError(
        "the payment state `cancelled` does not exist in this database yet, so nothing was "
        "written. `ck_payments_status` is written against five states and the sixth is "
        "CR-137-BRC07 task P3.5, `payments/0036` — a migration that ALTERS the CHECK. It is "
        "on the branch, so this tree has not applied its migrations. Run them; without "
        "0036 a cancel is refused by the database with an error no clerk could read.",
        br_ref="BR-PAY-002",
    )


def _reason_or_refuse(reason: Any) -> str:
    """The drawing's *Why* field is REQUIRED (p044 ②), and it is a CODE.

    ⚠ **THE REASON IS NOT KEPT ANYWHERE A RETENTION SWEEP CANNOT REACH.** It
    lands in `audit_log`, which is pruned like every other row (PO ruling
    2026-09-23, `OQ-1340` CLOSED: *"when audit log is delete - it is deleted
    thats okay"*). The drawing's own help under the field says the same thing —
    *"This is the only record of the reason."* **So no screen, document or
    docstring may call this a permanent record**, and none does. Whether the
    reason deserves a column of its own is `OQ-PAY-12604`, filed rather than
    decided here: a column on `payments` is `P3-DB`'s to add.
    """
    text = "" if reason is None else str(reason).strip()
    if not text:
        raise PaymentRuleError(
            "a cancel needs a reason. The Why field is required because the cancelled row and "
            "its reversing row are the only trace this money was ever taken, and a cancel with "
            "no reason is a payment that vanished from a clerk's point of view.",
            br_ref="BR-PAY-002",
        )
    if text not in CANCEL_REASONS:
        raise PaymentRuleError(
            f"{text!r} is not one of this product's cancel reasons "
            f"({', '.join(CANCEL_REASONS)}). A reason nothing can filter on is a reason nobody "
            "can report on; the bounce reasons are a different vocabulary and are not accepted "
            "here (BR-PAY-011 governs those).",
            br_ref="BR-PAY-002",
        )
    return text


def _replay(original: models.Payment) -> CancelledPayment:
    """The answer to a second click — the FIRST cancel, `created: false`.

    The reversing row is found by the link rather than remembered, so a replay
    answers with the row that actually exists.
    """
    reversing = (
        models.Payment.objects.filter(tenant_id=original.tenant_id, reverses_payment_id=original.pk)
        .order_by("created_at", "id")
        .first()
    )
    return CancelledPayment(
        payment_id=str(original.pk),
        payment_no=original.payment_no,
        created=False,
        status=original.status,
        amount=str(original.amount),
        currency=original.currency,
        reversing_payment_no=None if reversing is None else reversing.payment_no,
        reversing_payment_id=None if reversing is None else str(reversing.pk),
        problems=(
            # CR-186-BRC10 — a POSTED cancel mirrored an entry; say so on the replay too.
            ({"code": ENTRY_REVERSED, "br_ref": "BR-PAY-021",
              "journal_entry_id": str(reversing.journal_entry_id),
              "detail": "the payment's journal entry was mirrored when it was cancelled."},)
            if reversing is not None and reversing.journal_entry_id is not None
            else (_unposted_problem(original), _no_bill_problem(original))
        ),
    )


def _unposted_problem(original: models.Payment) -> dict[str, Any]:
    return {
        "code": NOTHING_TO_UNPOST,
        "br_ref": "BR-PAY-021",
        "detail": "this payment was `processing`, so it had reached no journal entry and "
        "there was nothing for the ledger to reverse. US-LED-001's contract row is "
        "'Payment CLEARED → DR cash / CR AR'; money that never arrived never posted.",
    }


def _no_bill_problem(original: models.Payment) -> dict[str, Any]:
    return {
        "code": NO_BILL_REOPENED,
        "br_ref": "BR-PAY-021",
        "detail": "this payment met no bill — a processing payment is not allocated, because "
        "taking a bill out of arrears on the strength of money that has not arrived is the "
        "thing BR-PAY-021 exists to prevent. Nothing re-opened, and nothing had closed.",
    }


def cancel_payment(
    *,
    actor: Any,
    payment_id: Any,
    reason: Any,
    cancelled_on: datetime,
    note: str | None = None,
) -> CancelledPayment:
    """Undo a payment taken by mistake — `POST /payments/{id}/cancel`.

    `cancelled_on` is the caller's moment and is **never read from a clock**
    (BR-TEN-043, gate G6). It dates the reversing row's own `PMT-` number and
    both of its BR-PAY-021 dates, for `_write_reversal`'s reason: the correction
    entered the system and the money "left" on the same day, because that is
    what undoing a mistyped receipt IS.

    ONE transaction. The status move, the reversing row and both audit rows
    commit together or not at all — a cancelled original with no reversing row
    would overstate the drawer by the amount of the payment, which is the exact
    fault the reversing row exists to prevent.
    """
    tenant_id = _tenant_id()
    with transaction.atomic():
        # ⚠ **THE LOCK COMES BEFORE THE READ, OR IT PROTECTS NOTHING**
        # (`reversal._lock_original` makes the same point at length). Two clerks
        # clicking Cancel on one payment both read `processing` otherwise, and
        # both write a reversing row — two negatives against one receipt.
        # On SQLite this is a no-op; the race is proved on PostgreSQL.
        original = (
            models.Payment.objects.select_for_update()
            .filter(tenant_id=tenant_id, pk=payment_id)
            .first()
        )
        if original is None:
            raise PaymentRuleError(
                f"payment {payment_id!r} is not one of this tenant's payments, so there is "
                "nothing to cancel (CLAUDE.md rule 1). Nothing is written.",
                br_ref="BR-PAY-002",
            )
        refusal = refusal_for(original)
        if refusal == REFUSED_ALREADY:
            # Hard rule 6 — a second click is the same act, not a new one.
            return _replay(original)
        if refusal is not None:
            raise _refusal_error(original, refusal)
        _sixth_state_or_refuse()
        chosen = _reason_or_refuse(reason)
        memo = None if note is None or not str(note).strip() else str(note).strip()
        if original.status == models.PAYMENT_POSTED:
            return _cancel_posted(
                actor=actor, original=original, chosen=chosen, memo=memo, cancelled_on=cancelled_on
            )

        before = {"status": original.status}
        original.status = CANCELLED
        # ⚠ **`update_fields` NAMES EXACTLY THE ALLOW LIST, AND THAT IS `P3.8`.**
        # `trg_payment_immutable`'s processing branch permits `status`,
        # `cleared_at` and `updated_at` plus the three correctable columns, and
        # nothing here asks for more. `payments/0014` is the only place that
        # list moves and this change does not touch it: a cancel writes a STATUS
        # and a NEW ROW, and does not widen immutability.
        original.save(update_fields=["status", "updated_at"])

        reversing = models.Payment.objects.create(
            tenant_id=original.tenant_id,
            account_id=original.account_id,
            # BR-TEN-035 — its own number, from the tenant's PMT- series, under
            # the day the cancel happened. A reversing row is a payment record
            # in its own right and appears on S33 as one.
            payment_no=numbering.next_number(numbering.PAYMENT, cancelled_on.date()),
            type=models.PAYMENT_TYPE_PAYMENT,
            method=original.method,
            # The sign lives on the AMOUNT, exactly as a bounce's does, so B2's
            # O-4 residue is never consulted and `payments_totals` nets without
            # knowing anything about cancelling.
            amount=-original.amount,
            currency=original.currency,
            status=CANCELLED,
            purpose=original.purpose,
            confirmation=original.confirmation,
            # The clerk's own words, on the row rather than only on a pruned
            # audit entry. The REASON CODE stays in the trail — see
            # `_reason_or_refuse`.
            memo=memo,
            # ⚠ **`reversal_reason` STAYS NULL.** `ck_payments_reversal_reason`
            # is written against the four BOUNCE reasons and a cancel is none of
            # them; NULL is lawful there and honest here.
            reversal_reason=None,
            is_partial_reversal=False,
            posted_at=cancelled_on,
            cleared_at=cancelled_on,
            reverses_payment=original,
            # A clerk did this, at a keyboard. Never derived.
            origin=models.PAYMENT_ORIGIN_ENTRY,
            origin_is_derived=False,
        )

        trail = {
            "reason": chosen,
            "note": memo,
            "amount": str(original.amount),
            "currency": original.currency,
            "reversing_payment_no": reversing.payment_no,
            "job": None if actor is not None else "payments.cancel",
        }
        # Hard rule 7, on BOTH rows: the original is what a clerk opens and the
        # reversing row is what the day's total nets against, and each has to be
        # explicable on its own.
        core_audit.money_action(
            actor,
            AUDIT_CANCELLED,
            AUDIT_ENTITY,
            str(original.pk),
            before=before,
            after={"status": CANCELLED, **trail},
        )
        core_audit.money_action(
            actor,
            AUDIT_CANCELLED,
            AUDIT_ENTITY,
            str(reversing.pk),
            after={"cancels_payment_no": original.payment_no, **trail},
        )

    return CancelledPayment(
        payment_id=str(original.pk),
        payment_no=original.payment_no,
        created=True,
        status=CANCELLED,
        amount=str(original.amount),
        currency=original.currency,
        reversing_payment_no=reversing.payment_no,
        reversing_payment_id=str(reversing.pk),
        reason=chosen,
        problems=(_unposted_problem(original), _no_bill_problem(original)),
    )


def _cancel_posted(
    *, actor: Any, original: models.Payment, chosen: str, memo: str | None, cancelled_on: datetime
) -> CancelledPayment:
    """`CR-186-BRC10` — cancel a POSTED payment: undo what posting did, in new rows.

    Inside `cancel_payment`'s transaction, after the row lock and the refusal
    checks. See the module docstring's amendment for the four things written.
    The order is load-bearing: the ledger mirror is written FIRST, so the
    reversing payment row can carry its `journal_entry_id` at INSERT — the
    column is a write-once stamp and an INSERT is free.
    """
    from apps.payments import bankrec_models as bankrec
    from apps.payments import ledger_seam, reconciliation, reversal

    entry_on, forwarded = ledger_seam.entry_date_for_posting(cancelled_on.date())
    mirror = None
    if original.journal_entry_id is not None:
        mirror = ledger_seam.reverse_payment_entry(
            payment=original,
            entry_date=entry_on,
            posted_at=cancelled_on,
            event=EVENT_CANCELLED,
            memo=f"Cancel of payment {original.payment_no or original.pk}",
            actor=actor,
        )

    before = {"status": original.status}
    original.status = CANCELLED
    # `payments/0051`'s posted branch: `status` may move posted -> cancelled.
    original.save(update_fields=["status", "updated_at"])

    reversing = models.Payment.objects.create(
        tenant_id=original.tenant_id,
        account_id=original.account_id,
        payment_no=numbering.next_number(numbering.PAYMENT, cancelled_on.date()),
        type=original.type,
        method=original.method,
        amount=-original.amount,
        currency=original.currency,
        status=CANCELLED,
        purpose=original.purpose,
        confirmation=original.confirmation,
        memo=memo,
        reversal_reason=None,
        is_partial_reversal=False,
        posted_at=cancelled_on,
        # Never reconciled with a bank — `cleared` means that since 2026-10-21.
        cleared_at=None,
        reverses_payment=original,
        journal_entry_id=None if mirror is None else mirror.entry_id,
        origin=models.PAYMENT_ORIGIN_ENTRY,
        origin_is_derived=False,
    )

    # ── the bills re-open: one negative mirror per allocation, classes too ──
    reopened: list[dict[str, Any]] = []
    for row in original.allocations.all().order_by("created_at", "id"):
        mirror_row = models.Allocation.objects.create(
            tenant_id=original.tenant_id,
            payment=reversing,
            invoice_id=row.invoice_id,
            amount=-row.amount,
        )
        models.AllocationClass.objects.bulk_create(
            [
                models.AllocationClass(
                    tenant_id=original.tenant_id,
                    allocation=mirror_row,
                    line_class=child.line_class,
                    amount=-child.amount,
                )
                for child in row.classes.all().order_by("line_class")
                if child.amount != ZERO
            ]
        )
        reopened.append({"invoice_id": str(row.invoice_id), "amount": str(row.amount)})

    # ── a deposit leaves the register with its money (BR-CUS-670) ──
    deposit_problems: tuple[dict[str, Any], ...] = ()
    if original.purpose == models.PURPOSE_DEPOSIT:
        _, deposit_problems = reversal._release_deposit(
            original.account_id, amount=original.amount, actor=actor
        )

    # ── the open batch drops by the cancelled amount ──
    if original.deposit_batch_id is not None:
        batch = (
            bankrec.DepositBatch.objects.select_for_update()
            .filter(tenant_id=original.tenant_id, pk=original.deposit_batch_id)
            .first()
        )
        if batch is not None:
            reconciliation.refresh_batch_total(batch)

    trail = {
        "reason": chosen,
        "note": memo,
        "amount": str(original.amount),
        "currency": original.currency,
        "reversing_payment_no": reversing.payment_no,
        "reversal_entry_id": None if mirror is None else str(mirror.entry_id),
        "entry_date": entry_on.isoformat(),
        "bills_reopened": reopened,
        "job": None if actor is not None else "payments.cancel",
    }
    core_audit.money_action(
        actor,
        AUDIT_CANCELLED,
        AUDIT_ENTITY,
        str(original.pk),
        before=before,
        after={"status": CANCELLED, **trail},
    )
    core_audit.money_action(
        actor,
        AUDIT_CANCELLED,
        AUDIT_ENTITY,
        str(reversing.pk),
        after={"cancels_payment_no": original.payment_no, **trail},
    )
    problems: tuple[dict[str, Any], ...] = (
        {
            "code": ENTRY_REVERSED,
            "br_ref": "BR-PAY-021",
            "journal_entry_id": None if mirror is None else str(mirror.entry_id),
            "detail": "the payment's journal entry was mirrored (hard rule 5); the holding "
            "account and receivables are back where they were.",
        },
        {
            "code": BILLS_REOPENED,
            "br_ref": "BR-PAY-021",
            "bills": reopened,
            "detail": "every bill this payment met re-opened by exactly what it took.",
        },
    )
    return CancelledPayment(
        payment_id=str(original.pk),
        payment_no=original.payment_no,
        created=True,
        status=CANCELLED,
        amount=str(original.amount),
        currency=original.currency,
        reversing_payment_no=reversing.payment_no,
        reversing_payment_id=str(reversing.pk),
        reason=chosen,
        problems=problems + (() if forwarded is None else (forwarded,)) + deposit_problems,
    )


def _refusal_error(payment: models.Payment, code: str) -> PaymentRuleError:
    """One refusal per code, and the `cleared` one NAMES REVERSE.

    ⚠ **THE SENTENCE MATTERS AS MUCH AS THE REFUSAL** (`P3.13`: *"the clerk is
    pointed at Reverse"*). A bare *"cannot cancel a cleared payment"* leaves the
    clerk holding a returned cheque with nowhere to go — which is the support
    call this whole phase exists to end.
    """
    name = payment.payment_no or payment.pk
    if code == REFUSED_CLEARED:
        # CR-186-BRC10 — PO 2026-10-21: "cleared payment cannot be cancled ; in
        # those cases refunds or credits will be issued".
        return PaymentRuleError(
            f"Payment {name} has cleared at the bank. Issue a refund or a credit instead.",
            br_ref="BR-PAY-021",
        )
    if code == REFUSED_BATCH_MATCHED:
        return PaymentRuleError(
            f"Payment {name} is in a matched deposit. Unmatch the deposit first.",
            br_ref="BR-PAY-004",
        )
    if code == REFUSED_IS_A_REVERSAL:
        return PaymentRuleError(
            f"payment {name} IS a reversing row — it is the record that another payment came "
            "back or was cancelled. Cancelling it would re-apply money nobody received.",
            br_ref="BR-PAY-002",
        )
    if code == REFUSED_MONEY_IS_POSTED:
        return PaymentRuleError(
            f"payment {name} is `processing` and yet already names a journal entry or a bill it "
            "met, which should not be possible (a processing payment posts nothing and is "
            "allocated to nothing, BR-PAY-021). Cancelling it would leave a bill closed against "
            "money nobody will receive. Nothing is written — this is reported, not worked around.",
            br_ref="BR-PAY-021",
        )
    return PaymentRuleError(
        f"payment {name} is {payment.status} and is append-only (BR-PAY-002, hard rule 4). Only "
        "a payment that is still `posted` can be cancelled; a payment past that point stands "
        "as it was recorded and is corrected with new rows.",
        br_ref="BR-PAY-002",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-137-BRC07 §3 P3.2 + P3.8 · 05-prototype/06 Payments Page Blueprint.pdf
#         2·3d p043–p044 + the act table p050 (on this branch since
#         `da07c7f8d` — see E1) ·
#         04-docs/05-modules/08-payments/06-epics/EP-PAY-01 US-PAY-004 §1 + TC-2 ·
#         02-business-rules.md BR-PAY-002 · BR-PAY-021 · BR-PAY-884 ·
#         06-backend/apps/payments/reversal.py `_original` ·
#         06-backend/apps/payments/migrations/0002 + 0014 (the trigger, both
#         branches) · CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · hard-won law 14
# generated: 2026-09-23 by the CR-137 P3-BACK lane
# checklist: A✔ B=deferred(P3.11 owns the Cancel modal) C✔ D✔ E=deferred(P3.11)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 ⚠ **THIS READ *"the blueprint PDF is NOT on this branch"* WHILE THIS LANE
#      WAS BUILDING, AND IT IS NO LONGER TRUE.** It was true at the pinned tip and
#      the drawing was read from `origin/claude/confirm-understanding-3ktufc`;
#      `da07c7f8d` put it on THIS branch at `05-prototype/06 Payments Page
#      Blueprint.pdf`, 2,905,141 bytes, sha256 `0cc31baf…`, and the copy read here
#      is byte-identical to it. `DEF-PAY-6230` is CLOSED. Read it from the branch.
#   E2 **NO LEDGER POSTING AND NO ALLOCATION REVERSAL**, against p050's act
#      table, because a `processing` payment has neither: `record_payment`
#      returns before `_allocate_and_post` when `cleared_at is None`. Reported
#      on every result as `no_entry_to_reverse_payment_never_posted` +
#      `no_bill_reopened_payment_met_none`, and raised as `OQ-PAY-12603` rather
#      than decided silently.
#   E3 the cancel REASON has no column and lives in `audit_log`, which is
#      pruned (PO 2026-09-23). Nothing here calls that a permanent record.
#      `OQ-PAY-12604` asks whether it deserves one; the column would be P3-DB's.
#   E4 `P3.5` LANDED (`payments/0036`) and `models.PAYMENT_CANCELLED` is read.
#      The `getattr` fallback and `_sixth_state_or_refuse` are KEPT for an
#      unmigrated tree, where the CHECK's own error is a CheckViolation that
#      reaches a clerk as silence. 0036 proves both halves of this file's
#      trigger assumption on a PostgreSQL clone — see the docstring.
#   E5 NO `idempotency_key` is accepted and none is needed — the STATUS is the
#      guard and it is stronger (see the module docstring). This is a departure
#      from `reversal_api`, which requires one, and the difference is real: a
#      reversal may lawfully happen twice in parts, a cancel may not happen
#      twice at all.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
