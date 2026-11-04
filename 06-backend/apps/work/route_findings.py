# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane FINDINGS — a route finding on the server: stored
#           when the reads door receives it, turned into a job by a matching
#           Work rule at once, else by a person (the reader on the phone, or
#           the office from *From the field → Route findings*).
# Rules:    BR-WRK-067 (PO 2026-10-22, verbatim *"if a rule is set work order
#           will get created , if not user can create the work order"*) ·
#           BR-MET-1202 (the capture position is evidence, never an address) ·
#           BR-WRK-033 / BR-WRK-024 (a rule-raised job stamps its rule and its
#           process's label) · BR-WRK-006 (a job stands on an anchor) ·
#           BR-WRK-008 (the template is copied, its version stamped) ·
#           BR-WRK-018 (a priority is a promise: the due date moves with it) ·
#           CLAUDE.md hard rules 1, 6, 7 · hard-won law 14 (a SAVEPOINT per
#           raise — a refused raise must not lose the finding on PostgreSQL)
# Tests:    06-backend/tests/test_cr187_route_findings.py ·
#           06-backend/tests/test_cr187_route_findings_pg.py
# Impacts:  apps/metering/field_reads.py (kind `finding` calls `receive` by
#           name) · apps/work/route_findings_api.py · work_route_findings
# ───────────────────────────────────────────────────────
"""A finding reaches the server, and a job follows — by rule, else by hand.

THE WORKED CASE THE PO WAS SHOWN (decision log 2026-10-22, *"TWO PO RULINGS"*)
────────────────────────────────────────────────────────────────────────────
Brazos has a rule *Leak → Leak repair, Same day*. Dana reports a leak at stop
14; the reads door hands the finding here, the rule matches, and WO-4870
*Leak repair · Same day* exists before the sync answers — the answer names it,
so her phone shows *WO-4870*. Brazos has no rule for *Broken seal*: Dana's
broken-seal finding is stored OPEN with its photographs and position, and both
her phone and the office's *Route findings* list offer *Create work order*.

ONE FINDING, ONE JOB — AND THE GUARANTEE IS AN UPDATE, NOT A READ
────────────────────────────────────────────────────────────────────────────
`_convert` raises the job and then moves the finding with
`UPDATE … SET status = 'work_order_created' WHERE id = … AND status = 'open'`,
both inside ONE savepoint. Two people pressing *Create work order* at the same
moment: on PostgreSQL the second UPDATE waits on the first's row lock, then
matches nothing, and its savepoint rolls its job back — `WO-` number and all.
The `status` read before it is the fast path for the common case (the second
press long after the first); the conditional UPDATE is what holds under a race.

⚠ **THE RULE'S RAISE CANNOT LOSE THE FINDING** (hard-won law 14). The finding
is inserted first, in the reads door's item savepoint; the raise runs in a
NESTED savepoint. A template unpublished at 17:00, an asset the template does
not apply to, metering refusing the anchor — each rolls back the raise only,
the finding stays `open`, and a person creates the job by hand. On SQLite that
is invisible; `tests/test_cr187_route_findings_pg.py` proves it.

WHICH RULE, WHEN TWO MATCH
────────────────────────────────────────────────────────────────────────────
The first ENABLED rule by name whose trigger is `route_finding` for this
finding's kind. One finding converts once (BR-WRK-067's *"a work order"*), so a
second matching rule does not raise a second job. A judgment, not a ruling —
recorded here and in the lane report.

⚠ **AN OPEN JOB ON THE SAME METER FROM THE SAME TEMPLATE IS JOINED, NOT
DOUBLED** — for a RULE (`P3.38`, *"one subject, one open job per template,
whoever raised the first"*): three readers each reporting the leak at stop 14
link to the one leak repair already open. A person creating one BY HAND is
making that choice deliberately and gets a new job.

WHAT IT DOES NOT DO
────────────────────────────────────────────────────────────────────────────
* **The reader's urgency sets nothing.** RW-21's *Now · This week · Routine*
  is stored as said; a rule's priority, or the one a person picks, is the
  job's. Which priority *Now* means is not ruled.
* **The office cannot see the photographs' bytes here.** They are route
  photos (`metering.field_read_photos`), held on that row; no office read of
  them exists yet. The list shows how many there are.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.work import mobile
from apps.work import models as work_models
from apps.work.route_finding_models import (
    CONVERTED_BY_HAND,
    CONVERTED_BY_READ_FORMAT,
    CONVERTED_BY_RULE,
    FINDING_KINDS,
    FINDING_READ_ANSWER,
    FINDING_OPEN,
    FINDING_STATUSES,
    FINDING_URGENCIES,
    FINDING_WORK_ORDER_CREATED,
    WorkRouteFinding,
)
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

logger = logging.getLogger("smartbillhub.work.route_findings")

#: The process a finding's rule is written on (`rule_processes`), which is
#: also the job's `source` — one string (`DEF-WRK-4096`).
PROCESS_KEY = "route_finding"
#: The rule's setting naming WHICH finding it raises for.
KIND_PARAM = "finding_kind"

ACTION_RECEIVED = "work.finding.received"
ACTION_RAISED = "work.order.raised_from_finding"

NOTE_CHARS = 2000
MAX_PHOTOS = 20


class FindingRefused(Exception):
    """A finding the server will not store, sent BACK to the reader (the reads
    door's posture since 2026-10-21, PO *"back to the technician"*): the
    machine `reason` and its specifics. Nothing is stored."""

    def __init__(self, reason: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _text(value: Any, limit: int) -> str | None:
    text = str(value or "").strip()
    return text[:limit] if text else None


# ══════════════════════════════════════════════════════════════════════════
# What the handset offers (RW-21's lists) and the by-hand form's priorities
# ══════════════════════════════════════════════════════════════════════════
def finding_options() -> dict[str, Any]:
    """`GET work/mobile/findings/options` — the kinds and urgencies RW-21
    offers, in its order, and the tenant's priorities for *Create work order*.
    Words travel as catalogue keys (B14 rule 35): the phone writes them."""
    priorities = work_models.WorkPriority.objects.filter(tenant_id=_tenant_id(), active=True)
    return {
        "kinds": [{"code": kind, "label_key": f"work.findings.kind.{kind}"} for kind in FINDING_KINDS],
        "urgencies": [
            {"code": urgency, "label_key": f"work.findings.urgency.{urgency}"}
            for urgency in FINDING_URGENCIES
        ],
        "priorities": [
            {"id": str(row.id), "code": row.code, "name": row.name, "rank": row.rank}
            for row in priorities.order_by("rank", "name")
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
# Receive — the reads door's kind `finding`
# ══════════════════════════════════════════════════════════════════════════
def receive(
    actor: Any,
    *,
    key: str,
    kind: Any,
    urgency: Any = None,
    note: Any = None,
    note_source: Any = None,
    detail: dict[str, Any] | None = None,
    photo_ids: list[Any] | None = None,
    route_id: Any = None,
    premises_id: Any = None,
    asset_id: Any = None,
    lat: Any = None,
    lng: Any = None,
    accuracy_m: Any = None,
    captured_at: Any = None,
    captor_id: Any = None,
    captor_technician_id: Any = None,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Store one finding and let a matching rule raise its job. Returns
    `(answer, duplicate)`.

    Called by `metering.field_reads._claim` inside the item's savepoint, with
    everything already parsed by that door (position, clock, the meter it
    resolved, the CAPTOR from the item's token). A key already stored answers
    the FIRST finding as it stands now and stores nothing (hard rule 6).
    """
    tenant_id = _tenant_id()
    first = WorkRouteFinding.objects.filter(tenant_id=tenant_id, key=key).first()
    if first is not None:
        return answer(first), True
    kind_text = str(kind or "").strip()
    if kind_text not in FINDING_KINDS:
        raise FindingRefused("finding_kind_unknown", {"kind": kind_text, "allowed": list(FINDING_KINDS)})
    urgency_text = _text(urgency, 20)
    if urgency_text is not None and urgency_text not in FINDING_URGENCIES:
        raise FindingRefused(
            "finding_urgency_unknown", {"urgency": urgency_text, "allowed": list(FINDING_URGENCIES)}
        )
    if not premises_id and not asset_id:
        # BR-WRK-006 — a job needs an anchor, so a finding that names neither
        # the stop nor the meter could never become one. Back to the reader.
        raise FindingRefused("finding_place_unknown")
    try:
        with transaction.atomic():
            row = WorkRouteFinding.objects.create(
                tenant_id=tenant_id,
                key=key,
                kind=kind_text,
                urgency=urgency_text,
                note=_text(note, NOTE_CHARS),
                note_source=_text(note_source, 20),
                detail=dict(detail or {}),
                photo_ids=[str(p)[:120] for p in (photo_ids or [])][:MAX_PHOTOS],
                route_id=route_id,
                premises_id=premises_id,
                asset_id=asset_id,
                lat=lat,
                lng=lng,
                accuracy_m=accuracy_m,
                captured_at=captured_at,
                captor_id=captor_id,
                captor_technician_id=captor_technician_id,
                received_payload=dict(payload or {}),
            )
            core_audit.write_row(
                action=ACTION_RECEIVED,
                entity_type="work_route_finding",
                entity_id=row.id,
                actor_user_id=captor_id or _actor_id(actor),
                after={"kind": kind_text, "urgency": urgency_text, "br_ref": "BR-WRK-067"},
            )
    except IntegrityError:
        # Two copies of one item in flight: the unique key refused the second
        # inside its savepoint, so the rest of the batch survives (law 14).
        first = WorkRouteFinding.objects.filter(tenant_id=tenant_id, key=key).first()
        if first is None:
            raise
        return answer(first), True
    _apply_rule(actor, row)
    row.refresh_from_db()
    return answer(row), False


def stored_finding(key: Any) -> dict[str, Any] | None:
    """The finding stored under this capture key, as it stands now, or None —
    the reads door's duplicate answer for an item whose token has expired."""
    row = _base().filter(key=str(key or "")).first()
    return None if row is None else answer(row)


def matching_rule(kind: str) -> Any | None:
    """The first ENABLED rule, by name, with a `route_finding` trigger for this
    kind — or None. READ ONLY."""
    tenant_id = _tenant_id()
    rule_ids = set(
        str(v)
        for v in work_models.WorkOrderRuleTrigger.objects.filter(
            tenant_id=tenant_id, kind=PROCESS_KEY, params__finding_kind=kind
        ).values_list("rule_id", flat=True)
    )
    rules = work_models.WorkOrderRule.objects.filter(tenant_id=tenant_id, enabled=True).order_by("name")
    for rule in rules.filter(pk__in=rule_ids) if rule_ids else []:
        return rule
    # A rule saved with no trigger rows still carries its first trigger on the
    # wave M columns (`rules.triggers_of`).
    for rule in rules.filter(trigger_kind=PROCESS_KEY):
        if not work_models.WorkOrderRuleTrigger.objects.filter(rule_id=rule.id).exists():
            if str((rule.params or {}).get(KIND_PARAM) or "") == kind:
                return rule
    return None


def _apply_rule(actor: Any, row: WorkRouteFinding) -> None:
    """`BR-WRK-067`'s first half — a matching rule raises the job NOW. Never
    raises: a raise the server refuses leaves the finding open, for a person."""
    rule = matching_rule(row.kind)
    if rule is None:
        return
    template = metering_seam.template(rule.template_id)
    if template is None or not template.get("active") or int(template.get("version") or 0) < 1:
        logger.warning(
            "route-finding rule %r points at a template that is not published; "
            "finding %s stays open for a person.",
            rule.name,
            row.key,
        )
        return
    existing = metering_seam.open_order_for_template(template["id"], _anchor(row))
    try:
        _convert(
            actor,
            row,
            template=template,
            priority_id=rule.priority_id,
            rule=rule,
            join_order_id=(existing or {}).get("id"),
        )
    except Exception:  # noqa: BLE001 — the finding is kept; a person takes it
        logger.exception(
            "route-finding rule %r could not raise for finding %s; it stays open.",
            rule.name,
            row.key,
        )


# ══════════════════════════════════════════════════════════════════════════
# The raise — by rule or by hand, ONE path
# ══════════════════════════════════════════════════════════════════════════
def _anchor(row: WorkRouteFinding) -> dict[str, Any]:
    """The meter when the reader named one, else the stop (BR-WRK-006). Never
    both: metering walks an asset to its own place, and a stop the reader
    stood at is not evidence of which unit a meter serves."""
    if row.asset_id:
        return {"asset_id": str(row.asset_id)}
    return {"premises_id": str(row.premises_id)}


def _source_ref(row: WorkRouteFinding) -> str | None:
    """What `Raised by` quotes — the METER's own number, else the stop's
    premise number. A human number, never a uuid (B14 rule 31)."""
    if row.asset_id and getattr(row.asset, "asset_no", None):
        return row.asset.asset_no
    if row.premises_id and getattr(row.premises, "premise_no", None):
        return row.premises.premise_no
    return None


class _AlreadyConverted(Exception):
    """The conditional UPDATE matched no row: somebody converted it first."""


def _convert(
    actor: Any,
    row: WorkRouteFinding,
    *,
    template: dict[str, Any],
    priority_id: Any,
    rule: Any = None,
    join_order_id: Any = None,
    conversion: str | None = None,
) -> Any:
    """Raise (or join) the job and move the finding, in ONE savepoint. Returns
    the order id; raises `_AlreadyConverted` when another hand got there first
    (its savepoint, job and all, rolled back).

    `conversion` is given only by `raise_for_read_answer` (MQ-033): neither a
    rule nor a person, so no `converted_by` and no rule memory."""
    from apps.work import rules as work_rules

    pending: list[Any] = []
    by_rule = rule is not None
    by_format = conversion == CONVERTED_BY_READ_FORMAT
    with transaction.atomic():
        if join_order_id:
            order_id = join_order_id
        else:
            payload: dict[str, Any] = {
                **_anchor(row),
                "type": template["name"],
                "scope": template["scope"],
                "service": (template.get("service") or {}).get("code"),
                "template_id": template["id"],
                "is_gate": template["is_gate"],
                "source": PROCESS_KEY,
                "source_ref": _source_ref(row),
            }
            if priority_id:
                # `create_work_order` stamps the priority AND the due date it
                # promises (`_resolve_priority`, `_resolve_due_at`).
                payload["priority_id"] = str(priority_id)
            if row.note:
                payload["technician_notes"] = row.note
            created = metering_seam.raise_work_order(actor, payload)
            order_id = created["id"]
            if by_rule:
                order = metering_seam.work_order_row(order_id)
                order.rule_id = rule.id
                metering_seam.save_order_fields(order, ["rule_id"])
        moved = WorkRouteFinding.objects.filter(
            tenant_id=row.tenant_id, pk=row.pk, status=FINDING_OPEN
        ).update(
            status=FINDING_WORK_ORDER_CREATED,
            work_order_id=order_id,
            conversion=(
                CONVERTED_BY_READ_FORMAT
                if by_format
                else CONVERTED_BY_RULE if by_rule else CONVERTED_BY_HAND
            ),
            rule_id=rule.id if by_rule else None,
            converted_by_id=None if (by_rule or by_format) else _actor_id(actor),
            converted_at=timezone.now(),
        )
        if moved != 1:
            raise _AlreadyConverted()
        if by_rule:
            # The rule's memory and its THIS MONTH count (`_counts`) — the same
            # row the sweep writes, keyed on the finding.
            work_models.WorkOrderRuleRaise.objects.create(
                tenant_id=row.tenant_id,
                rule_id=rule.id,
                subject_kind=PROCESS_KEY,
                subject_key=str(row.id),
                work_order_id=order_id,
            )
            if not join_order_id:
                work_rules.assign_by_rule(actor, rule, order_id, pending=pending)
        core_audit.write_row(
            action=work_rules.ACTION_RULE_RAISED if by_rule else ACTION_RAISED,
            entity_type="work_order",
            entity_id=order_id,
            actor_user_id=None if (by_rule or by_format) else _actor_id(actor),
            after={
                "rule": rule.name if by_rule else None,
                "read_format": (row.detail or {}).get("read_format") if by_format else None,
                "process": PROCESS_KEY,
                "finding_kind": row.kind,
                "finding": str(row.id),
                "joined_open_job": bool(join_order_id),
                "br_ref": "BR-WRK-067",
            },
        )
    if pending:
        transaction.on_commit(lambda: work_rules._push_pending(actor, pending))
    return order_id


def _published(template_id: Any) -> dict[str, Any]:
    template = metering_seam.template(template_id) if template_id else None
    if template is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if not template.get("active") or int(template.get("version") or 0) < 1:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-067",
            message_key="work.findings.template_not_published",
            params={"template": template.get("name") or ""},
        )
    return template


def create_work_order(actor: Any, row: WorkRouteFinding, data: Any) -> dict[str, Any]:
    """`BR-WRK-067`'s second half — a person creates the job from an open
    finding: `{template_id, priority_id?}`. Once: a finding already converted
    answers the job it has, `duplicate: true`, and raises nothing."""
    body = data if isinstance(data, dict) else {}
    if row.status != FINDING_OPEN:
        return {**answer(row), "duplicate": True}
    template_id = str(body.get("template_id") or "").strip()
    if not template_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-WRK-067", message_key="work.findings.template_required"
        )
    template = _published(template_id)
    priority_id = body.get("priority_id") or None
    if priority_id and not work_models.WorkPriority.objects.filter(
        tenant_id=row.tenant_id, pk=priority_id
    ).exists():
        raise errors.deny_as_not_found("BR-TEN-003")
    refusal = metering_seam.raise_refusal(template["id"], _anchor(row))
    if refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-067",
            message_key=refusal,
            params={"template": template.get("name") or ""},
        )
    try:
        _convert(actor, row, template=template, priority_id=priority_id)
    except _AlreadyConverted:
        row.refresh_from_db()
        return {**answer(row), "duplicate": True}
    row.refresh_from_db()
    return {**answer(row), "duplicate": False}


# ══════════════════════════════════════════════════════════════════════════
# MQ-033 — a read-format ANSWER raises its job (`CR-192-BRC10`, BR-MET-1217)
# ══════════════════════════════════════════════════════════════════════════
def read_format_template(template_id: Any) -> dict[str, Any] | None:
    """The job TEMPLATE a read-format question may name in `raise_work`, as
    `{id, name, template_no, published, service}`, or None when this tenant
    has no such template. READ ONLY — metering's Settings → Reads validates a
    question's `raise_work` through this (`metering.seams.work_job_template`)
    and never reads Work's tables itself.

    *Published* is the test `_published` applies to a by-hand raise: active
    and at version 1 or later. A job's TYPE is its template's (`BR-WRK-008`),
    which is why the utility's *"utility-chosen type"* is a template here.
    """
    try:
        template = metering_seam.template(template_id) if template_id else None
    except Exception:  # noqa: BLE001 — a malformed id is simply not a template
        return None
    if template is None:
        return None
    return {
        "id": template["id"],
        "name": template["name"],
        "template_no": template.get("template_no"),
        "published": bool(template.get("active")) and int(template.get("version") or 0) >= 1,
        "service": (template.get("service") or {}).get("code"),
    }


def raise_for_read_answer(
    actor: Any,
    *,
    key: str,
    template_id: Any,
    route_id: Any = None,
    premises_id: Any = None,
    asset_id: Any = None,
    captor_id: Any = None,
    captured_at: Any = None,
    lat: Any = None,
    lng: Any = None,
    accuracy_m: Any = None,
    detail: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """MQ-033 — a reader's ANSWER matched its question's `raise_work`, so ONE
    job of the utility's chosen template is raised, linked back to the reading.
    Returns `(finding answer, duplicate)`.

    PO, verbatim (2026-10-24, *"this is correct"* to the summary): *"raise a
    work order (an answer raises a job of a utility-chosen type, linked back
    to the reading)"*. It goes through the SAME path a route finding's rule
    takes (`BR-WRK-067`, `_convert`): a finding of kind `read_answer` is
    stored, then converted in a nested savepoint. So:

    * **idempotent on reading + question** — `key` is
      `read-answer:<field reading key>:<question key>` and the finding's
      unique `(tenant, key)` is the guarantee; a resend answers the first;
    * **linked back** — `detail` carries the reading's key, its
      `meter_read_id`, the format, version and question, and the answer;
    * **a refused raise keeps the finding** (law 14) — an unpublished
      template, an asset the template does not apply to: the finding stays
      OPEN and a person creates the job from *Route findings*, exactly as for
      a rule (`_apply_rule`);
    * **one open job per template per subject** (`P3.38`) — joined, not
      doubled, as a rule's raise is.

    Called by `metering.read_formats` inside its own savepoint. Never raises
    for a refused raise; raises `FindingRefused` only when the finding could
    never become a job (no anchor — `BR-WRK-006`).
    """
    tenant_id = _tenant_id()
    first = WorkRouteFinding.objects.filter(tenant_id=tenant_id, key=key).first()
    if first is not None:
        return answer(first), True
    if not premises_id and not asset_id:
        raise FindingRefused("finding_place_unknown")
    try:
        with transaction.atomic():
            row = WorkRouteFinding.objects.create(
                tenant_id=tenant_id,
                key=key,
                kind=FINDING_READ_ANSWER,
                detail=dict(detail or {}),
                route_id=route_id,
                premises_id=premises_id,
                asset_id=asset_id,
                lat=lat,
                lng=lng,
                accuracy_m=accuracy_m,
                captured_at=captured_at,
                captor_id=captor_id,
            )
            core_audit.write_row(
                action=ACTION_RECEIVED,
                entity_type="work_route_finding",
                entity_id=row.id,
                actor_user_id=captor_id or _actor_id(actor),
                after={"kind": FINDING_READ_ANSWER, "br_ref": "BR-MET-1217"},
            )
    except IntegrityError:
        first = WorkRouteFinding.objects.filter(tenant_id=tenant_id, key=key).first()
        if first is None:
            raise
        return answer(first), True
    template = metering_seam.template(template_id) if template_id else None
    if template is None or not template.get("active") or int(template.get("version") or 0) < 1:
        logger.warning(
            "read-format answer names a template that is not published; finding %s stays open.",
            key,
        )
    else:
        existing = metering_seam.open_order_for_template(template["id"], _anchor(row))
        try:
            _convert(
                actor,
                row,
                template=template,
                priority_id=None,
                join_order_id=(existing or {}).get("id"),
                conversion=CONVERTED_BY_READ_FORMAT,
            )
        except Exception:  # noqa: BLE001 — the finding is kept; a person takes it
            logger.exception("read-format answer %s could not raise; it stays open.", key)
    row.refresh_from_db()
    return answer(row), False


# ══════════════════════════════════════════════════════════════════════════
# Reads — the office list, one finding, the reader's own
# ══════════════════════════════════════════════════════════════════════════
def _base() -> Any:
    return WorkRouteFinding.objects.filter(tenant_id=_tenant_id()).select_related(
        "route", "premises", "asset", "captor", "work_order", "rule", "converted_by"
    )


def _decimal(value: Any) -> str | None:
    return None if value is None else f"{value}"


def answer(row: WorkRouteFinding) -> dict[str, Any]:
    """One finding as every surface reads it. `id` is an ADDRESS; every value a
    screen draws is a word, a number a clerk quotes or a count (B14 rule 31).
    `capture_point` is where the PHONE was — never the property (BR-MET-1202)."""
    order = row.work_order if row.work_order_id else None
    premises = row.premises if row.premises_id else None
    return {
        "id": str(row.id),
        "key": row.key,
        "kind": row.kind,
        "urgency": row.urgency,
        "note": row.note,
        "status": row.status,
        "conversion": row.conversion,
        "rule": row.rule.name if row.rule_id else None,
        "work_order": (
            {"id": str(order.id), "order_no": order.order_no} if order is not None else None
        ),
        "meter_no": row.asset.asset_no if row.asset_id else None,
        "stop": (
            {"premise_no": premises.premise_no, "address": premises.address_line}
            if premises is not None
            else None
        ),
        "route": (row.route.code if row.route_id else None),
        "technician": (
            (getattr(row.captor, "full_name", None) or None) if row.captor_id else None
        ),
        "photographs": len(row.photo_ids or []),
        "capture_point": (
            {
                "lat": _decimal(row.lat),
                "lng": _decimal(row.lng),
                "accuracy_m": _decimal(row.accuracy_m),
            }
            if row.lat is not None and row.lng is not None
            else None
        ),
        "detail": row.detail or {},
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "converted_by": (
            (getattr(row.converted_by, "full_name", None) or None) if row.converted_by_id else None
        ),
        "converted_at": row.converted_at.isoformat() if row.converted_at else None,
    }


def office_page(*, status: Any = None, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """`GET /work/route-findings?status=open|work_order_created|all` — newest
    first, paged with no cap (NFR-3). Default `open`: that is the work.
    `counts` is over every status, never the page."""
    base = _base()
    counts = {status_word: 0 for status_word in FINDING_STATUSES}
    for item in base.order_by().values("status").annotate(n=Count("id")):
        counts[item["status"]] = int(item["n"])
    wanted = str(status or FINDING_OPEN).strip().lower()
    if wanted != "all":
        if wanted not in FINDING_STATUSES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.findings.status_unknown",
                params={"status": wanted, "allowed": ", ".join((*FINDING_STATUSES, "all"))},
            )
        base = base.filter(status=wanted)
    qs = base.order_by("-received_at", "-id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = min(max(int(str(page)), 1), last)
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    rows = [answer(row) for row in qs[start : start + size]]
    return {"rows": rows, "page": number, "per": size, "total": total, "counts": counts}


def office_finding(finding_id: Any) -> WorkRouteFinding:
    row = _base().filter(pk=finding_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def office_create(actor: Any, finding_id: Any, data: Any) -> dict[str, Any]:
    """`POST /work/route-findings/{id}/work-order` — the office's *Create work
    order…*. The office roles that raise jobs (`WorkOrdersReadAnyWriteAdmin
    OrClerk` at the edge) make this call."""
    with transaction.atomic():
        return create_work_order(actor, office_finding(finding_id), data)


def _own(actor: Any, key: Any) -> WorkRouteFinding:
    """The caller's OWN finding by its capture key — a technician reads and
    converts only what they captured (`07-endpoints.md` §0 rule 10: 404,
    never 403). A login with no technician profile has none."""
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.NotFoundError()
    row = _base().filter(key=str(key or "")).first()
    if row is None:
        raise errors.NotFoundError()
    mine = (row.captor_technician_id and row.captor_technician_id == technician.id) or (
        row.captor_id and str(row.captor_id) == str(_actor_id(actor))
    )
    if not mine:
        raise errors.NotFoundError()
    return row


def mobile_finding(actor: Any, key: Any) -> dict[str, Any]:
    """`GET /work/mobile/findings/{key}` — the reader's own finding now."""
    return answer(_own(actor, key))


def mobile_create(actor: Any, key: Any, data: Any) -> dict[str, Any]:
    """`POST /work/mobile/findings/{key}/work-order` — *Create work order* on
    the reader's phone, for a finding no rule took. Online only."""
    with transaction.atomic():
        return create_work_order(actor, _own(actor, key), data)


__all__ = [
    "FindingRefused",
    "answer",
    "create_work_order",
    "finding_options",
    "matching_rule",
    "mobile_create",
    "mobile_finding",
    "office_create",
    "office_page",
    "receive",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 lane FINDINGS — BR-WRK-067 (decision log 2026-10-22 "TWO PO RULINGS" (2))
# generated: 2026-10-22 by lane FINDINGS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(the RLS and migration files are 🔒; ledger row owed by the coordinator)
# gates: G78 · G85 · pytest tests/test_cr187_route_findings*.py (SQLite and PostgreSQL 16)
# exceptions: which rule wins when two match (first by name) and joining an open job are judgments, reported
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
