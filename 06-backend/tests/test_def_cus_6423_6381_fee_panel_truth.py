"""**The request's Fees tab tells the truth about a waive and about the books**
(`DEF-CUS-6423`, `DEF-CUS-6381`).

`DEF-CUS-6423` — after a waive the panel read *"Application fee $0.00 waived.
BILLERR"*. Two faults in one sentence: the figure printed was `quoted`, which
sums the UNWAIVED lines and so is 0.00 on exactly this branch, and the reason
printed was the Settings CODE the waive form sends. The read now serves what
was waived and the reason's NAME, and the screen prints those.

`DEF-CUS-6381` — `posts_to_ledger` was a literal `False`, untrue since
2026-09-15, when money taken at the counter began posting `DR 1010 · CR 2400`
through payments. It is now derived from that journal entry.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
* A name assertion passes if the name is simply the code echoed back — so the
  code is asserted ABSENT from the name.
* A `posts_to_ledger is True` assertion passes if the flag became a literal
  `True` — so the SAME request is read before and after the money is taken,
  and it must flip.
"""

from decimal import Decimal

import pytest

from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.tenancy import models as tenancy_models
from tests.fee_quote_helpers import quote_fee
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "applicant_phone": "555-0142",
    "address_as_given": "14 Willow Bend, Springfield",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I'm moving into somewhere",
}


def _billerr(tenant):
    """`BILLERR — Billing error correction`, the row Settings seeds and the
    waive form offers. Kept as the utility's own row if provisioning made it."""
    row, _ = tenancy_models.ReasonCode.objects.get_or_create(
        tenant=tenant,
        code="BILLERR",
        defaults={"name": "Billing error correction", "active": True},
    )
    return row


def test_waive_45_with_billerr_serves_45_waived_and_the_reasons_name(brazos, dana):
    with tenant_ctx(brazos):
        name = _billerr(brazos).name
        request = sr.create_request(dana, dict(CAPTURE))
        line = quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        sr.waive_fee_line(dana, line.id, reason="BILLERR")

        fees = reads.fees_tab(sr.request_row(request.id))

    assert fees["quoted"]["display"] == "0.00"  # what the panel USED to print
    assert fees["waived"]["amount"] == "45.0000"
    assert fees["waived"]["display"] == "45.00"
    assert fees["waived"]["currency"] == fees["quoted"]["currency"]
    (served,) = fees["lines"]
    assert served["waived"] is True
    assert served["waive_reason"] == "BILLERR"  # stored, sent back, never printed
    assert served["waive_reason_name"] == name == "Billing error correction"
    assert "BILLERR" not in served["waive_reason_name"]


def test_a_reason_that_is_not_a_code_is_served_as_typed(brazos, dana):
    """An older free-text waive is already words; it is not swapped for a code
    or dropped."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        line = quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.waive_fee_line(dana, line.id, reason="first application at this address")
        (served,) = reads.fees_tab(sr.request_row(request.id))["lines"]
    assert served["waive_reason_name"] == "first application at this address"


def test_posts_to_ledger_is_false_for_a_quote_and_true_once_the_counter_posts(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        before = reads.fees_tab(sr.request_row(request.id))
        sr.collect_fee(
            dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
        )
        after = reads.fees_tab(sr.request_row(request.id))
        receipt = sr.fee_total_to_collect(request.id)["counter_receipt"]

    assert before["posts_to_ledger"] is False
    assert receipt is not None and receipt["collection_entry_id"]
    assert after["posts_to_ledger"] is True
