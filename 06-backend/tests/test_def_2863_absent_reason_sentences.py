# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2863 — the issued bill's services band read
#          `sewer   not read this period (tariff_prices_no_consumption)`.
#          Reported by the PO from bill BL-2608-000048.
# Rules:   B14 rule 32 (no internal code in the copy a human reads) ·
#          BR-BIL-015 (a missing read is a human decision, and the bill says so)
#          · BR-RAT-015 (sewer is a share of WATER usage-charge dollars, so it
#          has no register of its own and *not read* is the wrong sentence)
# Tests:   this file
# Impacts: apps/billing/documents.py
# ───────────────────────────────────────────────────────
"""Every reason a service was not measured reads as a sentence, not a token.

TWO FAULTS IN ONE STRING, and the second is the one worth naming.

The visible fault is `(tariff_prices_no_consumption)` — an internal constant on
a customer's bill. The quieter fault is the sentence around it: *not read this
period* tells a customer something went wrong, and for a sewer service billed
as a percentage of water (BR-RAT-015) nothing did. There is no sewer register.
It was never going to be read.

So this file does not test one translation. It walks EVERY value the reason can
hold — billing's own seven and the five metering forwards through it — and
asserts each has a sentence of its own, and that an unrecognised value prints
the neutral sentence WITHOUT its token and records a named absence, so the gap
is reportable rather than printed at the customer.
"""

import pytest

from apps.billing import documents
from apps.billing.stages import measure_consumption
from apps.metering import selectors as metering_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill, a_stage6_payload, pdf_text

pytestmark = pytest.mark.django_db

#: Every value that can reach `documents._services`. Collected from the two
#: modules that MINT them rather than typed out, so a new reason on either side
#: fails this file instead of reaching a bill as a raw token.
EVERY_REASON = sorted(
    {
        value
        for module in (measure_consumption, metering_selectors)
        for name, value in vars(module).items()
        if (name.startswith("ABSENT_") or name.startswith("READ_ABSENT_"))
        and isinstance(value, str)
    }
)


def a_payload_with_reason(reason):
    payload = a_stage6_payload()
    payload["services"] = [
        {
            "code": "sewer",
            "name": "Sewer",
            "measured": False,
            "estimated": False,
            "absent_reason": reason,
        }
    ]
    return payload


def test_def_2863__the_constant_set_is_not_empty():
    """Hard-won law 7 — a walk over an empty set passes and proves nothing."""
    assert len(EVERY_REASON) >= 10, EVERY_REASON
    assert "tariff_prices_no_consumption" in EVERY_REASON
    assert "no_meter" in EVERY_REASON


@pytest.mark.parametrize("reason", EVERY_REASON)
def test_def_2863__no_reason_ever_prints_as_its_own_token(brazos, dana, reason):
    """The defect, over the whole constant set rather than the one value seen."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_reason(reason))

        document = documents.render_invoice(bill)

        state = next(field.value for field in document.services)
        assert reason not in state, state
        assert "_" not in state, state
        assert state == state.lower() or state[0].isupper(), state
        assert reason not in pdf_text(document.pdf)
        assert reason not in document.body


def test_def_2863__sewer_does_not_claim_a_meter_nobody_was_ever_going_to_read(brazos, dana):
    """BR-RAT-015 — the sentence, not just the token.

    Sewer bills as a share of the WATER usage charge. There is no sewer
    register, so *not read this period* is not merely clumsy, it is untrue: it
    invites a customer to ask when somebody will come and read it.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(
            brazos,
            dana,
            bill_payload=a_payload_with_reason(measure_consumption.ABSENT_NOT_USAGE_MEASURED),
        )

        document = documents.render_invoice(bill)

        state = next(field.value for field in document.services)
        assert "not read" not in state, state
        assert "another service" in state, state


def test_def_2863__a_reason_nobody_recognises_says_less_rather_than_saying_the_code(brazos, dana):
    """The refusal half. An unknown token is REPORTED, never printed."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_reason("a_future_reason"))

        document = documents.render_invoice(bill)

        state = next(field.value for field in document.services)
        assert state == "not read this period", state
        assert "a_future_reason" not in pdf_text(document.pdf)
        absences = {absent.field: absent for absent in document.absent}
        assert "service_absent_reason" in absences
        assert "a_future_reason" in absences["service_absent_reason"].detail


def test_def_2863__a_missing_reason_is_also_a_sentence_and_also_reported(brazos, dana):
    """`absent_reason: null` printed *no reason recorded* — copy for us, not them."""
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana, bill_payload=a_payload_with_reason(None))

        document = documents.render_invoice(bill)

        state = next(field.value for field in document.services)
        assert state == "not read this period", state
        assert "no reason recorded" not in pdf_text(document.pdf)
        assert "service_absent_reason" in {absent.field for absent in document.absent}


def test_def_2863__a_measured_service_still_says_read(brazos, dana):
    """The negative half — the two measured states are untouched."""
    with tenant_ctx(brazos):
        payload = a_stage6_payload()
        payload["services"] = [
            {
                "code": "electric",
                "name": "Electric",
                "measured": True,
                "estimated": True,
                "absent_reason": None,
            }
        ]
        bill = an_issued_bill(brazos, dana, bill_payload=payload)

        document = documents.render_invoice(bill)

        assert next(field.value for field in document.services) == "estimated read"
        assert not any(absent.field == "service_absent_reason" for absent in document.absent)
