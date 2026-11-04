# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 findings) · US-BIL-004 (phase 2 calculate + phase
#           3 breaks) · US-BIL-005 (phase 5 issue)   Screens: S31 steps 2, 4, 6
# Rules:    BR-BIL-051 (phase 2 and the release are BACKGROUND batches; the
#           clerk is not held at the screen and closing the browser loses
#           nothing) · BR-BIL-052 (per-account, restartable, resumable) ·
#           BR-BIL-053 (the break list names the STAGE that failed; *"the run
#           cannot enter phase 4 with an unresolved break row"*) · BR-BIL-055
#           (a break never blocks the run) · BR-BIL-023 (a re-run REPLACES a
#           draft) · CLAUDE.md hard rule 6 (idempotency: a job that runs twice
#           must not bill twice) · hard rule 1 (tenant scoping) · BR-TEN-043
#           (event time is an argument — a worker reads no clock)
# ───────────────────────────────────────────────────────
"""CR-051 W0/W1/W2 — the background worker, the durable break list, the gauge.

WHAT THIS FILE PROVES, and the order is the order the CR asks for:

  tc1   the two stale sentences are gone, and the things they said were
        impossible are registered
  tc2   `POST .../calculate` with `background: true` answers **202** with a job
        id and the poll address `/api/jobs/{id}`
  tc3   the job body writes `done`/`total` on the JOB RECORD as it goes
  tc4   an account that cannot be billed gets a `bill_run_breaks` ROW with its
        reason and its stage
  tc5   the break list SURVIVES — a fresh request, with no calculate in it,
        serves the same rows
  tc6   **idempotency**: the same run calculated twice does not double-bill and
        does not double-file the break
  tc7   a break that a later pass drafts is CLOSED, so the run can enter phase 4
  tc8   `GET /billing/runs/{id}` serves the phase, the scope, the decisions and
        the counts
  tc9   `background: true` with nothing to run the job falls back to INLINE and
        says so, rather than queueing into a void (law 3 / DEF-2487)
  tc10  the findings job records COUNTS on the run and does not cache the lists
  tc11  a second click while a job is active folds into the SAME job (NFR-16)

⚠ **tc12 AND tc13 ARE THE LAW-14 CASES AND THEY ARE THE REASON THIS FILE HAS AN
`isolation` MARK.** `config/settings/test.py` hardcodes in-memory SQLite, which
has NO aborted-transaction state, so a break-writing loop with the savepoint
REMOVED passes every case above, green, on every machine. Those two run against
real PostgreSQL and are the only place the savepoint is actually proved.

Run them:  DJANGO_SETTINGS_MODULE=config.settings.local pytest -m isolation \\
           tests/test_cr051_run_jobs_and_breaks.py --reuse-db

⚠ **TWO HARNESS FACTS THAT COST THIS LANE AN HOUR EACH — WRITTEN DOWN SO THE
NEXT ONE PAYS NEITHER.**

1. **`api_call` and `core.jobs.run_pending` both CLEAR the tenant context on
   the way out — they do not restore it.** `core.tenancy.tenant_context` says
   so in as many words (*"Context is cleared on exit even on error — a job can
   never carry one tenant's context into the next tenant's loop iteration"*),
   which is exactly right for a worker and surprising in a test. So a case that
   does `with tenant_ctx(t): … api_call(…) … more ORM …` runs the ORM after it
   with NO tenant set. On PostgreSQL that is refused by RLS; **on the SQLite
   suite it silently reads and writes rows nothing can see afterwards**, and
   what you get is an assertion about a count that is quietly zero. Every case
   below keeps api_call and `run_pending` OUT of the block whose ORM follows
   them.
2. **A run needs its own `bill_date`** — see `a_run`.
"""

import uuid

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import run_jobs, run_resume
from apps.billing import runs as billing_runs
from apps.tenancy import models as tenancy_models
from core import jobs as core_jobs

from tests.isolation_helpers import (
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
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
)

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — a run with one billable account and one that breaks
# ══════════════════════════════════════════════════════════════════════════
def a_run(tenant, cycle, key="2026-06|cr051"):
    """A run carrying the CLERK'S TYPED BILL DATE (BR-BIL-070, OQ-122).

    ⚠ **THE `bill_date` IS NOT DECORATION AND LEAVING IT OFF COSTS AN HOUR.**
    `runs.calculate_run` is handed a `service_date` by its caller, so a direct
    call works without one — but the JOB path goes through
    `selectors.prepared_for(run)`, which derives the service date from the run
    and then the cycle and REFUSES when neither has one rather than reaching for
    a clock (BR-TEN-043 / G6). Every case below that runs through a job needs
    this; the ones that call the engine directly do not, which is exactly how a
    missing date hides.
    """
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=SERVICE_DATE,
        idempotency_key=key,
    )


def prepared_for(cycle):
    return billing_runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )


def a_world(tenant, actor, *, with_a_break=True):
    """One account that bills and (optionally) one whose read never arrived.

    The breaking account is `consumption=None` — a unit whose electric read did
    not come in — which reaches phase 2 (BR-BIL-015 keeps it in the run) and
    breaks at `measure-consumption`. That is the commonest real break and the
    one BR-BIL-040 exists to name.
    """
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    good = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9001", label="Good")
    an_account(tenant, good["id"], "ACC-9001")
    if with_a_break:
        bad = a_billed_unit(
            actor, tenant, cycle, plan, asset_no="M-9002", label="Bad", consumption=None,
            # DEF-BIL-8583 / DEF-BIL-8671: read in May, missed in June. A meter
            # NEVER read has no multiplier since R3 + R4 went live (e998f92b1)
            # and is held at prepare, so it never reached phase 2 and the run
            # counted 1 of 1. See `a_billed_unit`'s docstring.
            read_last_month=True,
        )
        an_account(tenant, bad["id"], "ACC-9002")
    return cycle


def a_world_that_breaks_in_the_job(tenant, actor, monkeypatch):
    """One account that bills and one that breaks INSIDE the calculate job.

    ⚠ **`DEF-BIL-8695` (2026-10-01) — WHY tc3 AND tc6 CANNOT USE `a_world`.**
    `a_world`'s breaking account is a MISSING READ, and since `12760474d`
    (`DEF-BIL-8650`/`8653`, 2026-10-01) a missing read is MUST-ANSWER on the
    Check: the job does not price an account carrying an unanswered decision,
    it leaves it waiting, so the job counted 1 of 1 and filed no break. That is
    the ruled behaviour. The direct `calculate_run` cases (tc4, tc5, tc14) still
    exercise the read break, because they hand the engine the prepared list
    themselves.

    **AND THE CHECK NOW SEES ALMOST EVERY OTHER BREAK TOO, ON PURPOSE.** It runs
    the same ruled path Calculate does, so a capacity service with no count, a
    size the schedule does not price or a rating refusal is BLOCKED at prepare
    and never reaches the job (tried first: a trash account with its cart count
    unobtainable is `ruled_path_refused` at prepare). What still breaks inside
    the job is a fact that moved between the Check and Calculate — the
    reading withdrawn, the cart removed — and no fixture can stage that race
    through the public path.

    So ACC-9002 is an ordinary, fully read account that passes the Check, and
    `calculate_account` refuses it at Calculate with BR-RAT-090's own reason
    (`unmetered_asset_count_undetermined`). What tc3 and tc6 prove is the JOB's
    half — the gauge counts the account that breaks, and a second job UPSERTS
    the one break row rather than appending or swallowing it — and that half
    runs unpatched: the real job, the real loop, the real `record_break`.
    """
    from apps.billing import gather as billing_gather

    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    good = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9001", label="Good")
    an_account(tenant, good["id"], "ACC-9001")
    bad = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9002", label="Bad")
    an_account(tenant, bad["id"], "ACC-9002")

    real = billing_runs.calculate_account

    def calculate_account(data, *args, **kwargs):
        if data.account_no == "ACC-9002":
            raise billing_gather.GatherProblem(
                billing_runs.CALC_ASSET_COUNT_UNAVAILABLE,
                "account ACC-9002: the cart count could not be determined at Calculate.",
            )
        return real(data, *args, **kwargs)

    monkeypatch.setattr(billing_runs, "calculate_account", calculate_account)
    return cycle


class _RecordingStore:
    """A BE-07 store backed by a dict — the shape `core.jobs` duck-types.

    The live `apps.tenancy.services.JobStore` writes the `jobs` table and works
    perfectly here; this one is used where a case needs to READ every save the
    kernel made (tc3's gauge), which a table read cannot show — it only shows
    the last one.
    """

    def __init__(self):
        self.records = {}
        self.saves = []

    def save(self, record):
        self.records[record["id"]] = dict(record)
        self.saves.append(dict(record))

    def get(self, job_id):
        found = self.records.get(str(job_id))
        return dict(found) if found else None

    def find_active(self, tenant_id, kind, scope_key):
        for record in self.records.values():
            if (
                str(record["tenant_id"]) == str(tenant_id)
                and record["kind"] == kind
                and record["scope_key"] == scope_key
                and record["status"] in core_jobs.ACTIVE_STATUSES
            ):
                return dict(record)
        return None


@pytest.fixture()
def recording_store():
    """Swap the registered store for a recording one, and put it back."""
    previous = core_jobs._store  # noqa: SLF001 — the kernel's registration point
    store = _RecordingStore()
    core_jobs.set_job_store(store)
    yield store
    core_jobs.set_job_store(previous)


@pytest.fixture()
def live_store():
    """The real `jobs` table, as `apps.tenancy` registers it in production."""
    from apps.tenancy import services as tenancy_services

    previous = core_jobs._store  # noqa: SLF001
    core_jobs.set_job_store(tenancy_services.JobStore())
    yield
    core_jobs.set_job_store(previous)


def calculate(tenant, run, *, background=False, user=None):
    body = {"background": True} if background else {}
    return api_call(
        billing_api.run_calculate,
        "post",
        user=user or FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        data=body,
    )


def breaks_of(tenant, run, *, resolved=None):
    return api_call(
        billing_api.run_breaks,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        query={"f.resolved": resolved} if resolved else None,
    )


def run_detail(tenant, run):
    return api_call(
        billing_api.run_item,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
    )


# ══════════════════════════════════════════════════════════════════════════
# tc1 — CR-051 task 4: the two sentences that said a worker cannot exist
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc1__the_stale_absences_are_no_longer_claimed_and_the_jobs_are_registered():
    """The claims are corrected AND the capability they denied exists.

    ⚠ **THE SERVED CLAIMS ARE WHAT IS ASSERTED, NOT THE COMMENT TEXT, AND THE
    FIRST DRAFT OF THIS CASE GOT THAT WRONG.** It grepped `apps/billing/api.py`
    for the sentence *"a promise of asynchrony this deployment does not keep"*
    and went red — on the CORRECTION, which quotes the old sentence in order to
    strike it. A test that cannot tell a retraction from the claim it retracts
    is worse than no test, because it pushes the next lane into deleting the
    history instead of correcting it.

    So what is asserted is what a CALLER can actually observe: the three
    `unavailable` codes that told every client these things were impossible are
    gone from the served envelopes, and the three job kinds are registered.

    ⚠ **BOTH HALVES, DELIBERATELY.** Asserting only that the codes are gone
    would pass on a lane that deleted them and built nothing — hard-won law 1
    turned inside out. A corrected comment with no registered handler is the
    same defect wearing the other face.
    """
    retracted = {
        "calculate_is_not_a_background_batch",
        "the_break_list_is_returned_and_not_stored",
        "release_is_not_a_background_batch",
    }
    served = {
        entry["code"]
        for group in (billing_api.CALCULATE_UNAVAILABLE, billing_api.RELEASE_UNAVAILABLE)
        for entry in group
    }
    assert not (
        served & retracted
    ), f"still telling callers these are impossible: {served & retracted}"

    # And `core/jobs.py`'s own claim, which is a docstring and has no envelope:
    # the correction must NAME what replaced it, or it is a deletion.
    assert "is still unbuilt" not in core_jobs.__doc__.split("⚠ **THIS PARAGRAPH SAID")[0]
    assert "CR-017 built the\n  worker half" in core_jobs.__doc__

    # The capability the sentences denied: three registered kinds, from the
    # module that owns the work (core/jobs.py's contract).
    for kind in run_jobs.RUN_JOBS:
        assert core_jobs.job_handler(kind) is not None, f"{kind} has no registered body"
    assert core_jobs.job_handler(run_jobs.CALCULATE_JOB) is run_jobs.run_calculate_job
    assert core_jobs.job_handler(run_jobs.FINDINGS_JOB) is run_jobs.run_findings_job
    assert core_jobs.job_handler(run_jobs.ISSUE_JOB) is run_jobs.run_issue_job


# ══════════════════════════════════════════════════════════════════════════
# tc1b — CR-051 task 4, THE HALF tc1 COULD NOT SEE
# ══════════════════════════════════════════════════════════════════════════
#: Every module in `apps/billing` that publishes served "what this cannot do"
#: entries. Listed rather than star-imported so a new one is a deliberate add.
_SERVED_CLAIM_MODULES = (
    "apps.billing.api",
    "apps.billing.issue",
    "apps.billing.release",
    "apps.billing.documents",
    "apps.billing.runs",
    "apps.billing.decisions",
    "apps.billing.pending",
    "apps.billing.selectors",
)

#: Phrases that assert an ABSENCE which no longer exists. Matched against the
#: text a CALLER receives, never against source, so a retraction that quotes the
#: old sentence in a comment cannot be mistaken for the claim it retracts —
#: which is the exact way tc1's first draft went red on the correction.
_EXPIRED_ABSENCES = (
    "There is no worker on this deployment",
    "no worker on this deployment",
    "celery` is a declared dependency with zero",
    "the worker half is still unbuilt",
    "there is no background batch",
)


def _served_claim_entries():
    """Every `{"code": …, "detail": …}` a billing module serves, discovered.

    ⚠ **DISCOVERED RATHER THAN LISTED, AND THAT IS THE WHOLE POINT OF THIS
    CASE.** tc1 above names TWO tuples by hand — `api.CALCULATE_UNAVAILABLE`
    and `api.RELEASE_UNAVAILABLE` — and passed on 2026-08-30 while a THIRD copy
    of the same retracted sentence went on being served to every caller from
    `release.RELEASE_HANDOFFS`, in a different module, for a further day. A
    hand-written list of the places to look is a check that cannot fail for any
    place somebody forgot to add, and forgetting is the failure mode.
    """
    import importlib

    out = []
    for name in _SERVED_CLAIM_MODULES:
        module = importlib.import_module(name)
        for attr in dir(module):
            value = getattr(module, attr, None)
            if not isinstance(value, tuple) or not value:
                continue
            if not all(isinstance(item, dict) and "code" in item for item in value):
                continue
            for item in value:
                out.append((f"{name}.{attr}", item))
    return out


def test_cr051_tc1b__no_billing_module_still_serves_an_absence_that_has_expired():
    """A worker exists. No served sentence anywhere in billing may say otherwise.

    ⚠ **THIS CASE EXISTS BECAUSE tc1 PASSED OVER THE DEFECT IT WAS WRITTEN FOR.**
    CR-051 task 4 named two files. The retracted sentence *"There is no worker on
    this deployment: `celery` is a declared dependency with zero `tasks.py`"* was
    corrected in both of `apps/billing/api.py`'s tuples on 2026-08-30 — and the
    same words, in `apps/billing/release.RELEASE_HANDOFFS`, were **served on the
    response of every single release** until 2026-08-31, because nothing looked
    outside the two tuples somebody had thought of.

    That is hard-won law 1 in its most expensive form: not a comment claiming a
    guarantee, but a SERVED sentence telling every caller a capability does not
    exist. `selectors.release_outcome_dict` puts it on the wire; a client reading
    it would build around a worker that has been running since 2026-08-19.

    So this asserts over EVERY served claim tuple this module publishes, found by
    walking the modules rather than by naming the tuples — and it is the absence
    of the phrase in SERVED text that is checked, so the corrections above, which
    quote the old sentence in order to strike it, cannot make it go red.
    """
    entries = _served_claim_entries()
    # A discovery walk that discovers nothing is a check that cannot fail.
    assert len(entries) >= 10, f"only {len(entries)} served claim(s) found — the walk is broken"

    offenders = [
        (where, entry["code"], phrase)
        for where, entry in entries
        for phrase in _EXPIRED_ABSENCES
        if phrase in str(entry.get("detail", ""))
    ]
    assert not offenders, (
        "a billing module still SERVES an absence that expired on 2026-08-19, when "
        f"CR-017 landed the worker: {offenders}"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc2 — CR-051 task 8: 202 + the poll address the framework already serves
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc2__calculate_answers_202_with_a_job_id_and_a_poll_address(
    brazos, dana, live_store
):
    """BR-BIL-051's background half, and B12 r1's accept contract.

    The 202 carries the job id and `status_url` and NOTHING about status, which
    is the contract's own shape: status truth lives at the poll endpoint, and a
    second copy in the accept response is a second thing to go stale.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        response = calculate(brazos, run, background=True)

    assert response.status_code == 202
    body = response.data
    assert body["background"] is True
    assert body["bill_run_id"] == str(run.pk)
    assert body["status_url"] == f"/api/jobs/{body['job_id']}"
    # The record is REAL — a 202 promising a poll URL with no row behind it is
    # the lie `core.jobs.enqueue` refuses to tell.
    with tenant_ctx(brazos):
        record = core_jobs._store.get(body["job_id"])  # noqa: SLF001
    assert record["kind"] == run_jobs.CALCULATE_JOB
    assert record["scope_key"] == f"billing:calculate:{run.pk}"
    assert record["status"] == core_jobs.QUEUED


# ══════════════════════════════════════════════════════════════════════════
# tc3 — CR-051 task 10: `done` and `total` on the job record
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc3__the_calculate_job_writes_done_and_total_on_the_record(
    brazos, dana, recording_store, monkeypatch
):
    """NFR-4's gauge — and the DENOMINATOR counts the ones that will break.

    *"412 of 1,124"* is only honest if the 1,124 counts the two that break, so
    `total` is every account the pass touches and `done` reaches it exactly.

    ⚠ **AMENDED 2026-08-31 (CR-051 task 11), NOT DELETED, AND THE SUPERSESSION
    IS QUOTED.** This case asserted `final["checkpoint"] == {"done": 2}` — the
    count-shaped marker task 10 wrote, whose own docstring said in as many
    words: *"⚠ THE CHECKPOINT IS THE COUNT, NOT A CURSOR … CR-051 task 11 is
    the real checkpoint and is not this lane's."* Task 11 is now built
    (`apps/billing/run_resume.py`) and the CALCULATE marker carries the cursor a
    resumed worker reads, so the old literal is the previous contract rather
    than a broken one.

    The assertion below is deliberately about the CONTRACT and not the literal:
    the gauge still reaches its denominator, and the marker is one
    `run_resume.plan_for` can actually resume from. A test pinned to a dict
    literal goes red on every honest extension of the shape it guards.
    """
    with tenant_ctx(brazos):
        # DEF-BIL-8695: the break must happen INSIDE the job — see the helper.
        cycle = a_world_that_breaks_in_the_job(brazos, dana, monkeypatch)
        run = a_run(brazos, cycle)
        record = run_jobs.enqueue_calculate(run)
        core_jobs.run_pending(record["id"])

    gauges = [
        save["progress"] for save in recording_store.saves if save["progress"]["total"] is not None
    ]
    assert gauges, "nothing wrote done/total on the job record"
    assert gauges[-1] == {"done": 2, "total": 2}, gauges
    final = recording_store.get(record["id"])
    assert final["status"] == core_jobs.SUCCEEDED
    marker = final["checkpoint"]
    assert marker["done"] == 2, marker
    # CR-051 task 11: the marker a resumed worker can act on. `plan_for` is the
    # only reader, so it is what the case asks rather than a dict literal.
    plan = run_resume.plan_for(final)
    assert plan.resuming is True, f"the calculate marker is not resumable: {marker}"
    assert plan.already_done == 2
    assert plan.resume_after == "ACC-9002"


# ══════════════════════════════════════════════════════════════════════════
# tc4 — CR-051 task 5: a break row, with its reason and its stage
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc4__an_unbillable_account_gets_a_row_with_its_reason_and_stage(brazos, dana):
    """BR-BIL-053/040 — *"ACC-1201 failed"* sends a clerk hunting.

    The row names the stage by the PIPELINE's own name, so the screen groups on
    it and a clerk fixes every missing read in one pass.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        result = billing_runs.calculate_run(prepared_for(cycle), bill_run=run)

        rows = list(billing_models.BillRunBreak.objects.filter(bill_run=run))

    assert result.drafted_count == 1
    assert len(rows) == 1
    row = rows[0]
    assert row.account_no == "ACC-9002"
    assert row.stage == "measure-consumption"
    assert row.reason == billing_runs.CALC_UNRESOLVED_READ
    assert row.retryable is True  # a clerk can enter the read and retry
    assert row.resolution is None  # OUTSTANDING — BR-BIL-053's own word
    assert row.detail  # the sentence, whole and unedited (BR-SHL-020)


# ══════════════════════════════════════════════════════════════════════════
# tc5 — CR-051 task 6: the list SURVIVES a fresh request
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc5__the_break_list_survives_a_request_that_calculates_nothing(brazos, dana):
    """A refresh, a logout and a shift change are the same thing to a server.

    ⚠ **THE ASSERTION THAT MATTERS IS THE INVOICE COUNT.** Before this change a
    GET could only have served breaks by CALCULATING, which writes drafts — so
    a break list that had cost a draft would look identical to this one from the
    outside. Counting the invoices before and after is what tells the two apart.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        billing_runs.calculate_run(prepared_for(cycle), bill_run=run)
        drafts_before = billing_models.Invoice.objects.filter(bill_run=run).count()

    response = breaks_of(brazos, run)
    again = breaks_of(brazos, run)  # a second refresh, no calculate between

    with tenant_ctx(brazos):
        drafts_after = billing_models.Invoice.objects.filter(bill_run=run).count()

    assert response.status_code == 200
    assert response.data["break_count"] == 1
    assert response.data["breaks"][0]["account_no"] == "ACC-9002"
    assert response.data["breaks"][0]["stage"] == "measure-consumption"
    assert response.data["breaks_by_stage"] == {"measure-consumption": ["ACC-9002"]}
    assert again.data == response.data  # byte-identical: a READ, not a pass
    assert drafts_after == drafts_before == 1, "serving the break list wrote a draft"


# ══════════════════════════════════════════════════════════════════════════
# tc6 — hard rule 6: the same run calculated twice does not double-bill
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc6__calculating_twice_bills_once_and_files_one_break(
    brazos, dana, recording_store, monkeypatch
):
    """🔒 THE IDEMPOTENCY CASE. Two full passes, everything counted after each.

    THREE THINGS MUST NOT DOUBLE and each has its own mechanism:
      * the DRAFT — stage 6 replaces an account's draft for this run rather
        than adding a second (BR-BIL-023). The guarantee is in the write.
      * the BREAK ROW — `uq_bill_run_breaks_once` at the DB level, so a
        re-delivered Celery task cannot append a contradiction.
      * the total — one invoice, one amount, unchanged between the passes.

    Run through the JOB both times, because that is the path a re-delivered
    task actually takes.

    ⚠ **THE `job_id` ASSERTION AT THE END IS NOT DECORATION, AND IT IS THERE
    BECAUSE THE FIRST VERSION OF THIS CASE PASSED ON BROKEN CODE.** Proving the
    guard RED with an `objects.create` in place of the upsert left the row count
    at 1 and the case GREEN — the unique constraint refused the second insert,
    `record_break` logged it and returned None, and from the outside "one row"
    looked identical either way. What that version actually left behind was the
    FIRST pass's row with the FIRST pass's job id, so a clerk asking *which pass
    raised this?* got the wrong answer for ever. Counting rows cannot see that;
    reading the row can.
    """
    # ⚠ THREE SEPARATE CONTEXT BLOCKS, AND THAT IS THE PRODUCTION SHAPE.
    # `core.jobs.run_job` enters the record's OWN tenant context and CLEARS it
    # on the way out — B3, so a worker can never carry one tenant's context into
    # the next tenant's task — so a caller that ran a job by hand and then kept
    # querying would be querying with no tenant set. Re-entering here is what a
    # worker process does between tasks, not a workaround.
    with tenant_ctx(brazos):
        # DEF-BIL-8695: the break must happen INSIDE the job — see the helper.
        cycle = a_world_that_breaks_in_the_job(brazos, dana, monkeypatch)
        run = a_run(brazos, cycle)
        first = run_jobs.enqueue_calculate(run)
    core_jobs.run_pending(first["id"])

    with tenant_ctx(brazos):
        invoices_after_one = list(
            billing_models.Invoice.objects.filter(bill_run=run).values_list("id", "total")
        )
        breaks_after_one = list(
            billing_models.BillRunBreak.objects.filter(bill_run=run).values_list("id", flat=True)
        )
        # The first job is finished, so this is a SECOND job over the same run —
        # not the fold-in of tc11. It is the re-delivery case.
        second = run_jobs.enqueue_calculate(run)
        assert second["id"] != first["id"]
    core_jobs.run_pending(second["id"])

    with tenant_ctx(brazos):
        invoices_after_two = list(
            billing_models.Invoice.objects.filter(bill_run=run).values_list("id", "total")
        )
        breaks_after_two = list(
            billing_models.BillRunBreak.objects.filter(bill_run=run).values_list("id", flat=True)
        )
        refreshed = billing_models.BillRunBreak.objects.get(bill_run=run)

    assert len(invoices_after_one) == 1
    assert len(invoices_after_two) == 1, "the second pass billed the account again"
    assert invoices_after_one[0][1] == invoices_after_two[0][1], "the amount moved on a re-run"
    assert len(breaks_after_one) == 1
    assert breaks_after_two == breaks_after_one, "the second pass filed a second break row"
    # UPSERTED, not appended-and-swallowed — see the docstring's last paragraph.
    assert str(refreshed.job_id) == second["id"], (
        "the break row still names the FIRST pass, so the second pass's write was "
        "refused by the unique constraint and quietly dropped rather than updating it"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc7 — BR-BIL-053: a break that stops being true stops being outstanding
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc7__a_break_the_next_pass_drafts_is_closed(brazos, dana):
    """*"The run cannot enter phase 4 with an unresolved break row."*

    So a break that has been fixed must LEAVE the work list, or the gate would
    refuse a run the clerk has already put right. It is marked, not deleted:
    *"we broke here and then it was fixed"* and *"this never broke"* are
    different mornings, and only the first explains a two-pass run.
    """
    from decimal import Decimal

    from apps.billing.contracts import ServiceReading
    from apps.billing.rating_seam import Quantity

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)
        billing_runs.calculate_run(prepared, bill_run=run)
        broken = billing_models.BillRunBreak.objects.get(bill_run=run)
        assert broken.resolution is None

        # The clerk enters the missing read, and the pass runs again.
        fixed = tuple(
            (
                data
                if data.account_no != "ACC-9002"
                else _with_read(data, ServiceReading, Quantity, Decimal)
            )
            for data in prepared.ready
        )
        billing_runs.calculate_run(
            type(prepared)(**{**prepared.__dict__, "ready": fixed}), bill_run=run
        )

        broken.refresh_from_db()
    outstanding = breaks_of(brazos, run).data
    everything = breaks_of(brazos, run, resolved="all").data

    assert broken.resolution == billing_models.BREAK_RESOLUTION_DRAFTED
    assert outstanding["break_count"] == 0, "a fixed break is still on the work list"
    assert everything["break_count"] == 1, "the history of the break was deleted, not closed"
    assert everything["breaks"][0]["resolution"] == billing_models.BREAK_RESOLUTION_DRAFTED


def _with_read(data, ServiceReading, Quantity, Decimal):
    """The clerk's entered read, swapped onto the data already gathered."""
    from apps.billing import gather

    return gather.with_readings(
        data,
        (
            ServiceReading(
                service_code="electric",
                consumption=Quantity(amount=Decimal("412.000000"), unit="kWh"),
            ),
        ),
    )


# ══════════════════════════════════════════════════════════════════════════
# tc8 — CR-051 task 1: one run, by its id
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc8__the_run_detail_serves_phase_scope_decisions_and_counts(brazos, dana):
    """The route the wizard needs to RE-OPEN a run — mounted, and read-only.

    `phase` is DERIVED and `status` is the stored column, and both are served:
    `bill_runs.status` never moves off `"draft"` (a defect this read does not
    fix and must not hide), so a screen rendering it alone titles every
    historical run *Draft*.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
    before = run_detail(brazos, run).data  # api_call clears context — see the header
    with tenant_ctx(brazos):
        billing_runs.calculate_run(prepared_for(cycle), bill_run=run)
    after = run_detail(brazos, run).data

    assert before["phase"] == "draft"
    assert before["counts"]["drafts"] == 0

    assert after["id"] == str(run.pk)
    assert after["phase"] == "calculated"
    assert after["status"] == "draft"  # the stored column, unchanged, served beside it
    assert after["scope"]["cycle_id"] == str(cycle.id)
    assert after["scope"]["period_start"] == PERIOD_START.isoformat()
    assert after["scope"]["period_end"] == PERIOD_END.isoformat()
    assert after["counts"]["drafts"] == 1
    assert after["counts"]["bills_issued"] == 0
    assert after["counts"]["breaks"] == 1
    assert after["counts"]["breaks_by_stage"]["measure-consumption"]["outstanding"] == 1
    assert after["decisions"] == {"taken": 0, "by_case": {}}
    # BR-MET-078 as hardened by CR-029: money never touches this surface.
    assert "total" not in after["counts"]
    assert "currency" not in after


# ══════════════════════════════════════════════════════════════════════════
# tc9 — law 3 / DEF-2487: never queue into a void
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc9__background_with_no_worker_runs_inline_and_says_so(brazos, dana, live_store):
    """An accepted job that bills nobody, for ever, is worse than the wait.

    The import REFUSES here; this falls back to INLINE, and the difference is
    deliberate — 50,000 rows inline exceeds the request timeout, so inline is
    not an option there, and a bill run inline is what this product did until
    today. Either way nothing is queued into a void.
    """
    previous = core_jobs._dispatch_probe  # noqa: SLF001
    core_jobs.set_dispatch_probe(lambda: (False, "no Celery worker answered the ping"))
    try:
        with tenant_ctx(brazos):
            cycle = a_world(brazos, dana)
            run = a_run(brazos, cycle)
        response = calculate(brazos, run, background=True)
        with tenant_ctx(brazos):
            jobs_filed = tenancy_models.Job.objects.filter(
                kind=run_jobs.CALCULATE_JOB, tenant=brazos
            ).count()
            drafts = billing_models.Invoice.objects.filter(bill_run=run).count()
    finally:
        core_jobs.set_dispatch_probe(previous)

    assert response.status_code == 201, "a 202 was answered with nothing to run the job"
    assert response.data["background"] is False
    assert jobs_filed == 0, "a job record was queued into a void"
    assert drafts == 1, "the fallback did not actually do the work"
    codes = {entry["code"] for entry in response.data["unavailable"]}
    assert "no_worker_means_inline_not_refused" in codes


# ══════════════════════════════════════════════════════════════════════════
# tc10 — CR-051 task 9: findings records counts, and does NOT cache the lists
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc10__the_findings_job_records_counts_and_caches_no_case_list(
    brazos, dana, live_store
):
    """The counts land on the run; the case lists do not, and that is stated.

    `selectors.prepared_for` records why: a prepare pass is *"recomputed on
    every call and cached nowhere … a clerk who fixes a plan and reloads must
    see the fix"*. Snapshotting the LISTS is OQ-843 and no lane may close it by
    choosing, so this asserts the boundary as well as the behaviour.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        record = run_jobs.enqueue_findings(run)
    core_jobs.run_pending(record["id"])  # clears context on exit — see tc6
    with tenant_ctx(brazos):
        run.refresh_from_db()
    detail = run_detail(brazos, run).data

    summary = run.findings_summary
    assert summary["job_id"] == str(record["id"])
    assert summary["accounts"] == 2
    assert summary["ready"] == 2
    assert summary["blocked"] == 0
    # ⚠ THE BOUNDARY: counts only. A key holding the case rows here would be the
    # cache OQ-843 exists to ask about.
    assert set(summary) == {
        "job_id",
        "accounts",
        "ready",
        "blocked",
        "decisions",
        "blocked_by_reason",
        # ⚠ AMENDED 2026-10-01 (`DEF-BIL-8583`): `silent` joined on 2026-09-01
        # (`3829b01a9`, BR-BIL-1025 — accounts examined with nothing to charge).
        # It is a COUNT, so the boundary above still holds.
        "silent",
    }
    assert summary["silent"] == 0
    assert detail["findings_summary"] == summary


# ══════════════════════════════════════════════════════════════════════════
# tc11 — NFR-16: a second click folds into the job already running
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc11__a_second_click_folds_into_the_active_job(brazos, dana, recording_store):
    """The scope key is the run and the verb, so a double-clicked *Work out the
    bills* is ONE job rather than two passes racing over the same accounts.

    ⚠ **THIS DECIDES WHAT A SECOND CLICK DOES, NOT WHAT A SECOND PASS DOES** —
    tc6 is the other half and neither substitutes for the other.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        first = run_jobs.enqueue_calculate(run)
        second = run_jobs.enqueue_calculate(run)  # still queued — the fold-in

    assert second["id"] == first["id"]
    assert len(recording_store.records) == 1


# ══════════════════════════════════════════════════════════════════════════
# tc12 · tc13 — CLAUDE.md HARD-WON LAW 14, and they need REAL POSTGRES
#
# ⚠ These two are the only cases in this file that can fail on the version of
# `runs.record_break` without its nested `transaction.atomic()`. On SQLite a
# failed statement leaves the transaction perfectly usable, so the broken code
# passes every case above. On PostgreSQL the transaction is ABORTED and every
# later query raises `InFailedSqlTransaction` — which would lose not one break
# but every draft and every break after it.
# ══════════════════════════════════════════════════════════════════════════
def _bare_run(name):
    """A tenant and a bill run, and NOTHING else — no owner, no premises, no
    account, no provisioning.

    ⚠ **THE MINIMALITY IS THE POINT, AND TWO RICHER SHAPES WERE MEASURED AND
    ABANDONED BEFORE THIS ONE.** (a) The `brazos` fixture ERRORS on the
    PostgreSQL tier — *"new row violates row-level security policy for table
    subscriptions"* — because the session-scoped probe-role fixture cannot be
    composed with the function-scoped tenant fixtures, which
    `test_us_bil_001_003_run_api._run_tenant` already records. (b)
    `provisioned_tenant` ERRORS too, on `users`, whether it is called inside a
    live tenant context or outside it. Neither of those is anything to do with
    breaks, and law 14 needs neither an account nor a user to be proved: it
    needs a transaction, a statement that fails, and a statement afterwards
    that must still work.
    """
    from apps.metering import models as metering_models
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.create(name=name, subdomain=f"{name.lower()}{uuid.uuid4().hex[:8]}")
    with live_tenant_context(tenant.id):
        cycle = metering_models.Cycle.objects.create(
            tenant=tenant,
            code=f"C-{str(tenant.id)[:4]}",
            start_day=PERIOD_START.day,
            days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
            bill_day=SERVICE_DATE.day,
        )
        run = billing_models.BillRun.objects.create(
            tenant=tenant,
            cycle=cycle,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=SERVICE_DATE,
            idempotency_key=f"{uuid.uuid4()}|2026-06-01|2026-06-30",
        )
    return tenant, run


def _a_break(account_id, account_no):
    return billing_runs.Break(
        account_id=str(account_id),
        account_no=account_no,
        stage="measure-consumption",
        reason=billing_runs.CALC_UNRESOLVED_READ,
        detail="no usable read for electric",
        retryable=True,
    )


@pytest.mark.isolation
@requires_postgres
def test_cr051_tc12__a_refused_break_write_does_not_poison_the_transaction():
    """🔒 **CLAUDE.md HARD-WON LAW 14, AND THIS IS THE ONLY CASE THAT PROVES IT.**

    `record_break` catches a database error and the calculate loop CONTINUES
    afterwards. On PostgreSQL, once any statement errors inside a transaction
    the transaction is ABORTED — every later query raises
    `InFailedSqlTransaction` and the work is thrown away at COMMIT — so without
    the nested `transaction.atomic()` a single refused break row would cost
    **every draft and every break after it**, not one break.

    **THE DEFAULT SUITE CANNOT SEE THIS.** `config/settings/test.py` hardcodes
    in-memory SQLite, which has no aborted-transaction state, so nothing about
    an aborted transaction is observable there at all.

    ⚠ **WHAT THIS CASE DOES AND DOES NOT PROVE, STATED PRECISELY BECAUSE THE
    RED PROOF DID NOT GO RED.** Deleting the savepoint from `record_break` and
    re-running this case on PostgreSQL was expected to fail and **passed** —
    `QuerySet.update_or_create` opens `transaction.atomic(using=self.db)` itself
    (django/db/models/query.py), so today the protection is Django's rather than
    ours. That is written into `record_break`'s own comment block, and the
    savepoint stays: a lane that swaps the call for a plain `create()` or adds
    a second statement to the block loses Django's wrapper with no test moving
    and no gate firing. **What this case DOES prove, on the right engine, is the
    property that matters: a break write the database refuses costs one break,
    and the pass and everything it had already written survive it.**

    The failure is induced as a REAL database refusal that lands ON THE
    STATEMENT: a break whose `account_no` is NULL against a NOT NULL column.

    ⚠ **THE FIRST DRAFT USED A GHOST ACCOUNT ID AND THAT DOES NOT WORK — WHICH
    IS A FINDING ABOUT THE PRODUCT, NOT ABOUT THE TEST, AND IS WRITTEN INTO
    `record_break`'s OWN DOCSTRING.** Django declares every foreign key
    `DEFERRABLE INITIALLY DEFERRED` on PostgreSQL, so an FK violation does not
    raise at INSERT: it raises at COMMIT, verbatim `assert
    <BillRunBreak object …> is None`, with `record_break` having returned a row
    perfectly happily. A SAVEPOINT cannot catch what has not happened yet. So
    the savepoint covers immediate refusals — NOT NULL, CHECK, UNIQUE, RLS —
    and a deferred one still takes the whole transaction down at the end.
    """
    from django.db import transaction

    from apps.billing.exceptions import BillingRuleError

    tenant, run = _bare_run("LawFourteen")
    with live_tenant_context(tenant.id):
        # ONE transaction around the lot — which is what a request and a Celery
        # task both give the pass, and the condition law 14 is about.
        with transaction.atomic():
            refused = billing_runs.record_break(run, _a_break(uuid.uuid4(), None))
            assert refused is None, "the planted NOT NULL violation did not fail"

            # ⚠ EVERY LINE BELOW IS THE ASSERTION. On an aborted transaction
            # each of these raises `InFailedSqlTransaction` instead of
            # answering, and the `except` in `record_break` cannot save it.
            assert billing_models.BillRunBreak.objects.filter(bill_run=run).count() == 0
            assert billing_runs.clear_break(run, uuid.uuid4()) == 0
            assert billing_models.BillRun.objects.filter(pk=run.pk).exists()

            # ── CR-051 task 6, 2026-08-31 — THE SECOND DOOR TAKES THE SAME
            # PATH AND MUST HAVE THE SAME PROPERTY. `clear_break` grew a
            # `resolution` argument and a SECOND caller, `mark_for_later`,
            # which now runs TWO statements where it ran one — so the same
            # refused-write-then-carry-on shape reaches it. Asserted with the
            # new call shape rather than assumed to be covered by the old one.
            assert (
                billing_runs.clear_break(
                    run, uuid.uuid4(), resolution=billing_models.BREAK_RESOLUTION_HELD
                )
                == 0
            )

            # …and the VOCABULARY refusal must not poison anything either. It
            # raises before any statement is sent, which is the whole reason it
            # is a `BillingRuleError` and not a database CHECK — but "before any
            # statement" is a claim, and on this engine a claim about statements
            # is testable. The query after it is the test.
            with pytest.raises(BillingRuleError):
                billing_runs.clear_break(run, uuid.uuid4(), resolution="sorted_it")
            assert billing_models.BillRun.objects.filter(pk=run.pk).exists()

    # And the transaction COMMITTED rather than being thrown away at the end,
    # which is the other half of what an aborted transaction costs.
    with live_tenant_context(tenant.id):
        assert billing_models.BillRun.objects.filter(pk=run.pk).exists()


@pytest.mark.isolation
@requires_postgres
def test_cr051_tc13__the_break_table_carries_a_forced_rls_policy_on_the_cluster():
    """Hard rule 1, read from the CLUSTER's own catalog and not from the file.

    A break row names a customer's account and the reason we could not bill
    them. Migration 0027 applies the signed B2 §3 template — and *"a comment
    claiming a guarantee is not the guarantee"* (hard-won law 1) applies to a
    migration too: what matters is whether the policy is ON THE TABLE that is
    running, which `pg_class.relrowsecurity` + `relforcerowsecurity` answer and
    a `grep` of the migration cannot.

    ⚠ **THIS CASE TAKES NO `rls` FIXTURE, DELIBERATELY, AND THERE IS NO SECOND
    CASE HERE THAT DOES.** The probe role needs `CREATEROLE`, which this
    environment's app role does not have, so anything requesting `rls` SKIPS
    with the helper's honest reason — and a case that can never run is a check
    that cannot fail. **The row-level proof is not missing, it is SHARED:**
    `tests/test_tenant_isolation.py::test_g5_every_rls_table_denies_a_query_
    with_no_tenant_context` sweeps EVERY table this same catalog read returns,
    under the probe role, so `bill_run_breaks` joined that sweep the moment
    migration 0027 ran — and its sibling
    `test_g5_the_rls_exempt_list_is_exactly_what_b2_declares` goes RED if a
    tenant-scoped table is ever added WITHOUT a policy. Duplicating either here
    would add a second place for the same guarantee to rot.
    """
    from tests.isolation_helpers import rls_enabled_tables

    assert "bill_run_breaks" in rls_enabled_tables(), (
        "migration 0027 wrote a policy that never reached this cluster — "
        "`bill_run_breaks` is not ENABLE + FORCE ROW LEVEL SECURITY"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc14 / tc15 — CR-051 task 6: BR-BIL-053 HAS TWO DOORS AND ONLY ONE WAS WIRED
# ══════════════════════════════════════════════════════════════════════════
#
# tc7 above proves the door a WHOLE-RUN pass opens: an account that drafts on a
# later calculate has its break closed as `drafted`. That was the only door the
# table could record. BR-BIL-053 gives a break exactly two ways out —
# *"allow user to retry immediately by fixing the issue"*, and failing that the
# account waits for the catch-up sub-run — and the second had no resolution
# value at all, so an account a clerk deliberately HELD kept an OUTSTANDING
# break row for ever.
#
# ⚠ **THE HOLDING PATH IS LIVE, NOT HYPOTHETICAL, WHICH IS WHY tc14 GOES THROUGH
# `decisions` RATHER THAN CALLING `mark_for_later` DIRECTLY.** A test that called
# the writer straight would prove the writer and miss the point: the sequence a
# clerk actually produces is break → holding decision on S31.3 → re-calculate,
# and it reaches `mark_for_later` through `decisions.apply_decisions`, at which
# moment the account has already LEFT `ready` and `_calculate_run`'s `clear_break`
# can never see it again.


def test_cr051_tc14__an_account_held_by_a_decision_leaves_the_break_work_list(brazos, dana):
    """BR-BIL-053's SECOND door — closed as `held`, and never as `drafted`.

    The two are different facts about a run and a supervisor reading
    `?f.resolved=all` afterwards is asking exactly which: `drafted` says the
    account was billed on this run in the end, `held` says it was not and is
    waiting in the catch-up queue. One value for both outcomes would answer the
    question wrongly rather than not at all.
    """
    from apps.billing import decisions as billing_decisions

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)
        billing_runs.calculate_run(prepared, bill_run=run)

        broken = billing_models.BillRunBreak.objects.get(bill_run=run)
        assert broken.resolution is None, "the account should have broken at calculate"
        held_account_id = str(broken.account_id)

        # The clerk holds it on S31.3 — BR-BIL-015's second choice — and the
        # prepare pass folds the decision in, which is where the account leaves.
        billing_decisions.record_decision(
            bill_run=run,
            account_id=held_account_id,
            case="missing_read",
            choice=billing_decisions.CHOICE_HOLD,
            reason="waiting on a field visit",
            decided_by=dana.user,
        )
        after = billing_decisions.apply_decisions(prepared, bill_run=run)
        assert held_account_id not in [
            data.account_id for data in after.ready
        ], "apply_decisions did not take the held account out of the run"

        broken.refresh_from_db()
        queued = billing_models.BillRunExclusion.objects.filter(
            bill_run=run, account_id=held_account_id
        ).count()

    outstanding = breaks_of(brazos, run).data
    everything = breaks_of(brazos, run, resolved="all").data

    assert queued == 1, "the account did not reach the catch-up queue"
    assert broken.resolution == billing_models.BREAK_RESOLUTION_HELD
    assert outstanding["break_count"] == 0, (
        "an account the clerk has already dealt with is still on the break work list — "
        "and BR-BIL-053's last clause would hold the run out of phase 4 over it"
    )
    assert everything["break_count"] == 1, "the history of the break was deleted, not closed"
    assert everything["breaks"][0]["resolution"] == billing_models.BREAK_RESOLUTION_HELD


def test_cr051_tc15__a_successful_retry_closes_the_break_it_fixed(brazos, dana):
    """BR-BIL-053's FIRST door — *"retry immediately by fixing the issue"*.

    ⚠ **AND THE OTHER HALF, WHICH IS THE ONE A NAIVE FIX BREAKS:** a retry that
    RAISES must leave the break exactly as it was. The account still cannot be
    billed and the clerk still has to see it, so the close belongs after the
    draft commits and not before it.
    """
    from decimal import Decimal

    from apps.billing.contracts import ServiceReading
    from apps.billing.exceptions import BillingRuleError
    from apps.billing.rating_seam import Quantity

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)
        billing_runs.calculate_run(prepared, bill_run=run)

        broken = billing_models.BillRunBreak.objects.get(bill_run=run)
        account_id = str(broken.account_id)

        # A retry that still cannot price leaves the row untouched. The read is
        # STILL missing, which is the same refusal the first pass hit.
        with pytest.raises(BillingRuleError):
            billing_runs.retry_account(prepared, account_id, bill_run=run)
        broken.refresh_from_db()
        assert broken.resolution is None, (
            "a FAILED retry closed the break — the account still cannot be billed and "
            "the clerk must still see it"
        )

        # Now the clerk enters the read and retries. This is the door.
        invoice = billing_runs.retry_account(
            prepared,
            account_id,
            bill_run=run,
            readings=(
                ServiceReading(
                    service_code="electric",
                    consumption=Quantity(amount=Decimal("412.000000"), unit="kWh"),
                ),
            ),
        )
        broken.refresh_from_db()

    outstanding = breaks_of(brazos, run).data
    everything = breaks_of(brazos, run, resolved="all").data

    assert invoice is not None
    assert broken.resolution == billing_models.BREAK_RESOLUTION_DRAFTED
    assert outstanding["break_count"] == 0, (
        "the clerk fixed the account with the button BR-BIL-053 names and their own "
        "fix stayed on their work list"
    )
    assert everything["break_count"] == 1


def test_cr051_tc15b__an_unknown_break_resolution_is_refused_rather_than_stored(brazos, dana):
    """`bill_run_breaks.resolution` is a TextField with no CHECK behind it.

    So a typo at a call site would write a state nothing can read back, into the
    one list a clerk works from. `BREAK_RESOLUTIONS` is the vocabulary and this
    is where it is enforced — a check that cannot fail is worse than none, and a
    column that accepts anything is exactly that.
    """
    from apps.billing.exceptions import BillingRuleError

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana)
        run = a_run(brazos, cycle)
        billing_runs.calculate_run(prepared_for(cycle), bill_run=run)
        broken = billing_models.BillRunBreak.objects.get(bill_run=run)

        with pytest.raises(BillingRuleError) as refusal:
            billing_runs.clear_break(run, broken.account_id, resolution="sorted_it")

        broken.refresh_from_db()

    assert "not a break resolution" in str(refusal.value)
    assert broken.resolution is None, "the refused resolution was written anyway"


# ══════════════════════════════════════════════════════════════════════════
# tc16 — CR-051 task 18: *Charges to add* can store the clerk's reply
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc16__an_extra_charge_decision_is_recorded_and_holds_at_its_boundary(brazos, dana):
    """S31.3's *Charges to add* tab offered Apply and the server refused it.

    `decisions.UNSUPPORTED_CASES` named `extra_charge` on the argument that the
    charge-code reader did not exist. It has since BR-BIL-075 landed on
    2026-08-26, so the reason for refusing to RECORD the reply had expired while
    the refusal stood — a clerk's answer to fifty rows went nowhere.

    **WHAT IS AND IS NOT BUILT, asserted in both directions.** The DECISION is
    recorded and the choices are published, so the control goes live. The MONEY
    is not: BR-BIL-007's amount comes from the tenant's own charge code and no
    case row in this product names one, so `apply` HOLDS the account at that
    named boundary — the same posture `prorate_to_cycle_days` takes — rather
    than billing it without the charge a human asked to add, or inventing a
    figure no rule produced.

    ⚠ **AND `DEF-2596` MEANS THIS CAN BE RECORDED AND NEVER ARISE.** No pass in
    this product emits an `extra_charge` case row, so the tab is empty on every
    database there is. The decision kind is built anyway and the absence is said
    plainly rather than left for a reader to discover.
    """
    from apps.billing import decisions as billing_decisions

    # The vocabulary the SCREEN reads — `selectors` and `read_analysis` both
    # publish `CHOICES_BY_CASE.get(case, ())` onto every case row, so this is
    # what turns the disabled control live with nothing edited in the frontend.
    assert "extra_charge" not in billing_decisions.UNSUPPORTED_CASES
    assert billing_decisions.CHOICES_BY_CASE["extra_charge"] == (
        billing_decisions.CHOICE_APPLY,
        billing_decisions.CHOICE_WAIVE,
    )
    # `overcharge` still refuses, and asserting that is what stops this case
    # passing on a lane that simply emptied the dict.
    assert "overcharge" in billing_decisions.UNSUPPORTED_CASES

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, with_a_break=False)
        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)
        account_id = prepared.ready[0].account_id

        row = billing_decisions.record_decision(
            bill_run=run,
            account_id=account_id,
            case="extra_charge",
            choice=billing_decisions.CHOICE_APPLY,
            reason="reconnection fee agreed on the phone",
            decided_by=dana.user,
        )
        assert row.pk is not None, "the reply was still not stored"
        assert row.case == "extra_charge"
        assert row.choice == billing_decisions.CHOICE_APPLY

        # …and the boundary: applied, so the account waits rather than billing
        # without the charge or with an invented one.
        after = billing_decisions.apply_decisions(prepared, bill_run=run)
        held_ids = [problem.account_id for problem in after.decisions]
        queued = billing_models.BillRunExclusion.objects.filter(
            bill_run=run, account_id=account_id
        ).first()

    assert account_id not in [data.account_id for data in after.ready]
    assert account_id in held_ids
    assert queued is not None, "the held account never reached the catch-up queue"
    why = "the queue cannot tell WHY this account is waiting"
    assert queued.reason_code == "staff_apply_extra_charge", why


def test_cr051_tc16b__waiving_an_extra_charge_changes_nothing_and_bills(brazos, dana):
    """The other choice, and it is not symmetrical with `apply`.

    Waiving means the charge does not go on the bill — so the account bills
    normally and the recorded row IS the whole of the act. That is exactly the
    `late_fee`/`waive` shape, and it is the reason `waive` is deliberately NOT
    in `HOLDING_CHOICES`: holding an account because a clerk declined to add
    something to it would be a punishment for a decision to do nothing.
    """
    from apps.billing import decisions as billing_decisions

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, with_a_break=False)
        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)
        account_id = prepared.ready[0].account_id

        billing_decisions.record_decision(
            bill_run=run,
            account_id=account_id,
            case="extra_charge",
            choice=billing_decisions.CHOICE_WAIVE,
            reason="goodwill",
            decided_by=dana.user,
        )
        after = billing_decisions.apply_decisions(prepared, bill_run=run)
        queued = billing_models.BillRunExclusion.objects.filter(
            bill_run=run, account_id=account_id
        ).count()

    still_billing = [data.account_id for data in after.ready]
    assert account_id in still_billing, "a WAIVED charge took the account out of the run"
    assert queued == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051@tasks1-10 (12-governance/11-change-requests.md §CR-051 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-051..055 · core/jobs.py's BE-07 contract)
# generated: 2026-08-30 by the CR-051 W0/W1/W2 backend lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-051 tasks 2/3/7/12 are other lanes') F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case RED-proved before its fix — the verbatim failures are in the lane report · tc12/tc13 run under DJANGO_SETTINGS_MODULE=config.settings.local against real PostgreSQL (law 14) · golden 33/33 unchanged
# exceptions: tc7 rebuilds `PreparedRun` through `type(prepared)(**{...})` rather than a published helper, because `runs` publishes no "swap one account's readings into a prepared run" door and inventing one for a test would put a production function in the repo that only a test calls (hard-won law 2 in reverse)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
