# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-002 (EP-WRK-01) — the fourteen finished write actions that
#           only a Python shell could reach become HTTP doors, and the two
#           readers ride inside `GET /connections/{id}`. Screen: Work-002.
# Rules:    BR-SHL-025 (the server enforces every mutating call regardless of
#           the button) · BR-MET-109 (a clerk raises as many orders as they
#           want) · BR-WRK-006 (the raise takes four anchors) · BR-MET-113 /
#           114 / 116 (tag once · human-marked to-dos · the master account) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    this file — TC-1..7, named for the story's own case table
# ───────────────────────────────────────────────────────
"""US-WRK-002 TC-1..7 — the fourteen doors, and what each one refuses.

⚠ **TWO OF THE STORY'S CASES ARE BUILT DIFFERENTLY FROM HOW THEY ARE WRITTEN,
AND BOTH ARE RECORDED HERE RATHER THAN QUIETLY RESHAPED** (decision log
2026-09-04):

**TC-3 names a Billing Clerk as the actor the server refuses.** This product has
exactly three roles and A4 gives the Billing Clerk *"full on
Premises/Accounts/Reads/Billing/Payments"* — a Clerk cancelling a build is not a
permission error, it is the Clerk's job. The role A4 refuses on this family is
the **Executive**, whose cell reads *"view across operational modules"*. The
rule TC-3 asserts — the server refuses regardless of what the button looked
like — is unchanged and is asserted below; only the actor who can demonstrate it
moved.

**TC-5 asks for G52's `unreached` count on `connections.py` to fall to zero. It
was already zero and always has been**, because G52's universe is the set of
`@require_role` declarations and **`connections.py` declares none** — measured,
not assumed (the assertion below reads the module). So the gate cannot speak
about these doors either way, and the guard TC-5 actually wants is TC-7's: every
writer has a route. Reported in the lane's decision-log row.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.urls import resolve
from django.urls.exceptions import Resolver404

from apps.metering import api as metering_api
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from core import errors  # noqa: F401 — the catalogue the envelope carries codes from

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus · erin
from tests.test_us_met_helpers import (
    audit_actions,
    make_premises,
    make_unit,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


# ── the fourteen, by name. THE LIST IS THE TEST (TC-7). ─────────────────────
#: `US-WRK-002` §5's own table, verbatim. Thirteen live in `connections.py`;
#: `create_work_order` is the fourteenth and is mounted from `apps/work/api.py`
#: because Work owns the one raise every door uses.
FOURTEEN_WRITERS: tuple[str, ...] = (
    "create_connection",
    "add_connection_service",
    "transition_service",
    "submit_connection",
    "hold_connection",
    "release_connection",
    "cancel_connection",
    "set_waiting_on",
    "mark_outstanding",
    "close_outstanding",
    "create_owner_account",
    "tag_charges_to_account",
    "set_characteristic",
    "create_work_order",
)

#: The URL each writer answers on, with a concrete id substituted. Written out
#: rather than derived, because a derivation would pass on a route that resolved
#: to the WRONG view — which is the whole failure this case exists to catch.
ID = "11111111-1111-1111-1111-111111111111"
ROUTE_OF_WRITER: dict[str, tuple[str, str]] = {
    "create_connection": ("post", "/api/brazosbend/connections"),
    "add_connection_service": ("post", f"/api/brazosbend/connections/{ID}/services"),
    "transition_service": ("post", f"/api/brazosbend/connections/{ID}/services/{ID}/transition"),
    "submit_connection": ("post", f"/api/brazosbend/connections/{ID}/submit"),
    "hold_connection": ("post", f"/api/brazosbend/connections/{ID}/hold"),
    "release_connection": ("post", f"/api/brazosbend/connections/{ID}/release"),
    "cancel_connection": ("post", f"/api/brazosbend/connections/{ID}/cancel"),
    "set_waiting_on": ("post", f"/api/brazosbend/connections/{ID}/waiting-on"),
    "mark_outstanding": ("post", f"/api/brazosbend/connections/{ID}/outstanding-work"),
    "close_outstanding": (
        "post",
        f"/api/brazosbend/connections/{ID}/outstanding-work/{ID}/close",
    ),
    "create_owner_account": ("post", f"/api/brazosbend/connections/{ID}/owner-account"),
    "tag_charges_to_account": ("post", f"/api/brazosbend/connections/{ID}/charges/tag"),
    "set_characteristic": (
        "put",
        f"/api/brazosbend/connections/{ID}/units/{ID}/characteristics/meter_size",
    ),
    "create_work_order": ("post", "/api/brazosbend/work-orders"),
}


def _build(actor, address="500 Main St", service="water", submitted=False):
    """One build with one service on one unit — the shape every case needs.

    ⚠ **`submitted=True` IS NOT A CONVENIENCE, IT IS A PRECONDITION OF THE STATE
    MACHINE.** `derive_connection_state` returns `draft` for anything not yet
    submitted, **before it ever looks at the hold** — *"A build becomes the
    utility's to deliver when it is requested."* So a hold placed on a draft is
    recorded (the timestamp is written, the reason is stored) and the state
    still reads *Draft*, which is correct and is asserted on its own below. The
    first cut of these cases held an unsubmitted build and read `draft`; the
    product was right and the fixture was wrong."""
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    made = w6.add_connection_service(
        actor, connection.id, service_code=service, unit_id=unit["id"]
    )
    if submitted:
        w6.submit_connection(actor, connection.id)
        connection.refresh_from_db()
    return connection, unit, made


def _post(view, tenant, actor, role, path, data=None, **kwargs):
    return api_call(
        view, "post", path, user=actor.user, role=role, tenant=tenant, data=data or {}, **kwargs
    )


#: ⚠ **`api_call` CLEARS THE TENANT CONTEXT ON THE WAY OUT, AND IT IS RIGHT TO.**
#: `core.tenancy.tenant_context` clears rather than restores in its `finally` —
#: *"a job can never carry one tenant's context into the next tenant's loop
#: iteration"* — so an ORM read written AFTER an `api_call`, inside the same
#: outer `tenant_ctx`, raises `AUTH-003` rather than reading. Four cases in the
#: first draft of this file did exactly that. The fix is to re-enter for the
#: read, which is also honest about what is being asserted: the door's answer
#: and the row it left behind are two separate observations.
def refusal(response):
    """The G1 envelope a REFUSED call comes back as — `{code, message_key,
    params, field_errors, br_ref, trace_id}`.

    ⚠ **A REFUSAL DOES NOT PROPAGATE OUT OF A DRF VIEW AND ASSERTING
    `pytest.raises` AROUND ONE IS A TEST THAT CANNOT FAIL FOR THE RIGHT
    REASON.** `@api_view` runs `core.errors.drf_exception_handler`, so what a
    caller — a browser, or `api_call` here — receives is a Response carrying the
    envelope, not an exception. The first draft of this file asserted
    `pytest.raises(ValidationError)` and went red with *"DID NOT RAISE"* while
    the log line beside it read `key=work.order.anchor_required`: the product
    was right and the test was reading the wrong surface.

    That matters beyond tidiness. The thing `BR-SHL-025` promises a clerk is a
    SENTENCE ON A SCREEN, and only the envelope carries it. A test that catches
    the exception one layer early proves the service refuses and says nothing
    about whether anybody is ever told.
    """
    assert response.status_code >= 400, f"expected a refusal, got {response.status_code}"
    return response.data


# ════════════════════════════════════════════════════════════════════════════
# TC-1 · a clerk raises an eighth order from the screen, and the counter moves
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc1_the_raise_adds_one_order_and_the_progress_counter_moves(dana, brazos):
    """`BR-MET-109` — *Add work order* adds ONE, and a clerk may add as many as
    they want. The story's figure is *5 of 7* → *5 of 8*; the fixture here is
    smaller and the ARITHMETIC is the assertion, not the literal."""
    with tenant_ctx(brazos):
        connection, unit, _made = _build(dana)
        for order_type in ("Meter set", "Service drop"):
            w6.create_work_order(dana, connection.id, {"type": order_type, "service": "water"})
        before_done, before_total = w6.order_progress(connection)

        response = _post(
            work_api.work_orders,
            brazos,
            dana,
            "system_admin",
            "/api/brazosbend/work-orders",
            {
                "connection_id": str(connection.id),
                "type": "Meter set",
                "service": "water",
                "scope": "per_asset",
                "mode": "our_crew",
                "unit_id": unit["id"],
            },
        )
        assert response.status_code == 200, response.data
        assert response.data["order_no"], response.data
        assert response.data["connection_id"] == str(connection.id)

        after_done, after_total = w6.order_progress(connection)
        assert (after_done, after_total) == (before_done, before_total + 1)


def test_us_wrk_002_tc1_the_raise_writes_exactly_one_audit_row_naming_the_anchor(
    dana, brazos, audit_rows
):
    """Hard rule 7. The audit row is METERING's own — the view adds none."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana)
        audit_rows.clear()
        _post(
            work_api.work_orders,
            brazos,
            dana,
            "system_admin",
            "/api/brazosbend/work-orders",
            {"connection_id": str(connection.id), "type": "Meter set", "service": "water"},
        )
    created = [row for row in audit_rows if row.get("action") == "work_order.created"]
    assert len(created) == 1, audit_actions(audit_rows)
    assert created[0]["after"]["connection_no"] == connection.connection_no


def test_us_wrk_002_tc1_the_raise_takes_a_premises_with_no_build_through_the_same_door(
    dana, brazos
):
    """`BR-WRK-006` through HTTP: wave A's leak investigation, from a screen."""
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        response = _post(
            work_api.work_orders,
            brazos,
            dana,
            "system_admin",
            "/api/brazosbend/work-orders",
            {"premises_id": cedar["id"], "type": "Leak investigation", "service": "water"},
        )
        assert response.status_code == 200, response.data
        assert response.data["connection_id"] is None
        assert response.data["premises_id"] == cedar["id"]


def test_us_wrk_002_tc1_an_order_anchored_on_nothing_is_refused_with_a_sentence(dana, brazos):
    """The Python refusal comes BEFORE the database's CHECK, so the clerk reads
    a sentence rather than a constraint name (`work.order.anchor_required`)."""
    with tenant_ctx(brazos):
        answered = refusal(
            _post(
                work_api.work_orders,
                brazos,
                dana,
                "system_admin",
                "/api/brazosbend/work-orders",
                {"type": "Leak investigation", "service": "water"},
            )
        )
    assert answered["message_key"] == "work.order.anchor_required"
    assert answered["br_ref"] == "BR-WRK-006"


# ════════════════════════════════════════════════════════════════════════════
# TC-2 · hold, then release, from the screen
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc2_hold_then_release_moves_the_state_and_carries_the_reason(dana, brazos):
    with tenant_ctx(brazos):
        connection, _unit, made = _build(dana, address="18 Larkspur Ln", submitted=True)
        w6.transition_service(dana, made["id"], work_tables.SVC_IN_PROGRESS)

    held = _post(
        metering_api.connection_hold,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/hold",
        {"reason": "permit"},
        connection_id=connection.id,
    )
    assert held.status_code == 200, held.data
    assert held.data["state"] == "on_hold"
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.waiting_on == "permit"

    released = _post(
        metering_api.connection_release,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/release",
        {"waiting_on": None},
        connection_id=connection.id,
    )
    assert released.status_code == 200, released.data
    # The state RE-DERIVES from what the services say; it does not go to a
    # remembered token. That is why the hold is a timestamp (§9.1 Figure 6).
    assert released.data["state"] == "in_progress"
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.waiting_on is None


def test_def_met_3652_releasing_a_build_that_is_not_held_is_refused_and_keeps_waiting_on(
    dana, brazos
):
    """`DEF-MET-3652` — the SERVER refuses it, not only the button.

    `BR-SHL-025` has two halves: the control is disabled with its reason, AND
    the door says no to a request the screen would never send. Until 2026-09-04
    only the first half was true here. `_stamp` had `expect_unset` for the hold
    direction and no mirror, so a release on a build that was never held wrote
    `NULL` over `NULL`, answered **200**, and — because `waiting_on` rides in
    the same call — **cleared a note somebody had typed**, with an audit row
    claiming the build had been released.

    ⚠ **NO TEST COULD HAVE CAUGHT IT BY ACCIDENT, WHICH IS THE POINT.** The
    screen disables that button, so nobody wrote the case the button prevents;
    the whole suite was green over it. It was found by the wave-B browser
    walkthrough calling the door DIRECTLY from the page's own session — the one
    check in this repository that asks the server rather than the DOM.

    The case asserts both consequences, because the refusal is the cheap half:
    what actually mattered was the note that was being destroyed.
    """
    with tenant_ctx(brazos):
        connection, _unit, made = _build(dana, address="41 Larkspur Ln", submitted=True)
        w6.transition_service(dana, made["id"], work_tables.SVC_IN_PROGRESS)

    # Not on hold, but waiting on something — the combination NCT-01 draws on
    # `CON-26-0121`, and exactly the state the old code destroyed.
    waiting = _post(
        metering_api.connection_waiting_on,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/waiting-on",
        {"waiting_on": "the meter is on order"},
        connection_id=connection.id,
    )
    assert waiting.status_code == 200, waiting.data
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.held_at is None
        assert connection.waiting_on == "the meter is on order"

    refused = _post(
        metering_api.connection_release,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/release",
        {"waiting_on": None},
        connection_id=connection.id,
    )
    assert refused.status_code >= 400, refused.data
    assert refused.data["message_key"] == "metering.connection_not_stamped"
    assert refused.data["br_ref"] == "BR-MET-104"

    # …and the note is still there. This is the assertion the defect is about.
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.waiting_on == "the meter is on order"


def test_us_wrk_002_tc2_waiting_on_is_its_own_door_and_does_not_touch_the_hold(dana, brazos):
    """`NCT-01` fact 1a — waiting on something and being on hold are two
    independent axes, which is why `set_waiting_on` is a separate route."""
    with tenant_ctx(brazos):
        connection, _unit, made = _build(dana, address="1408 Elm", submitted=True)
        w6.transition_service(dana, made["id"], work_tables.SVC_IN_PROGRESS)
    response = _post(
        metering_api.connection_waiting_on,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/waiting-on",
        {"waiting_on": "materials"},
        connection_id=connection.id,
    )
    assert response.status_code == 200, response.data
    assert response.data["state"] == "in_progress"
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.waiting_on == "materials"
        # Waiting is not holding: the hold stamp is untouched.
        assert connection.held_at is None


# ════════════════════════════════════════════════════════════════════════════
# TC-3 · NEGATIVE — the server refuses regardless of the button (BR-SHL-025)
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "view,suffix,body",
    [
        ("connection_cancel", "cancel", {"reason": "duplicate"}),
        ("connection_hold", "hold", {"reason": "permit"}),
        ("connection_submit", "submit", {}),
        ("connection_owner_account", "owner-account", {}),
    ],
)
def test_us_wrk_002_tc3_an_executive_is_refused_by_the_server_on_every_write(
    dana, brazos, view, suffix, body
):
    """A4 gives the Executive VIEW across the operational modules, so a write on
    this family is 403 **even with a perfectly disabled button** — the story's
    named actor is a Billing Clerk and A4 gives the Clerk this write, so the
    demonstrable actor is the Executive (see this file's docstring)."""
    executive = staff_actor(brazos, "executive", "eve@brazosbendutilities.test")
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana)
    response = _post(
        getattr(metering_api, view),
        brazos,
        executive,
        "executive",
        f"/api/brazosbend/connections/{connection.id}/{suffix}",
        body,
        connection_id=connection.id,
    )
    assert response.status_code == 403, response.data
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        # NO WRITE. The refusal is a refusal, not a rollback of a partial act.
        assert connection.cancelled_at is None
        assert connection.held_at is None
        assert connection.submitted_at is None


def test_us_wrk_002_tc3_the_executive_may_still_READ_the_same_family(dana, brazos):
    """The asymmetry is the rule, not an oversight: A4's Executive cell on this
    family reads VIEW. A permission class that refused the read too would have
    made every `readOnly` branch on the screen unreachable — DEF-196, exactly."""
    executive = staff_actor(brazos, "executive", "eve2@brazosbendutilities.test")
    with tenant_ctx(brazos):
        _build(dana)
        response = api_call(
            metering_api.connections,
            "get",
            "/api/brazosbend/connections",
            user=executive.user,
            role="executive",
            tenant=brazos,
        )
        assert response.status_code == 200, response.data


def test_us_wrk_002_tc3_a_billing_clerk_may_write_because_a4_says_so(dana, marcus, brazos):
    """The other half of the same rule, and the reason the story's actor moved:
    refusing the Clerk here would be a permission the signed matrix does not
    have."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana, submitted=True)
    response = _post(
        metering_api.connection_hold,
        brazos,
        marcus,
        "billing_clerk",
        f"/api/brazosbend/connections/{connection.id}/hold",
        {"reason": "permit"},
        connection_id=connection.id,
    )
    assert response.status_code == 200, response.data
    assert response.data["state"] == "on_hold"


def test_us_wrk_002_tc2_a_hold_on_a_build_nobody_requested_still_reads_draft(dana, brazos):
    """The state machine's own order, pinned so it cannot drift silently:
    `cancelled` → `not submitted` → `held` → what the services say. A hold on an
    unrequested build is RECORDED — the stamp and the reason are both there —
    and the build is still a Draft, because a build becomes the utility's to
    deliver when it is requested and not before."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana, address="4 Sorrel Ct")  # NOT submitted
    response = _post(
        metering_api.connection_hold,
        brazos,
        dana,
        "system_admin",
        f"/api/brazosbend/connections/{connection.id}/hold",
        {"reason": "permit"},
        connection_id=connection.id,
    )
    assert response.status_code == 200, response.data
    assert response.data["state"] == "draft"
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.held_at is not None
        assert connection.waiting_on == "permit"


# ════════════════════════════════════════════════════════════════════════════
# TC-4 · NEGATIVE — terminal is terminal, and the refusal is a catalogue key
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc4_an_activated_service_cannot_go_back_to_pending(dana, brazos):
    with tenant_ctx(brazos):
        connection, _unit, made = _build(dana)
        w6.transition_service(dana, made["id"], work_tables.SVC_IN_PROGRESS)
        w6.transition_service(dana, made["id"], work_tables.SVC_ACTIVATED)
        answered = refusal(
            _post(
                metering_api.connection_service_transition,
                brazos,
                dana,
                "system_admin",
                f"/api/brazosbend/connections/{connection.id}/services/{made['id']}/transition",
                {"to_state": work_tables.SVC_PENDING},
                connection_id=connection.id,
                connection_service_id=made["id"],
            )
        )
    assert answered["message_key"] == "metering.connection_service_transition_refused"
    assert answered["br_ref"] == "BR-MET-104"
    # The two states BY NAME — "cannot transition" with no nouns in it is a
    # message a clerk cannot act on (`transition_service`'s own docstring).
    assert answered["params"]["from"] == work_tables.SVC_ACTIVATED
    assert answered["params"]["to"] == work_tables.SVC_PENDING


def test_us_wrk_002_tc4_every_refusal_these_doors_raise_resolves_in_the_catalogue(dana, brazos):
    """`g32`'s question asked of THIS wave's doors specifically: a `message_key`
    the screen cannot render is a refusal that communicates nothing (DEF-320).
    The gate asks it of the whole backend; this asks it of the fourteen, so the
    failure names this wave rather than arriving as a number."""
    import json
    from pathlib import Path

    catalogue = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    reachable = {
        "metering.connection_already_stamped",
        "metering.connection_cancelled",
        "metering.connection_service_state_unknown",
        "metering.connection_service_transition_refused",
        "metering.connection_payer_already_set",
        "metering.todo.title_required",
        "metering.todo.human_close_required",
        "metering.payload_not_object",
        "metering.service_not_enabled",
        "work.order.anchor_required",
    }
    missing = sorted(key for key in reachable if key not in catalogue)
    assert missing == [], missing


# ════════════════════════════════════════════════════════════════════════════
# TC-5 · G52's universe, measured rather than assumed
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc5_g52_says_nothing_about_these_doors_and_the_reason_is_measurable():
    """TC-5 asks for `connections.py`'s unreached count to fall to **0**. It was
    0 before this wave and after it, because **G52's universe is `@require_role`
    and `connections.py` declares none** — so the gate could not have reported
    these fourteen either way.

    Asserted rather than described, so that the day somebody adds a role gate to
    a connections service this case goes RED and the claim above stops being
    true silently (hard-won law 1: a comment claiming a guarantee is not one)."""
    from pathlib import Path

    source = Path(w6.__file__).read_text(encoding="utf-8")
    assert "@require_role" not in source, (
        "connections.py now declares a role gate — G52 can speak about these "
        "doors, so TC-5's claim must be re-measured against the gate itself"
    )


# ════════════════════════════════════════════════════════════════════════════
# TC-6 · TENANT ISOLATION — a stranger's id is 404, identical to an absent row
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc6_lone_star_holding_a_brazos_build_is_a_404(dana, erin, brazos, lonestar):
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana)
    with tenant_ctx(lonestar):
        stranger = _post(
            metering_api.connection_hold,
            lonestar,
            erin,
            "system_admin",
            f"/api/lonestarridge/connections/{connection.id}/hold",
            {"reason": "permit"},
            connection_id=connection.id,
        )
        absent = _post(
            metering_api.connection_hold,
            lonestar,
            erin,
            "system_admin",
            f"/api/lonestarridge/connections/{ID}/hold",
            {"reason": "permit"},
            connection_id=ID,
        )
    assert stranger.status_code == 404
    # BYTE-IDENTICAL to a row that never existed, EVERY FIELD BUT THE TRACE ID:
    # existence must not leak (G4). A status-only assertion would pass on two
    # 404s carrying different message keys, which is the leak wearing a
    # matching status code.
    one = {k: v for k, v in stranger.data.items() if k != "trace_id"}
    two = {k: v for k, v in absent.data.items() if k != "trace_id"}
    assert one == two, (one, two)
    # And nothing was written to the stranger's build.
    with tenant_ctx(brazos):
        connection.refresh_from_db()
        assert connection.held_at is None


# ════════════════════════════════════════════════════════════════════════════
# TC-7 · THE GUARD — a writer with no route is the failure (law 2's shape)
# ════════════════════════════════════════════════════════════════════════════
def test_us_wrk_002_tc7_every_one_of_the_fourteen_writers_exists_as_named():
    """The list is the story's, so a RENAMED service fails here rather than
    leaving a route pointing at nothing."""
    where = {name: (w6, work_api) for name in FOURTEEN_WRITERS}
    missing = [name for name in where if not hasattr(w6, name)]
    assert missing == [], f"named in US-WRK-002 §5 and absent from connections.py: {missing}"


def test_us_wrk_002_tc7_every_one_of_the_fourteen_writers_has_exactly_one_route():
    """**The `built is not wired` guard, in the direction that matters here.**

    Each writer's URL is resolved through `config/urls.py` — the real resolver,
    not the module's own `urlpatterns` — and the view it lands on must be the
    one that calls that writer. A route that resolved to the WRONG view would
    pass a mere `resolve() != 404`, which is why the view is named."""
    expected_view = {
        "create_connection": metering_api.connections,
        "add_connection_service": metering_api.connection_add_service,
        "transition_service": metering_api.connection_service_transition,
        "submit_connection": metering_api.connection_submit,
        "hold_connection": metering_api.connection_hold,
        "release_connection": metering_api.connection_release,
        "cancel_connection": metering_api.connection_cancel,
        "set_waiting_on": metering_api.connection_waiting_on,
        "mark_outstanding": metering_api.connection_mark_outstanding,
        "close_outstanding": metering_api.connection_close_outstanding,
        "create_owner_account": metering_api.connection_owner_account,
        "tag_charges_to_account": metering_api.connection_tag_charges,
        "set_characteristic": metering_api.connection_unit_characteristic,
        "create_work_order": work_api.work_orders,
    }
    assert set(expected_view) == set(FOURTEEN_WRITERS)
    doorless: list[str] = []
    wrong: list[str] = []
    for writer in FOURTEEN_WRITERS:
        _verb, url = ROUTE_OF_WRITER[writer]
        try:
            match = resolve(url)
        except Resolver404:
            # ⚠ CAUGHT, NOT ALLOWED TO PROPAGATE. Django's own `Resolver404`
            # carries every pattern it tried — some 900 lines of them — and a
            # failure a reader has to excavate is the shape DEF-182 warns about:
            # a check whose output cannot distinguish one cause from another.
            # The name of the writer and its URL is the whole finding.
            doorless.append(f"{writer} → {url}")
            continue
        if match.func is not expected_view[writer]:
            wrong.append(
                f"{writer} → {url} lands on {match.func.__name__}, "
                f"not {expected_view[writer].__name__}"
            )
    assert doorless == [], (
        "US-WRK-002 TC-7 — writer(s) with NO ROUTE, which is hard-won law 2 "
        f"exactly (built, tested, unreachable): {doorless}"
    )
    assert wrong == [], (
        "US-WRK-002 TC-7 — route(s) resolving to the WRONG view, which a bare "
        f"'it resolves' check would have passed: {wrong}"
    )


def test_us_wrk_002_tc7_the_two_readers_ride_inside_the_connection_detail(dana, brazos):
    """`characteristic()` and `outstanding_work()` get no route of their own —
    `07-endpoints.md` §1's closing line. Both must be ON the detail payload, or
    the "sixteen unreachable things" count has not actually fallen to zero."""
    from apps.metering import connection_reads

    with tenant_ctx(brazos):
        connection, unit, _made = _build(dana)
        w6.mark_outstanding(dana, connection.id, title="Common area has no water service")
        w6.set_characteristic(
            dana,
            unit["id"],
            service_code="water",
            key="meter_size",
            value="0.625",
            unit_of_measure="in",
        )
        detail = connection_reads.connection_detail(connection.id)

    assert [row["title"] for row in detail["outstanding"]] == [
        "Common area has no water service"
    ]
    unit_row = next(row for row in detail["unit_rows"] if row["id"] == unit["id"])
    assert unit_row["characteristics"] == [
        {
            "service": "water",
            "key": "meter_size",
            "value": "0.625",
            # HARD RULE 3 — the unit is its OWN field and is never folded into
            # the value. A caller cannot be made to guess what 0.625 measures.
            "unit_of_measure": "in",
        }
    ]


def test_us_wrk_002_tc7_a_unit_with_nothing_recorded_carries_an_empty_list_not_a_zero(
    dana, brazos
):
    """`characteristic()`'s own docstring: **None means NO CHARACTERISTIC
    RECORDED** — not that the unit does not take the service, and never zero."""
    from apps.metering import connection_reads

    with tenant_ctx(brazos):
        connection, unit, _made = _build(dana)
        detail = connection_reads.connection_detail(connection.id)
    unit_row = next(row for row in detail["unit_rows"] if row["id"] == unit["id"])
    assert unit_row["characteristics"] == []


# ── the remaining doors, each proved once: a route that is never called is a
#    route nobody has checked, and six of these fourteen are only reachable
#    from cases below. ────────────────────────────────────────────────────────
def test_us_wrk_002_the_outstanding_work_pair_marks_and_closes_through_http(dana, brazos):
    """`BR-MET-114` — a person marks it, and ONLY a person closes it."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana)
        marked = _post(
            metering_api.connection_mark_outstanding,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{connection.id}/outstanding-work",
            {"title": "Left off, because common area has no water service"},
            connection_id=connection.id,
        )
        assert marked.status_code == 200, marked.data
        assert marked.data["blocks_creation"] is False  # it NEVER blocks

        closed = _post(
            metering_api.connection_close_outstanding,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{connection.id}"
            f"/outstanding-work/{marked.data['id']}/close",
            {},
            connection_id=connection.id,
            todo_id=marked.data["id"],
        )
        assert closed.status_code == 200, closed.data
        assert closed.data["already_closed"] is False
    with tenant_ctx(brazos):
        assert w6.outstanding_work(connection.id) == []


def test_us_wrk_002_the_service_and_submit_doors_add_a_service_and_request_the_build(
    dana, brazos
):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="91 Fen Close")
        unit = make_unit(dana, premises["id"])
        created = w6.create_connection(dana, {"premises_id": premises["id"]})

        added = _post(
            metering_api.connection_add_service,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{created['id']}/services",
            {"service": "electric", "unit_id": unit["id"]},
            connection_id=created["id"],
        )
        assert added.status_code == 200, added.data
        assert added.data["service"] == "electric"
        assert added.data["created"] is True

        submitted = _post(
            metering_api.connection_submit,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{created['id']}/submit",
            {},
            connection_id=created["id"],
        )
        assert submitted.status_code == 200, submitted.data
        assert work_tables.Connection.objects.get(pk=created["id"]).submitted_at is not None


def test_us_wrk_002_the_create_door_raises_a_draft_build_against_an_existing_premises(
    dana, brazos
):
    """`POST /connections` — the thirteenth writer, riding on the list view's
    own path because Django reaches only the first view registered on one."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="200 Cypress Way")
        response = _post(
            metering_api.connections,
            brazos,
            dana,
            "system_admin",
            "/api/brazosbend/connections",
            {"premises_id": premises["id"]},
        )
        assert response.status_code == 200, response.data
        assert response.data["connection_no"].startswith("CON-")


def test_us_wrk_002_tagging_a_payer_twice_is_refused_rather_than_re_pointed(dana, brazos):
    """`BR-MET-113` — a debt that changed debtor with nothing recording the move
    is the hazard hard rule 4 exists for. A correction is a new charge on the
    right account, never a quiet re-pointing of the old one.

    The account fixture is `test_w6_connections._an_account`'s shape, reused
    rather than re-authored: a second copy of "how this suite makes an account"
    is a second thing to keep in step with `BR-CUS-1024`."""
    from apps.customers import services as customers_services

    from tests import identity_fixtures

    with tenant_ctx(brazos):
        connection, unit, _made = _build(dana, address="903 Birch Ln")
        account = customers_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": "2026-08-01",
                "contact": {"full_name": "Ridge Property LLC"},
                "customer": identity_fixtures.customer_block(
                    "Ridge Property LLC", account_type="residential"
                ),
            },
        )
        account = SimpleNamespace(id=account["id"])
        first = _post(
            metering_api.connection_tag_charges,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{connection.id}/charges/tag",
            {"account_id": str(account.id)},
            connection_id=connection.id,
        )
        assert first.status_code == 200, first.data
        answered = refusal(
            _post(
                metering_api.connection_tag_charges,
                brazos,
                dana,
                "system_admin",
                f"/api/brazosbend/connections/{connection.id}/charges/tag",
                {"account_id": str(account.id)},
                connection_id=connection.id,
            )
        )
    assert answered["message_key"] == "metering.connection_payer_already_set"
    assert answered["br_ref"] == "BR-MET-113"


def test_us_wrk_002_setting_a_characteristic_without_its_unit_of_measure_is_refused(
    dana, brazos
):
    """Hard rule 3 at the door: a number whose unit is implied by an identifier
    is a number nothing can validate or migrate (`BR-MET-108`'s own argument)."""
    with tenant_ctx(brazos):
        connection, unit, _made = _build(dana)
        answered = refusal(
            api_call(
                metering_api.connection_unit_characteristic,
                "put",
                f"/api/brazosbend/connections/{connection.id}"
                f"/units/{unit['id']}/characteristics/meter_size",
                user=dana.user,
                role="system_admin",
                tenant=brazos,
                data={"service": "water", "value": "0.625", "unit_of_measure": ""},
                connection_id=connection.id,
                unit_id=unit["id"],
                key="meter_size",
            )
        )
    # The refusal names the FIELD, so the screen can put it under the input.
    assert [row["field"] for row in answered["field_errors"]] == ["unit_of_measure"]


def test_us_wrk_002_cancelling_a_build_then_holding_it_is_refused_by_the_service(dana, brazos):
    """The danger-tier door works, and every other door on the build then
    refuses — `_refuse_if_cancelled`, which the views do not re-implement."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana)
        cancelled = _post(
            metering_api.connection_cancel,
            brazos,
            dana,
            "system_admin",
            f"/api/brazosbend/connections/{connection.id}/cancel",
            {"reason": "duplicate build"},
            connection_id=connection.id,
        )
        assert cancelled.status_code == 200, cancelled.data
        assert cancelled.data["state"] == "cancelled"
        answered = refusal(
            _post(
                metering_api.connection_hold,
                brazos,
                dana,
                "system_admin",
                f"/api/brazosbend/connections/{connection.id}/hold",
                {"reason": "permit"},
                connection_id=connection.id,
            )
        )
    assert answered["message_key"] == "metering.connection_cancelled"


def test_us_wrk_002_a_build_with_no_common_area_is_refused_only_for_want_of_an_owner(dana, brazos):
    """`BR-MET-116` AS AMENDED — `DEF-WRK-9603`.

    This case read *"a build with no common area gets no master account, by
    name"* and accepted `BR-MET-116`/`BR-CUS-083`. The PO reversed that on
    2026-09-21 — *"common area is option"* — and `create_owner_account` deleted
    `connection_no_common_area_for_master` (its docstring records the ruling),
    so the door no longer refuses a house for having no shared area. What it
    still refuses, by name, is an owner nobody has identified (`BR-CUS-1024`,
    the customers door's own guard) — which is what an empty body meets, and
    what this case now asserts. It must NEVER again be the retired common-area
    refusal."""
    with tenant_ctx(brazos):
        connection, _unit, _made = _build(dana, address="12 Juniper Row")
        answered = refusal(
            _post(
                metering_api.connection_owner_account,
                brazos,
                dana,
                "system_admin",
                f"/api/brazosbend/connections/{connection.id}/owner-account",
                {},
                connection_id=connection.id,
            )
        )
    assert answered["message_key"] != "metering.connection_no_common_area_for_master", answered
    assert answered["br_ref"] == "BR-CUS-1024", answered
    assert answered["message_key"] == "customers.account.identity_kind_required", answered


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-002@ab786097 (EP-WRK-01) · 07-endpoints.md §1 rows 1–14 · 10-execution-plan.md wave B task B1
# generated: 2026-09-04 by the CR-070 wave B build lane
# checklist: A✔ B✔ C✔ D✔ E✔(ConnectionDetailPage's action row presses these) F✔ G✔ H=n/a
# gates: RED PROVED FIRST — with `path("connections/<uuid:connection_id>/hold", …)` removed, TC-7 fails naming the writer and the URL; quoted in the lane report
# exceptions: TC-3's actor is an Executive and not the story's Billing Clerk (A4 gives the Clerk this write) · TC-5's G52 count was already 0 and the reason is asserted rather than described — both in this file's docstring and in the decision log
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
