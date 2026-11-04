# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W0 — every customer gets a number (design B18 §2.5, §11 W0)
# Rules:    BR-TEN-035 (numbers come from the tenant series, tenant-editable) ·
#           BR-CUS-054 (the first-class customer entity being numbered) ·
#           BR-TEN-043 (the issue date is an input, never a clock read) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Screens:  S8 Settings -> Numbering (the series appears there by derivation)
# ───────────────────────────────────────────────────────
"""CR-030 W0 — `customers.customer_no`, the twenty-fourth series.

WHY THIS EXISTS, in one sentence a reader can check: accounts, premises, units,
bills, payments, assets and work orders all carry a number and `customers` did
not, so every deposit carry-forward and every *"they owe money on another
account"* check rested on a clerk matching a NAME.

The worked case put to the PO (B18 §2.5): a returning customer holding
**$153.50** on a CLOSED account gets it carried across — or does not, because
nobody found them.

PROVED RED FIRST (hard-won law 7). Before the column existed every case below
failed on `AttributeError: 'Customer' object has no attribute 'customer_no'`;
before the series existed, `test_..._allocates_from_the_tenant_series` failed on
`NumberingError: unknown series 'customer'`. The two catalogue-count guards in
`test_cr005_numbering_set08.py` and `test_cr005_numbering_reaches_records.py`
went red on the commit that added the series, which is what they are for.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.tenancy import models as tenancy_models
from core import numbering as core_numbering

from tests.isolation_helpers import (  # noqa: F401
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

# `_plan` builds a PUBLISHED rate plan a unit can be put on. Imported rather
# than re-written: BR-RAT-030 makes only published plans assignable, and a
# second copy of that detail is a second place for it to go stale.
from tests.identity_fixtures import SAMPLE_COMPANY_TAX_ID  # noqa: E402
from tests.test_us_cus_003_account_write import _plan  # noqa: E402

pytestmark = pytest.mark.django_db


def _account_for(actor, tenant, *, label, service="electric"):
    """An account to hang a customer link on. Built through the REAL services of
    the modules that own each row — no ORM shortcut across a boundary (B1)."""
    from apps.metering import services as metering_services

    # ⚠ AND THE PREMISE TOO — `make_premises` defaults `services_available` to
    # the Brazos set. THIRD place the service has to be threaded, which is the
    # honest shape of a multi-service product: a premise cannot offer a service
    # its tenant has not enabled, a unit cannot sit on a plan for one, and a
    # service point cannot exist for one.
    premises = make_premises(actor, services_available=[service])
    unit = make_unit(actor, premises["id"], label=label)
    # ⚠ THE PLAN'S SERVICE MUST MATCH THE UNIT'S TOO. `_plan` defaults to
    # electric, and Lone Star Ridge is water-only — so a cross-tenant case that
    # threads `service` into `ensure_service_point` and NOT into the plan fails
    # one line later with the same `service_not_enabled`. Both, or neither.
    plan = _plan(tenant, name=f"{service.title()} Standard", service_code=service)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], service)
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-08-15",
            # ⛔ **NO `contact` AND NO `customer`, AND THAT IS THIS SUITE'S
            # SUBJECT RATHER THAN A DODGE OF `BR-CUS-1024` (PO 2026-09-01).**
            # The rule has three rows and the THIRD one is the PO's own: a
            # payload presenting NO party at all is not a payload that failed to
            # identify one, and it keeps every in-process creator working — *"a
            # transfer, a seed, a service request that opens an account for a
            # party named elsewhere"* (`services.refuse_account_without_identity`).
            # That is EXACTLY this fixture: every case below names the party on
            # the very next line, with an explicit `link_customer`, because the
            # thing under test is WHICH NUMBER that call hands out.
            #
            # ⚠ **THE OTHER REPAIR WOULD HAVE MOVED THE ASSERTIONS, WHICH IS WHY
            # IT WAS NOT MADE.** Giving this payload the suite-wide identity
            # block (`tests/identity_fixtures.py`) mints a customer at the door,
            # so the `link_customer` on the next line hands out **C-00002** and
            # `test_w0_tc1`'s signed *"the first customer a tenant ever creates
            # is C-00001"* would have had to be edited to stay green. A fixture
            # is allowed to change; the figure it pins is not.
            #
            # The contact carried a name and an email and nothing in this file
            # ever read either.
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# The number itself
# ══════════════════════════════════════════════════════════════════════════


def test_w0_tc1__a_new_customer_allocates_from_the_tenant_series(brazos, marcus):
    """The seeded default is `C-{00000}`, so the first customer a tenant ever
    creates is **C-00001** — the shortest thing a clerk can read back down a
    phone, which is the whole reason the number exists."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W0 A")
        linked = customers_services.link_customer(
            account_id=account["id"], external_ref="CUST-118", display_name="Ridge Coffee Co."
        )
        assert linked["customer_no"] == "C-00001"
        row = customers_models.Customer.objects.get(pk=linked["id"])
        assert row.customer_no == "C-00001"


def test_w0_tc2__numbers_are_gapless_and_the_series_has_its_own_counter(brazos, marcus):
    """Gapless WITHIN a tenant, and on its OWN counter — a shared pool would
    make the second customer C-00002 only by accident of how many accounts had
    been created first."""
    with tenant_ctx(brazos):
        seen = []
        for i in range(3):
            account = _account_for(marcus, brazos, label=f"W0 B{i}")
            linked = customers_services.link_customer(
                account_id=account["id"],
                external_ref=f"CUST-20{i}",
                display_name=f"Customer {i}",
            )
            seen.append(linked["customer_no"])
        assert seen == ["C-00001", "C-00002", "C-00003"]


def test_w0_tc3__a_second_tenant_counts_independently(brazos, lonestar, marcus, erin):
    """CLAUDE.md rule 1. Two tenants both open at C-00001; a shared sequence
    would leak one tenant's customer count to the other, which is a disclosure
    as well as a bug."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W0 C")
        first = customers_services.link_customer(
            account_id=account["id"], external_ref="CUST-1", display_name="Brazos One"
        )
    with tenant_ctx(lonestar):
        # ⚠ NOT electric: Lone Star Ridge is a WATER utility in the fixture set
        # and `ensure_service_point` refuses a service the tenant has not
        # enabled (`metering.service_not_enabled`). Hardcoding one service in a
        # cross-tenant test is how you write a case that only passes for the
        # first tenant you thought of.
        account = _account_for(erin, lonestar, label="W0 C", service="water")
        second = customers_services.link_customer(
            account_id=account["id"], external_ref="CUST-1", display_name="Lone Star One"
        )
    assert first["customer_no"] == second["customer_no"] == "C-00001"


def test_w0_tc4__relinking_an_existing_ref_does_not_burn_a_second_number(brazos, marcus):
    """BR-CUS-054's matching rule: one `external_ref` = ONE customer row. The
    landlord with fourteen units is ONE customer with ONE number, not fourteen —
    which is the point of the whole entity."""
    with tenant_ctx(brazos):
        a1 = _account_for(marcus, brazos, label="W0 D1")
        a2 = _account_for(marcus, brazos, label="W0 D2")
        one = customers_services.link_customer(
            account_id=a1["id"], external_ref="CUST-118", display_name="Ridge Coffee Co."
        )
        two = customers_services.link_customer(
            account_id=a2["id"], external_ref="cust-118", display_name="Ridge Coffee Co."
        )
        assert one["id"] == two["id"]
        assert one["customer_no"] == two["customer_no"] == "C-00001"
        assert customers_models.Customer.objects.filter(tenant_id=brazos.id).count() == 1
        # And the series did NOT advance for the second call.
        series = tenancy_models.NumberSeries.objects.get(
            tenant_id=brazos.id, series=core_numbering.CUSTOMER
        )
        assert series.next_number == 2


def test_w0_tc5__the_legacy_ref_survives_beside_our_number(brazos, marcus):
    """⚠ THE ONE A LANE IS MOST LIKELY TO GET WRONG. `customer_no` does NOT
    replace `external_ref`: theirs reconciles against the system we migrated
    from (BR-CUS-054), ours is quotable. A utility needs both, and a customer
    created by the S18 wizard has no `external_ref` at all."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W0 E")
        linked = customers_services.link_customer(
            account_id=account["id"], external_ref="CIVIC-9931", display_name="Okonkwo, David"
        )
        row = customers_models.Customer.objects.get(pk=linked["id"])
        assert row.external_ref == "CIVIC-9931"
        assert row.customer_no == "C-00001"

        walk_up = _account_for(marcus, brazos, label="W0 E2")
        no_ref = customers_services.link_customer(
            account_id=walk_up["id"], display_name="Alvarez, Rosa"
        )
        row2 = customers_models.Customer.objects.get(pk=no_ref["id"])
        assert row2.external_ref is None
        assert row2.customer_no == "C-00002"


def test_w0_tc6__a_tenant_that_edited_its_format_gets_that_format(brazos, marcus):
    """BR-TEN-035 makes every series tenant-editable, so nothing here may assume
    `C-`. This is also why the 0014 backfill passes a REAL issue date to
    `render` (BR-TEN-043): a tenant already on `C-{YYYY}-{0000}` would raise on
    a None date."""
    with tenant_ctx(brazos):
        series = tenancy_models.NumberSeries.objects.get(
            tenant_id=brazos.id, series=core_numbering.CUSTOMER
        )
        series.format = "C-{YYYY}-{0000}"
        series.save(update_fields=["format"])
        account = _account_for(marcus, brazos, label="W0 F")
        linked = customers_services.link_customer(
            account_id=account["id"], external_ref="CUST-7", display_name="Formatted"
        )
        assert linked["customer_no"].startswith("C-20")
        assert linked["customer_no"].endswith("-0001")


def test_w0_tc7__the_series_is_seeded_at_provisioning_and_appears_on_the_screen(brazos):
    """A series the Settings screen cannot show is a series a tenant cannot
    edit. It is derived from the catalogue rather than typed, so this cannot
    drift (the gap BR-LED-021 (i) was about)."""
    from apps.tenancy import services as tenancy_services

    assert tenancy_services.SERIES_DEFAULTS[core_numbering.CUSTOMER] == "C-{00000}"
    with tenant_ctx(brazos):
        assert tenancy_models.NumberSeries.objects.filter(
            tenant_id=brazos.id, series=core_numbering.CUSTOMER
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# The backfill — migration 0014
# ══════════════════════════════════════════════════════════════════════════


def test_w0_tc8__the_backfill_numbers_existing_rows_in_creation_order(brazos, marcus):
    """The migration's own function, driven directly against real rows.

    Two properties matter and neither is provable by the migration merely
    APPLYING (which it does on every test-database build, against an empty
    table): rows are numbered oldest-first, and **the tenant's counter advances
    past them**. A bulk `row_number()` would satisfy the first and not the
    second, and would then hand the same numbers out again to the next customer
    `link_customer` created — a duplicate-key error at an unrelated later
    moment, which is the worst kind of bug to inherit."""
    import importlib

    from django.apps import apps as django_apps

    # The module name starts with a digit, so it cannot be imported by `from`.
    _mod = importlib.import_module("apps.customers.migrations.0014_cr030_w0_backfill_customer_no")

    with tenant_ctx(brazos):
        made = []
        for i in range(3):
            account = _account_for(marcus, brazos, label=f"W0 G{i}")
            linked = customers_services.link_customer(
                account_id=account["id"],
                external_ref=f"CUST-30{i}",
                display_name=f"Backfill {i}",
            )
            made.append(linked["id"])

        # Put them back the way a pre-W0 database held them.
        customers_models.Customer.objects.filter(tenant_id=brazos.id).update(customer_no=None)
        series = tenancy_models.NumberSeries.objects.get(
            tenant_id=brazos.id, series=core_numbering.CUSTOMER
        )
        series.next_number = 1
        series.save(update_fields=["next_number"])

        _mod.forwards(django_apps, None)

        rows = list(
            customers_models.Customer.objects.filter(tenant_id=brazos.id)
            .order_by("created_at", "id")
            .values_list("customer_no", flat=True)
        )
        assert rows == ["C-00001", "C-00002", "C-00003"]
        series.refresh_from_db()
        assert series.next_number == 4, "the counter must advance past what it just handed out"


@pytest.mark.isolation
@requires_postgres
def test_w0_tc9__a_second_tenant_sees_none_of_the_first_tenants_customers(
    rls, brazos, lonestar, marcus
):  # noqa: F811
    """CLAUDE.md rule 1, asserted through the DATABASE under a role RLS applies
    to — the app-layer filter is deliberately not in the path.

    ⚠ THE FIRST VERSION OF THIS CASE WAS A PLAIN ORM QUERY UNDER `tenant_ctx`,
    and it went green having proven nothing: the app connects as a SUPERUSER,
    superusers bypass row-level security unconditionally, and
    `isolation_helpers` exists to say exactly that. Both tenants opening at
    `C-00001` (TC-3) makes the number a tempting cross-tenant handle, so this is
    the case that has to be real."""
    with live_tenant_context(brazos.id):
        account = _account_for(marcus, brazos, label="W0 H")
        # ⚠ **`kind` AND `identity` ARE REQUIRED NOW, AND WITHOUT THEM
        # `link_customer` CREATES NOTHING AND SAYS SO IN ITS RETURN VALUE**
        # rather than raising: `not_created: {code: customer_not_identified,
        # missing: customer_kind_missing}`. BR-CUS-1022/1023 make identity a
        # per-kind fact — a phone for a person, a Tax ID for a company —
        # because a name alone cannot tell two customers apart. So `linked`
        # came back with `id: None`, no `customers` row was written, and
        # `assert_rls_scoped` correctly refused to conclude anything about a
        # policy from an empty table.
        # ⚠ THIS IS NOT AN RLS FAILURE AND THE REST OF THIS FILE IS STILL RED
        # ON THE ORDINARY SQLITE SUITE FOR THE SAME REASON — see the defect
        # filed with this change. Only TC-9 is repaired here, because only TC-9
        # is this lane's.
        linked = customers_services.link_customer(
            account_id=account["id"],
            external_ref="CUST-ISO",
            display_name="Brazos Only",
            kind="company",
            identity={"tax_id": SAMPLE_COMPANY_TAX_ID},
        )
    assert_rls_scoped(rls, "customers", owner=brazos, intruder=lonestar, owner_ids={linked["id"]})
    assert_no_foreign_rows_anywhere(rls, lonestar, ("customers", "customer_accounts"))
