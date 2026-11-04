# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13 task T-36, lane S-ORDER — partial and failed
#           outcomes end to end: carried through the order, the cost (the
#           invoice path) and the office queue.
# Rules:    BR-FLD-00004 (R4 — four outcomes: Passed · Partly done · Failed ·
#           Waiting on someone; Failed is the work failing, Waiting is being
#           blocked by a person, a part or access) · BR-WRK-023 (`outcome` is
#           its own axis) · BR-WRK-054 (a FAILED outcome raises a follow-up at
#           Accept — metering's chain, unchanged) · BR-WRK-050/051 (the report
#           and its cost lines, generated at Accept) · BR-WRK-004 / OQ-WRK-1491
#           (a job's cost is captured and POSTED NOWHERE) · hard rule 1
# Tests:    06-backend/tests/test_cr187_order_outcomes.py
# Impacts:  apps/work/field_orders_api.py (two reads) · the native app's FF-34/FF-35
#           and the office acceptance queue (Walkthrough §4)
# ───────────────────────────────────────────────────────
"""The four outcomes, read back out of a closed job — for the office.

WHAT THE CLOSE ALREADY CARRIES, AND WHY NOTHING ON THE CLOSE PATH CHANGES
------------------------------------------------------------------------
The close is `submit_field_result` (metering), reached from the phone through
`sync._apply_close`. It already stores the OUTCOME token (`work_orders.outcome`,
`ck_work_orders_outcome`) and the whole `field_data` the phone sends, merged.
R4's four words are four of the five tokens metering already has:

    Passed            → passed
    Partly done       → partially_done
    Failed            → failed
    Waiting on someone→ waiting_on_someone_else

(`cancelled` is the fifth token and is not an outcome a technician closes
with — R4 names four. The close path does not refuse it today; that is
`sync.py`'s door and is reported as a gap rather than changed from this lane.)

So the field app's contract for the REASON rides in `field_data`, at the TOP
level, under keys the server already reads:

    field_data.reason   — the sentence (*Meter seized*, *Customer not home*).
                          `_failure_reason` in metering reads `reason` FIRST
                          after `failure_reason`, so a Failed job's reason is
                          what lands in the build's *Waiting on* at Accept with
                          no change to metering (`BR-WRK-054`).
    field_data.blocker  — Waiting on someone only: `person` · `part` ·
                          `access` (R4's own three words).

⚠ **NOTHING IS REFUSED FOR A MISSING REASON, DELIBERATELY.** Rule 1 of
`07-endpoints.md` §0: an older handset (and the web field app, which stays
live) closes with an outcome and no reason, and must keep working. The office
read below says `reason_missing: true` instead — a blank the office can SEE,
rather than a close the technician cannot make.

WHAT THE OFFICE SEES (E2E-04, -05, -06)
---------------------------------------
* **Partly done** — *which steps remain*: the order's own copied task rows
  (`work_order_tasks`) with no tick, in their `seq` order, plus done / total.
* **Failed** — the reason and how many photographs the job carries (*closed
  Failed with a photograph*).
* **Waiting on someone** — the blocker named, and `is_failure: false`: *"a
  blocked job is not a failure and does not read as one in the office."*

THE COST — WHICH IS THE WHOLE OF "THE INVOICE PATH" TODAY
---------------------------------------------------------
A completed order reaches money exactly one way: Accept generates the job's
REPORT with its frozen cost lines (`services.generate_work_order_report`,
`BR-WRK-050`), and those lines are **posted nowhere** — `OQ-WRK-1491` was ruled
2026-09-04, *"(a) captured, posted nowhere"* (`costing.post_field_cost_to_ledger`
raises by design). No billing table is written by any work order, so there is
no invoice to carry an outcome onto and this lane writes none (the brief: *"do
not write billing tables"*). What a partial job carries through the cost is
therefore the TRUTH of what was done: labour from the clocks that ran and parts
actually used — never the template's planned list. Before Accept the office
sees the cost as a PREVIEW computed by the same one function; after Accept, the
frozen report's total.
"""

from __future__ import annotations

import math
from typing import Any

from django.db.models import Count, F
from django.utils import timezone

from apps.work import models as work_models
from apps.work.seams import metering_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

#: R4's four words → the stored token. The KEYS are what the field app and the
#: office screens use as catalogue keys; the VALUES are metering's tokens, read
#: from metering through the seam when compared (`_tokens()`), and pinned
#: equal by `test_cr187_order_outcomes.py` so a renamed token goes red.
R4_WORDS: dict[str, str] = {
    "passed": "passed",
    "partly_done": "partially_done",
    "failed": "failed",
    "waiting_on_someone": "waiting_on_someone_else",
    # FB-013 (`DEF-WRK-10641`, PO ruling (b) 2026-10-28) — the fifth outcome a
    # technician closes with: the step stopped because a FRESH read showed the
    # balance cleared. `BR-FLD-00004` AMENDED 2026-10-28 from four to five.
    "not_done_paid": "not_done_payment_received",
}

#: R4: *"Waiting on someone is being blocked by a person, a part or access"*.
BLOCKERS: tuple[str, ...] = ("person", "part", "access")

#: The shape each outcome reads as on the office's queue — the distinction
#: E2E-05/06 exist to prove: failing is not being blocked.
KIND_BY_OUTCOME: dict[str, str] = {
    "passed": "done",
    "partially_done": "partial",
    "failed": "failure",
    "waiting_on_someone_else": "blocked",
    # Not a failure and not blocked: the job was not needed (FB-013).
    "not_done_payment_received": "paid",
}


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _tokens() -> Any:
    return metering_seam.work_order_state_tokens()


def word_for(token: str | None) -> str | None:
    """The R4 word for a stored token, or None (no outcome, or `cancelled`)."""
    for word, stored in R4_WORDS.items():
        if stored == token:
            return word
    return None


def _remaining_steps(order_id: Any) -> tuple[list[dict[str, Any]], int, int]:
    """The order's own task rows with no tick, in `seq` order, plus done/total.

    Read from `work_order_tasks` — the COPY the order took at raise
    (`BR-WRK-008`) — never the template, so a template edited since cannot
    change which steps a partial job left undone.
    """
    rows = list(
        work_models.WorkOrderTask.objects.filter(tenant_id=_tenant_id(), work_order_id=order_id)
        .order_by("seq")
        .values("seq", "title", "is_mandatory", "ticked_at")
    )
    remaining = [
        {"seq": r["seq"], "title": r["title"], "is_mandatory": r["is_mandatory"]}
        for r in rows
        if r["ticked_at"] is None
    ]
    return remaining, len(rows) - len(remaining), len(rows)


def _photographs(order_id: Any) -> int:
    from apps.work.evidence_models import WorkOrderAttachment

    return WorkOrderAttachment.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order_id
    ).count()


def _photos_missing(data: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """`(count, items)` of the close's recorded photo gap — see `outcome_record`."""
    gap = data.get("photos_missing") if isinstance(data.get("photos_missing"), dict) else {}
    items = gap.get("items") if isinstance(gap.get("items"), list) else []
    try:
        count = int(gap.get("count") or len(items))
    except (TypeError, ValueError):
        count = len(items)
    return count, items


def outcome_record(order: Any) -> dict[str, Any]:
    """What a closed job SAID, shaped for the office (R4, E2E-04/05/06).

    `None`-valued keys are answers, not omissions: a job with no outcome reads
    `outcome: null`, a passed job reads `remaining_steps: []`, and a blocker
    that is not one of R4's three is served AS SENT under `blocker` with
    `blocker_known: false` rather than dropped.
    """
    data = order.field_data if isinstance(order.field_data, dict) else {}
    token = order.outcome
    kind = KIND_BY_OUTCOME.get(token or "")
    reason = None
    for key in ("reason", "failure_reason", "outcome_note"):
        value = data.get(key)
        if value is not None and str(value).strip():
            reason = str(value).strip()
            break
    blocker = data.get("blocker")
    blocker = str(blocker).strip().lower() if blocker not in (None, "") else None
    remaining, done, total = _remaining_steps(order.id)
    gap_count, gap_items = _photos_missing(data)
    record: dict[str, Any] = {
        "outcome": token,
        "word": word_for(token),
        "kind": kind,
        # E2E-06 — *"a blocked job is not a failure and does not read as one"*.
        "is_failure": token == _tokens().FAILED,
        "reason": reason,
        "reason_missing": kind in ("partial", "failure", "blocked") and reason is None,
        "blocker": blocker if kind == "blocked" else None,
        "blocker_known": (blocker in BLOCKERS) if kind == "blocked" and blocker else None,
        "steps_done": done,
        "steps_total": total,
        # E2E-04 — *"Office sees which steps remain"*. Every outcome carries the
        # list (a failed or blocked job has undone steps too); the screen draws
        # it for a partial job.
        "remaining_steps": remaining,
        "photographs": _photographs(order.id),
        # `BR-WRK-040` as superseded 2026-10-21 (PO: *"warn"*) — the close was
        # recorded WITH its gap, and this is where the office sees it: how many
        # REQUIRED photographs the close arrived without, and which. Written
        # by the server at the close (`metering.connections._with_photo_gap`),
        # never by the phone. `0` and `[]` are answers, not omissions.
        "photos_missing": gap_count,
        "photos_missing_items": gap_items,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        # FB-013 — the technician's own Arrived and Finished (`labour_time`,
        # server-written at the close, `DEF-WRK-4127`), for every outcome.
        "times": _times(data),
        # FB-013 — a paid close's money: what the phone SAW and what the server
        # READ at the close (`money.paid_close_record`). None on any other close.
        "payment_received": (
            data.get("payment_received") if isinstance(data.get("payment_received"), dict) else None
        ),
    }
    return record


def _times(data: dict[str, Any]) -> dict[str, Any] | None:
    """`{arrived_at, finished_at}` from the close's `labour_time`, or None."""
    block = data.get("labour_time") if isinstance(data.get("labour_time"), dict) else None
    if not block:
        return None
    return {"arrived_at": block.get("arrived_at"), "finished_at": block.get("finished_at")}


def cost_of(order: Any) -> dict[str, Any]:
    """The job's cost as the office reads it — `BR-WRK-051`'s one function.

    After Accept: the frozen report's version and total (`frozen: true`).
    Before: a PREVIEW from `costing.work_order_cost_lines`, the same function
    the report will call, so the two cannot disagree about arithmetic. Money is
    a STRING at two decimals for display (hard rule 2); nothing here is posted
    (`OQ-WRK-1491`, ruled).
    """
    from apps.work import costing

    report = (
        work_models.WorkOrderReport.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id)
        .order_by("-version")
        .first()
    )
    if report is not None:
        return {"frozen": True, "report_version": report.version, "total": f"{report.total:.2f}"}
    lines, total = costing.work_order_cost_lines(order)
    return {
        "frozen": False,
        "report_version": None,
        "total": f"{total:.2f}",
        "lines": [
            {
                "kind": line.kind,
                "description": line.description,
                "qty": f"{line.qty}",
                "unit": line.unit,
                "amount": f"{line.display_amount:.2f}",
            }
            for line in lines
        ],
    }


def order_outcome(order_id: Any) -> dict[str, Any]:
    """`GET /work-orders/{id}/outcome` — one job's outcome and its cost."""
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.NotFoundError()
    return {
        "id": str(order.id),
        "order_no": order.order_no,
        **outcome_record(order),
        "cost": cost_of(order),
    }


def _outcome_filter(raw: Any) -> list[str]:
    """`?outcome=partly_done,failed` — R4 WORDS (or the stored tokens), any of.

    An unknown word is refused BY NAME (`BR-WRK-026`'s posture: a filter that
    silently matched nothing would read as *no partial jobs today*).
    """
    if raw in (None, ""):
        return []
    picked: list[str] = []
    for part in str(raw).split(","):
        word = part.strip()
        if not word:
            continue
        token = R4_WORDS.get(word) or (word if word in R4_WORDS.values() else None)
        if token is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                br_ref="BR-FLD-00004",
                message_key="work.outcome.filter_unknown",
                params={"outcome": word, "allowed": ", ".join(R4_WORDS)},
            )
        picked.append(token)
    return picked


def office_queue(
    *,
    outcome: Any = None,
    accepted: Any = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """The office ACCEPTANCE QUEUE with the outcome on every row (Walkthrough
    §4: *"Review and accept completed work; reopen or raise a follow-on; see
    what a partial left undone"*).

    `outcome` filters by R4 word(s); `accepted` is `false` (the default — what
    is waiting for the office), `true`, or `all`. Paged in SQL with
    `core.pagination`'s clamp and no maximum (NFR-3, NFR-5). `tally` counts
    each outcome over the WHOLE filtered-by-acceptance set, never the page —
    the `awaiting_approval` footer's argument.

    Oldest completion first, then id, so the order is total.
    """
    qs = metering_seam.finished_orders_queryset()
    mode = str(accepted if accepted is not None else "false").strip().lower()
    if mode in ("false", "0", "no", ""):
        qs = qs.filter(accepted_at__isnull=True)
    elif mode in ("true", "1", "yes"):
        qs = qs.filter(accepted_at__isnull=False)
    elif mode != "all":
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.outcome.accepted_filter_unknown",
            params={"accepted": mode, "allowed": "false, true, all"},
        )
    tally_rows = qs.order_by().values("outcome").annotate(n=Count("id"))
    tally = {word: 0 for word in R4_WORDS}
    tally["none"] = 0
    for row in tally_rows:
        tally[word_for(row["outcome"]) or "none"] += int(row["n"])
    picked = _outcome_filter(outcome)
    if picked:
        qs = qs.filter(outcome__in=picked)
    qs = qs.order_by(F("completed_at").asc(nulls_last=True), "id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = min(max(int(str(page)), 1), last)
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    rows = list(qs[start : start + size])
    from apps.work import field_raise
    from apps.work import selectors as work_selectors

    raised_in_field = field_raise.raised_in_field_ids([r.id for r in rows])
    now = timezone.now()
    out = []
    for order in rows:
        out.append(
            {
                "id": str(order.id),
                "order_no": order.order_no,
                "type": order.type,
                "premise": work_selectors._premise_of(order),
                "technician": (
                    (order.assignee_technician.user.full_name or None)
                    if order.assignee_technician_id and order.assignee_technician.user_id
                    else None
                ),
                "raised_in_field": str(order.id) in raised_in_field,
                "waiting_days": (
                    max(0, (now - order.completed_at).days) if order.completed_at else None
                ),
                **outcome_record(order),
                "cost": cost_of(order),
            }
        )
    return {"rows": out, "page": number, "per": size, "total": total, "tally": tally}
