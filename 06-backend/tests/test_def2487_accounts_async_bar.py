# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (accounts cutover through the ONE runner)
#           Screens: S81 / IMP-01 · WFL-01 stages 3–5
# Defect:   DEF-2487 (critical) — a 1,048-account commit is killed by the
#           60-second web-worker timeout after a clean dry run, and the screen
#           can only say "Something went wrong. Nothing was saved — try again."
# Change:   PO 2026-08-30, verbatim: *"can we run anything above 100 recors
#           directly using worker batch job"*
# Rules:    BR-MET-096 (ONE runner, every target inherits it) · BR-MET-035 (the
#           role gate is at the door) · BR-MET-098 (the approver bar) ·
#           CLAUDE.md law 3 (defaults fail closed) · law 7 (prove a guard RED)
# Tests:    this file · 10-scripts/def2487_accounts_bar_benchmark.py (the
#           measurement the bar is chosen from — a script, not a case, for the
#           reason CR-026's own benchmark gives)
# Impacts:  apps/metering/import_runs.py · apps/metering/import_progress.py ·
#           core/jobs.py · apps/tenancy/services.py · config/settings/*
# ───────────────────────────────────────────────────────
"""DEF-2487 — **a row is not a row, and one bar for every target killed a demo.**

WHAT HAPPENED, IN THE NUMBERS THAT MATTER. `ASYNC_ROW_BAR` was 5,000 for every
import target. It was justified by a measurement taken on PREMISES rows — 2.03
ms per row, so 5,000 rows is about ten seconds — and an ACCOUNTS row is not a
premises row: it opens an account, inherits the unit's services, plan and meters
(CR-047), writes an opening balance, posts to the ledger and snapshots the whole
account-detail payload for its audit row. **Measured on live PostgreSQL: 45
queries and 121–127 ms per account.**

    rows      load      ms/row   vs the 60s web-worker timeout
     100      12.7s       127     4.7x  — comfortable
     500      60.5s       121     1.0x  — level with the wall
   1,048     130.6s       125     0.5x  — the worker is killed

`06-backend/docker-entrypoint.sh` runs `gunicorn --timeout 60`. So the commit
the Product Owner ran on a screen share never finished: the worker was SIGKILLed
with the transaction still open, Django never formed a response, and the browser
fell back to its generic strip over a reference the CLIENT had minted. Reproduced
under a real gunicorn at `--timeout 60` — `[CRITICAL] WORKER TIMEOUT (pid:…)`,
HTTP 500, an HTML body, 60.8 s wall — and the run was left `validated` with zero
accounts written, so the sentence on screen was TRUE and useless.

THREE THINGS ARE PROVED HERE, AND THE SECOND IS THE ONE THAT COULD HAVE MADE
THINGS WORSE.

1. **The bar is per target and per stage**, and it divides into the timeout with
   margin. The stage half is measured, not fastidiousness: on the same 1,048-row
   file transform took 0.2s and validate 0.2s, so pushing THOSE to a worker at
   101 rows would make an operator poll for a fifth of a second of work.
2. **A deferral refuses when nothing would run it.** In production `JOBS_EAGER`
   is False and `apps/tenancy/tasks.send` swallows a broker failure by design, so
   a deployment with no worker accepts the file, says *queued*, and writes
   nothing, for ever. Moving the accounts commit onto that path without this
   check would have replaced a visible 500 with silence — strictly worse, and
   ours (CLAUDE.md law 3).
3. **Nothing on the accounts load path may demand a role**, because a deferred
   stage runs as `_JobActor`, which carries an id and no role. That is DEF-2515's
   defect and DEF-1108's before it; lowering the bar to 100 moves almost every
   real migration onto that path, so the walk is done END TO END here — the whole
   load, with an opening balance and a deposit so the ledger posting is included
   — rather than by reading decorators.

⚠ **THE RED EVIDENCE, QUOTED (law 7).** Each guard below was run against the
pre-fix engine first.

* the bar: with `_defers` put back to `_row_count(run) > ASYNC_ROW_BAR`,
  `test_an_accounts_file_over_its_own_bar_goes_to_a_worker` fails with

      AssertionError: a file over its own bar must go to a worker
      assert None is True
       +  where None = <built-in method get of dict object>('deferred')

  — a 3-row accounts file above a patched accounts bar of 2 was still answered
  synchronously, because the target's own bar was not consulted at all.
* the refusal: with the `_refuse_no_worker(stage)` line removed from `_defer`,
  `test_a_deferral_is_refused_when_nothing_would_run_it` fails with

      Failed: DID NOT RAISE BizError

  and the queued job record it should never have created is then there for the
  assertion that follows.
* the stall: with the two `stalled` keys removed from `import_progress.read`,
  `test_a_job_nothing_has_claimed_is_reported_as_stalled` fails with

      KeyError: 'stalled'
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.customers import models as customers_models
from apps.metering import import_progress, import_runs, models as metering_models
from apps.tenancy import models as tenancy_models, services as tenancy_services
from core import errors, jobs as core_jobs

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _plan  # noqa: E402

pytestmark = pytest.mark.django_db

CUTOVER = "2026-08-31"
ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

# ⛔ **`KIND` AND `PHONE` JOINED THIS FILE FOR `BR-CUS-1024` (PO 2026-09-01,
# `DEF-2398`), AND THEY ARE THE IMPORT'S OWN ANSWER TO IT.** The accounts file
# carried a name and a `CUST_ID` and no identity at all, so from the moment the
# rule landed every one of the three rows rejected on
# `ACC.CUSTOMER_IDENTITY_REQUIRED`, `created` was **0 of 3**, and the reject
# percentage then crossed the approval bar — which is why the SECOND case in
# this file died on the approver role and looked like something else entirely.
#
# The columns are the ones `import_runs.ACCOUNT_IDENTIFIER_COLUMNS` already
# offers and `test_cr058_w7_accounts_identity_import.py` already exercises:
# `customer_kind`, and the template's EXISTING `phone` column, which carries the
# contact number AND — for a person — identifies them. A phone is enough to mint
# a number (`BR-CUS-1023`), is NOT one of `BR-CUS-1024`'s reuse identifiers and
# is NOT `BR-CUS-089`'s money test, so all three rows load under their own
# customer numbers and **no assertion in this file moves**: every case here is
# about the async bar and the approval role.
HEADERS = "UNIT_REF,ACCT,NAME,CUST_ID,TYPE,STATUS,OPENED,CURRENT,DEP,DEPDATE,KIND,PHONE"
MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "CUST_ID": "customer_ref",
    "TYPE": "account_type",
    "STATUS": "status",
    "OPENED": "opened_at",
    "CURRENT": "ob_current",
    "DEP": "deposit_on_file",
    "DEPDATE": "deposit_received_on",
    "KIND": "customer_kind",
    "PHONE": "phone",
}

#: What one account actually costs, in milliseconds, measured on live PostgreSQL
#: by `10-scripts/def2487_accounts_bar_benchmark.py` at 100, 500 and 1,048 rows
#: (127, 121 and 125 — the worst is the one recorded). It is a CONSTANT here and
#: not a measurement: this suite runs on in-memory SQLite with no server in front
#: of it, so it cannot time the thing that broke. What it CAN do is hold the
#: arithmetic — bar x cost against the timeout — so that lifting a bar without
#: re-measuring goes red.
#: ⚠ **RE-MEASURED 2026-08-30 AFTER `DEF-2480`: 127 → 94.** The old figure is
#: kept here rather than overwritten silently, because this constant is
#: documented as a MEASUREMENT and one that no longer matches any measurement is
#: hard-won law 1 (a comment claiming a guarantee is not the guarantee). Both
#: runs are `10-scripts/def2487_accounts_bar_benchmark.py` on live PostgreSQL at
#: 100 / 500 / 1,048 rows, worst of the three:
#:
#:     before DEF-2480   121 · 119 · 122 ms/row   (1,048 rows = 128.1 s)
#:     after  DEF-2480    94 ·  90 ·  90 ms/row   (1,048 rows =  94.6 s)
#:
#: `DEF-2480` removed a second, identical `account_detail_dict` build that
#: `_open_account` did on the very next line — 24 queries a row, measured.
#:
#: ⛔ **THE NUMBER GOING DOWN IS NOT PERMISSION TO PUT THE BAR UP.** The bar for
#: this target is 100 by a PO instruction of 2026-08-30 and moving a number the
#: PO named needs their word, not an arithmetic argument. For the record, the
#: same 3x margin that justified 100 at 127 ms/row would now justify 222 — that
#: is a fact about the engine, and the bar is a decision about the product.
MEASURED_MS_PER_ACCOUNT_ROW = 94

#: ⛔ **EVERY TARGET THAT DECLARES A LOAD BAR, AND WHAT ITS ROW ACTUALLY COST
#: (`DEF-PAY-6204`).** Until this existed the margin check below read ONE bar —
#: accounts — and passed truthfully over everything else in the table, which is
#: CLAUDE.md hard-won law 7's *reporting zero over a scope it silently
#: excludes*. A declared blind spot with no number attached is indistinguishable
#: from an empty one, so the check now walks this map and PRINTS what it
#: skipped beside what it checked.
#:
#: Each figure is a measurement with a script behind it, never an estimate:
#:   * accounts — 94 ms/row, `10-scripts/def2487_accounts_bar_benchmark.py`
#:   * premises — 2.03 ms/row, CR-026's own run (`cr026_import_benchmark.py`)
#:   * payments — 89.0 ms/row, `10-scripts/pay_p1_1_load_bar_benchmark.py`,
#:     2026-09-22, on a migrated PostgreSQL 16 clone with every row confirmed
#:     written
#:
#: ⚠ **A TARGET WITH A BAR AND NO FIGURE FAILS BY NAME**, which is the point:
#: adding a row to `ASYNC_ROW_BAR_BY_TARGET` now costs a measurement rather
#: than a guess, and that is what DEF-2487 asked for in its own words —
#: *"it needs a row in this table and a figure beside it"*.
MEASURED_MS_PER_ROW_BY_TARGET = {
    import_runs.TARGET_ACCOUNTS: MEASURED_MS_PER_ACCOUNT_ROW,
    import_runs.TARGET_PREMISES: 2.03,
    import_runs.TARGET_PAYMENTS: 89.0,
    # DEF-AST-8103 (2026-09-30): the worst of insert/update, 1,000 meters
    # inserted in 20.09 s on PostgreSQL 16 — `10-scripts/def_ast_8103_upload_cost.py`.
    import_runs.TARGET_ASSETS_METERS: 20.1,
}

#: How much of the timeout the slowest allowed file may use. Three times' margin
#: is the same posture CR-026 recorded for the original bar (*"inside a 30s
#: gateway timeout with 3x margin"*); at 100 accounts the real figure is 4.7x.
REQUIRED_MARGIN = 3.0

#: The gauge writes on a SECOND, autocommit connection in production; on SQLite
#: that connection has no `set_config`, so the two stall cases write through the
#: ORM instead — the same table, the same shape, the posture
#: `test_cr026_background_stages` already takes for every gauge case.
GAUGE_IN_TEST = override_settings(IMPORT_PROGRESS_ISOLATED=False)


def _units(actor, tenant, count):
    """`count` units on one premises, each on a published plan and carrying an
    electric service point — everything BR-MET-040 and BR-CUS-047 need."""
    from apps.metering import services as metering_services

    premises = make_premises(actor, services_available=["electric"])
    plan_id = str(_plan(tenant, service_code="electric").id)
    out = []
    for index in range(count):
        unit = make_unit(actor, premises["id"], label=f"DEF2487 Unit {index}")
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": plan_id})
        metering_services.ensure_service_point(unit["id"], "electric")
        out.append(unit)
    return out


def _content(units) -> str:
    lines = [HEADERS]
    for index, unit in enumerate(units, start=1):
        lines.append(
            f"{unit['unit_no']},A-77{index:02d},Customer {index},CUST-77{index:02d},"
            f"residential,active,2024-02-12,{index * 10}.00,25.00,2024-02-12,"
            f"person,{identity_fixtures.SAMPLE_PERSON_PHONE}"
        )
    return "\n".join(lines) + "\n"


def _extracted(actor, units) -> str:
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ACCOUNTS,
            "source_kind": "file",
            "file_name": "def2487-accounts.csv",
            "content": _content(units),
            "session_ref": "sess_def2487",
            "write_mode": "insert",
        },
    )
    return run["id"]


def _validated(actor, units) -> str:
    run_id = _extracted(actor, units)
    import_runs.transform(
        actor,
        run_id,
        {"mapping": MAPPING, "row_handling": ALL_OFF, "options": {"cutover_on": CUTOVER}},
    )
    import_runs.validate(actor, run_id)
    return run_id


class _NoWorker:
    """A dispatch probe that answers what a deployment with no worker answers."""

    def __call__(self) -> tuple[bool, str]:
        return False, "no Celery worker answered the ping"


@pytest.fixture()
def no_worker():
    """Install the not-ready probe for one case and take it away afterwards.

    ⚠ It restores whatever was registered rather than clearing, because
    `TenancyConfig.ready()` registers the real one at import time and a test that
    cleared it would quietly disarm the check for every case after it.
    """
    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(_NoWorker())
    yield
    core_jobs.set_dispatch_probe(previous)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE BAR — per target, per stage, and inside the wall
# ══════════════════════════════════════════════════════════════════════════
def test_the_accounts_load_bar_is_100_rows_and_the_default_is_untouched():
    """The figure the requester named, asserted so drift goes RED (law 9's
    posture applied to a number): PO 2026-08-30, *"can we run anything above 100
    recors directly using worker batch job"*.

    The DEFAULT stays 5,000 — `test_cr026_background_stages` asserts it too, and
    the two together are the statement that this change narrowed one target
    rather than moving everyone's bar.

    ⚠ **THE PREMISES LINE NO LONGER MEANS WHAT IT ORIGINALLY MEANT, AND SAYING
    SO IS THE POINT.** It was written to show that a neighbour still inherited
    the untouched default; since `DEF-MET-5756` premises has a measured bar of
    its own, so it now asserts THAT. What still carries the original meaning is
    the `ASYNC_ROW_BAR == 5_000` line above it, which reads the constant
    directly and cannot be changed by any target growing a row.
    """
    assert import_runs.async_row_bar(import_runs.TARGET_ACCOUNTS, "load") == 100
    assert import_runs.ASYNC_ROW_BAR == 5_000
    # ⚠ **THIS LINE READ `== 5_000` AND WAS RED FOR FOUR DAYS (`DEF-MET-6203`).**
    # True when it was written on 2026-09-11; `DEF-MET-5756` gave premises its
    # own measured bar of 500 on 2026-09-18 and moved the table without moving
    # the assertion that names it. Both dates are `git log -S` on the symbol,
    # not recollection. It failed on every run since, in a file whose other
    # fourteen cases pass and which takes nearly five minutes — which is where
    # a true red goes to hide (hard-won law 7, *proved red then never read*).
    assert import_runs.async_row_bar(import_runs.TARGET_PREMISES, "load") == 500


def test_accounts_transform_and_validate_keep_the_default_bar():
    """Measured on the same 1,048-row file: transform 0.2s, validate 0.2s. The
    cost that broke this target is entirely in the LOAD, so pushing the cheap
    stages to a worker at 101 rows would buy an operator nothing and cost them a
    poll — and, on a deployment whose worker is down, would refuse two stages
    that never needed one."""
    assert import_runs.async_row_bar(import_runs.TARGET_ACCOUNTS, "transform") == 5_000
    assert import_runs.async_row_bar(import_runs.TARGET_ACCOUNTS, "validate") == 5_000


def test_every_bar_divides_into_the_web_worker_timeout_with_margin():
    """⛔ **THE ARITHMETIC NOBODY WAS DOING, WHICH IS THE WHOLE DEFECT.**

    The bar of 5,000 was never wrong on its own — it was applied to a target
    whose per-row cost nobody had measured, and no check anywhere compared the
    two. This is that check. It cannot time the real thing (this suite is
    SQLite, with no web server in front of it), so it holds the measured figure
    and the timeout as constants and refuses a bar that spends more than a third
    of the request's life.
    """
    allowed = import_runs.WEB_WORKER_TIMEOUT_SECONDS / REQUIRED_MARGIN

    # ⛔ **EVERY TARGET WITH A DECLARED LOAD BAR, NOT JUST ACCOUNTS
    # (`DEF-PAY-6204`).** This read one bar until 2026-09-22 and passed
    # truthfully over the rest of the table — the exact shape law 7 names, and
    # the reason the payments bar reached the branch with no figure behind it.
    declared = sorted(
        target
        for (target, stage) in import_runs.ASYNC_ROW_BAR_BY_TARGET
        if stage == "load"
    )
    unmeasured = [t for t in declared if t not in MEASURED_MS_PER_ROW_BY_TARGET]
    assert not unmeasured, (
        f"{unmeasured} declare a load bar and nobody has timed a row. "
        "DEF-2487 is what happens when a bar is applied to a per-row cost "
        "nobody measured: add the figure to MEASURED_MS_PER_ROW_BY_TARGET "
        "with the script that produced it, or take the bar out."
    )

    margins: list[str] = []
    for target in declared:
        bar = import_runs.async_row_bar(target, "load")
        cost = MEASURED_MS_PER_ROW_BY_TARGET[target]
        worst_case_seconds = bar * cost / 1000
        margins.append(
            f"{target}: {bar} rows x {cost} ms = {worst_case_seconds:.1f}s "
            f"({allowed / worst_case_seconds:.1f}x inside {allowed:.1f}s)"
        )
        assert worst_case_seconds <= allowed, (
            f"{bar} {target} rows at {cost} ms/row is {worst_case_seconds:.1f}s "
            f"inside a request the web worker kills at "
            f"{import_runs.WEB_WORKER_TIMEOUT_SECONDS}s. That is DEF-2487. "
            f"Re-measure before raising it."
        )

    # ⚠ **PRINT WHAT WAS SKIPPED BESIDE WHAT WAS CHECKED (law 7).** A target
    # with no row in `ASYNC_ROW_BAR_BY_TARGET` takes the STAGE default, whose
    # own comment argues it fails closed at an accounts-shaped cost — but
    # nobody has timed those loads either, and a check that says nothing about
    # them reads exactly like a check that cleared them.
    inherits = sorted(set(import_runs.TARGETS) - set(declared))
    print(
        "\nload bars checked against a measured per-row cost:\n  "
        + "\n  ".join(margins)
        + f"\nNOT checked — no bar of their own, inheriting the stage default "
        f"of {import_runs.ASYNC_ROW_BAR_BY_STAGE['load']} rows, none of them "
        f"ever timed: {inherits}"
    )


def test_the_web_worker_timeout_matches_the_one_the_container_actually_runs():
    """The figure is only useful if it is the deployment's. `docker-entrypoint.sh`
    is the source; this is the copy, and a copy nobody compares is hard-won law 1
    (a comment claiming a guarantee is not the guarantee)."""
    from pathlib import Path

    entrypoint = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"
    text = entrypoint.read_text(encoding="utf-8")
    assert f'--timeout "${{GUNICORN_TIMEOUT:-{import_runs.WEB_WORKER_TIMEOUT_SECONDS}}}"' in text, (
        "import_runs.WEB_WORKER_TIMEOUT_SECONDS no longer matches the gunicorn "
        "timeout in docker-entrypoint.sh — every per-target bar is measured "
        "against that number"
    )


def test_an_accounts_file_over_its_own_bar_goes_to_a_worker(brazos, dana, monkeypatch):
    """The bar READ, not merely declared. Three rows, an accounts bar of 2.

    ⚠ Patched on the target's own key rather than on `ASYNC_ROW_BAR`, because
    patching the module constant is exactly what would keep passing over the
    defect: the whole failure was that the accounts target never consulted a bar
    of its own.
    """
    monkeypatch.setitem(
        import_runs.ASYNC_ROW_BAR_BY_TARGET, (import_runs.TARGET_ACCOUNTS, "load"), 2
    )
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 3)
        run_id = _validated(dana, units)
        answer = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert answer.get("deferred") is True, "a file over its own bar must go to a worker"
        assert answer["stage"] == "load"
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "validated"


def test_an_accounts_file_at_its_own_bar_is_untouched(brazos, dana, monkeypatch):
    """The other half, and the one that keeps a small import from noticing: AT
    the bar the same call is synchronous, writes the accounts and answers a
    receipt. `>` and not `>=` — a 100-row file is a 100-row file."""
    monkeypatch.setitem(
        import_runs.ASYNC_ROW_BAR_BY_TARGET, (import_runs.TARGET_ACCOUNTS, "load"), 3
    )
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 3)
        run_id = _validated(dana, units)
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert "deferred" not in receipt
        assert receipt["counts"]["created"] == 3
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "loaded"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE REFUSAL — never queue into a queue nothing is consuming
# ══════════════════════════════════════════════════════════════════════════
@override_settings(JOBS_EAGER=False, JOBS_REQUIRE_LIVE_WORKER=True)
def test_a_deferral_is_refused_when_nothing_would_run_it(brazos, dana, monkeypatch, no_worker):
    """⛔ **THE ONE THAT STOPS THIS FIX MAKING THINGS WORSE.**

    With no worker consuming the queue, an accepted import is an upload that
    reports success and never happens. So the promise is checked before it is
    made: the operator gets a refusal naming the two things they can do, the run
    stays exactly where it was, and NO job record is created — because a queued
    record nothing will claim is the silence this refusal exists to prevent.
    """
    monkeypatch.setitem(
        import_runs.ASYNC_ROW_BAR_BY_TARGET, (import_runs.TARGET_ACCOUNTS, "load"), 2
    )
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 3)
        run_id = _validated(dana, units)
        jobs_before = tenancy_models.Job.objects.count()

        with pytest.raises(errors.BizError) as refusal:
            import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        assert refusal.value.message_key == "metering.import.no_worker"
        assert tenancy_models.Job.objects.count() == jobs_before, (
            "a refused deferral must leave no queued record — that record IS the "
            "silent failure this refuses"
        )
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "validated"
        assert customers_models.Account.objects.filter(account_no="A-7701").count() == 0


@override_settings(JOBS_EAGER=False, JOBS_REQUIRE_LIVE_WORKER=True)
def test_a_probe_that_raises_is_read_as_not_ready():
    """CLAUDE.md law 3. The probe reaches a broker over a network, so it can fail
    in ways nobody enumerated; *"we could not tell"* is not a reason to promise
    someone their 1,048 accounts are being loaded."""

    def _explodes() -> tuple[bool, str]:
        raise RuntimeError("broker unreachable")

    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(_explodes)
    try:
        ready, reason = core_jobs.dispatch_is_ready()
    finally:
        core_jobs.set_dispatch_probe(previous)
    assert ready is False
    assert "RuntimeError" in reason


def test_eager_dispatch_never_asks_a_broker_anything():
    """On a demo box the body runs inside `enqueue`, so there is nothing to be
    ready and no reason to touch the network. Asserted because the alternative —
    a ping on every dev import — is a plausible refactor that would break every
    machine with no Redis."""
    with override_settings(JOBS_EAGER=True):
        ready, reason = tenancy_services.job_dispatch_ready()
    assert ready is True
    assert "eager" in reason


def test_with_no_probe_registered_the_answer_is_ready():
    """A deployment that has not wired a probe has not asked for the check and
    must not be broken by its absence — the same posture `set_job_dispatcher`
    takes about a missing transport."""
    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(None)
    try:
        assert core_jobs.dispatch_is_ready() == (True, "no probe registered")
    finally:
        core_jobs.set_dispatch_probe(previous)


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE STALL — "queued" is a status until it is a symptom
# ══════════════════════════════════════════════════════════════════════════
def _queued_gauge(run, *, age_seconds: int):
    import_progress.queued(run, "load", 3, None)
    row = metering_models.ImportRunProgress.objects.get(run_id=run.id)
    metering_models.ImportRunProgress.objects.filter(pk=row.pk).update(
        updated_at=timezone.now() - timedelta(seconds=age_seconds)
    )
    return import_progress.read(run)


@GAUGE_IN_TEST
def test_a_job_nothing_has_claimed_is_reported_as_stalled(brazos, dana):
    """A worker can die in the second after it answered the ping, and
    `tasks.send` swallows a broker failure by design — so the record simply rests
    `queued` and the operator watches a bar that will never move. The gauge says
    so, in a field the screen can render."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        run_id = _extracted(dana, units)
        run = metering_models.ImportRun.objects.get(pk=run_id)
        gauge = _queued_gauge(run, age_seconds=import_progress.STALLED_AFTER_SECONDS + 5)
        assert gauge["state"] == "queued"
        assert gauge["stalled"] is True
        assert gauge["stalled_after_seconds"] == import_progress.STALLED_AFTER_SECONDS


@GAUGE_IN_TEST
def test_a_job_queued_a_moment_ago_is_not_stalled(brazos, dana):
    """The half that keeps the notice meaningful: a healthy queue claims a
    message in well under a second, and a warning shown on every deferral is a
    warning nobody reads."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        run_id = _extracted(dana, units)
        run = metering_models.ImportRun.objects.get(pk=run_id)
        gauge = _queued_gauge(run, age_seconds=0)
        assert gauge["stalled"] is False


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE WORKER'S ROLELESS ACTOR — the whole load, end to end
# ══════════════════════════════════════════════════════════════════════════
def test_the_whole_accounts_load_runs_for_an_actor_that_carries_no_role(brazos, dana):
    """⛔ **THE WALK, DONE BY RUNNING IT RATHER THAN BY READING DECORATORS.**

    `DEF-2515` was one `@require_role` on one function the worker calls, and it
    only ever fired above 5,000 rows. Lowering the accounts bar to 100 moves
    almost every real migration onto that path, so the question *"is there
    another one"* has to be answered for the WHOLE load and not for the seam
    list — and the honest way to answer it is to run the load as the worker
    runs it, through `_load_apply`, with `_JobActor` carrying an id and nothing
    else.

    The file is chosen to touch every branch that could hold a gate: an opening
    balance (so `import_writer` writes buckets and the ledger posts an opening
    batch), a deposit (so the deposit half posts too — DEF-1713), a customer ref
    (so `link_customer` runs), and the run's rollback point and account-series
    catch-up at the end.

    ⚠ **`inspect.getsource` IS THE WRONG INSTRUMENT** for the static version of
    this question — `require_role` sets `__wrapped__` and `getsource` follows it,
    so it reports clean over a live defect (`test_def2515_worker_has_no_role`
    carries that finding in full). Running the path cannot be fooled that way.
    """
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 3)
        run_id = _validated(dana, units)
        worker_actor = import_runs._JobActor(dana.id)

        receipt = import_runs._load_apply(
            worker_actor, run_id, "insert", {"approved": True}, import_progress.NULL
        )

        assert receipt["counts"]["created"] == 3
        assert receipt["counts"]["rejected_at_write"] == 0
        # The money halves both landed — an AUTH refusal anywhere under here
        # would have taken the whole transaction down, which is the shape of the
        # defect this case exists for.
        assert receipt["counts"]["with_opening_balance"] == 3
        assert receipt["counts"]["deposits_held"] == 3
        assert receipt["counts"]["with_services"] >= 3
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "loaded"
        assert (
            customers_models.Account.objects.filter(
                tenant_id=brazos.id, account_no__startswith="A-77"
            ).count()
            == 3
        )


def test_the_worker_actor_still_cannot_walk_in_the_front_door(brazos, dana):
    """Removing nothing is only safe if the door still holds. `import_runs.load`
    keeps its `@require_role`, so a roleless caller is refused there — which is
    what makes the case above a statement about the WORKER path and not about
    the product's authorisation."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            import_runs.load(
                import_runs._JobActor(dana.id),
                "00000000-0000-0000-0000-000000000000",
                {},
            )


def test_no_role_gate_stands_between_the_loader_and_the_money(brazos, dana):
    """The static half, over the functions the case above actually reached.

    It is deliberately a SECOND check and not a replacement: the end-to-end run
    proves today's path, and this names the functions so the next lane that
    decorates one fails here, on the commit that does it, rather than in a
    utility's migration.
    """
    from apps.customers import services as customers_services
    from apps.customers import import_writer

    offenders = [
        f"{fn.__module__}.{fn.__name__}"
        for fn in (
            customers_services.create_from_import,
            customers_services.update_from_import,
            customers_services.link_customer,
            import_writer.write_opening_buckets,
        )
        if _is_role_guarded(fn)
    ]
    assert offenders == [], (
        "a deferred import stage runs as `_JobActor`, which carries no role, so "
        "a @require_role on any of these can only ever produce a false refusal "
        f"(DEF-2487, DEF-2515, DEF-1108): {offenders}"
    )


def _is_role_guarded(fn: Any) -> bool:
    """Does `require_role` wrap this callable? `__code__` does NOT unwrap, and
    the wrapper closes over `allowed_set` — see `test_def2515_worker_has_no_role`
    for why `inspect.getsource` reports clean over a live defect."""
    code = getattr(fn, "__code__", None)
    return bool(code is not None and "allowed_set" in (code.co_freevars or ()))


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2487 (critical) + CR-050 — reported by the Product Owner on a screen share,
#   utility ottumwa-water-works, build v2.81.1, 1,048 accounts
# generated: 2026-08-30 by the DEF-2487 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def2487_accounts_async_bar.py 15 passed✔ ·
#   tests/test_cr026_background_stages.py + test_def1108_deferred_load_approver.py +
#   test_def2515_worker_has_no_role.py: 5 failed / 24 passed, and all five are the SAME five
#   that fail on the tip with this lane's files reverted (proved by running them against a
#   copy of 06-backend holding HEAD's versions of the five changed modules) ·
#   tests/test_cr047_*.py 73 passed✔ · run_gates: the one gate this lane moved was G35
#   version-lockstep, and it PASSES at 2.83.0
# exceptions: the timing figures are CONSTANTS here rather than measurements — this suite runs
#   on in-memory SQLite with no web server in front of it, so it cannot time the thing that
#   broke. `10-scripts/def2487_accounts_bar_benchmark.py` is the measurement, and it is a
#   script and not a case for the reason CR-026's own benchmark gives · the live proofs that
#   only three processes can give (the gunicorn kill, the deferred load through a real Celery
#   worker, and the no-worker refusal against a real Redis) are recorded in the decision log
#   entry of 2026-08-30, not here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
