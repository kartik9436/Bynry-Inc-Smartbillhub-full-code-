# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-007 (EP-RBS-03) — CR-075 wave I tasks I1, I2, I3 and I7.
#           Screens: RBS-004 Overview (the next-run line) · RBS-008.
# Rules:    BR-RBS-016 (a schedule is evaluated in the TENANT's timezone, and a
#           missed firing RAISES rather than silently catching up) ·
#           BR-INT-062 (a wall time that occurs twice runs ONCE — late is a
#           delay, twice is a duplicate) · BR-RBS-004 (an Action produces a plan
#           first) · BR-RBS-041 (permission up front is the one switch that
#           removes the wait) · BR-INT-054 as amended (one scheduler) ·
#           CLAUDE.md hard rule 1 · hard-won law 7
# Tests:    this file, on SQLite. The PostgreSQL half — two tenants under RLS
#           FORCE, and the enqueue surviving a poisoned transaction — is
#           06-backend/tests/test_us_rbs_007_scheduler_pg.py, which SKIPS here
#           rather than passing vacuously (hard-won law 14).
# Impacts:  apps/runbooks/scheduler.py · apps/runbooks/apps.py · services.py ·
#           seams/tenancy_seam.py · docker-compose.yml · 10-scripts/gates/
#           g117_runbooks_queue_split.py
# ───────────────────────────────────────────────────────
"""US-RBS-007 — the clock, the tenant's own clock, and the firing that did not happen.

**TC-RBS-007.1** a runbook set to Daily 06:00 `America/Chicago` fires at 06:00
Chicago and not at 06:00 UTC · **TC-RBS-007.2** the runner is down across a
firing and run history reads **Failed**, naming the missed time, once ·
**TC-RBS-007.3** two tenants, two zones, one runbook key, two different instants
· **TC-RBS-007.4** the two daylight-saving cases · **TC-RBS-22** scope is
resolved once.

⚠ **EVERY CLOCK ASSERTION HERE IS MADE ON THE TENANT'S WALL CLOCK AND NOT ON
UTC, AND THAT IS THE WHOLE POINT OF THE FILE.** `DEF-MET-4101` was a clock
question answered in the wrong frame: every check compared UTC while the product
showed local, so the two agreed with each other for months and neither agreed
with the customer. A test that asserted *"the sweep enqueued something"* would
pass on a scheduler that fires six hours early.

⚠ **AND THE MISSED-FIRING CASES ARE WRITTEN AS *HOW MANY ROWS*, NOT AS *A ROW
EXISTS*.** `BR-RBS-016` forbids two opposite failures — a silent skip and six
replays — so a case that only asserted a Failed row appeared would pass on a
scheduler that wrote one every minute for ever.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest

from apps.runbooks import models, scheduler, services
from apps.runbooks.contract import MODE_SET, Block, RunbookDefinition, Step, SubjectRef
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CHICAGO = "America/Chicago"
NEW_YORK = "America/New_York"


def _utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=dt_timezone.utc)


def _runbook(tenant, **overrides) -> models.Runbook:
    fields = dict(
        key="sweep",
        name="Pre-bill sweep",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="account",
        template_key="sweep",
        enabled=True,
        trigger_kind=models.TRIGGER_SCHEDULE,
        cron="0 6 * * *",
        timezone=CHICAGO,
        cap=100,
        current_version=1,
        trusted_version=1,
    )
    fields.update(overrides)
    return models.Runbook.objects.create(tenant=tenant, **fields)


# ═══════════════════════════════════════════════════════════════════════════
# TC-RBS-007.1 — the tenant's own clock, and it is a DIFFERENT INSTANT in
# January than in July for the same words on the screen.
# ═══════════════════════════════════════════════════════════════════════════


def test_daily_six_fires_at_six_chicago_not_at_six_utc():
    spec = scheduler.parse_cron("0 6 * * *")
    tz = scheduler.zone(CHICAGO)

    winter = scheduler.next_fire_after(spec, tz, _utc(2026, 1, 1))
    summer = scheduler.next_fire_after(spec, tz, _utc(2026, 7, 1))

    # The wall clock is the same in both. That is what the clerk set.
    assert winter.astimezone(tz).strftime("%H:%M") == "06:00"
    assert summer.astimezone(tz).strftime("%H:%M") == "06:00"
    # The INSTANT is not, and a UTC-only scheduler would have them equal.
    assert winter.hour == 12, "06:00 CST is 12:00 UTC"
    assert summer.hour == 11, "06:00 CDT is 11:00 UTC"
    assert winter.hour != summer.hour, (
        "the two would be identical on a scheduler that evaluates cron in UTC — "
        "which is DEF-MET-4101's shape, a clock question answered in the wrong frame"
    )


def test_a_cron_that_names_no_reachable_date_answers_none_rather_than_guessing():
    spec = scheduler.parse_cron("0 6 30 2 *")  # six o'clock on 30 February
    assert scheduler.next_fire_after(spec, scheduler.zone(CHICAGO), _utc(2026, 1, 1)) is None


@pytest.mark.parametrize(
    "bad",
    ["0 6 * *", "0 6 * * MON", "70 6 * * *", "0 6 * * 9", "0 6 * * *  extra field", ""],
)
def test_a_cron_a_clerk_typed_wrong_is_refused_at_save(bad):
    """`US-RBS-007` field table: *cron valid or refused at save*.

    ⚠ Refused HERE or refused NEVER. Until 2026-09-07 `cron` was stored as any
    non-empty string, which was harmless while nothing read it and becomes a
    schedule that silently never fires the moment something does.
    """
    with pytest.raises(errors.ValidationError):
        services._validated_setting("cron", bad)


def test_a_timezone_zoneinfo_does_not_know_is_refused_rather_than_defaulted_to_utc():
    with pytest.raises(errors.ValidationError):
        services._validated_setting("timezone", "America/Notaplace")
    assert services._validated_setting("timezone", CHICAGO) == CHICAGO


# ═══════════════════════════════════════════════════════════════════════════
# TC-RBS-007.4 — the two daylight-saving cases. One is BR-INT-062's; the other
# is this lane's judgment, recorded in the decision log of 2026-09-07.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_clock_goes_back_and_the_runbook_runs_once():
    """`BR-INT-062` — *late is a delay, twice is a duplicate*.

    01:30 on 1 November 2026 happens TWICE in Chicago. A scheduler that walked
    instants would fire twice; this one walks the WALL CLOCK, so 01:30 appears
    once in the day whatever the offsets do.
    """
    spec = scheduler.parse_cron("30 1 * * *")
    tz = scheduler.zone(CHICAGO)
    fires = scheduler.fires_between(
        spec, tz, after=_utc(2026, 11, 1, 0, 0), until=_utc(2026, 11, 2, 0, 0)
    )
    assert len(fires) == 1, f"one firing, not {len(fires)} — twice is a duplicate"
    assert fires[0].astimezone(tz).strftime("%H:%M %Z") == "01:30 CDT", (
        "the FIRST of the two occurrences (fold=0)"
    )


def test_the_clock_goes_forward_and_the_runbook_fires_late_rather_than_not_at_all():
    """02:30 on 8 March 2026 never happens in Chicago. It still runs.

    ⚠ **THIS IS A JUDGMENT THIS LANE MADE AND WROTE DOWN**, not a rule it read:
    `EP-RBS-03` §8 records the case as unruled and as ours rather than the
    Product Owner's. The alternative was to skip the day, and a silent skip is
    the exact failure this wave exists to prevent — an absence no check in this
    repository can see. The decision and its reasoning are in
    `12-governance/02-decision-log.md`, 2026-09-07.
    """
    tz = scheduler.zone(CHICAGO)
    assert not scheduler.local_wall_time_exists(datetime(2026, 3, 8, 2, 30), tz), (
        "the fixture is only meaningful if 02:30 really is inside the gap"
    )
    spec = scheduler.parse_cron("30 2 * * *")
    fires = scheduler.fires_between(
        spec, tz, after=_utc(2026, 3, 8, 0, 0), until=_utc(2026, 3, 9, 0, 0)
    )
    assert len(fires) == 1, "it fires — once — rather than being skipped"
    assert fires[0].astimezone(tz).strftime("%H:%M %Z") == "03:30 CDT", (
        "an hour late on the new clock, which is a fact a clerk can read on RBS-008"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-RBS-007.3 — two tenants, two zones, one runbook key.
# ═══════════════════════════════════════════════════════════════════════════


def test_two_tenants_in_two_zones_fire_at_two_different_instants(brazos, lonestar):
    with tenant_ctx(brazos):
        texas = _runbook(brazos, timezone=CHICAGO)
    with tenant_ctx(lonestar):
        east = _runbook(lonestar, timezone=NEW_YORK)

    at = _utc(2026, 1, 1)
    texas_next = scheduler.next_run_at(texas, now=at)
    east_next = scheduler.next_run_at(east, now=at)

    assert texas_next.hour == 12 and east_next.hour == 11
    assert texas_next != east_next, (
        "a single global beat entry would give both utilities the same instant, "
        "which is the shape TC-RBS-007.3 exists to refuse"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-RBS-007.2 — the runner is down across a firing.
# ═══════════════════════════════════════════════════════════════════════════


def test_a_missed_firing_is_visible_as_failed_and_names_the_missed_time(brazos):
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        # ⚠ **`created_at` IS THE ANCHOR AND THE FIXTURE HAS TO SAY SO.** The
        # first draft of this case set it to 1 January and asserted ONE missed
        # firing; the scheduler correctly found FIVE, because a schedule that
        # has existed since the 1st has been missed every morning since. Set it
        # to midnight on the 5th and exactly one 06:00 has gone by.
        models.Runbook.objects.filter(pk=runbook.pk).update(
            created_at=_utc(2026, 1, 5, 0, 0)
        )
        runbook.refresh_from_db()

        # 08:00 Chicago on 5 January — two hours after a 06:00 firing nobody ran.
        now = _utc(2026, 1, 5, 14, 0)
        verdict = scheduler.decide(runbook, now=now)
        assert verdict.due is None, "two hours late is not 'due', it is missed"
        assert len(verdict.missed) == 1

        scheduler.raise_missed(runbook, verdict)
        row = models.RunbookRun.objects.get(runbook=runbook)

    assert row.status == models.RUN_STATUS_FAILED
    assert row.started_at == _utc(2026, 1, 5, 12, 0), "the MISSED time, not the sweep's time"
    text = row.report[0]["payload"]["text"]
    assert "5 Jan 2026 at 06:00 CST" in text, f"the tenant's clock, with its zone named: {text}"
    assert "RBS" not in text and "BR-" not in text, "B14 rule 32 — no internal code in clerk copy"


def test_the_same_missed_window_never_raises_twice(brazos):
    """*Never a silent catch-up and never six replays* — the second half.

    A test asserting only that a Failed row appeared would pass on a scheduler
    that wrote one every single minute for ever.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.Runbook.objects.filter(pk=runbook.pk).update(created_at=_utc(2026, 1, 5))
        runbook.refresh_from_db()
        now = _utc(2026, 1, 5, 14, 0)

        first = scheduler.decide(runbook, now=now)
        scheduler.raise_missed(runbook, first)

        second = scheduler.decide(runbook, now=now)
        assert second.missed == (), (
            "the failed row's started_at IS the anchor advance; a second sweep in the "
            "same minute must find nothing left to raise"
        )
        assert models.RunbookRun.objects.filter(runbook=runbook).count() == 1


def test_ten_missed_days_are_one_row_that_says_ten(brazos):
    """*"the sweep did not run for ten days"* is the fact, and it is one line.

    ⚠ **THE COUNT IS AN INCLUSIVE ONE AND THE FIRST DRAFT OF THIS CASE GOT IT
    WRONG BY ONE** — it said *1 to 9 January* over an anchor of midnight on the
    1st and a clock of 08:00 on the 10th, which is TEN 06:00s. The scheduler was
    right and the fixture was wrong, which is worth leaving written down: an
    off-by-one in a missed-firing count is a sentence a clerk would read and
    believe.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.Runbook.objects.filter(pk=runbook.pk).update(created_at=_utc(2026, 1, 1, 0, 0))
        runbook.refresh_from_db()

        now = _utc(2026, 1, 10, 14, 0)  # 08:00 Chicago on the 10th
        verdict = scheduler.decide(runbook, now=now)
        assert len(verdict.missed) == 10, "1 to 10 January inclusive"

        scheduler.raise_missed(runbook, verdict)
        row = models.RunbookRun.objects.get(runbook=runbook)

    assert models.RunbookRun.objects.count() == 1, "ONE row for the window, not ten"
    assert row.counts == {"missed": 10}
    text = row.report[0]["payload"]["text"]
    assert "10 times" in text and "1 Jan 2026 at 06:00" in text and "10 Jan 2026 at 06:00" in text


def test_the_lookback_is_bounded_and_the_sentence_says_at_least(brazos, monkeypatch):
    """Law 7 — a check that cannot cover its whole subject prints what it skipped."""
    monkeypatch.setattr(scheduler, "MISS_LIMIT", 3)
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.Runbook.objects.filter(pk=runbook.pk).update(created_at=_utc(2026, 1, 1, 0, 0))
        runbook.refresh_from_db()
        verdict = scheduler.decide(runbook, now=_utc(2026, 1, 10, 14, 0))
        assert verdict.truncated is True
        scheduler.raise_missed(runbook, verdict)
        text = models.RunbookRun.objects.get(runbook=runbook).report[0]["payload"]["text"]
    assert "at least 3 times" in text, (
        f"a cap reported as a count is a number that is quietly a lie: {text}"
    )


def test_changing_the_schedule_forgets_the_firings_of_the_schedule_it_replaced(brazos):
    """A utility that moves *daily 06:00* to *weekly Monday* has missed nothing.

    The anchor reads `runbook_versions.summary`, which already records the
    fields an edit moved and is append-only.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.Runbook.objects.filter(pk=runbook.pk).update(created_at=_utc(2026, 1, 1, 0, 0))
        runbook.refresh_from_db()
        version = models.RunbookVersion.objects.create(
            tenant=brazos,
            runbook=runbook,
            version=2,
            definition={},
            summary=[{"field": "cron", "from": "0 6 * * *", "to": "0 6 * * 1"}],
        )
        models.RunbookVersion.objects.filter(pk=version.pk).update(
            changed_at=_utc(2026, 1, 9, 12, 0)
        )
        anchor = scheduler.schedule_anchor(runbook, now=_utc(2026, 1, 10, 14, 0))
    assert anchor == _utc(2026, 1, 9, 12, 0)


def test_a_cap_change_is_not_a_schedule_change(brazos):
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.Runbook.objects.filter(pk=runbook.pk).update(created_at=_utc(2026, 1, 8, 0, 0))
        runbook.refresh_from_db()
        version = models.RunbookVersion.objects.create(
            tenant=brazos,
            runbook=runbook,
            version=2,
            definition={},
            summary=[{"field": "cap", "from": 100, "to": 400}],
        )
        models.RunbookVersion.objects.filter(pk=version.pk).update(
            changed_at=_utc(2026, 1, 9, 12, 0)
        )
        anchor = scheduler.schedule_anchor(runbook, now=_utc(2026, 1, 10, 14, 0))
    assert anchor == _utc(2026, 1, 8, 0, 0), "raising a cap does not move the clock"


# ═══════════════════════════════════════════════════════════════════════════
# THE SWEEP ITSELF — what it enqueues, and on which kind
# ═══════════════════════════════════════════════════════════════════════════


def test_a_due_check_is_enqueued_on_the_check_kind_and_a_due_action_on_the_act_kind(brazos):
    with tenant_ctx(brazos):
        check = _runbook(brazos, key="sweep", kind=models.KIND_CHECK)
        action = _runbook(brazos, key="ladder", kind=models.KIND_ACTION)
        for row in (check, action):
            models.Runbook.objects.filter(pk=row.pk).update(created_at=_utc(2026, 1, 5, 0, 0))

        now = _utc(2026, 1, 5, 12, 1)  # one minute after 06:00 Chicago
        kinds = {}
        for row in models.Runbook.objects.all():
            verdict = scheduler.decide(row, now=now)
            assert verdict.due == _utc(2026, 1, 5, 12, 0)
            kinds[row.key] = scheduler._kind_for(row)

    assert kinds == {"sweep": "runbooks.check", "ladder": "runbooks.act"}


def test_a_scheduled_action_runs_dry_unless_permission_was_given_up_front(brazos):
    """`BR-RBS-004` and `BR-RBS-041` — the switch removes the WAIT, never the plan."""
    with tenant_ctx(brazos):
        held = _runbook(brazos, key="ladder", kind=models.KIND_ACTION)
        permitted = _runbook(
            brazos,
            key="ladder2",
            kind=models.KIND_ACTION,
            gate_mode=models.GATE_APPROVED_UP_FRONT,
        )
        a_check = _runbook(brazos, key="sweep", kind=models.KIND_CHECK)
        assert scheduler._mode_for(held) == models.MODE_DRY
        assert scheduler._mode_for(permitted) == models.MODE_LIVE
        assert scheduler._mode_for(a_check) == models.MODE_DRY


def test_a_disabled_or_manual_runbook_has_no_next_run_and_the_screen_draws_the_absence(brazos):
    with tenant_ctx(brazos):
        assert scheduler.next_run_at(_runbook(brazos, key="a", enabled=False)) is None
        assert (
            scheduler.next_run_at(
                _runbook(brazos, key="b", trigger_kind=models.TRIGGER_MANUAL)
            )
            is None
        )
        assert scheduler.next_run_at(_runbook(brazos, key="c", cron=None)) is None


def test_two_sweeps_inside_the_grace_window_fold_into_one_job(brazos):
    """`scope_key` carries the FIRING, so a beat that ticks twice is one job."""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        fired_for = _utc(2026, 1, 5, 12, 0)
        first = scheduler.scope_key(runbook.tenant_id, runbook.key, fired_for)
        again = scheduler.scope_key(runbook.tenant_id, runbook.key, fired_for)
        tomorrow = scheduler.scope_key(
            runbook.tenant_id, runbook.key, fired_for + timedelta(days=1)
        )
    assert first == again
    assert first != tomorrow, "tomorrow's 06:00 is different work"


# ═══════════════════════════════════════════════════════════════════════════
# I1 — THE TWO JOB KINDS ARE REGISTERED, AND ON A QUEUE
# ═══════════════════════════════════════════════════════════════════════════


def test_both_job_kinds_have_a_body_and_a_queue():
    """`DEF-RBS-4353` — the plan said this was done and nothing implemented it.

    A kind with a queue and no body is a message a worker cannot run; a kind
    with a body and no queue rides the shared queue, so a ten-minute sweep sits
    in front of whatever a clerk is waiting for.
    """
    from core import jobs as core_jobs

    for kind in scheduler.JOB_KINDS:
        assert core_jobs.job_handler(kind) is not None, f"{kind} has no body"
        assert core_jobs.job_queue(kind) == scheduler.RUNBOOKS_QUEUE, f"{kind} is not routed"


def test_the_job_body_leaves_the_tenant_context_it_was_given(brazos):
    """`DEF-RBS-4363` — and the assertion is chosen so SQLite can fail it.

    `core.jobs.run_job` enters `tenant_context(record["tenant_id"])` before it
    calls the body and then calls `succeed(job_id)` → `_load(job_id)` after it
    returns. `core.tenancy.tenant_context` **clears on exit rather than
    restoring**, so a body that opens a nested one leaves no tenant set and that
    `_load` reads the RLS-FORCEd `jobs` table and finds nothing: *unknown job*.
    The RUN is written correctly either way, so only the JOB record says failed.

    ⚠ **THE OBVIOUS TEST — *run the job and assert it succeeded* — CANNOT FAIL
    HERE.** `config/settings/test.py` hardcodes SQLite, which has no row-level
    security, so the missing tenant reads every row and the job succeeds on the
    broken build (hard-won law 14, one layer up). So this asserts the INVARIANT
    instead: the context this function was handed is still set when it returns.
    That is false on every vendor.
    """
    from apps.runbooks import scheduler as sched
    from core import tenancy as core_tenancy

    with tenant_ctx(brazos):
        runbook = _runbook(brazos, key="ghost")
        before = core_tenancy.current_tenant_id()
        # A runbook key nothing matches takes the earliest return, which is the
        # branch a nested `with` would still have wrapped.
        sched.run_scheduled_job(
            {"tenant_id": str(brazos.id), "payload": {"runbook_key": "not-a-runbook"}}
        )
        assert core_tenancy.current_tenant_id() == before, (
            "the body cleared the context `run_job` set, so `succeed(job_id)` reads "
            "the RLS-FORCEd jobs table with no tenant and raises 'unknown job'"
        )
        assert runbook.key == "ghost"


def test_the_beat_entry_is_installed_and_not_merely_declared():
    """Hard-won law 2 with a clock in it: a correct dict nobody hands to celery."""
    entry = scheduler.beat_schedule()[scheduler.BEAT_ENTRY]
    assert entry["task"] == scheduler.SWEEP_TASK
    assert entry["schedule"] == float(scheduler.SWEEP_EVERY_SECONDS)

    from config.celery import app

    installed = dict(getattr(app.conf, "beat_schedule", None) or {})
    assert scheduler.BEAT_ENTRY in installed, (
        "RunbooksConfig.ready() must call scheduler.install() — a beat entry that is "
        "declared and never installed fires for nobody and every screen goes on "
        "drawing a next-run time"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-007 (EP-RBS-03 §3 test cases, verbatim) · CR-075 wave I tasks I1, I2, I3, I7 · BR-RBS-016 · BR-INT-062
# generated: 2026-09-07 by the CR-075 wave I build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a(the screen's own cases are in 07-frontend) F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_007_scheduler.py · pytest tests/test_us_rbs_007_scheduler_pg.py · G117
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
