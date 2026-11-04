# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-043 (EP-RBS-05) — CR-075: runbook 28, *Meters past
#           change-out age or never tested*. The FIRST runbook in the Assets
#           category, which held one step and no runbook until this commit.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-010
#           (every record states the rule that decided it, in a clerk's words)
#           · BR-RBS-011 (a failure names its fix route, tenant-relative) ·
#           BR-RBS-012 (a guard is absolute and evaluated before any step) ·
#           BR-RBS-019 (the declared unit of work) · BR-RBS-020 (the report is
#           composed at close and frozen) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-022 (a work item is the ENGINE's act, never a port) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-024 (one category
#           from the fixed sixteen) · BR-RBS-039 (every foreign read through a
#           seam this module owns) · BR-AST-007 (a test is due at
#           last_test_date + test_interval_months; the stored status never
#           moves) · BR-REP-001 (no unlabelled money number ships anywhere) ·
#           RBR-03 (policy lives in Settings and is never duplicated on a card)
#           · CLAUDE.md hard rule 2 (money stored to 4 decimals, shown to 2) ·
#           hard-won law 7 (a declared blind spot carries a NUMBER) ·
#           B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_043_meter_change_out.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/metering_seam.py ·
#           apps/metering/selectors.py · apps/assets/selectors.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/
#           RB-128-meters-past-change-out-age-or-never-tested.md
# ───────────────────────────────────────────────────────
"""Runbook 28 — **Meters past change-out age or never tested**.

`RB-128`'s whole commitment, and the card carries one sentence and no more:

> A clerk sees meters older than the utility's change-out age or with no test
> on file, ranked by revenue at risk, each with **Order a test →** or
> **Schedule change-out →**.

⚠ **IT IS A CHECK, AND THE CARD'S *Kind* ROW IS CONDITIONAL — READ THIS BEFORE
CHANGING IT.** The card says the runbook *"waits on `RB-049` for a field order,
and is **a Check without it**"*. `RB-049` does not exist: there is no field
order, no work-order port and nothing in `interfaces.PORTS` that could raise
one. So this is built as a Check — **constructed with no ports at all**, which
is `BR-RBS-002`'s promise that the capability is ABSENT rather than merely
unused — and its two controls are FIX ROUTES rather than writes.

**WHAT IT WOULD BECOME THE DAY `RB-049` ARRIVES, so the next lane does not have
to re-derive it.** `RB-049` registers *work order* and *inspection* as subject
types on the contract. When it lands, **Order a test →** and **Schedule
change-out →** stop being links to the Assets registry and become two acts:

  * the runbook's `kind` moves from `check` to `action` — `BR-RBS-001` says a
    kind never changes afterwards, so that is a NEW VERSION of the runbook and
    not an edit to this line;
  * it declares a port that raises a field order in `work` — **which does not
    exist today and is a fifteenth port**, i.e. a reviewed interface under
    `BR-RBS-022` with its row in the schema brief, never a line added on the way
    past. `work` publishes no `runbook_ports.py` at all;
  * step 3 gains a fourth outcome — *ordered* — and the two fix routes below
    become the two `planned_action` sentences;
  * the guards do not move, the scope does not move, and the arithmetic in
    steps 1 and 2 does not move. **Only the ending changes.**

Until then the two controls open `assets`, where a clerk records a test date or
schedules a change-out by hand, and **that is a working door rather than a
refusal** — this is deliberately not hard-won law 2's *live screen behind a dead
control*.

WHAT *THE UTILITY'S CHANGE-OUT AGE* IS, AND WHY IT IS THE METER'S OWN
----------------------------------------------------------------------
The card says *"the utility's change-out age"* and this product holds no such
tenant setting. What it does hold is `assets.expected_life_years` **per meter**,
and the Assets screen's own Age-and-replacement forecast already counts a meter
as past life at `install_date + expected_life_years` (B16 §5.1b). This runbook
reads that same fact through the same derivation rather than inventing a
second one, for the reason `RBR-09` gives about thresholds generally: a 5/8"
residential water meter and a 6" compound do not have the same life, and a
utility-wide number would either retire the small ones early or leave the big
ones running.

**The Settings-owned parameter is DECLARED anyway and its setting does not
exist yet** — the `RB-119` `orphan_means` precedent, and for the same reason: a
parameter that appears the day the setting does is a smaller change than one
nobody remembered. `RBR-03` means the value is never duplicated onto this card.

WHAT THIS RUNBOOK CANNOT SEE, EACH WITH ITS FIGURE
---------------------------------------------------
Hard-won law 7: a declared blind spot with no number beside it is
indistinguishable from an empty one. Three of them, and every one travels as a
count in the report:

1. **A meter with no `expected_life_years` can never be found by an age rule.**
   It is not young; it is unrecorded. `meters_with_no_expected_life` travels and
   the verdict says it out loud, because *"0 past change-out age"* over a fleet
   that records no lives at all is a clean bill of health that is a lie.
2. **A meter with no install date and no purchase date has no age at all.**
   `meters_with_no_age_base` travels for the same reason.
3. **A meter TESTED but past its test interval is NOT one of this card's two
   groups.** The card names *past change-out age* and *never tested*, and a
   third group would be scope this lane invented. `BR-AST-007`'s derived
   overdue state is real and is already drawn on the Assets registry, so the
   COUNT travels as a tile — `tests_overdue` — and no row is raised for it.
   Adding it as a group is a change request, not a lane's decision.

WHY *REVENUE AT RISK* IS A MONTH OF BILLED REVENUE AND NOT A PROJECTION
------------------------------------------------------------------------
The card asks for a ranking and names no method. This runbook uses **what this
meter's account was last billed for this meter's service on its most recent
ISSUED bill** — a dollar the customer has actually been charged, not a tariff
this Check looked up and re-interpreted, which is rating's job. `RB-105` sets
the same precedent in `_price_per_unit` and for the same reason.

⚠ **`None` IS NEVER `0.0000`.** An account that has never billed, or a bill
carrying no usage line for the service, has an UNKNOWN figure — and an unknown
sorted as zero would put the very meter a clerk should see first at the bottom
of a list ranked by money. Unknown sorts to the top of the unknowns, below every
known figure, and says *not billed yet* in words.

⚠ **THE MONEY IS ONLY READ FOR A METER THAT IS ALREADY A FINDING.** Ranking is
over what was found, so a clean fleet costs one census read and no bill reads at
all. On the seeded utility that is the difference between 3 bill reads and 137.

⚠ **THE TILE DECLARES ITS BASIS — `posting`** (`BR-REP-001`, and
`DEF-RBS-4350`). This money comes off issued bills, so it is billing-side; a
tile that said nothing would take the renderer's fallback and read *Posting
date* by luck rather than by declaration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_SETTING,
    Block,
    Finding,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)

# ⚠ **NO `tenancy_seam` HERE, DELIBERATELY.** A meter's AGE is computed on the
# far side of the seam, from the tenant's own business date, and re-deriving it
# here would be a second answer to *how old is this meter* — the exact thing
# `meter_lifecycle_census`'s docstring says the shared `age_base` exists to
# prevent. So this module reads no clock and needs no date door.
from apps.runbooks.seams import billing_seam, customers_seam, metering_seam

KEY = "meter_change_out"

ZERO = Decimal("0")

# ── the three steps, in the card's own order ──────────────────────────────

STEP_AGE = "past_change_out_age"
STEP_TESTS = "never_tested"
STEP_RISK = "revenue_at_risk"

STEP_LABELS = {
    STEP_AGE: "Past change-out age",
    STEP_TESTS: "No test on file",
    STEP_RISK: "Rank by revenue at risk",
}

# ── the two groups the card names, and the one it does not ────────────────
#
# ⚠ **TWO GROUPS, NOT THREE.** *Tested but overdue* is a real state
# (`BR-AST-007`) and is NOT one of this card's groups; it travels as a count.

GROUP_PAST_LIFE = "past_change_out_age"
GROUP_NEVER_TESTED = "never_tested"
GROUP_ORDER = (GROUP_PAST_LIFE, GROUP_NEVER_TESTED)

OUTCOME_OK = "ok"
OUTCOME_PAST_LIFE = "past_change_out_age"
OUTCOME_NEVER_TESTED = "never_tested"
OUTCOME_BOTH = "both"

#: Tenant-relative, and the shell prefixes the tenant (`BR-RBS-011`). ⚠ NOT
#: `/brazosbend/assets` — a route with a tenant baked into it is a route that is
#: right on exactly one utility.
FIX_ASSETS = "assets"

#: The two controls the card names, in its own words. They are LINKS today and
#: the module docstring says what they become when `RB-049` lands.
LABEL_ORDER_TEST = "Order a test"
LABEL_SCHEDULE_CHANGE_OUT = "Schedule change-out"

GROUP_FACTS: dict[str, dict[str, str]] = {
    GROUP_PAST_LIFE: {
        "label": "Past change-out age",
        "breaks": "An over-age meter under-registers, and the loss is invisible",
        "fix_route": FIX_ASSETS,
        "fix_label": LABEL_SCHEDULE_CHANGE_OUT,
        "rule": "A meter is due for change-out once it is older than its expected life",
    },
    GROUP_NEVER_TESTED: {
        "label": "No test on file",
        "breaks": "Nobody can say whether this meter measures correctly",
        "fix_route": FIX_ASSETS,
        "fix_label": LABEL_ORDER_TEST,
        "rule": "A meter with no test on file has never been proved accurate",
    },
}

#: `work_items.weight` is an INTEGER and a screen turns it back into a word
#: (B14 rule 32). 100 stops billing; 50 is before go-live; 0 is routine. Neither
#: of these stops a bill, and both are money leaking quietly — so both sit in the
#: middle band, and the AGE one is heavier because an over-age meter is losing
#: revenue today while an untested one merely might be.
WEIGHT_PAST_LIFE = 40
WEIGHT_NEVER_TESTED = 30


@dataclass
class _StepResult:
    """What every set step returns — what it found, and what it LOOKED AT.

    `checked` is not decoration. A step reporting nothing because the fleet is
    young and a step reporting nothing because no meter records an expected life
    are the same sentence with very different meanings, and a check whose output
    cannot tell a reader which is which is worse than no check at all (hard-won
    law 7).
    """

    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "items": dict(self.items), "checked": dict(self.checked)}


def _set(ctx_or_view, step: str) -> dict[str, Any]:
    return dict((ctx_or_view.set_results.get(step) or {}))


def _items(ctx_or_view, step: str) -> dict[str, dict[str, Any]]:
    return dict(_set(ctx_or_view, step).get("items") or {})


def _checked(ctx_or_view, step: str) -> dict[str, Any]:
    return dict(_set(ctx_or_view, step).get("checked") or {})


def _census(ctx) -> dict[str, Any]:
    """The fleet, read ONCE per run and cached on the context.

    Steps 1 and 2 are two questions about one walk — *how old is it* and *when
    was it last tested* — and asking metering twice would be two walks that can
    disagree about which meters are in scope inside a single run.
    """
    cached = ctx.set_results.get("_census")
    if cached is None:
        cached = metering_seam.meter_lifecycle_census(include_sample=True)
        ctx.set_results["_census"] = cached
    return cached


def _by_id(ctx) -> dict[str, dict[str, Any]]:
    return {str(one.get("asset_id")): one for one in (_census(ctx).get("meters") or [])}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):  # pragma: no cover — defensive
        return None


# ── the guards, absolute and evaluated before step 1 (`BR-RBS-012`) ───────


def guard_sample(ctx: Any, subject: SubjectRef) -> bool:
    """`BR-TEN-056` fills a new tenant with realistic, deletable sample records.

    On the seeded utility that is almost the whole fleet, so a run that put them
    on a clerk's list would be a list of things nobody should act on. The flag
    travels on the meter row rather than being filtered inside the read, because
    a guard applied inside a read cannot be SEEN on the screen that draws it.
    """
    return bool(_by_id(ctx).get(str(subject.subject_id), {}).get("is_sample"))


def guard_retired(ctx: Any, subject: SubjectRef) -> bool:
    """A retired meter is off the estate — `BR-AST-005`'s terminal behaviour.

    Every retired meter is by definition past its change-out age, so without
    this guard the list would be the graveyard first and the live fleet
    underneath it.
    """
    return str(_by_id(ctx).get(str(subject.subject_id), {}).get("behavior_class") or "") == (
        "terminal"
    )


def guard_store_room(ctx: Any, subject: SubjectRef) -> bool:
    """A meter standing on nothing is spare stock, not a service point.

    `RB-119` records the same judgment in the other direction — *"a meter in the
    store room is not a finding and its status says so"*. A spare has never been
    tested by definition and has no revenue to be at risk, so a runbook ranked
    by revenue would put the entire store room at the bottom of every run for
    ever. It is a guard rather than a filter so the count is visible.
    """
    return not _by_id(ctx).get(str(subject.subject_id), {}).get("service_point_id")


# ── step 1 · past change-out age ──────────────────────────────────────────


def step_past_change_out_age(ctx, subjects) -> dict[str, Any]:
    """1 · SET — each meter's age against ITS OWN expected life.

    ⚠ **THE COMPARISON IS `age_months > life_years × 12`, STRICTLY GREATER**,
    which is the Assets screen's own forecast rule (B16 §5.1b) read verbatim. A
    meter exactly at its life is due, not past; moving that boundary here would
    make two screens disagree about the same box in the same yard.

    ⚠ **A METER WITH NO LIFE AND A METER WITH NO INSTALL DATE ARE COUNTED, NOT
    SKIPPED SILENTLY.** Neither can be judged by an age rule, and both numbers
    travel — see the module docstring's blind-spot list.
    """
    walked = {str(one.subject_id) for one in subjects}
    rows = [one for one in (_census(ctx).get("meters") or []) if str(one["asset_id"]) in walked]
    items: dict[str, dict[str, Any]] = {}
    no_life = no_base = 0
    for row in rows:
        life = row.get("expected_life_years")
        age = row.get("age_months")
        if not life:
            no_life += 1
            continue
        if age is None:
            no_base += 1
            continue
        life_months = int(life) * 12
        if int(age) > life_months:
            items[str(row["asset_id"])] = {
                "age_months": int(age),
                "life_months": life_months,
                "over_by_months": int(age) - life_months,
                "age_base": row.get("age_base"),
            }
    return _StepResult(
        items=items,
        checked={
            "meters_checked": len(rows),
            "meters_past_change_out_age": len(items),
            # Hard-won law 7 — what this step could not see, with its number.
            "meters_with_no_expected_life": no_life,
            "meters_with_no_age_base": no_base,
            # ⚠ `False` MEANS NOBODY COULD ANSWER, WHICH IS NOT `no meters`.
            "meters_answered": bool(_census(ctx).get("meters_answered")),
            "age_is_measured_from": "the install date, or the purchase date for stock",
        },
    ).as_dict()


# ── step 2 · no test on file ──────────────────────────────────────────────


def step_never_tested(ctx, subjects) -> dict[str, Any]:
    """2 · SET — the card's *never tested*: **no test on file**, and only that.

    ⚠ **`last_test_date IS NULL` IS THE WHOLE RULE.** A meter with a test on
    file that is past its interval is `BR-AST-007`'s DERIVED overdue state, it
    is drawn on the Assets registry already, and it is **not one of this card's
    two groups**. Its count travels so a clerk can see it; no row is raised for
    it, because raising one would be this lane widening a commitment.
    """
    walked = {str(one.subject_id) for one in subjects}
    rows = [one for one in (_census(ctx).get("meters") or []) if str(one["asset_id"]) in walked]
    items: dict[str, dict[str, Any]] = {}
    overdue = with_a_test = no_cadence = 0
    for row in rows:
        if row.get("last_test_date"):
            with_a_test += 1
            if row.get("test_overdue"):
                overdue += 1
            continue
        if not row.get("test_interval_months"):
            no_cadence += 1
        items[str(row["asset_id"])] = {
            "test_interval_months": row.get("test_interval_months"),
            "next_test": row.get("next_test"),
        }
    return _StepResult(
        items=items,
        checked={
            "meters_checked": len(rows),
            "meters_with_no_test_on_file": len(items),
            "meters_with_a_test_on_file": with_a_test,
            # ⚠ **THE THIRD STATE THE CARD DOES NOT NAME**, counted rather than
            # raised — see the step docstring.
            "tested_but_past_their_interval": overdue,
            "of_the_untested_ones_with_no_cadence_either": no_cadence,
        },
    ).as_dict()


# ── step 3 · rank by revenue at risk ──────────────────────────────────────


def _account_for(ctx, meter: dict[str, Any]) -> str | None:
    """This meter's account, walked meter → service point → unit → account.

    ⚠ **ONE READ FOR THE WHOLE PINNED SET, CACHED.** `accounts_for_units` is a
    batch and a per-meter read would be one round trip per meter — the cost
    `metering_seam.service_point_graph` already states and the one `NFR-3` binds
    every list in this product against.
    """
    cached = ctx.set_results.get("_accounts")
    if cached is None:
        unit_ids = sorted(
            {
                str(one["unit_id"])
                for one in (_census(ctx).get("meters") or [])
                if one.get("unit_id")
            }
        )
        cached = customers_seam.accounts_for_units(unit_ids)
        ctx.set_results["_accounts"] = cached
    unit_id = meter.get("unit_id")
    if not unit_id:
        return None
    row = cached.get(str(unit_id)) or {}
    # ⚠ **THE KEY IS `id`, NOT `account_id`, AND THE FIRST DRAFT OF THIS LINE
    # READ `account_id` — WHICH IS A SILENT `None` ON EVERY ROW.** `customers`
    # publishes the occupying account as `{"id", "account_no", "customer_name",
    # "status", "unit_id"}`; there is no `account_id` member, so the wrong key
    # returns `None`, every meter reports *"Not billed yet"*, and the whole
    # ranking the card asks for collapses into alphabetical order with nothing
    # on any screen to notice. It was found by RUNNING it against the seeded
    # utility and by nothing else (hard-won law 6), and
    # `test_us_rbs_043_meter_change_out.py` asserts a real dollar figure so it
    # cannot come back.
    account_id = row.get("id")
    return str(account_id) if account_id else None


def _billed_for_service(ctx, account_id: str, service: str) -> tuple[Decimal | None, str | None]:
    """What this account was last billed for this service, and the currency.

    Measured from the account's most recent ISSUED bill: the usage lines for
    that service, summed. It is money the customer has actually been charged,
    not a tariff this Check looked up and re-interpreted — which matters because
    re-interpreting a tariff is rating's job and this is a Check (`RB-105`'s
    `_price_per_unit` records the same posture).

    ⚠ **MEMOISED PER ACCOUNT AND READ ONLY FOR A METER THAT IS ALREADY A
    FINDING.** A clean fleet does no bill reads at all.

    `None` where the account has never billed or the bill carries no usage line
    for the service. **`None` is never `0.0000`.**
    """
    cache = ctx.set_results.setdefault("_bills", {})
    if account_id not in cache:
        cache[account_id] = billing_seam.issued_bills_for_account(account_id, limit=1)
    bills = cache[account_id] or []
    if not bills:
        return None, None
    amount = ZERO
    seen = False
    for line in bills[0].get("lines") or []:
        if str(line.get("kind")) != "usage":
            continue
        if service and str(line.get("service") or "") != service:
            continue
        value = _decimal(line.get("amount"))
        if value is None:
            continue
        amount += value
        seen = True
    if not seen:
        return None, None
    return amount, bills[0].get("currency")


def step_revenue_at_risk(ctx, subject) -> dict[str, Any]:
    """3 · PER RECORD — one meter, one row, and the money only where it matters.

    ⚠ **THIS STEP RANKS NOTHING AND THE CARD ASKS FOR A RANKING.** A per-record
    step sees one meter and cannot order a list; the ORDER is applied when the
    report is composed (`BR-RBS-020` — composed at close and frozen). Stated
    here so the next reader does not go looking for a sort that is not in this
    function; `RB-105` step 8 carries the identical note for the identical
    reason.

    ⚠ **A METER THAT IS NEITHER PAST ITS AGE NOR UNTESTED COSTS NO BILL READ.**
    Its row is `ok` and its money is `None` — not because the money is zero, but
    because nobody asked.
    """
    asset_id = str(subject.subject_id)
    meter = _by_id(ctx).get(asset_id, {})
    past_life = _items(ctx, STEP_AGE).get(asset_id)
    untested = _items(ctx, STEP_TESTS).get(asset_id)

    if past_life and untested:
        outcome = OUTCOME_BOTH
    elif past_life:
        outcome = OUTCOME_PAST_LIFE
    elif untested:
        outcome = OUTCOME_NEVER_TESTED
    else:
        outcome = OUTCOME_OK

    if outcome == OUTCOME_OK:
        return {
            "outcome": OUTCOME_OK,
            "decided_by_rule": "Inside its expected life and tested",
            "reason": "nothing to do on this meter.",
            "data": {
                "asset_no": meter.get("asset_no"),
                "service": meter.get("service_code"),
                "at_risk": None,
                "currency": None,
            },
        }

    account_id = _account_for(ctx, meter)
    at_risk = currency = None
    if account_id:
        at_risk, currency = _billed_for_service(
            ctx, account_id, str(meter.get("service_code") or "")
        )

    # The heavier group decides the row's fix route: a meter that is BOTH over
    # age and untested is changed out, and the change-out puts a tested meter in
    # its place — ordering a test on a meter you are about to remove is work
    # nobody wants done.
    group = GROUP_PAST_LIFE if past_life else GROUP_NEVER_TESTED
    facts = GROUP_FACTS[group]
    return {
        "outcome": outcome,
        "decided_by_rule": facts["rule"],
        "reason": _row_words(outcome, past_life, untested, meter),
        "fix_route": facts["fix_route"],
        "data": {
            "asset_no": meter.get("asset_no"),
            "type": meter.get("type_name"),
            "service": meter.get("service_code"),
            "group": group,
            "fix_label": facts["fix_label"],
            "also_untested": bool(untested) and outcome == OUTCOME_BOTH,
            "age_months": (past_life or {}).get("age_months"),
            "over_by_months": (past_life or {}).get("over_by_months"),
            "last_test_date": meter.get("last_test_date"),
            # Hard rule 2: money is STORED to 4 decimals and DISPLAYED to 2. The
            # store is here; the two is the renderer's.
            "at_risk": None if at_risk is None else _stored(at_risk),
            "currency": currency,
            "at_risk_is": "billed for this service on the last issued bill",
            "billed_to": bool(account_id),
        },
    }


def _stored(value: Decimal) -> str:
    """4 decimals, the way every money field in this product is written."""
    return str(value.quantize(Decimal("0.0001")))


def _row_words(outcome: str, past_life, untested, meter: dict[str, Any]) -> str:
    """What the row says, in words a clerk reads — never a code (B14 rule 32)."""
    if outcome == OUTCOME_BOTH:
        months = (past_life or {}).get("over_by_months", 0)
        return f"{_years(months)} past its change-out age, and no test on file."
    if outcome == OUTCOME_PAST_LIFE:
        months = (past_life or {}).get("over_by_months", 0)
        life = int((past_life or {}).get("life_months", 0) / 12)
        return f"{_years(months)} past a {life}-year life."
    since = meter.get("install_date") or meter.get("purchase_date")
    if since:
        return f"No test on file since it went in on {since}."
    return "No test on file, and no install date either."


def _years(months: Any) -> str:
    """*17 months* reads as a number; *1 year 5 months* reads as an age."""
    total = int(months or 0)
    if total < 12:
        return f"{total} month{'s' if total != 1 else ''}"
    years, rest = divmod(total, 12)
    if not rest:
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{years} year{'s' if years != 1 else ''} {rest} month{'s' if rest != 1 else ''}"


# ── the report, composed at close and frozen (`BR-RBS-020`) ───────────────


def _tile(tile_id: str, label: str, value: dict[str, Any], detail: str | None = None):
    tile: dict[str, Any] = {"id": tile_id, "label": label, "value": value}
    if detail:
        tile["detail"] = detail
    return tile


def _text(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def _money_value(amount: Decimal, currency: str | None) -> dict[str, Any]:
    """A money value that DECLARES ITS BASIS (`BR-REP-001`, `DEF-RBS-4350`).

    `posting`: this figure is summed off ISSUED bills, so it is billing-side
    money that has been posted. A tile with no basis takes the renderer's
    fallback and reads *Posting date* by luck rather than by declaration — which
    was right for the accounting export and wrong for the test bill.
    """
    return {
        "kind": "money",
        "amount": _stored(amount),
        "currency": currency or "",
        "basis": "posting",
    }


def _found_rows(view) -> list[dict[str, Any]]:
    """Every record that is a finding, RANKED BY REVENUE AT RISK — the card's
    own sort, applied here because a per-record step cannot order a list.

    ⚠ **AN UNKNOWN FIGURE SORTS BELOW EVERY KNOWN ONE AND ABOVE NOTHING ELSE**,
    never as zero: a meter on an account that has never billed is exactly the
    one a clerk should look at, and sorting it as `0.0000` would bury it under
    every $2 residential meter in the fleet.
    """
    rows = [one for one in view.records if one.outcome != OUTCOME_OK]

    def key(record):
        amount = _decimal((record.data or {}).get("at_risk"))
        return (
            0 if amount is not None else 1,
            -(amount or ZERO),
            str((record.data or {}).get("asset_no") or ""),
        )

    return sorted(rows, key=key)


def report(view) -> list[Block]:
    """Composed at CLOSE from what the steps counted, then frozen (`BR-RBS-020`).

    **Verdict · KPIs · Records · Action · Downloads.** The Records block is the
    card's own sentence — *ranked by revenue at risk, each with Order a test →
    or Schedule change-out →* — so the ranking and the two links are the point of
    it, and each row carries exactly one of the two labels.
    """
    age = _checked(view, STEP_AGE)
    tests = _checked(view, STEP_TESTS)
    found = _found_rows(view)

    checked = int(age.get("meters_checked") or 0)
    past_life = int(age.get("meters_past_change_out_age") or 0)
    untested = int(tests.get("meters_with_no_test_on_file") or 0)
    no_life = int(age.get("meters_with_no_expected_life") or 0)
    no_base = int(age.get("meters_with_no_age_base") or 0)
    overdue = int(tests.get("tested_but_past_their_interval") or 0)

    total = ZERO
    currency = None
    known = 0
    for record in found:
        amount = _decimal((record.data or {}).get("at_risk"))
        if amount is None:
            continue
        known += 1
        total += amount
        currency = currency or (record.data or {}).get("currency")

    guarded = len(view.guarded)
    # ⚠ **THE BLIND-SPOT SENTENCE IS PART OF THE ANSWER, NOT A FOOTNOTE.** On a
    # fleet that records no expected life, *"0 past change-out age"* alone reads
    # as *your meters are young*.
    unjudgeable = no_life + no_base
    detail = []
    if unjudgeable:
        detail.append(
            f"{unjudgeable} meter{'s' if unjudgeable != 1 else ''} could not be judged on age — "
            f"{no_life} record no expected life and {no_base} record no install date."
        )
    if guarded:
        detail.append(f"{guarded} were left out by the guards.")
    if not checked:
        detail.append("No meters of this utility's own to look at yet.")

    return [
        Block(
            block="verdict",
            payload={
                "word": "Clear" if not found else "To fix",
                "tone": "success" if not found else "warning",
                "count": (
                    f"{len(found)} meter{'s' if len(found) != 1 else ''} of {checked}."
                    if checked
                    else "No meters checked."
                ),
                "detail": " ".join(detail),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    _tile(
                        "past_change_out_age",
                        "Past change-out age",
                        _text(str(past_life)),
                        "Older than its own expected life",
                    ),
                    _tile(
                        "never_tested",
                        "No test on file",
                        _text(str(untested)),
                        "Never proved accurate",
                    ),
                    # ⚠ A RATIO, BECAUSE A BARE COUNT ANSWERS NOTHING HERE. *14*
                    # is meaningless; *14 of 137* is the number that says whether
                    # this runbook can see the fleet at all.
                    _tile(
                        "not_judgeable",
                        "Cannot be judged",
                        _text(f"{unjudgeable} of {checked}" if checked else "—"),
                        "No expected life, or no install date",
                    ),
                    # ⚠ **THE GROUP THIS CARD DOES NOT NAME**, shown as a number
                    # and never as a row — see `step_never_tested`.
                    _tile(
                        "tests_overdue",
                        "Tested but overdue",
                        _text(str(overdue)),
                        "Not one of this runbook's two groups",
                    ),
                    _tile(
                        "at_risk",
                        "Revenue at risk",
                        (_money_value(total, currency) if known else _text("—")),
                        (
                            f"A month, across {known} of {len(found)} found"
                            if known
                            else "Nothing found has billed yet"
                        ),
                    ),
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [
                    {"key": "meter", "label": "Meter"},
                    {"key": "why", "label": "Why"},
                    {"key": "at_risk", "label": "A month", "numeric": True},
                    {"key": "fix", "label": ""},
                ],
                "rows": [
                    {
                        "id": str(record.subject.subject_id),
                        "cells": {
                            # B14 rule 31 — the meter's own number, never its id.
                            "meter": _text(
                                str((record.data or {}).get("asset_no") or record.subject.label)
                            ),
                            "why": _text(record.reason),
                            "at_risk": (
                                _money_value(
                                    _decimal((record.data or {}).get("at_risk")) or ZERO,
                                    (record.data or {}).get("currency"),
                                )
                                if (record.data or {}).get("at_risk") is not None
                                else _text("Not billed yet")
                            ),
                            "fix": {
                                "kind": "link",
                                # The card's own two controls, with the arrow the
                                # renderer draws.
                                "label": str((record.data or {}).get("fix_label") or ""),
                                "to": record.fix_route or FIX_ASSETS,
                            },
                        },
                    }
                    for record in found
                ],
                "total": len(found),
                # ⚠ **`empty` IS `{title, helper}` AND NOT A STRING — AND THE
                # FIRST DRAFT PASSED A STRING.** `RecordsPayload.empty` is
                # declared with two fields in
                # `07-frontend/src/features/runbooks/blocks/types.ts`, and
                # `RecordsBlock` draws `payload.empty.title` in an `<h4>` and
                # `payload.empty.helper` in a `<p>`. A string makes both
                # `undefined`, so the block renders **a blank area** between the
                # KPI strip and the Action button — no error, no console
                # warning, nothing red. `validate_report` cannot see it:
                # `PAYLOAD_FIELDS` closes the NAMES and says nothing about their
                # SHAPES, so the wrong type passes every backend check
                # (`DEF-RBS-4406`). It was found by looking at the rendered page
                # (hard-won law 6) and by nothing else.
                "empty": (
                    {
                        "title": "Nothing to change out.",
                        "helper": "Every meter is inside its expected life and has a test on file.",
                    }
                    if checked
                    else {
                        "title": "No meters to look at yet.",
                        "helper": "This utility owns no meter of its own that is in service.",
                    }
                ),
            },
        ),
        Block(
            block="action",
            payload={
                "label": "Raise a field order for all",
                "tier": "secondary",
                "enabled": False,
                # ⚠ B14 rule 33 — a refusal caps at five or six words. The long
                # version is in the module docstring, where it belongs.
                "reason": "Field orders are not built yet",
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "meters_found", "label": "Meters found", "format": "csv"},
                    {"id": "whole_fleet", "label": "Whole fleet", "format": "csv"},
                ]
            },
        ),
    ]


# ── what the run leaves on somebody's desk (`BR-RBS-022`) ─────────────────


def findings(view) -> list[Finding]:
    """One item per meter found — and **the ENGINE writes the rows**.

    A Check holds no writer at all and still populates `RBS-007`, which is the
    whole reason raising a work item is an engine act and refused BY NAME as a
    port (`BR-RBS-002`, `BR-RBS-022`).

    ⚠ **THE FINGERPRINT IS THE `kind` PLUS THE SUBJECT, AND THE RUN IS NOT IN
    IT** (`BR-RBS-017`, `US-RBS-006` §5). This runbook is the kind that reports
    the same meter every month until somebody changes it out; with the run in
    the fingerprint each month would mint a new row and the age a clerk reads —
    *"this has been waiting since March"* — would reset to today.

    ⚠ **`kind` NAMES WHAT WAS ASKED AND NEVER THE SENTENCE THAT CAME BACK.** The
    title carries the meter's age and that number moves every month; a
    fingerprint built on it would mint twelve rows a year for one meter.
    """
    out: list[Finding] = []
    for record in _found_rows(view):
        data = record.data or {}
        group = str(data.get("group") or GROUP_NEVER_TESTED)
        facts = GROUP_FACTS[group]
        out.append(
            Finding(
                kind=group,
                title=f"{data.get('asset_no') or record.subject.label} — {record.reason}",
                fix_route=record.fix_route or facts["fix_route"],
                weight=WEIGHT_PAST_LIFE if group == GROUP_PAST_LIFE else WEIGHT_NEVER_TESTED,
                # B14 rule 31 — what it is ABOUT, in the clerk's words.
                subject_ref=str(data.get("asset_no") or record.subject.label),
                subject_type=record.subject.subject_type,
                subject_id=str(record.subject.subject_id),
            )
        )
    return out


# ── the pinned scope (`BR-RBS-009`, `BR-RBS-019`) ─────────────────────────


def resolve(ctx):
    """The pinned set: **every meter this utility owns** — the declared unit.

    ⚠ **THE GUARDS DECIDE WHAT IS WALKED, NOT THIS FUNCTION.** Sample records,
    retired meters and store-room stock are all resolved into the set and then
    guarded out, because `RBS-004.4` draws a guard disabled WITH its reason and
    a filter applied here would be an exclusion no screen can show
    (`BR-RBS-012`). The pinned count and the walked count are two different
    figures and the report never presents one as the other.

    ⚠ **THE LABEL IS THE METER'S OWN NUMBER, NEVER ITS DATABASE ID** (B14 rule
    31). A meter with no number falls back to its type and its service, which
    are also things a clerk reads.
    """
    out = []
    for row in _census(ctx).get("meters") or []:
        label = str(row.get("asset_no") or "")
        if not label:
            label = (
                " · ".join(
                    str(part) for part in (row.get("type_name"), row.get("service_code")) if part
                )
                or "Meter"
            )
        out.append(SubjectRef(subject_type="meter", subject_id=str(row["asset_id"]), label=label))
    return out


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Meters past change-out age or never tested",
    # ⚠ **A CHECK, AND THE CARD'S KIND ROW IS CONDITIONAL** — *"waits on RB-049
    # for a field order, and is a Check without it"*. `RB-049` does not exist,
    # so this holds NO ports at all and the capability is absent rather than
    # unused (`BR-RBS-002`). The module docstring says what it becomes the day
    # `RB-049` lands, so the next lane does not re-derive it.
    kind=models.KIND_CHECK,
    # The source names this as the empty Assets category's FIRST runbook. Until
    # this commit the category held one step and no runbook, and an empty
    # category is never drawn as a filter chip (`RB-019`, `BR-RBS-025`).
    category="assets",
    subject_type="meter",
    unit_of_work="a meter",
    # ⚠ **MANUAL ONLY, WHICH IS THE NARROWEST DECLARATION THE CARD SUPPORTS.**
    # `RB-128`'s Trigger row reads *Not yet defined* and its commitment opens
    # *"A clerk sees…"*, so a person presses Run. Adding a schedule would be a
    # WIDER declaration than the card makes, and widening one is a change
    # request rather than a lane's decision (`13-change-process.md`). `RB-119`
    # sets the same precedent in the other direction.
    triggers=(models.TRIGGER_MANUAL,),
    # ⚠ NONE. The source's tag table covers runbooks 1–22 only and states
    # nothing for 28; inventing tags here would put this runbook on filters
    # nobody chose.
    tags=(),
    parameters=(
        Parameter(
            name="change_out_age",
            type=PARAM_REF_SETTING,
            label="Change-out age",
            # ⚠ **DECLARED, AND THE SETTING DOES NOT EXIST YET.** `RBR-03` makes
            # policy Settings-owned and read-only on a card; no `assets` setting
            # holds a utility-wide change-out age today, so the step reads each
            # meter's OWN `expected_life_years` — which is what the Assets
            # screen's replacement forecast already uses (B16 §5.1b). The
            # absence is stated rather than papered over, and `RB-119`'s
            # `orphan_means` is declared the same way for the same reason: a
            # parameter that appears the day the setting does is a smaller
            # change than one nobody remembered.
            setting_key="assets.change_out_age_years",
        ),
        Parameter(
            name="never_tested_means",
            type=PARAM_ENUM,
            label="Never tested means",
            default="no_test_on_file",
            # ⚠ ONE CHOICE, AND IT IS THE CARD'S OWN WORDS — *"with no test on
            # file"*. A second value (*past its test interval*) is a THIRD group
            # this card does not name; its count travels as a tile instead.
            # `RB-119`'s `duplicate_means` sets the precedent.
            choices=("no_test_on_file",),
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=guard_sample),
        Guard(key="retired", label="Never include: Retired", applies=guard_retired),
        Guard(key="store_room", label="Never include: In the store room", applies=guard_store_room),
    ),
    resolve=resolve,
    report=report,
    findings=findings,
    steps=(
        Step(
            key=STEP_AGE, label=STEP_LABELS[STEP_AGE], mode=MODE_SET, run=step_past_change_out_age
        ),
        Step(key=STEP_TESTS, label=STEP_LABELS[STEP_TESTS], mode=MODE_SET, run=step_never_tested),
        Step(
            key=STEP_RISK,
            label=STEP_LABELS[STEP_RISK],
            mode=MODE_PER_RECORD,
            run=step_revenue_at_risk,
        ),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-043 (EP-RBS-01; CR-075, runbook 28 — RB-128)
# generated: 2026-09-07 by the CR-075 runbooks 28+33 lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a runbook needs none; RB-020's claim is that adding one costs one line in definitions/__init__.py) E=n/a(no screen — RBS-004 and RBS-006 are renderers over the definition and the report) F✔ G✔ H=n/a(no 🔒 path — it composes no key, holds no port and writes nothing)
# exceptions: (1) A CHECK, on the card's own conditional kind row — RB-049 does not exist and there is no work-order port; what it becomes when RB-049 lands is written out in the module docstring. (2) *The utility's change-out age* is read as the METER's own expected_life_years, which is what the Assets replacement forecast already uses; the Settings parameter is declared and its key does not exist. (3) *Tested but past its interval* is a THIRD state the card does not name — counted as a tile, never raised as a row. (4) Revenue at risk is a MONTH of billed revenue off the last issued bill, never a projection, and an unknown is None and never 0.0000.
# gates: MEASURED 2026-09-07, not claimed — `pytest tests/test_us_rbs_043_meter_change_out.py tests/test_us_rbs_044_budget_relevel.py` **51 passed**, with ELEVEN cases first shown RED on the specific wrong build each docstring names · `G115` (the module's boundary census) names neither of this lane's files; its two failures are `leak_alert.py:838` (landed 7f5c2892, 2026-09-07) and the port count still reading thirteen against fourteen (the port landed dff6b379, the constant was written 815777f0) — both DATED with `git log -S`, both filed as `DEF-RBS-4379` · `G2` code-trace names only `accounting_export.py`'s `US-RBS-042` · `G23` surface-debt **PASS** · `ruff` **All checks passed** · `black --line-length 100` clean · the browser walkthrough `10-scripts/render-checks/rbs-2833-runbooks.mjs` **28 checks, all green in Chromium** · full `run_gates` **89 PASS / 30 FAIL / 2 SKIP**, against a lane-start baseline of **82 / 37 / 2** — seven fewer failures than when this lane started and not one of the thirty names anything it wrote. Three of those thirty were PROVED pre-existing by running them in a worktree at the commit before this lane's first: `test_us_rbs_015_conformance` money-basis (seven tiles in five OTHER runbooks), `test_us_rbs_038` `z_cutover`, and the `RBS-004` setup fixture (wave T's `domain`/`multi` fields, fixture not regenerated).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
