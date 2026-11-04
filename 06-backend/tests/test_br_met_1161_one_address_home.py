# ── Trace ──────────────────────────────────────────────
# Rule:     BR-MET-1161 (PO ruling 2026-09-04, verbatim in the decision log:
#           *"we are having addresses at one place now - Premises and Units ->
#           then they flow to {Meters, Sub meter, assets} + { accounts} -> …
#           so they will also draw addresses from same place that we we can
#           maintain the integrtiy"*). Same ruling family as `CR-070 §W`.
# Rules:    B2 §2 `addresses.kind` (SUPERSEDED at its second value) ·
#           BR-CWP-027 (a stranger's `location_text` is a report, not a record)
# Impacts:  apps/customers/services.py (ADDRESS_KINDS) · eleven locale files ·
#           10-scripts/gates/g84_one_address_home.py
# ───────────────────────────────────────────────────────
"""ONE HOME FOR AN ADDRESS, and the three cases that can tell it is true.

WHY THIS FILE EXISTS AT ALL, given nothing was broken
------------------------------------------------------
Nothing in this product had TWO addresses for one place on 2026-09-04. The
count is the evidence and it is in the decision log: **0 rows** of
`addresses.kind='service'` against 51 `mailing`, and **no code path anywhere
reads one** — the only four hits for the string are the tuple that permits it,
the validator that checks against that tuple, and a docstring explaining why the
mailing selector will not fall back to it.

So this is a FENCE, not a repair, and it is worth saying plainly: the door was
open onto a room nobody had entered. The first importer, lane or clerk to write
through it would create a second service address for a premises with no rule
saying which of the two is true — and at THAT moment there is no clean fix,
only a choice about whose data to discard.

THE THREE CASES
----------------
    1. the door is CLOSED       — `kind='service'` is refused BY NAME, and the
                                  refusal says where an address actually lives
    2. the door is still OPEN   — `kind='mailing'` is untouched. This is the
       for the fact that differs   case that stops the fence being a wall: where
                                  the BILL goes is a different fact from where
                                  the METER is, for every landlord there is
    3. the one home ANSWERS     — the service address is reachable
                                  `account → unit → premises` and equals the
                                  premises' own line. Without this case the
                                  first two would pass on a product that had
                                  simply lost the ability to say where a
                                  customer lives

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
Case 1 was run against the tree as it stood before the change and FAILED, with
the account created and the second address written:

    AssertionError: assert 'service' not in ['mailing', 'service']

Cases 2 and 3 passed before and after — which is the point of including them.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _unit_on_a_plan(actor, tenant, *, address_line: str, label: str = "A"):
    """A premises, a unit and a published plan — the minimum an account needs.

    The plan is here because `BR-MET-040` refuses an account on an unpriced
    unit; it is not part of what this file is measuring.
    """
    premises = make_premises(actor, address_line=address_line, city="Kirkwood", state="MO")
    unit = make_unit(actor, premises["id"], label=label)
    plan = rating_models.RatePlan.objects.filter(tenant=tenant, status="published").first()
    if plan is not None:
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    return premises, unit


def test_br_met_1161__the_service_kind_door_is_closed_and_says_why(marcus, brazos):
    """CASE 1 — `kind='service'` is refused, and the refusal names the home.

    ⚠ **THE ASSERTION IS ON THE TUPLE AND ON THE REFUSAL, not on a row count.**
    A test that only counted `addresses` rows afterwards would also pass if the
    write silently DROPPED the address — which is the failure mode hard-won law
    1 names: a screen that says *"saved"* over nothing.
    """
    assert "service" not in customers_services.ADDRESS_KINDS, (
        "BR-MET-1161: an address is stored on `premises`. A second, editable "
        "service address hanging off the account is the duplication the PO "
        "ruled out on 2026-09-04."
    )
    assert customers_services.ADDRESS_KINDS == ("mailing",)

    with tenant_ctx(brazos):
        _premises, unit = _unit_on_a_plan(marcus, brazos, address_line="1900 Chestnut Ave")
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(
                marcus,
                {
                    "unit_id": unit["id"],
                    "account_type": "residential",
                    "addresses": [
                        {"kind": "service", "line1": "1900 Chestnut Ave", "city": "Kirkwood"}
                    ],
                },
            )

    failed = caught.value.field_errors[0]
    assert failed["field"] == "addresses[0].kind"
    # A refusal that only says "no" leaves the clerk with the same job: the
    # message must name where the address actually lives.
    assert failed["message_key"] == "customers.address.kind_service_retired"


def test_br_met_1161__the_mailing_address_is_untouched(marcus, brazos):
    """CASE 2 — the fence is not a wall.

    Where the BILL goes is a different fact from where the METER is, for every
    landlord, every managing agent and everyone who has moved. `BR-MET-1161`
    names this as exception 1 and this case is what keeps it honest.
    """
    with tenant_ctx(brazos):
        _premises, unit = _unit_on_a_plan(marcus, brazos, address_line="1902 Chestnut Ave")
        customers_services.create_account(
            marcus,
            {
                "unit_id": unit["id"],
                "account_type": "residential",
                "addresses": [
                    {
                        "kind": "mailing",
                        "line1": "PO Box 44",
                        "city": "Saint Louis",
                        "state": "MO",
                        "postal_code": "63101",
                    }
                ],
            },
        )
        rows = list(
            customers_models.Address.objects.filter(tenant=brazos, line1="PO Box 44").values(
                "kind", "city"
            )
        )

    assert rows == [{"kind": "mailing", "city": "Saint Louis"}]


def test_br_met_1161__the_one_home_still_answers_where_the_meter_is(marcus, brazos):
    """CASE 3 — the walk works, so closing the door lost nothing.

    `account -> unit -> premises` is the chain the PO drew. If this case ever
    goes red, the first two are measuring a product that can no longer say
    where a customer's service is — which would make the fence a regression
    rather than a rule.
    """
    with tenant_ctx(brazos):
        _premises, unit = _unit_on_a_plan(marcus, brazos, address_line="1904 Chestnut Ave")
        created = customers_services.create_account(
            marcus, {"unit_id": unit["id"], "account_type": "residential"}
        )
        walked = (
            customers_models.Account.objects.filter(pk=created["id"])
            .values_list("unit__premises__address_line", "unit__premises__city")
            .first()
        )
        served = customers_selectors.account_detail_dict(
            customers_models.Account.objects.get(pk=created["id"])
        )["premise_locality"]
        # The invariant is AGREEMENT with the home, not a literal: the fixture
        # picks the postcode, and a test that hardcoded one would be asserting
        # the fixture rather than the walk.
        home = (
            metering_models.Premises.objects.filter(address_line="1904 Chestnut Ave")
            .values("city", "state", "postal_code")
            .first()
        )

        # And the unit itself declares no address of its own — the borrow is
        # the only way to get one, which is what makes it single-homed.
        own_address_columns = [
            f.name
            for f in metering_models.Unit._meta.get_fields()
            if f.name in {"address_line", "line1", "city", "state", "postal_code"}
        ]

    assert walked == ("1904 Chestnut Ave", "Kirkwood")
    assert own_address_columns == []
    # `DEF-CUS-3653` — and the account DETAIL serves that locality, so the
    # header's `Austin, TX 78704` line has a source now that `kind='service'`
    # is gone. Without this assertion the screen would render nothing and every
    # test here would still be green (hard-won law 2).
    assert served == home
    assert served["city"] == "Kirkwood"  # and it is really the premises' own row
