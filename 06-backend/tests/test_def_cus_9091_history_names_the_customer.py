# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9091 — the request history's WHO column said "System" for a
#           row the CUSTOMER wrote (the Track reply of DEF-CWP-9049, a portal
#           note). Found on the 21-walk re-run, W14-07-clerk-history.png.
# Tests:    this file · ServiceRequestDetailPage.test.tsx (the WHO cell)
# ───────────────────────────────────────────────────────
"""A history row's actor, as the server serves it: staff, customer or system.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): marking EVERY actor-less row
as the customer would satisfy the reply case — so the request's own
system rows (numbering, the move to Submitted) are asserted to stay `system`.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

import pytest

from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from core.tenancy import tenant_context
from tests.test_cr158_portal_application_documents import docs_dir, ready  # noqa: F401
from tests.test_def_cwp_9049_track_reply_document import (
    PNG,
    _ask_for_more,
    _phone,
    _reply,
    _sent_with_one_file,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403


@pytest.mark.django_db
def test_the_customers_reply_names_the_applicant_and_system_rows_stay_system(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)
    assert _reply(ready, reference, _phone(), PNG, "clearer-id.png", "image/png").status_code == 200
    with tenant_context(ready.id):
        rows = reads.history_tab(sr.request_row(request_id))
    replied = [r for r in rows if (r["note_type"] or "").startswith("customer_replied")]
    assert len(replied) == 1
    assert replied[0]["actor_kind"] == "customer"
    assert replied[0]["actor_name"] == "Daniel Okafor", "the applicant's name the header already shows"
    numbered = [r for r in rows if r["note_type"] == "number_allocated"]
    assert numbered and all(r["actor_kind"] == "system" and r["actor_name"] is None for r in numbered)
    asked = [r for r in rows if r["to_state"] == "more_info"]
    assert asked and all(r["actor_kind"] == "staff" for r in asked)
