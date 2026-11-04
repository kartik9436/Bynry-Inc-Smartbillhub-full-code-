"""**CR-171-BRC10 P1.05 — `GET /moves/{ref}` for every status (images 03–17).**

An `SR-` reference opens its REQUEST as the move-in details view (to approve,
waiting on the customer, declined); an `MVI-` reference opens the job, the
draft or the committed move-in. Every state now also carries `status` (the
LIST's one function), `reference`, `step`, `tiles`, `facts`, `tab_counts` and
`still_open`.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A chip that agrees with nothing.** Each case asserts the page's `status`
    EQUALS the list row's `status` for the same reference — the two are the
    `DEF-127` pair the CR's §6.1 exists to keep together.
  * **An `SR-` that resolves to the request's Edit DRAFT.** The draft carries
    the request's own `SR-` as its reference; the case parks one and asserts
    the page is still the REQUEST view (`state == "request"`).
"""

import pytest

from apps.customers import move_in_list, move_record_reads

from tests.test_cr171_p1_04_move_ins_list import _rows, _scenario
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _list_status(reference):
    row = next(r for r in _rows()["rows"] if r["reference"] == reference)
    return row["status"]


def test_the_page_says_what_the_list_says_for_every_status(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        references = [
            s["req_a"].request_no,
            s["req_w"].request_no,
            s["req_d"].request_no,
            s["job_n"].move_no,
            s["job_d"].move_no,
            s["job_c"].move_no,
            s["park"].reference,
            s["rec_w"][1]["move_no"],
            s["rec_c"][1]["move_no"],
        ]
        seen = set()
        for reference in [ref for ref in references if ref]:
            page = move_record_reads.record_detail(reference)
            assert page["status"] == _list_status(reference), reference
            assert page["reference"] == reference
            assert {"tiles", "facts", "tab_counts", "still_open"} <= set(page), reference
            seen.add(page["status"])
        assert seen == set(move_in_list.STATUSES), seen


def test_an_sr_reference_opens_the_request_not_its_edit_draft(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        page = move_record_reads.record_detail(s["req_a"].request_no.lower())
        assert page["state"] == "request"
        assert page["status"] == "to_approve"
        assert page["actions"] == ["approve", "ask_for_more", "edit", "decline"]
        assert page["facts"]["who"]["name"] == "Verma, Asha"
        assert page["facts"]["request"]["unit_is_vacant"] is True
        assert page["tiles"]["move_in_date"]["value"] == "2026-10-08"
        assert page["tab_counts"]["audit"] >= 1
        declined = move_record_reads.record_detail(s["req_d"].request_no)
        assert declined["status"] == "declined"
        # REQ's ONE function, after lane FLOW's Reopen (OQ-CUS-12789 (a)).
        assert declined["actions"] == ["reopen"]


def test_an_approved_requests_sr_opens_its_job(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        page = move_record_reads.record_detail(s["job_n"].request.request_no)
        assert page["reference"] == s["job_n"].move_no
        assert page["status"] == "not_started"
        drafted = move_record_reads.record_detail(s["job_d"].move_no)
        assert drafted["status"] == "draft"
        assert drafted["park_id"] == str(s["park_of_job"].id)
        assert drafted["step"]["reached"] == 3  # the draft's own step, in four


def test_a_committed_move_in_serves_tiles_details_and_still_open(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        waiting = move_record_reads.record_detail(s["rec_w"][1]["move_no"])
        assert waiting["status"] == "waiting_on_a_read"
        assert waiting["tiles"]["opening_reads"]["taken"] == 0
        assert waiting["tiles"]["opening_reads"]["of"] == 1
        assert [row for row in waiting["still_open"] if row["kind"] == "opening_read"]
        assert waiting["facts"]["details"]["account"]["account_no"]
        assert waiting["facts"]["details"]["customer"]["name"] == "G, Nilesh"
        done = move_record_reads.record_detail(s["rec_c"][1]["move_no"])
        assert done["status"] == "completed"
        assert done["tiles"]["opening_reads"]["taken"] == done["tiles"]["opening_reads"]["of"] == 1
        assert done["tiles"]["fees"]["lines"] == 0
        assert not [row for row in done["still_open"] if row["kind"] == "opening_read"]


def test_a_seven_step_draft_page_reads_the_four_step_cell(brazos, dana):
    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
        if not s["park"].reference:
            pytest.skip("no MVI series on this tenant — the list case covers the cell")
        page = move_record_reads.record_detail(s["park"].reference)
        assert page["status"] == "draft"
        assert page["step"]["reached"] == 3 and page["step"]["of"] == 4
        assert page["step"]["name"] == "Billing"


def test_the_route_serves_an_sr_reference(brazos, dana):
    from apps.customers import api

    with tenant_ctx(brazos):
        s = _scenario(dana, brazos)
    response = api_call(
        api.move_record_detail, "get", f"/api/brazos/moves/{s['req_w'].request_no}",
        user=dana.user, role="system_admin", tenant=brazos, ref=s["req_w"].request_no,
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == "waiting_on_customer"
    assert response.data["actions"][:2] == ["approve", "resend_ask"]
