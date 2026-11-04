# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 (EP-RBS-01) TC-RBS-5 — CR-075 wave B task B5: the
#           per-record savepoint, on real PostgreSQL, where it is the only
#           thing that works.
# Rules:    BR-RBS-007 (every record executes in its OWN savepoint; one failure
#           never aborts the run) · BR-RBS-023 (a per-record step runs once per
#           subject in its own savepoint) · CLAUDE.md hard-won law 14 (a failed
#           statement poisons the whole PostgreSQL transaction, and the test
#           suite is SQLite, which does not) · hard-won law 7 (a check that
#           cannot fail is the defect)
# Tests:    this file
# Impacts:  apps/runbooks/engine/executor.py::_run_one_record
# ───────────────────────────────────────────────────────
"""TC-RBS-5 — one record fails a database constraint; the others still commit.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_rbs_savepoint_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE:** `config/settings/test.py`
hardcodes in-memory SQLite, **SQLite has no aborted-transaction state**, and the
broken implementation this file exists to refuse — `try: step.run(...) except
IntegrityError: continue`, with no savepoint — **passes the entire default suite
green on every machine**. It then loses the whole run the first time a real row
is refused in production. Two lanes found that independently on 2026-08-29, in
different modules, weeks apart; it is hard-won law 14.

Every case here carries `requires_postgres` and **SKIPS on the default suite
rather than passing vacuously** — `G5` once ran the isolation suite on SQLite
and called 192 skips a pass, which is the exact failure this note exists to keep
out of the record.

⚠ **THE NEGATIVE CASE IS THE POINT OF THE FILE, NOT A BONUS.**
`test_..._the_naive_version_loses_the_run` implements the obvious wrong code
*in the test* and asserts PostgreSQL punishes it. Without that, a green here
would prove only that the happy path works — and a later lane "simplifying" the
savepoint away would meet a suite that agrees with them. The refusal text
PostgreSQL actually produced is quoted in that case's docstring.

WHAT THE FIXTURE WRITES, AND WHY IT IS `work_items`
----------------------------------------------------
A per-record step needs a real database write to have anything to fail at.
`work_items` carries `UNIQUE (tenant_id, fingerprint)` (`BR-RBS-017` — the
upsert that makes thirty daily sweeps one item ageing), so planting a row and
then asking a step to insert the same fingerprint produces a genuine
`IntegrityError` from PostgreSQL rather than a simulated one.

⚠ **`runbook_run_records` IS DELIBERATELY NOT USED, AND THAT IS NOT A STYLE
CHOICE.** Its `idempotency_key` is `NOT NULL`, and **how that key is composed
contradicts itself across our own documents** — `BR-RBS-008` names the RUN as a
component and `TC-RBS-4`'s worked figure requires that it does not, because with
the run in the key a same-day re-run of the ladder sends **496 notices where 248
were meant**. That is `DEF-RBS-4246`, minted as `OQ-RBS-1737`, and it is OPEN.
Writing a record row here would mean composing a key in test code that a later
lane would copy into the engine. Nothing in this module composes one.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from apps.runbooks import models
from apps.runbooks.contract import MODE_PER_RECORD, Block, RunbookDefinition, Step, SubjectRef
from apps.runbooks.engine import executor
from tests.isolation_helpers import live_tenant_context, requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

#: Four subjects, and the SECOND one is the poisoned record. It is second rather
#: than first on purpose: if it were first, a run that recovered by starting
#: over would look identical to a run that recovered by savepoint.
SUBJECT_IDS = ("a-1", "poisoned", "a-3", "a-4")

#: The fingerprint the fixture plants and the step then tries to insert again.
DUPLICATE_FINGERPRINT = "rbs:tc5:already-here"


def _resolve(ctx):
    return [SubjectRef(subject_type="account", subject_id=i, label=i) for i in SUBJECT_IDS]


def _report(view):
    return [Block(block="kpis", payload={"examined": view.record_count})]


def _write_a_work_item(tenant):
    """The per-record step: insert one `work_items` row per subject.

    The poisoned subject reuses a fingerprint the fixture already planted, so
    PostgreSQL refuses that INSERT with a real unique-violation.
    """

    def step(ctx, subject):
        fingerprint = (
            DUPLICATE_FINGERPRINT
            if subject.subject_id == "poisoned"
            else f"rbs:tc5:{subject.subject_id}"
        )
        models.WorkItem.objects.create(
            tenant=tenant,
            source_kind=models.WORK_ITEM_SOURCE_FINDING,
            fingerprint=fingerprint,
            title=f"finding for {subject.subject_id}",
        )
        return "raised"

    return step


def _definition(tenant) -> RunbookDefinition:
    return RunbookDefinition(
        key="tc_rbs_5_probe",
        name="Savepoint probe",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="account",
        unit_of_work="account",
        resolve=_resolve,
        report=_report,
        steps=(
            Step(
                key="raise_finding",
                label="Raise a finding",
                mode=MODE_PER_RECORD,
                run=_write_a_work_item(tenant),
            ),
        ),
    )


def _plant_the_collision(tenant):
    models.WorkItem.objects.create(
        tenant=tenant,
        source_kind=models.WORK_ITEM_SOURCE_FINDING,
        fingerprint=DUPLICATE_FINGERPRINT,
        title="planted, so the second subject collides",
    )


# ── the case the plan asks for ────────────────────────────────────────────


@requires_postgres
@pytest.mark.django_db
def test_tc_rbs_5_one_record_fails_its_constraint_and_the_others_commit(brazos):
    """`TC-RBS-5` — four subjects, one refused, **three still commit**.

    `BR-RBS-007`: every record executes in its own savepoint and one failure
    never aborts the run. The count is the whole assertion: **3 of 4**, plus the
    one planted row, is 4 rows in `work_items` when the transaction commits, and
    the refused record is reported as `failed` with the database's own reason on
    it rather than vanishing.

    ⚠ **THE COUNT IS TAKEN INSIDE THE SAME TRANSACTION, AND THAT IS THE PROOF
    RATHER THAN A SHORTCUT — THE FIRST DRAFT OF THIS DOCSTRING SAID THE
    OPPOSITE AND WAS WRONG.** It claimed the damage of a missing savepoint
    lands *at COMMIT*, so the case had to run with `transaction=True`. What
    PostgreSQL actually does is abort the transaction at the refused statement,
    and **the very next query raises** — which is what the negative case below
    catches, verbatim. So the counting query IS the assertion: under the shipped
    executor it returns 4, and under the naive version it cannot run at all.
    Written down because a docstring describing a mechanism it never observed is
    hard-won law 1, and this one had to be corrected after watching the run.
    """
    with live_tenant_context(brazos.id):
        _plant_the_collision(brazos)
        definition = _definition(brazos)

        with transaction.atomic():
            result = executor.execute(definition, tenant_id=brazos.id)

        # the run survived, and it says which record did not
        assert len(result.records) == 4
        failed = [r for r in result.records if r.outcome == executor.OUTCOME_FAILED]
        assert len(failed) == 1
        assert failed[0].subject.subject_id == "poisoned"
        assert "unique" in failed[0].reason.lower() or "duplicate" in failed[0].reason.lower()

        # and — the assertion SQLite cannot make — the other three are DURABLE
        assert models.WorkItem.objects.count() == 4
        assert set(
            models.WorkItem.objects.values_list("fingerprint", flat=True)
        ) == {
            DUPLICATE_FINGERPRINT,
            "rbs:tc5:a-1",
            "rbs:tc5:a-3",
            "rbs:tc5:a-4",
        }


@requires_postgres
@pytest.mark.django_db
def test_tc_rbs_5_the_naive_version_loses_the_run_on_postgresql(brazos):
    """⚠ **THE MUST-FIRST-FAIL CASE — the obvious wrong code, punished here.**

    This is `try: step.run(...) except IntegrityError: continue` with **no
    savepoint**, written out in the test rather than described, because a check
    whose failure mode you cannot demonstrate is a check you do not understand
    (hard-won law 7, habit 2).

    **On SQLite this loop completes and writes three rows.** On PostgreSQL the
    refused INSERT aborts the transaction and the very next statement raises,
    verbatim:

        django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of the
        'atomic' block.

    So the assertion is that it RAISES. The day someone deletes the savepoint
    from `executor._run_one_record`, the case above goes red here and this one
    stays green — which is what tells the next reader that the two cases are
    testing the same thing from opposite sides.
    """
    with live_tenant_context(brazos.id):
        _plant_the_collision(brazos)
        step = _write_a_work_item(brazos)
        subjects = _resolve(None)
        ctx = executor.ExecutionContext(runbook_key="naive")

        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic():
                for subject in subjects:
                    try:
                        step(ctx, subject)  # ← NO savepoint. This is the bug.
                    except IntegrityError:
                        continue
        assert "transaction" in str(caught.value).lower()


@requires_postgres
@pytest.mark.django_db
def test_tc_rbs_5_a_set_step_that_fails_is_not_swallowed(brazos):
    """A SET step has no savepoint and must not pretend to.

    `BR-RBS-007` is about RECORDS. A set step runs once over the whole pinned
    set — a tie-out, a totals comparison — and there is nothing to skip past: if
    it fails, the run fails. Catching it per-record would silently turn one
    broken tie-out into a clean-looking run, which is the most dangerous shape
    this product has.
    """
    from apps.runbooks.contract import MODE_SET

    def failing_set_step(ctx, subjects):
        raise IntegrityError("the tie-out could not be computed")

    definition = RunbookDefinition(
        key="tc_rbs_5_set",
        name="Set probe",
        kind=models.KIND_CHECK,
        category="finance",
        subject_type="account",
        unit_of_work="account",
        resolve=_resolve,
        report=_report,
        steps=(Step(key="tie_out", label="Tie out", mode=MODE_SET, run=failing_set_step),),
    )
    with live_tenant_context(brazos.id):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                executor.execute(definition, tenant_id=brazos.id)


@requires_postgres
@pytest.mark.django_db
def test_tc_rbs_5_a_deadlock_shaped_error_is_recovered_too_not_only_integrity(brazos):
    """The catch is `DatabaseError`, not `IntegrityError`, and that is deliberate.

    A refused row is the common case, but a check constraint, a deadlock and a
    statement timeout all abort a PostgreSQL transaction the same way, and a
    savepoint recovers from all of them. Catching only `IntegrityError` would
    leave the widest class of aborts uncovered **while looking handled** — the
    same shape as reading `exc.__cause__` one hop and returning the generic
    sentence for every row.

    Provoked here with a genuine PostgreSQL error that is not an integrity
    violation: a division by zero inside the statement.
    """
    from django.db import connection

    def divide_by_zero(ctx, subject):
        if subject.subject_id == "poisoned":
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 / 0")
        models.WorkItem.objects.create(
            tenant=brazos,
            source_kind=models.WORK_ITEM_SOURCE_FINDING,
            fingerprint=f"rbs:tc5:div:{subject.subject_id}",
            title=subject.subject_id,
        )
        return "raised"

    definition = RunbookDefinition(
        key="tc_rbs_5_div",
        name="Division probe",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="account",
        unit_of_work="account",
        resolve=_resolve,
        report=_report,
        steps=(
            Step(key="divide", label="Divide", mode=MODE_PER_RECORD, run=divide_by_zero),
        ),
    )
    with live_tenant_context(brazos.id):
        with transaction.atomic():
            result = executor.execute(definition, tenant_id=brazos.id)
        failed = [r for r in result.records if r.outcome == executor.OUTCOME_FAILED]
        assert len(failed) == 1
        assert models.WorkItem.objects.count() == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-015 (EP-RBS-01; CR-075 wave B task B5)
# generated: 2026-09-06 by the CR-075 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave B) E=n/a(no screen in wave B) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_rbs_savepoint_pg.py under config.settings.local with DATABASE_URL
# exceptions: every case SKIPS on the default SQLite suite and says why — the guarantee cannot exist there (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
