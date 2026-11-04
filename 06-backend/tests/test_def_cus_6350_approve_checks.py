# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6350 — Approve checked nothing about the property or the
#           unit, so two move-ins for one unit could both be approved and a
#           move-in onto an occupied unit failed only on move day.
# Rulings:  PO 2026-09-23 (decision log, §4 of *"THE FEE TABLE'S COLUMNS …
#           AND *APPROVE* CHECKS THE PROPERTY AND UNIT BEFORE IT IS PRESSED"*,
#           and *"RULED: A NEW CONNECTION ONLY WHERE THE ADDRESS IS NOT IN
#           PREMISES — IN ANY STATUS"*, `OQ-CUS-12615` CLOSED)
# Rules:    B14 rule 31 (the refusal names an ACCOUNT NUMBER, never an id) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 8 (the address
#           is walked to, never copied)
# Tests:    this file (sqlite) · the same file on real PostgreSQL via
#           10-scripts/proof-db.sh (hard-won law 14 — the occupancy read)
# ───────────────────────────────────────────────────────
"""**Approve checks the place before it is pressed — proved through the doors a
clerk's press reaches** (`approve_and_raise`, and the detail read the window
draws from).

RED FIRST, IN THIS HARNESS (hard-won law 7). Run against the tip this lane
started from (`4f3cda892`), the approval cases below fail because the product
APPROVED what they expect it to refuse — `Failed: DID NOT RAISE <class
'core.errors.BizError'>` — and the payload cases fail with `KeyError` /
`StopIteration` because no place condition was served. The run is quoted in
this lane's conformance record.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2), asked before any
green was trusted:

  * **A refusal for the wrong reason.** Every refused case asserts the
    `message_key` AND its params — an arrears refusal or a missing outcome would
    also raise `BizError`, and a case that only caught the class would pass over
    it. The arrears search is recorded in every fixture for exactly that reason.
  * **"Free" because nothing was there to find.** The master-account case
    ASSERTS the master account exists at the address before approving, so the
    pass cannot come from an empty table.
  * **"Waiting" read off the response.** The second-move-in case reads the job
    back out of `move_in_jobs` before approving the second request.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import move_in_jobs
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from core import errors

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_name": "David, Tim",
    "applicant_email": "tim.david@example.test",
    "applicant_phone": "641-555-0116",
    "property_type": "rental_tenant_applying",
    "what_they_said": "Moving into the flat on the first",
}

_C = "customers.serviceRequest.condition."


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING
# ═══════════════════════════════════════════════════════════════════════════
def _highland(actor, **overrides):
    """`highland park, Ottumwa` — the PO's own property, through the real door."""
    payload = {
        "address_line": "highland park",
        "city": "Ottumwa",
        "state": "IA",
        "postal_code": "52501",
        "owner_manager": "Highland Park Holdings LLC",
    }
    payload.update(overrides)
    return make_premises(actor, **payload)


def _served_unit(actor, tenant, premises, *, label):
    """A unit that can take an account — a plan and a service point, the SHARED
    fixtures' way (`test_br_cus_1077_move_in_job._served_unit`), never a second
    builder."""
    from apps.metering import services as metering_services

    unit = make_unit(actor, premises["id"], label=label)
    plan = make_plan(tenant, name=f"DEF-CUS-6350 {label}", services=("electric",))
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _request(actor, *, outcome_address="12 Highland Park", **capture):
    """A submitted request with the arrears search recorded — the shortest walk
    to the point the Approve window opens on, with no other condition blocking.
    """
    row = sr.create_request(actor, {**CAPTURE, "address_as_given": outcome_address, **capture})
    sr.submit(actor, row.id)
    sr.link_customer(actor, row.id, customer_id=None)
    return sr.request_row(row.id)


def _occupy(actor, unit, *, name="Prior, Tenant"):
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _refusal(actor, request, **kw):
    with pytest.raises(errors.BizError) as caught:
        sr.approve_and_raise(actor, request.id, **kw)
    return caught.value


def _window(request, outcome):
    """The rows the Approve window draws for `outcome`, read from the detail."""
    detail = reads.detail(request.id)
    served = detail["decision"]["what_approving_will_do"][outcome]["conditions"]
    return {row["key"]: row for row in served["conditions"]}, served


# ═══════════════════════════════════════════════════════════════════════════
# 1 · MOVE-IN — the four place conditions
# ═══════════════════════════════════════════════════════════════════════════
def test_a_move_in_onto_an_occupied_unit_is_refused_naming_the_account(brazos, dana):
    """**(3) The unit is free.** Occupied → refused, and the sentence names WHO
    is there by ACCOUNT NUMBER (B14 rule 31), which is what the window prints."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = _served_unit(dana, brazos, premises, label="1")
        occupant = _occupy(dana, unit)
        request = _request(dana, picked_unit_id=str(unit["id"]))

        refusal = _refusal(dana, request, outcome="move_in")

        assert refusal.message_key == _C + "unitOccupied"
        assert refusal.params["account_no"] == occupant["account_no"]
        assert refusal.params["condition"] == "unit_free"
        # Nothing was written: the outcome travelled WITH the approval and
        # rolled back with it (`DEF-CUS-5427`), and no job was raised.
        assert sr.request_row(request.id).state == customers_models.ServiceRequest.SUBMITTED
        assert not move_in_jobs.MoveInJob.objects.filter(request_id=request.id).exists()


def test_a_vacant_unit_billed_to_the_master_account_reads_free(brazos, dana):
    """**A master account names no unit, so it occupies none** — the ruling's own
    clause. Proved against a master account that is ASSERTED to exist, so the
    pass cannot come from an empty table."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = make_unit(dana, premises["id"], label="2")
        masters = customers_models.Account.objects.filter(
            tenant_id=brazos.id, premises_id=premises["id"], kind="master"
        )
        if not masters.exists():
            # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
            top_up_homes(dana, premises["id"])
            customers_services.create_master_account(
                dana,
                {
                    "premises_id": premises["id"],
                    "account_type": "commercial",
                    "opened_at": "2026-07-01",
                    "customer": identity_fixtures.customer_block(
                        "Highland Park Holdings LLC", kind="company"
                    ),
                },
            )
        master = masters.get()
        assert master.unit_id is None  # the reason it cannot occupy anything
        request = _request(dana, picked_unit_id=str(unit["id"]))

        rows, _served = _window(request, "move_in")
        assert rows["unit_free"]["state"] == "clear"
        out = sr.approve_and_raise(dana, request.id, outcome="move_in")
        assert out["request"].state == customers_models.ServiceRequest.APPROVED
        assert out["job"]["raised"]["kind"] == "move_in"


def test_the_approved_move_in_job_carries_the_requested_date(brazos, dana):
    """**`OQ-CUS-12616` step 6 — the job the clerk lands on carries the date the
    applicant asked for.**

    Read through the page the landing opens (`/moves/{MVI-…}` →
    `move_record_reads.record_detail`), by the job's own NUMBER, never its id.
    The date is READ THROUGH THE LINK to the request (`move_in_jobs` §2) — the
    job stores none — so this proves the walk, not a copy.

    ⚠ **PENDING ON LANE `REQ-FIX` FOR ITS CAPTURE HALF, BY NAME.** This case
    sets the request's `requested_start` through `update_request`, the door the
    server has today. Whether the CAPTURE SCREEN writes that date is `REQ-FIX`'s
    work on `ServiceRequestCapturePage.tsx` and had not landed when this was
    written (tip `07d75275b`); when it does, a browser walk from capture to the
    job is the proof this case cannot give.
    """
    from apps.customers import move_record_reads

    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = _served_unit(dana, brazos, premises, label="7")
        request = _request(dana, picked_unit_id=str(unit["id"]))
        sr.update_request(dana, request.id, {"requested_start": "2026-10-01"})

        out = sr.approve_and_raise(dana, request.id, outcome="move_in")
        move_no = out["job"]["raised"]["move_no"]
        assert move_no and move_no.startswith("MVI-")

        page = move_record_reads.record_detail(move_no)
        assert page["move_no"] == move_no
        assert page["effective_on"] == "2026-10-01"
        assert page["what_happened"]["moved_in_on"]["value"] == "2026-10-01"
        assert page["request"]["request_no"] == request.request_no


@requires_postgres
def test_the_move_in_job_is_raised_after_the_approval_has_committed(brazos, dana, monkeypatch):
    """**`DEF-CUS-6421` — found by this lane's browser walk, not by any test.**

    `approve_and_raise` raises the job AFTER its own transaction commits
    (`BR-WRK-055`), and the move-in job's number was allocated with
    `SELECT … FOR UPDATE` in whatever transaction the caller had — none. On
    PostgreSQL Django refuses that (*"select_for_update cannot be used outside
    of a transaction"*), so every move-in approved through the screen read
    *The job could not be opened.* and the clerk could never land on the job
    (`OQ-CUS-12616`).

    ⚠ **WHY THIS NEEDS A STAND-IN, AND WHAT IT STANDS IN FOR.** Every pytest
    case runs inside a wrapping transaction, so autocommit is never on here
    and the refusal cannot happen as it does for a real request. The stand-in
    reports autocommit ON whenever no atomic block is open BEYOND the test's
    own wrapper — exactly the state a real request is in once the approval has
    committed — and leaves Django's own check to do the refusing. SQLite has no
    `FOR UPDATE`, so the check never runs there: PostgreSQL only (law 14).

    RED without the fix — `move_in_jobs.py` as it stands at `286458b98` and at
    `4ab6b289f` — on PostgreSQL, in this harness:
    `TransactionManagementError: select_for_update cannot be used outside of a
    transaction.` — logged, and `job` came back `not_raised`.
    """
    from django.db import connection

    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = _served_unit(dana, brazos, premises, label="8")
        request = _request(dana, picked_unit_id=str(unit["id"]))

        wrapper_depth = len(connection.atomic_blocks)
        real = connection.get_autocommit
        monkeypatch.setattr(
            connection,
            "get_autocommit",
            lambda: len(connection.atomic_blocks) <= wrapper_depth or real(),
        )
        out = sr.approve_and_raise(dana, request.id, outcome="move_in")

        assert "raised" in out["job"], out["job"]
        assert out["job"]["raised"]["move_no"].startswith("MVI-")
        assert move_in_jobs.MoveInJob.objects.filter(request_id=request.id).count() == 1


def test_a_second_move_in_for_the_same_unit_is_refused_naming_the_first(brazos, dana):
    """**(4) No other move-in waiting.** The PO's own case: two applications for
    `U-00003`; the first approved raises a pending job, the second is refused
    and told which application holds the unit."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = make_unit(dana, premises["id"], label="3")
        court = _request(dana, applicant_name="District Court", picked_unit_id=str(unit["id"]))
        tim = _request(dana, picked_unit_id=str(unit["id"]))

        sr.approve_and_raise(dana, court.id, outcome="move_in")
        job = move_in_jobs.MoveInJob.objects.get(request_id=court.id)
        assert job.state == move_in_jobs.STATE_PENDING

        refusal = _refusal(dana, tim, outcome="move_in")
        assert refusal.message_key == _C + "moveInWaiting"
        assert refusal.params["request_no"] == court.request_no
        assert refusal.params["condition"] == "no_other_move_in"


def test_a_move_in_whose_address_is_not_in_premises_is_refused(brazos, dana):
    """**(1) Property on file.** And the three checks after it are NOT REACHED —
    one problem, told once, not three blockers for one cause."""
    with tenant_ctx(brazos):
        request = _request(dana, outcome_address="4 Nowhere Lane")

        refusal = _refusal(dana, request, outcome="move_in")
        assert refusal.message_key == _C + "propertyNotOnFile"
        assert refusal.params["blocking"] == "premises_on_file"

        rows, served = _window(request, "move_in")
        assert [key for key in rows][:4] == [
            "premises_on_file",
            "unit_chosen",
            "unit_free",
            "no_other_move_in",
        ]
        assert rows["premises_on_file"]["state"] == "blocked"
        for key in ("unit_chosen", "unit_free", "no_other_move_in"):
            assert rows[key]["state"] == "not_reached", key
            assert rows[key]["blocking"] is False, key
        assert served["blocking"] == ["premises_on_file"]
        assert "unit_free" not in served["outstanding"]


def test_a_move_in_with_a_property_and_no_unit_chosen_is_refused(brazos, dana):
    """**(2) A unit is chosen where the premises has units.**"""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        make_unit(dana, premises["id"], label="1")
        make_unit(dana, premises["id"], label="2")
        request = _request(dana, picked_premises_id=str(premises["id"]))

        refusal = _refusal(dana, request, outcome="move_in")
        assert refusal.message_key == _C + "unitNotChosen"
        assert refusal.params["count"] == 2


def test_a_move_in_at_a_property_with_no_units_is_refused_with_its_own_sentence(brazos, dana):
    """A move-in opens an account ON A UNIT (`BR-CUS-020`), so a building with
    none would fail on move day — told as *no units here*, not *pick one*."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        request = _request(dana, picked_premises_id=str(premises["id"]))

        refusal = _refusal(dana, request, outcome="move_in")
        assert refusal.message_key == _C + "propertyHasNoUnits"


def test_the_window_serves_the_move_in_rows_with_numbers_not_ids(brazos, dana):
    """What the window prints for a clear move-in: the place, the unit NUMBER and
    label — and no database id anywhere in a param (B14 rule 31)."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        unit = make_unit(dana, premises["id"], label="1")
        request = _request(dana, picked_unit_id=str(unit["id"]))

        rows, served = _window(request, "move_in")
        assert rows["premises_on_file"]["params"]["place"] == "highland park, Ottumwa"
        assert rows["unit_chosen"]["params"] == {"unit_no": unit["unit_no"] or "", "label": "1"}
        assert rows["unit_free"]["message_key"] == _C + "unitFree"
        assert rows["no_other_move_in"]["message_key"] == _C + "noOtherMoveIn"
        assert served["blocking"] == []
        for row in rows.values():
            for value in (row["params"] or {}).values():
                assert str(value) not in (str(unit["id"]), str(premises["id"]))


# ═══════════════════════════════════════════════════════════════════════════
# 2 · NEW CONNECTION — only where the address is NOT in Premises
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status", ["active", "draft", "pending", "inactive"])
def test_a_new_connection_at_a_property_in_premises_is_refused_whatever_its_status(
    brazos, dana, status
):
    """PO 2026-09-23: *"we dont allow these status - dont create new request even
    if property is in draft, pending or inactive"*. PRESENCE decides; the status
    column is never read."""
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        premises = _highland(dana)
        metering_models.Premises.objects.filter(pk=premises["id"]).update(status=status)
        request = _request(dana, picked_premises_id=str(premises["id"]))

        refusal = _refusal(dana, request, outcome="new_connection")
        assert refusal.message_key == _C + "addressInPremises"
        assert refusal.params["property"] == "highland park"


def test_an_exact_match_on_file_is_refused_without_a_choice(brazos, dana):
    """The applicant typed the address the way it is on file, and nobody picked
    it: it is still IN Premises. Tidied — case and `St`/`Street` — before the
    comparison."""
    with tenant_ctx(brazos):
        _highland(dana, address_line="500 Main Street", postal_code="52501")
        request = _request(
            dana,
            outcome_address="500 MAIN ST",
            address_postal_code_as_given="52501",
        )
        refusal = _refusal(dana, request, outcome="new_connection")
        assert refusal.message_key == _C + "addressInPremises"


def test_in_premises_grades_new_connection_not_possible_before_the_click(brazos, dana):
    """PO 2026-10-11, option A — the window greys New connection out WITH its
    reason instead of offering it and refusing after. The grade is read off the
    same condition the refusal is, so the two cannot disagree."""
    with tenant_ctx(brazos):
        _highland(dana, address_line="500 Main Street", postal_code="52501")
        request = _request(dana, outcome_address="500 MAIN ST", address_postal_code_as_given="52501")
        options = {row["outcome"]: row for row in reads.detail(request.id)["decision"]["options"]}
    assert options["new_connection"]["verdict"] == "not_possible"
    assert options["new_connection"]["message_key"] == "customers.serviceRequest.checkFact.addressInPremises"
    assert options["move_in"]["verdict"] != "not_possible"


def test_a_near_match_keeps_new_connection_pickable(brazos, dana):
    """A NEAR match is a question (*same property* or *new address*), not a
    refusal — so it is NOT greyed out."""
    with tenant_ctx(brazos):
        _highland(dana)
        request = _request(dana, outcome_address="highland pk")
        options = {row["outcome"]: row for row in reads.detail(request.id)["decision"]["options"]}
    assert options["new_connection"]["message_key"] != "customers.serviceRequest.checkFact.addressInPremises"


def test_a_near_match_blocks_until_the_clerk_says_it_is_a_new_address(brazos, dana):
    """**`highland pk` looks like `highland park`.** Approve stays OFF by default
    — a duplicate can never be created by not looking — and *It's a new address*,
    sent WITH the approval, clears it and is recorded with the clerk's name."""
    with tenant_ctx(brazos):
        _highland(dana)
        request = _request(dana, outcome_address="highland pk")

        rows, _served = _window(request, "new_connection")
        assert rows["address_not_in_premises"]["state"] == "choose"
        assert rows["address_not_in_premises"]["blocking"] is True
        assert rows["address_not_in_premises"]["params"]["as_given"] == "highland pk"
        assert rows["address_not_in_premises"]["params"]["property"] == "highland park"

        refusal = _refusal(dana, request, outcome="new_connection")
        assert refusal.message_key == _C + "addressLooksLike"

        out = sr.approve_and_raise(dana, request.id, outcome="new_connection", address_is_new=True)
        assert out["request"].state == customers_models.ServiceRequest.APPROVED
        events = customers_models.ServiceRequestEvent.objects.filter(
            request_id=request.id, note_type="address_declared_new"
        )
        assert events.count() == 1


def test_same_property_picks_it_and_then_the_refusal_names_it(brazos, dana):
    """*Same property* is the capture pick (`picked_premises_id`) — after it, the
    request is IN Premises and the new connection is refused by name."""
    with tenant_ctx(brazos):
        premises = _highland(dana)
        request = _request(dana, outcome_address="highland pk")
        rows, _ = _window(request, "new_connection")
        chosen = rows["address_not_in_premises"]["params"]["premises_id"]
        assert chosen == str(premises["id"])

        sr.update_request(dana, request.id, {"picked_premises_id": chosen})
        refusal = _refusal(dana, sr.request_row(request.id), outcome="new_connection")
        assert refusal.message_key == _C + "addressInPremises"


def test_a_new_address_is_allowed_and_raises_the_build(brazos, dana):
    with tenant_ctx(brazos):
        _highland(dana)
        request = _request(dana, outcome_address="77 Quarry Road")
        rows, served = _window(request, "new_connection")
        assert rows["address_not_in_premises"]["message_key"] == _C + "addressNotInPremises"
        assert rows["no_open_request_here"]["state"] == "clear"
        assert served["blocking"] == []
        # ⚠ no Unit-free row for a new connection — PO's layout.
        assert "unit_free" not in rows

        out = sr.approve_and_raise(dana, request.id, outcome="new_connection")
        assert out["job"]["raised"]["kind"] == "connection"


def test_a_second_open_application_for_the_same_new_address_is_refused(brazos, dana):
    """Both builds would create the premises at their last button — the one
    duplicate the Premises check cannot see, because it does not exist yet."""
    with tenant_ctx(brazos):
        first = _request(dana, outcome_address="77 Quarry Road", applicant_name="Rosa Alvarez")
        second = _request(dana, outcome_address="77 quarry rd")
        sr.approve_and_raise(dana, first.id, outcome="new_connection")

        refusal = _refusal(dana, second, outcome="new_connection")
        assert refusal.message_key == _C + "openRequestHere"
        assert refusal.params["request_no"] == first.request_no


def test_address_is_new_is_only_a_literal_true_on_the_wire(brazos, dana):
    """A string `"true"` is not a yes. A truthy string read as one would clear
    the one check that stops a duplicate address being built — so the door
    reads a JSON `true` and nothing else, and says the refusal in words."""
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.customers import service_request_api as api

    with tenant_ctx(brazos):
        _highland(dana)
        request = _request(dana, outcome_address="highland pk")
    path = f"/api/v1/service-requests/{request.id}/approve"
    assert resolve(path).func is api.service_request_approve
    call = APIRequestFactory().post(
        path, {"outcome": "new_connection", "address_is_new": "true"}, format="json"
    )
    force_authenticate(call, user=dana.user)
    call.tenant_role = "system_admin"
    call.tenant_id = brazos.id
    with tenant_ctx(brazos):
        response = api.service_request_approve(call, request_id=str(request.id))
    assert response.status_code == 422, response.data
    assert "addressLooksLike" in str(response.data)


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE MATCHER — metering's one answer, on worked pairs
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("a", "b", "verdict"),
    [
        ("highland pk", "highland park", "near"),
        ("500 MAIN ST", "500 Main Street", "exact"),
        ("500 Main St.", "500 main street", "exact"),
        ("12 Main Street", "21 Main Street", "none"),
        ("77 Quarry Road", "77 quarry rd", "exact"),
        ("Oak Ridge Drive", "Elm Street", "none"),
    ],
)
def test_same_place_on_worked_pairs(a, b, verdict):
    from apps.metering import address_match

    assert address_match.same_place(a, b) == verdict


def test_a_different_postcode_is_a_different_place():
    from apps.metering import address_match

    assert (
        address_match.same_place("500 Main St", "500 Main St", postcode_a="52501", postcode_b="52502")
        == "none"
    )


def test_the_matcher_says_how_many_rows_it_compared(brazos, dana):
    """Law 7's fifth shape: *nothing close* and *nothing searched* are different
    answers, so the count travels."""
    from apps.metering import address_match

    with tenant_ctx(brazos):
        _highland(dana)
        answer = address_match.premises_matching_address("highland pk")
        assert answer["match"] == "near"
        assert answer["compared"] >= 1
        assert address_match.premises_matching_address("zz")["compared"] == 0
