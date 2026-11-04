# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.10`
#          (*"Deliver the file · The outbound queue carries the link, not the
#          file · BR-NOT-005 · Recipients get a link that respects their
#          permissions"*). Drawing p15, read as an IMAGE per B14 rule 42.
# Rules:   BR-NOT-005 (queue only) · BR-REP-007 · BR-REP-017 CONFIRMED (the
#          rows are written now, the dispatch is W6) · BR-REP-018 (three-day
#          file) · BR-REP-020 CONFIRMED (internal staff only) · CLAUDE.md
#          rule 6 (idempotency) · hard-won law 2 and its mirror · law 7
# ───────────────────────────────────────────────────────
"""Delivery, asserted as BEHAVIOUR: a run finishes and a named person is told.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY — asked before they were
written, per hard-won law 7 habit (2).**

  · **The delivery case.** Asserting *"one row exists"* would pass over a
    product that queued the right number of rows carrying the wrong thing —
    an attachment, a bare *your report is ready*, or a link to another
    tenant's run. So it asserts the LINK's exact string, built from the slug
    and the run id, and asserts the recipient ADDRESS is the person the
    schedule names.
  · **The idempotency case.** Counting rows after two sweeps would also be
    satisfied by a second sweep that raised before it wrote. So it asserts the
    outcome CODE flips from `..._queued` to `..._already_queued` — the fold-in
    actually happening — and that the row's id is unchanged.
  · **The failure case.** Asserting *no row* is the whole risk: a test that
    never queues anything passes it. So the SAME fixture is driven twice —
    once with the run succeeded (a row) and once failed (no row) — and both
    halves are asserted in one function, so a broken writer cannot satisfy it.
  · **The mandatory-link case** drives `rendering.validate_body` directly with
    a body that has had the token removed, and asserts the refusal NAMES the
    token. A test that only checked the good body would pass over a class
    whose `mandatory_content` was an empty tuple.
  · **`pytest.skip` is not used anywhere in this file.** A skip that fires
    when a fixture lacks something reads as a pass in the summary line.

⚠ **NOTHING HERE ASSERTS A SEND, BECAUSE NOTHING SENDS.** `BR-REP-017` is
CONFIRMED: the dispatch ships at W6. `test_nothing_is_dispatched` asserts that
as a VALUE — the row's status — rather than leaving it to this paragraph.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications import catalogs, models as notif_models, rendering, seed_templates
from apps.reports import delivery, notifications_seam, run_history, schedules
from apps.reports.models import CADENCE_DAILY, ReportDefinition, ReportSchedule
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import seeding_ctx, tenant_ctx

pytestmark = pytest.mark.django_db

SLUG = "brazosbend"


@pytest.fixture(autouse=True)
def wired(tmp_path, settings):
    """The deployment's own wiring — real store, real transport, EAGER.

    ⚠ `config/settings/test.py` SETS `JOBS_EAGER = False` AND AN ENVIRONMENT
    VARIABLE DOES NOT OVERRIDE IT. `test_cr142_p4_schedules.py` records the
    same measurement; without this the accept path reaches for Celery and dies
    on a traceback that names Redis and says nothing about the setting that
    sent it there.
    """
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def _staff(actor, tenant):
    """Give `actor` a MEMBERSHIP, which is what makes them staff.

    `staff_actor` creates a `users` row and NO membership, and
    `identity.selectors.user_list` — the read `BR-REP-020` is enforced through
    — queries `TenantMembership`. `test_cr142_p4_schedules.py` records the
    measurement in full.
    """
    from apps.identity import models as identity_models

    with seeding_ctx(tenant):
        role, _ = identity_models.Role.objects.get_or_create(
            code=actor.role, defaults={"name": actor.role.replace("_", " ").title()}
        )
        identity_models.TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=actor.user,
            defaults={"role": role, "status": identity_models.TenantMembership.STATUS_ACTIVE},
        )
    return actor


def _schedule(tenant, actor, *, name="AR Ageing", key="ar-aging-delivery-fixture"):
    definition = ReportDefinition.objects.create(
        tenant=tenant,
        key=key,
        name=name,
        dataset="invoices",
        group_code="finance",
    )
    return ReportSchedule.objects.create(
        tenant=tenant,
        definition=definition,
        cadence=CADENCE_DAILY,
        params={"resource": "ar_aging", "q": "", "filters": {}},
        recipients=[str(actor.id)],
        next_run_at=timezone.now() - timedelta(minutes=1),
        enabled=True,
        created_by_user_id=actor.id,
    )


def _fire_only(actor):
    """Fire every due schedule and deliver NOTHING — the firing half alone.

    ⚠ **`tenant_slug=None` IS WHY, AND IT IS THE PRODUCT'S OWN BEHAVIOUR
    RATHER THAN A TEST HOOK.** A caller that cannot name the utility gets no
    message, because a link with a hole in it is worse than no link
    (`delivery.NOT_DELIVERED_NO_TENANT_SLUG`). Every case below needs a run
    that EXISTS before it decides what delivery should do with it, and the
    beat is the only caller that has a slug.

    ⚠ **IT IS NEEDED BECAUSE `JOBS_EAGER` FINISHES THE EXPORT INSIDE
    `fire()`.** On a deployment the job is Celery's and is still running when
    the sweep returns, so the first sweep fires and the next one delivers.
    Under the eager transport one call does both — which five cases in this
    file were first written NOT to expect, and the code was right.
    """
    return schedules.sweep(actor=actor, tenant_slug=None)


def _rows(tenant):
    return list(
        notif_models.OutboundMessage.objects.filter(
            tenant=tenant, source_type="report"
        ).order_by("created_at")
    )


# ═══════════════════════════════════════════════════════════════════════════
# `P4.10` — the phase's DONE WHEN: *delivered to named internal staff*
# ═══════════════════════════════════════════════════════════════════════════


def test_a_finished_run_queues_one_email_carrying_the_link_and_not_the_file(brazos, dana):
    """The task's own outcome sentence, asserted on the LINK's exact string.

    Two sweeps, and both are load-bearing: the first FIRES (the job has no
    file yet, so nothing is delivered — the run is not ready), the second
    DELIVERS. That is the product's real shape, not a convenience: a message
    can never announce a run that has not finished.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
        first = _fire_only(dana.user)
        assert first["fired"], "the schedule was due and did not fire"
        # ⚠ AND IT DELIVERED NOTHING, WHICH IS ASSERTED RATHER THAN ASSUMED:
        # a fixture that cannot tell "nothing was delivered" from "the slug was
        # missing" would let the case below pass for the wrong reason.
        assert [item["code"] for item in first["delivery"]] == [
            delivery.NOT_DELIVERED_NO_TENANT_SLUG
        ]
        second = schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        rows = _rows(brazos)
        # ⚠ **RE-READ, BECAUSE `fire()` WROTE TO A DIFFERENT INSTANCE.** The
        # sweep loads its own `ReportSchedule` rows through `due()`, so the
        # object this test is holding still has `last_job_id is None` — and an
        # assertion built from it would compare the link against
        # `.../history/None` and fail with a message about a LINK when the
        # fault was a stale ORM object.
        schedule.refresh_from_db()
        job_id = schedule.last_job_id

    assert len(rows) == 1, f"one run, one message — got {len(rows)}"
    row = rows[0]
    assert row.channel == notif_models.CHANNEL_EMAIL
    # ⚠ THE ADDRESS IS THE PERSON THE SCHEDULE NAMES, not a fallback and not
    # an unavailable_reason. A row with a reason instead of an address is a
    # message that will never be delivered, and it is what the first draft of
    # this seam produced when `account_id=None` went through the customer read.
    assert row.recipient_address == dana.user.email
    assert row.unavailable_reason is None
    # ⚠ THE LINK, EXACTLY. `P4.10`: the queue carries the LINK, not the file.
    context = row.render_context or {}
    assert job_id is not None, "the sweep fired and left no job id on the schedule"
    assert context["report_link"] == f"/{SLUG}/reports/history/{job_id}"
    assert context["report_name"] == "AR Ageing"
    # ⚠ AND NOTHING THAT COULD BE A FILE. The palette has no token for one, so
    # this asserts the palette rather than the value: a later lane adding an
    # attachment token would fail here and not in a review comment.
    palette = catalogs.catalog_for("email_scheduled_report").tokens
    assert not {token for token in palette if "file" in token or "attach" in token}
    assert second["delivered"] == 1


def test_a_second_sweep_folds_into_the_one_message_rather_than_writing_a_second(brazos, dana):
    """CLAUDE.md rule 6, asserted on the outcome CODE and the row id.

    A count of one after two sweeps would also be satisfied by a second sweep
    that raised before it wrote — which is delivery silently stopping, the
    opposite of what this case exists to prove.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _schedule(brazos, dana)
        _fire_only(dana.user)
        first = schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        second = schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        rows = _rows(brazos)

    codes_first = [item["code"] for item in first["delivery"]]
    codes_second = [item["code"] for item in second["delivery"]]
    assert notifications_seam.REPORT_MESSAGE_QUEUED in codes_first
    assert notifications_seam.REPORT_MESSAGE_ALREADY_QUEUED in codes_second
    assert len(rows) == 1


def test_a_run_that_failed_tells_nobody_and_a_run_that_succeeded_does(brazos, dana):
    """BOTH halves in one function, deliberately — see the module docstring.

    A test that only asserted *no row for a failure* is satisfied by a writer
    that never queues anything at all.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
        _fire_only(dana.user)
        schedule.refresh_from_db()
        # ⚠ **THE STATUS IS WRITTEN THROUGH THE STORE AND NOT THROUGH
        # `core_jobs.fail`, AND THE REASON IS WORTH THE THREE LINES.**
        # `fail()` is forward-only — *"only a running job can fail"* — and the
        # EAGER transport has already run this job to `succeeded` inside
        # `fire()`. Calling it raises `JobsError`, which is the kernel being
        # right about its own lifecycle and this case being about a state that
        # a Celery deployment reaches normally and an eager one cannot.
        store = tenancy_services.JobStore()
        record = store.get(schedule.last_job_id)
        record["status"] = "failed"
        record["error"] = "the report raised"
        store.save(record)
        schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        assert _rows(brazos) == [], "a failed run must not announce itself as ready"
        # `4·1` still shows the schedule, marked failing — `P4.8`, unchanged.
        schedule.refresh_from_db()
        assert schedule.enabled is True

        # And now the other half: a run that DID succeed.
        _schedule(brazos, dana, key="ar-aging-delivery-fixture-2")
        _fire_only(dana.user)
        schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        assert len(_rows(brazos)) == 1


def test_nothing_is_dispatched_because_br_rep_017_says_w6(brazos, dana):
    """`BR-REP-017` CONFIRMED, asserted as a VALUE rather than as a sentence."""
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _schedule(brazos, dana)
        _fire_only(dana.user)
        schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        row = _rows(brazos)[0]
    assert row.status == notif_models.STATUS_QUEUED
    assert row.sent_at is None


def test_without_a_tenant_slug_there_is_no_message_and_the_reason_is_named(brazos, dana):
    """A link with a hole in it is worse than no link, and silence is worse than both.

    `sweep()` called by anything but the beat has no slug. It must not guess
    one, and it must not go quiet: the reason travels on the outcome.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _schedule(brazos, dana)
        _fire_only(dana.user)
        outcome = schedules.sweep(actor=dana.user)  # no slug
        assert _rows(brazos) == []
    assert [item["code"] for item in outcome["delivery"]] == [
        delivery.NOT_DELIVERED_NO_TENANT_SLUG
    ]


def test_a_schedule_whose_person_has_left_queues_nothing_and_says_which(brazos, dana):
    """`BR-REP-020` refuses rather than filters, and delivery must not soften it.

    Dropping the unknown recipient and sending to whoever is left would be a
    month-end pack quietly going to fewer people than the schedule names.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
        _fire_only(dana.user)
        schedule.recipients = ["00000000-0000-0000-0000-000000000000"]
        schedule.save(update_fields=["recipients"])
        outcome = schedules.sweep(actor=dana.user, tenant_slug=SLUG)
        assert _rows(brazos) == []
    codes = [item["code"] for item in outcome["delivery"]]
    assert codes == [delivery.NOT_DELIVERED_NO_RECIPIENTS]


# ═══════════════════════════════════════════════════════════════════════════
# THE LINK CANNOT BE EDITED OUT — the task made structural
# ═══════════════════════════════════════════════════════════════════════════


def test_the_seeded_body_carries_the_link_and_a_body_without_one_is_refused():
    """`{report_link}` is mandatory content, so a tenant cannot remove it.

    ⚠ The refusal must NAME the token. A bare *"this body is invalid"* is a
    message a clerk cannot act on, and `validate_body` is the save-time gate a
    real person meets.
    """
    seeded = {entry.code: entry for entry in seed_templates.SEEDABLE}
    body = seeded["email_scheduled_report"].body
    assert "{report_link}" in body
    rendering.validate_body("email_scheduled_report", body)

    stripped = body.replace("Open it here: {report_link}\n", "")
    with pytest.raises(rendering.RenderRefused) as refused:
        rendering.validate_body("email_scheduled_report", stripped)
    assert "{report_link}" in str(refused.value)


def test_the_class_is_listed_seeded_and_ruled_so_it_is_not_orphan_wording():
    """Three registers, one class — the shape `seeded_wording_without_rule` counts.

    A class seeded and unruled is wording nothing can ever send, which is the
    gap CR-048 B9 exists to measure. This one is ruled from its first commit.
    """
    from apps.notifications import rule_catalog

    assert "email_scheduled_report" in catalogs.LISTINGS
    assert "email_scheduled_report" in {entry.code for entry in seed_templates.SEEDABLE}
    assert "email_scheduled_report" not in rule_catalog.seeded_wording_without_rule()
    event = rule_catalog.event("scheduled_report_ready")
    assert event.source_type == "report"
    assert event.template_classes == {notif_models.CHANNEL_EMAIL: "email_scheduled_report"}


def test_the_run_link_is_a_path_and_carries_no_host():
    """A message carrying `http://localhost:8000/...` is worse than one carrying a path."""
    built = delivery.run_link("brazosbend", "abc")
    assert built == "/brazosbend/reports/history/abc"
    assert "://" not in built


def test_the_history_screen_and_this_module_build_the_same_address():
    """`5·2`'s address is spelled in two files, so a test holds them together.

    `ReportRunsPage.tsx` builds ``${historyBase}/${row.id}`` and this module
    builds `RUN_PATH`. Nothing else can notice them parting company — the day
    the route moves, a clerk clicks a link in an email and lands on a 404.
    """
    assert delivery.RUN_PATH == "/{tenant}/reports/history/{run}"
    assert run_history.RUN_KINDS == ("list_export",)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.10 (05-prototype/09 Reports Build Brief.pdf p15, read as an image per B14 rule 42) · 04-docs/05-modules/12-reports/06-epics/EP-REP-04-scheduler.md US-REP-015 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-007/017/018/020
# generated: 2026-09-27 by lane REP-P4-REST
# ──────────────────────────────────────────────────────────
