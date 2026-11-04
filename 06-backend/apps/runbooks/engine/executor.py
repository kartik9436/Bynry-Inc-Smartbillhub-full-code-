# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 · US-RBS-002 (EP-RBS-01) — CR-075 wave B task B3: pin
#           scope · evaluate · per-record steps in their own SAVEPOINT · set
#           steps once · close.
# Rules:    BR-RBS-003 (dry and live are the SAME code path, differing only in
#           whether the writer is bound) · BR-RBS-007 (every record executes in
#           its own savepoint; one failure never aborts the run) · BR-RBS-009
#           (scope resolved ONCE and pinned) · BR-RBS-012 (guards are absolute,
#           evaluated before any step) · BR-RBS-020 (the report is composed at
#           close and frozen) · BR-RBS-023 (a step declares its mode) ·
#           CLAUDE.md hard-won law 14 (a savepoint is the ONLY option on
#           PostgreSQL, and SQLite cannot see the difference)
# Tests:    06-backend/tests/test_us_rbs_015_conformance.py (TC-RBS-15,
#           TC-RBS-17, TC-RBS-22) · 06-backend/tests/test_rbs_savepoint_pg.py
#           (TC-RBS-5 — PostgreSQL only, skipped in RED on SQLite)
# Impacts:  apps/runbooks/services.py · apps/runbooks/registry.py
# ───────────────────────────────────────────────────────
"""The executor — one code path for a dry run and a live one.

    scope = resolve(params)          ← ONCE, pinned, fingerprinted
    guards                           ← absolute, before any step
    steps in declaration order:
        mode "set"        → run ONCE over the whole pinned set
        mode "per_record" → run once per subject, each in its OWN SAVEPOINT
    close                            ← compose report, validate, FREEZE

⚠⚠ **THE SAVEPOINT IS NOT THE TIDY OPTION. IT IS THE ONLY OPTION, AND THE
TEST SUITE CANNOT TELL YOU THAT.** This paragraph is in the code rather than in
a document because the next lane will otherwise "simplify" it away, and every
check in this repository will agree with them.

On PostgreSQL, **one failed statement aborts the entire transaction**. Written
the obvious way —

    for subject in subjects:
        try:
            step.run(ctx, subject)
        except IntegrityError:
            continue                 # ← WRONG, and green on every machine

— the first refused row poisons the transaction, every later query raises
`InFailedSqlTransaction`, and **the whole run is lost at COMMIT**. Wrapping each
record in a nested `transaction.atomic()` issues a real `SAVEPOINT`, so the
failed record rolls back to its own savepoint and the transaction survives.

**`config/settings/test.py` hardcodes in-memory SQLite, which has no
aborted-transaction state at all**, so the broken version above passes the
entire suite, green, on every machine, and fails the first time a real row is
refused in production. Two lanes found this independently on 2026-08-29, in
different modules, weeks apart — hard-won law 14. `TC-RBS-5` therefore lives in
`tests/test_rbs_savepoint_pg.py`, runs under `config.settings.local` with a real
`DATABASE_URL`, and **SKIPS rather than passing** wherever only SQLite is
available.

⚠ **DRY AND LIVE ARE ONE PATH** (`BR-RBS-003`). There is no `if mode == "dry"`
anywhere below and there must never be one. The only difference is what
`ExecutionContext.ports` holds: a mapping of bound writers, or nothing. A dry
run that walked a different path would prove nothing about the live one, which
is why `TC-RBS-2` is first shown red on a deliberately divergent second
implementation.

⚠ **A CHECK'S CONTEXT HOLDS NO PORTS AT ALL** (`BR-RBS-002`) — not an empty
allow-list it is trusted not to use, and not writers that refuse. `ports_for()`
returns `()` for a Check, `RunbookDefinition` refuses a Check that declares one,
and `ExecutionContext.port()` raises naming the runbook. Three layers, because
this is the sentence that lets two people press **Run ▶** on a thousand
accounts.

⚠ **WHAT THIS EXECUTOR DELIBERATELY DOES NOT DO, AND WHY EACH.**

* **It writes no `runbook_run_records` row.** That table's `idempotency_key` is
  `NOT NULL`, and **how it is composed contradicts itself across our own
  documents** — `BR-RBS-008` names the RUN as a component and `TC-RBS-4`'s
  worked figure (*248 notices, not 496*) requires that it does not. That is
  `DEF-RBS-4246`, minted as `OQ-RBS-1737`, and it is OPEN. Writing a record row
  here would mean composing a key, so the per-record outcomes are carried in
  memory and returned; wave C persists them once the question is answered. **A
  lane arriving here to add that write must read `OQ-RBS-1737` first** — with the
  run in the key, a same-day re-run of the ladder sends 496 notices where 248
  were meant.
* **It raises no work item — it COMPUTES them, and `services.close_run` writes
  them** (`CR-075` wave H, `US-RBS-006`). ⚠ **This bullet said *"the
  upsert-by-fingerprint is wave C's, with the first Check in front of it"* until
  2026-09-07 and it is amended rather than deleted**, because a stale
  instruction in a docstring is exactly what a lane reads and follows (the
  status-column law, `DEF-WRK-4030`). Raising a work item IS an engine act
  (`BR-RBS-022`) and `raise_work_item` is refused BY NAME as a port — a
  fourteenth port would give every Check the ability to write. What lives here
  is `definition.findings(view)`, computed from the same view `report()` gets
  and carried on `RunResult.findings`; `engine/work_items.py` turns those into
  rows at close, upserted by a fingerprint that never contains the run id.
* **It writes no audit row.** Also an engine act, also wave L's — and
  `BR-RBS-015` waits on the audit module, because a blank actor today means *a
  system job* and every automation in the product is indistinguishable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from django.db import DatabaseError, transaction

from apps.runbooks import interfaces
from apps.runbooks.boundary import PortDeclaration
from apps.runbooks.engine import acts, stop, work_items
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    Finding,
    RunbookContractError,
    RunbookDefinition,
    SubjectRef,
    scope_fingerprint,
    validate_report,
)

#: What a per-record step's outcome is called when it raised. The word is the
#: engine's, not a runbook's, so the Records block can draw a consistent tone
#: for something no rule decided.
OUTCOME_FAILED = "failed"
OUTCOME_SKIPPED = "skipped"


class GuardedSubject(Exception):
    """Raised by nothing — a guard returns True; this exists only to be cited.

    Left out on purpose: a guard is not an exception path. It is evaluated
    before any step and the subject is simply not walked (`BR-RBS-012`).
    """


class CapExceeded(Exception):
    """**The run is REFUSED. It is never truncated** — `BR-RBS-006`, task `L4`.

    ⚠ **TRUNCATING IS THE OBVIOUS BUILD AND IT IS THE ONE THE RULE FORBIDS**,
    which is why this is an exception and not a slice. `EP-RBS-04` names *a
    build that truncates* as the wrong build `TC-RBS-3` is first shown red on:
    a ladder that quietly acted on the first 400 of 835 would report a clean
    run, and **the 435 nobody sent to are invisible** — no row, no count, no
    sentence. A refusal is loud, names both numbers, and leaves the clerk the
    three choices `L4` gives them (narrow the scope, raise the limit, send the
    first 400 deliberately).

    ⚠ **IT IS RAISED AFTER THE GUARDS AND BEFORE ANY STEP.** The number the cap
    is compared against is the number of subjects that would be WALKED — the
    pinned set minus the guarded — because that is the number of things the run
    would do, and comparing against the pinned set would refuse a run of 1,035
    accounts of which 62 are protected and 835 would be acted on. Both figures
    travel on the exception so the sentence can carry them.

    ⚠ **A CAP OF `None` IS A TENANT WHO HAS NOT SET ONE, NOT A LIMIT OF ZERO.**
    That reading is `CR-075` wave `Q′`'s, recorded in the decision log of
    2026-09-06, and it is asserted rather than left implicit because the other
    reading refuses every run at every utility that has not been to the Limits
    tab.
    """

    def __init__(self, *, planned: int, cap: int, pinned: int) -> None:
        self.planned = planned
        self.cap = cap
        self.pinned = pinned
        super().__init__(
            f"this run would act on {planned} records and the limit is {cap}. "
            "A cap refuses the run and never truncates it (BR-RBS-006): narrow the "
            "scope, raise the limit, or send the first ones deliberately."
        )


@dataclass
class ExecutionContext:
    """What a step is handed. **A Check's `ports` is empty and cannot be filled.**

    `params` are the runbook's declared parameters, already resolved for this
    run. `seams` is where wave C hands a step its read functions; it is empty
    here because the seams name no selector yet — wave A left them bound to
    nothing deliberately, since naming a selector no module exposes fails `G20`
    and naming one nothing calls is dead code.
    """

    runbook_key: str
    tenant_id: Any = None
    run_id: Any = None
    #: The runbook's display NAME, carried so `acts.actor_for` can put
    #: *"Collections ladder, version 1"* in the trail rather than a key
    #: (`BR-RBS-015`, B14 rule 31 — no database id is ever the visible value).
    runbook_name: str = ""
    #: `dry` or `live`. ⚠ **NOTHING BELOW BRANCHES ON IT** (`BR-RBS-003`) — it
    #: is read ONCE, in `build_context`, to decide whether the ports handed to a
    #: step carry writers, and it travels here only so a record row can say
    #: which kind of run wrote it.
    mode: str = "dry"
    params: Mapping[str, Any] = field(default_factory=dict)
    ports: Mapping[str, PortDeclaration] = field(default_factory=dict)
    seams: Mapping[str, Any] = field(default_factory=dict)
    #: Set by the executor before the per-record pass so a per-record step can
    #: read what a set step computed — each meter's own normal, say.
    set_results: dict[str, Any] = field(default_factory=dict)

    def port(self, name: str) -> PortDeclaration:
        """The writer for `name`, or a refusal that says which layer refused.

        A Check reaching here at all is a bug that `RunbookDefinition` should
        already have refused at construction; the message says so rather than
        pretending this is an ordinary missing key, because the two have very
        different fixes.
        """
        try:
            return self.ports[name]
        except KeyError:
            raise RunbookContractError(
                f"runbook {self.runbook_key!r} asked for port {name!r} and holds none by that "
                "name. A Check holds NO ports at all (BR-RBS-002) — the capability is absent, "
                "not merely unused — and an Action holds only the ports it declared."
            ) from None


@dataclass(frozen=True)
class RecordOutcome:
    """One subject's result. The plan and the outcome belong in one row.

    *What did it say it would do versus what it did* is the audit
    (`03-field-map.md` §4). Persisting these is wave C's, once `OQ-RBS-1737`
    says how the idempotency key is composed — see the module docstring.
    """

    subject: SubjectRef
    step_key: str
    outcome: str
    reason: str = ""
    decided_by_rule: str = ""
    fix_route: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Everything a run produced, before anything is written to a row."""

    runbook_key: str
    subjects: tuple[SubjectRef, ...]
    scope_fingerprint: str
    guarded: tuple[SubjectRef, ...]
    set_results: dict[str, Any]
    records: tuple[RecordOutcome, ...]
    counts: dict[str, int]
    report: list[dict[str, Any]]
    #: How many times each step actually ran. `TC-RBS-17` asserts a set step
    #: executes ONCE and a per-record step once per subject; without this it
    #: would be asserted by counting side effects, which is how a test ends up
    #: named after an assertion it does not make.
    step_runs: dict[str, int]
    #: The step a Stop landed inside, or `""`. `CR-075` wave L task L5 — a run
    #: that was stopped and one that simply had fewer subjects produce the same
    #: short record list, and only this tells them apart.
    stopped_at_step: str = ""
    #: What the run leaves on somebody's desk (`CR-075` wave H, `US-RBS-006`).
    #:
    #: ⚠ **COMPUTED HERE, WRITTEN BY `services.close_run` — the same split
    #: `report` already has, and for the same reason.** The executor writes no
    #: row at all: it pins a scope, walks steps and composes what the run
    #: produced. Turning a `Finding` into a `work_items` row is durable, so it
    #: belongs on the other side of that line — and `work_items` is written by
    #: the ENGINE and never by a port (`BR-RBS-022`), which is what lets a Check
    #: holding no writer populate `RBS-007`.
    findings: tuple[Finding, ...] = ()


def build_context(
    definition: RunbookDefinition,
    *,
    tenant_id: Any = None,
    run_id: Any = None,
    mode: str = "dry",
    params: Mapping[str, Any] | None = None,
) -> ExecutionContext:
    """The one place a runbook's writers are decided — and a Check gets none.

    `interfaces.ports_for(kind)` returns `()` for a Check, so the mapping below
    is empty for one, always. For an Action it holds the DECLARATIONS the
    runbook named.

    ⚠ **THIS IS WHERE — AND THE ONLY WHERE — DRY DIFFERS FROM LIVE**
    (`BR-RBS-003`). From `CR-075` wave L the thirteen declarations carry real
    writers, so *"nothing can be written"* stops being true of the declaration
    and has to become true of the CONTEXT. A dry run, and a live run of a
    runbook that is not on `acts.LIVE_ENABLED_RUNBOOKS`, is handed a copy of
    each port with `writer=None`: `port.is_bound` is False, `acts.act()` records
    what it WOULD do, and every statement a live run walks is walked. That set
    is **empty in wave L** — phase 2 ships the acting half with sending switched
    off and wave `N` turns the first runbook on.

    A branch inside a step would prove nothing about the live path; this
    substitution proves all of it except the one call at the end.
    """
    allowed = {p.name for p in interfaces.ports_for(definition.kind)}
    ports = {
        name: interfaces.PORTS[name] for name in definition.ports if name in allowed
    }
    if mode != "live" or not acts.live_enabled(definition.key):
        ports = {name: replace(port, writer=None) for name, port in ports.items()}
    return ExecutionContext(
        runbook_key=definition.key,
        tenant_id=tenant_id,
        run_id=run_id,
        runbook_name=definition.name,
        mode=mode,
        params=dict(params or {}),
        ports=ports,
    )


def pin_scope(
    definition: RunbookDefinition, ctx: ExecutionContext
) -> tuple[tuple[SubjectRef, ...], str]:
    """Resolve ONCE and freeze — `BR-RBS-009`, `TC-RBS-22`.

    An account that becomes past due mid-run is not in the review list and is
    not acted on. The fingerprint is what a later reader uses to prove the set
    did not move; it is **not** an idempotency key and must never be used as one
    (`OQ-RBS-1737`).

    Every subject `resolve()` returns must be a `SubjectRef` of the runbook's
    own declared subject type. A runbook that resolves accounts while declaring
    `subject_type = "meter"` would draw a Records table whose rows do not match
    its own columns, and nothing downstream could tell.
    """
    subjects = tuple(definition.resolve(ctx))
    for subject in subjects:
        if not isinstance(subject, SubjectRef):
            raise RunbookContractError(
                f"runbook {definition.key!r} resolve() returned {subject!r}, which is not a "
                "SubjectRef. resolve() is ONE function returning the pinned set."
            )
        if subject.subject_type != definition.subject_type:
            raise RunbookContractError(
                f"runbook {definition.key!r} declares subject_type "
                f"{definition.subject_type!r} and resolve() returned a "
                f"{subject.subject_type!r}. The declared unit is what the Records table's "
                "columns and the run's record count are drawn from (BR-RBS-019)."
            )
    return subjects, scope_fingerprint(subjects)


def apply_guards(
    definition: RunbookDefinition, ctx: ExecutionContext, subjects: Sequence[SubjectRef]
) -> tuple[tuple[SubjectRef, ...], tuple[SubjectRef, ...]]:
    """Split the pinned set into *walked* and *guarded*, BEFORE any step runs.

    `BR-RBS-012`: guards are **absolute**. A guarded record is skipped whatever
    the checks would have concluded, and no step ever sees it — which is the
    difference between a guard and a rule. `RBS-004.4` draws the control
    disabled with its reason rather than hiding it.
    """
    walked: list[SubjectRef] = []
    guarded: list[SubjectRef] = []
    for subject in subjects:
        if any(guard.applies(ctx, subject) for guard in definition.guards):
            guarded.append(subject)
        else:
            walked.append(subject)
    return tuple(walked), tuple(guarded)


def execute(
    definition: RunbookDefinition,
    *,
    tenant_id: Any = None,
    run_id: Any = None,
    mode: str = "dry",
    params: Mapping[str, Any] | None = None,
    ctx: ExecutionContext | None = None,
    cap: int | None = None,
) -> RunResult:
    """Run it. One path for dry and live; the writer is bound or it is not.

    Steps run in DECLARATION ORDER. That is what lets a runbook compute each
    meter's own normal in a set step and then use it in the per-record pass —
    the shape `12-the-contract.md` §3 draws for runbooks 11 and 21 — and it is
    why the mode is per step rather than per runbook.

    `cap` is the tenant's own limit from the runbook row (`L4`). It is checked
    HERE rather than at the endpoint because *"the planned count exceeds the
    cap"* cannot be known before the scope is resolved, and because every run in
    this product — a route, a schedule, a management command, the conformance
    suite — comes through this function while only one of them comes through an
    endpoint. See `CapExceeded`.
    """
    ctx = ctx or build_context(
        definition, tenant_id=tenant_id, run_id=run_id, mode=mode, params=params
    )
    subjects, fingerprint = pin_scope(definition, ctx)
    walked, guarded = apply_guards(definition, ctx, subjects)
    if cap is not None and len(walked) > cap:
        raise CapExceeded(planned=len(walked), cap=cap, pinned=len(subjects))

    records: list[RecordOutcome] = []
    step_runs: dict[str, int] = {}
    #: The step a Stop landed inside, or "" — carried onto `RunResult` so the
    #: Records block can say *"the records after this point were not looked
    #: at"* rather than leaving a clerk to infer it from a short list.
    stopped_at_step = ""

    for step in definition.steps:
        if step.mode == MODE_SET:
            # ── SET: once over the whole pinned set, whatever its size. ──
            # A tie-out over 1,410 bills, a totals comparison, each meter's own
            # normal. Registering one of these as per-record is what `TC-RBS-17`
            # goes red on: it would run 1,410 times and compare a set with
            # itself.
            step_runs[step.key] = step_runs.get(step.key, 0) + 1
            ctx.set_results[step.key] = step.run(ctx, walked)
            continue

        if step.mode != MODE_PER_RECORD:  # pragma: no cover — refused at construction
            raise RunbookContractError(
                f"runbook {definition.key!r} step {step.key!r} has mode {step.mode!r} at run "
                "time, which construction should have refused (BR-RBS-023)."
            )

        for subject in walked:
            # ⚠ STOP IS ASKED HERE, AT THE TOP OF EVERY ITERATION, AND READ
            # FRESH FROM THE DATABASE (`US-RBS-012`: *"stopping halts before the
            # next record"*). The person pressing Stop is in another process, so
            # a value captured when the run started cannot see them — that is
            # `EP-RBS-04`'s *"a stop that only sets a flag"*, and it is the
            # build `TC-RBS-9` is first shown red on. Records already acted stay
            # acted: nothing below un-writes anything (hard rule 4).
            if stop.stopped(ctx):
                stopped_at_step = step.key
                break
            step_runs[step.key] = step_runs.get(step.key, 0) + 1
            records.append(_run_one_record(step, ctx, subject))
        if stopped_at_step:
            break

    counts = _count(records, guarded)
    # ⚠ **ONE VIEW, HANDED TO BOTH.** `report()` and `findings()` answer two
    # questions about the same run — *what does a reader see* and *what is left
    # on somebody's desk* — and building the view twice would let them be built
    # from two different snapshots of `ctx.set_results`.
    view = _ReportView(
        definition=definition,
        subjects=subjects,
        guarded=guarded,
        records=tuple(records),
        counts=counts,
        set_results=dict(ctx.set_results),
    )
    report = validate_report(definition.report(view), runbook_key=definition.key)
    findings = tuple(work_items.collect(definition, view))
    return RunResult(
        runbook_key=definition.key,
        subjects=subjects,
        scope_fingerprint=fingerprint,
        guarded=guarded,
        set_results=dict(ctx.set_results),
        records=tuple(records),
        counts=counts,
        report=report,
        step_runs=step_runs,
        stopped_at_step=stopped_at_step,
        findings=findings,
    )


def _run_one_record(step: Any, ctx: ExecutionContext, subject: SubjectRef) -> RecordOutcome:
    """One subject, inside its OWN SAVEPOINT. Read the module docstring first.

    ⚠⚠ **`transaction.atomic()` HERE IS A SAVEPOINT AND IT IS LOAD-BEARING.**
    It is nested inside whatever transaction the caller opened, so Django issues
    `SAVEPOINT` / `ROLLBACK TO SAVEPOINT` rather than `BEGIN` / `ROLLBACK`. On
    PostgreSQL that is the ONLY thing that lets the run continue after a refused
    row: without it the first `IntegrityError` aborts the whole transaction and
    **every later record is lost at COMMIT**, however carefully the exception
    was caught.

    **Do not simplify this to `try: step.run(...) except DatabaseError:
    continue`.** That version passes the entire test suite green — the suite is
    in-memory SQLite, which has no aborted-transaction state — and loses the run
    the first time a real row is refused in production. Hard-won law 14, found
    independently by two lanes on 2026-08-29. `TC-RBS-5` proves this on real
    PostgreSQL and skips here.

    ⚠ **THE EXCEPTION IS `DatabaseError`, NOT `IntegrityError`.** A refused row
    is the common case, but a check constraint, a deadlock and a statement
    timeout all abort a PostgreSQL transaction exactly the same way, and a
    savepoint recovers from all of them. Catching only `IntegrityError` would
    leave the widest class of aborts uncovered while looking handled — the same
    shape as reading `exc.__cause__` one hop and returning the generic sentence
    for every row.
    """
    try:
        with transaction.atomic():
            outcome = step.run(ctx, subject)
    except DatabaseError as exc:
        return RecordOutcome(
            subject=subject,
            step_key=step.key,
            outcome=OUTCOME_FAILED,
            reason=str(exc),
        )
    if isinstance(outcome, RecordOutcome):
        return outcome
    if isinstance(outcome, str):
        return RecordOutcome(subject=subject, step_key=step.key, outcome=outcome)
    if isinstance(outcome, Mapping):
        return RecordOutcome(
            subject=subject,
            step_key=step.key,
            outcome=str(outcome.get("outcome", "")),
            reason=str(outcome.get("reason", "")),
            decided_by_rule=str(outcome.get("decided_by_rule", "")),
            fix_route=str(outcome.get("fix_route", "")),
            data=dict(outcome.get("data", {})),
        )
    raise RunbookContractError(
        f"runbook {ctx.runbook_key!r} step {step.key!r} returned {outcome!r}. A per-record step "
        "returns an outcome — a RecordOutcome, a mapping or the outcome word — because every "
        "record states the rule that decided it, in words a clerk can read (BR-RBS-010)."
    )


def _count(records: Sequence[RecordOutcome], guarded: Sequence[SubjectRef]) -> dict[str, int]:
    """Per-outcome counts, INCLUDING the ones with no record row.

    `BR-RBS-035`: a volume runbook keeps a record row for anything acted on or
    flagged and **a count per outcome for the rest**. A guarded subject has no
    record row at all — no step saw it — so it would vanish from every total if
    the counts were derived from the rows alone.
    """
    counts: dict[str, int] = {}
    for record in records:
        counts[record.outcome] = counts.get(record.outcome, 0) + 1
    if guarded:
        counts[OUTCOME_SKIPPED] = counts.get(OUTCOME_SKIPPED, 0) + len(guarded)
    return counts


@dataclass(frozen=True)
class _ReportView:
    """What `report(run)` is handed — everything the run produced, read-only.

    A frozen dataclass rather than the `RunbookRun` row on purpose: the report
    is composed from **records and counts** (`12-the-contract.md` §1), and
    handing a report function the database row would let it read a column that
    changes after the run closes, which is exactly what `BR-RBS-020`'s freeze
    exists to prevent.
    """

    definition: RunbookDefinition
    subjects: tuple[SubjectRef, ...]
    guarded: tuple[SubjectRef, ...]
    records: tuple[RecordOutcome, ...]
    counts: Mapping[str, int]
    set_results: Mapping[str, Any]

    @property
    def record_count(self) -> int:
        """The count a clerk reads — 1,840 meter-days, never 176,640 intervals."""
        return len(self.records)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-015 · US-RBS-002 (EP-RBS-01; CR-075 wave B task B3)
# generated: 2026-09-06 by the CR-075 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave B — the routes are wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H=n/a(no 🔒 path: no idempotency key is composed here — OQ-RBS-1737 is open and wave L owns it)
# gates: pytest tests/test_us_rbs_015_conformance.py · pytest tests/test_rbs_savepoint_pg.py (PostgreSQL) · G115
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
