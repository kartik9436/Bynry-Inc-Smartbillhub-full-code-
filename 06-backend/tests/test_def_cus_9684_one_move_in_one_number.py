# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9684 (CR-168-BRC10 round 8, lane FIX-8A) — an approved
#           service request linked to MVI-26-0005 while the move-in it became
#           was filed under MVI-26-0006, so the request's own link opened a page
#           reading *Visit: Not raised* over a visit raised, done and accepted.
# Rules:    BR-CUS-1090 (one move-in, one number) · CR-122-BRC06 (the draft's
#           reference) · BR-CUS-1077 (the approval's job)
# ───────────────────────────────────────────────────────
"""The number printed on the request wins over the wizard's draft.

The approval issues `MVI-…` on the spot and prints it on the request. The
move-in wizard then autosaves a draft on open, and a draft that was not told
the job's number mints its own from the same series. `record_move` preferred
the DRAFT's, so the finished move was filed under a number the request never
named. The job's number is the older promise — it has been on the request page
since Approve — so it is the one the record adopts, and the draft's becomes a
gap (`BR-TEN-035` permits one)."""

from __future__ import annotations

import pytest

from apps.customers import move_in_jobs, move_record_reads, moves
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.tenancy import wizard_parks

from tests import identity_fixtures
from tests.test_br_cus_1090_move_in_job_number import (
    CAPTURE,
    _move_in_request,
    _occupant,
    _served_unit,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_the_approved_request_and_the_finished_move_name_one_number(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 16", address="16 Poplar Grove")
        outgoing = _occupant(dana, unit, name="Baptiste, Marie")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-09-19"})
        sr.approve_and_raise(dana, request.id)
        issued = move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no
        assert issued

        # The wizard autosaves on open, as the approval's door opens it: the
        # request id rides in the values and the subject carries no number.
        draft = wizard_parks.park(
            dana,
            {
                "flow": "move_in",
                "step": 1,
                "subject_label": "Unit 16, 16 Poplar Grove",
                "subject_ref": {"unit_id": str(unit["id"])},
                "values": {"service_request_id": str(request.id)},
            },
        )

        result = customers_services.move_in(
            dana,
            outgoing["id"],
            {
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-09-20",
                "contact": {"full_name": CAPTURE["applicant_name"]},
                "customer": identity_fixtures.customer_block(
                    CAPTURE["applicant_name"], account_type="residential"
                ),
                "service_request_id": str(request.id),
                "wizard_park_id": str(draft.id),
            },
        )

        assert result["move_no"] == issued, (
            f"the request names {issued}, the move was filed as {result['move_no']}"
        )
        assert moves.MoveRecord.objects.filter(move_no=issued).count() == 1
        # The request's own link opens the FINISHED move, not the approval.
        page = move_record_reads.record_detail(issued)
        assert page["move_no"] == issued
        assert page["state"] != "approved"
