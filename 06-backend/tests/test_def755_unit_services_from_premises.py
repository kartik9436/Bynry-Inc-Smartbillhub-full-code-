# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-755 — *"A UNIT'S SERVICES ARE DERIVED FROM ITS METERS, NOT FROM
#          ITS PREMISES — SO A UNIT LOSES A SERVICE THE DAY ITS METER IS
#          PULLED"*. `selectors.unit_list_dict` read
#          `[point["service"] for point in service_points_for(unit.id)]`;
#          `unit_detail_dict` served no services at all.
# Change:  PO, 2026-08-26, after withdrawing CR-037: **a unit's services ARE its
#          premises' services** — no unit-level column, no override. And on the
#          deployed screen: *"We ahve fixed premises already . premises are
#          showing Utility services now"* while units still read "No services"
#          on 9,881 rows.
# Story:   US-MET-002 (S15 units list + detail)
# Rules:   BR-MET-003 (a premises offers only what the utility sells) ·
#          BR-MET-118 as withdrawn (the ruling above is what stands)
# ───────────────────────────────────────────────────────
"""Two questions that were sharing one word.

  · **what this unit HAS** — its premises' `services_available`. The rule.
  · **what is METERED here** — its service points. Still true, still useful,
    and now called `metered_services`.

⚠ **THE OLD DERIVATION WAS NOT WRONG WHEN IT WAS WRITTEN.** `unit_list_dict`'s
own docstring said "services from service_points": it was answering the second
question honestly and the field was simply named `services`. It became wrong the
moment the ruling made the first question the one the name asks. That is why no
gate could catch it — nothing compares a derivation against a rule about what it
should derive from — and why the three cases below are the fix's real content.

⚠ **THE SERVICE-POINT READERS THAT ARE *NOT* TOUCHED.** `derivation.py`'s
route/cycle logic, the service agreements, `_service_code_by_asset` and the
billing gather all read service points ON PURPOSE: they are about REALISATION —
what is metered and connected — which is a different question and still has the
right source. Only the unit's services DISPLAY moved.
"""

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

# ⚠ **`services=[]` ON EVERY UNIT BELOW THAT MUST START WITH NO SERVICE POINT —
# `BR-MET-119` AS AMENDED 2026-09-25 (`DEF-MET-6796`, shipped in `630f472c3`).**
# PO, verbatim: *"the premises' list is what a unit takes, the tick-list stays,
# and a clerk may untick"*. Since then a create that asks nothing gives the unit
# one service point per service its address offers, so the five cases about a
# unit whose points are FEWER than its address's offer went red the day it
# shipped (green at `33d0f8aed`, red at `630f472c3`). `[]` is the
# unticked-everything door that ruling keeps lawful, and it is now the honest
# way to build "a unit with nothing metered yet". No assertion moved.
_NO_POINTS = {"services": []}


def _service(code: str):
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.get(code=code)


def _point(unit, code: str):
    """A service point on this unit — the thing the OLD derivation read."""
    return models.ServicePoint.objects.create(
        tenant_id=unit.tenant_id, unit=unit, service=_service(code)
    )


def _unit_row(unit_id):
    return selectors.unit_list_dict(models.Unit.objects.get(pk=unit_id))


def test_def755__a_units_services_are_its_premises_services(brazos, dana):
    """THE RULE, at its simplest: the premises offers electric + water, so the
    unit does, with no service point anywhere in the picture."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="61 Ruling Way", services_available=["electric", "water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit A")
        row = _unit_row(unit["id"])
    assert row["services"] == ["electric", "water"]


def test_def755__CONSEQUENCE_1__available_but_NOT_YET_METERED_still_shows(brazos, dana):
    """⚠ The 9,881-row case. A freshly migrated unit has no service point at
    all, so the old derivation returned `[]` and the screen said "No services"
    for a unit whose address demonstrably offers two."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="63 Ruling Way", services_available=["electric", "water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit A", **_NO_POINTS)
        assert not models.ServicePoint.objects.filter(unit_id=unit["id"]).exists()
        row = _unit_row(unit["id"])
    assert row["services"] == ["electric", "water"]
    # …and the metered set is honestly empty, which is the useful half: this
    # unit has water available and no water meter.
    assert row["metered_services"] == []


def test_def755__CONSEQUENCE_2__pulling_the_meter_does_not_remove_the_service(brazos, dana):
    """⚠ The case the withdrawn CR-037 predicted in writing the day before:
    *"a unit silently loses a service the moment its meter is pulled"*."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="65 Ruling Way", services_available=["electric", "water"]
        )
        unit_row = make_unit(dana, premises["id"], label="Unit A", **_NO_POINTS)
        unit = models.Unit.objects.get(pk=unit_row["id"])
        point = _point(unit, "water")
        before = _unit_row(unit.id)
        assert before["metered_services"] == ["water"]

        # The meter comes out — the service point is soft-deleted.
        from django.utils import timezone

        point.deleted_at = timezone.now()
        point.save(update_fields=["deleted_at"])
        after = _unit_row(unit.id)

    # The SERVICE is untouched: the address still offers water.
    assert after["services"] == ["electric", "water"]
    # What changed is the honest fact — nothing is metered here now.
    assert after["metered_services"] == []


def test_def755__CONSEQUENCE_3__a_sub_metered_unit_does_not_double_count(brazos, dana):
    """Two points on the same service (a master and a sub) used to put the code
    in the list TWICE, so the S15 cell drew `Water Water`."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="67 Ruling Way", services_available=["electric", "water"]
        )
        unit_row = make_unit(dana, premises["id"], label="Unit A", **_NO_POINTS)
        unit = models.Unit.objects.get(pk=unit_row["id"])
        _point(unit, "water")
        _point(unit, "water")
        row = _unit_row(unit.id)
    assert row["metered_services"] == ["water"], "one entry per SERVICE, not per point"
    assert row["services"] == ["electric", "water"]


def test_def755__the_two_facts_no_longer_share_a_word(brazos, dana):
    """The shape of the fix, in one row: available ≠ metered, and both are
    served. A unit with Electric metered on an address offering Electric AND
    Water must not be reported as offering only Electric."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="69 Ruling Way", services_available=["electric", "water"]
        )
        unit_row = make_unit(dana, premises["id"], label="Unit A", **_NO_POINTS)
        unit = models.Unit.objects.get(pk=unit_row["id"])
        _point(unit, "electric")
        row = _unit_row(unit.id)
    assert row["services"] == ["electric", "water"]
    assert row["metered_services"] == ["electric"]
    assert row["services"] != row["metered_services"]


def test_def755__the_DETAIL_dict_serves_services_too(brazos, dana):
    """It served none at all, so the unit's services were invisible to the
    write path's audit rows and to `customers.seams`' move-in/move-out
    payloads as well as to the detail screen."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="71 Ruling Way", services_available=["electric"]
        )
        unit_row = make_unit(dana, premises["id"], label="Unit A")
        detail = selectors.unit_detail_dict(models.Unit.objects.get(pk=unit_row["id"]))
    assert detail["services"] == ["electric"]


def test_def755__an_unasked_premises_gives_its_units_null_not_an_empty_list(brazos, dana):
    """DEF-762's three states, inherited. `[]` here would put *this unit offers
    nothing* into a clerk's mouth for every unit of every address nobody has
    been asked about — which is the "No services" the PO is looking at."""
    with tenant_ctx(brazos):
        created = services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "73 Ruling Way"})
        assert models.Premises.objects.get(pk=created["id"]).services_available is None
        unit_row = make_unit(dana, created["id"], label="Unit A")
        row = _unit_row(unit_row["id"])
    assert row["services"] is None
    assert row["services"] != []


def test_def755__a_copy_is_served__a_unit_cannot_mutate_its_premises(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="75 Ruling Way", services_available=["electric"]
        )
        unit_row = make_unit(dana, premises["id"], label="Unit A")
        row = _unit_row(unit_row["id"])
        row["services"].append("gas")
        stored = models.Premises.objects.get(pk=premises["id"])
    assert stored.services_available == ["electric"]


def test_def755__the_units_FILTER_matches_what_the_column_shows(brazos, dana):
    """⚠ Reported as a decision, not assumed. The `service` filter read service
    points, so a clerk who filtered by Water lost every unit that HAS water and
    no water meter — the filter disagreeing with the cell beside it. Both now
    read the premises."""
    with tenant_ctx(brazos):
        watery = make_premises(
            dana, address_line="77 Ruling Way", services_available=["electric", "water"]
        )
        dry = make_premises(dana, address_line="79 Ruling Way", services_available=["electric"])
        with_water = make_unit(dana, watery["id"], label="Unit A", **_NO_POINTS)
        without = make_unit(dana, dry["id"], label="Unit B", **_NO_POINTS)
        # No service points anywhere: under the old filter NOTHING matched.
        assert not models.ServicePoint.objects.filter(
            unit_id__in=[with_water["id"], without["id"]]
        ).exists()
        matched = [str(u.id) for u in selectors.units_list(filters={"service": "water"})]
    assert with_water["id"] in matched
    assert without["id"] not in matched


def test_def755__the_filter_does_not_match_an_UNASKED_premises(brazos, dana):
    """*Unrecorded* is not *water*. Those units are found by their empty
    Services cell, never by a filter that guessed on their behalf."""
    with tenant_ctx(brazos):
        unasked = services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "81 Ruling Way"})
        unit = make_unit(dana, unasked["id"], label="Unit A")
        matched = [str(u.id) for u in selectors.units_list(filters={"service": "water"})]
    assert unit["id"] not in matched


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-755 (12-governance/10-defect-log.csv) + the PO ruling of
#         2026-08-26 (verbatim above, CR-037 withdrawn) + BR-MET-003
# screens: S15 units list + unit detail · the S15 Download
# generated: 2026-08-26 by lane DEFSWEEP
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
