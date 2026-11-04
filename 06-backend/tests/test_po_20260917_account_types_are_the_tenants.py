# ── Trace ──────────────────────────────────────────────
# Rules:    PO ruling 2026-09-17 (*"utility can get their own account types"*),
#           which SUPERSEDES BR-CUS-094's PLATFORM posture · BR-TEN-030 (codes
#           unique per tenant, case-insensitive; a code is frozen once used) ·
#           BR-TEN-034 (a used row is not deletable; a deactivated row stops
#           being pickable) · BR-TEN-036 (a seeded row is deactivatable, never
#           deletable) · BR-CUS-094 (`government` is LEGACY, not re-labelled)
# Defects:  DEF-CUS-5647 (four live controls over a server that refused all
#           four) · DEF-CUS-5648 (the refusal key existed in no catalogue)
# Screens:  S8 Settings → Reference data → Account types
# ───────────────────────────────────────────────────────
"""What a clerk can now DO on the Account types card, asserted through the same
handler the endpoint calls.

⚠ **THE HALF THAT MATTERS IS THE ISOLATION HALF, AND IT IS NOT HERE.** RLS does
not exist on sqlite, so every case in this file asserts the SERVICE layer's own
tenant scoping — which is real and load-bearing, because it is what the test
suite and any non-Postgres path rely on. The database half (ENABLE, FORCE, both
policy expressions read back from `pg_class`/`pg_policy`, and two tenants adding
the same code) is
`tests/test_us_cus_schema_and_seed.py::test_po_20260917_rls__account_types_are_the_tenants_own_and_not_shared`,
marked `isolation` and Postgres-only. **Quoting this file as proof of isolation
would be quoting a check over a scope it silently excludes** (CLAUDE.md law 7).
"""

import pytest

from apps.customers import lookups as customer_lookups
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    api_call,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)
from tests.test_us_met_helpers import staff_actor

pytestmark = pytest.mark.django_db

HANDLER = customer_lookups.AccountTypeLookupHandler()

#: BR-CUS-094's seven selectable + `government`, kept LEGACY rather than
#: re-labelled. Derived from the model so the next ruling moves it with the code.
SEEDED = len(customer_models.AccountType.SEVEN_CATEGORIES) + len(
    customer_models.AccountType.LEGACY_CODES
)


def _codes(tenant):
    return list(
        customer_models.AccountType.objects.filter(tenant=tenant)
        .order_by("sort_order", "code")
        .values_list("code", flat=True)
    )


# ══════════════════════════════════════════════════════════════════════════
# The seed — eight rows, per tenant, in the ruled order
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__a_new_tenant_gets_its_own_eight_rows(growth_plan, identity_seam):
    """⚠ **THE COUNT USED TO BE A PLATFORM FACT AND IS NOW A PER-TENANT ONE.**

    It also closes a drift that was harmless until today: `BR-CUS-094` ratified
    seven categories on 2026-08-24 and the platform fixture went on listing
    FOUR, which did not matter while the seam was insert-missing over a global
    table that already held all eight. `customers.0019` reported that in its own
    docstring and could not fix it from its lane."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))

    for tenant in (brazos, lonestar):
        assert customer_models.AccountType.objects.filter(tenant=tenant).count() == SEEDED == 8

    # The PICKER's order is BR-CUS-094's ruled order, stored rather than
    # inferred: sorting by `code` would put Agricultural first and quietly
    # re-order a screen the PO drew.
    assert _codes(brazos) == [
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
        "government",  # legacy, at 900, behind everything selectable
    ]
    with tenant_ctx(brazos):
        government = customer_models.AccountType.objects.get(tenant=brazos, code="government")
        assert government.legacy is True, "BR-CUS-094: government is retired from new records"
        assert government.active is True, "…and changes nothing else — it stays valid"
        assert all(
            row.is_system for row in customer_models.AccountType.objects.filter(tenant=brazos)
        ), "every seeded row is is_system: deactivatable, never deletable (BR-TEN-036)"


def test_po_20260917__seeding_twice_creates_nothing_and_never_overwrites_a_rename(
    growth_plan, identity_seam
):
    """BR-TEN-012 by natural key. A tenant that renamed `Commercial` to
    `Business` keeps it through every later seed run."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customer_models.AccountType.objects.get(tenant=tenant, code="commercial")
        HANDLER.update(row, {"name": "Business"})
        assert customer_services.ensure_account_types() == 0
        assert (
            customer_models.AccountType.objects.get(tenant=tenant, code="commercial").name
            == "Business"
        )


# ══════════════════════════════════════════════════════════════════════════
# ADD — the control the PO reported as doing nothing
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__add_creates_a_row_a_clerk_can_then_use(growth_plan, identity_seam):
    """`DEF-CUS-5647`: this raised `BIZ_LOCKED` with an uncatalogued message key
    until 2026-09-17, so the clerk saw a control that did nothing and said
    nothing."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        created = HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
        assert created.tenant_id == tenant.id
        assert created.is_system is False, "a tenant-added row is deletable (BR-TEN-036)"
        assert created.active is True
        assert created.legacy is False, "a row created today is new business"
        # It lands AFTER everything already in the list, in creation order.
        assert created.sort_order == customer_models.AccountType.LEGACY_SORT_ORDER + 10
        assert _codes(tenant)[-1] == "marina_berth"

        assert HANDLER.count() == SEEDED + 1
        assert HANDLER.serialize(created)["used_by"] == 0
        # …and the resolver the account write path uses accepts it.
        field_errors = []
        resolved = customer_services._resolve_account_type("marina_berth", field_errors)
        assert field_errors == []
        assert resolved is not None and resolved.id == created.id


def test_po_20260917__a_second_tenant_does_not_see_the_first_ones_addition(
    growth_plan, identity_seam
):
    """The service-layer half of isolation — the database half is the
    Postgres-only case named in this module's docstring."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    with tenant_ctx(brazos):
        HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
    with tenant_ctx(lonestar):
        assert HANDLER.count() == SEEDED
        assert "marina_berth" not in _codes(lonestar)
        # And the SAME code is accepted here, which is the whole point of the
        # constraint moving from global to per-tenant.
        mine = HANDLER.create({"code": "marina_berth", "name": "Boat slip"})
        assert mine.name == "Boat slip"
    with tenant_ctx(brazos):
        assert (
            customer_models.AccountType.objects.get(tenant=brazos, code="marina_berth").name
            == "Marina berth"
        )


def test_po_20260917__a_duplicate_code_is_refused_with_copy(growth_plan, identity_seam):
    """BR-TEN-030, case-insensitively, and with a message key that EXISTS —
    which `DEF-CUS-5648` is entirely about."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as caught:
            HANDLER.create({"code": "ResidentiaL", "name": "Homes"})
    assert caught.value.message_key == "customers.lookups.duplicate_code"


# ══════════════════════════════════════════════════════════════════════════
# EDIT — the name always, the code only while nothing uses it
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__the_name_is_editable_and_the_code_freezes_once_used(
    growth_plan, identity_seam, monkeypatch
):
    """BR-TEN-030's second half. The code is what `rating` stores as TEXT in
    charge narrowing and in the plan/tax targeting lists, none of which this
    handler can see — so renaming a USED code would silently re-point money."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
        HANDLER.update(row, {"name": "Boat slip", "code": "boat_slip"})
        row.refresh_from_db()
        assert (row.code, row.name) == ("boat_slip", "Boat slip")

        # Now make it used. `used_by` counts three tables; the count is what the
        # rule keys off, so it is stubbed rather than building an account here.
        monkeypatch.setattr(HANDLER, "used_by", lambda _row: 3)
        HANDLER.update(row, {"name": "Marina berth"})  # the NAME still moves
        row.refresh_from_db()
        assert row.name == "Marina berth"
        with pytest.raises(errors.ValidationError) as caught:
            HANDLER.update(row, {"code": "berth"})
    assert caught.value.message_key == "customers.lookups.code_frozen_once_used"


# ══════════════════════════════════════════════════════════════════════════
# DEACTIVATE — always allowed, and it closes the picker
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__deactivating_stops_a_type_being_pickable_and_keeps_it_valid(
    growth_plan, identity_seam
):
    """BR-TEN-034. A deactivated row is not resurrected and not destroyed: every
    account already carrying it keeps it."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customer_models.AccountType.objects.get(tenant=tenant, code="industrial")
        HANDLER.set_active(row, False)
        row.refresh_from_db()
        assert row.active is False

        field_errors = []
        assert customer_services._resolve_account_type("industrial", field_errors) is None
        assert field_errors and field_errors[0]["field"] == "account_type"

        # …and a re-seed does NOT switch it back on (BR-TEN-012).
        assert customer_services.ensure_account_types() == 0
        row.refresh_from_db()
        assert row.active is False


# ══════════════════════════════════════════════════════════════════════════
# DELETE — the two locks, each with a sentence on it
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__a_seeded_row_is_never_deletable(growth_plan, identity_seam):
    """BR-TEN-036."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customer_models.AccountType.objects.get(tenant=tenant, code="residential")
        with pytest.raises(errors.BizError) as caught:
            HANDLER.delete(row)
    assert caught.value.message_key == "customers.lookups.seeded_not_deletable"
    assert caught.value.br_ref == "BR-TEN-036"


def test_po_20260917__a_used_row_is_refused_in_words_rather_than_by_the_fk(
    growth_plan, identity_seam, monkeypatch
):
    """BR-TEN-034. The three PROTECTed FKs would refuse it anyway — as a 500
    with no sentence in it, and on PostgreSQL by poisoning the transaction
    (CLAUDE.md law 14). This is the same answer with copy on it."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
        monkeypatch.setattr(HANDLER, "used_by", lambda _row: 2)
        with pytest.raises(errors.BizError) as caught:
            HANDLER.delete(row)
    assert caught.value.message_key == "customers.lookups.type_in_use"
    assert caught.value.br_ref == "BR-TEN-034"


def test_po_20260917__an_unused_tenant_row_really_is_deleted(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
        HANDLER.delete(row)
        assert HANDLER.count() == SEEDED


def test_po_20260917__used_by_counts_all_three_referencing_tables(growth_plan, identity_seam):
    """⚠ **IT COUNTED ONLY `accounts` UNTIL 2026-09-17**, which was defensible
    while the row was platform-wide and the PROTECTed FK enforced the rest
    across every tenant. Now the row is this tenant's, so every referencing row
    that can block a Delete is this tenant's too — and offering a Delete the
    database then refuses is a control that lies."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customer_models.AccountType.objects.get(tenant=tenant, code="residential")
        # The 13 seeded sub-types hang off the seeded types; residential has its
        # own, so the count is non-zero through account_subtypes ALONE, with no
        # account and no service request in the database at all.
        subtypes = customer_models.AccountSubtype.objects.filter(
            tenant=tenant, account_type=row
        ).count()
        assert subtypes > 0, "the BR-CUS-067 tree seeds sub-types under residential"
        assert HANDLER.used_by(row) == subtypes
        assert HANDLER.serialize(row)["used_by"] == subtypes


# ══════════════════════════════════════════════════════════════════════════
# The picker (task 6) — every active row, not a tuple
# ══════════════════════════════════════════════════════════════════════════
def test_po_20260917__the_request_picker_offers_a_row_the_tenant_added(growth_plan, identity_seam):
    """⚠ **`DEF-CUS-5647`'s second half.**
    `service_request_categories` read the live rows into a dict and then
    iterated `AccountType.SEVEN_CATEGORIES` over it, so a row outside that tuple
    could not appear however active it was — the tenant's own addition was
    dropped in silence."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        HANDLER.create({"code": "marina_berth", "name": "Marina berth"})
    body = _categories(tenant)
    codes = [row["code"] for row in body["selectable"]]
    assert codes == [
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
        "marina_berth",  # appended, in the order the tenant created it
    ]
    assert [row["code"] for row in body["legacy"]] == ["government"]


def test_po_20260917__the_request_picker_drops_a_deactivated_row(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customer_models.AccountType.objects.get(tenant=tenant, code="municipal")
        HANDLER.set_active(row, False)
    assert "municipal" not in [r["code"] for r in _categories(tenant)["selectable"]]


def _categories(tenant):
    """`GET /service-requests/categories`, through the real DRF stack.

    ⚠ **TWO STAND-INS FAILED HERE BEFORE THIS ONE, AND BOTH FAILURES ARE WORTH
    THE NOTE (hard-won law 7: exercise it the way it really runs).** A
    `SimpleNamespace` request is refused outright — DRF's `Request.__init__`
    asserts its argument is an `HttpRequest` — and a `SimpleNamespace` USER gets
    past that and then answers **401**, whose body has no `selectable` key at
    all, so the case failed on a `KeyError` that said nothing about categories.
    A real staff row and `api_call` are what the wired stack actually has."""
    from apps.customers import service_request_api

    actor = staff_actor(tenant, "system_admin", f"walk@{tenant.subdomain}.test")
    response = api_call(
        service_request_api.service_request_categories,
        "get",
        f"/api/{tenant.subdomain}/service-requests/categories",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
    )
    assert response.status_code == 200, (response.status_code, response.data)
    return response.data


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-17 (12-governance/02-decision-log.md) + BR-CUS-1079
# generated: 2026-09-17 by the account-types lane
# checklist: A✔ B✔ C✔ D✔ E=covered by the browser walkthrough (10-scripts/po_20260917_account_types_walkthrough.mjs) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: RLS cannot be exercised here — sqlite has none — so the database half is the `isolation`-marked case in tests/test_us_cus_schema_and_seed.py and this file says so in its docstring rather than implying coverage it does not have
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
