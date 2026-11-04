# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-004 (phase 2 calculate)   Screens: S31 step 2 (the check)
# Change:   CR-105-BRC03 — the bill run rebuild. Blueprint p050, the panel
#           headed *"What it must also do, but cannot be drawn"*, verbatim:
#           *"Refuse rather than run inline above the bar — a deployment with
#           no worker runs the check inline today and the request dies long
#           before its own `ran inline` answer can be read. And resume without
#           re-walking: a worker killed at 9,000 of 10,000 pays 22 minutes
#           again unless the checkpoint is used."*
# Contract: TD-17 (*"every job idempotent + resumable"*) · NFR-4 (progress) ·
#           B12 r1 §3 (202 + job_id; the client polls /api/jobs/{id})
# Rules:    BR-BIL-052 (per-account, restartable, resumable) · BR-BIL-023 (a
#           re-calculation REPLACES a draft) · CLAUDE.md hard rule 6
# Tests:    this file. The half that runs the ENGINE is tc1 and tc2.
# Impacts:  core/jobs.py (reclaim + resume) · apps/billing/run_jobs.py (the bar
#           and the refusal) · apps/tenancy/tasks.py (a redelivery resumes) ·
#           config/settings/base.py (visibility_timeout, the bar)
# ───────────────────────────────────────────────────────
"""CR-105-BRC03 — the two things p050 says the bill run must do off-screen.

⚠ **WHY THESE CASES GO THROUGH `core.jobs` AND NOT THROUGH A HAND-BUILT DICT.**
`tests/test_cr051_run_scale.py` proves the resume by calling
`run_jobs.run_calculate_job(record)` with a record it builds itself — a plain
dict whose `id` is the BILL RUN's primary key, never saved to the `jobs` table
and never passed through a status transition. Every one of those cases passes
today and every one of them would go on passing while the transport was broken,
because the transport is the part they skip. That is CLAUDE.md hard-won law 7's
*looking at the wrong thing*: a test named after an assertion it does not make.

**What was actually broken, and it was one hop.** A worker killed mid-pass
writes NOTHING — `core.jobs.run_job` catches `Exception`, and a process that
dies does not raise one — so the record is left saying `running`. Celery's
`CELERY_TASK_ACKS_LATE` then re-delivers the message, `run_pending` reaches
`start()`, and `start()` refused a `running` record with *"cannot start (resume
is failed→running)"*. So the checkpoint `apps/billing/run_resume.py` writes so
carefully was reachable by **nothing in this product**: the CR-051 kill proof
gets to it only by hand-writing `core_jobs.fail(job_id, "worker killed
(SIGKILL)")` first, which is a step no deployment performs.

tc1 and tc2 therefore drive the REAL path: mint a record, run it, kill it in a
way that records nothing, and deliver it again exactly as a broker does.
"""

from __future__ import annotations

import pytest

from apps.billing import models as billing_models
from apps.billing import run_jobs, run_resume
from apps.billing import runs as billing_runs
from core import jobs as core_jobs

from tests.test_cr051_run_jobs_and_breaks import (  # noqa: F401
    a_run,
    calculate,
    live_store,  # noqa: F401 — fixture: the real `jobs` table
)
from tests.test_us_bil_001_prepare import (
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    # ⚠ NAMED EXPLICITLY, and it is not decoration. `sqlite_guc` is autouse and
    # arrives in most suites through the star-import chain; it does not arrive
    # here, and without it `apps.tenancy.tasks.run_pending_job` — which enters
    # `core.tenancy.tenant_context` itself, as a real worker must — dies on
    # sqlite with `no such function: set_config`. That is the shim, not the
    # code under test.
    sqlite_guc,
)

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing
# ══════════════════════════════════════════════════════════════════════════
def a_world(tenant, actor, *, accounts=4):
    """`accounts` billable accounts on one cycle, numbered in WALK ORDER.

    The numbers are what the resume cursor is compared against, so they are
    explicit and ascending rather than left to a fixture: a case about a cursor
    that did not control the order would prove nothing.
    """
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    for index in range(1, accounts + 1):
        unit = a_billed_unit(
            actor, tenant, cycle, plan, asset_no=f"M-85{index:02d}", label=f"U{index}"
        )
        an_account(tenant, unit["id"], f"ACC-85{index:02d}")
    return cycle


def drafts_of(tenant, run):
    """`{account_id: total}` for the run's drafts — the money a double-bill moves."""
    rows = billing_models.Invoice.objects.filter(
        tenant_id=tenant.id, bill_run=run, status=billing_models.INVOICE_DRAFT
    ).values_list("account_id", "total")
    return {str(account_id): total for account_id, total in rows}


def a_queued_job(run):
    """A REAL `jobs` row, minted by the kernel exactly as the request does.

    The dispatcher is unplugged for the duration so the record RESTS `queued`
    rather than being executed in-process by the eager transport — which is
    what `JOBS_EAGER=False` does in production, and what makes *"deliver the
    same message again"* something this file can actually do.
    """
    previous = core_jobs._dispatcher  # noqa: SLF001 — the kernel's own switch
    core_jobs.set_job_dispatcher(None)
    try:
        return run_jobs.enqueue_calculate(run)
    finally:
        core_jobs.set_job_dispatcher(previous)


def deliver(record, tenant):
    """The message arriving at a worker — THE REAL DOOR, not `run_pending`.

    `apps.tenancy.tasks.run_pending_job` is the one Celery task every job kind
    rides (the RECORD says what kind it is), so this is byte-for-byte what a
    `celery-billing` worker executes. Calling `run_pending` directly instead
    would test the kernel and skip the hop that was broken — which is the
    mistake `test_cr051_run_scale.py` makes one layer further out.
    """
    from apps.tenancy import tasks as tenancy_tasks

    return tenancy_tasks.run_pending_job(
        str(record["id"]), str(tenant.id), kind=str(record["kind"])
    )


class _WorkerKilled(BaseException):
    """What a SIGKILL looks like to `core.jobs.run_job`, which is: nothing.

    `run_job` catches `Exception`, so this escapes without `fail()` being
    written and the record is left saying `running` — precisely the state
    `10-scripts/cr051_kill_and_resume.py` reports after signal 9 (*"job status
    after the kill: running (a SIGKILL records nothing)"*). A subclass of
    `Exception` would be a simulated kill that RECORDS A FAILURE, which proves
    the opposite of the point.
    """


def _kill_after(monkeypatch, accounts: int):
    """Let `accounts` accounts finish, then vanish without recording anything."""
    original = billing_runs.calculate_account
    done: list[str] = []

    def counted(data, **kwargs):
        if len(done) >= accounts:
            raise _WorkerKilled("the worker vanished")
        result = original(data, **kwargs)
        done.append(str(getattr(data, "account_no", "?")))
        return result

    monkeypatch.setattr(billing_runs, "calculate_account", counted)
    return done


def _gathered(monkeypatch) -> list[str]:
    """Every account the next pass actually WALKS, by number."""
    seen: list[str] = []
    original = billing_runs.gather.gather_account

    def counted(**kwargs):
        seen.append(str(getattr(kwargs["account"], "account_no", "?")))
        return original(**kwargs)

    monkeypatch.setattr(billing_runs.gather, "gather_account", counted)
    return seen


# ══════════════════════════════════════════════════════════════════════════
# tc1/tc2 — RESUME WITHOUT RE-WALKING, through the transport that carries it
# ══════════════════════════════════════════════════════════════════════════
def test_cr105_tc1__a_redelivered_job_left_running_by_a_dead_worker_resumes(
    brazos, dana, live_store
):
    """p050: *"a worker killed at 9,000 of 10,000 pays 22 minutes again unless
    the checkpoint is used."*

    RED before the fix, verbatim:

        core.jobs.JobsError: job 019… is running — cannot start
        (resume is failed→running)

    which is `run_pending` refusing the very redelivery `CELERY_TASK_ACKS_LATE`
    exists to produce. Not slow — impossible: the record stayed `running` for
    ever and the run never finished at all.
    """
    # ⚠ A PRIVATE `MonkeyPatch`, NOT THE FIXTURE — `sqlite_guc` is autouse and
    # shares the fixture's `monkeypatch`, so the `undo()` below would lift its
    # `set_config` shim and the redelivery would die on `no such function:
    # set_config` instead of on anything this case is about (`DEF-922`, stated
    # in that fixture's own docstring).
    kill = pytest.MonkeyPatch()
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc1")
        kill.setattr(run_jobs, "PROGRESS_EVERY", 1)  # a cursor per account
        record = a_queued_job(run)
        _kill_after(kill, 2)

        with pytest.raises(_WorkerKilled):
            deliver(record, brazos)

        killed = core_jobs._store.get(record["id"])  # noqa: SLF001
        assert killed["status"] == core_jobs.RUNNING, (
            "a SIGKILL records nothing, so the record must still say running — "
            "if it does not, this case has stopped simulating a kill"
        )
        assert killed["checkpoint"] and killed["checkpoint"].get(
            "cursor"
        ), "the first pass wrote no cursor, so there is nothing for a resume to read"

        # ── the redelivery: the same message, arriving again ──
        kill.undo()
        deliver(record, brazos)

        after = core_jobs._store.get(record["id"])  # noqa: SLF001
        assert after["status"] == core_jobs.SUCCEEDED
        assert len(drafts_of(brazos, run)) == 4, "the resumed delivery did not finish the run"


def test_cr105_tc2__the_resumed_delivery_skips_what_the_first_one_finished(
    brazos, dana, live_store
):
    """The half that is worth the 22 minutes. Not *"it finished"* — *"it did
    not re-walk"*, which is a different claim and the only one p050 makes.

    Asserted through the transport rather than by handing `run_calculate_job` a
    checkpoint, because the checkpoint has to survive `_store.save`, a
    `running` record and `start()` before it means anything in production.
    """
    kill = pytest.MonkeyPatch()  # private — see tc1
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc2")
        kill.setattr(run_jobs, "PROGRESS_EVERY", 1)
        record = a_queued_job(run)
        _kill_after(kill, 2)
        with pytest.raises(_WorkerKilled):
            deliver(record, brazos)
        before = drafts_of(brazos, run)
        assert len(before) == 2, "the kill landed outside the pass — adjust the count"

        kill.undo()
        watch = pytest.MonkeyPatch()
        watch.setattr(run_jobs, "PROGRESS_EVERY", 1)
        walked = _gathered(watch)
        try:
            deliver(record, brazos)
        finally:
            watch.undo()

        assert sorted(walked) == ["ACC-8503", "ACC-8504"], (
            "the resumed delivery re-walked the cycle — it gathered "
            f"{sorted(walked)} when the first two were already drafted"
        )
        after = drafts_of(brazos, run)
        assert len(after) == 4, "an account gained a second draft — hard rule 6"
        for account_id, total in before.items():
            assert after[account_id] == total, "money moved on a resume"


def test_cr105_tc3__a_failed_record_resumes_and_a_succeeded_one_never_does(
    brazos, dana, live_store
):
    """`resume` widens exactly one edge and must widen no other.

    `succeeded` is terminal for ever (core/jobs.py's own status vocabulary),
    and a resume that could reach it would be a second pass over a run whose
    bills may already be issued — hard rule 4.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc3")
        record = a_queued_job(run)
        core_jobs.start(record["id"])
        core_jobs.fail(record["id"], "soft time limit")

        core_jobs.resume(record["id"])  # failed → running → succeeded
        assert core_jobs._store.get(record["id"])["status"] == core_jobs.SUCCEEDED  # noqa: SLF001

        with pytest.raises(core_jobs.JobsError) as refused:
            core_jobs.resume(record["id"])
        assert "succeeded" in str(refused.value)


def test_cr105_tc4__reclaim_keeps_the_checkpoint_and_refuses_every_other_status(
    brazos, dana, live_store
):
    """The checkpoint is the whole asset. A reclaim that cleared it would turn
    a 22-minute saving into a 22-minute cost while looking like a repair."""
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc4")
        record = a_queued_job(run)
        core_jobs.start(record["id"])
        marker = run_resume.checkpoint(done=1, total=2, account_no="ACC-8501")
        core_jobs.record_progress(record["id"], done=1, total=2, checkpoint=marker)

        reclaimed = core_jobs.reclaim(record["id"], reason="worker lost")
        assert reclaimed["status"] == core_jobs.FAILED
        assert reclaimed["checkpoint"] == marker, "the reclaim threw the cursor away"
        assert core_jobs._store.get(record["id"])["checkpoint"] == marker  # noqa: SLF001

        with pytest.raises(core_jobs.JobsError):
            core_jobs.reclaim(record["id"], reason="again")  # it is failed now, not running


def test_cr105_tc9__run_pending_alone_still_refuses_and_the_transport_calls_resume(
    brazos, dana, live_store
):
    """**This case IS the RED proof, kept rather than described.**

    `run_pending` is deliberately unchanged: an abandoned `running` record is
    not something an EAGER in-process dispatch can ever produce, and widening
    the kernel's ordinary entry point would let one be reclaimed by a caller
    that had no business deciding the previous attempt was dead. So the
    widening lives in `resume`, and the first assertion below is the exact
    failure every redelivery got until 2026-09-14:

        JobsError: job … is running — cannot start (resume is failed→running)

    The second assertion is the other half, and it is hard-won law 2's mirror:
    a capability nothing calls is not a capability. `apps.tenancy.tasks` is the
    ONE Celery task every job kind rides, so if its body stops naming `resume`
    the widening is dead code and this goes RED — which is the check nobody
    wrote for the checkpoint itself, and why the checkpoint sat unreachable for
    a fortnight.
    """
    import inspect

    from apps.tenancy import tasks as tenancy_tasks

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc9")
        record = a_queued_job(run)
        core_jobs.start(record["id"])  # a worker picked it up and then vanished

        with pytest.raises(core_jobs.JobsError) as refused:
            core_jobs.run_pending(record["id"])
        assert "cannot start" in str(refused.value)

        core_jobs.resume(record["id"])
        assert core_jobs._store.get(record["id"])["status"] == core_jobs.SUCCEEDED  # noqa: SLF001

    body = inspect.getsource(tenancy_tasks.run_pending_job)
    assert "core_jobs.resume(" in body, (
        "the Celery task no longer calls core.jobs.resume — a re-delivered job "
        "reaches start() with a `running` record again and every checkpoint in "
        "this product goes back to being unreachable"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc5-tc7 — REFUSE RATHER THAN RUN INLINE ABOVE THE BAR
# ══════════════════════════════════════════════════════════════════════════
def test_cr105_tc5__the_bar_is_the_published_arithmetic_and_drift_goes_red():
    """p050 publishes both figures: **137 ms per account** and *"the request
    wall is about 60 seconds"*. `run_jobs.MEASURED_SECONDS_PER_ACCOUNT` is the
    RLS-enforced correction of that first figure (0.17, DEF-2717), so the bar
    is 60 ÷ 0.17 with a margin — a number this case recomputes rather than
    copies, so moving either input without moving the bar goes RED.
    """
    wall = run_jobs.REQUEST_WALL_SECONDS
    bar = run_jobs.INLINE_ACCOUNT_BAR_DEFAULT
    assert wall == 60
    assert bar * run_jobs.MEASURED_SECONDS_PER_ACCOUNT < wall, (
        f"a run of {bar} accounts costs "
        f"{bar * run_jobs.MEASURED_SECONDS_PER_ACCOUNT:.0f}s inline, which is past the "
        f"{wall}s request wall — the bar no longer bounds the thing it exists for"
    )
    assert bar >= 200, "the bar is so low that ordinary small runs are refused"


def test_cr105_tc6__above_the_bar_with_no_worker_the_run_is_refused_not_run_inline(
    brazos, dana, live_store, monkeypatch, settings
):
    """p050: *"Refuse rather than run inline above the bar."*

    RED before the fix: **201 with `background: false`** — the inline pass,
    whose answer the clerk cannot read because the request wall arrives first.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc6")
    settings.BILLING_INLINE_ACCOUNT_BAR = 1  # this 2-account run is above it
    monkeypatch.setattr(run_jobs, "would_run", lambda: (False, "no worker"))

    response = calculate(brazos, run, background=True)
    assert response.status_code == 422, (
        f"a run above the bar with no worker answered {response.status_code} — it "
        "ran inline, and the request wall arrives long before that answer does"
    )
    assert response.data["message_key"] == "billing.run.noWorker", response.data
    with tenant_ctx(brazos):
        assert drafts_of(brazos, run) == {}, "it refused and drafted anyway"


def test_cr105_tc7__below_the_bar_the_inline_fallback_is_exactly_what_it_was(
    brazos, dana, live_store, monkeypatch, settings
):
    """The refusal is *above the bar* and nowhere else.

    A small utility running with no worker at all keeps the product it has
    today — which is the whole reason `run_jobs.py` chose an inline fallback
    over the import's flat refusal, and this case is what stops the fix quietly
    taking that away.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle, key="2026-06|cr105-tc7")
    settings.BILLING_INLINE_ACCOUNT_BAR = 5_000
    monkeypatch.setattr(run_jobs, "would_run", lambda: (False, "no worker"))

    response = calculate(brazos, run, background=True)
    assert response.status_code == 201
    assert response.data["background"] is False
    with tenant_ctx(brazos):
        assert len(drafts_of(brazos, run)) == 2


def test_cr105_tc8__the_bar_and_the_broker_are_declared_where_an_operator_can_move_them():
    """Two settings, and each was a lesson somebody else paid for.

    * `BILLING_INLINE_ACCOUNT_BAR` must be DECLARED, not merely read through
      `getattr(settings, NAME, DEFAULT)` — `DEF-2806` is the record of a
      ceiling that told operators it was overridable while Django never
      exposed the name, so `BILLING_MAX_ACCOUNTS_PER_RUN=5000` in a `.env`
      changed nothing and said nothing. The literal here is held equal to the
      module's so the pair cannot drift.
    * The broker's `visibility_timeout` must sit ABOVE the hard time limit, or
      `core.jobs.reclaim` stops being safe: a legitimate 70-minute run would be
      re-delivered while it is still running, and the redelivery would reclaim
      a record whose worker is very much alive.
    """
    from django.conf import settings

    assert settings.BILLING_INLINE_ACCOUNT_BAR == run_jobs.INLINE_ACCOUNT_BAR_DEFAULT
    assert run_jobs.inline_account_bar() == run_jobs.INLINE_ACCOUNT_BAR_DEFAULT

    visibility = settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"]
    assert visibility > settings.CELERY_TASK_TIME_LIMIT, (
        f"visibility_timeout {visibility}s is not above the {settings.CELERY_TASK_TIME_LIMIT}s "
        "hard limit — a running job would be re-delivered and then reclaimed under itself"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-105-BRC03 (05-prototype/04 Billing, As Built.pdf p050 · core/jobs.py's BE-07 contract · apps/billing/run_resume.py)
# generated: 2026-09-14 by the CR-105-BRC03 job-transport lane
# checklist: A✔ B=n/a(no frontend half in this lane) C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
