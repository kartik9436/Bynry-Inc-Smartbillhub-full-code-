"""**CR-171-BRC10 P1.02 · P1.03 · P1.04 — the Move-ins list of the redesign.**

Images 01 and 02: every status a move-in can be in is a row of ONE list —
requests (*To approve*, *Waiting on customer*, *Declined*), approved jobs
(*Not started*), drafts (*Draft*), committed move-ins (*Waiting on a read*,
*Completed*) and *Cancelled* — with five tiles, a Status and a Service filter,
search by customer, unit, MVI- and SR- numbers, and server paging (NFR-3).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A status filter that agrees with itself and not with the row.** The
    status is spelled twice — a SQL `CASE` (filter, tiles, page) and the row
    builder — so `test_every_row_is_selected_by_its_own_status` filters by
    EACH status and asserts every row served carries that status, AND that the
    eight filtered totals add up to the unfiltered total. A row that changed
    status between the two spellings fails one or the other.
  * **A scenario that never reached a status.** The scenario asserts it holds
    at least one row of EVERY status before any other assertion, so a filter
    case cannot pass over an empty bucket.
  * **A *waiting on a read* that is really *no meters*.** The waiting unit has a
    meter and no read; the completed unit has a meter AND a read on the
    move-in date; a third unit has no meter at all and must read *completed*.
  * **Paging that passes because the list was short.** The paging case asks
    for `per=3` over a list of more than three and asserts the two pages are
    disjoint and together complete.
"""

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.customers import move_in_jobs, move_in_list, move_reads, moves
from apps.customers import seams as customers_seams
from apps.customers import service_request as rules
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    brazos,
    commit_read,
    dana,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 5)
CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_phone": "(641) 555-0182",
    "property_type": "standalone_owner_occupied",
    "requested_start": "2026-10-08",
    "what_they_said": "Moving in",
}


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES — real rows through real doors
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code):
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="CR-171 list", defaults={"code": "cr171-list", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"CR-171 list — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, label, *, meters=(), services=("electric",), address="40 Kestrel Park"):
    premises = make_premises(actor, address_line=address, services_available=list(services))
    unit = make_unit(actor, premises["id"], label=label, services=list(services))
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, services[0]).id)}
    )
    for asset_no, service, uom in meters:
        a_meter(actor, asset_no, unit_id=unit["id"], service=service, uom=uom)
    return unit


def _asset_id(unit, asset_no):
    answer = metering_selectors.reads_for_unit(unit["id"])
    return next(m["asset_id"] for m in answer["meters"] if m["asset_no"] == asset_no)


def _committed(actor, unit, *, name, on, reads=None):
    """A COMMITTED move-in: an open account and its `move_records` row,
    written through `moves.record_move` — the one writer both doors use."""
    account = customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": on.isoformat(),
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )
    for asset_no, value in reads or ():
        commit_read(actor, _asset_id(unit, asset_no), day=on.isoformat(), value=value)
    record = moves.record_move(
        kind=moves.KIND_MOVE_IN, account_id=account["id"], effective_on=on, actor=actor
    )
    return account, record


def _request(actor, unit, *, name):
    """A SUBMITTED request resolved *served, vacant* — a To-approve row."""
    request = sr.create_request(
        actor,
        {**CAPTURE, "applicant_name": name, "applicant_email": f"{name[:4].lower()}@ex.test",
         "address_as_given": str(unit["unit_no"])},
    )
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    row = sr.request_row(request.id)
    assert row.resolution_kind == customers_models.ServiceRequest.RESOLUTION_SERVED_VACANT
    return row


def _park(actor, *, step, unit=None, request_id=None, where="values", four=False, services=None,
          label="Draft unit"):
    subject = {"unit_id": str(unit["id"]) if unit else None, "account_id": None}
    values = {"unit_id": str(unit["id"]) if unit else "", "opened_at": ""}
    if request_id is not None:
        (subject if where == "subject" else values)["service_request_id"] = str(request_id)
    if four:
        values[move_reads.MOVE_IN_STEP_SHAPE_KEY] = move_reads.MOVE_IN_STEP_SHAPE_FOUR
    if services is not None:
        values["services"] = services
    return customers_seams.park_wizard_draft(
        actor,
        {
            "flow": "move_in",
            "step": step,
            "subject_label": label,
            "subject_ref": subject,
            "values": values,
            "waiting_on": "",
        },
    )


def _scenario(actor, tenant):
    """One of every status, named so each assertion can find its row."""
    seed_config()
    out = {}
    # Requests: to approve, waiting on customer, declined.
    out["req_a"] = _request(actor, _unit(actor, tenant, "SCW-A"), name="Verma, Asha")
    out["req_w"] = _request(actor, _unit(actor, tenant, "SCW-B"), name="Pratt, Owen")
    sr.ask_for_more(actor, out["req_w"].id, reason="lease", message_to_applicant="lease")
    out["req_d"] = _request(actor, _unit(actor, tenant, "SCW-C"), name="Doe, Dana")
    sr.refuse_request(actor, out["req_d"].id, reason="No lease", reason_code=rules.REFUSAL_OTHER)
    # A draft that IS the to-approve request's edit — never its own row.
    out["park_of_request"] = _park(
        actor, step=2, request_id=out["req_a"].id, where="subject", label="SCW-A edit"
    )
    # Jobs: one not started, one with a draft (reads Draft), one cancelled.
    out["job_n"] = _approved_job(actor, tenant, "SCW-D", "Brandt, Carl")
    out["job_d"] = _approved_job(actor, tenant, "SCW-E", "Ortiz, Lena")
    out["park_of_job"] = _park(actor, step=5, request_id=out["job_d"].request_id, label="SCW-E")
    out["job_c"] = _approved_job(actor, tenant, "SCW-F", "Gone, Gary")
    move_in_jobs.MoveInJob.objects.filter(id=out["job_c"].id).update(
        state=move_in_jobs.STATE_CANCELLED
    )
    # An unlinked seven-step draft parked at old step 5 (Preferences) → 3 · Billing.
    out["park"] = _park(
        actor, step=5, unit=_unit(actor, tenant, "SCW-G"), services=["water"], label="SCW-G"
    )
    # Committed: waiting on a read, completed (read taken), completed (no meter).
    unit_w = _unit(actor, tenant, "SCW-H", meters=(("E-5041", "electric", "kWh"),))
    out["rec_w"] = _committed(actor, unit_w, name="G, Nilesh", on=TODAY - timedelta(days=2))
    unit_c = _unit(actor, tenant, "SCW-I", meters=(("E-5042", "electric", "kWh"),))
    out["rec_c"] = _committed(
        actor, unit_c, name="Raman, Priya", on=TODAY - timedelta(days=5),
        reads=(("E-5042", "16082"),),
    )
    out["rec_n"] = _committed(actor, _unit(actor, tenant, "SCW-J"), name="Nometer, Ned",
                              on=TODAY - timedelta(days=9))
    return out


def _approved_job(actor, tenant, label, name):
    request = _request(actor, _unit(actor, tenant, label), name=name)
    sr.decide_outcome(actor, request.id, outcome="move_in")
    sr.approve_and_raise(actor, request.id)
    return move_in_jobs.MoveInJob.objects.get(request_id=request.id)


def _rows(**kw):
    return move_in_list.move_ins_list(as_of=TODAY, per=100, **kw)


def _ids(payload):
    return {
        r.get("record_id") or r.get("request_id") or r.get("job_id") or r.get("park_id")
        or r.get("account_id")
        for r in payload["rows"]
    }


def _by_ref(payload):
    return {row["reference"] or row.get("move_no"): row for row in payload["rows"]}


# ════════════════════════════════════════════════════════════════════════════
# P1.02 / P1.03 — ONE four-step list, and a seven-step draft read in four
# ════════════════════════════════════════════════════════════════════════════
def test_the_server_declares_four_steps_unit_customer_billing_review():
    assert move_reads.MOVE_IN_STEP_IDS == ("unit", "customer", "billing", "review")
    assert move_reads.MOVE_IN_STEP_COUNT == 4


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(1, 1), (2, 1), (3, 2), (4, 1), (5, 3), (6, 3), (7, 4), (99, 4)],
)
def test_a_seven_step_draft_resumes_on_the_cr_map(stored, expected):
    class Park:
        step = stored
        values = {"customer": {"full_name": "kept"}, "deposit": {"amount": "150.00"}}
        subject_ref = {"unit_id": "u"}

    assert move_reads.move_in_park_step(Park) == expected
    # Every value kept: the map reads the step and touches nothing else.
    assert Park.values == {"customer": {"full_name": "kept"}, "deposit": {"amount": "150.00"}}


def test_a_four_step_draft_is_never_remapped():
    class Marked:
        step = 2
        values = {move_reads.MOVE_IN_STEP_SHAPE_KEY: move_reads.MOVE_IN_STEP_SHAPE_FOUR}
        subject_ref = {}

    class FromTheEditDoor:
        step = 3
        values = {}
        subject_ref = {"service_request_id": "x", "request_no": "SR-26-0001"}

    assert move_reads.move_in_park_step(Marked) == 2  # the map would say 1
    assert move_reads.move_in_park_step(FromTheEditDoor) == 3  # the map would say 2


# ════════════════════════════════════════════════════════════════════════════
# P1.04 — every status, one function, the filter and the row agreeing
# ════════════════════════════════════════════════════════════════════════════
def test_every_row_is_selected_by_its_own_status(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        everything = _rows()
        served = {row["status"] for row in everything["rows"]}
        assert served == set(move_in_list.STATUSES), served  # one of every kind

        added = 0
        for status in move_in_list.STATUSES:
            if status == move_in_list.STATUS_TO_APPROVE:
                continue  # as a filter value `to_approve` is the drawn GROUP — below
            page = _rows(filters={"status": status})
            assert {row["status"] for row in page["rows"]} <= {status}, status
            added += page["total"]
        group = _rows(filters={"status": "to_approve"})
        assert {row["status"] for row in group["rows"]} == {"to_approve", "waiting_on_customer"}
        added += sum(1 for row in group["rows"] if row["status"] == "to_approve")
        assert added == everything["total"]

        rows = _by_ref(everything)
        assert rows[s["req_a"].request_no]["status"] == "to_approve"
        assert rows[s["req_a"].request_no]["action"] == "review"
        assert rows[s["req_a"].request_no]["actions"][0] == "approve"
        assert rows[s["req_w"].request_no]["status"] == "waiting_on_customer"
        assert rows[s["req_d"].request_no]["status"] == "declined"
        assert rows[s["job_n"].move_no]["status"] == "not_started"
        assert rows[s["job_n"].move_no]["action"] == "start"
        assert rows[s["job_c"].move_no]["status"] == "cancelled"
        assert rows[s["rec_w"][1]["move_no"]]["status"] == "waiting_on_a_read"
        assert rows[s["rec_w"][1]["move_no"]]["opening_read"]["missing"] == ["E-5041"]
        assert rows[s["rec_c"][1]["move_no"]]["status"] == "completed"
        assert [r["reading"] for r in rows[s["rec_c"][1]["move_no"]]["opening_read"]["readings"]]
        assert rows[s["rec_n"][1]["move_no"]]["status"] == "completed"  # no meter ≠ waiting
        assert rows[s["rec_c"][1]["move_no"]]["step"]["done"] is True


def test_a_draft_for_a_request_or_a_job_is_that_row_not_a_second_one(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        payload = _rows()
        park_ids = {row.get("park_id") for row in payload["rows"]
                    if row["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_IN}
        assert str(s["park_of_request"].id) not in park_ids
        assert str(s["park_of_job"].id) not in park_ids
        assert str(s["park"].id) in park_ids

        job_row = _by_ref(payload)[s["job_d"].move_no]
        assert job_row["status"] == "draft"
        assert job_row["action"] == "resume"
        assert job_row["park_id"] == str(s["park_of_job"].id)
        # Parked at old step 5 (Preferences) under the seven-step wizard → 3 · Billing.
        assert (job_row["step"]["reached"], job_row["step"]["name"]) == (3, "Billing")
        # A request appears once, as itself.
        assert sum(1 for r in payload["rows"] if r.get("request_id") == str(s["req_a"].id)) == 1


def test_the_drawn_status_groups_and_the_service_filter(brazos, dana):
    with tenant_ctx(brazos):
        _scenario(dana, brazos)
        open_rows = _rows(filters={"status": "open"})["rows"]
        assert {r["status"] for r in open_rows} == {"not_started", "draft", "waiting_on_a_read"}
        assert {r["status"] for r in _rows(filters={"status": "to_approve"})["rows"]} == {
            "to_approve", "waiting_on_customer",
        }
        assert {r["status"] for r in _rows(filters={"status": "completed"})["rows"]} == {
            "completed"
        }
        assert _rows(filters={"status": "nonsense"})["total"] == 0  # BR-SHL-011
        assert _rows(filters={"status": "all"})["total"] == _rows()["total"]

        water = _rows(filters={"service": "water"})["rows"]
        assert [r["status"] for r in water] == ["draft"]  # only the draft ticked water
        assert water[0]["services"] == ["water"]
        either = _rows(filters={"service": "electric,water"})["rows"]
        # A row matches when it takes ANY ticked service — and only then.
        assert all(set(r["services"] or ()) & {"electric", "water"} for r in either)
        assert {r["status"] for r in either} >= {"waiting_on_a_read", "completed", "draft"}


def test_the_five_tiles_count_the_whole_list(brazos, dana):
    with tenant_ctx(brazos):
        _scenario(dana, brazos)
        kpis = _rows(q="zzzz-no-match")["kpis"]  # tiles ignore the search
        assert kpis["to_approve"] == 1
        assert kpis["not_started"] == 1
        assert kpis["drafts"] == 2  # the unlinked draft + the job with a draft
        assert kpis["waiting_on_a_read"] == 1
        # Requested start 2026-10-08 is within the week for the request rows and
        # the jobs (whose request carries it): to_approve + waiting + 2 jobs.
        assert kpis["starting_this_week"] == 4
        assert kpis["by_status"]["cancelled"] == 1


def test_search_by_reference_name_and_paging(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        assert [r["reference"] for r in _rows(q=s["req_w"].request_no)["rows"]] == [
            s["req_w"].request_no
        ]
        assert [r["reference"] for r in _rows(q=s["rec_w"][1]["move_no"])["rows"]] == [
            s["rec_w"][1]["move_no"]
        ]
        assert [r["status"] for r in _rows(q="Raman")["rows"]] == ["completed"]

        total = _rows()["total"]
        first = move_in_list.move_ins_list(as_of=TODAY, per=3, page=1)
        second = move_in_list.move_ins_list(as_of=TODAY, per=3, page=2)
        assert first["total"] == total and len(first["rows"]) == 3
        assert not _ids(first) & _ids(second)


def test_the_seven_step_draft_reads_three_of_four_billing_on_the_list(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        row = next(r for r in _rows()["rows"] if r.get("park_id") == str(s["park"].id))
        assert row["step"] == {
            "reached": 3, "of": 4, "id": "billing", "name": "Billing", "unavailable": None,
        }


def test_the_set_wise_read_dates_agree_with_the_per_unit_read(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _unit(dana, brazos, "SCW-K", meters=(("E-1", "electric", "kWh"), ("W-1", "water", "kgal")),
                     services=("electric", "water"))
        commit_read(dana, _asset_id(unit, "E-1"), day="2026-09-01", value="100")
        commit_read(dana, _asset_id(unit, "E-1"), day="2026-09-20", value="140")
        bare = _unit(dana, brazos, "SCW-L")
        bulk = customers_seams.latest_read_dates_for_units([unit["id"], bare["id"]])
        single = metering_selectors.reads_for_unit(unit["id"])
        assert {m["asset_no"]: m["latest_read_at"] for m in bulk[str(unit["id"])]["meters"]} == {
            m["asset_no"]: m["latest_read_at"] for m in single["meters"]
        } == {"E-1": "2026-09-20", "W-1": None}
        assert bulk[str(bare["id"])]["meters"] == []


def test_the_api_takes_the_status_and_service_filters(brazos, dana):
    from apps.customers import api

    with tenant_ctx(brazos):
        _scenario(dana, brazos)
    response = api_call(
        api.move_ins_list, "get", "/api/brazos/move-ins", user=dana.user, role="system_admin",
        tenant=brazos, query={"f.status": "open", "f.service": "electric"},
    )
    assert response.status_code == 200, response.data
    assert response.data["rows"]
    assert {r["status"] for r in response.data["rows"]} <= {"not_started", "draft", "waiting_on_a_read"}
    assert set(response.data["filters"]) >= {"status", "service"}


def test_the_server_map_is_the_front_ends_map_key_for_key():
    """`move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR` == `moveShared.MOVE_IN_SEVEN_STEP_TO_FOUR`
    — the list's STEP cell and the wizard's resume read one map in two
    languages (the `DEF-648` boundary)."""
    import re
    from pathlib import Path

    shared = (
        Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "features" / "customers"
        / "moveShared.tsx"
    ).read_text(encoding="utf-8")
    block = re.search(
        r"export const MOVE_IN_SEVEN_STEP_TO_FOUR: Readonly<Record<number, number>> = \{(.*?)\};",
        shared,
        re.S,
    )
    assert block, "the front end's map is not where this test reads it"
    front = {int(k): int(v) for k, v in re.findall(r"(\d+):\s*(\d+)", block.group(1))}
    assert front == move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR


def test_a_committed_move_in_cancelled_through_the_cancel_door_reads_cancelled(brazos, dana):
    """`DEF-CUS-9713` (lane MVI-FLOW): the list read a committed cancel off a
    `close_reason` the database refuses and nothing writes. The cancel door
    closes the account the DAY BEFORE it opened; `move_in_cancel.is_cancelled`
    is the one predicate. Through the REAL door, on the list AND the page."""
    from apps.customers import move_in_cancel, move_record_reads

    with tenant_ctx(brazos):
        seed_config()
        unit = _unit(dana, brazos, "SCW-X")
        _account, record = _committed(dana, unit, name="Late, Lucy", on=TODAY - timedelta(days=1))
        move_in_cancel.cancel(dana, record["move_no"], note="Changed their mind")
        row = _by_ref(_rows())[record["move_no"]]
        assert row["status"] == "cancelled"
        assert [r["reference"] for r in _rows(filters={"status": "cancelled"})["rows"]] == [
            record["move_no"]
        ]
        assert move_record_reads.record_detail(record["move_no"])["status"] == "cancelled"
