# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the reads the redesigned discount
#          screens need (CR-166 §9): the derived status, the contract fields on
#          every row, the form's lists, Plans with accounts, the Accounts tab
#          and the Audit tab.
# Rules:   NFR-3 (every list pages in SQL) · B14 rule 31 (names, never ids, on
#          screen) · hard rule 8 (an address is walked to the premises) ·
#          BR-RAT-079 (no proof document is served) · PO 2026-10-03 rulings 1–4
# Tests:   06-backend/tests/test_cr166_discounts_round2.py
# ───────────────────────────────────────────────────────
"""What the discount screens READ. Nothing here writes.

THE STATUS IS DERIVED FROM DATES, AND THERE ARE SIX
--------------------------------------------------
`draft · waiting_approval · scheduled · active · ended · retired` (CR-166 §9).
Since ruling 1 an approved version is stored `active` WITH its start date, so
*Scheduled* is not a stored state any more — it is an approved version whose
start has not arrived. One definition, two spellings that cannot drift: SQL
(`status_annotation`, which the list filters and sorts on) and the same CASE
evaluated for one row (`discount_status`).

  retired           the dated retire has passed (`retire_on` < today), or a
                    discount retired by the old dateless act
  active            an approved version is in force today
  scheduled         an approved version starts later, none is in force
  ended             approved versions exist and every one has ended
  waiting_approval  nothing approved yet, a version awaits approval
  draft             nothing approved, nothing submitted
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import (
    Case,
    CharField,
    Exists,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.rating import discount_lists
from apps.rating import discounts as discount_models
from apps.rating import models as rating_models
from apps.rating import seams
from core import tenancy as core_tenancy

STATUSES = ("draft", "waiting_approval", "scheduled", "active", "ended", "retired")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


# ── the derived status ─────────────────────────────────────────────────────
def status_annotation(today: Any) -> Case:
    """The six statuses as ONE SQL expression over `discounts` (outer ref pk)."""
    approved = discount_models.DiscountVersion.objects.filter(
        discount=OuterRef("pk"),
        status=discount_models.VERSION_ACTIVE,
        effective_from__isnull=False, tenant_id=_tenant_id(),
    )
    in_force = approved.filter(effective_from__lte=today).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    )
    pending = discount_models.DiscountVersion.objects.filter(
        discount=OuterRef("pk"), status=discount_models.VERSION_PENDING_APPROVAL, tenant_id=_tenant_id()
    )
    return Case(
        When(
            Q(retire_on__lt=today)
            | Q(status=discount_models.DISCOUNT_RETIRED, retire_on__isnull=True),
            then=Value("retired"),
        ),
        When(Exists(in_force), then=Value("active")),
        When(Exists(approved.filter(effective_from__gt=today)), then=Value("scheduled")),
        When(Exists(approved), then=Value("ended")),
        When(Exists(pending), then=Value("waiting_approval")),
        default=Value("draft"),
        output_field=CharField(),
    )


def type_annotation(today: Any) -> Coalesce:
    """The type of the version a row SHOWS — in force today, else the latest
    (`selectors.discount_version_in_force`'s rule, in SQL), so `f.type` pages
    in the database."""
    versions = discount_models.DiscountVersion.objects.filter(discount=OuterRef("pk"), tenant_id=_tenant_id())
    in_force = (
        versions.filter(
            status=discount_models.VERSION_ACTIVE,
            effective_from__isnull=False,
            effective_from__lte=today,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .order_by("-effective_from", "-version_no")
        .values("discount_type")[:1]
    )
    latest = versions.order_by("-version_no").values("discount_type")[:1]
    return Coalesce(Subquery(in_force), Subquery(latest), output_field=CharField())


def discount_status(discount: Any) -> str:
    """The derived status of ONE discount (the same CASE, one row)."""
    annotated = getattr(discount, "derived_status", None)
    if annotated:
        return annotated
    today = seams.tenant_today()
    row = (
        discount_models.Discount.objects.filter(pk=discount.pk, tenant_id=_tenant_id())
        .annotate(derived_status=status_annotation(today))
        .values_list("derived_status", flat=True)
        .first()
    )
    return row or "draft"


# ── the contract fields every row carries (CR-166 §9) ──────────────────────
def contract_fields(discount: Any, version: Any) -> dict[str, Any]:
    """`version · status · program_owner · exclusivity_group · eligibility ·
    effective_from · effective_to · offered_to · receiving · granted_this_month
    · scheduled_next` for one discount and the version it shows."""
    from apps.rating import selectors

    today = seams.tenant_today()
    eligibility = None
    if version is not None:
        eligibility = discount_lists.as_option(
            discount_models.LIST_ELIGIBILITY, version.eligibility_code
        )
        if eligibility is None and version.eligibility_summary:
            # A version saved before the list existed and not mapped (none on
            # a migrated estate): its words, honestly labelled as proof.
            eligibility = {
                "value": None,
                "label": version.eligibility_summary,
                "checked_by": discount_models.CHECKED_BY_PROOF,
            }
    upcoming = None
    if version is not None and version.effective_from is not None:
        upcoming = (
            discount_models.DiscountVersion.objects.filter(
                tenant_id=_tenant_id(),
                discount=discount,
                status=discount_models.VERSION_ACTIVE,
                effective_from__gt=max(today, version.effective_from),
            )
            .order_by("effective_from", "version_no")
            .first()
        )
    return {
        "version": version.version_no if version is not None else None,
        "status": discount_status(discount),
        "program_owner": discount_lists.as_option(
            discount_models.LIST_PROGRAM_OWNER, discount.programme_owner
        ),
        "exclusivity_group": (
            discount_lists.as_option(
                discount_models.LIST_EXCLUSIVITY_GROUP, version.exclusivity_group
            )
            if version is not None
            else None
        ),
        "eligibility": eligibility,
        "effective_from": (
            version.effective_from.isoformat()
            if version is not None and version.effective_from
            else None
        ),
        "effective_to": (
            version.effective_to.isoformat()
            if version is not None and version.effective_to
            else None
        ),
        "offered_to": offered_units(discount, today),
        "receiving": receiving_count(discount, today),
        # 🔒 DEF-2430 / DEF-BIL-5341 — WHAT ISSUED BILLS GRANTED THIS MONTH,
        # summed from `discount_grants` (written at issue since this build),
        # with its symbol (`$75.00`). It was served NULL while nothing wrote a
        # grant, because a 0 then was a figure pretending to be a fact; now a
        # $0.00 IS the record. "This month" is the month of the bill's period
        # end — the same date a grant's cap year is decided by — net of any
        # correction's reversal.
        "granted_this_month": granted_this_month(discount, today),
        "scheduled_next": (
            {
                "value_display": selectors.discount_value_display(
                    upcoming.discount_type,
                    upcoming.value,
                    selectors.discount_allowance_unit(upcoming),
                    upcoming.currency,
                ),
                "effective_from": upcoming.effective_from.isoformat(),
            }
            if upcoming is not None
            else None
        ),
    }


def _carrying_plan_ids(discount: Any, day: Any) -> Any:
    return (
        discount_models.PlanDiscountRule.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=day))
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=day))
        .values("rate_plan_id")
    )


def offered_units(discount: Any, day: Any) -> int:
    """UNITS on a plan that offers it today (the drawing's *Offered to · 75
    units on its plans*). Units, and named units, for the reason
    `selectors.discount_offered_unit_count` gives (`DEF-RAT-4664`)."""
    return rating_models.UnitPlanAssignment.objects.filter(
        tenant_id=_tenant_id(),
        rate_plan_id__in=_carrying_plan_ids(discount, day),
        assigned_from__lte=day,
    ).filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=day)).count()


def _receiving_qs(discount: Any, day: Any) -> Any:
    return discount_models.DiscountEnrolment.objects.filter(
        tenant_id=_tenant_id(), discount=discount, enrolled_on__lte=day
    ).filter(Q(ended_on__isnull=True) | Q(ended_on__gte=day))


def receiving_count(discount: Any, day: Any) -> int:
    """ACCOUNTS enrolled today (*Receiving it · 12 accounts*)."""
    return _receiving_qs(discount, day).count()


# ── GET /discounts/form-options ────────────────────────────────────────────
ENROLMENT_MODE_LABELS = (
    (discount_models.ENROLMENT_AUTOMATIC, "Automatic"),
    (discount_models.ENROLMENT_APPLY_AND_APPROVE, "Apply and approve"),
)
VERIFICATION_LABELS = (
    (discount_models.VERIFY_ONE_TIME_PROOF, "One-time proof at enrollment"),
    (discount_models.VERIFY_ANNUAL_RECERT, "Annual recertification"),
    (discount_models.VERIFY_AGENCY_FILE_MONTHLY, "Agency file, monthly"),
    (discount_models.VERIFY_AUTOMATIC, "Automatic"),
)
LAPSE_LABELS = (
    (discount_models.LAPSE_NOTIFY_THEN_DROP, "Notify, then drop the enrollment"),
    (discount_models.LAPSE_DROP_SILENTLY, "Drop the enrollment"),
    (discount_models.LAPSE_NEVER_EXPIRES, "Never expires"),
)
BUDGET_PERIOD_LABELS = (
    (discount_models.BUDGET_PERIOD_MONTHLY, "Monthly"),
    (discount_models.BUDGET_PERIOD_ANNUAL, "Annual"),
    (discount_models.BUDGET_PERIOD_LIFETIME, "Lifetime"),
)
BUDGET_OUT_LABELS = (
    (discount_models.EXHAUSTION_SUSPEND, "Suspend the discount"),
    (discount_models.EXHAUSTION_REFUSE_NEW, "Stop new enrollments"),
    (discount_models.EXHAUSTION_CONTINUE, "Keep going over budget"),
)
TYPE_LABELS = (
    (discount_models.DISCOUNT_PERCENTAGE, "Percentage"),
    (discount_models.DISCOUNT_FIXED_AMOUNT, "Fixed amount"),
    (discount_models.DISCOUNT_RATE_OVERRIDE, "Rate override"),
    (discount_models.DISCOUNT_CHARGE_WAIVER, "Charge waiver"),
    (discount_models.DISCOUNT_USAGE_ALLOWANCE, "Usage allowance"),
)
APPLIES_TO_LABELS = (
    (discount_models.SCOPE_WHOLE_BILL, "Subtotal before taxes"),
    (discount_models.SCOPE_ALL_SERVICES, "All services"),
    (discount_models.SCOPE_SPECIFIC_SERVICES, "Specific services"),
    (discount_models.SCOPE_ONE_SERVICE, "One service"),
    (discount_models.SCOPE_USAGE_ONLY, "Usage charges only"),
    (discount_models.SCOPE_BASE_ONLY, "Base charges only"),
    (discount_models.SCOPE_NAMED_CODES, "Named charge codes"),
)


def form_options() -> dict[str, Any]:
    """Every list the New discount form renders, from the server — the three
    per-utility lists (Settings › Reference data) and the fixed vocabularies —
    plus the utility's currency, which the form SHOWS and never edits."""

    def rows(pairs: Any) -> list[dict[str, str]]:
        return [{"value": value, "label": label} for value, label in pairs]

    return {
        "program_owners": discount_lists.options(discount_models.LIST_PROGRAM_OWNER),
        "exclusivity_groups": discount_lists.options(discount_models.LIST_EXCLUSIVITY_GROUP),
        "eligibility": discount_lists.options(discount_models.LIST_ELIGIBILITY),
        "enrollment_modes": rows(ENROLMENT_MODE_LABELS),
        "verification": rows(VERIFICATION_LABELS),
        "lapse": rows(LAPSE_LABELS),
        "budget_periods": rows(BUDGET_PERIOD_LABELS),
        "budget_out": rows(BUDGET_OUT_LABELS),
        "types": rows(TYPE_LABELS),
        "applies_to": rows(APPLIES_TO_LABELS),
        # Field ADDED to CR-166 §9 by task 3 (2026-10-03): where the form reads
        # the currency it shows read-only.
        "currency": seams.tenant_currency(),
    }


# ── GET /discounts/{id}/plans ──────────────────────────────────────────────
def discount_plans_queryset(discount: Any) -> Any:
    """The plans that offer it now or later (an ENDED binding is history),
    ordered by plan name — one query; the counts are per page."""
    today = seams.tenant_today()
    return (
        discount_models.PlanDiscountRule.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=today))
        .select_related("rate_plan")
        .order_by("rate_plan__name", "id")
    )


def discount_plan_rows(rules: list[Any]) -> list[dict[str, Any]]:
    """One page of plan rows with `units` and `accounts` (open accounts on
    those units) — two counts per row, on a page of at most `per` plans."""
    today = seams.tenant_today()
    # `CR-166-BRC10` r3 t6 (§9 "Fields added") — image 21 draws Services and
    # Customer classes per plan. Service CODES (the screen words them) and class
    # NAMES (B14 rule 31), each in one query for the page.
    plan_ids = [rule.rate_plan_id for rule in rules]
    services_by_plan: dict[str, list[str]] = {}
    for plan_id, code in (
        rating_models.PlanRateSchedule.objects.filter(tenant_id=_tenant_id(), rate_plan_id__in=plan_ids)
        .order_by("service__sort", "service__code")
        .values_list("rate_plan_id", "service__code")
    ):
        services_by_plan.setdefault(str(plan_id), []).append(code)
    class_names = seams.account_type_names(
        [one for rule in rules for one in (rule.rate_plan.account_type_ids or [])]
    )
    out = []
    for rule in rules:
        units = rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan=rule.rate_plan, assigned_from__lte=today
        ).filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=today))
        accounts = (
            seams._account_queryset()
            .filter(unit_id__in=units.values("unit_id"))
            .exclude(status__behavior_class="terminal")
            .count()
        )
        out.append(
            {
                "plan_id": str(rule.rate_plan_id),
                "plan": rule.rate_plan.name,
                "plan_code": rule.rate_plan.code,
                "available_from": rule.available_from.isoformat() if rule.available_from else None,
                "available_to": rule.available_to.isoformat() if rule.available_to else None,
                "units": units.count(),
                "accounts": accounts,
                "services": services_by_plan.get(str(rule.rate_plan_id), []),
                # `[]` = every class; a class the tenant cannot name is left out.
                "customer_classes": [
                    class_names[str(one)]
                    for one in (rule.rate_plan.account_type_ids or [])
                    if str(one) in class_names
                ],
            }
        )
    return out


# ── GET /discounts/{id}/accounts ───────────────────────────────────────────
ACCOUNT_SORTS = ("account_number", "enrolled_on", "renew_by")
ACCOUNT_DEFAULT_SORT = "account_number"
ACCOUNT_FILTERS = ("status", "plan")
ACCOUNT_STATUSES = ("receiving", "proof_pending", "renewal_due")


def _notice_days(discount: Any) -> int:
    from apps.rating import discount_services

    version = discount_services.active_version(discount, seams.tenant_today())
    return int(version.recertification_notice_days) if version is not None else 60


def discount_accounts_queryset(discount: Any, params: Any) -> Any:
    """The accounts RECEIVING it (or due to), paged and filtered in SQL.

    One row per enrolment current today (`ended_on` null or not yet passed).
    Status, by the enrolment's own columns: *Proof pending* while verification
    is pending; *Renewal due* once `recertification_due_on` is inside the
    version's notice period; *Receiving* otherwise.
    """
    today = seams.tenant_today()
    due_by = today + timedelta(days=_notice_days(discount))
    pending = (
        discount_models.VERIFICATION_PENDING,
        discount_models.VERIFICATION_EXPIRED,
        discount_models.VERIFICATION_REJECTED,
    )
    unit_of_account = Subquery(
        seams._account_queryset().filter(pk=OuterRef(OuterRef("account_id"))).values("unit_id")[:1]
    )
    plan_name = Subquery(
        rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), unit_id=unit_of_account, assigned_from__lte=today
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=today))
        .order_by("-assigned_from")
        .values("rate_plan__name")[:1]
    )
    qs = (
        discount_models.DiscountEnrolment.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .filter(Q(ended_on__isnull=True) | Q(ended_on__gte=today))
        .annotate(
            row_status=Case(
                When(verification_status__in=pending, then=Value("proof_pending")),
                When(recertification_due_on__lte=due_by, then=Value("renewal_due")),
                default=Value("receiving"),
                output_field=CharField(),
            ),
            account_number=seams.account_number_subquery(),
            plan_name=plan_name,
        )
    )
    term = (params.q or "").strip()
    if len(term) >= 2:
        qs = qs.filter(account_id__in=seams.account_search_ids(term))
    status = params.filters.get("status")
    if status and status.lower() != "all":
        qs = qs.filter(row_status=status.lower())
    plan = params.filters.get("plan")
    if plan and plan.lower() != "all":
        units = rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id=plan, assigned_from__lte=today
        ).filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=today))
        qs = qs.filter(account_id__in=seams.account_ids_on_units(units.values("unit_id")))
    field = {
        "account_number": "account_number",
        "enrolled_on": "enrolled_on",
        "renew_by": "recertification_due_on",
    }.get(params.sort or ACCOUNT_DEFAULT_SORT, "account_number")
    prefix = "-" if params.dir == "desc" else ""
    return qs.order_by(f"{prefix}{field}", "id")


def _month_window(today: Any) -> tuple[Any, Any]:
    first = today.replace(day=1)
    following = (first + timedelta(days=32)).replace(day=1)
    return first, following


def granted_this_month(discount: Any, today: Any) -> str | None:
    """`DEF-2430` — the net subsidy this discount's grants record for bills
    whose period ends this month, with the utility's symbol. One aggregate."""
    from apps.rating import selectors

    first, following = _month_window(today)
    total = discount_models.DiscountGrant.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        discount=discount,
        period_end__gte=first,
        period_end__lt=following,
    ).aggregate(total=Sum("amount"))["total"]
    return selectors._display_money_with_symbol(total or Decimal("0"), seams.tenant_currency())


def discount_account_rows(enrolments: list[Any]) -> list[dict[str, Any]]:
    """One page of Accounts-tab rows — the names walked in two queries, this
    month's grants in a third (`DEF-2430`, one GROUP BY for the page)."""
    from apps.rating import selectors

    facts = seams.discount_account_facts([row.account_id for row in enrolments])
    currency = seams.tenant_currency()
    first, following = _month_window(seams.tenant_today())
    this_month = {
        row["enrolment_id"]: selectors._display_money_with_symbol(row["total"], currency)
        for row in discount_models.DiscountGrant.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            enrolment_id__in=[row.id for row in enrolments],
            period_end__gte=first,
            period_end__lt=following,
        )
        .values("enrolment_id")
        .annotate(total=Sum("amount"))
    }
    zero_display = selectors._display_money_with_symbol(Decimal("0"), currency)
    out = []
    for row in enrolments:
        fact = facts.get(str(row.account_id), {})
        out.append(
            {
                # Field ADDED to CR-166 §9 by task 3: the id `POST
                # /discount-enrolments/{id}/end` needs. An identifier the
                # screen ACTS on and never shows (B14 rule 31).
                "enrolment_id": str(row.id),
                "account_id": str(row.account_id),
                "account_number": fact.get("account_number") or row.account_number,
                "customer_name": fact.get("customer_name"),
                "premises_address": fact.get("premises_address"),
                "plan": row.plan_name,
                "enrolled_on": row.enrolled_on.isoformat(),
                "renew_by": (
                    row.recertification_due_on.isoformat() if row.recertification_due_on else None
                ),
                # 🔒 DEF-2430 — this enrolment's recorded grants this month, net
                # of reversals, with its symbol. Never a computed guess.
                "this_month": this_month.get(row.id, zero_display),
                "status": row.row_status,
            }
        )
    return out


#: `DEF-1005` — the Accounts tab's CSV, in the tab's own column order (image 20).
ACCOUNT_CSV_HEADER = (
    "Account",
    "Customer",
    "Address",
    "Plan",
    "Enrolled",
    "Renew by",
    "This month",
    "Status",
)
_ACCOUNT_STATUS_WORDS = {
    "receiving": "Receiving",
    "proof_pending": "Proof pending",
    "renewal_due": "Renewal due",
}
#: Rows per database read while streaming — a CSV of a 40,000-account tenant is
#: read 500 at a time and never held whole (NFR-3; NFR-5: no cap).
CSV_CHUNK = 500


def _mdy(value: Any) -> str:
    return value.strftime("%m/%d/%Y") if value else ""


def discount_accounts_csv(discount: Any, params: Any) -> Iterable[str]:
    """`DEF-1005` — `GET /discounts/{id}/accounts?format=csv`: the WHOLE
    filtered set (the same `q`, `f.status`, `f.plan` and sort as the page),
    streamed in chunks of 500 — the plan Units CSV's shape (`plan_reads`,
    2.485.1). No row cap: the read is the queryset, never a list."""
    head = io.StringIO()
    csv.writer(head).writerow(ACCOUNT_CSV_HEADER)
    yield head.getvalue()
    qs = discount_accounts_queryset(discount, params)
    chunk: list[Any] = []

    def _flush(items: list[Any]) -> str:
        out = io.StringIO()
        writer = csv.writer(out)
        for row, item in zip(discount_account_rows(items), items, strict=True):
            writer.writerow(
                (
                    row["account_number"] or "",
                    row["customer_name"] or "",
                    row["premises_address"] or "",
                    row["plan"] or "",
                    _mdy(item.enrolled_on),
                    _mdy(item.recertification_due_on),
                    row["this_month"] or "",
                    _ACCOUNT_STATUS_WORDS.get(row["status"], row["status"]),
                )
            )
        return out.getvalue()

    for item in qs.iterator(chunk_size=CSV_CHUNK):
        chunk.append(item)
        if len(chunk) >= CSV_CHUNK:
            yield _flush(chunk)
            chunk = []
    if chunk:
        yield _flush(chunk)


#: `DEF-1005` — the Audit tab's CSV (image 22): When · Who · What · Change ·
#: Reason. *What* is the server's action code and *Change* is before → after
#: field by field — the whole record, for a spreadsheet.
AUDIT_CSV_HEADER = ("When", "Who", "What", "Change", "Reason")


def _audit_side(side: Any) -> str:
    if not isinstance(side, dict):
        return "" if side is None else str(side)
    def _text(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(one) for one in value)
        return "" if value is None else str(value)

    return "; ".join(f"{key}: {_text(value)}" for key, value in side.items() if key != "reason")


def discount_audit_csv(discount: Any) -> Iterable[str]:
    """`DEF-1005` — `GET /discounts/{id}/audit?format=csv`: every audit row of
    the discount, newest first, read 500 at a time (NFR-3, no cap). Names, never
    ids — the same `discount_audit_entries` the tab reads (B14 rule 31)."""
    head = io.StringIO()
    csv.writer(head).writerow(AUDIT_CSV_HEADER)
    yield head.getvalue()
    qs = seams.discount_audit_queryset(discount_audit_filter(discount))
    total = qs.count()
    for start in range(0, total, CSV_CHUNK):
        rows = list(qs[start : start + CSV_CHUNK])
        entries = discount_audit_entries(rows, seams.audit_actor_payloads(rows))
        out = io.StringIO()
        writer = csv.writer(out)
        for entry in entries:
            before, after = _audit_side(entry["before"]), _audit_side(entry["after"])
            change = f"{before} -> {after}" if before and after else (after or before)
            writer.writerow(
                (
                    entry["at"] or "",
                    (entry["actor"] or {}).get("name") or "",
                    entry["action"],
                    change,
                    entry["reason"] or "",
                )
            )
        yield out.getvalue()


# ── GET /discounts/{id}/audit ──────────────────────────────────────────────
def discount_audit_filter(discount: Any) -> Q:
    """Every audit row about this discount, its versions, its plan bindings and
    its enrolments — four entity types, ids as SUBQUERIES (no list of 40,000
    enrolment ids is ever built)."""
    versions = discount_models.DiscountVersion.objects.filter(
        tenant_id=_tenant_id(), discount=discount
    ).values("id")
    bindings = discount_models.PlanDiscountRule.objects.filter(
        tenant_id=_tenant_id(), discount=discount
    ).values("id")
    enrolments = discount_models.DiscountEnrolment.objects.filter(
        tenant_id=_tenant_id(), discount=discount
    ).values("id")
    return (
        Q(entity_type="discount", entity_id=discount.id)
        | Q(entity_type="discount_version", entity_id__in=versions)
        | Q(entity_type="plan_discount_rule", entity_id__in=bindings)
        | Q(entity_type="discount_enrolment", entity_id__in=enrolments)
    )


#: Keys whose value is an identifier — dropped from the audit view (B14 rule
#: 31: no database id is ever a visible value). `account` is REPLACED by the
#: account number instead, because which account is the point of the row.
_ID_KEYS = {"id", "discount", "corrects", "superseded_by", "version_id", "gl_account_id"}


def _audit_view(payload: Any, numbers: dict[str, str], plans: dict[str, str] | None = None) -> Any:
    if not isinstance(payload, dict):
        return payload
    out = {}
    for key, value in payload.items():
        if key in _ID_KEYS or key.endswith("_id"):
            continue
        if key == "account" and value:
            out["account"] = numbers.get(str(value), value)
            continue
        if key == "rate_plan":
            # `DEF-RAT-9309` — a plan link names the PLAN (image 22's *Added
            # to plan · Residential Standard*); its id is never served.
            name = (plans or {}).get(str(value))
            if name:
                out["plan"] = name
            continue
        out[key] = value
    return out


def discount_audit_entries(rows: list[Any], actors: list[Any]) -> list[dict[str, Any]]:
    """`{at, actor, action, before, after, reason}` per row, NAMES not ids. On
    an update both sides keep only the fields that changed."""
    account_ids = []
    for row in rows:
        for side in (row.before, row.after):
            if isinstance(side, dict) and side.get("account"):
                account_ids.append(side["account"])
    numbers = seams.account_numbers(account_ids)
    plan_ids = [
        str(side["rate_plan"])
        for row in rows
        for side in (row.before, row.after)
        if isinstance(side, dict) and side.get("rate_plan")
    ]
    plans = (
        {
            str(pk): name
            for pk, name in rating_models.RatePlan.objects.filter(
                tenant_id=_tenant_id(), pk__in=plan_ids
            ).values_list("id", "name")
        }
        if plan_ids
        else {}
    )
    out = []
    for row, actor in zip(rows, actors, strict=False):
        before = _audit_view(row.before, numbers, plans) if row.before is not None else None
        after = _audit_view(row.after, numbers, plans) if row.after is not None else None
        if isinstance(before, dict) and isinstance(after, dict):
            keys = sorted(set(before) | set(after))
            changed = [key for key in keys if before.get(key) != after.get(key)]
            before = {key: before.get(key) for key in changed}
            after = {key: after.get(key) for key in changed}
        raw_after = row.after if isinstance(row.after, dict) else {}
        out.append(
            {
                "at": row.created_at.isoformat() if row.created_at else None,
                "actor": actor,
                "action": row.action,
                "before": before,
                "after": after,
                "reason": (
                    raw_after.get("reason")
                    or raw_after.get("correction_reason")
                    or raw_after.get("change_reason")
                    or raw_after.get("end_reason")
                ),
            }
        )
    return out


__all__ = [
    "ACCOUNT_DEFAULT_SORT",
    "ACCOUNT_FILTERS",
    "ACCOUNT_SORTS",
    "STATUSES",
    "contract_fields",
    "discount_account_rows",
    "discount_accounts_queryset",
    "discount_audit_entries",
    "discount_audit_filter",
    "discount_plan_rows",
    "discount_plans_queryset",
    "discount_status",
    "form_options",
    "status_annotation",
    "type_annotation",
]
