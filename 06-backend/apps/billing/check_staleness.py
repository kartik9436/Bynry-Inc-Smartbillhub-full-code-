# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-A1 (six accounts blocked on an unpublished plan; the
#           plan is published; only those six re-check and turn ready)
# Ruling:   OQ-843 RE-RULED 2026-09-30, option C — *"Save results, and
#           automatically re-check an account when its plan, reading, meter or
#           payment changes"*
# Plan:     15-bulk-bill-run-build-plan.md B9 · B15
# Tests:    06-backend/tests/test_bbr_check_store.py
# ───────────────────────────────────────────────────────
"""A saved Check result goes stale when its account's facts move; re-check it.

WHICH PATTERN, AND WHY THIS ONE
-------------------------------
This repository has NO signal, outbox or event bus between modules (grepped
2026-09-30: no `post_save` receiver, no outbox table, no change feed), and the
rule against cross-module writes forbids metering, rating or payments writing
into billing's store. So billing POLLS a read-only **"changed since" seam** on
each owning module — the same seam pattern every other billing read uses:

  * metering  `units_changed_since(unit_ids, since)` — the unit row (its plan
    assignment), its readings, its meters;
  * rating    `plans_changed_since(plan_ids, since)` — the plan row (publish),
    its schedule links, and a new DATED price version on any of its schedules
    (`DEF-BIL-8245`: a new price version is a plan change for this ruling);
  * payments  `bill_run_checks.accounts_changed_since(account_ids, since)`.

`sweep(run)` asks each ONCE for every account the run saved, with `since` =
the oldest `checked_at` among them, and marks stale exactly the accounts whose
fact changed AFTER their own `checked_at`; it then re-checks just those
(`check_store.check_run(only_accounts=…)`, plan B15). Nothing is written in
another module and nothing is guessed about a change the seam did not report.

WHEN IT RUNS
------------
  * every `GET …/findings` of an open run sweeps first (so a clerk who fixed a
    plan in another tab sees it on the next look — *"the 6 turn green within
    seconds"*); a re-check of up to `INLINE_RECHECK` accounts runs inline and a
    bigger one goes to the billing queue as a background re-check;
  * a beat entry sweeps every open run every `SWEEP_SECONDS` (installed from
    `BillingConfig.ready`, the `identity.session_cleanup` pattern).

OPEN RUNS ONLY: a run whose bills have gone out is history, and re-checking it
would describe a world its bills no longer match.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.billing import check_models, gather, models

logger = logging.getLogger("smartbillhub.billing")

#: Up to this many stale accounts are re-checked inside the request that found
#: them (137 ms an account measured → ~7 s); more go to a background job.
INLINE_RECHECK = 50
#: How often the beat sweep runs. A display cadence, not a rule.
SWEEP_SECONDS = 60
SWEEP_TASK = "billing.check.sweep"
BEAT_ENTRY = "billing-check-sweep"

#: Statuses of a run that may still change what it bills.
OPEN_RUN_STATUSES = ("draft",)


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    return gather._resolve(module, attribute, kind)


#: WHICH CATEGORY OF THE CHECK each kind of change touches (DEF-BIL-8286) —
#: the registry re-runs it and everything downstream of it, nothing else:
#:   * a unit's readings, meters or plan assignment → `account` (and so every
#:     category that reads the readings — all but payments);
#:   * a plan row (published, edited), or a new price version under it
#:     (DEF-BIL-8245) → `services` (the gather prices on it);
#:   * a payment posted or reversed → `payments` only — no gather at all.
#: A row already marked stale with no change reported is re-checked in full.
UNIT_CHANGE = "account"
PLAN_CHANGE = "services"
PAYMENT_CHANGE = "payments"


def stale_account_ids(run: Any) -> list[str]:
    """The accounts whose saved result an owning module has since moved under."""
    return list(stale_categories(run))


def stale_categories(run: Any) -> dict[str, frozenset[str] | None]:
    """`{account_id: the categories to re-run}` — None means re-check in full.

    🔒 HUMAN-REVIEW-PENDING · **IT COSTS WHAT CHANGED, NOT THE RUN'S SIZE
    (`DEF-BIL-8694`, 2026-10-01).** It read every saved row of the run and
    handed metering and payments the run's every unit and account id as bound
    parameters — 3.1 s at 40,015 accounts, before every look at the Check,
    while the page itself took 0.02 s. Now it asks each owner what changed
    since the run's OLDEST check, for the whole utility (`None` — no id list),
    and reads back only the saved rows those changes, or a stale flag, can
    touch. The per-row test below is unchanged, so the answer is the same set:
    a row none of the changed ids names, and not flagged, was never stale."""
    from django.db import connection
    from django.db.models import Min, Q

    saved = check_models.BillRunAccountCheck.objects.filter(tenant_id=run.tenant_id, bill_run=run)
    since = saved.aggregate(first=Min("checked_at"))["first"]
    if since is None:
        return {}
    plans = {str(p) for p in saved.exclude(plan_id=None).values_list("plan_id", flat=True).distinct()}

    units_changed = _ask("metering", "units_changed_since", None, since)
    plans_changed = _ask("rating", "plans_changed_since", plans, since)
    paid_changed = _ask("payments", "accounts_changed_since", None, since, "bill_run_checks")

    touched_by = (
        Q(stale=True)
        | Q(account_id__in=list(paid_changed))
        | Q(unit_id__in=list(units_changed))
        | Q(plan_id__in=list(plans_changed))
    )
    if units_changed:
        # A master's COVERED units: `?|` asks a jsonb array for any of these
        # ids (PostgreSQL). Elsewhere every row that covers units is read.
        touched_by |= (
            Q(covered_unit_ids__has_any_keys=list(units_changed))
            if connection.vendor == "postgresql"
            else ~Q(covered_unit_ids=[])
        )
    rows = list(
        saved.filter(touched_by).values(
            "account_id", "checked_at", "covered_unit_ids", "unit_id", "plan_id", "stale"
        )
    )

    stale: dict[str, frozenset[str] | None] = {}
    for r in rows:
        mine = {str(u) for u in (r["covered_unit_ids"] or [])}
        if r["unit_id"]:
            mine.add(str(r["unit_id"]))

        def moved(moment: Any, at: Any = r["checked_at"]) -> bool:
            return moment is not None and moment > at

        touched: set[str] = set()
        if any(moved(units_changed.get(u)) for u in mine):
            touched.add(UNIT_CHANGE)
        if r["plan_id"] and moved(plans_changed.get(str(r["plan_id"]))):
            touched.add(PLAN_CHANGE)
        if moved(paid_changed.get(str(r["account_id"]))):
            touched.add(PAYMENT_CHANGE)
        if touched:
            stale[str(r["account_id"])] = frozenset(touched)
        elif r["stale"]:
            stale[str(r["account_id"])] = None
    return stale


def _ask(module: str, attribute: str, ids: Any, since: Any, kind: str = "selectors") -> dict:
    """`ids=None` asks about every row of the utility (`DEF-BIL-8694`)."""
    seam = _resolve(module, attribute, kind)
    if seam is None or (ids is not None and not ids):
        return {}
    return seam(None if ids is None else list(ids), since) or {}


def sweep(run: Any, *, recheck: bool = True, actor_user_id: Any = None) -> dict[str, Any]:
    """Mark the run's stale accounts and re-check them. Returns what it did."""
    if run.status not in OPEN_RUN_STATUSES or run.cycle_id is None:
        return {"stale": 0, "rechecked": 0, "background": False}
    from apps.billing import check_store

    if check_store.run_is_sent(run):
        # PO 2026-09-30: automatic re-check STOPS for a sent run — its check
        # record is locked as the report of what was sent.
        return {"stale": 0, "rechecked": 0, "background": False}
    by_account = stale_categories(run)
    stale = list(by_account)
    if not stale:
        return {"stale": 0, "rechecked": 0, "background": False}
    check_models.BillRunAccountCheck.objects.filter(
        tenant_id=run.tenant_id, bill_run=run, account_id__in=stale
    ).update(stale=True)
    if not recheck:
        return {"stale": len(stale), "rechecked": 0, "background": False}
    # DEF-BIL-8286 — one re-check per SET of touched categories, so a posted
    # payment re-runs the payments category and nothing else.
    groups: dict[frozenset[str] | None, list[str]] = {}
    for account_id, touched in by_account.items():
        groups.setdefault(touched, []).append(account_id)
    if len(stale) <= INLINE_RECHECK:
        from apps.billing import check_store

        for touched, ids in groups.items():
            check_store.check_run(
                run, only_accounts=ids, categories=None if touched is None else sorted(touched)
            )
        return {"stale": len(stale), "rechecked": len(stale), "background": False}
    from apps.billing import run_jobs

    for touched, ids in groups.items():
        run_jobs.enqueue_check(
            run,
            only_accounts=ids,
            actor_user_id=actor_user_id,
            categories=None if touched is None else sorted(touched),
        )
    return {"stale": len(stale), "rechecked": 0, "background": True}


def sweep_open_runs() -> dict[str, Any]:
    """The beat body: every open run of every tenant that has saved results."""
    from core import tenancy as core_tenancy

    live = _resolve("tenancy", "live_tenant_subdomains")
    swept = 0
    for subdomain in (live() if live else ()) or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(subdomain))
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            run_ids = (
                check_models.BillRunAccountCheck.objects.filter(tenant_id=tenant_id)
                .values_list("bill_run_id", flat=True)
                .distinct()
            )
            for run in models.BillRun.objects.filter(
                tenant_id=tenant_id, pk__in=list(run_ids), status__in=OPEN_RUN_STATUSES
            ):
                try:
                    sweep(run)
                    swept += 1
                except Exception:  # noqa: BLE001 — one run never stops the sweep
                    logger.exception("bill run check sweep failed for run %s", run.pk)
    return {"runs": swept}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA (the `session_cleanup` pattern)."""
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(SWEEP_SECONDS),
            "args": (),
            "options": {"expires": SWEEP_SECONDS},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the sweep task and its beat entry. Never raises: a deployment
    without celery starts, and the findings read still sweeps on every look."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    app.task(name=SWEEP_TASK, bind=False)(sweep_open_runs)
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(beat_schedule())
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY}


__all__ = [
    "INLINE_RECHECK",
    "beat_schedule",
    "install",
    "stale_account_ids",
    "stale_categories",
    "sweep",
]
