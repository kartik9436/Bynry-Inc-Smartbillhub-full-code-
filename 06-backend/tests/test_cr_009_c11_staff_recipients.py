# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — staff recipients RULED: OQ-261 CLOSED)
#           Screens: shell-chrome (the bell) · S8 (SET-12 staff rows)
# Rules:    BR-NOT-021 (PO 2026-08-17, verbatim: "the user who started the
#           action, plus all System Admins for failures") · BR-NOT-020 (still
#           ONE message per bulk action — more MAILBOXES, never more messages) ·
#           BR-NOT-019 (in-app delivers) · CLAUDE.md rule 6 (idempotent
#           delivery per message per inbox)
# ───────────────────────────────────────────────────────
"""BR-NOT-021, proved end to end: one message, the ruled mailboxes.

The load-bearing assertion is a PAIR of counts — `OutboundMessage` grew by ONE
and `InAppMessage` grew by FOUR — because each half alone can lie: one queue
row delivered to one inbox passes the first, and four queue rows delivered to
four inboxes passes the second.

⚠ THE SECOND FIGURE READ *THREE* UNTIL 2026-09-01 AND THE FOURTH MAILBOX WAS
NEVER OPTIONAL: it is the tenant's PROVISIONING OWNER, who is a System Admin by
BR-TEN-001 and was missing only because the shared harness stubbed
`provision_owner` with a function that wrote no `users` row (DEF-566, and the
sample-data collapse it caused, DEF-2395). See the acceptance case for the full
reasoning — the rule did not change, the fixture stopped lying about who exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.identity import models as identity_models
from apps.notifications import bulk_summary, dispatcher, in_app, models, seed_templates
from apps.notifications import staff_recipients

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

FINISHED_AT = datetime(2026, 8, 18, 7, 5, tzinfo=dt_timezone.utc)


def _admin_with_membership(tenant, email):
    """An ACTIVE System Admin membership — what `identity.selectors.user_list`
    serves and `is_active_system_admin` passes. The shared `staff_actor`
    deliberately creates only the user row (most tests need no membership);
    this ruling is ABOUT memberships, so this file builds the real thing."""
    actor = staff_actor(tenant, "system_admin", email)
    role = identity_models.Role.objects.get(code="system_admin")
    identity_models.TenantMembership.objects.create(
        tenant=tenant,
        user=actor.user,
        role=role,
        status=identity_models.TenantMembership.STATUS_ACTIVE,
    )
    return actor


def _clerk_with_membership(tenant, email):
    actor = staff_actor(tenant, "billing_clerk", email)
    role = identity_models.Role.objects.get(code="billing_clerk")
    identity_models.TenantMembership.objects.create(
        tenant=tenant,
        user=actor.user,
        role=role,
        status=identity_models.TenantMembership.STATUS_ACTIVE,
    )
    return actor


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RESOLVER — the ruling, each clause separately
# ══════════════════════════════════════════════════════════════════════════
def test_c11__a_clean_action_reaches_the_initiator_and_nobody_else(brazos, dana):
    """First clause: *"the user who started the action"*. No failure → the
    admins are NOT copied, however many exist."""
    with tenant_ctx(brazos):
        _admin_with_membership(brazos, "admin-one@brazosbendutilities.test")
        audience = staff_recipients.resolve_staff_recipients(actor=dana, failure=False)

    assert [entry.reason for entry in audience.recipients] == ["initiator"]
    assert audience.recipients[0].user_id == str(dana.user.id)


def test_c11__a_failure_adds_every_active_system_admin(brazos, dana):
    """Second clause: *"plus all System Admins for failures"* — ALL of them,
    ACTIVE ones only, and never the Billing Clerk."""
    with tenant_ctx(brazos):
        one = _admin_with_membership(brazos, "admin-one@brazosbendutilities.test")
        two = _admin_with_membership(brazos, "admin-two@brazosbendutilities.test")
        clerk = _clerk_with_membership(brazos, "clerk@brazosbendutilities.test")
        # A deactivated admin is a LEAVER, not a recipient.
        gone = staff_actor(brazos, "system_admin", "gone@brazosbendutilities.test")
        identity_models.TenantMembership.objects.create(
            tenant=brazos,
            user=gone.user,
            role=identity_models.Role.objects.get(code="system_admin"),
            status=identity_models.TenantMembership.STATUS_DEACTIVATED,
        )
        audience = staff_recipients.resolve_staff_recipients(actor=dana, failure=True)

    ids = {entry.user_id for entry in audience.recipients}
    assert str(dana.user.id) in ids
    assert str(one.user.id) in ids and str(two.user.id) in ids
    assert str(clerk.user.id) not in ids
    assert str(gone.user.id) not in ids
    assert audience.recipients[0].reason == "initiator"


def test_c11__an_initiating_admin_is_one_person_one_mailbox(brazos):
    """The initiator who IS a System Admin appears once, as the initiator —
    a person must never receive the same failure twice under two reasons."""
    with tenant_ctx(brazos):
        admin = _admin_with_membership(brazos, "admin-init@brazosbendutilities.test")
        audience = staff_recipients.resolve_staff_recipients(actor=admin, failure=True)

    matching = [e for e in audience.recipients if e.user_id == str(admin.user.id)]
    assert len(matching) == 1
    assert matching[0].reason == "initiator"


def test_c11__an_unresolvable_identity_read_is_reported_never_read_as_no_admins(
    brazos, dana, monkeypatch
):
    """DEF-075's shape: "nobody could look" and "there are none" must not
    travel the same. The initiator still gets their copy."""
    monkeypatch.setattr(staff_recipients, "_resolve", lambda attribute: None)
    with tenant_ctx(brazos):
        audience = staff_recipients.resolve_staff_recipients(actor=dana, failure=True)

    assert [entry.reason for entry in audience.recipients] == ["initiator"]
    assert len(audience.problems) == 1
    assert audience.problems[0]["code"] == staff_recipients.ADMINS_UNRESOLVABLE


# ══════════════════════════════════════════════════════════════════════════
# 2 · END TO END — ONE MESSAGE, THREE INBOXES
# ══════════════════════════════════════════════════════════════════════════
def test_c11__a_failed_run_is_one_queue_row_and_a_mailbox_per_ruled_recipient(brazos, dana):
    """THE ACCEPTANCE PAIR. A billing run failing 3 of 1,204 accounts, started
    by Dana, on a tenant with three other System Admins:

      * `outbound_messages` grows by **1** (BR-NOT-020 untouched), and
      * `in_app_messages` grows by **4** (BR-NOT-021: Dana + both admins +
        the tenant's PROVISIONING OWNER),

    through the REAL dispatcher and the REAL adapter — nothing stubbed.

    ⚠ **THE FIGURE WAS 3 AND THE THIRD ADMIN WAS ALWAYS SUPPOSED TO BE THERE
    (DEF-566 / DEF-2395, 2026-09-01).** BR-TEN-001 makes the provisioning owner
    a System Admin of every tenant, so a real Brazos Bend has three of them
    before this test adds a single row. It read 3 only because the shared
    harness stubbed `provision_owner` with a function that wrote no `users` row
    and no membership, so the owner did not exist to be notified. With the seam
    real the owner is a ruled recipient like any other, and **that is the rule
    working rather than the fan-out widening** — which is the distinction the
    clean-run case below still pins from the other side.

    The owner is fetched by their signup address rather than created: inside one
    tenant an address names one person (BR-IDN-029), so `staff_actor` returns
    the row provisioning already wrote.
    """
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        one = _admin_with_membership(brazos, "admin-one@brazosbendutilities.test")
        two = _admin_with_membership(brazos, "admin-two@brazosbendutilities.test")
        owner = staff_actor(brazos, "system_admin", "dana@brazosbendutilities.com")

        queue_before = models.OutboundMessage.objects.count()
        inbox_before = models.InAppMessage.objects.count()

        summary = bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=1204,
            failed_count=3,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        assert models.OutboundMessage.objects.count() - queue_before == 1

        result = dispatcher.dispatch_cycle(
            now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana
        )
        assert result.sent == 1, f"nothing was dispatched: {result.problems}"
        assert models.InAppMessage.objects.count() - inbox_before == 4

        # Every ruled recipient can READ it in their own bell.
        for recipient in (dana, one, two, owner):
            items = in_app.inbox(actor=recipient)
            assert len(items) == 1, f"{recipient.user.email} has no copy"
            assert "Billing run" in items[0].body
            assert "3" in items[0].body

        # And a RETRIED cycle re-delivers to nobody (rule 6, per inbox).
        row = models.OutboundMessage.objects.get(pk=summary.message_id)
        models.OutboundMessage.objects.filter(pk=row.pk).update(
            status=models.STATUS_QUEUED, batch_id=None, sent_at=None
        )
        again = dispatcher.dispatch_cycle(
            now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana
        )
        assert again.sent == 1
        assert models.InAppMessage.objects.count() - inbox_before == 4


def test_c11__a_clean_run_still_reaches_only_the_person_who_ran_it(brazos, dana):
    """The fan-out must not have widened the CLEAN case: zero failures, two
    admins on the tenant, and exactly ONE mailbox row — Dana's."""
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        one = _admin_with_membership(brazos, "admin-one@brazosbendutilities.test")

        bulk_summary.queue_bulk_summary(
            operation="Payment import",
            operation_id=uuid.uuid4(),
            total_count=40,
            failed_count=0,
            finished_at=FINISHED_AT,
            actor=dana,
        )
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)

        assert in_app.unread_count(actor=dana) == 1
        assert in_app.unread_count(actor=one) == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009c11 (12-governance/02-decision-log.md → 2026-08-17 C-11 verbatim · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-021 · apps/notifications/staff_recipients.py · apps/notifications/bulk_summary.py · apps/notifications/in_app.py)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(service-level — the wire half is asserted in test_cr_009_notification_rules.py) E=deferred(screen half in NotificationRules.test.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the acceptance pair was run BEFORE `in_app.deliver_batch` grew the fan-out loop and failed reading `in_app_messages grew by 1, expected 3`; the deactivated-admin exclusion was proved by asserting the leaver IN and reading the failure.
# exceptions: (1) MEMBERSHIPS ARE BUILT BY HAND because the shared `identity_seam` fixture stubs owner provisioning — the ruling is ABOUT memberships, so this file creates real rows against the real Role catalog rather than widening the shared stub. (2) THE BULK OPERATION IS SIMULATED, as in test_cr_009_bulk_one_message.py, and for its reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
