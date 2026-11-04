# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-008 (EP-RBS-03) — CR-075 wave J tasks J1 and J3: cutover
#           plans, their items, and the run whose result becomes an item's
#           EVIDENCE.
# Rules:    BR-RBS-026 (Onboarding & Cutover sorts first while a plan is open
#           and last once it closes) · BR-RBS-011 (a failure names its fix
#           route) · BR-RBS-020 (a run's report is frozen at close, so evidence
#           read from it cannot change afterwards) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 2 (money 4 stored / 2 displayed) ·
#           hard rule 7 (every money action writes audit_log) · B14 rule 31
#           (no database id is ever the visible value of a field)
# Tests:    06-backend/tests/test_us_rbs_008_cutover_readiness.py
# Impacts:  apps/runbooks/cutover_api.py (the three routes) ·
#           apps/runbooks/definitions/cutover_readiness.py (step 9 reads a plan)
# ───────────────────────────────────────────────────────
"""Cutover plans, their items, and how a RUN becomes an item's evidence.

A cutover plan is the list of things that must be true before a utility can be
switched off its old system. Some of them this product can check — *balances
tie*, *sample data gone* — and some of them it never can: *the customer signs
off the bill layout* is a person's act with a person's name on it.

⚠ **A NULL `runbook_key` IS A HUMAN TASK THE ENGINE NEVER PERFORMS**
(`03-field-map.md` D-7, `US-RBS-008` §7). That is the whole distinction the
column carries, and it is nullable rather than required precisely so the
commonest item on a real plan — *Legacy set read-only · Utility IT* — can exist.

════════════════════════════════════════════════════════════════════════════
THE INTEGRATION BETWEEN A PLAN AND THE ENGINE, IN ONE SENTENCE
════════════════════════════════════════════════════════════════════════════
**A plan item optionally names a runbook; the run id and its figures are stored
ON the item; and a ZERO-VARIANCE re-run turns the item green on its own.**

Three things follow from it and each is a decision rather than an implementation
detail:

1. **THE FIGURES ARE COPIED ONTO THE ITEM, NOT LOOKED UP THROUGH THE RUN.**
   `evidence_ref` carries *"$1,204.05 variance, 12 accounts"* as text. `RB-102`'s
   own design note asks for this — *"the plan shows why it went green, not
   merely that it did"* — and the reason it is a copy is retention: a run is
   prunable and a cutover plan is the record an implementer hands over at
   go-live. `last_run` is kept BESIDE it as a foreign key with `SET_NULL`, so
   the trail survives as words when the row does not.

2. **THE RUNBOOK DOES NOT ATTACH ITS OWN EVIDENCE.** It is a Check and holds no
   ports at all (`BR-RBS-002`); attaching is a person pressing **Attach to plan
   ✓** on `RBS-006-R2`. Two acts, and only the second one writes — which is why
   `RB-102`'s card says *"attaching evidence to the plan is an act the engine or
   the owning module performs"*.

3. **GREEN IS DECIDED HERE AND NOT IN THE RUNBOOK.** The run publishes a
   variance; this module reads it and applies the rule. Putting the rule in the
   runbook would mean a Check deciding whether a task is done, which is exactly
   the write `BR-RBS-002` removes from it.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ANSWERED IN WRITING** (hard-won law 7).
The dangerous shape is **an item that goes green because the run found nothing
to compare** — no trial balance, a file whose every line failed to parse, a run
that failed. So `attach_evidence` refuses a run that is not `done`, refuses one
whose runbook is not the one the item names, and reads the variance from the
FROZEN report rather than recomputing it. A run that compared zero lines carries
a blocker, so its verdict is not `Go` and the item does not turn green.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.runbooks import models
from core import errors
from core import tenancy as core_tenancy

#: A plan item is open, done, or blocked. Three and no fourth: `RBS-006-R2`
#: region 12 draws two states and the third exists because an implementer needs
#: to say *"this one is stuck and it is not mine"* without ticking it.
ITEM_OPEN = "open"
ITEM_DONE = "done"
ITEM_BLOCKED = "blocked"
ITEM_STATUSES = (ITEM_OPEN, ITEM_DONE, ITEM_BLOCKED)

PLAN_OPEN = "open"
PLAN_CLOSED = "closed"
PLAN_STATUSES = (PLAN_OPEN, PLAN_CLOSED)

ZERO = Decimal("0")


def _tenant_id() -> Any:
    """The tenant, or a refusal. **Never a default** (CLAUDE.md hard rule 1)."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _plans():
    return models.CutoverPlan.objects.filter(tenant_id=_tenant_id())


def _items(plan):
    return models.CutoverPlanItem.objects.filter(tenant_id=plan.tenant_id, plan=plan)


# ── reading ───────────────────────────────────────────────────────────────


def plan_dict(plan: models.CutoverPlan) -> dict[str, Any]:
    """One plan and its items, in the reader's terms.

    ⚠ **`id` IS SERVED AND IS NEVER THE VISIBLE VALUE OF A FIELD** (B14 rule
    31). A screen needs it to build a link; what it DRAWS is `name` and the
    item's `seq`, which is the number an implementer says out loud — *"item 4 is
    still open"*.
    """
    return {
        "id": str(plan.id),
        "name": plan.name,
        "go_live_on": plan.go_live_on,
        "status": plan.status,
        "closed_at": plan.closed_at,
        "items": [item_dict(item) for item in _items(plan).order_by("seq")],
    }


def item_dict(item: models.CutoverPlanItem) -> dict[str, Any]:
    """One plan item, with its evidence and whether a person owns it."""
    return {
        "seq": item.seq,
        "title": item.title,
        "owner": item.owner,
        "due_on": item.due_on,
        "runbook_key": item.runbook_key,
        # ⚠ THE WORD A CLERK READS, DERIVED HERE AND NOT ON THE SCREEN. Two
        # screens deriving *"is this a human task"* from a null is two places
        # the rule can drift; `RBS-006-R2` region 12 draws this pill.
        "human_task": item.runbook_key is None,
        "last_run_id": str(item.last_run_id) if item.last_run_id else None,
        "evidence_ref": item.evidence_ref,
        "status": item.status,
    }


def open_plan() -> models.CutoverPlan | None:
    """The tenant's open cutover plan, or None.

    ⚠ **THE MOST RECENT OPEN ONE, AND A TENANT NORMALLY HAS AT MOST ONE.**
    Nothing in the schema forbids two — a utility rehearsing a cutover and then
    doing it for real legitimately has a closed one and an open one — so this
    picks by `-created_at` rather than asserting uniqueness, which would refuse
    the rehearsal case for the sake of a guarantee nobody asked for.
    """
    return _plans().filter(status=PLAN_OPEN).order_by("-created_at", "-id").first()


def plan_for_run(plan_ref: Any = None) -> dict[str, Any] | None:
    """The plan a run is about — named, or the tenant's open one.

    Runbook 2's step 9 calls this. A run started with no plan named still has to
    say something useful, and *"the plan that is open"* is what an implementer
    means when they press Run without choosing.

    ⚠ **A NAME OR AN ID, BOTH ACCEPTED.** The `ref:object` parameter carries
    whatever the setup screen put in it, and a run recorded three months ago may
    name a plan by a string that is no longer an id. Resolving by name as well
    means an old run still reads correctly, which is what `BR-RBS-020`'s freeze
    is for.
    """
    plan = None
    if plan_ref not in (None, ""):
        plan = _plans().filter(pk=str(plan_ref)).first() if _looks_like_id(plan_ref) else None
        if plan is None:
            plan = _plans().filter(name=str(plan_ref)).first()
    if plan is None:
        plan = open_plan()
    return None if plan is None else plan_dict(plan)


def _looks_like_id(value: Any) -> bool:
    """A uuid-shaped string. A `filter(pk=…)` on a name RAISES on PostgreSQL.

    ⚠ **AND IT DOES NOT ON SQLITE, WHICH IS HARD-WON LAW 14's SECOND COSTUME.**
    `filter(pk="Silver Creek go-live")` against a uuid column is a
    `DataError: invalid input syntax for type uuid` on PostgreSQL and a quiet
    empty queryset on SQLite — so the version without this guard passes the
    whole suite green and 500s the first time an implementer names their plan.
    """
    text = str(value)
    return len(text) == 36 and text.count("-") == 4


def plans_page(*, page: int = 1, per: int = 50) -> dict[str, Any]:
    """Every plan, newest first, PAGED — `NFR-3`, and it has no exceptions.

    ⚠ **THERE IS NO UNPAGINATED LIST IN THIS MODULE AND THERE MUST NOT BE ONE.**
    `NFR-3` and `NFR-5` are CLAUDE.md's load-bearing flexibility for T4/T3, and
    the repo already carries four breaches that named the old 3,000 ceiling as
    their excuse (`DEF-PAY-4221`). A cutover plan list is short today; the rule
    is not about today.
    """
    per = max(1, min(int(per or 50), 1000))
    page = max(1, int(page or 1))
    queryset = _plans().order_by("-created_at", "-id")
    total = queryset.count()
    start = (page - 1) * per
    return {
        "rows": [plan_dict(plan) for plan in queryset[start : start + per]],
        "page": page,
        "per": per,
        "total": total,
    }


# ── writing ───────────────────────────────────────────────────────────────


def create_plan(
    *, name: str, go_live_on: Any = None, items: Any = None, actor_id: Any = None
) -> dict[str, Any]:
    """A plan and its items, in one transaction.

    `seq` is the caller's own ordering and is UNIQUE per plan
    (`uq_cutover_plan_items_seq`), so two items cannot claim position 4 and a
    plan always reads in one order. Absent, it is the item's position in the
    list — which is what somebody typing a plan means.
    """
    tenant_id = _tenant_id()
    label = str(name or "").strip()
    if not label:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="runbooks.cutover.name")
    with transaction.atomic():
        plan = models.CutoverPlan.objects.create(
            tenant_id=tenant_id, name=label, go_live_on=go_live_on, status=PLAN_OPEN
        )
        for position, raw in enumerate(list(items or ()), start=1):
            entry = dict(raw)
            title = str(entry.get("title") or "").strip()
            if not title:
                raise errors.ValidationError(
                    errors.VAL_REQUIRED, message_key="runbooks.cutover.item_title"
                )
            models.CutoverPlanItem.objects.create(
                tenant_id=tenant_id,
                plan=plan,
                seq=int(entry.get("seq") or position),
                title=title,
                owner=(str(entry["owner"]).strip() if entry.get("owner") else None),
                due_on=entry.get("due_on"),
                # ⚠ THE NULL IS THE POINT — a human task the engine never
                # performs. `or None` rather than `""`, because an empty string
                # would be a runbook key that names nothing and step 9 would
                # count it as automatable.
                runbook_key=(str(entry["runbook_key"]).strip() or None)
                if entry.get("runbook_key")
                else None,
                status=ITEM_OPEN,
            )
    _audit(
        "cutover.plan_created",
        plan,
        actor_id=actor_id,
        after={"name": label, "items": len(list(items or ()))},
    )
    return plan_dict(plan)


def update_item(
    *, plan_id: Any, seq: int, status: Any = None, owner: Any = None, actor_id: Any = None
) -> dict[str, Any]:
    """Tick, un-tick or re-own ONE item. `PATCH /cutover-plans/{id}/items/{seq}`.

    ⚠ **A HUMAN TASK IS TICKED BY A PERSON AND NOTHING ELSE MAY TICK IT.** That
    is not enforced by a role here — it is enforced by there being no other
    caller: `attach_evidence` below refuses an item whose `runbook_key` is null,
    by name, so a run can never complete somebody's signature.
    """
    plan = _plans().filter(pk=str(plan_id)).first()
    if plan is None:
        raise errors.NotFoundError(errors.NOT_FOUND)
    item = _items(plan).filter(seq=int(seq)).first()
    if item is None:
        raise errors.NotFoundError(errors.NOT_FOUND)
    if status is not None:
        if status not in ITEM_STATUSES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="runbooks.cutover.item_status"
            )
        item.status = status
    if owner is not None:
        item.owner = str(owner).strip() or None
    item.save(update_fields=["status", "owner", "updated_at"])
    _audit(
        "cutover.item_updated",
        plan,
        actor_id=actor_id,
        after={"seq": item.seq, "title": item.title, "status": item.status, "owner": item.owner},
    )
    return item_dict(item)


def attach_evidence(
    *, plan_id: Any, seq: int, run_id: Any, actor_id: Any = None
) -> dict[str, Any]:
    """**Attach to plan ✓** — a RUN becomes this item's evidence, `US-RBS-008` §7.

    Four refusals, and each one is a way an item could otherwise go green over
    nothing:

    1. **The run must be `done`.** A `failed` or still-`running` run has no
       verdict, and a report that has not been frozen (`BR-RBS-020`) can still
       change.
    2. **The run's runbook must be the one the item NAMES.** Attaching a cash
       application run to *balances tie* would put a green tick and a real run id
       on a task nobody performed — evidence that is worse than none, because it
       looks checkable.
    3. **A HUMAN TASK REFUSES EVIDENCE.** `runbook_key IS NULL` means the engine
       never performs it (`03-field-map.md` D-7). *Customer signs bill layout* is
       ticked by a person on `update_item`, and a run cannot sign anything.
    4. **The variance is read from the FROZEN report, never recomputed.** The
       report is the artefact `BR-RBS-020` freezes and `TC-RBS-16` asserts
       byte-for-byte; recomputing here would mean the plan and the run could
       state different reasons for the same tick.

    **A ZERO-VARIANCE RE-RUN TURNS THE ITEM GREEN ON ITS OWN**, which is
    `US-RBS-008`'s own sentence. *Zero variance* is read as **the run's verdict
    carries no blocker** rather than as *the difference is 0.00*, and that is a
    recorded judgment: a run whose balances tie perfectly but which found sample
    data still present is not a cutover anybody should tick, and the verdict is
    the one place all nine steps are already summed.
    """
    plan = _plans().filter(pk=str(plan_id)).first()
    if plan is None:
        raise errors.NotFoundError(errors.NOT_FOUND)
    item = _items(plan).filter(seq=int(seq)).first()
    if item is None:
        raise errors.NotFoundError(errors.NOT_FOUND)
    if item.runbook_key is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RBS-008",
            message_key="runbooks.cutover.human_task_takes_no_evidence",
        )
    run = models.RunbookRun.objects.filter(tenant_id=plan.tenant_id, pk=str(run_id)).first()
    if run is None:
        raise errors.NotFoundError(errors.NOT_FOUND)
    if run.status != models.RUN_STATUS_DONE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RBS-020",
            message_key="runbooks.cutover.run_not_finished",
        )
    if run.runbook.key != item.runbook_key:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-RBS-008",
            message_key="runbooks.cutover.run_is_a_different_runbook",
        )

    verdict = verdict_of(run)
    item.last_run = run
    item.evidence_ref = evidence_sentence(verdict)
    item.status = ITEM_DONE if verdict["clear"] else ITEM_OPEN
    item.save(update_fields=["last_run", "evidence_ref", "status", "updated_at"])
    _audit(
        "cutover.evidence_attached",
        plan,
        actor_id=actor_id,
        after={
            "seq": item.seq,
            "title": item.title,
            "status": item.status,
            "evidence": item.evidence_ref,
            # ⚠ THE RUN ID IS IN THE TRAIL AND NEVER ON THE SCREEN (B14 rule
            # 31). An auditor asking *which run said this* needs it; the
            # implementer reading the plan needs the sentence.
            "run_id": str(run.id),
        },
    )
    return item_dict(item)


# ── reading a frozen report ───────────────────────────────────────────────


def verdict_of(run: models.RunbookRun) -> dict[str, Any]:
    """The verdict block of a run's FROZEN report, and whether it is clear.

    ⚠ **`clear` IS DERIVED FROM THE VERDICT'S TONE, NOT FROM ITS WORD.** The
    words are a runbook's own — *Go*, *Balanced*, *Ready to import* — and a
    fifth runbook will invent a sixth. The TONE is the contract: `success` is the
    only tone that means nothing is outstanding, and `VerdictTone` is a closed
    vocabulary the renderer already draws from.
    """
    blocks = list(run.report or ())
    verdict = next(
        (block for block in blocks if block.get("block") == "verdict"), {"payload": {}}
    )
    payload = dict(verdict.get("payload") or {})
    return {
        "word": str(payload.get("word") or ""),
        "tone": str(payload.get("tone") or ""),
        "count": str(payload.get("count") or ""),
        "detail": str(payload.get("detail") or ""),
        "clear": str(payload.get("tone") or "") == "success",
    }


def evidence_sentence(verdict: dict[str, Any]) -> str:
    """*"Go · 9 of 9 steps clear"* — what the plan item shows, in words.

    ⚠ **NO RUN ID AND NO RULE NUMBER** (B14 rules 31 and 32). An implementer
    reading a plan wants to know why it went green; the run id is on the item as
    a link and the rule is in this file's docstrings. Rule 33 caps a FACT at six
    words, and the join is a middle dot so each clause is counted on its own.
    """
    parts = [verdict["word"], verdict["count"]]
    if verdict["detail"]:
        parts.append(verdict["detail"])
    return " · ".join(part for part in parts if part)


# ── the audit row ─────────────────────────────────────────────────────────


def _audit(action: str, plan: models.CutoverPlan, *, actor_id: Any, after: dict[str, Any]) -> None:
    """Every write here writes `audit_log` — CLAUDE.md hard rule 7.

    ⚠ **THIS ONE CARRIES A PERSON AND NOT AN AUTOMATION ACTOR, AND THE
    DISTINCTION IS `BR-AUD-019`'s WHOLE POINT.** A runbook passes
    `AutomationActor("runbook", …)` so a clerk reads *"Returned payments,
    version 4"* rather than a colleague's name. These three acts are a PERSON
    pressing a button — creating the plan, ticking an item, attaching evidence —
    so `actor_user_id` is the signed-in user and `automation` is absent. A
    cutover plan is the record an implementer hands over at go-live, and *who
    ticked this* is the first question asked of it.

    ⚠ **`core.audit.write_row` REFUSES A ROW CARRYING BOTH**, by name, so the
    two cannot be confused here even by accident — and it refuses a row with no
    tenant context and one with no sink, because *"losing the row silently is
    not an option"* (rule 7). Nothing below catches those: an audit that cannot
    be written must fail the action rather than let it through unrecorded.
    """
    from core import audit as core_audit

    core_audit.write_row(
        action=action,
        entity_type="cutover_plan",
        entity_id=str(plan.id),
        actor_user_id=actor_id,
        after=after,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-008 (EP-RBS-03; RB-102; CR-075 wave J tasks J1 and J3; 03-field-map.md D-7)
# generated: 2026-09-07 by the CR-075 wave J build lane
# checklist: A✔ B✔ C✔ D✔(apps/runbooks/cutover_api.py) E=n/a(RBS-006-R2 renders the run; the plan surface is RBS-007, wave H) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_008_cutover_readiness.py · G115
# exceptions: (1) `clear` is read from the verdict's TONE and not its WORD — the words are each runbook's own and the tone is the closed vocabulary · (2) a zero-variance re-run means NO BLOCKER in the verdict rather than a 0.00 difference, argued in `attach_evidence`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
