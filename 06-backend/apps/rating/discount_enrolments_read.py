# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — rating's ONE THIRD of R27 Plans &
#           Discounts. Drawing read as an IMAGE (B14 rule 42): p060–p061.
# Rules:    `BR-REP-040` (a k-way merge of three SQL-sorted, SQL-limited
#           streams) · `NFR-3` · `NFR-5` · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 2 (percentages stored 6dp, DISPLAY 2) · hard
#           rule 4 (this file writes nothing) · B1 (rating publishes ITS OWN
#           tables).
# ───────────────────────────────────────────────────────
"""**ASSISTANCE**, R27's third programme — one row per ENROLMENT.

p061 draws `Assistance · 100381 · Alvarez, R. · 01/07/2026 · Low-income · 20% ·
— · — · Review due`. So the TERMS cell for this programme is a PERCENTAGE and
not a month count, and INSTALMENT and REMAINING are em-dashes by right: an
assistance discount reduces a bill, it is not a thing an account pays down.

⚠ **THE PERCENTAGE IS THE ACTIVE VERSION'S AND NOT THE DISCOUNT'S.** A discount's
identity and its VALUE are two tables on purpose — `DiscountVersion` carries
`discount_type` and `value` — so a subsidy that moved from 20% to 25% has two
versions and one code. Reading the value off the discount would be reading a
column that is not there; reading the LATEST version regardless of status would
print a `draft` figure nobody approved at a customer.

⚠ **A FIXED-AMOUNT DISCOUNT SERVES ITS PERCENTAGE AS NULL AND NOT AS ZERO**
(`BR-REP-024`). `$8.00 off` is not `0%`, and a column that printed `0%` for it
would tell a clerk the subsidy is worthless.
"""

from __future__ import annotations

from typing import Any

from apps.rating import discounts
from core import tenancy as core_tenancy

PROGRAMME_ASSISTANCE = "assistance"

#: p061's `Status` parameter defaults to `Active`. A CURRENT enrolment is one
#: that has not ended — `ended_on IS NULL` — which is the partial unique
#: constraint's own definition (`uq_discount_enrolments_current`), read rather
#: than restated as a status string this table does not carry.
def discount_enrolments(
    *, as_of: Any = None, limit: int | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """Assistance enrolments, SORTED BY `enrolled_on` DESC and LIMITED in SQL.

    ⚠ **THE ACTIVE VERSION IS FETCHED PER DISCOUNT AND NOT PER ENROLMENT.** Five
    hundred accounts on one low-income subsidy share one version, so the version
    read is keyed on the DISCOUNT and done once for the page — the N+1 that only
    shows on the tenant nobody tested on.
    """
    rows = discounts.DiscountEnrolment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    )
    if as_of is not None:
        rows = rows.filter(enrolled_on__lte=as_of)
    if status != "all":
        rows = rows.filter(ended_on__isnull=True)
    rows = rows.select_related("account", "discount").order_by("-enrolled_on", "-id")
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    materialised = list(rows)
    values = _values_for({row.discount_id for row in materialised})
    return [_shape(row, values) for row in materialised]


def _values_for(discount_ids: set[Any]) -> dict[str, dict[str, Any]]:
    """`{discount_id: {type, value}}` for the ACTIVE version of each, in ONE query."""
    if not discount_ids:
        return {}
    found: dict[str, dict[str, Any]] = {}
    versions = discounts.DiscountVersion.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        discount_id__in=discount_ids,
        status=discounts.VERSION_ACTIVE,
    ).order_by("discount_id", "-version_no")
    for version in versions:
        key = str(version.discount_id)
        # The first row per discount is its highest active version number.
        found.setdefault(key, {"type": version.discount_type, "value": version.value})
    return found


def _shape(row: Any, values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """One enrolment in R27's own column vocabulary (p061).

    ⚠ **`status` IS THE VERIFICATION STATUS AND NOT THE ENROLMENT'S LIFE.** p061
    draws `Review due` against this row, which is `verification_status` — the
    thing a clerk acts on. Whether the enrolment has ENDED is already answered by
    its presence in the filtered set.
    """
    version = values.get(str(row.discount_id)) or {}
    percent = (
        version.get("value")
        if version.get("type") == discounts.DISCOUNT_PERCENTAGE
        else None
    )
    return {
        "programme": PROGRAMME_ASSISTANCE,
        "account": row.account.account_no,
        "account_id": str(row.account_id),
        "since": row.enrolled_on,
        "terms_months": None,
        "terms_percent": percent,
        # Em-dashes by right — see the module docstring.
        "instalment": None,
        "remaining": None,
        "currency": None,
        "status": row.verification_status,
    }
