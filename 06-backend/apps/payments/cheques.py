# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-30 (task 56) — "Give a cheque a state of its own",
#           RULED 2026-09-01. The CR's own words: *"There is no cheque in this
#           system. A cheque is an ordinary payment whose tender is `check` and
#           whose number is typed into a free-text reference field."*
# Story:    US-PAY-001 (the payment a cheque is) · US-PAY-009 (the reversal it
#           is NOT)   Screens: S22 · S33 · S35 · S37 · S21
# Rules:    BR-PAY-880 (NEW — a cheque carries its number, its date and its
#           drawer bank as structured fields) · BR-PAY-881 (a cheque not yet
#           banked may be VOIDED at the counter without a bank reversal) ·
#           BR-PAY-883 (a post-dated cheque is held out of the cut until its
#           date, and named on the day it becomes bankable) · BR-PAY-002 /
#           CLAUDE.md hard rule 4 (append-only once out of `processing` — and
#           see WHY A VOID IS A STATUS MOVE) · BR-PAY-021 (both dates) ·
#           BR-TEN-043 / gate G6 (the caller names the day) · rule 7 (audit)
# Ruling:   PO 2026-09-01, CR-059 §8 CS-30. Lateness reads the ACTUAL arrival
#           date (PO 2026-08-11), so a re-presented cheque is judged on the day
#           it finally cleared — already ruled and NOT re-asked (law 13).
# Tests:    06-backend/tests/test_cr059_cs30_cheques.py
# Impacts:  apps/payments/reconciliation.cut_deposit_batches (reads
#           `bankable_from`) · apps/payments/models.Payment (payments/0017's
#           three columns) · apps/payments/services.record_payment (the writer
#           that stamps them)
# ───────────────────────────────────────────────────────
"""A cheque, as a thing rather than as free text.

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this decides whether an instrument may
be banked and voids one at the counter. AI-authored 2026-09-03 under the PO
ruling of 2026-08-09. **No glob in `10-scripts/gates/human_owned.txt` matches
this file**; editing that list is a process event and the PO's call, not a
lane's (`allocation_release.py` records the identical finding). REPORTED.

════════════════════════════════════════════════════════════════════════════
WHAT CS-30 ASKED FOR AND WHAT THIS FILE IS
════════════════════════════════════════════════════════════════════════════
CS-30 lists four new rules. **Three are built here and the fourth is stated as
unbuilt rather than half-built**, which is the whole point of the CR being
re-opened:

    ✔ structured fields — number, date, drawer bank, unique per utility
    ✔ void before banking, without a bank reversal
    ✔ a post-dated cheque held out of the cut until its date, and named on
      the day it becomes bankable
    ✘ RE-PRESENTMENT — *"a returned cheque presented again is the SAME cheque,
      carrying its history: presented → returned → re-presented → cleared."*
      **NOT BUILT.** It needs a second self-link on `payments` and a state walk
      through the reversal path, and this lane's brief is the first three. It is
      named here, in `problems[]` on every result, and in the lane's report —
      not left as a silence somebody discovers on a screen.

════════════════════════════════════════════════════════════════════════════
THE NUMBER IS `payments.confirmation` AND THAT IS THE CONSIDERED HALF
════════════════════════════════════════════════════════════════════════════
CS-30 asks for the number as a structured field. It already is one:
`payments.confirmation` is *"the cheque or confirmation number"* in hard rule
4's own words, and it is **one of the exactly three columns the PO opened to
correction on 2026-09-02** (`payments/0014`) — so a mistyped cheque number is
fixable today through `POST /payments/{id}/correct-reference`.

**A fourth column holding the number would hold a number nobody could ever
correct**, which is precisely the defect CS-34 was written to remove, rebuilt
one column along. So `payments/0017` adds the two facts that genuinely had
nowhere to live — `cheque_date` and `drawer_bank` — plus `bankable_from`, and
the number stays where it is and stays correctable.

════════════════════════════════════════════════════════════════════════════
⚠ A VOID IS A STATUS MOVE, NOT A COLUMN. HARD RULE 4 DECIDES THIS, NOT TASTE
════════════════════════════════════════════════════════════════════════════
The obvious build is a `voided_at` column and a `void_reason` beside it. **It is
not lawful and the trigger says so.** `payments/0002` lets a `processing`
payment change `status`, `cleared_at` and `updated_at` and **nothing else** —
whole-row compared, *"so a column added later is frozen the day it is created"*
— and `payments/0014` opened three more columns for corrections **in any
status** by PO ruling, none of which is a void. Widening that allow list again
is a NEW ruling and not this one; CLAUDE.md says so in terms.

**And it does not need to be widened, because the status already carries the
fact.** A cheque *"not yet banked"* is a `processing` payment: the money has not
arrived, nothing has posted to the books, and there is no journal entry to
reverse. Moving it to `failed` is a transition the trigger already permits, it
needs no schema change, and the REASON lives on the `audit_log` row hard rule 7
writes for every money action.

⚠ **WHAT THAT COSTS, SAID RATHER THAN DISCOVERED (`OQ-1340`'s shape):** the void
reason lives ONLY in `audit_log`, which is pruned on a retention schedule. That
is the same cost the PO accepted for a corrected cheque number on 2026-09-02 and
the same open question — so **this file does not describe the void reason as a
permanent record**, and nor may any screen or document, until `OQ-1340` is
answered.

════════════════════════════════════════════════════════════════════════════
⚠ THE NUMBER'S UNIQUENESS IS A SERVICE CHECK AND NOT A DATABASE INDEX
════════════════════════════════════════════════════════════════════════════
CS-30's first rule asks for a cheque number *"unique per utility"*. **A unique
index cannot express that soundly here, and the proof is in this same CR.**

A partial index would have to exclude a cheque whose earlier row has been
REVERSED — and *"has this row been reversed"* lives in ANOTHER row
(`payments.reverses_payment_id` on the reversing record), which no partial-index
predicate can reach. Worked, on this CR's own CS-32: cheque **#8842** is
recorded against the wrong Patel, then MOVED — the original stays `cleared`, the
destination row carries the same number, and a `(tenant, confirmation)` index
would refuse a correction this product is being built to make. The same is true
of re-presentment the day it lands.

So the duplicate check is `refuse_a_duplicate_cheque` below, where it can say
*"cheque 8842 from First National is already recorded as PMT-2608-000412"* and
can exempt a reversed one. **What that costs, stated: two identical cheques
submitted concurrently could both land**, because a service check is not a
constraint. The check catches the human typo it exists for, which is what CS-30
describes; a race between two clerks typing the same cheque number in the same
second is not a case this product has, and closing it would refuse the two
lawful flows above. Recorded in `12-governance/02-decision-log.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: EP-PAY-01 §5's `<entity>.<verb>` shape. Its own code rather than
#: `payment.reversed`, because a void is NOT a reversal and a screen filtering
#: the trail for bank events must not find counter events among them.
AUDIT_VOIDED = "payment.cheque_voided"

#: What the cheque surface does NOT do, on every result (the discipline
#: `services.RECORD_UNAVAILABLE` and `reversal.REVERSE_UNAVAILABLE` keep).
CHEQUE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "re_presentment_not_built",
        "br_ref": "BR-PAY-882",
        "detail": "the PO ruled on 2026-09-01 that a returned cheque presented again is the "
        "SAME cheque, carrying its history — presented, returned, re-presented, cleared. That "
        "walk is NOT built: it needs a second self-link on `payments` and a path through the "
        "reversal service, and this lane built the structured fields, the bankable-from hold "
        "and the counter void. A re-presented cheque is today recorded as a new payment and "
        "the link to its bounce is lost.",
    },
    {
        "code": "void_reason_lives_only_in_the_audit_trail",
        "br_ref": "BR-PAY-881",
        "detail": "a void is a status move plus an audit row, because hard rule 4's trigger "
        "lets a processing payment change only its status and its clearing date. The reason "
        "is therefore in `audit_log`, which is pruned on a retention schedule; whether such a "
        "row is exempt from pruning is OQ-1340 and is OPEN, so this path is not a permanent "
        "record of why a cheque was torn up.",
    },
)


@dataclass(frozen=True)
class VoidedCheque:
    """One cheque voided at the counter. No bank, no ledger, no reversal."""

    payment_id: str
    payment_no: str | None
    account_id: str
    amount: Decimal
    currency: str
    status: str
    reason: str
    problems: tuple[dict[str, Any], ...] = field(default=CHEQUE_UNAVAILABLE)


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def is_a_structured_cheque(payment: models.Payment) -> bool:
    """`cheque_date` being set is what makes a row a structured cheque.

    Not the tender code: `payments.method` is a tenant-extensible LOOKUP
    (BR-TEN-036 / BR-PAY-026) whose codes a utility may rename, so keying off
    the string `check` would be a rule that breaks when somebody renames a
    lookup row. The DATE is the fact CS-30 adds and it is the fact this module
    reads.
    """
    return payment.cheque_date is not None


def validate_cheque_fields(
    *,
    cheque_date: Any,
    drawer_bank: Any,
    bankable_from: Any,
    confirmation: Any,
) -> None:
    """CS-30's first rule, checked BEFORE anything is written.

    **The three travel together or not at all.** A cheque date with no drawer
    bank would defeat the duplicate check below — two banks legitimately issue
    the same cheque number, so the pair is what identifies an instrument — and a
    cheque with no number cannot be matched to a bank line at all, which is
    `CS-34`'s own finding about what an unmatched reference costs.

    `bankable_from` earlier than the cheque's own date is REFUSED: it would say
    the utility may bank an instrument before the day it exists.
    """
    if cheque_date is None:
        if drawer_bank or bankable_from is not None:
            raise PaymentRuleError(
                "a drawer bank or a bankable-from date was given with no cheque date. A "
                "cheque's three structured facts travel together (CR-059 CS-30) — half of "
                "them describes an instrument nobody can identify.",
                br_ref="BR-PAY-880",
            )
        return
    if not (drawer_bank or "").strip():
        raise PaymentRuleError(
            "a cheque carries its number, its DATE and its DRAWER BANK (CR-059 CS-30). The "
            "bank is not optional: two banks legitimately issue the same cheque number, so "
            "without it a duplicate cannot be told from an ordinary second cheque.",
            br_ref="BR-PAY-880",
        )
    if not (confirmation or "").strip():
        raise PaymentRuleError(
            "a cheque needs its number. It is what a bank line is matched on, so a cheque "
            "without one is an unmatched line and a reconciliation nobody can finish.",
            br_ref="BR-PAY-880",
        )
    if bankable_from is not None and bankable_from < cheque_date:
        raise PaymentRuleError(
            f"this cheque is dated {cheque_date.isoformat()} and was marked bankable from "
            f"{bankable_from.isoformat()}. A cheque cannot be banked before the day it is "
            "written; leave the hold empty for a cheque that may be banked today.",
            br_ref="BR-PAY-883",
        )


def refuse_a_duplicate_cheque(
    tenant_id: Any, *, confirmation: str, drawer_bank: str, exclude_id: Any = None
) -> None:
    """CS-30's *"unique per utility"*, as a SERVICE check. See the module docstring.

    Identity is **(drawer bank, number)** and not the number alone, because two
    banks issue cheque #1001 every week and a utility that banks both is not
    making a mistake.

    **A cheque whose row has been REVERSED is exempt**, and that exemption is
    why this is not a database index: the fact lives in another row. It is what
    lets CS-32 move cheque #8842 to the right Patel and re-record it there, and
    it is what will let a re-presentment land when that is built.
    """
    if not (confirmation or "").strip() or not (drawer_bank or "").strip():
        return
    rows = models.Payment.objects.filter(
        tenant_id=tenant_id,
        confirmation=confirmation.strip(),
        drawer_bank=drawer_bank.strip(),
        cheque_date__isnull=False,
    ).exclude(status=models.PAYMENT_FAILED)
    if exclude_id is not None:
        rows = rows.exclude(pk=exclude_id)
    for row in rows:
        if models.Payment.objects.filter(tenant_id=tenant_id, reverses_payment_id=row.pk).exists():
            # Reversed: the money came back or the record was corrected, so the
            # instrument's number is free again. This is the clause a partial
            # unique index could never express — the fact is in ANOTHER row.
            continue
        raise PaymentRuleError(
            f"cheque {confirmation} from {drawer_bank} is already recorded as "
            f"{row.payment_no or row.pk}, dated {row.cheque_date.isoformat()} for "
            f"{row.amount}. Two cheques with one number from one bank is a typo far more often "
            "than it is a fact; if this really is a second instrument, correct the number on "
            "one of them first.",
            br_ref="BR-PAY-880",
        )


def bankable_on(day: date) -> Any:
    """Every cheque this tenant may bank on `day` and has not banked yet.

    CS-30's fourth rule has two halves and this is the second: a post-dated
    cheque is held out of the cut **and named on the day it becomes bankable**.
    Without this read the hold is a trap — the money sits in the drawer and
    nothing ever tells anybody it is ready.

    S37's list. `day` is the caller's business day and no clock is read
    (BR-TEN-043, gate G6).
    """
    return (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            # CR-186-BRC10 — a new payment is `posted`; `cleared` is a legacy row.
            status__in=(models.PAYMENT_POSTED, models.PAYMENT_CLEARED),
            deposit_batch_id__isnull=True,
            bankable_from__isnull=False,
            bankable_from__lte=day,
        )
        # CR-059 CS-32 — `selectors.payment_row` reads the move marks off
        # `moved_from_payment` and off `moved_to`; joined here so a cheque list
        # is three queries and not three per row (see `payment_queryset`).
        .select_related("account", "method", "moved_from_payment", "moved_from_payment__account")
        .prefetch_related("moved_to", "moved_to__account")
        .order_by("bankable_from", "posted_at", "id")
    )


def held_after(day: date) -> Any:
    """The complement — post-dated cheques NOT yet bankable on `day` (S33/S37)."""
    return (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            deposit_batch_id__isnull=True,
            bankable_from__isnull=False,
            bankable_from__gt=day,
        )
        # CR-059 CS-32 — `selectors.payment_row` reads the move marks off
        # `moved_from_payment` and off `moved_to`; joined here so a cheque list
        # is three queries and not three per row (see `payment_queryset`).
        .select_related("account", "method", "moved_from_payment", "moved_from_payment__account")
        .prefetch_related("moved_to", "moved_to__account")
        .order_by("bankable_from", "posted_at", "id")
    )


def uncleared_cheques() -> Any:
    """*"the thing a bookkeeper actually asks for"* — cheques awaiting clearance.

    CS-30: *"the pieces exist (a `processing` filter, an in-transit tile) but
    neither is a list of cheques awaiting clearance."* This is that list: rows
    that are structured cheques and are still `processing`, so the money has not
    arrived.
    """
    return (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            # CR-186-BRC10 (PO 2026-10-21): a cheque is `posted` until its
            # deposit batch is reconciled with the bank, then `cleared`.
            # `processing` is a cheque taken before the change.
            status__in=(models.PAYMENT_POSTED, models.PAYMENT_PROCESSING),
            cheque_date__isnull=False,
        )
        # CR-059 CS-32 — `selectors.payment_row` reads the move marks off
        # `moved_from_payment` and off `moved_to`; joined here so a cheque list
        # is three queries and not three per row (see `payment_queryset`).
        .select_related("account", "method", "moved_from_payment", "moved_from_payment__account")
        .prefetch_related("moved_to", "moved_to__account")
        .order_by("cheque_date", "posted_at", "id")
    )


def void_cheque(actor: Any, *, payment_id: Any, reason: str, on_date: date) -> VoidedCheque:
    """CS-30's third rule — torn up at the counter, with no bank event.

    *"A cheque not yet banked may be voided at the counter without a bank
    reversal; once it is in a cut batch, only the reversal path applies."*

    **IT IS A STATUS MOVE AND NOT A REVERSAL, AND THE DIFFERENCE REACHES THE
    CUSTOMER.** Running this through `reverse_payment` would write a reversing
    row, mirror a journal entry that does not exist, and — if the reason were
    left at its default — count an NSF against a customer whose cheque never
    went near a bank, with a cash-only flag possible behind it. A cheque taken in
    error and torn up before the deposit is cut is a COUNTER event; CS-30 says
    so in as many words.

    **THREE THINGS ARE REFUSED, each because the void would be a lie:**

      * a cheque that has CLEARED — the money arrived and is in the books. That
        is a reversal (`POST /payments/{id}/reverse`), a bank event, and it
        writes the rows this path deliberately does not.
      * a payment sitting in a deposit batch — it is in the cut, whatever its
        status says, and the batch total names it.
      * a row that is not a structured cheque — this path exists for an
        instrument somebody can physically tear up.

    Nothing is posted, nothing is reversed and no allocation moves: a
    `processing` payment met no bill and reached no ledger (BR-PAY-021), which is
    exactly why the counter void is expressible at all.

    `on_date` is the caller's business day and is recorded; no clock is read.
    """
    tenant_id = _tenant_id()
    if not (reason or "").strip():
        raise PaymentRuleError(
            "voiding a cheque needs a reason. A payment that vanishes from the drawer with no "
            "explanation is the one thing a bookkeeper cannot reconcile.",
            br_ref="BR-PAY-881",
        )
    payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id} is not this tenant's. Nothing was voided.",
            br_ref="BR-TEN-003",
        )
    if not is_a_structured_cheque(payment):
        raise PaymentRuleError(
            f"{payment.payment_no or payment.pk} is not a cheque — it carries no cheque date. "
            "The counter void exists for an instrument somebody can physically tear up; any "
            "other correction is a reversal (BR-PAY-011) or a reapply (BR-PAY-031).",
            br_ref="BR-PAY-881",
        )
    if payment.status == models.PAYMENT_POSTED:
        # CR-186-BRC10 — a posted cheque is applied and journalled, so a void
        # (which writes neither) would leave the books wrong. Cancel undoes both.
        raise PaymentRuleError(
            f"Cheque {payment.confirmation or payment.payment_no} is posted. Cancel the payment instead.",
            br_ref="BR-PAY-881",
        )
    if payment.status != models.PAYMENT_PROCESSING:
        raise PaymentRuleError(
            f"cheque {payment.confirmation or payment.payment_no} is {payment.status!r}, so the "
            "money has already arrived and is in the books. A cheque that has cleared is put "
            "right by a REVERSAL — a bank event that writes a reversing row and mirrors the "
            "journal entry — and not by a counter void, which writes neither.",
            br_ref="BR-PAY-881",
        )
    if payment.deposit_batch_id is not None:
        raise PaymentRuleError(
            f"cheque {payment.confirmation or payment.payment_no} is already in a deposit "
            "batch, so it has been cut and the batch total names it. Voiding it here would "
            "leave the batch claiming money that is not in it; the reversal path applies "
            "from the moment a cheque is banked.",
            br_ref="BR-PAY-881",
        )

    with transaction.atomic():
        payment.status = models.PAYMENT_FAILED
        # `status` and `updated_at` ONLY. `payments/0002`'s trigger compares the
        # whole row minus its allow list, so touching any other column here
        # would be refused — and that refusal is the guarantee this path leans
        # on rather than a thing it works around.
        payment.save(update_fields=["status", "updated_at"])
        # ── hard rule 7, INSIDE the transaction ─────────────────────────────
        # `core.audit` raises rather than losing the row, which takes the void
        # with it. And this row is the ONLY place the reason exists — see the
        # module docstring on OQ-1340.
        core_audit.money_action(
            actor,
            AUDIT_VOIDED,
            "payment",
            str(payment.pk),
            before={"status": models.PAYMENT_PROCESSING},
            after={
                "payment_no": payment.payment_no,
                "account_id": str(payment.account_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": models.PAYMENT_FAILED,
                "cheque_number": payment.confirmation,
                "cheque_date": payment.cheque_date.isoformat(),
                "drawer_bank": payment.drawer_bank,
                "reason": reason,
                "on_date": on_date.isoformat(),
                # Stated on the trail as well as in the docstring: a reader of
                # this row must not have to know that a void is not a bounce.
                "posted_to_ledger": False,
                "is_a_bank_event": False,
                "job": None if actor is not None else "payments.cheque_void",
            },
        )
    return VoidedCheque(
        payment_id=str(payment.pk),
        payment_no=payment.payment_no,
        account_id=str(payment.account_id),
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        reason=reason,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-30 (RULED 2026-09-01) · §11 task 56 · BR-PAY-880..883 ·
#         apps/payments/migrations/0002 (the trigger a void obeys rather than
#         widens) · apps/payments/migrations/0014 (the three-column allow list
#         this does NOT touch) · apps/payments/migrations/0017 (the three new
#         columns) · apps/payments/reconciliation.cut_deposit_batches ·
#         OQ-1340 (OPEN — audit-row pruning)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 task 57 owns P7,
#            S22/S35's fields and S37's becoming-bankable list) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 **RE-PRESENTMENT IS NOT BUILT.** CS-30's second new rule (PO 2026-09-01)
#      needs a second self-link on `payments` and a state walk through the
#      reversal path. It is on `problems[]` on every result and in the lane
#      report; REPORTED, not silently skipped.
#   E2 the cheque number's uniqueness is a SERVICE check and not a unique index.
#      A partial index cannot exempt a reversed row — the fact lives in another
#      row — and this CR's own CS-32 move re-records cheque #8842 on the correct
#      account. Recorded in 12-governance/02-decision-log.md with what it costs.
#   E3 there is no `voided_at` column. Hard rule 4's trigger permits a
#      `processing` row to change its STATUS, so the void is `processing →
#      failed` plus its audit row; a column would have needed the allow list
#      widened, which CLAUDE.md says is a new ruling and not this one.
#   E4 no glob in `10-scripts/gates/human_owned.txt` matches this file, so G7
#      does not read its markers. That list is the PO's to change.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
