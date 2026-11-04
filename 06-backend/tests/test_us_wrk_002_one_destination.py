# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-002 (EP-WRK-01) — the acts on a build, RE-HOSTED: reachable
#           from the premises and from the account, never from a screen of its
#           own. US-WRK-004 — the work orders at a place and on an account.
#           US-WRK-006 — the fixture grows: a 26-unit build with NO owner
#           account, and a single-unit build that has one.
# Rules:    CR-070 §W.10 / §W.11 (PO ruling 2026-09-04, one destination) ·
#           BR-WRK-006 (four anchors) · BR-WRK-026 (six filters and a 400 on a
#           seventh — UNTOUCHED, because these are paths) · BR-MET-1161 (an
#           address lives on `premises` and everything else WALKS to it) ·
#           CLAUDE.md hard rule 1 (tenant scoping; a neighbour's build is not
#           visible and not knowable)
# Tests:    this file — the five routes resolve; both hosts; the anchor word;
#           the redirect answer; isolation; and BR-WRK-026 proved unmoved
# ───────────────────────────────────────────────────────
"""CR-070 wave O — `US-WRK-002` TC-1..7 re-pointed, and `US-WRK-004` TC-1..5.

⚠ **RE-POINTED, NOT REWRITTEN.** The seven-plus-one acts these cases exercise
are the same fourteen doors wave B mounted and `test_us_wrk_002_doors.py` still
covers them at the SERVICE level, unchanged. What moved is the HOST — the screen
a person presses them from — so what this file adds is the reads that make the
two hosts possible, and the proof that a bookmark to the retired address still
lands somewhere real.
"""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from apps.work import services as work_services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _call(view, tenant, actor, role, path, **kwargs):
    return api_call(
        view, "get", f"/api/{tenant.subdomain}{path}", user=actor.user, role=role,
        tenant=tenant, **kwargs,
    )


def _build_at(actor, address, *, units=1, orders=()):
    """One build at one address, with `units` units serviced and `orders` jobs."""
    premises = make_premises(actor, address_line=address, services_available=["water"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    unit_ids = []
    for index in range(units):
        unit = make_unit(actor, premises["id"], label=f"Unit {index + 1}")
        unit_ids.append(unit["id"])
        w6.add_connection_service(actor, connection.id, service_code="water", unit_id=unit["id"])
    for order_type in orders:
        w6.create_work_order(actor, connection.id, {"type": order_type, "service": "water"})
    return premises, connection, unit_ids


# ── The routes exist at all — a future lane cannot lose the include silently ──


def test_wave_o_the_five_routes_resolve_through_config_urls():
    """`config/urls.py`'s own rule: every include is named here and then called,
    so an include that goes missing turns THIS red rather than turning a screen
    blank.

    ⚠ The four that hang off another module's noun are the interesting ones.
    metering is included BEFORE work and claims `premises/<uuid>` and
    `premises/<uuid>/deactivate`; customers is included AFTER work and claims
    `accounts/<uuid>/…` for half a dozen things. Neither claims `work-orders` or
    `build`, and this case is what says so out loud.
    """
    uuid = "018f6d4e-0000-7000-8000-000000000001"
    assert resolve(f"/api/brazosbend/premises/{uuid}/work-orders").func is work_api.premises_work_orders
    assert resolve(f"/api/brazosbend/premises/{uuid}/build").func is work_api.premises_build
    assert resolve(f"/api/brazosbend/accounts/{uuid}/work-orders").func is work_api.account_work_orders
    assert resolve(f"/api/brazosbend/accounts/{uuid}/build").func is work_api.account_build
    assert resolve(f"/api/brazosbend/work/builds/{uuid}/home").func is work_api.build_home


# ── US-WRK-004 TC-1..3 — the premises is the host that always exists ─────────


def test_us_wrk_004_tc1_the_premises_shows_its_build_and_its_jobs(dana, brazos):
    """The 26-unit build everyone works from, on the host that cannot be absent.

    ⚠ **JUDGMENT 1, PROVED RATHER THAN ASSERTED — AND THE ASSERTION BELOW IS
    WHAT PROVES IT, NOT THIS DOCSTRING.** `owner_account_id` is NULLABLE, and
    `_build_at` names no owner, so this build has 26 units and **0 owner
    accounts**. An account-only host would have rendered an empty screen on it.

    ⚠ **THIS DOCSTRING SAID `create_owner_account()` RAISES
    `NotImplementedError("OQ-373")` UNTIL 2026-09-12 (`DEF-MET-5081`).** It does
    not; `OQ-373` closed 2026-08-25 → `BR-MET-116`. **The test is unchanged and
    still passes** — which is the point worth keeping: a green test carrying a
    false reason is the least visible surface of all eight this defect covered,
    because nothing about it is ever red.
    """
    with tenant_ctx(brazos):
        premises, connection, _ = _build_at(
            dana, "1408 Elm St", units=26, orders=["Meter set", "Service drop"]
        )
        assert connection.owner_account_id is None  # judgment 1's own case

    build = _call(work_api.premises_build, brazos, dana, "system_admin",
                  f"/premises/{premises['id']}/build",
                  premises_id=premises["id"]).data["build"]
    assert build["connection_no"] == connection.connection_no
    assert build["units"] == 26
    assert build["orders"] == {"done": 0, "total": 2}
    # The home is the PREMISES, because there is no owner account to be.
    assert build["home"] == {"kind": "premises", "id": str(premises["id"])}
    # CLAUDE.md hard rule 2 — four decimals stored, two displayed, and the
    # SERVER did the rounding. A null quote is two nulls and never a zero.
    assert set(build["quote_total"]) == {"stored", "display"}

    orders = _call(work_api.premises_work_orders, brazos, dana, "system_admin",
                   f"/premises/{premises['id']}/work-orders",
                   premises_id=premises["id"]).data
    assert orders["count"] == 2
    assert {row["type"] for row in orders["results"]} == {"Meter set", "Service drop"}
    # `stands_on` is one WORD the screen turns into a sentence — never printed.
    assert {row["stands_on"] for row in orders["results"]} == {"build"}


def test_us_wrk_004_tc2_a_premises_with_no_build_answers_null_and_not_an_error(dana, brazos):
    """*"No connection work here"* is the ORDINARY answer, not a failure.

    Most premises in a utility's book were connected long before this product
    existed. The screen renders no Build tab at all on this answer (law 2,
    `G13`); an empty panel would be dead UI and a 404 would be a lie.
    """
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])

    answer = _call(work_api.premises_build, brazos, dana, "system_admin",
                   f"/premises/{cedar['id']}/build", premises_id=cedar["id"])
    assert answer.data == {"build": None}

    with tenant_ctx(brazos):
        leak = work_services.raise_work_order(
            dana, {"type": "Leak investigation", "service": "water", "premises_id": cedar["id"]}
        )
    orders = _call(work_api.premises_work_orders, brazos, dana, "system_admin",
                   f"/premises/{cedar['id']}/work-orders", premises_id=cedar["id"]).data
    # BR-WRK-006 — a leak investigation on a meter that has been in the ground
    # for years has no build, and it still belongs to the address.
    assert [row["order_no"] for row in orders["results"]] == [leak["order_no"]]
    assert orders["results"][0]["stands_on"] == "premises"
    assert orders["results"][0]["connection"] is None


def test_us_wrk_004_tc3_the_list_holds_finished_work_too(dana, brazos):
    """A person standing at an address asks *"what has happened here"*.

    ⚠ **THIS IS WHERE THE SCOPED LISTS DIFFER FROM THE DISPATCHER'S QUEUE.**
    `GET /work-orders` draws the OPEN window (`planned · in_progress ·
    blocked`); a tab that did the same would say *"no jobs"* about an address
    with twenty finished ones on it.
    """
    with tenant_ctx(brazos):
        premises, connection, _ = _build_at(dana, "500 Main St", orders=["Meter set"])
        finished = w6.create_work_order(dana, connection.id, {"type": "Gas tap", "service": "water"})
        field_close(dana, finished["id"], field_data={"ok": True}, outcome="passed")

    rows = _call(work_api.premises_work_orders, brazos, dana, "system_admin",
                 f"/premises/{premises['id']}/work-orders",
                 premises_id=premises["id"]).data["results"]
    by_no = {row["order_no"]: row for row in rows}
    assert finished["order_no"] in by_no
    # Newest first — the question is a HISTORY of one place, and a history
    # starts with what happened last.
    assert [row["order_no"] for row in rows][0] == finished["order_no"]
    # The drawer's own fields ride with the row, so the eye opens without a
    # second read. `accepted_at` is null on a completed order and THAT is the
    # review queue (BR-MET-110) — never defaulted to the completion date.
    assert by_no[finished["order_no"]]["accepted_at"] is None
    assert by_no[finished["order_no"]]["field_data"] == {"ok": True}


# ── US-WRK-004 TC-4 — the account host, reached by walking ───────────────────


def test_us_wrk_004_tc4_the_account_shows_the_work_at_its_address(dana, brazos):
    """`BR-MET-1161` — an account declares no address, so the walk is
    account → unit → premises, and the jobs come from there.

    Each row says WHICH anchor it stands on, because a person on an account sees
    the move-out's final read (on the ACCOUNT) beside the build's install jobs
    (on the BUILD), and a list that did not say would be claiming they are the
    same kind of thing.
    """
    from apps.customers import services as customer_services

    with tenant_ctx(brazos):
        premises, connection, unit_ids = _build_at(
            dana, "12 Willow Way", orders=["Meter set"]
        )
        account = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit_ids[0]),
                "account_type": "residential",
                "opened_at": "2026-08-15",
                "contact": {"full_name": "Rodriguez, M.", "phone": "+1 (281) 555-0142"},
                # BR-CUS-1024 — the door refuses an account whose party is not
                # identified. A phone is enough to open one and can never make a
                # match `strong`; this file is about where WORK is reached from,
                # not about identity.
                "customer": {
                    "display_name": "Rodriguez, M.",
                    "kind": "person",
                    "identity": {"phone": "+1 (281) 555-0142"},
                },
            },
        )
        on_account = work_services.raise_work_order(
            dana, {"type": "Final read", "service": "water", "account_id": account["id"]}
        )

    rows = _call(work_api.account_work_orders, brazos, dana, "system_admin",
                 f"/accounts/{account['id']}/work-orders",
                 account_id=account["id"]).data["results"]
    stands = {row["order_no"]: row["stands_on"] for row in rows}
    assert stands[on_account["order_no"]] == "account"
    # The build's own job is at the same address and is in the list, saying so.
    assert "build" in set(stands.values())

    # The build reader walks the same way: no owner account is set, so it is
    # found through the account's unit's premises.
    build = _call(work_api.account_build, brazos, dana, "system_admin",
                  f"/accounts/{account['id']}/build", account_id=account["id"]).data["build"]
    assert build["connection_no"] == connection.connection_no
    assert build["premises_id"] == str(premises["id"])


# ── The redirect — a bookmark is a working link and stays one ────────────────


def test_wave_o_a_bookmarked_connection_link_resolves_to_a_home(dana, brazos):
    """Judgment 5 — `/connections/<uuid>` REDIRECTS; it does not 404.

    The New Connect wizard's completion, the *New connects* tab and every
    bookmark point at that path today. A 404 would break a working link in
    order to punish a screen.
    """
    with tenant_ctx(brazos):
        premises, connection, _ = _build_at(dana, "8 Quarry Rd")

    answer = _call(work_api.build_home, brazos, dana, "system_admin",
                   f"/work/builds/{connection.id}/home", connection_id=connection.id)
    assert answer.data == {"home": {"kind": "premises", "id": str(premises["id"])}}


def test_wave_o_an_unknown_build_is_a_404_identical_to_a_neighbours(dana, erin, brazos, lonestar):
    """Hard rule 1 — *"not yours"* and *"not there"* are the SAME sentence.

    Anything else is an existence oracle across the tenant boundary: a Lone Star
    Ridge session could learn which of Brazos Bend's ids are real by watching
    which of them answered differently.
    """
    absent_id = "018f6d4e-0000-7000-8000-0000000000ff"
    with tenant_ctx(brazos):
        _, connection, _ = _build_at(dana, "3 Kiln Ln")

    stranger = _call(work_api.build_home, lonestar, erin, "system_admin",
                     f"/work/builds/{connection.id}/home", connection_id=connection.id)
    absent = _call(work_api.build_home, lonestar, erin, "system_admin",
                   f"/work/builds/{absent_id}/home", connection_id=absent_id)
    assert stranger.status_code == 404
    assert absent.status_code == 404
    # ⚠ **STATUS-ONLY WOULD NOT BE ENOUGH.** Two 404s carrying different message
    # keys is the leak wearing a matching status code (`G4`, and
    # `test_us_wrk_002_doors.py` makes the same assertion on the hold door). The
    # bodies must be identical but for the trace id.
    def _without_trace(payload):
        body = dict(payload or {})
        body.pop("trace_id", None)
        return body

    assert _without_trace(stranger.data) == _without_trace(absent.data)


def test_wave_o_lone_star_ridge_sees_none_of_brazos_bends_builds(dana, erin, brazos, lonestar):
    """Hard rule 1 on both scoped reads, with RLS `FORCE` underneath.

    A cross-tenant premises id yields an EMPTY page rather than a refusal, and
    that is the same sentence as *"nothing has happened at this address"* — the
    neighbour cannot tell the two apart, which is the point.
    """
    with tenant_ctx(brazos):
        premises, _, _ = _build_at(dana, "44 Foundry St", orders=["Meter set"])

    assert _call(work_api.premises_build, lonestar, erin, "system_admin",
                 f"/premises/{premises['id']}/build",
                 premises_id=premises["id"]).data == {"build": None}
    assert _call(work_api.premises_work_orders, lonestar, erin, "system_admin",
                 f"/premises/{premises['id']}/work-orders",
                 premises_id=premises["id"]).data["count"] == 0


def test_wave_o_br_wrk_026_did_not_move_the_dispatcher_still_takes_six(dana, brazos):
    """⚠ **THE RULE THIS WAVE WAS CAREFUL NOT TO TOUCH.**

    `BR-WRK-026` gives the dispatcher exactly six filters and a `400` on a
    seventh. Scoping by PATH is what keeps that true: adding *account* and
    *premises* as filters would have made it eight and put a signed rule in the
    way of a screen (execution plan judgment 3). This case asserts the shape of
    the un-scoped list is unchanged — no `premises` and no `account` filter
    appeared on it.
    """
    with tenant_ctx(brazos):
        _build_at(dana, "9 Anvil Ct", orders=["Meter set"])

    data = api_call(
        work_api.work_orders, "get", f"/api/{brazos.subdomain}/work-orders",
        user=dana.user, role="system_admin", tenant=brazos,
        query={"f.premises_id": "anything", "f.account_id": "anything"},
    ).data
    # An UNDECLARED param is ignored, never refused (BR-SHL-011) — so the two
    # filters that would have broken the rule simply do not exist, and the list
    # answers as though they were not sent.
    assert data["count"] == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-002 · US-WRK-004 · US-WRK-006 (EP-WRK-01) · CR-070 §W.10 · §W.11
# generated: 2026-09-04 by the CR-070 wave O build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_wrk_002_one_destination.py · G78 (the reads are Work's; nothing writes a foreign row)
# exceptions: the SEVEN acts themselves are still covered by tests/test_us_wrk_002_doors.py at the service level, unchanged by this wave — re-pointing the HOST does not re-prove the doors
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
