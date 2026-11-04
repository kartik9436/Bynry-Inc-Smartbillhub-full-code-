# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (TC-6 isolation, from the WRITE path — the rows the
#           queue-write service leaves must never cross tenants)
#           Screens: S8 · S30 · S35
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE) · rule 6 (idempotency — a key that is not per tenant is
#           a cross-tenant collision) · BR-NOT-005 (the queue is PLATFORM-WIDE,
#           so one leak here spans every module) · B2 §3 policy template ·
#           NFR-10 (isolation — release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing (tests/isolation_helpers.py explains the probe role).
# ───────────────────────────────────────────────────────
"""Tenant isolation of the queue WRITE path.

`test_us_not_001_outbound_isolation.py` proves the POLICY on the table. This
file proves the SERVICE lives inside it: that `queue_document` stamps the
caller's tenant and nothing else, that its rows are invisible to a neighbour
through a non-superuser probe, and that the idempotency key it honours is
per-tenant — two utilities can bill an invoice with the same id on the same
morning, and neither may block or see the other.

The write path is where B1's module boundary is deliberately open (billing,
payments, reports and ledger all reach this one function, r16 #7). A ruled
exception for CROSS-MODULE writes must never become one for CROSS-TENANT
writes, and that is what these cases are for.
"""

import pytest

from apps.notifications import models, services

from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
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

A_PIN = services.TemplatePin(code="bill_residential", template_id=None, version=None)


def queue_through_the_service(tenant, invoice_id):
    """One bill queued the way a release queues it — through the published
    service, under a LIVE tenant context (the GUC the policy reads)."""
    with live_tenant_context(tenant.id):
        return services.queue_document(
            source_type="invoice",
            source_id=invoice_id,
            template=services.TemplatePin(
                code="bill_residential", template_id=invoice_id, version=3, language="en-US"
            ),
            recipients=(
                services.Recipient(
                    channel=models.CHANNEL_PRINT,
                    address="1901 Bluestem Ln, Unit A\nKaty TX 77494",
                    snapshot={"name": "Sarah Chen"},
                ),
            ),
        )


@pytest.mark.isolation
@requires_postgres
def test_us_not_001_tc6__rows_the_service_writes_never_cross_tenants(rls):  # noqa: F811
    """US-NOT-001 TC-6 from the write side.

    Both tenants queue a bill through the same service call in the same test.
    Under Lone Star Ridge's context the probe must see exactly one row — its
    own — and the read that would leak a MAILING LIST rather than an id (an
    address, formatted and ready to post) must come back with one row too.
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    from uuid import uuid4

    bb = queue_through_the_service(brazos, uuid4())
    lsr = queue_through_the_service(lonestar, uuid4())

    assert_rls_scoped(
        rls,
        "outbound_messages",
        owner=brazos,
        intruder=lonestar,
        owner_ids={bb.messages[0].id},
    )
    with live_tenant_context(lonestar.id):
        assert rls.ids("outbound_messages") == {lsr.messages[0].id}
        assert rls.count("outbound_messages", "recipient_address IS NOT NULL") == 1
    assert_no_foreign_rows_anywhere(rls, lonestar, ("outbound_messages",))


@pytest.mark.isolation
@requires_postgres
def test_us_not_001_tc6b__the_service_refuses_to_write_with_no_tenant_context(rls):  # noqa: F811
    """CLAUDE.md rule 1, on the live cluster rather than on the mirror.

    A dispatcher, a management command or a metrics job runs outside a request.
    The service refuses BEFORE any statement is issued, so the deny-by-default
    policy is the second line of defence and not the first — and the count of
    rows in the table is unchanged.
    """
    from uuid import uuid4

    from core import errors

    brazos, _ = provisioned_tenant(brazosbend_payload())
    queued = queue_through_the_service(brazos, uuid4())

    with pytest.raises(errors.AuthError):
        services.queue_document(source_type="invoice", source_id=uuid4(), template=A_PIN)

    # Nothing was written by the refused call: under the owner's own context the
    # probe still sees exactly the one row the successful call left.
    with live_tenant_context(brazos.id):
        assert rls.ids("outbound_messages") == {queued.messages[0].id}


@pytest.mark.isolation
@requires_postgres
def test_us_not_001_tc6c__the_idempotency_key_is_per_tenant(rls):  # noqa: F811
    """CLAUDE.md rule 6 and rule 1 together, which is the case neither one
    catches alone.

    Two utilities can hold an invoice with the SAME id — ids are unique per
    table, not per platform. If `tenant` were missing from
    `uq_outbound_msgs_source_channel`, the second tenant's bill would either be
    refused by a collision with a row it cannot even see (a bill that silently
    never goes out) or, worse, be reported as "already queued" against another
    utility's row.

    Both tenants queue the same source id here and BOTH must get their own row.
    """
    from uuid import uuid4

    shared_invoice_id = uuid4()
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())

    first = queue_through_the_service(brazos, shared_invoice_id)
    second = queue_through_the_service(lonestar, shared_invoice_id)

    assert [message.created for message in first.messages] == [True]
    assert [message.created for message in second.messages] == [True]
    assert first.messages[0].id != second.messages[0].id
    with live_tenant_context(lonestar.id):
        assert rls.ids("outbound_messages") == {second.messages[0].id}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 + r12 #16 + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 notifications queue-WRITE lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the measured `-m isolation` counts on this
#         environment; the POLICY these cases stand on was proved RED on a live
#         cluster by the schema slice (notifications/0002's trailer quotes the
#         five failures verbatim)
# exceptions: these cases prove the WRITE path only. Nothing here proves
#         anything about DISPATCH — there is no dispatcher (US-NOT-002), so
#         "batches never cross tenants" (US-NOT-002 TC-7) is NOT covered and is
#         named rather than left looking covered
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
