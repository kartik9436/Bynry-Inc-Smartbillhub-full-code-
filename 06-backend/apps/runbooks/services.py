# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3: the write path.
#           US-RBS-015 (EP-RBS-01) — CR-075 wave B task B3: open_run/close_run.
# Rules:    B1 (the engine writes this module's own seven tables; an Action
#           writes another module's data ONLY through a port, after the gate) ·
#           BR-RBS-002 (a Check is CONSTRUCTED with no ports — a write from one
#           is a construction error, not a runtime refusal) · BR-RBS-020 (the
#           report is composed at close and frozen) · BR-RBS-022 (work items and
#           audit rows are the ENGINE's, never a port) · BR-RBS-038 (every edit
#           makes a new version; a run pins the version that produced it) ·
#           CLAUDE.md hard rule 7 (every money action writes audit_log) ·
#           hard-won law 14 (a per-record savepoint is the only option on
#           PostgreSQL)
# Tests:    06-backend/tests/test_us_rbs_041_module.py ·
#           06-backend/tests/test_us_rbs_015_conformance.py
# Impacts:  apps/runbooks/ports/ (the thirteen declarations, none bound) ·
#           apps/runbooks/engine/executor.py ·
#           10-scripts/gates/g115_runbooks_import_census.py ·
#           10-scripts/gates/g74_unread_tables_baseline.txt (Runbook,
#           RunbookVersion and RunbookRun get their first writer here)
# ───────────────────────────────────────────────────────
"""runbooks writes — this module's OWN seven tables, and nothing else's.

**EVERY CALLABLE HERE WRITES ONE OF THIS MODULE'S OWN SEVEN TABLES AND NOTHING
ELSE.** Phase 1 of `CR-075` ships an engine that **cannot write anything outside
this module**: no port is bound to a writer, so a runbook that tried would fail
to construct rather than fail at runtime. Wave A made that true of the boundary;
wave B adds the writers a run needs — `open_run` and `close_run` — and both of
them touch `runbooks`, `runbook_versions` and `runbook_runs` only.

THREE ROUTES TO THE DATABASE AND NO FOURTH (spec B1)
-----------------------------------------------------
1. **The engine writes these seven tables** — `runbooks`, `runbook_versions`,
   `runbook_runs`, `runbook_run_records`, `work_items`, `cutover_plans`,
   `cutover_plan_items`. That is this file's job, from wave B onwards.
2. **An Action writes another module's data ONLY through a port**, after the
   gate — `apps/runbooks/ports/`. Each port maps to ONE service function in the
   owning module. **Wave A declares all thirteen and binds none.**
3. **Every read of another module goes through a seam** this module owns —
   `apps/runbooks/seams/`.

⚠ **TWO THINGS THE ENGINE DOES THAT NO RUNBOOK MAY**, and they are the reason a
Check can be useful while holding no writer at all: **raising a work item** and
**writing an audit row**. A Check produces findings; the ENGINE upserts them
into `work_items` when the run closes. That is why `raise_work_item` is **not**
one of the thirteen ports, whatever the specification's architecture section
says (`12-the-contract.md` §6 · `03-field-map.md` D-1).

WHAT LANDS HERE, AND WITH WHICH WAVE
------------------------------------
* wave B — `open_run` / `close_run`, pinning the version at start and freezing
  the report and the scope fingerprint at close. **BUILT — this file.**
* wave C — the engine's work-item upsert (**by fingerprint**, so thirty daily
  sweeps over one missing read are one item ageing, not thirty rows), and the
  `runbook_run_records` write, which cannot be built before `OQ-RBS-1737`;
* wave L — binding the thirteen ports, each idempotent per record, each writing
  its own audit row **through the engine**, with sending switched OFF.

⚠ **THREE OF THE SEVEN TABLES ARE STILL UNWRITTEN HERE, DELIBERATELY, AND ONE
OF THEM IS BLOCKED RATHER THAN MERELY LATER.** `runbook_run_records` cannot be
written until `OQ-RBS-1737` says how `idempotency_key` is composed: the column
is `NOT NULL`, `BR-RBS-008` names the RUN as a component of the key, and
`TC-RBS-4`'s worked figure — *248 notices, not 496* — requires that it does not
(`DEF-RBS-4246`). **Nothing in this module composes such a key**, in code, in a
default or in a docstring stating it as settled. `work_items` waits on wave C's
upsert; `cutover_plans` / `cutover_plan_items` wait on wave J.

⚠ **WHEN A PER-RECORD STEP CATCHES A DATABASE ERROR AND CARRIES ON, IT MUST DO
SO INSIDE A NESTED `transaction.atomic()` — A SAVEPOINT — AND THAT IS NOT THE
TIDY OPTION, IT IS THE ONLY ONE** (hard-won law 14). On PostgreSQL a failed
statement aborts the whole transaction: `try: … except IntegrityError: continue`
loses every later write at COMMIT. **`config/settings/test.py` hardcodes
in-memory SQLite, which has no aborted-transaction state**, so the broken
version passes the entire suite green on every machine and fails the first time
a real row is refused in production. Any such code here is proved on a real
PostgreSQL before it is believed. This paragraph is in the file rather than in a
document because the next lane will otherwise "simplify" the savepoint away.
The savepoint itself lives in `engine/executor.py`; `TC-RBS-5` proves it in
`tests/test_rbs_savepoint_pg.py`, which skips where only SQLite is available.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.runbooks import contract, domains, models, selectors
from apps.runbooks.contract import RunbookDefinition, validate_report
from apps.runbooks.engine import executor
from apps.runbooks.engine.executor import RunResult
from core import errors


#: THE KEY UNDER WHICH A VERSION DOCUMENT CARRIES THE TENANT'S OWN SETTINGS.
#:
#: `03-field-map.md` §2 declares `runbook_versions.definition` as *"the whole
#: seven-part object: parameters, steps, guards, **gate, cap**, requires,
#: ports"* — and `contract.RunbookDefinition.as_definition_document()` carries
#: **neither gate nor cap**, correctly, because those two are the TENANT's and
#: not the shipped module's. `07-endpoints.md` row 3 then says a change to
#: schedule, cap, gate or enabled *"writes a new version"*.
#:
#: ⚠ **PUT TOGETHER, THOSE THREE SENTENCES ARE ONLY SATISFIABLE IF A VERSION
#: DOCUMENT HOLDS BOTH HALVES**, and a version that did not would make every cap
#: change write a document identical to the one before it — an Activity tab of
#: *"Edited"* rows with nothing to show for any of them. So the stored document
#: is the shipped definition's keys, plus this one key holding what the tenant
#: set.
#:
#: ⚠ **THE SPLIT IS ALSO WHAT MAKES A TEMPLATE UPDATE DETECTABLE AT ALL** — see
#: `pending_template_update`: the shipped half is compared with the registry and
#: the tenant half is never in that comparison, so *we changed the steps* and
#: *you raised your cap* can never be mistaken for each other.
#:
#: A version row written before this key existed simply has no `settings`, and
#: every comparison below strips the key before comparing, so an old row and a
#: new one holding the same shipped definition compare EQUAL. Nothing is
#: backfilled — `runbook_versions` is append-only (`migrations/0003`).
SETTINGS_KEY = "settings"

#: The tenant-owned fields a version document carries, and the exact set
#: `PUT /runbooks/{key}` may change. `07-endpoints.md` row 3 names *schedule,
#: cap, gate or enabled*; `visible_to_roles` is `RB-050`'s addition (*an Admin
#: may widen or narrow it per runbook*) and is stamped here rather than folded
#: in silently.
EDITABLE_SETTINGS: tuple[str, ...] = (
    "enabled",
    "trigger_kind",
    "cron",
    "event_kind",
    "timezone",
    "cap",
    "gate_mode",
    "visible_to_roles",
    # ⚠ **THE INPUT VALUES — `BR-RBS-042`, wave `T`, and it is ONE NAME ON
    # PURPOSE.** `DEF-RBS-4338`: a signed rule said a utility sets a runbook's
    # inputs and this list held eight schedule-and-limit fields, so
    # `PUT /runbooks/{key}` could not save one and `RBS-004`'s **Change scope**
    # was a button over nothing. Putting it HERE rather than on a route of its
    # own is what makes an input change behave like every other edit: it writes
    # a version (`BR-RBS-038`), it shows on the Activity tab, and it drops the
    # trust ratchet (`BR-RBS-036`) — none of which is new code.
    "parameters",
)

#: Fields a caller may NOT change through the edit route, each because a signed
#: rule says so. Refused BY NAME rather than ignored: a `PUT` that silently
#: dropped `kind` would leave the caller believing a Check had become an Action.
FROZEN_FIELDS: tuple[str, ...] = (
    "key",  # the address every run, work item and plan item cites
    "kind",  # BR-RBS-001 — declared at creation and never changed
    "category",  # BR-RBS-024 — one category, and it names the owning module
    "subject_type",  # what the runbook walks
    "unit_of_work",  # BR-RBS-019 — never the raw row
    "origin",  # how this runbook came to exist
    "template_key",  # which shipped module holds its code
    "current_version",  # system-derived; every edit moves it
    "trusted_version",  # BR-RBS-036 — the ratchet is not a field a caller sets
)


def settings_document(runbook: models.Runbook) -> dict[str, Any]:
    """What the tenant set, as the version document records it.

    One function, so the writer and the comparison cannot drift: a settings key
    added to `EDITABLE_SETTINGS` appears in the next version document, in the
    edit allow-list and in the Activity tab's change list, all at once.
    """
    return {name: getattr(runbook, name) for name in EDITABLE_SETTINGS}


def shipped_half(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """A stored version document with the tenant's settings taken back out.

    This is the half compared with the registry to decide whether a template
    update is on offer. A document written before `SETTINGS_KEY` existed has no
    such key and comes back unchanged, which is why an old v1 and a new v1 over
    the same shipped code compare equal.
    """
    return {k: v for k, v in dict(document or {}).items() if k != SETTINGS_KEY}


def _write_version(
    runbook: models.Runbook,
    *,
    document: Mapping[str, Any],
    summary: list[dict[str, Any]],
    changed_by_id: Any = None,
) -> models.RunbookVersion:
    """Append one version row and point `current_version` at it. The ONLY writer.

    `BR-RBS-038`: **every edit makes a new version**, and a version is never
    edited afterwards — `migrations/0003` puts a trigger on the table that
    refuses an UPDATE and refuses a DELETE while the runbook still exists, so
    the guarantee this module's docstring has always claimed is a fact about the
    database rather than a sentence about the code (hard-won law 1).
    """
    latest = selectors.latest_version(runbook)
    number = 1 if latest is None else latest.version + 1
    version = models.RunbookVersion.objects.create(
        tenant_id=runbook.tenant_id,
        runbook=runbook,
        version=number,
        definition=dict(document),
        summary=list(summary),
        changed_by_id=changed_by_id,
    )
    models.Runbook.objects.filter(pk=runbook.pk).update(current_version=number)
    runbook.current_version = number
    return version


def ensure_version(
    runbook: models.Runbook, definition: RunbookDefinition
) -> models.RunbookVersion:
    """The immutable snapshot a run pins — and it NEVER adopts a changed template.

    `BR-RBS-038` has two halves and this function is where they meet. **A run
    cannot pin a version that does not exist**, so a runbook with no version at
    all is bootstrapped here at v1 from the definition it is about to run. And
    **a change to a shipped template is OFFERED on a tenant's copy and never
    applied without a person accepting it** — so once a version exists, a
    divergence between the stored document and the live one mints NOTHING.

    ⚠ **THAT SECOND HALF IS A CHANGE OF BEHAVIOUR AND IT IS DELIBERATE
    (`DEF-RBS-4306`, `CR-075` wave E task `E3`).** Until this wave, a run over
    changed code minted a new version and pinned it — which reads like
    versioning working and is the rule inverted: the tenant's copy adopted our
    edit **silently, at the next run, with nobody asked**. `RBS-004.7` would
    have shown a version nobody made, and `BR-RBS-042` clause 5 names the cost —
    *a fix to one shared step lands in every runbook that uses it, and breaks
    every one of them just as fast; `BR-RBS-038` is what that risk is for.*

    ⚠ **AND A DIVERGENCE THEN STOPS THE RUN RATHER THAN RUNNING THE WRONG
    THING.** Pinning v1 while the executor walks v2's steps would put a version
    number on a report that did not produce it, which is a lie in exactly the
    record a regulator reads. `open_run` refuses instead, in five words a clerk
    can act on, and the act is one press of the *Review →* the setup screen
    draws. There is no third option that is honest: the steps are Python, so
    *run the old steps* is not a thing this engine can do.

    ⚠ **IT COMPARES THE SHIPPED HALF OF THE DOCUMENT, NOT THE VERSION NUMBER.**
    Re-registering the same code must not mint a version on every process start
    — a hundred deploys would give one runbook a hundred identical versions. The
    tenant's own settings are excluded from that comparison, so raising a cap
    can never read as a template change and shipping a step can never read as an
    edit the tenant made.

    The bootstrap row writes `changed_by = NULL`, which is correct: no person
    edited it, the code did. Its summary names `origin`, which is what
    `RBS-004.7` draws as *Added from templates*.
    """
    latest = selectors.latest_version(runbook)
    if latest is not None:
        return latest
    return _write_version(
        runbook,
        document={
            **definition.as_definition_document(),
            SETTINGS_KEY: settings_document(runbook),
        },
        summary=[{"field": "origin", "to": runbook.origin}],
    )


def open_run(
    runbook: models.Runbook,
    definition: RunbookDefinition,
    *,
    mode: str = models.MODE_DRY,
    trigger: str = models.TRIGGER_MANUAL,
    event_ref: str | None = None,
    parent_run: models.RunbookRun | None = None,
) -> models.RunbookRun:
    """Start a run: pin the version, record how it fired, mark it running.

    **The version is PINNED here and never re-read** (`BR-RBS-038`,
    `TC-RBS-13`). A run opened this morning against version 8 draws version 8's
    definition for ever, whatever the code says next week.

    The scope fingerprint is written by `close_run` rather than here, because
    the scope is resolved by the executor's first act and the run row must exist
    before there is anything to pin it to. `BR-RBS-009` is about resolving
    ONCE — which `executor.pin_scope` does — not about which statement stores
    the digest.

    ⚠ `mode` defaults to `dry` and that is not a convenience. `BR-RBS-004`: an
    Action always produces a plan first, and there is no route in the product
    that acts without one.

    ⚠ **`started_at` IS STAMPED HERE, AND IT WAS NOT UNTIL WAVE D
    (`DEF-RBS-4291`).** This function set `status = running` and left the
    timestamp null, `close_run` set `finished_at` only, and nothing else in the
    module wrote either — so **every run ever opened carried no start time**.
    Nothing went red: a nullable timestamp is a legal value everywhere, the
    conformance suite asserts the version pin and the frozen report rather than
    the clock, and no reader existed. It surfaced the moment one did — `RBS-008`
    draws **Started** and **Took**, and both would have been blank on every row
    of the run history for ever, with `tsc` and every test green. The schema had
    been saying so all along: `03-field-map.md` §3 declares `started_at`
    *system-derived*, and `ix_runbook_runs_recent` indexes
    `(tenant, runbook, -started_at)` — an index on a column nobody writes.
    `timezone.now()` and not the caller's clock, for the same reason `close_run`
    uses it: the two ends of one duration must come from one source.

    ⚠ **TWO REFUSALS LIVE HERE AND BOTH ARE AT THIS DOOR ON PURPOSE (wave `E2`).**
    `POST /runbooks/{key}/runs` is wave `L`, so a rule enforced at an HTTP route
    would be a rule enforced nowhere for a whole phase. Every run in this
    product — a route, a schedule, a management command, the conformance suite —
    passes through this function, so this is the one place a refusal cannot be
    walked around, and wave `L`'s route inherits both by calling it.

    **1 · A PENDING TEMPLATE UPDATE STOPS THE RUN** (`BR-RBS-038`). The stored
    version and the live module have diverged, so pinning the stored number
    would put a version on a report that did not produce it. Refused, named, and
    cleared by one press of *Review →*.

    **2 · AN EDITED ACTION MAY NOT RUN LIVE** (`BR-RBS-036`, the trust ratchet).
    `trusted_version` is the version whose dry run has been reviewed; an edit
    moves `current_version` past it and the runbook is dry-run only until a
    person reviews one clean dry run. A **Check** is never caught by this — it
    writes nothing whatever its mode — and `mode = dry` is never caught either,
    which is what *drops back to dry-run only* means rather than *stops*.
    """
    version = ensure_version(runbook, definition)
    _refuse_a_pending_template_update(runbook, definition)
    _refuse_an_untrusted_live_run(runbook, mode)
    return models.RunbookRun.objects.create(
        tenant=runbook.tenant,
        runbook=runbook,
        version=version.version,
        mode=mode,
        trigger=trigger,
        event_ref=event_ref,
        parent_run=parent_run,
        status=models.RUN_STATUS_RUNNING,
        started_at=timezone.now(),
    )


def close_run(
    run: models.RunbookRun,
    result: RunResult,
    *,
    status: str = models.RUN_STATUS_DONE,
) -> models.RunbookRun:
    """Freeze the report onto the run — and refuse a thirteenth block HERE.

    `BR-RBS-020`: the report is **composed once, at close, from the twelve block
    types, and frozen**. A past run reopened draws exactly what it drew that
    day, which is the thing a regulator asks for and what `TC-RBS-16` asserts
    byte-for-byte.

    ⚠ **A THIRTEENTH BLOCK IS REFUSED AT CLOSE, NOT AT RENDER** (`TC-RBS-15`).
    The executor validated the report it composed; this validates it AGAIN, at
    the moment it becomes durable, because those are two different events and
    only one of them is what a clerk later reads. **The run is marked `failed`
    and the block is named.** Refused at render instead, the run would already
    be marked done and a clerk would meet a half-drawn screen with no way to
    tell whether the missing part mattered.

    ⚠ **THE REFUSAL IS DEVELOPER-FACING, WHICH IS WHY IT CARRIES NO
    `message_key`.** A block outside the twelve can only come from a runbook
    module — a Python file in this repository — so it is a build error and never
    a clerk's refusal. A refusal a clerk can provoke needs a key in all eleven
    locale catalogues or it reaches them as silence; this one cannot be provoked
    from a screen at all.
    """
    try:
        frozen = validate_report(result.report, runbook_key=result.runbook_key)
    except Exception:
        models.RunbookRun.objects.filter(pk=run.pk).update(
            status=models.RUN_STATUS_FAILED,
            scope_fingerprint=result.scope_fingerprint,
            counts=dict(result.counts),
            finished_at=timezone.now(),
        )
        raise
    counts = dict(result.counts)
    # ⚠ **THE WORK LIST IS FILLED HERE, AFTER THE REPORT VALIDATES AND BEFORE
    # THE RUN IS MARKED DONE** (`CR-075` wave H, `BR-RBS-017`, `BR-RBS-022`).
    # A run whose report is refused raises nothing: the block list is what a
    # clerk would have read the finding on, so raising over a screen that
    # cannot draw would put an item on a desk with nowhere to go.
    #
    # ⚠ **AND IT RUNS EVEN WHEN THE RUN RAISED NOTHING**, because *nothing
    # raised* is the fixed-everything case — that is what closes yesterday's
    # item, and `J-RBS-1`'s last assertion is exactly it.
    counts.update(_raise_the_work_items(run, result))
    models.RunbookRun.objects.filter(pk=run.pk).update(
        status=status,
        scope_fingerprint=result.scope_fingerprint,
        counts=counts,
        report=frozen,
        finished_at=timezone.now(),
    )
    run.refresh_from_db()
    return run


def _raise_the_work_items(run: models.RunbookRun, result: RunResult) -> dict[str, int]:
    """`RunResult.findings` → `work_items`, upserted by fingerprint.

    ⚠ **THE DEFINITION IS RE-RESOLVED FROM THE REGISTRY RATHER THAN ADDED TO
    THIS FUNCTION'S SIGNATURE.** `close_run` is called from six places — the
    conformance suite, two seed scripts, `run_to_completion`, the scheduler and
    a management command — and widening a signature every caller already passes
    the same fact into is how a shared function ends up with two ways to be
    called. The registry holds exactly one definition per key.

    A key the registry does not hold cannot raise anything and does not
    pretend to: the counts say `0` and the run closes.
    """
    from apps.runbooks.contract import RunbookContractError
    from apps.runbooks.engine import work_items
    from apps.runbooks.registry import registry

    try:
        definition = registry.get(result.runbook_key)
    except RunbookContractError:
        return {work_items.COUNT_RAISED: 0, work_items.COUNT_CLOSED: 0}
    return work_items.upsert(run, definition, result.findings)


def run_to_completion(
    runbook: models.Runbook,
    definition: RunbookDefinition,
    *,
    mode: str = models.MODE_DRY,
    trigger: str = models.TRIGGER_MANUAL,
    params: Mapping[str, Any] | None = None,
) -> tuple[models.RunbookRun, RunResult]:
    """Open, execute, close — the whole shape in one place, for one runbook.

    It lives here rather than in the executor because **the executor writes no
    row at all**: it pins a scope, walks steps and composes a report, and
    everything durable is this file's. Wave D's `POST /runbooks/{key}/runs`
    calls this; the conformance suite calls it to prove that a dry run of a
    registered runbook writes nothing outside these seven tables.

    ⚠ **`mode=mode` ON THE `execute` CALL IS `DEF-RBS-4345`, AND IT WAS
    MISSING.** This function took `mode`, wrote it onto the run row through
    `open_run`, and then called the executor **without it** — so `execute`'s own
    `mode="dry"` default won, `build_context` unbound every port, and a run
    whose `runbook_runs.mode` column read `live` executed as a dry run. Wave `M`
    found it by binding a writer and watching nothing be written; nothing else
    could have, because the run row and the report both say `live` and the only
    disagreement is inside one function call.

    ⚠ **THE `cap` REFUSES THE RUN AND NEVER TRUNCATES IT** (`BR-RBS-006`, task
    `L4`). It is read from the RUNBOOK row — the tenant's own setting — and
    handed down, because the executor holds a definition and never a row. `None`
    is a tenant who has not set one, not a limit of zero.

    ⚠ **`params` IS AN OVERRIDE LAYER, NOT THE WHOLE ANSWER — CHANGED IN WAVE
    `T`.** What a step reads is `run_parameters(runbook, definition,
    overrides=params)`: the declared defaults, **the values this tenant saved**,
    then whatever the caller passed. Before this wave the tenant's own inputs
    reached no run at all, because there was nowhere to save one
    (`DEF-RBS-4338`) — a caller that passed nothing got the shipped defaults and
    a caller that passed everything got exactly what it passed, and neither was
    the utility's answer.

    ⚠ **THIS IS ALSO WHERE THE WORD *all* BECOMES A SET** (`BR-RBS-042` clause
    1), one statement before `executor.execute` pins it (`BR-RBS-009`). The
    ordering is load-bearing: expand it any earlier and a service enabled since
    setup is silently outside the run, with nothing on any screen to see.
    """
    run = open_run(runbook, definition, mode=mode, trigger=trigger)
    resolved = run_parameters(runbook, definition, overrides=params)
    try:
        with transaction.atomic():
            result = executor.execute(
                definition,
                tenant_id=runbook.tenant_id,
                run_id=run.pk,
                mode=mode,
                params=resolved,
                cap=effective_cap(runbook.cap, resolved),
            )
    except executor.CapExceeded as over:
        _fail_run_over_cap(run, over)
    return close_run(run, result), result


#: The parameter four runbooks declare for the same rule the `cap` column holds.
#: One name, checked in one place, so a fifth runbook spelling it differently is
#: a miss this constant makes findable rather than a silent second cap.
MOST_PER_RUN = "most_per_run"


def effective_cap(column: int | None, resolved: Mapping[str, Any]) -> int | None:
    """The cap actually enforced, from the TWO places this product keeps one.

    ⚠ **THE NUMBER A CLERK TYPES WAS ENFORCED BY NOTHING — `DEF-RBS-4382`.**
    `runbooks.cap` is a first-class setting: it is in `EDITABLE_SETTINGS`, it
    validates, and `PUT /runbooks/{key}` saves it. It is also **null until an
    admin sets it**. Meanwhile four runbooks — the collections ladder, deposit
    review, payment plans and returned payments — declare a `most_per_run`
    PARAMETER, `RB-108`'s card lists it as an input beside a *capped at 400*
    sentence in its guards, and the setup screen lets a clerk type into it.
    **Nothing read it.** Wave `M`'s dry cycle walked **973 accounts a week**
    against a card that said 400, unrefused and untruncated, five Mondays
    running.

    **Why the LOWER of the two rather than one winning outright.** Both
    controls are real and they answer different questions: the column is the
    tenant's standing ceiling, set by an admin on the runbook; the parameter is
    what a clerk chose for THIS run. Letting either override the other makes
    the other decorative, which is the defect this function exists to close —
    so the run is refused by whichever is tighter, and neither control can be
    typed into with no effect. `BR-RBS-006` is unchanged: a cap REFUSES the run
    and never truncates it.

    Absent means absent: with neither set there is no cap, which is what the
    engine already did and what `NFR-5` requires — no hard cap anywhere.
    """
    typed = resolved.get(MOST_PER_RUN)
    # A parameter can be absent, blank, or the word a multi-select stores; only
    # a positive whole number is a limit. Anything else is not a cap and must
    # not silently become one.
    try:
        chosen = int(typed) if typed is not None and str(typed).strip() != "" else None
    except (TypeError, ValueError):
        chosen = None
    if chosen is not None and chosen < 1:
        chosen = None
    candidates = [value for value in (column, chosen) if value is not None]
    return min(candidates) if candidates else None


def _fail_run_over_cap(run: models.RunbookRun, over: executor.CapExceeded) -> None:
    """Mark the refused run and re-raise it as the refusal a clerk reads.

    ⚠ **THE RUN ROW IS MARKED BEFORE THE REFUSAL LEAVES**, because `open_run`
    wrote it OUTSIDE the transaction the executor runs in — deliberately, so a
    failed run leaves evidence rather than vanishing — and a row left at
    `running` for ever is a runbook that can never be started again once
    `already_running` lands. The counts carry both numbers so `RBS-008` can say
    *"refused: 835 against a limit of 400"* without re-deriving either.
    """
    models.RunbookRun.objects.filter(pk=run.pk).update(
        status=models.RUN_STATUS_FAILED,
        counts={"planned": over.planned, "cap": over.cap, "pinned": over.pinned},
        finished_at=timezone.now(),
    )
    raise errors.ValidationError(
        errors.VAL_RANGE,
        message_key="runbooks.refusal.over_cap",
        params={"planned": over.planned, "cap": over.cap},
    ) from over


# ═══════════════════════════════════════════════════════════════════════════
# CR-075 WAVE E — THE DEFINITION SURFACE: ADD · CLONE · EDIT · ACCEPT
#
# `US-RBS-038` · `US-RBS-040`. Three write routes (`07-endpoints.md` rows 3, 5
# and 6) and the two rules that bite on all of them:
#
#   `BR-RBS-038`  every edit makes a new version; a run pins the version that
#                 produced it and its stored plan and report never change; and
#                 a change to a shipped template is OFFERED on a tenant's copy
#                 and never applied without a person accepting it.
#   `BR-RBS-036`  an edited Action is dry-run only until one clean dry run has
#                 been reviewed — the trust ratchet.
#
# ⚠ **THESE ARE THE FIRST WRITES THIS MODULE HAS EVER ACCEPTED FROM A PERSON**,
# and three standing rules bite at once:
#
#   * `BR-RBS-002` — a Check is CONSTRUCTED with no writer. Nothing below binds
#     a port, calls one, or gives a definition a writer it did not declare. A
#     cloned Check is still a Check: `kind` is copied and `FROZEN_FIELDS`
#     refuses an edit to it, so there is no path from here to an Action.
#   * `OQ-RBS-1737` is OPEN — **nothing here composes an idempotency key**, in
#     code, in a default, or in a docstring stating one as settled. No function
#     below writes `runbook_run_records`.
#   * `OQ-RBS-1731` is CLOSED at **100** and **wave `L4` carries the change**.
#     `cap` is still required with no default, exactly as built, and nothing
#     here pre-empts `L4` by shipping the number early — a cap invented in this
#     wave would be an answer arriving from the wrong file.
# ═══════════════════════════════════════════════════════════════════════════


def _slug(text: str) -> str:
    """A runbook key from a person's words — lower case, hyphens, nothing else.

    `RBS-004`'s key is *the address a person can read, type and share*
    (`setupTypes.ts`), and B14 rule 31 bans a database id as the visible value
    of a field, so a clone cannot be addressed by its uuid. A slug is the only
    other stable handle.
    """
    kept = [c.lower() if c.isalnum() else "-" for c in (text or "").strip()]
    slug = "".join(kept)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:80]


def _free_key(tenant_id: Any, wanted: str) -> str:
    """`wanted`, or `wanted-2`, `wanted-3` … — the first one this tenant is free of.

    ⚠ **A SUFFIX RATHER THAN A REFUSAL, AND THAT IS A JUDGMENT WITH A REASON.**
    *Tom clones Dunning and names it Commercial accounts* is wave E's own goal
    sentence; two clones both called *Commercial accounts* is a thing a person
    will do, and refusing the second with *pick another name* makes the product
    argue with them about a field they do not know exists. The NAME is theirs
    and may repeat; the KEY is the address and must not.

    It is bounded rather than a `while True`: at 200 attempts the key is not the
    problem and a loop that cannot end is worse than a refusal.
    """
    base = wanted or "runbook"
    taken = set(
        models.Runbook.objects.filter(tenant_id=tenant_id, key__startswith=base).values_list(
            "key", flat=True
        )
    )
    if base not in taken:
        return base
    for suffix in range(2, 202):
        candidate = f"{base}-{suffix}"
        if candidate not in taken:
            return candidate
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-RBS-043",
        message_key="runbooks.refusal.already_added",
    )


def _template(template_key: str) -> RunbookDefinition:
    """The shipped definition behind a key, or a refusal a clerk can read.

    Imported inside the function for the reason `selectors._registry_definition`
    gives: `registry` imports `definitions`, which import runbook modules, which
    import `models`, which this file imports. A module-level import closes that
    loop. The name is the string literal `apps.runbooks.registry`, which is what
    `G115` rule 3 permits.
    """
    from apps.runbooks.registry import registry

    if not (template_key or "").strip():
        raise errors.ValidationError(errors.VAL_REQUIRED)
    try:
        return registry.get(template_key)
    except Exception:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="runbooks.refusal.unknown_template",
        ) from None


def add_template(tenant_id: Any, template_key: str, *, actor_id: Any = None) -> models.Runbook:
    """`POST /runbooks` — add a shipped template to this tenant's My runbooks.

    `07-endpoints.md` row 5: *Add a template to My runbooks. Body
    `{template_key}` … **Admin** · `201 · the new runbook`*.

    ⚠ **ADD ONCE, THEN CLONE — `BR-RBS-043`, ruled by this lane and written into
    `02-business-rules.md` in the same commit.** A tenant holds at most one copy
    of a shipped template under the template's own key, and a second copy is
    made by CLONING it. Adding twice is refused rather than silently returning
    the row that already exists: the library's whole state vocabulary is
    **Added · Not added** (`07-endpoints.md` row 4), so a second add is a stale
    screen or a double click, and answering `201` to it would tell the caller
    something was created that was not.

    ⚠ **THE COPY'S `cap` IS NULL AND THAT IS `OQ-RBS-1731`'s BUILT ANSWER, NOT
    AN OVERSIGHT.** The question is CLOSED at **100** and **wave `L4` carries
    the change**; until it lands, an Action cannot be enabled until an admin
    types a number — the safe shape, because an answer can only ever widen it.
    Shipping 100 from here would be `L4`'s work arriving from the wrong file and
    would make `L4` a no-op nobody notices.

    ⚠ **`trusted_version = 1` AND THE RATCHET IS THEREFORE SATISFIED ON DAY ONE**
    (`BR-RBS-036`). The rule restricts an **edited** Action, not a fresh one: the
    definition being added is the one we shipped and reviewed, so the first run
    is not held. The ratchet fires the moment somebody edits it.
    """
    definition = _template(template_key)
    existing = selectors.runbook_by_template(tenant_id, template_key)
    if existing is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RBS-043",
            message_key="runbooks.refusal.already_added",
            params={"key": existing.key},
        )
    with transaction.atomic():
        runbook = models.Runbook.objects.create(
            tenant_id=tenant_id,
            key=_free_key(tenant_id, definition.key),
            name=definition.name,
            kind=definition.kind,
            category=definition.category,
            tags=list(definition.tags),
            origin=models.ORIGIN_SHIPPED,
            template_key=definition.key,
            subject_type=definition.subject_type,
            unit_of_work=definition.unit_of_work,
            trigger_kind=_first_trigger(definition),
            current_version=1,
            trusted_version=1,
        )
        _write_version(
            runbook,
            document={
                **definition.as_definition_document(),
                SETTINGS_KEY: settings_document(runbook),
            },
            summary=[{"field": "origin", "to": models.ORIGIN_SHIPPED}],
            changed_by_id=actor_id,
        )
    return runbook


def clone_runbook(
    source: models.Runbook, *, name: str, actor_id: Any = None
) -> models.Runbook:
    """`POST /runbooks/{key}/clone` — clone and vary (`RB-040`).

    `07-endpoints.md` row 6: *Body `{name}`; the copy carries `origin = cloned`
    and **its own version 1***. Wave E's goal sentence is this function: *Tom
    clones Dunning, names it Commercial accounts, sets the first reminder to 15
    days — **both rows appear with their own schedule, cap and dry run***.

    ⚠ **THE COPY CARRIES THE SOURCE'S `template_key`, AND THAT IS WHAT MAKES A
    CLONE RUNNABLE AT ALL.** A clone's KEY is new, so the registry — which is
    keyed by the shipped module's key — holds nothing under it. Its steps are
    still the template's Python module, because `BR-RBS-042` puts the steps on
    our side and a tenant only ever sets input values. So `template_key` is the
    pointer to the code, and without it a clone would be a runbook with a
    schedule, a cap and no way to find out what it does. `RB-020`'s claim holds
    exactly as written: runbook 23 costs one Python module, and a clone of it
    costs none.

    ⚠ **THE SETTINGS ARE COPIED AND THE HISTORY IS NOT.** The copy starts at its
    own version 1 with the source's cap, schedule, gate and visibility, and with
    **no runs**: *both rows appear with their own schedule, cap and dry run* is
    two independent runbooks, not one with two names. A copied run history would
    make a past result reachable from a runbook that never produced it.

    ⚠ **`enabled = False` ON THE COPY, DELIBERATELY.** A clone exists to be
    varied — Tom's next act is *sets the first reminder to 15 days* — and a copy
    that arrived live on the source's schedule would run once on the wrong
    settings before he got there. Law 3: the unsafe option is the one you type.
    """
    label = (name or "").strip()
    if not label:
        raise errors.ValidationError(errors.VAL_REQUIRED)
    with transaction.atomic():
        copy = models.Runbook.objects.create(
            tenant_id=source.tenant_id,
            key=_free_key(source.tenant_id, _slug(label) or f"{source.key}-copy"),
            name=label,
            kind=source.kind,
            category=source.category,
            tags=list(source.tags or ()),
            origin=models.ORIGIN_CLONED,
            template_key=source.template_key or source.key,
            cloned_from=source,
            subject_type=source.subject_type,
            unit_of_work=source.unit_of_work,
            enabled=False,
            trigger_kind=source.trigger_kind,
            cron=source.cron,
            event_kind=source.event_kind,
            timezone=source.timezone,
            cap=source.cap,
            gate_mode=source.gate_mode,
            visible_to_roles=(
                None if source.visible_to_roles is None else list(source.visible_to_roles)
            ),
            current_version=1,
            trusted_version=1,
        )
        latest = selectors.latest_version(source)
        shipped = shipped_half(latest.definition if latest is not None else None)
        _write_version(
            copy,
            document={**shipped, SETTINGS_KEY: settings_document(copy)},
            summary=[
                {"field": "origin", "to": models.ORIGIN_CLONED},
                {"field": "cloned_from", "to": source.name},
            ],
            changed_by_id=actor_id,
        )
    return copy


def update_runbook(
    runbook: models.Runbook, changes: Mapping[str, Any], *, actor_id: Any = None
) -> models.RunbookVersion | None:
    """`PUT /runbooks/{key}` — change schedule, cap, gate or enabled; write a version.

    `07-endpoints.md` row 3. Returns the version that was written, or `None`
    when nothing actually moved.

    ⚠ **A NO-OP EDIT WRITES NO VERSION**, and that is `BR-RBS-038` read
    carefully rather than loosely: *every EDIT makes a new version*, and a
    request that sets the cap to the number it already is edited nothing. The
    alternative — a version per request — turns the Activity tab into a log of
    who opened the settings sheet, which is the one screen an auditor asks for
    first (`RBS-004.7`).

    ⚠ **AN UNKNOWN FIELD IS REFUSED AND A FROZEN FIELD IS REFUSED BY NAME.**
    Silently ignoring either is the failure mode this repository keeps paying
    for: the caller believes the change landed. `kind` is `BR-RBS-001` — a Check
    that could become an Action would end `BR-RBS-002` — and `key`, `category`,
    `origin` and `template_key` are each the answer to *what is this runbook*
    rather than *how do you want it run*.

    ⚠ **THE TRUST RATCHET DROPS HERE AND IS ENFORCED AT THE NEXT RUN**
    (`BR-RBS-036`, `07-endpoints.md` E-2: *"enforced on the next run, not on the
    edit"*). This function moves `current_version` past `trusted_version` and
    `open_run` is what refuses; the edit itself is never refused, because a
    person narrowing a runbook's scope after a bad run must not be stopped from
    doing exactly that.
    """
    unknown = [k for k in changes if k not in EDITABLE_SETTINGS and k not in FROZEN_FIELDS]
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, params={"fields": sorted(unknown)}
        )
    frozen = [k for k in changes if k in FROZEN_FIELDS]
    if frozen:
        raise errors.BizError(
            errors.BIZ_IMMUTABLE,
            br_ref="BR-RBS-001",
            message_key="runbooks.refusal.not_editable",
            params={"fields": sorted(frozen)},
        )
    moved: list[dict[str, Any]] = []
    for field, raw in changes.items():
        if field == "parameters":
            value: Any = _validated_parameters(runbook, raw)
        else:
            value = _validated_setting(field, raw)
        before = getattr(runbook, field)
        if before == value:
            continue
        setattr(runbook, field, value)
        moved.append({"field": field, "from": before, "to": value})
    if not moved:
        return None
    with transaction.atomic():
        models.Runbook.objects.filter(pk=runbook.pk).update(
            **{change["field"]: change["to"] for change in moved}
        )
        latest = selectors.latest_version(runbook)
        return _write_version(
            runbook,
            document={
                **shipped_half(latest.definition if latest is not None else None),
                SETTINGS_KEY: settings_document(runbook),
            },
            summary=moved,
            changed_by_id=actor_id,
        )


def accept_template_update(
    runbook: models.Runbook, *, actor_id: Any = None
) -> models.RunbookVersion | None:
    """Take the offered template change onto this copy — `BR-RBS-038`, wave `E3`.

    **This is the *pressed* in *changing nothing until pressed*.** The offer is
    computed on read (`selectors.pending_template_update`) and nothing anywhere
    else applies it: not `ensure_version`, not `open_run`, not a nightly job.
    Until this function is called, the copy's stored steps, guards and
    parameters are exactly what they were when it was added.

    Returns the new version, or `None` when there is nothing on offer —
    idempotent rather than a refusal, because *accept an update that has already
    been accepted* is a double click and answering it with an error would teach
    a clerk that the button is broken.

    ⚠ **IT KEEPS THE TENANT'S SETTINGS AND TAKES ONLY THE SHIPPED HALF.**
    Accepting *1 new step* must not reset the cap somebody raised to 400. The
    two halves of the document exist for exactly this moment.
    """
    from apps.runbooks.registry import registry

    if not runbook.template_key:
        return None
    try:
        definition = registry.get(runbook.template_key)
    except Exception:
        return None
    latest = selectors.latest_version(runbook)
    incoming = definition.as_definition_document()
    if latest is not None and shipped_half(latest.definition) == incoming:
        return None
    with transaction.atomic():
        version = _write_version(
            runbook,
            document={**incoming, SETTINGS_KEY: settings_document(runbook)},
            summary=[{"field": "template", "to": runbook.template_key}],
            changed_by_id=actor_id,
        )
        # `BR-RBS-036` — accepting OUR change is an edit like any other, so an
        # Action re-enters dry-run until a person reviews one clean dry run.
        # A Check is never held: it writes nothing whatever its mode.
        if runbook.kind == models.KIND_ACTION:
            models.Runbook.objects.filter(pk=runbook.pk).update(
                trusted_version=None
            )
            runbook.trusted_version = None
        else:
            models.Runbook.objects.filter(pk=runbook.pk).update(
                trusted_version=version.version
            )
            runbook.trusted_version = version.version
    return version



# ══════════════════════════════════════════════════════════════════════════
# CR-075 WAVE H — ASSIGN · RESOLVE · REOPEN (`US-RBS-006`, `RBS-007`)
#
# ⚠ **A PERSON MAY MOVE FOUR FIELDS AND NOTHING ELSE.** `title`, `weight`,
# `subject_ref`, `fix_route` and `fingerprint` are the ENGINE's — they are
# re-derived on every run, so a person's edit to one would be silently reverted
# the next morning, which is worse than refusing it. `US-RBS-006` §5 names
# exactly what a person sets: **owner · due date · status**, and *resolving
# stamps `resolved_at`; reopening clears it and keeps the row.*
# ══════════════════════════════════════════════════════════════════════════

#: The two statuses, and the field map's own sentence for each.
WORK_ITEM_OPEN = "open"
WORK_ITEM_RESOLVED = "resolved"

#: What `PATCH /work-items/{id}` accepts. A key outside this set is REFUSED
#: rather than ignored: a caller that sent `title` believing it would stick
#: deserves to be told, and silently dropping it is how a screen ends up
#: claiming an edit that never happened.
WORK_ITEM_EDITABLE = frozenset({"owner_id", "due_on", "status"})


def update_work_item(
    item: models.WorkItem, payload: Mapping[str, Any], *, actor_id: Any = None
) -> models.WorkItem:
    """Assign, resolve or reopen one item — the three verbs of `RBS-007`.

    ⚠ **RESOLVING IS NOT DELETING, AND REOPENING IS NOT A SECOND ROW.** The row
    survives both, with its `created_at` untouched, because the age a clerk
    reads is the FIRST sighting — thirty daily sweeps over one missing read are
    *one item, thirty days old*. `TC-RBS-006.2`'s *must first fail on* is a
    fingerprint that includes the run id, which would make every reopen a new
    row and reset that age to today.

    ⚠ **AND A PERSON RESOLVING AN ITEM THE ENGINE STILL RAISES DOES NOT WIN
    FOREVER — IT REOPENS ON THE NEXT RUN.** That is deliberate and it is the
    difference between this list and a to-do list: the item is DERIVED, so
    ticking it while the fault is still there is a statement about the tick and
    not about the estate.
    """
    unknown = sorted(set(payload) - WORK_ITEM_EDITABLE)
    if unknown:
        # ⚠ **NO `message_key`, AND THAT IS DELIBERATE RATHER THAN AN
        # OVERSIGHT (`G32`).** `RBS-007` sends exactly three fields, so this
        # refusal cannot be provoked from a screen at all — it can only come
        # from a caller written against a shape this service does not have,
        # which makes it developer-facing. A key here would be eleven catalogue
        # entries no clerk can ever read.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, params={"fields": sorted(unknown)}
        )

    fields: dict[str, Any] = {}
    if "owner_id" in payload:
        fields["owner_user_id"] = payload["owner_id"] or None
    if "due_on" in payload:
        fields["due_on"] = payload["due_on"] or None
    if "status" in payload:
        status = str(payload["status"])
        if status not in (WORK_ITEM_OPEN, WORK_ITEM_RESOLVED):
            # ⚠ **NO `message_key` HERE EITHER, FOR THE SAME REASON ONE LINE
            # UP.** `RBS-007` offers *Resolve* and *Reopen* and sends one of two
            # words; a third can only come from a caller written by hand. The
            # precedent is four lines down in `_validated_setting`, which
            # refuses an unparseable integer the same way — a clerk cannot type
            # one into a number field either.
            raise errors.ValidationError(
                errors.VAL_FORMAT, params={"field": "status", "value": status}
            )
        fields["status"] = status
        # `US-RBS-006` §5, word for word: *resolving stamps `resolved_at`;
        # reopening clears it and keeps the row.*
        fields["resolved_at"] = timezone.now() if status == WORK_ITEM_RESOLVED else None

    if not fields:
        return item
    fields["updated_at"] = timezone.now()
    models.WorkItem.objects.filter(pk=item.pk).update(**fields)
    item.refresh_from_db()
    return item


# ── the two refusals `open_run` carries ──────────────────────────────────────


def _refuse_a_pending_template_update(
    runbook: models.Runbook, definition: RunbookDefinition
) -> None:
    """`BR-RBS-038` — a run cannot pin a version the code has moved past.

    The refusal is FIVE WORDS (B14 rule 33) and names an act a clerk can
    perform: the setup screen already draws *Template updated · 1 new step ·
    Review →* over the same fact, so the sentence and the button agree.
    """
    latest = selectors.latest_version(runbook)
    if latest is None:
        return
    if shipped_half(latest.definition) == definition.as_definition_document():
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-RBS-038",
        message_key="runbooks.refusal.update_pending",
        params={"key": runbook.key, "version": latest.version},
    )


def _refuse_an_untrusted_live_run(runbook: models.Runbook, mode: str) -> None:
    """`BR-RBS-036` — an edited Action is dry-run only until one clean dry run.

    ⚠ **THE ACT THAT CLEARS THE RATCHET IS WAVE `L`'s AND ITS ABSENCE IS THE
    SAFE DIRECTION.** *Reviewed* is a person approving a plan —
    `POST /runbooks/runs/{id}/approve`, `07-endpoints.md` row 12 — and that
    route does not exist yet. So today an edited Action can only run dry, which
    is what phase 1 promises anyway (*"nothing can be written: no writer is
    bound"*). Stated here rather than left to be discovered, because a reader
    could take this for a ratchet nobody can ever release.
    """
    if mode != models.MODE_LIVE or runbook.kind != models.KIND_ACTION:
        return
    if runbook.trusted_version == runbook.current_version:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-RBS-036",
        message_key="runbooks.refusal.dry_run_first",
        params={"key": runbook.key},
    )


# ── validating one setting ───────────────────────────────────────────────────


def _first_trigger(definition: RunbookDefinition) -> str:
    """The trigger a freshly added runbook starts on.

    `manual` whenever the definition offers it, because a runbook that arrives
    on a schedule nobody set is a run nobody asked for. Otherwise the first
    declared trigger, so a schedule-only or event-only runbook is not silently
    given a trigger it does not declare.
    """
    if models.TRIGGER_MANUAL in definition.triggers:
        return models.TRIGGER_MANUAL
    return definition.triggers[0]


# ══════════════════════════════════════════════════════════════════════════
# CR-075 WAVE T — THE INPUT VALUES (`US-RBS-039`, `BR-RBS-042`)
#
# PO verbatim, 2026-09-06: *"you cannot change the logic those are finate steps
# ; you can change the input to logic … this way, we control the inputs however
# process remain same , and then out put produced is filtered ; please note
# every utility will not have all utility services or all combinations of Plans
# and rates, so we ahve to work in variables"*.
#
# Two functions, and the split is the whole of the rule:
#
#   `_validated_parameters`  what a tenant may SAVE — checked against the
#                            runbook's own declaration and, for a domain, the
#                            tenant's own data. *all* is saved AS THE WORD.
#   `run_parameters`         what a RUN actually walks — the declared defaults,
#                            the tenant's answers over the top, and *all*
#                            expanded HERE, at run start, where `BR-RBS-009`
#                            pins it.
#
# ⚠ **THE DANGEROUS SIMPLIFICATION IS TO DO THE EXPANSION IN THE FIRST ONE.** It
# is one line shorter and it silently freezes the domain: a utility that sets
# *all services* with Water and Sewer would be outside Trash for ever the day it
# enables Trash, with no error, no screen change and nothing anywhere to see.
# ══════════════════════════════════════════════════════════════════════════


def definition_for(runbook: models.Runbook) -> RunbookDefinition | None:
    """The shipped module behind this runbook row, or `None` if there is none.

    A clone carries the source's `template_key` and its own `key`, and the
    registry holds the CODE under the template key — `BR-RBS-043` says so and it
    is why *added* is read as `template_key` plus `origin = shipped`. So the
    template key is asked first and the runbook's own key second.

    ⚠ **`None` IS A REAL ANSWER AND NOT AN ERROR.** A runbook row can outlive
    the module that shipped it — a template withdrawn, a definition renamed —
    and the version document still holds what it was. A caller that needs the
    declaration says what it does without one rather than raising here.
    """
    from apps.runbooks.registry import registry

    for candidate in (runbook.template_key, runbook.key):
        if not candidate:
            continue
        try:
            return registry.get(candidate)
        except Exception:
            continue
    return None


def _validated_parameters(runbook: models.Runbook, raw: Any) -> dict[str, Any]:
    """What a tenant set its inputs to — refused by NAME when it is not legal.

    ⚠ **THE WHOLE DOCUMENT, NEVER A DELTA**, exactly as `visible_to_roles` is
    stored as the whole answer. A delta has no way to say *put this input back
    to what it shipped with*: `{"services": null}` is indistinguishable from
    *do not mention services*, and the screen sends every row it drew anyway.
    **An input the caller omits is an input this tenant has not set**, and it
    runs on the declared default.

    Four refusals, each by name because a silently-dropped input is a tenant
    believing their choice landed:

      1. a name the runbook does not declare — including one it USED to declare,
         which is how a template update leaves a stale answer behind;
      2. a list on an input that takes one value (`multi=False`);
      3. the word *all* on an input that takes one value — *all* is a rule about
         several (`BR-RBS-042` clause 1);
      4. a value outside the input's own vocabulary: `choices` for the runbook's
         fixed list, and **the tenant's own domain** for a tenant-resolved one.

    ⚠ **THE DOMAIN CHECK READS THE TENANT'S DATA, WHICH IS THE POINT** (clause
    2). A utility that sells Water and Sewer cannot save *services = Trash*, and
    the same request at a utility that sells Trash is accepted. Both are
    correct; a hardcoded list of eleven would accept both and one of them would
    then filter every run down to nothing while the screen looked healthy.
    """
    if not isinstance(raw, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, params={"field": "parameters"})
    definition = definition_for(runbook)
    declared = {p.name: p for p in (definition.parameters if definition else ())}
    unknown = sorted(name for name in raw if name not in declared)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, params={"field": "parameters", "fields": unknown}
        )
    out: dict[str, Any] = {}
    for name, value in raw.items():
        out[name] = _validated_parameter_value(declared[name], value)
    return out


def _validated_parameter_value(parameter: Any, value: Any) -> Any:
    """One input's value, against that input's own declaration."""
    allowed = _allowed_values(parameter)
    if isinstance(value, (list, tuple)):
        if not parameter.multi:
            raise errors.ValidationError(errors.VAL_FORMAT, params={"field": parameter.name})
        chosen = [str(one) for one in value]
        if allowed is not None:
            outside = sorted(set(chosen) - set(allowed))
            if outside:
                raise errors.ValidationError(
                    errors.VAL_UNKNOWN_LOOKUP,
                    params={"field": parameter.name, "values": outside},
                )
        # Order is the DOMAIN's, not the order a person happened to tick them
        # in: two admins choosing the same two services must not write two
        # versions that differ by nothing a person can see.
        if allowed is not None:
            return [one for one in allowed if one in set(chosen)]
        return sorted(dict.fromkeys(chosen))
    if value == contract.PARAM_ALL:
        if not parameter.multi:
            raise errors.ValidationError(errors.VAL_FORMAT, params={"field": parameter.name})
        # ⚠ STORED AS THE WORD. `run_parameters` expands it at run start.
        return contract.PARAM_ALL
    if allowed is not None and value is not None and str(value) not in allowed:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, params={"field": parameter.name, "values": [str(value)]}
        )
    return value


def _allowed_values(parameter: Any) -> tuple[str, ...] | None:
    """This input's vocabulary, or `None` when it has none (a money box, a date).

    ⚠ **A DOMAIN IS READ AND `choices` IS DECLARED, AND THEY ARE NEVER BOTH**
    (`contract.Parameter._check_domain`). An unbounded domain has no readable
    vocabulary at all — forty thousand accounts is not a list to check a value
    against — so a value on one is accepted as typed and the RUN is what finds
    an account that is not there. That is the honest shape: the alternative is a
    validator that reads every account row on every save.
    """
    if parameter.choices:
        return tuple(str(one) for one in parameter.choices)
    if parameter.domain is None:
        return None
    if not domains.DOMAIN_IS_BOUNDED.get(parameter.domain, False):
        return None
    return domains.members(parameter.domain)


def run_parameters(
    runbook: models.Runbook,
    definition: RunbookDefinition,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """What THIS run walks: defaults, the tenant's answers, and *all* expanded.

    Three layers, in this order, and the order is the rule:

      1. every declared parameter's **default** — so an input a tenant has never
         touched runs on what the runbook shipped with;
      2. the tenant's **stored answers**, for declared names only. A name the
         document holds and the definition no longer declares is IGNORED rather
         than passed through: a template update that drops an input must not
         leave a value behind that a step could still read;
      3. a caller's **overrides**, which is how a one-off run from a screen
         passes an account or a period that is not a saved setting.

    ⚠ **THEN *all* IS EXPANDED, HERE, AND NOWHERE EARLIER** (`BR-RBS-042` clause
    1). This is the moment the rule turns into a set: a utility that set *all
    services* with Water and Sewer and has since enabled Trash gets **three**,
    because the domain is read now rather than when they pressed Save. After
    this returns, `executor.pin_scope` resolves once and freezes
    (`BR-RBS-009`), so the set cannot move again inside the run.

    ⚠ **AN EMPTY DOMAIN EXPANDS TO AN EMPTY LIST AND THAT IS NOT AN ERROR
    HERE.** A utility that has enabled no services yet gets `[]`, the run
    matches nothing, and the result says so — which is a true answer. Raising
    would turn *"you have not set this utility up yet"* into a crash on a
    screen, and the setup screen already says an empty domain says so.
    """
    values: dict[str, Any] = {p.name: p.default for p in definition.parameters}
    declared = {p.name: p for p in definition.parameters}
    stored = runbook.parameters if isinstance(runbook.parameters, dict) else {}
    for name, value in stored.items():
        if name in declared:
            values[name] = value
    for name, value in dict(overrides or {}).items():
        values[name] = value
    for name, parameter in declared.items():
        if values.get(name) != contract.PARAM_ALL:
            continue
        if parameter.choices:
            values[name] = [str(one) for one in parameter.choices]
        elif parameter.domain is not None:
            values[name] = list(domains.members(parameter.domain))
    return values


def _validated_setting(field: str, raw: Any) -> Any:
    """One editable field, checked against the vocabulary that owns it.

    ⚠ **`cap` HAS NO MAXIMUM AND NEVER WILL** (`NFR-5`, and CLAUDE.md's opening
    paragraph makes that flexibility the deliverable rather than the
    background). A ceiling typed here would be exactly the *account maximum that
    would have to be removed when T4 arrives* the instruction forbids. What is
    refused is a cap of zero or below, which is not a limit — it is a runbook
    that can never run, expressed as a number.
    """
    if field == "enabled":
        return bool(raw)
    if field == "cap":
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise errors.ValidationError(errors.VAL_FORMAT, params={"field": field}) from None
        if value < 1:
            raise errors.ValidationError(errors.VAL_RANGE, params={"field": field})
        return value
    if field == "trigger_kind":
        if raw not in models.TRIGGER_KINDS:
            raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, params={"field": field})
        return raw
    if field == "event_kind":
        if raw is not None and raw not in models.EVENT_KINDS:
            raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, params={"field": field})
        return raw
    if field == "gate_mode":
        if raw not in models.GATE_MODES:
            raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, params={"field": field})
        return raw
    if field == "visible_to_roles":
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)) or any(
            role not in models.VISIBILITY_ROLES for role in raw
        ):
            raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, params={"field": field})
        # Stored as the whole answer rather than a delta, and normalised so two
        # admins typing the same three roles in a different order do not write
        # two versions that differ by nothing a person can see.
        return sorted(dict.fromkeys(str(role) for role in raw))
    if field in ("cron", "timezone"):
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            raise errors.ValidationError(errors.VAL_REQUIRED, params={"field": field})
        # ⚠ **CHECKED HERE OR CHECKED NEVER (`CR-075` wave I task `I2`).** Both
        # of these were stored as any non-empty string until 2026-09-07, which
        # was correct while nothing read them and became a silent production
        # failure the moment something did: `US-RBS-007`'s own field table says
        # *"cron valid or refused at save"* and *"tz from the tenant's own
        # setting"*. A cron a clerk fat-fingers is refused while they are
        # looking at it, rather than at 06:00 on a morning when nobody is —
        # and a timezone `zoneinfo` does not know would otherwise fall back to
        # UTC and reproduce `DEF-MET-4101`, a clock question answered in the
        # wrong frame, one schedule at a time.
        from apps.runbooks import scheduler

        try:
            scheduler.parse_cron(text) if field == "cron" else scheduler.zone(text)
        except scheduler.CronError as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT, params={"field": field, "why": str(problem)}
            ) from None
        return text
    raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, params={"field": field})


# ══════════════════════════════════════════════════════════════════════════
# CR-173-BRC10 — A RUN BY HAND (`POST /runbooks/{key}/runs`, `07-endpoints.md`
# row 4). PO 2026-10-07, the GIS row: *"we will call APi manually and test it
# first when everything work then we will do nightly job for specific
# utility/tenant"* — and the New World receipt push is run the same way. Until
# this, **Run ▶** refused on every runbook (`RunbookSetupPage.tsx`'s hold).
# ══════════════════════════════════════════════════════════════════════════

RUN_MODES_BY_HAND = (models.MODE_DRY, models.MODE_LIVE)


def request_run(
    runbook: models.Runbook,
    *,
    mode: str,
    parameters: Mapping[str, Any] | None,
    started_by_name: str | None = None,
) -> dict[str, Any]:
    """Queue ONE run of `runbook`, started by a person. Returns the job record.

    It rides the schedule's own job kinds and body (`scheduler.run_scheduled_
    job`), so every refusal `open_run` enforces — the template-update stop and
    the trust ratchet — applies to a run by hand exactly as to a scheduled one.

    Three refusals here, each by name, before anything is queued:

    1. a mode that is neither `dry` nor `live`;
    2. `live` on a runbook that is not on `engine.acts.LIVE_ENABLED_RUNBOOKS` —
       it would run DRY and say *live* on the run row, which is the lie
       `DEF-RBS-4345` was;
    3. an input the runbook does not declare, or a value its declaration
       refuses (`_validated_parameters`, the same check a saved setting gets).

    `started_by_name` travels as an override so the run's port can record WHO
    pressed it on the far side's own run row; it is never read as an input.
    """
    from apps.runbooks import scheduler
    from apps.runbooks.engine import acts
    from core import jobs as core_jobs

    if mode not in RUN_MODES_BY_HAND:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, params={"field": "mode", "values": [str(mode)]}
        )
    definition = definition_for(runbook)
    if definition is None:
        raise errors.NotFoundError()
    if mode == models.MODE_LIVE and not acts.live_enabled(definition.key):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RBS-003",
            message_key="runbooks.refusal.dry_only",
            params={"key": runbook.key},
        )
    chosen = _validated_parameters(runbook, dict(parameters or {}))
    if started_by_name:
        chosen["started_by_name"] = str(started_by_name)
    kind = scheduler.CHECK_JOB if runbook.kind == models.KIND_CHECK else scheduler.ACT_JOB
    stamp = timezone.now().isoformat()
    return core_jobs.enqueue(
        kind,
        scope_key=f"{runbook.tenant_id}:{runbook.key}:manual:{stamp}",
        payload={
            "tenant_id": str(runbook.tenant_id),
            "runbook_key": runbook.key,
            "mode": mode,
            "trigger": models.TRIGGER_MANUAL,
            "params": chosen,
        },
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01; CR-075 wave A task A3) · US-RBS-015 (CR-075 wave B task B3)
# generated: 2026-09-06 by the CR-075 wave A build lane; extended 2026-09-06 by the wave B lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint before wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H=n/a(no 🔒 path — nothing here composes an idempotency key; OQ-RBS-1737 is open and wave L owns it)
# gates: G115 (the import census) · pytest tests/test_us_rbs_015_conformance.py · G74 (the three baseline lines this wave moves)
# exceptions: no port is bound to a writer; runbook_run_records and work_items are NOT written here — OQ-RBS-1737 and wave C own them
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
