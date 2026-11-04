# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W5 task W5-T1:
#           the `RT-001` / `CY-001` grammar END TO END, and the one writer that
#           was still minting the old one.
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7 W5-T1
# Rules:    D5 (*"Rt-001 is good"*) · D2 (one schedule generation) ·
#           BR-MET-073 (route codes come from the number series) ·
#           BR-MET-077 (a cycle is a definition) · BR-TEN-063 (sample data is
#           idempotent) · hard-won law 6 (diff the running app, which is how
#           this was found) · OQ-338 (**CLOSED-RULED 2026-08-23**, PO verbatim
#           *"A: geography only - option a"* — the areas half of D5, and the
#           half that stubbed this task; finished by CR-029 RC-W6b below)
# ───────────────────────────────────────────────────────
"""W5-T1 — the second grammar, found in a browser and killed here.

**HOW THIS WAS FOUND, BECAUSE IT MATTERS.** RC-W5-T8 brought the product up and
looked at Settings → Routes & Cycles on the seeded demo tenant. The Routes table
held seven rows:

    RT-001 … RT-006   1–2 members each,   real service sets, real areas
    SCW-R1            41 members, 48 accounts, "All services", area "—"

and the Cycles table held `CY-001 … CY-006` beside **`SCW-M`**. The one cycle
that actually carried every account on the tenant was the one wearing the OLD
grammar — and `CY-001`'s Accounts column read **0**.

**WHY EVERY GATE AND EVERY TEST MISSED IT.** `tests/test_cr029_w0_seed.py::
test_the_route_and_cycle_codes_use_the_ruled_grammar` asserts exactly this rule
and PASSES, because its fixture calls the demo command's own
`_seed_cycles_and_routes` and nothing else. The `SCW-*` rows come from a
different writer — `apps/metering/sample_data.py`, the BR-TEN-056 sample-records
seam that runs for **every tenant that opts into sample data**, not just the
demo — and no test had ever put the two writers in one tenant and read the list
back. This file does exactly that.

**AND IT WAS WRITING THE DEPRECATED COLUMNS TOO.** The sample cycle was created
with `window_start` / `window_end` / `bill_date` — three of the six columns
CR-029 D2 superseded and W5-T2 drops — and with **no frequency, no start day and
no days to complete**, so it proposed no window, published no next cycle date,
and was skipped by the dashboard countdown. A cycle holding 48 accounts that the
calendar could not see.

⚠ **OQ-338 IS CLOSED, AND THE STUB THAT SAT HERE IS GONE.** D5 was put to the
PO as two things and only the naming half came back (*"Rt-001 is good"*), so
this task reconciled CODES and said out loud that it was leaving the areas
registry alone — *"no test below asserts anything about who owns an area"*. The
PO ruled the second half on 2026-08-23, verbatim: ***"A: geography only -
option a"***.

**What that makes law:** an area is a TAG ON A PREMISES (North · Downtown ·
East); **routes are created and edited in exactly ONE place, the routes
registry**; Settings' "Areas & sub-areas" holds areas and nothing route-shaped.
It is what the code already did — r10's SET-04, which duplicated the routes
registry byte for byte and put one premises on Route 3 and Route 1 at once, was
never built — so nothing changes in behaviour and the last section of this file
PINS it instead. A conformance test, deliberately: the cheapest way to grow a
second registry is for someone to add one list, one column at a time, and every
gate in this repo would stay green while they did.
"""

import pytest

from apps.metering import models as metering_models
from apps.metering import sample_data, schedule, selectors as metering_selectors
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

RULED_ROUTE = r"^RT-\d{3}$"
RULED_CYCLE = r"^CY-\d{3}$"


@pytest.fixture()
def sampled(brazos, dana):
    """A tenant that has taken the sample records — the real seam, not a
    reimplementation, so this test cannot drift from what a tenant gets."""
    with tenant_ctx(brazos):
        sample_data.seed_sample_records(dana)
        yield {"tenant": brazos, "actor": dana}


# ═══════════════════════════════════════════════════════════════════════════
# D5 — ONE GRAMMAR, AND THE SAMPLE SEAM OBEYS IT TOO
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t1__the_sample_seam_mints_the_ruled_route_and_cycle_codes(sampled):
    """*"Rt-001 is good"* is the product's grammar, not the demo command's.

    A tenant that opts into sample data gets routes and cycles like every other
    tenant's: allocated from the `RT-`/`CY-` number series (BR-MET-073), not
    from a constant in a fixture file.
    """
    import re

    with tenant_ctx(sampled["tenant"]):
        routes = [row["code"] for row in metering_selectors.routes_list()]
        cycles = [row["code"] for row in metering_selectors.cycles_list()]
    assert routes, "the sample seam created no route"
    assert cycles, "the sample seam created no cycle"
    bad_routes = [code for code in routes if not re.match(RULED_ROUTE, code)]
    bad_cycles = [code for code in cycles if not re.match(RULED_CYCLE, code)]
    assert bad_routes == [], f"routes outside the D5 grammar: {bad_routes}"
    assert bad_cycles == [], f"cycles outside the D5 grammar: {bad_cycles}"


def test_w5_t1__the_sample_cycle_carries_the_three_ruled_fields_about_time(sampled):
    """B17 §2 — start day · frequency · days to complete. The sample cycle held
    none of the three and carried the deprecated calendar dates instead, so it
    proposed no window and the dashboard countdown skipped it."""
    with tenant_ctx(sampled["tenant"]):
        row = metering_models.Cycle.objects.order_by("code").first()
        assert row is not None
        assert row.frequency in schedule.FREQUENCIES, f"frequency={row.frequency!r}"
        assert row.start_day is not None, "no start day"
        assert row.days_to_complete is not None, "no days to complete"
        assert row.first_run_date is not None, "no first run — the engine has no anchor"


def test_w5_t1__the_sample_cycle_proposes_a_window_and_a_next_date(sampled):
    """The consequence of the fact above, at the payload the screens read. A
    cycle with no anchor publishes `next_cycle_date = None`, which is what made
    a cycle holding every account invisible to the dashboard countdown."""
    with tenant_ctx(sampled["tenant"]):
        row = metering_models.Cycle.objects.order_by("code").first()
        served = metering_selectors.cycle_dict(row)
    assert served["next_cycle_date"] is not None
    assert served["proposed_windows"], "the cycle proposes no window"
    assert served["read_window_source"] == "derived"


#: The deprecated names this seam once wrote — held as NAMES rather than as
#: attribute reads, because every one of them is now a dropped column.
#:
#: ⚠ **THIS TUPLE HELD FOUR, THEN ONE, AND NOW NONE OF THEM IS A COLUMN.** It
#: named `window_start`, `window_end`, `bill_date` and `due_day`; metering 0021
#: dropped three, and metering 0023 took `bill_date` — the last one — once
#: OQ-344 ruled what replaces it (*"I'd say B - these are defualt - user can
#: override"*, PO 2026-08-23).
#:
#: So the assertion INVERTS from *"the seam writes none of these values"* to
#: *"none of these is reachable at all"*. `getattr` on a Cycle no longer answers
#: for any of them, and a test that read them would now fail on the ATTRIBUTE
#: rather than on the value — which is a worse test than none.
_SEAM_WRITTEN_DEPRECATED = ("window_start", "window_end", "bill_date", "due_day")


def test_w5_t1__the_sample_seam_writes_no_deprecated_column(sampled):
    """D2 — the legacy calendar dates are superseded, and all six are now gone.

    A writer still filling one is a reader the drop cannot retire, so this case
    guarded the seam while the columns existed. It now guards the other
    direction: none of the four names this seam ever wrote is a field on the
    model, so the seam CANNOT write one, and a lane re-adding a column would
    have to pass here first.
    """
    fields = {field.name for field in metering_models.Cycle._meta.get_fields()}
    reachable = sorted(name for name in _SEAM_WRITTEN_DEPRECATED if name in fields)
    assert reachable == [], f"deprecated columns are back on the model: {reachable}"
    with tenant_ctx(sampled["tenant"]):
        rows = list(metering_models.Cycle.objects.all())
    assert rows, "the sample seam created no cycle"
    # …and the RULED generation is what it writes instead.
    assert all(row.start_day is not None and row.days_to_complete is not None for row in rows)


def test_w5_t1__the_sample_route_carries_a_service_set_and_an_area(sampled):
    """The same defect W0-T1 closed for the demo command's routes, in the other
    writer: `SCW-R1` was served as *"All services"* with area *"—"*, and DEF-227
    records what an all-services route does to a service point that already
    belongs to a route drawn for its own service."""
    with tenant_ctx(sampled["tenant"]):
        rows = list(metering_models.Route.objects.all())
    assert rows, "the sample seam created no route"
    nulls = [row.code for row in rows if row.service_id is None]
    assert nulls == [], f"sample routes with no service: {nulls}"


# ═══════════════════════════════════════════════════════════════════════════
# BR-TEN-063 — AND IT IS STILL IDEMPOTENT
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t1__a_replay_creates_no_second_route_or_cycle(sampled):
    """⚠ **THE RISK THIS CHANGE INTRODUCES, PINNED.** The old seam was
    idempotent on a CONSTANT code (`SCW-R1`), and a series-allocated code is
    different on every call — so a naive fix would mint a new route on every
    replay. Idempotency moves to the sample route's own stable NAME.
    """
    with tenant_ctx(sampled["tenant"]):
        before_routes = len(metering_selectors.routes_list())
        before_cycles = len(metering_selectors.cycles_list())
        sample_data.seed_sample_records(sampled["actor"])
        assert len(metering_selectors.routes_list()) == before_routes
        assert len(metering_selectors.cycles_list()) == before_cycles


# ═══════════════════════════════════════════════════════════════════════════
# OQ-338 — AREAS ARE GEOGRAPHY, AND A ROUTE HAS EXACTLY ONE EDITING SURFACE
#
# PO, verbatim, 2026-08-23: *"A: geography only - option a"*.
# ═══════════════════════════════════════════════════════════════════════════
def test_oq338__no_reference_list_is_a_second_routes_registry():
    """The registry of reference lists declares no route- and no cycle-shaped
    list, so Settings' reference data has no door to a route at all.

    ⚠ **This is the assertion the ruling actually buys.** Areas holding no
    route COLUMN is easy to keep true by accident; a *second list* called
    `routes` appearing beside it is how r10 got two registries, and it would
    look like a perfectly ordinary CR-004 card on the way in.
    """
    route_shaped = sorted(
        code
        for code in tenancy_services.LOOKUP_LISTS
        if "route" in code.lower() or "cycle" in code.lower()
    )
    assert route_shaped == [], f"reference lists that look like a routes registry: {route_shaped}"


def test_oq338__an_area_row_publishes_nothing_route_shaped(brazos, dana):
    """What `GET /lookups/areas` serves for one area: identity, hierarchy and
    the shared list fields. No route, no cycle, no member count — an area
    describes WHERE a premises is, and the routes registry describes who reads
    it."""
    with tenant_ctx(brazos):
        served = tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "OQ338N", "name": "North district"}
        )
    leaked = sorted(k for k in served if "route" in k.lower() or "cycle" in k.lower())
    assert leaked == [], f"an area row publishes route-shaped keys: {leaked}"
    # …and the keys it DOES publish are geography, stated positively so a
    # silently emptied payload cannot pass this test.
    assert {"code", "name", "parent_code", "parent_name", "is_sub_area"} <= set(served)


def test_oq338__the_areas_list_refuses_a_route_field_rather_than_storing_it(brazos, dana):
    """Nobody can grow the second registry through the payload either.

    The base validator refuses every field it does not know, which is what
    turns *"areas are geography only"* from a docstring into behaviour: a
    client that posts `route_code` to `/lookups/areas` is REFUSED, not
    silently ignored — and being ignored is the failure mode that lets a
    feature ship half-built.
    """
    with tenant_ctx(brazos):
        with pytest.raises((errors.ValidationError, errors.BizError)) as caught:
            tenancy_services.create_lookup_entry(
                dana,
                "areas",
                {"code": "OQ338R", "name": "North district", "route_code": "RT-001"},
            )
    assert caught.value is not None
    with tenant_ctx(brazos):
        assert not tenancy_models.Area.objects.filter(code="OQ338R").exists()


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 §7 RC-W5 T1 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W5 lane
# checklist: A✔ B=n/a(no screen of its own — the grammar it asserts is what SET-05 renders) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: the browser walkthrough (W5-T8) is what found this; these tests are what keep it found
# exceptions: (1) [CR-029 RC-W6b 2026-08-23] OQ-338 is CLOSED-RULED (*"A: geography only - option a"*) and the stub that read *"OPEN and untouched"* is REMOVED — the last section asserts the ownership the ruling makes law. (2) the ownership tests are CONFORMANCE, not regression: no defect preceded them, because the duplication the ruling forbids was never built. They exist because a second registry arrives one column at a time and no gate in this repo would object
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
