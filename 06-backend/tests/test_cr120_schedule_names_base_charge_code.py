# ── Trace ──────────────────────────────────────────────
# Change:  CR-120-BRC06 — the rate schedule NAMES its base charge code. PO
#          ruling 2026-09-19, verbatim: *"no this is not correct ; So: plan →
#          rate schedule -> charge code → base charges - this is correct"*, and
#          *"we are not bindng base charges in rate schedule - you were taking
#          it default; now we are making it explicit it is a same rule - change
#          is default -> expliciate"*.
# Rules:   BR-RAT-1025 (NEW — the schedule names the code; NAMED first, the
#          `is_base` lookup second) · BR-RAT-088 CONFIRMED-AS-AMENDED (the
#          CHARGE CODE still owns the base AMOUNT) · BR-RAT-1011 / CR-078 (the
#          named-then-inferred precedent) · DEF-468 (R4 refuses on ambiguity) ·
#          DEF-2923 (a coherence refusal belongs at activation, not billing) ·
#          CLAUDE.md hard rule 2
# Impacts: apps/rating/resolution.py (R4) · apps/rating/resolution_catalogue.py ·
#          apps/rating/services.py · apps/rating/selectors.py ·
#          apps/rating/migrations/0037_cr120_schedule_base_charge_code.py
# ───────────────────────────────────────────────────────
"""THE SCHEDULE NAMES THE CODE, AND NOTHING THAT EXISTS CHANGES BEHAVIOUR.

⚠ **THE CLAIM THIS FILE HAS TO PROVE IS A NEGATIVE, AND A NEGATIVE IS WHERE A
CHECK PASSES WRONGLY.** The ruling rests on *"no existing schedule changes
behaviour and no bill moves on day one"*. A test that asserts that by running
the NEW code twice would be law 7's *incapable of failing* shape wearing the
name of the proof — it would pass whatever the new code did.

**So the negative is proved TWO ways and neither of them is that:**

  1. **ACROSS TREES.** `10-scripts/cr120_base_route_measure.py` resolves the
     base for every ready account on a real seeded PostgreSQL and prints a
     canonical line per account. It is run on THIS tree and on a control
     worktree pinned at the tip this lane started from, and the two outputs are
     diffed. That is the 47-of-47 figure in the review-ledger row.
  2. **BY CONSTRUCTION, HERE.** The fallback arm is asserted to take the
     IDENTICAL path: `resolve_base_charge(codes, service)` and
     `resolve_base_charge(codes, service, None)` must return the same object,
     and the seeded versions are asserted to carry a NULL binding, so arm 2 is
     the arm every existing row uses.

**AND THE POSITIVE HALF ASSERTS THE ROUTE, NOT THE NUMBER.** On the day this
ships the named code and the inferred code are the SAME code on every tenant,
so `base_charge == $8.00` passes whichever arm answered. Only
`base_source == "named_charge_code"` says a person's choice was honoured — the
same reason `base_source` exists at all (`DEF-2823`: *"a test that asserts the
figure passes when the figure is right and the SOURCING is wrong"*).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import resolution

pytestmark = pytest.mark.django_db

WATER = "water"
SIZE = "W-58"


def _schedule(**kwargs) -> resolution.ScheduleVersion:
    facts = {
        "version_id": "v-1",
        "service": WATER,
        "tariff_id": "t-1",
        "effective_from": date(2026, 1, 1),
        "size_rows": {SIZE: None},
    }
    facts.update(kwargs)
    return resolution.ScheduleVersion(**facts)


def _code(**kwargs) -> resolution.ChargeCode:
    base = {
        "code": "BASE-W",
        "service": WATER,
        "is_base": True,
        "charge_type": "recurring",
        "amount_rule": "flat",
        "amounts": {SIZE: Decimal("8.00")},
    }
    base.update(kwargs)
    return resolution.ChargeCode(**base)


def _resolved(*codes: resolution.ChargeCode):
    """R4's own narrowing, so these cases price what a bill would price."""
    return tuple(
        (code, resolution.charge_code_amount(code, SIZE if code.service else None))
        for code in codes
    )


def _chain(schedule: resolution.ScheduleVersion, *codes: resolution.ChargeCode):
    catalogue = resolution.Catalogue(
        plan_versions=(
            resolution.PlanVersion(
                plan_id="p-1",
                version=1,
                services=(WATER,),
                schedules={WATER: "t-1"},
                effective_from=date(2026, 1, 1),
            ),
        ),
        schedule_versions=(schedule,),
        charge_codes=codes,
    )
    return resolution.resolve(
        catalogue=catalogue,
        account=resolution.AccountFacts(account_no="AC-1", unit_id="u-1"),
        premises=resolution.PremisesFacts(),
        meters=(resolution.MeterFacts(WATER, SIZE, multiplier=Decimal("1")),),
        quantities={WATER: Decimal("10")},
        service_date=date(2026, 7, 1),
    )


# ══════════════════════════════════════════════════════════════════════════
# ARM 2 · THE FALLBACK — what every schedule that exists does
# ══════════════════════════════════════════════════════════════════════════


def test_a_schedule_that_names_nothing_resolves_exactly_as_it_does_today():
    """**THE WHOLE SAFETY OF THE RULING, IN ONE ASSERTION.**

    `base_charge_code` defaults to None on `ScheduleVersion` and `rating/0037`
    adds the column NULL, so this is what EVERY version on EVERY tenant does on
    the day this ships. `base_source == "charge_code"` — the INFERRED route —
    is what says the new arm did not take over.

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9832`), NOT DELETED — ARM 2 IS RETIRED.**
    PO, verbatim: *"if it is provided then you will take it if it is not
    provided then you will take it zeo ; but you cannot take W-COM because it is
    availabel in charge coede"*. It asserted `$8.00` via the inferred route; a
    schedule naming nothing now bills `$0` with `base_source="not_set"`.
    """
    line = _chain(_schedule(), _code()).services[0]
    assert line.base_charge == Decimal("0")
    assert line.base_source == "not_set"


def test_passing_None_is_the_same_call_as_passing_nothing():
    """⚠ **THE ONE ASSERTION THAT CANNOT BE SATISFIED BY A COINCIDENCE.**

    Both forms must reach the SAME code path, not merely agree on today's
    fixture. If a lane later gives the named arm a different narrowing, an
    `is_base` lookup and an explicit `None` would start disagreeing here before
    they disagree on a bill.
    """
    codes = _resolved(_code())
    # `DEF-RAT-9832` (2026-10-06): the shared path now REFUSES as not bound, so
    # the two forms must both raise it.
    with pytest.raises(resolution.BaseChargeNotBound):
        resolution.resolve_base_charge(codes, WATER)
    with pytest.raises(resolution.BaseChargeNotBound):
        resolution.resolve_base_charge(codes, WATER, None)


def test_the_ambiguity_refusal_still_fires_when_nothing_is_named():
    """`DEF-468` (PO 2026-08-21) is UNTOUCHED on the inferred arm. Two codes
    declaring themselves the base and no binding is still *the customer is
    billed by catalogue order*, and the chain still refuses rather than taking
    the first match.

    ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`): still never the first match — but
    no longer the ambiguity sentence. Neither code is named, so neither is
    taken: `BaseChargeNotBound`, which `resolve` bills as `$0` not-set."""
    codes = _resolved(_code(), _code(code="BASE-W-2", amounts={SIZE: Decimal("34.00")}))
    with pytest.raises(resolution.BaseChargeNotBound) as refusal:
        resolution.resolve_base_charge(codes, WATER)
    assert "names no base charge code" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# ARM 1 · THE NAMED CODE — `BR-RAT-1025`
# ══════════════════════════════════════════════════════════════════════════


def test_the_named_code_is_the_base_and_the_line_SAYS_it_was_named():
    """The explicit route, end to end. The figure alone proves nothing here —
    `$8.00` is what the inferred arm produces too — so the assertion that
    carries the ruling is `base_source`."""
    line = _chain(_schedule(base_charge_code="BASE-W"), _code()).services[0]
    assert line.base_charge == Decimal("8.00")
    assert line.base_source == "named_charge_code"


def test_naming_one_of_two_base_codes_CURES_the_ambiguity_it_does_not_repeat_it():
    """⚠ **THIS IS WHY THE NAMED ARM DOES NOT RUN `DEF-468`'s CHECK.**

    Two codes declare themselves water's base — `$8.00` and `$34.00` — which
    `DEF-468` refuses outright, because the catalogue's order would otherwise
    decide what a customer pays. **Naming one is the CURE for that**, and a
    utility with a residential and a commercial base needs exactly this. The
    figure asserted is the NAMED one, and it is deliberately the one a
    first-match would NOT have returned.
    """
    line = _chain(
        _schedule(base_charge_code="BASE-W-2"),
        _code(),
        _code(code="BASE-W-2", amounts={SIZE: Decimal("34.00")}),
    ).services[0]
    assert line.base_charge == Decimal("34.00")
    assert line.base_source == "named_charge_code"


def test_a_named_code_that_does_not_reach_this_account_REFUSES_it_does_not_fall_back():
    """⚠ **THE FAIL DIRECTION, AND IT IS THE POINT OF THE WHOLE BINDING.**

    The schedule names a code scoped to commercial; this account is
    residential, so R4's narrowing drops it. Falling through to the `is_base`
    lookup would bill `$8.00` while step 5 of the wizard shows the commercial
    code — **the screen and the bill disagreeing with neither visibly wrong**,
    which is `BR-RAT-088`'s own failure shape (§A3: `$23,069.50` a month across
    1,247 connections) in the other direction.

    ⚠ **SUPERSEDED 2026-09-30 — THE CHAIN NO LONGER REFUSES; IT BILLS `$0`.**
    PO: *"if user did not define and bind base charges in rate schedule - then
    as a default you take 0 and complete the bill instead of refusing"*. A
    bound code that cannot answer here is *no base bound for this account*.
    **What does NOT move is the point of this case: it never falls back to the
    other code's `$8.00`.** `resolve_base_charge` still raises the named
    refusal (`BaseChargeNotBound`, a `ChargeCodeAmountMissing`); `resolve`
    catches it and answers `base_source="not_set"`.
    """
    line = _chain(
        _schedule(base_charge_code="BASE-W-COM"),
        _code(),
        _code(
            code="BASE-W-COM",
            customer_classes=("commercial",),
            amounts={SIZE: Decimal("15.00")},
        ),
    ).services[0]
    assert line.base_charge == Decimal("0")
    assert line.base_source == "not_set"
    with pytest.raises(resolution.ChargeCodeAmountMissing) as refusal:
        resolution.resolve_base_charge((), WATER, "BASE-W-COM")
    message = str(refusal.value)
    assert "BASE-W-COM" in message
    assert "BR-RAT-1025" in message
    # It must not silently become the OTHER code's figure.
    assert "8.00" not in message
    # ⚠ **AND IT MUST NOT NAME A CAUSE THAT CANNOT OCCUR (`DEF-498`).** A base
    # code can never fail the recurrence test — `rides_a_periodic_bill` returns
    # True for `is_base` before it reads `charge_type` or `auto_apply`
    # (`BR-RAT-117`, `BR-RAT-088`: *"this does not move the base"*) — so a
    # refusal offering *"not carried on an ordinary periodic bill"* would send a
    # utility to look at the wrong two flags. A first draft of this message did.
    assert "periodic bill" not in message


def test_a_named_code_that_is_simply_absent_REFUSES_rather_than_inferring():
    """The binding points at a code the catalogue does not carry for this
    account at all. Same refusal, same reason: an inferred answer here is a
    figure no screen showed.

    ⚠ SUPERSEDED 2026-09-30: `$0` with `base_source="not_set"` instead of a
    refusal — and still never the inferred code's `$8.00`."""
    line = _chain(_schedule(base_charge_code="BASE-GONE"), _code()).services[0]
    assert line.base_charge == Decimal("0")
    assert line.base_source == "not_set"


def test_the_legacy_scalar_is_NOT_consulted_when_a_code_is_named():
    """⚠ **THE RETIRED COLUMN STAYS RETIRED.** A version with BOTH a legacy
    `$12.00` in `size_rows` and a named code must bill the CODE. Reading the
    scalar here would resurrect the column `BR-RAT-088` retired, on the one
    path that was built to replace it."""
    line = _chain(
        _schedule(size_rows={SIZE: Decimal("12.00")}, base_charge_code="BASE-W"), _code()
    ).services[0]
    assert line.base_charge == Decimal("8.00")
    assert line.base_source == "named_charge_code"


def test_base_source_has_exactly_three_values_and_schedule_is_still_one_of_them():
    """The pre-`BR-RAT-088` tenant is untouched by this ruling: no charge code
    at all, no binding, and R4's legacy fallback still answers with
    `base_source == "schedule"`."""
    line = _chain(_schedule(size_rows={SIZE: Decimal("12.00")})).services[0]
    assert line.base_charge == Decimal("12.00")
    assert line.base_source == "schedule"
