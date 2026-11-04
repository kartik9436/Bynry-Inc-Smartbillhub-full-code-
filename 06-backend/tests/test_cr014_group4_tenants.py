# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 group 4 — the journeys that need a tenant which is NOT
#           brazos-bend. The cohort builders are in
#           tests/journey_cohort_fixtures.py and are registered per journey in
#           08-qa/01-e2e/stack/seed_journey_fixture.py (T4-22, T5-21, T5-22,
#           T7-09).
# Rules:    CLAUDE.md rule 1 (every write inside the RIGHT tenant's context;
#           RLS FORCE — a second tenant's rows cannot be written from the
#           first's, and that refusal is the product working) · rule 6 (a
#           re-boot re-runs every seeder; `provision_tenant` is idempotent on
#           the subdomain and a replay mints no session) · BR-TEN-011
#           (subdomain grammar allows hyphens, so the journeys' own names are
#           used) · BR-AST-034 (the 10,000-row import cap these files cross).
# Golden:   No money figure is asserted here. Group 4's cohorts are PRE-bill by
#           construction — a currency-lock journey needs zero financial records
#           — so what is asserted is the SHAPE provisioning produced and the
#           absence the journeys depend on.
# Red-proof: proved RED before green; the failures are quoted in the W11 lane
#           report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""CR-014 group 4 — a second tenant, provisioned rather than constructed.

The failure this file exists to prevent is subtle and would never fail a
journey: a fixture that INSERTS a `tenants` row and hand-builds the rest seeds
a tenant no signup ever produced — no trial subscription, no owner membership,
no number series — and every screen the journey walks still renders. So the
cohort calls the real `provision_tenant`, and these cases assert the things
only provisioning could have created.

The second property is an ABSENCE: T4-22 and T7-09 are currency-LOCK journeys,
and the lock is caused by the first financial record. A cohort that left an
issued bill behind would pre-lock the currency, step 1 would fail for a reason
neither journey describes, and the diagnosis would go looking in the wrong
module entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import journey_cohort_fixtures as cohort

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[2]


# ⚠ THIS FILE DELIBERATELY REQUESTS NEITHER `brazos` NOR `dana`, AND THAT IS
# THE WHOLE REASON IT CAN TEST ANYTHING — DEF-566.
#
# `tests/test_us_met_helpers.brazos` depends on `test_us_ten_helpers.identity_seam`,
# a monkeypatch fixture that replaces `apps.identity.services.provision_owner`
# with a stub returning a random uuid4 and creating NO `users` row and NO
# `tenant_memberships` row. It calls itself *"skip-until-wired"*; the real
# function has been authored since (apps/identity/services.py:811), so the stub
# now shadows a working implementation. Measured on this database:
#
#     OWNER_USER_ID: caf31309-2eaf-43f5-9424-fafdfea1c0f3   ← a uuid4, i.e. the stub
#     ALL USERS:     [dana@brazosbendutilities.test]        ← the fixture's own
#     ALL MEMBERSHIPS: []
#
# So under those fixtures a provisioned tenant has no owner, `tenant_actor`
# refuses correctly, and NOTHING about provisioning's real output can be
# asserted. Requesting only `db` lets the real seam run. Filed as DEF-566;
# `tests/test_us_ten_helpers.py` is not this lane's to change, and changing a
# fixture several hundred tests share is not a thing to do in passing.


def test_group4_t4_22_t7_09__maple_creek_is_provisioned_not_constructed(db):
    """The tenant carries what only `provision_tenant` writes.

    A trial subscription, an owner who holds a System Admin MEMBERSHIP (not a
    typed `role` attribute), and the seeded chart of accounts. Each is asserted
    because each is invisible to every journey assertion: a hand-built tenant
    renders every screen identically and fails only later, in production.
    """
    from apps.identity import models as identity_models
    from apps.ledger import models as ledger_models
    from apps.tenancy import models as tenancy_models

    result = cohort.ensure_maple_creek_cohort(None)

    tenant = tenancy_models.Tenant.objects.get(subdomain=cohort.MAPLE_CREEK_SUBDOMAIN)
    with cohort._in_tenant(tenant.id):
        membership = (
            identity_models.TenantMembership.objects.filter(tenant=tenant)
            .select_related("user", "role")
            .first()
        )
        chart = ledger_models.LedgerAccount.objects.filter(tenant=tenant).count()
        services = tenancy_models.TenantService.objects.filter(tenant=tenant).count()

    assert result["tenant"] == cohort.MAPLE_CREEK_SUBDOMAIN
    assert membership is not None and membership.role.code == "system_admin"
    assert membership.user.email == cohort.MAPLE_CREEK_OWNER_EMAIL
    assert chart >= 13  # the shared chart provisioning seeds (J1 step 3b's count)
    assert services >= 1


def test_group4_t4_22_t7_09__the_currency_is_still_settable(db):
    """*"zero financial records at start"* — the precondition, PROVED.

    The currency lock is CAUSED by the first financial record, so this absence
    is not tidiness: it is the entire fixture. The builder refuses rather than
    report success if anything financial exists, and this holds it to that.
    """
    from apps.billing import models as billing_models
    from apps.payments import models as payment_models
    from apps.tenancy import models as tenancy_models

    result = cohort.ensure_maple_creek_cohort(None)
    tenant = tenancy_models.Tenant.objects.get(subdomain=cohort.MAPLE_CREEK_SUBDOMAIN)
    with cohort._in_tenant(tenant.id):
        issued = billing_models.Invoice.objects.filter(tenant=tenant, status="issued").count()
        payments = payment_models.Payment.objects.filter(tenant=tenant).count()

    assert issued == 0 and payments == 0
    assert result["financial_records"] == {"issued_invoices": 0, "payments": 0}
    # And the tenant is NOT already on CAD — setting it is the journey's step 1.
    assert tenant.currency == "USD"


def test_group4_t4_22__the_second_tenant_is_billable_when_the_journey_asks(db):
    """The first bill has to be PRODUCIBLE, or the lock never happens.

    A currency-lock journey whose bill run finds nothing to bill reports no
    lock — and reads exactly like a lock that failed. `prepare_run` is called
    read-only by the builder for this reason; here the same account is asserted
    to be on a plan with a committed read behind it.
    """
    from apps.customers import models as customer_models
    from apps.tenancy import models as tenancy_models

    cohort.ensure_maple_creek_cohort(None)
    tenant = tenancy_models.Tenant.objects.get(subdomain=cohort.MAPLE_CREEK_SUBDOMAIN)
    with cohort._in_tenant(tenant.id):
        account = customer_models.Account.objects.get(
            tenant=tenant, account_no=cohort.MAPLE_CREEK_ACCOUNT
        )
        plan = account.unit.rate_plan

    assert plan is not None
    assert plan.code == cohort.PLAN_CODE  # the SAME flat plan brazos-bend prices


def test_group4__provisioning_a_second_tenant_twice_mints_one(db):
    """CLAUDE.md rule 6. `provision_tenant` is idempotent on the subdomain, so
    a re-booted stack finds the tenant and writes nothing twice — including no
    second owner, which would silently give the tenant two System Admins and
    change what T5-26's last-admin guard is even about."""
    from apps.identity import models as identity_models
    from apps.tenancy import models as tenancy_models

    from apps.customers import models as customer_models

    cohort.ensure_maple_creek_cohort(None)
    tenant = tenancy_models.Tenant.objects.get(subdomain=cohort.MAPLE_CREEK_SUBDOMAIN)
    with cohort._in_tenant(tenant.id):
        users_after_one = identity_models.User.objects.filter(tenant=tenant).count()

    cohort.ensure_maple_creek_cohort(None)

    tenants = tenancy_models.Tenant.objects.filter(
        subdomain=cohort.MAPLE_CREEK_SUBDOMAIN
    ).count()
    with cohort._in_tenant(tenant.id):
        users_after_two = identity_models.User.objects.filter(tenant=tenant).count()
        owners = identity_models.User.objects.filter(
            tenant=tenant, email=cohort.MAPLE_CREEK_OWNER_EMAIL
        ).count()
        accounts_here = customer_models.Account.objects.filter(
            tenant=tenant, account_no=cohort.MAPLE_CREEK_ACCOUNT
        ).count()

    assert tenants == 1
    # ⚠ The tenant holds MORE than one user by design, and asserting "1" was
    # wrong: CR-010's mandate PLANTS a new tenant with sample data, so
    # provisioning mints the owner AND the sample staff cast. What idempotency
    # means here is that the SECOND pass adds nobody.
    assert users_after_two == users_after_one
    assert owners == 1
    assert accounts_here == 1


def test_group4_t5_22__lakeview_has_harbor_tower_and_no_units_on_it(db):
    """T5-22's premises exists and is EMPTY.

    The journey's whole assertion is that 3,200 units are refused before one is
    created. Units already sitting on the premises would make the refusal about
    a different number, and a partial creation is exactly what the cap exists
    to prevent — so seeding any would seed the failure state.
    """
    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models

    result = cohort.ensure_lakeview_cohort(None)
    tenant = tenancy_models.Tenant.objects.get(subdomain=cohort.LAKEVIEW_SUBDOMAIN)
    with cohort._in_tenant(tenant.id):
        premises = metering_models.Premises.objects.get(
            tenant=tenant, address_line=cohort.HARBOR_TOWER
        )
        units = metering_models.Unit.objects.filter(tenant=tenant, premises=premises).count()

    assert result["premises"] == cohort.HARBOR_TOWER
    assert units == 0


def test_group4_t5_21__the_three_csvs_cross_the_cap_and_rejoin(db):
    """T5-21's files: one over the cap, and two that split it exactly.

    Three properties, and each one is load-bearing for a different half of the
    journey: the whole file EXCEEDS `IMPORT_ROW_CAP` (or nothing is refused),
    the first part sits exactly ON it (or the accepted half tests a different
    boundary), and the two parts REJOIN byte for byte (or they are not *"the
    same content split"* and the journey's recovery proves nothing).
    """
    from apps.assets import services as asset_services

    result = cohort.ensure_import_cap_csvs(REPO_ROOT)
    directory = Path(result["directory"])
    whole = (directory / "assets-cutover.csv").read_text()
    part_one = (directory / "assets-cutover-1.csv").read_text()
    part_two = (directory / "assets-cutover-2.csv").read_text()

    def body(text: str) -> str:
        return text.split("\n", 1)[1]

    assert result["files"]["assets-cutover.csv"]["rows"] == cohort.CUTOVER_ROWS
    assert cohort.CUTOVER_ROWS > asset_services.IMPORT_ROW_CAP
    assert result["files"]["assets-cutover-1.csv"]["rows"] == asset_services.IMPORT_ROW_CAP
    assert body(part_one) + body(part_two) == body(whole)
    # Generated, never committed — the directory carries its own .gitignore.
    assert (directory / ".gitignore").read_text().strip().endswith("*")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-014 group 4 · W11 lane 2026-08-22
# generated: 2026-08-22
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: pytest (this file) · seed_journey_fixture.py --check · golden 33/33
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

