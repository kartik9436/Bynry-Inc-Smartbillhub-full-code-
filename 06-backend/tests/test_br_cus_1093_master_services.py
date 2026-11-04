# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-1093 (PO ruling 2026-09-23 — a MASTER account takes its
#           utility services from its PREMISES; verbatim: *"in case of mater
#           account - we will have to take utility servcies from premies, since
#           it belong to premises"*)
# Pin:      **NO COLUMN AND NO BACKFILL.** The service list is a READ of
#           `premises.services_available`, held by reference exactly as
#           BR-CUS-672 requires of an inherited fact — tc2 is that assertion.
# Rules:    BR-CUS-1010 (a master hangs off the ADDRESS; `accounts.unit_id` is
#           NULL) · BR-CUS-672 (an account inherits its unit's services, and
#           "every inherited fact is held by reference, never copied") ·
#           BR-CUS-068 (a master's coverage rides `service_agreements`) ·
#           DEF-762 (`services_available` NULL ≠ `[]`)
# Defects:  DEF-CUS-6295 (a correct absence that never says why)
# Impacts:  apps/metering/selectors.py (premises_services_for) ·
#           apps/customers/seams.py · apps/customers/selectors.py
# ───────────────────────────────────────────────────────
"""BR-CUS-1093 — the owner's account reads the building's services.

**THE GAP WAS AN INTERSECTION, NOT A BUG.** `BR-CUS-1010` leaves a master
account's `unit_id` NULL; `BR-CUS-672` inherits services FROM THE UNIT. Both
signed, both correct, and together they gave a master account **no services at
all** — which is what the Product Owner reported from the Accounts register:
*"it is not taking utility service applicable also not taking plan"*. Every
check in this repository asks whether the code matches a rule, and here it did.

**PROVED RED FIRST (hard-won law 7), AND MEASURED ON POSTGRESQL, NOT ONLY
HERE.** Before `_premises_service_codes` existed, `10-scripts/
br_cus_1093_master_services_readback.py` created the PO's own case on a clone
of the demo utility — a premises carrying `water` with no common area — and
read `AC-2026-00052`'s cell as **`[]`**, which the register draws as *No
services*. After: **`['water']`**. tc1 is that case in the suite.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED OF EACH.** tc1 alone would pass
if the premises list were simply COPIED onto every account, so tc4 asserts an
ordinary account on a unit is untouched by it, and tc3 asserts an agreement
service the building does not list SURVIVES rather than being replaced. tc2
would pass against a backfill, so it counts `service_agreements` before and
after and requires the number not to move. tc1 fails the moment the union in
`service_codes_for` is removed — which is the property that makes it a test of
the walk and not of something else.
"""

from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services

from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.br_cus_1114_fixtures import top_up_homes
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = date(2026, 8, 1)


def _master(actor, premises):
    """The owner's account at this address, through the real door.

    `create_master_account` writes `premises_id` and leaves `unit_id` NULL
    (`BR-CUS-1010`), which is the whole state under test — a fixture that set
    `unit_id` by hand would be testing an account this product cannot create.
    """
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    made = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )
    return customer_models.Account.objects.get(pk=made["id"])


def _existing_master(premises_id):
    """The master the premises door may already have opened for this address.

    `metering.premises_owners` creates the owner's account by resolving
    `create_master_account` through the customers seam, so on some paths the
    account exists before this file asks for one. Re-creating it would hit
    `BR-CUS-1011`'s one-master-per-premises refusal.
    """
    return customer_models.Account.objects.filter(
        premises_id=premises_id, kind=customer_services.ACCOUNT_KIND_MASTER
    ).first()


def _master_for(actor, premises):
    return _existing_master(premises["id"]) or _master(actor, premises)


def _common_area(actor, premises, plan, *, label, service):
    unit = make_unit(
        actor,
        premises["id"],
        label=label,
        unit_type="common_area",
        is_common_area=True,
        services=[service],
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


# ══════════════════════════════════════════════════════════════════════════
# THE PIN
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_1093_tc1__a_master_with_no_common_area_reads_the_buildings_services(
    brazos, dana
):
    """**THE PRODUCT OWNER'S OWN CASE.** A premises that offers water, nothing
    shared, and the owner's account on it. Before the ruling this cell was `[]`
    and the register drew *No services*.

    ⚠ **THE ACCOUNT HOLDS NO SERVICE AGREEMENT, AND THAT IS THE POINT.** There
    is no common area to hold one on. The services come from the building, by
    reference, or they come from nowhere.
    """
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="77 Cedar Row", services_available=["water"]
        )
        master = _master_for(dana, premises)

        assert master.unit_id is None, "BR-CUS-1010 — a master names no unit"
        assert customer_selectors.service_agreements_for(master) == []

        assert customer_selectors.service_codes_for(master) == ["water"]
        assert customer_selectors.service_codes_for_accounts([master]) == {
            str(master.id): ["water"]
        }


def test_br_cus_1093_tc2__held_by_reference_a_new_service_appears_with_no_backfill(
    brazos, dana
):
    """**`BR-CUS-672`'s second half, asserted as arithmetic.** *"Every inherited
    fact is held by reference, never copied."*

    A service is added to the BUILDING and the owner's account reads it on the
    next call, with **no row written to `service_agreements`** — the count is
    taken before and after and must not move. A backfill would pass tc1 and
    fail here, which is the only reason this case exists.

    ⚠ The two services are `water` and `electric` because those are the two the
    shared fixture tenant ENABLES (`BR-MET-003`: availability ⊆ the tenant's
    enabled set, and `_clean_services` refuses anything else by name). A case
    written against `gas` refuses at the premises door and never reaches the
    assertion — which looks exactly like the selector being wrong.
    """
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="79 Cedar Row", services_available=["water"]
        )
        master = _master_for(dana, premises)
        before = customer_models.ServiceAgreement.objects.filter(account=master).count()
        assert customer_selectors.service_codes_for(master) == ["water"]

        metering_services.update_premises(
            dana, premises["id"], {"services_available": ["water", "electric"]}
        )

        # The platform catalogue's order, not the order the clerk typed
        # (IS-2's stable-order law applied to a cell).
        assert customer_selectors.service_codes_for(master) == ["electric", "water"]
        after = customer_models.ServiceAgreement.objects.filter(account=master).count()
        assert after == before == 0, "nothing may be written to make this true"


def test_br_cus_1093_tc3__an_agreement_the_building_does_not_list_is_not_erased(
    brazos, dana
):
    """**A UNION, NEVER A SUBSTITUTION — and this is the service that would
    vanish.**

    A master's coverage rides `service_agreements` (`BR-CUS-1010`), and the two
    facts can genuinely part company: a new service point IS refused unless the
    building offers the service (`metering.services._…service_not_at_premises`),
    **but `services_available` may be EDITED DOWN afterwards with no check
    against the points already standing on it** — `_clean_services` validates
    the list against the tenant's enabled set and against nothing else. So the
    state below is reachable through the product's own front doors, in three
    ordinary clerk actions, and it is the state where a substitution would
    DELETE `electric` from an owner's cell while a real electric common area
    keeps billing them for it.

    ⚠ **THIS IS WHY THE BUILD IS A UNION AND WHY THE CASE IS BUILT RATHER THAN
    ASSERTED IN A DOCSTRING.** A reading of `BR-CUS-1093` that replaced the
    agreements with the column would pass tc1, tc2, tc4, tc5, tc6 and tc7.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Common Area Plan", services=["electric"])
        premises = make_premises(
            dana, address_line="81 Cedar Row", services_available=["electric", "water"]
        )
        _common_area(dana, premises, plan, label="Hallway", service="electric")
        master = _master_for(dana, premises)

        # …and now the clerk takes electric off the BUILDING. The hallway's
        # service point and the master's open agreement on it are untouched.
        metering_services.update_premises(
            dana, premises["id"], {"services_available": ["water"]}
        )

        codes = customer_selectors.service_codes_for(master)
        assert codes == ["electric", "water"], (
            "the agreement's service AND the building's, in catalogue order"
        )
        assert customer_selectors.service_codes_for_accounts([master]) == {
            str(master.id): ["electric", "water"]
        }


def test_br_cus_1093_tc4__an_ordinary_account_does_not_read_the_building(brazos, dana):
    """**THE MIRROR CASE, AND IT IS WHAT STOPS tc1 PASSING FOR THE WRONG
    REASON.**

    `BR-CUS-1093` is a rule about ONE kind of account. A tenant's account takes
    its services from its unit (`BR-CUS-672`) and must not acquire a service
    merely because the building offers it — on a premises listing electric AND
    water where this unit is metered for water alone, the cell stays
    `['water']`.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential", services=["water"])
        premises = make_premises(
            dana, address_line="83 Cedar Row", services_available=["electric", "water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit A", services=["water"])
        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        created = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": OPENED.isoformat(),
                "contact": {"full_name": "Elena Rivera"},
                "customer": identity_fixtures.customer_block(
                    "Elena Rivera", account_type="residential"
                ),
            },
        )
        customer_services.activate_account(dana, created["id"])
        account = customer_models.Account.objects.get(pk=created["id"])

        assert account.kind == "regular"
        assert customer_selectors.service_codes_for(account) == ["water"], (
            "electric is at the address and not on this unit — BR-CUS-672 decides"
        )
        assert customer_selectors.service_codes_for_accounts([account]) == {
            str(account.id): ["water"]
        }


def test_br_cus_1093_tc5__an_address_nobody_asked_about_still_reads_empty(brazos, dana):
    """**`DEF-762`'s third state, and `DEF-CUS-6295`'s case.**

    `services_available` NULL means *nobody was ever asked*; `[]` is a clerk
    answering *this address offers nothing*. Neither can put a chip on the row,
    so BOTH read `[]` here — and the register says the FACT (*no services at
    this address*) rather than the reason, because B14 rule 33 puts rationale at
    zero words on screen. The distinction survives one call up, in
    `metering.selectors.premises_services_for`, which is where a later screen
    would read it.
    """
    with tenant_ctx(brazos):
        never_asked = make_premises(
            dana, address_line="85 Cedar Row", services_available=None
        )
        answered_none = make_premises(
            dana, address_line="87 Cedar Row", services_available=[]
        )
        blank_master = _master_for(dana, never_asked)
        empty_master = _master_for(dana, answered_none)

        assert customer_selectors.service_codes_for(blank_master) == []
        assert customer_selectors.service_codes_for(empty_master) == []

        # …and the two are still TELLABLE APART at the seam.
        served = metering_selectors.premises_services_for(
            [never_asked["id"], answered_none["id"]]
        )
        assert served[str(never_asked["id"])] is None
        assert served[str(answered_none["id"])] == []


def test_br_cus_1093_tc6__the_singular_and_the_plural_cannot_disagree(brazos, dana):
    """One answer, two query plans.

    `service_codes_for` serves `GET /accounts/{id}`; `service_codes_for_accounts`
    serves the register, batched for `NFR-3`. A rule added to one and not the
    other is the shape of `DEF-3483` — two places drawing a service two
    different ways — so this asserts them against each other over a master, an
    ordinary account and a master with nothing recorded, in one call.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Mixed", services=["electric"])
        with_services = make_premises(
            dana, address_line="89 Cedar Row", services_available=["electric", "water"]
        )
        _common_area(dana, with_services, plan, label="Hallway", service="electric")
        master = _master_for(dana, with_services)
        bare = make_premises(dana, address_line="91 Cedar Row", services_available=None)
        bare_master = _master_for(dana, bare)

        accounts = [master, bare_master]
        batched = customer_selectors.service_codes_for_accounts(accounts)
        for account in accounts:
            assert batched[str(account.id)] == customer_selectors.service_codes_for(
                account
            ), f"{account.account_no} disagrees between the singular and the plural"


def test_br_cus_1093_tc7__a_page_with_no_master_asks_metering_nothing_extra(
    brazos, dana, django_assert_num_queries
):
    """**`DEF-2723`'s statement count does not move for the ordinary case.**

    The accounts register is an `NFR-3` list a utility opens all day, and a
    per-page premises read that fired whether or not a master was on the page
    would be a query bought for nobody. `_premises_services_for_masters` asks
    for the ids it needs and makes **no query at all** when there are none.
    """
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="93 Cedar Row", services_available=["water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit A", services=["water"])
        created = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": OPENED.isoformat(),
                "contact": {"full_name": "Sam Okafor"},
                "customer": identity_fixtures.customer_block(
                    "Sam Okafor", account_type="residential"
                ),
            },
        )
        account = customer_models.Account.objects.get(pk=created["id"])

        # ⚠ **ZERO, NOT "ONE MORE".** A read that fired and returned nothing
        # would pass an equality check on the RESULT and still cost a round trip
        # per page — the difference `DEF-2723` measured at 562 ms.
        with django_assert_num_queries(0):
            assert customer_selectors._premises_services_for_masters([account]) == {}

        # And the master path DOES ask, exactly once, so the zero above is the
        # absence of a question rather than a read that cannot fire at all
        # (hard-won law 7: a check incapable of failing is not a check).
        master = _master_for(dana, premises)
        with django_assert_num_queries(1):
            asked = customer_selectors._premises_services_for_masters([master])
        assert asked == {str(premises["id"]): ["water"]}
