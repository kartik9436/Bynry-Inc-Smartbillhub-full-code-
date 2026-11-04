# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · P1.22 · lane MVI-FLOW
# Rules:    CR-171 §6.2 J6 · §6.1 (Cancelled) · BR-MET-036 (occupancy derived) ·
#           BR-CUS-056 (the next tenant's boundary day) · BR-PAY-014 (a refund
#           is a REQUEST) · CLAUDE.md hard rules 4 · 7
# Question: OQ-CUS-12790 — CLOSED 2026-10-05 → (a); built by lane RULINGS
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**Cancel move-in — both kinds, read back from the tables.**

RED-FIRST (law 7): written before `move_in_cancel` existed; first run
`ModuleNotFoundError: No module named 'apps.customers.move_in_cancel'`.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **Asserting the response, not the rows.** Every case reads the job, the
    account, the agreements, the refund and the work order back.
  * **A "vacant" that is asserted, not derived.** The committed case asks
    metering's own `occupancy_of` — the derivation the Units page shows.
  * **A cancel that locks the next tenant out.** The boundary case moves a
    second household in ON the cancelled move-in's own date and proves it is
    accepted.
  * **A refund that passes because nothing was paid.** The money case records
    a real $25.00 payment first and reads the `refunds` row's amount.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from core import errors

from apps.customers import models as customers_models
from apps.customers import move_in_cancel, move_in_jobs, moves
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors

from tests.test_br_cus_1077_move_in_job import _move_in_request, _served_unit
from tests.test_def_cus_6353_first_occupant_move_in import _payload, _work_catalogue
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _committed(actor, tenant, *, label="Unit 3B", address="8 Kestrel Park", **extra):
    _premises, unit = _served_unit(actor, tenant, label=label, address=address)
    result = customers_services.move_in_to_unit(actor, unit["id"], _payload(**extra))
    record = moves.MoveRecord.objects.get(pk=result["move_record_id"])
    return unit, result, record


# ═══════════════════════════════════════════════════════════════════════════
# NOT STARTED — the pending job
# ═══════════════════════════════════════════════════════════════════════════
def test_cancelling_a_not_started_move_in_cancels_its_job_and_nothing_else(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="U-9", address="9 Oak")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        accounts = customers_models.Account.objects.count()

        preview = move_in_cancel.preview(job.move_no)
        assert preview["kind"] == "not_started" and preview["allowed"] is True

        answer = move_in_cancel.cancel(dana, job.move_no.lower())

        job.refresh_from_db()
        assert job.state == move_in_jobs.STATE_CANCELLED
        assert job.closed_reason == move_in_cancel.CLOSED_BY_CANCEL
        assert job.closed_at is not None
        assert answer["status"] == "cancelled"
        assert customers_models.Account.objects.count() == accounts
        # The request WAS approved; the job is what was called off.
        assert sr.request_row(request.id).state == "approved"
        # A second press is refused by name, and the preview says so first.
        assert move_in_cancel.preview(job.move_no)["allowed"] is False
        with pytest.raises(errors.BizError) as caught:
            move_in_cancel.cancel(dana, job.move_no)
    assert caught.value.message_key == "customers.moveIn.cancel.alreadyCancelled"
    assert [r["action"] for r in audit_rows if r["action"] == "move_in_job.cancelled"] == [
        "move_in_job.cancelled"
    ]


def test_an_unknown_reference_is_a_404(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            move_in_cancel.cancel(dana, "MVI-99-9999")


# ═══════════════════════════════════════════════════════════════════════════
# COMMITTED — J6's reversals, as new rows
# ═══════════════════════════════════════════════════════════════════════════
def test_cancelling_a_committed_move_in_closes_the_account_and_the_unit_reads_vacant(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        unit, result, record = _committed(dana, brazos)
        unit_row = metering_selectors.unit_row(unit["id"])
        assert metering_selectors.occupancy_of(unit_row) == "occupied"
        reads_before = record.reads_committed

        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is True, preview
        assert preview["reverses"]["account"]["closes_on"] == "2026-07-31"

        answer = move_in_cancel.cancel(dana, record.move_no, note="Changed their mind")

        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.status.code == "closed"
        assert account.closed_at == date(2026, 7, 31)  # the DAY BEFORE 1 Aug
        assert account.close_reason == customers_models.CLOSE_REASON_OTHER
        assert move_in_cancel.is_cancelled(account) is True
        open_agreements = customers_models.ServiceAgreement.objects.filter(
            account=account, ended_on__isnull=True
        )
        assert open_agreements.count() == 0
        # BR-MET-036 — derived, nothing wrote the unit.
        assert metering_selectors.occupancy_of(unit_row) == "vacant"
        # The move record is never updated (BR-CUS-152).
        record.refresh_from_db()
        assert record.reads_committed == reads_before and record.kind == "move_in"
        assert answer["unit"] == "vacant" and answer["refund"] is None
    cancelled = [r for r in audit_rows if r["action"] == "account.move_in_cancelled"]
    assert len(cancelled) == 1
    assert cancelled[0]["before"]["status"] != "closed"
    assert cancelled[0]["after"]["note"] == "Changed their mind"


def test_the_next_household_can_move_in_on_the_cancelled_date(brazos, dana):
    """BR-CUS-056 refuses a start ON the previous account's close. Closing the
    cancelled account the day before keeps 1 August free for the next tenant."""
    with tenant_ctx(brazos):
        unit, _result, record = _committed(dana, brazos, label="Unit 4", address="4 Elm")
        move_in_cancel.cancel(dana, record.move_no)
        again = customers_services.move_in_to_unit(dana, unit["id"], _payload())
        account = customers_models.Account.objects.get(pk=again["id"])
        assert account.opened_at == date(2026, 8, 1)


def test_a_second_cancel_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos, label="Unit 5", address="5 Elm")
        move_in_cancel.cancel(dana, record.move_no)
        assert move_in_cancel.preview(record.move_no)["refusal"]["code"] == (
            move_in_cancel.ALREADY_CANCELLED
        )
        with pytest.raises(errors.BizError) as caught:
            move_in_cancel.cancel(dana, record.move_no)
    assert caught.value.message_key == "customers.moveIn.cancel.alreadyCancelled"


def test_cancel_is_refused_once_a_bill_has_issued(brazos, dana, monkeypatch):
    """J6: *"refused once one has"*. Billing's own seam answers the question."""
    from apps.customers import seams

    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos, label="Unit 6", address="6 Elm")
        monkeypatch.setattr(seams, "last_issued_invoice_date", lambda _id: date(2026, 9, 1))
        assert move_in_cancel.preview(record.move_no)["refusal"]["code"] == (
            move_in_cancel.BILL_ISSUED
        )
        with pytest.raises(errors.BizError) as caught:
            move_in_cancel.cancel(dana, record.move_no)
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.closed_at is None
    assert caught.value.message_key == "customers.moveIn.cancel.billIssued"


def test_cancel_is_refused_when_billing_cannot_answer(brazos, dana, monkeypatch):
    """`None` from billing is not *no bill* (DEF-075) — the safe direction."""
    from apps.customers import seams

    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos, label="Unit 7", address="7 Elm")
        monkeypatch.setattr(seams, "billing_can_answer", lambda: False)
        with pytest.raises(errors.BizError) as caught:
            move_in_cancel.cancel(dana, record.move_no)
    assert caught.value.message_key == "customers.moveIn.cancel.billingUnreadable"


def test_a_register_deposit_no_payment_backs_is_refused_and_nothing_written(brazos, dana):
    """`OQ-CUS-12790` CLOSED (a) on 2026-10-05: a held deposit is RELEASED and
    refunded with the rest (`test_cr171_oq_cus_12790_cancel_refund.py` holds
    Nilesh's $175.00). What remains refused is a register that says $150.00
    while payments holds none of it — a release cannot create money — and the
    whole cancel rolls back. This replaced the hold's own expiry test, which
    went red the day the stub was removed (law 2)."""
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos, label="Unit 8", address="8 Elm")
        customers_models.Account.objects.filter(pk=result["id"]).update(
            deposit_on_file=Decimal("150.000000")
        )
        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is True
        assert "OQ-CUS-12790" not in str(preview)
        with pytest.raises(PaymentRuleError):
            move_in_cancel.cancel(dana, record.move_no)
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.closed_at is None
        assert account.deposit_on_file == Decimal("150.000000")


def test_money_taken_as_credit_is_a_refund_request_not_a_payout(brazos, dana):
    """J6 worked: a $25.00 counter payment on an unbilled move-in → a refund
    REQUEST for $25.00 (BR-PAY-014: no money moves until Finance approves)."""
    from apps.payments import models as payments_models
    from apps.payments import services as payments_services
    import uuid

    with tenant_ctx(brazos):
        _unit, result, record = _committed(dana, brazos, label="Unit 9", address="9 Elm")
        payments_services.record_payment(
            dana,
            account_id=result["id"],
            amount=Decimal("25.00"),
            posted_at=datetime(2026, 8, 1, 15, tzinfo=dt_timezone.utc),
            cleared_at=datetime(2026, 8, 1, 15, tzinfo=dt_timezone.utc),
            method_code="check",
            confirmation="1043",
            idempotency_reference=uuid.uuid4(),
        )
        preview = move_in_cancel.preview(record.move_no)
        assert preview["reverses"]["refund"]["amount"] == "25.0000"

        answer = move_in_cancel.cancel(dana, record.move_no)

        refund = payments_models.Refund.objects.get(account_id=result["id"])
        assert refund.amount == Decimal("25.00")
        assert refund.status == payments_models.REFUND_REQUESTED
        assert answer["refund"]["amount"] == "25.0000"
        assert answer["refund"]["status"] == payments_models.REFUND_REQUESTED


def test_open_work_orders_are_cancelled_through_works_own_door(brazos, dana):
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        _high, _normal, reconnect, _reread, crew = _work_catalogue(brazos)
        _unit, result, record = _committed(
            dana,
            brazos,
            label="Unit 10",
            address="10 Elm",
            field_visit={"orders": [{"type_id": str(reconnect.id), "crew_id": str(crew.id)}]},
        )
        order_id = result["work_orders"][0]["id"]
        preview = move_in_cancel.preview(record.move_no)
        assert len(preview["reverses"]["work_orders"]) == 1

        answer = move_in_cancel.cancel(dana, record.move_no)

        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert order.dispatch_state == "cancelled"
        assert answer["work_orders_cancelled"] == [order.order_no]


# ═══════════════════════════════════════════════════════════════════════════
# ⚖️ THE HUMAN SIGN-OFF OF 2026-10-06
# ═══════════════════════════════════════════════════════════════════════════
def _water_and_sewer_unit(actor, tenant, *, label, address):
    """Unit 3B taking water AND sewer — the two services the PO was shown.

    `brazos` sells Electric + Water only; sewer is switched on through the same
    `tenant_services.enabled` column the S8 settings screen writes
    (`test_br_cus_1101_service_subset.py`'s precedent), never past the rule."""
    from apps.metering import services as metering_services
    from apps.tenancy import models as tenancy_models
    from tests.test_us_met_helpers import make_plan, make_premises, make_unit

    tenancy_models.TenantService.objects.filter(
        tenant_id=tenant.id, service__code__in=["water", "sewer"]
    ).update(enabled=True)
    premises = make_premises(actor, address_line=address, services_available=["water", "sewer"])
    unit = make_unit(actor, premises["id"], label=label)
    plan = make_plan(tenant, name=f"Signed {label}", services=("water", "sewer"))
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    for service in ("water", "sewer"):
        metering_services.ensure_service_point(unit["id"], service)
    return unit


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana, monkeypatch):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO 2026-10-06,
    decision log *"SIX MOVE-IN MONEY FILES SIGNED"*, verbatim: *"Money-file
    review: approve these six? - all good - go ahead"*). Statement 4 of six,
    exactly as shown:

    *"Nilesh moved into Unit 3B on 1 August and paid $25.00. Cancelling before
    any bill closes his account as of 31 July and ends water and sewer the same
    day; asks Finance to refund the $25.00 and cancels the visit WO-0062; keeps
    his meter readings and shows the unit as Vacant. Once a bill has gone out,
    Cancel is refused."*

    WO-0062 is the number the example carried; the order number is the
    tenant's sequence, so the test asserts THE visit raised by this move-in is
    the one cancelled. A held deposit on cancel is ruling (B)'s, signed
    2026-10-05 and asserted in `test_cr171_oq_cus_12790_cancel_refund.py`.
    """
    import uuid

    from apps.customers import seams
    from apps.work import connection_models as work_tables
    from apps.payments import models as payments_models
    from apps.payments import services as payments_services

    with tenant_ctx(brazos):
        _high, _normal, reconnect, _reread, crew = _work_catalogue(brazos)
        unit = _water_and_sewer_unit(dana, brazos, label="Unit 3B", address="3 Signed Way")
        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(
                field_visit={"orders": [{"type_id": str(reconnect.id), "crew_id": str(crew.id)}]}
            ),
        )
        record = moves.MoveRecord.objects.get(pk=result["move_record_id"])
        order_id = result["work_orders"][0]["id"]
        unit_row = metering_selectors.unit_row(unit["id"])
        payments_services.record_payment(
            dana,
            account_id=result["id"],
            amount=Decimal("25.00"),
            posted_at=datetime(2026, 8, 1, 15, tzinfo=dt_timezone.utc),
            cleared_at=datetime(2026, 8, 1, 15, tzinfo=dt_timezone.utc),
            method_code="check",
            confirmation="1043",
            idempotency_reference=uuid.uuid4(),
        )
        reads_before = record.reads_committed

        move_in_cancel.cancel(dana, record.move_no)

        account = customers_models.Account.objects.get(pk=result["id"])
        ended = {
            agreement.service_point.service.code: agreement.ended_on
            for agreement in customers_models.ServiceAgreement.objects.filter(
                account=account
            ).select_related("service_point__service")
        }
        refund = payments_models.Refund.objects.get(account_id=result["id"])
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        record.refresh_from_db()
        vacant = metering_selectors.occupancy_of(unit_row)

        # Once a bill has gone out, Cancel is refused — a second household on Unit 3C.
        other = _water_and_sewer_unit(dana, brazos, label="Unit 3C", address="3C Signed Way")
        billed = customers_services.move_in_to_unit(dana, other["id"], _payload())
        billed_record = moves.MoveRecord.objects.get(pk=billed["move_record_id"])
        monkeypatch.setattr(seams, "last_issued_invoice_date", lambda _id: date(2026, 9, 1))
        with pytest.raises(errors.BizError) as refused:
            move_in_cancel.cancel(dana, billed_record.move_no)
        still_open = customers_models.Account.objects.get(pk=billed["id"]).closed_at

    # Moved in on 1 August; closed as of 31 July.
    assert account.opened_at == date(2026, 8, 1)
    assert account.status.code == "closed" and account.closed_at == date(2026, 7, 31)
    # Water and sewer end the same day.
    assert ended == {"water": date(2026, 7, 31), "sewer": date(2026, 7, 31)}
    # Finance is ASKED to refund the $25.00 — a request, no money moved.
    assert refund.amount == Decimal("25.00")
    assert refund.status == payments_models.REFUND_REQUESTED
    # The visit is cancelled.
    assert order.dispatch_state == "cancelled"
    # The readings are kept and the unit shows Vacant.
    assert record.reads_committed == reads_before
    assert vacant == "vacant"
    # Once a bill has gone out, Cancel is refused and nothing closes.
    assert refused.value.message_key == "customers.moveIn.cancel.billIssued"
    assert still_open is None
