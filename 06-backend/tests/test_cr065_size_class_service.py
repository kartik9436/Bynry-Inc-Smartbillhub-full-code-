# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2385 — a rate schedule for ONE service offers every OTHER
#           service's size classes, so the Fire schedule prices *Electric
#           CT-metered*.   Screens: S9 / r10 RAT-03 · CHG-02 · S8 SET-04.sizes
# Change:   CR-065 tasks A1–A4 and D1 — a size class names the utility service
#           it belongs to, seeded from the ratified map, backfilled for the
#           tenants that already exist, served, filterable, and editable by a
#           tenant on Settings.
# Ruling:   PO 2026-09-02, verbatim, sent with a screenshot of the Fire rate
#           schedule's minimum-bill step listing Electric 3φ 400A, Electric
#           CT-metered, Gas 250 CFH (residential) and Gas 1,000+ CFH among the
#           seven fire lines: *"This is where we are setting rates for fire  you
#           should show only capacity for fire . in Setting a capacity needs to
#           tags to utility services ."*
# Rules:    BR-TEN-078 (SUPERSEDED for this one list by the ruling above — it
#           had named `service_size_classes` unscoped, twice) · BR-TEN-170 (same
#           clause, same supersession) · BR-TEN-171 (the ratified rows, keyed by
#           service since they were written) · BR-TEN-071 (seed data never
#           deletes, which is why an untagged row must keep working) ·
#           BR-TEN-012 (insert-if-absent — a tenant's own row is never
#           rewritten) · BR-TEN-026 (a service must be ENABLED for this tenant)
# Note:     Written BEFORE the fix and shown RED on the shipped build — hard-won
#           law 7. The RED output of each case is quoted in the lane report.
# ───────────────────────────────────────────────────────
"""CR-065 — a size class knows which utility service it belongs to.

**THE ACCEPTANCE CASE IS THE PRODUCT OWNER'S OWN SCREENSHOT** and it is
`test_cr065_the_fire_schedule_offers_six_fire_sizes_and_nothing_else`: ask the
size-class list for `fire` and get **six** rows, none of them electric and none
of them gas. On the shipped build that call returned **sixty**.

⚠ **IT ASKED FOR SEVEN UNTIL 2026-09-03, AND THE NUMBER MOVED FOR A REASON THAT
HAS NOTHING TO DO WITH THIS CR.** PO 2026-09-03: *"remove private hydrants from
list"*. `HYD` "Private hydrant" left fire's ratified list — a hydrant is an
asset, not a utility-service size — so fire is six and the platform total is
**fifty-nine**. Nothing about the TAGGING this file tests changed; only how many
rows carry the `fire` tag.

WHY THE OTHER CASES EXIST, AND THEY ARE NOT PADDING
-----------------------------------------------------
Two of them guard the halves of this change that could quietly take something
away from a utility that already exists:

  · **an UNTAGGED row lists everywhere.** `BR-TEN-071` forbids deleting a
    tenant's own row, so a size class a utility added last week — which nobody
    has tagged and nobody can tag on its behalf — must keep appearing on every
    service's picker. A filter that dropped it would make a row they own
    invisible, which is worse than an untidy list.

  · **the backfill fills PLATFORM rows only.** It is keyed on `is_system` AND on
    a code the ratified map knows, so a tenant's own row keeps its blank tag and
    a WITHDRAWN seeded code (`E-3P` *"Electric 3φ"*, dropped from the ratified
    list on 2026-08-27 and deleted from nobody) stays untagged and stays
    visible. Nobody has ruled what `E-3P` is now, and inventing an answer is
    what this case exists to catch.

⚠ **THE TAG IS THE PLATFORM'S FACT AND THE SEED DOES NOT ASK ABOUT
ENABLEMENT.** `FL-2` is fire's size whether or not this utility sells fire, so a
tenant that signed up for water alone still receives fire's six rows correctly
tagged — they simply never reach a picker, because no picker asks about a service
they do not sell. The WRITE is the opposite and `test_..._refuses_a_service_this
_tenant_does_not_sell` pins it: a person naming a service must name one this
tenant has ENABLED (`BR-TEN-026`).
"""

import pytest
from django.apps import apps as django_apps

from apps.tenancy import models, selectors, service_size_classes as sizes, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _codes(rows):
    return [row["code"] for row in rows]


def _entry(tenant, code):
    return models.MeterSizeClass.objects.get(tenant=tenant, code=code)


# ── A2 · the ratified map's key finally travels ──────────────────────────────
def test_cr065_every_seeded_size_class_names_its_service():
    """THE RED CASE FOR A2. On the shipped build `seed_entries()` returned
    `{code, name}` and this KeyError'd on all sixty rows — the map has been keyed
    by service since it was written and the seeding path threw the key away."""
    rows = sizes.seed_entries()
    assert len(rows) == 64  # 59 until CR-080 2026-09-07; 60 until PO 2026-09-03
    assert all(row["service_code"] for row in rows), "no row may seed untagged"
    assert {row["service_code"] for row in rows} <= set(sizes.SERVICE_ORDER)


def test_cr065_the_fiftynine_split_by_service_the_way_the_ratified_map_does():
    """The count per service, so a row moving between services goes RED rather
    than quiet. Sewer is absent because it is ruled to have NONE (BR-RAT-015 —
    a share of the water usage charge, reading no register of its own).

    ⚠ **FIRE IS SIX AND WAS SEVEN** — PO 2026-09-03, *"remove private hydrants
    from list"*. Every other count on this table is exactly as it was, which is
    the assertion that matters here: a withdrawal from one service must not move
    another."""
    counts: dict[str, int] = {}
    for row in sizes.seed_entries():
        counts[row["service_code"]] = counts.get(row["service_code"], 0) + 1
    assert counts == {
        "electric": 6,
        "water": 9,
        "gas": 4,
        "trash": 7,
        "storm_water": 5,
        "solar": 10,
        "broadband": 3,
        "thermal_heat": 8,  # 3 until CR-080 (PO 2026-09-07)
        "battery": 6,
        "fire": 6,  # 7 until PO 2026-09-03 withdrew `HYD`
    }
    assert sum(counts.values()) == 64  # 59 until CR-080
    assert "sewer" not in counts


def test_cr065_the_service_code_is_the_code_never_a_display_name():
    """`thermal_heat`, not *"Thermal/Heat"*. DEF-972 is this exact confusion one
    level up, where this module first wrote `thermal` — a code no service has —
    and the lookup raised KeyError on a key that was self-consistently wrong."""
    thermal = {r["service_code"] for r in sizes.seed_entries() if r["code"].startswith("TH-")}
    assert thermal == {"thermal_heat"}
    catalog = set(models.Service.objects.values_list("code", flat=True))
    assert {r["service_code"] for r in sizes.seed_entries()} <= catalog


def test_cr065_the_fixture_mirrors_the_ratified_map_tag_included():
    """The fixture is a MIRROR, not the source (BR-TEN-171). `test_cr039_e20`
    already refuses drift on the whole row; this names the field CR-065 added so
    a reader of THIS file can see which half is being asserted."""
    fixture = services._load_seed_fixture()
    assert [row.get("service_code") for row in fixture["service_size_classes"]] == [
        row["service_code"] for row in sizes.seed_entries()
    ]


# ── A4 · a new tenant is seeded tagged ───────────────────────────────────────
def test_cr065_a_new_tenants_seeded_rows_carry_their_service(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    assert _entry(tenant, "FL-2").service.code == "fire"
    assert _entry(tenant, "E-CT").service.code == "electric"
    assert _entry(tenant, "W-2").service.code == "water"
    assert _entry(tenant, "SOL-P4").service.code == "solar"


def test_cr065_the_seed_tags_a_service_this_tenant_does_not_sell(growth_plan, identity_seam):
    """The platform's fact, not the tenant's. Brazos Bend signs up for electric
    and water; `fire` is present-but-off in `tenant_services`, and fire's six
    rows still arrive correctly tagged. Routing the SEED through the enablement
    check would have refused most of the fixture for every tenant alive."""
    tenant, _ = provisioned_tenant()
    assert not models.TenantService.objects.get(tenant=tenant, service__code="fire").enabled
    # `HYD` used to be the row asserted here; it left the seed by PO ruling on
    # 2026-09-03, so a fire DIAMETER carries the case now. A new tenant must not
    # receive `HYD` at all — asserted below rather than assumed.
    assert _entry(tenant, "FL-12").service.code == "fire"
    assert not models.MeterSizeClass.objects.filter(tenant=tenant, code="HYD").exists(), (
        "PO 2026-09-03 withdrew `HYD` from fire's size list, so no NEW tenant "
        "may be seeded with it. BR-TEN-071 keeps it for tenants that already "
        "have it; this asserts the seed, not a deletion."
    )


def test_cr065_the_list_publishes_the_service_as_code_and_never_as_a_bare_id(
    growth_plan, identity_seam
):
    """`{id, code}` — the id is what an edit sends back, the code is what a
    person recognises. B14 rule 31 forbids a database id being what a field
    SHOWS, and `null` is published as null rather than omitted, because ABSENT
    (this list has no scope) and NULL (nobody has said) are different facts."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {r["code"]: r for r in selectors.lookup_page("service_size_classes", None)}
    assert rows["FL-2"]["service"] == {
        "id": str(_entry(tenant, "FL-2").service_id),
        "code": "fire",
    }


# ── B1 · THE PRODUCT OWNER'S SCREENSHOT ──────────────────────────────────────
def test_cr065_the_fire_schedule_offers_six_fire_sizes_and_nothing_else(
    growth_plan, identity_seam
):
    """**THE ACCEPTANCE CASE.** The PO photographed the Fire rate schedule's
    minimum-bill step listing Electric 3φ 400A, Electric CT-metered, Gas 250 CFH
    (residential) and Gas 1,000+ CFH among the fire lines. On the shipped
    build this call answered SIXTY rows and there was no filter to pass.

    ⚠ **SIX, NOT SEVEN — PO 2026-09-03, *"remove private hydrants from list"*.**
    The screenshot that raised this CR showed seven fire rows; the seventh was
    `HYD` "Private hydrant" and the PO has since removed it, so the schedule a
    clerk sees offers the six line diameters and nothing else."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        offered = _codes(selectors.lookup_page("service_size_classes", None, "fire"))
    assert offered == ["FL-10", "FL-12", "FL-2", "FL-4", "FL-6", "FL-8"]
    assert len(offered) == 6
    assert "HYD" not in offered, (
        "a private hydrant is an asset, not a fire-service size (PO 2026-09-03). "
        "Offering it here would put $25.00 a month back on a rate schedule."
    )
    # the four rows in the screenshot, by name, gone
    assert "E-3P-400" not in offered and "E-CT" not in offered
    assert "G-250" not in offered and "G-1000" not in offered


def test_cr065_every_service_gets_its_own_sizes(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        counts = {
            code: len(selectors.lookup_page("service_size_classes", None, code))
            for code in sizes.SERVICE_ORDER
        }
    assert counts == {
        "electric": 6,
        "water": 9,
        "gas": 4,
        "sewer": 0,
        "trash": 7,
        "storm_water": 5,
        "solar": 10,
        "broadband": 3,
        "thermal_heat": 8,  # 3 until CR-080 (PO 2026-09-07)
        "battery": 6,
        "fire": 6,  # 7 until PO 2026-09-03 withdrew `HYD`
    }


def test_cr065_an_untagged_row_is_offered_on_every_service(growth_plan, identity_seam):
    """**THE ROW A UTILITY OWNS AND NOBODY HAS TAGGED.** `BR-TEN-071` forbids
    deleting a tenant's own row, so `NULL` cannot mean *"belongs to nothing"* —
    it means *"nobody has said"*, and such a row keeps appearing everywhere,
    exactly as all sixty did before this change (fifty-nine since the
    private hydrant left fire's list on 2026-09-03)."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.create_lookup_entry(
            admin_actor(), "service_size_classes", {"code": "FL-14", "name": 'Fire line 14"'}
        )
        for code in ("fire", "water", "electric", "battery"):
            assert "FL-14" in _codes(selectors.lookup_page("service_size_classes", None, code))


def test_cr065_an_unscoped_list_ignores_the_filter_rather_than_refusing(
    growth_plan, identity_seam
):
    """`f.service_code` on a list with no scope is a picker asking a question
    that list has no rows to exclude on — the honest answer is every row, the
    same posture `uoms_for_service` takes for a service code it cannot name."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        every = _codes(selectors.lookup_page("payment_methods", None))
        filtered = _codes(selectors.lookup_page("payment_methods", None, "fire"))
    assert filtered == every and len(every) > 0


# ── B3 · a tenant tags a size they added ─────────────────────────────────────
def test_cr065_a_tenant_can_tag_a_size_they_added(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        created = services.create_lookup_entry(
            admin_actor(),
            "service_size_classes",
            {"code": "W-8", "name": 'Water 8"', "service": "water"},
        )
        assert created["service"]["code"] == "water"
        assert "W-8" in _codes(selectors.lookup_page("service_size_classes", None, "water"))
        assert "W-8" not in _codes(selectors.lookup_page("service_size_classes", None, "fire"))


def test_cr065_a_tag_can_be_set_and_cleared_on_an_existing_row(growth_plan, identity_seam):
    """An explicit `null` CLEARS the tag — a real act a person performs on the
    form — and an OMITTED key leaves the stored tag alone."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = services.create_lookup_entry(
            admin_actor(), "service_size_classes", {"code": "W-9", "name": 'Water 9"'}
        )
        assert row["service"] is None
        tagged = services.update_lookup_entry(
            admin_actor(), "service_size_classes", row["id"], {"service": "water"}
        )
        assert tagged["service"]["code"] == "water"
        renamed = services.update_lookup_entry(
            admin_actor(), "service_size_classes", row["id"], {"name": 'Water 9 inch'}
        )
        assert renamed["service"]["code"] == "water", "an omitted key leaves the tag alone"
        cleared = services.update_lookup_entry(
            admin_actor(), "service_size_classes", row["id"], {"service": None}
        )
        assert cleared["service"] is None


def test_cr065_refuses_a_service_this_tenant_does_not_sell(growth_plan, identity_seam):
    """BR-TEN-026. Brazos Bend has fire present-but-off, so a person naming it
    is refused — the same refusal as naming `unicorn`, deliberately, because
    which services a utility sells is not something the error should publish."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(),
                "service_size_classes",
                {"code": "FL-16", "name": 'Fire line 16"', "service": "fire"},
            )
    assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP
    assert {fe["field"] for fe in excinfo.value.field_errors} == {"service"}
    assert not models.MeterSizeClass.objects.filter(tenant=tenant, code="FL-16").exists()


def test_cr065_refuses_a_service_nobody_has(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(),
                "service_size_classes",
                {"code": "X-1", "name": "Unicorn 1", "service": "unicorn"},
            )
    assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP


# ── A3 · the backfill, for the tenants that already exist ────────────────────
def _run_backfill(direction="forward"):
    """Run tenancy/0035's own function against the LIVE model registry.

    The migration module's name starts with a digit, so it is loaded by path
    rather than imported — and it is the real function, not a copy, because a
    test that re-implemented the backfill would prove only that two copies
    agree.
    """
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "apps/tenancy/migrations/0035_cr065_size_class_service_backfill.py"
    )
    spec = importlib.util.spec_from_file_location("m0035_cr065", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = module.backfill if direction == "forward" else module.unbackfill
    fn(django_apps, None)
    return module


def test_cr065_the_backfill_fills_platform_rows_and_never_a_tenants_own(
    growth_plan, identity_seam
):
    """**THE CASE THAT PROTECTS A UTILITY THAT ALREADY EXISTS.** The tenant is
    put back into the pre-CR-065 state — every tag cleared, plus one row the
    tenant created and one WITHDRAWN seeded code — and the migration's own
    function is run over it."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.create_lookup_entry(
            admin_actor(), "service_size_classes", {"code": "FL-14", "name": 'Fire line 14"'}
        )
        # `E-3P` is the real case: seeded before 2026-08-27, withdrawn from the
        # ratified list that day, and deleted from nobody (BR-TEN-071).
        models.MeterSizeClass.objects.create(
            tenant=tenant, code="E-3P", name="Electric 3φ", is_system=True, active=True
        )
        models.MeterSizeClass.objects.filter(tenant=tenant).update(service=None)

        _run_backfill()

        assert _entry(tenant, "FL-2").service.code == "fire", "a platform row is filled"
        assert _entry(tenant, "E-CT").service.code == "electric"
        assert _entry(tenant, "FL-14").service_id is None, "a tenant's own row is NEVER touched"
        assert _entry(tenant, "E-3P").service_id is None, "a withdrawn code stays unruled"
        # and the untouched pair still lists everywhere, which is the point of
        # leaving them alone rather than guessing.
        for code in ("fire", "water"):
            offered = _codes(selectors.lookup_page("service_size_classes", None, code))
            assert "FL-14" in offered and "E-3P" in offered


def test_cr065_the_backfill_reverses_without_losing_a_tenants_own_tag(
    growth_plan, identity_seam
):
    """Reversing clears exactly the set the forward pass wrote. A row a PERSON
    tagged is `is_system=False` and survives — a database reversed and
    re-applied lands where it started rather than losing somebody's work."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        mine = services.create_lookup_entry(
            admin_actor(),
            "service_size_classes",
            {"code": "W-8", "name": 'Water 8"', "service": "water"},
        )
        _run_backfill("reverse")
        assert _entry(tenant, "FL-2").service_id is None
        assert _entry(tenant, "W-8").service.code == "water", "a person's own tag survives"
        _run_backfill()
        assert _entry(tenant, "FL-2").service.code == "fire"
        assert models.MeterSizeClass.objects.get(pk=mine["id"]).service.code == "water"


def test_cr065_a_reseed_never_rewrites_an_existing_rows_tag(growth_plan, identity_seam):
    """BR-TEN-012 / BR-TEN-071. The seeder is insert-if-absent, tag included: a
    utility that has retagged a seeded row keeps its answer, and the fixture
    never argues with it."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = _entry(tenant, "FL-2")
        row.service = models.Service.objects.get(code="water")
        row.save(update_fields=["service"])
        handler = services.lookup_handler("service_size_classes")
        created = handler.seed(tenant, sizes.seed_entries())
    assert created == 0
    assert _entry(tenant, "FL-2").service.code == "water"
