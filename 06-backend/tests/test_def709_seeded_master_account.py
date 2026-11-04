# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S17 (the
#           Accounts list, its `Master` pill and its `kind` filter) · S21
#           (Account detail, the same pill)
# Change:   DEF-709 — the master-account feature is built, wired and INVISIBLE,
#           because no seed anywhere creates a master account.
# Rules:    BR-CUS-068 (a master account is an ordinary `accounts` row,
#           `kind='master'`, payer = the premises' owner/manager, anchored on a
#           common-area unit — and `create_master_account` is its ONLY door) ·
#           BR-CUS-083 (connection charges on a multi-unit build are invoiced to
#           the developer THROUGH a master account) · BR-MET-116 (the owner's
#           build account, `Units 26` = 25 apartments + 1 common area) ·
#           BR-MET-101 (a common area is a unit with a FLAG) · BR-MET-040 (a
#           plan is required before that account may activate) · BR-TEN-057
#           (`is_sample` on the owning row) · BR-TEN-063 (idempotent) ·
#           BR-TEN-043 / DEF-629 / DEF-704 (no literal dates — every date is
#           decided when the seed runs)
# Tests:    this file
# Impacts:  core/sample_fixture.py · apps/metering/sample_data.py ·
#           apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""DEF-709 — **the SEEDED estate must contain a master account.**

WHY THIS FILE EXISTS AT ALL, WHEN TWO MASTER-ACCOUNT SUITES ALREADY PASS
------------------------------------------------------------------------
`tests/test_br_cus_068_master_accounts.py` and `tests/test_br_cus_068_master_
bill.py` both build their own premises, their own common areas and their own
master account inline, and both are green. **That is precisely how DEF-709
hid.** They prove the FEATURE works; nobody ever asked the DEMO ESTATE whether
it contains one, and it did not — so `accounts.kind` was `regular` on every row
of every tenant the product has ever planted, the `Master` pill rendered
against nothing, and the `kind` filter partitioned a set with one side empty.

So every assertion below runs against the estate the real seeders plant, through
those seeders' own entry points. A test that constructs its own master account
here would reproduce the defect rather than catch it.
"""

from datetime import date

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample
from core import sample_fixture as fixture
from core.pagination import ListParams

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
)

pytestmark = pytest.mark.django_db

#: BR-CUS-083's worked case, verbatim: `SR-26-0043` → `CON-26-0117`,
#: 500 Main Street, 25 units, $14,390.00 — *"a) the developer, via a master
#: account"*. The developer is the premises' `owner_manager`, which is the payer
#: BR-CUS-068 names ("payer = the premises' owner/manager").
DEVELOPER = "Ridge Property LLC"
PREMISES_ADDRESS = fixture.CR030_COMMON_AREA_ADDRESS
COMMON_AREA_UNIT_NO = fixture.CR030_COMMON_AREA_UNIT_NO


@pytest.fixture()
def seeded(brazos, dana):
    """The sample plant in the orchestrator's own order (`apps.tenancy.
    sample_data.SAMPLE_MODULES`): rating — the plans a unit must carry before an
    account may activate (BR-MET-040) — then metering (the places, including the
    common area), then customers (the accounts, including the master).

    Through each module's REAL seam, never a reimplementation, so this file
    cannot drift from what a tenant actually receives.
    """
    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        customers_sample.seed_sample_records(dana)
    return brazos, dana


def _masters(tenant):
    return customers_models.Account.objects.filter(
        tenant_id=tenant.id, kind=customers_services.ACCOUNT_KIND_MASTER
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT ITSELF — the estate contains a master account
# ══════════════════════════════════════════════════════════════════════════


def test_the_seeded_estate_contains_a_master_account(seeded):
    """**DEF-709, stated as the one assertion that would have caught it.**

    RED before this lane: `assert 0 >= 1` — no seeder in the repository had
    ever written a `kind='master'` row, so `AccountsListPage`'s `Master` pill,
    `AccountDetailPage`'s pill and the `ACCOUNT_KINDS` filter all rendered
    against an empty set on every tenant this product has ever planted.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        assert _masters(tenant).count() >= 1, (
            "DEF-709: the demo estate must contain at least one kind='master' account, "
            "or the Master pill and the kind filter have nothing to render"
        )


def test_the_master_account_is_the_developers_and_stands_on_500_main_st(seeded):
    """BR-CUS-083 — *"a) the developer, via a master account"*, at
    `CON-26-0117` · `500 Main St` · 25 units · $14,390.00.

    The payer is asserted from the CONTACT, because BR-CUS-068 makes it derived
    rather than typed: with no contact in the payload the path takes the
    premises' own `owner_manager` (PO 2026-08-22: *"payer = the premises'
    owner/manager"*). If the estate ever renames the developer this goes red,
    which is the point — two copies of one fact is the drift this avoids.

    ⚠ **HOW THE ACCOUNT REACHES `500 Main St` CHANGED ON 2026-09-01 (`CR-056`
    W1 / `BR-CUS-1010`) AND *WHICH* ADDRESS IT STANDS ON DID NOT.** This read
    `Unit.objects.get(pk=master.unit_id)` and then that unit's premises — the
    ANCHOR hop. The account now names the address directly, so the premises is
    read from `master.premises_id`, and the common area it used to anchor on is
    asserted the way it is actually held: as a unit this account COVERS through
    an open service agreement.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _masters(tenant).get()
        assert master.unit_id is None
        premises = metering_models.Premises.objects.get(
            tenant_id=tenant.id, pk=master.premises_id
        )
        covered = customers_selectors.covered_unit_ids(master)
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, pk=covered[0])
        assert unit.unit_no == COMMON_AREA_UNIT_NO
        assert unit.premises_id == premises.id
        assert premises.address_line == PREMISES_ADDRESS
        contact = customers_models.Contact.objects.get(tenant_id=tenant.id, account=master)
        assert contact.full_name == DEVELOPER == premises.owner_manager


def test_the_anchor_is_a_common_area_carrying_a_plan(seeded):
    """BR-MET-101 — *a common area is a unit with a FLAG* — and BR-MET-116's
    ordering constraint: *"the owner's master account CANNOT be created before
    the common area has a plan"*, because `create_master_account` creates the
    account ACTIVE and BR-MET-040 refuses an active account on an unpriced unit.

    Both halves are asserted on the SEEDED unit, so a seed that plants the unit
    without its plan fails here rather than in a refusal message nobody reads.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=COMMON_AREA_UNIT_NO)
        assert unit.is_common_area is True
        assert unit.rate_plan_id is not None, "BR-MET-040 / BR-MET-116"
        assert unit.deleted_at is None


def test_the_master_account_actually_covers_its_common_area(seeded):
    """BR-CUS-068's *"the SAME account–unit linkage every account uses"*: the
    coverage IS `service_agreements` over the common area's service points.

    Without them the account is created with a `unit_has_no_service_points`
    warning and covers nothing — a `Master` pill on a row that bills for no
    service, which is a different flavour of the same emptiness DEF-709 is.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _masters(tenant).get()
        agreements = customers_models.ServiceAgreement.objects.filter(
            tenant_id=tenant.id, account=master
        )
        assert agreements.count() >= 1
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=COMMON_AREA_UNIT_NO)
        point_ids = set(
            metering_models.ServicePoint.objects.filter(tenant_id=tenant.id, unit=unit).values_list(
                "id", flat=True
            )
        )
        assert set(agreements.values_list("service_point_id", flat=True)) <= point_ids


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE THREE SURFACES — each read the way the screen reads it
# ══════════════════════════════════════════════════════════════════════════


def test_the_accounts_list_serves_kind_master_on_the_seeded_row(seeded):
    """S17's identity cell (`AccountsListPage.tsx` ~806) reads `row.kind`.
    `selectors.account_row` serves it on every row — this asserts the SEEDED
    estate gives it something other than `regular` to serve."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        rows = customers_selectors.account_list(ListParams(per=500))
        kinds = {row["kind"] for row in rows}
        assert "master" in kinds
        assert "regular" in kinds, "both sides of the partition must be demonstrable"


def test_the_kind_filter_partitions_the_seeded_estate(seeded):
    """S17's `kind` filter (`ACCOUNT_KINDS`) → `selectors.account_list`'s
    `f.kind`. Before DEF-709 the `master` side answered an empty page on every
    tenant, which reads as a broken filter rather than as missing data."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        masters = customers_selectors.account_list(ListParams(per=500, filters={"kind": "master"}))
        regulars = customers_selectors.account_list(
            ListParams(per=500, filters={"kind": "regular"})
        )
        assert len(masters) >= 1
        assert {row["kind"] for row in masters} == {"master"}
        assert "master" not in {row["kind"] for row in regulars}


def test_account_detail_serves_kind_master(seeded):
    """S21's pill beside the status pill (`AccountDetailPage.tsx` ~535) reads
    `account.kind` off `account_detail_dict`."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _masters(tenant).get()
        detail = customers_selectors.account_detail(master.id)
        assert detail["kind"] == "master"
        assert detail["account_no"] == master.account_no


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE FIXTURE'S OWN LAWS — sample tag, idempotency, no literal dates
# ══════════════════════════════════════════════════════════════════════════


def test_the_master_account_and_its_rows_carry_the_sample_tag(seeded):
    """BR-TEN-057 — the tag on the OWNING row, so BR-TEN-061's `--remove`
    sweeps this account exactly like every other seeded one."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _masters(tenant).get()
        assert master.is_sample is True
        assert (
            customers_models.Contact.objects.get(tenant_id=tenant.id, account=master).is_sample
            is True
        )
        assert (
            customers_models.Address.objects.filter(
                tenant_id=tenant.id, account=master, is_sample=False
            ).count()
            == 0
        )
        assert (
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=tenant.id, account=master, is_sample=False
            ).count()
            == 0
        )
        unit = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no=COMMON_AREA_UNIT_NO)
        assert unit.is_sample is True


def test_seeding_twice_writes_no_second_master_and_no_second_common_area(seeded):
    """BR-TEN-063 — the seed is safe to run twice. Both halves are replayed:
    metering's common area (guarded by `unit_no`) and customers' master account
    (guarded by the anchor unit already having an account, the same guard the 48
    ordinary sample accounts use)."""
    tenant, dana_user = seeded
    with tenant_ctx(tenant):
        before = _masters(tenant).count()
        metering_sample.seed_sample_records(dana_user)
        customers_sample.seed_sample_records(dana_user)
        assert _masters(tenant).count() == before
        assert (
            metering_models.Unit.objects.filter(
                tenant_id=tenant.id, unit_no=COMMON_AREA_UNIT_NO
            ).count()
            == 1
        )
        assert (
            metering_models.Unit.objects.filter(tenant_id=tenant.id, is_common_area=True).count()
            == 1
        )


def test_the_master_account_opens_on_a_date_decided_when_the_seed_runs(seeded):
    """DEF-629 / DEF-704 — **no literal dates**. A hardcoded `opened_at` is a
    clock waiting to expire: DEF-704 was filed because the demo's only payment
    plan had been silently in arrears since a typed date. BR-MET-116 names the
    clock this one reads: the build account opens on the TENANT'S today.

    Asserted as a RANGE around the run, not as a constant, so the assertion
    itself cannot become the literal it is forbidding.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        from apps.customers import seams

        master = _masters(tenant).get()
        today = seams.tenant_today()
        assert isinstance(master.opened_at, date)
        assert abs((master.opened_at - today).days) <= 1, (
            "the seeded master account must open on the tenant's own today "
            "(BR-MET-116 / BR-TEN-043), never on a date typed into the fixture"
        )


def test_the_common_area_is_not_one_of_the_builds_twenty_five_units(seeded):
    """B18 §5.4.8 draws `UNITS 25` for `CON-26-0117` and
    `apps/metering/sample_data._w6_units_for` reads the seat's own `units`
    tuple. The common area is BR-MET-116's 26th (*`Units 26` = 25 apartments +
    1 common area*) and must not join that tuple, or the drawn 25 silently
    becomes 26."""
    seat = next(
        entry for entry in metering_sample.W6_SEATS if entry["address_line"] == PREMISES_ADDRESS
    )
    declared = {unit_no for _label, unit_no in seat.get("units", ())}
    assert len(declared) == 25
    assert COMMON_AREA_UNIT_NO not in declared
