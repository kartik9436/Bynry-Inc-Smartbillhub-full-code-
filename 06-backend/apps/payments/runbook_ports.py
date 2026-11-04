# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-014 (EP-RBS-04) — CR-075 wave L task L2: the
#           five ports payments owns, bound to ONE service function each, in
#           the module that owns the tables.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-018 (a money-bearing action carries a second
#           approval) · BR-RBS-013 / CLAUDE.md hard rule 4 (no UPDATE or DELETE
#           on a payment; corrections are new rows) · hard rule 6
#           (idempotency) · hard rule 1 (tenant scoping) · hard rule 2 (money
#           to 4 decimals, never a float, always with its currency)
# Tests:    06-backend/tests/test_us_rbs_010_port_writers.py
# Impacts:  apps/runbooks/ports/payments_ports.py (binds these five)
# ───────────────────────────────────────────────────────
"""The five writes a runbook may make in this module. Every one is a NEW ROW.

⚠ **HARD RULE 4 IS THE SHAPE OF THIS WHOLE FILE.** No UPDATE and no DELETE on a
payment, an issued invoice, an invoice line or a journal entry — corrections are
new rows. So there is no port here that edits anything: `apply_payment` records
a payment, `post_credit` writes allocations, `raise_refund` writes a refund
REQUEST, `record_match` names a pairing, `schedule_retry` writes an intent.
**The one narrow exception hard rule 4 carries — `confirmation`, `memo` and
`method_id` through `POST /payments/{id}/correct-reference` — is not reachable
from here and must not be widened to be.** A runbook that could rewrite a cheque
number is a runbook that can rewrite the evidence.

⚠ **EACH FUNCTION DELEGATES TO THIS MODULE'S OWN SERVICE, BY NAME.** They are
thin on purpose: a port that reimplemented allocation order, refund approval or
the deposit-batch rules would be a second copy of payments' law living in a file
payments' reviewers do not read. What each adds is (a) the runbook's
`AutomationActor` as the actor, so the trail names the automation rather than a
person (`BR-RBS-015`), and (b) an idempotency handle the runbook can compute the
same way twice.

⚠ **THE ENGINE WRITES THE RUNBOOK'S AUDIT ROW, NOT THIS FILE** (`BR-RBS-022`).
The services below write payments' OWN rule-7 rows, as they always did.

⚠ **`apply_fee` IS NOT HERE AND IS NOT PAYMENTS'.** It is billing's — a fee is a
charge line and payments writes no charge line, ever (`apps/payments/ladder.py`
says the same thing about the ladder's own late-fee rung: *"This engine CITES
the step and applies nothing"*). The collections category's owning module is
payments and runbook 8 still holds `apply_fee`; that is `DEF-RBS-4262`'s reading
— the category is PROVENANCE, and the allow-list is the runbook's own `ports[]`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from apps.payments import (
    autopay,
    credit,
    idempotency,
    ladder,
    reconciliation,
    refunds,
    services,
)


def apply_payment(
    *,
    actor: Any,
    account_id: Any,
    amount: Decimal,
    posted_at: dt.datetime,
    idempotency_reference: Any,
    currency: str | None = None,
    method_code: str | None = None,
    confirmation: str | None = None,
    memo: str | None = None,
    cleared_at: dt.datetime | None = None,
) -> dict[str, Any]:
    """PORT `apply_payment` — record a landed payment and allocate it by the order.

    Delegates to `apps.payments.services.record_payment`, which is `BR-PAY-022`'s
    one door: all of it, or none of it. The allocation order is that function's
    default (`oldest first`) and is **not** re-decided here — a port that chose
    an order would be a second statement of a signed rule.

    ⚠ **`amount` IS A `Decimal` AND NEVER A FLOAT** (hard rule 2). Money is
    stored to 4 decimals and displayed to 2; a float that has been through JSON
    is not money and this refuses it rather than storing a value nobody can
    reconcile.

    ⚠ **`idempotency_reference` IS REQUIRED AND IS THE RUNBOOK'S OWN HANDLE.**
    Hard rule 6 makes an inbound payment idempotent on
    `(source, reference)`; the runbook passes the same reference on a retry, so
    a re-run applies the SAME payment once rather than twice. `posted_at` is an
    argument and never a clock read (`BR-TEN-043`, gate `G6`).
    """
    _require_decimal(amount, "amount")
    recorded = services.record_payment(
        actor,
        account_id=account_id,
        amount=amount,
        posted_at=posted_at,
        cleared_at=cleared_at,
        currency=currency,
        method_code=method_code,
        confirmation=confirmation,
        memo=memo,
        idempotency_source=idempotency.SOURCE_IMPORT,
        idempotency_reference=idempotency_reference,
    )
    payment = getattr(recorded, "payment", None)
    return {
        "entity_type": "payment",
        "entity_id": str(getattr(payment, "pk", "") or ""),
        "created": bool(getattr(recorded, "created", True)),
        "amount": str(amount),
        "currency": currency,
    }


def post_credit(
    *,
    actor: Any,
    account_id: Any,
    invoice_id: Any,
    invoice_total: Decimal,
    occurred_on: dt.date | None = None,
) -> dict[str, Any]:
    """PORT `post_credit` — draw a carried credit down against an open bill.

    Delegates to `apps.payments.credit.apply_credit_at_issue` (`BR-PAY-010`).
    `invoice_total` is the CALLER's figure: this module prices nothing and
    rounds nothing — B4 is finance-signed and lives in `core.money` — so a
    runbook that wanted to invent a total would have nowhere to put it.

    Worked, `US-PAY-007`'s own case: credit 57.13 against a bill of 42.10
    applies **42.10** and carries **15.03**, which applies again next cycle and
    is never dropped. Rows are append-only (`BR-PAY-002`), so a second call for
    the same invoice finds nothing left to apply rather than applying it twice.
    """
    _require_decimal(invoice_total, "invoice_total")
    application = credit.apply_credit_at_issue(
        actor=actor,
        account_id=account_id,
        invoice_id=invoice_id,
        invoice_total=invoice_total,
        occurred_on=occurred_on,
    )
    return {
        "entity_type": "allocation",
        "entity_id": str(invoice_id),
        "created": bool(getattr(application, "applied", Decimal("0")) > 0),
        "applied": str(getattr(application, "applied", "")),
        "carried": str(getattr(application, "carried", "")),
    }


def raise_refund(
    *,
    actor: Any,
    amount: Decimal,
    method: str,
    requested_at: dt.datetime,
    account_id: Any = None,
    payment_id: Any = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """PORT `raise_refund` — a refund REQUEST. **No money moves here.**

    `BR-PAY-014`: step 1 is a request and the row exists from that moment so the
    approval queue has something to show. `BR-RBS-018` then applies on top —
    a refund is money-bearing, so it carries the second approval, and
    `OQ-RBS-1732` was closed on 2026-09-06 with **every money-bearing action
    carrying it and NO threshold**. There is deliberately no `threshold`
    argument here: a threshold can only ever widen what an automation may do
    unattended, and shipping without one cannot be wrong in the dangerous
    direction.

    ⚠ **THIS PORT CANNOT APPROVE OR ISSUE.** `approve_refund` and
    `issue_refund` exist in this module and are NOT bound to any port. A runbook
    may ask; a person decides.
    """
    _require_decimal(amount, "amount")
    result = refunds.request_refund(
        actor,
        payment_id=payment_id,
        account_id=account_id,
        amount=amount,
        method=method,
        requested_at=requested_at,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    refund = getattr(result, "refund", None)
    return {
        "entity_type": "refund",
        "entity_id": str(getattr(refund, "pk", "") or ""),
        "created": bool(getattr(result, "created", True)),
        "amount": str(amount),
        "status": str(getattr(refund, "status", "")),
    }


def record_match(
    *,
    actor: Any,
    batch_id: Any,
    bank_line_id: Any,
    occurred_at: dt.datetime,
) -> dict[str, Any]:
    """PORT `record_match` — name a bank line as one deposit batch's.

    Delegates to `apps.payments.reconciliation.match_bank_line`. **Nothing
    reconciles here**: the amounts still differ by the processor's fee and that
    difference remains to be explained in `reconcile_batch`, which is a person's
    act and is not a port. `occurred_at` is an argument, never a clock read.

    A batch that is already reconciled is LOCKED (`BR-PAY-004`) and this raises
    rather than force-matching — the engine records that refusal against the
    record row in the owning module's own words, which is what `BR-RBS-010`
    asks for.
    """
    difference = reconciliation.match_bank_line(
        actor=actor,
        batch_id=batch_id,
        bank_line_id=bank_line_id,
        occurred_at=occurred_at,
    )
    return {
        "entity_type": "bank_line",
        "entity_id": str(bank_line_id),
        "created": True,
        "difference": str(difference),
    }


def schedule_retry(
    *,
    actor: Any,
    account_id: Any,
    invoice_id: Any,
    amount: Decimal,
    due_date: dt.date,
    currency: str = "USD",
) -> dict[str, Any]:
    """PORT `schedule_retry` — put a failed debit back on the rails, dated.

    Delegates to `apps.payments.autopay.record_intent_at_issue`, which is
    `BR-PAY-015`'s one write and is **IDEMPOTENT ON THE INVOICE**:
    `UNIQUE (tenant, invoice_id)` is the guarantee rather than a
    `SELECT`-then-`INSERT` two workers would both win. So a runbook retrying the
    same failed debit twice promises the customer one draft, not two — which is
    the whole reason this is the function bound rather than a fresh row per
    attempt.

    ⚠ **A NON-ENROLLED ACCOUNT GETS NO INTENT AND THAT IS REPORTED, NOT
    RAISED** (`TC-4`). A ladder walking 1,004 accounts must not fail because 300
    of them are not on autopay.
    """
    _require_decimal(amount, "amount")
    result = autopay.record_intent_at_issue(
        actor=actor,
        account_id=account_id,
        invoice_id=invoice_id,
        amount=amount,
        due_date=due_date,
        currency=currency,
    )
    intent = getattr(result, "intent", None)
    return {
        "entity_type": "autopay_capture_intent",
        "entity_id": str(getattr(intent, "pk", "") or ""),
        "created": bool(getattr(result, "created", False)),
        "amount": str(amount),
        "currency": currency,
        "scheduled_on": str(due_date),
    }


def _require_decimal(value: Any, what: str) -> None:
    """Hard rule 2: money is a `Decimal`. A float is refused, loudly.

    ⚠ **THE REFUSAL IS THE POINT.** A float that has been through JSON is not
    money — `0.1 + 0.2` is not `0.3` — and storing one produces a figure that
    reconciles against nothing and that no column type will catch, because
    these values pass through `jsonb` on the way here.
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{what} must be a Decimal and arrived as {type(value).__name__}. Money is stored "
            "to 4 decimals and never as a float (CLAUDE.md hard rule 2); a runbook that "
            "computed one has already lost the figure."
        )


def step_ladder(
    *,
    actor: Any,
    account_id: Any,
    rung: str,
    as_of: dt.date,
    channels: tuple[str, ...] = ("pdf_print",),
    cut_date: dt.date | None = None,
) -> dict[str, Any]:
    """PORT `step_ladder` — ONE collections step: the notice, its record, the tier.

    ⚠ **THIS IS THE FOURTEENTH PORT AND IT WAS ADDED DELIBERATELY** (`CR-075`
    wave `N`, 2026-09-07). `12-the-contract.md` §6 says a new runbook needing a
    new port is *"adding a reviewed interface, not a custom write"* — this is
    that, and the reasoning is `DEF-RBS-4347`'s ruling in the decision log.
    Runbook 8 previously held `queue_notice`, which is `notifications`' port and
    writes ONE of the three rows a ladder step is. The other two —
    `notice_history` and `account_collection_state` — are PAYMENTS' tables under
    `BR-PAY-017`, so a runbook writing them would be a second writer of a signed
    rule's state and `notifications` writing them would be a cross-module write.
    **The act belongs to whoever owns the state it moves**, so the port is
    payments' and the whole step happens on the far side of it.

    ⚠ **NOTHING HERE SENDS.** `notices.send_*` write queue rows and the
    dispatcher sends (`BR-NOT-005`); no delivery provider is connected. The word
    on every result is **Queued**.

    ⚠ **PAYMENTS MAY STILL REFUSE, AND A REFUSAL IS A NORMAL RETURN.** An active
    payment plan or a tier already sent comes back `stepped: false` with the
    reason, not as an exception: the engine records it as the outcome and the
    clerk reads why. `ladder.step_one` holds both checks.

    `as_of` and `cut_date` are ARGUMENTS, never clock reads (`BR-TEN-043`,
    `G6`) — a ladder re-taken for last Tuesday must take last Tuesday's date
    onto the letter.
    """
    step = ladder.step_one(
        account_id=account_id,
        rung=rung,
        as_of=as_of,
        actor=actor,
        channels=tuple(channels),
        cut_date=cut_date,
    )
    return {
        "entity_type": "notice_history",
        # The honest half, and the one the Records table draws: False means
        # payments refused this step, and a clerk must never be told a notice
        # went out when it did not.
        "stepped": step.stepped,
        "skip_reason": step.skip_reason,
        "rung": step.rung,
        # Both ends of the move, so *the ladder climbed* is a fact a reader can
        # check rather than a claim — `DEF-RBS-4347` was invisible precisely
        # because nothing anywhere recorded the two tiers.
        "tier_from": step.tier_from,
        "tier_to": step.tier_to,
        "message_ids": list(step.queued_message_ids),
        "problems": [dict(problem) for problem in step.problems],
        # Stated as a VALUE rather than only in prose (hard-won law 1).
        "dispatched": False,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-014 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a port is called by the engine, never over HTTP) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path here — every function delegates to a service already on the guarded surface, and the idempotency KEY is composed in apps/runbooks/engine/acts.py)
# gates: pytest tests/test_us_rbs_010_port_writers.py · G115 · G6 (no clock read — every moment is an argument)
# exceptions: approve_refund, issue_refund, reconcile_batch and the correct-reference path are deliberately NOT bound to any port
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
