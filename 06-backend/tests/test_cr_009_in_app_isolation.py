# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — tenant isolation for the in-app message store)
#           Screens: shell-chrome · S8
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · B2 §3 policy template · DB-1 ·
#           BR-NOT-019 (every row here is a RENDERED MESSAGE BODY) · NFR-10
#           (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing. The PER-USER half is asserted in
#           tests/test_cr_009_in_app_channel.py, which runs on both, because it
#           is enforced in the service and not by a policy.
# ───────────────────────────────────────────────────────
"""Tenant isolation for `in_app_messages` — and what a leak would actually show.

Every row here holds a RENDERED MESSAGE BODY: the same artifact the queue row
would have handed a provider. A bulk-run summary names how many accounts a
utility billed and how many failed. Read across a tenant boundary, that is one
utility reading another utility's operational figures out of a bell menu, with
no request against their own data to explain where the number came from.

The WRITE side matters as much, and differently: a delivery that landed in the
wrong tenant would put a message in a stranger's inbox, and the recipient would
have no way to tell that it was not theirs.

Asserted through a NON-SUPERUSER probe role, so the policy is genuinely
consulted rather than bypassed.
"""

import uuid

import pytest

from apps.notifications import models

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db


def _delivered(payload=None, *, body="Billing run finished.\n\n1204 processed · 3 failed"):
    """A tenant with ONE delivered in-app message in ONE user's inbox.

    The queue row is created directly rather than through `queue_bulk_summary`,
    deliberately: this file is about the POLICY, and driving the whole
    queue→render→dispatch chain here would make an RLS failure look like a
    rendering failure.
    """
    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    user_id = uuid.uuid4()
    with live_tenant_context(tenant.id):
        queued = models.OutboundMessage.objects.create(
            tenant_id=tenant.id,
            source_type="bulk_action",
            source_id=uuid.uuid4(),
            channel=models.CHANNEL_IN_APP,
            template_code="staff_bulk_summary",
            recipient_address=str(user_id),
            status=models.STATUS_SENT,
        )
        row = models.InAppMessage.objects.create(
            tenant_id=tenant.id,
            user_id=user_id,
            outbound_message=queued,
            body=body,
        )
    return tenant, row


@pytest.mark.isolation
@requires_postgres
def test_us_not_018_tc15a__in_app_messages_are_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """Deny-by-default, not filter-by-default.

    It matters here because the WRITER of this table is a DISPATCHER — a job
    that runs outside any request, and exactly the caller that forgets to enter
    a tenant context.
    """
    _delivered()
    assert_denied_without_context(rls, "in_app_messages")


@pytest.mark.isolation
@requires_postgres
def test_us_not_018_tc15__one_tenants_in_app_messages_are_invisible_to_another(rls):  # noqa: F811
    """A bell menu must never be able to show another utility's run figures."""
    brazos, bb_row = _delivered()
    lonestar, lsr_row = _delivered(
        lonestarridge_payload(), body="Payment import finished.\n\n40 processed · 0 failed"
    )

    assert_rls_scoped(
        rls,
        "in_app_messages",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(bb_row.id)},
    )

    with live_tenant_context(lonestar.id):
        assert rls.count("in_app_messages", "id = %s", [str(bb_row.id)]) == 0
        assert rls.ids("in_app_messages") == {str(lsr_row.id)}


@pytest.mark.isolation
@requires_postgres
def test_us_not_018_tc15b__a_write_into_another_tenants_inbox_is_refused(rls):  # noqa: F811
    """`WITH CHECK`. A delivery that landed in the wrong tenant would put a
    message in a stranger's inbox and they would have no way to tell."""
    brazos, _ = _delivered()
    lonestar, _ = _delivered(lonestarridge_payload())
    assert_write_into_other_tenant_refused(rls, "in_app_messages", owner=brazos, intruder=lonestar)


def test_us_not_018__the_table_carries_the_column_every_policy_depends_on():
    """The SHAPE assertion, and it runs EVERYWHERE including sqlite.

    It proves nothing about RLS and does not pretend to — what it proves is that
    the column the policy is written against exists and is NOT NULL, which is the
    one way a policy can be silently switched off by a later migration.
    """
    field = models.InAppMessage._meta.get_field("tenant")
    assert field.null is False
    assert field.db_column == "tenant_id"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set · 04-docs/02-decisions/02-database-design-brief.md §3 · 06-backend/db/rls_notifications_in_app.sql · tests/test_cr_009_notification_rules_isolation.py, whose shape this repeats)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a policy probe) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with migration 0012 reverted (`migrate notifications 0011`) all three policy cases FAILED, the scoped read returning Lone Star Ridge's row under Brazos Bend's context. Transcript in the lane report.
# exceptions: (1) POSTGRES ONLY for the three policy cases — sqlite has no RLS and a green run there would prove nothing. The shape case runs everywhere and says exactly what it does and does not prove. (2) PER-USER isolation is NOT asserted here: it is enforced in `apps/notifications/in_app.py` rather than by a policy, and its tests live in test_cr_009_in_app_channel.py where they run on both engines.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
