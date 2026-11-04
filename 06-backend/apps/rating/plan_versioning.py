"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — WHICH PLAN VERSION A READ SEES.

`BR-RAT-1066` (PO-approved plans drawing 2026-10-03, closing `OQ-324` as (B);
`CR-167-BRC10` §9): **a plan version has dates and owns what it binds, and the
service date picks exactly one.** Row in `12-governance/09-human-review-ledger.md`
(2026-10-03, CR-167-BRC10 r2 t3) — this file decides which services, schedules,
charge codes, taxes, discounts and plan terms price a bill on a given day.

── THE ONE RULE EVERY BINDING READ GOES THROUGH ───────────────────────────
The six binding tables (`plan_services`, `plan_rate_schedules`,
`plan_charge_rules`, `plan_tax_rules`, `plan_discount_rules`) carry
`plan_version_id`. Their DEFAULT manager (`PlanBindingManager`) returns only
the rows of ONE version per plan:

  1. the published, un-superseded version whose window covers THE DAY;
  2. else the plan's HEAD (`rate_plans.head_version_id`).

**THE DAY** is `pricing_day()` when a caller opened one (billing's gather does,
with the period end — R1's own rule, *"the plan version in force on the
service-period end date"*), else the utility's today. So every reader that
existed before this file — about a hundred of them, money and screen — keeps
asking the question it always asked and gets the version in force, without
being edited.

⚠ **A PLAN WITH ONE VERSION READS EXACTLY AS BEFORE, AND THAT IS PROVED, NOT
ASSUMED.** Before `rating/0063` every plan had one set of bindings; the
migration points all of them at the plan's head, and the head is the fallback
in step 2 — so a dateless published plan (`DEF-438`), a day before the plan's
start or after its end, and a draft plan all read the head, which is the same
rows they read yesterday. Only a plan that has been given a SECOND priceable
version can read anything different, and only on a day inside that version's
window. Golden suite and a before/after bill comparison on PostgreSQL say so
(`CR-167-BRC10` §9).

── THE HEAD AND THE MIRROR ────────────────────────────────────────────────
`rate_plans.head_version_id` is the version a dateless read falls back to: the
LATEST-STARTING published version (or the draft v1 of a draft plan). A *draft
new version* of a live plan is never the head. `rate_plans`' four term columns
(`minimum_bill_amount`, `outside_city_factor`, `budget_billing`,
`late_fee_charge_id`) are the head's terms, kept equal to the head row's copy
on every write; a day priced by a NON-head version reads that version's own
copy (`terms_on`). That keeps every reader of those columns right on the head
and gives the dated money readers the right answer off it.

⚠ **NOTHING HERE WRITES ON A READ.** The head does not move at midnight; the
date moves which version is in force (step 1), and the head is only the
fallback for days no window covers.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Any, Iterator

from django.apps import apps as django_apps
from django.db import models
from django.db.models import OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

#: `plan_versions.status` — three values. `history` is every filing row that
#: is not a priceable version: the in-place version bumps written before
#: `rating/0063` (v1, v2 … of a plan whose content then moved on) and the head
#: a legacy in-place edit replaces. It prices nothing and is outside the lock.
VERSION_DRAFT = "draft"
VERSION_PUBLISHED = "published"
VERSION_HISTORY = "history"
VERSION_STATUSES = (VERSION_DRAFT, VERSION_PUBLISHED, VERSION_HISTORY)

#: The four plan-level TERMS a version owns (`BR-RAT-1066`). Identity — name,
#: code, description, customer classes, intended-for, notes — stays on the
#: plan and is never versioned (`BR-RAT-1067`).
TERM_FIELDS = ("minimum_bill_amount", "outside_city_factor", "budget_billing", "late_fee_charge_id")

#: `DEF-RAT-10031` (PO 2026-10-09, option (b), fixed going forward only) — set
#: `True` in `plan_versions.snapshot` by every copy `plan_writes._publish` takes
#: AFTER the plan's term columns mirror the version, i.e. a copy that records
#: the version's OWN terms. A copy without it may hold the version it replaced
#: (`plan_reads.version_terms_recorded` decides, never this flag alone). It is
#: never plan content: every reader of a snapshot's facts skips it.
TERMS_RECORDED_KEY = "terms_recorded"

_PRICING_DAY: ContextVar[date | None] = ContextVar("rating_plan_pricing_day", default=None)

# A memoised read made under one pricing day must not answer the same read made
# under another (`core.batch_reads.register_context_key`).
from core import batch_reads as _batch_reads  # noqa: E402

_batch_reads.register_context_key(_PRICING_DAY.get)


@contextmanager
def pricing_day(day: date | None) -> Iterator[None]:
    """Read every plan binding AS OF `day` inside the block.

    Billing's gather opens one per account (and per split segment) with the
    period end, so a December bill computed in January reads December's plan
    version. `None` leaves the utility's today in charge.
    """
    token = _PRICING_DAY.set(day)
    try:
        yield
    finally:
        _PRICING_DAY.reset(token)


def binding_day() -> date:
    day = _PRICING_DAY.get()
    if day is not None:
        return day
    from apps.rating import seams

    return seams.tenant_today()


def _model(name: str) -> Any:
    return django_apps.get_model("rating", name)


def _in_force_subquery(plan_ref: Any, day: date) -> Subquery:
    PlanVersion = _model("PlanVersion")
    return Subquery(
        PlanVersion.objects.filter(
            rate_plan_id=plan_ref,
            status=VERSION_PUBLISHED,
            superseded_by__isnull=True,
            effective_from__isnull=False,
            effective_from__lte=day,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
        .order_by("-effective_from")
        .values("id")[:1]
    )


def current_version_expression(plan_ref: Any, day: date | None = None) -> Any:
    """SQL: the id of the version of plan `plan_ref` that a read on `day` sees."""
    RatePlan = _model("RatePlan")
    when = day or binding_day()
    head = Subquery(RatePlan.objects.filter(pk=plan_ref).values("head_version_id")[:1])
    return Coalesce(_in_force_subquery(plan_ref, when), head)


class PlanBindingQuerySet(models.QuerySet):
    def of_version(self, version: Any) -> "PlanBindingQuerySet":
        return self.filter(plan_version_id=getattr(version, "pk", version))


class PlanBindingManager(models.Manager.from_queryset(PlanBindingQuerySet)):  # type: ignore[misc]
    """The default manager of every binding table: ONE version per plan (module
    docstring). `all_versions` is the unfiltered manager for writes and for a
    read that names its version."""

    def get_queryset(self) -> PlanBindingQuerySet:
        qs = super().get_queryset()
        return qs.filter(plan_version_id=current_version_expression(OuterRef("rate_plan_id")))


class AllVersionsManager(models.Manager.from_queryset(PlanBindingQuerySet)):  # type: ignore[misc]
    pass


def version_on(plan_id: Any, day: date | None = None) -> Any:
    """The `PlanVersion` a read of `plan_id` on `day` sees (module rule), or None
    for a plan with no version row at all."""
    PlanVersion = _model("PlanVersion")
    RatePlan = _model("RatePlan")
    when = day or binding_day()
    row = (
        PlanVersion.objects.filter(
            rate_plan_id=plan_id,
            status=VERSION_PUBLISHED,
            superseded_by__isnull=True,
            effective_from__isnull=False,
            effective_from__lte=when,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=when))
        .order_by("-effective_from")
        .first()
    )
    if row is not None:
        return row
    head_id = RatePlan.objects.filter(pk=plan_id).values_list("head_version_id", flat=True).first()
    if head_id is None:
        return None
    return PlanVersion.objects.filter(pk=head_id).first()


def priceable_versions(plan_id: Any) -> list[Any]:
    """Every version that can price a day, in start order (R1's candidates)."""
    PlanVersion = _model("PlanVersion")
    return list(
        PlanVersion.objects.filter(
            rate_plan_id=plan_id, status=VERSION_PUBLISHED, superseded_by__isnull=True
        ).order_by("effective_from", "version_no")
    )


def terms_on(plan: Any, day: date | None = None) -> dict[str, Any]:
    """The four plan TERMS on `day`: the plan's own columns when the head is
    the version read (the mirror), else that version's own copy."""
    version = version_on(plan.pk, day)
    source = plan
    if version is not None and str(version.pk) != str(plan.head_version_id or ""):
        source = version
    return {field: getattr(source, field) for field in TERM_FIELDS}


def ensure_head(plan: Any) -> Any:
    """The plan's head version, creating it when a plan has none.

    A plan written by `create_plan` gets its v1 at once; this exists for every
    other writer (test fixtures and seeders that write `rate_plans` directly)
    so a binding row is never orphaned from a version. The created row carries
    the plan's window, its terms and its status — exactly what `rating/0063`
    wrote for every plan already on disk.
    """
    PlanVersion = _model("PlanVersion")
    RatePlan = _model("RatePlan")
    if getattr(plan, "head_version_id", None):
        return plan.head_version_id
    fresh = RatePlan.objects.filter(pk=plan.pk).values_list("head_version_id", flat=True).first()
    if fresh:
        plan.head_version_id = fresh
        return fresh
    version = PlanVersion.objects.create(
        tenant_id=plan.tenant_id,
        rate_plan_id=plan.pk,
        version_no=int(plan.version or 1),
        snapshot={},
        status=VERSION_DRAFT if plan.status == "draft" else VERSION_PUBLISHED,
        effective_from=plan.effective_from,
        effective_to=plan.effective_to,
        **{field: getattr(plan, field) for field in TERM_FIELDS},
    )
    RatePlan.objects.filter(pk=plan.pk).update(head_version_id=version.pk)
    plan.head_version_id = version.pk
    return version.pk


class BindingVersionMixin:
    """`save()` stamps a binding row with its plan's head when no version was
    named — so a writer that predates `BR-RAT-1066` keeps writing the plan's
    current statement, which is what it always meant."""

    def save(self, *args: Any, **kwargs: Any) -> None:
        if getattr(self, "plan_version_id", None) is None and getattr(self, "rate_plan_id", None):
            RatePlan = _model("RatePlan")
            plan = RatePlan.objects.get(pk=self.rate_plan_id)
            self.plan_version_id = ensure_head(plan)
        super().save(*args, **kwargs)  # type: ignore[misc]


def plan_version_starts(
    plan_id: Any, *, unit_id: Any = None, period_start: date, period_end: date
) -> list[date]:
    """The days inside `(period_start, period_end]` on which a published plan
    version STARTS — billing's split cuts there (`BR-RAT-114`). `plan_id` None
    means the unit's current plan (`unit_plan_assignments`, rating's own)."""
    PlanVersion = _model("PlanVersion")
    if plan_id is None and unit_id is not None:
        Assignment = _model("UnitPlanAssignment")
        plan_id = (
            Assignment.objects.filter(unit_id=unit_id, assigned_to__isnull=True)
            .values_list("rate_plan_id", flat=True)
            .first()
        )
    if plan_id is None:
        return []
    versions = priceable_versions(plan_id)
    if len(versions) <= 1:
        return []
    return sorted(
        {
            row.effective_from
            for row in PlanVersion.objects.filter(
                rate_plan_id=plan_id,
                status=VERSION_PUBLISHED,
                superseded_by__isnull=True,
                effective_from__gt=period_start,
                effective_from__lte=period_end,
            )
        }
    )
