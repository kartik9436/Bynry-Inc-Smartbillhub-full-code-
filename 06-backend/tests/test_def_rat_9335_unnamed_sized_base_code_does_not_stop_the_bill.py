# ── Trace ──────────────────────────────────────────────
# Story:    CR-167-BRC10 round 1 (lane PLAN-SRV) — the README's check (b),
#           *"why do four base codes resolve, and which one does a bill charge?"*
# Rules:    BR-RAT-1025 (PO 2026-09-19: *"plan → rate schedule -> charge code →
#           base charges"* — the schedule NAMES the code that owns its base) ·
#           BR-RAT-088 (the charge code owns the base).
# Defect:   DEF-RAT-9335 — held as `xfail(strict=True)` in round 1 and shown
#           red first, verbatim:
#             apps.rating.resolution.ChargeCodeAmountMissing: R4: charge code
#             'BASE-W-FIRE' applies to this account and states no amount for
#             connection size 'W-58' on service 'water'. …
#           FIXED 2026-10-03 on the PO's ruling, verbatim: *"(a) Fix it: use the
#           base the schedule names. Bills refused today start going out; bills
#           already issued don't change."* The marker is removed; R4 now skips
#           a base code the schedule did not name (`resolve_charge_codes`
#           `named_base`). The second case pins the half that must NOT move.
# ───────────────────────────────────────────────────────
"""A schedule that names its base code must not be refused by a code it did
not name.

THE WORKED CASE (measured on PostgreSQL 16, `10-scripts/cr167_base_checks_pg.py`,
probe utility `plansrv-rcp`): a residential 5/8" water account; the water
schedule names `BASE-W1` ($10.00, every size, every class). The utility also
holds `BASE-W-FIRE`, a water base code for every class priced only for 1" and
2". The September bill is REFUSED with *"R4: charge code 'BASE-W-FIRE' applies
to this account and states no amount for connection size 'W-58'"* — about a
code the bill would never charge, because the schedule named another.

`resolve_charge_codes` (R4) prices EVERY applicable `is_base` code before
`resolve_base_charge` narrows to the named one, so a code that is never billed
can still stop the bill. Expected: base `$10.00`, `base_source =
"named_charge_code"`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import resolution

pytestmark = pytest.mark.django_db

WATER = "water"
SIZE = "W-58"


def _chain(*codes: resolution.ChargeCode, named: str | None):
    schedule = resolution.ScheduleVersion(
        version_id="v-1",
        service=WATER,
        tariff_id="t-1",
        effective_from=date(2026, 1, 1),
        size_rows={SIZE: None},
        base_charge_code=named,
    )
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
        service_date=date(2026, 9, 30),
    )


def _code(code: str, amounts: dict[str, Decimal]) -> resolution.ChargeCode:
    return resolution.ChargeCode(
        code=code,
        service=WATER,
        is_base=True,
        charge_type="recurring",
        amount_rule="flat",
        amounts=amounts,
    )


def test_an_unnamed_base_code_priced_for_other_sizes_does_not_stop_the_named_base():
    named = _code("BASE-W1", {SIZE: Decimal("10.00")})
    unnamed_sized = _code("BASE-W-FIRE", {"W-1": Decimal("12.00"), "W-2": Decimal("20.00")})
    line = _chain(named, unnamed_sized, named="BASE-W1").services[0]
    assert line.base_charge == Decimal("10.00")
    assert line.base_source == "named_charge_code"


def test_a_schedule_that_names_nothing_is_still_refused_by_an_unpriced_size():
    """The other half: with NO named code nothing narrows, so the sized code
    still prices this account and still refuses (design §A2, `DEF-468`'s
    posture). Only a schedule that NAMES its base changed."""
    named = _code("BASE-W1", {SIZE: Decimal("10.00")})
    unnamed_sized = _code("BASE-W-FIRE", {"W-1": Decimal("12.00"), "W-2": Decimal("20.00")})
    with pytest.raises(resolution.ChargeCodeAmountMissing, match="BASE-W-FIRE"):
        _chain(named, unnamed_sized, named=None)


def test_the_named_code_itself_still_refuses_an_unpriced_size():
    """The narrowing skips OTHER codes only — the named code is still priced
    at this size, and a size it does not price still refuses."""
    named = _code("BASE-W1", {"W-1": Decimal("10.00")})
    with pytest.raises(resolution.ChargeCodeAmountMissing, match="BASE-W1"):
        _chain(named, named="BASE-W1")
