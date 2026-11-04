# ── Trace ──────────────────────────────────────────────
# Rule:    BR-BIL-1048 — a bill charges for the services the ACCOUNT HOLDS.
#          This file is its READ: `customers.selectors.billed_service_codes_for`.
# Rules:   BR-CUS-1101 (the account takes a subset) · BR-CUS-030 (move-out
#          closes the agreements) · BR-CUS-068 (a master holds agreements on
#          other covered units) · hard rule 4 (the rows are closed, never
#          deleted)
# Defect:  DEF-BIL-6823
# ───────────────────────────────────────────────────────
"""**THE READ, AND THE ONE CASE THAT WOULD HAVE BEEN A DISASTER.**

⚠ **`s2` IS WHY THIS READ IS DATED AND NOT A COPY OF `service_codes_for`.**
The obvious implementation asks *is this agreement still open* — which is what
the S17 chips ask, and what `service_codes_for` answers. But `_end_service_agr
eements` stamps the move-out date on every open agreement (`BR-CUS-030`) and
the FINAL bill is prepared **afterwards**, over a period the customer plainly
did hold their services in. An open/closed read would narrow every final bill
to nothing and refuse it on `GATHER_NO_TARIFF`. **Every closing customer's last
bill.** `s2` is the assertion that catches it.

⚠ **`s3` AND `s4` ARE THE THREE-VALUED HALF.** `None` is *nobody can tell*, and
`gather` narrows nothing on it. An account with no overlapping agreement is not
an account that bought nothing — `BR-CUS-1101` refuses an empty list at the
move-in door for exactly that reason — so this read may only ever hand billing
a NON-EMPTY set to subtract from.
"""

from datetime import date

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    api_call,
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

MOVE_IN_DAY = "2026-08-15"
MOVE_OUT_DAY = "2026-08-14"

SIX = ("electric", "water", "gas", "sewer", "trash", "broadband")
THREE = ["electric", "water", "trash"]
NOT_TAKEN = {"gas", "sewer", "broadband"}


def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _sells(tenant, services=SIX):
    tenancy_models.TenantService.objects.filter(
        tenant_id=tenant.id, service__code__in=list(services)
    ).update(enabled=True)


def _unit_offering(actor, tenant, *, label="Unit A", services=SIX):
    _sells(tenant, services)
    premises = make_premises(actor, services_available=list(services))
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant).id)}
    )
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    return unit


def _payload(**overrides):
    payload = {
        "account_type": "residential",
        "opened_at": MOVE_IN_DAY,
        "contact": {
            "full_name": "Thomas Nguyen",
            "email": "thomas.nguyen@example.com",
            "phone": "+1 (281) 555-0144",
        },
        "customer": {
            "display_name": "Thomas Nguyen",
            "kind": "person",
            "identity": {"phone": "+1 (281) 555-0144"},
        },
    }
    payload.update(overrides)
    return payload


def _outgoing(actor, tenant, unit):
    account = customers_services.create_account(
        actor,
        {
            **_payload(
                opened_at="2026-07-01",
                contact={
                    "full_name": "Okafor D.",
                    "email": "okafor@example.com",
                    "phone": "+1 (281) 555-0100",
                },
                customer={
                    "display_name": "Okafor D.",
                    "kind": "person",
                    "identity": {"phone": "+1 (281) 555-0100"},
                },
            ),
            "unit_id": str(unit["id"]),
            "status": "active",
        },
    )
    customers_services.move_out(actor, account["id"], {"moved_out_on": MOVE_OUT_DAY})
    return account


def _read(account_id, start, end):
    account = customers_models.Account.objects.get(pk=account_id)
    return customers_selectors.billed_service_codes_for(
        account, period_start=start, period_end=end
    )


# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_1048_s1__the_read_answers_the_three_the_account_took(
    brazos, marcus
):
    """Six offered, six connected, three taken — and the read says three.

    RED BEFORE THIS LANE: `billed_service_codes_for` did not exist, so billing
    had nothing to ask and charged for all six (`DEF-BIL-6823`).
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos)
        outgoing = _outgoing(marcus, brazos, unit)
        incoming = customers_services.move_in(
            marcus, outgoing["id"], _payload(services=list(THREE))
        )
        held = _read(incoming["id"], date(2026, 9, 1), date(2026, 9, 30))

    assert held is not None
    assert set(held) == set(THREE)
    assert set(held) & NOT_TAKEN == set()


def test_br_bil_1048_s2__a_closed_agreement_still_counts_for_its_own_period(
    brazos, marcus
):
    """⚠ **THE FINAL BILL. THIS IS THE CASE THAT WOULD HAVE COST THE MOST.**

    The account moves out, `BR-CUS-030` stamps `ended_on` on every agreement,
    and the final bill is prepared afterwards for the period the customer WAS
    there. A read that asked *is it open today* would answer nothing here and
    the bill would refuse on `GATHER_NO_TARIFF` — for every closing customer.

    ⚠ **PROVED RED AGAINST THAT NAIVE READ, NOT MERELY AGAINST THE TIP.** At
    the tip the function does not exist, so every case in this file is red with
    an `AttributeError` — which proves nothing about the DATE logic. So the
    open-only form (`if ended is not None: continue`) was installed on purpose
    and this suite run: **`s2` failed on `assert None is not None` and the
    three others passed.** That is the false pass this case exists for, and it
    is the only case that can see it.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit F")
        outgoing = _outgoing(marcus, brazos, unit)
        incoming = customers_services.move_in(
            marcus, outgoing["id"], _payload(services=list(THREE))
        )
        customers_services.move_out(
            marcus, incoming["id"], {"moved_out_on": "2026-09-20"}
        )
        open_rows = customers_models.ServiceAgreement.objects.filter(
            tenant_id=brazos.id, account_id=incoming["id"], ended_on__isnull=True
        ).count()
        held = _read(incoming["id"], date(2026, 9, 1), date(2026, 9, 30))

    # The agreements really are closed — otherwise this case proves nothing.
    assert open_rows == 0
    assert held is not None, "the final bill would have been refused"
    assert set(held) == set(THREE)


def test_br_bil_1048_s3__a_period_after_the_move_out_cannot_tell(brazos, marcus):
    """Nothing overlaps, so the answer is `None` — *nobody can tell*.

    Deliberately NOT an empty tuple. `gather` narrows nothing on `None`, so a
    period outside the tenancy prices as it always did rather than producing a
    zeroed bill nobody asked for.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit G")
        outgoing = _outgoing(marcus, brazos, unit)
        incoming = customers_services.move_in(
            marcus, outgoing["id"], _payload(services=list(THREE))
        )
        customers_services.move_out(
            marcus, incoming["id"], {"moved_out_on": "2026-09-20"}
        )
        held = _read(incoming["id"], date(2026, 11, 1), date(2026, 11, 30))

    assert held is None


def test_br_bil_1048_s4__an_account_with_no_agreements_cannot_tell(brazos, marcus):
    """An account that holds no agreement row at all — an import that never
    wrote them — is `None`, never `()`. Narrowing it to nothing would zero a
    real customer's bill on an ABSENCE, which is worse than the defect."""
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit H")
        account = customers_services.create_account(
            marcus,
            {**_payload(), "unit_id": str(unit["id"]), "status": "active"},
        )
        customers_models.ServiceAgreement.objects.filter(
            tenant_id=brazos.id, account_id=account["id"]
        ).delete()
        held = _read(account["id"], date(2026, 9, 1), date(2026, 9, 30))

    assert held is None
