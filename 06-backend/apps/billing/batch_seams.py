# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B27
#           (changes row 55)
# Findings: 04-docs/05-modules/07-billing/19-check-cost-measured.md §4
# Rules:    B1 (billing asks, the owning module answers — every load below is
#           the owner's own published batch read) · CLAUDE.md hard rule 1 ·
#           hard-won law 14 (each loader in its own savepoint)
# Tests:    06-backend/tests/test_b27_batch_reads.py
# ───────────────────────────────────────────────────────
"""WHICH OWNING MODULE LOADS WHICH OF A CHECK BATCH'S OWN ROWS — one list.

`check_engine.CheckContext.batches` calls `load(accounts, ctx)` once per batch
of 500, inside the batch memo (`core.batch_reads`). Each entry below names an
owning module's BATCH READ: it answers the whole batch's question in one query
set and primes the memo with exactly the answer its per-account read gives, so
the Check reads the same facts it always read, one query set instead of five
hundred.

⚠ **AN ENTRY THAT IS NOT PUBLISHED, OR THAT FAILS, IS SKIPPED — AND THE PASS IS
THEN SLOWER, NEVER DIFFERENT.** Nothing primed means each account's own read
asks the database exactly as before. Each loader runs in its own savepoint
(law 14: a failed statement must not poison the batch's transaction on
PostgreSQL) and its failure is LOGGED, because a loader that quietly never
primes is a slow pass that reads like a fast one. `LAST` records what each
batch's loaders did, for the measurement and the tests.

WHAT A LOADER IS GIVEN: the batch's accounts (customers' rows, already in
hand) and the pass's dates. It must not widen the question: a loader primes
only the keys its per-account read would be asked with in this pass.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.billing import gather
from core import batch_reads

logger = logging.getLogger("smartbillhub.billing")


def _unit_ids(accounts: list[Any]) -> list[str]:
    return sorted({str(a.unit_id) for a in accounts if getattr(a, "unit_id", None)})


#: How far back the batch's one read of meter heads reaches for an account's
#: last-bill anchor (`runs.billed_positions` reads from the last bill's start).
#: An account billed longer ago than this reads its own heads, as before — a
#: bound on the batch read's size, never on what is billed.
ANCHOR_REACH_DAYS = 92


def prime_billing_history(accounts: list[Any], ctx: Any) -> None:
    """BILLING'S OWN ROWS — each account's last ISSUED bill, in three queries.

    The Check asks four questions of the same row one account at a time —
    `runs.last_issued_window`, `runs._payload_read_ids`,
    `selectors.last_issued_invoice_period_end` (all *"the locked bill with the
    latest `period_end`, then `created_at`"*) and `gather.
    _skipped_instalment_last_run` (the last RUN-issued bill, by `issued_at`).
    Each list is ordered by the database with the per-account read's own
    `ORDER BY` after `account_id`, and the first row per account is taken, so
    the answer is the one `.first()` gave, NULLs placed where the database
    places them."""
    from django.db.models import F

    from apps.billing import gather, models, runs, selectors
    from core import tenancy as core_tenancy

    ids = [str(a.id) for a in accounts]
    tenant_id = core_tenancy.current_tenant_id()
    # TWO "last bills" from ONE query (`DEF-BIL-9254`): `any_end` is the
    # newest issued DOCUMENT (the move-out guard's
    # `last_issued_invoice_period_end`, which a fee counts for), and `last` is
    # the newest issued SERVICE bill — a fee covers no service period, so it
    # anchors neither the window, the payload's reads nor the calendar
    # (`selectors.NON_SERVICE_BILL_TYPES`, the per-account reads' own rule).
    last: dict[str, tuple[Any, Any, Any]] = {}
    any_end: dict[str, Any] = {}
    # `DEF-CUS-10154` — a live move-out final DRAFT anchors the SERVICE reads
    # (`selectors.billed_position_q`) and never `any_end`, which stays the
    # issued-document read the move-out date guard asks.
    for account_id, invoice_id, start, end, bill_type, status in (
        models.Invoice.objects.filter(
            selectors.billed_position_q(), tenant_id=tenant_id, account_id__in=ids
        )
        .order_by("account_id", "-period_end", "-created_at")
        .values_list("account_id", "id", "period_start", "period_end", "bill_type", "status")
    ):
        if status in models.INVOICE_LOCKED_STATUSES:
            any_end.setdefault(str(account_id), end)
        if bill_type not in selectors.NON_SERVICE_BILL_TYPES:
            last.setdefault(str(account_id), (invoice_id, start, end))
    payloads = (
        dict(
            models.Invoice.objects.filter(
                tenant_id=tenant_id, pk__in=[row[0] for row in last.values()]
            ).values_list("id", "bill_payload")
        )
        if last
        else {}
    )
    by_run: dict[str, Any] = {}
    for account_id, run_id in (
        models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=ids,
            status__in=models.INVOICE_LOCKED_STATUSES,
            bill_run__isnull=False,
        )
        .order_by("account_id", F("issued_at").desc(nulls_last=True), "-period_end", "-created_at")
        .values_list("account_id", "bill_run_id")
    ):
        by_run.setdefault(str(account_id), run_id)
    skipped = (
        {
            (str(run_id), str(account_id))
            for run_id, account_id in models.BillRunDecision.objects.filter(
                tenant_id=tenant_id,
                bill_run_id__in=list(set(by_run.values())),
                account_id__in=list(by_run),
                case="plan_instalment_due",
                choice="skip",
                superseded_by__isnull=True,
            ).values_list("bill_run_id", "account_id")
        }
        if by_run
        else set()
    )
    for account in accounts:
        key = str(account.id)
        row = last.get(key)
        start, end = (row[1], row[2]) if row is not None else (None, None)
        window = None if start is None or end is None else (start, end)
        batch_reads.prime(runs.last_issued_window, window, key)
        batch_reads.prime(selectors.last_issued_invoice_period_end, any_end.get(key), key)
        batch_reads.prime(selectors.last_issued_service_period_end, end, key)
        batch_reads.prime(
            runs._payload_read_ids,
            runs._read_ids_in_payload(payloads.get(row[0]) if row is not None else None),
            key,
        )
        run_id = by_run.get(key)
        batch_reads.prime(
            gather._skipped_instalment_last_run,
            run_id is not None and (str(run_id), key) in skipped,
            getattr(account, "tenant_id", None),
            key,
        )


def _billing(_found: Any, accounts: list[Any], ctx: Any) -> None:
    prime_billing_history(accounts, ctx)


def _metering(found: Any, accounts: list[Any], ctx: Any) -> None:
    """Units, service points, meters (through assets), readings, disputes —
    the heads read reaching back to the earliest last-bill start in the batch
    (within `ANCHOR_REACH_DAYS`), where `runs.billed_positions` finds its
    anchor read."""
    from datetime import timedelta

    from apps.billing import runs

    floor = ctx.period_start - timedelta(days=ANCHOR_REACH_DAYS)
    starts = [
        window[0]
        for window in (runs.last_issued_window(a.id) for a in accounts)
        if window is not None and window[0] >= floor
    ]
    found(
        _unit_ids(accounts),
        period_start=ctx.period_start,
        period_end=ctx.period_end,
        reads_from=min([ctx.period_start, *starts]),
    )


def _customers(found: Any, accounts: list[Any], _ctx: Any) -> None:
    """Agreements, the primary contact's name, dark days — customers' rows,
    for the accounts customers already handed the run."""
    found(accounts)


def _rating(found: Any, accounts: list[Any], ctx: Any) -> None:
    """Each unit's dated plan history, each account's exemption certificates
    and discount enrolments."""
    found(
        _unit_ids(accounts),
        [str(a.id) for a in accounts],
        period_start=ctx.period_start,
        period_end=ctx.period_end,
    )


#: `(module, attribute, kind, adapter)` — each owning module's batch read, in
#: the order they run, and how billing hands it the batch. Billing's own rows
#: first: the metering read reaches back to the last bills they name.
LOADERS: tuple[tuple[str, str, str, Any], ...] = (
    ("billing", "prime_billing_history", "batch_seams", _billing),
    ("metering", "prime_check_batch", "selectors", _metering),
    ("customers", "prime_check_batch", "selectors", _customers),
    ("rating", "prime_check_batch", "selectors", _rating),
)

#: What the last batch's loaders did — `{name: "ok" | "absent" | "failed"}`.
LAST: dict[str, str] = {}


def load(accounts: list[Any], ctx: Any) -> dict[str, str]:
    """Run every published loader for this batch. Never raises."""
    LAST.clear()
    if not accounts:
        return dict(LAST)
    for module, attribute, kind, adapter in LOADERS:
        name = f"{module}.{attribute}"
        found = gather._resolve(module, attribute, kind)
        if found is None:
            LAST[name] = "absent"
            continue
        try:
            with transaction.atomic():
                adapter(found, accounts, ctx)
            LAST[name] = "ok"
        except Exception:  # noqa: BLE001 — see the module docstring
            LAST[name] = "failed"
            logger.exception("bill run check: batch loader %s failed; reading per account", name)
    return dict(LAST)


__all__ = ["LAST", "LOADERS", "load"]
