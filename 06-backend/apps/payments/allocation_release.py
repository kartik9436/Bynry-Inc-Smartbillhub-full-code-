# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-006 (allocation — what a payment meets) · US-BIL-015 /
#           US-BIL-016 (the correction that replaces the bill it met)
#           Screens: S30 (Fix a bill — the settlement panel, CR-059 task 20) ·
#           S21 (Account detail, Payments tab) · S33 (Record payments)
# Change:   CR-059 CS-36, 2026-09-01 — *"Re-allocate the payment when a bill is
#           corrected"*. ⛔ LIVE TODAY: a customer who paid 100.00 for a 100.00
#           bill that is then corrected to 80.00 is invoiced for 80.00, told he
#           is six days late, and entered into the collection ladder, while the
#           books say the utility owes him 20.00.
# Rules:    BR-PAY-1072 (a restatement releases the allocations against the bill
#           it replaces — append-only negative mirror rows, never an edit) ·
#           BR-PAY-1073 (a release posts NO journal line, because no money
#           moves) · BR-PAY-1074 (the release runs BEFORE the rebill is issued,
#           inside the correction's one transaction) · BR-BIL-014 (billing
#           emits the re-allocation plan; payments executes it) · BR-PAY-031
#           (reversing rows, never edits) · BR-PAY-010 (the released money
#           becomes carried credit and the next issue draws it down) ·
#           BR-PAY-041 (a credit position is signed and never floored) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money, CHAR(3)) ·
#           rule 4 (append-only) · rule 5 (only the ledger writes journal
#           lines — and this writes none) · rule 6 (idempotency) · rule 7
#           (audit)
# Golden:   NOTHING HERE MINTS A FIGURE. It moves rows that already exist by
#           their own stored amounts and rounds nothing — ❄️ GT-7, PE-4, PE-7,
#           PE-9, PE-10 and PE-13/GT-47 are untouched, and 10-scripts/
#           03-golden-verify.py was run before and after (33 PASS both times).
# Tests:    06-backend/tests/test_cr059_cs36_release.py (the service) ·
#           06-backend/tests/test_cr059_cs36_restatement_pg.py (the three
#           shapes, the tie-out, the replay and the goodwill — on PostgreSQL)
# Impacts:  apps/billing/payments_seam.release_allocations_for_invoice (the
#           seam billing resolves this through) · apps/billing/corrections.
#           execute_restatement (the ONE call site) · apps/payments/credit.
#           credit_position (rises on its own, by rows, with no change) ·
#           apps/payments/billing_seam.allocated_so_far (nets these rows)
# ───────────────────────────────────────────────────────
"""RELEASE WHAT A PAYMENT PUT AGAINST A BILL THAT IS BEING REPLACED.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this writes `allocations` on a money
path, carries a hard-rule-6 replay guarantee and states in terms that it posts
no journal line. AI-authored 2026-09-01 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE TODAY
(measured 2026-09-01), so G7 does not read the two markers above.** Its
neighbours `apps/payments/allocation.py`, `services.py`, `reversal.py`,
`refunds.py`, `reconciliation.py` and `lockbox.py` are each listed by their
exact path and no wildcard covers a new sibling. **Editing that list is a
process event and the PO's call, not a lane's** — its own header says so, and
`issue.py`, `decisions.py` and `read_analysis.py` each record a money path that
went unguarded because every lane was correctly unwilling to add itself. So the
line is REPORTED for the PO batch, in the review-ledger row, rather than
self-granted. **G53 names this file for exactly that reason and its finding is
correct**; what closes it is a ruling, not an edit here.

╔══════════════════════════════════════════════════════════════════════════╗
║  ONE INSERTED STEP. EVERYTHING ELSE THE CORRECTION NEEDS ALREADY WORKS.  ║
╚══════════════════════════════════════════════════════════════════════════╝
A restatement writes four things and all four are correct: a credit note for
the original in full, a rebill inheriting the ORIGINAL due date, the original
moved to `corrected`, and an audit row. **And a fifth thing it did not do: the
payment was never touched.** The 100.00 allocation went on pointing at a bill
that payments can no longer see — `billing_seam.OPEN_INVOICE_STATUSES` reads
`issued` and `paid` and the original is now `corrected` — so:

    the account screen said   outstanding 80.00 · credit 0.00 · days late 6
    the ledger said (rightly) receivable −20.00, the utility owes him 20.00
    and the gap was 100.00, reported by nothing anywhere.

This function is the missing step. Once the allocations are released, the
credit position rises **on its own** (100.00 paid − 0.00 applied, computed from
rows) and the rebill's issue **draws it down** (BR-PAY-010's
`credit.apply_credit_at_issue`, built and wired since 2026-08-15). Result:
outstanding **0.00** · account credit **20.00**, visible and refundable · days
late **0** · the ledger unchanged at **−20.00**, and the two halves agree.

**THE SAME ONE STEP HANDLES ALL THREE DIRECTIONS WITH NO SPECIAL CASE.**

    down     100.00 paid, corrected to  80.00 → release 100.00, rebill draws
                                                80.00, credit 20.00 remains
    up       100.00 paid, corrected to 120.00 → release 100.00, rebill draws
                                                100.00, **20.00 owing** on the
                                                rebill AT THE ORIGINAL DUE DATE
    partial   60.00 paid, corrected to  80.00 → release  60.00, rebill draws
                                                60.00, **20.00 owing**

A **goodwill concession** releases NOTHING, because no bill changed and no
payment moved (PO 2026-08-11: *"you dont touch the bill"*). That is not a case
this function handles; it is a call the correction does not make.

────────────────────────────────────────────────────────────────────────────
THREE RULES, AND EACH ONE IS INVISIBLE IN THE CODE THAT KEEPS IT
────────────────────────────────────────────────────────────────────────────
**BR-PAY-1072 · APPEND-ONLY.** One NEGATIVE mirror row per payment still
applied to this bill, hung off THAT payment. Nothing is edited and nothing is
deleted — `allocations` accepts no UPDATE and no DELETE in any state and the
`0002` trigger is the guarantee, not this paragraph. It is precisely the shape
a bounced cheque already writes (`reversal._write_reversal`), which is why this
is a small function and not a mechanism.

**BR-PAY-1073 · NO JOURNAL LINE.** No money moves: the customer's cash is
already in the books, the credit note has already reversed the original's
revenue and receivable, and the rebill posts its own. A release re-points a
SUBLEDGER application; it is not a cash event, and rule 5 is not being reached
around — there is nothing to post. ⚠ **THE CONSEQUENCE, REPORTED RATHER THAN
QUIETLY LEFT:** the released money shows in the subledger as account credit
while the books carry it inside `1200 Accounts receivable` rather than in
`2400 Customer credit`, because `credit.apply_credit_at_issue` posts nothing
either. The AR control still ties out to the penny — that is what CS-36's own
worked figure (receivable **−20.00**) asserts and what the tie-out test proves
— and reclassifying between two ledger accounts is a finance question about
`apply_credit_at_issue`, not about this function.

**BR-PAY-1074 · BEFORE THE REBILL, IN THE SAME TRANSACTION.** *"The order is
the whole trick"* (CS-36, verbatim). Release AFTER the rebill issues and the
rebill draws down a credit balance that does not exist yet, so it issues
unsettled and the customer is chased for money they have paid — the original
defect with an extra step. Release in a transaction of its OWN and a crash
between the two leaves a released payment with no rebill to meet, which is a
customer with a credit and no bill.

**So this function REFUSES to run outside an open transaction.** That is not
belt-and-braces: `execute_restatement` is `@transaction.atomic`, so inside it
this nests as a SAVEPOINT and the ordering rule is kept by construction, while
a future caller that forgot is told rather than being allowed to write the
defect the rule exists to name. Hard-won law 3 — the unsafe option must be the
one you type.

────────────────────────────────────────────────────────────────────────────
IDEMPOTENCY: THE ARITHMETIC IS THE GUARD, AND THE CASE ROW IS THE OTHER ONE
────────────────────────────────────────────────────────────────────────────
Hard rule 6. CS-36 says the guard *"exists and must be relied on rather than
reinvented"* — `correction_case_bills` holds one row per bill per case and only
moves `queued` → `done`, so a replayed execution never reaches this function
twice for the same bill. **That guard is relied on and NOT duplicated here.**

What this function adds is not a second guard but the correct arithmetic: it
releases what the BILL still has on it, so a second call finds 0.00 and writes
nothing. Mirroring row-by-row would, on a replay, mirror its own negative rows
back into positives and re-apply the whole 100.00 to a bill nobody owes. The
replay is proved on PostgreSQL rather than argued here.

⚠ **AND THE CAP IS NOT THE SAME AS THE PER-PAYMENT SUM — `_still_applied` has
the worked case.** A bounced cheque hangs its negative rows off the REVERSING
payment, so a bounced bill holds `+247.87` on one payment and `−247.87` on
another; releasing every positive net would leave the bill **−247.87** allocated
and the customer owing **495.74** on a **247.87** bill. This was found by a test
going red, not by reading the code (hard-won law 7).

**NOTHING IS ROUNDED.** Every figure is a Σ of stored `allocations.amount`
values and is written back with its sign flipped. There is no new rounding site
on a money path and no B4/B5 figure can move through this file (CLAUDE.md rule
2: round only at finalization/display).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from core import audit as core_audit
from core import tenancy as core_tenancy

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError

__all__ = ["ReleasedRow", "Released", "release_allocations_for_invoice", "AUDIT_RELEASED"]

ZERO = Decimal("0")

#: hard rule 7 — every money action writes `audit_log`. A code, never prose:
#: the trail is grouped on it and S33's release row (CR-059 task 20) reads it
#: to say *"re-allocated — bill 2608-0141 corrected"* rather than rendering an
#: unexplained negative row.
AUDIT_RELEASED = "payment.allocations_released"


def _tenant_id() -> Any:
    """Hard rule 1: never touch a tenant table without `app.tenant_id` set."""
    return core_tenancy.current_tenant_id()


@dataclass(frozen=True)
class ReleasedRow:
    """One payment's release: what came off, and the row that took it off.

    `amount` is POSITIVE — it is what was RELEASED. The row written is its
    negative. Reporting the magnitude is what lets a caller add these up
    without every consumer remembering the sign convention, and the mirror
    row's own id is here so a screen can point at a real row rather than at a
    subtraction it performed itself.
    """

    payment_id: str
    payment_no: str | None
    amount: Decimal
    allocation_id: str


@dataclass(frozen=True)
class Released:
    """What a release did to ONE bill — or, at 0.00, that it did nothing.

    `released` is 0.00 on a bill nobody paid AND on a replay, and those are the
    same fact for the caller: no allocation now points at this bill. It is
    never `None`, because this module owns `allocations` outright and can
    always answer — the seam's None-is-not-zero rule is about facts another
    module holds, and this is not one of them.
    """

    invoice_id: str
    released: Decimal
    currency: str | None
    rows: tuple[ReleasedRow, ...] = ()

    @property
    def released_anything(self) -> bool:
        return self.released > ZERO


def _refuse_outside_a_transaction() -> None:
    """BR-PAY-1074's second half, enforced instead of documented.

    A release that commits on its own is the defect the rule names: a crash
    before the rebill leaves a customer holding a credit against no bill. The
    only lawful caller is inside `corrections.execute_restatement`'s atomic
    block, where this nests as a savepoint.
    """
    connection = transaction.get_connection()
    if not connection.in_atomic_block:
        raise PaymentRuleError(
            "releasing a bill's allocations must happen INSIDE the correction's own "
            "transaction, and this call is not in one (BR-PAY-1074). The release and the "
            "rebill that consumes it either both land or neither does — a release that "
            "committed on its own would leave a customer holding a credit against a bill "
            "that was never issued. Nothing was written.",
            br_ref="BR-PAY-1074",
        )


def _still_applied(
    tenant_id: Any, invoice_id: Any
) -> tuple[Decimal, list[tuple[models.Payment, Decimal]]]:
    """`(what the bill still has on it, the payments holding it)` — both NET.

    ⚠ **TWO FIGURES, AND THE FIRST ONE CAPS THE SECOND. THAT IS NOT TIDINESS —
    IT IS THE BOUNCE CASE, AND IT WAS FOUND BY A TEST GOING RED.** A bounced
    cheque writes its negative mirror rows against the REVERSING payment, not
    against the original (BR-PAY-013), so a bill that was paid and then bounced
    holds `+247.87` on one payment and `−247.87` on another. Releasing every
    positive net would write a *second* `−247.87` and leave the bill showing
    **−247.87** allocated — the customer would owe **495.74** on a **247.87**
    bill. So the loop draws down against the BILL's own net, oldest receipt
    first, exactly as `credit.apply_credit_at_issue` draws a credit down against
    a bill's open balance.

    The invariant the caller relies on: after the release, the Σ of allocations
    against this bill is **0.00**. A replay then finds 0.00 and writes nothing,
    which is hard rule 6 held by arithmetic rather than by a second key.

    Ordered oldest receipt first — the same order `credit._unapplied_by_payment`
    uses — so the released list, the audit row and the screen all read in one
    order and a test can assert a sequence.
    """
    rows = models.Allocation.objects.filter(tenant_id=tenant_id, invoice_id=invoice_id)
    bill_net = rows.aggregate(total=Sum("amount"))["total"] or ZERO
    if bill_net <= ZERO:
        return ZERO, []
    applied = {
        row["payment_id"]: row["net"] or ZERO
        for row in rows.values("payment_id").annotate(net=Sum("amount"))
    }
    payments = (
        models.Payment.objects.filter(tenant_id=tenant_id, pk__in=list(applied))
        .select_for_update()
        .order_by("posted_at", "created_at", "id")
    )
    holders = [(payment, applied[payment.pk]) for payment in payments if applied[payment.pk] > ZERO]
    return bill_net, holders


def _one_currency(pairs: list[tuple[models.Payment, Decimal]], invoice_id: Any) -> str | None:
    """The CHAR(3) that rides with the released amount (hard rule 2).

    One currency per utility and never converted (BR-TEN-042), so two different
    codes against one bill is a broken world rather than a case to handle — it
    is refused BY NAME instead of being netted into a figure whose unit nobody
    could state.
    """
    codes = {payment.currency for payment, _ in pairs if payment.currency}
    if not codes:
        return None
    if len(codes) > 1:
        raise PaymentRuleError(
            f"the payments applied to bill {invoice_id} carry more than one currency "
            f"({sorted(codes)}), so what would be released has no single CHAR(3) to travel "
            "with it (BR-TEN-042 — one currency per utility, never converted). Refused "
            "rather than summed; nothing was written.",
            br_ref="BR-TEN-042",
        )
    return codes.pop()


def release_allocations_for_invoice(
    *,
    invoice_id: Any,
    reason: str,
    occurred_on: date | None = None,
    actor: Any = None,
) -> Released:
    """Take every payment off a bill that is being replaced. BR-PAY-1072/73/74.

    Called from `corrections.execute_restatement`, between the credit note and
    the rebill, inside that function's transaction. See the module docstring for
    why the ORDER and the TRANSACTION are rules rather than implementation
    detail, and why nothing is posted to the ledger.

    Worked, CS-36's own case: Ajinkya's **100.00** against bill `2608-0141`
    comes off as one **−100.00** mirror row hung off his own payment. His credit
    position is then 100.00 paid − 0.00 applied = **100.00**, the rebill issues
    at 80.00 and draws **80.00** of it, and **20.00** stays as visible,
    refundable credit.

    `reason` is the correction's own reason code, carried into the audit row so
    the trail says WHY the money came off. `occurred_on` is the correction's
    business date (BR-TEN-043 — event time is an argument); **no clock is read
    anywhere on this path**, exactly as `services.record_payment` reads none.

    Returns what was released, at 0.00 for a bill nobody paid and at 0.00 for a
    replay. It raises only on a broken world: outside a transaction, or a bill
    whose payments disagree about their currency.
    """
    _refuse_outside_a_transaction()
    tenant_id = _tenant_id()
    bill_net, holders = _still_applied(tenant_id, invoice_id)
    currency = _one_currency(holders, invoice_id)

    rows: list[ReleasedRow] = []
    released = ZERO
    remaining = bill_net
    for payment, net in holders:
        if remaining <= ZERO:
            break
        # Capped at what the BILL still has on it — see `_still_applied`. Taking
        # the payment's whole net instead would double-release a bill whose
        # cheque has already bounced.
        share = net if net < remaining else remaining
        # BR-PAY-1072: a NEGATIVE mirror row hung off the payment that made the
        # application. The original row is untouched — `allocations` refuses
        # UPDATE and DELETE in every state (migration 0002), so this is the only
        # lawful way to unmake an application, and it is the same one a bounce
        # uses. NOTHING IS ROUNDED: `share` is a Σ of stored amounts.
        mirror = models.Allocation.objects.create(
            tenant_id=tenant_id,
            payment=payment,
            invoice_id=invoice_id,
            amount=-share,
        )
        released += share
        remaining -= share
        rows.append(
            ReleasedRow(
                payment_id=str(payment.pk),
                payment_no=payment.payment_no,
                amount=share,
                allocation_id=str(mirror.pk),
            )
        )

    if released > ZERO:
        # hard rule 7, INSIDE the transaction — money that moved with no record
        # of who moved it is impossible on this path, and a lost audit row takes
        # the release (and therefore the whole correction) with it.
        core_audit.money_action(
            actor,
            AUDIT_RELEASED,
            "invoice",
            str(invoice_id),
            after={
                "account_id": str(holders[0][0].account_id),
                "released": str(released),
                "currency": currency,
                "reason": reason,
                "occurred_on": occurred_on.isoformat() if occurred_on is not None else None,
                "rows": [
                    {
                        "payment_id": row.payment_id,
                        "payment_no": row.payment_no,
                        "amount": str(row.amount),
                        "allocation_id": row.allocation_id,
                    }
                    for row in rows
                ],
                # BR-PAY-1073, said out loud in the trail a finance user reads:
                # this event moved a subledger application and posted nothing.
                "journal_entry_id": None,
                "posts_no_journal_line": "no money moved",
                "job": None if actor is not None else "payments.allocation_release",
            },
        )

    return Released(
        invoice_id=str(invoice_id),
        released=released,
        currency=currency,
        rows=tuple(rows),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-36 (the specification, in full) · §11 tasks 14/19/21 ·
#         §7 (how payments works today — the bounce's second step, the credit
#         position's arithmetic, the two dates) · §6 (the ten rulings of
#         2026-09-01) · 04-docs/05-modules/08-payments/02-business-rules.md ·
#         CLAUDE.md hard rules 1/2/4/5/6/7 and hard-won laws 1/2/3/7/14
# generated: 2026-09-01 by the CR-059 W4 CS-36 lane (tasks 14/19/21)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — CS-36 asks for ONE service and
#         ONE call in the restatement; there is deliberately no route, because a
#         clerk never releases an allocation on its own — the correction does)
#         E=deferred(no-frontend-half — S30's settlement panel and the S21/S33
#         release rows are CR-059 task 20, NOT this task) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 row in 09-human-review-ledger.md)
# gates: ruff✔ black✔ · proved RED first — the transaction guard, the ordering
#         and the replay were each broken deliberately, RUN, and the measured
#         failure quoted in the lane report before any of them was trusted green
#         (hard-won law 7). The three shapes, the tie-out and the replay run on
#         PostgreSQL, not on the default SQLite suite (hard-won law 14).
# exceptions: (1) NO ROUTE AND NO ROLE GATE. Every other CS in this wave adds a
#         door; this one deliberately does not. The only caller is
#         `corrections.execute_restatement`, which is already gated by the
#         correction workflow's own approval (BR-BIL-014, US-BIL-017 TC-4), and
#         a second way to release an allocation would be a way to move a
#         customer's money that no approval covers. REPORTED rather than added.
#         (2) THE RELEASED MONEY SITS IN `1200 AR` IN THE BOOKS, NOT IN `2400
#         CUSTOMER CREDIT`. That is `credit.apply_credit_at_issue`'s existing
#         shape (it posts nothing) and not something this lane changed; the AR
#         control ties out exactly, which is the assertion CS-36 asks for. Named
#         in the docstring rather than patched around.
#         (3) IDEMPOTENCY IS THE CASE ROW'S PLUS THE NET ARITHMETIC — no new
#         idempotency key was minted, because CS-36 says the guard exists and
#         must be relied on. The replay is PROVED, not asserted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
