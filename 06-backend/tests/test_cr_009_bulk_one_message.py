# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — ONE message per bulk action)
#           Screens: shell-chrome (the bell) · S8
# Rules:    BR-NOT-020 (*"for single notification send 1 message and for bulk
#           action also send 1 message only saying nulk action is completed"*,
#           and where the operation had failures the summary must say HOW MANY) ·
#           BR-NOT-005 (queue only) · CLAUDE.md rule 6 (the queue's five-column
#           unique key is what makes "exactly one" structural)
# ───────────────────────────────────────────────────────
"""BR-NOT-020, as a COUNT.

The CR asks for exactly this file and says why: *"it belongs in the module's
business rules and needs a test that drives a bulk operation and asserts the
queue grew by exactly one."*

**A COUNT AND NOT A SHAPE ASSERTION.** A test that checked "the queued message
looks like a summary" passes just as happily on two hundred summaries, which is
the failure the rule exists to prevent. So the assertions here are
`OutboundMessage.objects.count()` before and after, against a bulk operation
over two hundred items.

**AND THE OTHER HALF.** A rule that only counted messages would let a lane ship
a reassuring one-liner over a run that failed eighty-seven times, and the CR is
explicit that *"a summary that hides a failure count is the same failure … in the
opposite direction."* Three tests below are about the failure count, and the
strongest of them is at the TEMPLATE level: the class makes `{failed_count}`
non-removable content, so even a utility editing the wording cannot drop it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import bulk_summary, catalogs, models, rendering, seed_templates

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call  # noqa: F401 — parity with the suite

pytestmark = pytest.mark.django_db

FINISHED_AT = datetime(2026, 8, 17, 21, 40, tzinfo=dt_timezone.utc)

#: The size of the bulk operation these tests drive. Two hundred, because that
#: is the number the PO's own ruling is written against: *"A bulk action over 200
#: accounts produces ONE message"*.
BULK_ITEMS = 200


def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=FINISHED_AT.date())


def _run_a_bulk_operation(actor, *, failed: int = 0, operation_id=None):
    """A bulk operation over `BULK_ITEMS` items that ends in ONE summary.

    The loop is REAL and is the point: this is the shape every bulk caller in
    the product has — iterate the items, count the outcomes, and then, ONCE,
    outside the loop, say what happened. A caller that queued inside the loop is
    what BR-NOT-020 forbids, and the count below is what would catch it.
    """
    processed = 0
    failures = 0
    for index in range(BULK_ITEMS):
        processed += 1
        if index < failed:
            failures += 1
    return bulk_summary.queue_bulk_summary(
        operation="Billing run",
        operation_id=operation_id or uuid.uuid4(),
        total_count=processed,
        failed_count=failures,
        finished_at=FINISHED_AT,
        actor=actor,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE COUNT
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc5__a_bulk_action_over_two_hundred_items_queues_exactly_one_message(brazos, dana):
    """**BR-NOT-020, the whole of it, in one number.**

    PO verbatim: *"for bulk action also send 1 message only saying nulk action
    is completed"*. Two hundred items in, one row on the queue.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        before = models.OutboundMessage.objects.count()
        summary = _run_a_bulk_operation(dana, failed=0)
        after = models.OutboundMessage.objects.count()

    assert after - before == 1, (
        f"a bulk action over {BULK_ITEMS} items queued {after - before} messages. "
        "BR-NOT-020 allows exactly one, and the reason is not tidiness: a clerk who "
        "receives 200 notifications turns the event off, and the failure they needed to "
        "see is the one they never get."
    )
    assert summary.total_count == BULK_ITEMS
    assert summary.created is True


def test_us_not_018_tc5b__failures_do_not_add_messages(brazos, dana):
    """The forbidden shape is specifically *"one per succeeded item plus one per
    failure"*. Eighty-seven failures out of two hundred is still ONE message."""
    with tenant_ctx(brazos):
        _seeded(dana)
        before = models.OutboundMessage.objects.count()
        summary = _run_a_bulk_operation(dana, failed=87)
        after = models.OutboundMessage.objects.count()

    assert after - before == 1
    assert summary.failed_count == 87


def test_us_not_018_tc6__a_retried_run_does_not_queue_a_second_summary(brazos, dana):
    """CLAUDE.md rule 6 — and the reason `source_id` is the RUN's id.

    A job that dies after queueing its summary and is retried must not tell the
    clerk twice. The DATABASE refuses it, so this holds even for a retry that
    never went through this function's own guard."""
    run_id = uuid.uuid4()
    with tenant_ctx(brazos):
        _seeded(dana)
        first = _run_a_bulk_operation(dana, failed=2, operation_id=run_id)
        before = models.OutboundMessage.objects.count()
        second = _run_a_bulk_operation(dana, failed=2, operation_id=run_id)
        after = models.OutboundMessage.objects.count()

    assert after == before
    assert first.created is True
    assert second.created is False
    assert second.message_id == first.message_id


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FAILURE COUNT — THE OTHER HALF OF THE RULING
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc3b__the_summary_states_the_failure_count(brazos, dana):
    """*"where the operation had failures it must say HOW MANY"*. The rendered
    body carries the number, not a word like "some"."""
    with tenant_ctx(brazos):
        _seeded(dana)
        summary = _run_a_bulk_operation(dana, failed=87)
        row = models.OutboundMessage.objects.get(pk=summary.message_id)
        artifact = rendering.render_for_dispatch(row)

    assert "87" in artifact.body
    assert "200" in artifact.body
    assert rendering.ABSENT_MARK not in artifact.body


def test_us_not_018_tc8__the_failure_count_is_non_removable_class_content(brazos, dana):
    """**THE STRONGEST GUARD, AND IT IS AT THE TEMPLATE LEVEL.**

    A utility editing this template down to *"Bulk action completed."* would
    produce exactly the reassuring summary the CR forbids. `mandatory_content`
    makes that a SAVE REFUSAL rather than a wording preference, so the rule
    survives a person who never read it.
    """
    catalog = catalogs.catalog_for(bulk_summary.TEMPLATE_CODE)
    assert "{failed_count}" in catalog.mandatory_content

    with pytest.raises(rendering.RenderRefused) as refusal:
        rendering.validate_body(bulk_summary.TEMPLATE_CODE, "Bulk action completed.")
    assert "failed_count" in str(refusal.value)


def test_us_not_018_tc7__a_caller_that_never_counted_its_failures_cannot_queue(brazos, dana):
    """`failed_count` has NO DEFAULT. A defaulted zero is how a run that failed
    87 times reports success, so the absence is a TypeError at the call site
    rather than a comforting lie in an inbox."""
    with tenant_ctx(brazos), pytest.raises(TypeError):
        bulk_summary.queue_bulk_summary(  # type: ignore[call-arg]
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=BULK_ITEMS,
            finished_at=FINISHED_AT,
            actor=dana,
        )


def test_us_not_018__more_failures_than_items_is_refused(brazos, dana):
    """Two figures from the same run that disagree would make a clerk distrust
    every summary after it."""
    with tenant_ctx(brazos), pytest.raises(bulk_summary.BulkSummaryRefused):
        bulk_summary.queue_bulk_summary(
            operation="Billing run",
            operation_id=uuid.uuid4(),
            total_count=10,
            failed_count=11,
            finished_at=FINISHED_AT,
            actor=dana,
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE RECIPIENT POLICY — RULED 2026-08-17 (BR-NOT-021, OQ-261 CLOSED)
# ══════════════════════════════════════════════════════════════════════════
def test_us_not_018_tc9__a_clean_job_with_no_signed_in_user_is_refused_with_the_ruling(brazos):
    """⚠ AMENDED 2026-08-18 — this test used to assert `"OQ-261" in refusal`
    because the question was OPEN. The PO closed it (2026-08-17, verbatim: *"the
    user who started the action, plus all System Admins for failures"* →
    BR-NOT-021), so the assertion moved from the question's id to the ruling's
    content. NOT loosened: a CLEAN nightly job still has nobody to report to —
    under the ruling, not for want of one — and the refusal must now cite the
    ruling so the operator knows a FAILED run would have reached the admins."""
    with tenant_ctx(brazos), pytest.raises(bulk_summary.BulkSummaryRefused) as refusal:
        bulk_summary.queue_bulk_summary(
            operation="Nightly reconciliation",
            operation_id=uuid.uuid4(),
            total_count=5,
            failed_count=0,
            finished_at=FINISHED_AT,
            actor=None,
        )
    assert "System Admins for failures" in str(refusal.value)
    assert "nobody to address" in str(refusal.value)


def test_cr_009_c11__a_failed_job_with_no_signed_in_user_reaches_the_system_admins(brazos, dana):
    """BR-NOT-021's other half: the SAME actor-less job WITH failures now has
    ruled recipients — every active System Admin — so it queues ONE message
    whose snapshot lists them. (Before the ruling this call was refused.)"""
    from apps.identity import models as identity_models
    from tests.test_us_met_helpers import staff_actor

    with tenant_ctx(brazos):
        _seeded(dana)
        admin = staff_actor(brazos, "system_admin", "night-admin@brazosbendutilities.test")
        identity_models.TenantMembership.objects.create(
            tenant=brazos,
            user=admin.user,
            role=identity_models.Role.objects.get(code="system_admin"),
            status=identity_models.TenantMembership.STATUS_ACTIVE,
        )
        summary = bulk_summary.queue_bulk_summary(
            operation="Nightly reconciliation",
            operation_id=uuid.uuid4(),
            total_count=5,
            failed_count=3,
            finished_at=FINISHED_AT,
            actor=None,
        )
        row = models.OutboundMessage.objects.get(pk=summary.message_id)

    recipients = row.recipient_snapshot["recipients"]
    assert len(recipients) >= 1, "a failure must reach at least one System Admin"
    assert all(entry["reason"] == "system_admin" for entry in recipients)
    # ONE queue row, whatever the mailbox count — BR-NOT-020 untouched.
    assert summary.created is True


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set, ruling 2 in full · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-020 · apps/notifications/bulk_summary.py · apps/notifications/catalogs.py staff_bulk_summary)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(no HTTP surface — a bulk operation calls the service) E=deferred(the message is READ in the shell bell) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: THE COUNT GUARD WAS PROVED RED FIRST (hard-won law 7): the helper's single call was replaced with a per-item `queue_bulk_summary` inside the loop, and the assertion failed reading `a bulk action over 200 items queued 200 messages`. The mandatory-content guard was proved red by removing `{failed_count}` from the class's `mandatory_content` and watching DID NOT RAISE.
# exceptions: (1) THE BULK OPERATION IS SIMULATED — it loops 200 items and counts outcomes rather than billing 200 real accounts, because no bill run calls this yet (OQ-262) and driving billing from a notifications test would couple two lanes' fixtures. What is REAL is the queue write, the template resolution, the render and the count. (2) [AMENDED 2026-08-18] THE RECIPIENT ASSERTIONS FOLLOW THE RULING (BR-NOT-021, OQ-261 closed): a clean actor-less job is still refused — with the ruling quoted — and a FAILED actor-less job now reaches the System Admins; the fan-out itself is proved end-to-end in tests/test_cr_009_c11_staff_recipients.py.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
