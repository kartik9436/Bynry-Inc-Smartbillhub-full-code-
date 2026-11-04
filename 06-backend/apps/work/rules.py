# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — rules that raise work orders on their own.
#           Screens: Work-026 (the list + the five-step builder), Work-007
#           (RAISED BY), Work-020.
# Rules:    BR-WRK-033 (a rule raises orders without a person; a rule that is
#           OFF raises nothing; every rule-raised order carries the rule as its
#           source; the list shows this month's count) · BR-WRK-024 (the source
#           stamp and the rule stamp) · BR-WRK-002 (every cross-module read is
#           through a seam; Work writes no other module's tables) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit_log) ·
#           hard-won law 14 (a SAVEPOINT per subject, or one refused row loses
#           the whole night's work on PostgreSQL)
# Tests:    06-backend/tests/test_us_wrk_037_rules.py (TC-1…TC-7, run with
#           JOBS_EAGER=false --reuse-db) · tests/test_us_wrk_037_rules_pg.py
#           (idempotency under a real aborted statement + RLS isolation, real
#           PostgreSQL, NOSUPERUSER role)
# Impacts:  apps/work/apps.py (registers the job, its queue AND the beat entry)
#           · apps/work/api.py (#82–#87) · apps/work/rules_models.py ·
#           apps/work/seams/{payments,billing,assets,metering,customers}_seam.py
# ───────────────────────────────────────────────────────
"""`work.rules_sweep` — the product's first nightly rule engine.

WHAT THIS FILE IS FOR, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
At 02:00 nobody is at the utility, and by 07:00 the dispatcher's screen has
three *Meter exchange* jobs on it, each saying **Raised by: Asset age rule**.

FIVE READERS, ONE PER SOURCE MODULE, ALL THROUGH SEAMS
────────────────────────────────────────────────────────────────────────────
`BR-WRK-033` gives a rule a `source_module`, and there are exactly five:

    payments   a final notice expired unpaid       payments_seam
    billing    a bill-run break nobody resolved    billing_seam
    assets     a meter past its certification life assets_seam
    reads      a continuous-flow alarm             metering_seam
    accounts   a move-in that has committed        customers_seam

Every one of them is a function in `apps/work/seams/`, and NOT because a rule
file says so — because **G78 fails the merge** on an import of another module's
models anywhere under `apps/work/` outside that package. The reason is worth
more than the rule: this code runs unattended, so a query written straight
against another module's tables would rot the day that module changes a column
and would fail at 02:00 with nobody reading the log.

⚠ **THE SWEEP IS IDEMPOTENT PER (RULE, SUBJECT), AND THE GUARANTEE IS A UNIQUE
INDEX RATHER THAN THE CHECK IN THIS FILE.**
`_already_raised()` is a fast path. The guarantee is
`uq_work_order_rule_raises_subject` on `work_order_rule_raises`, because two
beat processes — or a nightly firing overlapping a hand-run from the terminal —
both read *"not raised"* in the same millisecond and both proceed. The unique
constraint refuses the second, this file catches that refusal **inside a
SAVEPOINT**, and the night ends with one job rather than two. A sweep protected
only by the `exists()` call double-raises about once a quarter, at 02:00, with
nothing in the logs.

⚠ **A SAVEPOINT PER SUBJECT, AND HARD-WON LAW 14 IS WHY THIS IS NOT TIDINESS.**
The sweep walks many subjects. One of them is refused — a duplicate raise, a
template someone unpublished at 17:00, a premises whose anchor was deleted. The
obvious shape is `try: … except Exception: continue`, and **on PostgreSQL it
loses the entire night**: once any statement errors inside a transaction the
transaction is aborted, every later query raises `InFailedSqlTransaction`, and
the work is discarded at COMMIT. **The test suite runs on in-memory SQLite,
which has no aborted-transaction state, so the broken version passes every test
on every machine and fails the first time a real row is refused.**
`_raise_one()` therefore opens a nested `transaction.atomic()` — a SAVEPOINT —
around each subject. That is not the tidy option; it is the only one.
`tests/test_us_wrk_037_rules_pg.py` proves it against a real PostgreSQL, because
nothing else can.

⚠ **A RULE THAT IS OFF COSTS NOTHING, NOT EVEN A READ.** `BR-WRK-033`'s second
half is *"a rule that is off raises nothing"*, and the cheap way to honour it is
to read the subjects and then skip. This file filters on `enabled=True` in the
QUERY, indexed by `ix_work_order_rules_enabled` — so a utility that has switched
a noisy rule off does not pay for it every night, and, more importantly, a rule
that is off cannot raise even if a reader has a side effect somebody adds later.

⚠ **WHY THE ORDER IS RAISED THROUGH ONE DOOR AND THEN STAMPED THROUGH ANOTHER.**
`metering_seam.raise_work_order` is metering's own `create_work_order`, and it
accepts `source` and `source_ref` in its payload but **not** `rule_id` or
`priority_id` — neither is a key that door reads. So the rule stamp is applied
immediately afterwards through `metering_seam.save_order_fields`, which is the
same door `apps/work/dispatch.py` uses for wave G's twelve columns. Both
statements are inside the subject's SAVEPOINT, so an order can never exist
without its rule stamp: `BR-WRK-024`'s *"a rule-raised order also stamps the
rule"* is atomic or it is nothing. The alternative — widening metering's
`create_work_order` — would edit a 4,500-line shared service file that other
CR-070 lanes are in tonight (hard-won law 11, mechanism two) to save one line.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone as dt_timezone
from typing import Any, Callable

from django.db import IntegrityError, transaction

from core import audit as core_audit
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from apps.work import models as work_models
from apps.work import promise, rule_processes
from apps.work.seams import (
    assets_seam,
    billing_seam,
    customers_seam,
    metering_seam,
    notifications_seam,
    payments_seam,
)

logger = logging.getLogger("smartbillhub.work.rules")

#: The job kind, declared here beside its body — `core/jobs.py`'s contract, the
#: same one `push.py` follows: a kind whose queue is declared in another file is
#: a kind somebody renames in one place.
RULES_SWEEP_JOB = "work.rules_sweep"

#: The named broker queue. The CONSUMER half is `celery-work` (`-Q work`) in
#: `docker-compose.yml` and shipped with wave J; `G109` checks the pair.
WORK_QUEUE = "work"

#: The beat entry's name and the celery task behind it. The PRODUCT HAS NEVER
#: HAD A NIGHTLY JOB OF ITS OWN before this one — notifications and payments
#: both install their entries from `ready()` rather than from a
#: `CELERY_BEAT_SCHEDULE` settings constant (`config/settings/base.py` declares
#: none, at HEAD or now), and this file follows that precedent rather than
#: minting a second mechanism.
BEAT_ENTRY = "work.rules_sweep"
SWEEP_TASK = "work.rules_sweep.all"

#: 02:00 local, expressed as seconds because the two existing installers express
#: their schedules that way and a mixed vocabulary in `app.conf.beat_schedule`
#: is how an entry gets read as the wrong unit. Nightly.
SWEEP_EVERY_SECONDS = 24 * 60 * 60

#: The audit action a rule-raised order writes. Hard rule 7 — and the row is
#: what makes *Raised by* checkable against something other than the screen.
ACTION_RULE_RAISED = "work.order.raised_by_rule"

WorkOrderRule = work_models.WorkOrderRule
WorkOrderRuleRaise = work_models.WorkOrderRuleRaise
WorkOrderRuleTrigger = work_models.WorkOrderRuleTrigger


# ── The readers — one per OVERNIGHT process ─────────────────────────────────
#
# Each returns a list of SUBJECTS: `{"kind", "key", "anchor", "detail"}`.
#   kind    what the rule fired on, as a word a supervisor can read
#   key     the source module's own id for that row, as text (never joined)
#   anchor  the payload fragment `raise_work_order` needs — BR-WRK-006 wants at
#           least one of connection_id / premises_id / account_id / asset_id
#   detail  what went in the audit row, so *why did this job appear* has an
#           answer that is not "a rule ran"
#
# ⚠ **AN ASSET SUBJECT IS `asset` WHICHEVER PROCESS FOUND IT** (`CR-168-BRC10`
# P3.65): two triggers on one rule — *past its certification* and *flow that
# never stops* — finding the same meter must be ONE subject, or the rule would
# raise twice. Wave M wrote `meter` for the continuous-flow reader; no memory
# row was ever written under it (`DEF-WRK-4096`: that reader never raised), so
# nothing is forgotten by the rename.


def _subjects_payments(params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payments_seam.expired_final_notices(
        grace_days=int(params.get("grace_days", 2) or 0)
    )
    return [
        {
            "kind": "account",
            "key": row["account_id"],
            "anchor": {"account_id": row["account_id"]},
            "detail": {"notice_on": row.get("notice_on"), "tier": row.get("tier")},
        }
        for row in rows
    ]


def _subjects_billing(params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = billing_seam.unresolved_breaks(retryable=bool(params.get("retryable", False)))
    return [
        {
            "kind": "account",
            "key": row["account_id"],
            "anchor": {"account_id": row["account_id"]},
            "detail": {"stage": row.get("stage"), "reason": row.get("reason")},
        }
        for row in rows
    ]


def _subjects_assets(params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = assets_seam.assets_past_certification(
        asset_type_ids=list(params.get("asset_type_ids") or []) or None
    )
    return [
        {
            "kind": "asset",
            "key": row["id"],
            "anchor": {"asset_id": row["id"]},
            "detail": {
                "asset_no": row.get("asset_no"),
                "certification_due": row.get("certification_due"),
            },
        }
        for row in rows
    ]


def _subjects_due_soon(params: dict[str, Any]) -> list[dict[str, Any]]:
    """`compliance_calendar` (P3.32) — the certification date READ AHEAD.

    The memory is keyed on the asset AND its due date, so the rule fires once
    per certification: a backflow preventer tested this October is due again
    next October, and that is a new subject rather than one already raised.
    """
    days = params.get("days_ahead")
    if not days:
        return []
    rows = assets_seam.assets_due_within(
        days_ahead=int(days),
        asset_type_ids=list(params.get("asset_type_ids") or []) or None,
    )
    return [
        {
            "kind": "asset_due",
            "key": f"{row['id']}@{row['certification_due']}",
            "anchor": {"asset_id": row["id"]},
            "detail": {
                "asset_no": row.get("asset_no"),
                "certification_due": row.get("certification_due"),
            },
        }
        for row in rows
    ]


def _subjects_reads(params: dict[str, Any]) -> list[dict[str, Any]]:
    """`high_usage_alert` — one service, one unit (P3.33, `DEF-WRK-4097`)."""
    rows = metering_seam.meters_in_continuous_flow(
        consecutive_reads=int(params.get("consecutive_reads", 3) or 1),
        minimum_consumption=str(params.get("minimum_consumption", "0") or "0"),
        service_code=params.get("service") or None,
        unit=params.get("unit") or None,
    )
    return [
        {
            "kind": "asset",
            "key": row["asset_id"],
            "anchor": {"asset_id": row["asset_id"]},
            "detail": {
                "reads": row.get("reads"),
                "latest_consumption": row.get("latest_consumption"),
                "unit": row.get("unit"),
            },
        }
        for row in rows
    ]


def _subjects_estimate_limit(params: dict[str, Any]) -> list[dict[str, Any]]:
    """`meter_read` (P3.32) — `BR-MET-027`'s forced visit, at Meter-read
    settings' own limit. Keyed per RUN of estimates (see the seam)."""
    rows = metering_seam.meters_at_estimate_limit()
    return [
        {
            "kind": "estimate_run",
            "key": f"{row['asset_id']}@{row['run_ends']}",
            "anchor": {"asset_id": row["asset_id"]},
            "detail": {"estimates": row.get("estimates"), "run_ends": row.get("run_ends")},
        }
        for row in rows
    ]


#: One reader per OVERNIGHT process, keyed by the process key — which IS the
#: label the job reads (`rule_processes`, `DEF-WRK-4096`). A test asserts this
#: map and `rule_processes.OVERNIGHT_KEYS` are the same set: an overnight
#: process with no reader is a rule that saves and never fires.
PROCESS_READERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    "dunning_auto": _subjects_payments,
    "billing_exception": _subjects_billing,
    "asset_age_rule": _subjects_assets,
    "compliance_calendar": _subjects_due_soon,
    "high_usage_alert": _subjects_reads,
    "meter_read": _subjects_estimate_limit,
}

#: ⚠ KEPT FOR ONE ROUND, KEYED BY WAVE M's TRIGGER NAMES, because the builder
#: on screen until lane RULES lands still validates against it. The four
#: overnight ones point at the same readers; `occupancy_completed` is a SCREEN
#: moment now (ruling 10) and has no overnight reader — its rule pre-selects
#: the visit on the move-in screen instead (`from_flows.propose`).
TRIGGER_READERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    legacy: PROCESS_READERS.get(key, lambda _params: [])
    for legacy, key in rule_processes.LEGACY_TRIGGERS.items()
}


def triggers_of(rule: Any) -> list[dict[str, Any]]:
    """A rule's triggers, in order — `{seq, kind, params}`, `kind` a PROCESS KEY.

    From `work_order_rule_triggers` (P3.65) when the rule has rows there; else
    from the wave M columns, which a rule saved before round 5 still carries
    alone. A legacy trigger name is read as the process it always meant.
    """
    rows = list(
        WorkOrderRuleTrigger.objects.filter(tenant_id=rule.tenant_id, rule_id=rule.id).order_by(
            "seq", "created_at"
        )
    )
    if rows:
        return [
            {
                "seq": row.seq,
                "kind": rule_processes.process_key(row.kind) or row.kind,
                "params": dict(row.params or {}),
            }
            for row in rows
        ]
    return [
        {
            "seq": 1,
            "kind": rule_processes.process_key(rule.trigger_kind) or rule.trigger_kind,
            "params": dict(rule.params or {}),
        }
    ]


def _read_subjects(rule: Any, trigger: dict[str, Any]) -> list[dict[str, Any]]:
    """The subjects ONE trigger of this rule fires on tonight, or an empty list.

    A screen moment or a retry has no overnight reader and answers nothing
    here BY DESIGN (ruling 10): its rule acts on the clerk's screen or on the
    retry, never at 02:00. A reader that raises is LOGGED AND SKIPPED: one
    module having a bad night must not stop the other rules raising.
    """
    reader = PROCESS_READERS.get(trigger["kind"])
    if reader is None:
        if rule_processes.process(trigger["kind"]) is None:
            logger.warning(
                "work rule %r names trigger %r, which is no process — it raises "
                "nothing. This is a rule that will never fire, not a transient.",
                rule.name,
                trigger["kind"],
            )
        return []
    try:
        return reader(dict(trigger.get("params") or {}))
    except Exception:  # noqa: BLE001 — see the docstring
        logger.exception(
            "the trigger reader for work rule %r failed; that rule raised "
            "nothing tonight and the others are unaffected.",
            rule.name,
        )
        return []


def subjects_tonight(rule: Any) -> list[dict[str, Any]]:
    """Every subject the rule's overnight triggers find, de-duplicated across
    triggers by (kind, key), each carrying the process that found it FIRST —
    which is the label its job reads. Two triggers on one meter: one subject,
    one job (P3.65: *"two triggers hitting the same meter on the same night
    still raise ONE job"*)."""
    return _subjects_of(rule, triggers_of(rule))


def _subjects_of(rule: Any, triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`subjects_tonight`'s body, for a saved rule OR the builder's unsaved
    probe — ONE de-duplication, so the Review and the sweep count the same
    subjects (`DEF-WRK-9661`: the preview de-duplicated by (kind, key) only and
    would count one meter twice where the sweep counts it once)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for trigger in triggers:
        for subject in _read_subjects(rule, trigger):
            ident = (subject["kind"], str(subject["key"]))
            asset = (subject.get("anchor") or {}).get("asset_id")
            if ident in seen or (asset and ("asset", str(asset)) in seen):
                continue
            seen.add(ident)
            if asset:
                seen.add(("asset", str(asset)))
            out.append({**subject, "process": trigger["kind"]})
    return out


# ── The raise ───────────────────────────────────────────────────────────────


def _already_raised(rule: Any, subject: dict[str, Any]) -> bool:
    """The FAST PATH, not the guarantee — see the module docstring."""
    return WorkOrderRuleRaise.objects.filter(
        tenant_id=rule.tenant_id,
        rule_id=rule.id,
        subject_kind=subject["kind"],
        subject_key=str(subject["key"]),
    ).exists()


#: What `_raise_one` answers when the template is already open on the subject
#: (P3.38). Not None — the sweep counts it apart from a refusal.
ALREADY_OPEN = "already_open"

#: What `_raise_one` answers when the raise REFUSED the subject — a template
#: unpublished since the rule was saved, or metering's own refusal (an asset the
#: template does not apply to, `DEF-WRK-9661`). Counted by the sweep as
#: `refused`, apart from a raise the unique index declined as already made.
REFUSED = "refused"


def _cannot_raise(template: dict[str, Any] | None, subject: dict[str, Any]) -> str | None:
    """Why the raise WOULD refuse this subject, or None — READ ONLY.

    The same two questions `_raise_one` and metering's raise ask, asked before
    anything is written, so *Tonight it raises N jobs* is the number the sweep
    raises (`DEF-WRK-9661`). The reason is the raise's own `message_key` (or
    `not_found` for a subject that has gone)."""
    if template is None or not template.get("active") or int(template.get("version") or 0) < 1:
        return "work.order.template_not_published"
    return metering_seam.raise_refusal(template["id"], subject.get("anchor") or {})


def _raise_one(actor: Any, rule: Any, subject: dict[str, Any]) -> Any:
    """One subject, inside its own SAVEPOINT. Returns the order, None, or
    `ALREADY_OPEN`.

    ⚠ **THE `atomic()` HERE IS THE POINT OF THE FUNCTION** (hard-won law 14).
    Everything this does — the raise, the rule stamp, the memory row, the
    assignment and the audit row — is one unit: an order without its memory
    row would be raised again tomorrow, and a memory row without its order
    would suppress a job that never existed. Either all happen or none does.

    ⚠ **THE SOURCE IS THE PROCESS'S OWN LABEL** (`DEF-WRK-4096`). It stamped
    `rule.source_module` until round 5 — `payments`, `billing`, `reads`,
    `accounts` — and the order table refuses all four, so four of five
    triggers raised nothing for a month and the sweep reported a healthy zero.
    """
    template = metering_seam.template(rule.template_id)
    if template is None or not template.get("active") or int(template.get("version") or 0) < 1:
        # `BR-WRK-012`/`BR-WRK-016` — a deactivated or draft template raises
        # nothing. Logged rather than raised: a supervisor unpublishing a
        # template at 17:00 must not stop the other rules at 02:00.
        logger.warning(
            "work rule %r points at a template that is not published; it "
            "raised nothing for subject %s.",
            rule.name,
            subject["key"],
        )
        return REFUSED

    # P3.38 — one subject, one open job per template, whoever raised the
    # first (a clerk at the asset's door, a move-in screen, another rule). A
    # READ before the savepoint: it changes nothing and refuses nothing.
    if metering_seam.open_order_for_template(template["id"], subject["anchor"]) is not None:
        return ALREADY_OPEN

    pending: list[Any] = []
    try:
        with transaction.atomic():
            order = metering_seam.raise_work_order(
                actor,
                {
                    **subject["anchor"],
                    "type": template["name"],
                    "scope": template["scope"],
                    "service": (template["service"] or {}).get("code"),
                    "template_id": template["id"],
                    "is_gate": template["is_gate"],
                    # `BR-WRK-024` — WHY this order exists, in the order
                    # table's own vocabulary: the PROCESS that found the
                    # subject (`dunning_auto`, `asset_age_rule`, …).
                    "source": subject["process"],
                    # The rule's NAME, not its id — `Work-007` prints this
                    # after *Raised by:* and B14 rule 31 forbids an internal id
                    # being the visible value of a field.
                    "source_ref": rule.name,
                },
            )

            # The rule stamp and the priority: two columns `create_work_order`
            # does not read from its payload. Same door `dispatch.py` uses.
            row = metering_seam.work_order_row(order["id"])
            fields = ["rule_id"]
            row.rule_id = rule.id
            if rule.priority_id:
                row.priority_id = rule.priority_id
                fields.append("priority_id")
                # `BR-WRK-018` — a priority IS a promise; the due date moves
                # with it, measured from the raise (`dispatch.change_priority`'s
                # rule, applied at birth).
                hours = promise.hours_for_job(
                    getattr(row.type_ref, "sla_hours", None) if row.type_ref_id else None,
                    getattr(rule.priority, "sla_hours", None) if rule.priority_id else None,
                )
                if hours and row.created_at is not None:
                    from datetime import timedelta

                    row.due_at = row.created_at + timedelta(hours=int(hours))
                    fields.append("due_at")
            metering_seam.save_order_fields(row, fields)

            # THE MEMORY. Written in the same unit as the order — see above.
            WorkOrderRuleRaise.objects.create(
                tenant_id=rule.tenant_id,
                rule_id=rule.id,
                subject_kind=subject["kind"],
                subject_key=str(subject["key"]),
                work_order_id=order["id"],
            )

            # P3.36 — step 2 (*Give the job to*) is READ, inside the unit.
            assigned = assign_by_rule(actor, rule, order["id"], pending=pending)

            core_audit.write_row(
                action=ACTION_RULE_RAISED,
                entity_type="work_order",
                entity_id=order["id"],
                after={
                    "rule": rule.name,
                    "source_module": rule_processes.module_of(subject["process"]),
                    "process": subject["process"],
                    "subject_kind": subject["kind"],
                    "subject_key": str(subject["key"]),
                    "assigned": assigned,
                    "detail": subject.get("detail") or {},
                },
            )
    except IntegrityError:
        # THE GUARANTEE FIRING. Another process raised this subject between our
        # `_already_raised` check and this INSERT. The SAVEPOINT this sits
        # inside is what makes the rest of the sweep survive it on PostgreSQL —
        # without it every later statement in the night raises
        # `InFailedSqlTransaction` and the whole run is discarded at COMMIT.
        logger.info(
            "work rule %r had already raised for %s %s — the unique index "
            "refused the second raise, which is the sweep being idempotent.",
            rule.name,
            subject["kind"],
            subject["key"],
        )
        return None
    except Exception:  # noqa: BLE001 — one bad subject must not end the night
        logger.exception(
            "work rule %r could not raise for %s %s; the sweep continues.",
            rule.name,
            subject["kind"],
            subject["key"],
        )
        return REFUSED
    # The technician's push — AFTER the savepoint, so the broker is never
    # handed a job row the database has not committed (`dispatch.record_act`).
    _push_pending(actor, pending)
    return order


def _push_pending(actor: Any, pending: list[Any]) -> None:
    from apps.work import dispatch

    for row, order, act, technician in pending:
        try:
            dispatch.push_after_assign(row, order, act, technician, actor)
        except Exception:  # noqa: BLE001 — a push is a consequence, never the act
            logger.exception("the push for a rule-assigned job could not be queued")


#: P3.36 — what *Give the job to* may say. `nobody` is the default and leaves
#: the job in the queue, which is what every rule did before round 5.
ASSIGN_KINDS: tuple[str, ...] = ("nobody", "area", "skill", "technician", "crew")


def assign_by_rule(
    actor: Any, rule: Any, order_id: Any, *, pending: list[Any] | None = None
) -> dict[str, Any] | None:
    """Step 2 of the builder, READ (P3.36) — the job arrives assigned as the
    rule says, or unassigned with the reason.

    * `technician` / `crew` — that holder, named on the rule.
    * `skill` — the matcher's best fit for the template's skill, as ADVICE
      (ruling 2: *"a guideline, never a block"*); the same `best_fit` flag the
      assign screen draws.
    * `area` — *whoever covers the area*: the best candidate already working
      in the job's area that day (`advice.area_match`). Nobody covering it
      leaves the job unassigned and says so; nothing is guessed.
    * `nobody` — unassigned.

    Runs inside the caller's savepoint; the push is the caller's after commit.
    """
    from apps.work import advice, dispatch

    spec = dict(rule.assignment or {})
    kind = str(spec.get("kind") or "nobody")
    if kind not in ASSIGN_KINDS or kind == "nobody":
        return None
    order = metering_seam.work_order_row(order_id)
    payload: dict[str, Any] | None = None
    if kind == "technician" and spec.get("id"):
        payload = {"technician_id": spec["id"]}
    elif kind == "crew" and spec.get("id"):
        payload = {"crew_id": spec["id"]}
    elif kind in ("skill", "area"):
        template = metering_seam.template(order.template_id) if order.template_id else None
        skill_id = ((template or {}).get("skill") or {}).get("id")
        on = advice.order_day(order)
        area_id = advice.order_area_id(order)
        page = advice.candidates_page(skill_id=skill_id, area_id=area_id, on=on, per=200)
        rows = page["rows"]
        if kind == "skill":
            chosen = next((r for r in rows if r["best_fit"]), None)
        else:
            chosen = next(
                (r for r in rows if r["advice"]["area_match"] and not r["advice"]["off_that_day"]),
                None,
            )
        if chosen is not None:
            payload = (
                {"technician_id": chosen["id"]}
                if chosen["kind"] == "person"
                else {"crew_id": chosen["id"]}
            )
    if payload is None:
        return {"kind": kind, "assigned": False}
    answer = dispatch.record_act(
        actor, order_id, {"act": "assign", **payload}, push=False, pending=pending
    )
    return {"kind": kind, "assigned": True, "to": (answer.get("technician") or {}).get("name")}


def sweep(actor: Any = None, *, rule_ids: list[Any] | None = None) -> dict[str, Any]:
    """Run every ENABLED rule of the tenant in context. The nightly body.

    Returns what it did, per rule, so the terminal and the job record both say
    something a person can read. Running it twice on the same night is the case
    `US-WRK-037` TC-1 asserts: the second run raises nothing.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        # CLAUDE.md hard rule 1. A sweep with no tenant would read nothing under
        # RLS anyway; saying so is better than reporting a successful run that
        # touched nothing.
        raise RuntimeError("work.rules_sweep ran with no app.tenant_id set")

    rules = WorkOrderRule.objects.filter(tenant_id=tenant_id, enabled=True).select_related(
        "priority"
    )
    if rule_ids:
        rules = rules.filter(pk__in=list(rule_ids))

    per_rule: list[dict[str, Any]] = []
    raised_total = 0
    for rule in rules.order_by("name"):
        subjects = subjects_tonight(rule)
        raised: list[str] = []
        already_open = 0
        refused = 0
        for subject in subjects:
            if _already_raised(rule, subject):
                continue
            order = _raise_one(actor, rule, subject)
            if order is ALREADY_OPEN:
                already_open += 1
            elif order is REFUSED:
                # `DEF-WRK-9661` — counted, never swallowed: the Review's
                # *cannot be raised* is this number, asked in advance.
                refused += 1
            elif order is not None:
                raised.append(order["order_no"])
        raised_total += len(raised)
        per_rule.append(
            {
                "rule_id": str(rule.id),
                "rule": rule.name,
                "source_module": rule.source_module,
                "subjects": len(subjects),
                "raised": len(raised),
                "already_open": already_open,
                "refused": refused,
                "orders": raised,
            }
        )

    return {"rules": per_rule, "raised": raised_total, "tenant_id": str(tenant_id)}


# ── The job, its queue, and the beat entry ──────────────────────────────────


def run_rules_sweep_job(record: dict[str, Any]) -> dict[str, Any]:
    """The job body. `core.jobs` hands it the record it saved."""
    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    with core_tenancy.tenant_context(tenant_id):
        return sweep(payload.get("actor_user_id"))


def scope_key(tenant_id: Any, when: date | None = None) -> str:
    """One sweep per tenant per DATE.

    `core.jobs.enqueue` folds a re-enqueue with a live scope key into the
    existing record (NFR-16), so a beat firing twice in one night — a restart,
    a duplicated schedule — becomes one job rather than two. The DATE is in the
    key because tomorrow's sweep is a different piece of work.
    """
    day = (when or datetime.now(dt_timezone.utc).date()).isoformat()
    return f"{tenant_id}:{RULES_SWEEP_JOB}:{day}"


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted in a
    test without starting celery — the schedule being CORRECT and the schedule
    being INSTALLED are two different claims, and hard-won law 2 is about
    exactly that gap. `apps/notifications/schedule.py` says the same in its own
    words; this is deliberately the same shape.
    """
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(
                every_seconds if every_seconds is not None else SWEEP_EVERY_SECONDS
            ),
            "args": (),
            "options": {"expires": None},
        }
    }


def sweep_all_tenants() -> dict[str, Any]:
    """ONE firing: enqueue a sweep for every live utility.

    A FAN-OUT and not a loop of sweeps, for the reason notifications gives for
    its own: one utility's slow night must not delay another's. Each tenant gets
    its own job row on the `work` queue, and `scope_key` makes a second firing
    on the same date fold into the first.
    """
    from importlib import import_module

    try:
        selectors = import_module("apps.tenancy.selectors")
        listed = selectors.live_tenant_subdomains()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception(
            "the live-utility read could not be made, so tonight's rules sweep "
            "paced nobody. Nothing is lost — rules raise on the next firing."
        )
        return {"tenants": 0, "queued": []}

    queued: list[str] = []
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        # `core.jobs.enqueue` takes the tenant from CONTEXT and refuses when
        # there is none (B3: jobs are per-tenant), so the fan-out enters each
        # utility's context to enqueue its own sweep rather than passing an id.
        with core_tenancy.tenant_context(tenant_id):
            record = core_jobs.enqueue(
                RULES_SWEEP_JOB,
                scope_key=scope_key(tenant_id),
                payload={"tenant_id": str(tenant_id)},
            )
        queued.append(str(record["id"]))
    return {"tenants": len(queued), "queued": queued}


#: Bound by `install()`. Kept because `app.task(...)(fn)` returns a NEW object
#: and leaves the module-level name bound to the plain function, which has no
#: `.delay` — the trap `apps/notifications/schedule.py` records in full.
_SWEEP_ALL_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the fan-out task. Idempotent.

    Called from `WorkConfig.ready()`. Returns what it did, so a caller and a
    test can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem. A failure to
    import celery is NOT an error: `manage.py check`, a migration and the test
    suite all run without a broker, and a Django app that refused to start
    because a scheduler is absent would be a worse product than one whose rules
    fire a little later.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the work rules-sweep schedule was not installed: celery is "
                "not available here (%s). Nothing is broken — the sweep still "
                "runs when enqueued.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    global _SWEEP_ALL_TASK
    _SWEEP_ALL_TASK = app.task(name=SWEEP_TASK, bind=False)(sweep_all_tenants)

    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


def register() -> None:
    """Register the body AND the queue. Called from `WorkConfig.ready`.

    Both, in one function, in the module that owns the work — `core/jobs.py`'s
    contract and `push.py`'s precedent. A kind registered in one file and routed
    in another keeps its old queue after a rename, silently.
    """
    core_jobs.set_job_handler(RULES_SWEEP_JOB, run_rules_sweep_job)
    core_jobs.set_job_queue(RULES_SWEEP_JOB, WORK_QUEUE)


# ── The screen's side: CRUD and the list `Work-026` draws ───────────────────
#
# These live HERE rather than in `apps/work/services.py` and
# `apps/work/selectors.py` for the reason `rules_models.py` gives for not being
# the end of `models.py`: those two files are 685 and 1,306 lines with other
# CR-070 lanes editing them tonight, and a pathspec commit takes the WHOLE
# working-tree content of every path it names (hard-won law 11, mechanism two).
# `api.py` imports this module by name.


#: P3.57 / P3.67 — the seven escalations a rule may add (ruling 34). A stalled
#: job is told ONCE per kind (`work_order_rule_escalation_fires`).
ESCALATION_KINDS: tuple[str, ...] = (
    "unassigned",
    "not_accepted",
    "running_late",
    "overdue",
    "on_hold_too_long",
    "failed",
    "not_approved",
)

#: P3.66 — *When* and *Who hears* on a rule's notification rows. Served by
#: `processes()` so the form draws them from the server, never a literal.
NOTIFY_WHEN: tuple[str, ...] = ("raised", "assigned", "on_the_way", "done")
NOTIFY_WHO: tuple[str, ...] = ("customer", "whoever_acted", "system_admins")
ALSO_TELL_KINDS: tuple[str, ...] = ("role", "user")


def _refuse(message_key: str, *, code: str | None = None, **params: Any) -> None:
    from core import errors

    raise errors.ValidationError(
        code or errors.VAL_UNKNOWN_LOOKUP,
        message_key=message_key,
        br_ref="BR-WRK-033",
        params=params or None,
    )


def _clean_trigger(raw: Any, seq: int) -> dict[str, Any]:
    """One trigger row, validated against its PROCESS's own settings (P3.30).

    The module is DERIVED from the process and never sent, so the form cannot
    compose the pair the wave M save refused (`triggerNotOfSource`).
    """
    from core import errors

    data = dict(raw or {}) if isinstance(raw, dict) else {}
    found = rule_processes.process(data.get("kind"))
    if found is None:
        _refuse("work.rules.trigger_unknown", trigger=str(data.get("kind") or ""))
    params_in = dict(data.get("params") or {})
    params: dict[str, Any] = {}
    for param in found.params:
        if param.kind == rule_processes.PARAM_SETTING:
            # Read-only — another screen's figure, never stored on the rule.
            continue
        value = params_in.get(param.name, None)
        if value in (None, "", []):
            if param.required:
                _refuse(
                    "work.rules.param_required",
                    code=errors.VAL_REQUIRED,
                    param=param.name,
                    trigger=found.key,
                )
            if param.default not in (None, []):
                params[param.name] = param.default
            continue
        if param.kind == rule_processes.PARAM_INT:
            try:
                number = int(str(value))
            except (TypeError, ValueError):
                _refuse("work.rules.param_invalid", code=errors.VAL_FORMAT, param=param.name)
            if param.minimum is not None and number < param.minimum:
                _refuse("work.rules.param_invalid", code=errors.VAL_RANGE, param=param.name)
            params[param.name] = number
        elif param.kind == rule_processes.PARAM_BOOL:
            params[param.name] = bool(value)
        elif param.kind == rule_processes.PARAM_QUANTITY:
            from decimal import Decimal, InvalidOperation

            try:
                amount = Decimal(str(value))
            except (InvalidOperation, ValueError):
                _refuse("work.rules.param_invalid", code=errors.VAL_FORMAT, param=param.name)
            if amount < 0:
                _refuse("work.rules.param_invalid", code=errors.VAL_RANGE, param=param.name)
            params[param.name] = str(amount)
        elif param.kind == rule_processes.PARAM_SERVICE:
            from apps.work.seams import tenancy_seam

            code = str(value).strip()
            if code not in tenancy_seam.enabled_service_codes():
                _refuse("work.rules.param_invalid", param=param.name, service=code)
            params[param.name] = code
        elif param.kind == rule_processes.PARAM_UNIT:
            params[param.name] = str(value).strip()
        elif param.kind == rule_processes.PARAM_ASSET_TYPES:
            params[param.name] = [str(item) for item in (value or [])]
        elif param.kind == rule_processes.PARAM_CHOICE:
            # `BR-WRK-067` — a value off the served list is a rule that never
            # fires; refused at save, never stored to wait for a match.
            choice = str(value).strip()
            if choice not in param.options:
                _refuse(
                    "work.rules.param_invalid",
                    code=errors.VAL_UNKNOWN_LOOKUP,
                    param=param.name,
                )
            params[param.name] = choice
    return {"seq": seq, "kind": found.key, "params": params}


def _clean_escalations(raw: Any) -> list[dict[str, Any]]:
    from core import errors

    out: list[dict[str, Any]] = []
    for row in raw or []:
        data = dict(row or {}) if isinstance(row, dict) else {}
        kind = str(data.get("kind") or "")
        if kind not in ESCALATION_KINDS:
            _refuse("work.rules.escalation_unknown", escalation=kind)
        try:
            hours = int(str(data.get("after_hours")))
        except (TypeError, ValueError):
            _refuse("work.rules.param_invalid", code=errors.VAL_FORMAT, param="after_hours")
        if hours < 1:
            _refuse("work.rules.param_invalid", code=errors.VAL_RANGE, param="after_hours")
        also: list[dict[str, Any]] = []
        for person in data.get("also_tell") or []:
            entry = dict(person or {}) if isinstance(person, dict) else {}
            if entry.get("kind") not in ALSO_TELL_KINDS or not entry.get("id"):
                _refuse("work.rules.also_tell_unknown")
            also.append({"kind": entry["kind"], "id": str(entry["id"])})
        message = data.get("event_key") or None
        if message is not None and message not in notifications_seam.event_keys():
            _refuse("work.rules.message_unknown", message=str(message))
        out.append({"kind": kind, "after_hours": hours, "also_tell": also, "event_key": message})
    return out


def _clean_notifications(raw: Any) -> list[dict[str, Any]]:
    keys = set(notifications_seam.event_keys())
    out: list[dict[str, Any]] = []
    for row in raw or []:
        data = dict(row or {}) if isinstance(row, dict) else {}
        key = str(data.get("event_key") or "")
        # `BR-NOT-017` — a catalogue KEY, never text; one home for the words.
        if key not in keys:
            _refuse("work.rules.message_unknown", message=key)
        when = data.get("when") or None
        who = data.get("who") or None
        if when is not None and when not in NOTIFY_WHEN:
            _refuse("work.rules.notify_row_invalid", when=str(when))
        if who is not None and who not in NOTIFY_WHO:
            _refuse("work.rules.notify_row_invalid", who=str(who))
        out.append({"event_key": key, "when": when, "who": who})
    return out


def _clean_rule(payload: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Validate a rule at SAVE time, not at sweep time.

    Two shapes are accepted, for one round: the round-5 shape — `triggers[]`
    of process keys (P3.65), `assign_to`, `notifications[]`, `escalations[]` —
    and wave M's single `source_module` + `trigger_kind`, which the builder on
    screen sends until lane RULES lands. Both are written as trigger rows.

    ⚠ **AN UNKNOWN TRIGGER IS REFUSED HERE RATHER THAN IGNORED AT 02:00.** A
    rule whose trigger has no process saves happily, sits on `Work-026` looking
    exactly like a working rule, shows THIS MONTH 0 for ever, and gives nobody
    a reason. Refusing at the door is the only place a person is present.
    """
    from core import errors

    cleaned: dict[str, Any] = {}
    data = dict(payload or {})

    if "reminders" in data:
        # Ruling 34: *"if reminders can be managed in notifications then
        # remove"* — they live on Settings → Notifications (P3.59).
        _refuse("work.rules.reminders_live_in_notifications", code=errors.VAL_FORMAT)

    if not partial or "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            raise errors.ValidationError(
                errors.VAL_REQUIRED, message_key="work.rules.nameRequired", br_ref="BR-WRK-033"
            )
        cleaned["name"] = name

    triggers: list[dict[str, Any]] | None = None
    if "triggers" in data:
        raw = data.get("triggers") or []
        if not raw:
            _refuse("work.rules.trigger_required", code=errors.VAL_REQUIRED)
        triggers = [_clean_trigger(row, n) for n, row in enumerate(raw, start=1)]
    elif not partial or "trigger_kind" in data or "source_module" in data:
        # ── wave M's shape (the builder on screen until lane RULES lands) ──
        trigger = str(data.get("trigger_kind") or "").strip()
        if trigger not in TRIGGER_READERS:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.rules.triggerUnknown",
                br_ref="BR-WRK-033",
                params={"trigger": trigger},
            )
        module = str(data.get("source_module") or "").strip()
        if module not in WorkOrderRule.SOURCE_MODULES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.rules.sourceUnknown",
                br_ref="BR-WRK-033",
                params={"source": module},
            )
        # The pair must agree. A rule claiming the assets module with a
        # payments trigger would read one module and be reported under another.
        if WorkOrderRule.TRIGGER_MODULE.get(trigger) != module:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.rules.triggerNotOfSource",
                br_ref="BR-WRK-033",
                params={"trigger": trigger, "source": module},
            )
        triggers = [
            _clean_trigger(
                {"kind": rule_processes.process_key(trigger), "params": dict(data.get("params") or {})},
                1,
            )
        ]
    if triggers is not None:
        first = triggers[0]
        process = rule_processes.BY_KEY[first["kind"]]
        cleaned["_triggers"] = triggers
        # The wave M columns stay lawful containers, filled from the FIRST
        # trigger so a screen still reading them is truthful about it.
        cleaned["trigger_kind"] = process.legacy_trigger or process.key
        cleaned["source_module"] = process.module
        cleaned["params"] = dict(first["params"])

    if not partial or "template_id" in data:
        template_id = data.get("template_id")
        if not template_id:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.rules.templateRequired",
                br_ref="BR-WRK-033",
            )
        if metering_seam.template(template_id) is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        cleaned["template_id"] = template_id

    if "assign_to" in data:
        spec = dict(data.get("assign_to") or {})
        kind = str(spec.get("kind") or "nobody")
        if kind not in ASSIGN_KINDS:
            _refuse("work.rules.assign_invalid", assign=kind)
        if kind in ("technician", "crew") and not spec.get("id"):
            _refuse("work.rules.assign_invalid", code=errors.VAL_REQUIRED)
        cleaned["assignment"] = {"kind": kind, **({"id": str(spec["id"])} if spec.get("id") else {})}
    elif "assignment" in data:
        cleaned["assignment"] = dict(data.get("assignment") or {})

    if "escalations" in data:
        cleaned["escalation"] = _clean_escalations(data.get("escalations"))
    elif "escalation" in data:
        cleaned["escalation"] = dict(data.get("escalation") or {})

    if "notifications" in data:
        raw = data.get("notifications")
        cleaned["notifications"] = (
            _clean_notifications(raw) if isinstance(raw, list) else dict(raw or {})
        )

    if "priority_id" in data:
        cleaned["priority_id"] = data.get("priority_id") or None
    if "enabled" in data:
        cleaned["enabled"] = bool(data.get("enabled"))
    return cleaned


def _write_triggers(rule_row: Any, triggers: list[dict[str, Any]]) -> None:
    """Replace a rule's trigger rows. A rule is not a financial row and is
    editable (`update_rule`'s docstring); the jobs it raised keep their stamps."""
    WorkOrderRuleTrigger.objects.filter(tenant_id=rule_row.tenant_id, rule_id=rule_row.id).delete()
    WorkOrderRuleTrigger.objects.bulk_create(
        [
            WorkOrderRuleTrigger(
                tenant_id=rule_row.tenant_id,
                rule_id=rule_row.id,
                seq=row["seq"],
                kind=row["kind"],
                params=row["params"],
            )
            for row in triggers
        ]
    )


def _escalations_of(row: Any) -> list[dict[str, Any]]:
    """The rule's escalation ROWS (P3.67), with each *Also tell* named. A wave
    M rule carries a dict here (one *Escalate after* box nothing read) and
    answers an empty list: that box never fired, and saying it did would be a
    claim nobody kept."""
    from apps.work.seams import identity_seam

    stored = row.escalation
    if not isinstance(stored, list):
        return []
    user_ids = [p["id"] for e in stored for p in e.get("also_tell") or [] if p.get("kind") == "user"]
    names = identity_seam.user_names(user_ids) if user_ids else {}
    out = []
    for entry in stored:
        out.append(
            {
                "kind": entry.get("kind"),
                "after_hours": entry.get("after_hours"),
                "event_key": entry.get("event_key"),
                "also_tell": [
                    {
                        "kind": person.get("kind"),
                        "id": person.get("id"),
                        "name": names.get(str(person.get("id")))
                        if person.get("kind") == "user"
                        else None,
                    }
                    for person in entry.get("also_tell") or []
                ],
            }
        )
    return out


def rule_dict(
    row: Any,
    *,
    this_month: int | None = None,
    jobs_raised: int | None = None,
    last_fired_at: Any = None,
    counted: bool = False,
) -> dict[str, Any]:
    """One rule as `Work-026` and image 62 draw it.

    ⚠ **NO DATABASE ID IS THE VISIBLE VALUE OF ANY FIELD** (B14 rule 31). `id`
    is here because the screen needs an address to PATCH, and every column the
    table RENDERS is a name, a word or a count.

    P3.61: `last_fired_at` (the newest job it raised, or null — *Never* is the
    finding) and `jobs_raised` (all time) beside `this_month`, all counted from
    `work_order_rule_raises`, the memory that outlives the order.
    """
    template = metering_seam.template(row.template_id)
    if not counted:
        counts = _counts(row)
        this_month, jobs_raised, last_fired_at = counts
    triggers = triggers_of(row)
    incomplete: list[dict[str, Any]] = []
    for trigger in triggers:
        found = rule_processes.process(trigger["kind"])
        trigger["module"] = found.module if found else None
        trigger["moment"] = found.moment if found else None
        # A rule saved before round 5 can lack a setting its process now
        # requires (a wave M leak rule has no service, `DEF-WRK-4097`). It
        # raises nothing until it is set, and the rule SAYS so rather than
        # reading *On* over a trigger that cannot fire (law 2's mirror).
        for param in found.params if found else ():
            if param.required and trigger["params"].get(param.name) in (None, "", []):
                incomplete.append({"seq": trigger["seq"], "param": param.name})
    notifications = row.notifications if isinstance(row.notifications, list) else []
    return {
        "id": str(row.id),
        "name": row.name,
        "source_module": row.source_module,
        "trigger_kind": row.trigger_kind,
        "params": dict(row.params or {}),
        "triggers": triggers,
        "template": {
            "id": str(row.template_id),
            "name": (template or {}).get("name"),
        },
        "priority": (
            {"id": str(row.priority_id), "name": row.priority.name} if row.priority_id else None
        ),
        "assignment": dict(row.assignment or {}),
        "assign_to": {"kind": (row.assignment or {}).get("kind") or "nobody",
                      "id": (row.assignment or {}).get("id")},
        "notifications": notifications,
        "escalation": row.escalation if isinstance(row.escalation, dict) else {},
        "escalations": _escalations_of(row),
        "enabled": bool(row.enabled),
        "incomplete": incomplete,
        "this_month": int(this_month or 0),
        "jobs_raised": int(jobs_raised or 0),
        "last_fired_at": last_fired_at.isoformat() if last_fired_at else None,
    }


def _month_start() -> Any:
    from datetime import datetime as _dt

    today = date.today()
    return _dt(today.year, today.month, 1, tzinfo=dt_timezone.utc)


def _counts(rule_row: Any) -> tuple[int, int, Any]:
    """(this month, all time, last fired) for one rule — from the memory."""
    from django.db.models import Count, Max, Q

    agg = WorkOrderRuleRaise.objects.filter(
        tenant_id=rule_row.tenant_id, rule_id=rule_row.id
    ).aggregate(
        this_month=Count("id", filter=Q(raised_at__gte=_month_start())),
        total=Count("id"),
        last=Max("raised_at"),
    )
    return agg["this_month"], agg["total"], agg["last"]


def _this_month_count(rule: Any) -> int:
    """`Work-026`'s THIS MONTH column — orders this rule raised since the 1st,
    counted from the memory (it outlives the order)."""
    return _counts(rule)[0]


def rules_page(*, page: Any = 1, per: Any = 50, q: str | None = None) -> dict[str, Any]:
    """`GET /work/rules` — the list, enabled first, then by name; the three
    counts annotated in ONE query (P3.61), and `q` searching the rule's name,
    its template's name and its triggers' process keys (P3.60's server half:
    *a search that searches*)."""
    import math

    from django.db.models import Count, Max, Q

    from core.pagination import clamp_page_size

    qs = WorkOrderRule.objects.filter(tenant_id=core_tenancy.current_tenant_id())
    text = (q or "").strip()
    if text:
        matching_processes = [
            p.key for p in rule_processes.PROCESSES if text.lower() in p.label.lower()
        ]
        template_ids = [
            t.id for t in metering_seam.templates_queryset().filter(name__icontains=text)
        ]
        qs = qs.filter(
            Q(name__icontains=text)
            | Q(template_id__in=template_ids)
            | Q(trigger_rows__kind__in=matching_processes)
            | Q(trigger_kind__in=[
                legacy for legacy, key in rule_processes.LEGACY_TRIGGERS.items()
                if key in matching_processes
            ])
        ).distinct()
    qs = (
        qs.select_related("priority")
        .annotate(
            n_month=Count("raises", filter=Q(raises__raised_at__gte=_month_start()), distinct=True),
            n_total=Count("raises", distinct=True),
            n_last=Max("raises__raised_at"),
        )
        .order_by("-enabled", "name", "id")
    )
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    return {
        "rows": [
            rule_dict(
                row,
                this_month=row.n_month,
                jobs_raised=row.n_total,
                last_fired_at=row.n_last,
                counted=True,
            )
            for row in qs[start : start + size]
        ],
        "page": number,
        "per": size,
        "total": total,
        "pages": last,
    }


def rule(rule_id: Any) -> Any:
    """One rule of the tenant in context, or a 404-shaped refusal.

    A cross-tenant id reads as *not found* and never as *forbidden* — the same
    answer every other read in this module gives, so a caller cannot learn that
    another utility's rule exists (`BR-TEN-003`).
    """
    from core import errors

    row = (
        WorkOrderRule.objects.filter(tenant_id=core_tenancy.current_tenant_id(), pk=rule_id)
        .select_related("priority")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def rule_detail(rule_id: Any) -> dict[str, Any]:
    """`GET /work/rules/{id}` — image 62: the rule, plus *Tonight it would
    raise N jobs* (P3.39's server half: the same read the sweep makes, writing
    nothing)."""
    row = rule(rule_id)
    out = rule_dict(row)
    out["tonight"] = tonight(row)
    return out


def tonight(row: Any) -> dict[str, Any]:
    """What the sweep WOULD raise for this rule tonight — subjects found, less
    those it already raised, those whose template is already open on them, and
    those the raise would REFUSE (`DEF-WRK-9661`). READ ONLY: no row is
    written, so the Review can state it before Activate (B14 rule 11)."""
    saved = getattr(row, "id", None) is not None
    template = metering_seam.template(row.template_id) if row.template_id else None
    return _count_tonight(row, subjects_tonight(row), template, remembered=saved)


def _count_tonight(
    rule: Any, subjects: list[dict[str, Any]], template: dict[str, Any] | None, *, remembered: bool
) -> dict[str, Any]:
    """⚠ **ONE COUNT FOR THE REVIEW, THE OVERVIEW AND THE SWEEP'S PROMISE
    (`DEF-WRK-9661`).** The Review read *Tonight it raises 4 jobs* and the sweep
    raised 3: a subject the raise refused was counted. Each subject now goes
    through the questions the sweep itself asks, in its order — already raised
    (a saved rule's memory), already open, then would the raise refuse it — and
    a refused subject is counted APART, with its reason, never as a job."""
    would = 0
    already_open = 0
    reasons: dict[str, int] = {}
    for subject in subjects:
        if remembered and _already_raised(rule, subject):
            continue
        if template and metering_seam.open_order_for_template(template["id"], subject["anchor"]):
            already_open += 1
            continue
        reason = _cannot_raise(template, subject)
        if reason is not None:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        would += 1
    return {
        "subjects": len(subjects),
        "would_raise": would,
        "already_open": already_open,
        "cannot_raise": sum(reasons.values()),
        "cannot_raise_reasons": reasons,
    }


def preview(payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/rules/preview {triggers[], template_id}` — the builder's
    Review: *Tonight it raises 47 jobs. Nothing is written yet.* (image 61).
    Validates exactly as a save does and writes NOTHING."""
    cleaned = _clean_rule({"name": "preview", **dict(payload or {})})
    probe = WorkOrderRule(
        tenant_id=core_tenancy.current_tenant_id(),
        name="preview",
        template_id=cleaned["template_id"],
        trigger_kind=cleaned["trigger_kind"],
        params=cleaned["params"],
    )
    subjects = _subjects_of(probe, cleaned["_triggers"])
    template = metering_seam.template(cleaned["template_id"])
    return _count_tonight(probe, subjects, template, remembered=False)


def processes() -> dict[str, Any]:
    """`GET /work/rules/processes` — the processes ONCE (P3.30), with the
    read-only settings they show (the estimate limit) and the vocabularies of
    the Notify step (P3.66/P3.67), so the form types no literal."""
    return {
        "results": [process.as_wire() for process in rule_processes.PROCESSES],
        "settings": {"est_max_consecutive": metering_seam.estimate_limit()},
        "assign_kinds": list(ASSIGN_KINDS),
        "escalation_kinds": list(ESCALATION_KINDS),
        "notify_when": list(NOTIFY_WHEN),
        "notify_who": list(NOTIFY_WHO),
        "also_tell_kinds": list(ALSO_TELL_KINDS),
        # Lane RULES: the message each escalation kind sends, so the form
        # shows it rather than typing a second copy of the mapping.
        "escalation_events": notifications_seam.escalation_events(),
    }


def rule_jobs_page(rule_id: Any, *, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/rules/{id}/jobs` — image 63: *Every job this rule has
    raised*, newest first, paged in SQL. Each row is the dispatcher's own row
    (order, premise, raised, state, outcome)."""
    import math

    from apps.work import dispatch
    from core.pagination import clamp_page_size

    row = rule(rule_id)
    qs = metering_seam.orders_raised_by_rule_queryset(row.id)
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    from apps.work import workforce

    target = workforce.default_target()
    default_hours = target["hours"] if target else None
    return {
        "rows": [dispatch._dispatch_row(order, default_hours) for order in qs[start : start + size]],
        "page": number,
        "per": size,
        "total": total,
    }


#: The rule's own audit actions, as WORDS (image 64).
_RULE_ACTS = {
    "work.rule.created": "created",
    "work.rule.updated": "edited",
    "work.rule.enabled": "turned_on",
    "work.rule.disabled": "turned_off",
}


def rule_audit_page(rule_id: Any, *, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/rules/{id}/audit` — image 64: who changed the rule, when and
    what, newest first, paged in SQL; names, never ids."""
    import math

    from apps.work.seams import audit_seam, identity_seam
    from core.pagination import clamp_page_size

    row = rule(rule_id)
    qs = audit_seam.entity_trail_queryset("work_order_rule", row.id).order_by("-created_at", "-id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    entries = list(qs[start : start + size])
    names = identity_seam.user_names([e.actor_user_id for e in entries if e.actor_user_id])
    return {
        "rows": [
            {
                "at": entry.created_at.isoformat() if entry.created_at else None,
                "by": {"name": names.get(str(entry.actor_user_id)) if entry.actor_user_id else None},
                "act": _RULE_ACTS.get(entry.action, entry.action),
                "before": entry.before or {},
                "after": entry.after or {},
            }
            for entry in entries
        ],
        "page": number,
        "per": size,
        "total": total,
    }


def create_rule(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """The builder's last step, *Activate rule* — `POST /work/rules`.

    Hard rule 7: a rule is a standing instruction to raise work, so creating
    one writes an audit row naming what it will do.
    """
    cleaned = _clean_rule(dict(payload or {}))
    triggers = cleaned.pop("_triggers")
    tenant_id = core_tenancy.current_tenant_id()
    with transaction.atomic():
        row = WorkOrderRule.objects.create(
            tenant_id=tenant_id,
            created_by=getattr(actor, "id", None),
            **cleaned,
        )
        _write_triggers(row, triggers)
        core_audit.write_row(
            action="work.rule.created",
            entity_type="work_order_rule",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None),
            after={
                "name": row.name,
                "triggers": [t["kind"] for t in triggers],
                "enabled": row.enabled,
            },
        )
    return rule_dict(rule(row.id))


def update_rule(actor: Any, rule_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PATCH /work/rules/{id}` — edit a rule in place.

    ⚠ **A RULE IS NOT A FINANCIAL ROW AND IS EDITABLE**, unlike almost
    everything else this module writes. Hard rule 4 names invoices, invoice
    lines, payments and journal entries and reaches none of this. The orders it
    ALREADY RAISED keep their own `source`, `source_ref` and `rule_id` stamps,
    so renaming a rule cannot rewrite the history of what it did — the
    `locked-at-issue` posture, one table along.
    """
    row = rule(rule_id)
    cleaned = _clean_rule(dict(payload or {}), partial=True)
    triggers = cleaned.pop("_triggers", None)
    before = {
        "name": row.name,
        "triggers": [t["kind"] for t in triggers_of(row)],
        "enabled": row.enabled,
    }
    with transaction.atomic():
        for key, value in cleaned.items():
            setattr(row, key, value)
        if cleaned:
            row.save(update_fields=[*cleaned.keys(), "updated_at"])
        if triggers is not None:
            _write_triggers(row, triggers)
        core_audit.write_row(
            action="work.rule.updated",
            entity_type="work_order_rule",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None),
            before=before,
            after={
                "name": row.name,
                "triggers": [t["kind"] for t in triggers_of(row)],
                "enabled": row.enabled,
            },
        )
    return rule_dict(rule(row.id))


def set_rule_enabled(actor: Any, rule_id: Any, enabled: bool) -> dict[str, Any]:
    """`POST /work/rules/{id}/enable` · `.../disable` — `BR-WRK-033`.

    ⚠ **SWITCHING A RULE OFF DOES NOT ERASE ITS MEMORY.** The rows in
    `work_order_rule_raises` stay exactly as they are, so a rule turned off in
    December and on again in March does not re-raise every subject it has ever
    seen on the first night back. That is the difference between a switch and a
    delete, and it is the reason `enabled` is a column rather than a deletion.
    """
    row = rule(rule_id)
    was = bool(row.enabled)
    if was != bool(enabled):
        row.enabled = bool(enabled)
        row.save(update_fields=["enabled", "updated_at"])
    core_audit.write_row(
        action="work.rule.enabled" if enabled else "work.rule.disabled",
        entity_type="work_order_rule",
        entity_id=row.id,
        actor_user_id=getattr(actor, "id", None),
        before={"enabled": was},
        after={"enabled": bool(enabled)},
    )
    return rule_dict(row)


def preselection(process_key: str) -> list[dict[str, Any]]:
    """P3.34 — what ENABLED rules on a SCREEN moment pre-select: `[{rule {id,
    name}, template_id, priority_id, assign_to}]`. READ ONLY.

    `BR-WRK-055` keeps *No visit needed* a recorded choice, so a rule on a
    moment a clerk stands in never raises by itself: the screen shows the
    rule's job TICKED with the rule's name, the clerk may untick it, and
    `from_flows.raise_for` applies the rule's priority and assignee to what is
    raised. Rules saved with the wave M trigger name (`occupancy_completed`)
    count as the move-in moment they always meant.
    """
    key = rule_processes.process_key(process_key)
    if key not in rule_processes.SCREEN_KEYS and key != "failed_outcome":
        return []
    out: list[dict[str, Any]] = []
    tenant_id = core_tenancy.current_tenant_id()
    legacy = [k for k, v in rule_processes.LEGACY_TRIGGERS.items() if v == key]
    candidates = (
        WorkOrderRule.objects.filter(tenant_id=tenant_id, enabled=True)
        .filter(
            models_Q(trigger_rows__kind=key)
            | models_Q(trigger_rows__kind__in=legacy)
            | (models_Q(trigger_rows__isnull=True) & models_Q(trigger_kind__in=[key, *legacy]))
        )
        .select_related("priority")
        .distinct()
        .order_by("name")
    )
    for row in candidates:
        out.append(
            {
                "rule": {"id": str(row.id), "name": row.name},
                "template_id": str(row.template_id),
                "priority_id": str(row.priority_id) if row.priority_id else None,
                "assign_to": dict(row.assignment or {}),
            }
        )
    return out


def shape_by_rule(actor: Any, order_id: Any, process_key: str, template_id: Any) -> dict[str, Any] | None:
    """Apply the FIRST enabled rule on `process_key` naming `template_id` to a
    job a screen or the retry just raised: its priority (and the due date that
    goes with it) and its assignee. P3.34 (a ticked screen job) and P3.35 (a
    failed job's retry — *never a second job*). Runs in the caller's
    transaction; returns what it applied, or None when no rule names the
    template."""
    from datetime import timedelta

    for spec in preselection(process_key):
        if str(spec["template_id"]) != str(template_id):
            continue
        row = WorkOrderRule.objects.select_related("priority").get(pk=spec["rule"]["id"])
        order = metering_seam.work_order_row(order_id)
        fields = ["rule_id"]
        order.rule_id = row.id
        if row.priority_id:
            order.priority_id = row.priority_id
            fields.append("priority_id")
            hours = promise.hours_for_job(
                getattr(order.type_ref, "sla_hours", None) if order.type_ref_id else None,
                getattr(row.priority, "sla_hours", None),
            )
            if hours and order.created_at is not None:
                order.due_at = order.created_at + timedelta(hours=int(hours))
                fields.append("due_at")
        metering_seam.save_order_fields(order, fields)
        pending: list[Any] = []
        assigned = assign_by_rule(actor, row, order_id, pending=pending)
        core_audit.write_row(
            action="work.order.shaped_by_rule",
            entity_type="work_order",
            entity_id=order_id,
            actor_user_id=getattr(actor, "id", None),
            after={"rule": row.name, "process": process_key, "assigned": assigned},
        )
        return {"rule": spec["rule"], "assigned": assigned, "pending": pending}
    return None


from django.db.models import Q as models_Q  # noqa: E402 — used by `preselection`


__all__ = [
    "ACTION_RULE_RAISED",
    "ALREADY_OPEN",
    "ESCALATION_KINDS",
    "PROCESS_READERS",
    "assign_by_rule",
    "create_rule",
    "preselection",
    "preview",
    "processes",
    "rule",
    "rule_audit_page",
    "rule_detail",
    "rule_dict",
    "rule_jobs_page",
    "rules_page",
    "set_rule_enabled",
    "shape_by_rule",
    "subjects_tonight",
    "tonight",
    "triggers_of",
    "update_rule",
    "BEAT_ENTRY",
    "RULES_SWEEP_JOB",
    "SWEEP_TASK",
    "TRIGGER_READERS",
    "WORK_QUEUE",
    "beat_schedule",
    "install",
    "register",
    "run_rules_sweep_job",
    "scope_key",
    "sweep",
    "sweep_all_tenants",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-037@d1b76486 (EP-WRK-07) · 10-execution-plan.md wave M task M1
# generated: 2026-09-05 by the CR-070 wave M build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(work/0019_rls_force_rules is the 🔒 path; review-ledger row is M6)
# gates: pytest tests/test_us_wrk_037_rules.py · tests/test_us_wrk_037_rules_pg.py on PostgreSQL · G78 · G109
# exceptions: `rule_id`/`priority_id` are stamped through `save_order_fields` rather than through `create_work_order`'s payload — that door does not read either key, and widening a 4,500-line shared service file to save one line is hard-won law 11 mechanism two (see the module docstring)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
