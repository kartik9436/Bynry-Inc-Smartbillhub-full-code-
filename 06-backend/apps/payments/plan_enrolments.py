# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — payments' ONE THIRD of R27 Plans &
#           Discounts. Drawing read as an IMAGE (B14 rule 42): p060–p061.
# Rules:    `BR-REP-040` (a k-way merge of three SQL-sorted, SQL-limited
#           streams) · `NFR-3` · `NFR-5` · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 2 (money 4dp, DISPLAY 2) · hard rule 4 (this
#           file writes nothing) · B1 (payments publishes ITS OWN tables).
# ───────────────────────────────────────────────────────
"""**PAYMENT PLANS**, R27's second programme — one row per ENROLMENT.

⚠ **`remaining` IS THE UNPAID INSTALMENTS AND IS COMPUTED IN SQL.** p061 draws
`1,612.60` remaining against a `403.15` instalment on a 6-instalment plan —
exactly four unpaid instalments — and the PAYMENT PLANS tile above it reads
`$14,204.00 remaining`, which is the SUM of that column. So the tile and the
column are one figure computed one way, and the aggregate runs over the WHOLE
filtered set rather than the page.

⚠ **UNPAID IS `paid_payment IS NULL` AND NEVER A STATUS ON THE PLAN.** An
instalment records the payment that settled it; the plan's own status says
whether the AGREEMENT is live. A plan that is `active` with every instalment
paid has nothing remaining, and a report reading the status would print the
whole total against it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from apps.payments import collections_models as plans
from core import tenancy as core_tenancy

PROGRAMME_PAYMENT_PLAN = "payment_plan"

#: p061's `Status` parameter defaults to `Active`. `LIVE_PLAN_STATUSES` is
#: payments' OWN tuple — proposed, agreement-sent, active — read rather than
#: retyped, so a status added to the vocabulary reaches this report without an
#: edit here. A hand-kept copy is `DEF-REP-6937`'s exact shape.
LIVE_STATUSES: tuple[str, ...] = plans.LIVE_PLAN_STATUSES

_MONEY = DecimalField(max_digits=18, decimal_places=6)


def plan_enrolments(
    *, as_of: Any = None, limit: int | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """Payment-plan enrolments, SORTED and LIMITED in SQL, with `remaining` annotated.

    ⚠ **`remaining` IS A CORRELATED AGGREGATE AND NOT AN N+1.** One `Sum` with a
    filter over the instalment table, annotated onto the plan queryset, so a page
    of fifty plans is one query and not fifty-one. At the top of the ICP the
    difference is the whole cost of the report.
    """
    rows = plans.PaymentPlan.objects.filter(tenant_id=core_tenancy.current_tenant_id())
    if as_of is not None:
        rows = rows.filter(proposed_on__lte=as_of)
    if status != "all":
        rows = rows.filter(status__in=LIVE_STATUSES)
    rows = (
        rows.select_related("account")
        .annotate(
            remaining_amount=Coalesce(
                Sum(
                    "installments__amount",
                    filter=Q(installments__paid_payment__isnull=True),
                    output_field=_MONEY,
                ),
                Decimal("0"),
                output_field=_MONEY,
            )
        )
        .order_by("-proposed_on", "-id")
    )
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    return [_shape(row) for row in rows]


def _shape(row: Any) -> dict[str, Any]:
    """One plan in R27's own column vocabulary (p061).

    `instalment` is `total_amount − down_payment` divided by the instalment
    count — the figure a customer pays each time, which is what p061's column
    holds. It is NOT read back off one instalment row: a plan whose last
    instalment carries a rounding remainder would then report that remainder as
    *the* instalment on every screen it appears on.
    """
    count = int(row.installment_count or 0)
    financed = (row.total_amount or Decimal("0")) - (row.down_payment or Decimal("0"))
    instalment = (financed / count).quantize(Decimal("0.0001")) if count else None
    return {
        "programme": PROGRAMME_PAYMENT_PLAN,
        "account": row.account.account_no,
        "account_id": str(row.account_id),
        "since": row.signed_on or row.proposed_on,
        "terms_months": count or None,
        "terms_percent": None,
        "instalment": instalment,
        "remaining": row.remaining_amount,
        "currency": row.currency,
        "status": row.status,
    }
