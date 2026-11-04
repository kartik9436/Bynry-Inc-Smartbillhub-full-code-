"""PO reports 2026-09-23 on `New request` (REQ-03) — the server half, lane REQ-FIX.

    DEF-CUS-6408  the billing address is captured in PARTS and reaches the
                  account door as a structured mailing address (line 2 too)
    DEF-CUS-6416  the server PRICES a fee line from the charge code and refuses
                  a caller's figure that disagrees — never trusts it
    OQ-357        closed 2026-09-23 as "both": a DRAFT's fee line is removed,
                  a submitted request's is waived
    DEF-CUS-6418  two stated absences that had stopped being true are retired

Each case was run against the unfixed tip first and watched fail (hard-won law
7); the failures are quoted in the lane report.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import service_request_api as api
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.customers import services as customer_services
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "at_the_counter",
    "applicant_kind": "person",
    "applicant_name": "Rivera, Ana",
    "applicant_email": "ana.rivera@example.com",
    "address_as_given": "212 Balcones Drive",
}


def _charge(tenant, code: str, amount: str) -> rating_models.Charge:
    """A live, flat, one-time charge code — the tenant's own price list. A
    provisioned tenant already carries some codes (`CONN` among them), so this
    SETS the price rather than inserting a second row the unique key refuses."""
    gl = ledger_models.LedgerAccount.objects.filter(tenant=tenant, code="4600").first()
    charge, _ = rating_models.Charge.objects.update_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": f"{code} fee",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": Decimal(amount),
            "gl_account_id": gl.id if gl is not None else None,
            "deleted_at": None,
        },
    )
    return charge


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-6408 · the billing address, in parts
# ═══════════════════════════════════════════════════════════════════════════


def test_the_billing_address_is_captured_in_parts_and_read_back_in_parts(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(
            dana,
            {
                **CAPTURE,
                "billing_address_same": False,
                "billing_line1_as_given": "PO Box 4471",
                "billing_line2_as_given": "Suite 200",
                "billing_city_as_given": "Round Rock",
                "billing_state_as_given": "TX",
                "billing_postal_code_as_given": "78664-1234",
            },
        )
        location = reads.detail(request.id)["location_and_services"]
    assert (
        location["billing_line1_as_given"],
        location["billing_line2_as_given"],
        location["billing_city_as_given"],
        location["billing_state_as_given"],
        location["billing_postal_code_as_given"],
    ) == ("PO Box 4471", "Suite 200", "Round Rock", "TX", "78664-1234")
    # The one-box value is untouched and nothing was composed into it.
    assert location["billing_address_as_given"] is None


def test_none_of_the_billing_parts_is_required(brazos, dana):
    """PO: *"do'nt make it mandatory"* — unticked with nothing typed is lawful."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "billing_address_same": False})
        location = reads.detail(request.id)["location_and_services"]
    assert location["billing_address_same"] is False
    assert location["billing_line1_as_given"] is None


def test_an_older_one_box_billing_address_is_kept_exactly_as_typed(brazos, dana):
    """`DEF-2703` / `BR-NOT-029` (a): the blob is never parsed into the parts."""
    with tenant_ctx(brazos):
        request = sr.create_request(
            dana,
            {
                **CAPTURE,
                "billing_address_same": False,
                "billing_address_as_given": "PO Box 4471, Round Rock TX 78664",
            },
        )
        location = reads.detail(request.id)["location_and_services"]
    assert location["billing_address_as_given"] == "PO Box 4471, Round Rock TX 78664"
    assert location["billing_city_as_given"] is None
    assert location["billing_postal_code_as_given"] is None


def test_the_account_door_keeps_the_unit_line_as_line_2():
    """The mailing address an account is opened with keeps `Suite 200` as its
    own column — it was refused as an unknown field, so a request's unit could
    only be dropped or glued onto line 1."""
    rows = customer_services._validate_addresses(
        [
            {
                "kind": "mailing",
                "line1": "PO Box 4471",
                "line2": "Suite 200",
                "city": "Round Rock",
                "state": "TX",
                "postal_code": "78664-1234",
            }
        ]
    )
    assert rows[0]["line1"] == "PO Box 4471"
    assert rows[0]["line2"] == "Suite 200"
    assert "country" not in customer_services.ADDRESS_FIELDS


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-6416 · the server prices the line
# ═══════════════════════════════════════════════════════════════════════════


def test_a_caller_cannot_quote_a_charge_code_at_a_price_it_does_not_carry(brazos, dana):
    """**The worked case: `CC-REQFEE` at $25.00, posted at $0.01.** Refused by
    name, never silently corrected — and nothing is written."""
    with tenant_ctx(brazos):
        _charge(brazos, "CC-REQFEE", "25.00")
        request = sr.create_request(dana, dict(CAPTURE))
        with pytest.raises(errors.ApiError) as caught:
            sr.add_fee_line(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("0.01"))
        assert caught.value.message_key == "customers.serviceRequest.feePriceMoved"
        assert caught.value.params["offered"] == "0.0100"
        assert caught.value.params["current"] == "25.0000"
        assert customer_models.ServiceRequestFee.objects.filter(request_id=request.id).count() == 0


def test_a_code_the_catalogue_cannot_price_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        with pytest.raises(errors.ApiError) as caught:
            sr.add_fee_line(dana, request.id, charge_code="MADE-UP", unit_amount=Decimal("0.01"))
    assert caught.value.message_key == "customers.serviceRequest.feeCodeNotPriced"


def test_the_price_is_the_catalogues_and_it_is_LOCKED_on_the_line(brazos, dana):
    """Added at $25.00; the utility then raises the code to $30.00. The line
    stays $25.0000 and the request still owes $25.00 — `quoted` sums the LINES
    and nothing reads the catalogue again."""
    with tenant_ctx(brazos):
        charge = _charge(brazos, "CC-REQFEE", "25.00")
        request = sr.create_request(dana, dict(CAPTURE))
        fee = sr.add_fee_line(
            dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00")
        )
        assert (fee.unit_amount, fee.amount) == (Decimal("25.0000"), Decimal("25.0000"))
        assert str(fee.charge_code_id) == str(charge.id)
        charge.amount = Decimal("30.00")
        charge.save(update_fields=["amount"])
        totals = sr.fee_total_to_collect(request.id)
    assert totals["quoted"] == Decimal("25.0000")
    assert totals["outstanding"] == Decimal("25.0000")


# ═══════════════════════════════════════════════════════════════════════════
# OQ-357 closed as "both" — remove while a draft, waive after
# ═══════════════════════════════════════════════════════════════════════════


def test_a_drafts_line_is_removed_and_the_audit_row_names_what_went(
    brazos, dana, audit_rows
):  # noqa: F811
    """**The worked case:** CC-REQFEE $25.00 plus CONN $60.00 added by mistake →
    remove CONN → one line, $25.00 quoted, and an audit row naming the $60.00."""
    with tenant_ctx(brazos):
        _charge(brazos, "CC-REQFEE", "25.00")
        _charge(brazos, "CONN", "60.00")
        request = sr.create_request(dana, dict(CAPTURE))
        sr.add_fee_line(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        mistake = sr.add_fee_line(
            dana, request.id, charge_code="CONN", unit_amount=Decimal("60.00")
        )
        sr.remove_fee_line(dana, mistake.id, request_id=request.id)
        codes = list(
            customer_models.ServiceRequestFee.objects.filter(request_id=request.id).values_list(
                "charge_code", flat=True
            )
        )
        totals = sr.fee_total_to_collect(request.id)
        removed = next(
            (row for row in audit_rows if row["action"] == "service_request.fee_removed"), None
        )
    assert codes == ["CC-REQFEE"]
    assert totals["quoted"] == Decimal("25.0000")
    assert removed is not None
    assert removed["before"]["charge_code"] == "CONN"
    assert removed["before"]["amount"] == "60.0000"


def test_removing_a_line_does_not_make_the_next_number_collide(brazos, dana):
    """Lines 1 and 2; line 1 is removed; the next line is 3. A COUNT would say 2
    — which `ux_sr_fees_request_line` refuses, because line 2 is still there.
    That is why `add_fee_line` numbers from the highest standing line."""
    with tenant_ctx(brazos):
        _charge(brazos, "CC-REQFEE", "25.00")
        _charge(brazos, "CONN", "60.00")
        request = sr.create_request(dana, dict(CAPTURE))
        first = sr.add_fee_line(
            dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00")
        )
        sr.add_fee_line(dana, request.id, charge_code="CONN", unit_amount=Decimal("60.00"))
        sr.remove_fee_line(dana, first.id, request_id=request.id)
        third = sr.add_fee_line(
            dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00")
        )
    assert third.line_no == 3


def test_a_submitted_requests_line_is_not_removed_and_is_waived_instead(brazos, dana):
    with tenant_ctx(brazos):
        _charge(brazos, "CONN", "60.00")
        request = sr.create_request(dana, dict(CAPTURE))
        fee = sr.add_fee_line(dana, request.id, charge_code="CONN", unit_amount=Decimal("60.00"))
        sr.submit(dana, request.id)
        with pytest.raises(errors.ApiError) as caught:
            sr.remove_fee_line(dana, fee.id, request_id=request.id)
        assert caught.value.message_key == "customers.serviceRequest.feeRemoveNotDraft"
        waived = sr.waive_fee_line(dana, fee.id, reason="HARDSHIP")
    assert waived.waived is True


def test_a_waived_line_is_not_removed(brazos, dana):
    with tenant_ctx(brazos):
        _charge(brazos, "CONN", "60.00")
        request = sr.create_request(dana, dict(CAPTURE))
        fee = sr.add_fee_line(dana, request.id, charge_code="CONN", unit_amount=Decimal("60.00"))
        sr.waive_fee_line(dana, fee.id, reason="HARDSHIP")
        with pytest.raises(errors.ApiError) as caught:
            sr.remove_fee_line(dana, fee.id, request_id=request.id)
    assert caught.value.message_key == "customers.serviceRequest.feeRemoveWaived"


def test_a_line_addressed_through_another_requests_url_is_not_found(brazos, dana):
    with tenant_ctx(brazos):
        _charge(brazos, "CONN", "60.00")
        one = sr.create_request(dana, dict(CAPTURE))
        other = sr.create_request(dana, dict(CAPTURE))
        fee = sr.add_fee_line(dana, one.id, charge_code="CONN", unit_amount=Decimal("60.00"))
        # HR-1: a 404, the same answer a row that does not exist gets.
        with pytest.raises(errors.NotFoundError):
            sr.remove_fee_line(dana, fee.id, request_id=other.id)
        assert customer_models.ServiceRequestFee.objects.filter(id=fee.id).exists()


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-6418 · two stated absences that stopped being true
# ═══════════════════════════════════════════════════════════════════════════


def test_the_two_false_absences_are_no_longer_served():
    codes = {row["code"] for row in api.SERVICE_REQUEST_UNAVAILABLE}
    assert "fee_line_cannot_be_removed" not in codes
    assert "acknowledgement_cannot_be_queued" not in codes
