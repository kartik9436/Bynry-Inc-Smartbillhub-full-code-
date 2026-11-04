# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3422 (PO, 2026-09-02) — *"this says - staff notification - but we
#          dont get any notification"*, with the bell reading "You're all caught
#          up." Three links were dead at once and each looked fine on its own:
#          (1) `notifications.services.queue_staff_alert` — the seam
#          `apps/tenancy/sample_data.py` resolves BY NAME — was never published,
#          so a provisioning shortfall raised nothing; (2) `core/bell.py` had no
#          sink AND no caller, and `bell_events` had no reader; (3) the dispatch
#          schedule fired for the tenants named in an environment variable and
#          for nobody when it is unset, which is every deployment.
# Story:   US-NOT-018 (ONE message per bulk action) × US-TEN-019 §5 (C-15, the
#          SOFT completeness check) × US-SHL-004 (the bell)
# Rules:   BR-NOT-021 (the ruled staff audience: the initiator, plus every
#          active System Admin on failure) · BR-NOT-020 (one message, more
#          mailboxes) · BR-NOT-019 (in-app is the channel that delivers) ·
#          BR-NOT-005 (queue only — nothing here sends inline) ·
#          BR-TEN-043 (no wall clock: every moment is a parameter) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · rule 6 (idempotency) ·
#          hard-won law 2 (BUILT IS NOT WIRED) · law 7 (RED before green)
# ───────────────────────────────────────────────────────
"""DEF-3422 — a real failure, a real bell item, the ruled recipients.

**WHY THIS FILE DRIVES PROVISIONING AND NOT `notify()`.** The unit test that
existed for the bell (`tests/test_be09_bell.py`, now deleted with the module it
tested) called `core.bell.notify()` with a sink of its own and passed for
three weeks over a product in which nothing called `notify()` and nothing had
ever registered a sink. A test that supplies the missing link cannot see that
the link is missing. So the acceptance case here arranges a REAL seeding
failure on a REAL tenant through the REAL provisioning job, runs a REAL
dispatch cycle, and reads the bell through the same `in_app.inbox` call the
shell's bell makes.

**THE FOUR LINKS, EACH ASSERTED SEPARATELY**, because that is what the defect
cost: every one of them individually looked fine.

  1. the seam the caller resolves is PUBLISHED (`test_..._the_seam_is_published`);
  2. it reaches the ruled audience — one queue row, one mailbox per recipient;
  3. the message travels queue → dispatcher → inbox and is READ from the bell;
  4. a second utility's System Admin never sees it (hard rule 1).

And two guards on the links that were removed rather than repaired: the bell
has ONE store (`bell_events` is gone), and the schedule names every live
utility when an operator has configured none.
"""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.identity import models as identity_models
from apps.notifications import bulk_summary, dispatcher, in_app, models, schedule, seed_templates
from apps.tenancy import models as tenancy_models
from apps.tenancy import seams

from tests.isolation_helpers import requires_postgres  # noqa: F401 — used by name
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    fake_module_seams,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the moment is NAMED, never read from a clock.
FINISHED_AT = datetime(2026, 9, 2, 16, 40, tzinfo=dt_timezone.utc)


def _admin(tenant, email):
    """An ACTIVE System Admin membership — what `identity.selectors.user_list`
    serves and `is_active_system_admin` passes."""
    actor = staff_actor(tenant, "system_admin", email)
    identity_models.TenantMembership.objects.create(
        tenant=tenant,
        user=actor.user,
        role=identity_models.Role.objects.get(code="system_admin"),
        status=identity_models.TenantMembership.STATUS_ACTIVE,
    )
    return actor


# ══════════════════════════════════════════════════════════════════════════
# LINK 1 · THE SEAM THE CALLER ALREADY RESOLVES BY NAME
# ══════════════════════════════════════════════════════════════════════════
def test_def3422_link1__the_seam_sample_data_names_is_published():
    """`apps/tenancy/sample_data.py` has resolved this name since C-15 landed
    and got `None` every time, so its own audit row recorded *"support_alert:
    not delivered — apps.notifications.services publishes no staff-alert
    seam"*. Nothing was wrong with either module; the wire was missing.

    Resolved through tenancy's OWN seam helper, the way the caller does it —
    asserting that `apps.notifications` has an attribute somewhere would pass
    on a function the caller cannot reach.
    """
    entry = seams.resolve("notifications", "queue_staff_alert")
    assert entry is not None, (
        "apps.notifications.services.queue_staff_alert is not published, so a "
        "provisioning shortfall raises no staff alert at all — which is the "
        "whole of DEF-3422's first link."
    )
    assert callable(entry)


# ══════════════════════════════════════════════════════════════════════════
# LINK 2 · THE RULED AUDIENCE — ONE MESSAGE, ONE MAILBOX PER RECIPIENT
# ══════════════════════════════════════════════════════════════════════════
def test_def3422_link2__one_queue_row_and_a_mailbox_per_ruled_recipient(brazos, dana):
    """BR-NOT-021 in full: *"the user who started the action, plus all System
    Admins for failures"*. An ALERT is a failure by definition, so both halves
    of the ruling always apply to it.

    The load-bearing assertion is a PAIR of counts, for
    `test_cr_009_c11_staff_recipients.py`'s reason: one queue row delivered to
    one inbox passes the first alone, and three queue rows delivered to three
    inboxes passes the second alone.
    """
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        _admin(brazos, "admin-one@brazosbendutilities.test")
        _admin(brazos, "admin-two@brazosbendutilities.test")

        queued_before = models.OutboundMessage.objects.count()
        delivered_before = models.InAppMessage.objects.count()

        outcome = bulk_summary.queue_staff_alert(
            actor=dana,
            operation="Sample data setup",
            operation_id=uuid.uuid4(),
            total_count=17,
            failed_count=1,
            finished_at=FINISHED_AT,
        )
        assert outcome["code"] == bulk_summary.STAFF_ALERT_QUEUED, outcome
        assert models.OutboundMessage.objects.count() - queued_before == 1, (
            "BR-NOT-020: one alert is ONE message however many people it "
            "reaches. More mailboxes, never more messages."
        )

        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        assert models.InAppMessage.objects.count() - delivered_before == 4, (
            "the ruled audience is the initiator plus every active System "
            "Admin, so one alert must land in four inboxes. ⚠ FOUR, not three: "
            "the fourth is the tenant's PROVISIONING OWNER, who is a System "
            "Admin by BR-TEN-001 and is easy to forget because no line of this "
            "test creates them — `test_cr_009_c11_staff_recipients.py` records "
            "the same correction and the same reason."
        )
        assert in_app.unread_count(actor=dana) == 1


def test_def3422_link2__an_alert_copies_the_admins_even_when_a_job_started_it(brazos):
    """A scheduled job has no signed-in user, and the provisioning plant is
    exactly that shape. `queue_bulk_summary` REFUSES a clean job-started
    summary because the ruling names nobody for it — an ALERT is different, and
    the difference is the reason this entry point exists: it always resolves
    the audience as a failure, so the System Admins are always on the envelope.
    """
    with tenant_ctx(brazos):
        anyone = _admin(brazos, "admin-solo@brazosbendutilities.test")
        seed_templates.seed_notice_templates(anyone, on_date=FINISHED_AT.date())

        outcome = bulk_summary.queue_staff_alert(
            actor=None,
            operation="Sample data setup",
            operation_id=uuid.uuid4(),
            total_count=17,
            failed_count=2,
            finished_at=FINISHED_AT,
        )
        assert outcome["code"] == bulk_summary.STAFF_ALERT_QUEUED, outcome
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=anyone)
        assert in_app.unread_count(actor=anyone) == 1


def test_def3422_link2__the_seam_raises_nothing_whatever_it_is_handed(brazos, dana):
    """**The promise this entry point exists to keep, tested at its edges.**

    C-15 is SOFT: the tenant opens whatever happened to the alert. So the one
    function a provisioning job calls must come back with a sentence rather than
    an exception, for every shape of bad input — including the two that would
    otherwise raise from the coercion, BEFORE the savepoint that makes the
    promise meaningful.
    """
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        for failed in (0, None, "twelve"):
            outcome = bulk_summary.queue_staff_alert(
                actor=dana,
                operation="Sample data setup",
                operation_id=uuid.uuid4(),
                total_count=18,
                failed_count=failed,
                finished_at=FINISHED_AT,
            )
            assert outcome["code"] == bulk_summary.STAFF_ALERT_REFUSED, (failed, outcome)
            assert outcome["message_id"] is None
            assert outcome["note"], "a refusal must say why, in a sentence"


def test_def3422_link2__a_repeated_alert_for_one_run_says_it_once(brazos, dana):
    """CLAUDE.md rule 6. The operation's own id is the key, so a retried
    provisioning job finds its own message and writes nothing — the DATABASE
    refuses the second, which is the only guarantee that survives a retry that
    never called this function twice."""
    operation_id = uuid.uuid4()
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        first = bulk_summary.queue_staff_alert(
            actor=dana,
            operation="Sample data setup",
            operation_id=operation_id,
            total_count=17,
            failed_count=1,
            finished_at=FINISHED_AT,
        )
        before = models.OutboundMessage.objects.count()
        second = bulk_summary.queue_staff_alert(
            actor=dana,
            operation="Sample data setup",
            operation_id=operation_id,
            total_count=17,
            failed_count=1,
            finished_at=FINISHED_AT,
        )
        assert models.OutboundMessage.objects.count() == before
        assert second["code"] == bulk_summary.STAFF_ALERT_ALREADY_QUEUED
        assert second["message_id"] == first["message_id"]


# ══════════════════════════════════════════════════════════════════════════
# LINK 3 · END TO END — A REAL SEEDING FAILURE REACHES A REAL BELL
# ══════════════════════════════════════════════════════════════════════════
def test_def3422_link3__a_failed_seeding_block_lands_in_the_owners_bell(
    growth_plan, identity_seam, audit_rows, monkeypatch, settings
):
    """**THE ACCEPTANCE CASE. Break a seeding block; read the bell.**

    Nothing is stubbed between the failure and the bell: the real provisioning
    job, the real C-15 check, the real seam, the real queue write, the real
    dispatcher, the real in-app adapter, and the same `in_app.inbox` read the
    shell's bell makes.

    `assets` is the module broken, following `test_us_ten_019_sample_data.py`'s
    choice. ⚠ It does NOT stay one line: with no meters, the opening reads fail
    validation, so no bill can be raised and no payment matched — this run came
    up **12 blocks short of 18**, and the alert says so. The COUNT is read back
    from the run's own record rather than written into this test, because the
    assertion that matters is that the bell carries the run's figure and not a
    figure this file remembered.

    The tenant's provisioning owner IS its System Admin (BR-TEN-001), so under
    BR-NOT-021 they are on the envelope twice over — as the initiator of the
    plant and as an admin of a failure — and must appear in exactly one
    mailbox.
    """
    settings.JOBS_EAGER = True
    fake_module_seams(monkeypatch, "assets", unwired=("seed_sample_records",))
    tenant, result = provisioned_tenant(brazosbend_payload(subdomain="brazosbend-short"))
    assert result["created"] is True, "C-15 is SOFT — the tenant opens regardless"

    incomplete = [row for row in audit_rows if row["action"] == "sample.seed_incomplete"]
    assert len(incomplete) == 1, "the plant came up short exactly once"
    note = incomplete[0]["after"]["support_alert"]
    assert "nobody was told" not in note, (
        "C-15's third limb is the support alert and this audit row still says "
        f"nobody was told: {note!r}"
    )
    assert "not delivered" not in note, note
    short_count = len(incomplete[0]["after"]["not_loaded"])
    assert short_count >= 1, "the arranged shortfall did not happen"

    owner = tenancy_models.Tenant.objects.get(pk=tenant.id)
    with tenant_ctx(owner):
        membership = identity_models.TenantMembership.objects.filter(
            tenant_id=owner.id, status=identity_models.TenantMembership.STATUS_ACTIVE
        ).first()
        assert membership is not None, "provisioning must leave an owner membership"
        bell_actor = staff_actor(owner, "system_admin", membership.user.email)
        bell_actor.user = membership.user
        bell_actor.id = membership.user.id

        assert in_app.unread_count(actor=bell_actor) == 0, (
            "a queued message is not a delivered one — the bell must still be "
            "empty until a dispatch cycle runs (BR-NOT-005)."
        )
        dispatcher.dispatch_cycle(
            now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=bell_actor
        )

        items = in_app.inbox(actor=bell_actor)
        assert len(items) == 1, (
            "the System Admin's bell is empty after a provisioning run that came "
            "up short. That is DEF-3422 exactly: the bell reads 'You're all "
            "caught up' and always will."
        )
        body = items[0].body
        assert f"{short_count} failed" in body, (
            "BR-NOT-020's binding half — *'where the operation had failures it "
            f"must say HOW MANY'*. The run recorded {short_count} part(s) that "
            f"did not load and the bell must carry that same figure, not a "
            f"reassuring one. Body was: {body!r}"
        )
        assert "BR-" not in body and "sample_data_runs" not in body, (
            "B14 rule 32 / DEF-2377: no rule id and no table name in copy a "
            f"clerk reads. Body was: {body!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# LINK 4 · HARD RULE 1 — ANOTHER UTILITY'S BELL IS ANOTHER UTILITY'S
# ══════════════════════════════════════════════════════════════════════════
def test_def3422_link4__another_utilitys_system_admin_never_sees_it(
    brazos, dana, growth_plan, identity_seam
):
    """One utility's alert must be invisible from the other's tenant scope.

    The read is made THROUGH the other tenant's context, which is the only
    version of this assertion that means anything: counting rows with no
    context at all proves nothing about what a signed-in person can see.
    """
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        bulk_summary.queue_staff_alert(
            actor=dana,
            operation="Sample data setup",
            operation_id=uuid.uuid4(),
            total_count=17,
            failed_count=1,
            finished_at=FINISHED_AT,
        )
        dispatcher.dispatch_cycle(now=FINISHED_AT, channels=(models.CHANNEL_IN_APP,), actor=dana)
        assert in_app.unread_count(actor=dana) == 1

    with tenant_ctx(lonestar):
        stranger = _admin(lonestar, "admin@lonestarridge.test")
        assert in_app.unread_count(actor=stranger) == 0
        assert in_app.inbox(actor=stranger) == ()


# ══════════════════════════════════════════════════════════════════════════
# THE TWO LINKS THAT WERE REMOVED RATHER THAN REPAIRED
# ══════════════════════════════════════════════════════════════════════════
def test_def3422__the_bell_has_exactly_one_store():
    """`bell_events` and `core/bell.py` are GONE (decision log 2026-09-03).

    A second table behind the same bell would be two answers to *"what is in my
    bell"*, and the one that had no writer, no reader and no caller is the one
    that went. Asserted rather than trusted to a grep, because the module came
    with a docstring calling itself *"the only sanctioned writer"* of a table
    nothing ever wrote — hard-won law 1.
    """
    assert not hasattr(tenancy_models, "BellEvent"), (
        "the bell's second store is back. One feed, one store: the queue row "
        "and the mailbox behind it."
    )
    # ⚠ THE FILE, NOT AN IMPORT. `pytest.raises(ImportError)` around
    # `__import__("core.bell")` was the first draft and it is worthless here:
    # this checkout shares a venv whose path also reaches a second copy of the
    # backend, so a module deleted in THIS tree still imports from the other
    # one. The check that cannot pass by accident is whether the source file is
    # in the repository.
    backend = pathlib.Path(__file__).resolve().parents[1]
    assert not (backend / "core" / "bell.py").exists(), (
        "core/bell.py is back. It had no registered sink and no caller outside "
        "its own test, so it could never put anything in anybody's bell."
    )


@requires_postgres
def test_def3422__the_bell_events_table_is_dropped(django_db_setup, django_db_blocker):
    """The MIGRATION ran, not merely the model deletion.

    A deleted model with a table still standing is the same silence in the
    other direction: nothing in the product would mention it and it would keep
    its RLS policy, its index and its row count forever.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.bell_events')")
        assert cursor.fetchone()[0] is None, "bell_events still exists"


def test_def3422__the_schedule_names_every_live_utility_when_none_is_configured(
    brazos, monkeypatch
):
    """**Hard-won law 3: defaults fail closed, and this one failed silent.**

    `NOTIFICATIONS_DISPATCH_TENANTS` names the utilities beat paces. Unset — the
    state of every deployment, because nothing sets it — `scheduled_subdomains`
    returned an empty tuple, so every firing dispatched to nobody and said so
    in a log nobody reads. Messages were queued correctly and delivered never,
    which is the bell empty for the reason furthest from where anyone looked.

    The environment variable still WINS when an operator sets it; what changed
    is what happens when they have not.
    """
    monkeypatch.delenv(schedule.DISPATCH_TENANTS_ENV, raising=False)
    assert brazos.subdomain in schedule.scheduled_subdomains(), (
        "with no operator configuration the dispatch schedule paces no utility "
        "at all, so nothing queued is ever delivered."
    )

    monkeypatch.setenv(schedule.DISPATCH_TENANTS_ENV, "just-this-one")
    assert schedule.scheduled_subdomains() == ("just-this-one",), (
        "an operator who names the utilities they pace must still get exactly "
        "those and no others."
    )


def test_def3422__one_beat_firing_delivers_an_alert_with_nothing_configured(
    brazos, dana, monkeypatch
):
    """**THE LINK THE LIST ASSERTION ALONE WOULD NOT HAVE PROVED.**

    The case above asserts that `scheduled_subdomains()` NAMES the utility. That
    is exactly the shape of check that let this defect live for a fortnight — a
    correct answer from one function while the chain around it does nothing. So
    this one fires the real fan-out the way beat fires it, with the environment
    variable UNSET, and reads the bell afterwards.

    `_DISPATCH_ONE_TASK` is unbound so the cycle runs inline: the fan-out hands
    each tenant to celery when there is a broker, and this suite has none.
    Unbinding it exercises the module's own documented fallback rather than
    replacing anything it does.
    """
    monkeypatch.delenv(schedule.DISPATCH_TENANTS_ENV, raising=False)
    monkeypatch.setattr(schedule, "_DISPATCH_ONE_TASK", None)

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=FINISHED_AT.date())
        bulk_summary.queue_staff_alert(
            actor=dana,
            operation="Sample data setup",
            operation_id=uuid.uuid4(),
            total_count=18,
            failed_count=12,
            finished_at=FINISHED_AT,
        )
        assert in_app.unread_count(actor=dana) == 0

    report = schedule.dispatch_all()
    assert brazos.subdomain in report["tenants"], report
    assert report["problem"] is None, report

    with tenant_ctx(brazos):
        assert in_app.unread_count(actor=dana) == 1, (
            "one firing of the schedule, with nothing configured, delivered "
            "nothing. That is DEF-3422's third link: the queue fills correctly "
            "and the bell stays empty forever."
        )
        assert "12 failed" in in_app.inbox(actor=dana)[0].body


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-004@5a55bc4 (the bell story, and the commit that fixed DEF-3422 · 12-governance/10-defect-log.csv · 12-governance/02-decision-log.md 2026-09-03 "the bell has one store and one feed" · apps/notifications/bulk_summary.py queue_staff_alert · apps/tenancy/sample_data.py completeness_check · apps/notifications/schedule.py scheduled_subdomains · 04-docs/05-modules/00-platform-shell/02-business-rules.md BR-SHL-026)
# generated: 2026-09-03 by story-coder (DEF-3422 bell lane)
# checklist: A✔ B=deferred(no frontend half — the bell that READS these messages is AppShell.tsx and shipped with CR-009; nothing on a screen changes) C✔ D=deferred(no HTTP surface of its own) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST, every case, and the failures are quoted in the lane report
# exceptions: (1) THE ACCEPTANCE CASE DRIVES PROVISIONING, not the seam. A test that supplies the missing link cannot see that the link is missing, which is precisely how `test_be09_bell.py` passed for three weeks over a bell nothing could fill. (2) NOTHING HERE READS A CLOCK — `FINISHED_AT` is named once and passed down (BR-TEN-043).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
