# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9779 — the move-in's Discounts to claim offered AUTOMATIC
#          discounts (Municipal account, Paperless, Autopay); a clerk's pick was
#          enrolled at Complete and the nightly sync ended it the next night.
# Rules:   BR-RAT-110 (only a discount the plan carries) · PO 2026-10-03
#          ruling (3) (an Automatic discount is granted and ended by the system)
#          · CR-062 J2 (the sample residential plan carries MUNICIPAL on purpose)
# ───────────────────────────────────────────────────────
"""**A move-in claims only discounts a person applies for.** ⚖️ AMENDED
2026-10-06 (`DEF-RAT-9833`, PO D2 (b)): Autopay and Paperless are claimable
again; the Municipal-account refusal below is unchanged.

Worked, on one plan carrying three discounts: SENIOR (apply and approve, 15%
off), MUNI (automatic, *Government or municipal account*, 20% off) and AUTOPAY
(automatic, *Autopay is on*, 0.50% off). The Billing step's claim list is
SENIOR alone; a move-in that posts MUNI is refused by name and opens no
account; a move-in that posts SENIOR enrols it, *pending* proof. No rate or
percentage moves — the plan panel still lists all three.
"""

from datetime import date

import pytest

from apps.customers import move_in_preferences
from apps.customers import services as customers_services
from apps.rating import discount_services, move_in_fees
from apps.rating import discounts as dm
from apps.rating import models as rating_models
from core import errors
from tests.test_cr094_wh_deposit import _outgoing, _payload, _unit
from tests.test_cr166_discounts_round2 import _discount
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

START = date(2026, 1, 1)


def _plan_with_three(actor, tenant):
    """A vacated unit whose plan carries SENIOR, MUNI and AUTOPAY from 01/01."""
    unit, plan = _unit(actor, tenant)
    rating_models.UnitPlanAssignment.objects.filter(unit_id=unit["id"]).update(
        assigned_from=START
    )
    outgoing = _outgoing(actor, tenant, unit)
    customers_services.move_out(actor, outgoing["id"], {"moved_out_on": "2026-08-14"})
    senior = _discount(actor, "SENIOR", start=START)
    muni = _discount(
        actor, "MUNI", value="20", start=START, mode=dm.ENROLMENT_AUTOMATIC,
        eligibility="government_account",
    )
    autopay = _discount(
        actor, "AUTOPAY", value="0.5", start=START, mode=dm.ENROLMENT_AUTOMATIC,
        eligibility="autopay_on",
    )
    for one in (senior, muni, autopay):
        discount_services.attach_discount_to_plan(actor, plan.id, one.id)
    return unit, plan, outgoing, senior, muni, autopay


def _move_in(actor, outgoing, **extra):
    payload = _payload(deposit={"decision": "required", "take_now": False})
    payload.update(extra)
    return customers_services.move_in(actor, outgoing["id"], payload)


def test_def_cus_9779__a_move_in_claiming_municipal_is_refused_by_name(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing, _senior, muni, _autopay = _plan_with_three(dana, brazos)
        before = customers_services.models.Account.objects.count()
        enrolled_before = dm.DiscountEnrolment.objects.filter(discount=muni).count()
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(marcus, outgoing, discount_claims=[{"discount_id": str(muni.id)}])
        assert customers_services.models.Account.objects.count() == before
        assert dm.DiscountEnrolment.objects.filter(discount=muni).count() == enrolled_before
    assert raised.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC
    assert raised.value.field_errors[0]["field"] == "discount_claims[0].discount_id"


def test_def_cus_9779__the_claim_list_holds_only_discounts_a_person_applies_for(brazos, dana):
    with tenant_ctx(brazos):
        unit, plan, _o, senior, muni, autopay = _plan_with_three(dana, brazos)
        sections = move_in_fees.narrowed_sections(
            plan.id, customer_class="residential", on_date=date(2026, 8, 15)
        )
    plan_codes = sorted(row["ref"]["code"] for row in sections["discounts"])
    claimable = sorted(row["ref"]["code"] for row in sections["claimable_discounts"])
    # The plan panel still shows everything the plan carries, at its own value.
    assert plan_codes == ["AUTOPAY", "MUNI", "SENIOR"]
    # ⚖️ AMENDED 2026-10-06 (`DEF-RAT-9833`) — this read `["SENIOR"]` until the
    # PO's ruling D2 (b), verbatim: *"Offer Autopay and Paperless at move-in as
    # drawn … Clark has to add those discounts"*. AUTOPAY is claimable again
    # (it switches the account's Autopay setting On); MUNI is still never
    # offered — that half of DEF-CUS-9779 stands unchanged.
    assert claimable == ["AUTOPAY", "SENIOR"]


def test_def_cus_9779__a_claimed_discount_still_enrols_pending_proof(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing, senior, _muni, _autopay = _plan_with_three(dana, brazos)
        result = _move_in(marcus, outgoing, discount_claims=[{"discount_id": str(senior.id)}])
        rows = list(
            dm.DiscountEnrolment.objects.filter(account_id=result["id"], discount=senior)
        )
    assert result["billing_extras"]["discounts"] == [
        {"discount_id": str(senior.id), "status": "pending"}
    ]
    assert len(rows) == 1


def test_def_cus_9779__the_automatic_reader_names_only_automatic_versions(brazos, dana):
    with tenant_ctx(brazos):
        _u, _p, _o, senior, muni, autopay = _plan_with_three(dana, brazos)
        found = discount_services.automatic_discount_ids(
            [senior.id, muni.id, autopay.id], date(2026, 8, 15)
        )
    assert found == {str(muni.id), str(autopay.id)}
