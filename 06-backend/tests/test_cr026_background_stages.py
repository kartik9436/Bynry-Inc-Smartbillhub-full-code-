# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 recorded ETL runner)   Change: CR-026 second
#           half (PO 2026-08-22 — *"the sizes of CSV file scan be 50,000 or
#           100,000 units or premises at a time; how you will hnadle such
#           volume in upload"*)
#           Screens: WFL-01.premises.2-4 (the stage rail), PRM-04
# Rules:    BR-MET-085 (a premises import loads premises and nothing else) ·
#           BR-MET-090 (the run's record is what it DID; the gauge is not that
#           record) · BR-MET-096 (ONE runner — every target inherits this) ·
#           BR-MET-098 (the approval bar) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 6 (idempotency)
# Journeys: the premises migration — a utility's first 431 rows
# ───────────────────────────────────────────────────────
"""THE THREE STAGES THAT MOVED INTO A WORKER, AND THE ONE PROMISE THAT DID NOT.

CR-026 measured the runner on 50,000 real rows: extract 6.8s · transform
**77.9s** · validate **50.8s** · load **101.5s**. Three of those blow any web
request timeout, so over `ASYNC_ROW_BAR` rows they are handed to a BE-07 job and
the endpoint answers 202 with a job id and a gauge to poll.

**THE FIRST TEST IN THIS FILE IS THE ONE THAT PROTECTS EVERYTHING ELSE** — a
file UNDER the bar is untouched: same call, same synchronous answer, no job
record, no gauge row. A 3-row import that answered 202 and made a screen poll
would be a product made worse, and the 79 CR-023/CR-025 tests that walk 3-row
files are the contract that says so.

**THE SECOND IS THE REGISTRATION, PROVED RED (hard-won law 7).** A job kind with
no registered body does not fail at enqueue; it fails later, in a worker, on a
file nobody is watching. With `MeteringConfig.ready()`'s three
`set_job_handler` lines removed — reproduced here by unregistering the kind
inside the test — this module reports, verbatim:

    E   core.jobs.JobsError: no handler registered for job kind
        'metering.import.transform' (the owning module registers it in
        AppConfig.ready)
    FAILED tests/test_cr026_background_stages.py::
        test_a_stage_kind_with_no_registered_body_dies_at_the_worker

which is the failure the registration exists to prevent, so the test asserts
the failure happens ONLY when the registration is taken away.

⚠ **THE BAR IS PATCHED DOWN, NEVER MEASURED UP.** Every deferral case here
patches `ASYNC_ROW_BAR` to 2 and walks a 3-row file. Writing a 5,001-row fixture
would buy nothing this cannot say and would cost the suite ten minutes — the
bar's VALUE is a ratified figure (decision log 2026-08-22, asserted below by
`test_the_ratified_async_bar_is_5000_rows`), and its BEHAVIOUR is what these
cases are about.

⚠ **`IMPORT_PROGRESS_ISOLATED=False` IS SET PER TEST AND IS NOT COSMETIC.** In
production the gauge is written on a second, autocommit connection so a poller
can read it WHILE the stage holds its row lock; a second connection would write
outside the test's transaction and leak rows into the next test. The setting is
the documented single-connection posture (`import_progress`'s docstring), and it
writes the same row through the ORM — so what these tests assert is the shape
and the arithmetic of the gauge, which is all a screen reads.
"""

import pytest
from django.test import override_settings

from apps.metering import api as metering_api
from apps.metering import import_progress, import_runs, models
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import errors
from core import jobs as core_jobs

from tests.test_cr023_import_stages import ALL_ON, MAPPING
from tests.test_cr023_load_stage import _file
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    marcus,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: What `ASYNC_ROW_BAR` is patched to when a case needs a 3-row file to be
#: "big". Two, so the same fixture serves both sides of the bar.
TINY_BAR = 2

#: Every gauge test runs on the caller's own connection — see the docstring.
GAUGE_IN_TEST = override_settings(IMPORT_PROGRESS_ISOLATED=False)


class _CapturedDispatch:
    """The BE-07 transport, replaced by a recorder for the length of one test.

    With `JOBS_EAGER` on (local, dev, demo) the body runs INSIDE the enqueue, so
    a test can never see the queued state it is trying to assert; with it off
    the real dispatcher hands the record to Celery and a broker we do not want
    a unit test to depend on. Both are wrong here, so the dispatcher is swapped
    for one that records — the production one is put back in `__exit__`,
    including when the test fails, because a leaked dispatcher would silently
    stop every later test in the session from running its jobs.
    """

    def __init__(self) -> None:
        self.records: list[dict] = []

    def __enter__(self) -> "_CapturedDispatch":
        core_jobs.set_job_dispatcher(self.records.append)
        return self

    def __exit__(self, *exc_info: object) -> None:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)


def _extracted(actor, rows: int = 3, *, bad: int = 0) -> str:
    """A run at stage 1, through the real extract — never a hand-built row."""
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "silvercreek_premises_2026.csv",
            "content": _file(rows, bad=bad),
            "session_ref": "sess_2b41",
            "ip": "71.42.108.14",
        },
    )
    return run["id"]


def _transformed(actor, rows: int = 3, *, bad: int = 0) -> str:
    run_id = _extracted(actor, rows, bad=bad)
    import_runs.transform(actor, run_id, {"mapping": MAPPING, "row_handling": ALL_ON})
    return run_id


def _validated(actor, rows: int = 3, *, bad: int = 0) -> str:
    run_id = _transformed(actor, rows, bad=bad)
    import_runs.validate(actor, run_id)
    return run_id


def _stage_jobs() -> int:
    """Import-stage jobs only.

    ⚠ **A PROVISIONED TENANT ALREADY HAS A JOB** — `BR-TEN-063`'s sample-data
    plant is enqueued the moment the tenant exists, so a bare `Job.objects.
    count()` here would be counting somebody else's work and would report a
    small import as having deferred something.
    """
    return tenancy_models.Job.objects.filter(kind__in=import_runs.STAGE_JOBS.values()).count()


def _lower_the_bar(monkeypatch) -> None:
    """Make a 3-row file "big" — see the module docstring.

    ⚠ **CALL IT AFTER THE FIXTURE IS BUILT, NEVER BEFORE.** Every stage reads
    the same bar, so lowering it first defers the SETUP stages too: the run then
    sits where stage 1 left it, the stage the case names is never reached, and
    the assertions pass or fail for a reason that has nothing to do with them.
    That is how the first draft of this file went red.
    """
    monkeypatch.setattr(import_runs, "ASYNC_ROW_BAR", TINY_BAR)


def _premises() -> int:
    """⚠ **THE TENANT ARRIVES WITH PREMISES ALREADY IN IT** — `BR-TEN-013`'s
    sample-data plant runs as part of provisioning (44 rows), so every count
    here is a DELTA. An absolute `== 3` reads as a clean assertion and is
    actually asserting how much sample data a fixture happens to seed."""
    return models.Premises.objects.count()


def _status(run_id) -> str:
    return models.ImportRun.objects.get(pk=run_id).status


def _gauge(run_id) -> dict | None:
    return import_progress.read(models.ImportRun.objects.get(pk=run_id))


# ═══════════════════════════════════════════════════════════════════════════
# THE PROMISE THAT DID NOT CHANGE
# ═══════════════════════════════════════════════════════════════════════════


@GAUGE_IN_TEST
def test_a_file_UNDER_the_bar_is_completely_unchanged(brazos, marcus):
    """The contract the other 79 import tests rest on: a 3-row file answers
    synchronously, with no `deferred` flag, no job record and no gauge row.

    ⚠ This is the case that fails first if anyone lowers `ASYNC_ROW_BAR` — and
    it asserts the ABSENCE of three things, because "a small import still
    works" is not the claim; "a small import is not touched" is.
    """
    with tenant_ctx(brazos):
        run_id = _extracted(marcus, 3)
        answer = import_runs.transform(marcus, run_id, {"mapping": MAPPING, "row_handling": ALL_ON})
        assert "deferred" not in answer
        assert answer["counts"]["in"] == 3
        assert answer["progress"] is None

        checked = import_runs.validate(marcus, run_id)
        assert "deferred" not in checked
        assert checked["status"] == "validated"

        before = _premises()
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert "deferred" not in receipt
        assert receipt["receipt"]["loaded"] == 3
        assert _premises() - before == 3

        assert _stage_jobs() == 0, "a small import enqueued a job"
        assert models.ImportRunProgress.objects.count() == 0, "a small import wrote a gauge"


def test_the_ratified_async_bar_is_5000_rows():
    """The figure the PO was shown (decision log 2026-08-22): *at 5,000 rows the
    slowest stage is 5,000 x 2.03 ms = 10.2s, inside a 30s gateway timeout with
    3x margin; the 5,001st row goes to a worker.* A test asserts the ratified
    number so drift goes RED rather than quiet."""
    assert import_runs.ASYNC_ROW_BAR == 5_000


# ═══════════════════════════════════════════════════════════════════════════
# THE REGISTRATION — the half that only fails in a worker
# ═══════════════════════════════════════════════════════════════════════════


def test_every_stage_kind_has_its_body_registered():
    """`MeteringConfig.ready()` registers all three. Nothing else in this repo
    checks that a kind an endpoint enqueues is a kind a worker can run."""
    assert core_jobs.job_handler(import_runs.TRANSFORM_JOB) is import_runs.run_transform_job
    assert core_jobs.job_handler(import_runs.VALIDATE_JOB) is import_runs.run_validate_job
    assert core_jobs.job_handler(import_runs.LOAD_JOB) is import_runs.run_load_job
    assert set(import_runs.STAGE_JOBS) == {"transform", "validate", "load"}


@GAUGE_IN_TEST
def test_a_stage_kind_with_no_registered_body_dies_at_the_worker(brazos, marcus, monkeypatch):
    """The RED proof of the test above (hard-won law 7): with the registration
    taken away the enqueue still succeeds — it is the WORKER that fails, later,
    on a file nobody is watching. The failure text is quoted in this module's
    docstring."""
    with tenant_ctx(brazos):
        run_id = _extracted(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch():
            answer = import_runs.transform(
                marcus, run_id, {"mapping": MAPPING, "row_handling": ALL_ON}
            )
            job_id = answer["job_id"]
        core_jobs.set_job_handler(import_runs.TRANSFORM_JOB, None)
        try:
            with pytest.raises(core_jobs.JobsError) as raised:
                core_jobs.run_pending(job_id)
            assert "no handler registered" in str(raised.value)
        finally:
            core_jobs.set_job_handler(import_runs.TRANSFORM_JOB, import_runs.run_transform_job)
        # …and with it back, the very same record runs to completion.
        core_jobs.run_pending(job_id)
        assert _status(run_id) == "transformed"


# ═══════════════════════════════════════════════════════════════════════════
# THE DEFERRAL, AND THE GAUGE A SCREEN POLLS
# ═══════════════════════════════════════════════════════════════════════════


@GAUGE_IN_TEST
def test_over_the_bar_transform_is_enqueued_and_the_gauge_says_queued(brazos, marcus, monkeypatch):
    """The 202 answer carries the run, the job id and where to poll (B12 r1 §3),
    and the gauge already says `queued` — because a screen cannot tell an empty
    gauge from *"nothing is happening"*."""
    with tenant_ctx(brazos):
        run_id = _extracted(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch() as dispatched:
            answer = import_runs.transform(
                marcus, run_id, {"mapping": MAPPING, "row_handling": ALL_ON}
            )

        assert answer["deferred"] is True
        assert answer["stage"] == "transform"
        assert answer["status_url"] == f"/api/jobs/{answer['job_id']}"
        assert len(dispatched.records) == 1
        assert dispatched.records[0]["kind"] == import_runs.TRANSFORM_JOB

        # NOTHING has run yet: the run is where stage 1 left it.
        assert _status(run_id) == "extracted"
        gauge = answer["progress"]
        assert gauge["state"] == "queued"
        assert (gauge["stage"], gauge["done"], gauge["total"]) == ("transform", 0, 3)
        assert gauge["job_id"] == answer["job_id"]

        # …then the worker runs it, and the same poll surface says so.
        core_jobs.run_pending(answer["job_id"])
        assert _status(run_id) == "transformed"
        finished = _gauge(run_id)
        assert (finished["state"], finished["done"], finished["pct"]) == ("done", 3, 100)


@GAUGE_IN_TEST
def test_validate_defers_the_same_way_and_reports_which_rule_it_is_on(brazos, marcus, monkeypatch):
    """Stage 3's gauge counts ROWS but its message names the RULE — *"Checking
    rule 4 of 11"* — because every rule walks every row and a bare fraction
    would tell an operator nothing about where the stage really is."""
    with tenant_ctx(brazos):
        run_id = _transformed(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch():
            answer = import_runs.validate(marcus, run_id)
        assert answer["deferred"] is True
        assert answer["stage"] == "validate"
        assert _status(run_id) == "transformed"

        core_jobs.run_pending(answer["job_id"])
        assert _status(run_id) == "validated"
        gauge = _gauge(run_id)
        assert (gauge["stage"], gauge["state"], gauge["done"]) == ("validate", "done", 3)


@GAUGE_IN_TEST
def test_a_second_click_folds_into_the_job_already_running(brazos, marcus, monkeypatch):
    """NFR-16 through `core.jobs`' scope key (`import:<stage>:<run>`): a
    double-clicked *Validate* joins the walk already under way rather than
    starting a second one over the same 100,000 rows."""
    with tenant_ctx(brazos):
        run_id = _transformed(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch():
            first = import_runs.validate(marcus, run_id)
            second = import_runs.validate(marcus, run_id)
        assert second["job_id"] == first["job_id"]
        assert _stage_jobs() == 1


@GAUGE_IN_TEST
def test_a_failed_stage_says_so_in_english_and_leaves_the_run_where_it_was(
    brazos, marcus, monkeypatch
):
    """The gauge is the only place a worker failure is explained where the
    IMPORT screen is already looking. The RUN's own status is untouched: a
    transform that died leaves the run `extracted`, which is what it is, and
    the operator may retry it."""
    with tenant_ctx(brazos):
        run_id = _extracted(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch():
            answer = import_runs.transform(
                marcus, run_id, {"mapping": MAPPING, "row_handling": ALL_ON}
            )

        def _explode(*args, **kwargs):
            raise RuntimeError("the database went away")

        monkeypatch.setattr(import_runs, "_transform_apply", _explode)
        with pytest.raises(RuntimeError):
            core_jobs.run_pending(answer["job_id"])

        gauge = _gauge(run_id)
        assert gauge["state"] == "failed"
        assert gauge["message"] == "RuntimeError: the database went away"
        assert _status(run_id) == "extracted"


@GAUGE_IN_TEST
def test_the_gauge_throttles_itself_to_one_write_per_1000_rows(brazos, marcus):
    """~100 UPDATEs against 100 seconds of work at 100,000 rows. A gauge that
    wrote per row would become the bottleneck it measures, so `step()` may be
    called as often as the caller likes — including once per row."""
    with tenant_ctx(brazos):
        run = models.ImportRun.objects.get(pk=_extracted(marcus, 3))
        reporter = import_progress.Reporter(
            tenant_id=run.tenant_id, run_id=run.id, stage="transform", total=100_000
        )
        reporter.start()
        for done in range(1, import_progress.ROWS_PER_WRITE):
            reporter.step(done)
        assert _gauge(run.id)["done"] == 0, "the throttle let a sub-1000-row step through"

        reporter.step(import_progress.ROWS_PER_WRITE)
        assert _gauge(run.id)["done"] == import_progress.ROWS_PER_WRITE

        # A MILESTONE is never throttled — a message that arrives late is a
        # screen lying about which half of a stage it is in.
        reporter.mark(import_progress.ROWS_PER_WRITE + 1, "Saving the mapped rows")
        assert _gauge(run.id)["message"] == "Saving the mapped rows"


# ═══════════════════════════════════════════════════════════════════════════
# THE LOAD — deferred, and every semantic CR-026 promised not to change
# ═══════════════════════════════════════════════════════════════════════════


@GAUGE_IN_TEST
@override_settings(JOBS_EAGER=True)
def test_over_the_bar_the_load_runs_in_a_worker_and_writes_exactly_what_it_did_before(
    brazos, marcus, monkeypatch
):
    """BR-MET-085 and the receipt, unchanged by the stage having moved: the same
    3 premises, the same recorded figures, and a 30-day rollback point.

    Run with `JOBS_EAGER` on — the demo/dev posture, where the body runs inside
    the enqueue — because that is the path a walkthrough takes and the one where
    a mistake in `_defer`'s own bookkeeping (writing `queued` OVER a finished
    gauge) would show.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, 3)
        before = _premises()
        _lower_the_bar(monkeypatch)
        answer = import_runs.load(marcus, run_id, {"write_mode": "insert"})

        assert answer["deferred"] is True
        assert answer["stage"] == "load"
        # Eager dispatch already ran it, so the gauge must read `done` — never
        # the `queued` the endpoint would have written for a real worker.
        assert _status(run_id) == "loaded"
        assert _gauge(run_id)["state"] == "done"
        assert _premises() - before == 3

        run = models.ImportRun.objects.get(pk=run_id)
        paper = import_runs.receipt(run)["receipt"]
        assert paper["loaded"] == 3
        assert paper["rollback_point"]["status"] == "available"


@GAUGE_IN_TEST
@override_settings(JOBS_EAGER=True)
def test_a_second_commit_answers_the_receipt_and_NEVER_defers(brazos, marcus, monkeypatch):
    """Hard rule 6, and the reason the already-loaded case is decided on the
    call rather than deferred: a receipt delivered by a poll nobody started is
    that guarantee broken by a technicality."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, 3)
        before = _premises()
        _lower_the_bar(monkeypatch)
        import_runs.load(marcus, run_id, {"write_mode": "insert"})
        again = import_runs.load(marcus, run_id, {"write_mode": "insert"})

        assert "deferred" not in again
        assert again["receipt"]["loaded"] == 3
        assert _premises() - before == 3, "the second commit loaded the file twice"
        assert _stage_jobs() == 1, "the second commit enqueued a job"


@GAUGE_IN_TEST
def test_the_approval_refusal_reaches_the_caller_on_the_call_it_made(brazos, marcus, monkeypatch):
    """BR-MET-098 over the bar: 3 rejects in 6 rows is 50%, past both bars, so
    the commit is refused BEFORE anything is enqueued — the operator is told
    on the call, exactly as they are today, and no job exists to poll."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, 6, bad=3)
        before = _premises()
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch() as dispatched, pytest.raises(errors.BizError) as raised:
            import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert raised.value.br_ref == "BR-MET-098"
        assert dispatched.records == []
        assert _premises() == before, "a refused commit wrote rows"


@GAUGE_IN_TEST
def test_a_committed_run_is_refused_before_it_is_deferred(brazos, marcus, monkeypatch):
    """BR-MET-090 — a committed run's rehearsal is closed, and a 202 that
    resolves to *"this run is closed"* is a refusal delivered by poll, which is
    not a refusal anyone reads. Taken on the unlocked read, before the bar."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, 3)
        import_runs.load(marcus, run_id, {"write_mode": "insert"})
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch() as dispatched, pytest.raises(errors.BizError):
            import_runs.validate(marcus, run_id)
        assert dispatched.records == []


# ═══════════════════════════════════════════════════════════════════════════
# THE API — 202 vs 200, and the surface a screen polls
# ═══════════════════════════════════════════════════════════════════════════


@GAUGE_IN_TEST
def test_the_endpoint_answers_200_under_the_bar_and_202_over_it(brazos, marcus, monkeypatch):
    """B12 r1 §3. The status code follows the ENGINE's `deferred` flag, so the
    API layer never forms its own opinion about how big is big."""
    with tenant_ctx(brazos):
        small = _extracted(marcus, 3)
    body = {"mapping": MAPPING, "row_handling": ALL_ON}
    answered = api_call(
        metering_api.import_transform,
        "post",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        data=body,
        run_id=small,
    )
    assert answered.status_code == 200

    with tenant_ctx(brazos):
        big = _extracted(marcus, 3)
    _lower_the_bar(monkeypatch)
    with _CapturedDispatch():
        deferred = api_call(
            metering_api.import_transform,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data=body,
            run_id=big,
        )
        assert deferred.status_code == 202
        assert deferred.data["deferred"] is True
        assert deferred.data["job_id"]


@GAUGE_IN_TEST
def test_the_poll_surface_serves_the_run_its_rules_and_its_gauge(brazos, marcus, monkeypatch):
    """`GET /imports/{id}` — *"Validating… 2 of 3"* in one payload, so a screen
    polls one URL rather than joining two. A READ: it writes nothing, because a
    screen asking *"how far?"* every two seconds is not an event."""
    with tenant_ctx(brazos):
        run_id = _transformed(marcus, 3)
        _lower_the_bar(monkeypatch)
        with _CapturedDispatch():
            import_runs.validate(marcus, run_id)

    answered = api_call(
        metering_api.import_run_detail,
        "get",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        run_id=run_id,
    )
    assert answered.status_code == 200
    assert answered.data["id"] == str(run_id)
    assert answered.data["counts"]["in"] == 3
    assert "rules" in answered.data
    gauge = answered.data["progress"]
    assert (gauge["stage"], gauge["state"], gauge["total"]) == ("validate", "queued", 3)


@GAUGE_IN_TEST
def test_the_poll_surface_answers_a_synchronous_run_with_no_gauge_at_all(brazos, marcus):
    """`progress: None`, served rather than omitted: a client that has to tell
    *"no gauge"* from *"key missing"* is a client two people will implement two
    ways."""
    with tenant_ctx(brazos):
        run_id = _transformed(marcus, 3)
    answered = api_call(
        metering_api.import_run_detail,
        "get",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        run_id=run_id,
    )
    assert answered.status_code == 200
    assert answered.data["progress"] is None
