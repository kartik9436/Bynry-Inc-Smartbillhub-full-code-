# ── Trace ──────────────────────────────────────────────
# Change:   DEF-CUS-5994 — the parked-drafts PANEL is removed and every parked
#           draft becomes a ROW of its own flow's list. PO ruling 2026-09-20,
#           verbatim: *"remove it - it is anyway in the list so we dont need it
#           sepretely - if it is not in list add it"*. It AMENDS `CR-035`
#           amendment 1 (PO 2026-08-26), which put parked work on each flow tab
#           and left the PLACEMENT open; this settles it.
# Rules:    BR-SHL-048 (a parked wizard changes nothing until it is executed,
#           and it joins to nothing — a LOOKUP, never a FK) · BR-SHL-046 (ONE
#           declared step list drives the step line) · BR-CUS-1077 (the shape:
#           a second row kind, named on every row, ordered by the DATABASE over
#           both) · NFR-3 (server pagination) · NFR-5 (no cap) ·
#           CLAUDE.md hard rule 1.
# Tests:    THIS FILE IS THE MECHANICAL HALF OF `DEF-CUS-5994`'s prevention —
#           it asks of EVERY flow the one question nobody owned: *does this
#           flow's own list carry the drafts that flow produces?*
# ───────────────────────────────────────────────────────
"""Every flow's list carries its own parked drafts — all five, one question.

**WHY A FILE OF ITS OWN RATHER THAN FIVE ADDITIONS TO FIVE SUITES.** The defect
was not that one list was wrong. It was that **the question belonged to
nobody**: each of the five lists tested ITS OWN rows at ITS OWN address, and
*"is every parked draft for this flow reachable on this flow's list"* was asked
by no suite, so four lists could exclude a row kind their own flow produces and
every check stayed green. That is hard-won law 2's shape and `DEF-CWP-3925`'s
mechanism exactly — a fact with no control in front of it — and the cure is one
case that sweeps all five rather than five cases that each look at one.

⚠ **RED PROVED FIRST, IN THE HARNESS THAT RUNS IT** (hard-won law 7, and its
2026-09-04 clause: a red proof through the wrong entry point is no proof). Run
before the implementation, `test_every_flow_list_carries_its_own_parked_drafts`
reported four of the five flows missing their draft — move-out alone passed,
because `BR-CUS-1077` had already widened that one window on 2026-09-19. The
failure is quoted in the lane report.

⚠ **AND THE COUNT MUST STAY HONEST, WHICH IS THE ONE CONSTRAINT THE RULING
KEPT.** `total` is the SERVER's count over the whole window, so a list that
gained a row kind must gain it in `total` too — not by adding a second number
to a first in Python, and not by splicing drafts into a page the database
already chose. `test_the_total_counts_the_draft_it_shows` is the assertion:
the figure a clerk reads and the rows they can page to are one window.
"""

from datetime import date

import pytest

from apps.customers import disconnect_reads, move_reads, transfer_reads
from apps.customers import seams as customers_seams
from apps.customers import services as customers_services
from apps.metering import connection_reads
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

#: The five flows `wizard_parks.flow` accepts, and for each the list that flow's
#: work lands on. **The map is the test** — a sixth flow added to the store with
#: no list beside it fails here rather than shipping invisible.
FLOW_LISTS = {
    "move_in": "the Move-ins tab",
    "move_out": "the Move-outs tab",
    "transfer": "the Transfers tab",
    "disconnect": "the Disconnects tab",
    "new_connect": "the New connects tab",
}


def _plan(tenant, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="5994 Parks", defaults={"code": "d5994", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"5994 Parks — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A"):
    premises = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _account(actor, tenant, *, label, name, status="active"):
    """One account through the ONE door, so the fixture is a real account."""
    unit = _unit(actor, tenant, label=label)
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": status,
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _park(actor, tenant, flow, *, step=2, waiting_on="the customer", account=None):
    """One parked draft for `flow`, THROUGH THE OWNING MODULE'S DOOR.

    ⚠ **NEVER `WizardPark.objects.create`.** `wizard_parks` is tenancy-hosted
    and `seams.park_wizard_draft` is the route customers may take (B1 /
    BR-TEN-013). A fixture writing the row directly would prove a table can
    hold a step; what is under test is that PARKING — the path a clerk walks —
    puts a row on the flow's list.

    Each payload is the one that flow's wizard actually sends, copied from the
    five `onPark` blocks: `subject_ref` carries COPIED ids and never a foreign
    key (BR-SHL-048 (a)), and `new_connect` carries `{}` because a new connect
    has no premise, unit or account id until it commits.
    """
    label = f"{flow} draft"
    if flow == "new_connect":
        subject_ref: dict = {}
        values: dict = {"draft": {"premise": {"address": "9 Cattail Row"}}}
        label = "9 Cattail Row"
    elif flow == "move_in":
        if account is None:
            unit = _unit(actor, tenant, label="41 Heron Walk")
            unit_id = str(unit["id"])
        else:
            unit_id = str(account["unit_id"])
        subject_ref = {"unit_id": unit_id, "account_id": None}
        values = {"unit_id": unit_id, "opened_at": "2026-09-30"}
        label = "41 Heron Walk"
    else:
        if account is None:
            account = _account(actor, tenant, label=f"{flow} home", name="Okonkwo, Adaeze")
        account_id = str(account["id"])
        subject_ref = {"account_id": account_id}
        values = {"account_term": account_id, "draft": {}}
        label = "Okonkwo, Adaeze"
    return customers_seams.park_wizard_draft(
        actor,
        {
            "flow": flow,
            "step": step,
            "subject_label": label,
            "subject_ref": subject_ref,
            "values": values,
            "waiting_on": waiting_on,
        },
    )


def _list_for(flow):
    """The flow's own list, called the way its endpoint calls it."""
    if flow == "move_in":
        return move_reads.move_ins_list(as_of=TODAY, per=50)
    if flow == "move_out":
        return move_reads.move_outs_list(as_of=TODAY, per=50)
    if flow == "transfer":
        return transfer_reads.list_transfers(as_of=TODAY, per=50)
    if flow == "disconnect":
        return disconnect_reads.list_disconnects(as_of=TODAY, per=50)
    return connection_reads.list_connections(per=50)


def _step_reached(row):
    """The step a row says it reached, in whichever shape its list serves it.

    ⚠ **THE FIVE LISTS DO NOT AGREE ON THIS KEY, AND THAT IS PRE-EXISTING.**
    The two move tabs serve `step` as `{reached, of, unavailable}` — a dict, so
    an absence can ride beside the number (`DEF-127`: a blank cell and an absent
    fact are indistinguishable once drawn). The Transfers tab serves a flat
    `step` int with `step_of` beside it, because `transfers._serialize` was
    written before that posture existed. **Neither is wrong and unifying them is
    not this defect's job** — it would change a wire contract three screens read
    — so this helper reads both and the divergence is REPORTED rather than
    silently normalised. A test that quietly accepted either shape without
    saying so would be hiding the finding it is standing on.
    """
    step = row.get("step")
    if isinstance(step, dict):
        return step.get("reached"), step.get("of"), step.get("unavailable")
    return step, row.get("step_of"), None


def _park_ids(payload):
    """Every `park_id` the page's rows carry — whatever else they carry.

    Deliberately read off the ROW rather than off a row-kind the test names:
    the assertion is *the draft is reachable on this list*, and pinning it to
    one spelling of one key would be a test named after an assertion it does
    not make (hard-won law 7).
    """
    return {row.get("park_id") for row in payload["rows"] if row.get("park_id")}


# ════════════════════════════════════════════════════════════════════════════
# THE ONE QUESTION NOBODY OWNED
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("flow", sorted(FLOW_LISTS))
def test_every_flow_list_carries_its_own_parked_drafts(brazos, marcus, flow):
    """PO 2026-09-20: *"it is anyway in the list … if it is not in list add it"*.

    One parked draft per flow, and the flow's own list must show it. This is
    the case that was RED for four of the five flows before the fix.
    """
    with tenant_ctx(brazos):
        park = _park(marcus, brazos, flow)
        payload = _list_for(flow)
        assert str(park.id) in _park_ids(payload), (
            f"a parked {flow} draft is not on {FLOW_LISTS[flow]} — the PO's ruling is that it "
            f"belongs there, and the panel that used to carry it is gone"
        )


@pytest.mark.parametrize("flow", sorted(FLOW_LISTS))
def test_the_draft_shows_the_real_step_it_was_parked_at(brazos, marcus, flow):
    """A parked draft HAS a step, so it prints one — that is the improvement.

    `MoveStepBar`'s own rule is that `reached` is the SERVER's answer and the
    component never derives one. A draft's answer is stored, so it is served;
    a record that was never walked keeps its absence. **Both, on one list.**
    """
    with tenant_ctx(brazos):
        _park(marcus, brazos, flow, step=3)
        payload = _list_for(flow)
        drafts = [row for row in payload["rows"] if row.get("park_id")]
        assert drafts, f"no draft row on {FLOW_LISTS[flow]}"
        reached, of, unavailable = _step_reached(drafts[0])
        # ⚠ A MOVE-IN draft parked under the seven-step wizard is served in the
        # FOUR-step shape since 2026-10-05 (`CR-171-BRC10` P1.03): old step 3
        # (Customer) is new step 2 (Customer). The step is still the clerk's.
        expected = move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR[3] if flow == "move_in" else 3
        assert reached == expected, f"{flow}: the step a clerk actually reached is not served"
        assert of is not None and of >= 3, (
            f"{flow}: the denominator is the flow's own declared step list"
        )
        assert unavailable is None, (
            f"{flow}: a row WITH a step must not also carry an absence for it"
        )


@pytest.mark.parametrize("flow", sorted(FLOW_LISTS))
def test_the_total_counts_the_draft_it_shows(brazos, marcus, flow):
    """The one constraint the ruling KEPT: the count does not lie.

    ⚠ **THIS IS NOT THE OLD PANEL'S RULE INVERTED.** `parkedDrafts.tsx` §2 kept
    drafts OUT of `total` because they were not rows of the list. They are rows
    now, so `total` must count them — and it must count them the way every
    other row is counted, as the SERVER's figure over the whole window. A list
    whose `total` moved by anything other than one here is either splicing in
    Python or counting a row it cannot page to.
    """
    with tenant_ctx(brazos):
        before = _list_for(flow)["total"]
        _park(marcus, brazos, flow)
        after = _list_for(flow)["total"]
        assert after == before + 1, (
            f"{flow}: the list shows the draft and its total does not count it — "
            f"{before} → {after}"
        )


@pytest.mark.parametrize("flow", sorted(FLOW_LISTS))
def test_a_draft_row_is_tellable_apart_from_a_record_at_a_glance(brazos, marcus, flow):
    """A row that HAPPENED and a draft that has not must not read the same.

    Every row carries `row_kind` — `BR-CUS-1077`'s posture, served on EVERY row
    rather than inferred from an absent field, because an inference is a second
    implementation of a rule and `DEF-127` is what that costs.
    """
    with tenant_ctx(brazos):
        _park(marcus, brazos, flow)
        payload = _list_for(flow)
        for row in payload["rows"]:
            assert row.get("row_kind"), f"{flow}: a row with no row_kind cannot be told apart"
        kinds = {row["row_kind"] for row in payload["rows"] if row.get("park_id")}
        assert len(kinds) == 1, f"{flow}: a draft row must carry ONE named kind, got {kinds}"
        assert "park" in next(iter(kinds)), (
            f"{flow}: the draft's row_kind should say it is a park — got {kinds}"
        )


@pytest.mark.parametrize("flow", sorted(FLOW_LISTS))
def test_a_draft_never_crosses_a_tenant(brazos, lonestar, marcus, flow):
    """Hard rule 1, asked of the NEW arm specifically.

    `wizard_parks` is read through `seams.wizard_park_queryset`, which forwards
    to the owning module's own queryset carrying the tenant filter under RLS
    `FORCE`. This asserts the seam is the path taken rather than trusting that
    it is.
    """
    with tenant_ctx(brazos):
        park = _park(marcus, brazos, flow)
    with tenant_ctx(lonestar):
        payload = _list_for(flow)
        assert str(park.id) not in _park_ids(payload), (
            f"{flow}: another tenant's parked draft is visible on this list"
        )
