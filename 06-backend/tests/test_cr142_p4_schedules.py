# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4. `P4.2` (a schedule
#          firing twice produces ONE file) · `P4.3` (recipients: internal staff
#          only) · `P4.7` (four cadences, four correct dates) · `P4.8` (a
#          failing schedule STAYS, marked failing). Drawings pp14–15, 34, 40,
#          read as images per B14 rule 42.
# Rules:   BR-REP-020 CONFIRMED · CLAUDE.md hard rule 6 (idempotency) ·
#          hard-won law 7 (prove a guard RED first, and ask what would make it
#          pass wrongly) · law 14 (SQLite is not PostgreSQL)
# ───────────────────────────────────────────────────────
"""The scheduler, asserted as BEHAVIOUR rather than as constants.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY — asked before they were
written, per hard-won law 7 habit (2).**

  · **The idempotency case.** `test_a_schedule_that_fires_twice_produces_one_file`
    would pass over a broken product if the SECOND call simply raised and the
    case counted rows afterwards. So it asserts the two accepted records carry
    the **same job id** — the fold-in actually happening — rather than asserting
    a count, which a refusal would also satisfy.
  · **The cadence cases.** Asserting `next_run_at(...) is not None` would pass
    for any date at all. Every case names the exact date it expects and the
    expected dates were worked out by hand from the drawing's own examples.
  · **The recipients case.** A case that only asserted the good path would pass
    over a `resolve_recipients` that accepted ANYTHING — including an email
    address. So the refusal is asserted in BOTH directions: a foreign tenant's
    real user id is refused, and this tenant's own is accepted.
  · **`pytest.skip` is not used anywhere in this file.** A skip that fires when
    a fixture lacks something reads as a pass in the summary line; the fixtures
    below create what they need.

⚠ **THE RLS HALF IS NOT HERE AND CANNOT BE.** `config/settings/test.py`
hardcodes in-memory SQLite, which has no row-level security of any kind, so
every isolation assertion would pass by vacuum (hard-won law 14).
`tests/test_cr142_p4_schedules_pg.py` is that half and runs on real PostgreSQL.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.reports import schedules
from apps.reports.models import (
    CADENCE_DAILY,
    CADENCE_MONTHLY,
    CADENCE_MONTHLY_ON_CYCLE_CLOSE,
    CADENCE_WEEKLY,
    ReportDefinition,
    ReportSchedule,
)
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import seeding_ctx, tenant_ctx

pytestmark = pytest.mark.django_db

UTC = ZoneInfo("UTC")


@pytest.fixture(autouse=True)
def wired(tmp_path, settings):
    """The deployment's own wiring — real store, real transport, EAGER.

    ⚠ **`config/settings/test.py` SETS `JOBS_EAGER = False` AND AN ENVIRONMENT
    VARIABLE DOES NOT OVERRIDE IT** — the base settings read the variable, the
    test settings then assign the constant unconditionally. Without this the
    accept path reaches for Celery and dies on
    `kombu.exceptions.OperationalError: Error 111 connecting to localhost:6379`,
    a traceback that names Redis and says nothing about the setting that sent
    it there. `test_cr142_p3_run_history.py` records the same measurement.
    """
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def _staff(actor, tenant):
    """Give `actor` a MEMBERSHIP of `tenant`, which is what makes them staff.

    ⚠ **`staff_actor` CREATES A `users` ROW AND NO MEMBERSHIP, AND THAT IS WHY
    THE FIRST RUN OF EVERY RECIPIENTS CASE FAILED.** `identity.selectors.
    user_list` — the read `BR-REP-020` is enforced through, and the one the
    Settings → Users screen uses — queries `TenantMembership`, not `User`. A
    user row with no membership is somebody who exists and holds no role here,
    and the product is right to leave them out: `P4.10` sends a LINK rather
    than a file precisely so *"recipients get a link that respects their
    permissions"*, and a person with no membership can sign in to nothing.

    ⚠ **SO THE FIXTURE IS FIXED AND THE READ IS NOT.** Making `tenant_staff`
    read `User` directly would have turned every case green while quietly
    widening a signed ruling to people who have no access — the shape
    CLAUDE.md names as a check that passes wrongly, and it is exactly what the
    brief warns about: *"a fixture that lacks something is a false pass — make
    fixtures create what they need."*
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


def _definition(tenant):
    """One report definition to hang a schedule on.

    The platform rows seeded by `reports/0003` are `tenant_id IS NULL`, and a
    schedule's FK is `PROTECT` against whichever row it names — so a case that
    reached for a seeded row would be asserting against data another lane may
    reseed. This makes its own.
    """
    return ReportDefinition.objects.create(
        tenant=tenant,
        key="ar-aging-scheduled-fixture",
        name="AR Ageing",
        dataset="invoices",
        group_code="finance",
    )


def _schedule(tenant, actor, *, cadence=CADENCE_DAILY, due=None, resource="ar_aging"):
    return ReportSchedule.objects.create(
        tenant=tenant,
        definition=_definition(tenant),
        cadence=cadence,
        params={"resource": resource, "q": "", "filters": {}},
        recipients=[str(actor.id)],
        next_run_at=due or (timezone.now() - timedelta(minutes=1)),
        enabled=True,
        created_by_user_id=actor.id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# `P4.2` — a schedule that fires twice produces ONE file
# ═══════════════════════════════════════════════════════════════════════════


def test_a_schedule_that_fires_twice_produces_one_file(brazos, dana):
    """The phase's own outcome sentence, asserted on the JOB ID.

    ⚠ **THE SAME ID, NOT A ROW COUNT.** A count of one would also be satisfied
    by a second call that raised — which is a schedule that silently stopped
    working, the opposite of what this test exists to prove.
    `core.jobs.enqueue` folds a duplicate scope key into the EXISTING record and
    returns it, so the same id coming back twice is the fold-in happening
    rather than an error being swallowed.

    ════════════════════════════════════════════════════════════════════════
    ⚠ THE DISPATCHER IS UNREGISTERED FOR THIS ONE CASE, AND THAT IS THE WHOLE
    REASON THE CASE IS HONEST — IT WAS RED ON THE FIRST RUN AND THIS IS WHY
    ════════════════════════════════════════════════════════════════════════
    `core.jobs.enqueue` folds only into an **ACTIVE** job:
    `_store.find_active(tenant, kind, scope_key)` looks for `queued` or
    `running`. Under the `wired` fixture above `JOBS_EAGER` is TRUE, so
    `_dispatcher(record)` runs the export in-process and the record is
    **succeeded before `enqueue` returns**. The second call therefore finds
    nothing active and correctly creates a second job.

    **MEASURED, not reasoned about: this case failed on its first run for
    exactly that reason** — two different ids, with the product behaving
    correctly. The first draft would have been "fixed" by asserting a row
    count, which the eager path satisfies trivially and which would have proved
    nothing about the constraint at all.

    So the dispatcher is cleared for the duration, which leaves the job
    `queued` — **and `queued` is not a contrivance, it is the production state
    the scope key exists for.** In production `JOBS_EAGER` is false and a job
    sits queued until a worker takes it; the race this key guards is two beat
    ticks, or two beat processes, reaching the same due instant while the first
    run has not finished. That is the only way one due instant is swept twice
    at all, because `fire()` advances `next_run_at` before it returns.
    """
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
        due_at = schedule.next_run_at
        previous_dispatcher = core_jobs._dispatcher
        core_jobs.set_job_dispatcher(None)
        try:
            first = schedules._enqueue(
                schedule, scope=schedules.scope_key(schedule.pk, due_at), actor=dana
            )
            second = schedules._enqueue(
                schedule, scope=schedules.scope_key(schedule.pk, due_at), actor=dana
            )
        finally:
            core_jobs.set_job_dispatcher(previous_dispatcher)
    assert first["status"] == "queued"
    assert first["id"] == second["id"]


def test_the_scope_key_carries_the_instant_and_not_only_the_schedule(brazos, dana):
    """October must not fold into September.

    A key of `report_schedule:{id}` alone would deduplicate ACROSS due dates, so
    a monthly schedule whose September run was still queued would silently lose
    October. The key is asserted here rather than only through behaviour because
    the behaviour needs a month of clock to show.
    """
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
    september = datetime(2026, 9, 1, 6, tzinfo=UTC)
    october = datetime(2026, 10, 1, 6, tzinfo=UTC)
    assert schedules.scope_key(schedule.pk, september) != schedules.scope_key(schedule.pk, october)
    assert str(schedule.pk) in schedules.scope_key(schedule.pk, september)


def test_a_sweep_fires_a_due_schedule_and_moves_its_next_run_on(brazos, dana):
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana, cadence=CADENCE_DAILY)
        before = schedule.next_run_at
        outcome = schedules.sweep()
        schedule.refresh_from_db()
    assert len(outcome["fired"]) == 1
    assert schedule.last_job_id is not None
    assert schedule.next_run_at > before
    assert schedule.next_run_at > timezone.now()


def test_a_paused_schedule_is_not_swept(brazos, dana):
    """Pause writes `enabled=false` and clears `next_run_at` (p41 ④)."""
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana)
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.save(update_fields=["enabled", "next_run_at"])
        outcome = schedules.sweep()
    assert outcome["fired"] == []


# ═══════════════════════════════════════════════════════════════════════════
# `P4.7` — four cadences, four correct dates
# ═══════════════════════════════════════════════════════════════════════════


def test_daily_fires_the_next_morning():
    """Friday 09:00 → Saturday 06:00. Worked by hand from `FIRE_AT_HOUR`."""
    friday = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    assert schedules.next_run_at(CADENCE_DAILY, after=friday, zone=UTC) == datetime(
        2026, 9, 26, 6, 0, tzinfo=UTC
    )


def test_daily_set_before_the_firing_hour_fires_the_same_morning():
    """02:00 on Friday → 06:00 THAT Friday, not Saturday.

    A person setting a daily schedule at two in the morning means today. The
    strictly-greater comparison in `next_run_at` is what makes this true and
    this case is what stops somebody "simplifying" it to `>=` on the date.
    """
    friday_small_hours = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)
    assert schedules.next_run_at(CADENCE_DAILY, after=friday_small_hours, zone=UTC) == datetime(
        2026, 9, 25, 6, 0, tzinfo=UTC
    )


def test_weekly_fires_the_same_weekday_a_week_on():
    """Friday 25 Sep → Friday 2 Oct, and 2 Oct IS a Friday."""
    friday = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    nxt = schedules.next_run_at(CADENCE_WEEKLY, after=friday, zone=UTC)
    assert nxt == datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
    assert nxt.weekday() == friday.weekday()


def test_monthly_clamps_into_a_short_month():
    """31 January → 28 February, never 3 March.

    ⚠ **THE CASE THAT CATCHES THE OBVIOUS BUG.** `+ timedelta(days=31)` is the
    reflex implementation of *monthly* and it drifts: January's run lands on 3
    March, March's on 3 April, and by June the month-end pack arrives in the
    middle of the month. 2027 is used because it is NOT a leap year, so the
    answer is the 28th and a leap-year off-by-one cannot hide here.
    """
    january = datetime(2027, 1, 31, 9, 0, tzinfo=UTC)
    assert schedules.next_run_at(CADENCE_MONTHLY, after=january, zone=UTC) == datetime(
        2027, 2, 28, 6, 0, tzinfo=UTC
    )


def test_monthly_on_cycle_close_is_not_a_cron_expression_and_uses_the_close_date(
    brazos, dana, monkeypatch
):
    """The fourth cadence, resolved through the ACCOUNTING period's close date.

    ⚠ **THE SEAM IS STUBBED AND THE ARITHMETIC IS NOT.** `current_period` is
    `apps.tenancy`'s and is ratified under `BR-TEN-022`; what this case owns is
    that `schedules` READS it and turns the answer into a firing instant at the
    right hour. Stubbing the seam is what keeps this a test of Phase 4 rather
    than a second test of the fiscal calendar.
    """
    monkeypatch.setattr(
        schedules.report_seams,
        "current_period",
        lambda **_kwargs: {"close_by": "2026-10-05"},
    )
    after = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    assert schedules.next_run_at(CADENCE_MONTHLY_ON_CYCLE_CLOSE, after=after, zone=UTC) == datetime(
        2026, 10, 5, 6, 0, tzinfo=UTC
    )


def test_monthly_on_cycle_close_refuses_rather_than_substituting_a_date(brazos, dana, monkeypatch):
    """No fiscal calendar → `None`, and NEVER the 1st of the month.

    ⚠ **THIS IS THE CASE THAT PROTECTS A RULING FROM A CONVENIENCE.** A
    substituted date would make the schedule look healthy and deliver a
    finance pack on a day nobody chose. `CR-029 D8①` withdrew the whole
    concept of deriving a cycle close ourselves; answering `None` is the same
    refusal one module along.
    """
    monkeypatch.setattr(schedules.report_seams, "current_period", lambda **_kwargs: None)
    after = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    assert schedules.next_run_at(CADENCE_MONTHLY_ON_CYCLE_CLOSE, after=after, zone=UTC) is None


def test_an_unknown_cadence_is_refused_by_name():
    """A fifth cadence is a migration (`P4.1`'s CHECK) AND a code branch.

    The CHECK constraint stops a fifth value reaching the table; this stops one
    reaching the arithmetic and silently returning whatever the last branch
    computed.
    """
    with pytest.raises(ValueError, match="unknown cadence"):
        schedules.next_run_at("fortnightly", after=timezone.now(), zone=UTC)


def test_a_missed_window_fires_once_and_never_catches_up(brazos, dana):
    """Three days dormant produces ONE run, not three.

    ⚠ **`advance()` LOOPS AND A ONE-STEP VERSION PASSES EVERY OTHER CASE IN
    THIS FILE.** That is what this case is for: it is the only one where the
    difference between *one step* and *walk to the future* is visible.
    """
    three_days_ago = timezone.now() - timedelta(days=3)
    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana, cadence=CADENCE_DAILY, due=three_days_ago)
        nxt = schedules.advance(schedule, now=timezone.now(), zone=UTC)
    assert nxt > timezone.now()
    assert nxt < timezone.now() + timedelta(days=2)


# ═══════════════════════════════════════════════════════════════════════════
# `P4.3` — recipients: internal staff only (`BR-REP-020`, RULED)
# ═══════════════════════════════════════════════════════════════════════════


def test_this_tenants_own_user_is_accepted(brazos, dana):
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        people = schedules.resolve_recipients(brazos.id, [str(dana.id)])
    assert len(people) == 1
    assert people[0].user_id == str(dana.id)
    assert people[0].name == dana.user.full_name


def test_another_tenants_user_is_refused_by_name(brazos, dana, lonestar, erin):
    _staff(dana, brazos)
    _staff(erin, lonestar)
    """A REAL user id, from a REAL other tenant — not a made-up uuid.

    ⚠ **A RANDOM UUID WOULD PROVE LESS.** Any lookup refuses a uuid that names
    nothing; the question `BR-REP-020` actually asks is whether a real person
    at another utility can be added, and only a real foreign id asks it.
    """
    with tenant_ctx(brazos):
        with pytest.raises(schedules.RecipientError) as refusal:
            schedules.resolve_recipients(brazos.id, [str(erin.id)])
    assert str(erin.id) in refusal.value.unknown


def test_an_email_address_is_refused(brazos, dana):
    """The ruling's own worked case: a free-text address cannot become a
    recipient, whatever a caller sends."""
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        with pytest.raises(schedules.RecipientError):
            schedules.resolve_recipients(brazos.id, ["auditor@example.com"])


def test_an_empty_recipient_list_is_refused(brazos, dana):
    _staff(dana, brazos)
    """A schedule with nobody on it produces a file and tells no one — which
    looks exactly like the product working."""
    with tenant_ctx(brazos):
        with pytest.raises(schedules.RecipientError):
            schedules.resolve_recipients(brazos.id, [])


def test_the_picker_offers_this_tenants_users_and_not_another_tenants(
    brazos, dana, marcus, lonestar, erin
):
    _staff(dana, brazos)
    _staff(marcus, brazos)
    _staff(erin, lonestar)
    with tenant_ctx(brazos):
        offered = {person.user_id for person in schedules.tenant_staff(brazos.id)}
    assert str(dana.id) in offered
    assert str(marcus.id) in offered
    assert str(erin.id) not in offered


# ═══════════════════════════════════════════════════════════════════════════
# `P4.8` — a failing schedule STAYS, marked failing
# ═══════════════════════════════════════════════════════════════════════════


def test_a_schedule_whose_report_errors_keeps_its_row_and_advances(brazos, dana):
    """*"…stays in the list marked failing and is not silently dropped"* (p40 ③).

    ⚠ **AND IT ADVANCES, WHICH IS THE HALF A READER WILL WANT TO ARGUE WITH.**
    A broken report that re-fires every minute until somebody notices is how a
    scheduler takes a product down. `4·1` marks the schedule failing from
    `last_job_id`; the utility fixes the report.

    ⚠ **THIS CASE ASSERTED `last_job_id is None` UNTIL `DEF-REP-6929` AND WAS
    WRONG ABOUT THE MECHANISM, NOT ABOUT THE OUTCOME.** An unregistered
    resource is not refused at ACCEPT time: `core.jobs.enqueue` takes the
    payload and only the HANDLER refuses it, so the schedule really does point
    at a job — a job that then FAILED. `fire()`'s `record is None` branch is
    the accept itself raising (a broker outage), which is a different event.

    ⚠ **AND `last_job_id is None` WOULD HAVE MEANT THE OPPOSITE OF WHAT THE
    DRAWING ASKS FOR.** `schedules_api.status_of` reads `_job(None)` as *we
    cannot say* and renders **On** — a green row over a report that has not
    run, hard-won law 2's mirror, which is what p40 ③ exists to prevent. What
    makes the screen say *Failing* is the row POINTING AT THE FAILED JOB, so
    that is what this case asserts.

    ⚠ **IT ASSERTS THE JOB'S STATUS AND NOT `status_of`, AND THE REASON IS A
    MEASUREMENT RATHER THAN A PREFERENCE.** `status_of` was asserted first and
    came back **`on`**, because `tenancy.selectors.report_run` resolves a job
    only when `payload.resource` is one of the reports module's own export
    resources — and this fixture's resource is deliberately not one. So
    `_job()` answers *we cannot say* for this synthetic row. **A real schedule
    always carries a resource from a real report definition**, so the screen is
    not wrong in the product; the FIXTURE cannot reach the screen's question.
    Asserting `status_of` here would have been a case that fails for a reason
    its own name does not mention. The `_job() is None -> on` behaviour itself
    is `DEF-REP-6929`, filed rather than fixed here.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        schedule = _schedule(brazos, dana, resource="a-resource-that-is-not-registered")
        before = schedule.next_run_at
        schedules.sweep()
        schedule.refresh_from_db()
        assert ReportSchedule.objects.filter(pk=schedule.pk).exists()
        assert schedule.enabled is True
        assert schedule.next_run_at > before
        # The row the screen reads its word from, and it says the run FAILED.
        assert schedule.last_job_id is not None
        job = tenancy_models.Job.objects.get(pk=schedule.last_job_id)
        assert job.status == "failed", job.status


# ═══════════════════════════════════════════════════════════════════════════
# WIRING — built is not wired (hard-won law 2)
# ═══════════════════════════════════════════════════════════════════════════


def test_the_beat_entry_names_a_task_and_a_tick():
    """*The schedule is correct* and *the schedule is installed* are two claims.

    This asserts the first without a broker. The second is asserted by
    `test_the_sweep_task_is_installed_on_the_app` below, against a stub app —
    because `install()` returning `{"installed": False}` on a machine with no
    celery is the honest answer and must not read as a pass.
    """
    entry = schedules.beat_schedule()
    assert schedules.BEAT_ENTRY in entry
    assert entry[schedules.BEAT_ENTRY]["task"] == schedules.SWEEP_TASK
    assert entry[schedules.BEAT_ENTRY]["schedule"] == float(schedules.SWEEP_EVERY_SECONDS)


def test_the_sweep_task_is_installed_on_the_app():
    """`install()` actually registers the task and the entry.

    ⚠ **A STUB APP, NOT THE REAL ONE.** Calling `install()` with no argument
    imports `config.celery`, which builds a Celery app and — on a machine with
    no broker — succeeds anyway, so the case would pass without proving the
    registration happened. A stub makes the registration observable.
    """

    class _StubApp:
        def __init__(self):
            self.conf = type("Conf", (), {"beat_schedule": {}})()
            self.registered = []

        def task(self, name, bind=False):
            def decorate(fn):
                self.registered.append(name)
                return fn

            return decorate

    app = _StubApp()
    outcome = schedules.install(app)
    assert outcome["installed"] is True
    assert schedules.SWEEP_TASK in app.registered
    assert schedules.BEAT_ENTRY in app.conf.beat_schedule


def test_a_scheduled_run_uses_the_kind_the_history_screen_reads():
    """⚠ **THE ONE-LINE CASE THAT STOPS A WHOLE CLASS OF INVISIBLE WORK.**

    `run_history.RUN_KINDS` is what screen `5·1` filters by. A schedule that
    enqueued its own kind would produce real files that never appear in the run
    history — live work behind a list that cannot see it. Asserted against
    `run_history`'s own tuple rather than against a literal, so a rename in
    either place goes red here instead of going quiet on screen.
    """
    from apps.reports import run_history

    assert schedules.SCHEDULE_JOB_KIND in run_history.RUN_KINDS
