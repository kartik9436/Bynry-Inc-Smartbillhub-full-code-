# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-012 (EP-RBS-04) — CR-075 wave L task L5, the half the Product
#           Owner reshaped on 2026-09-06.
# Rules:    OQ-RBS-1737 CLOSED (the duplicate check moved from the RECORD to the
#           RUN) · supersedes BR-RBS-008 (PROPOSED, never confirmed) ·
#           CLAUDE.md hard rule 6 · BR-TEN-043 (event time is an argument)
# Tests:    this file
# Impacts:  apps/runbooks/engine/duplicates.py
# ───────────────────────────────────────────────────────
"""The Product Owner's own two scenarios, and the third state a key cannot express.

> *"if it runs at 7 am and user approved it then it will create records/data in
> system. when you again run it at 9 am - you will find those record means you
> can see that it is duplicate. second scenario lets say you run at 7 am and no
> one approve it until 9 am ; then again 9 am run at that time you will see same
> job ran at 7 am and not yet approved; you can give warning to user sayng that
> job is pending to be approved; keep 24 hours time limit on the same job or we
> can parameteise the frequency of the runs"*

Both scenarios are cases below, by name. The third is the one that matters most:
**an unapproved earlier run is a WARNING, not a skip** — neither of the two
candidate keys we put to the Product Owner could have said that at all, because a
key is a yes/no.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.runbooks import models
from apps.runbooks.engine import duplicates
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar

pytestmark = pytest.mark.django_db

SEVEN_AM = dt.datetime(2026, 9, 7, 7, 0, tzinfo=dt.timezone.utc)
NINE_AM = dt.datetime(2026, 9, 7, 9, 0, tzinfo=dt.timezone.utc)


def _runbook(tenant, key="collections_ladder"):
    return models.Runbook.objects.create(
        tenant=tenant,
        key=key,
        name="Collections ladder",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="past due",
    )


def _run(tenant, runbook, *, status, started_at, records=0):
    run = models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        mode=models.MODE_DRY,
        status=status,
        started_at=started_at,
    )
    for n in range(records):
        models.RunbookRunRecord.objects.create(
            tenant=tenant,
            run=run,
            subject_type="account",
            planned_action="Queue the 10-day notice",
            idempotency_key=f"k-{run.pk}-{n}",
        )
    return run


def test_scenario_one_seven_am_approved_then_nine_am_sees_the_rows(brazos):
    """**812 records are VISIBLE, so the 09:00 run knows and writes nothing.**

    Detection is a READ of what exists — not a fingerprint computed in advance.
    That is the whole of the ruling, and the count travels so the second run can
    tell a clerk *"812 already"* rather than merely refusing.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        _run(brazos, runbook, status=models.RUN_STATUS_DONE, started_at=SEVEN_AM, records=3)
        verdict = duplicates.check(
            tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM
        )

    assert verdict.verdict == duplicates.VERDICT_ALREADY_ACTED
    assert verdict.is_duplicate is True
    assert verdict.records_written == 3
    assert "3 records" in verdict.message


def test_scenario_two_unapproved_at_nine_is_a_WARNING_and_not_a_skip(brazos):
    """**The third state.** *"job is pending to be approved"* — a warning.

    A build that treated this as a duplicate would silently discard a run whose
    plan is still sitting on a clerk's screen, and the clerk would never learn
    why the 09:00 run did nothing. `is_duplicate` is False here **on purpose**.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        _run(
            brazos,
            runbook,
            status=models.RUN_STATUS_AWAITING_APPROVAL,
            started_at=SEVEN_AM,
            records=2,
        )
        verdict = duplicates.check(
            tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM
        )

    assert verdict.verdict == duplicates.VERDICT_PENDING_APPROVAL
    assert verdict.is_duplicate is False, "a run waiting for a person is NOT a duplicate"
    assert verdict.warning is True
    assert "waiting to be approved" in verdict.message


def test_the_time_bound_is_twenty_four_hours_by_default(brazos):
    """*"keep 24 hours time limit on the same job"* — the Product Owner's figure.

    A run from 25 hours ago is outside the window and the job may run again.
    """
    from core import tenancy as core_tenancy

    assert duplicates.DEFAULT_FREQUENCY_HOURS == 24
    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        _run(
            brazos,
            runbook,
            status=models.RUN_STATUS_DONE,
            started_at=NINE_AM - dt.timedelta(hours=25),
            records=5,
        )
        verdict = duplicates.check(tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM)
    assert verdict.verdict == duplicates.VERDICT_NONE


def test_the_frequency_is_a_parameter_and_a_weekly_ladder_can_use_it(brazos):
    """*"or we can parameteise the frequency of the runs"* — read as ONE control.

    This lane's recorded reading (decision log 2026-09-06): the frequency is a
    parameter and 24 hours is its default, because the two are the same control
    at different settings. A weekly ladder sets 168 and the same run is then
    still *the same job* six days later.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        _run(
            brazos,
            runbook,
            status=models.RUN_STATUS_DONE,
            started_at=NINE_AM - dt.timedelta(hours=25),
            records=5,
        )
        weekly = duplicates.check(
            tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM, frequency_hours=168
        )
    assert weekly.verdict == duplicates.VERDICT_ALREADY_ACTED


def test_zero_hours_is_refused_rather_than_switching_the_guarantee_off():
    """Zero would mean *never treat any run as the same job* — the guarantee off."""
    with pytest.raises(ValueError):
        duplicates.check(tenant_id=None, runbook_id=None, now=NINE_AM, frequency_hours=0)


def test_a_sibling_runbooks_run_is_invisible_to_this_one(brazos):
    """**A false pass this check could have had** (hard-won law 7, habit 2).

    Filtered on the tenant alone, two different runbooks running at 07:00 would
    each report the other as a duplicate and neither would ever act again.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        ladder = _runbook(brazos, key="collections_ladder")
        other = _runbook(brazos, key="cash_application")
        _run(brazos, other, status=models.RUN_STATUS_DONE, started_at=SEVEN_AM, records=9)
        verdict = duplicates.check(tenant_id=brazos.id, runbook_id=ladder.pk, now=NINE_AM)
    assert verdict.verdict == duplicates.VERDICT_NONE


def test_a_run_never_reports_ITSELF_as_a_duplicate(brazos):
    """The other false pass: without `exclude`, every run finds itself."""
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        mine = _run(
            brazos, runbook, status=models.RUN_STATUS_RUNNING, started_at=NINE_AM, records=1
        )
        verdict = duplicates.check(
            tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM, this_run_id=mine.pk
        )
    assert verdict.verdict == duplicates.VERDICT_NONE


def test_another_utilitys_run_is_not_this_utilitys_duplicate(brazos, lonestar):
    """Hard rule 1 at the application layer. The RLS half is on PostgreSQL."""
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(lonestar.id):
        theirs = _runbook(lonestar)
        _run(lonestar, theirs, status=models.RUN_STATUS_DONE, started_at=SEVEN_AM, records=4)
    with core_tenancy.tenant_context(brazos.id):
        mine = _runbook(brazos)
        verdict = duplicates.check(tenant_id=brazos.id, runbook_id=mine.pk, now=NINE_AM)
    assert verdict.verdict == duplicates.VERDICT_NONE


def test_a_stopped_earlier_run_is_reported_with_its_count_rather_than_as_clean(brazos):
    """A run stopped at record 120 wrote 120 rows, so it is NOT nothing.

    Reported as `EARLIER_RUN` with the count, because the count is what a clerk
    reads — the status word alone cannot tell *stopped at 0* from *stopped at
    120*.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = _runbook(brazos)
        _run(
            brazos, runbook, status=models.RUN_STATUS_STOPPED, started_at=SEVEN_AM, records=7
        )
        verdict = duplicates.check(tenant_id=brazos.id, runbook_id=runbook.pk, now=NINE_AM)
    assert verdict.verdict == duplicates.VERDICT_EARLIER_RUN
    assert verdict.records_written == 7
    assert verdict.is_duplicate is False
    assert verdict.warning is True


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-012 (EP-RBS-04; CR-075 wave L task L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_012_duplicates.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
