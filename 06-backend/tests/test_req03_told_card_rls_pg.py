# ── Trace ──────────────────────────────────────────────
# Change: REQ-03 redrawn, six steps into four (PO 2026-09-29). Task 2's card,
#         `What the customer is told`, reads `service_request_messages` — and
#         a clerk's ticks are a statement about one utility's customer.
# Rules:  CLAUDE.md hard rule 1 (never touch a tenant table without
#         `app.tenant_id` set; RLS FORCE is on) · B2 §3 · hard-won law 14 (the
#         default suite is in-memory SQLite, which has no row-level security
#         at all) · hard-won law 7 (*192 skips once read as a pass* — the skip
#         below is loud on purpose, and the probe FAILS rather than skips when
#         it could bypass anything)
# Tests:  this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""The review card's table under real row-level security.

⚠ **`config/settings/test.py` HARDCODES IN-MEMORY SQLITE AND IGNORES
`DATABASE_URL`**, so `test_req03_four_steps_server.py`'s tenant case proves the
APP-LAYER filter and can prove nothing about the database. This file is the
other half. Run it against a real PostgreSQL — the whole line, because a header
that omits `JOBS_EAGER=false` costs an hour (`DEF-567`):

    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_req03?sslmode=disable"
    pytest tests/test_req03_told_card_rls_pg.py

⚠ **AND THE READS RUN UNDER A PROBE ROLE RATHER THAN THE APPLICATION'S OWN.**
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
**unconditionally, `FORCE` included**, and the development role here is a
superuser (`DEF-2717`, measured: `rolsuper = t`). An RLS assertion made on that
connection returns rows because the policy was never consulted — it passes by
FINDING the other tenant's row, which is the exact false pass law 7 asks you to
describe before trusting a check. `rls.assert_is_a_real_proof()` FAILS, never
skips, if the probe could bypass anything.
"""

from __future__ import annotations

import pytest

from apps.customers import applicant_messages
from apps.customers import service_request_service as sr
from apps.customers.applicant_message_models import ServiceRequestMessage

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import brazos, dana, erin, lonestar, tenant_ctx  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "service_request_messages"

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}


def _a_request_with_a_stored_tick(actor, tenant):
    request = sr.create_request(actor, dict(CAPTURE))
    ServiceRequestMessage.objects.create(
        tenant_id=tenant.id,
        request_id=request.id,
        occasion="request_received",
        send=False,
    )
    return request


@requires_postgres
def test_the_card_s_table_is_scoped_by_the_database_and_not_only_by_the_code(
    rls, brazos, lonestar, dana, erin  # noqa: F811
):
    """**Hard rule 1, asserted through the DATABASE.** Each utility stores its
    own clerks' ticks; the app-layer filter is deliberately not in the path."""
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        _a_request_with_a_stored_tick(dana, brazos)
    with tenant_ctx(lonestar):
        _a_request_with_a_stored_tick(erin, lonestar)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)


@requires_postgres
def test_with_no_tenant_set_the_table_answers_nothing(rls, brazos, dana):  # noqa: F811
    """⚠ **AND THIS IS THE ONE A COUNT WOULD MISREAD.** With `app.tenant_id`
    unset the policy answers ZERO truthfully, and a lane that counts first and
    reads the number as *the table is empty* has drawn the wrong conclusion
    (`DEF-PAY-6166`). It is asserted as a DENY, deliberately."""
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        _a_request_with_a_stored_tick(dana, brazos)
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_the_card_itself_answers_only_this_utilitys_ticks(
    rls, brazos, lonestar, dana, erin  # noqa: F811
):
    """The read a screen actually calls, on the database that actually
    enforces this. Lonestar unticks its own row; Brazos' card is unmoved."""
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        brazos_request = sr.create_request(dana, dict(CAPTURE))
    with tenant_ctx(lonestar):
        # ⚠ The SAME request id, deliberately: a filter on `request_id` alone
        # would pass this file, and a filter on the tenant is what must.
        ServiceRequestMessage.objects.create(
            tenant_id=lonestar.id,
            request_id=brazos_request.id,
            occasion="request_received",
            send=False,
        )
    with tenant_ctx(brazos):
        card = applicant_messages.on_submit_card(brazos_request)
    assert card["rows"][0]["will_send"] is True
    assert card["rows"][0]["not_sent_reason"] is None
