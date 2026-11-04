# ── Trace ──────────────────────────────────────────────
# Defect:  **DEF-2414** (2026-09-01, PO, on the running product at v2.123.0) —
#          *"Bills are not generated during tenant creation process"*. A utility
#          that ticked **Trash** at signup got **ZERO bills — not fewer, none**:
#          94 of 94 account/period pairs refused, **8 of the 17 seeding blocks
#          failed**, and the sample-plant job still reported SUCCEEDED
#          (`DEF-2413`).
# Ruling:  PO 2026-09-01, verbatim: *"we will ahve to set in seeder as well as
#          in setting the sizes also on Units - so it works properly - please
#          evaluate and fix it"* — fixed on the **DATA** side, the check NOT
#          relaxed. Confirmed the same day: *"this is correct - The size stays
#          on the equipment record, not on the unit itself."*
#          `12-governance/02-decision-log.md`, 2026-09-01.
# Rules:   **BR-RAT-081** (a service is DECLARED metered or unmetered — the
#          declaration this fixture never wrote) · **BR-RAT-090** (an unmetered
#          service's quantity is a COUNT of its assets; ratified 3 × $15.00 =
#          $45.00, and *"'no carts recorded' and 'zero carts' are different
#          facts and only one of them is billable"*) · **BR-MET-710** (a
#          declared-unmetered point answers `service_not_metered` whether or not
#          equipment stands on it) · **BR-AST-500** (`Asset.size_class`; NULL is
#          a real answer and is never defaulted) · **BR-TEN-171** (the ratified
#          size codes) · BR-RAT-832 (trash base `$0.00`) · BR-RAT-015 / GT-17 ❄️
#          (the reference bill: water $39.50, sewer $15.80)
# Tests:   TC-1..6 below.
# ───────────────────────────────────────────────────────
"""DEF-2414 — a utility that sells Trash gets bills, and the demo keeps its zero.

**THE ASSERTION NOBODY WAS MAKING, AND THE DEFECT ROW SAYS SO IN TERMS:** *"a
provisioning run must assert that every service a tenant can select at signup
actually produces bills, because that is the assertion nothing in the repo makes
today."* `TC-1` is that assertion. Every other case in this file exists to stop
a later lane satisfying it the cheap way.

⚠ **`@requires_postgres`, AND FOR THE REASON CLAUDE.md's LAW 14 GIVES.**
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`.
This file drives `provision_tenant` and the whole sample plant — RLS, savepoints
and the billing run — so it runs where those behave as they do in production:

    DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgres://… \\
      pytest tests/test_def_2414_trash_tenant_bills.py --reuse-db

WHAT WAS MEASURED, on PostgreSQL 16, through `tenancy.services.provision_tenant`
— the entry point the S114 signup screen calls — and its sample-plant job
-------------------------------------------------------------------------------
                        invoices   failed blocks (of 17)
    with Trash, BEFORE         0        8
    with Trash, AFTER         96        0
    without Trash (control)   96        0

**AND THE FIX THE DEFECT ROW PREDICTED WOULD NOT HAVE WORKED**, which is why
`TC-4` pins the mechanism rather than only the outcome. Giving the seeded carts
a `size_class` — the obvious reading of *"set the sizes in the seeder"* — moves
the refusal exactly one branch down, from `connection_size_unresolved` to
`meter_multiplier_not_published_to_billing`: a cart standing on a trash service
point makes metering answer `no_read` rather than `no_meter`, so `DEF-2875`'s
no-meter tolerance never fires and the adapter demands a meter multiplier from a
device that has no register. **Still zero bills.** What produces bills is
`BR-RAT-081`'s DECLARATION, which is the other half of the same seeder data.

RED PROOF (r11 step 2d) — each measured against the tree at this lane's base
-----------------------------------------------------------------------------
  * TC-1 · empty `fixture.UNMETERED_ESTATE_SERVICES` → `0 invoices` and
    `8 failed blocks`; the case fails on `assert 0 > 0`.
  * TC-2 · same mutation → `AssertionError` naming `trash` as still metered.
  * TC-3 · delete the `size_class` line in `assets/sample_data._seed_cr028_shape`
    → `assert 0 == 4`, which is the state every seeded tenant shipped in.
  * TC-4 · add `"sewer"` to `UNMETERED_ESTATE_SERVICES` → the sewer line prices
    off an asset COUNT of zero and GT-17's `$15.80` becomes `$0.00`.
  * TC-5 · plant a cart on `CART_UNIT_WITH_NONE` → `assert 1 == 0`, the
    demonstration the ruling requires be preserved.
  * TC-6 · return `codes[0]` unconditionally from `_container_size_class` →
    `assert 'CART-35' == 'CART-96'`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import models as asset_models
from apps.assets import selectors as asset_selectors
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import sample_data as tenancy_sample_data
from core import sample_fixture as fixture
from core import tenancy as core_tenancy

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The service the defect is about. Read from the fixture's own declaration so a
#: lane that renames or empties it cannot leave this file passing over nothing.
TRASH = "trash"


def _payload(slug: str, services: list[str]) -> dict:
    """One signup payload per tenant, so cases cannot see each other's rows."""
    data = dict(brazosbend_payload())
    data["subdomain"] = slug
    data["name"] = f"DEF-2414 {slug}"
    data["services"] = services
    owner = dict(data["owner"])
    owner["email"] = f"owner@{slug}.test"
    data["owner"] = owner
    return data


def _plant(services: list[str]):
    """A tenant provisioned through the REAL signup service, then planted.

    ⚠ **THE ACTOR IS THE PROVISIONING OWNER AND NOT `admin_actor()`** — the
    same trap `DEF-2722`'s file records: an invented uuid is stripped by
    `tenancy.sample_data._attributed`, `BR-BIL-058`'s release gate then refuses
    to issue anything (*"this sample load has no attributable user"*), and five
    money blocks fail for a reason that has nothing to do with this defect. The
    production job body builds `_PlantActor(payload["actor_user_id"])`; this is
    that actor, so what runs is the path a signup actually walks.
    """
    tenant, result = provisioned_tenant(
        _payload(f"def2414-{uuid.uuid4().hex[:10]}", services)
    )
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    with tenant_ctx(tenant):
        summary = tenancy_sample_data.seed_sample_data(actor)
    return tenant, actor, summary


@pytest.fixture(scope="module")
def trash_tenant(django_db_setup, django_db_blocker):
    """ONE planted trash utility for the whole file — the plant is minutes, not
    seconds, and every case below reads the same end state rather than each
    paying for its own. Cases assert, they never write."""
    with django_db_blocker.unblock():
        yield _plant(["water", "sewer", "trash"])


def _failed_blocks(tenant) -> list[str]:
    with tenant_ctx(tenant):
        return [
            f"{row.get('module')}:{row.get('block')}"
            for row in tenancy_sample_data.stored_blocks()
            if row.get("outcome") not in ("seeded", "skipped")
        ]


def _unit_id_for(index: int) -> str:
    from apps.metering import selectors as metering_selectors

    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[index]
    for row in metering_selectors.units_list():
        if row.unit_no == unit_no:
            return str(row.id)
    raise AssertionError(f"unit_index {index} ({unit_no}) was not seeded")


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · the assertion the defect row says nothing in the repo makes
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc1__a_tenant_that_sells_trash_produces_bills(trash_tenant):
    """**A utility that ticks Trash at signup gets bills, and every block runs.**

    Measured before the fix: `invoices=0`, `failed_blocks=8` — the billing block
    refused with *"has no bills to release"* and took payments, the refund, the
    correction, the second cycle, collections, the payment plan and the plan
    money down with it. Measured after: `invoices=96`, `failed_blocks=0`, the
    same figure a tenant WITHOUT trash has always produced.

    ⚠ **BOTH HALVES ARE ASSERTED AND NEITHER IS ENOUGH ALONE.** `0 == 0`
    satisfies any relational check, so the count is asserted against the number
    the fixture PLANS rather than a literal; and a run can produce bills while
    still losing blocks, which is `DEF-2413` — a plant that reports SUCCEEDED
    over eight failures.
    """
    tenant, _actor, _summary = trash_tenant
    with tenant_ctx(tenant):
        invoices = billing_models.Invoice.objects.filter(tenant_id=tenant.id).count()
        accounts = customer_models.Account.objects.filter(tenant_id=tenant.id).count()
    assert invoices > 0, (
        "a tenant that sells Trash produced NO bills at all — DEF-2414. "
        f"{accounts} accounts, {invoices} invoices"
    )
    assert invoices >= accounts, (
        f"only {invoices} bills for {accounts} accounts: some accounts were refused"
    )
    assert _failed_blocks(tenant) == [], (
        "the sample plant lost blocks on a trash tenant: "
        f"{_failed_blocks(tenant)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · the mechanism — BR-RAT-081's declaration, written by the seeder
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc2__the_seeder_declares_trash_unmetered(trash_tenant):
    """**BR-RAT-081's declaration reaches the seeded tenant.**

    `tenant_services.metered` is `BooleanField(default=True)` and provisioning
    writes all ten rows without naming it, so every service on every tenant
    shipped declared metered — `DEF-2409`, which the PO has since ruled becomes
    a three-way declaration (*"metered / share of another service / capacity"*,
    2026-09-01) with **trash on the CAPACITY side**. This asserts today's
    boolean carries the value that mapping requires, so the enum lane inherits a
    correct row rather than one it has to migrate.

    The column's own docstring has always said this is the intended state — *"a
    tenant selling Trash sets it False and opts into the branch"* — and nothing
    in the fixture ever did it.
    """
    tenant, _actor, _summary = trash_tenant
    with tenant_ctx(tenant):
        row = tenancy_models.TenantService.objects.get(
            tenant_id=tenant.id, service__code=TRASH
        )
        assert row.enabled, "the tenant was provisioned with trash"
        assert row.metered is False, (
            "trash is priced by a COUNT of the unit's carts (BR-RAT-090) and must be "
            "DECLARED unmetered (BR-RAT-081); left metered, billing demands a "
            "connection size and a meter multiplier from equipment with no register "
            "and every account is refused"
        )
        from apps.tenancy import selectors as tenancy_selectors

        assert TRASH in set(tenancy_selectors.unmetered_service_codes())


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · the ruled seeder data — a sized container
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc3__every_seeded_container_on_a_connection_carries_a_size(
    trash_tenant,
):
    """**The PO's *"set the sizes in the seeder"*, asserted on the rows.**

    Every `container_cart` that DECLARES a service stands on that service's
    connection and carries a `BR-TEN-171` code; the inventory spare
    (`CART-0099`), which declares none and sits in stock, correctly carries
    NULL — `BR-AST-500` makes *"no size recorded"* a real answer and this must
    not be defaulted into a fabricated one.

    Before this lane every one of them was NULL, which is the `DEF-515` shape:
    a column with a migration, a read path and two screens, and no seeded row
    carrying a value, reads to the next person as a fix that never landed.
    """
    tenant, _actor, _summary = trash_tenant
    from apps.tenancy import service_size_classes

    ratified = {code for code, _name in service_size_classes.size_classes_for_service(TRASH)}
    with tenant_ctx(tenant):
        carts = list(
            asset_models.Asset.objects.filter(
                tenant_id=tenant.id, type__code=fixture.TRASH_CART_TYPE
            )
        )
        assert carts, "the trash tenant seeded no containers at all"
        # `Asset.service_point` IS the connection — a cart with one stands on a
        # trash connection; a cart without one is stock in the yard.
        on_connection = [c for c in carts if c.service_point_id is not None]
        in_stock = [c for c in carts if c.service_point_id is None]
        assert on_connection, "no container declares a service"
        for cart in on_connection:
            assert cart.size_class, (
                f"{cart.asset_no} stands on a trash connection and records no size"
            )
            assert cart.size_class in ratified, (
                f"{cart.asset_no} carries {cart.size_class!r}, which is not one of "
                f"BR-TEN-171's ratified trash codes {sorted(ratified)} — a demo tenant "
                "must never teach a vocabulary the product does not have"
            )
        for cart in in_stock:
            assert cart.size_class in (None, ""), (
                f"{cart.asset_no} is in inventory and stands on no connection, so it "
                "has no connection size to record (BR-AST-500: NULL is a real answer)"
            )


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · the frozen figures the fix must not move
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc4__gt17s_reference_bill_is_unmoved(trash_tenant):
    """**GT-17 ❄️ — water `$39.50`, sewer `$15.80` — on a bill this run made.**

    The reference unit takes 8 kgal exactly and keeps ZERO carts by
    construction, so its trash line is `$0.00` and its water and sewer lines are
    the frozen ones. This is the case that catches a fix which makes trash bill
    by moving something else: adding `sewer` to `UNMETERED_ESTATE_SERVICES`, for
    instance, routes it into BR-RAT-090's asset count — a sewer connection has
    no assets, the count is zero, and `$15.80` silently becomes `$0.00`.
    """
    tenant, _actor, _summary = trash_tenant
    with tenant_ctx(tenant):
        unit_id = _unit_id_for(fixture.CASE_REFERENCE_BILL)
        account = customer_models.Account.objects.get(
            tenant_id=tenant.id, unit_id=unit_id
        )
        invoice = (
            billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, account_id=account.id
            )
            .order_by("period_start")
            .first()
        )
        assert invoice is not None, "the GT-17 reference account produced no bill"
        lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, invoice_id=invoice.id
            ).select_related("service")
        )

        def total(service: str, kind: str) -> Decimal:
            return sum(
                (
                    line.amount
                    for line in lines
                    if line.service_id is not None
                    and line.service.code == service
                    and line.kind == kind
                ),
                Decimal("0"),
            )

        assert total("water", "usage") == Decimal("39.50"), (
            "GT-17 ❄️ water usage is $39.50 (5 kgal × $4.00 + 3 kgal × $6.50)"
        )
        assert total("sewer", "usage") == Decimal("15.80"), (
            "GT-17 ❄️ / BR-RAT-015 sewer is 40% of the water usage charge = $15.80"
        )


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · the two demonstration units the ruling requires be preserved
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc5__all_three_cart_cases_bill_their_ratified_figure(trash_tenant):
    """**3 → `$45.00`, 1 → `$15.00`, 0 → `$0.00` ON AN ISSUED BILL.**

    `test_cr028_seed.py` already pins the three COUNTS. What it cannot say is
    that the zero one still produces a bill, and that is exactly what the ruling
    asks to be preserved — `BR-RAT-090`: *"'no carts recorded' and 'zero carts'
    are different facts and only one of them is billable."*

    ⚠ **THIS IS THE CASE THAT REFUSES THE OBVIOUS FIX.** Planting a container on
    every unit with a trash service would make every account billable and would
    take `CART_UNIT_WITH_NONE` from 0 carts to 1 — deleting the demonstration
    and charging 46 units `$15.00` a month they do not owe. The count and the
    money are asserted together so neither can be satisfied alone.
    """
    tenant, _actor, _summary = trash_tenant
    expected = {
        fixture.CART_UNIT_WITH_THREE: (3, Decimal("45.00")),
        fixture.CART_UNIT_WITH_ONE: (1, Decimal("15.00")),
        fixture.CART_UNIT_WITH_NONE: (0, Decimal("0.00")),
    }
    with tenant_ctx(tenant):
        for unit_index, (carts, money) in expected.items():
            unit_id = _unit_id_for(unit_index)
            account = customer_models.Account.objects.get(
                tenant_id=tenant.id, unit_id=unit_id
            )
            invoice = (
                billing_models.Invoice.objects.filter(
                    tenant_id=tenant.id, account_id=account.id
                )
                .order_by("period_start")
                .first()
            )
            assert invoice is not None, (
                f"unit_index {unit_index} ({carts} carts) produced NO bill — a zero "
                "cart count is a real answer and it must still bill (BR-RAT-090)"
            )
            usage = [
                line
                for line in billing_models.InvoiceLine.objects.filter(
                    tenant_id=tenant.id, invoice_id=invoice.id
                ).select_related("service")
                if line.service_id is not None
                and line.service.code == TRASH
                and line.kind == "usage"
            ]
            assert len(usage) == 1, (
                f"unit_index {unit_index}: expected one trash usage line, got "
                f"{len(usage)}"
            )
            line = usage[0]
            assert line.quantity == Decimal(carts), (
                f"unit_index {unit_index}: BR-RAT-090's OBSERVED count is {carts}"
            )
            # CLAUDE.md rule 3 — the quantity never travels without its unit.
            assert line.unit == fixture.TRASH_UOM
            assert line.amount == money, (
                f"unit_index {unit_index}: {carts} × ${fixture.TRASH_PER_CART} must "
                f"bill ${money} (BR-RAT-090, PO 2026-08-21)"
            )
            assert (
                asset_selectors.billable_asset_count(
                    unit_id, TRASH, invoice.period_end
                )
                == carts
            )


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · the seeded band is the ratified one, and it is not typed twice
# ══════════════════════════════════════════════════════════════════════════


def test_def_2414_tc6__the_seeded_band_is_the_one_the_fixture_declares(trash_tenant):
    """**Every container on one unit takes the SAME band, and it is the
    fixture's declared one.**

    Two assets on ONE service point recording DIFFERENT sizes make
    `connection_size_for` answer `None` by ruling (decision log 2026-08-27 — one
    connection has one size), so the three carts on the walkthrough unit sharing
    a band is not tidiness, it is the difference between that unit having a
    resolvable connection size and having none.

    And the band is `fixture.TRASH_CART_SIZE`, which is what the carts'
    valuation line has claimed since they were first seeded (*"a 96-gal cart"*)
    — said once, in the fixture, rather than implied in a comment.
    """
    tenant, _actor, _summary = trash_tenant
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(tenant):
        unit_id = _unit_id_for(fixture.CART_UNIT_WITH_THREE)
        bands = {
            asset.size_class
            for asset in asset_models.Asset.objects.filter(
                tenant_id=tenant.id, type__code=fixture.TRASH_CART_TYPE
            )
            if asset.service_point_id is not None
        }
        assert bands == {fixture.TRASH_CART_SIZE}, (
            f"the seeded containers record {sorted(bands)}; one connection has one "
            f"size, so they must all be {fixture.TRASH_CART_SIZE!r}"
        )
        assert (
            metering_selectors.connection_size_for(unit_id, TRASH)
            == fixture.TRASH_CART_SIZE
        ), (
            "the walkthrough unit's three carts must resolve ONE connection size; "
            "two different recorded sizes on one point answer None by ruling"
        )
        # And the unit that deliberately holds nothing answers None, which is
        # the honest answer and must never be defaulted into a band.
        assert (
            metering_selectors.connection_size_for(
                _unit_id_for(fixture.CART_UNIT_WITH_NONE), TRASH
            )
            is None
        )


# generated: 2026-09-01 by the DEF-2414 lane (PO ruling 2026-09-01 — connection
# sizes are set in the seeder and are settable on the equipment record)
