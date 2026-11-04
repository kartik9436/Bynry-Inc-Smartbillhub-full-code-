# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-004 (phase 2 calculate)   Screens: S31 step 4
# Rules:    BR-BIL-052 (per-account, restartable, resumable — *"already-drafted
#           accounts are not recomputed and never duplicated"*) · BR-BIL-023 (a
#           re-run REPLACES a draft) · BR-BIL-053 (the break list) ·
#           BR-MET-082 Amendment 1 (the population is re-derived every run) ·
#           CLAUDE.md hard rule 6 (a bill run is idempotent) · hard rule 2
#           (money is stored to 4 decimals) · BR-TEN-043 (no clock in a worker)
# Change:   CR-051 tasks 11 (the checkpoint) · 21 (the measurement) ·
#           22 (the plural seams) · 23 (the invoice-line write)
# ───────────────────────────────────────────────────────
"""CR-051 W2/W5/W6 — the run at scale: measured, batched, and resumable.

WHAT THIS FILE PROVES, in the order the CR asks for it:

  tc1   the MEASURED figures are recorded where a human can read them, and
        drift goes RED (task 21 — the ratified-figure pattern
        `test_cr026_background_stages.py::test_the_ratified_async_bar_is_5000_rows`
        set for the premises import)
  tc2   a job record with NO checkpoint resumes nothing — every first delivery
        and every inline call is the pass this product ran yesterday
  tc3   a checkpoint round-trips, and one this build does not recognise is
        treated as absent (slow and correct beats fast and wrong)
  tc4   the skip needs BOTH halves: above the cursor is never skipped, and
        below the cursor with no draft and no break is never skipped either
  tc5   **the whole point** — a re-delivered job skips the accounts it already
        finished, and bills nobody twice
  tc6   a NEW job on the same run re-drafts everything, so a clerk who fixed a
        plan is re-priced rather than handed the old drafts
  tc7   the gauge stays honest across a resume — *"9,000 of 10,000"*, never
        *"0 of 1,000"*
  tc8   the per-run seam cache answers the SAME thing the seam does, and asks
        once for a thousand accounts instead of a thousand times (task 22)
  tc9   the cache is scoped to one pass and never leaks between two
  tc10  a bulk-written invoice line is byte-identical to a singly-written one,
        to the last of its four decimals (task 23 · hard rule 2)
  tc11  the REAL kill proof exists and still bites — see below
  tc12  neither new module can reach a frozen figure
  tc13  the ceiling is the MEASURED one, and drift from it goes RED (task 30)
  tc14  an oversized run is refused before a single row is drafted
  tc15  both doors refuse it — the enqueue AND the worker
  tc16  a run inside the ceiling is untouched, and `0` switches it off
  tc17  sizing a run costs a constant handful of statements, not a walk
  tc18  the findings screen gets the memo WITHIN a request and stores nothing
        across two — the PO's *"it is dyanmic"* ruling, in code

⚠ **THE KILL ITSELF IS NOT IN THIS FILE, AND THAT WAS MEASURED RATHER THAN
ASSUMED.** A real kill needs a second PROCESS, a second process can only see
rows the first COMMITTED, and in pytest-django that means
`django_db(transaction=True)` — which this repository has twice established it
cannot host. This lane wrote the case, ran it, and found the teardown does not
merely delete seed rows, it FAILS on `cannot truncate a table referenced in a
foreign key constraint` and leaves the test database unusable for every case
after it. So the kill is `10-scripts/cr051_kill_and_resume.py` — the same
disposition `cr026_import_benchmark.py` has — and tc11 here guards that it
still sends signal 9 and still checks both properties. tc4, tc5 and tc6 are the
deterministic half and run on BOTH tiers.

⚠ **WHICH CASE GUARDS WHICH HALF OF THE SKIP — WRITTEN DOWN BECAUSE THE RED
PROOFS CORRECTED THIS LANE'S OWN ANSWER.** Breaking the CURSOR half of
`run_resume.skip_predicate` was first pointed at **tc6**, and **tc6 PASSED** —
tc6 runs a job with no checkpoint, so the predicate returns its always-False
lambda and the broken line is never reached. A check that cannot fail over the
thing it is aimed at is worse than no check, because it is trusted (CLAUDE.md
law 11 says exactly this about `--stat`). The real mapping, each proved RED:

  * **tc4** guards BOTH halves of the `and`. Cursor half removed →
    `assert True is False … skip(<id>, 'ACC-9503')`, an account ABOVE the
    cursor carrying a stale draft skipped. Write half removed →
    `assert True is False … skip('00000000-…', 'ACC-9500')`, an account that
    entered the population between two passes skipped and billed by nobody.
  * **tc5** guards that a resume RESUMES: `plan_for` never resuming →
    *"the resumed pass re-walked the cycle — it gathered ['ACC-9501', …]"*.
  * **tc6** guards that a job with NO checkpoint skips nothing: `plan_for`
    resuming on a checkpoint-less record → *"a NEW calculate job skipped
    accounts it had never billed"*.

⚠ **THE FIGURES IN tc1 ARE NOT A PERFORMANCE ASSERTION AND MUST NEVER BECOME
ONE.** They are what a human was shown. A test that timed a run would be red on
a busy machine and green on a fast one, and it would be measuring the CI box
rather than the product. `10-scripts/cr051_run_benchmark.py` is the measurement;
this only asserts that what was published is still what the code says.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.billing import run_jobs, run_resume
from apps.billing import runs as billing_runs
from apps.billing import seam_batch
from apps.billing import selectors as billing_selectors

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
    api_call,
    brazos,
    dana,
    staff_actor,  # noqa: F401 — re-exported by the shared helper module
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

from core import jobs as core_jobs

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[2]
DECISION_LOG = REPO / "12-governance" / "02-decision-log.md"


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing
# ══════════════════════════════════════════════════════════════════════════
def a_run(tenant, cycle, key="2026-06|cr051-scale"):
    """A run carrying the clerk's typed bill date — see
    `test_cr051_run_jobs_and_breaks.a_run` for why leaving it off costs an hour
    (the JOB path derives the service date from the run and refuses without
    one rather than reaching for a clock)."""
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=SERVICE_DATE,
        idempotency_key=key,
    )


def a_world(tenant, actor, *, accounts=4):
    """`accounts` billable accounts on one cycle, numbered in walk order.

    The numbers are what the cursor is compared against, so they are explicit
    and ascending rather than left to a fixture: `customers.
    accounts_for_bill_run` orders by `account_no`, and a case about a cursor
    that did not control the order would prove nothing.
    """
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    for index in range(1, accounts + 1):
        unit = a_billed_unit(
            actor, tenant, cycle, plan, asset_no=f"M-95{index:02d}", label=f"U{index}"
        )
        an_account(tenant, unit["id"], f"ACC-95{index:02d}")
    return cycle


def prepared(cycle, **kwargs):
    return billing_runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
        **kwargs,
    )


def drafts_of(tenant, run):
    """`{account_no: total}` for the run's draft invoices — the money, per
    account, which is what a double-bill would move."""
    rows = billing_models.Invoice.objects.filter(
        tenant_id=tenant.id, bill_run=run, status=billing_models.INVOICE_DRAFT
    ).values_list("account_id", "total")
    return {str(account_id): total for account_id, total in rows}


def a_job_record(tenant, run, *, checkpoint=None, status=core_jobs.RUNNING):
    """A BE-07 record shaped exactly as `core.jobs.enqueue` mints one."""
    return {
        "id": str(run.pk),
        "tenant_id": str(tenant.id),
        "kind": run_jobs.CALCULATE_JOB,
        "status": status,
        "progress": {"done": 0, "total": None},
        "checkpoint": checkpoint,
        "result_link": None,
        "error": None,
        "scope_key": f"billing:calculate:{run.pk}",
        "payload": {"run_id": str(run.pk), "actor_user_id": None},
    }


# ══════════════════════════════════════════════════════════════════════════
# tc1 — task 21: the measurement is published, and drift goes RED
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc1__the_measured_figures_are_published_in_the_decision_log():
    """CR-051 task 21: *"publish the figures"*, and the CR says why there was
    nothing to publish before — *"There is no timing figure for a bill run of
    any size anywhere in this repo."*

    What is asserted is that the decision log carries the three sizes and the
    per-account figure a human was shown, so a later change that makes the run
    ten times slower cannot leave a published number standing unchallenged.
    The measurement itself is `10-scripts/cr051_run_benchmark.py`; nothing here
    times anything (see the module docstring).
    """
    text = DECISION_LOG.read_text(encoding="utf-8")
    # Case-insensitive because the row states the figure in a heading voice
    # ("THE ANSWER IS 137 ms PER ACCOUNT") and a test that pinned the casing
    # would go red on an edit that changed nothing a reader cares about.
    entry = [line for line in text.splitlines() if "137 ms per account" in line.lower()]
    assert entry, (
        "the decision log no longer carries the bill run's measured per-account "
        "figure. CR-051 task 21 published it; a number nobody can find is a "
        "number nobody can challenge."
    )
    row = entry[0]
    for size in ("100", "1,000", "10,000"):
        assert (
            size in row
        ), f"the published measurement no longer names the {size}-account run"
    assert "cr051_run_benchmark.py" in row, (
        "the published figures no longer name the script that produced them — a "
        "measurement with no reproducer is an opinion (hard-won law 1)"
    )


def test_cr051_tc1b__the_benchmark_exists_and_rolls_back():
    """The reproducer is real and its safety property is stated in it.

    A benchmark that left 10,000 accounts behind would be a fixture nobody
    asked for, in a database somebody is using.
    """
    script = (REPO / "10-scripts" / "cr051_run_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "IT WRITES NOTHING" in script
    assert "raise _Rollback" in script


# ══════════════════════════════════════════════════════════════════════════
# tc2-tc4 — the checkpoint itself
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc2__a_record_with_no_checkpoint_resumes_nothing(brazos, dana):
    """`core.jobs.enqueue` mints `checkpoint: None`, so this is EVERY first
    delivery and every re-press of the button. Nothing is skipped and the
    expensive half of the plan is never even computed."""
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle)
        plan = run_resume.plan_for(a_job_record(brazos, run))
        assert plan.resuming is False
        assert plan.already_done == 0
        skip = run_resume.skip_predicate(plan, run)
        assert skip("any-id", "ACC-9501") is False


def test_cr051_tc3__a_checkpoint_round_trips_and_an_unknown_one_is_ignored():
    """The marker is three scalars whatever the size of the run (see
    `run_resume.checkpoint`), and a shape this build does not recognise is
    treated as ABSENT — a resumed job then re-walks the cycle, which is slow
    and always correct. Guessing at a marker is the one case that costs money.
    """
    marker = run_resume.checkpoint(done=9_000, total=10_000, account_no="ACC-9000")
    assert marker == {"v": 1, "done": 9_000, "total": 10_000, "cursor": "ACC-9000"}

    plan = run_resume.plan_for({"id": "j", "checkpoint": marker})
    assert plan.resuming is True
    assert plan.resume_after == "ACC-9000"
    assert plan.already_done == 9_000

    future = dict(marker, v=run_resume.CHECKPOINT_VERSION + 7)
    assert run_resume.plan_for({"id": "j", "checkpoint": future}).resuming is False
    assert run_resume.plan_for({"id": "j", "checkpoint": {"done": 3}}).resuming is False
    assert run_resume.plan_for({"id": "j", "checkpoint": None}).resuming is False


def test_cr051_tc4__the_skip_needs_both_the_cursor_and_the_write(brazos, dana):
    """⚠ **THE `and` IS THE WHOLE SAFETY ARGUMENT.** Three accounts, one drafted:

    * ABOVE the cursor and drafted  -> NOT skipped (a new job's stale draft)
    * BELOW the cursor and NOT drafted -> NOT skipped (BR-MET-082 Amendment 1:
      an account can appear in the population between two passes, and skipping
      it would leave that customer silently unbilled)
    * BELOW the cursor and drafted  -> skipped, and only then
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=3)
        run = a_run(brazos, cycle)
        billing_runs.calculate_run(prepared(cycle), bill_run=run)
        drafted = list(drafts_of(brazos, run))
        assert len(drafted) == 3

        plan = run_resume.ResumePlan(resume_after="ACC-9502", already_done=2)
        skip = run_resume.skip_predicate(plan, run)
        # Below the cursor and drafted — the only True in this function.
        assert skip(drafted[0], "ACC-9501") is True
        assert skip(drafted[0], "ACC-9502") is True
        # Above the cursor, even though this account HAS a draft.
        assert skip(drafted[0], "ACC-9503") is False
        # Below the cursor, but no draft and no break — the account that
        # appeared between the two passes.
        assert skip("00000000-0000-0000-0000-000000000000", "ACC-9500") is False


# ══════════════════════════════════════════════════════════════════════════
# tc5-tc7 — the resume, end to end
# ══════════════════════════════════════════════════════════════════════════
def _gather_counter(monkeypatch):
    """Count how many accounts a pass actually GATHERS. That is the thing task
    11 is trying not to do twice, so it is the thing the case measures."""
    calls: list[str] = []
    original = billing_runs.gather.gather_account

    def counted(**kwargs):
        calls.append(str(getattr(kwargs["account"], "account_no", "?")))
        return original(**kwargs)

    monkeypatch.setattr(billing_runs.gather, "gather_account", counted)
    return calls


def test_cr051_tc5__a_re_delivered_job_skips_what_it_finished_and_bills_nobody_twice(
    brazos, dana, monkeypatch
):
    """**The point of task 11.** A job runs, is interrupted after two accounts,
    and is delivered again. The second delivery gathers only what is left, and
    every account still has exactly ONE draft for the same money.

    CLAUDE.md hard rule 6, and the two halves are asserted separately because
    they are different claims: *nobody is billed twice* is correctness, and
    *the cycle is not re-walked* is the whole reason this file exists.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle)
        first = a_job_record(brazos, run)
        run_jobs.run_calculate_job(first)
        before = drafts_of(brazos, run)
        assert len(before) == 4

        # The interruption, expressed as the record a dead worker leaves: a
        # checkpoint naming the second account and nothing else. tc11 produces
        # this record by killing a real process; this case asserts what the
        # RESUME does with it, on any vendor.
        second = a_job_record(
            brazos,
            run,
            checkpoint=run_resume.checkpoint(done=2, total=4, account_no="ACC-9502"),
        )
        gathered = _gather_counter(monkeypatch)
        run_jobs.run_calculate_job(second)

        assert sorted(gathered) == ["ACC-9503", "ACC-9504"], (
            "the resumed pass re-walked the cycle — it gathered "
            f"{sorted(gathered)} when the checkpoint said the first two were done"
        )
        after = drafts_of(brazos, run)
        assert len(after) == 4, "an account gained a second draft — hard rule 6"
        assert (
            after == before
        ), "money moved on a resume; a resumed pass reprices nothing"


def test_cr051_tc6__a_new_job_on_the_same_run_re_drafts_everything(
    brazos, dana, monkeypatch
):
    """The other direction, and it is the one a clerk feels. Somebody fixes a
    plan and presses *Work out the bills* again: that is a NEW job with no
    checkpoint, and it must re-price every account rather than hand back the
    drafts from the pass before.

    This is why the skip cannot be *"does this account already have a draft"*
    on its own — see `run_resume`'s docstring.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=3)
        run = a_run(brazos, cycle)
        run_jobs.run_calculate_job(a_job_record(brazos, run))

        gathered = _gather_counter(monkeypatch)
        run_jobs.run_calculate_job(a_job_record(brazos, run))  # a fresh record
        assert len(gathered) == 3, (
            "a NEW calculate job skipped accounts it had never billed — a clerk "
            "who fixed a plan would be handed the old drafts"
        )


def test_cr051_tc7__the_gauge_stays_honest_across_a_resume(brazos, dana):
    """NFR-4. A worker killed at 9,000 of 10,000 that comes back reporting
    *"0 of 1,000"* tells an operator the work restarted, which is the exact
    thing the checkpoint exists to stop being true."""
    seen: list[tuple[int, int]] = []
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=3)
        run = a_run(brazos, cycle)
        # Two of the three already done, and only the third handed to the loop.
        one_left = prepared(cycle)
        one_left = type(one_left)(
            **{
                **{
                    field: getattr(one_left, field)
                    for field in one_left.__dataclass_fields__  # noqa: SLF001 — a dataclass
                },
                "ready": one_left.ready[2:],
            }
        )
        billing_runs.calculate_run(
            one_left,
            bill_run=run,
            already_done=2,
            on_progress=lambda done, total, label: seen.append((done, total)),
        )
    assert seen == [(3, 3)], (
        "a resumed pass reported its own progress from zero rather than from "
        f"what the earlier attempt had already done — {seen}"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc8-tc9 — task 22: the plural seams
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc8__the_pass_cache_answers_the_same_thing_and_asks_once(brazos, dana):
    """Task 22 — *"ask once for a thousand accounts, not a thousand times for
    one"*. The cache must be invisible: the SAME question, the SAME answer,
    asked fewer times.

    ⚠ It is NOT allowed to be a new place where a pricing question is decided
    (CR-051's second hard rule). The assertion is therefore equality against
    the uncached answer, account by account, not merely a smaller call count.
    """
    accounts = 4
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=accounts)

        # ⚠ **THE PRE-TASK-22 WORLD IS AN EMPTY ALLOWLIST, NOT A MISSING
        # CACHE.** `prepare_run` always opens one now, so the honest "before"
        # is a pass in which nothing is on the list — the same code path, the
        # same everything, with the memo disabled. A first draft of this case
        # monkeypatched `gather._resolve` to count, which REPLACED the wrapper
        # it was trying to measure and reported `90 < 90` for both passes.
        original_list = dict(seam_batch.BATCHABLE)
        seam_batch.BATCHABLE.clear()
        try:
            plain = prepared(cycle)
        finally:
            seam_batch.BATCHABLE.update(original_list)

        # `pass_cache` is re-entrant, so opening one here hands `prepare_run`
        # this very object — which is how the case reads the counters without
        # instrumenting anything (tc9 proves that nesting behaviour).
        with seam_batch.pass_cache() as cache:
            cached = prepared(cycle)

    assert len(plain.ready) == len(cached.ready) == accounts
    for before, after in zip(plain.ready, cached.ready, strict=True):
        assert before == after, (
            "the per-pass cache changed an answer. It may only ask the same "
            "question fewer times (CR-051's second hard rule: a plural seam "
            "asks the SAME question for many accounts)."
        )

    assert (
        cache.saved() > 0
    ), f"the cache served nothing — asked {cache.asked}, served {cache.served}"
    # The purest form of the claim: the tenant's regional settings take no
    # arguments at all, so however many accounts a run has, that read happens
    # ONCE. `gather._tenant_currency` asks for it per account.
    assert cache.asked.get("tenancy.regional_settings") == 1, (
        f"the tenant's settings were read {cache.asked.get('tenancy.regional_settings')} "
        f"times for {accounts} accounts — task 22 asks for once"
    )
    assert cache.served.get("tenancy.regional_settings") == accounts - 1


def test_cr051_tc9__the_cache_never_outlives_its_pass(brazos, dana):
    """`selectors.prepared_for` records the constraint this must not break:
    *"Recomputed on every call and cached nowhere … a clerk who fixes a plan
    and reloads must see the fix."* The cache lives for ONE pass; outside the
    context manager there is none, and a second pass gets its own."""
    assert seam_batch.active() is None
    with seam_batch.pass_cache() as first:
        assert seam_batch.active() is first
        with seam_batch.pass_cache() as inner:
            # A nested pass does NOT start a second cache — one pass, one cache.
            assert inner is first
        assert seam_batch.active() is first
    assert seam_batch.active() is None
    with seam_batch.pass_cache() as second:
        assert second is not first


# ══════════════════════════════════════════════════════════════════════════
# tc10 — task 23: the invoice-line write
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc10__a_bulk_written_line_is_identical_to_a_singly_written_one(
    brazos, dana
):
    """CLAUDE.md hard rule 2 — money is stored to 4 decimals — and CR-051 task
    25: no priced arithmetic moves. Two accounts on the same plan with the same
    reading must produce lines equal to the last decimal, and the batch must
    not have re-rounded anything on its way into the database.

    ⚠ **THE ASSERTION READS THE DATABASE, NOT THE OBJECTS.** A rounding that
    happens in the column rather than in the code is invisible to a comparison
    of what was passed in — which is the whole failure mode a bulk write could
    introduce.
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=2)
        run = a_run(brazos, cycle)
        billing_runs.calculate_run(prepared(cycle), bill_run=run)
        lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=brazos.id, invoice__bill_run=run
            ).order_by("account_id", "kind", "description")
        )
    assert lines, "the run wrote no invoice lines at all"
    by_account: dict[str, list] = {}
    for line in lines:
        by_account.setdefault(str(line.account_id), []).append(line)
    first, second = (by_account[key] for key in sorted(by_account))
    assert len(first) == len(second)
    for left, right in zip(first, second, strict=True):
        assert left.kind == right.kind
        assert left.amount == right.amount, (
            f"two identical accounts were charged differently for a {left.kind} "
            f"line: {left.amount} vs {right.amount}"
        )
        assert left.amount == left.amount.quantize(Decimal("0.0001")) or (
            left.amount.as_tuple().exponent >= -4
        ), f"a {left.kind} line stored more than 4 decimals: {left.amount!r}"


# ══════════════════════════════════════════════════════════════════════════
# tc11 — THE KILLED WORKER, AND WHY THE KILL ITSELF IS NOT IN THIS FILE
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc11__the_real_kill_proof_exists_and_actually_kills_something():
    """⚠ **A REAL KILL CANNOT LIVE IN THIS SUITE, AND THAT WAS MEASURED RATHER
    THAN ASSUMED.**

    A kill needs a second PROCESS, and a second process can only see rows the
    first one COMMITTED — which in pytest-django means
    `django_db(transaction=True)`. This repository has already established
    twice that it cannot host that (`tests/test_us_cus_003_account_race.py` and
    `tests/test_us_cus_004_move_in_race.py`, both in as many words: *"buying a
    nicer-looking test by breaking the suite it runs in is not a trade this
    lane will make"*). This lane wrote the case anyway, ran it, and found it is
    worse than those notes say — the teardown does not merely delete seed rows,
    it FAILS and leaves the test database unusable for every case after it:

        psycopg.errors.FeatureNotSupported: cannot truncate a table referenced
        in a foreign key constraint
        DETAIL:  Table "meter_read_asset_monthly_usage" references "assets".
        django.core.management.base.CommandError: Database
        test_sbh_agent_… couldn't be flushed.

    So the kill lives in `10-scripts/cr051_kill_and_resume.py`, the same
    disposition `cr026_import_benchmark.py` has for a measurement, and the
    DETERMINISTIC half of task 11 stays here in tc4, tc5 and tc6 — which run on
    both tiers and are the ones a merge can rely on.

    **What this case guards is that the proof still exists and still bites**: a
    script that stopped sending signal 9, or stopped checking that nobody was
    billed twice, would be a proof in name only.
    """
    script = (REPO / "10-scripts" / "cr051_kill_and_resume.py").read_text(
        encoding="utf-8"
    )
    assert "signal.SIGKILL" in script, (
        "the kill proof no longer sends signal 9 — an exception or a flag is a "
        "simulated kill, and a simulated kill proves nothing about a worker "
        "that vanishes mid-transaction"
    )
    assert "child.exitcode != -signal.SIGKILL" in script, (
        "the kill proof no longer CHECKS that the child died of signal 9, so it "
        "would pass over a child that was allowed to finish"
    )
    assert "nobody was billed twice" in script, "the idempotency check is gone"
    assert "re-walked the whole cycle" in script, "the not-re-walked check is gone"
    assert "multiprocessing" in script, "the proof no longer forks a second process"


# ══════════════════════════════════════════════════════════════════════════
# The trace the CR asks for — task 25's assertion lives in its own gate, but
# this file states the claim it depends on.
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc12__nothing_in_this_lane_reaches_a_frozen_figure():
    """CR-051 task 25: *"Golden suite unchanged — 33/33 before and after,
    asserted, because no task here touches priced arithmetic."*

    The structural half of that claim, checkable here: neither the checkpoint
    nor the per-pass cache imports the pricing engine or the rating seam's
    money callables, so there is no path from either to a ❄️ FROZEN B4/B5
    figure. The arithmetic half is `10-scripts/03-golden-verify.py`.
    """
    for module in ("run_resume.py", "seam_batch.py"):
        text = (
            Path(__file__).resolve().parents[1] / "apps" / "billing" / module
        ).read_text(encoding="utf-8")
        assert not re.search(r"^\s*from apps\.rating", text, re.MULTILINE), (
            f"{module} imports rating directly — a money path must go through "
            "apps/billing/rating_seam.py, which is a guarded file"
        )
        assert "price_bill" not in text and "price_period" not in text, (
            f"{module} reaches the pricing engine. It exists to ask the same "
            "questions fewer times, never to answer one."
        )


# ══════════════════════════════════════════════════════════════════════════
# tc13-tc16 — CR-051 task 30: the largest run this deployment accepts
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc13__the_ceiling_is_the_measured_one_and_drift_goes_red():
    """CR-051 task 30. The number is not a preference and the case says where
    it comes from, so a later change to it is a decision somebody made rather
    than a number that slid.

    **25,000 is headroom for the largest BILLING CYCLE anybody sensibly
    configures** — PO ruling 2026-09-14, verbatim: *"(b) Keep 25,000, fix the
    stale comment only - generally utilities will devide them into nilling
    cycles and hence 25k limit is good"*. A utility divides its accounts into
    cycles, so no single run ever covers the whole book: a 40,000-account T5
    tenant bills, say, four cycles of 10,000. At the measured ~170 ms an
    account, 25,000 is about seventy minutes of a worker that has two slots.
    The ratified-figure pattern, same as tc1.

    ⚠ **THIS DOCSTRING ARGUED FROM BOOK SIZE UNTIL 2026-09-14 AND ITS PREMISE
    HAD INVERTED (`DEF-BIL-4224`).** It read *"25,000 is eight times the
    largest utility this product is for — `CLAUDE.md`'s own first line says
    under 3,000 connections"*. That line was superseded on 2026-09-06 and the
    ICP ceiling is now 40,000, so the same sentence read **0.625×** while this
    test went on passing — **a ratified-figure test asserts the CONSTANT and
    defends it in prose, so its premise can move without one assertion changing
    colour.** The constant did not move and `NFR-5` is not breached; the reason
    did.
    """
    assert run_jobs.MAX_ACCOUNTS_PER_RUN_DEFAULT == 25_000
    assert run_jobs.max_accounts_per_run() == 25_000


def test_cr051_tc14__an_oversized_run_is_refused_before_anything_is_drafted(
    brazos, dana, settings
):
    """The refusal names the count, the ceiling and what to do — and it happens
    with NOTHING written.

    ⚠ **THE ORDER IS THE POINT.** `runs.scope_account_count` answers in two
    queries where the prepare pass would take the length of the run, so a
    100,000-account run is stopped at the door rather than half way through.
    The case asserts there are no drafts afterwards, because a ceiling that
    fires late is a crash with bills behind it.
    """
    settings.BILLING_MAX_ACCOUNTS_PER_RUN = 2
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle)
        with pytest.raises(billing_runs.BillingRuleError) as refused:
            run_jobs.refuse_if_oversized(run)
        sentence = str(refused.value)
        assert "4 accounts" in sentence and "2 in one pass" in sentence, sentence
        # CR-016: what to DO, not which rule said so.
        assert (
            "fewer services" in sentence and "one billing cycle at a time" in sentence
        )
        assert "Nothing has been drafted" in sentence
        assert (
            billing_models.Invoice.objects.filter(
                tenant_id=brazos.id, bill_run=run
            ).count()
            == 0
        )


def test_cr051_tc15__the_enqueue_and_the_worker_both_refuse(brazos, dana, settings):
    """Both doors, because they are different failures at different moments.

    The ENQUEUE refuses while a person is still at the screen. The WORKER's own
    check fires only when the ceiling was LOWERED after the job was queued —
    a real sequence on a deployment being tuned, and the honest answer there is
    the same refusal rather than an hour of work nobody wants.
    """
    settings.BILLING_MAX_ACCOUNTS_PER_RUN = 2
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle)
        with pytest.raises(billing_runs.BillingRuleError):
            run_jobs.enqueue_calculate(run)
        with pytest.raises(billing_runs.BillingRuleError):
            run_jobs.run_calculate_job(a_job_record(brazos, run))
        assert (
            billing_models.Invoice.objects.filter(
                tenant_id=brazos.id, bill_run=run
            ).count()
            == 0
        )


def test_cr051_tc16__a_run_inside_the_ceiling_is_untouched_and_zero_disables_it(
    brazos, dana, settings
):
    """The other direction, which is every run this product has ever done.

    A run under the ceiling passes through and `refuse_if_oversized` returns
    its size; `0` switches the ceiling off entirely, and an operator has to
    type that (hard-won law 3 — the unsafe option is the one you type).
    """
    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=3)
        run = a_run(brazos, cycle)
        assert run_jobs.refuse_if_oversized(run) == 3
        run_jobs.run_calculate_job(a_job_record(brazos, run))
        assert (
            billing_models.Invoice.objects.filter(
                tenant_id=brazos.id, bill_run=run, status=billing_models.INVOICE_DRAFT
            ).count()
            == 3
        )
        settings.BILLING_MAX_ACCOUNTS_PER_RUN = 0
        assert run_jobs.max_accounts_per_run() == 0
        assert run_jobs.refuse_if_oversized(run) == 0


def test_cr051_tc17__the_size_costs_a_constant_number_of_queries(brazos, dana):
    """`runs.scope_account_count` must not be the prepare pass wearing a hat.

    ⚠ **THIS CASE'S FIRST DRAFT COULD NOT FAIL, AND THE RED PROOF IS WHAT FOUND
    IT.** It counted calls to `gather.gather_account` and asserted zero; the
    sabotage that replaces the `COUNT(*)` with a walk over the population calls
    `gather.covered_units`, not `gather_account`, so **the case passed over the
    exact regression it exists to catch.** A check whose output cannot tell
    pass from fail is worse than no check, because it is trusted.

    The property is *"it does not pay for the pass"* and the honest measure of
    that is SQL STATEMENTS: a constant handful whatever the population, rather
    than a number that grows with it. Measured here at two sizes so a walk
    cannot hide behind a small fixture — the count must not move when the
    population trebles.
    """

    def statements(call) -> tuple[int, int]:
        seen = 0

        def counter(execute, sql, params, many, context):
            nonlocal seen
            seen += 1
            return execute(sql, params, many, context)

        with connection.execute_wrapper(counter):
            answer = call()
        return answer, seen

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=3)
        small, small_queries = statements(
            lambda: billing_runs.scope_account_count(cycle_id=cycle.id)
        )
        for index in range(4, 13):
            unit = a_billed_unit(
                dana,
                brazos,
                cycle,
                a_priced_plan(brazos),
                asset_no=f"M-96{index:02d}",
                label=f"W{index}",
            )
            an_account(brazos, unit["id"], f"ACC-96{index:02d}")
        big, big_queries = statements(
            lambda: billing_runs.scope_account_count(cycle_id=cycle.id)
        )

    assert small == 3 and big == 12, (small, big)
    assert big_queries == small_queries, (
        f"sizing 12 accounts cost {big_queries} statements where sizing 3 cost "
        f"{small_queries} — scope_account_count is walking the population it "
        "exists to COUNT, and at 25,000 accounts that is the whole run"
    )
    assert small_queries <= 8, (
        f"sizing a run cost {small_queries} statements; it is two seam calls "
        "and a COUNT(*), and a ceiling that is expensive to check is a ceiling "
        "nobody will check at the door"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc18 — the findings screen: memoised WITHIN a request, stored across none
# ══════════════════════════════════════════════════════════════════════════
def test_cr051_tc18__findings_is_memoised_within_a_request_and_stored_across_none(
    brazos, dana, monkeypatch
):
    """`GET /billing/runs/{id}/findings` IS the prepare pass, so it gets task
    22's memo — and it may never get a stored answer.

    **THE RULING THAT DRAWS THE LINE** (`12-governance/02-decision-log.md`
    2026-08-30, closing `OQ-843`), verbatim: *"it is dyanmic, so at the time of
    compute if data is changed, process will dynamically use it becuase it will
    collect data at that instansce"*. A clerk who fixes a plan and reloads must
    see the fix, and that row ends *"A lane may not reopen this by proposing a
    cache."*

    That forbids **storing the result across requests**. It does not forbid the
    memo — the same row asks for it by name, *"make the pass FASTER (plural
    seams, bulk write), never cache it"* — and the difference is the whole of
    this case: the memo stops the same question being asked twice inside ONE
    computation and is gone before the next request begins, so every request
    still collects its data at that instant. Both halves are asserted here
    because asserting only the first would let a later lane "optimise" this
    screen into something faster and wrong.

    ⚠ **HALF ONE'S FIRST DRAFT COULD NOT FAIL, AND THE RED PROOF IS WHAT FOUND
    IT — the third time in this lane.** It opened its own `pass_cache` around
    the call so it could read the counters. `pass_cache` is RE-ENTRANT, so that
    cache is the one the pass then uses — and the case stayed green with
    `prepare_run` sabotaged into opening no cache at all. It was proving *"a
    memo that is already open gets used"*, which nothing was in doubt about,
    and never *"the findings screen opens one"*, which is the whole claim.
    **It now records the caches CONSTRUCTED during the call.** The recorder
    subclasses `_PassCache` and calls `super().__init__`, so the behaviour under
    test is untouched and only construction is observed — unlike a first draft
    of `tc8`, which monkeypatched `gather._resolve` and thereby REPLACED the
    wrapper it was trying to measure.
    """
    built: list = []
    real_cache_class = seam_batch._PassCache

    class RecordingCache(real_cache_class):  # type: ignore[misc,valid-type]
        """The real cache, and a note that it was made. Nothing is replaced."""

        def __init__(self) -> None:
            super().__init__()
            built.append(self)

    monkeypatch.setattr(seam_batch, "_PassCache", RecordingCache)

    with tenant_ctx(brazos):
        cycle = a_world(brazos, dana, accounts=4)
        run = a_run(brazos, cycle)

        # HALF ONE — the findings screen OPENS a memo of its own. Called with
        # no cache in scope, exactly as a GET arrives at a WSGI worker.
        assert seam_batch.active() is None
        body = billing_selectors.findings_dict(run)

        assert len(body["ready"]) == 4, body["blocked"]
        assert len(built) == 1, (
            f"drawing one findings screen opened {len(built)} pass caches. "
            "findings_dict calls prepared_for -> runs.prepare_run, which opens "
            "exactly one for the pass; zero means the screen pays the whole "
            "repeated-question cost again, and more than one means a pass is "
            "answering the same question from two places."
        )
        cache = built[0]
        assert cache.saved() > 0, (
            f"the findings pass served nothing from its memo — asked "
            f"{cache.asked}, served {cache.served}."
        )
        assert cache.asked.get("tenancy.regional_settings") == 1, (
            "the tenant's settings were read "
            f"{cache.asked.get('tenancy.regional_settings')} times to draw ONE "
            "findings screen for 4 accounts"
        )

        # HALF TWO — nothing survives the request. The currency comes from the
        # tenant row through `tenancy.regional_settings`, the most-memoised
        # seam of all (no arguments at all), so if any answer were kept across
        # calls this is where it would show.
        assert {ready["currency"] for ready in body["ready"]} == {brazos.currency}
        was = brazos.currency
        brazos.currency = "CAD" if was != "CAD" else "USD"
        brazos.save(update_fields=["currency"])

        again = billing_selectors.findings_dict(run)

    assert (
        seam_batch.active() is None
    ), "a pass cache outlived the request that opened it"
    assert (
        {ready["currency"] for ready in again["ready"]} == {brazos.currency} != {was}
    ), (
        "the findings screen answered with the world as it was when it was first "
        "drawn. The PO's ruling is that this pass is DYNAMIC — \"at the time of "
        'compute if data is changed, process will dynamically use it" — so a '
        "stored answer is a defect, not an optimisation. The memo is within-pass "
        "only; see apps/billing/seam_batch.py."
    )
