# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 / **TC-7 (isolation — mandatory)**
#           "Account A-20991 (Dan Okafor) exists only in Harbor Point Water. In
#           a Silver Creek session, search 'A-20991' and 'Okafor' → Zero results
#           for both; automated isolation test seeds both tenants, runs the
#           search under each tenant context, and asserts no row from the other
#           tenant is ever returned."
#           Screens: shell chrome (the topbar box, every authenticated screen)
# Rules:    BR-SHL-006 (CONFIRMED — "runs under app.tenant_id + RLS FORCE; never
#           another tenant's rows"; release-blocking) · CLAUDE.md hard rule 1 ·
#           B2 §3 RLS policy template · NFR-10 (zero tolerance)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off PostgreSQL — SQLite has no RLS, so a green run there
#           would prove nothing (tests/isolation_helpers.py explains the probe
#           role and why a superuser connection makes an RLS assertion vacuous).
# ───────────────────────────────────────────────────────
"""The database half of universal search's tenant isolation.

⚠ **THIS IS THE SHARPEST SURFACE IN THE PRODUCT FOR A SCOPING MISTAKE, AND THAT
IS WHY THE MANDATORY TC IS HERE.** Every other screen reads ONE module's table.
Global search reads NINE at once, on every keystroke, from a box that is on
every authenticated screen — so a filter dropped in one selector does not leak
one screen's worth of another utility's data, it leaks their customers, their
addresses, their meters, their bills and their payments in one popover.

THREE LAYERS ARE ASSERTED, AND THEY FAIL INDEPENDENTLY
-------------------------------------------------------
  1 · **The application layer** — every source filters `tenant_id=`. Proved by
      seeding BOTH tenants with rows that MATCH THE SAME QUERY and asserting the
      search returns only the caller's. If a `tenant_id=` were dropped, both
      tenants' rows would come back and this goes red.
  2 · **The kernel's refusal** — `core.search.search()` raises rather than
      running without `app.tenant_id`. There is no lawful tenant-less search.
  3 · **The database** — RLS FORCE, asserted through the NON-SUPERUSER probe
      role, so the policies are genuinely consulted rather than bypassed. This
      is the layer that still holds if 1 is buggy, and it is the only one a
      SQLite run cannot say anything about.

**Layer 1 is the one written to fail loudly, because it is the one a lane can
break by accident.** A new search source is nine lines of ORM; forgetting the
tenant filter in it is a one-line mistake that every other test in the repo
would pass. `test_tc7_a_query_matching_both_tenants_returns_only_the_callers`
is built so that it CANNOT pass on an unscoped query: the two tenants hold rows
whose identifiers differ only in their tenant, and the query matches both.
"""

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.assets import models as asset_models
from apps.billing.models import Invoice
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.payments import models as payment_models
from core import errors, permissions, search

from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    clear_live_guc,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_idn_helpers import idn  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db

#: Every table universal search reads. A row of any of these reaching the wrong
#: tenant is the release blocker BR-SHL-006 names.
SEARCH_TABLES = (
    "premises",
    "units",
    "assets",
    "accounts",
    "contacts",
    "customers",
    "invoices",
    "payments",
    "service_requests",
)


def _populate(tenant, *, account_no, name, marker):
    """One row on every searchable surface, all carrying `marker`.

    `marker` is what makes layer 1 provable: BOTH tenants get rows containing
    it, so a query for it matches in both and an unscoped source returns both.
    """
    status = customer_models.AccountStatus.objects.create(
        tenant=tenant, code="active", name="Active", behavior_class="billable"
    )
    # ⚠ **`AccountType.objects.first()` STOOD HERE AND RETURNED `None` ON
    # POSTGRESQL, WHICH IS WHY THIS WHOLE FILE ERRORED** (`DEF-SHL-6714`).
    # `account_types` was a PLATFORM table — no `tenant_id`, rows seeded once by
    # a migration for everybody — until the PO ruling of 2026-09-17 (*"utility
    # can get their own account types"*, `customers.0054`/`0055`) made it the
    # TENANT's own and put RLS on it. A tenant this fixture creates by hand has
    # none, so `.first()` answered `None`, `accounts.account_type_id` is NOT
    # NULL, and the resulting `NotNullViolation` poisoned the transaction and
    # took every later case in the file with it (CLAUDE.md law 14).
    # ⚠ **IT IS INVISIBLE ON SQLITE, WHICH IS WHY NOTHING ELSE WENT RED:** with
    # no RLS, `.first()` there returns some OTHER tenant's row and the FK is
    # satisfied, so the same line is green in the default suite and wrong.
    # The seed is taken through the product's own path rather than by minting a
    # row here, so this fixture keeps telling the truth about what a real tenant
    # holds.
    customer_services.ensure_account_types()
    # `DEF-SHL-10691` — BY TENANT: where RLS is bypassed (a superuser
    # cluster) a code-only `get` sees BOTH tenants' seeded rows and raises
    # `MultipleObjectsReturned` before any search runs.
    account_type = customer_models.AccountType.objects.get(tenant_id=tenant.id, code="residential")
    today = timezone.localdate()
    now = timezone.now()

    premises = metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"P-{marker}",
        name=f"{name} Court",
        address_line=f"7 {marker} Road",
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, unit_no=f"U-{marker}", label="Unit 1"
    )
    account = customer_models.Account.objects.create(
        tenant=tenant,
        account_no=account_no,
        kind="regular",
        status=status,
        account_type=account_type,
        premises_id=premises.id,
        unit=unit,
    )
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name=name, is_primary=True
    )
    master = customer_models.Account.objects.create(
        tenant=tenant,
        account_no=f"M-{marker}",
        kind="master",
        status=status,
        account_type=account_type,
        premises_id=premises.id,
    )
    # ⚠ A SECOND REGULAR ACCOUNT, CARRYING THE MARKER. The story's account is
    # A-10432 / A-20991 (TC-7's own data) and neither contains the marker, so
    # the shared-query sweep would not reach the `accounts` group at all — the
    # single most important group to prove scoped, and the one whose absence
    # would have made this test quietly weaker than it looks.
    marker_unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, unit_no=f"U2-{marker}", label="Unit 2"
    )
    marker_account = customer_models.Account.objects.create(
        tenant=tenant,
        account_no=f"A-{marker}",
        kind="regular",
        status=status,
        account_type=account_type,
        premises_id=premises.id,
        unit=marker_unit,
    )
    asset_type = asset_models.AssetType.objects.create(
        tenant=tenant, code="water_meter", name="Water meter", category="meters"
    )
    stage = asset_models.AssetLifecycleStage.objects.create(
        tenant=tenant, code="in_service", name="In service", behavior_class="in_service"
    )
    asset = asset_models.Asset.objects.create(
        tenant=tenant,
        asset_no=f"MTR-{marker}",
        serial_no=f"SN-{marker}",
        type=asset_type,
        status=stage,
    )
    customer = customer_models.Customer.objects.create(
        tenant=tenant, customer_no=f"C-{marker}", kind="person", display_name=name
    )
    invoice = Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=f"BL-{marker}",
        status="issued",
        service_date=today,
        period_start=today,
        period_end=today,
        due_date=today,
        subtotal=Decimal("100.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("100.00"),
        currency="USD",
    )
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=f"PMT-{marker}",
        type=payment_models.PAYMENT_TYPE_PAYMENT,
        purpose=payment_models.PURPOSE_BILL,
        amount=Decimal("10.00"),
        currency="USD",
        status=payment_models.PAYMENT_POSTED,
        posted_at=now,
    )
    request = customer_models.ServiceRequest.objects.create(
        tenant=tenant,
        request_no=f"SR-{marker}",
        state=customer_models.ServiceRequest.SUBMITTED,
        channel=customer_models.ServiceRequest.CHANNEL_STAFF_COLLECTIONS,
        applicant_kind=customer_models.ServiceRequest.APPLICANT_PERSON,
        applicant_name=name,
        address_as_given=f"7 {marker} Road",
    )
    # Only rows whose identifier CARRIES the marker belong in the sweep — the
    # story account is found by its own number, in the TC-7 case below.
    marked = {
        "premises": premises,
        "unit": unit,
        "unit (2)": marker_unit,
        "account": marker_account,
        "master account": master,
        "asset": asset,
        "customer": customer,
        "bill": invoice,
        "payment": payment,
        "service request": request,
    }
    return marked, account


@pytest.fixture()
def two_utilities(idn):
    """Silver Creek and Harbor Point, each fully populated.

    US-SHL-003 §4's own test data: Silver Creek holds A-10432 (Maria Delgado);
    **A-20991 (Dan Okafor) exists ONLY in Harbor Point.**
    """
    silver, harbor = idn.silvercreek, idn.bluemesa
    with live_tenant_context(silver.id):
        silver_rows, _ = _populate(
            silver, account_no="A-10432", name="Maria Delgado", marker="SHARED"
        )
    with live_tenant_context(harbor.id):
        harbor_rows, _ = _populate(harbor, account_no="A-20991", name="Dan Okafor", marker="SHARED")
    return silver, harbor, silver_rows, harbor_rows


def _labels(results):
    return {row["label"] for rows in results.values() for row in rows}


# ══════════════════════════════════════════════════════════════════════════
# LAYER 1 — THE APPLICATION. A QUERY THAT MATCHES BOTH TENANTS.
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_tc7_a_query_matching_both_tenants_returns_only_the_callers(two_utilities):
    """**THE CASE THAT CANNOT PASS ON AN UNSCOPED QUERY.**

    Both utilities hold a row on EVERY ONE of the nine searchable surfaces whose
    identifier contains `SHARED`. One query for it matches twenty rows across
    the two tenants. A source that dropped its `tenant_id=` filter would return
    the other utility's rows here and NOWHERE ELSE IN THE SUITE — every other
    test seeds one tenant, so an unscoped query looks correct in all of them.
    """
    silver, harbor, silver_rows, harbor_rows = two_utilities

    with live_tenant_context(silver.id):
        silver_view = search.search("SHARED", role=permissions.SYSTEM_ADMIN)
    with live_tenant_context(harbor.id):
        harbor_view = search.search("SHARED", role=permissions.SYSTEM_ADMIN)

    # Each side sees its own rows — otherwise the assertions below would pass on
    # a search that returns nothing at all, which proves nothing.
    assert silver_view, "Silver Creek sees none of its own rows — the fixture wrote nothing"
    assert harbor_view, "Harbor Point sees none of its own rows — the fixture wrote nothing"

    # ⚠ **THE COMPARISON IS BY ID, NOT BY LABEL, AND THAT IS THE POINT.** Both
    # utilities hold rows whose identifiers are byte-identical — `M-SHARED`,
    # `MTR-SHARED`, `BL-SHARED` — because the marker is what makes one query
    # match both. So a label cannot tell the two tenants apart, and a test that
    # compared labels would be satisfied by the LEAKED row. The record ids can.
    # (The account NUMBERS differ — A-10432 against A-20991 — and those are
    # asserted verbatim in the TC-7 case below, which is where the story puts
    # them.)
    silver_ids = {row["id"] for rows in silver_view.values() for row in rows}
    harbor_ids = {row["id"] for rows in harbor_view.values() for row in rows}

    # Positive control FIRST: each side really sees its own nine rows. Without
    # this the leak assertions would pass on a search that returned nothing.
    for name, row in silver_rows.items():
        assert str(row.id) in silver_ids, f"Silver Creek cannot see its own {name}"
    for name, row in harbor_rows.items():
        assert str(row.id) in harbor_ids, f"Harbor Point cannot see its own {name}"

    # The leak check: row for row, in both directions.
    for name, row in harbor_rows.items():
        assert str(row.id) not in silver_ids, (
            f"LEAK — Silver Creek's search returned Harbor Point's {name}"
        )
    for name, row in silver_rows.items():
        assert str(row.id) not in harbor_ids, (
            f"LEAK — Harbor Point's search returned Silver Creek's {name}"
        )
    assert not (silver_ids & harbor_ids), "LEAK — a row is visible to both utilities"


@pytest.mark.isolation
@requires_postgres
def test_tc7_the_story_queries_verbatim(two_utilities):
    """US-SHL-003 TC-7 exactly as written: "A-20991" and "Okafor", zero results.

    Dan Okafor exists only in Harbor Point. A Silver Creek session searching for
    him — by his account number, and by his NAME, which reaches through the
    `contacts` join BR-SHL-005 signs off — finds nothing at all.
    """
    silver, harbor, _, _ = two_utilities

    with live_tenant_context(silver.id):
        by_number = search.search("A-20991", role=permissions.SYSTEM_ADMIN)
        by_name = search.search("Okafor", role=permissions.SYSTEM_ADMIN)
    assert by_number == {}, f"LEAK — Silver Creek found {by_number}"
    assert by_name == {}, f"LEAK — Silver Creek found Dan Okafor: {by_name}"

    # The mirror, so the test cannot pass because the query is simply wrong.
    with live_tenant_context(harbor.id):
        assert "A-20991" in _labels(search.search("A-20991", role=permissions.SYSTEM_ADMIN))
        assert "A-20991" in _labels(search.search("Okafor", role=permissions.SYSTEM_ADMIN))


# ══════════════════════════════════════════════════════════════════════════
# LAYER 2 — THE KERNEL REFUSES TO SEARCH WITHOUT TENANT CONTEXT
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_tc7_a_tenant_less_search_is_refused_rather_than_run_unscoped(two_utilities):
    """BR-SHL-006: there is no lawful tenant-less search.

    The alternative — running and relying on RLS to return nothing — would be a
    query that silently answers "no results" when the real answer is "this
    request has no tenant", and would leak everything the day a policy is
    dropped from one table. It raises instead.
    """
    clear_live_guc()
    with pytest.raises(errors.AuthError):
        search.search("SHARED", role=permissions.SYSTEM_ADMIN)


@pytest.mark.isolation
@requires_postgres
def test_tc7_context_from_a_tenant_that_does_not_exist_finds_nothing(two_utilities):
    """A well-formed but unknown tenant id returns nothing rather than everything.

    Belt beside the brace: the middleware resolves the tenant from the path and
    404s an unknown slug, so this id cannot arrive from a request. It is here
    because the failure it guards against — a filter that treats "no match" as
    "no filter" — is silent, and because a background job sets context itself.
    """
    stranger = uuid.uuid4()
    with live_tenant_context(stranger):
        assert search.search("SHARED", role=permissions.SYSTEM_ADMIN) == {}


# ══════════════════════════════════════════════════════════════════════════
# LAYER 3 — THE DATABASE, THROUGH A NON-SUPERUSER PROBE
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
@pytest.mark.parametrize("table", SEARCH_TABLES)
def test_tc7_every_searched_table_is_rls_scoped(two_utilities, rls, table):  # noqa: F811
    """Each of the nine tables, asserted through a role RLS applies to.

    `assert_rls_scoped` reads the table under each tenant's live GUC as
    `sbh_rls_probe` — NOLOGIN NOSUPERUSER NOBYPASSRLS — so the policy is really
    consulted. The app-layer filter is deliberately not in the path: this is the
    layer that still holds when a selector is wrong.
    """
    silver, harbor, _, _ = two_utilities
    assert_rls_scoped(rls, table, owner=silver, intruder=harbor)


@pytest.mark.isolation
@requires_postgres
def test_tc7_under_one_tenants_context_no_foreign_row_of_any_table_is_reachable(
    two_utilities, rls  # noqa: F811
):
    """The sweep: nine tables, one context, not one foreign row anywhere."""
    silver, harbor, _, _ = two_utilities
    assert_no_foreign_rows_anywhere(rls, silver, SEARCH_TABLES)
    assert_no_foreign_rows_anywhere(rls, harbor, SEARCH_TABLES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003 (EP-SHL-01) TC-7 + BR-SHL-006 + the PO ruling of 2026-09-03
# generated: 2026-09-03 by story-coder (universal-search lane)
# gates: proved RED on the live cluster by deleting the `tenant_id=` filter from
#        `apps/customers/search_sources._account_rows` — the shared-marker case
#        then returned BOTH utilities' accounts and named the leak. Transcript in
#        the lane report (hard-won law 7).
# exceptions: none — every case here runs on PostgreSQL and skips with a VENDOR
#        reason off it; not one is unconditionally skipped (DEF-101's lesson)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
