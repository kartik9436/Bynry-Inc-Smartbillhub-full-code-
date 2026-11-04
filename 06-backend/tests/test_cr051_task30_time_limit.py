# ── Trace ──────────────────────────────────────────────
# Change:   CR-051 task 30 — *"State the largest run this deployment accepts
#           and what it does above it"*. The SIZE half shipped 2026-08-31; this
#           is the TIME half, which `DEF-2829` records the CR counting as done
#           while its own prose said otherwise.
# Rules:    BR-BIL-1030 (a background job is bounded in time as well as in
#           size, and what it does at the limit is fail honestly) ·
#           CLAUDE.md hard-won law 2 (built is not wired) · law 3 (defaults
#           fail closed) · B14 rule 32 / G28 (no internal id in clerk copy)
# Defects:  DEF-2829 (the count said 30 done over its own caveat) ·
#           DEF-2806 (a hard-killed job stays `running` for ever) ·
#           DEF-2806 (two ceilings said they were env overrides and were not)
# Impacts:  config/settings/base.py · core/jobs.py · apps/billing/runs.py ·
#           apps/billing/print_set.py
# ───────────────────────────────────────────────────────
"""CR-051 task 30 — a bill run that hangs is stopped, and it says so.

WHAT THIS FILE PROVES, in the order the task asks for it:

  tc1   both limits exist, the soft one is first, and the gap between them is
        big enough for the failing job to write its own row
  tc2   the numbers are the DERIVED ones and drift goes RED — the ceiling
        times the slowest per-account figure ever published, plus headroom
  tc3   **built is not wired** (hard-won law 2): the numbers Celery actually
        runs on are the ones in the settings file
  tc4   the two SIZE ceilings are declared as settings and agree with the
        module defaults that shadow them (`DEF-2806`)
  tc5   a job that runs out of time is recorded `failed` on the SAME path
        every other failure takes, with a sentence a clerk can read
  tc6   ...and its checkpoint survives, so the next attempt RESUMES
  tc7   the sentence is clerk copy: no rule id, no register id, no class name
  tc8   an ordinary failure is untouched — the diagnosis a support cycle needs
        is still `Type: message`
  tc9   the bill run's progress gauge does NOT swallow the limit
  tc10  the print set's per-bill handler does NOT swallow it either
  tc11  a time limit RELEASES the database connection the signal interrupted,
        and puts the tenant back on the new one — without which the honest
        failure path raises instead of recording anything
  tc12  the kernel still imports and behaves with no Celery installed

⚠ **WHY tc9 AND tc10 EXIST AT ALL, BECAUSE THEY LOOK LIKE PARANOIA.**
`SoftTimeLimitExceeded` subclasses `Exception` and Celery raises it EXACTLY
ONCE, wherever the task happens to be. Both of those handlers are `except
Exception: log; continue` — the shape a batch uses so one broken row never
costs the other nine thousand their post — and both sit on the hot path of the
longest-running job this product has. Swallowed there, the limit does not fire
again: the run continues unbounded until the hard kill, nothing is logged as
wrong, and every test in this file except these two still passes. That is a
check that cannot bite, which CLAUDE.md law 11 says is worse than no check.

⚠ **THE REAL WORKER PROOF IS NOT IN THIS FILE**, for the reason
`test_cr051_run_scale.py` already records about the killed worker: a real soft
time limit needs a real Celery worker in a second PROCESS with a real broker,
and this suite has neither. It is `10-scripts/cr051_time_limit_proof.py`, which
starts redis, starts a worker with a five-second soft limit, enqueues a body
that sleeps past it, and reads the job record back. tc5 and tc6 are the
deterministic half and prove the same two properties in-process.
"""

import importlib
import sys
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from django.conf import settings

from apps.billing import print_set, run_jobs
from core import jobs

REPO = Path(__file__).resolve().parents[2]
TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000b")

#: The measured inputs BR-BIL-1030's arithmetic is built from. They are stated
#: here rather than imported because the whole point of tc2 is that the settings
#: and the derivation are two things that must agree — importing one from the
#: other would make the check compare a number with itself.
CEILING_ACCOUNTS = 25_000
SLOWEST_SECONDS_PER_ACCOUNT = 0.219  # CR-051 task 26, RLS enforced, 10,000 accounts
HEADROOM = 1.5
FAILURE_WRITE_ALLOWANCE_SECONDS = 300


class FakeStore:
    """The documented store contract — the same fake `test_be07_jobs.py` uses."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    def save(self, record):
        self.rows[record["id"]] = dict(record)

    def get(self, job_id):
        row = self.rows.get(job_id)
        return dict(row) if row else None

    def find_active(self, tenant_id, kind, scope_key):
        return None


@pytest.fixture()
def store(monkeypatch):
    fake = FakeStore()
    was_store, was_dispatcher = jobs._store, jobs._dispatcher
    jobs.set_job_store(fake)
    # ⚠ AND THE DISPATCHER TOO. `enqueue` hands the record to whatever
    # dispatcher the app registered, which under the test settings is Celery —
    # so without this the case reaches for a broker that is deliberately not
    # running and dies on `Error 111 connecting to localhost:6379`. Nothing
    # here is about transport; `test_be07_jobs.py` clears both for the same
    # reason.
    jobs.set_job_dispatcher(None)
    monkeypatch.setattr(jobs, "current_tenant_id", lambda: TENANT)

    @contextmanager
    def fake_tenant_context(tenant_id):
        yield tenant_id

    monkeypatch.setattr(jobs, "tenant_context", fake_tenant_context)
    yield fake
    # PUT THE REAL ONES BACK, not None: this file runs in a session with a
    # hundred other cases that expect the app's own store and transport.
    jobs.set_job_store(was_store)
    jobs.set_job_dispatcher(was_dispatcher)


def _soft_time_limit_error():
    from celery.exceptions import SoftTimeLimitExceeded

    return SoftTimeLimitExceeded()


# ══════════════════════════════════════════════════════════════════════════
# tc1-tc4 — the settings themselves
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc1__both_limits_exist_and_leave_room_to_fail_honestly():
    """Two limits, in the right order, with a gap big enough to write a row.

    A soft limit ABOVE the hard one is never reached — the worker is killed
    first and the record is left `running` for ever (`DEF-2806`). A gap too
    small is the same failure with extra steps: the soft signal is only seen
    when control returns to Python, so a statement in flight has to finish
    before the failure row can be written.
    """
    soft = settings.CELERY_TASK_SOFT_TIME_LIMIT
    hard = settings.CELERY_TASK_TIME_LIMIT
    assert isinstance(soft, int) and isinstance(hard, int)
    assert soft > 0 and hard > 0
    assert soft < hard, (
        "the SOFT limit must fire first. Above the hard one it is never reached: "
        "Celery kills the worker, nothing is recorded, and the job row says "
        "`running` for ever"
    )
    assert hard - soft >= FAILURE_WRITE_ALLOWANCE_SECONDS, (
        f"only {hard - soft}s between the soft limit and the hard kill. The failing "
        f"job has to unwind, roll back its transaction and write its own failure "
        f"row in that window, and a statement already in flight finishes first"
    )


def test_cr051_tc2__the_limits_are_the_derived_numbers_and_drift_goes_red():
    """BR-BIL-1030's arithmetic, recomputed rather than copied.

    ceiling × slowest measured seconds per account × headroom → the soft limit,
    plus the failure-write allowance → the hard one. This is the ratified-figure
    pattern: a lane that lowers either number without moving the derivation is
    changing what this deployment promises, and it goes RED here first.
    """
    longest_legitimate_run = CEILING_ACCOUNTS * SLOWEST_SECONDS_PER_ACCOUNT
    assert round(longest_legitimate_run) == 5475  # 1 h 31 m, the run at the ceiling

    soft = settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert soft >= longest_legitimate_run, (
        f"the soft limit ({soft}s) is BELOW the longest run this deployment "
        f"accepts ({longest_legitimate_run:.0f}s at {CEILING_ACCOUNTS:,} accounts × "
        f"{SLOWEST_SECONDS_PER_ACCOUNT}s). A limit under the legitimate work kills "
        f"correct runs, which is worse than no limit: it teaches an operator to "
        f"turn it off"
    )
    assert soft == 8220, "BR-BIL-1030 publishes 8,220s (2 h 17 m) — 5,475 × 1.5, rounded up"
    assert round(longest_legitimate_run * HEADROOM) <= soft <= 8220

    hard = settings.CELERY_TASK_TIME_LIMIT
    assert hard == 8520, "BR-BIL-1030 publishes 8,520s — the soft limit plus 300s"
    assert hard == soft + FAILURE_WRITE_ALLOWANCE_SECONDS


def test_cr051_tc3__celery_actually_runs_on_these_numbers():
    """HARD-WON LAW 2 — BUILT IS NOT WIRED.

    Two settings in a file are two settings in a file. What bounds a task is
    `app.conf.task_soft_time_limit`, and it only carries these values because
    `config/celery.py` reads Django settings under the `CELERY` namespace. If
    that namespace or those names ever changed, every other case here would
    still pass over a deployment with no time limit at all.
    """
    from config.celery import app

    assert app.conf.task_soft_time_limit == settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert app.conf.task_time_limit == settings.CELERY_TASK_TIME_LIMIT


def test_cr051_tc4__the_size_ceilings_are_real_settings_and_agree(settings):
    """DEF-2806 — the ceilings said they were deployment overrides and were not.

    Both readers ask `getattr(settings, "<NAME>", <module default>)`, which
    cannot fail: an undeclared setting is indistinguishable from one left at its
    default, so the product behaved correctly at 25,000 while an operator's
    environment variable was read by nobody.

    The number is stated twice — a settings module may not import
    `apps.billing` — so this case is what stops the pair drifting the way
    `package.json` and `pyproject.toml` did three times.
    """
    assert settings.BILLING_MAX_ACCOUNTS_PER_RUN == run_jobs.MAX_ACCOUNTS_PER_RUN_DEFAULT
    assert settings.BILLING_MAX_BILLS_PER_PRINT_SET == print_set.MAX_BILLS_PER_PRINT_SET_DEFAULT
    # …and the readers see the SETTING, not their own fallback.
    settings.BILLING_MAX_ACCOUNTS_PER_RUN = 7
    settings.BILLING_MAX_BILLS_PER_PRINT_SET = 9
    assert run_jobs.max_accounts_per_run() == 7
    assert print_set.max_bills_per_print_set() == 9


# ══════════════════════════════════════════════════════════════════════════
# tc5-tc8 — what a job that ran out of time leaves behind
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc5__a_job_that_runs_out_of_time_is_recorded_failed(store):
    """The run stops claiming it is working, and it says what happened.

    ⚠ **THIS IS THE EXISTING FAILURE PATH AND NOT A SECOND ONE.** The soft
    limit arrives at `run_job`'s ordinary `except Exception` exactly like a
    pricing error would; all this lane added is the SENTENCE, because
    `str(SoftTimeLimitExceeded())` is the empty string and the record would
    otherwise have read `SoftTimeLimitExceeded: ` on a clerk's screen.
    """
    record = jobs.enqueue("billing.run.calculate")

    def runner(rec):
        raise _soft_time_limit_error()

    with pytest.raises(Exception):  # noqa: B017 — re-raised so Celery's retry sees it
        jobs.run_job(record["id"], runner)

    row = store.get(record["id"])
    assert row["status"] == jobs.FAILED
    assert "stopped" in row["error"] and "minutes" in row["error"]
    assert "carries on from where it stopped" in row["error"]
    assert "SoftTimeLimitExceeded" not in row["error"]


def test_cr051_tc6__the_checkpoint_survives_so_the_next_attempt_resumes(store):
    """CR-051 task 11's resume is what makes the soft limit cheap to hit.

    `fail()` writes the status and the sentence and touches nothing else, and
    `start()` admits `failed → running`. So a clerk who presses the button again
    does not pay for the 9,000 accounts the killed attempt already billed.
    """
    record = jobs.enqueue("billing.run.calculate")

    def runner(rec):
        # The real sequence, not a staged one: the run reports its place as it
        # goes, and the limit lands somewhere in the middle of that.
        jobs.record_progress(rec["id"], done=9_000, total=10_000, checkpoint={"after": "ACC-9000"})
        raise _soft_time_limit_error()

    with pytest.raises(Exception):  # noqa: B017
        jobs.run_job(record["id"], runner)

    row = store.get(record["id"])
    assert row["status"] == jobs.FAILED
    assert row["checkpoint"] == {"after": "ACC-9000"}, (
        "the checkpoint was lost, so the next attempt re-walks every account the "
        "timed-out one already billed — 22 minutes of redone work at the measured rate"
    )
    resumed = jobs.start(record["id"])
    assert resumed["status"] == jobs.RUNNING
    assert resumed["checkpoint"] == {"after": "ACC-9000"}


def test_cr051_tc7__the_sentence_is_clerk_copy_and_carries_no_internal_id():
    """`job.error` is drawn STRAIGHT onto the bill-run wizard's progress band.

    B14 rule 32 clause 4 and G28: a register id in front of a utility clerk is
    a register id on the screen. It says the three things a person needs — it
    stopped, why, and that nothing was lost — and names none of ours.
    """
    text = jobs.time_limit_error_text(_soft_time_limit_error())
    for forbidden in ("BR-", "OQ-", "DEF-", "CR-", "GT-", "SoftTimeLimit", "celery", "Celery"):
        assert forbidden not in text, f"{forbidden!r} is not something a clerk should read"
    assert text.strip() == text and len(text) < 500
    # The number comes from the setting, so the sentence and the limit agree.
    assert str(max(1, round(settings.CELERY_TASK_SOFT_TIME_LIMIT / 60))) in text


def test_cr051_tc8__an_ordinary_failure_is_untouched(store):
    """Everything that is NOT a time limit still records its own diagnosis.

    `Type: message` is often the only thing a support cycle has, and shortening
    it to be tidy would cost more than the tidiness is worth.
    """
    record = jobs.enqueue("billing.run.calculate")

    def runner(rec):
        raise RuntimeError("run blew up")

    with pytest.raises(RuntimeError):
        jobs.run_job(record["id"], runner)
    assert store.get(record["id"])["error"] == "RuntimeError: run blew up"


# ══════════════════════════════════════════════════════════════════════════
# tc9-tc10 — the two broad handlers that would have swallowed it
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr051_tc9__the_run_gauge_does_not_swallow_the_limit(monkeypatch):
    """`runs._progress` catches everything so a broken gauge never kills a run.

    It has to keep doing that AND let this one through. Caught here, the limit
    is logged as *"progress reporting failed"* and the run bills on to account
    25,000 with the worker's only warning spent.
    """
    from apps.billing import runs

    monkeypatch.setattr(runs, "calculate_account", lambda *a, **k: types.SimpleNamespace(pk="1"))
    monkeypatch.setattr(runs, "clear_break", lambda *a, **k: None)

    prepared = types.SimpleNamespace(
        ready=(types.SimpleNamespace(account_id="a1", account_no="ACC-1"),),
        service_date=None,
    )

    def gauge(done, total, account_no):
        raise _soft_time_limit_error()

    with pytest.raises(Exception) as blew_up:  # noqa: B017
        runs._calculate_run(prepared, bill_run=None, on_progress=gauge)
    assert type(blew_up.value).__name__ == "SoftTimeLimitExceeded"

    # …and an ORDINARY gauge failure is still swallowed, which is the half a
    # naive fix would have broken.
    def broken_gauge(done, total, account_no):
        raise RuntimeError("the gauge is down")

    result = runs._calculate_run(prepared, bill_run=None, on_progress=broken_gauge)
    assert result.drafted == ("1",)


def test_cr051_tc10__the_print_set_does_not_hold_the_limit_as_one_broken_bill(monkeypatch):
    """`print_set._add_one` turns any exception into a held bill — except this one.

    Drawing a page is where a print set spends nearly all of its time, so this
    handler is the single most likely place the limit lands. Held as a broken
    bill it would file the whole run's warning against one customer and print
    the other 24,999 past a limit that never fires again.
    """
    from apps.billing import customers_seam

    address = customers_seam.MailingAddress(
        account_id="a1",
        readable=True,
        line1="1408 Elm Street",
        city="Houston",
        state="TX",
        postal_code="77002",
    )
    monkeypatch.setattr(print_set.customers_seam, "print_address_for_account", lambda _id: address)

    def blows_up(invoice):
        raise _soft_time_limit_error()

    monkeypatch.setattr(print_set, "_page_for", blows_up)
    invoice = types.SimpleNamespace(
        invoice_no="BL-2608-000094",
        account_id="a1",
        account=types.SimpleNamespace(account_no="AC-2026-00001"),
    )
    result = print_set.PrintSetResult()
    with pytest.raises(Exception) as blew_up:  # noqa: B017
        print_set._add_one(invoice, None, None, {}, result)
    assert type(blew_up.value).__name__ == "SoftTimeLimitExceeded"

    # …and an ordinary render failure is STILL one held bill and not a dead set.
    monkeypatch.setattr(print_set, "_page_for", lambda _i: (_ for _ in ()).throw(ValueError("boom")))
    held = print_set._add_one(invoice, None, None, {}, print_set.PrintSetResult())
    assert held is not None and held.reason_code == print_set.HELD_DOCUMENT_REFUSED


# ══════════════════════════════════════════════════════════════════════════
# tc11 — the connection the signal interrupted
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc11__a_time_limit_releases_the_interrupted_connection(store, monkeypatch):
    """⚠ **WITHOUT THIS THE HONEST FAILURE PATH ITSELF FAILS, AND ONLY A REAL
    DATABASE SHOWS IT.**

    Celery raises the soft limit from a SIGNAL HANDLER, so it lands wherever the
    task is — and a long job is usually inside a database call. Interrupted
    there, psycopg is left with a command in flight and the next query raises
    *"another command is already in progress"*. The next query is `fail()`'s own
    `_load`, so the record stays `running` and the limit records nothing.
    Measured on a real Celery worker against real PostgreSQL on 2026-09-01;
    `10-scripts/cr051_time_limit_proof.py` is the reproducer.

    **This case can only prove the WIRING** (hard-won law 2), because the suite
    runs on in-memory SQLite, which has no such state — CLAUDE.md law 14's
    neighbour. So it asserts that the release happens, with the record's tenant,
    on a time limit and NOT on an ordinary failure.
    """
    released: list[object] = []
    monkeypatch.setattr(jobs, "release_interrupted_connection", lambda t=None: released.append(t))

    record = jobs.enqueue("billing.run.calculate")
    with pytest.raises(Exception):  # noqa: B017
        jobs.run_job(record["id"], lambda rec: (_ for _ in ()).throw(_soft_time_limit_error()))
    assert released == [TENANT], (
        "a job stopped by the time limit did not release the connection the signal "
        "interrupted, so `fail()` will raise instead of recording the failure"
    )

    released.clear()
    other = jobs.enqueue("billing.run.calculate")
    with pytest.raises(RuntimeError):
        jobs.run_job(other["id"], lambda rec: (_ for _ in ()).throw(RuntimeError("ordinary")))
    assert released == [], "an ordinary failure must not drop a healthy connection"


def test_cr051_tc11b__the_release_puts_the_tenant_back():
    """The reopened session has NO `app.tenant_id`, and under RLS that is fatal.

    `core.tenancy` sets the marker with `set_config(..., is_local := false)` —
    a SESSION setting — so it dies with the connection it was set on. Reopened
    without it, RLS FORCE returns zero rows and `fail()`'s `_load` raises
    *"unknown job"* over a row that is sitting right there. Measured the same
    afternoon, one hour after the first half of this defect.
    """
    source = Path(jobs.__file__).read_text(encoding="utf-8")
    body = source.split("def release_interrupted_connection")[1].split("\ndef ")[0]
    assert "set_current_tenant(tenant_id)" in body, (
        "the release no longer re-applies the tenant, so the reopened connection "
        "reads nothing under row-level security and the failure row is never written"
    )
    assert "release_interrupted_connection(record[\"tenant_id\"])" in source
    assert 'conn.vendor != "postgresql"' in body, (
        "the release no longer restricts itself to PostgreSQL. SQLite has no "
        "mid-command state to clear, and the SUITE'S DATABASE IS AN IN-MEMORY "
        "SQLITE CONNECTION — closing it destroys the database for every test after"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc12 — the kernel still runs where there is no Celery
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc12__no_celery_is_a_valid_deployment():
    """`core/jobs.py` must import and behave with Celery absent.

    Its own docstring and `tenant_task_class()` already depend on that, and a
    time-limit predicate that imported Celery eagerly would have broken every
    broker-less run of this suite. With no Celery there are no time-limit types,
    so `is_time_limit` is False for everything and nothing is ever re-raised —
    which is correct: without Celery nothing raises one.
    """
    saved = {name: mod for name, mod in sys.modules.items() if name.split(".")[0] == "celery"}
    try:
        for name in list(saved):
            sys.modules.pop(name, None)
        sys.modules["celery"] = None  # a failed import, not a missing one
        fresh = importlib.reload(jobs)
        fresh._time_limit_types = None
        assert fresh.time_limit_exceptions() == ()
        assert fresh.is_time_limit(RuntimeError("x")) is False
        fresh.reraise_if_time_limit(RuntimeError("x"))  # a no-op, not a crash
        assert fresh.failure_text(RuntimeError("x")) == "RuntimeError: x"
    finally:
        sys.modules.pop("celery", None)
        sys.modules.update(saved)
        importlib.reload(jobs)
        jobs._time_limit_types = None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051 task 30 (12-governance/11-change-requests.md) + BR-BIL-1030
#         (04-docs/05-modules/07-billing/02-business-rules.md) + DEF-2829
# generated: 2026-09-01 by the CR-051 task 30 / CR-053 task 14 lane
# checklist: A✔ B=n/a(no screen) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · golden-verify 33 PASS / 0 FAIL before and after —
#         nothing on this path computes money.
# exceptions: (1) NO REAL WORKER RUNS HERE. A soft time limit needs a second
#         process and a broker; the real proof is
#         10-scripts/cr051_time_limit_proof.py, exactly as the killed-worker
#         proof lives in 10-scripts/cr051_kill_and_resume.py.
#         (2) tc9 CALLS `runs._calculate_run` DIRECTLY, a private function. The
#         public `calculate_run` only wraps it in the pass cache, and the guard
#         under test is one line inside the loop; going through the public door
#         would need a full PreparedRun and a priced tenant for no more proof.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
