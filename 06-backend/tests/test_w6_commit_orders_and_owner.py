# ── Trace ──────────────────────────────────────────────
# Defects: DEF-MET-5428 (step 6's work orders are collected and DISCARDED —
#          `commit_connection` never read `work_orders` off the payload) ·
#          DEF-MET-5093 (the wizard's owner block reaches the account door
#          under five keys it reads none of, so the owner's NAME never
#          arrived either, not only the identifier)
# Rules:   BR-MET-112 (nothing is written until step 9; ONE transaction) ·
#          BR-WRK-006 (an order stands on an anchor) · BR-WRK-008 (copy,
#          never link — the order takes its own copies and the VERSION says
#          which copy) · BR-MET-116 (the owner's build account is a MASTER
#          account) · BR-CUS-1024 (no identifier, no account) ·
#          BR-CUS-1022 (which identifier counts follows the KIND)
# Screens: S87 step 6 (Plans & work orders) · step 8 (review) · step 9
# ───────────────────────────────────────────────────────
"""**The commit is tested on what it WROTE, never on what the payload said.**

Both defects this file exists for survived a full suite because every test
that touched them asserted a FLAG or a PAYLOAD:

    NewConnectWizard.test.tsx:304   asserts `create_owner_account` is true
    NewConnectWizard.test.tsx       asserts the payload carries `work_orders`

Both assertions are TRUE and both were true on the day each defect shipped.
The payload is the browser's half of a contract; nothing here asserted the
server's half, so a clerk could be promised nine work orders, press
**Create connection ✓**, and get a build with zero and no refusal at all.

So every case below commits a connection for real and then asks the DATABASE
what exists — `WorkOrder.objects.filter(connection=…)`, and
`connections.owner_account_id`. That is the only question that could have
caught either one.
"""

import pytest

from apps.customers import models as customers_models
from apps.metering import services as metering_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.br_cus_1114_fixtures import top_up_homes
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _published_template(actor, name: str, service: str = "electric"):
    """A template a clerk could actually pick at step 6.

    ⚠ **PUBLISHED, and that is not decoration.** `BR-WRK-011` — *"0 is a draft
    and it is not a version"* — so `create_work_order` refuses a draft before
    it writes the order row. A fixture that skipped the publish would be
    testing the refusal path while claiming to test the raise.
    """
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return work_tables.WorkOrderTemplate.objects.get(pk=header["id"])


# ════════════════════════════════════════════════════════════════════════════
# DEF-MET-5428 — step 6's proposal reaches the database
# ════════════════════════════════════════════════════════════════════════════
def test_the_commit_raises_the_work_orders_the_payload_names(dana, brazos):
    """**Two named at step 6, two in the database, two in the manifest.**

    The register row names exactly this check: *"commit a connection carrying
    two `work_orders` and assert `WorkOrder.objects.filter(connection=…)
    .count() == 2`"*. It is an INTEGRATION assertion on purpose — the payload
    was already correct and a unit test of either side passes on the defect.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        tap = _published_template(dana, "Water tap", service="water")
        meter_set = _published_template(dana, "Meter set", service="electric")
        created = w6.create_connection(dana, {"premises_id": premises["id"]})

        result = w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}],
                "work_orders": [
                    {"template_id": str(tap.id), "template_version": tap.version},
                    {"template_id": str(meter_set.id), "template_version": meter_set.version},
                ],
            },
        )

        orders = list(
            work_tables.WorkOrder.objects.filter(connection_id=created["id"]).order_by("order_no")
        )
        assert len(orders) == 2, "step 6's proposal was collected and discarded"
        # THE ANCHOR — `BR-WRK-006`. A build's orders stand on the CONNECTION,
        # which is the anchor `create_work_order` has taken positionally since
        # before metering/0044 widened the contract to four.
        assert {str(order.connection_id) for order in orders} == {str(created["id"])}
        # `BR-WRK-008` — the order remembers WHICH version it copied.
        assert all(order.template_version >= 1 for order in orders)
        assert {order.template_id for order in orders} == {tap.id, meter_set.id}
        # AND THE SCREEN CAN READ ITS OWN PROMISE BACK OFF THE SERVER. A figure
        # the server never returns cannot be wrong on screen and cannot be
        # right either — which is how the review step promised nine.
        assert result["manifest"]["work_orders"] == 2


def test_a_commit_naming_no_work_orders_raises_none(dana, brazos):
    """**Zero is a real answer and it is REPORTED, not left absent.**

    A clerk may remove every proposal at step 6. The manifest then says `0`,
    which is *"we made none"* — the honest reading, and distinct from the
    `None` that `sub_meter_links` and `premises` carry for *"this count cannot
    be answered here"*.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        result = w6.commit_connection(dana, created["id"], {"units": [{"label": "Unit 1"}]})
        assert work_tables.WorkOrder.objects.filter(connection_id=created["id"]).count() == 0
        assert result["manifest"]["work_orders"] == 0


def test_an_unpublished_template_takes_the_whole_build_down(dana, brazos):
    """**BR-MET-112 — BOTH OR NEITHER, proved on the half that can refuse.**

    The orders are raised INSIDE the commit's one transaction, so a template
    that cannot be copied refuses the build rather than leaving a premises
    with 26 units and a promise nobody kept. The alternative — catching the
    refusal and carrying on — is the shape CLAUDE.md law 14 exists for: on
    PostgreSQL the transaction is already poisoned and the units are lost at
    COMMIT anyway, silently, while this suite's sqlite would pass it green.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        draft = w6.create_work_order_template(
            dana, {"name": "Not published yet", "service": "electric", "sequence": 0}
        )
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        before = w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count()

        with pytest.raises(errors.BizError) as refused:
            w6.commit_connection(
                dana,
                created["id"],
                {
                    "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                    "work_orders": [{"template_id": draft["id"], "template_version": 0}],
                },
            )
        assert "template_not_published" in str(refused.value)
        # NOT ONE unit survived the refusal.
        assert w6.metering_models.Unit.objects.filter(premises_id=premises["id"]).count() == before
        assert work_tables.WorkOrder.objects.filter(connection_id=created["id"]).count() == 0


def test_a_republished_template_is_raised_from_the_version_it_copies(dana, brazos):
    """**The stamp describes the COPY, and the payload's number cannot make it
    lie** — `BR-WRK-008`.

    A template republished between step 6's proposal and step 9's press is
    ordinary: two clerks, one afternoon. The copies come from the template's
    rows AT THE RAISE, so stamping the browser's older number would produce an
    order whose version says v1 over a checklist copied from v2 — the rule
    broken by a VALUE instead of by a join, which is the exact failure
    `create_work_order` already refuses a DRAFT to avoid.

    So the order is raised from the published version that was actually
    copied, and the divergence is REPORTED on the commit rather than swallowed.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        template = _published_template(dana, "Backflow test")
        stale_version = template.version
        w6.publish_work_order_template(dana, template.id)
        template.refresh_from_db()
        assert template.version == stale_version + 1

        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        result = w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}],
                "work_orders": [
                    {"template_id": str(template.id), "template_version": stale_version}
                ],
            },
        )
        order = work_tables.WorkOrder.objects.get(connection_id=created["id"])
        assert order.template_version == template.version
        moved = [row for row in result["unavailable"] if row["field"] == "work_orders"]
        assert len(moved) == 1
        assert moved[0]["code"] == "template_republished_since_proposal"


# ════════════════════════════════════════════════════════════════════════════
# DEF-MET-5093 — the owner reaches the account door
# ════════════════════════════════════════════════════════════════════════════
def _premises_with_a_priced_common_area(actor, tenant):
    """A building whose common area is already built and already priced.

    ⚠ **THE COMMON AREA IS MADE HERE RATHER THAN IN THE COMMIT'S OWN `units`,
    AND THE REASON IS A DIFFERENT DEFECT** (`DEF-MET-5437`, filed by this
    lane): the wizard keys `plan_assignments` and `meters` by `unit_label` and
    the commit reads `unit_id`, so a build cannot price a unit it created in
    the same call. `BR-MET-116`'s master path needs a PRICED common area
    (`BR-MET-040`), so pricing it up front is what keeps these cases about the
    OWNER rather than about that.
    """
    service = tenancy_models.Service.objects.get(code="electric")
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name="Small Commercial",
        defaults={"code": "small-commercial", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name="Small Commercial — electric", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    premises = make_premises(actor, address_line="1408 Elm Street")
    common = make_unit(
        actor,
        premises["id"],
        label="Common area",
        unit_type="common_area",
        is_common_area=True,
    )
    metering_services.assign_unit_plan(actor, common["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(common["id"], "electric")
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    return premises, common


def test_the_owners_name_and_identifier_reach_the_account(dana, brazos):
    """**`connections.owner_account_id` is not null — the register row's own
    durable check, and a test on the FLAG cannot make it.**

    The wizard sends `{name, kind, sub_category, email, phone}` and the door
    reads `contact` and `customer`. Before this mapping existed the call was
    refused on its own payload with `identity_kind_required`, so the owner's
    NAME never arrived either.
    """
    with tenant_ctx(brazos):
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})

        result = w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [],
                "create_owner_account": True,
                "owner": {
                    # The five keys the wizard has always sent…
                    "name": "Brazos Bend Developments LLC",
                    "kind": "builder_developer",
                    "sub_category": "permanent",
                    "email": "office@brazosbend.example",
                    "phone": "555-0147",
                    # …and the two the account door cannot open without.
                    "party_kind": "company",
                    "identity": {"tax_id": "99-0001234"},
                },
            },
        )

        connection = work_tables.Connection.objects.get(pk=created["id"])
        assert connection.owner_account_id is not None
        assert result["manifest"]["customers"] == 1

        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        # THE NAME ARRIVED. This is the half the register row says was lost
        # along with the identifier, and it is the half a clerk would notice.
        contact = customers_models.Contact.objects.get(account=account)
        assert contact.full_name == "Brazos Bend Developments LLC"
        assert contact.email == "office@brazosbend.example"
        assert account.kind == "master"


def test_a_person_owner_is_identified_by_the_phone_the_wizard_already_asks_for(dana, brazos):
    """**`BR-CUS-1023` — for a PERSON a phone is enough to mint a number**, and
    step 1 has collected one all along.

    It is not enough to REUSE somebody else's (`BR-CUS-1024`'s matching test
    is name plus a government identifier), and that asymmetry is deliberate.
    Here it means a landlord with a phone opens an account and a COMPANY with
    the same phone does not — the Tax ID is its only creating identifier.
    """
    with tenant_ctx(brazos):
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [],
                "create_owner_account": True,
                "owner": {
                    "name": "Marisol Ibarra",
                    "kind": "landlord",
                    "sub_category": "permanent",
                    "email": "",
                    "phone": "555-0182",
                    "party_kind": "person",
                },
            },
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])
        assert connection.owner_account_id is not None


def test_the_owner_classification_is_never_read_as_the_party_kind(dana, brazos):
    """**`builder_developer` is not `company`, and guessing which it is would
    write a value into a customer's row** (`DEF-MET-5438`).

    `DEF-MET-5093`'s prescription said *"`kind` → `customer.kind`"*. All FOUR
    of the wizard's classifications — builder or developer, property owner,
    landlord, occupier — are refused by `_validate_customer_kind`, which knows
    only `person` and `company`. So the classification is mapped NOWHERE and
    the party kind is asked for by name; a build that omits it is refused with
    the field that is missing, which is the refusal a clerk can act on.
    """
    with tenant_ctx(brazos):
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        with pytest.raises(errors.BizError) as refused:
            w6.commit_connection(
                dana,
                created["id"],
                {
                    "units": [],
                    "create_owner_account": True,
                    "owner": {
                        "name": "Brazos Bend Developments LLC",
                        "kind": "builder_developer",
                        "sub_category": "permanent",
                        "email": "",
                        "phone": "555-0147",
                    },
                },
            )
        # The refusal names the KIND, never the classification — and it is not
        # the unknown-lookup error a classification would have produced.
        assert "identity_kind_required" in str(refused.value)
        connection = work_tables.Connection.objects.get(pk=created["id"])
        assert connection.owner_account_id is None


def test_a_caller_already_speaking_the_doors_language_is_not_retranslated(dana, brazos):
    """**The mapping is a translation, never an override.**

    `create_owner_account` is called by the wizard AND by tests, the seeder and
    any door that already assembles `contact`/`customer` properly. A translation
    that overwrote those would quietly demote every one of them to whatever the
    wizard happens to collect.
    """
    with tenant_ctx(brazos):
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.create_owner_account(
            dana,
            created["id"],
            {
                "name": "Ignored Wizard Name",
                "contact": {"full_name": "Hand-assembled Payer"},
                "customer": identity_fixtures.company_customer("Hand-assembled Payer"),
            },
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        contact = customers_models.Contact.objects.get(account=account)
        assert contact.full_name == "Hand-assembled Payer"
