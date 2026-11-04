# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-012 · US-RBS-014 (EP-RBS-04) — CR-075 wave L
#           tasks L2 and L5: the engine's own two acts, on the far side of
#           every port.
# Rules:    BR-RBS-004 (an Action always produces a PLAN first) · BR-RBS-022
#           (a write is a named port; the audit row is the ENGINE's) ·
#           BR-RBS-015 / BR-AUD-019 (the runbook is the audit actor, named and
#           versioned; it never borrows a user identity) · BR-RBS-003 (dry and
#           live are ONE path, differing only in whether the writer is bound) ·
#           BR-RBS-002 (a Check holds no ports at all) · CLAUDE.md hard rule 7
#           (every money action writes audit_log) · hard rule 6 (idempotency) ·
#           hard rule 1 (tenant scoping) · hard-won law 14 (a SAVEPOINT, not a
#           bare except)
# Tests:    06-backend/tests/test_us_rbs_012_acts.py ·
#           06-backend/tests/test_us_rbs_012_pg.py (PostgreSQL — the savepoint
#           and the UNIQUE index, neither of which SQLite can prove)
# Impacts:  apps/runbooks/engine/executor.py (build_context binds or unbinds) ·
#           apps/runbooks/definitions/dunning.py (its only writing step) ·
#           apps/runbooks/ports/*_ports.py (the writers this calls)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED · HUMAN-REVIEW-PENDING — the two acts no runbook may perform itself.

AI-authored 2026-09-06 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in `12-governance/09-human-review-ledger.md`.
🔒 **idempotency keys** — this file composes the per-record key hard rule 6
turns into a UNIQUE index, and it is the first file in this module that can
change a customer's record.

WHAT THIS FILE IS
-----------------
Thirteen ports write other modules' rows. **Two things happen around every one
of those writes and neither belongs to a runbook**: the `runbook_run_records`
row that says what was planned and what happened, and the `audit_log` row that
names the runbook as the actor. `BR-RBS-022` puts both here, in the engine, and
that is not tidiness — it is the only thing that lets a **Check** populate the
work list and leave a trail while holding **no writer at all** (`BR-RBS-002`).

    plan(ctx, request)   → the record row, planned_action written, no outcome
    act(ctx, planned)    → the port call, the outcome, the audit row

**`plan` ALWAYS RUNS AND `act` MAY NOT.** `BR-RBS-004`: an Action always
produces a plan first and there is no route in the product that acts without
one. `BR-RBS-041` (PO 2026-09-06) removed the WAIT for a runbook an admin has
trusted up front — **it did not remove the plan**, so the two calls stay two
calls whichever way that switch is set.

⚠ DRY AND LIVE ARE ONE PATH AND THERE IS NO `if mode == "dry"` BELOW
---------------------------------------------------------------------
`BR-RBS-003`. The difference between a dry run and a live one is **whether the
port handed to the step has a writer behind it**, and that is decided once, in
`executor.build_context`, before any step runs. Here the question is asked as
`port.is_bound` and answered the same way every time:

    bound      → call the writer, outcome `done`
    not bound  → write nothing, outcome `planned` — *this is what it WOULD do*

A dry run therefore walks the identical statements a live one walks, which is
what makes the dry run evidence about the live one. A version of this file that
branched on the mode would prove nothing about the code that eventually sends,
and `TC-RBS-2` is first shown red on exactly that build.

⚠ THE ACTOR IS THE RUNBOOK, NAMED AND VERSIONED, AND NEVER A PERSON
--------------------------------------------------------------------
`BR-RBS-015`, and until 2026-09-06 the platform could not express it: a NULL
`actor_user_id` meant *"system job"*, so a runbook would have had to borrow a
staff login and **a person would appear to have personally sent 812 letters at
07:00 on a Monday**. `US-AUD-010` closed that (`audit/0007`), and this file is
where Runbooks finally uses it: every audit row below is written with
`core.audit.AutomationActor("runbook", <the runbook's name>, <its version>)`,
and `core.audit.write_row` REFUSES an automation actor that also carries a user
id. A clerk reads *"Collections ladder, version 1"*.

⚠ THE IDEMPOTENCY KEY — WHAT IS SETTLED AND WHAT IS DELIBERATELY NOT
----------------------------------------------------------------------
`OQ-RBS-1737` was closed by the Product Owner on 2026-09-06 and **they reshaped
the question rather than picking one of our two candidate keys**: the duplicate
check moved from the RECORD to the RUN. That ruling lives in
`engine/duplicates.py`, which is the brace. **This is the belt**, and it is
smaller than `BR-RBS-008` (PROPOSED, never confirmed) described:

    runbook · action kind · subject type · subject id · discriminator

**THE RUN IS NOT IN IT.** With the run in the key a retry mints a fresh key for
all 248 records and the ladder queues 496 notices in one morning — the field
map's own worked figure, and the contradiction `DEF-RBS-4246` recorded.

**`discriminator` IS THE RUNBOOK'S OWN REPEAT BOUNDARY AND ITS CONTENT IS NOT
SETTLED HERE, ON PURPOSE.** Drop it and the ladder can never write to the same
customer twice, so somebody chased in September is **never** chased again.
Runbook 8 passes its RUNG, which is what makes *first reminder, then 10-day,
then 5-day, then certified* possible over one debt. What the right
discriminator is for the other eight Actions is each runbook's question, asked
when that runbook is built with the real thing in front of it; **no document,
docstring or test in this commit says the composition is settled**, because the
2026-09-06 ruling made it a smaller question rather than an answered one.

⚠ WHAT WOULD MAKE THE IDEMPOTENCY CHECK PASS WRONGLY (hard-won law 7, habit 2)
-------------------------------------------------------------------------------
* **A `SELECT` then an `INSERT`.** Two workers each find no row and each write
  one. → The UNIQUE index `uq_runbook_run_records_idem` is the guarantee; the
  `SELECT` below is only there to give the clerk a sentence. The INSERT is
  wrapped in its own SAVEPOINT and an `IntegrityError` from it is READ AS THE
  ANSWER, not as a failure.
* **`except IntegrityError: continue` with no savepoint.** Green on the whole
  suite — `config/settings/test.py` hardcodes in-memory SQLite, which has no
  aborted-transaction state — and it loses the run the first time a real row is
  refused on PostgreSQL (hard-won law 14). → `transaction.atomic()` here is a
  nested block and therefore a real `SAVEPOINT`; `tests/test_us_rbs_012_pg.py`
  proves it on PostgreSQL and SKIPS rather than passing anywhere else.
* **A key computed from a mutable label.** A customer's name changes and the
  same notice goes again. → Only ids and code-defined words enter the key.
* **READING *A ROW EXISTS* AS *THE ACT HAPPENED*.** This one was live and it
  would have silenced the whole ladder: a DRY run writes a record row with
  outcome `planned`, meaning *nothing was written*, and the first version of
  this file refused every later act on that key. Wave `M`'s month of dry runs
  left 878 such rows on a real tenant, so the live half would have queued **0**
  notices for ever with every check green. → `_resume_or_refuse` reads the
  OUTCOME: `done` and `already` are spent, `planned`, `held` and `failed` are
  resumable. Read its docstring before touching either set.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, IntegrityError, transaction

from core import audit as core_audit
from core import tenancy as core_tenancy

from apps.runbooks import models
from apps.runbooks.contract import SubjectRef

#: The audit action code every port write is recorded under. One code, with the
#: PORT in the payload, because a catalogue entry per port would be thirteen
#: codes describing one event — *a runbook wrote something* — and a clerk
#: filtering the trail wants the runbook, which is the actor column.
AUDIT_ACTION = "runbook.port_write"
AUDIT_ENTITY = "runbook_run_record"

#: What the record row's `outcome` says. `planned` is the DRY answer and is not
#: a failure: it means the step reached the port and the port had no writer.
OUTCOME_PLANNED = "planned"
OUTCOME_DONE = "done"
OUTCOME_ALREADY = "already"
OUTCOME_FAILED = "failed"
OUTCOME_HELD = "held"

#: ⚠ **EMPTY, AND THAT IS WAVE L's WHOLE POSTURE.** `CR-075`'s phase 2 ships the
#: dangerous half **with sending switched off**; wave `M` soaks it for a full
#: cycle in production and wave `N` turns the first runbook on. A runbook whose
#: key is not in here holds writer-less ports in EVERY mode, so `act()` records
#: what it WOULD do and calls nothing — which is `L6`'s *"the runbook DISABLED
#: for live"*, enforced for the whole catalogue rather than for one file.
#:
#: ⚠ **THE UNSAFE OPTION IS THE ONE YOU TYPE** (hard-won law 3). Adding a key
#: here is what turns a runbook live; there is no setting, no environment
#: variable and no default that can do it, so a misconfigured deployment cannot
#: switch sending on by accident.
#:
#: ⚠ **ONE KEY SINCE `CR-173-BRC10` (2026-10-07): `newworld_receipt_push`.**
#: The first runbook turned on, and chosen because it is the one that WRITES
#: NO MONEY: it places a file of payments already posted in a City's SFTP
#: folder. Being on this list is necessary and not sufficient — a run reaches
#: the writer only when it is started LIVE (a System Admin's **Run ▶ · Run for
#: real**, or a schedule *approved up front*), and the writer itself sends
#: nothing for a utility that has not typed a City folder on its own New World
#: connection (PO 2026-10-07 S1). Decision log 2026-10-07 has the whole chain.
LIVE_ENABLED_RUNBOOKS: frozenset[str] = frozenset({"newworld_receipt_push"})


class ActRefused(Exception):
    """The engine will not perform this act, and the message says which rule.

    Developer-facing and therefore carrying no `message_key`: every condition
    below can only be reached from a runbook module — a Python file in this
    repository — so it is a build error and never a clerk's refusal. A refusal a
    clerk can provoke needs a key in all eleven catalogues or it reaches them as
    silence (`G32`'s 21 live refusals); this one cannot be provoked from a
    screen at all.
    """


@dataclass(frozen=True)
class ActRequest:
    """What a step says it is about to do, before anything is written.

    Everything here is known at EVALUATION (`BR-RBS-004`) — the record row is
    written from it before the port is reached, so a run that dies mid-way
    leaves the plan behind rather than a silence.
    """

    port: str
    action_kind: str
    subject: SubjectRef
    #: The words a clerk reads in the Records table. Plain language, no rule id
    #: (B14 rule 32).
    planned_action: str
    #: The runbook's own repeat boundary — see the module docstring. Empty means
    #: *this may happen to this subject exactly once, ever*, which is almost
    #: never what a runbook wants and is never chosen by accident.
    discriminator: str = ""
    decided_by_rule: str = ""
    reason: str = ""
    fix_route: str = ""
    amount: Decimal | None = None
    currency: str | None = None
    #: The keyword arguments handed to the port's writer. Ids and code words.
    payload: Mapping[str, Any] = field(default_factory=dict)
    #: What the audit row is ABOUT once the write lands — the owning module's
    #: entity, not ours. Filled from the writer's answer when it can be.
    entity_type: str = ""


@dataclass
class PlannedAct:
    """A written `runbook_run_records` row, waiting for `act()`."""

    request: ActRequest
    record_id: Any
    idempotency_key: str
    #: True when the key was ALREADY in the index — an earlier run of this
    #: runbook already did this to this subject at this rung. Nothing is written
    #: again and the clerk is told which run did it.
    already: bool = False
    outcome: str = ""


def idempotency_key(
    *,
    runbook_key: str,
    action_kind: str,
    subject: SubjectRef,
    discriminator: str = "",
) -> str:
    """The per-record key. **The run is deliberately not in it** — see the docstring.

    Worked, on the ladder's own figures: 248 accounts are due the 10-day notice
    on Monday. The 07:00 run writes 248 keys. The 09:00 re-run computes the
    SAME 248 keys, the UNIQUE index refuses every one of them, and the second
    Done screen reads **0 queued** while naming the 248 already sent — *248
    notices in total, not 496*, which is `TC-RBS-4`'s figure and the reason the
    run is not in the key.

    And the mirror, which is why `discriminator` exists: the same customer at
    the 5-day rung three days later has a DIFFERENT key, so they are written to
    again. Drop the discriminator and they never are.
    """
    parts = (
        runbook_key,
        action_kind,
        subject.subject_type,
        str(subject.subject_id),
        discriminator,
    )
    for part in parts[:4]:
        if not str(part).strip():
            raise ActRefused(
                "an idempotency key needs the runbook, the action kind and the subject; "
                f"got {parts!r}. A blank component would collapse two different acts onto "
                "one key and the second would be silently refused (hard rule 6)."
            )
    return "|".join(str(part) for part in parts)


def actor_for(ctx: Any) -> core_audit.AutomationActor:
    """The runbook, named and versioned — never a person (`BR-RBS-015`).

    The NAME is the runbook's own display name, because that is what a clerk
    reads in the trail: *"Collections ladder, version 1"*. The VERSION is the
    version pinned on the run (`BR-RBS-038`), so a row written by version 1
    still says version 1 after somebody edits the runbook to version 2 — which
    is the whole reason `actor_version` is a column rather than a lookup.
    """
    run = _run_row(ctx)
    name = getattr(ctx, "runbook_name", "") or ctx.runbook_key
    version = str(run.version) if run is not None else None
    return core_audit.AutomationActor(
        kind=core_audit.ACTOR_KIND_RUNBOOK, name=name, version=version
    )


def _run_row(ctx: Any) -> Any:
    """The run row, read FRESH. Returns None when the ctx carries no run.

    Read fresh rather than cached because `stop.py` asks the same row the same
    way and a cached status is a stop button that does not stop anything —
    `TC-RBS-9`'s *"a stop that only sets a flag"*.
    """
    run_id = getattr(ctx, "run_id", None)
    if run_id is None:
        return None
    return models.RunbookRun.objects.filter(pk=run_id).first()


def live_enabled(runbook_key: str) -> bool:
    """Is this runbook allowed to reach a bound writer? **No, in wave L.**"""
    return runbook_key in LIVE_ENABLED_RUNBOOKS


def plan(ctx: Any, request: ActRequest) -> PlannedAct:
    """Write the record row FIRST — the plan, before anything is acted on.

    `BR-RBS-004`. The row carries `planned_action`, the rule that decided it in
    a clerk's words (`BR-RBS-010`) and, where there is money, the amount with
    its currency beside it (hard rule 2 — stored to 4 decimals, displayed to 2,
    and never a float).

    ⚠ **THE INSERT IS THE IDEMPOTENCY CHECK AND THE `SELECT` IS ONLY THE
    SENTENCE.** A retry arrives concurrently: two workers each find no row and
    each write one, and only a UNIQUE INDEX refuses the second. So the INSERT
    runs inside its OWN SAVEPOINT and an `IntegrityError` out of it is read as
    *"already done"*, never as a failure. On PostgreSQL a nested
    `transaction.atomic()` issues a real `SAVEPOINT`; without it the refused row
    aborts the whole transaction and every later record is lost at COMMIT,
    however carefully the exception was caught (hard-won law 14, and the suite
    is SQLite, which cannot show you that).
    """
    if ctx.tenant_id is None and core_tenancy.current_tenant_id() is None:
        raise ActRefused(
            "no tenant context: a runbook may not write a record row without app.tenant_id "
            "set (CLAUDE.md hard rule 1; RLS FORCE would refuse it anyway)."
        )
    key = idempotency_key(
        runbook_key=ctx.runbook_key,
        action_kind=request.action_kind,
        subject=request.subject,
        discriminator=request.discriminator,
    )
    tenant_id = ctx.tenant_id or core_tenancy.current_tenant_id()
    existing = models.RunbookRunRecord.objects.filter(
        tenant_id=tenant_id, idempotency_key=key
    ).first()
    if existing is not None:
        return _resume_or_refuse(ctx, request, existing, key)
    try:
        with transaction.atomic():  # ⚠ a SAVEPOINT — read the docstring
            row = models.RunbookRunRecord.objects.create(
                tenant_id=tenant_id,
                run_id=ctx.run_id,
                subject_type=request.subject.subject_type,
                subject_id=_as_uuid(request.subject.subject_id),
                planned_action=request.planned_action,
                decided_by_rule=request.decided_by_rule or None,
                reason=request.reason or None,
                fix_route=request.fix_route or None,
                amount=request.amount,
                currency=request.currency,
                # ⚠ **`jsonable`, NOT `dict` — `DEF-RBS-4340`, found by the
                # FIRST firing of wave `M`'s dry cycle and by nothing else.**
                # A port's payload is the writer's kwargs, so it legitimately
                # carries rich objects: runbook 8 puts an `AutomationActor` in
                # it because `queue_notice` needs one. `data` is a jsonb
                # column, and storing the payload VERBATIM raised
                # `TypeError: Object of type AutomationActor is not JSON
                # serializable` on the first record of the first run — every
                # run, dry and live, over any Action with an actor in its
                # payload. The whole acting half was unrunnable and every test,
                # gate and typecheck was green.
                # `core/audit.jsonable` was written for exactly this class
                # (`DEF-657`) and its docstring says where it belongs: *"at the
                # single place all of them pass through"*, which for this
                # column is here. `_seal` twenty lines below already coerces
                # its half of the same row — *"the two halves of one row
                # disagreed about their own types"* is DEF-657's own sentence
                # and it was true again.
                # The LIVE object is untouched: `act()` still calls
                # `port.call(**dict(planned.request.payload))`, so the writer
                # receives the actor and only the stored copy is flattened.
                data=core_audit.jsonable(dict(request.payload)),
                idempotency_key=key,
            )
    except IntegrityError:
        # The index refused it — which is the ANSWER. Another worker, or an
        # earlier run of this same runbook, already planned this act for this
        # subject at this rung.
        earlier = models.RunbookRunRecord.objects.filter(
            tenant_id=tenant_id, idempotency_key=key
        ).first()
        if earlier is None:  # pragma: no cover — the index refused, so a row exists
            return PlannedAct(
                request=request, record_id=None, idempotency_key=key, already=True,
                outcome=OUTCOME_ALREADY,
            )
        return _resume_or_refuse(ctx, request, earlier, key)
    return PlannedAct(request=request, record_id=row.pk, idempotency_key=key)


#: The outcomes that mean **the act HAPPENED** and must never happen again. A
#: key holding one of these is spent for ever, which is the whole point of
#: `TC-RBS-4`'s *248 notices, not 496*.
OUTCOMES_SPENT = frozenset({OUTCOME_DONE, OUTCOME_ALREADY})


def _resume_or_refuse(
    ctx: Any, request: ActRequest, existing: Any, key: str
) -> PlannedAct:
    """A key already in the index — **did the act HAPPEN, or was it only planned?**

    ⚠ **THIS DISTINCTION IS `DEF-RBS-4347`'s SECOND HALF, AND WITHOUT IT PHASE
    2's DRY CYCLE PERMANENTLY DISABLES THE LIVE ONE.** The first version of this
    file read *a row exists* as *already done*, and it is not the same sentence.
    Wave `M` ran the collections ladder DRY for a month on a real tenant and
    wrote **878 record rows with outcome `planned`** — the word that means *the
    step reached the port and the port had no writer*, i.e. **nothing was
    written anywhere**. Turn the runbook live the next morning and every one of
    those 878 keys is in the index, every `act()` returns `already`, and the
    ladder queues **0 notices for ever**. The customer is never chased and the
    Done screen reads *"0 queued · 878 already sent"* about letters that were
    never written, let alone posted.
    **Nothing could have caught that**: the run is green, the counts add up, the
    idempotency guarantee is doing exactly what it was told, and the only wrong
    thing is which question it was asked.

    **So the row is read for its OUTCOME, not for its existence:**

    * `done` · `already` — the act HAPPENED. Refused, for ever, and the clerk is
      told which run did it. This is the guarantee `TC-RBS-4` measures.
    * `planned` — a plan and nothing else. **Resumable**, and this is the ONLY
      thing that makes `BR-RBS-004`'s *plan first, then act* possible at all:
      the approval pass finds its own plan rows and carries them out.
    * `held` · `failed` — the port refused, or the database did. Also resumable:
      a missing template that has since been published, or a deadlock, must not
      exclude that customer from every future run of this runbook.
    * anything else, including blank — treated as spent, because an outcome word
      this file does not recognise is not evidence that nothing happened.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7, habit 2): treating
    `already` as resumable. It is the word `act()` stamps when it REFUSED on
    this very rule, so resuming it would make the refusal self-clearing and the
    second run would send. It is in `OUTCOMES_SPENT` for that reason and the
    test asserts it by name.

    The row is re-pointed at THIS run, because *what did it say it would do
    versus what it did* must be answerable from the run that did it — a resumed
    row still showing the planning run would put the act on the wrong pass.
    """
    outcome = (existing.outcome or "").strip()
    if outcome in OUTCOMES_SPENT or outcome not in _RESUMABLE:
        return PlannedAct(
            request=request,
            record_id=existing.pk,
            idempotency_key=key,
            already=True,
            outcome=outcome or OUTCOME_ALREADY,
        )
    models.RunbookRunRecord.objects.filter(pk=existing.pk).update(
        run_id=ctx.run_id,
        planned_action=request.planned_action,
        decided_by_rule=request.decided_by_rule or None,
        reason=request.reason or None,
        fix_route=request.fix_route or None,
        amount=request.amount,
        currency=request.currency,
        data=core_audit.jsonable(dict(request.payload)),
    )
    return PlannedAct(request=request, record_id=existing.pk, idempotency_key=key)


#: The outcomes that mean **nothing was written**, so the act may still be
#: carried out. Kept beside `OUTCOMES_SPENT` rather than derived from it,
#: because *everything not spent is resumable* would silently make a new outcome
#: word resumable on the day somebody adds one.
_RESUMABLE = frozenset({OUTCOME_PLANNED, OUTCOME_HELD, OUTCOME_FAILED})


def act(ctx: Any, planned: PlannedAct) -> PlannedAct:
    """Perform the write — or record what it WOULD have done, on the same path.

    ⚠ **THE ONLY QUESTION ASKED HERE IS `port.is_bound`** (`BR-RBS-003`). In
    wave L no runbook is on `LIVE_ENABLED_RUNBOOKS`, so `build_context` hands
    every step writer-less ports and this records `planned`. The statements
    walked are the same ones a live run walks, which is what makes the dry run
    evidence about the live one.

    ⚠ **EVERY OUTCOME WRITES AN AUDIT ROW, INCLUDING `planned`.** Hard rule 7
    audits the ACTION, and *the automation decided to charge this customer a
    fee and was held* is exactly the fact a disputing customer asks about six
    weeks later. Writing the row only on success would leave the whole dry
    cycle — the thing wave `M` soaks for a month — invisible to the trail.
    """
    if planned.already:
        _write_audit(ctx, planned, outcome=OUTCOME_ALREADY)
        return _seal(planned, OUTCOME_ALREADY)

    port = ctx.port(planned.request.port)
    if not port.is_bound:
        _write_audit(ctx, planned, outcome=OUTCOME_PLANNED)
        return _seal(planned, OUTCOME_PLANNED)

    try:
        with transaction.atomic():  # ⚠ a SAVEPOINT — hard-won law 14
            answer = port.call(**dict(planned.request.payload))
    except DatabaseError as exc:
        # The row is refused by the database. The savepoint above rolls back to
        # itself, the transaction survives, and the other 1,003 records commit.
        _write_audit(ctx, planned, outcome=OUTCOME_FAILED, detail={"error": str(exc)})
        return _seal(planned, OUTCOME_FAILED, reason=str(exc))
    except Exception as exc:  # the owning module's own refusal, in its words
        _write_audit(ctx, planned, outcome=OUTCOME_HELD, detail={"refused": str(exc)})
        return _seal(planned, OUTCOME_HELD, reason=str(exc))

    detail = dict(answer) if isinstance(answer, Mapping) else {"answer": str(answer)}
    # ⚠ **A PORT MAY ANSWER *NOT DONE* WITHOUT RAISING (`CR-173-BRC10`).** A
    # port that raises has its savepoint rolled back above — correct for a
    # write that did not happen, and fatal for a port whose FAILURE is itself
    # a record: `send_partner_file` writes the run row Settings → Integrations
    # shows and alerts the System Admins when the City's folder refuses, and a
    # raise would erase both. So `{"done": False, "reason": …}` seals the row
    # FAILED — resumable, so the next run tries again — with the port's own
    # sentence, and nothing it wrote is rolled back. Only an explicit `False`
    # counts: an answer that does not mention `done` is DONE, exactly as before.
    if detail.get("done") is False:
        why = str(detail.get("reason") or "the owning module did not act")
        _write_audit(ctx, planned, outcome=OUTCOME_FAILED, detail=detail)
        return _seal(planned, OUTCOME_FAILED, reason=why, detail=detail)
    _write_audit(ctx, planned, outcome=OUTCOME_DONE, detail=detail)
    return _seal(planned, OUTCOME_DONE, detail=detail)


def perform(ctx: Any, request: ActRequest) -> PlannedAct:
    """`plan` then `act`, which is the only order there is (`BR-RBS-004`)."""
    return act(ctx, plan(ctx, request))


# ── the two writes this file owns, and nothing else ───────────────────────


def _seal(
    planned: PlannedAct,
    outcome: str,
    *,
    reason: str = "",
    detail: Mapping[str, Any] | None = None,
) -> PlannedAct:
    """Stamp the outcome onto the record row — the second half of one row.

    ⚠ **THIS IS NOT AN EDIT OF FINANCIAL HISTORY.** Hard rule 4 names issued
    invoices, invoice lines, payments and journal entries; `runbook_run_records`
    is this module's own table and its whole design is *the plan, then the
    outcome, in the same row* — two tables would make *what did it say it would
    do versus what it did* a join, and the audit becomes a query nobody writes.
    """
    if planned.record_id is None:
        planned.outcome = outcome
        return planned
    updates: dict[str, Any] = {"outcome": outcome}
    if reason:
        updates["reason"] = reason
    if detail:
        row = models.RunbookRunRecord.objects.filter(pk=planned.record_id).first()
        merged = dict(row.data or {}) if row is not None else {}
        merged["result"] = core_audit.jsonable(dict(detail))
        updates["data"] = merged
    models.RunbookRunRecord.objects.filter(pk=planned.record_id).update(**updates)
    planned.outcome = outcome
    return planned


def _write_audit(
    ctx: Any,
    planned: PlannedAct,
    *,
    outcome: str,
    detail: Mapping[str, Any] | None = None,
) -> None:
    """Hard rule 7, with the RUNBOOK as the actor (`BR-RBS-015`).

    ⚠ **`money_action` BRANCHES ON `AutomationActor` AND THAT BRANCH IS WHY
    THIS WORKS.** An `AutomationActor` has no `.id` and no `.pk`, so a writer
    that reached for `getattr(actor, "id")` would resolve it to `None` and write
    a BLANK row — the automation silently losing its name on the way to the
    trail, with every test still green. `core/audit.py` says so in its own
    docstring and branches first.

    ⚠ **NOT CAUGHT.** `AuditWriteError` propagates: rule 7 says the action may
    not stand without its row, and this is the money path.
    """
    core_audit.money_action(
        actor_for(ctx),
        AUDIT_ACTION,
        AUDIT_ENTITY,
        str(planned.record_id) if planned.record_id is not None else "",
        after={
            "runbook": ctx.runbook_key,
            "run_id": str(getattr(ctx, "run_id", "") or ""),
            "port": planned.request.port,
            "action_kind": planned.request.action_kind,
            "subject_type": planned.request.subject.subject_type,
            "subject_id": str(planned.request.subject.subject_id),
            "planned_action": planned.request.planned_action,
            "outcome": outcome,
            "idempotency_key": planned.idempotency_key,
            # Money never travels without its currency (hard rule 2).
            "amount": str(planned.request.amount) if planned.request.amount is not None else None,
            "currency": planned.request.currency,
            "detail": dict(detail or {}),
        },
    )


def _as_uuid(value: Any) -> Any:
    """`subject_id` is a `UUIDField`; a runbook whose subject is not a row leaves it null."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-012 · US-RBS-014 (EP-RBS-04; CR-075 wave L tasks L2 + L5)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — the approve/stop routes are L3 and a sibling's api.py) E=n/a(no screen — L7's screens are another lane's) F✔ G✔ H✔(🔒 idempotency keys — HUMAN-OWNED + HUMAN-REVIEW-PENDING above, row in 12-governance/09-human-review-ledger.md, glob in 10-scripts/gates/human_owned.txt)
# gates: pytest tests/test_us_rbs_012_acts.py · pytest tests/test_us_rbs_012_pg.py (PostgreSQL) · G115 (the import census) · G7 (the 🔒 ledger row)
# exceptions: LIVE_ENABLED_RUNBOOKS is EMPTY — no runbook can reach a bound writer in wave L, which is the wave's own posture and not a gap
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
