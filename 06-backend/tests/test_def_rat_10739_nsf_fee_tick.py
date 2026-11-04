"""P7 = A — a utility marks its OWN NSF fee code on Plans & Rates › Charges.

PO ruling 2026-10-31, decision log *"Twelve open payment questions answered
(PO)"*, verbatim *"P7-A"*, put as: Plans & Rates › Charges gets an "NSF fee"
tick marking a utility's NSF charge (any code), backed by the existing
`charges.is_nsf_fee` flag (`DEF-RAT-10739`).

THE WORKED CASE: Brazos Bend calls its returned-cheque fee `RETCHK`, $35.00,
and lists it on the plan. Unticked, cheque 4102 ($76.40) bounces and no fee is
charged (`nsf_fee_not_set_on_plan`). Ticked through the charge-code save, the
same bounce charges `RETCHK` $35.00 and the account owes $111.40.

ONE NSF FEE PER PLAN: `selectors.plan_nsf_charge` refuses two marked codes on
one plan by name at bounce time, so the tick and the plan's Charges list each
refuse to CREATE that state, naming the code already doing the job.

RED FIRST (hard-won law 7): `test_ticking_retchk_*` was green on the service
already (the flag landed backend-first), which is the defect — the SCREEN drew
no tick; the screen half is `ChargeCodeWizard.nsfFee.dom.test.tsx`. The two
refusal cases below failed on the tip: the second tick was saved and the plan
accepted two marked codes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from apps.payments import models, reversal
from apps.rating import models as rating_models
from apps.rating import services as rating_services

from tests.test_def_pay_10698_nsf_fee import (
    CHEQUE_4102,
    _fee_bills,
    _gl,
    _list_on_plan,
    _owed,
    _plan_of,
)
from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill

pytestmark = pytest.mark.django_db

RETCHK_PRICE = D("35.00")
RETURNED_ON = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)


def _code(tenant, code, *, marked=False, amount=RETCHK_PRICE):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{code} returned payment fee",
        charge_type="penalty",
        amount_rule="flat",
        amount=amount,
        gl_account_id=_gl(tenant).id,
        is_nsf_fee=marked,
    )


def _account_with_cheque(brazos, dana, suffix):
    account = a_one_time_account(brazos, dana, account_no=f"A-{suffix}", asset_no=f"M-{suffix}")
    an_issued_bill(
        brazos, account, number=f"BL-{suffix}", total=CHEQUE_4102, issued_on=date(2026, 10, 1)
    )
    recorded = a_payment(dana, account, amount=CHEQUE_4102, confirmation="4102")
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _bounce(actor, payment):
    return reversal.reverse_payment(
        actor,
        payment_id=payment.pk,
        returned_on=RETURNED_ON,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )


def _field_keys(exc):
    return [
        entry.get("message_key")
        for entry in (getattr(exc, "field_errors", None) or exc.params.get("field_errors") or [])
    ]


def test_ticking_retchk_makes_a_bounce_charge_it(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, cheque = _account_with_cheque(brazos, dana, "73901")
        retchk = _code(brazos, "RETCHK")
        _list_on_plan(brazos, _plan_of(account), retchk)

        rating_services.update_charge(dana, retchk.pk, {"is_nsf_fee": True})

        retchk.refresh_from_db()
        assert retchk.is_nsf_fee is True
        result = _bounce(dana, cheque)
        assert result.nsf_fee_status == "charged"
        assert result.nsf_fee_code == "RETCHK"
        assert result.nsf_fee_amount == RETCHK_PRICE
        assert _fee_bills(account).count() == 1
        assert _owed(account) == D("111.40"), "$76.40 + $35.00"


def test_unticked_retchk_charges_nothing(brazos, dana, marcus):
    """The check that stops the case above passing wrongly: a bounce that
    charged any penalty on the plan would pass it without the tick."""
    with tenant_ctx(brazos):
        account, cheque = _account_with_cheque(brazos, dana, "73902")
        _list_on_plan(brazos, _plan_of(account), _code(brazos, "RETCHK"))
        result = _bounce(dana, cheque)
        assert result.nsf_fee_status == "nsf_fee_not_set_on_plan"
        assert _fee_bills(account).count() == 0


def test_a_second_nsf_tick_on_the_same_plan_is_refused_naming_the_first(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, _cheque = _account_with_cheque(brazos, dana, "73903")
        plan = _plan_of(account)
        _list_on_plan(brazos, plan, _code(brazos, "NSF-OLD", marked=True))
        retchk = _code(brazos, "RETCHK")
        _list_on_plan(brazos, plan, retchk)

        with pytest.raises(Exception) as caught:
            rating_services.update_charge(dana, retchk.pk, {"is_nsf_fee": True})
        assert "rating.charges.nsf_fee_taken_on_plan" in str(caught.value.__dict__)
        assert "NSF-OLD" in str(caught.value.__dict__)
        retchk.refresh_from_db()
        assert retchk.is_nsf_fee is False


def test_a_tick_on_a_code_no_plan_shares_is_allowed(brazos, dana, marcus):
    """Per PLAN, not per utility: another plan may charge another code."""
    with tenant_ctx(brazos):
        _code(brazos, "NSF-OLD", marked=True)
        retchk = _code(brazos, "RETCHK")
        rating_services.update_charge(dana, retchk.pk, {"is_nsf_fee": True})
        retchk.refresh_from_db()
        assert retchk.is_nsf_fee is True


def test_a_plan_listing_two_nsf_fees_is_refused(brazos, dana, marcus):
    with tenant_ctx(brazos):
        first = _code(brazos, "NSF-OLD", marked=True)
        second = _code(brazos, "RETCHK", marked=True)
        fe: list = []
        rating_services._validate_plan_charge_rules(
            [{"charge": first.code}, {"charge": second.code}], fe
        )
        assert [e["message_key"] for e in fe] == ["rating.plans.second_nsf_fee"]
        assert fe[0]["params"]["charge_code"] == "NSF-OLD"
