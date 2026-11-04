# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-018 (cycle completeness bar + chase list) · US-MET-019
#           (the S25 Missing chip) · US-MET-012 (the Pending status pill)
#           Screens: S25 · S27 · S28 (batch review coverage)
# Change:   CR-038 W1 — the backend of plan-driven read completeness
# Rules:    BR-MET-049 (plan-driven read-set completeness) · BR-MET-057 (cycle
#           read-window drives expectations; per-cycle completeness bar +
#           chase list) · BR-MET-059 (channel model; flat meter = single
#           `total` channel) · BR-MET-016/053 (lineage HEADS count once) ·
#           BR-MET-011 (derived, never stored counters) · BR-RAT-067 (a TOU
#           window's channel is STATED, never derived) · BR-AST-029 (net meter
#           cycle = consumption + export records) · BR-MET-052 (a retired
#           meter expects no read) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 3 (registers are named channels, never bare numbers)
# Tests:    06-backend/tests/test_us_met_018_plan_registers.py (resolver +
#           import rule — the guard proved RED first) ·
#           06-backend/tests/test_us_met_018_completeness.py (coverage, chase
#           list, Missing chip, Pending, isolation)
# Impacts:  apps/metering/services.py (validate_read_batch groups registers
#           and stores the rule outcome) · selectors.needs_attention_counts
#           (the Missing chip stops serving null) · api.py (chase-list route,
#           `f.status=pending` on GET /reads, batch coverage)
# ───────────────────────────────────────────────────────
"""BR-MET-049 + BR-MET-057 — the plan-driven completeness computation.

THE TWO SIGNED RULES THIS MODULE IMPLEMENTS, VERBATIM
(04-docs/05-modules/04-metering/02-business-rules.md, both CONFIRMED):

  BR-MET-049 — "**Plan-driven read-set completeness**: the unit's plan
  determines the required read set per meter (TOU → per-window records;
  demand → +demand record); completeness is tracked and enforced as a VEE
  validation before billing" (PO RD-2, "track it and use it for validations").

  BR-MET-057 — "Cycle read-window drives expectations; per-cycle completeness
  bar + chase list" (PO RD-15).

US-MET-018 §2 sharpens both into the arithmetic here: *"Expected set = Σ over
the cycle's route-member units of the plan-driven required channel records;
completeness % = collected required records ÷ expected required records"* and
*"Expectations count only within the window — before window open there is
nothing to chase."*

════════════════════════════════════════════════════════════════════════════
DERIVED, NEVER STORED
════════════════════════════════════════════════════════════════════════════
No expected-set, no counter and no completeness figure is written anywhere by
this module — US-MET-018 §5 says it outright (*"no stored counter —
BR-MET-011"*), and the reason is the reason BR-MET-011 exists: a stored
expected set is a SECOND SOURCE OF TRUTH that goes stale the moment a plan
gains a window or a meter joins a route. Every answer here is recomputed from
the unit's plan (through the rating seam), the cycle's own schedule fields and
the committed lineage heads, at the moment somebody asks.

THE REQUIRED SET PER METER (BR-MET-049 read with BR-MET-059):

  flat · tiered · seasonal · capacity · percent_of_service → {total}
      BR-MET-059: *"flat meter = single `total` channel"*. The rule names TOU
      and demand as the models that EXTEND the set; every other model's meter
      measures one register. (`capacity`/`percent_of_service` price without a
      quantity of their own — a meter standing on one still reads its single
      register.)
  time_of_use → the plan's OWN TimeOfUseWindow channels + {total}
      Read from the rows through rating's `pricing_inputs`, NEVER a hardcoded
      three: a two-window schedule expects two windows. `total` rides along
      because BR-MET-052's sum-sanity (Σ windows ≈ total ±1%) needs the total
      register, and US-MET-018 §1 states the set as *"TOU → windows + total"*.
      A window whose channel was never stated is BR-RAT-067's refusal — the
      set is UNRESOLVABLE, reported by name, never ranked or guessed.
  demand → {total, demand}
      BR-MET-049: *"demand → +demand record"* — the energy register plus the
      max-demand register (US-MET-018 §4 counts demand meters at 2 records).
  net-metered asset → + {export}
      An ASSET fact (BR-AST-029: a net cycle is one consumption record + one
      export record), layered onto whatever the plan expects.

An UNRESOLVABLE set is a STATED ABSENCE with its reason (the `REGISTERS_
ABSENT_*` vocabulary below), never a guess and never an empty set pretending
to be an answer: "rating cannot answer" must not read as "this meter expects
nothing" (the DEF-075 posture, same as every seam in this module).

════════════════════════════════════════════════════════════════════════════
THE WINDOW (BR-MET-057) — WHICH DAYS EXPECTATIONS COUNT IN
════════════════════════════════════════════════════════════════════════════
Two callers, two anchors, both already ruled elsewhere:

  * A caller that NAMES a period (a batch tagged with its reading month, the
    chase-list endpoint's `period` param) gets `schedule.derive_read_window`
    in that month — the *"month already picked"* use `services._cycle_window_
    for` documents, so completeness and the `out_of_window` flag read the SAME
    window for the same batch.
  * "The CURRENT window" (the S25 Missing chip, the Pending derivation, the
    chase list with no period named) is `period_engine.latest_opened_window
    (as_of=today)` when the cycle has a `first_run_date` — the ruled generator
    (OQ-339/340/341 all closed 2026-08-23), walked to the most recent
    occurrence that has OPENED — falling back to `derive_read_window` anchored
    in the tenant's current month (and, for a window that leaves its month,
    the previous one) when no first run was ever set. That fallback anchor is
    the same recorded lane judgment `cycle_dict`'s derived window carries.
    ⚠ It used to be `upcoming_windows(count=1)`, which skips a window the
    moment it has ENDED; BR-MET-132 below is why that changed.

BEFORE the window opens, nothing is counted and nothing is chased — US-MET-018
TC-6, the chase list answers *"window opens <date>"* with zero rows.

⚠ **AFTER IT CLOSES, IT KEEPS COUNTING — BR-MET-132, CONFIRMED PO 2026-08-26,
CLOSING OQ-389 AND AMENDING US-MET-019 §5's LITERAL READING.** Verbatim: *"Keep
counting until the run consumes the period — those are the chase days"*. This
module used to follow §5's *"open window only (BR-MET-057)"* to the letter and
the consequence was measured before it was ruled: CY-001's window closes
**20 Aug**, its bill run is **25 Aug**, and on **22 Aug** — with sixty meters
unread — the chip read **0**, on precisely the five days a clerk chases
stragglers. So a window is chaseable while it is OPEN *or* CLOSED-BUT-UNBILLED
(`CHASEABLE_WINDOW_STATES`), and a period is dropped only once a bill run has
consumed it (`period_is_consumed` → billing's own `period_consumed_by_run`).
The chase-list endpoint still answers for any NAMED period, so a period this
module does drop is never unreachable.

COLLECTED counts committed LINEAGE HEADS only (BR-MET-016/053 — a superseded
chain counts exactly once), dated inside the window (US-MET-018 §5), and only
records the expected set names — an extra channel never inflates the bar. An
ESTIMATED head counts: the record exists (estimation is this chase list's own
fix action), and BR-MET-028 keeps it labelled everywhere it shows.

NOTHING HERE IS MONEY, and no rating PRICE is read — `pricing_inputs` is asked
for the STRUCTURE (model + window channels + demand config) and every price in
it is ignored. Pricing is the 🔒 engine's; this module counts registers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.db.models import Q

from apps.metering import models, period_engine, seams
from core import tenancy as core_tenancy
from core.pagination import filter_values

__all__ = [
    "REGISTERS_ABSENT_NO_PLAN",
    "REGISTERS_ABSENT_RATING_UNWIRED",
    "REGISTERS_ABSENT_SERVICE_NOT_ON_PLAN",
    "REGISTERS_ABSENT_NO_VERSION",
    "REGISTERS_ABSENT_WINDOW_CHANNEL_UNSTATED",
    "REGISTERS_ABSENT_NO_WINDOWS",
    "REGISTERS_ABSENT_MODEL_UNRESOLVED",
    "REGISTERS_ABSENT_NO_SERVICE",
    "ExpectedRegisters",
    "PlanRegisterResolver",
    "window_for_period",
    "current_window",
    "period_is_consumed",
    "CHASEABLE_WINDOW_STATES",
    "cycle_coverage",
    "batch_cycle_coverage",
    "chase_list",
    "missing_records_count",
    "pending_read_entries",
]


# ── the stated absences (VALUES, not prose — screens group on them) ─────────
#: The unit holds no plan. NOT a defect: *"a unit with no plan contributes no
#: required records (the plan determines the set — BR-MET-049)"* — US-MET-018
#: §1 and TC-5. A stray read on such a unit is `vacant_unit`'s business.
REGISTERS_ABSENT_NO_PLAN = "no_plan"
#: Rating publishes no selectors — CANNOT ANSWER, never "expects nothing".
REGISTERS_ABSENT_RATING_UNWIRED = seams.PLAN_INPUTS_UNWIRED
#: The plan names no rate schedule for this meter's service.
REGISTERS_ABSENT_SERVICE_NOT_ON_PLAN = seams.PLAN_INPUTS_SERVICE_NOT_ON_PLAN
#: No tariff version in force on the service date (BR-RAT-007 — no fallback).
REGISTERS_ABSENT_NO_VERSION = seams.PLAN_INPUTS_NO_VERSION
#: A TOU window whose register was never stated (BR-RAT-067: NULL is a
#: REFUSAL) — the set cannot be stated without ranking or guessing.
REGISTERS_ABSENT_WINDOW_CHANNEL_UNSTATED = "window_channel_not_stated"
#: A time_of_use version with no window rows at all.
REGISTERS_ABSENT_NO_WINDOWS = "tou_windows_not_configured"
#: A model this module has no ruled set for. A NEW pricing model must STATE
#: its register set here; defaulting it to {total} silently would be a guess.
REGISTERS_ABSENT_MODEL_UNRESOLVED = "model_unresolved"
#: The meter stands on no service point / names no service — no plan hop exists.
REGISTERS_ABSENT_NO_SERVICE = "no_service_point"

#: BR-MET-132 — the window states a clerk can still chase in, named ONCE so the
#: chip, the Pending list and any surface added later cannot drift apart. PO
#: verbatim 2026-08-26: *"Keep counting until the run consumes the period —
#: those are the chase days"*. `before_open` is deliberately absent: US-MET-018
#: TC-6 says there is nothing to chase before a window opens, and BR-MET-132
#: amended the END of the window, not its start.
CHASEABLE_WINDOW_STATES: frozenset[str] = frozenset({"open", "closed_unbilled"})

#: The models whose meter reads ONE register (BR-MET-059's flat-meter default,
#: extended to every model BR-MET-049 does not name as set-extending).
_SINGLE_REGISTER_MODELS = frozenset(
    {"flat", "tiered", "seasonal", "capacity", "percent_of_service"}
)


def _tenant_id() -> UUID:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _channel_sort_key(channel: str) -> tuple[int, str]:
    """Canonical display order — models.CHANNELS order, unknowns last."""
    try:
        return (models.CHANNELS.index(channel), channel)
    except ValueError:  # pragma: no cover - extensible enum, future channels
        return (len(models.CHANNELS), channel)


@dataclass(frozen=True)
class ExpectedRegisters:
    """One meter's required read set for a period — or a stated absence.

    `channels` is the ordered required set, and it is `None` (never `()`)
    when the set could not be resolved — with `absent_reason` saying exactly
    why. An empty tuple would claim "this meter expects nothing", which is a
    different and dangerous statement (the DEF-075 lesson).
    """

    channels: tuple[str, ...] | None
    absent_reason: str | None = None
    model: str | None = None
    plan_id: str | None = None

    def detail(self) -> dict[str, Any]:
        """The self-describing extras a rule outcome carries (BR-MET-022/056)."""
        out: dict[str, Any] = {}
        if self.model:
            out["plan_model"] = self.model
        if self.plan_id:
            out["plan_id"] = self.plan_id
        return out


@dataclass(frozen=True)
class PricingUnit:
    """The unit the thing that PRICES this meter is quoted in — or a stated
    absence. `BR-MET-1160`'s left-hand input at upload.

    `unit` is the rate schedule's own `uom` (rating's `pricing_inputs`
    publishes it as `billed_unit`, and it is the SAME STRING
    `rating.pricing.stages.normalize._gate_uom` refuses the bill against at
    2am). `None` never means *"there is nothing to match"* — it means the
    question could not be answered, and `absent_reason` says which of the four
    ways, so the rule REPORTS instead of half-firing (the DEF-075 lesson, the
    same one `ExpectedRegisters` above is shaped by).
    """

    unit: str | None
    absent_reason: str | None = None
    plan_id: str | None = None

    def detail(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.plan_id:
            out["plan_id"] = self.plan_id
        return out


#: The rate schedule states no unit at all. `TariffVersion.uom` is NULLABLE
#: (`US-RAT-005 §5`), and an absent price unit is `BR-RAT-038`'s business on
#: the rate-schedule screen, not a clerk's at the import screen — so the rule
#: reports rather than manufacturing a mismatch against a blank.
PRICING_UNIT_ABSENT_NOT_STATED = "schedule_states_no_unit"


class PlanRegisterResolver:
    """Derives expected register sets, caching per (plan, service, date) FOR
    ONE COMPUTATION — a batch validation or one coverage pass. The cache is
    the DEF-324 discipline (one rating read per plan+service, not per meter),
    and it lives on this object precisely so nothing outlives the ask:
    a NEW resolver re-derives everything (derived, never stored).

    ⚠ **IT ALSO ANSWERS `BR-MET-1160`'s QUESTION — WHAT UNIT PRICES THIS METER
    — AND THAT IS WHY THE RAW SEAM ANSWER IS NOW CACHED RATHER THAN THE
    DERIVED SET.** Both questions are answered from ONE `plan_register_inputs`
    call for a (plan, service, date): the register SET comes from the pricing
    model and its windows, the pricing UNIT from the same projection's
    `billed_unit`. Deriving them from two separate calls would double every
    rating hop a 500-row batch makes, which is DEF-324 exactly.
    """

    def __init__(self) -> None:
        self._by_plan: dict[tuple[str, str, date], ExpectedRegisters] = {}
        self._inputs: dict[tuple[str, str, date], dict[str, Any]] = {}
        self._unit_plan: dict[str, Any] = {}

    # ── the one rating hop both answers are derived from ────────────────────
    def _plan_inputs(self, plan_id: Any, service_code: str, service_date: date) -> dict[str, Any]:
        """`seams.plan_register_inputs` for a (plan, service, date), ONCE.

        One call per distinct triple per resolver — the register set and the
        pricing unit are two readings of the same projection, never two asks.
        """
        key = (str(plan_id), service_code, service_date)
        cached = self._inputs.get(key)
        if cached is None:
            cached = seams.plan_register_inputs(plan_id, service_code, service_date)
            self._inputs[key] = cached
        return cached

    # ── the plan half (BR-MET-049's set, before asset facts) ────────────────
    def _plan_set(self, plan_id: Any, service_code: str, service_date: date) -> ExpectedRegisters:
        key = (str(plan_id), service_code, service_date)
        cached = self._by_plan.get(key)
        if cached is not None:
            return cached
        answer = self._derive_plan_set(plan_id, service_code, service_date)
        self._by_plan[key] = answer
        return answer

    def _derive_plan_set(
        self, plan_id: Any, service_code: str, service_date: date
    ) -> ExpectedRegisters:
        asked = self._plan_inputs(plan_id, service_code, service_date)
        if asked["status"] != seams.PLAN_INPUTS_OK:
            return ExpectedRegisters(
                channels=None, absent_reason=asked["status"], plan_id=str(plan_id)
            )
        inputs = asked["inputs"]
        model = inputs.get("model")
        if model in _SINGLE_REGISTER_MODELS:
            return ExpectedRegisters(
                channels=(models.CHANNEL_TOTAL,), model=model, plan_id=str(plan_id)
            )
        if model == "demand":
            return ExpectedRegisters(
                channels=(models.CHANNEL_TOTAL, models.CHANNEL_DEMAND),
                model=model,
                plan_id=str(plan_id),
            )
        if model == "time_of_use":
            windows = inputs.get("windows") or []
            if not windows:
                return ExpectedRegisters(
                    channels=None,
                    absent_reason=REGISTERS_ABSENT_NO_WINDOWS,
                    model=model,
                    plan_id=str(plan_id),
                )
            channels: set[str] = set()
            for window in windows:
                channel = window.get("channel")
                if not channel:
                    # BR-RAT-067: NULL is a refusal. Guessing here would be the
                    # price-rank resolver the PO deleted, reborn in metering.
                    return ExpectedRegisters(
                        channels=None,
                        absent_reason=REGISTERS_ABSENT_WINDOW_CHANNEL_UNSTATED,
                        model=model,
                        plan_id=str(plan_id),
                    )
                channels.add(str(channel))
            channels.add(models.CHANNEL_TOTAL)  # Σ windows ≈ total (BR-MET-052)
            return ExpectedRegisters(
                channels=tuple(sorted(channels, key=_channel_sort_key)),
                model=model,
                plan_id=str(plan_id),
            )
        return ExpectedRegisters(
            channels=None,
            absent_reason=REGISTERS_ABSENT_MODEL_UNRESOLVED,
            model=str(model) if model else None,
            plan_id=str(plan_id),
        )

    # ── the meter half (asset facts layered on) ─────────────────────────────
    def for_meter_row(
        self,
        *,
        unit_rate_plan_id: Any,
        service_code: str | None,
        service_date: date,
        net_metering: bool,
    ) -> ExpectedRegisters:
        """The required set for one meter, from already-fetched facts."""
        if not service_code:
            return ExpectedRegisters(channels=None, absent_reason=REGISTERS_ABSENT_NO_SERVICE)
        if not unit_rate_plan_id:
            return ExpectedRegisters(channels=None, absent_reason=REGISTERS_ABSENT_NO_PLAN)
        base = self._plan_set(unit_rate_plan_id, service_code, service_date)
        if base.channels is None or not net_metering:
            return base
        # BR-AST-029: the net meter's export record, an ASSET fact.
        with_export = set(base.channels) | {models.CHANNEL_EXPORT}
        return ExpectedRegisters(
            channels=tuple(sorted(with_export, key=_channel_sort_key)),
            model=base.model,
            plan_id=base.plan_id,
        )

    def _asset_plan_facts(self, asset: Any) -> tuple[str | None, Any]:
        """`(service_code, unit_rate_plan_id)` for one resolved asset.

        The asset arrives from `seams.meter_by_no` with `service_point__service`
        already joined; the unit's plan is one metering-owned read, cached per
        unit so a 500-row batch asks once per unit rather than once per row.

        Shared by `for_asset` and `pricing_unit_for_asset` so the two answers
        can never be derived from two different plans for one meter.
        """
        service_point = getattr(asset, "service_point", None)
        service = getattr(service_point, "service", None)
        service_code = getattr(service, "code", None)
        unit_id = getattr(service_point, "unit_id", None)
        if unit_id is None:
            return service_code, None
        key = str(unit_id)
        if key not in self._unit_plan:
            self._unit_plan[key] = (
                models.Unit.objects.filter(tenant_id=_tenant_id(), pk=unit_id)
                .values_list("rate_plan_id", flat=True)
                .first()
            )
        return service_code, self._unit_plan[key]

    def for_asset(self, asset: Any, *, service_date: date) -> ExpectedRegisters:
        """The required set for one resolved asset (the import path's shape)."""
        service_code, plan_id = self._asset_plan_facts(asset)
        return self.for_meter_row(
            unit_rate_plan_id=plan_id,
            service_code=service_code,
            service_date=service_date,
            net_metering=bool(getattr(asset, "net_metering", False)),
        )

    # ── BR-MET-1160: what unit prices this meter, at the moment of upload ────
    def pricing_unit_for_asset(self, asset: Any, *, service_date: date) -> PricingUnit:
        """**The rate schedule's own unit for this meter's service, on this
        read's date** — the right-hand side of `BR-MET-1160`'s comparison.

        ⚠ **IT IS THE SCHEDULE'S `uom`, NOT `tenant_services.billed_uom`, AND
        THE DIFFERENCE IS `DEF-3108`.** That column is NULL on every tenant
        this product has ever provisioned, so a rule comparing against it is
        blind everywhere — which is exactly what the save-time gate did until
        2026-09-02. This asks rating for the unit the ENGINE will price with:
        `pricing_inputs(...)["billed_unit"]` is `TariffVersion.uom`, the same
        string `rating.pricing.stages.normalize._gate_uom` compares a read
        against before it refuses a bill (`BR-RAT-038`). So a read this rule
        passes is a read that bill run will not stop on, and the two cannot
        drift apart by construction.
        **No effective-billed-unit substitution happens here and none is
        needed** — neither side of this comparison is that column, so there is
        no second copy of `DEF-3108`'s fix in this module (hard-won law 5).

        Every unanswerable case is REPORTED with its own reason and never
        collapsed into "the units match": rating unwired, the plan naming no
        schedule for this service, no version in force on the read's date
        (`BR-RAT-007` has no fallback to today's prices), the unit holding no
        plan at all, the meter standing on no service point — and a schedule
        that states no unit, which is the rate screen's problem and not the
        clerk's.
        """
        service_code, plan_id = self._asset_plan_facts(asset)
        if not service_code:
            return PricingUnit(unit=None, absent_reason=REGISTERS_ABSENT_NO_SERVICE)
        if not plan_id:
            return PricingUnit(unit=None, absent_reason=REGISTERS_ABSENT_NO_PLAN)
        asked = self._plan_inputs(plan_id, service_code, service_date)
        if asked["status"] != seams.PLAN_INPUTS_OK:
            return PricingUnit(
                unit=None, absent_reason=asked["status"], plan_id=str(plan_id)
            )
        stated = (asked["inputs"] or {}).get("billed_unit")
        stated = str(stated).strip() if stated else ""
        if not stated:
            return PricingUnit(
                unit=None,
                absent_reason=PRICING_UNIT_ABSENT_NOT_STATED,
                plan_id=str(plan_id),
            )
        return PricingUnit(unit=stated, plan_id=str(plan_id))


# ── the window (BR-MET-057) ─────────────────────────────────────────────────


def window_for_period(cycle: Any, anchor: date) -> tuple[date, date] | None:
    """The cycle's read window in a month the CALLER already picked — the
    `services._cycle_window_for` posture (a batch's reading month, the
    chase-list `period` param), so completeness and the `out_of_window` flag
    read one window. `None` when the cycle has no schedule to derive from.

    ⚠ The EFFECTIVE start day, through `period_engine.cycle_read_window` — the
    one derivation (`DEF-MET-10588`, 2026-10-24). The Reads cycle page asks the
    chase list for the window it prints, so this and `cycle_dict` must agree."""
    return period_engine.cycle_read_window(cycle, anchor)


def period_is_consumed(cycle: Any, window: tuple[date, date]) -> bool:
    """BR-MET-132's drop condition — has a bill run consumed this period?

    One seam call (`seams.period_consumed_by_run` → billing's own selector);
    metering never reads `bill_runs` itself (B1).

    **A `None` FROM THE SEAM IS READ AS *NOT CONSUMED*, DELIBERATELY.** None
    means billing could not answer, which is not the same fact as "no run
    billed this period" (DEF-075's posture). The two possible errors are not
    symmetric: keeping a period counted after it was billed shows a clerk a
    number they can dismiss in one look, while dropping a period nobody read
    is DEF-046's chip-stuck-at-zero — a silent zero reads as good news. So the
    unknown resolves LOUD.
    """
    answer = seams.period_consumed_by_run(cycle.id, window[0], window[1])
    return bool(answer)


def current_window(cycle: Any, today: date) -> dict[str, Any] | None:
    """The occurrence that matters TODAY, with its state.

    Returns `{"period_start", "period_end", "state"}` where state is one of

      · `"open"`            — start ≤ today ≤ end;
      · `"closed_unbilled"` — the window has ENDED and no bill run has
        consumed the period. **These are BR-MET-132's chase days**;
      · `"before_open"`     — nothing has opened yet, or the last thing that
        opened has been billed and the next window has not started
        (US-MET-018 TC-6's *"window opens Aug 12"*),

    or `None` when the cycle has no derivable schedule at all.

    ════════════════════════════════════════════════════════════════════════
    BR-MET-132 — AMENDED 2026-08-26, AND THE OLD BEHAVIOUR WAS THE DEFECT
    ════════════════════════════════════════════════════════════════════════
    This function used to skip an occurrence the moment it ENDED, because
    US-MET-019 §5 says the Missing chip counts *"open window only
    (BR-MET-057)"* and that is what the words say. The consequence was
    measured and put to the PO as OQ-389: CY-001's reading window closes
    **20 Aug** and its bill run is **25 Aug**, so on **22 Aug** — with sixty
    meters unread — the chip read **0**, on exactly the five days a clerk is
    chasing stragglers. The chip went quiet for the days it exists for.

    BR-MET-132, PO verbatim 2026-08-26 (CONFIRMED, closing OQ-389 and
    amending US-MET-019 §5's literal reading): *"Keep counting until the run
    consumes the period — those are the chase days"*. So the skip condition
    is no longer *ended*; it is **consumed by a bill run**
    (`period_is_consumed`).

    ⚠ **ONE LANE JUDGMENT, STATED HERE RATHER THAN HIDDEN IN A CALL SITE.**
    The rule says *"windows"*, plural, and this looks at exactly ONE: the most
    recent occurrence to have OPENED (`period_engine.latest_opened_window`).
    An older occurrence that a run never consumed is therefore dropped once a
    newer one opens. Two reasons, and the second is the one that decided it:

      1. The PO's worked case is a single period — the gap between one
         window's close and that period's own run. *"Those are the chase
         days"* names that gap, not a backlog.
      2. The alternative has no floor. A tenant that has never completed a
         run — or one whose billing module simply cannot answer, which is the
         `None` case above — would have EVERY occurrence since its first run
         counted, so the chip would grow without bound and cost one coverage
         computation per period to produce. A chip whose cost is unbounded is
         a chip that stops loading.

    Where a run skips a period and a later one is billed, this reports
    `before_open` and that period's gap has to be found from the chase-list
    endpoint, which answers any NAMED period. Recorded in
    `12-governance/02-decision-log.md` so it can be overturned deliberately.

    A cycle WITH a first run walks the ruled generator (OQ-339/340/341
    closed). A cycle with only `start_day` + `days_to_complete` falls back to
    the rendering derivation in today's month — and the PREVIOUS month, so a
    still-running spillover window is not mistaken for "not open" — the same
    anchor judgment `cycle_dict` records. ⚠ On that fallback path the
    closed-unbilled state is offered for THIS MONTH'S window only: a cycle
    with no first run has never run, so last month's derived window is a
    RENDERING and not an occurrence that happened, and counting it would put
    a phantom backlog on every freshly configured cycle.
    """
    if getattr(cycle, "first_run_date", None):
        opened = period_engine.latest_opened_window(
            frequency=getattr(cycle, "frequency", None),
            start_day=getattr(cycle, "start_day", None),
            days_to_complete=getattr(cycle, "days_to_complete", None),
            first_run=cycle.first_run_date,
            as_of=today,
        )
        if opened is not None:
            if opened.period_end >= today:
                return {
                    "period_start": opened.period_start,
                    "period_end": opened.period_end,
                    "state": "open",
                }
            if not period_is_consumed(cycle, (opened.period_start, opened.period_end)):
                # BR-MET-132 — the chase days.
                return {
                    "period_start": opened.period_start,
                    "period_end": opened.period_end,
                    "state": "closed_unbilled",
                }
        windows = period_engine.upcoming_windows(
            frequency=getattr(cycle, "frequency", None),
            start_day=getattr(cycle, "start_day", None),
            days_to_complete=getattr(cycle, "days_to_complete", None),
            first_run=cycle.first_run_date,
            as_of=today,
            count=1,
        )
        if not windows:
            return None
        window = windows[0]
        return {
            "period_start": window.period_start,
            "period_end": window.period_end,
            "state": "open" if window.period_start <= today else "before_open",
        }
    next_month_anchor = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    this_month = window_for_period(cycle, today)
    candidates = [
        window
        for window in (
            window_for_period(cycle, today.replace(day=1) - timedelta(days=1)),  # previous
            this_month,
            window_for_period(cycle, next_month_anchor),
        )
        if window is not None
    ]
    if not candidates:
        return None
    # The same reading `period_engine.upcoming_windows` implements: a
    # still-running window is "open". When last month's spillover and this
    # month's window are BOTH running (OQ-341 allows the overlap), the LATEST
    # running one answers — the OQ-345 attribution question is about READS and
    # stays refused where it is; a COUNT must still answer with one window.
    running = [w for w in candidates if w[0] <= today <= w[1]]
    if running:
        start, end = max(running, key=lambda w: w[0])
        return {"period_start": start, "period_end": end, "state": "open"}
    # BR-MET-132 on the no-first-run path: THIS month's window, once it has
    # closed, until a run consumes it. Last month's derived window is not
    # offered — see the docstring's second ⚠.
    if (
        this_month is not None
        and this_month[1] < today
        and not period_is_consumed(cycle, this_month)
    ):
        return {
            "period_start": this_month[0],
            "period_end": this_month[1],
            "state": "closed_unbilled",
        }
    upcoming = [w for w in candidates if w[0] > today]
    if upcoming:
        start, end = min(upcoming, key=lambda w: w[0])
        return {"period_start": start, "period_end": end, "state": "before_open"}
    return None  # pragma: no cover - three monthly anchors always yield one


def _tenant_today() -> date:
    return seams.tenant_today()


# ── expected meters (the cycle's routes' service points) ────────────────────


#: `DEF-CUS-9753` — the asset-type categories whose devices are READ: meters
#: and sub-meters. `apps.assets.selectors.READ_DEVICE_CATEGORIES` is the same
#: pair; it is restated by value because metering reads assets' rows through a
#: seam and never imports its selectors (B1). A cart, a fire line or a PV array
#: is `behind_the_meter`: counted or owned, never read, so never owed a read.
READ_DEVICE_CATEGORIES: tuple[str, ...] = ("meters", "sub_meters")


def _expected_meters(cycle_id: Any, window_end: date) -> list[Any]:
    """Every meter the cycle expects a read from: assets standing on this
    cycle's service points (BR-MET-033 membership stamps `service_points.
    cycle_id`), excluding meters retired by the window's close — BR-MET-052
    reads a retired meter as an error, so expecting one would chase a ghost.

    READ-ONLY probe on the assets registry (the `seams.meter_by_no` / archive
    result-set Eng disposition — assets publishes no by-cycle selector; no
    write crosses the boundary), tenant-scoped like every query here (rule 1).
    The retirement predicate mirrors `services._asset_is_retired`: an explicit
    `retire_date` on/before the window close, or a terminal lifecycle stage.
    """
    asset_model = django_apps.get_model("assets", "Asset")
    return list(
        asset_model.objects.filter(
            tenant_id=_tenant_id(),
            service_point__cycle_id=cycle_id,
            service_point__deleted_at__isnull=True,
        )
        .exclude(Q(retire_date__isnull=False) & Q(retire_date__lte=window_end))
        .exclude(status__behavior_class="terminal")
        # `DEF-CUS-9753` — only a device somebody READS is expected to deliver
        # a read: a cart, a fire line or a PV array (`behind_the_meter`) was
        # chased as a meter short on every window, for ever.
        .filter(type__category__in=READ_DEVICE_CATEGORIES)
        .select_related(
            "service_point",
            "service_point__service",
            "service_point__route",
            "service_point__unit",
            "service_point__unit__premises",
        )
        .order_by("asset_no")
    )


def _collected_heads(
    asset_ids: list[Any], window_start: date, window_end: date
) -> set[tuple[str, str]]:
    """(asset_id, channel) pairs with a committed LINEAGE HEAD dated inside
    the window — a superseded chain counts exactly once (BR-MET-016/053,
    US-MET-018 TC-7), and an estimated head counts (the record exists;
    BR-MET-028 keeps it labelled)."""
    rows = (
        models.MeterRead.objects.filter(
            tenant_id=_tenant_id(),
            asset_id__in=asset_ids,
            superseded_by_id__isnull=True,
            read_at__date__gte=window_start,
            read_at__date__lte=window_end,
        )
        .values_list("asset_id", "channel")
        .distinct()
    )
    return {(str(asset_id), channel) for asset_id, channel in rows}


def _meter_rows(
    cycle: Any, window: tuple[date, date], *, resolver: PlanRegisterResolver | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per-meter expectation vs collection over one window.

    Returns `(rows, unresolved)`: `rows` carries every meter WITH a resolved
    set (its expected/collected/missing channels); `unresolved` names every
    meter whose set could not be stated, WITH its reason — reported beside the
    figures, never buried in them (a bar computed while ten meters are
    unresolvable must say so or it lies by omission).
    """
    window_start, window_end = window
    resolver = resolver or PlanRegisterResolver()
    meters = _expected_meters(cycle.id, window_end)
    unit_ids = {meter.service_point.unit_id for meter in meters if meter.service_point is not None}
    plans = dict(
        models.Unit.objects.filter(tenant_id=_tenant_id(), id__in=unit_ids).values_list(
            "id", "rate_plan_id"
        )
    )
    collected = _collected_heads([meter.id for meter in meters], window_start, window_end)

    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for meter in meters:
        point = meter.service_point
        unit_id = getattr(point, "unit_id", None)
        expected = resolver.for_meter_row(
            unit_rate_plan_id=plans.get(unit_id),
            service_code=getattr(getattr(point, "service", None), "code", None),
            service_date=window_start,
            net_metering=bool(getattr(meter, "net_metering", False)),
        )
        if expected.channels is None:
            if expected.absent_reason != REGISTERS_ABSENT_NO_PLAN:
                # No plan = no required set, by rule (TC-5) — not "unresolved".
                unresolved.append(
                    {
                        "meter": meter.asset_no,
                        "asset_id": str(meter.id),
                        "reason": expected.absent_reason,
                    }
                )
            continue
        have = {channel for channel in expected.channels if (str(meter.id), channel) in collected}
        missing = [channel for channel in expected.channels if channel not in have]
        unit = getattr(point, "unit", None)
        rows.append(
            {
                "asset_id": str(meter.id),
                "meter": meter.asset_no,
                "unit_id": str(unit_id) if unit_id else None,
                "unit": getattr(unit, "label", None),
                "premises": getattr(getattr(unit, "premises", None), "address_line", None),
                "route": getattr(getattr(point, "route", None), "code", None),
                "service": getattr(getattr(point, "service", None), "code", None),
                "expected_channels": list(expected.channels),
                "collected_channels": sorted(have, key=_channel_sort_key),
                "missing_channels": missing,
            }
        )
    return rows, unresolved


# ── the per-cycle figures (the completeness bar) ────────────────────────────


def cycle_coverage(
    cycle: Any,
    *,
    period_anchor: date | None = None,
    today: date | None = None,
    resolver: PlanRegisterResolver | None = None,
) -> dict[str, Any]:
    """BR-MET-057's completeness bar for one cycle and one window.

    With `period_anchor` the window is derived in that month (the caller named
    the period); without it, the CURRENT occurrence as of `today`. Figures per
    US-MET-018 §2: expected/collected required RECORDS, completeness % =
    collected ÷ expected, plus the pending-meter roll-up the S25 header reads.
    Before window open nothing is counted (TC-6): the payload states the
    window and `window_opens`, and every figure is honestly zero.
    """
    today = today or _tenant_today()
    if period_anchor is not None:
        window = window_for_period(cycle, period_anchor)
        if window is None:
            return {
                "cycle_id": str(cycle.id),
                "cycle_code": cycle.code,
                "window": None,
                "window_absent_reason": "cycle_schedule_not_set",
            }
        if window[0] > today:
            state = "before_open"
        elif window[1] < today:
            # An explicitly NAMED past period: the window is honestly CLOSED,
            # and the figures still compute — the chase continues after close
            # for a period the clerk names (the story's purpose: gaps found
            # before the bill date, not inside the billing run).
            state = "closed"
        else:
            state = "open"
        window_state = {"period_start": window[0], "period_end": window[1], "state": state}
    else:
        window_state = current_window(cycle, today)
        if window_state is None:
            return {
                "cycle_id": str(cycle.id),
                "cycle_code": cycle.code,
                "window": None,
                "window_absent_reason": "cycle_schedule_not_set",
            }
        window = (window_state["period_start"], window_state["period_end"])

    payload: dict[str, Any] = {
        "cycle_id": str(cycle.id),
        "cycle_code": cycle.code,
        "window": {
            "period_start": window[0].isoformat(),
            "period_end": window[1].isoformat(),
            "state": window_state["state"],
        },
        "days_left": max((window[1] - today).days, 0),
    }
    if window_state["state"] == "before_open":
        # US-MET-018 TC-6: no pending pressure before window open.
        payload["window_opens"] = window[0].isoformat()
        payload.update(
            expected_records=0,
            collected_records=0,
            missing_records=0,
            completeness_pct=None,
            expected_meters=0,
            pending_meters=0,
            rows=[],
            unresolved=[],
        )
        return payload

    rows, unresolved = _meter_rows(cycle, window, resolver=resolver)
    expected_records = sum(len(row["expected_channels"]) for row in rows)
    collected_records = sum(len(row["collected_channels"]) for row in rows)
    missing_records = expected_records - collected_records
    payload.update(
        expected_records=expected_records,
        collected_records=collected_records,
        missing_records=missing_records,
        # Decimal, not float — count arithmetic (US-MET-018 §7: no money math),
        # but this repo puts no figure through float on principle. One decimal
        # place, half-up, the TC-1 rendering ("96.3% (734 ÷ 762)").
        completeness_pct=(
            str(
                (Decimal(collected_records * 100) / Decimal(expected_records)).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            if expected_records
            else None
        ),
        expected_meters=len(rows),
        pending_meters=sum(1 for row in rows if row["missing_channels"]),
        rows=rows,
        unresolved=unresolved,
    )
    return payload


def chase_list(
    cycle: Any, *, period_anchor: date | None = None, today: date | None = None
) -> dict[str, Any]:
    """BR-MET-057's chase list: the meters still missing required registers,
    shaped for the review screen and a CSV export later — unit · premises ·
    meter · route · service · missing channels BY NAME · days left, ordered
    days-left ascending then unit label (EP-MET-03's capability row).

    Bounded by the cycle's own membership (<3,000 connections — BR-MET-055's
    no-unbounded-endpoints posture holds: this can never exceed the cycle).
    """
    coverage = cycle_coverage(cycle, period_anchor=period_anchor, today=today)
    rows = [
        {
            "unit_id": row["unit_id"],
            "unit": row["unit"],
            "premises": row["premises"],
            "meter": row["meter"],
            "asset_id": row["asset_id"],
            "route": row["route"],
            "service": row["service"],
            "missing_channels": row["missing_channels"],
            "days_left": coverage.get("days_left", 0),
        }
        for row in coverage.get("rows", [])
        if row["missing_channels"]
    ]
    rows.sort(key=lambda row: (row["days_left"], row["unit"] or "", row["meter"] or ""))
    out = {
        key: coverage[key]
        for key in (
            "cycle_id",
            "cycle_code",
            "window",
            "window_absent_reason",
            "window_opens",
            "days_left",
            "expected_records",
            "collected_records",
            "missing_records",
            "completeness_pct",
            "expected_meters",
            "pending_meters",
            "unresolved",
        )
        if key in coverage
    }
    out["rows"] = rows
    out["count"] = len(rows)
    return out


def batch_cycle_coverage(batch: Any) -> dict[str, Any] | None:
    """The S28 review step's coverage block for one staged/validated batch.

    `None` (a stated absence, served with its reason by the API) when the
    batch was not tagged with a cycle — coverage is a CYCLE computation
    (BR-MET-057) and a cycle-less batch has no expectation to compare against.

    Meters, not records, because the review step's question is *"which meters
    does this cycle still wait on"*: `missing_after_batch` treats the batch's
    own staged meters as arriving — batches APPEND per cycle at any cadence
    (BR-MET-054), so an earlier batch's committed heads count too; a meter is
    missing only if NEITHER this batch nor a committed head in the window
    covers it.
    """
    cycle = getattr(batch, "cycle", None)
    if cycle is None:
        return None
    anchor = batch.period_month or _tenant_today()
    window = window_for_period(cycle, anchor)
    if window is None:
        return {
            "cycle_id": str(cycle.id),
            "cycle_code": cycle.code,
            "window": None,
            "window_absent_reason": "cycle_schedule_not_set",
        }
    window_start, window_end = window
    meters = _expected_meters(cycle.id, window_end)
    expected_ids = {str(meter.id) for meter in meters}
    in_batch = {
        str(asset_id)
        for asset_id in models.ReadImportRow.objects.filter(
            tenant_id=_tenant_id(), batch=batch, asset_id__isnull=False
        ).values_list("asset_id", flat=True)
    }
    committed = {
        asset_id
        for asset_id, _channel in _collected_heads(
            [meter.id for meter in meters], window_start, window_end
        )
    }
    missing_ids = expected_ids - in_batch - committed
    missing_meter_nos = sorted(meter.asset_no for meter in meters if str(meter.id) in missing_ids)
    cap = 100  # the review block stays light; the chase list serves the full set
    return {
        "cycle_id": str(cycle.id),
        "cycle_code": cycle.code,
        "window": {
            "period_start": window_start.isoformat(),
            "period_end": window_end.isoformat(),
        },
        "expected_meters": len(expected_ids),
        "received_in_batch": len(expected_ids & in_batch),
        "committed_before_batch": len(expected_ids & committed),
        "missing_after_batch": len(missing_ids),
        "missing_meter_nos": missing_meter_nos[:cap],
        "missing_truncated": len(missing_meter_nos) > cap,
    }


# ── the S25 Missing chip (US-MET-019) ───────────────────────────────────────


def missing_records_count(today: date | None = None) -> dict[str, Any]:
    """Missing required RECORDS across every active cycle a clerk can still
    chase in — *"records, not bare meters"* (US-MET-019 §5), window-scoped per
    BR-MET-057 (before open, a cycle contributes nothing — TC-6).

    ⚠ **"CHASE IN" MEANS OPEN *OR* CLOSED-BUT-UNBILLED — BR-MET-132, PO
    2026-08-26.** This counted OPEN windows only until that ruling, which is
    US-MET-019 §5 read literally and which zeroed the chip on the chase days
    themselves: CY-001's window closes 20 Aug, the run is 25 Aug, and on
    22 Aug the chip said 0 over sixty unread meters. The predicate is
    `CHASEABLE_WINDOW_STATES` and the drop condition is now the run consuming
    the period (`current_window`, `period_is_consumed`).

    Returns the count PLUS the unresolved-meter total, because a chip reading
    "3 missing" while eleven meters could not be resolved is a lie by
    omission; the API serves both.
    """
    today = today or _tenant_today()
    resolver = PlanRegisterResolver()
    missing = 0
    unresolved = 0
    cycles = models.Cycle.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True, status="active"
    )
    for cycle in cycles:
        window_state = current_window(cycle, today)
        if window_state is None or window_state["state"] not in CHASEABLE_WINDOW_STATES:
            continue
        coverage = cycle_coverage(cycle, today=today, resolver=resolver)
        missing += coverage.get("missing_records", 0) or 0
        unresolved += len(coverage.get("unresolved", []))
    return {"missing": missing, "unresolved_meters": unresolved}


# ── the Pending derivation on GET /reads (US-MET-012) ───────────────────────


def pending_read_entries(
    *, filters: dict[str, Any] | None = None, q: str | None = None, today: date | None = None
) -> list[dict[str, Any]]:
    """US-MET-012 §1, verbatim: *"Pending = plan-required record (meter ×
    channel, BR-MET-049) with no committed read this cycle — derived, not
    stored."* One entry per missing (meter, channel) across the open windows,
    shaped alongside `read_dict` rows (id-less: nothing exists to address —
    the id is null and `derived` says why), honouring the declared S25 filters
    that can apply to a record that does not exist yet: route, cycle, service,
    channel, asset and the meter-number search.

    ⚠ **THE WINDOW PREDICATE IS THE CHIP'S — `CHASEABLE_WINDOW_STATES`,
    BR-MET-132.** That rule is written about the Missing CHIP and says nothing
    about this list, and leaving the list on the old open-window-only reading
    was considered and rejected: the chip would read "60 missing" on 22 Aug
    while `GET /reads?f.status=pending` returned nothing, so the number a
    clerk is told to act on would have no rows behind it — hard-won law 2, in
    the one place the two surfaces meet. One predicate, named once, so they
    cannot disagree. Recorded as a lane judgment rather than left silent.
    """
    today = today or _tenant_today()
    filters = filters or {}
    resolver = PlanRegisterResolver()
    cycles = models.Cycle.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True, status="active"
    )
    if filters.get("cycle"):
        cycles = cycles.filter(pk=filters["cycle"])
    entries: list[dict[str, Any]] = []
    for cycle in cycles:
        window_state = current_window(cycle, today)
        if window_state is None or window_state["state"] not in CHASEABLE_WINDOW_STATES:
            continue
        coverage = cycle_coverage(cycle, today=today, resolver=resolver)
        for row in coverage.get("rows", []):
            if not row["missing_channels"]:
                continue
            for channel in row["missing_channels"]:
                entries.append(
                    {
                        "id": None,
                        "derived": "pending",  # not stored — BR-MET-049/US-MET-012
                        "meter": row["meter"],
                        "asset_id": row["asset_id"],
                        "channel": channel,
                        "status": "pending",
                        "lifecycle": None,
                        "read_at": None,
                        "consumption": None,
                        "unit_label": row["unit"],
                        "premises": row["premises"],
                        "route": row["route"],
                        "service": row["service"],
                        "cycle_id": coverage["cycle_id"],
                        "cycle_code": coverage["cycle_code"],
                        "window": coverage["window"],
                        "days_left": coverage.get("days_left", 0),
                    }
                )
    if services := filter_values(filters.get("service")):  # OQ-306 — ANY of
        entries = [e for e in entries if e["service"] in services]
    if filters.get("channel"):
        entries = [e for e in entries if e["channel"] == filters["channel"]]
    if filters.get("asset"):
        entries = [e for e in entries if e["asset_id"] == str(filters["asset"])]
    if filters.get("route"):
        route_code = (
            models.Route.objects.filter(tenant_id=_tenant_id(), pk=filters["route"])
            .values_list("code", flat=True)
            .first()
        )
        entries = [e for e in entries if route_code is not None and e["route"] == route_code]
    if q:
        needle = q.strip().lower()
        entries = [e for e in entries if needle in (e["meter"] or "").lower()]
    entries.sort(key=lambda e: (e["days_left"], e["meter"] or "", e["channel"]))
    return entries


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-018@EP-MET-03 (story + BR-MET-049/057 verbatim) · EP-MET-04
#         gate semantics · CR-038 W1 task list · BR-RAT-067/BR-AST-029 context
# generated: 2026-08-26 by the CR-038 W1 backend lane
# checklist: A✔ B=deferred(W2 frontend lane owns the screens — this lane is
#            backend-only by its CR task split) C✔(tests/test_us_met_018_*.py —
#            guard proved RED first, output quoted verbatim) D✔(api.py routes)
#            E=deferred(W2) F✔ G✔ H=deferred(not a 🔒 path — no money, no rate
#            read beyond STRUCTURE, no RLS policy, no idempotency key; counts
#            of registers only)
# exceptions: (1) capacity/percent_of_service meters expect {total} — BR-MET-049
#            names only TOU and demand as set-extending and BR-MET-059 makes
#            `total` the single-register default; REPORTED rather than silent.
#            (2) ⚠ SUPERSEDED 2026-08-26 by BR-MET-132 (OQ-389 RULED) — the
#            chip no longer counts OPEN windows only. It counts OPEN and
#            CLOSED-BUT-UNBILLED and drops a period when a run consumes it.
#            The lane judgment inside that rule is that ONE window is looked
#            at (the most recent to have opened), so an older period a run
#            skipped is not counted; argued in `current_window` and recorded
#            in 12-governance/02-decision-log.md. (3) `_expected_meters` is a READ-ONLY get_model
#            probe on assets (no by-cycle selector published) — the
#            `seams.meter_by_no` Eng disposition, restated. (4) with two
#            OQ-341-overlapping open windows the chip counts the NEWER one —
#            a COUNT must answer while OQ-345 (read attribution) stays refused.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
