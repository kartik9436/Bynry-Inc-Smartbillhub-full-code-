# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-041 (Not in this run and catch-up) · US-BIL-039 TC-3 (every
#           See on Who is billed opens this list with its filter pressed)
# Rules:    BR-BIL-1054 (PO 2026-09-30) · BR-BIL-034 (hold ≠ forget) ·
#           BR-BIL-1025 (nothing to bill is not a fault) · NFR-3 (every list
#           pages)
# Defects:  DEF-BIL-8223 (Leave for next cycle) · DEF-BIL-8410 (the queue at
#           Send)
# Plan:     15-bulk-bill-run-build-plan.md B20 · A9 · F19
# Tests:    06-backend/tests/test_bbr_not_in_run.py
# ───────────────────────────────────────────────────────
"""NOT IN THIS RUN — every account the run does not bill, and every unit it
cannot bill, on the run itself, with its reason.

PO 2026-09-30, verbatim: *"then the accounts are not bill or theya re on hold
or ecluded in this run - we need to show them as a list or somthing and allow
to run ran them later"*.

THE GROUPS (the list's filter buttons, and Sign off's *See* targets):

  * `blocked`  — the saved Check found a problem that blocks it; the reason is
    its FIRST blocking tag, and `also` counts the others;
  * `held`     — a clerk's answer holds it (a hold written to the queue at
    Calculate), or it is still WAITING on a decision nobody answered;
  * `nothing`  — examined and quiet: nothing to bill (BR-BIL-1025);
  * `left_out` — a ready account the clerk left out (BR-BIL-1054);
  * `nobody`   — a UNIT in the cycle with nobody to bill. It is a unit row, not
    an account, so it has no checkbox and no catch-up — the fix is an account.

Before Send the list says what WILL go to Pending billing; after Send each
account row carries its queue state (days waiting, left for the next cycle,
caught up by which run). Built from saved rows only — the Check store, the
run's own queue rows and one batched display read — never a re-check.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.billing import check_engine, check_models, check_store, decisions, models, pending, runs
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

GROUP_BLOCKED = "blocked"
GROUP_HELD = "held"
GROUP_NOTHING = "nothing"
GROUP_LEFT_OUT = "left_out"
GROUP_NOBODY = "nobody"
#: DEF-BIL-8416 — a WAIVED account (PO 2026-09-30, fixed-charge case 2): not
#: billed and not carried, so it is never queued and never caught up — and it
#: is still LISTED, because an account in no list is one the clerk cannot find
#: (clerk check A3: every account ends as sent, broken, or here).
GROUP_WAIVED = "waived"
GROUPS: tuple[str, ...] = (
    GROUP_BLOCKED,
    GROUP_HELD,
    GROUP_NOTHING,
    GROUP_LEFT_OUT,
    GROUP_WAIVED,
    GROUP_NOBODY,
)

#: Why a HELD account is held: a clerk's hold, or no answer yet.
REASON_HOLD = "hold"
REASON_WAITING = "waiting_on_a_decision"
REASON_WAIVED = "waived"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _holding_answer(run: Any, raised: dict[str, set[str]]) -> set[str]:
    """Accounts a live answer holds — their own, or the tag's standing answer
    for a decision the account raised and did not answer itself."""
    own: dict[str, dict[str, str]] = {}
    for row in decisions.current_decisions(run):
        own.setdefault(str(row.account_id), {})[row.case] = row.choice
    standing = decisions.standing_answers(run)
    held: set[str] = set()
    for account_id, cases in raised.items():
        mine = own.get(account_id, {})
        for case in cases:
            choice = mine.get(case) or standing.get(case)
            if choice and (case, choice) in decisions.HOLDING_CHOICES:
                held.add(account_id)
    for account_id, mine in own.items():
        for case, choice in mine.items():
            if case != decisions.CASE_LEFT_OUT and (case, choice) in decisions.HOLDING_CHOICES:
                held.add(account_id)
    return held


def rows_for(run: Any, *, statuses: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Every row, unpaged, in group order then account number. The account
    rows come from the saved Check; the unit rows from the run's saved list of
    units with nobody to bill (`check_store.check_run`). `statuses` is
    `check_store.account_statuses(run)` when the caller has already read it
    (Sign off does, `DEF-BIL-8696`) — the same answer, not read twice."""
    tenant_id = _tenant_id()
    checks = check_models.BillRunAccountCheck.objects.filter(tenant_id=tenant_id, bill_run=run)
    if statuses is None:
        # ⛔ `DEF-BIL-8809` — only the accounts the run holds no bill for, in
        # SQL, and their statuses and pricing partition from ONE read. A billed
        # account is never a row here, and on a sent 40,008-bill run the old
        # read decided all 40,015 accounts twice in Python (~0.85 s of 1.0 s)
        # to skip 40,008 of them.
        statuses, partition = check_store.unbilled_statuses_and_partition(run)
        checks = check_store.unbilled(checks, run)
        billed: set[str] = set()
    else:
        # What Calculate does with each account the Check let through — the
        # same partition *Price N* counts (DEF-BIL-8554), so a row's group is
        # its truth.
        partition = check_store.pricing_partition(run)
        billed = {
            str(one)
            for one in models.Invoice.objects.filter(
                tenant_id=tenant_id, bill_run=run
            ).values_list("account_id", flat=True)
        }
    saved = {
        str(r["account_id"]): r
        for r in checks.values("account_id", "account_no", "unit_id", "account_kind")
    }
    first, blocking = check_store.first_blocking(run)
    raised: dict[str, set[str]] = {}
    for account_id, code in check_models.BillRunFinding.objects.filter(
        tenant_id=tenant_id, bill_run=run, severity="decision"
    ).values_list("account_id", "code"):
        raised.setdefault(str(account_id), set()).add(code)
    queued = {
        str(row.account_id): row
        for row in models.BillRunExclusion.objects.filter(tenant_id=tenant_id, bill_run=run)
    }
    held_by_answer = _holding_answer(run, raised)

    rows: list[dict[str, Any]] = []
    for account_id, status in statuses.items():
        if account_id in billed:
            continue
        queue = queued.get(account_id)
        if status == check_engine.STATUS_BLOCKED:
            group, reason = GROUP_BLOCKED, first.get(account_id)
        elif status == check_engine.STATUS_QUIET:
            group, reason = GROUP_NOTHING, runs.RUN_NOTHING_TO_BILL
        elif status == check_engine.STATUS_LEFT_OUT:
            group, reason = GROUP_LEFT_OUT, decisions.LEFT_OUT_REASON
        elif partition.get(account_id) == check_store.WAIVED:
            group, reason = GROUP_WAIVED, REASON_WAIVED
        elif partition.get(account_id) == check_store.UNDECIDED:
            group, reason = GROUP_HELD, REASON_WAITING
        elif partition.get(account_id) == check_store.HELD:
            group, reason = GROUP_HELD, REASON_HOLD
        elif status == check_engine.STATUS_DECISION:
            group, reason = GROUP_HELD, REASON_WAITING
        elif account_id in held_by_answer or (
            queue is not None and queue.reason_code != decisions.LEFT_OUT_REASON
        ):
            group, reason = GROUP_HELD, REASON_HOLD
        else:
            continue  # ready: it will be (or was) priced
        row = saved.get(account_id, {})
        rows.append(
            {
                "key": f"account:{account_id}",
                "kind": "account",
                "group": group,
                "reason": reason,
                "also": max(blocking.get(account_id, 0) - 1, 0) if group == GROUP_BLOCKED else 0,
                "account_id": account_id,
                "account_no": row.get("account_no"),
                "account_kind": row.get("account_kind"),
                "unit_id": str(row["unit_id"]) if row.get("unit_id") else None,
                "queue": _queue_state(queue),
            }
        )
    summary = dict(run.findings_summary or {})
    for unit_id in summary.get("units_nobody_ids") or ():
        rows.append(
            {
                "key": f"unit:{unit_id}",
                "kind": "unit",
                "group": GROUP_NOBODY,
                "reason": runs.RUN_UNIT_HAS_NO_ACCOUNT,
                "also": 0,
                "account_id": None,
                "account_no": None,
                "account_kind": None,
                "unit_id": str(unit_id),
                "queue": None,
            }
        )
    order = {group: i for i, group in enumerate(GROUPS)}
    rows.sort(key=lambda r: (order[r["group"]], r["account_no"] or "", r["unit_id"] or ""))
    return rows


def _queue_state(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "reason_code": row.reason_code,
        "origin": pending.origin_of(row.reason_code),
        "held_on": row.created_at.date().isoformat(),
        "next_cycle": row.next_cycle_at is not None,
        "resolved_by_run_id": str(row.resolved_by_run_id) if row.resolved_by_run_id else None,
    }


def not_in_run(run: Any, params: Any) -> dict[str, Any]:
    """The list, paged (NFR-3), filtered by `group`, searched by `q` (account
    number), with the header's counts: accounts and units apart, and per group.

    `as_of` (YYYY-MM-DD, the clerk's today — BR-TEN-043, no clock here) adds
    `age_days` to each queued row once the run is sent; absent, no age."""
    rows = rows_for(run)
    counts = {group: 0 for group in GROUPS}
    for row in rows:
        counts[row["group"]] += 1
    group = str(params.get("group") or "")
    shown = [r for r in rows if not group or r["group"] == group]
    query = str(params.get("q") or "").strip().lower()
    if query:
        shown = [r for r in shown if query in (r["account_no"] or "").lower()]
    per = clamp_page_size(params.get("per"))
    try:
        page = max(int(str(params.get("page"))), 1)
    except (TypeError, ValueError):
        page = 1
    last = max((len(shown) + per - 1) // per, 1)
    page = min(page, last)
    chunk = [dict(r) for r in shown[(page - 1) * per : page * per]]
    _decorate(chunk, params)
    return {
        "bill_run_id": str(run.pk),
        "sent": check_store.run_is_sent(run),
        "counts": {
            **counts,
            "accounts": sum(1 for r in rows if r["kind"] == "account"),
            "units": sum(1 for r in rows if r["kind"] == "unit"),
        },
        "results": chunk,
        "count": len(shown),
        "page": page,
        "per": per,
    }


def _decorate(chunk: list[dict[str, Any]], params: Any) -> None:
    """The words each row shows (B14 rule 31 — never an id): the customer and
    address for an account, the unit's label and address for a unit row; and
    the days waiting for a queued row when the caller names its day."""
    from apps.billing import gather

    shown = check_store.display_for([r["account_id"] for r in chunk if r["account_id"]])
    unit_refs = gather._resolve("metering", "unit_refs")
    units = (
        unit_refs([r["unit_id"] for r in chunk if r["kind"] == "unit"]) if unit_refs else {}
    ) or {}
    as_of = None
    if params.get("as_of"):
        try:
            as_of = date.fromisoformat(str(params.get("as_of")))
        except ValueError:
            as_of = None
    for row in chunk:
        if row["kind"] == "account":
            row.update(shown.get(row["account_id"], {}))
        else:
            ref = units.get(row["unit_id"] or "", {})
            row.update(
                {
                    "customer_name": None,
                    "address": ref.get("premise_address"),
                    "unit_label": ref.get("label"),
                }
            )
        queue = row.get("queue")
        if queue is not None and as_of is not None:
            queue["age_days"] = max((as_of - date.fromisoformat(queue["held_on"])).days, 0)


__all__ = ["GROUPS", "not_in_run", "rows_for"]
