# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-902 (PO, 2026-08-27, live app v2.61.1) — the three seeded
#          sub-areas are in the fixture and not on the tenant.
#          PO verbatim: *"in this setting - unable to see sub areas"*.
# Rules:   BR-TEN-160 (which lists the sweep re-offers: STRUCTURAL only, and no
#          list is ever added to that set to make it sweep) · BR-TEN-161 (a
#          list older than the fixture SAYS SO on its own screen, by natural
#          key) · BR-TEN-067 (structural catalogues are exempt from the S111
#          toggle) · BR-TEN-030 (codes ci-unique per tenant) · BR-TEN-071
#          (insert-if-absent; never UPDATE, never DELETE)
# Questions: OQ-550 (may the sweep re-offer a discretionary list this tenant
#          demonstrably already holds?) — OPEN, nothing here decides it ·
#          OQ-216 (the tenant-level opt-in residue) — OPEN
# Impacts: apps/tenancy/services.reference_list_fixture_gap ·
#          GET /lookups/{list}/fixture-gap · SettingsReferenceData.tsx
# ───────────────────────────────────────────────────────
"""DEF-902 — *the data is correct and your tenant does not have it.*

`lookup_defaults.json` at `V2.48.0.2` ships **seven** area rows with their
`parent_code` wiring. Silver Creek Water shows **four**. The fixture, the
two-level depth cap and the Add-entry dialog are all correct and shipped — the
tenant was PROVISIONED BEFORE the fixture grew, and nothing re-offers a
reference list to a tenant that already has one. **The PO ratified the three
missing names that same morning (OQ-432) and then could not see them.**

Hard-won law 4 in its data form, and it is invisible to the whole suite for a
reason worth stating: every other test seeds a FRESH tenant, where the fixture
is the only writer and all seven rows land. The fixture is provably correct.
The gap only exists on a tenant that predates it — so these cases MANUFACTURE
that tenant by deleting the three rows a fresh seed created, which is the only
way to reproduce an August tenant in a September suite.

⚠ **NOTHING HERE DELIVERS ANYTHING.** BR-TEN-160 keeps delivery in the sweep
and the sweep is unchanged; whether it should re-offer a list the tenant
already holds is OQ-550, routed to the PO. `test_areas_is_not_structural`
exists to make the tempting wrong fix — quietly widening
`STRUCTURAL_REFERENCE_LISTS` so `areas` sweeps — fail loudly.

RED PROOFS (broken first, hard-won law 7 — transcripts in the lane report):
  · add "areas" to STRUCTURAL_REFERENCE_LISTS
      → `test_areas_is_not_structural` and
        `test_sweep_defers_every_discretionary_list_by_name` both go red.
  · compare by COUNT instead of by code in reference_list_fixture_gap
      → `test_the_gap_is_by_natural_key_never_by_count` goes red.
"""

import json
from pathlib import Path

import pytest

from apps.tenancy import models, services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

FIXTURE = json.loads(Path(services.FIXTURE_PATH).read_text(encoding="utf-8"))

#: DEF-902's measured case, verbatim from the fixture. The three the PO
#: ratified under OQ-432 on 2026-08-27 and then could not see.
THE_THREE_SUB_AREAS = ("NORTH-NE", "NORTH-NW", "EAST-SE")


def _make_an_august_tenant(tenant):
    """Reproduce a tenant PROVISIONED BEFORE the fixture grew.

    A fresh seed writes all seven areas, so the only honest way to test the
    gap is to remove the three that were added later — which is precisely the
    state Silver Creek Water is in, arrived at from the other direction.
    """
    with tenant_ctx(tenant):
        models.Area.objects.filter(tenant=tenant, code__in=THE_THREE_SUB_AREAS).delete()


# ══════════════════════════════════════════════════════════════════════════
# BR-TEN-160 — which lists the sweep re-offers, and the fix that must not happen
# ══════════════════════════════════════════════════════════════════════════
def test_areas_is_not_structural():
    """**THE GUARD AGAINST THE TEMPTING WRONG FIX.**

    Adding `areas` to `STRUCTURAL_REFERENCE_LISTS` would make it sweep and
    would close DEF-902 in one line. It is wrong, and BR-TEN-160 clause 1 says
    why: that set is ALSO what a tenant which DECLINED the S111 defaults
    receives at provisioning (BR-TEN-067), so widening it to fix a delivery
    problem silently hands sample content to a tenant that asked for none —
    the exact harm OQ-088's closure names. The two uses cannot be tuned apart.
    """
    assert "areas" not in services.STRUCTURAL_REFERENCE_LISTS, (
        "BR-TEN-160 clause 1: `areas` is SAMPLE content under BR-TEN-067. If it "
        "must reach existing tenants, that is OQ-550 and a PO ruling — never a "
        "widening of the set that also governs what a DECLINING tenant is given"
    )


def test_the_structural_set_is_schema_required_vocabulary_only():
    """BR-TEN-067's own words — *"vocabulary the schema itself requires"*. Every
    member names a column something cannot exist without; nothing here is a
    convenience. Pinned as a SET so a later addition is a visible diff with a
    reason beside it, not a quiet one."""
    assert set(services.STRUCTURAL_REFERENCE_LISTS) == {
        "meter_types",
        "read_methods",
        "asset_types",
        "asset_statuses",
        "account_statuses",
        "premises_types",
        "occupancy_statuses",
        "device_types",
        # ⚠ ADDED AT MERGE, 2026-08-27, WHICH IS THIS ASSERTION DOING ITS JOB.
        # `owner_categories` landed from CR-039 wave C (BR-TEN-150 clause 3)
        # while this lane was in flight, and the reason is the set's own test:
        # `premises_owners.category_id` is NOT NULL, so a tenant with an empty
        # list literally cannot record its first owner. That is schema-required
        # vocabulary, not a convenience, so it belongs here — and the addition
        # is visible with its reason beside it, exactly as the docstring asks.
        "owner_categories",
    }


def test_sweep_defers_every_discretionary_list_by_name(growth_plan, identity_seam):  # noqa: F405
    """BR-TEN-160: the sweep re-offers the structural set and nothing else, and
    a deferred list is named with its OQ rather than skipped into silence
    (the DEF-016 posture). `areas` is in the deferred half."""
    from apps.tenancy import reference_sweep

    tenant, _ = provisioned_tenant()
    plan = reference_sweep.sweep_tenant(tenant, dry_run=True)
    by_list = {row["list"]: row for row in plan["lists"]}
    assert by_list["areas"]["action"] == reference_sweep.ACTION_DEFERRED
    assert reference_sweep.DISCRETIONARY_DEFERRAL_OQ in by_list["areas"]["detail"]
    for list_code in services.STRUCTURAL_REFERENCE_LISTS:
        assert by_list[list_code]["action"] != reference_sweep.ACTION_DEFERRED, list_code


# ══════════════════════════════════════════════════════════════════════════
# BR-TEN-161 — the gap is VISIBLE
# ══════════════════════════════════════════════════════════════════════════
def test_a_freshly_seeded_list_has_no_gap(growth_plan, identity_seam):  # noqa: F405
    """The control case, and the reason the whole suite was blind to DEF-902:
    a tenant seeded today holds every fixture row, so `missing` is empty."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        gap = services.reference_list_fixture_gap("areas")
    assert gap["missing"] == []
    assert gap["fixture_version"] == FIXTURE["version"]
    assert gap["fixture_entries"] == 7 and gap["held"] == 7


def test_the_gap_names_the_three_sub_areas(growth_plan, identity_seam):  # noqa: F405
    """**DEF-902's measured case.** Seven in the fixture, four on the tenant,
    and the screen must be able to say WHICH three and what they are called —
    a count alone would have told the PO nothing they did not already see."""
    tenant, _ = provisioned_tenant()
    _make_an_august_tenant(tenant)
    with tenant_ctx(tenant):
        gap = services.reference_list_fixture_gap("areas")
    assert gap["held"] == 4 and gap["fixture_entries"] == 7
    assert [row["code"] for row in gap["missing"]] == list(THE_THREE_SUB_AREAS)
    assert [row["name"] for row in gap["missing"]] == ["NE", "NW", "SE"]


def test_the_gap_says_the_sweep_will_not_deliver_it(growth_plan, identity_seam):  # noqa: F405
    """The screen must say what to DO, and that depends on BR-TEN-160. It is
    SERVED rather than assumed by the screen, so the day the structural set
    moves the sentence moves with it instead of drifting."""
    tenant, _ = provisioned_tenant()
    _make_an_august_tenant(tenant)
    with tenant_ctx(tenant):
        assert services.reference_list_fixture_gap("areas")["sweep_delivers"] is False
        assert services.reference_list_fixture_gap("read_methods")["sweep_delivers"] is True


def test_the_gap_is_by_natural_key_never_by_count(growth_plan, identity_seam):  # noqa: F405
    """BR-TEN-161 clause (a). A tenant that lost three seeded rows and added
    three of its own has the RIGHT COUNT and is not current. A count-only
    check calls this healthy; the code comparison names all three."""
    from apps.tenancy import services as tenancy_services

    tenant, _ = provisioned_tenant()
    _make_an_august_tenant(tenant)
    with tenant_ctx(tenant):
        actor = admin_actor()  # noqa: F405
        for code, name in (("RIVER", "Riverside"), ("HILL", "Hillcrest"), ("BAY", "Bayfront")):
            tenancy_services.create_lookup_entry(actor, "areas", {"code": code, "name": name})
        gap = tenancy_services.reference_list_fixture_gap("areas")
    assert gap["held"] == 7 and gap["fixture_entries"] == 7  # the counts MATCH
    assert [row["code"] for row in gap["missing"]] == list(THE_THREE_SUB_AREAS)


def test_the_gap_reports_the_version_the_tenant_was_seeded_at(
    growth_plan,  # noqa: F405
    identity_seam,  # noqa: F405
):
    """`seeded_version` is the highest version in the TENANT's own ledger for
    this list — evidence of what it actually received, never the fixture's."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        gap = services.reference_list_fixture_gap("areas")
    assert gap["seeded_version"] == FIXTURE["version"]


def test_the_state_keyed_list_resolves_through_the_SWEEPS_OWN_RESOLVER(
    growth_plan,  # noqa: F405
    identity_seam,  # noqa: F405
):
    """⚠ **THE ONE LIST THAT IS NOT A PLAIN ARRAY, AND THE ONE THAT WOULD LIE —
    THREE TIMES OVER (DEF-960).**

    `tax_jurisdictions` has no `code` ANYWHERE in its chain, and each absence
    breaks a different reader:

      1. **The fixture is a DICT keyed by STATE**, not an array under its own
         key (CR-010's tax ruling, DEF-444). A naive `fixture[list_code]`
         iterates its KEYS and reports a gap of ZERO for a list that has one.
      2. **The TABLE has no `code` column** (BR-TEN-037 — tenant-entered, the
         NAME is its identity), so `row.code` is an **HTTP 500**.
      3. **The fixture ROWS have no `code` key either** — they read
         `{"name": "County", "level": "county"}` — so filtering on
         `entry["code"]` empties the list and reports zero AGAIN, silently.

    All three are one root cause and one fix: ask the readers that have already
    met these exceptions. `_fixture_entries` resolves (1),
    `reference_sweep._held_codes` resolves (2) through the handler's own
    `serialize` (which publishes `code: row.name`), and `_fixture_entry_key`
    resolves (3) the same way on the fixture side, so the two compare like
    with like. This case pins all three: the count must equal the SEEDER's and
    must never be zero.
    """
    from apps.tenancy import reference_sweep

    tenant, _ = provisioned_tenant()
    # ⚠ THE TENANT'S OWN STATE, NEVER A LITERAL — and the reason is DEF-961,
    # which this case is what found. `seed_demo` and the test payloads record
    # the state as "Texas" while the fixture keys its rows "TX", so this tenant
    # legitimately resolves to the 3-row `ALL` scaffold and NONE of the five
    # Texas rows. Asserting against a hardcoded "TX" would test the fixture;
    # asserting against the tenant's own column tests what this read is FOR,
    # and it stays true on the day DEF-961 is fixed.
    expected = len(services.tax_jurisdiction_entries(FIXTURE, tenant.state))
    assert expected > 0, "the fixture must carry rows for this tenant or the case proves nothing"
    with tenant_ctx(tenant):
        gap = services.reference_list_fixture_gap("tax_jurisdictions")
        # …and it agrees with the sweep, by construction rather than by luck.
        assert gap["fixture_entries"] == len(
            reference_sweep._fixture_entries(FIXTURE, "tax_jurisdictions", tenant.state)
        )
    assert gap["fixture_entries"] == expected


def test_a_list_the_fixture_ships_nothing_for_reports_no_gap(
    growth_plan,  # noqa: F405
    identity_seam,  # noqa: F405
):
    """`premises_types` is deliberately absent from the fixture — metering's own
    BR-MET-034 seed is the single ratified source (DEF-026). A list the platform
    ships nothing for cannot be BEHIND the platform, and must not claim to be."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        gap = services.reference_list_fixture_gap("premises_types")
    assert gap["fixture_entries"] == 0 and gap["missing"] == []


def test_an_unknown_list_is_404_not_an_empty_gap(growth_plan, identity_seam):  # noqa: F405
    """An unknown or unwired list must not answer *"nothing is missing"* — that
    is a claim about a list this deployment does not have."""
    from core import errors

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(errors.NotFoundError):
        services.reference_list_fixture_gap("no_such_list")


# ══════════════════════════════════════════════════════════════════════════
# The wire (GET /lookups/{list}/fixture-gap)
# ══════════════════════════════════════════════════════════════════════════
def test_the_route_is_not_swallowed_by_the_entry_id_route(growth_plan, identity_seam):  # noqa: F405
    """`lookups/<list>/<entry_id>` would match `fixture-gap` as an entry id, so
    the literal segment is registered ABOVE it — the DEF-520 route-ordering
    shape. Asserted through the resolver rather than by calling the view, so
    the ORDER is what is being tested."""
    from django.urls import resolve

    from apps.tenancy import api

    match = resolve("/api/v1/lookups/areas/fixture-gap")
    assert match.func is api.lookup_fixture_gap
    assert match.kwargs == {"list_code": "areas"}
