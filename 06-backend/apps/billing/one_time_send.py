# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-033 (Send: authorise and issue ONE one-time bill,
#           idempotently, only after the clerk acknowledges the amounts)
#           Screens: S30 (the one-time bill page, step 4)
# Contract: 04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md §5
# Plan:     12-one-time-bill-build-plan.md A6 · A7 · B10 (as amended 2026-09-30)
# Rules:    BR-BIL-005 (idempotent) · BR-BIL-014 (penalty approval — RECORDED,
#           not enforced, PO 2026-09-30) · BR-BIL-016 / BR-BIL-036 (delivery;
#           paper is the floor) · BR-BIL-051 (issue) · BR-BIL-058 (the release
#           gate's five confirmations) · BR-TEN-043 (event time is the caller's)
#           · CLAUDE.md rules 4, 6, 7
# Tests:    06-backend/tests/test_otb_a_one_time_api_contract.py
# Impacts:  apps/billing/api.py (`POST /billing/one-time/{run_id}/send`)
# ───────────────────────────────────────────────────────
"""ONE Send for ONE one-time bill — the release gate and the issue, in one call.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is the transition INTO financial
immutability for every bill that is not part of a cycle run (CLAUDE.md rule 4),
and it writes the `bill_run_releases` row `issue` requires. AI-authored
2026-09-30 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). Row in 12-governance/09-human-review-ledger.md.

IT RE-IMPLEMENTS NOTHING
────────────────────────
A cycle run reaches issue through two routes and two human acts — the S31
sign-off (`POST …/release`, five separately recorded confirmations) and *Send
them out* (`POST …/issue`). A one-time bill is ONE bill and ONE clerk, and the
redrawn page draws ONE act: the Send card's five confirmations (amended from a
single tick, PO 2026-09-30, option B) unlocking **Send**. So this calls the
same two functions those routes call — `release.authorise_release` and
`release.release_run` — in order, with the five the clerk ticked. Everything
issue does is issue's: the number
from the tenant's series, the due date, the GL stamps, the template pin, the
delivery rows, the balanced posting handoff, the read lock and the audit rows.

⚠ **FIVE TICKS, NOT ONE — PO RULING 2026-09-30, OPTION B, verbatim: *"B · Show
all five ticks on the one-time Send card."*** Until that ruling the page asked
ONE question (*"I checked the amounts"*) and this recorded it as all five of
BR-BIL-058's confirmations. BR-BIL-058 records five facts because *"a release
that went out without the compliance check is a different event from one that
did"*, and one tick could not say which. Now the Send card shows the same five
a cycle release asks — compliance, email, text, autopay, final — Send stays
disabled until all five are ticked, and `send` takes the five the clerk gave
and records each exactly as given, with `confirmed_by` = the clerk and
`confirmed_at` = their `sent_at`. Nothing here infers a confirmation.

ONE BILL OR NOTHING
───────────────────
`release_run` never lets a break stop a cycle run (BR-BIL-055) — 499 issue and
one comes back named. A one-time run holds ONE bill, so a break is the whole
run failing, and leaving a stamped release over an unissued draft would make the
next Send answer *"already sent"* over a bill nobody received. So the pair runs
inside ONE transaction and a broken bill raises, rolling back the authorisation
and the release stamp together. ⚠ **ON POSTGRESQL THIS IS SAFE ONLY BECAUSE
`issue_run` WRAPS EACH BILL IN ITS OWN SAVEPOINT** — a failed statement inside
it poisons only that savepoint (hard-won law 14), and the outer rollback here
then discards everything cleanly. Proved on PostgreSQL 16, not only on sqlite.

IDEMPOTENT, AT THE LEVEL A CLERK CAN SEE
────────────────────────────────────────
A second Send — a double click, a retry after a timeout — finds the run's
COMPLETED release and answers `created: false` with the SAME bill: the same
number, the same total, nothing written (hard rule 6, US-BIL-033 TC-5). An
authorised-but-unreleased row (a crash between the two) is RESUMED rather than
re-authorised, exactly as `POST …/issue` resumes one (epic TC-13).

PENALTY APPROVAL IS RECORDED, NOT ENFORCED — PO RULING 2026-09-30
─────────────────────────────────────────────────────────────────
`OQ-BIL-12781` asked where a penalty bill's approval lives, because nothing in
the product records an approval of a DRAFT and a refusal would have refused
every penalty bill for ever. The PO closed it the same day: Send is never
refused for it; the body may carry `approved_by` — a staff user
(`{"user_id": …}`) or a typed name (`{"name": …}`) — which is written into the
draft's `bill_payload.penalty.approved_by` BEFORE issue freezes the payload, and
into `audit_log`. There is no `approvalRequired` refusal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import delivery_seam, models, release
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import tenancy as core_tenancy

#: What `unavailable` says on every Send answer — each a real limit, stated.
SEND_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "paper_is_always_queued_for_a_bill",
        "br_ref": "BR-BIL-036",
        "detail": "print is the floor for every bill and the queue owner adds it whatever "
        "was chosen, so 'email' queues email AND paper, exactly as 'email_and_paper' does. "
        "The choice is recorded as the clerk's intent; no rule lets a bill go out without "
        "its paper copy.",
    },
)


class SendRefused(BillingRuleError):
    """The one bill of this run could not be issued; nothing was written."""


@dataclass(frozen=True)
class SendOutcome:
    invoice: models.Invoice
    created: bool
    delivery: str


def one_time_run_or_none(run: models.BillRun) -> bool:
    """True when `run` is a ONE-TIME run — no cycle, one account (migration 0021)."""
    return run.cycle_id is None and run.scope_account_id is not None


def _the_bill(run: models.BillRun) -> models.Invoice | None:
    return (
        models.Invoice.objects.filter(tenant_id=core_tenancy.current_tenant_id(), bill_run=run)
        .order_by("created_at", "id")
        .first()
    )


def _record_approval(invoice: models.Invoice, approved_by: dict[str, Any], *, actor: Any) -> None:
    """PO 2026-09-30 — who approved a penalty bill, on the bill and in the audit log.

    Written while the bill is still a DRAFT (the only window its payload can be
    written in, `billing/0006`), so issue freezes it with the money. `user_id` is
    kept as the record's identity and is never shown as a value (B14 rule 31); a
    typed `name` is kept as typed.
    """
    payload = dict(invoice.bill_payload or {})
    payload["penalty"] = {**dict(payload.get("penalty") or {}), "approved_by": dict(approved_by)}
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    audit.money_action(
        actor,
        "invoice.penalty_approval_recorded",
        "invoice",
        str(invoice.pk),
        before=None,
        after={"approved_by": dict(approved_by)},
    )


def _refuse_a_closed_account_unless_its_move_out_final(bill: models.Invoice) -> None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-CUS-10093` — the ONE carve-out, and the wall around it.

    PO ruling 2026-10-13, option B: *"Sending a draft whose account the
    move-out has since closed must be ALLOWED, because the bill was raised
    while the account was billable. That is the only carve-out, and only for a
    final draft created by a move-out."* So a draft whose account has left the
    billable classes (BR-CUS-055) is sent ONLY when it is that draft
    (`final_bill.move_out_final_draft`); any other draft on a closed account —
    an interim drafted before the close, say — is refused by name, so nothing
    else on a closed account can be billed.
    """
    from apps.billing import final_bill, gather

    if final_bill.move_out_final_draft(bill):
        return
    account_or_404 = gather._resolve("customers", "account_or_404")
    if account_or_404 is None:  # pragma: no cover — customers always publishes it
        return
    account = account_or_404(bill.account_id)
    if gather._behavior_class(account) in final_bill.BILLABLE_CLASSES:
        return
    raise SendRefused(
        f"account {getattr(account, 'account_no', bill.account_id)} is closed, and only the "
        "final draft its move-out created may be sent after the close (DEF-CUS-10093). "
        "Nothing was sent.",
        message_key="billing.oneTime.err.alreadyClosed",
    )


def send(
    run: models.BillRun,
    *,
    delivery: str,
    sent_at: datetime,
    template_id: Any,
    template_version: int,
    template_pin_explicit: bool,
    approved_by: dict[str, Any] | None,
    confirmations: release.Confirmations,
    confirmed_by: Any,
    actor: Any,
) -> SendOutcome:
    """Authorise and issue this run's ONE draft, or answer the bill already sent.

    The caller has already checked the body's shape; this is the money half.
    `confirmations` are the FIVE the clerk ticked (PO ruling 2026-09-30, option
    B), recorded exactly as given — `authorise_release` refuses, naming each,
    if any is missing, so nothing here can infer one. `sent_at` is the clerk's
    moment (BR-TEN-043) and is both the release's `confirmed_at` and the
    bill's `issued_at` — one press of Send is one business moment.
    """
    done = release.completed_releases(run).first()
    if done is not None:
        invoice = _the_bill(run)
        if invoice is None:  # pragma: no cover — a released run always holds its bill
            raise SendRefused("this run was released with no bill on it.")
        return SendOutcome(invoice=invoice, created=False, delivery=delivery)

    bill = _the_bill(run)
    if bill is None:
        raise SendRefused(
            f"run {run.pk} holds no draft bill, so there is nothing to send. A one-time "
            "run is created with its one draft (BR-BIL-020); a run with none was refused "
            "at draft and has nothing to issue."
        )

    _refuse_a_closed_account_unless_its_move_out_final(bill)

    with transaction.atomic():
        if approved_by and bill.bill_type == "penalty" and bill.status == models.INVOICE_DRAFT:
            _record_approval(bill, approved_by, actor=actor)
        row = release.pending_releases(run).first()
        if row is None:
            row = release.authorise_release(
                bill_run=run,
                summary=release.summary_for(run),
                confirmations=confirmations,
                confirmed_by=confirmed_by,
                confirmed_at=sent_at,
                actor=actor,
            )
        with delivery_seam.clerk_delivery_choice(delivery):
            outcome = release.release_run(
                bill_run=run,
                release_row=row,
                released_at=sent_at,
                issued_at=sent_at,
                template_id=template_id,
                template_version=template_version,
                actor=actor,
                template_pin_explicit=template_pin_explicit,
            )
        if outcome.issued.broken:
            broken = outcome.issued.broken[0]
            raise SendRefused(
                "the bill could not be issued, so nothing was sent and nothing was "
                f"recorded: {getattr(broken, 'detail', broken)}"
            )
        audit.money_action(
            actor,
            "invoice.one_time_sent",
            "invoice",
            str(bill.pk),
            before=None,
            after={
                "bill_run_id": str(run.pk),
                # PO 2026-09-30 (option B) — the five, as the clerk gave them,
                # with who and when. This recorded `acknowledged: True` for one
                # tick standing for all five.
                "confirmations": {
                    name: bool(getattr(confirmations, name))
                    for name in (
                        *(name for name, _column in release.CONFIRMATION_COLUMNS),
                        release.FINAL_CONFIRMATION,
                    )
                },
                "confirmed_by": str(confirmed_by) if confirmed_by is not None else None,
                "confirmed_at": sent_at.isoformat(),
                "delivery": delivery,
                "sent_at": sent_at.isoformat(),
                "release_id": str(row.pk),
            },
        )
    bill.refresh_from_db()
    return SendOutcome(invoice=bill, created=True, delivery=delivery)


def sent_body(outcome: SendOutcome) -> dict[str, Any]:
    """§5's answer — the same shape whether this call issued the bill or found it."""
    invoice = outcome.invoice
    return {
        "run_id": str(invoice.bill_run_id),
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "total": str(invoice.total.quantize(_FOUR)) if invoice.total is not None else None,
        "currency": invoice.currency,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "status": invoice.status,
        "delivery": "queued",
        "delivery_choice": outcome.delivery,
        "reads": "locked",
        "created": outcome.created,
        "unavailable": [dict(row) for row in SEND_UNAVAILABLE],
    }


_FOUR = Decimal("0.0001")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-033@2026-09-30 (sources: 13-one-time-bill-api-contract.md §5 as
#         amended 2026-09-30 · 12-one-time-bill-build-plan.md A6/A7/B10 ·
#         EP-BIL-03 US-BIL-033 · decision log 2026-09-30 "SIX ANSWERS")
# generated: 2026-09-30 by the one-time bill API lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see tests/test_otb_a_one_time_api_contract.py (sqlite) and the
#        PostgreSQL 16 run named in the lane report
# exceptions: SEND_UNAVAILABLE above
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
