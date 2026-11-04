# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 (enrolment, eligibility & the level computation) ·
#           US-BIL-019 (the budget bill: actuals monthly, variance on every
#           bill, settle-up month — the READ half) · US-BIL-020 (re-level at
#           drift, off-budget as a staff act, per-account override ±30%)
#           Screens: S30 (Budget Bills tab)
# Rules:    BR-BIL-017 (one live budget status per account; the ±30% override
#           bound is measured against the COMPUTED level; ⚠ the two-missed-
#           payments drop-off is SUPERSEDED — PO 2026-08-11) · BR-BIL-021
#           (every parameter is a tenant setting, read through the seam, never
#           defaulted) · BR-BIL-011 (the monthly posting is the ACTUALS posting
#           — the level never reaches the ledger as a price) · BR-RAT-043
#           (budget billing rides the plan flag) · BR-TEN-043 (event time is an
#           argument, never a clock) · BR-SHL-025 / BR-IDN-009 (server-enforced
#           RBAC) · BR-SHL-020 (plain language when something is absent) ·
#           CLAUDE.md rule 2 (money) · rule 7 (every money action audits)
# Golden:   ❄️ WE-8 → GT-24 (B5 FROZEN): trailing-12 $2,904 → level $242;
#           the variance walk −50.87 → −40.27 → +2.98. NOTHING HERE COMPUTES A
#           FIGURE — `apps/billing/budget.py` owns the arithmetic and
#           `budget_service.py` owns the write.
# Tests:    06-backend/tests/test_us_bil_surface_apis.py
# Impacts:  config/urls.py (the include) · apps/billing/selectors.py (the read
#           model + `budget_history_for`) · 07-frontend BudgetBillsPage
# ───────────────────────────────────────────────────────
"""`/budget-billing` — the HTTP surface for a customer on a flat monthly amount.

THIN by law (B8/LAW 0): the reads go through `selectors`, every write goes
through `budget_service`, no ORM here, no arithmetic here, and every refusal is
a catalog exception the BE-02 handler renders.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS
════════════════════════════════════════════════════════════════════════════
`budget.py` + `budget_service.py` are 60KB of finance-signed arithmetic and an
append-only event ledger, and `budget_service.enroll` **had no caller in the
product at all** — only tests. Its own trailer said so: *"S30's Budget Bills tab
has no endpoint yet; REPORTED, and the reason is that no story owns the S30
tab's API surface"*. So a utility could not put one customer on budget billing.

════════════════════════════════════════════════════════════════════════════
WHERE THE ENROLMENT'S FOUR FACTS COME FROM, AND WHY THE CALLER IS THIS FILE
════════════════════════════════════════════════════════════════════════════
`enroll` takes `trailing_actuals`, `months_of_history`, `plan_offers_budget` and
`currency` as ARGUMENTS and issues no cross-module query — the same posture
`late_fee.overdue_portion` takes with its receipts, and it is what keeps the
service testable and free of B1 violations. Somebody has to read them, and this
is the boundary that may:

  · **trailing actuals + months of history** are facts about BILLING's own
    `invoices` table, so `selectors.budget_history_for` reads them here. ISSUED
    and PAID bills only: a level computed off drafts would set what a customer
    pays for a year from numbers that can still change.
  · **currency** comes off those same bills. When the account's history carries
    TWO currencies the read reports `mixed_currency` and this route REFUSES
    rather than picking one — a level is a money figure and CLAUDE.md rule 2
    does not permit guessing its CHAR(3).
  · **`plan_offers_budget`** is BR-RAT-043's plan flag and belongs to RATING.
    Billing has no published selector for it and `rating_seam` names no callable
    that answers it. **So it is a required field on the request** rather than
    assumed true: an account enrolled on a plan that does not offer budget
    billing is a customer paying a flat amount their tariff never promised. The
    gap is REPORTED in `BUDGET_UNAVAILABLE` and raised as **OQ-237**; nothing
    here decides it.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SURFACE WILL NOT DO
════════════════════════════════════════════════════════════════════════════
  · **It never bills.** BR-BIL-011: the bill is computed as full actuals by the
    ordinary pipeline every month and the level is what the customer is ASKED to
    pay. There is no "generate budget bills" action here and there must not be
    one — a second pricing path is how two engines start disagreeing about a
    customer's money.
  · **It drops nobody automatically.** PO 2026-08-11, verbatim *"nodrop we chase
    for payments until write off"*. `remove_from_budget` is a STAFF act with a
    name on it, and this surface offers no rule-driven removal.
  · **It settles nothing up.** `budget.settle_up_gl_account` raises on OQ-142 —
    the settle-up line's ledger side is not ruled — so the figures are computed
    and recorded and the posting stops at the boundary. Reported, not stubbed
    into a route that would promise a posting.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

import calendar
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.db.models import Case, Exists, F, IntegerField, OuterRef, Sum, Value, When
from django.db.models.functions import Mod
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import (
    budget,
    budget_service,
    customers_seam,
    open_balance,
    selectors,
    settings_seam,
)
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from apps.billing.models import BUDGET_EVENT_SETTLED, AccountBudgetEvent
from core import errors
from core import tenancy as core_tenancy
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

logger = logging.getLogger(__name__)

#: Why §05 screen 25's `RE-LEVEL` column carries a month and not a drift.
#: Served on every row so a caller never has to infer the absence, and so the
#: screen can say it in one short line instead of leaving a blank cell.
#: Drift is |recomputed − current| / current (BR-BIL-017), and every figure of
#: it costs a fresh twelve-month invoice read for one account — a drift column
#: would be one such read per row and a drift KPI one per enrolled account. It
#: is a new read, not a rendering. ⚠ The rule id lives HERE and not in the
#: served sentence: G28 was red on this constant from 2026-09-14, the day it
#: landed, because a served `_unavailable` sentence is clerk-facing by
#: definition even when today's screen happens not to print it (`DEF-BIL-5339`
#: is what that costs when one does).
RELEVEL_DRIFT_ABSENT = (
    "nothing stores a recomputed level, so this screen serves the cadence a re-level is "
    "next due on and not how far the level has drifted. Every figure of drift costs a "
    "fresh twelve-month invoice read for one account; a drift column would be one such "
    "read per row and a drift KPI one per enrolled account. It is a new read, not a "
    "rendering."
)

#: What this surface cannot answer, carried on every response. The
#: `pending.PENDING_UNAVAILABLE` discipline: a caller must never have to infer
#: an absence, and a reviewer must never have to take a docstring's word.
#:
#: ⚠ **THE WORDS A CLERK READS COME FROM `message_key`, RESOLVED IN THE ELEVEN
#: CATALOGUES; `detail` IS THE ID-FREE ENGLISH MIRROR OF THAT SENTENCE AND THE
#: REASONING LIVES IN THE COMMENT BESIDE EACH ENTRY — `DEF-BIL-5339`,
#: 2026-09-15.** Until that day every `detail` here was written for the record
#: and carried its rule ids, its open-question ids and two Python identifiers,
#: and `GapNotes` printed it unchanged at `/:tenant/billing/budget` for four
#: weeks. B14 rule 32 keeps a rule id and an internal code out of clerk-facing
#: copy; rule 33 says rationale is ZERO words on screen; and the 2026-08-19
#: ruling (`DEF-322`) says a served sentence's words come from the catalogue
#: entry for its `message_key` and from nothing else. G32 reads these keys off
#: the dict literal and fails one that does not resolve; G33 caps each at six
#: words a sentence; `tests/test_def_bil_5339_clerk_facing_copy.py` ties every
#: `detail` to its `en` sentence so the two cannot drift, and refuses an id in
#: either. `br_ref` is the MACHINE field that keeps the rule for support —
#: rendered on `data-br-ref`, never as text — and it is where the ids belong.
#: `OQ-237` and `OQ-142` are still OPEN; only where their citation sits moved.
BUDGET_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # BR-RAT-043 puts budget-billing eligibility on the rate PLAN and rating
    # publishes no selector that answers "does this account's plan offer budget
    # billing?". `budget_service.enroll` therefore takes it as an argument and
    # the enrol route requires it on the request rather than assuming true — an
    # account enrolled on a plan that does not offer budget billing is a
    # customer paying a flat amount their tariff never promised. OQ-237 asks
    # the PO where that flag is read from; the enrol form asks the clerk to
    # confirm it in the meantime, which is what the sentence points at.
    {
        "code": "plan_budget_flag_is_a_caller_fact",
        "br_ref": "BR-RAT-043 · OQ-237",
        "message_key": "billing.budget.gap.planFlag",
        "detail": "Plan eligibility is not shown here. Confirm it when enrolling.",
    },
    # The settle-up month's figure is computed and recorded, and its GL
    # account is OPEN (OQ-142) — `budget.settle_up_gl_account` raises. So no
    # settle-up posts through this surface and no route promises one. The
    # amount and its direction are still shown on the bill, because the
    # customer needs to know.
    {
        "code": "settle_up_has_no_ledger_side",
        "br_ref": "BR-BIL-011 · OQ-142",
        "message_key": "billing.budget.gap.settleUpNotPosted",
        "detail": "Settle-up amounts are shown, not posted.",
    },
    # The prototype's step 1 offers "All eligible residential (312)" and
    # "Import list from CSV". Neither ships: enrolment sets what a customer pays
    # every month for a year, `enroll` refuses an account already enrolled, and
    # a bulk action over 312 accounts would need a per-account eligibility read
    # (the plan flag above) that does not exist. REPORTED rather than drawn as
    # a control that would enrol nobody or, worse, enrol everybody at a level
    # nobody checked (BR-BIL-017 · BR-BIL-060).
    {
        "code": "no_bulk_enrolment",
        "br_ref": "BR-BIL-017 · BR-BIL-060",
        "message_key": "billing.budget.gap.oneAtATime",
        # `DEF-BIL-8721` — American English, the catalogue's own words since
        # DEF-SHL-6351 (2026-09-23); the API and the screen say one sentence.
        "detail": "Enroll accounts one at a time. No list import.",
    },
    # BR-BIL-017's automatic two-missed-payments drop-off is SUPERSEDED (PO
    # 2026-08-11, verbatim *"nodrop we chase for payments until write off"*).
    # Nothing in this product removes an account because it fell behind; an
    # account in arrears is chased through collections and stays on its level
    # while that happens. The only way off is the staff act this surface serves.
    {
        "code": "drop_off_rule_is_superseded",
        "br_ref": "BR-BIL-017",
        "message_key": "billing.budget.gap.noAutoRemoval",
        "detail": "Nobody leaves budget billing automatically.",
    },
)

#: `parameters_unavailable` on the enrollments list, in the SAME shape as a
#: `BUDGET_UNAVAILABLE` entry (`DEF-BIL-5339`). It used to be
#: `str(BillingConfigError)` — the settings seam's own refusal, which names a
#: dotted module path and BR-BIL-017 — and the tab printed it under the list
#: title. The seam's sentence is right for the LOG and is still logged; a clerk
#: reads the catalogue sentence for `message_key`. Served only when tenancy's
#: settings read is not published (BR-BIL-021: never the seeded defaults, which
#: would print figures no tenant chose).
BUDGET_PARAMETERS_UNREADABLE: dict[str, Any] = {
    "code": "budget_parameters_unreadable",
    "br_ref": "BR-BIL-017 · BR-BIL-021",
    "message_key": "billing.budget.gap.parametersUnreadable",
    "detail": "Budget settings could not be read.",
}


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id from the session user,
    ROLE SERVER-ATTACHED by the identity layer (BE-04), never client input.

    The services behind this surface read `actor.role` (BR-BIL-027's publish
    right) and `actor.id` (`core.audit.money_action`, hard rule 7). Handing them
    the bare Django `User` gives them an object with no role, and a service that
    cannot resolve a role refuses — which is the right default and the wrong
    outcome for a request the permission layer has already authorised. The same
    shim `apps/tenancy/api.py` uses, for the same reason.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="billing.payload_not_object")
    return data


def _date_field(payload: dict[str, Any], name: str) -> date:
    """A REQUIRED business date from the caller — BR-TEN-043, gate G6. No clock.

    An enrolment stamps `enrolled_on` and a re-level stamps `last_leveled_at`,
    and both gate future behaviour: the cadence check counts whole months from
    the stamp. A server clock here would let a request from another timezone
    move a customer's next re-level by a day.
    """
    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.ops.date_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.date_format",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _money_field(payload: dict[str, Any], name: str) -> Decimal:
    """A money argument as a STRING → Decimal. A JSON float is REFUSED.

    CLAUDE.md rule 2. By the time a JSON number reaches this function it is an
    IEEE double; an override of 200.10 would arrive as 200.09999999999999 and be
    stored to six places as exactly that. The refusal names the field.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.budget.amount_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.money_string",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.money_string",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _refusal(broken: Exception, default_br_ref: str) -> errors.BizError:
    """A service refusal, as the ONE catalog exception G9 allows — the sentence
    travels in `params.detail` for the audit row and the log:
    *"account … cannot be enrolled: it has 9 months of billing history and the
    tenant requires 12"* is what support reads when a clerk calls.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.

    The clerk reads `billing.budget.refused`: *"This account can't be put on
    budget billing as asked. Check its billing history and settings."*
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(broken, "br_ref", None) or default_br_ref,
        message_key="billing.budget.refused",
        params={"detail": str(broken)},
    )


def _status_dict(
    status: Any,
    *,
    actuals: dict[Any, tuple[str, int]] | None = None,
    cadence_months: int | None = None,
) -> dict[str, Any]:
    row = selectors.budget_status_row(
        status, effective_level=budget_service.effective_level(status)
    )
    row.update(_relevel_fields(status, cadence_months=cadence_months))
    if actuals is not None:
        # ⚠ ABSENT, NEVER `0.00`. An account enrolled this week has had no bill
        # yet, so the meter has said nothing — which is a different statement
        # from "the meter said zero", and the drawn column renders the dash.
        total, months = actuals.get(status.pk, (None, 0))
        row["actual_to_date"] = total
        row["actual_months"] = months
    return row


def _as_of(request: Any) -> date:
    """§05 entry 25.2's horizon: the date the forecast is taken from.

    An ARGUMENT with today as its default, and it decides exactly one thing —
    which occurrence of each account's settle-up month comes next. A malformed
    one is REFUSED rather than silently falling back to today: a caller that
    meant to stand at a fixed date and mistyped it would otherwise get a
    different forecast with no sign that its argument was ignored, which is the
    silently-ignored-flag shape hard-won law 14 closes with.
    """
    raw = str(request.query_params.get("as_of") or "").strip()
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        # The SAME key `_date_field` uses two hundred lines up — *"Use a date
        # like 2026-08-16."* One question, one answer (hard-won law 5); a
        # second key saying the same thing in eleven catalogues is how two
        # sentences for one refusal start to drift.
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="billing.ops.date_format"
        ) from None


def _int_param(request: Any, name: str, *, low: int, high: int) -> int | None:
    """A bounded integer filter, or None. Out of range is None, not a refusal:
    a month filter is a screen control and an unknown value means *no filter*."""
    try:
        value = int(str(request.query_params.get(name) or ""))
    except (TypeError, ValueError):
        return None
    return value if low <= value <= high else None


def _forecast_row(status: Any, *, window: dict[str, Any] | None, as_of: date) -> dict[str, Any]:
    """One row of §05 entry 25.2's table — every figure a string this server computed.

    `settles_in_year` is projected from `months_away`, which SQL has already
    computed and ordered on, so the year on screen and the order of the rows
    cannot disagree.

    ⚠ **THE TWO SUMS ARE ABSENT, NEVER `0.00`, when the account has had no bill
    inside its current settle-up period** — an account enrolled last week, or
    one that trued up this month, has a real balance of nothing and a meter that
    has said nothing, and those read differently to a clerk.
    """
    # The identity columns come from the SAME builder the Budget Bills tab uses,
    # so `100412 / Navarro, P.` means one thing on both screens and the customer
    # name has ONE resolution (hard-won law 5). B14 rule 31 — the id travels for
    # the LINK, the NUMBER is what shows.
    identity = selectors.budget_status_row(
        status, effective_level=budget_service.effective_level(status)
    )
    settlement = budget.settle_up(balance=status.variance_balance)
    months_away = int(getattr(status, "months_away", 0) or 0)
    settles_month = int(status.settle_up_month)
    settles_year = as_of.year + ((as_of.month - 1 + months_away) // 12)
    return {
        "account_id": identity["account_id"],
        "account_no": identity["account_no"],
        "customer_name": identity["customer_name"],
        "settles_in_month": settles_month,
        "settles_in_year": settles_year,
        "months_away": months_away,
        "settles_this_month": months_away == 0,
        "paid_on_level": None if window is None else window["paid_on_level"],
        "actual_so_far": None if window is None else window["actual_so_far"],
        "months_billed": 0 if window is None else window["months"],
        # `budget.SettleUp.signed`: "+ collects, − credits" — the drawn column,
        # from the ❄️ frozen dataclass rather than negated here.
        "balance_signed": None if settlement is None else str(settlement.signed),
        "settle_up_amount": None if settlement is None else str(settlement.amount),
        "settle_up_direction": None if settlement is None else settlement.direction,
        "settle_up_taxable": budget.SETTLE_UP_TAXABLE,
        "currency": identity["currency"],
    }


def _forecast_summary(*, as_of: date) -> dict[str, Any]:
    """§05 entry 25.2's four tiles, each an SQL aggregate over the whole tenant.

    ⚠ **NOT A PYTHON FOLD.** `GET /outstandings` is CLAUDE.md's named breach of
    `NFR-3` for sorting a per-debtor list in Python on the strength of a 3,000
    connection ceiling that moved to 40,000; a tile that walked every enrolled
    account here would be the same mistake with a different name. Every figure
    below is a `count()` or an `aggregate()`.

    The two totals are POSITIVE magnitudes — the drawing's `TO COLLECT
    $1,204.60` and `TO CREDIT $318.20` — because a tile is a heading and a
    signed heading reads as an error. The SIGN lives on the row, where
    `balance_signed` carries it.
    """
    enrolled = budget_service.status_queryset().filter(status=budget.STATUS_ENROLLED)
    dated = enrolled.filter(settle_up_month__isnull=False)
    settled_this_period = AccountBudgetEvent.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        budget_status_id=OuterRef("pk"),
        event=BUDGET_EVENT_SETTLED,
        occurred_on__year=as_of.year,
        occurred_on__month=as_of.month,
    )
    this_month = dated.filter(settle_up_month=as_of.month).annotate(
        already_settled=Exists(settled_this_period)
    ).filter(already_settled=False)
    later = dated.exclude(pk__in=this_month.values("pk"))

    collecting = this_month.filter(variance_balance__lt=Decimal("0"))
    crediting = this_month.filter(variance_balance__gt=Decimal("0"))
    currencies = sorted(
        {row for row in this_month.values_list("currency", flat=True) if row}
    )
    one_currency = currencies[0] if len(currencies) == 1 else None
    collect_total = collecting.aggregate(total=Sum("variance_balance"))["total"]
    credit_total = crediting.aggregate(total=Sum("variance_balance"))["total"]
    return {
        "settling_this_month": this_month.count(),
        "settling_month": as_of.month,
        "settling_year": as_of.year,
        # `variance_balance` is NEGATIVE when the customer owes; the tile prints
        # the magnitude, which is `budget.settle_up`'s `amount` for every one of
        # these rows.
        "to_collect_amount": (
            str(-collect_total) if one_currency and collect_total is not None else None
        ),
        "to_collect_accounts": collecting.count(),
        "to_credit_amount": (
            str(credit_total) if one_currency and credit_total is not None else None
        ),
        "to_credit_accounts": crediting.count(),
        "currency": one_currency,
        "currencies": currencies,
        "later_accounts": later.count(),
        "later_months": later.values("settle_up_month").distinct().count(),
        # Enrolled, but the tenant published no settle-up month, so they never
        # true up. Counted so the screen states it rather than omitting them.
        "no_settle_month": enrolled.filter(settle_up_month__isnull=True).count(),
    }


def _relevel_cadence_months(parameters: dict[str, Any] | None) -> int | None:
    """BR-BIL-021's `relevel_cadence_months`, or None when it cannot be read.

    Never a substituted 6. `settings_seam.budget_billing` refuses rather than
    falling back for exactly this reason, and a cadence assumed here would tell
    a clerk an account is due for a re-level against a number nobody chose.
    """
    if parameters is None:
        return None
    try:
        return int(parameters["relevel_cadence_months"])
    except (KeyError, TypeError, ValueError):
        return None


def _cadence_cutoff(cadence_months: int) -> date:
    """The `last_leveled_at` on or before which an account is due by cadence."""
    today = date.today()
    total = today.month - cadence_months
    year = today.year + (total - 1) // 12
    month = (total - 1) % 12 + 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _relevel_fields(status: Any, *, cadence_months: int | None) -> dict[str, Any]:
    """§05 screen 25's `RE-LEVEL` column — THE CADENCE HALF, AND ONLY THAT.

    ⚠ **THE DRIFT HALF IS NOT SERVED, DELIBERATELY, AND THE FIELD SAYS SO.**
    The drawing puts *`Drifted 14%`* in this column and *`drifted past 10%`*
    under its KPI. `budget.relevel_due` needs BOTH gates — the cadence AND a
    drift breach — and drift is `|recomputed − current| ÷ current`, so every
    figure of it costs a fresh twelve-month invoice read PER ACCOUNT. Nothing
    stores a recomputed level, so a drift column is 50 extra queries a page and
    the KPI is one per enrolled account. That is a **new read** (a recomputed
    level persisted by `relevel`), not a rendering, and it is reported rather
    than approximated: a drift percentage computed from anything cheaper would
    be a money-adjacent figure this product cannot stand behind.

    So what is served is what is STORED: `last_leveled_at` plus the tenant's own
    cadence gives the month the account is next due, and `relevel_is_due` says
    whether that month has arrived. Both are facts; neither is an estimate of a
    drift.
    """
    if cadence_months is None or status.last_leveled_at is None:
        return {
            "relevel_due_on": None,
            "relevel_is_due": None,
            "relevel_drift_unavailable": RELEVEL_DRIFT_ABSENT,
        }
    total = status.last_leveled_at.month + cadence_months
    year = status.last_leveled_at.year + (total - 1) // 12
    month = (total - 1) % 12 + 1
    day = min(status.last_leveled_at.day, calendar.monthrange(year, month)[1])
    due_on = date(year, month, day)
    return {
        "relevel_due_on": due_on.isoformat(),
        "relevel_is_due": due_on <= date.today(),
        "relevel_drift_unavailable": RELEVEL_DRIFT_ABSENT,
    }


def _summary(*, cadence_months: int | None) -> dict[str, Any]:
    """§05 screen 25's four KPI tiles, each from a fact this product holds.

    ⚠ **THE THIRD TILE IS THE CADENCE COUNT, NOT A DRIFT COUNT** — see
    `_relevel_fields`. The drawn detail line *"drifted past 10%"* is an
    illustration of a figure this screen cannot read (B14 rule 37); what is
    counted is the accounts whose cadence has arrived, which is
    `budget.relevel_due`'s first gate and is stored.

    ⚠ **`accounts_total` AND `asks_waiting` ARE CROSS-MODULE AND GO THROUGH A
    SEAM OR NOT AT ALL.** Each is served as null WITH its reason when the
    owning module publishes no read — never as 0, which on a tile reads as
    *"nobody"* rather than *"nobody could ask"*.
    """
    enrolled = budget_service.status_queryset().filter(status=budget.STATUS_ENROLLED)
    shortfall = enrolled.exclude(variance_balance=Decimal("0"))
    currencies = sorted({row for row in shortfall.values_list("currency", flat=True) if row})
    totals = shortfall.aggregate(total=Sum("variance_balance"))
    accounts_total, accounts_absent = customers_seam.account_count()
    asks, asks_absent = customers_seam.level_pay_asks_waiting()
    due_count: int | None = None
    if cadence_months is not None:
        due_count = enrolled.filter(last_leveled_at__lte=_cadence_cutoff(cadence_months)).count()
    return {
        "enrolled": enrolled.count(),
        "accounts_total": accounts_total,
        "accounts_total_unavailable": accounts_absent,
        "shortfall_accounts": shortfall.count(),
        # ⚠ ONE CURRENCY OR NONE (CLAUDE.md rule 2). A tenant whose enrolled
        # accounts carry two currencies gets the COUNT and no total: adding
        # 100 USD to 100 CAD is not 200 of anything, and a tile is the last
        # place to invent an exchange rate.
        "shortfall_amount": (
            str(totals["total"]) if len(currencies) == 1 and totals["total"] is not None else None
        ),
        "shortfall_currency": currencies[0] if len(currencies) == 1 else None,
        "shortfall_currencies": currencies,
        "relevel_due": due_count,
        "relevel_cadence_months": cadence_months,
        "asks_waiting": asks,
        "asks_waiting_unavailable": asks_absent,
    }


def _account_or_refuse(account_id: str) -> Any:
    """The account's LIVE budget status, or the refusal that names why not."""
    status = budget_service.status_for(account_id)
    if status is None:
        raise errors.NotFoundError()
    return status


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Reads & Billing runs — Executive View
def budget_enrollments(request: Any) -> Response:
    """S30's Budget Bills tab — every account on the programme.

    Serves the accounts, not a summary: a "312 enrolled" chip with no rows is
    the shape a clerk cannot work from, and every figure here is per-account.

    `parameters` carries the tenant's own S69 settings (BR-BIL-021) so the
    screen can say *"we average 12 months and true up in month 12"* in the
    tenant's numbers rather than in a hardcoded sentence. When those settings
    have not been published the block is served as null WITH the reason — never
    as the ratified defaults, which would print figures no tenant chose.

    ⚠ **THE REASON IS `BUDGET_PARAMETERS_UNREADABLE`, A GAP IN THE SAME SHAPE
    AS `unavailable[]`, AND NOT THE SEAM'S SENTENCE (`DEF-BIL-5339`).** Until
    2026-09-15 this served `str(BillingConfigError)` — *"apps.tenancy.selectors
    .settings_family is not published … (BR-BIL-017) …"* — and the tab printed
    it at a clerk. The seam's sentence is the engineer's and goes to the log.
    """
    require_tenant(request)
    try:
        parameters = dict(settings_seam.budget_billing())
        parameters_absent: dict[str, Any] | None = None
    except BillingConfigError as unreadable:
        logger.warning("budget parameters unreadable: %s", unreadable)
        parameters, parameters_absent = None, dict(BUDGET_PARAMETERS_UNREADABLE)

    paginator = StandardPagination()
    # `select_related("account")` because DEF-3158's fix puts the account's own
    # NUMBER in the first column (B14 rule 31 — never the database id), and a
    # lazy FK read per row is 50 extra queries on a 50-row page.
    queryset = (
        budget_service.status_queryset().select_related("account").order_by("-created_at", "-id")
    )
    if str(request.query_params.get("f.status") or "") in budget.STATUSES:
        queryset = queryset.filter(status=request.query_params["f.status"])
    cadence = _relevel_cadence_months(parameters)
    # §05 screen 25's `Re-level due` chip. It filters on the CADENCE, which is
    # the first of `budget.relevel_due`'s two gates and the only one this screen
    # can read — see `_relevel_fields` for why the drift half is not served.
    if str(request.query_params.get("f.relevel") or "") == "due" and cadence is not None:
        queryset = queryset.filter(last_leveled_at__lte=_cadence_cutoff(cadence))
    term = str(request.query_params.get("q") or "").strip()
    if term:
        queryset = selectors.budget_apply_search(queryset, term)
    page = paginator.paginate_queryset(queryset, request)
    rows = list(page or [])
    actuals = selectors.budget_actuals_to_date([row.pk for row in rows])
    response = paginator.get_paginated_response(
        [_status_dict(row, actuals=actuals, cadence_months=cadence) for row in rows]
    )
    response.data["parameters"] = parameters
    response.data["parameters_unavailable"] = parameters_absent
    response.data["statuses"] = list(budget.STATUSES)
    response.data["summary"] = _summary(cadence_months=cadence)
    response.data["unavailable"] = [dict(entry) for entry in BUDGET_UNAVAILABLE]
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def budget_eligibility(request: Any, account_id: str) -> Response:
    """*"What would this customer's flat monthly amount be?"* — READ ONLY.

    The prototype's step 2 shows the clerk the number before they commit
    ("Last 12mo total → New flat monthly"), and this is that read. It writes
    nothing: no status row, no event, no audit row. A clerk who opens it and
    walks away has enrolled nobody.

    ⚠ **IT DOES NOT ANSWER THE PLAN QUESTION AND SAYS SO.** `eligible` is null
    when `plan_offers_budget` is not supplied on the query, because BR-RAT-043
    puts that flag on the rate plan and nothing publishes it (OQ-237). A `true`
    here would be this route deciding a rule it does not own; a `false` would
    refuse customers who qualify. So the two halves it CAN answer — the history
    length and the computed level — are answered, and the third is named.
    """
    require_tenant(request)
    history = selectors.budget_history_for(
        account_id, months=_months_setting(default_when_unreadable=None) or 12
    )
    required_months, required_absent = _required_months()
    if history["mixed_currency"]:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-017",
            message_key="billing.budget.refused",
            params={
                "detail": (
                    f"account {account_id} has been billed in more than one currency, so a "
                    "single monthly level cannot be computed for it. A level is a money "
                    "figure and every money figure carries exactly one CHAR(3) "
                    "(CLAUDE.md rule 2) — picking one of the two would be this product "
                    "choosing which of a customer's currencies they pay in."
                )
            },
        )

    level: str | None = None
    level_absent: str | None = None
    if required_months is None:
        level_absent = required_absent
    elif history["months_of_history"] < required_months:
        level_absent = (
            f"this account has {history['months_of_history']} month(s) of issued billing "
            f"history and the tenant's budget-billing settings require {required_months}. "
            "No level is computed, because averaging over a short history would set what "
            "the customer pays for a year off a season rather than a year."
        )
    else:
        try:
            computed = budget.compute_level(
                trailing_actuals=tuple(Decimal(value) for value in history["actuals"]),
                months=required_months,
                rounding=str(settings_seam.budget_billing()["level_rounding"]),
            )
            level = str(computed)
        except (BillingRuleError, BillingConfigError, KeyError) as unreadable:
            level_absent = str(unreadable)

    return Response(
        {
            "account_id": str(account_id),
            "months_of_history": history["months_of_history"],
            "bills_read": history["bills_read"],
            "trailing_actuals": history["actuals"],
            # The CURRENCY of every figure on this response. Null when the
            # account has never been billed — never "USD", which would be this
            # module inventing a tenant's currency.
            "currency": history["currency"],
            "required_months": required_months,
            "required_months_unavailable": required_absent,
            # THE COMPUTED LEVEL, or the reason there is none. Never 0.00: a zero
            # monthly amount is a real, chooseable figure and would read as "this
            # customer pays nothing".
            "computed_level": level,
            "computed_level_unavailable": level_absent,
            # OQ-237 — the half this route may not answer. Explicitly null.
            "eligible": None,
            "eligible_unavailable": (
                "BR-RAT-043 puts budget-billing eligibility on the rate PLAN and no "
                "endpoint publishes that flag (OQ-237). The enrolment request carries it."
            ),
            "already_enrolled": budget_service.status_for(account_id) is not None,
            # CR-044 §2.5 — WHAT THIS CUSTOMER ALREADY OWES, beside the level.
            #
            # It is not decoration. Enrolling an account that is $450.00 in
            # arrears at a $242.00 level is a decision a clerk should make
            # KNOWING, because the level does not touch the arrears: the
            # customer carries both, and the variance balance the programme
            # opens is a third figure again.
            #
            # ⚠ `None` IS NOT `0.00` on any of these. Zero means the customer
            # owes nothing from before; None means nobody could ask, and the
            # screen renders a dash with `open_balance_problems` as the reason.
            # A `0.00` on an unreachable seam would tell a clerk that a
            # customer in arrears is square — the defect BR-BIL-160 was written
            # for, one screen earlier in the same flow.
            **_open_balance_fields(account_id),
            "unavailable": [dict(entry) for entry in BUDGET_UNAVAILABLE],
        }
    )


def _open_balance_fields(account_id: str) -> dict[str, Any]:
    """CR-044 §4 — the shared reader, rendered as this response's own fields.

    The SAME figure the customer's bill prints, because it is computed by the
    same seam from the same three records (`apps/billing/open_balance.py` states
    why at length). Money travels as a STRING at the column's own scale, never
    as a float — a Decimal in JSON comes back a float and rule 2 forbids it.
    """
    position = open_balance.open_balance_for_account(account_id)
    return {
        "open_balance": None if position.open_balance is None else str(position.open_balance),
        # CLAUDE.md rule 2 — the amount's OWN currency, not the response's
        # `currency` field. They differ on exactly the account this figure was
        # built for: one migrated in owing money has never been billed, so
        # `currency` above (the BILLED currency) is null while the arrears
        # figure is real and is denominated on its opening bucket.
        "open_balance_currency": position.currency,
        "open_balance_bills": position.bills,
        "open_balance_basis": position.basis,
        "open_balance_basis_oq": position.basis_oq,
        "open_balance_problems": [dict(entry) for entry in position.problems],
    }


def _required_months() -> tuple[int | None, str | None]:
    try:
        return int(settings_seam.budget_billing()["eligibility_months"]), None
    except (BillingConfigError, KeyError, TypeError, ValueError) as unreadable:
        return None, str(unreadable)


def _months_setting(*, default_when_unreadable: int | None) -> int | None:
    months, _ = _required_months()
    return months if months is not None else default_when_unreadable


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def budget_enroll(request: Any) -> Response:
    """US-BIL-018 — put ONE account on budget billing.

    ONE account, deliberately. The prototype offers "All eligible residential
    (312)" and a CSV import; neither is served (see `BUDGET_UNAVAILABLE`).
    Enrolment fixes what a customer pays every month for a year, and a bulk
    action over accounts whose plan flag nothing can read would enrol people at
    a level nobody looked at.

    ❄️ Worked on WE-8/GT-24: trailing-12 $2,904 → level **$242**, variance opens
    at 0.00, the settle-up month is copied from the tenant setting and one audit
    row is written. Nothing in this file computes any of that.
    """
    require_tenant(request)
    payload = _payload(request)
    account_id = payload.get("account_id")
    if not account_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.budget.account_required",
            field_errors=[{"field": "account_id", "code": errors.VAL_REQUIRED}],
        )
    if "plan_offers_budget" not in payload:
        # REQUIRED, never defaulted — see the module docstring and OQ-237.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.budget.plan_flag_required",
            field_errors=[{"field": "plan_offers_budget", "code": errors.VAL_REQUIRED}],
        )
    on_date = _date_field(payload, "on_date")
    required_months, required_absent = _required_months()
    history = selectors.budget_history_for(account_id, months=required_months or 12)
    if history["mixed_currency"] or history["currency"] is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-017",
            message_key="billing.budget.refused",
            params={
                "detail": (
                    f"account {account_id} has no single billed currency to enrol it in "
                    f"({history['bills_read']} issued bill(s) read). A monthly level is a "
                    "money amount and carries exactly one CHAR(3) (CLAUDE.md rule 2), so "
                    "there is nothing to compute one in."
                )
            },
        )
    if required_months is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-021",
            message_key="billing.budget.refused",
            params={"detail": required_absent},
        )
    try:
        status = budget_service.enroll(
            actor=_actor(request),
            account_id=account_id,
            trailing_actuals=tuple(Decimal(value) for value in history["actuals"]),
            months_of_history=history["months_of_history"],
            plan_offers_budget=bool(payload["plan_offers_budget"]),
            currency=str(history["currency"]),
            on_date=on_date,
        )
    except (BillingRuleError, BillingConfigError) as refusal:
        raise _refusal(refusal, "BR-BIL-017") from refusal
    return Response(
        {**_status_dict(status), "trailing_actuals": history["actuals"]}, status=201
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def budget_account(request: Any, account_id: str) -> Response:
    """One enrolled account: its level, its position and its whole event trail.

    The trail is the append-only `account_budget_events` ledger (US-BIL-019
    TC-6), and it is served WITH the derived balance beside the cached one so
    the screen can show them agreeing. A cache nobody checks is a second source
    of truth waiting to disagree — the service keeps `recompute_balance` for
    exactly this, and hiding it here would waste it.
    """
    require_tenant(request)
    status = _account_or_refuse(account_id)
    events = budget_service.event_queryset().filter(budget_status=status).order_by(
        "occurred_on", "created_at", "id"
    )
    return Response(
        {
            **_status_dict(status),
            "variance_balance_recomputed": str(budget_service.recompute_balance(status)),
            "events": [selectors.budget_event_row(event) for event in events],
            "unavailable": [dict(entry) for entry in BUDGET_UNAVAILABLE],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def budget_relevel(request: Any, account_id: str) -> Response:
    """US-BIL-020 — the S30 "Re-level" row action (`manual=True`).

    Manual skips the CADENCE gate and NOT the arithmetic: the level is
    recomputed from the trailing actuals exactly as the periodic job computes
    it. BR-BIL-017 allows a staff re-level with an audit row, and the row says
    `manual: true` so a later reader can tell it from a cadence run.

    A re-level that does not MOVE the level answers 200 with `changed: false`
    and the unchanged row. That is not a failure — *"we looked and it was fine"*
    is the fact J09 step 5 asks for (US-BIL-020 TC-1) — and reporting it as an
    error would train a clerk to ignore the one that matters.
    """
    require_tenant(request)
    status = _account_or_refuse(account_id)
    payload = _payload(request)
    on_date = _date_field(payload, "on_date")
    required_months, required_absent = _required_months()
    if required_months is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-021",
            message_key="billing.budget.refused",
            params={"detail": required_absent},
        )
    history = selectors.budget_history_for(account_id, months=required_months)
    try:
        moved = budget_service.relevel(
            actor=_actor(request),
            account_id=account_id,
            trailing_actuals=tuple(Decimal(value) for value in history["actuals"]),
            on_date=on_date,
            manual=True,
        )
    except (BillingRuleError, BillingConfigError) as refusal:
        raise _refusal(refusal, "BR-BIL-017") from refusal
    status.refresh_from_db()
    return Response(
        {
            **_status_dict(status),
            "changed": moved is not None,
            "trailing_actuals": history["actuals"],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def budget_override(request: Any, account_id: str) -> Response:
    """US-BIL-020 — the per-account override, bounded ±30% WITH a reason.

    ❄️ Worked (TC-3): computed 242, staff set **200** with "customer hardship
    request" → accepted, because the bound is **169.40 – 314.60**. TC-4's 150
    and 320 are both refused, and so is any override with no reason.

    The bound is measured against the COMPUTED level and never against a
    previous override — chaining them would let three 30% steps walk a level to
    twice what the trailing twelve months say, one audited row at a time. That
    is `budget.validate_override`'s guarantee and this route does not repeat it.
    """
    require_tenant(request)
    _account_or_refuse(account_id)
    payload = _payload(request)
    try:
        status = budget_service.override_level(
            actor=_actor(request),
            account_id=account_id,
            override=_money_field(payload, "override"),
            reason=payload.get("reason"),
            on_date=_date_field(payload, "on_date"),
        )
    except (BillingRuleError, BillingConfigError) as refusal:
        raise _refusal(refusal, "BR-BIL-017") from refusal
    return Response(_status_dict(status))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def budget_remove(request: Any, account_id: str) -> Response:
    """The ONLY way off the programme — a STAFF decision with a name on it.

    PO ruling 2026-08-11, verbatim *"nodrop we chase for payments until write
    off"*: BR-BIL-017's automatic drop-off is SUPERSEDED, so nothing here can be
    triggered by arrears. The variance balance is CARRIED, never dropped
    (US-BIL-020 §5), and the response says so with the figure — a customer
    coming off budget billing still owes (or is owed) that money, and a screen
    that reported "removed" with no number would let it disappear from view.
    """
    require_tenant(request)
    _account_or_refuse(account_id)
    payload = _payload(request)
    try:
        status = budget_service.remove_from_budget(
            actor=_actor(request),
            account_id=account_id,
            reason=payload.get("reason"),
            on_date=_date_field(payload, "on_date"),
        )
    except (BillingRuleError, BillingConfigError) as refusal:
        raise _refusal(refusal, "BR-BIL-017") from refusal
    return Response(
        {
            **_status_dict(status),
            "variance_balance_carried": str(status.variance_balance),
            "currency": status.currency,
        }
    )



# ═══════════════════════════════════════════════════════════════════════════
# §05 ENTRY 25.3 — `Asks from the portal` (S67)
# ═══════════════════════════════════════════════════════════════════════════
#
# The clerk's sentence the drawing opens with: *"Six people asked online to
# level their payments. Which can I do, and what were they told?"*
#
# ──────────────────────────────────────────────────────────────────────────
# WHOSE TABLE A CUSTOMER'S ASK LIVES IN — SETTLED BEFORE A LINE WAS WRITTEN
# ──────────────────────────────────────────────────────────────────────────
# **`customers.service_requests`, and billing must never own one.** The
# blueprint states the rule the product already holds (`BR-CWP-066`): *"a
# portal ask raises an ordinary service request, never a request of a new
# kind"*. A `billing.budget_ask` table would be exactly that new kind, and it
# would put a customer's words in the module that prices their water.
#
# So the path crosses TWO boundaries and writes across NEITHER:
#
#   25.4 Join  →  portal calls `customers.service_request_service
#                 .create_from_portal` — customers' own door into customers'
#                 own table (B2 §2: *the module that owns the rule owns the
#                 exception to it*). The portal writes no billing row.
#   25.3 here  →  billing READS those requests through
#                 `apps/billing/customers_seam.py`. No `import apps.customers`
#                 anywhere; the read is resolved by NAME at call time (B1, G6).
#   25.1 Enrol →  billing writes `billing.account_budget_status`. The portal
#                 never touches it.
#
# ──────────────────────────────────────────────────────────────────────────
# ⚠ AND THE QUEUE CANNOT BE FILLED TODAY — `OQ-BIL-12359`
# ──────────────────────────────────────────────────────────────────────────
# Three of the seven drawn columns have no source anywhere in the product:
#
#   · **which requests are level-pay asks.** The only marker is an English
#     sentence, and the constant that builds it lives in `apps/portal`, which
#     billing may not import. Not a bad option declined — an option billing
#     does not have.
#   · **the account it is about.** `create_from_portal` says it in its own
#     docstring: *"it links no account and changes none"* (`BR-CWP-026`,
#     CONFIRMED). Giving the ask an account REVERSES a signed rule, so it is
#     the PO's and not a lane's (law 13, first bullet).
#   · **the level the customer was shown.** Captured nowhere, by anything.
#     The drawing makes this column the whole reason the screen exists —
#     *"SR-4468: shown $112.00, correct today $119.00"* — and a queue that
#     showed only today's figure would break a promise silently.
#
# `OQ-BIL-12359` asks where those three facts are kept. Until it is answered
# the rows are WITHHELD WITH THEIR REASON and never served as an empty list:
# `[]` on this table says *six people asked and none of them qualifies*, and a
# clerk who reads that closes the tab while six customers wait.


def _asks_summary() -> dict[str, Any]:
    """The four tiles the drawing puts above the queue — three absent, one real.

    ⚠ **ONE OF FOUR IS SERVABLE AND THAT IS WORTH BEING PRECISE ABOUT.**
    `ENROLLED THIS MONTH` is billing's own row and billing's own date, so it is
    counted. The other three are all downstream of the same missing fact, so
    they carry the SAME sentence — `customers_seam._level_pay_asks_absent` —
    rather than three wordings of one absence that a reader would take for
    three different problems.

    ⚠ **AND THE DRAWN DETAIL LINE UNDER THE FOURTH TILE IS NOT SERVED.** It
    reads *"3 from the portal"*; nothing on `account_budget_status` records
    where an enrolment came from, and B14 rule 37 makes a drawn figure an
    illustration rather than a fact to build to. The tile carries its count and
    says the provenance is not held, which is the `BR-SHL-020` shape this file
    already uses for `accounts_total`.
    """
    asks, asks_absent = customers_seam.level_pay_asks_waiting()
    today = date.today()
    enrolled_this_month = (
        budget_service.status_queryset()
        .filter(status=budget.STATUS_ENROLLED, enrolled_on__gte=today.replace(day=1))
        .count()
    )
    return {
        "waiting": asks,
        "waiting_unavailable": asks_absent,
        "eligible_now": None,
        "eligible_now_unavailable": asks_absent,
        "not_eligible": None,
        "not_eligible_unavailable": asks_absent,
        "enrolled_this_month": enrolled_this_month,
        "enrolled_from_portal": None,
        "enrolled_from_portal_unavailable": (
            "nothing on an enrolment records where it came from, so the share of this "
            "month's enrolments that began as a customer's own ask is not held."
        ),
    }


#: What this screen cannot answer, in the shape `BUDGET_UNAVAILABLE` already
#: uses. ⚠ **NO ID IN `detail`, DELIBERATELY** — `GapNotes` renders `detail` as
#: text on a clerk's screen and B14 rule 32 keeps a rule id and an internal code
#: out of clerk-facing copy. Its neighbours above carry ids in that field; this
#: one does not, and the conformance record states the divergence rather than
#: quietly widening it.
ASKS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "level_pay_ask_carries_no_route_account_or_level",
        "br_ref": "BR-CWP-026 · BR-CWP-066 · OQ-BIL-12359",
        "detail": "An ask to level payments arrives as an ordinary service request, which is "
        "what keeps a customer's words out of the billing tables. It carries no route, no "
        "account and no record of the amount the customer was shown, so the queue cannot be "
        "filled and no figure on it can be checked against what was promised.",
    },
    {
        "code": "eligibility_rides_a_plan_flag_billing_cannot_read",
        "br_ref": "BR-RAT-043 · OQ-237",
        "detail": "Whether a plan offers a flat monthly amount is a rate-plan setting, and "
        "nothing publishes it to this screen. A row cannot be marked eligible or not "
        "eligible here, so the decision stays with the clerk on the enrol screen.",
    },
)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Reads & Billing runs — Executive View
def budget_asks(request: Any) -> Response:
    """§05 entry 25.3 — every customer waiting for a person to put them on a level.

    ⚠ **PAGED AT THE SEAM, NOT AFTER IT** (`NFR-3`, and `DEF-PAY-4221` is what
    the alternative costs). `limit`/`offset` travel to the owning module so this
    can never become the fifth unpaginated list in the product. Nothing here
    caps a tenant and nothing declares a maximum (`NFR-5`, B6).

    ⚠ **`count` IS `null` WHILE THE ROWS ARE UNREADABLE, NOT `0`.** DRF's
    envelope wants a number and this one refuses to invent it, for the reason
    `customers_seam` gives for every other unreachable read: a zero is a claim
    about customers and a null is a claim about the product.
    """
    require_tenant(request)
    params = parse_list_params(request.query_params)
    page, rows_absent = customers_seam.level_pay_asks(
        limit=params.per, offset=(params.page - 1) * params.per
    )
    return Response(
        {
            "count": None if page is None else page.get("count"),
            "results": [] if page is None else list(page.get("rows") or []),
            "page": params.page,
            "per": params.per,
            "rows_unavailable": rows_absent,
            "summary": _asks_summary(),
            "unavailable": [dict(entry) for entry in ASKS_UNAVAILABLE],
        }
    )

@api_view(["GET"])
@permission_classes([AnyTenantRole])
def budget_settle_up_forecast(request: Any) -> Response:
    """§05 entry **25.2 `Settle-up forecast`** — READ ONLY, and it posts nothing.

    The clerk's sentence the drawing opens with: *"Who is going to be trued up,
    when, and for how much — so I can answer them before they ring?"*

    ════════════════════════════════════════════════════════════════════════
    ⚠ THERE IS NO BUTTON HERE ON PURPOSE, AND THIS IS WHERE THE REASON LIVES
    ════════════════════════════════════════════════════════════════════════
    An earlier version of the drawing offered a bulk **"Settle these 2"**. The
    blueprint withdrew it and recorded why, which is the half worth keeping:
    *"The cycle run already posts the settle-up, on the account's own bill,
    inside the same write that creates it, idempotently per invoice. A bulk
    button would have been a second writer for the same money."*
    `budget_service.record_bill` is that writer and
    `uq_budget_event_once_per_invoice` is the constraint that makes a re-draft
    return the same facts rather than moving the variance twice. So this route
    is a **GET and nothing else**, and there is no sibling POST to add later.

    B14 rule 33 keeps that paragraph OFF the screen — *"RATIONALE … is ZERO
    WORDS ON SCREEN, it belongs in the code and the register"* — which is why it
    is here, at length, rather than in the catalogue.

    ════════════════════════════════════════════════════════════════════════
    WHAT IT SERVES, AND WHY THE THREE MONEY COLUMNS TIE OUT
    ════════════════════════════════════════════════════════════════════════
    `PAID ON THE LEVEL` and `ACTUAL SO FAR` are the two sums
    `selectors.budget_settle_up_windows` takes over the account's CURRENT
    settle-up period, and `BALANCE` is the same account's `variance_balance` put
    through `budget.settle_up`. Those are not two answers to one question: a
    `billed` event's movement IS `level − actual`, so over that window
    `Σlevel − Σactual` is the balance by construction. **The browser therefore
    adds nothing** — every figure on the screen is a decimal string this route
    computed, which is the rule screen 25.1's lane applied when it refused to
    sum twelve monthly figures client-side.

    ⚠ **THE DRAWN SIGN IS `budget.SettleUp.signed`, NOT A FLIPPED CONVENTION.**
    The drawing prints `+$212.80 Collect` and `−$61.40 Credit`, and the engine's
    `variance_balance` runs the other way (❄️ WE-8: −50.87 is the month the
    customer UNDER-paid). Those are the same fact and the reconciliation was
    already written: `SettleUp.amount` is always positive, `direction` carries
    the sign, and `SettleUp.signed`'s own docstring reads *"+ collects, −
    credits"* — exactly the drawn column. So `balance_signed` is served from the
    frozen dataclass rather than negated here, and **no frozen figure moves**.

    ⚠ **AN ACCOUNT WITH NO SETTLE-UP MONTH IS NOT A ROW WITH A BLANK CELL.**
    `settle_up_month` is nullable — a tenant that has never published one
    enrols accounts without it (BR-BIL-021, never defaulted) — and such an
    account NEVER trues up. It is excluded from the rows and the tiles and
    COUNTED in `no_settle_month`, so the screen can say so in one line instead
    of printing a forecast that silently omits people.

    ⚠ **ONE CURRENCY OR NONE ON THE TILES** (CLAUDE.md rule 2), which is
    `_summary`'s rule on the neighbouring screen and it carries over unchanged:
    a tenant whose settling accounts carry two currencies gets the COUNTS and no
    totals. Adding 100 USD to 100 CAD is not 200 of anything.

    `as_of` is the forecast's horizon and is a QUERY ARGUMENT defaulting to
    today. It decides one thing only — which occurrence of each account's month
    comes next — and having it on the request is what lets a test stand at a
    fixed date instead of freezing a clock (BR-TEN-043's posture for a read).
    """
    require_tenant(request)
    as_of = _as_of(request)

    # ORDER AND PAGE ARE CUT IN SQL (`NFR-3`), never in Python: `GET
    # /outstandings` is the cautionary row in CLAUDE.md for exactly this, and a
    # forecast is one row per ENROLLED account at a utility of any size.
    settled_this_period = AccountBudgetEvent.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        budget_status_id=OuterRef("pk"),
        event=BUDGET_EVENT_SETTLED,
        occurred_on__year=as_of.year,
        occurred_on__month=as_of.month,
    )
    queryset = (
        budget_service.status_queryset()
        .filter(status=budget.STATUS_ENROLLED, settle_up_month__isnull=False)
        .select_related("account")
        .annotate(
            already_settled=Exists(settled_this_period),
            raw_months_away=Mod(
                F("settle_up_month") - as_of.month + 12, Value(12), output_field=IntegerField()
            ),
        )
        .annotate(
            months_away=Case(
                # Its month is THIS month and it has already been trued up, so
                # the next one is a year out. Without this an account settles
                # twice on the tile in the weeks after its own settle-up.
                When(raw_months_away=0, already_settled=True, then=Value(12)),
                default=F("raw_months_away"),
                output_field=IntegerField(),
            )
        )
        .order_by("months_away", "account__account_no", "id")
    )

    month_filter = _int_param(request, "f.month", low=1, high=12)
    if month_filter is not None:
        queryset = queryset.filter(settle_up_month=month_filter)
    direction = str(request.query_params.get("f.direction") or "")
    if direction == budget.SETTLE_COLLECT:
        queryset = queryset.filter(variance_balance__lt=Decimal("0"))
    elif direction == budget.SETTLE_CREDIT:
        queryset = queryset.filter(variance_balance__gt=Decimal("0"))
    term = str(request.query_params.get("q") or "").strip()
    if term:
        queryset = selectors.budget_apply_search(queryset, term)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    rows = list(page or [])
    windows = selectors.budget_settle_up_windows([row.pk for row in rows])
    response = paginator.get_paginated_response(
        [_forecast_row(row, window=windows.get(row.pk), as_of=as_of) for row in rows]
    )
    response.data["as_of"] = as_of.isoformat()
    response.data["directions"] = [budget.SETTLE_COLLECT, budget.SETTLE_CREDIT]
    response.data["summary"] = _forecast_summary(as_of=as_of)
    response.data["unavailable"] = [dict(entry) for entry in BUDGET_UNAVAILABLE]
    return response


urlpatterns = [
    # ORDER IS LOAD-BEARING: `budget-billing/enrollments` is all-static and MUST
    # be declared above `budget-billing/<str:account_id>`, or the word
    # "enrollments" resolves as an account id and the enrol POST 404s.
    # `settle-up-forecast` is the same hazard and its test asserts the address.
    path("budget-billing", budget_enrollments),
    path("budget-billing/enrollments", budget_enroll),
    # `asks` is all-static and MUST stay above `<str:account_id>` for the same
    # reason `enrollments` does, or the word resolves as an account id and the
    # queue 404s. §05 entry 25.3.
    path("budget-billing/asks", budget_asks),
    path("budget-billing/settle-up-forecast", budget_settle_up_forecast),
    path("budget-billing/<str:account_id>", budget_account),
    path("budget-billing/<str:account_id>/eligibility", budget_eligibility),
    path("budget-billing/<str:account_id>/relevel", budget_relevel),
    path("budget-billing/<str:account_id>/override", budget_override),
    path("budget-billing/<str:account_id>/remove", budget_remove),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@b3f81d0 (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-05-budget-billing.md — US-BIL-018 + US-BIL-019 + US-BIL-020 — · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-011/017/021 · 04-docs/05-modules/07-billing/08-worked-examples.md WE-8; so a later change to any of them makes this stamp findable as stale in one grep. Co-packets US-BIL-019, US-BIL-020, same three sources)
# generated: 2026-08-16 by story-coder (billing SURFACE lane — the endpoint budget_service.py's own trailer recorded as owned by no story)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_bil_surface_apis.py could not resolve `/budget-billing` through the root URLconf before this file was included, and the mixed-currency refusal was shown to fail before it went in. Both quoted verbatim in the lane report. pytest✔ · run_gates✔ · golden 33/33✔
# exceptions: E3 `plan_offers_budget` is a REQUIRED request field, not an assumption: BR-RAT-043 puts it on the rate plan, rating publishes no selector for it, and enrolling on a default of `true` would put customers on a flat amount their tariff never promised. Raised as OQ-237 · E3 an account whose issued bills carry TWO currencies is REFUSED rather than enrolled on one of them (rule 2) · E3 no bulk enrolment and no CSV import — the prototype draws both and neither can be served honestly without the plan flag · E3 a re-level that does not move the level answers 200 `changed: false`, not an error: "we looked and it was fine" is the fact US-BIL-020 TC-1 asks for · E3 the tenant's S69 parameters are served NULL with their reason when unpublished — never the ratified defaults, which would print figures no tenant chose · E3 a money argument arriving as a JSON float is REFUSED rather than coerced
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
