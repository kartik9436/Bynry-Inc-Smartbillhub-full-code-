# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 task `P2.11`, the half that was REPORTED and not done
#          (`DEF-PAY-6268`) — the unclosed-till notice now fires on a schedule.
# Rules:   PO ruling 2026-09-23 §3.1 (no auto-close; the notice TELLS) ·
#          BR-TEN-081 (the utility's own clock) · BR-TEN-043 (beat owns a
#          duration; the day is an input) · BR-NOT-009 (quiet hours are the
#          dispatcher's, not a scheduler's) · CLAUDE.md hard rule 1 · rule 6 ·
#          hard-won law 2 (built is not wired) · law 3 · law 7
# ───────────────────────────────────────────────────────
"""The counter watch has a schedule, and the schedule is INSTALLED.

WHAT THIS FILE IS FOR, AND WHY ONE CASE IN IT MATTERS MORE THAN THE REST
------------------------------------------------------------------------
`P2.11` landed on 2026-09-23 complete and correct: a sweep that finds the tills
nobody closed, a seam that tells every System Admin, a command that runs it, an
event on Settings → Notifications, eleven locale catalogues, twenty-one cases.
**Nothing called any of it.** A supervisor was told if, and only if, a person
typed `manage.py sweep_open_counters`, so the cost the PO accepted in §3.1 — a
clerk who cannot take money until somebody seals yesterday's till — had no upper
bound at all.

So the case that matters is
`test_the_entry_is_installed_on_the_live_celery_app`, and what makes it the one
that matters is WHERE IT LOOKS. Asserting that `beat_schedule()` returns the
right dictionary proves the schedule is CORRECT and says nothing about whether
anything installs it — which is precisely the gap that existed, and hard-won
law 2 in one sentence. That case reads `config.celery.app.conf.beat_schedule`:
the object beat itself reads.

    RED PROOF (law 7): with `counter_watch_schedule.install()` deleted from
    `PaymentsConfig.ready()`, that case reads

        AssertionError: celery beat has no counter-watch entry …
        assert 'payments.counter_watch' in {'customers.cut_date_watch': …,
               'notifications.dispatch': …, 'payments.collections_ladder': …,
               'runbooks.schedule_sweep': …, 'work.rules_sweep': …}

    while `test_the_entry_is_data_and_names_the_fanout` below stays green,
    which is the two claims coming apart exactly as law 2 says they do.

WHAT WOULD MAKE THESE CASES PASS WRONGLY
-----------------------------------------
  1. **A sweep that entered no tenant.** *"0 counters left open"* is what a
     query with no `app.tenant_id` reports, truthfully, about nothing (hard
     rule 1). Every case that expects a finding drives a REAL open till through
     and reads the number that reaches the seam.
  2. **An hour test that passes because nothing ran.** `not_the_hour` and
     `ran: True` are asserted as a PAIR at one server instant, so a case cannot
     be satisfied by a sweep that silently did nothing for another reason.
  3. **A "no write" claim proved by behaviour.** A branch this file does not
     exercise could still write. The absence is therefore asserted from the
     SOURCE of both modules, which is the only thing that can see it.
"""

from __future__ import annotations

import datetime as dt
import pathlib
from zoneinfo import ZoneInfo

import pytest

from apps.payments import counter_watch
from apps.payments import counter_watch_schedule as schedule
from apps.payments import counter_session_models as tills
from apps.payments import run_alert_seam

from tests.test_cr136_p2_10_11_wire import MONDAY_0855, an_open_till
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

#: BR-TEN-043 — every moment here is NAMED. Nothing below reads a clock.
TUESDAY = dt.date(2026, 9, 22)
CHICAGO = ZoneInfo("America/Chicago")
HONOLULU = ZoneInfo("Pacific/Honolulu")

#: ONE instant on ONE server. In Chicago it is 06:02 and the watch fires; in
#: Honolulu it is 01:02 and it does not. That pair IS the multi-zone answer.
ELEVEN_UTC = dt.datetime(2026, 9, 22, 11, 2, tzinfo=dt.UTC)
#: Five hours later: now Honolulu is at 06:02 and Chicago is at 11:02.
SIXTEEN_UTC = dt.datetime(2026, 9, 22, 16, 2, tzinfo=dt.UTC)


def _pin(monkeypatch, *, instant: dt.datetime, zone: ZoneInfo, day: dt.date = TUESDAY):
    """Pin the utility's clock, its zone and its business day.

    The instant is converted INTO the zone exactly as `_tenant_moment` does, so
    the only thing these cases vary is which zone the utility is on — which is
    the fact under test. Nothing is frozen globally.
    """
    monkeypatch.setattr(schedule, "_tenant_moment", lambda z: instant.astimezone(z))
    monkeypatch.setattr("apps.payments.settings_seam.tenant_timezone", lambda: zone)
    monkeypatch.setattr("apps.tenancy.selectors.tenant_today", lambda: day)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ONE THAT MATTERS — the entry is INSTALLED, not merely declared
# ══════════════════════════════════════════════════════════════════════════
def test_the_entry_is_installed_on_the_live_celery_app():
    """**Hard-won law 2, asserted on the object beat actually reads.**

    `PaymentsConfig.ready()` runs on every process that could be beat. Without
    its `counter_watch_schedule.install()` line the entry is a dict nobody
    hands to celery — which is what `DEF-PAY-6268` was, with every other check
    in this repository green over it.
    """
    from config.celery import app

    installed = dict(getattr(app.conf, "beat_schedule", None) or {})
    assert schedule.BEAT_ENTRY in installed, (
        "celery beat has no counter-watch entry, so nobody is told about a counter "
        "left open unless a person types a command — and under PO ruling 2026-09-23 "
        f"§3.1 that clerk cannot take money until somebody does. Installed: {installed}"
    )
    assert installed[schedule.BEAT_ENTRY]["task"] == schedule.FANOUT_TASK
    assert app.tasks.get(schedule.FANOUT_TASK) is not None, (
        "beat would publish a message no worker consumes, and the broker reports "
        "that as success."
    )
    assert app.tasks.get(schedule.WATCH_TASK) is not None


def test_no_other_module_claims_this_beat_key():
    """Every installer does `existing.update(schedule)`, so a shared key is one
    schedule silently erasing another. `G132` enforces this across the repo;
    this is the same claim from inside the running app."""
    from config.celery import app

    installed = dict(getattr(app.conf, "beat_schedule", None) or {})
    assert installed[schedule.BEAT_ENTRY]["task"] == schedule.FANOUT_TASK
    assert schedule.BEAT_ENTRY == "payments.counter_watch"
    assert schedule.BEAT_ENTRY != "payments.collections_ladder"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE ENTRY AS DATA, AND THE CONFIGURATION AROUND IT
# ══════════════════════════════════════════════════════════════════════════
def test_the_entry_is_data_and_names_the_fanout():
    """No clock, no broker, no side effect — and, on its own, no proof of
    anything. It is the case above that says the entry reached celery."""
    entry = schedule.beat_schedule(every_seconds=900)
    assert set(entry) == {schedule.BEAT_ENTRY}
    assert entry[schedule.BEAT_ENTRY]["task"] == schedule.FANOUT_TASK
    assert entry[schedule.BEAT_ENTRY]["schedule"] == 900.0


def test_a_nonsense_interval_is_ignored_rather_than_obeyed(monkeypatch):
    """`0` would be beat firing continuously, which is a loop and not a
    schedule. It falls back to the default and logs."""
    monkeypatch.setenv(schedule.SWEEP_EVERY_SECONDS_ENV, "0")
    assert schedule.sweep_every_seconds() == schedule.DEFAULT_SWEEP_EVERY_SECONDS
    monkeypatch.setenv(schedule.SWEEP_EVERY_SECONDS_ENV, "not-a-number")
    assert schedule.sweep_every_seconds() == schedule.DEFAULT_SWEEP_EVERY_SECONDS
    monkeypatch.setenv(schedule.SWEEP_EVERY_SECONDS_ENV, "300")
    assert schedule.sweep_every_seconds() == 300


def test_a_nonsense_hour_falls_back_instead_of_switching_the_watch_off(monkeypatch):
    """The direction of the damage decides this one.

    `collections_schedule.schedule_hour` RAISES on an unreadable hour, because
    running a ladder at an hour nobody chose posts certified disconnection
    notices. Here a typo in an environment file must not silently switch off the
    only thing telling a supervisor about a locked-out clerk, so it falls back
    with a log line.
    """
    monkeypatch.setenv(schedule.WATCH_HOUR_ENV, "25")
    assert schedule.watch_hour() == schedule.DEFAULT_WATCH_HOUR
    monkeypatch.setenv(schedule.WATCH_HOUR_ENV, "breakfast")
    assert schedule.watch_hour() == schedule.DEFAULT_WATCH_HOUR
    monkeypatch.setenv(schedule.WATCH_HOUR_ENV, "5")
    assert schedule.watch_hour() == 5


class _StubApp:
    """A celery app with the two surfaces `install()` touches, and nothing else."""

    def __init__(self):
        self.conf = type("Conf", (), {"beat_schedule": {}})()
        self.registered = {}

    def task(self, *, name, bind=False):
        def wrap(fn):
            self.registered[name] = fn
            return fn

        return wrap


def test_install_registers_both_tasks_and_replaces_rather_than_duplicates():
    """Two entries would be two sweeps per interval. The task OBJECTS are
    asserted for `install()`'s own stated reason: a fan-out that kept the plain
    function would run every utility's sweep inline inside beat's process."""
    app = _StubApp()
    result = schedule.install(app)
    assert result["installed"] is True
    assert schedule.BEAT_ENTRY in app.conf.beat_schedule
    assert schedule.WATCH_TASK in app.registered
    assert schedule.FANOUT_TASK in app.registered
    schedule.install(app)
    assert len(app.conf.beat_schedule) == 1


def test_a_deployment_without_celery_starts_anyway(monkeypatch):
    """A Django app that refused to boot because a scheduler is absent would be
    a worse product than one whose notice goes out when the worker returns."""
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "config.celery":
            raise ImportError("no celery here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    result = schedule.install()
    assert result["installed"] is False
    assert "celery" in result["reason"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BANKING DAY IS NOT THE SERVER'S — TWO UTILITIES, ONE INSTANT
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_two_utilities_in_different_zones_each_fire_at_their_own_six(
    brazos, lonestar, dana, marcus, monkeypatch
):
    """**The multi-zone answer, as a pair of opposite results at ONE instant.**

    A celery-beat entry has one schedule for the whole deployment, so the
    per-utility decision has to be made in the app (BR-TEN-043). At 11:02 UTC a
    utility on Chicago time is at 06:02 and is told; the same code at the same
    instant for a utility on Honolulu time is at 01:02 and says `not_the_hour`
    and names when it will run. Five hours later the answers swap.

    ⚠ The two are asserted TOGETHER. A case that only checked the refusal would
    be satisfied by a watch that never runs for anybody.
    """
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)

    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    chicago = schedule.watch_one(brazos.subdomain)
    assert chicago["ran"] is True, chicago
    assert chicago["as_of"] == TUESDAY.isoformat()
    assert chicago["tills_left_open"] == 1

    _pin(monkeypatch, instant=ELEVEN_UTC, zone=HONOLULU)
    honolulu = schedule.watch_one(lonestar.subdomain)
    assert honolulu["ran"] is False
    assert honolulu["reason"] == "not_the_hour"
    assert honolulu["next_run_at"].startswith("2026-09-22T06:00:00")

    _pin(monkeypatch, instant=SIXTEEN_UTC, zone=HONOLULU)
    later = schedule.watch_one(lonestar.subdomain)
    assert later["ran"] is True, later


@pytest.mark.django_db
def test_only_the_first_sweep_of_the_hour_runs(brazos, monkeypatch):
    """Beat fires every fifteen minutes; the hour must still be ONE pass.

    `sweep_id` makes a repeat harmless, so this is about cost rather than
    correctness — and it is asserted because the alternative is four indexed
    queries per utility per morning for ever.
    """
    _pin(monkeypatch, instant=dt.datetime(2026, 9, 22, 11, 2, tzinfo=dt.UTC), zone=CHICAGO)
    assert schedule.watch_one(brazos.subdomain)["ran"] is True

    _pin(monkeypatch, instant=dt.datetime(2026, 9, 22, 11, 32, tzinfo=dt.UTC), zone=CHICAGO)
    late = schedule.watch_one(brazos.subdomain)
    assert late["ran"] is False
    assert late["reason"] == "already_swept_this_hour"


@pytest.mark.django_db
def test_a_disagreement_about_what_day_it_is_refuses_rather_than_guessing(brazos, monkeypatch):
    """Inside the midnight boundary the instant and `tenant_today()` disagree.

    Sweeping then would take the cut-off from one opinion of the day and the
    hour from the other — the bug BR-TEN-043 exists to prevent. The next sweep
    is unambiguous, and the sweep is idempotent, so refusing costs nothing.
    """
    _pin(
        monkeypatch,
        instant=dt.datetime(2026, 9, 22, 11, 2, tzinfo=dt.UTC),
        zone=CHICAGO,
        day=dt.date(2026, 9, 23),
    )
    report = schedule.watch_one(brazos.subdomain, force=True)
    assert report["ran"] is False
    assert report["reason"] == "midnight_boundary"


# ══════════════════════════════════════════════════════════════════════════
# 4 · IT TELLS, AND IT NEVER CLOSES
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_the_scheduled_run_tells_a_supervisor_and_closes_nothing(brazos, dana, marcus, monkeypatch):
    """The whole point of `P2.11`, reached the way it will actually be reached.

    The till is read back FIELD BY FIELD afterwards. §3.1 struck the midnight
    auto-close, so the absence of a write is the deliverable — and a scheduled
    caller is exactly where a future lane would be tempted to add one.
    """
    with tenant_ctx(brazos):
        till = an_open_till(brazos, marcus, opened_at=MONDAY_0855)
        before = {
            field.name: getattr(till, field.name)
            for field in tills.CounterSession._meta.concrete_fields
        }

    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    report = schedule.watch_one(brazos.subdomain)

    assert report["ran"] is True
    assert (
        report["tenants_examined"] == 1
    ), "a sweep that entered no tenant reports zero counters truthfully, about nothing"
    assert report["tills_left_open"] == 1
    codes = {out.get("code") for out in report["outcomes"]}
    assert run_alert_seam.COUNTER_WATCH_QUEUED in codes, codes

    with tenant_ctx(brazos):
        after_row = tills.CounterSession.objects.get(pk=till.pk)
        after = {
            field.name: getattr(after_row, field.name)
            for field in tills.CounterSession._meta.concrete_fields
        }
    assert after == before, "the watch TELLS — a System Admin closes a till and a job never does"


@pytest.mark.django_db
def test_a_second_firing_that_morning_says_it_once(brazos, dana, marcus, monkeypatch):
    """CLAUDE.md rule 6. `sweep_id` is a uuid5 of (utility, day), so moving the
    hour — or an operator running the command by hand afterwards — cannot put a
    second message in front of a supervisor."""
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)

    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    first = schedule.watch_one(brazos.subdomain)
    second = schedule.watch_one(brazos.subdomain, force=True)

    assert run_alert_seam.COUNTER_WATCH_QUEUED in {o.get("code") for o in first["outcomes"]}
    assert run_alert_seam.COUNTER_WATCH_ALREADY_QUEUED in {
        o.get("code") for o in second["outcomes"]
    }


@pytest.mark.django_db
def test_a_clean_morning_tells_nobody(brazos, monkeypatch):
    """A daily message nobody needs is one a clerk switches off, and then the
    failure they needed to see is the one they never get. An unattended sweep
    that found nothing addresses nobody (BR-NOT-021 refuses a failed count below
    one) and still REPORTS that it looked."""
    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    report = schedule.watch_one(brazos.subdomain)
    assert report["ran"] is True
    assert report["tills_left_open"] == 0
    assert report["tenants_examined"] == 1


def test_the_schedule_module_contains_no_write_to_a_till_at_all():
    """⚠ **AN ABSENCE, ASSERTED FROM THE SOURCE — the one thing no behavioural
    case can be relied on to notice.**

    `counter_watch.py` carries this guard already. It is repeated for the
    scheduling module because a scheduled caller is where *"while we are here,
    let us just close it"* would be written, and PO ruling 2026-09-23 §3.1 says
    no job may seal a till.

    ⚠ **THE SCHEDULE'S CLAIM IS THE STRONGER ONE AND IT IS NOT THE SAME LIST.**
    `counter_watch.py` SELECTs, so its guard names the write verbs and allows a
    queryset. The schedule touches no ORM at all — it resolves a tenant id
    through a seam, decides an hour, and hands a triple to the sweep — so what
    is asserted here is that **no queryset and no till model reach it**, which
    forbids every write including ones a verb list would miss.

    ⚠ **TWO TOKENS ARE DELIBERATELY NOT IN THIS LIST, AND BOTH OMISSIONS ARE
    THE POINT RATHER THAN A GAP.**

    `.update(` — `install()` legitimately calls `existing.update(schedule)` on a
    plain dict. A list that fired on that would be switched off by the next
    lane, which is worse than no list; the queryset clause closes the hole
    instead, because with no queryset in the file no `.update()` in it can reach
    a row.

    The TABLE NAME — the module says *"nothing here writes to `counter_sessions`"*
    four times, which is the rule being stated rather than broken. `G6` has
    fired on prose describing `G6` three times for exactly this shape, so the
    list names the IMPORT a write would have to come through, never the English.
    """
    source = pathlib.Path(schedule.__file__).read_text()
    orm = sorted(token for token in (".objects.", "counter_session_models") if token in source)
    assert orm == [], (
        "`counter_watch_schedule.py` reaches the ORM. It TELLS and it never closes "
        "(PO ruling 2026-09-23 §3.1), and it does that by handing the reading to "
        f"`counter_watch.sweep`. Found {orm}"
    )
    verbs = (".save(", ".delete(", ".create(", ".bulk_update(", "cursor()")
    assert sorted(token for token in verbs if token in source) == []

    # And the module it calls, so the pair cannot drift apart. Its list is the
    # one its own author wrote, `.update(` included, because that file HAS
    # querysets and there the token is unambiguous.
    swept = pathlib.Path(counter_watch.__file__).read_text()
    swept_forbidden = (".save(", ".update(", ".delete(", ".create(", ".bulk_update(", "cursor()")
    assert [token for token in swept_forbidden if token in swept] == []


# ══════════════════════════════════════════════════════════════════════════
# 5 · WHO IT WATCHES, AND WHAT IT SAYS WHEN IT WATCHES NOBODY
# ══════════════════════════════════════════════════════════════════════════
def test_with_no_utility_readable_the_firing_reports_rather_than_looking_healthy(
    monkeypatch,
):
    """`DEF-3422` — the notifications dispatcher paced an environment variable
    nothing set, and every firing on every deployment reached nobody while the
    queue filled up behind it. A fan-out that dispatches nowhere must SAY so."""
    monkeypatch.setenv(schedule.WATCH_TENANTS_ENV, "")
    monkeypatch.setattr("apps.tenancy.selectors.live_tenant_subdomains", lambda: ())
    result = schedule.watch_all()
    assert result["dispatched"] == 0
    assert result["problem"] == schedule.NO_TENANTS_FOUND


@pytest.mark.django_db
def test_the_default_is_every_live_utility_and_an_operator_may_narrow_it(brazos, monkeypatch):
    """Hard-won law 3: watching nobody is the unsafe option, so it is not what
    an unset variable means here."""
    monkeypatch.delenv(schedule.WATCH_TENANTS_ENV, raising=False)
    assert brazos.subdomain in schedule.watched_subdomains()

    monkeypatch.setenv(schedule.WATCH_TENANTS_ENV, f" {brazos.subdomain} , {brazos.subdomain} ")
    assert schedule.watched_subdomains() == (
        brazos.subdomain,
    ), "the same utility twice would be two sweeps per firing for one utility"


@pytest.mark.django_db
def test_an_unknown_subdomain_is_named_rather_than_silently_skipped(brazos):
    """An operator's typo must not read as a clean morning."""
    report = schedule.watch_one("no-such-utility", force=True)
    assert report["ran"] is False
    assert report["reason"] == "unknown_tenant"


@pytest.mark.django_db
def test_the_watch_leaves_its_callers_tenant_context_where_it_found_it(brazos, monkeypatch):
    """`tenant_context` CLEARS on exit rather than restoring, so a watch called
    from inside one would empty it — and every query afterwards would be denied
    with nothing visibly wrong (`apps/audit/diagnostics.sweep_expired` records
    the same trap)."""
    from core import tenancy as tenancy_kernel

    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    with tenant_ctx(brazos):
        schedule.watch_one(brazos.subdomain)
        assert tenancy_kernel.current_tenant_id() is not None


@pytest.mark.django_db
def test_status_says_when_it_next_runs_and_never_when_it_last_did(brazos, monkeypatch):
    """`last_run_at` is ABSENT rather than served as null: nothing records a
    counter-watch pass, and a screen renders a null as *"never"*, which is a
    claim and not an absence."""
    _pin(monkeypatch, instant=ELEVEN_UTC, zone=CHICAGO)
    with tenant_ctx(brazos):
        payload = schedule.status()
    assert payload["hour"] == schedule.DEFAULT_WATCH_HOUR
    assert payload["next_run_at"].startswith("2026-09-23T06:00:00")
    assert "last_run_at" not in payload
