# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-1101 — AN ACCOUNT TAKES A SUBSET OF ITS UNIT'S SERVICE
#           POINTS (PO ruling 2026-09-25, their own scenario: a premises
#           offers six services, the unit has six service points, five carry a
#           meter or an asset, AND THE ACCOUNT TAKES ONLY THREE).
#           Screens: S19 (move-in wizard, the Services step) · S17/S21 (the
#           account's service chips, which read the agreements)
# Rules:    BR-CUS-1101 (this file) · BR-CUS-015 (one chip per ACTIVE
#           agreement) · BR-CUS-029 (every inherited fact is held by reference)
#           · BR-CUS-030 / US-CUS-005 §5 (move-out closes the agreements) ·
#           hard rule 4 (the rows are closed, never deleted)
# Story:    US-CUS-004 §5 TC-7 / TC-8 / TC-9
# ───────────────────────────────────────────────────────
"""T1 · T2 · T7 — the account takes three of six, and only three exist.

⚠ **T1 ASSERTS BOTH SIDES ON PURPOSE.** A test that asserts three agreements
exist and stops is the false pass this rule is most likely to ship under: the
loop it replaces created one row per point unconditionally, so *at least three*
was true before the change and is true after it. What can only be true
afterwards is that **the other three were not created**, and both halves are
asserted here against the same run.

⚠ **AND THE DEFAULT IS ASSERTED TOO.** Every existing caller of
`_open_service_agreements` passes nothing and must still take every point; a
subset that quietly became the default would break S18, the S68 import and
`activate_account` at once, and no test of the new behaviour would see it.
"""

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
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
LATER_MOVE_OUT = "2026-09-30"

#: The PO's own scenario: SIX services offered at the premises and connected at
#: the unit. `fire` is position 11 of the eleven and is deliberately in the list
#: so the six are not all "the usual four plus two".
SIX = ("electric", "water", "gas", "sewer", "trash", "broadband")
#: The three the account takes. The other three must not exist afterwards.
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
    """Switch the six ON for this tenant.

    The `brazos` fixture provisions **Electric + Water** only, and
    `metering.ensure_service_point` refuses a service the tenant does not SELL
    (`BR-MET-003`) before it ever reaches the premises check — so the PO's
    six-service scenario cannot be built on the fixture as it stands. This
    flips `tenant_services.enabled`, which is the same column the S8 settings
    screen writes, rather than reaching past the rule.
    """
    tenancy_models.TenantService.objects.filter(
        tenant_id=tenant.id, service__code__in=list(services)
    ).update(enabled=True)


def _unit_offering(actor, tenant, *, label="Unit A", services=SIX):
    """A unit with a plan and one service point per named service.

    `services_available` is the PREMISES' own offer (`BR-MET-119`): a service
    point may only be put on a unit whose address offers that service, so the
    six are declared on the building before they are connected at the unit —
    which is the PO's scenario stated exactly (*a premises offers six*).
    """
    _sells(tenant, services)
    premises = make_premises(actor, services_available=list(services))
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
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
    """A tenancy to follow — opened on every point, then closed, so the unit is
    free and the incoming move-in has a predecessor to be named after."""
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


def _agreement_services(account_id):
    """{service code} for every agreement the account holds, open or closed."""
    account = customers_models.Account.objects.get(pk=account_id)
    by_point = customers_selectors._service_by_point_for(account)
    return {
        by_point.get(str(row.service_point_id))
        for row in customers_models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account
        )
    }


# ══════════════════════════════════════════════════════════════════════════
# T1 — three of six, and the other three ARE NOT CREATED
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1101_t1__the_account_takes_three_of_six(brazos, marcus):
    """The PO's scenario, walked: six offered, six connected, three taken.

    RED before this lane: `_open_service_agreements` looped every point on the
    unit unconditionally, so the account got SIX rows and `taken` below read
    all six — `services` was not even an accepted field and the move-in was
    refused as an unknown key before it got that far.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos)
        outgoing = _outgoing(marcus, brazos, unit)

        incoming = customers_services.move_in(
            marcus, outgoing["id"], _payload(services=list(THREE))
        )

        taken = _agreement_services(incoming["id"])
        rows = customers_models.ServiceAgreement.objects.filter(
            tenant_id=brazos.id, account_id=incoming["id"]
        )

    # ── the side a naive test asserts ──────────────────────────────────────
    assert taken == set(THREE)
    assert rows.count() == 3
    # ── the side that can ONLY be true after this rule (the false pass) ────
    # Three services the unit really has, really connected, and this account
    # holds NO row for any of them — not an open one and not a closed one.
    assert taken & NOT_TAKEN == set()
    # And the chips a clerk sees say the same thing (BR-CUS-015).
    with tenant_ctx(brazos):
        detail = customers_selectors.account_detail_dict(
            customers_models.Account.objects.get(pk=incoming["id"])
        )
    assert sorted(detail["services"]) == sorted(THREE)
    assert len(detail["service_agreements"]) == 3


def test_br_cus_1101_t1__saying_nothing_still_takes_everything(brazos, marcus):
    """The default, asserted in the same file as the subset.

    Every caller that is not the move-in wizard passes nothing, and a subset
    that became the default would silently halve S18 and the S68 import.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit B")
        outgoing = _outgoing(marcus, brazos, unit)
        incoming = customers_services.move_in(marcus, outgoing["id"], _payload())
        taken = _agreement_services(incoming["id"])
    assert taken == set(SIX)


# ══════════════════════════════════════════════════════════════════════════
# T2 — a service the unit has no point for is REFUSED, BY NAME
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1101_t2__a_service_not_at_the_unit_is_refused(brazos, marcus):
    """A clerk cannot buy a connection that does not exist.

    `solar` is a real service in the eleven and is NOT connected at this unit,
    which is the case that matters: refusing an invented word proves nothing,
    because the danger is a real service the clerk believes is there.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit C")
        outgoing = _outgoing(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_in(
                marcus, outgoing["id"], _payload(services=["electric", "solar"])
            )
        # BR-SHL-019 — the refusal is the whole act: no account was opened.
        opened_after = customers_models.Account.objects.filter(
            tenant_id=brazos.id, unit_id=unit["id"], closed_at__isnull=True
        ).count()

    error = excinfo.value.field_errors[0]
    assert error["field"] == "services"
    assert error["code"] == errors.VAL_UNKNOWN_LOOKUP
    assert error["message_key"] == "customers.move_in.service_not_at_unit"
    # NAMED, and the unit's own offer beside it.
    assert error["params"]["services"] == ["solar"]
    assert set(error["params"]["allowed"]) == set(SIX)
    assert opened_after == 0


def test_br_cus_1101_t2__an_empty_list_is_refused(brazos, marcus):
    """`[]` is a screen that lost the clerk's ticks, not *take nothing*."""
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit D")
        outgoing = _outgoing(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_in(marcus, outgoing["id"], _payload(services=[]))
    error = excinfo.value.field_errors[0]
    assert error["field"] == "services"
    assert error["message_key"] == "customers.move_in.services_required"


# ══════════════════════════════════════════════════════════════════════════
# T7 — move-out closes ONLY the agreements the account holds
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1101_t7__move_out_closes_only_what_the_account_holds(brazos, marcus):
    """`_end_service_agreements` filters on `account=account`, so this was
    already correct — and *already correct* is a claim, so it is asserted.

    The case that can tell a correct implementation from a wrong one needs a
    SECOND account holding agreements at the same moment. A neighbouring unit
    in the same tenant, still occupied, is that account: a move-out that closed
    by tenant or by service point rather than by account would close its rows
    too, and every count below would still look plausible on its own.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit E")
        neighbour_unit = _unit_offering(marcus, brazos, label="Unit F")
        neighbour = customers_services.create_account(
            marcus,
            {
                **_payload(
                    opened_at="2026-07-01",
                    contact={
                        "full_name": "Nadeau R.",
                        "email": "nadeau@example.com",
                        "phone": "+1 (281) 555-0177",
                    },
                    customer={
                        "display_name": "Nadeau R.",
                        "kind": "person",
                        "identity": {"phone": "+1 (281) 555-0177"},
                    },
                ),
                "unit_id": str(neighbour_unit["id"]),
                "status": "active",
            },
        )
        outgoing = _outgoing(marcus, brazos, unit)
        incoming = customers_services.move_in(
            marcus, outgoing["id"], _payload(services=list(THREE))
        )

        customers_services.move_out(marcus, incoming["id"], {"moved_out_on": LATER_MOVE_OUT})

        mine = list(
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=brazos.id, account_id=incoming["id"]
            )
        )
        theirs = list(
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=brazos.id, account_id=neighbour["id"]
            )
        )

    # THREE rows, all closed on the move-out day — hard rule 4: closed, never
    # deleted, and `started_on` untouched.
    assert len(mine) == 3
    assert {row.ended_on.isoformat() for row in mine} == {LATER_MOVE_OUT}
    # The other three were never created, so there was nothing there to close.
    assert len(mine) == 3
    # ⛔ The neighbour's SIX are untouched — the half that fails if the close
    # ever stops being scoped to the account.
    assert len(theirs) == 6
    assert all(row.ended_on is None for row in theirs)


# ══════════════════════════════════════════════════════════════════════════
# A1 — the FIELD on the REAL ENDPOINT, not only on the service function
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1101_a1__the_move_in_endpoint_takes_the_field(brazos, marcus):
    """`POST /accounts/{id}/move-in` carries `services` through the wire.

    ⚠ **THE SERVICE-LEVEL CASES ABOVE CANNOT SEE A VOCABULARY MISTAKE.** They
    call `customers_services.move_in` directly, so a `services` missing from
    `MOVE_IN_FIELDS` would refuse only at the door — every one of them would
    still pass and the field would be unreachable from any browser. This is the
    door.
    """
    with tenant_ctx(brazos):
        unit = _unit_offering(marcus, brazos, label="Unit G")
        outgoing = _outgoing(marcus, brazos, unit)
        # ⚠ **A REAL USER, NOT `FakeUser()`.** `moves.record_move` writes
        # `performed_by` as a FK, so a fabricated id leaves a row the suite's
        # own constraint check refuses at teardown — which is the pre-existing
        # red in `test_us_cus_004_005_move_in_out.py` and has nothing to do
        # with this rule. Using the clerk the rest of this file acts as keeps
        # the failure this case CAN see about the vocabulary.
        response = api_call(
            customers_api.account_move_in,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data=_payload(services=list(THREE)),
            account_id=str(outgoing["id"]),
        )
        assert response.status_code == 201, getattr(response, "data", response)
    # ⚠ **RE-ENTERED.** `api_call` opens and CLOSES its own tenant context (it
    # is standing in for the middleware), so the read below has none to work in
    # and metering refuses `BR-TEN-003` — which reads like a tenancy bug and is
    # the harness, not the code.
    with tenant_ctx(brazos):
        taken = _agreement_services(response.data["id"])
    assert taken == set(THREE)
    assert taken & NOT_TAKEN == set()
