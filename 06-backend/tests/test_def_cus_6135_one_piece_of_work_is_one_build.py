# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-6135 (parking a draft build and finishing it created a
#          SECOND build, and left the draft row behind as a third)
# Rules:   BR-SHL-048 (d), CONFIRMED-AS-AMENDED 2026-09-21 — PO verbatim:
#          *"this is big problem - we cannot create two build - you can update
#          the existing build"* · BR-SHL-048 (a) — a park carries COPIED VALUES
#          and NO foreign key, which is the mechanism this uses · BR-MET-112 —
#          nothing is written until the last button, unchanged · CR-122-BRC06 —
#          the two flows that MINT a draft reference, untouched · CLAUDE.md
#          hard rule 1 (tenant scoping)
# Process: 12-governance/22-product-maintenance-process.md §4
# ───────────────────────────────────────────────────────
"""**One piece of work is one build, and one row once it is finished.**

WHAT WAS BROKEN
---------------
Approving `SR-26-0002` raised `CON-26-0129` as a draft. Parking its wizard
wrote a `wizard_parks` row with `flow=new_connect` and `reference` **EMPTY**,
so the New connects tab drew a row whose connection cell was **blank**; and the
last press, after the resume, answered `200` with **`CON-26-0132`** — a second
build on the same property naming no application — while `CON-26-0129` stayed a
draft and stayed the one the application pointed at.

**Two halves, and this file owns the server's.** The browser half — the park
forgetting which build it was — is `ParkedBuildFinishesItself.dom.test.tsx`.

WHAT WOULD MAKE THESE CASES PASS WRONGLY (CLAUDE.md law 7, habit 2)
-------------------------------------------------------------------
* **Counting rows on the New connects LIST.** That list draws parked wizards as
  rows too, so parking twice moves its count by two with nothing committed. The
  walk's own first version did exactly that and announced a second build over a
  run in which nothing was written. Every case below reads the `connections`
  TABLE or the id the service answers with.
* **Asserting the draft moved off `draft`.** A second build leaves the first
  one exactly where it was, so `state` cannot tell the two apart. The verdict is
  the **id**.
* **Asserting a reference is non-empty.** It would pass on a draft carrying a
  freshly minted `MVI-` number, which is the thing this must NOT do — a build
  has a number already and minting a second is the paper half of the defect. So
  the reference is compared to the build's own `connection_no`.
"""

import pytest

from apps.metering import connection_reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.tenancy import wizard_parks

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _park_body(**over):
    """What `POST /wizard-parks` receives when a clerk presses `Park it` in the
    New Connect wizard. `subject_ref` is the browser's own spelling."""
    body = {
        "flow": "new_connect",
        "subject_label": "500 Main St",
        "subject_ref": {},
        "step": 1,
        "values": {"draft": {"owner": {"name": "Brazos Bend Warehousing"}}},
        "waiting_on": "customer",
    }
    body.update(over)
    return body


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE PARK NAMES THE BUILD IT IS FINISHING
# ════════════════════════════════════════════════════════════════════════════
def test_a_park_carries_the_builds_own_number_rather_than_minting_one(brazos, dana):
    """`BR-SHL-048 (d)`. The row a parked wizard leaves on the New connects tab
    read BLANK; it now reads `CON-26-0129`."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        draft = w6.create_connection(dana, {"premises_id": str(premises["id"])})

        row = wizard_parks.park(
            dana,
            _park_body(
                subject_ref={
                    "connection_id": draft["id"],
                    "connection_no": draft["connection_no"],
                }
            ),
        )

        assert row.reference == draft["connection_no"]
        # ⛔ NOT A NEW NUMBER. `new_connect` is not in `DRAFT_REFERENCE_SERIES`
        # and must not join it: a build already has a number.
        assert not row.reference.startswith("MVI-")


def test_the_list_row_shows_that_number_and_stops_claiming_there_is_no_build(brazos, dana):
    """The served row, not the column — `park_row` is what the tab draws."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        draft = w6.create_connection(dana, {"premises_id": str(premises["id"])})
        row = wizard_parks.park(
            dana,
            _park_body(
                subject_ref={
                    "connection_id": draft["id"],
                    "connection_no": draft["connection_no"],
                }
            ),
        )

        served = connection_reads.park_row(row)

        assert served["connection_no"] == draft["connection_no"]
        # ⛔ *"Nobody has raised this connection yet"* became FALSE for this
        # case on 2026-09-21. A stated absence that outlives its cause is a lie
        # the product tells about itself (hard-won law 1).
        assert served["connection_no_unavailable"] is None


def test_a_new_connect_started_from_scratch_still_names_nothing(brazos, dana):
    """`BR-MET-112` unchanged: no build exists, so there is no number, and the
    absence below is the sentence that was written for exactly this case."""
    with tenant_ctx(brazos):
        row = wizard_parks.park(dana, _park_body())

        assert row.reference is None
        served = connection_reads.park_row(row)
        assert served["connection_no"] is None
        assert served["connection_no_unavailable"]["br_ref"] == "BR-SHL-048"


def test_a_second_park_of_the_same_build_declines_the_number_and_never_refuses(brazos, dana):
    """Two tabs, one build. `uq_wizard_parks_tenant_reference_ci` is one number
    to one draft, and meeting it as a 500 would lose an afternoon's typing —
    which is the original defect wearing a new hat.

    ⚠ **THE SECOND DRAFT STILL CARRIES THE BUILD'S ID**, so it still FINISHES
    that build. The number is the label; the id is the ruling."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        draft = w6.create_connection(dana, {"premises_id": str(premises["id"])})
        ref = {"connection_id": draft["id"], "connection_no": draft["connection_no"]}

        first = wizard_parks.park(dana, _park_body(subject_ref=ref))
        second = wizard_parks.park(dana, _park_body(subject_ref=ref))

        assert first.reference == draft["connection_no"]
        assert second.reference is None
        assert second.subject_ref["connection_id"] == draft["id"]


# ════════════════════════════════════════════════════════════════════════════
# 2 · THE LAST PRESS FINISHES THAT BUILD AND SPENDS THE DRAFT
# ════════════════════════════════════════════════════════════════════════════
def _wizard_plan(connection_id, premises_id, **over):
    plan = {
        "premises": {"id": str(premises_id)},
        "mode": "our_crew",
        "scope": "new_units",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
        "connection_id": connection_id,
        "wizard_park_id": None,
        "units": [{"label": "Apt 1", "is_common_area": False}],
        "meters": [],
        "plan_assignments": [],
        "create_owner_account": False,
        "owner": {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
    }
    plan.update(over)
    return plan


def test_finishing_a_resumed_build_leaves_one_build_and_one_row(brazos, dana):
    """The whole ruling, in one press."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        draft = w6.create_connection(dana, {"premises_id": str(premises["id"])})
        park = wizard_parks.park(
            dana,
            _park_body(
                subject_ref={
                    "connection_id": draft["id"],
                    "connection_no": draft["connection_no"],
                }
            ),
        )
        builds_before = work_tables.Connection.objects.count()

        built = w6.commit_new_connect(
            dana,
            _wizard_plan(draft["id"], premises["id"], wizard_park_id=str(park.id)),
        )

        # ⛔ THE VERDICT: the SAME id, which needs no denominator.
        assert built["id"] == str(draft["id"])
        assert work_tables.Connection.objects.count() == builds_before, "no second build"
        # And the draft that was holding the typing is spent, so the tab draws
        # ONE row for this piece of work.
        assert not tenancy_models.WizardPark.objects.filter(pk=park.id).exists()


def test_a_draft_already_discarded_never_refuses_the_build(brazos, dana):
    """A clerk may have thrown the draft away in another tab, or pressed the
    last button twice. Neither is a reason to lose eight steps of work."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        draft = w6.create_connection(dana, {"premises_id": str(premises["id"])})
        park = wizard_parks.park(dana, _park_body())
        wizard_parks.discard(dana, park.id)

        built = w6.commit_new_connect(
            dana,
            _wizard_plan(draft["id"], premises["id"], wizard_park_id=str(park.id)),
        )

        assert built["id"] == str(draft["id"])


def test_a_build_started_from_scratch_and_parked_also_spends_its_draft(brazos, dana):
    """`BR-MET-112`'s path: no `connection_id`, so the press CREATES the build —
    exactly one — and the draft is still spent."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        park = wizard_parks.park(dana, _park_body())
        builds_before = work_tables.Connection.objects.count()

        built = w6.commit_new_connect(
            dana,
            _wizard_plan(None, premises["id"], wizard_park_id=str(park.id)),
        )

        assert work_tables.Connection.objects.count() == builds_before + 1, "exactly one"
        assert built["id"] is not None
        assert not tenancy_models.WizardPark.objects.filter(pk=park.id).exists()


def test_a_press_that_names_no_draft_touches_no_draft(brazos, dana):
    """The ordinary case: most presses were never parked, and a park belonging
    to somebody else's unfinished work must survive one."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="500 Main St")
        somebody_elses = wizard_parks.park(dana, _park_body())

        w6.commit_new_connect(dana, _wizard_plan(None, premises["id"]))

        assert tenancy_models.WizardPark.objects.filter(pk=somebody_elses.id).exists()


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-SHL-048 (d) · 02-decision-log.md 2026-09-21 ("ONE PIECE OF WORK IS
#         ONE BUILD") · DEF-CUS-6135
# generated: 2026-09-21 by lane PARK-1
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
