# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-039 (Sign off: a summary that adds up to Scope's figures,
#           usage and charges, payments and balances, how it will be paid)
# Rules:    BR-BIL-056/057 (one consolidated summary) · BR-BIL-035 (previous
#           balance − payments + this period = total due) · BR-BIL-1054 ·
#           PO 2026-09-30 fixed-charge case 2 (*"Waived $26"* on Sign off)
# Defect:   DEF-BIL-8220 (no summary read behind Sign off) · DEF-BIL-8696 (one
#           read per account: 250–396 s at 40,008 bills) · DEF-BIL-8720 (Amount
#           due ignored a payment plan's part not yet due)
# Plan:     15-bulk-bill-run-build-plan.md B19 · A8 · changes row 37
# Tests:    06-backend/tests/test_bbr_sign_off_summary.py ·
#           06-backend/tests/test_d8696_signoff_batched.py
# ───────────────────────────────────────────────────────
"""THE SIGN-OFF SUMMARY — every line adds back to the figure it came from.

PO 2026-09-30, verbatim: *"first screen units vacant units ect thos thing does
not match - we need to show accounts/units billed not billed, we need to show
much much usage across all utility services and charges - across all utility
services, + other top catgoes, we need to show much payment is applied"*.

A READ, over what the run already holds: its saved Check (who was checked and
why each is out), its draft bills and their lines (what is charged), the
release panel (`release.summary_for` — by customer type, waived), and, per
bill, the SAME arithmetic issue stamps (`payments_seam.prior_position_for_
account` with the customers opening position — BR-BIL-035/160), asked through
the same seams and never recomputed here. Nothing is written.

EVERY SECTION SAYS WHETHER IT FOOTS. *Who is billed* carries `reconciles` for
accounts and for units: the accounts line must add back to the number of
accounts the Check walked (which is Scope's *Accounts to bill*), and the units
line to the cycle's units. A line that does not foot is served with the
difference, never hidden — that is the defect the PO reported.

MONEY is served as TEXT at the stored scale (CLAUDE.md rule 2; the screen
displays 2). A figure a seam could not answer is `null` with the reason in
`problems`, never `0.00` (BR-BIL-035's own rule for the same figures).

🔒 HUMAN-OWNED · on `10-scripts/gates/human_owned.txt` since 2026-10-02 (decision log
*"THREE MORE ANSWERS"* (3), under the PO's 2026-08-09 ruling).

🔒 HUMAN-REVIEW-PENDING · **NO QUESTION IS ASKED PER ACCOUNT (`DEF-BIL-8696`,
2026-10-01).** At 40,008 bills this read asked payments and customers three
questions per bill — about 120,000 statements, 250–396 s — and a web worker is
killed at 60 s, so Sign off never showed. Every seam is now asked ONCE for the
whole run, with the run's accounts handed over as a SUBQUERY (`_account_scope`)
rather than as 40,000 bound ids, and the per-bill arithmetic still runs through
the same functions the bill is stamped with (`payments_seam.
prior_position_for_account`, `open_balance.whole_account`) over the answers
read in bulk. Nothing is stored and nothing goes stale: it is a read of the run
as it stands, exactly as before. `10-scripts/d8696_signoff_parity.py` compares
every figure with the old read's on the same world.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

from apps.billing import check_engine, check_models, check_store, models, not_in_run, runs
from apps.billing.exceptions import BillingRuleError
from core import tenancy as core_tenancy

ZERO = Decimal("0")
logger = logging.getLogger(__name__)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _counted(run: Any) -> Any:
    """The run's bills that count: drafts before Send, issued after — never a
    discarded draft (BR-BIL-004)."""
    return models.Invoice.objects.filter(tenant_id=_tenant_id(), bill_run=run).exclude(
        status__in=(models.INVOICE_VOID,)
    )


#: The bill fields Sign off reads — never `bill_payload` or the snapshot
#: columns, which are most of a bill's bytes (`DEF-BIL-8696`: 9.5 s to load
#: 40,008 whole bills).
_BILL_FIELDS = ("id", "tenant_id", "bill_run_id", "account_id", "status", "total", "currency",
                "period_end")


def _bills(run: Any) -> list[Any]:
    """The run's bills that count (`_counted`), with only the fields read here."""
    return list(_counted(run).only(*_BILL_FIELDS))


def _account_scope(run: Any) -> Any:
    """The accounts with a bill that counts, as a QUERYSET of ids — handed to
    every batched seam, which reads it as a subquery (`DEF-BIL-8696`)."""
    return _counted(run).values_list("account_id", flat=True)


def _who_is_billed(run: Any, bills: list[Any]) -> dict[str, Any]:
    tenant_id = _tenant_id()
    statuses = check_store.account_statuses(run)
    saved = {
        str(r["account_id"]): r
        for r in check_models.BillRunAccountCheck.objects.filter(
            tenant_id=tenant_id, bill_run=run
        ).values("account_id", "account_kind", "unit_id", "covered_unit_ids")
    }
    billed = {str(b.account_id) for b in bills}
    groups: dict[str, list[str]] = defaultdict(list)
    for row in not_in_run.rows_for(run, statuses=statuses):
        if row["kind"] == "account":
            groups[row["group"]].append(row["account_id"])
    accounted = billed | {a for ids in groups.values() for a in ids}
    # Priced-ready accounts with no bill: their draft failed (BR-BIL-053's
    # breaks), shown as their own line rather than lost in the arithmetic.
    failed = sorted(
        a for a, s in statuses.items() if s == check_engine.STATUS_READY and a not in accounted
    )
    regular = sum(1 for a in billed if (saved.get(a) or {}).get("account_kind") != "master")
    master = len(billed) - regular
    not_billed = {
        "blocked": len(groups[not_in_run.GROUP_BLOCKED]),
        "held": len(groups[not_in_run.GROUP_HELD]),
        "nothing_to_bill": len(groups[not_in_run.GROUP_NOTHING]),
        "left_out": len(groups[not_in_run.GROUP_LEFT_OUT]),
        # DEF-BIL-8416 — waived: not billed by design, never "failed".
        "waived": len(groups[not_in_run.GROUP_WAIVED]),
        "failed_to_draft": len(failed),
    }
    to_bill = len(statuses)
    accounts = {
        "to_bill": to_bill,
        "billed": len(billed),
        "regular": regular,
        "master": master,
        "not_billed": sum(not_billed.values()),
        **not_billed,
    }
    accounts["reconciles"] = to_bill == accounts["billed"] + accounts["not_billed"]

    # ── units: billed through their own account or a master's, or not ──────
    def units_of(account_id: str) -> set[str]:
        row = saved.get(account_id) or {}
        covered = {str(u) for u in (row.get("covered_unit_ids") or [])}
        if row.get("unit_id"):
            covered.add(str(row["unit_id"]))
        return covered

    own: set[str] = set()
    through_master: set[str] = set()
    for account_id in billed:
        target = (
            through_master if (saved.get(account_id) or {}).get("account_kind") == "master" else own
        )
        target |= units_of(account_id)
    through_master -= own
    quiet_units = (
        {u for a in groups[not_in_run.GROUP_NOTHING] for u in units_of(a)} - own - through_master
    )
    not_billed_units = {
        u
        for group in (
            not_in_run.GROUP_BLOCKED,
            not_in_run.GROUP_HELD,
            not_in_run.GROUP_LEFT_OUT,
            not_in_run.GROUP_WAIVED,  # DEF-BIL-8416: a waived account's unit is not billed
        )
        for a in groups[group]
        for u in units_of(a)
    } | {u for a in failed for u in units_of(a)}
    not_billed_units -= own | through_master | quiet_units
    nobody = len((run.findings_summary or {}).get("units_nobody_ids") or [])
    in_cycle = _units_in_cycle(run)
    units = {
        "in_cycle": in_cycle,
        "billed": len(own) + len(through_master),
        "own_account": len(own),
        "through_master": len(through_master),
        "not_billed": len(not_billed_units) + len(quiet_units) + nobody,
        "account_not_billed": len(not_billed_units),
        "nothing_to_bill": len(quiet_units),
        "nobody_to_bill": nobody,
    }
    units["reconciles"] = in_cycle is not None and in_cycle == units["billed"] + units["not_billed"]
    return {"accounts": accounts, "units": units, "failed_to_draft_ids": failed}


def _units_in_cycle(run: Any) -> int | None:
    from apps.billing import gather

    seam = gather._resolve("metering", "units_in_cycle")
    if seam is None or run.cycle_id is None:
        return None
    try:
        return len(set(seam(run.cycle_id, service_codes=None) or ()))
    except Exception:  # noqa: BLE001 — a count is display; None, never a guess
        return None


def _usage_and_charges(run: Any, bills: list[Any]) -> dict[str, Any]:
    """Per service: bills, usage WITH ITS UNIT (rule 3), usage charges, base
    charges, total; then the other top categories and this run's charges.
    Every figure is a sum of the draft lines' own amounts — nothing re-priced.

    `DEF-BIL-8696` — summed in SQL (`GROUP BY`), never line by line in Python:
    a 40,000-bill run has ~300,000 lines. NUMERIC sums are exact, so each
    figure is the one the Python loop made, to the last stored place."""
    from django.db.models import Count, Q, Sum

    from apps.billing import gather

    lines = models.InvoiceLine.objects.filter(
        tenant_id=_tenant_id(), invoice__in=_counted(run).values("pk")
    )
    priced = Q(kind__in=("usage", "base", "minimum"), service_id__isnull=False)
    codes = gather._resolve("tenancy", "service_ids_by_code")
    code_by_id = {str(v): k for k, v in ((codes() if codes else {}) or {}).items()}
    services: dict[str, dict[str, Any]] = {}

    def entry_for(service_id: Any) -> dict[str, Any]:
        code = code_by_id.get(str(service_id), str(service_id))
        return services.setdefault(
            code,
            {
                "bills": 0,
                "usage": defaultdict(lambda: ZERO),
                "usage_charges": ZERO,
                "base_charges": ZERO,
                "total": ZERO,
            },
        )

    for row in (
        lines.filter(priced)
        .values("service_id", "kind", "unit")
        .annotate(amount=Sum("amount"), quantity=Sum("quantity"))
        .order_by()
    ):
        entry = entry_for(row["service_id"])
        amount = row["amount"] if row["amount"] is not None else ZERO
        if row["kind"] == "usage":
            entry["usage_charges"] += amount
            if row["quantity"] is not None and row["unit"]:
                entry["usage"][row["unit"]] += row["quantity"]
        else:
            entry["base_charges"] += amount
        entry["total"] += amount
    for row in (
        lines.filter(priced)
        .values("service_id")
        .annotate(n=Count("invoice_id", distinct=True))
        .order_by()
    ):
        entry_for(row["service_id"])["bills"] += row["n"]
    other: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in lines.exclude(priced).values("kind").annotate(amount=Sum("amount")).order_by():
        other[row["kind"]] += row["amount"] if row["amount"] is not None else ZERO
    rows = []
    subtotal = ZERO
    for code in sorted(services):
        entry = services[code]
        subtotal += entry["total"]
        rows.append(
            {
                "service_code": code,
                "bills": entry["bills"],
                "usage": [
                    {"quantity": _text(q), "unit": u} for u, q in sorted(entry["usage"].items())
                ],
                "usage_charges": _text(entry["usage_charges"]),
                "base_charges": _text(entry["base_charges"]),
                "total": _text(entry["total"]),
            }
        )
    charges = sum((b.total or ZERO for b in bills), ZERO)
    other_total = sum(other.values(), ZERO)
    return {
        "services": rows,
        "services_subtotal": _text(subtotal),
        "other": {
            "taxes": _text(other.get("tax", ZERO)),
            "fees": _text(other.get("fee", ZERO)),
            "credits_and_adjustments": _text(other.get("adjustment", ZERO)),
        },
        "this_run_charges": _text(charges),
        # Services + the other categories must BE this run's charges.
        "reconciles": subtotal + other_total == charges,
    }


def _whole_account_reads(run: Any, bills: list[Any], scope: Any, credit: Any) -> Any:
    """🔒 DEF-BIL-8682 — everything `issue._whole_account_window` asks payments
    and billing PER BILL, asked ONCE for the whole run (NFR-3: a run at the top
    of T5 is 40,000 bills), then handed to `open_balance.whole_account`, which
    stays the one statement of the arithmetic.

    Returns `answer(account_id, position) -> (whole, received)` — `whole` is
    `whole_account`'s dict and `received` payments' split of the window — or
    None when payments does not publish the batched reads (Sign off then keeps
    the open-bills window, as issue does when payments cannot answer).

    `DEF-BIL-8696` — `scope` is the run's accounts as a queryset (each read
    takes it as a subquery) and `credit` the credit positions already read for
    the whole run by the caller."""
    from apps.billing import decisions, open_balance, payments_seam

    ids = sorted({str(bill.account_id) for bill in bills})
    if not ids:
        return None
    if credit is None:
        return None
    since = open_balance.payments_since_for_accounts(scope, exclude_bill_run=run)
    # DEF-BIL-8412 — *Apply next bill*: the same test `issue._defers_late_payments`
    # makes per bill, from ONE read of the run's current answers.
    defers = {
        str(row.account_id)
        for row in decisions.current_decisions(run)
        if row.case == "paid_after_cutoff" and row.choice == decisions.CHOICE_APPLY_NEXT_BILL
    }
    through = {bill_id: None for bill_id in ids}
    for bill in bills:
        if str(bill.account_id) in defers:
            through[str(bill.account_id)] = bill.period_end
    received = payments_seam.payments_received_by_type_for_accounts(
        {key: (since.get(key), through[key]) for key in ids}, scope=scope
    )
    if received is None:
        return None

    def answer(account_id: Any, position: Any) -> tuple[Any, Any]:
        key = str(account_id)
        split = received.get(key)
        if split is None or key not in credit:
            return None, None
        whole = open_balance.whole_account(
            account_id,
            position,
            since=since.get(key),
            through_date=through[key],
            credit=credit[key],
            received=split["received"],
            beyond=split["beyond"],
        )
        return whole, split

    return answer


def _payments_and_balances(run: Any, bills: list[Any]) -> dict[str, Any]:
    """BR-BIL-035's arithmetic, summed over the run's bills — asked through the
    SAME seams issue asks when it stamps each bill, so Sign off shows what the
    bills will say: previous balance − payments and credits applied + this
    run's charges − a payment plan's part not yet due = amount due. A seam that
    cannot answer for a bill makes the totals `null` and says which bills,
    never a zero.

    🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — each seam asked ONCE for the
    whole run (`_run_reads`), each bill's position then put together by
    `payments_seam.prior_position_for_account` from those answers — the same
    function, the same arithmetic, no statement per bill.

    🔒 `DEF-BIL-8720` — BR-BIL-1061 (PO 2026-10-01): *"$62 + $45 = $107, with
    the rest of the plan shown as not yet due"*. The bill subtracts an ACTIVE
    plan's part falling due after its due date from what it asks
    (`open_balance.plan_not_yet_due`); Sign off now does too, and serves the
    amount it held back as `plan_not_yet_due`, so its *Amount due* is what the
    bills will ask."""
    from apps.billing import customers_seam, issue, payments_seam

    previous = paid = due = held_back = ZERO
    payments = credits = ZERO
    payment_count = credit_count = 0
    applied_accounts = 0
    unknown: list[str] = []
    positions: dict[str, Any] = {}
    amounts_due: dict[str, Decimal] = {}
    # 🔒 `DEF-BIL-8727` — a SENT bill answers with what it was stamped with.
    stamped = _stamped_balance_forward(bills)
    reads = _run_reads(run, [bill for bill in bills if str(bill.pk) not in stamped])
    whole_by_account = reads["whole"]
    split_known = whole_by_account is not None
    for bill in bills:
        key = str(bill.account_id)
        block = stamped.get(str(bill.pk))
        if block is not None:
            figures = _stamped_figures(block)
            if figures is None:
                unknown.append(key)
                continue
            stamped_previous, stamped_paid, stamped_due, stamped_plan = figures
            # The stamp carries no payments/credits split (`payments_applied`
            # and `credits_applied` stay null for a run holding a sent bill —
            # a split nobody stamped is a made-up figure).
            split_known = False
            positions[key] = _StampedPosition(open_balance=stamped_previous - stamped_paid)
            previous += stamped_previous
            paid += stamped_paid
            if stamped_paid:
                applied_accounts += 1
            held_back += stamped_plan
            amounts_due[str(bill.pk)] = stamped_due
            due += stamped_due
            continue
        try:
            # `DEF-BIL-8696` — the run's batched answers handed in where the
            # batch was published; asked per account exactly as before where not.
            handed: dict[str, Any] = {}
            if reads["open"] is not None:
                handed["open_position"] = reads["open"][key]
            if reads["credit"] is not None:
                handed["credit"] = reads["credit"].get(key)
            totals = reads["totals"]
            position = payments_seam.prior_position_for_account(
                bill.account_id,
                totals_by_invoice_id=(
                    issue._prior_bill_totals(bill)
                    if totals is None
                    else {k: v for k, v in totals.get(key, {}).items() if k != str(bill.pk)}
                ),
                opening=(
                    customers_seam.opening_position_for_account(bill.account_id)
                    if reads["opening"] is None
                    else reads["opening"][key]
                ),
                **handed,
            )
        except Exception:  # noqa: BLE001 — reported, never a zero
            position = None
        if position is None or position.open_balance is None:
            unknown.append(key)
            continue
        # 🔒 DEF-BIL-8682 / OQ-217 CLOSED (PO 2026-10-01, BR-BIL-1065) — the
        # SAME whole-account window issue stamps on the bill, so Sign off shows
        # what the bills will say; the open-bills window only where payments
        # cannot answer, exactly as issue falls back.
        whole = None
        received = None
        if whole_by_account is not None:
            whole, received = whole_by_account(bill.account_id, position)
        if whole is not None:
            position = replace(
                position,
                previous_balance=whole["previous_balance"],
                payments_credits=whole["payments_credits"],
                open_balance=whole["open_balance"],
            )
            payments += received["payments"]
            credits += received["credits"]
            payment_count += received["payment_count"]
            credit_count += received["credit_count"]
        else:
            split_known = False
        positions[key] = position
        previous += position.previous_balance or ZERO
        paid += position.payments_credits or ZERO
        if position.payments_credits:
            applied_accounts += 1
        amount = position.open_balance + (bill.total or ZERO)
        plan = _plan_held_back(reads, key, position.open_balance)
        if plan is not None:
            amount -= plan
            held_back += plan
        amounts_due[str(bill.pk)] = amount
        due += amount
    charges = sum((b.total or ZERO for b in bills), ZERO)
    known = not unknown
    split = known and split_known
    return {
        "previous_balance": _text(previous) if known else None,
        "payments_and_credits_applied": _text(paid) if known else None,
        "accounts_with_payments_applied": applied_accounts if known else None,
        # DEF-BIL-8682 — the figure above PARTED by payments' own type column
        # (D1 25, 28): `payments_applied + credits_applied` is it exactly. Null
        # on a run where any bill fell back to the open-bills window, because
        # that window has no such split and a guessed one is a made-up figure.
        "payments_applied": _text(payments) if split else None,
        "payments_count": payment_count if split else None,
        "credits_applied": _text(credits) if split else None,
        "credits_count": credit_count if split else None,
        "this_run_charges": _text(charges),
        # DEF-BIL-8720 — what the bills hold back as a payment plan's part not
        # yet due (BR-BIL-1061); 0 on a run with no account on a plan.
        "plan_not_yet_due": _text(held_back) if known else None,
        "amount_due": _text(due) if known else None,
        "unanswered_accounts": sorted(unknown),
        "reconciles": known and previous - paid + charges - held_back == due,
        "how_paid": _how_paid(run, bills, amounts_due, reads["scope"]) if known else None,
        "credit_covers_bills": _credit_covers(bills, positions),
    }


@dataclass(frozen=True)
class _StampedPosition:
    """Where a SENT bill's account stood, as its own stamp says — the one field
    `_credit_covers` reads off a position."""

    open_balance: Decimal


def _stamped_balance_forward(bills: list[Any]) -> dict[str, dict[str, Any]]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8727` — `{bill id: balance_forward}`
    for every bill of the run that is no longer a DRAFT and carries the block
    issue stamped on it (`issue._stamp_balance_forward`, BR-BIL-035).

    WHY: once a run is sent its bills are in payments' open set, and the
    computed path (`prior_position_for_account` over billing's prior totals,
    which exclude the bill itself) cannot price the bill it is standing on —
    every one of the 40,008 bills of the sent 40,000-account run came back
    unanswered and Sign off printed `—` for every money figure. A sent bill's
    previous balance, payments and amount due are not a question any more:
    they are on the bill, immutable, and Sign off shows what the bills SAY.

    Only the `balance_forward` key is read (`bill_payload -> 'balance_forward'`
    in SQL) — never the payload, which is most of a bill's bytes. A locked bill
    with no block (stamped before BR-BIL-035 existed) is absent here and is
    computed as before."""
    locked = [bill.pk for bill in bills if bill.status != models.INVOICE_DRAFT]
    if not locked:
        return {}
    out: dict[str, dict[str, Any]] = {}
    rows = (
        models.Invoice.objects.filter(tenant_id=_tenant_id(), pk__in=_locked_ids(bills))
        .exclude(status=models.INVOICE_DRAFT)
        .values_list("pk", "bill_payload__balance_forward")
    )
    for pk, block in rows:
        if isinstance(block, dict):
            out[str(pk)] = block
    return out


def _locked_ids(bills: list[Any]) -> Any:
    """The run's non-draft bills as a SUBQUERY, never 40,008 bound ids
    (`DEF-BIL-8696`'s lesson) — every bill in `bills` belongs to one run."""
    return (
        _counted_for(bills[0].bill_run_id)
        .exclude(status=models.INVOICE_DRAFT)
        .values("pk")
    )


def _counted_for(bill_run_id: Any) -> Any:
    return models.Invoice.objects.filter(tenant_id=_tenant_id(), bill_run_id=bill_run_id).exclude(
        status__in=(models.INVOICE_VOID,)
    )


def _stamped_figures(
    block: dict[str, Any],
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    """(previous balance, payments and credits, total due, plan not yet due)
    off a stamp, as Decimals from their text. None when the stamp itself says
    `—` for any of the first three (issue stamps a null, never a zero, when a
    seam could not answer), so the bill is reported unanswered as before."""
    try:
        previous = block.get("previous_balance")
        paid = block.get("payments_credits")
        due = block.get("total_due")
        if previous is None or paid is None or due is None:
            return None
        plan = block.get("plan_not_yet_due")
        return (
            Decimal(str(previous)),
            Decimal(str(paid)),
            Decimal(str(due)),
            ZERO if plan is None else Decimal(str(plan)),
        )
    except (ArithmeticError, ValueError, TypeError):
        return None


def _run_reads(run: Any, bills: list[Any]) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — everything Sign off asks other
    modules, asked ONCE for the whole run. A batch a module does not publish is
    `None`, and the caller then asks that one per account, as before.

      * `open` — payments' open bills per account (`open_positions_for_accounts`);
      * `credit` — payments' signed credit position per account;
      * `totals` — billing's own locked bill totals per account (the bill's own
        excluded by the caller, as `issue._prior_bill_totals` excludes it);
      * `opening` — customers' migrated opening balance per account;
      * `whole` — the whole-account window (`_whole_account_reads`);
      * `plans` — an ACTIVE plan's split for the run's due date, `skipped` the
        accounts this run answered *Skip this month* for (`DEF-BIL-8720`)."""
    from apps.billing import customers_seam, decisions, issue, open_balance, payments_seam

    scope = _account_scope(run)
    if not bills:
        return {"scope": scope, "open": {}, "credit": {}, "totals": {}, "opening": {},
                "whole": None, "plans": {}, "skipped": set()}
    credit = payments_seam.credit_positions_for_accounts(scope)
    try:
        bill_date, due_days = issue._due_terms_for(run)
        due_date = issue.derive_due_date(bill_date, due_days)
    except BillingRuleError:
        due_date = None
    plans = payments_seam.plan_instalments_for_accounts(scope, due_by=due_date)
    if plans is None:
        # Payments publishes no batch: ask per account, as the bill does.
        plans = {}
        for key in {str(bill.account_id) for bill in bills}:
            split = payments_seam.plan_instalments_for_bill(key, due_by=due_date)
            if split:
                plans[key] = split
    skipped = (
        {
            str(row.account_id)
            for row in decisions.current_decisions(run)
            if row.case == "plan_instalment_due" and row.choice == decisions.CHOICE_SKIP
        }
        if plans
        else set()
    )
    return {
        "scope": scope,
        "open": payments_seam.open_positions_for_accounts(scope),
        "credit": credit,
        "totals": open_balance.locked_bill_totals_for_accounts(scope),
        "opening": customers_seam.opening_positions_for_accounts(scope),
        "whole": _whole_account_reads(run, bills, scope, credit),
        "plans": plans,
        "skipped": skipped,
    }


def _plan_held_back(reads: dict[str, Any], key: str, stands: Decimal) -> Decimal | None:
    """`DEF-BIL-8720` — what this account's bill holds back as a payment plan's
    part not yet due: `open_balance.plan_not_yet_due` over payments' split,
    the run's *Skip this month* answer, and where the account stands."""
    from apps.billing import open_balance

    held = open_balance.plan_not_yet_due(
        reads["plans"].get(key), skipped=key in reads["skipped"], stands=stands
    )
    return None if held is None else held["not_yet_due"]


#: One page of *Credit covers the bill* — the bucket above carries the count
#: of the whole run (NFR-3: a list is a page, its total is a count).
CREDIT_COVERS_PAGE = 50


def _credit_covers(bills: list[Any], positions: dict[str, Any]) -> dict[str, Any]:
    """🔒 DEF-BIL-8242 · BR-BIL-1053 — each drafted bill whose account's CREDIT
    balance covers its total in full (decision log 2026-09-30, coordinator
    judgement 4: the bill amount exists only after Calculate, so this is Sign
    off's and not Check's). Credit $500.00 against a $49.44 bill → covered,
    $450.56 left after. Ordered by account number; the first page, and the
    count of all of them."""
    rows = []
    for bill in bills:
        position = positions.get(str(bill.account_id))
        if position is None or position.open_balance is None:
            continue
        credit = -position.open_balance
        total = bill.total or ZERO
        if credit > ZERO and credit >= total:
            rows.append(
                {
                    "account_id": str(bill.account_id),
                    "account_no": None,  # filled below in ONE read
                    "bill_total": _text(total),
                    "credit": _text(credit),
                    "left_after": _text(credit - total),
                    "currency": getattr(bill, "currency", None),
                }
            )
    if rows:
        from apps.billing import check_models

        numbers = {
            str(account_id): account_no
            for account_id, account_no in check_models.BillRunAccountCheck.objects.filter(
                tenant_id=_tenant_id(),
                bill_run_id=bills[0].bill_run_id,
                account_id__in=[row["account_id"] for row in rows],
            ).values_list("account_id", "account_no")
        }
        for row in rows:
            row["account_no"] = numbers.get(row["account_id"])
    rows.sort(key=lambda row: row["account_no"] or "")
    return {"results": rows[:CREDIT_COVERS_PAGE], "count": len(rows)}


def _how_paid(
    run: Any, bills: list[Any], amounts_due: dict[str, Decimal], scope: Any
) -> dict[str, Any]:
    """How the amount due will be paid — each bill in exactly ONE row, in this
    order, so the rows add back to the amount due: credit covers the bill ·
    level pay · autopay on the due date · a payment-plan instalment due ·
    pay by the due date. `amounts_due` is each bill's own amount due
    (`DEF-BIL-8720`: net of a plan's part not yet due); `scope` the run's
    accounts as a queryset, read as a subquery (`DEF-BIL-8696`)."""
    from apps.billing import gather, selectors

    level_pay = {
        str(a)
        for a in models.AccountBudgetStatus.objects.filter(
            tenant_id=_tenant_id(), account_id__in=scope
        )
        .filter(status="enrolled")
        .values_list("account_id", flat=True)
    }
    queryset = gather._resolve("customers", "account_queryset")
    autopay = (
        {
            str(pk)
            for pk in queryset()
            .filter(pk__in=scope, autopay=True, cash_only_no_autopay=False)
            .values_list("pk", flat=True)
        }
        if queryset is not None
        else set()
    )
    plan_due: set[str] = set()
    bill_day, cycle_due_days = selectors.cycle_terms_for(run)
    bill_date = runs.effective_bill_date(run.bill_date, bill_day, run.period_end)
    due_days = runs.effective_due_days(run.due_days, cycle_due_days)
    reader = gather._resolve("payments", "instalments_due", "bill_run_checks")
    if reader is not None and bill_date is not None and due_days is not None:
        plan_due = {a for a, _c, _p in reader(scope, due_date=bill_date + timedelta(days=due_days))}
    buckets = {
        key: {"bills": 0, "amount": ZERO}
        for key in ("credit_covers", "level_pay", "autopay", "plan_instalment", "by_due_date")
    }
    for bill in bills:
        account_id = str(bill.account_id)
        amount = amounts_due[str(bill.pk)]
        if amount <= ZERO:
            key = "credit_covers"
        elif account_id in level_pay:
            key = "level_pay"
        elif account_id in autopay:
            key = "autopay"
        elif account_id in plan_due:
            key = "plan_instalment"
        else:
            key = "by_due_date"
        buckets[key]["bills"] += 1
        buckets[key]["amount"] += amount
    return {k: {"bills": v["bills"], "amount": _text(v["amount"])} for k, v in buckets.items()}


def build_sign_off_summary(run: Any) -> dict[str, Any]:
    """A8 · the whole of Sign off's figures, built NOW from the run as it stands
    — the one computation. `sign_off_summary` serves it saved while nothing it
    was built from has been written since."""
    from apps.billing import release

    bills = _bills(run)
    who = _who_is_billed(run, bills)
    usage = _usage_and_charges(run, bills)
    payments = _payments_and_balances(run, bills)
    panel = release.summary_for(run).as_payload()
    return {
        "bill_run_id": str(run.pk),
        "sent": check_store.run_is_sent(run),
        "run_summary": {
            "bills": len(bills),
            "accounts_to_bill": who["accounts"]["to_bill"],
            "this_run_charges": usage["this_run_charges"],
            "payments_applied": payments["accounts_with_payments_applied"],
            # DEF-BIL-8682 — the tile's "2,118 payments" (D1 25); null where
            # the run has no payments/credits split (see `credits_applied`).
            "payments_count": payments["payments_count"],
            "amount_due": payments["amount_due"],
        },
        "who_is_billed": {"accounts": who["accounts"], "units": who["units"]},
        "usage_and_charges": usage,
        "payments_and_balances": payments,
        "by_customer_type": [
            row for row in panel.get("by_category") or [] if row.get("axis") == "consumer_category"
        ],
        "waived": panel.get("waived") or [],
        "waived_total": panel.get("waived_total"),
        "currency": panel.get("currency"),
    }


# ══════════════════════════════════════════════════════════════════════════
# 🔒 DEF-BIL-8696 — THE SUMMARY SAVED, AND REBUILT THE MOMENT IT WOULD DIFFER
# ══════════════════════════════════════════════════════════════════════════
#
# Batched, the build above still reads every bill, line, check row and payment
# of the run: ~10 s at 40,000 accounts on a quiet machine, against S2's 2 s. So
# it is SAVED on the run (`bill_runs.sign_off_snapshot`) under the KEY of every
# row it reads (`inputs_key`), and `GET …/sign-off-summary` serves the saved
# copy only while the key is unchanged. It is the shape the PO ruled for the
# Check itself (OQ-843 re-ruled 2026-09-30, option C: *"Save results, and
# automatically re-check an account when its plan, reading, meter or payment
# changes"*): saved, and rebuilt the moment what it depends on changes.
#
# WHEN IT IS STALE — exactly when a row it is built from has been written since
# it was saved. Every one of these moves the key (`core.row_versions`: the
# count and the Σ xmin of each set below):
#
#   billing     the run's own row (its terms, its Check summary) · every bill of
#               the run and every other bill of its accounts · the run's bill
#               lines · its saved Check rows and findings · its decisions and
#               standing answers (an answer, a leave-out, a put-back) · its
#               Pending-billing rows · its release · its accounts' credit notes
#               and level-pay status
#   payments    its accounts' payments, refunds, plans and instalments, and the
#               allocations made by them or against their bills
#   customers   its accounts' rows (autopay, type) and opening buckets
#   metering    the cycle and the utility's routes, service points, units and
#               premises (`units_in_cycle`)
#
# So a re-Calculate (new draft bills and lines) and a decision change each make
# it stale — the two the defect names — and so does a payment posted while the
# run waits at Sign off, which the bills would count at Send.
#
# WHEN IT IS BUILT — at the end of every Calculate (`refresh_sign_off_snapshot`,
# from `runs.calculate_run`, in the worker), so Sign off opens on it; and on
# any read that finds the key moved, which builds, saves and serves the new one
# in that request. Where the key cannot be read (not PostgreSQL, or a module
# that publishes no key) nothing is saved and every read builds — the old
# behaviour, never a guess.
#
# NOT KEYED, stated so nobody reads it as covered: the tenancy catalogues
# (service codes, account types, areas) — utility-wide settings a bill run does
# not move. Editing one while a run waits at Sign off leaves its saved summary
# as built until anything else above is written or the run is calculated again.


#: Moves whenever `build_sign_off_summary` would answer differently over the
#: SAME rows. `DEF-BIL-8727` is the first: every sent run saved before it holds
#: a summary of 40,008 unanswered bills under a key no row will ever move, so
#: without this the fix would never reach a run that was already sent.
SUMMARY_BUILD = "build-2:DEF-BIL-8727"


def inputs_key(run: Any) -> str | None:
    """The key of every row `build_sign_off_summary` reads (see above), or None
    where it cannot be read — which means *build it*, never *unchanged*."""
    import hashlib
    import json

    from django.db.models import Q

    from apps.billing import customers_seam, gather, payments_seam
    from core import row_versions

    if not row_versions.supported():
        return None
    tenant_id = _tenant_id()
    scope = _account_scope(run)
    run_bills = models.Invoice.objects.filter(tenant_id=tenant_id, bill_run=run)
    accounts_bills = models.Invoice.objects.filter(tenant_id=tenant_id, account_id__in=scope)
    own = row_versions.keys(
        models.Invoice.objects.filter(Q(bill_run=run) | Q(account_id__in=scope), tenant_id=tenant_id),
        models.InvoiceLine.objects.filter(tenant_id=tenant_id, invoice__in=run_bills.values("pk")),
        check_models.BillRunAccountCheck.objects.filter(tenant_id=tenant_id, bill_run=run),
        check_models.BillRunFinding.objects.filter(tenant_id=tenant_id, bill_run=run),
        check_models.BillRunStandingAnswer.objects.filter(tenant_id=tenant_id, bill_run=run),
        models.BillRunDecision.objects.filter(tenant_id=tenant_id, bill_run=run),
        models.BillRunExclusion.objects.filter(tenant_id=tenant_id, bill_run=run),
        models.BillRunRelease.objects.filter(tenant_id=tenant_id, bill_run=run),
        models.CreditNote.objects.filter(tenant_id=tenant_id, account_id__in=scope),
        models.AccountBudgetStatus.objects.filter(tenant_id=tenant_id, account_id__in=scope),
    )
    # The run's own row by its COLUMNS, not its row version: saving the summary
    # writes this row, and a key that moved on its own save would never match.
    columns = [
        field.attname
        for field in models.BillRun._meta.concrete_fields
        if field.attname not in ("sign_off_snapshot", "sign_off_snapshot_key", "updated_at")
    ]
    row = models.BillRun.objects.filter(tenant_id=tenant_id, pk=run.pk).values(*columns).first()
    plant = gather._resolve("metering", "plant_key")
    parts = [
        # The BUILD's own version: a summary saved by older code is rebuilt
        # once, because no row moving is what would otherwise tell it to.
        SUMMARY_BUILD,
        own,
        json.dumps(row, sort_keys=True, default=str),
        payments_seam.activity_key_for_accounts(scope, invoice_ids=accounts_bills.values("pk")),
        customers_seam.activity_key_for_accounts(scope),
        "no-cycle" if run.cycle_id is None else (plant(run.cycle_id) if plant else None),
    ]
    if any(part is None for part in parts):
        return None
    return hashlib.sha256("|".join(parts).encode()).hexdigest()  # type: ignore[arg-type]


def _save(run: Any, summary: dict[str, Any], key: str) -> None:
    """Saved by a column UPDATE, never `run.save()`: it touches no other field
    of a run a sibling request may be writing (its Check summary, its status)."""
    models.BillRun.objects.filter(tenant_id=_tenant_id(), pk=run.pk).update(
        sign_off_snapshot=summary, sign_off_snapshot_key=key
    )


def refresh_sign_off_snapshot(run: Any) -> bool:
    """Build and save the summary now — the end of every Calculate. True when
    saved. NEVER raises: a summary that cannot be built is built again by the
    first read, and a Calculate must not fail for want of a summary."""
    from django.db import transaction

    try:
        # A SAVEPOINT, because a Calculate called inside a request's transaction
        # must not be left aborted by a failed statement here (hard-won law 14).
        with transaction.atomic():
            key = inputs_key(run)
            if key is None:
                return False
            _save(run, build_sign_off_summary(run), key)
        return True
    except Exception:  # noqa: BLE001 — the read rebuilds; Calculate's outcome stands
        logger.exception("sign off summary not saved for run %s", getattr(run, "pk", run))
        return False


def sign_off_summary(run: Any) -> dict[str, Any]:
    """A8 · `GET …/sign-off-summary` — the whole of Sign off's figures: the
    saved summary while its key still matches, else built now (and saved)."""
    key = inputs_key(run)
    if key is not None:
        saved = (
            models.BillRun.objects.filter(tenant_id=_tenant_id(), pk=run.pk)
            .values_list("sign_off_snapshot", "sign_off_snapshot_key")
            .first()
        )
        if saved is not None and saved[0] is not None and saved[1] == key:
            return saved[0]
    summary = build_sign_off_summary(run)
    if key is not None:
        from django.db import transaction

        try:
            with transaction.atomic():  # a savepoint (hard-won law 14)
                _save(run, summary, key)
        except Exception:  # noqa: BLE001 — the figures are served either way
            logger.exception("sign off summary not saved for run %s", run.pk)
    return summary


__all__ = ["build_sign_off_summary", "inputs_key", "refresh_sign_off_snapshot", "sign_off_summary"]
