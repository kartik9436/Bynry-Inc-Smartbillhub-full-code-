# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 / TC-6 — "Lone Star Ridge queue query: its rows only;
#           Brazos Bend's 1,124-bill rows invisible (RLS FORCE)"
#           Screens: S8 · S30 · S35
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · B2 §3 policy template · DB-1 ·
#           BR-NOT-005 (the queue is PLATFORM-WIDE, so one leak here spans
#           every module at once) · NFR-10 (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing (tests/isolation_helpers.py explains the probe role).
#           Proved RED against the live cluster by neutering the policy
#           migration first; the transcript is in 0002's trailer (law 7).
# ───────────────────────────────────────────────────────
"""The database half of the outbound queue's tenant isolation.

This is the table where a missing policy costs the most. Every row holds a
customer's name, service address, phone number or email address — snapshotted
at queue time (BR-TEN-017) so it stays readable long after the source row has
moved on — and r12 #16 makes it PLATFORM-WIDE, so bills, receipts, collection
notices and report emails all sit in the same table. One absent policy is not
one module's leak; it is another utility's mailing list, already formatted.

Asserted through a NON-SUPERUSER probe role, so the policy is genuinely
consulted rather than bypassed.
"""

from uuid import uuid4

import pytest

from apps.notifications import models

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
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


def _queued_bill(payload=None):
    """A tenant with one bill queued to print — the J17 step-1 handoff."""
    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    with live_tenant_context(tenant.id):
        row = models.OutboundMessage.objects.create(
            tenant_id=tenant.id,
            source_type="invoice",
            # The SAME source id in both tenants, on purpose: ids are unique per
            # table, not per platform, and an id-guessing read is the attack
            # that survives a missing application-layer filter.
            source_id=uuid4(),
            channel=models.CHANNEL_PRINT,
            template_code="bill_residential",
            template_version=3,
            template_language="en-US",
            recipient_address="1901 Bluestem Ln, Unit A\nKaty TX 77494",
            recipient_snapshot={"name": "Sarah Chen"},
        )
    return tenant, row


@pytest.mark.isolation
@requires_postgres
def test_the_outbound_queue_is_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
    B2 §3 template's `::uuid` cast of '' raises and NO row is visible.

    This is the case that matters for a QUEUE specifically. A dispatcher, a
    maintenance command or a metrics job is exactly the kind of caller that runs
    outside a request and forgets to enter a tenant context — and a
    filter-by-default policy would hand it the whole platform's messages.
    """
    _queued_bill()
    assert_denied_without_context(rls, "outbound_messages")


@pytest.mark.isolation
@requires_postgres
def test_us_not_001_tc6__one_tenants_queue_rows_are_invisible_to_another(rls):  # noqa: F811
    """US-NOT-001 TC-6, verbatim: *"Lone Star Ridge queue query → its rows only;
    Brazos Bend's 1,124-bill rows invisible (RLS FORCE)."*

    Proved RED by neutering `notifications/0002`: the probe then saw both
    tenants' rows and this failed naming the leak.
    """
    brazos, bb_row = _queued_bill()
    lonestar, lsr_row = _queued_bill(lonestarridge_payload())

    assert_rls_scoped(
        rls, "outbound_messages", owner=brazos, intruder=lonestar, owner_ids={str(bb_row.id)}
    )

    with live_tenant_context(lonestar.id):
        # The id-guessing attack — the one that survives a missing app filter.
        assert rls.count("outbound_messages", "id = %s", [str(bb_row.id)]) == 0
        assert rls.ids("outbound_messages") == {str(lsr_row.id)}
        # …and the read that would leak a mailing list rather than an id.
        assert rls.count("outbound_messages", "recipient_address IS NOT NULL") == 1
        # Deliberately NOT asserted here: the same query through the ORM.
        # `models.OutboundMessage.objects.filter(pk=...)` runs as the APP role,
        # which is a superuser in dev/CI and therefore bypasses row-level
        # security, FORCE or not — the first draft of this file asserted it and
        # went RED for that reason rather than a leak. That bypass is the whole
        # reason `sbh_rls_probe` exists (tests/isolation_helpers.py), and the
        # ORM half of this guarantee belongs with the first tenant-scoped
        # SELECTOR over this table, which does not exist yet (US-NOT-013).

    assert_no_foreign_rows_anywhere(rls, lonestar, ("outbound_messages",))


@pytest.mark.isolation
@requires_postgres
def test_a_write_into_another_tenants_queue_is_refused(rls):  # noqa: F811
    """WITH CHECK, not just USING.

    The queue's write path is the one place B1's module boundary is deliberately
    open — billing, payments, reports and ledger all INSERT here (r16 #7). A
    ruled exception for CROSS-MODULE writes must never become one for
    CROSS-TENANT writes, so the stamp is refused even when the neighbour's
    tenant_id is known.
    """
    brazos, _ = _queued_bill()
    lonestar, _ = _queued_bill(lonestarridge_payload())
    assert_write_into_other_tenant_refused(
        rls, "outbound_messages", owner=brazos, intruder=lonestar
    )


@pytest.mark.isolation
@requires_postgres
def test_the_outbound_queue_carries_enable_and_force(rls):  # noqa: F811
    """B2 §3 is ENABLE **and** FORCE — FORCE is the half that applies the policy
    to the table's OWNER, which is the role the application connects as in more
    deployments than anyone would like. ENABLE alone reads as protected in every
    catalog view and protects nothing from the owner.
    """
    from django.db import connection

    _queued_bill()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'outbound_messages'"
        )
        enabled, forced = cursor.fetchone()
    assert enabled, "outbound_messages has no row-level security"
    assert forced, "outbound_messages lacks FORCE — the owner role would bypass the policy"


@pytest.mark.isolation
@requires_postgres
def test_the_idempotency_key_exists_in_the_database_not_only_in_the_model(rls):  # noqa: F811
    """CLAUDE.md rule 6, checked in the catalog rather than in Django.

    A `UniqueConstraint` that a migration failed to apply is invisible to every
    ORM-level test — the model still declares it and Django never asks the
    database. The guarantee that a re-released bill cannot queue twice is an
    INDEX or it is nothing, so this reads the index.
    """
    from django.db import connection

    _queued_bill()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'outbound_messages' "
            "AND indexname = 'uq_outbound_msgs_source_channel'"
        )
        row = cursor.fetchone()
    assert row is not None, "uq_outbound_msgs_source_channel is missing — a bill could queue twice"
    indexdef = row[0]
    assert "UNIQUE" in indexdef
    for column in ("tenant_id", "source_type", "source_id", "channel", "copy_no"):
        assert column in indexdef, f"{column} missing from the idempotency key"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 + r12 #16 + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 notifications outbound-queue schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — schema slice) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a live Postgres cluster — with 0002's apply_rls
#         neutered, FIVE cases failed and the catalog sweep named the table:
#         `test_g5_the_rls_exempt_list_is_exactly_what_b2_declares` →
#         "AssertionError: tenant-scoped table(s) with NO row-level security
#         policy: ['outbound_messages'] — every one is a cross-tenant read
#         away"; the deny-without-context and cross-tenant-write cases →
#         "Failed: DID NOT RAISE DatabaseError"; TC-6 → "outbound_messages:
#         under <A>'s context the database exposed rows of {<B>}"; the
#         ENABLE/FORCE case → "outbound_messages has no row-level security".
#         Restored: `-m isolation` 64 passed / 12 skipped, up from the 59/12
#         baseline by exactly these five.
#         The idempotency-index case was proved RED separately by removing the
#         UniqueConstraint: "uq_outbound_msgs_source_channel is missing — a
#         bill could queue twice".
# exceptions: no case here proves anything about DISPATCH — the dispatcher is
#         US-NOT-002 and does not exist, so "batches never cross tenants"
#         (US-NOT-002 TC-7) is NOT covered by this file and is named rather
#         than left looking covered
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
