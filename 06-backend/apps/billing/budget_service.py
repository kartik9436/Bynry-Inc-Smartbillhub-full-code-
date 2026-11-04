# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 (enrolment, eligibility, the level computation) ·
#           US-BIL-019 (the budget bill: variance on every bill, settle-up) ·
#           US-BIL-020 (re-level at drift, per-account override ±30%)
#           Screens: S30 (Budget Bills tab) · S66/S69 (the parameter rows)
# Rules:    BR-BIL-017 (⚠ two-missed-payments drop-off SUPERSEDED — PO
#           2026-08-11) · BR-BIL-021 (every parameter a tenant setting, read
#           through the seam, never defaulted here) · BR-BIL-011 (the monthly
#           posting is the ACTUALS posting; the level never reaches the ledger
#           as a price) · BR-RAT-043 (budget billing rides the plan flag) ·
#           BR-TEN-043 (event time is an argument, never a clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 7 (every
#           money action writes audit_log)
# Golden:   WE-8 → GT-24 (B5 ❄️ FROZEN): level 242; −50.87 → −40.27 → +2.98
# Tests:    06-backend/tests/test_us_bil_018_budget_enrollment.py ·
#           06-backend/tests/test_us_bil_019_budget_bill.py ·
#           06-backend/tests/test_us_bil_020_budget_maintenance.py
# Impacts:  apps/billing/models.AccountBudgetStatus / AccountBudgetEvent ·
#           apps/billing/stages/assemble_document.py (asks this what to stamp
#           on the bill) · apps/billing/selectors.py (publishes the read)
# ───────────────────────────────────────────────────────
"""Budget billing's WRITE path — the only way these two tables are written.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4 / CLAUDE.md sensitive
paths): what this module stores is what a customer is asked to pay every month
for a year. AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

The arithmetic is `apps/billing/budget.py` and none of it is repeated here.
This module does four things and no more: read the tenant's parameters through
the seam, call that arithmetic, persist the result with an append-only event
row, and write `audit_log` (hard rule 7). Every function takes its business
date as an argument (BR-TEN-043) — nothing here reads a clock.

THE BALANCE IS A DERIVATION, AND THE CACHE IS CHECKED
-----------------------------------------------------
`account_budget_status.variance_balance` is the running total of
`account_budget_events.movement`. US-BIL-019 TC-6 makes that structural rather
than conventional: the events table is append-only (migration 0013's trigger on
Postgres, this module's single write path everywhere), and `recompute_balance`
re-derives the figure from the rows so a test can assert the two agree. A cache
nobody checks is a second source of truth waiting to disagree.

WHAT THIS MODULE DOES NOT DO, DELIBERATELY
-------------------------------------------
* **It never touches `invoices` or `invoice_lines`.** The bill is computed as
  full actuals by the ordinary pipeline (`runs.calculate_account` → stages
  1–6), and it stays that way: BR-BIL-011 recognises revenue and tax on the
  ACTUALS every month. There is no second pricing path here and there must
  never be one.
* **It defines no "missed payment".** PO 2026-08-11, verbatim *"nodrop we chase
  for payments until write off"* — BR-BIL-017's drop-off is SUPERSEDED and the
  undefined miss it depended on is MOOT. `remove_from_budget` exists because a
  human can still take an account off the programme from S30; nothing automatic
  can.
* **It posts nothing.** The settle-up line's ledger side is OQ-142 and
  `budget.settle_up_gl_account` raises. `settle_up` computes and records the
  amount and its direction — the billing-side figures the frozen chain fixes —
  and stops at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from apps.billing import budget, models, settings_seam
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import tenancy as core_tenancy
from core import money

ZERO = Decimal("0")


class BudgetRuleError(BillingRuleError):
    """A budget rule refused. Same catalog shape as every other billing refusal."""


@dataclass(frozen=True)
class BudgetBillFacts:
    """The three columns WE-8 puts on EVERY budget bill, plus what is due.

    This is the payload `assemble_document` stamps and the document renders:
    *"the bill shows three columns — actual, level, variance movement — and the
    running variance balance on every bill"* (US-BIL-019 §1).

    `amount_due` is the PO's ruling of 2026-08-11 made into a fact a screen and
    an aging calculation can both read: **the level is what is due**.
    """

    level: Decimal
    actual: Decimal
    variance_movement: Decimal
    running_balance: Decimal
    amount_due: Decimal
    currency: str
    settle_up_direction: str | None = None
    settle_up_amount: Decimal | None = None

    def as_payload(self) -> dict[str, Any]:
        """The `bill_payload["budget"]` block — strings, so a reprint in 2031
        renders exactly what was stamped (the `custom_snapshot` reasoning:
        money that travels as a string cannot be re-rounded downstream)."""
        block = {
            "level": str(self.level),
            "actual": str(self.actual),
            "variance_movement": str(self.variance_movement),
            "variance_balance": str(self.running_balance),
            "amount_due": str(self.amount_due),
            "currency": self.currency,
        }
        if self.settle_up_direction is not None:
            block["settle_up"] = {
                "direction": self.settle_up_direction,
                "amount": str(self.settle_up_amount),
                # B4.2 / WE-8 — never revenue, never taxed. Stamped on the bill
                # so the document itself states the class, and US-BIL-019 TC-5's
                # "forged as taxable" has something to be false against.
                "taxable": budget.SETTLE_UP_TAXABLE,
                "class": "ar_timing",
            }
        return block


# ── tenant parameters (BR-BIL-021 — read, never defaulted) ──────────────────
def _params() -> dict[str, Any]:
    """The S69 budget-billing settings for THIS tenant.

    Read through `settings_seam`, which refuses rather than falling back: an
    unreachable `eligibility_months` is not twelve, and an unreachable
    `override_bound_pct` is not thirty. Both would let through a change to a
    customer's monthly amount that the tenant's own settings forbid — the exact
    reasoning `settings_seam.finance_controls` records for the finance page.
    """
    return settings_seam.budget_billing()


def _param(key: str) -> Any:
    values = _params()
    if key not in values:
        raise BudgetRuleError(
            f"the tenant's budget-billing settings carry no {key!r}. The ratified "
            "default lives once, in apps.tenancy.settings_families.BUDGET_BILLING, "
            "and is merged in by tenancy's own read — a default substituted here "
            "would be a second copy of a BR-BIL-017 figure, free to drift from the "
            "one the tenant's S69 screen shows."
        )
    return values[key]


def _decimal_param(key: str) -> Decimal:
    raw = _param(key)
    return raw if isinstance(raw, Decimal) else Decimal(str(raw))


# ── reads ───────────────────────────────────────────────────────────────────
def status_queryset():
    """Tenant-scoped, always. CLAUDE.md rule 1 — the explicit filter, with RLS
    FORCE as the second and independent guarantee."""
    return models.AccountBudgetStatus.objects.filter(tenant_id=core_tenancy.current_tenant_id())


def event_queryset():
    return models.AccountBudgetEvent.objects.filter(tenant_id=core_tenancy.current_tenant_id())


def status_for(account_id: Any) -> models.AccountBudgetStatus | None:
    """This account's LIVE budget status, or None if it is not on the programme."""
    return (
        status_queryset()
        .filter(account_id=account_id, status=budget.STATUS_ENROLLED)
        .order_by("-created_at")
        .first()
    )


def effective_level(status: models.AccountBudgetStatus) -> Decimal:
    """What the customer actually pays: the override if there is one, else the
    computed level. BR-BIL-017 (OQ-068) keeps BOTH — the ±30% bound is measured
    against the computed one, so overwriting it would make the next override
    unvalidatable."""
    return status.level_override if status.level_override is not None else status.level


def recompute_balance(status: models.AccountBudgetStatus) -> Decimal:
    """The variance balance DERIVED from the append-only events (TC-6).

    The value `status.variance_balance` caches. Kept as a function rather than
    left implicit so a test can assert the two agree, and so a support question
    ("where did this balance come from?") has an answer that is a query.
    """
    total = event_queryset().filter(budget_status=status).aggregate(total=Sum("movement"))["total"]
    return money.finalize(total if total is not None else ZERO)


# ── the write path ──────────────────────────────────────────────────────────
def _record_event(
    *,
    status: models.AccountBudgetStatus,
    event: str,
    occurred_on: date,
    movement: Decimal = ZERO,
    level: Decimal | None = None,
    actual: Decimal | None = None,
    reason: str | None = None,
    actor: Any = None,
    invoice: Any = None,
) -> models.AccountBudgetEvent:
    """Append one event and move the cached balance to match it.

    THE ONLY WRITER of `account_budget_events`, which is what makes the
    append-only guarantee reachable on SQLite as well as on Postgres (migration
    0013 installs the trigger; the developer database has no triggers, and a
    guarantee that only holds on one of the two databases is hard-won law 1).
    """
    movement = money.finalize(movement)
    balance_after = money.finalize(status.variance_balance + movement)
    row = models.AccountBudgetEvent.objects.create(
        tenant_id=status.tenant_id,
        budget_status=status,
        account_id=status.account_id,
        invoice=invoice,
        event=event,
        level=level,
        actual=actual,
        movement=movement,
        balance_after=balance_after,
        currency=status.currency,
        reason=reason,
        # The actor arrives as the permission layer's namespace (id + role +
        # user), not as a `User` row. The FK is set by id rather than by
        # assignment, which would refuse the namespace, and the id is resolved
        # by `core.audit.actor_user_id` — the ONE answer to that question
        # (DEF-BIL-5090). It was correct here and duplicated, which is how the
        # broken copy three files away went unnoticed.
        actor_id=audit.actor_user_id(actor),
        occurred_on=occurred_on,
    )
    status.variance_balance = balance_after
    status.save(update_fields=["variance_balance", "updated_at"])
    return row


@transaction.atomic
def enroll(
    *,
    actor: Any,
    account_id: Any,
    trailing_actuals: tuple[Decimal, ...],
    months_of_history: int,
    plan_offers_budget: bool,
    currency: str,
    on_date: date,
) -> models.AccountBudgetStatus:
    """US-BIL-018 — enrol one account and compute its level.

    ❄️ WE-8/GT-24: trailing-12 $2,904 → level **$242**, variance opens at 0.00,
    settle-up month copied from the tenant setting, one audit row.

    `on_date` is the enrolment's BUSINESS date and is an argument (BR-TEN-043);
    `plan_offers_budget` and `months_of_history` are facts the CALLER read from
    rating and billing respectively — this module issues no cross-module query,
    the same posture `late_fee.overdue_portion` takes with its receipts.
    """
    required_months = int(_param("eligibility_months"))
    verdict = budget.eligibility(
        months_of_history=months_of_history,
        required_months=required_months,
        plan_offers_budget=plan_offers_budget,
    )
    if not verdict.eligible:
        raise BudgetRuleError(
            f"account {account_id} cannot be enrolled on budget billing: "
            f"{verdict.detail} ({verdict.reason}, BR-BIL-017/BR-RAT-043)."
        )
    if status_for(account_id) is not None:
        raise BudgetRuleError(
            f"account {account_id} is already on budget billing. One live budget "
            "status per account (BR-BIL-017) — a second would give the account two "
            "levels and no rule for which one is charged."
        )

    level = budget.compute_level(
        trailing_actuals=trailing_actuals,
        months=required_months,
        rounding=str(_param("level_rounding")),
    )
    settle_up_month = _param("settle_up_month")
    status = models.AccountBudgetStatus.objects.create(
        tenant_id=core_tenancy.current_tenant_id(),
        account_id=account_id,
        status=budget.STATUS_ENROLLED,
        level=level,
        currency=currency,
        variance_balance=ZERO,
        last_leveled_at=on_date,
        settle_up_month=int(settle_up_month) if settle_up_month is not None else None,
        enrolled_on=on_date,
    )
    _record_event(
        status=status,
        event=models.BUDGET_EVENT_ENROLLED,
        occurred_on=on_date,
        level=level,
        actor=actor,
    )
    audit.money_action(
        actor,
        "budget.enrolled",
        "account_budget_status",
        status.pk,
        after={
            "account_id": str(account_id),
            "level": str(level),
            "currency": currency,
            "settle_up_month": status.settle_up_month,
            "eligibility_months": required_months,
        },
    )
    return status


@transaction.atomic
def record_bill(
    *,
    account_id: Any,
    actual: Decimal,
    on_date: date,
    invoice: Any = None,
    bill_type: str = "cycle",
    actor: Any = None,
) -> BudgetBillFacts | None:
    """US-BIL-019 — one cycle bill's effect on a budget account.

    Returns None when the account is not on budget billing, which is what makes
    this safe to call from the pipeline for EVERY account: a non-budget bill is
    unchanged in every respect.

    ❄️ WE-8/GT-24, in order: Jul actual 292.87 → movement −50.87, balance
    −50.87 · Aug 231.40 → +10.60, balance −40.27 · Sep 198.75 → +43.25, balance
    **+2.98**. `amount_due` is **242.00** on every one of those bills (PO
    2026-08-11, *"Level is due"*).

    IN THE SETTLE-UP MONTH the accumulated balance is collected or credited on
    the same bill and the balance resets to 0.00 — one settle-up event, one
    audit row, and the level still due alongside it.

    IDEMPOTENT PER INVOICE. A bill run that re-drafts a bill must not move the
    variance twice; the `uq_budget_event_once_per_invoice` constraint is the
    guarantee and this is the check in front of it, so a replay returns the same
    facts rather than raising.
    """
    status = status_for(account_id)
    if status is None:
        return None

    level = effective_level(status)
    actual = money.finalize(actual)

    if invoice is not None:
        already = (
            event_queryset()
            .filter(invoice=invoice, event=models.BUDGET_EVENT_BILLED)
            .order_by("created_at")
            .first()
        )
        if already is not None:
            # A replay. Re-report what was recorded rather than moving the
            # balance a second time (hard rule 6's shape, applied to a run that
            # re-drafts a bill — BR-BIL-023).
            return _facts_from_event(status, already)

    movement = budget.variance_movement(level=level, actual=actual)
    settlement = None
    if status.settle_up_month is not None and on_date.month == status.settle_up_month:
        # The balance to true up is the position AFTER this month's movement:
        # this bill's own variance belongs to the year being settled.
        settlement = budget.settle_up(balance=money.finalize(status.variance_balance + movement))

    due = budget.amount_due(level=level, actual=actual, settlement=settlement, bill_type=bill_type)

    _record_event(
        status=status,
        event=models.BUDGET_EVENT_BILLED,
        occurred_on=on_date,
        movement=movement,
        level=level,
        actual=actual,
        invoice=invoice,
        actor=actor,
    )
    if settlement is not None:
        # The settle-up REVERSES the accumulated balance to zero, and it does so
        # as its own append-only row: "what was trued up, and when" is a
        # question the year-end asks and a reset counter cannot answer.
        _record_event(
            status=status,
            event=models.BUDGET_EVENT_SETTLED,
            occurred_on=on_date,
            # Zeroes the balance: after the BILLED row above, `variance_balance`
            # is the position being trued up, so its negation is the movement
            # that resets it to 0.00 (US-BIL-019 TC-3, "balance resets 0.00").
            movement=-status.variance_balance,
            level=level,
            actual=actual,
            invoice=invoice,
            actor=actor,
            reason=f"annual settle-up ({settlement.direction} {settlement.amount})",
        )
        audit.money_action(
            actor,
            "budget.settled",
            "account_budget_status",
            status.pk,
            after={
                "account_id": str(account_id),
                "direction": settlement.direction,
                "amount": str(settlement.amount),
                "taxable": budget.SETTLE_UP_TAXABLE,
                "class": "ar_timing",
                "balance_after": str(status.variance_balance),
            },
        )

    return BudgetBillFacts(
        level=level,
        actual=actual,
        variance_movement=movement,
        running_balance=status.variance_balance,
        amount_due=due,
        currency=status.currency,
        settle_up_direction=None if settlement is None else settlement.direction,
        settle_up_amount=None if settlement is None else settlement.amount,
    )


def _facts_from_event(
    status: models.AccountBudgetStatus, event: models.AccountBudgetEvent
) -> BudgetBillFacts:
    """Re-report a bill already recorded, from its own row (the replay path)."""
    level = event.level if event.level is not None else effective_level(status)
    actual = event.actual if event.actual is not None else ZERO
    return BudgetBillFacts(
        level=level,
        actual=actual,
        variance_movement=event.movement,
        running_balance=event.balance_after,
        amount_due=budget.amount_due(level=level, actual=actual),
        currency=event.currency,
    )


@transaction.atomic
def relevel(
    *,
    actor: Any,
    account_id: Any,
    trailing_actuals: tuple[Decimal, ...],
    on_date: date,
    manual: bool = False,
) -> models.AccountBudgetStatus | None:
    """US-BIL-020 — the periodic re-level, and the S30 row action.

    The automatic path fires ONLY at cadence and ONLY on a drift breach; both
    are tenant settings (±20% each 6 months seeded). US-BIL-020 TC-6: a forged
    mid-cadence job call is a no-op, because a re-level changes what a customer
    pays and must not be triggerable by calling a function more often.

    `manual=True` is the S30 "Re-level" row action, which BR-BIL-017 allows with
    an audit row — it skips the CADENCE gate and not the arithmetic.

    Returns the status when the level MOVED, None when it did not, so a caller
    can report "412 evaluated, 38 re-levelled" without re-reading anything.
    """
    status = status_for(account_id)
    if status is None:
        return None
    months = int(_param("eligibility_months"))
    recomputed = budget.compute_level(
        trailing_actuals=trailing_actuals,
        months=months,
        rounding=str(_param("level_rounding")),
    )
    months_since = _months_between(status.last_leveled_at, on_date)
    if not manual:
        if not budget.relevel_due(
            current_level=status.level,
            recomputed_level=recomputed,
            drift_pct=_decimal_param("relevel_drift_pct"),
            months_since_last_level=months_since,
            cadence_months=int(_param("relevel_cadence_months")),
        ):
            # Evaluated and unchanged — still stamped, because "we looked and it
            # was fine" is the fact J09 step 5 asks for (US-BIL-020 TC-1).
            status.last_leveled_at = on_date
            status.save(update_fields=["last_leveled_at", "updated_at"])
            return None

    previous = status.level
    status.level = recomputed
    status.last_leveled_at = on_date
    status.save(update_fields=["level", "last_leveled_at", "updated_at"])
    _record_event(
        status=status,
        event=models.BUDGET_EVENT_RELEVELED,
        occurred_on=on_date,
        level=recomputed,
        actor=actor,
        reason=f"re-level {previous} → {recomputed}" + (" (manual)" if manual else ""),
    )
    audit.money_action(
        actor,
        "budget.releveled",
        "account_budget_status",
        status.pk,
        before={"level": str(previous)},
        after={"level": str(recomputed), "manual": manual, "months_since_last": months_since},
    )
    return status


@transaction.atomic
def override_level(
    *,
    actor: Any,
    account_id: Any,
    override: Decimal,
    reason: str | None,
    on_date: date,
) -> models.AccountBudgetStatus:
    """US-BIL-020 — the per-account level override, bounded ±30% WITH a reason.

    Worked (TC-3): computed 242, staff set **200** with "customer hardship
    request" → accepted, because the bound is **169.40 – 314.60**. TC-4's 150
    and 320 are both refused, and so is any override with no reason.

    The bound is measured against the COMPUTED level, never against a previous
    override: chaining overrides would let three 30% steps walk a level to
    twice what the trailing twelve months say, one audited row at a time.
    """
    status = status_for(account_id)
    if status is None:
        raise BudgetRuleError(
            f"account {account_id} is not on budget billing, so its level cannot be "
            "overridden (BR-BIL-017)."
        )
    budget.validate_override(
        computed_level=status.level,
        override=money.finalize(override),
        reason=reason,
        bound_pct=_decimal_param("override_bound_pct"),
    )
    previous = status.level_override
    status.level_override = money.finalize(override)
    status.level_override_reason = reason
    status.save(update_fields=["level_override", "level_override_reason", "updated_at"])
    _record_event(
        status=status,
        event=models.BUDGET_EVENT_OVERRIDDEN,
        occurred_on=on_date,
        level=status.level_override,
        actor=actor,
        reason=reason,
    )
    audit.money_action(
        actor,
        "budget.overridden",
        "account_budget_status",
        status.pk,
        before={"level_override": None if previous is None else str(previous)},
        after={
            "computed_level": str(status.level),
            "level_override": str(status.level_override),
            "reason": reason,
        },
    )
    return status


@transaction.atomic
def remove_from_budget(
    *, actor: Any, account_id: Any, reason: str | None, on_date: date
) -> models.AccountBudgetStatus:
    """The S30 "Remove from budget" row action — a STAFF decision with a name.

    **THIS IS THE ONLY WAY OFF THE PROGRAMME.** PO ruling 2026-08-11, verbatim
    *"nodrop we chase for payments until write off"*: BR-BIL-017's automatic
    two-missed-payments drop-off is SUPERSEDED, so nothing in this product
    removes an account because it fell behind. An account in arrears is chased
    through the ordinary collections path and stays on its level while that
    happens.

    The variance balance is CARRIED, never dropped (US-BIL-020 §5: *"never
    silently dropped"*). The status row keeps its balance and its events, and
    the next actuals bill is where it is settled — which is also why removal
    does not delete anything.
    """
    status = status_for(account_id)
    if status is None:
        raise BudgetRuleError(f"account {account_id} is not on budget billing (BR-BIL-017).")
    status.status = budget.STATUS_OFF_BUDGET
    status.save(update_fields=["status", "updated_at"])
    _record_event(
        status=status,
        event=models.BUDGET_EVENT_REMOVED,
        occurred_on=on_date,
        level=effective_level(status),
        actor=actor,
        reason=reason,
    )
    audit.money_action(
        actor,
        "budget.removed",
        "account_budget_status",
        status.pk,
        before={"status": budget.STATUS_ENROLLED},
        after={
            "status": budget.STATUS_OFF_BUDGET,
            "reason": reason,
            # Stated in the trail because it is the half a reader will ask
            # about: the customer still owes (or is owed) this.
            "variance_balance_carried": str(status.variance_balance),
        },
    )
    return status


def _months_between(start: date | None, end: date) -> int:
    """Whole months from `start` to `end`, or a number large enough to pass any
    cadence when the account has never been levelled.

    A NULL `last_leveled_at` means "never levelled since enrolment", and an
    account that has never been evaluated is due one — treating the absence as
    "zero months ago" would freeze it out of every future re-level.
    """
    if start is None:
        return 10_000
    return (end.year - start.year) * 12 + (end.month - start.month)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@e9d5a48 (co-packets US-BIL-019@e9d5a48 · US-BIL-020@e9d5a48 — the four frozen sources: 04-docs/02-decisions/05-golden-tests.md · 07-billing/06-epics/EP-BIL-05-budget-billing.md · 07-billing/02-business-rules.md · 07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's Budget Bills tab has no endpoint yet; REPORTED, and the reason is that no story owns the S30 tab's API surface) E=deferred(no-frontend-half — S30 Budget Bills tab unbuilt; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) NO cross-module query. `months_of_history`, `plan_offers_budget`
#         and `trailing_actuals` are ARGUMENTS the caller read from billing and
#         rating — the `late_fee.overdue_portion` posture, and what makes every
#         figure here testable against data a test had to seed.
#         (2) The settle-up POSTING is not emitted: `budget.settle_up_gl_account`
#         raises OQ-142 and this module records the amount and direction only.
#         (3) NO drop-off path, no miss counter — PO 2026-08-11 SUPERSEDES
#         BR-BIL-017's two-miss clause; `remove_from_budget` is a staff action.
#         (4) `record_bill` is called from stage 6 for every account and returns
#         None for the ones not enrolled, so a non-budget bill is untouched.
#         (5) The S69 tenant setting `drop_off_missed_payments` still exists in
#         apps/tenancy and NOTHING reads it any more — it is dead configuration
#         as of the PO's ruling. REPORTED (DEF-063) rather than deleted from
#         another module's lane.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
