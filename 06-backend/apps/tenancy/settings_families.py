# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM 2026-08-08 — the S63–S71
#           Reference-data rule-page cards; their own stories are allocated but
#           NOT yet authored, so this packet builds the ratified endpoints only) ·
#           US-MET-011 (S64 read-validation config — TC-7 "no value is hardcoded",
#           TC-8 negative) · US-TEN-005 (the S8 per-tab save contract reused here)
#           Screens: S64, S66, S69, S70, S71
# Rules:    BR-MET-020 · BR-MET-025 · BR-MET-026 · BR-MET-027 · BR-MET-052 (S64) ·
#           BR-BIL-001 · BR-BIL-002 · BR-BIL-008 · BR-BIL-021 · BR-BIL-029 ·
#           BR-PAY-010 · BR-CUS-050 · BR-RAT-028 (S66) · BR-BIL-017 (S69) ·
#           BR-PAY-013 · BR-PAY-016 · BR-PAY-017 · BR-PAY-018 (S70) ·
#           BR-PAY-019 · BR-BIL-013 · BR-BIL-014 · BR-BIL-018 · BR-REP-022 (S71) ·
#           BR-TEN-024 (atomic per-tab save) · BR-TEN-043 (event-time forward)
# Tests:    06-backend/tests/test_us_ten_settings_rule_pages.py
# Impacts:  apps/tenancy/{models,services,selectors,api}.py · every engine that
#           reads a threshold instead of a constant (metering VEE · billing late
#           fee / guardrail / minimum bill · payments collections + bank match ·
#           reports DSO) — config-over-constant, BR-MET-020's blanket rule
# ───────────────────────────────────────────────────────
"""The five S8 rule-page settings families (11b §2.3, PO-ratified endpoints).

ONE declarative registry, read by services (write path), selectors (read path)
and api (thin). Nothing here touches the database or the ORM: it is the field
law — which parameters exist, what each is worth when a tenant has not touched
it, and what a legal value is.

PROVENANCE RULE FOLLOWED HERE (the whole point of this file being declarative):
every parameter below is named by a SIGNED rule or by the A1 S63–S71 addendum
line for its screen, and carries that rule on the `br` field of its spec. Where
a rule names a parameter but ratifies no default, the default is None and the
docstring says so — nothing was invented, and no parameter exists here that no
rule names. Two consequences worth reading before adding anything:

- `allocation_order` and `correction_approval_mode` accept exactly ONE value
  each. BR-PAY-010 (OQ-010 CLOSED) confirms the DEFAULT order and says "tenant
  configurable" but enumerates no second value — B4 §Payments still carries a
  PLACEHOLDER for partial-payment allocation; BR-BIL-014 (OQ-072 CLOSED) fixes
  v1 at "ALL corrections require System Admin approval" and defers the
  threshold variant to v2. Offering a second value would be answering a
  question finance has not answered (CLAUDE.md: guesses in billing become
  silent production errors). The moment either is ratified, it is one tuple
  entry here — no other file changes.
  **`allocation_order` is the BETWEEN-bill walk (which bill the money meets)
  and is a different parameter from `allocation_class_order`, the WITHIN-bill
  sequence added below.** The two are read by the same engine and neither is
  the other; keeping the names apart is the whole reason a reviewer can tell
  which of BR-PAY-010's two clauses a refusal is about.
- `allocation_class_order` and `tax_remitting_basis_by_authority` are the two
  parameters the PO's rulings of **2026-08-12** created. Both existed as
  BEHAVIOUR before they existed as settings, and both are documented at their
  Param below with the ruling verbatim.
- `back_bill_segment_estimate_source` (S71) is the THIRD, from the PO's ruling
  of the same day closing OQ-191, and it is the one that did NOT exist as
  behaviour first: the behaviour it defaults to REPLACES a refusal that shipped
  hours earlier. Documented at its Param with the ruling verbatim and its
  worked figure (14/28 × 6 kgal = 3 kgal). Like `allocation_class_order`, its
  choice list is MIRRORED from the engine that reads it, and a test asserts the
  copies are equal.
- `settle_up_month` (BR-BIL-017) and `minimum_bill_amount` (BR-BIL-021) default
  to None: the rules name the parameter but ratify no value. None means UNSET,
  never "zero" — a consuming engine must refuse rather than assume, exactly the
  fail-safe BR-MET-020/US-MET-011 TC-9 demands of the read-validation config.

STORAGE (documented choice — see also the migration docstring): `tenant_settings`
already hosts grouped tenant config, and three of the S66 parameters ALREADY
exist there as typed columns (`late_grace_mode`/`late_grace_days` from the B2
header late-fee settings per BR-BIL-002/008, `deposit_interest_rate_annual`
from B2 r9 #5 which is tagged "(S66)" in the schema itself). Those three keep
being the source of truth and are surfaced THROUGH this family — duplicating
them into a document would have created two homes for one rule. Every other
parameter lives in one jsonb document column per family on the same row
(`read_validation`, `billing_defaults`, `budget_billing`, `collections`,
`finance_controls`). jsonb rather than a column each because two families are
not flat — the collections ladder is an ordered list (BR-PAY-017) and the
read-validation floors are per-unit (BR-MET-020) — and one shape for all five
beats a per-family argument.

MONEY/DECIMAL: every decimal parameter is stored and returned as a canonical
decimal STRING and parsed with `Decimal` (CLAUDE.md rule 2 — never binary
floats). A JSON number that arrives as a Python float is converted through its
repr, never through float arithmetic; clients should send decimal strings.

⚠ REPORTED, NOT RESOLVED (spec divergences this file implements one way):
1. B2 r16 #6 PM-proposes `read_validation_settings` as a METERING-owned table.
   This lane may not create a table in another module's app (territory +
   CLAUDE.md "cross-module writes are forbidden"), and 11b §2.3 puts
   GET/PUT /settings/read-validation on the tenancy Settings surface, so the
   S64 document lives on `tenant_settings`. Re-homing is a one-migration move
   when the metering lane wants it; the field names below are B2 r5 #15's.
2. The overcharge guardrail: 11b §2.3 lists it under S66 Billing defaults,
   the EP-TEN-07 scope addendum lists it under S71 Finance controls. It is
   implemented ONCE, on S66, following 11b §2.3 (the ratified endpoint
   inventory) and B2 r10 #6, which calls `overcharge_guardrail_pct` a tenant
   BILLING setting. Named here so the reviewer sees the choice.
3. BR-BIL-021 also names cycle due-days, numbering format, template set, bill
   messages/footer and tax authorities as part of the same tenant billing
   config family. Each already has a different ratified home (BR-BIL-024 puts
   due-days on the CYCLE; /settings/number-series; BR-TEN-033 templates;
   rating tax authorities). None is duplicated here.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from core import errors

# ── parameter spec ──────────────────────────────────────────────────────────
DECIMAL = "decimal"
INTEGER = "int"
BOOLEAN = "bool"
CHOICE = "choice"
INT_LIST = "int_list"
#: An ORDER over a closed set: the stored value is a PERMUTATION of `choices` —
#: every member present, each exactly once, and the sequence is the setting.
#: Added 2026-08-12 for `allocation_class_order`; see that Param.
CHOICE_SEQUENCE = "choice_sequence"
#: A per-item CHOICE: `{item key: one of choices}`. An item with no entry is
#: UNSET, and unset is a real state — never a default in disguise. Added
#: 2026-08-12 for `tax_remitting_basis_by_authority`; see that Param.
CHOICE_MAP = "choice_map"


@dataclass(frozen=True)
class Param:
    """One tenant-settable parameter.

    `br` is the rule that NAMES the parameter (and, where one exists, ratifies
    its default) — it is carried into refusals so a 422 can cite its law.
    `column` non-None means the value lives in that EXISTING typed column on
    `tenant_settings` instead of the family's jsonb document.
    """

    key: str
    kind: str
    default: Any
    br: str
    minimum: Any = None
    maximum: Any = None
    exclusive_min: bool = False
    choices: tuple[str, ...] = ()
    nullable: bool = False
    column: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Family:
    """One rule page: its endpoint slug, its jsonb column, its parameters."""

    slug: str
    document_field: str
    screen: str
    audit_action: str
    params: tuple[Param, ...]
    cross_checks: tuple[Callable[[dict[str, Any]], list[dict[str, Any]]], ...] = field(
        default_factory=tuple
    )

    @property
    def by_key(self) -> dict[str, Param]:
        return {param.key: param for param in self.params}


def _field_error(key: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": key, "code": code, "message_key": message_key, "params": params}


# ── S64 · Read validation & estimation rules ────────────────────────────────
# ⚠ SUPERSEDED (CR-038 A1, PO 2026-08-26 → served from apps/metering — see the
# note on FAMILIES below; kept defined for migration 0004's dotted-path
# default). Original provenance, still true of the figures:
# BR-MET-020 (OQ-002 CLOSED, PO R6) ratifies: high 200% + absolute floors
# 50 kWh / 1 kgal · low 25% · days 25–35 flag / 20–45 hard. B2 r5 #15 adds
# est_method trailing_3_daily_avg (BR-MET-026) + est_max_consecutive 2
# (BR-MET-027). US-MET-011 §5 adds three S64-card extensions marked
# PROPOSED-SCHEMA there: zero_scope, mismatch_default_pct (BR-MET-025's
# 3% sample), tou_sum_tolerance_pct (BR-MET-052's confirmed ±1%).
ZERO_SCOPES = ("active_non_vacant", "all", "off")
# ⚠ **THIS TUPLE IS STALE ON PURPOSE AND IS NOT THE PRODUCT'S ANSWER.** The
# `read_validation` family is NOT in `FAMILIES` — it was re-homed to metering by
# `CR-038` A1 and is kept defined only because migration 0004 references
# `default_read_validation` by dotted path (see the note above `FAMILIES`). Since
# `CR-079` (PO 2026-09-07) the LIVE vocabulary is **seven** methods, owned by
# `apps.metering.estimation.EST_METHODS`, of which `RUNNABLE_EST_METHODS` is the
# five the engine can actually run. A reader who took the line below for the
# product's answer would believe there is still exactly one.
EST_METHODS = ("trailing_3_daily_avg",)  # BR-MET-026 names exactly one method


def _check_day_bounds(merged: dict[str, Any]) -> list[dict[str, Any]]:
    """US-MET-011 §5: "soft within hard; min < max" — the soft (flag) window
    must sit inside the hard window, and each window must be a real window."""
    problems: list[dict[str, Any]] = []
    soft_min, soft_max = merged["days_soft_min"], merged["days_soft_max"]
    hard_min, hard_max = merged["days_hard_min"], merged["days_hard_max"]
    if soft_min >= soft_max:
        problems.append(
            _field_error(
                "days_soft_max",
                errors.VAL_RANGE,
                "settings.read_validation.day_window_inverted",
                br="BR-MET-020",
                min=soft_min,
                max=soft_max,
            )
        )
    if hard_min >= hard_max:
        problems.append(
            _field_error(
                "days_hard_max",
                errors.VAL_RANGE,
                "settings.read_validation.day_window_inverted",
                br="BR-MET-020",
                min=hard_min,
                max=hard_max,
            )
        )
    if hard_min > soft_min or hard_max < soft_max:
        problems.append(
            _field_error(
                "days_soft_min",
                errors.VAL_RANGE,
                "settings.read_validation.soft_outside_hard",
                br="BR-MET-020",
                soft=[soft_min, soft_max],
                hard=[hard_min, hard_max],
            )
        )
    return problems


READ_VALIDATION = Family(
    slug="read-validation",
    document_field="read_validation",
    screen="S64",
    audit_action="settings.read_validation.updated",
    params=(
        Param("high_pct", DECIMAL, "200", "BR-MET-020", minimum=0, exclusive_min=True),
        Param("high_abs_kwh", DECIMAL, "50", "BR-MET-020", minimum=0),
        Param("high_abs_kgal", DECIMAL, "1", "BR-MET-020", minimum=0),
        Param("low_pct", DECIMAL, "25", "BR-MET-020", minimum=0, maximum=100, exclusive_min=True),
        Param("zero_scope", CHOICE, "active_non_vacant", "BR-MET-020", choices=ZERO_SCOPES),
        Param("days_soft_min", INTEGER, 25, "BR-MET-020", minimum=1),
        Param("days_soft_max", INTEGER, 35, "BR-MET-020", minimum=1),
        Param("days_hard_min", INTEGER, 20, "BR-MET-020", minimum=1),
        Param("days_hard_max", INTEGER, 45, "BR-MET-020", minimum=1),
        Param("mismatch_default_pct", DECIMAL, "3", "BR-MET-025", minimum=0),
        Param("tou_sum_tolerance_pct", DECIMAL, "1", "BR-MET-052", minimum=0, exclusive_min=True),
        Param("est_method", CHOICE, "trailing_3_daily_avg", "BR-MET-026", choices=EST_METHODS),
        Param("est_max_consecutive", INTEGER, 2, "BR-MET-027", minimum=1),
    ),
    cross_checks=(_check_day_bounds,),
)


# ── S66 · Billing defaults ──────────────────────────────────────────────────
# BR-BIL-001 late fee = max($5, 1.5% × overdue portion) · BR-BIL-008 grace
# default 5 calendar days, tenant 0–30 · BR-BIL-002 grace mode calendar |
# business · BR-BIL-029 overcharge guardrail default 200% · BR-PAY-010
# allocation order default oldest-invoice-first · BR-CUS-050/057 (B2 r9 #5)
# deposit interest, DEFAULT 0, tagged (S66) in the schema itself · BR-BIL-021
# names "minimum-bill amounts" as a tenant FALLBACK — no value is ratified and
# BR-RAT-028 makes NULL mean "none", so the default here is None.
GRACE_MODES = ("calendar", "business")
ALLOCATION_ORDERS = ("oldest_invoice_first",)  # BR-PAY-010; see module docstring

#: THE FOUR WITHIN-INVOICE LINE CLASSES, in BR-PAY-038's ruled sequence:
#: usage+base → taxes → the tenant-defined class → fees LAST.
#:
#: MIRRORED from `apps.payments.allocation.ALLOCATION_CLASSES`, not imported:
#: tenancy owns no payments knowledge and an import edge tenancy → payments
#: would be one. `allocation.py` mirrors the same four into
#: `apps.billing.rating_seam` for the same reason, and a test asserts the copies
#: are EQUAL so a signed order cannot come to exist twice with two meanings
#: (tests/test_po_20260812_allocation_class_order_setting.py). If this tuple is
#: ever edited without that test going red, the order the tenant sees and the
#: order the engine walks have parted company.
ALLOCATION_CLASS_SEQUENCE = ("usage_base", "taxes", "tenant_defined", "fees")

#: ── THE BILL RUN'S STANDING ANSWERS (`BR-BIL-1040`, `DEF-BIL-5255`) ─────────
#: Screen 16's `DEFAULTS` group asks a clerk three questions ONCE for a whole
#: run — *when there is no reading*, *when a bill looks unusually large*,
#: *unusual days* — and the control has to open on something. **The PO's
#: instruction of 2026-09-14 is that the something is never a literal:** *"no
#: hardcoding"*. So the value a run opens on is a tenant setting with a default
#: this platform supplies, and `apps.billing.runs.create_run` writes whatever
#: the clerk left it at onto the run itself.
#:
#: MIRRORED from `apps.billing.decisions.CHOICES_BY_CASE`, not imported — the
#: `ALLOCATION_CLASS_SEQUENCE` precedent two blocks up, for its reason: tenancy
#: owns no billing knowledge and an import edge tenancy → billing would be one.
#: `tests/test_br_bil_1040_run_case_defaults.py` asserts the copies are EQUAL,
#: so a case that gains or loses a choice cannot come to mean two things.
#:
#: THE THREE SEEDED VALUES ARE THE DRAWING'S OWN, and each is a choice the
#: engine already implements: *Estimate from history* → `estimate`, *Hold it
#: for review* → `investigate`, *Pro-rate by days* → `prorate_to_cycle_days`.
#: The last two HOLD the account rather than billing it, which the drawing says
#: in its own helper text (*"Holds the bill - pricing not built"*).
RUN_MISSING_READ_CHOICES = ("estimate", "hold", "bill_without_service")
RUN_HIGH_USAGE_CHOICES = ("bill_as_is", "investigate")
RUN_DAYS_THRESHOLD_CHOICES = ("prorate_to_cycle_days", "wait_next_cycle", "bill_as_is")

BILLING_DEFAULTS = Family(
    slug="billing-defaults",
    document_field="billing_defaults",
    screen="S66",
    audit_action="settings.billing_defaults.updated",
    params=(
        Param("late_pct", DECIMAL, "1.5", "BR-BIL-001", minimum=0),
        Param("late_min_amount", DECIMAL, "5", "BR-BIL-001", minimum=0),
        Param(
            "late_grace_days",
            INTEGER,
            5,
            "BR-BIL-008",
            minimum=0,
            maximum=30,
            column="late_grace_days",
        ),
        Param(
            "late_grace_mode",
            CHOICE,
            "calendar",
            "BR-BIL-002",
            choices=GRACE_MODES,
            column="late_grace_mode",
        ),
        Param(
            "minimum_bill_amount",
            DECIMAL,
            None,
            "BR-BIL-021",
            minimum=0,
            nullable=True,
            note="tenant FALLBACK only — per-plan/per-service minimums win (BR-RAT-028)",
        ),
        Param(
            "overcharge_guardrail_pct", DECIMAL, "200", "BR-BIL-029", minimum=0, exclusive_min=True
        ),
        Param(
            "allocation_order",
            CHOICE,
            "oldest_invoice_first",
            "BR-PAY-010",
            choices=ALLOCATION_ORDERS,
        ),
        # ── THE ALLOCATION SEQUENCE, PO ruling 2026-08-12 ──────────────────
        # Verbatim: *"Cant we give option to user to set the rule in settings;
        # Im not sure how Utilities are going to set settlement rules ; they
        # might differ in case of HOA or SUb metering ; better to let user set
        # the sequence; we can give default option and allow them to change the
        # order"*.
        #
        # BR-PAY-010's second clause ("within invoice usage+base → taxes → fees
        # last"), as EXTENDED by BR-PAY-038 to four classes on 2026-08-11. The
        # engine has taken this as an argument since it was written
        # (`allocation.allocate_payment(class_order=…)`); until 2026-08-12 the
        # only thing missing was somewhere for a tenant to keep their answer.
        #
        # THE DEFAULT IS THE 11 AUGUST ORDER, UNMOVED, and so is its worked
        # figure: usage+base $100.58 + tax $8.30 + a tenant-defined service fee
        # $15.00 + a late fee $5.00 = $128.88; a $120.00 payment meets 100.58,
        # then 8.30, then 11.12 of the 15.00, and the late fee stays LAST at
        # 0.00. A tenant who wants tax first sets it; nobody's figure moves
        # because this parameter exists.
        Param(
            "allocation_class_order",
            CHOICE_SEQUENCE,
            list(ALLOCATION_CLASS_SEQUENCE),
            "BR-PAY-038",
            choices=ALLOCATION_CLASS_SEQUENCE,
            note="a PERMUTATION of the four classes — all four, each once. An order that "
            "dropped one would stop allocating money to it while every bill still footed",
        ),
        Param(
            "deposit_interest_rate_annual",
            DECIMAL,
            "0",
            "BR-CUS-050",
            minimum=0,
            column="deposit_interest_rate_annual",
        ),
        # ── THE BILL RUN'S STANDING ANSWERS — BR-BIL-1040, DEF-BIL-5255 ────
        # Screen 16's DEFAULTS group, the blueprint's *"single biggest
        # error-reducer in this redraw"*. Each is the value the run's control
        # OPENS on; `bill_runs.case_defaults` records what the clerk left it at,
        # so changing a setting here never reaches a run already in flight.
        Param(
            "run_default_missing_read",
            CHOICE,
            "estimate",
            "BR-BIL-1040",
            choices=RUN_MISSING_READ_CHOICES,
            note="screen 16 'When there is no reading' — 'Estimate from history'. "
            "'hold' and 'bill_without_service' are BR-BIL-015's other two, verbatim",
        ),
        Param(
            "run_default_high_usage",
            CHOICE,
            "investigate",
            "BR-BIL-1040",
            choices=RUN_HIGH_USAGE_CHOICES,
            note="screen 16 'When a bill looks unusually large' — 'Hold it for review'. "
            "'investigate' HOLDS the account out of the run (decisions.HOLDING_CHOICES)",
        ),
        Param(
            "run_default_days_threshold",
            CHOICE,
            "prorate_to_cycle_days",
            "BR-BIL-1040",
            choices=RUN_DAYS_THRESHOLD_CHOICES,
            note="screen 16 'Unusual days' — 'Pro-rate by days'. ⚠ It HOLDS: no signed "
            "rule scales a measured consumption to N days, which the drawing's own "
            "helper says out loud ('Holds the bill - pricing not built')",
        ),
        # ── CR-181-BRC10 Q4 — HOW LONG A CLOSED ACCOUNT MAY BE REOPENED ─────
        # PO ruling 2026-10-13, verbatim: *"Q4 - keep 5 years right now"*. A
        # returning customer moving back into the SAME unit may have their old
        # account reopened at move-in only when it closed within this many
        # years; an older one gets a new account (`customers.move_in_reopen`).
        # *"right now"* is why it is a setting and not a constant. 0 turns
        # reopening off.
        Param(
            "reopen_within_years",
            INTEGER,
            5,
            "BR-CUS-1119",
            minimum=0,
            maximum=50,
            note="PO 2026-10-13 Q4 '5 years right now'; read by customers.move_in_reopen",
        ),
        # ── CR-183-BRC10 B3 — HOW SHORT AND HOW LONG A TEMPORARY STOP MAY BE ──
        # PO ruling 2026-10-14, verbatim: *"No minimum, 12 months maximum, set
        # in Settings. - this is correct - also set min limit to 10 days for
        # time being"*. Approval of a temporary stop outside these is refused by
        # name (`customers.temporary_stop`). *"for time being"* is why each is a
        # setting and not a constant. Worked: SR-26-0017 asks 13 Oct → 16 Oct,
        # 3 days, and is refused under the default 10.
        Param(
            "temporary_stop_min_days",
            INTEGER,
            10,
            "BR-CUS-1121",
            minimum=1,
            maximum=365,
            note="PO 2026-10-14 B3 '10 days for time being'; read by customers.temporary_stop",
        ),
        Param(
            "temporary_stop_max_months",
            INTEGER,
            12,
            "BR-CUS-1121",
            minimum=1,
            maximum=60,
            note="PO 2026-10-14 B3 '12 months maximum'; read by customers.temporary_stop",
        ),
    ),
)


# ── S69 · Budget billing rules ──────────────────────────────────────────────
# BR-BIL-017 (OQ-068 CLOSED) ratifies every value below except the settle-up
# month: "level = trailing-12-month average (whole $); eligibility = 12-mo
# history; auto re-level at ±20% drift each 6 mo; annual settle-up month;
# off-budget after 2 missed payments — every parameter a tenant setting with
# these as seeded defaults; per-account level override bounded ±30%".
LEVEL_ROUNDINGS = ("whole_dollar",)  # BR-BIL-017 "whole $" — the only ratified mode

BUDGET_BILLING = Family(
    slug="budget-billing",
    document_field="budget_billing",
    screen="S69",
    audit_action="settings.budget_billing.updated",
    params=(
        Param("eligibility_months", INTEGER, 12, "BR-BIL-017", minimum=1),
        Param("level_rounding", CHOICE, "whole_dollar", "BR-BIL-017", choices=LEVEL_ROUNDINGS),
        Param("relevel_drift_pct", DECIMAL, "20", "BR-BIL-017", minimum=0, exclusive_min=True),
        Param("relevel_cadence_months", INTEGER, 6, "BR-BIL-017", minimum=1),
        Param(
            "settle_up_month",
            INTEGER,
            None,
            "BR-BIL-017",
            minimum=1,
            maximum=12,
            nullable=True,
            note="rule names the parameter, ratifies no month — UNSET until the tenant picks",
        ),
        Param("drop_off_missed_payments", INTEGER, 2, "BR-BIL-017", minimum=1),
        Param("override_bound_pct", DECIMAL, "30", "BR-BIL-017", minimum=0, exclusive_min=True),
    ),
)


# ── S70 · Collections & notices rules ───────────────────────────────────────
# BR-PAY-017 ladder: due+3 reminder → late fee → 10-day → 5-day → 48h certified
# final · BR-PAY-016 plan notices: reminder 3 days before installment,
# missed-notice day+1, 2nd miss VOIDS the plan · BR-PAY-013 N NSFs (default 2,
# config) → cash-only/no-autopay privilege flag · BR-PAY-018 paper suppressed
# until the address is verified (config). Key names for the last two are B2
# r14 #5's own ("nsf_privilege_n", "suppress_paper_on_bad_address"); the first
# three keys are r14 #5's "collection-ladder intervals".
# NOT configurable and deliberately absent: whether the final notice is
# certified (A19 rule 3 / BR-PAY-017 fix it) and the paper-only v1 channel set.


def _check_notice_tiers(merged: dict[str, Any]) -> list[dict[str, Any]]:
    """BR-PAY-017: the ladder escalates — each tier fires nearer disconnection
    than the one before it, so the day list must be strictly descending."""
    tiers = merged["notice_tier_days"]
    if not tiers:
        return [
            _field_error(
                "notice_tier_days",
                errors.VAL_REQUIRED,
                "settings.collections.ladder_empty",
                br="BR-PAY-017",
            )
        ]
    if any(later >= earlier for earlier, later in zip(tiers, tiers[1:])):
        return [
            _field_error(
                "notice_tier_days",
                errors.VAL_RANGE,
                "settings.collections.ladder_not_descending",
                br="BR-PAY-017",
                tiers=tiers,
            )
        ]
    return []


COLLECTIONS = Family(
    slug="collections",
    document_field="collections",
    screen="S70",
    audit_action="settings.collections.updated",
    params=(
        Param("reminder_days_after_due", INTEGER, 3, "BR-PAY-017", minimum=0),
        Param("notice_tier_days", INT_LIST, [10, 5], "BR-PAY-017", minimum=1),
        Param("final_notice_hours", INTEGER, 48, "BR-PAY-017", minimum=1),
        Param("plan_reminder_days_before", INTEGER, 3, "BR-PAY-016", minimum=0),
        Param("plan_missed_notice_days_after", INTEGER, 1, "BR-PAY-016", minimum=0),
        Param("plan_void_after_misses", INTEGER, 2, "BR-PAY-016", minimum=1),
        Param("nsf_privilege_n", INTEGER, 2, "BR-PAY-013", minimum=1),
        Param("suppress_paper_on_bad_address", BOOLEAN, True, "BR-PAY-018"),
        # ── two settings the PO ruled on 2026-08-12 that had no storage until
        # 2026-08-15 (DEF-097). Both were CLOSED questions whose rulings implied
        # a stored value, and nothing compared the ruling against the registry —
        # so the collections engine took them as arguments and refused by name
        # rather than inventing a default, which is why they were findable.
        #
        # The floor: the PO ruled the SAME $25 floor applies to the whole ladder
        # (OQ-157), and per-utility (OQ-137) — "$38 vs $180 average-bill
        # utilities" was their own reasoning for why one number cannot fit both.
        # Worked: a **$2.40** unpaid balance earns no fee, no $8.00 certified
        # letter and no notice; **$25.00 exactly IS chased** (the comparison is
        # strict, asserted on the payments side).
        Param("ladder_balance_floor_amount", DECIMAL, "25", "BR-PAY-017", minimum=0),
        # The pause threshold: a partial payment pauses the ladder only if it
        # clears a percentage of what is outstanding (OQ-136). Worked, on the
        # PO's own case: **$150 against $948 is 15.8%** and does NOT pause; at
        # 25% it would need **$237.00**, at 50% **$474.00**. Seeded at the lower
        # of the two figures the PO named.
        Param(
            "partial_payment_pause_percent",
            DECIMAL,
            "25",
            "BR-PAY-016",
            minimum=0,
            maximum=100,
        ),
        # ── CR-059 CS-10 (2026-09-02) — the scheduled collection sequence.
        # CS-10's ONE new rule, verbatim: *"The scheduled run is per-utility and
        # runs on that utility's business day, not on UTC."* Both halves of that
        # sentence are here: PER-UTILITY is why these are Params rather than
        # deployment settings, and the BUSINESS DAY is what
        # `apps/payments/collections_schedule.py` reads `tenant_today()` for.
        #
        # ⚠ **THE SWITCH SEEDS `False`, AND THAT IS HARD-WON LAW 3.** A schedule
        # that started writing to customers the moment the code deployed would
        # be a change to a utility's collections practice made by a deploy.
        # Worked: on an account 62 days overdue, every rung is past due at once,
        # so the first unattended pass on a tenant nobody switched on would post
        # the friendly reminder — and the next four days would walk it to the
        # $8.00 certified 48-hour final. Nobody chose that; nobody typed it.
        #
        # The HOUR is stored beside it and is inert while the switch is off.
        # **6 is a SEEDED DEFAULT and not a ruling** — the same posture the four
        # BR-PAY-017 intervals above take. It is early enough that a notice
        # printed overnight is on a clerk's desk when the utility opens, and a
        # utility that wants another hour changes one field on S70.
        Param("collections_schedule_enabled", BOOLEAN, False, "BR-PAY-017"),
        Param(
            "collections_schedule_hour",
            INTEGER,
            6,
            "BR-PAY-017",
            minimum=0,
            maximum=23,
        ),
    ),
    cross_checks=(_check_notice_tiers,),
)


# ── S71 · Finance controls ──────────────────────────────────────────────────
# BR-PAY-019 bank auto-match: amount + date ±3 days, a finance setting (B2
# r12 #10) · BR-BIL-013 (OQ-070 CLOSED) small-balance write-off default $5,
# tenant-config 0–50 · BR-REP-022 DSO target, default 15 days · BR-BIL-014
# (OQ-072 CLOSED) v1 = ALL corrections need System Admin approval · BR-BIL-018
# (OQ-071 CLOSED) back-bill window capped at 12 months, theft cases EXEMPT.
CORRECTION_APPROVAL_MODES = ("all",)  # BR-BIL-014 v1; see module docstring

#: WHERE A SPLIT BACK-BILL SEGMENT'S USAGE COMES FROM (BR-BIL-018 as amended,
#: OQ-191). MIRRORED from `apps.billing.backbill.SEGMENT_ESTIMATE_SOURCES` —
#: tenancy owns no billing knowledge, so the two copies are asserted equal by
#: tests/test_po_20260812_backbill_segment_estimate.py, for the reason
#: `ALLOCATION_CLASS_SEQUENCE` gives: a tenant saving a value the engine spells
#: differently would keep the old behaviour while the screen said otherwise.
BACK_BILL_SEGMENT_ESTIMATE_SOURCES = ("day_weighted", "metering")

#: BR-LED-002's two remitting bases. MIRRORED from
#: `apps.ledger.journal.REMITTING_BASES` — the same two strings
#: `record_tax_remittance` already accepts — rather than imported, for the
#: reason `ALLOCATION_CLASS_SEQUENCE` gives: tenancy owns no ledger knowledge.
#: A test asserts the two copies are equal
#: (tests/test_po_20260812_remitting_basis_setting.py), because a second
#: spelling of a basis is a utility filing on the wrong one.
REMITTING_BASES = ("billed", "collected")

#: ⚠ **WHO PAYS THE CARD FEE — `OQ-1394`, CLOSED 2026-09-04.** The question
#: offered three exclusive options and the PO took the first two TOGETHER,
#: verbatim: *"we have to give both the options so far some utilities abosrb it
#: other pass it to customer ; so we have to flexible and create a flag
#: somewhere to on and off it"*, restated 2026-09-05 as *"Either Utility will
#: abosrb or Customer will absorb - we need to give utility flexibility to
#: choose"*. There is no third value: *bank-only* is not a fee policy, it is a
#: utility not switching card payments on.
CARD_FEE_PAYERS = ("utility", "customer")

FINANCE_CONTROLS = Family(
    slug="finance-controls",
    document_field="finance_controls",
    screen="S71",
    audit_action="settings.finance_controls.updated",
    params=(
        Param("bank_match_date_tolerance_days", INTEGER, 3, "BR-PAY-019", minimum=0),
        # ── WHO PAYS THE CARD FEE, PO ruling 2026-09-04 (OQ-1394), restated
        # 2026-09-05. Both answers are lawful and neither is lawful everywhere,
        # so the product holds a switch rather than a policy.
        #
        # **THE DEFAULT IS `utility` AND THAT IS THE SAFETY ARGUMENT**
        # (hard-won law 3 — the unsafe option must be the one you type).
        # Surcharging is regulated in several states and prohibited outright in
        # some; a utility that never opens this screen must not begin adding a
        # line to its customers' bills because a default said so.
        #
        # ⚠ **`customer` IS NOT A BOOLEAN'S OTHER HALF — IT IS AN OBLIGATION.**
        # Turning it on means the fee must be COMPUTED from the processor's own
        # schedule, DISCLOSED before the commit (a customer paying $142.18 sees
        # the surcharge and the new total BEFORE pressing, never after), and
        # CHECKED against that customer's state. None of those three exist yet
        # and none can: there is no processor and therefore no fee schedule.
        # Until one lands, `apps/payments` REFUSES to price a surcharge by name
        # rather than inventing a percentage — the switch stores the utility's
        # intention, and the intention is not the arithmetic.
        Param("card_fee_payer", CHOICE, "utility", "OQ-1394", choices=CARD_FEE_PAYERS),
        # ── THE BANK-MATCH AMOUNT TOLERANCE, PO ruling 2026-08-17 (CR-008 #7)
        # Verbatim: *"Okay. We can take it as threshold from user"*, answering
        # whether r10's *"bank match tolerance $0.05"* should be built.
        #
        # ⚠ TODAY THE AMOUNT MATCH IS EXACT TO THE PENNY. `apps/payments/
        # reconciliation.auto_match` compared `batch.recorded_total ==
        # line.amount` and nothing else, so this parameter does not CHANGE a
        # figure — it introduces a window where there was none, on money.
        #
        # **THE DEFAULT IS 0 AND THAT IS THE WHOLE SAFETY ARGUMENT**
        # (hard-won law 3 — the unsafe option must be the one you type).
        # `abs(recorded_total − amount) <= 0` is exactly `==`, so a tenant who
        # never opens this screen keeps penny-exact matching for ever. Seeding
        # r10's 0.05 would silently start auto-matching, reconciling and
        # LOCKING (BR-PAY-004) a $412.30 deposit against a $412.27 bank line
        # for every utility in the product, on the day this shipped.
        #
        # The cap is 5.00: a tolerance is for a rounding or a bank's cent, and
        # a "tolerance" wide enough to swallow a whole small payment is a
        # different feature (a fee derivation) that OQ-160 forbids deriving.
        Param(
            "bank_match_amount_tolerance",
            DECIMAL,
            "0",
            "BR-PAY-019",
            minimum=0,
            maximum=5,
            note="CR-008 #7 (PO 2026-08-17). 0 = today's penny-exact match, and it is the "
            "seeded default deliberately. Read by apps.payments.settings_seam."
            "match_amount_tolerance",
        ),
        # ⚠ TWO WRITE-OFF FIGURES LIVE ON THIS PAGE AND THEY MEAN DIFFERENT
        # THINGS. The names below are the only thing standing between a utility
        # setting one when they meant the other (CR-008 ruling 2), so read both:
        #
        #   `write_off_threshold_amount`          $5, capped $50 — BR-BIL-013's
        #     AUTOMATIC small-balance write-off at a FINAL bill. A $0.40 residue
        #     is cleared without anybody deciding anything.
        #   `write_off_approval_threshold_amount` $0 — the MANUAL collections
        #     write-off (`apps/payments/writeoffs.py`). Above it, an approver is
        #     required; at or below it, the requester's own act is the decision.
        #
        # The keys are deliberately NOT renamed (a stored-key migration buys
        # nothing); the SCREEN carries the unambiguous labels.
        Param("write_off_threshold_amount", DECIMAL, "5", "BR-BIL-013", minimum=0, maximum=50),
        # ── THE MANUAL WRITE-OFF APPROVAL THRESHOLD, CR-008 ruling 2 ────────
        # The PO delegated this one — *"decide for me"* — and the decision is
        # recorded in 12-governance/11-change-requests.md under CR-008.
        #
        # **THE DEFAULT IS 0.00, NOT r10's $5,000.** Today EVERY manual
        # write-off of any size needs a System-Admin approval: `writeoffs.py`
        # has no threshold at all. Since an amount must be > 0 (the service
        # refuses zero), a threshold of 0 means no write-off ever qualifies —
        # today's behaviour, preserved exactly. Shipping 5000 would mean every
        # write-off under $5,000 stopped needing approval the moment this
        # landed, which is a LOOSENING of a money control arriving as a
        # settings default (hard-won law 3).
        Param(
            "write_off_approval_threshold_amount",
            DECIMAL,
            "0",
            "BR-PAY-020",
            minimum=0,
            note="CR-008 ruling 2 (2026-08-17). A manual write-off ABOVE this needs an "
            "approver; 0 = every one does, which is what the code did before this "
            "parameter existed. NOT the same figure as write_off_threshold_amount",
        ),
        # ── THE MANUAL CREDIT / ADJUSTMENT APPROVAL THRESHOLD ───────────────
        # CR-059 CS-35, 2026-09-02. *"requires Admin approval above a
        # tenant-set threshold, matching write-offs"* — so it is deliberately
        # the same SHAPE as `write_off_approval_threshold_amount` two lines up,
        # and a THIRD figure on this page, which is exactly why the comment
        # block above exists. Read them together:
        #
        #   `write_off_threshold_amount`                    $5  — automatic
        #     small-balance clear-out at a FINAL bill (BR-BIL-013). Nobody
        #     decides anything.
        #   `write_off_approval_threshold_amount`           $0  — the MANUAL
        #     collections write-off. Above it, an approver is required.
        #   `credit_adjustment_approval_threshold_amount`   $0  — a manual
        #     CREDIT or ADJUSTMENT recorded on an account. Above it, the
        #     recorder must hold System Admin.
        #
        # **THE DEFAULT IS 0.00 AND THAT MEANS EVERY ONE NEEDS AN ADMIN.** A
        # credit is money given away, so the loose setting is the one a utility
        # has to type and be seen typing (hard-won law 3 — the unsafe option
        # must be the one you type). It matches the write-off default for the
        # same reason and by the same argument (CR-008 ruling 2), and it
        # preserves today's behaviour exactly: before this parameter existed
        # there was no way to record a credit row at all.
        Param(
            "credit_adjustment_approval_threshold_amount",
            DECIMAL,
            "0",
            "BR-PAY-020",
            minimum=0,
            note="CR-059 CS-35 (2026-09-02). A manual credit or adjustment ABOVE this "
            "needs a System Admin to record it; 0 = every one does. NOT the same figure "
            "as either write-off threshold above",
        ),
        # ── THE ALLOWANCE FOR DOUBTFUL ACCOUNTS, PO ruling 2026-09-03 ──────
        # `CR-060` C5 / task T15. PO verbatim: *"Why I recommended deferring it.
        # Three reasons: let's do this"* — the heading of the argument FOR
        # deferring, quoted back and chosen against. The three reasons are in
        # `12-governance/02-decision-log.md` so the trade is on file.
        #
        # **THE SWITCH DEFAULTS TO FALSE AND THAT IS THE WHOLE SAFETY ARGUMENT**
        # (hard-won law 3 — the unsafe option must be the one you type), and it
        # is a lane judgment recorded in the decision log rather than a thing
        # the PO was asked twice about (law 13). Turning it on for every tenant
        # would move a SIGNED posting under utilities who never chose the
        # policy: BR-PAY-020's write-off is `DR 6900 Bad debt / CR 1200`, and
        # under an allowance it becomes `DR 1290 / CR 1200`. Reason (3) of the
        # three the PO was shown is still true of everyone who leaves it off —
        # *most utilities under 3,000 connections are not audited and never book
        # one* — so off is not a deferral, it is the correct answer for them.
        #
        # ⚠ **THE FOUR RATES ARE SETTINGS AND NOT CONSTANTS, AND THE REASON IS
        # THE PO's OWN.** Reason (2) of the three: *the percentages are a
        # judgment about a utility's own customers, not a feature, and honestly
        # setting them needs a year of that utility's history.* Hardcoding one
        # would be this product asserting something about somebody else's book
        # of debts. The defaults below are the figures the PO was shown.
        #
        # **WORKED, on those figures**, and every one is asserted in
        # `tests/test_cr060_t15_allowance.py`:
        #
        #     $9,200.00 current   × 1%  =    92.00
        #     $3,100.00 1–30 days × 5%  =   155.00
        #     $1,800.00 31–60     × 20% =   360.00
        #     $1,233.30 61+       × 50% =   616.65
        #     ────────────────────────────────────
        #     $15,333.30 owed           = $1,223.65 allowance
        #
        # and the balance sheet reads *"owed $15,333.30, realistically expect
        # $14,109.65"*.
        #
        # ⚠ **FOUR RATES OVER THE PRODUCT'S FIVE AGEING BANDS, AND THE FOLD IS
        # DELIBERATE.** `apps/payments/outstandings.AGEING_BUCKETS` is
        # current · 1-30 · 31-60 · 61-90 · 90+. The PO signed FOUR percentages
        # against FOUR amounts, so `61-90` and `90+` are both priced by
        # `allowance_rate_61_plus`. Adding a fifth rate would split $1,233.30
        # across two bands and move $1,223.65 — a figure the PO has seen — for
        # no ruling. A utility that wants to price 90+ harder is a later
        # setting, not a silent one.
        #
        # Rates are stored as FRACTIONS to six decimals (`0.010000` = 1%),
        # which is CLAUDE.md hard rule 2 and matches `taxes.rate`. They are NOT
        # percentage points: `discount_versions.value` stores those and the two
        # spellings a hundredfold apart is exactly the shape DIS-02's own tests
        # exist to keep out of money.
        Param(
            "allowance_for_doubtful_accounts_enabled",
            BOOLEAN,
            False,
            "BR-LED-795",
            note="CR-060 T15 (PO 2026-09-03). FALSE = today's DIRECT write-off, DR 6900 "
            "Bad debt / CR 1200, unchanged. TRUE = the month-end estimate posts DR 6900 / "
            "CR 1290 and a write-off CONSUMES the allowance, DR 1290 / CR 1200 — never "
            "both, or bad debt is expensed twice",
        ),
        Param(
            "allowance_rate_current",
            DECIMAL,
            "0.010000",
            "BR-LED-795",
            minimum=0,
            maximum=1,
            note="CR-060 T15. A FRACTION, not percentage points: 0.010000 = 1%. The "
            "default is the figure shown to the PO on 2026-09-03 ($9,200.00 → $92.00)",
        ),
        Param(
            "allowance_rate_1_30",
            DECIMAL,
            "0.050000",
            "BR-LED-795",
            minimum=0,
            maximum=1,
            note="CR-060 T15. 0.050000 = 5% ($3,100.00 → $155.00)",
        ),
        Param(
            "allowance_rate_31_60",
            DECIMAL,
            "0.200000",
            "BR-LED-795",
            minimum=0,
            maximum=1,
            note="CR-060 T15. 0.200000 = 20% ($1,800.00 → $360.00)",
        ),
        Param(
            "allowance_rate_61_plus",
            DECIMAL,
            "0.500000",
            "BR-LED-795",
            minimum=0,
            maximum=1,
            note="CR-060 T15. 0.500000 = 50% ($1,233.30 → $616.65). Prices BOTH 61-90 and "
            "90+, because the PO signed four rates against four amounts and a fifth band "
            "would move the $1,223.65 they were shown",
        ),
        Param("dso_target_days", INTEGER, 15, "BR-REP-022", minimum=1),
        Param(
            "correction_approval_mode",
            CHOICE,
            "all",
            "BR-BIL-014",
            choices=CORRECTION_APPROVAL_MODES,
        ),
        Param("back_bill_cap_months", INTEGER, 12, "BR-BIL-018", minimum=1),
        Param("back_bill_theft_exempt", BOOLEAN, True, "BR-BIL-018"),
        # ── THE SPLIT-SEGMENT ESTIMATE SOURCE, PO ruling 2026-08-12 ────────
        # Verbatim: *"B is correct; and if required give option C also as
        # backup ; I will make B default and C as option for user"* (OQ-191).
        #
        # A back-billed period cut at a tariff change (OQ-155, *"Split by
        # days"*) can leave a segment with no read measuring ITS OWN days —
        # a tariff changes 15 Feb, the period is 1–28 Feb and 6 kgal, and the
        # meter was read on the 1st and the 28th and not on the 15th. The
        # segment's usage then comes from one of two places and the tenant
        # picks which:
        #
        #   day_weighted (B, THE DEFAULT) — billing weights the stated
        #     sub-period's own measured usage by the segment's days:
        #     **14/28 × 6 kgal = 3 kgal each side**, and the segment is MARKED
        #     ESTIMATED on the bill, because it is one.
        #   metering (C, the option) — ask metering for an estimate under its
        #     OWN rules (BR-MET-026 trailing-3 daily average, BR-MET-027's
        #     consecutive cap, BR-MET-062's demand refusal). Estimates are
        #     metering's, which is why this is the better answer wherever it
        #     can be had.
        #
        # DEFAULTING TO B IS THE RULING, not a convenience: the PO said so in
        # those words, and B needs no seam that does not exist yet. REFUSING is
        # deliberately NOT a third value — it is the last resort when neither
        # estimate can be produced, not a policy a tenant selects.
        Param(
            "back_bill_segment_estimate_source",
            CHOICE,
            "day_weighted",
            "BR-BIL-018",
            choices=BACK_BILL_SEGMENT_ESTIMATE_SOURCES,
            note="OQ-191 (PO 2026-08-12). day_weighted = billing weights the period's own "
            "usage by the segment's days (14/28 × 6 kgal = 3 kgal); metering = ask "
            "BR-MET-026. Either way the segment is MARKED ESTIMATED on the bill",
        ),
        # ── THE PER-AUTHORITY REMITTING BASIS, PO ruling 2026-08-12 ────────
        # Verbatim: *"E Remit on what you BILLED, not what you collected -
        # this is also correct"*, said after ruling that the allocation
        # sequence becomes a tenant setting. Read together: BOTH bases are
        # legitimate and WHICH applies is the customer's to set.
        #
        # That is what BR-LED-002 (CONFIRMED) already said — *"BOTH bases
        # always computed (billed = tax on issued bills; collected = tax inside
        # cleared payments via allocation); per-authority setting picks the
        # remitting basis"* — and `apps/ledger/reporting.remittance_by_authority`
        # already served both columns (LE-3: 47.38 billed / 20.97 collected).
        # What it carried was a live problem code,
        # `per_authority_remitting_basis_is_not_stored`: the report could show a
        # utility both figures and could not record which one they file on.
        # This parameter is that home.
        #
        # THE KEY IS THE AUTHORITY'S OWN GL ACCOUNT CODE ("2200-01"). The PO
        # ruled on 2026-08-11 (BR-BIL-069) that each authority has its own
        # 2200-nn account, so the account IS the authority in the books and the
        # S41 row is already labelled with that code. Keying by code rather
        # than by account UUID keeps the stored document readable, exportable
        # and diffable by the finance officer whose filing it describes; the
        # cost is stated rather than hidden — an account RENUMBERED after the
        # choice is made reads back as UNSET, which fails closed and shows up on
        # S41 as an authority still to be ruled on, never as the wrong basis.
        #
        # NO DEFAULT, AND THAT IS THE RULE ITSELF, not an omission: LE-3 has
        # State on COLLECTED and County on BILLED in the same month for the same
        # tenant, so any seeded basis is wrong for one of them in its first
        # month (hard-won law 3 — the unsafe option must be the one you type).
        # An authority with no entry is UNSET and the report says so.
        Param(
            "tax_remitting_basis_by_authority",
            CHOICE_MAP,
            {},
            "BR-LED-002",
            choices=REMITTING_BASES,
            note="{tax authority GL account code: 'billed'|'collected'}; an authority with no "
            "entry is UNSET and the S41 report reports it as such — never defaulted",
        ),
        # ── THE DISCOUNT SECOND-APPROVAL THRESHOLD, PO ruling 2026-08-19
        # (CR-013 part 3, design §A8). Verbatim: *"okay, but allow user to set
        # it , we can provide default."*
        #
        # WHAT IT MEASURES, because the choice was the whole question: **the
        # BUDGET CAP typed on the discount**, not a forecast of what the
        # programme will cost. Part 3 step 4 already asks for a budget cap, so
        # the figure exists at the moment of approval and is a COMMITMENT
        # rather than an estimate that moves between submit and approve.
        #
        # ⚠ **A DISCOUNT WITH NO BUDGET CAP ALWAYS REQUIRES THE SECOND
        # APPROVAL** — unbounded is the largest commitment there is. That rule
        # lives in `apps.rating.discount_services.second_approval_required`,
        # not here, because it is not expressible as a threshold.
        #
        # ⚠ **RAISED FROM 10000 TO 50000 ON 2026-08-21 (PO ruling, OQ-290).**
        # PO verbatim: *"I will increase the discount limit and accommodate it
        # for time being"*, and, asked for the figure: *"$50000"*.
        #
        # WHY IT MOVED. Two CONFIRMED rules gave this gate two different
        # quantities and two different figures, and neither was withdrawn:
        # BR-RAT-077 measures the discount's own BUDGET CAP against a tenant
        # setting (this Param); BR-RAT-091 clause 1 measures a PROJECTED
        # MONTHLY SUBSIDY against $500. Nothing in the product projects a
        # monthly subsidy (DEF-402), so only this one has ever been evaluable.
        # Rather than pick between them mid-build, the PO raised the bar so the
        # gate stops firing while the question is settled properly.
        #
        # Against Silver Creek's own catalogue at 10000, SENIOR (≈$12,312/yr)
        # and CAP (≈$11,400/yr) each needed the second approval. **At 50000
        # NOTHING IN THE CATALOGUE TRIPS IT** — the largest is SENIOR at
        # $12,312, a quarter of the bar. That is the intended effect of "for
        # time being", stated plainly rather than discovered later.
        #
        # ⚠ **A DISCOUNT WITH NO BUDGET CAP STILL ALWAYS REQUIRES IT.** Raising
        # the figure does not disable the gate; the unbounded case is not a
        # comparison and no threshold reaches it.
        #
        # ⚠ **THE UNIT HALF OF OQ-290 IS NOT CLOSED.** The figure was given
        # against a question framed in $/month; the quantity this Param is
        # compared to is a budget cap the fixture states ANNUALLY. At 50000 the
        # two readings agree for every discount that exists — the largest is
        # $12,312/yr, i.e. $1,026/mo, and both clear — so no bill and no
        # approval changes either way. It is recorded rather than resolved.
        #
        # Read by `apps.rating.discount_services.second_approval_threshold`,
        # which REFUSES if the key is absent rather than substituting a number
        # — a default copied into the reader is a second copy, free to drift
        # from the one on the tenant's own screen.
        # ⚠ **IT STARTS UNSET — PO RULING 2026-09-10, AND THAT IS THE FEATURE
        # BEING TURNED OFF RATHER THAN A MISSING DEFAULT.** Verbatim: *"Keep the
        # plumbing, default it off. The threshold setting stays but starts
        # unset, so nothing ever requires a second approval unless a utility
        # deliberately turns it on."*
        #
        # The PO's reason is the part that generalises: *"we have cap also that
        # one person get maixim X discount - that it - we dont have to double
        # check it again"*. Exposure is already bounded per customer three ways
        # (cap per bill, per year, lifetime) and once more in total (the budget
        # cap), so a second signature was checking something already bounded —
        # and in a utility run by 10-20 staff a mandatory second approver may
        # not exist at all.
        #
        # ⚠ **THIS CLOSES `PRB-13` / `OQ-290` WITHOUT CHOOSING BETWEEN THE TWO
        # SIGNED POLICIES.** BR-RAT-077 (the budget cap against this setting)
        # and BR-RAT-091 ($500 against a projected monthly subsidy) disagreed
        # twice over. Neither runs by default now, so the conflict stops being
        # live — and the columns, the setting and the freeze-at-submit behaviour
        # all stay, so a larger utility switches it back on and gets the whole
        # mechanism back.
        Param(
            "discount_second_approval_threshold_amount",
            DECIMAL,
            None,
            "BR-RAT-077",
            minimum=0,
            nullable=True,
            note="CR-013 part 3 / design §A8 (PO 2026-08-19; figure raised to 50000 by PO "
            "ruling 2026-08-21, OQ-290; UNSET by PO ruling 2026-09-10 — the plumbing stays and "
            "the default goes off). Measured against the DISCOUNT's own budget cap. While it is "
            "unset NOTHING requires a second approval, a blank budget cap included. "
            "Read by apps.rating.discount_services.second_approval_threshold",
        ),
    ),
)


# ⚠ READ_VALIDATION IS NOT IN THIS DICT — SUPERSEDED by CR-038 A1 (PO
# 2026-08-26). S64 is served by apps/metering/{api,selectors,services}.py from
# the metering-owned stores THE ENGINE ACTUALLY READS (`read_validation_
# settings` + the new per-service `read_validation_service_settings`); this
# family's document on `tenant_settings` was a second home whose edits never
# reached validation — the divergence this module's own header docstring
# (item 1) reserved re-homing for. The Family OBJECT and `default_read_
# validation` below stay DEFINED because tenancy migration 0004 references
# `default_read_validation` by dotted path as the jsonb column's default, and
# a committed migration may not be edited (migration-guard); the column stays
# a lawful container that nothing routes to.
# ── E·2 · Reports settings (CR-142-BRC07 `P4.6` + `P5.5`) ──────────────────
#
# ⚠ **THIS FAMILY IS TENANCY'S, AND THAT IS THE ANSWER TO A CROSS-MODULE
# WRITE RATHER THAN A WORKAROUND FOR ONE.** The drawing files both cards under
# a REPORTS heading on `S8`, and the heading is PRESENTATION — the front end's
# `referenceDataConfig.ts` says so in its own words (*"owner is not the group"*:
# `reason_codes` is billing's and files under Plans & Rates). What the cards
# actually govern is the PLATFORM EXPORT KERNEL:
#
#   · `file_retention_days` overrides `apps/tenancy/exports.ARTIFACT_RETENTION_
#     DAYS`, the constant every list export in this product is kept for —
#     audit's, the platform's and reports' alike. It was never reports' number.
#   · `default_download_format` is what a download IS unless the clerk asks
#     otherwise, and the kernel is the thing that writes the file.
#
# So tenancy declares it, tenancy validates it, tenancy writes it and tenancy
# audits it; `apps/reports` READS it through the seam it has had since `P3.1`
# (`report_seams.resolve_constant("tenancy", ...)`). No module writes another
# module's row and no module writes another module's constant.
#
# ⚠ **TWO CARDS, ONE FAMILY, ONE DOCUMENT — deliberately.** `clean()` above
# takes a PARTIAL change set and merges it onto what is stored, so a form that
# knows one key posts one key and leaves the other alone. Two families would
# have meant two jsonb columns for two integers, and a second audit action for
# one screen section.
#
# ⚠ **`default_download_format` HAS EXACTLY ONE CHOICE AND THE HOLE IS
# SIGNED.** `apps/reports/models.FORMATS` is `("csv",)` because no PDF renderer
# is declared anywhere in this product (drawing p34 callout ③), and
# `apps/tenancy/exports.py` has said the same since 2026-08-16. A choice set
# with one value is this file's established shape for *the rule names the
# parameter and ratifies one value* — `allocation_order` and
# `correction_approval_mode` are the precedent — and the view renders it as a
# fixed control that says so rather than as a dropdown of one.
REPORT_DOWNLOAD_FORMATS = ("csv",)

REPORTS = Family(
    slug="reports",
    document_field="reports",
    screen="S8",
    audit_action="settings.reports.updated",
    params=(
        # BR-REP-018 CONFIRMED (PO 2026-08-08, IS-11): *"Generated files are
        # retained 3 days by default, tenant-configurable"*. Three is the
        # ratified default and is the constant's own value, so a tenant that
        # never opens this card is where it always was.
        #
        # ⚠ **MINIMUM 1, NOT 0.** Zero days is not a shorter window, it is
        # *delete the file before anybody can fetch it* — a setting whose only
        # effect is to break every download link the product issues. The
        # maximum is deliberately absent (`NFR-5`: no hard caps anywhere).
        #
        # ⚠ **LOWERING IT TAKES EFFECT ON EVERY HISTORICAL RUN IMMEDIATELY**,
        # because retention is evaluated against the run's timestamp and is
        # never stored on it (`apps/reports/run_history.py`). Three days to one
        # makes yesterday's file unavailable the moment the row is saved. That
        # reasoning is written HERE and is NOT drawn on the screen — B14 rule
        # 33 puts rationale at zero words.
        Param(
            "file_retention_days",
            INTEGER,
            3,
            "BR-REP-018",
            minimum=1,
            note="Overrides apps.tenancy.exports.ARTIFACT_RETENTION_DAYS for this tenant. "
            "Read by apps.tenancy.exports.artifact_retention_days() and, through the "
            "reports seam, by apps.reports.run_history.",
        ),
        Param(
            "default_download_format",
            CHOICE,
            "csv",
            "BR-REP-018",
            choices=REPORT_DOWNLOAD_FORMATS,
            note="IS-11: CSV always, PDF where layout matters, no XLSX in v1. One value "
            "today because no PDF renderer is declared anywhere in the product — see "
            "apps.reports.models.FORMATS, which carries the same hole.",
        ),
    ),
)


# ── E·3 · Service requests (`DEF-CUS-10445`, PO 2026-10-22) ────────────────
#
# The decision log of 2026-10-22, *"Service request acknowledgement: target
# date, default 15 days, service type name"*: the acknowledgement tells an
# applicant the date their request is aimed at — the date they asked for, and
# when they gave none, the request date plus a default number of days. PO,
# verbatim: *"Default 15 days"*, and the same day's *"don't do any
# hardcoding"*. So the 15 is a SEEDED SETTING a utility changes, never a
# constant in the code that reads it.
#
# ⚠ **TENANCY'S, FOR `REPORTS`' REASON.** The number lives on the one
# `tenant_settings` row every rule page saves to, and `apps/customers` READS it
# through its seam (`seams.service_request_default_target_days`); no module
# writes another module's row. The Settings card files under the ACCOUNTS
# heading beside the account types, because service requests are an Accounts
# screen — the heading is presentation.
#
# ⚠ **WORKING DAYS, AND ONE NUMBER FOR TWO SCREENS.** The PO ruled on
# 2026-09-22 that a new request's `Connection date` opens *"15 working days"*
# ahead, and that sat in a constant (`service_request_api.CONNECTION_DATE_
# WORKING_DAYS`). It is the same fact as this one — when service is aimed at
# when the customer named no date — so both now read THIS parameter, counted
# by `customers.cut_date.business_days_after` with the utility's holidays. A
# clerk who leaves the prefill alone and an applicant who gave no date are
# told the same day.
#
# ⚠ **MINIMUM 0, NO MAXIMUM.** Zero is a lawful answer (*"we aim for the same
# day"*); a negative number would date the target before the request. No upper
# bound, because `NFR-5` puts no hard caps anywhere.
SERVICE_REQUESTS = Family(
    slug="service-requests",
    document_field="service_requests",
    screen="S8",
    audit_action="settings.service_requests.updated",
    params=(
        Param(
            "service_request_default_target_days",
            INTEGER,
            15,
            "BR-CUS-079",
            minimum=0,
            note="DEF-CUS-10445, PO 2026-10-22 *'Default 15 days'* (and 2026-09-22 *'make "
            "it default add 15 working days'*). WORKING days. Read through "
            "apps.customers.seams.service_request_default_target_days by "
            "service_request_service.acknowledgement_facts (no preferred date) and by "
            "service_request_api.service_request_capture_defaults (the Connection date "
            "prefill).",
        ),
    ),
)


FAMILIES: dict[str, Family] = {
    family.slug: family
    for family in (
        BILLING_DEFAULTS,
        BUDGET_BILLING,
        COLLECTIONS,
        FINANCE_CONTROLS,
        REPORTS,
        SERVICE_REQUESTS,
    )
}


# ── defaults (also the model/migration column defaults) ─────────────────────
def _fresh(default: Any) -> Any:
    """A COPY of a container default, so no two rows share one object.

    `notice_tier_days`, `allocation_class_order` and
    `tax_remitting_basis_by_authority` all default to a container declared once
    on the Param. Handing the same list out to a seeded row, to a read and to a
    save would make one tenant's edit — or one JSON encoder that sorts in place
    — reach every other caller holding it. Cheap to copy, impossible to debug
    when it is not.
    """
    if isinstance(default, list):
        return list(default)
    if isinstance(default, dict):
        return dict(default)
    return default


def defaults_for(family: Family) -> dict[str, Any]:
    """The ratified seeded defaults for the family's DOCUMENT half only —
    parameters living in a typed column are that column's own default."""
    return {param.key: _fresh(param.default) for param in family.params if param.column is None}


def default_read_validation() -> dict[str, Any]:
    return defaults_for(READ_VALIDATION)


def default_billing_defaults() -> dict[str, Any]:
    return defaults_for(BILLING_DEFAULTS)


def default_budget_billing() -> dict[str, Any]:
    return defaults_for(BUDGET_BILLING)


def default_collections() -> dict[str, Any]:
    return defaults_for(COLLECTIONS)


def default_reports() -> dict[str, Any]:
    return defaults_for(REPORTS)


def default_service_requests() -> dict[str, Any]:
    return defaults_for(SERVICE_REQUESTS)


def default_finance_controls() -> dict[str, Any]:
    return defaults_for(FINANCE_CONTROLS)


# ── value coercion (pure) ───────────────────────────────────────────────────
def _to_decimal_string(raw: Any) -> str:
    """Canonical decimal string. Bools are refused (True is not 1 here) and a
    JSON number arriving as a Python float goes through its repr — never
    through binary-float arithmetic (CLAUDE.md rule 2)."""
    if isinstance(raw, bool):
        raise InvalidOperation("bool is not a decimal")
    value = Decimal(str(raw).strip())
    if not value.is_finite():
        raise InvalidOperation("non-finite decimal")
    return str(value)


def _to_int(raw: Any) -> int:
    if isinstance(raw, bool):
        raise ValueError("bool is not an integer")
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if not text or (text.lstrip("-") and not text.lstrip("-").isdigit()):
        raise ValueError(f"{raw!r} is not an integer")
    return int(text)


def _coerce(param: Param, raw: Any) -> tuple[Any, list[dict[str, Any]]]:
    """One value → its stored form, or the field errors explaining the refusal."""
    if raw is None:
        if param.nullable:
            return None, []
        return None, [
            _field_error(param.key, errors.VAL_REQUIRED, "settings.param_required", br=param.br)
        ]

    if param.kind == BOOLEAN:
        if not isinstance(raw, bool):
            return None, [
                _field_error(
                    param.key, errors.VAL_FORMAT, "settings.param_not_boolean", br=param.br
                )
            ]
        return raw, []

    if param.kind == CHOICE:
        value = str(raw)
        if value not in param.choices:
            # A value outside the ratified set is a refusal, never a guess —
            # see the module docstring on the single-value choice sets.
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.param_bad_choice",
                    br=param.br,
                    allowed=list(param.choices),
                )
            ]
        return value, []

    if param.kind == CHOICE_SEQUENCE:
        # An ORDER over a closed set. One check does all of it, because every
        # way of getting it wrong is the same fact: the value is not a
        # permutation of `choices`. A dropped class is the dangerous one — the
        # allocator only requires that the classes a BILL states are placed, so
        # an order missing `taxes` would allocate every bill correctly, foot
        # every total, and leave the tax balance outstanding forever.
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_FORMAT,
                    "settings.param_not_sequence",
                    br=param.br,
                    allowed=list(param.choices),
                )
            ]
        if any(not isinstance(item, str) for item in raw) or sorted(raw) != sorted(param.choices):
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.param_not_permutation",
                    br=param.br,
                    allowed=list(param.choices),
                )
            ]
        return list(raw), []

    if param.kind == CHOICE_MAP:
        # A per-item choice. An item with NO entry is unset; `None` as a value
        # is refused rather than read as unset, because a stored null and an
        # absent key would be two spellings of one state and only one of them
        # survives a round trip through the document.
        if not isinstance(raw, dict):
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_FORMAT,
                    "settings.param_not_map",
                    br=param.br,
                    allowed=list(param.choices),
                )
            ]
        chosen: dict[str, str] = {}
        for item, value in raw.items():
            if not isinstance(item, str) or not item.strip():
                return None, [
                    _field_error(
                        param.key,
                        errors.VAL_FORMAT,
                        "settings.param_not_map",
                        br=param.br,
                        allowed=list(param.choices),
                    )
                ]
            if not isinstance(value, str) or value not in param.choices:
                return None, [
                    _field_error(
                        param.key,
                        errors.VAL_UNKNOWN_LOOKUP,
                        "settings.param_bad_choice",
                        br=param.br,
                        allowed=list(param.choices),
                    )
                ]
            chosen[item] = value
        return chosen, []

    if param.kind == INT_LIST:
        if not isinstance(raw, (list, tuple)):
            return None, [
                _field_error(param.key, errors.VAL_FORMAT, "settings.param_not_list", br=param.br)
            ]
        out: list[int] = []
        for item in raw:
            try:
                number = _to_int(item)
            except (TypeError, ValueError):
                return None, [
                    _field_error(
                        param.key, errors.VAL_FORMAT, "settings.param_not_integer", br=param.br
                    )
                ]
            if param.minimum is not None and number < param.minimum:
                return None, [
                    _field_error(
                        param.key,
                        errors.VAL_RANGE,
                        "settings.param_below_min",
                        br=param.br,
                        min=param.minimum,
                    )
                ]
            out.append(number)
        return out, []

    if param.kind == INTEGER:
        try:
            number = _to_int(raw)
        except (TypeError, ValueError):
            return None, [
                _field_error(
                    param.key, errors.VAL_FORMAT, "settings.param_not_integer", br=param.br
                )
            ]
        return _range_checked(param, number, number)

    # DECIMAL
    try:
        text = _to_decimal_string(raw)
    except (InvalidOperation, ValueError, TypeError):
        return None, [
            _field_error(param.key, errors.VAL_FORMAT, "settings.param_not_decimal", br=param.br)
        ]
    return _range_checked(param, text, Decimal(text))


def _range_checked(param: Param, stored: Any, comparable: Any) -> tuple[Any, list[dict[str, Any]]]:
    if param.minimum is not None:
        floor = Decimal(str(param.minimum)) if isinstance(comparable, Decimal) else param.minimum
        too_low = comparable <= floor if param.exclusive_min else comparable < floor
        if too_low:
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_RANGE,
                    "settings.param_below_min",
                    br=param.br,
                    min=param.minimum,
                    exclusive=param.exclusive_min,
                )
            ]
    if param.maximum is not None:
        ceiling = Decimal(str(param.maximum)) if isinstance(comparable, Decimal) else param.maximum
        if comparable > ceiling:
            return None, [
                _field_error(
                    param.key,
                    errors.VAL_RANGE,
                    "settings.param_above_max",
                    br=param.br,
                    max=param.maximum,
                )
            ]
    return stored, []


# ── the two entry points services/selectors use ─────────────────────────────
def merge(family: Family, document: Any, columns: dict[str, Any]) -> dict[str, Any]:
    """The family's CURRENT value set: stored value where the tenant (or the
    provisioning seed) has one, ratified default otherwise.

    Defaults are merged at read time only so a parameter added to this registry
    later renders immediately on an older row — the row itself is seeded with
    the defaults by the migration and by every save, so the DATABASE stays the
    source of truth (BR-MET-020: engines read config, never constants)."""
    stored = document if isinstance(document, dict) else {}
    out: dict[str, Any] = {}
    for param in family.params:
        if param.column is not None:
            value = columns.get(param.column)
            if value is None:
                value = param.default
            elif param.kind == DECIMAL:
                value = str(value)
            out[param.key] = value
            continue
        out[param.key] = stored[param.key] if param.key in stored else _fresh(param.default)
    return out


def clean(family: Family, changes: Any, current: dict[str, Any]) -> dict[str, Any]:
    """Validate a PARTIAL change set against the family; return the full, legal
    value set to store (BR-TEN-024: one atomic per-tab save).

    Unknown keys are refused rather than ignored — a typo that silently does
    nothing is how a threshold quietly stays at its old value.
    """
    if not isinstance(changes, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    by_key = family.by_key
    field_errors: list[dict[str, Any]] = [
        _field_error(key, errors.VAL_FORMAT, "settings.unknown_field")
        for key in sorted(set(changes) - set(by_key))
    ]
    merged = dict(current)
    for key, raw in changes.items():
        param = by_key.get(key)
        if param is None:
            continue
        value, problems = _coerce(param, raw)
        field_errors.extend(problems)
        if not problems:
            merged[key] = value
    if not field_errors:
        for check in family.cross_checks:
            field_errors.extend(check(merged))
    if field_errors:
        first = field_errors[0]
        raise errors.ValidationError(
            first["code"],
            message_key=first["message_key"],
            params=first["params"],
            field_errors=field_errors,
        )
    return merged


def split(family: Family, values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Full value set → (jsonb document, {column: value}) for the writer."""
    document = {p.key: values[p.key] for p in family.params if p.column is None}
    columns = {p.column: values[p.key] for p in family.params if p.column is not None}
    return document, columns


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07 lead story, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packets EP-MET-04@34f14b6 (S64 field law) · EP-TEN-05@0733260 (the S8 save contract))
# generated: 2026-08-09 by story-coder v1 (tenancy settings rule-page gap lane)
# amended:   2026-08-12 by story-coder (tenant-settings lane) — TWO parameters, from the PO's
#            two rulings of 2026-08-12, plus the two Param KINDS they needed
#            (CHOICE_SEQUENCE, CHOICE_MAP): `allocation_class_order` on S66 (*"better to let
#            user set the sequence; we can give default option and allow them to change the
#            order"*) and `tax_remitting_basis_by_authority` on S71 (*"E Remit on what you
#            BILLED, not what you collected - this is also correct"*). Both defaults are the
#            behaviour that already shipped — the four-class order unchanged, and NOTHING for
#            the basis, because LE-3 puts two authorities on two different bases in one month.
#            NO MIGRATION: the document defaults are callables the migrations reference by
#            name, and `merge` supplies a new parameter's default at READ time, so an existing
#            row renders it immediately and stores it on its next save. `_fresh` was added at
#            the same time — a container default declared once on a Param was being handed out
#            by reference to every seeded row and every read (`notice_tier_days` had the same
#            latent bug since 2026-08-09); it is copied now.
# amended-gates: ruff✔ black✔ makemigrations --check "No changes detected"✔ · pytest tests
#            2058 passed / 132 skipped / 1 xfailed✔ · run_gates 20 PASS / 0 FAIL✔ (G15 + G18
#            green with the three new settings.param_* refusal keys in all eleven catalogues)
# amended:   2026-08-12 by story-coder (OQ-191 back-bill lane) — ONE parameter, from the PO's
#            third ruling of 2026-08-12: `back_bill_segment_estimate_source` on S71
#            (*"B is correct; and if required give option C also as backup ; I will make B
#            default and C as option for user"*). Unlike the two above it did NOT exist as
#            behaviour first — the behaviour it defaults to REPLACES a refusal that shipped
#            hours earlier the same day. Seeded `day_weighted` (option B, the PO's own
#            default); `metering` (option C) asks BR-MET-026. Refusing is deliberately NOT a
#            third value — it is the last resort when neither estimate can be produced, not
#            a policy a tenant selects. The choice list is MIRRORED from
#            `apps.billing.backbill.SEGMENT_ESTIMATE_SOURCES` for the reason
#            `ALLOCATION_CLASS_SEQUENCE` gives, and a test asserts the copies are equal.
#            NO MIGRATION: `merge` supplies a new Param's default at READ time, so an
#            existing row renders it immediately and stores it on its next save.
# amended-gates: ruff✔ black✔ makemigrations --check "No changes detected"✔ ·
#            tests/test_po_20260812_backbill_segment_estimate.py 15 passed (PROVED RED
#            first — `KeyError: 'back_bill_segment_estimate_source'`) ·
#            tests/test_us_ten_settings_rule_pages.py + the full suite: see the lane report
# checklist: A✔ B✔ C✔ D=deferred(pure registry — the endpoint half is api.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: read_validation stored on tenant_settings, not the metering-owned read_validation_settings table B2 r16 #6 PM-proposes (out of territory; 11b §2.3 puts the endpoint on the tenancy surface) — REPORTED · overcharge guardrail implemented on S66 per 11b §2.3 + B2 r10 #6, not on S71 per the EP-TEN-07 addendum — REPORTED · allocation_order + correction_approval_mode + level_rounding + est_method accept exactly the one value their rule names (B4 payments-allocation PLACEHOLDER; BR-BIL-014 threshold mode is v2) — refusal, never a guessed second value · settle_up_month + minimum_bill_amount default None because no rule ratifies a value — UNSET, never 0 · S63–S71 stories (US-TEN-013..017) are allocated but UNAUTHORED, so this packet is anchored on EP-TEN-07's addendum + 11b §2.3 and cites no story ID that does not exist
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
