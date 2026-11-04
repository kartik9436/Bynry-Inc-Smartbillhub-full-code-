# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-005 (S11 rate schedule wizard — the base-rate step) ·
#           US-BIL-003 (gather — which base charge a bill charges)
#           Screens: S11 (RAT-03 step 2, "Base rates") · S31 (where the $0.00
#           would have printed)
# Rules:    CR-013 part 1, verbatim: *"Blank base = size not served"* ·
#           BR-RAT-012 / BR-RAT-027 (the base charge lives on the PLAN's
#           service) · CLAUDE.md rule 2 (money is NUMERIC(18,6), never coerced)
# Ruling:   PO 2026-08-19 (decision log, CR-013 ruling 3) — *"print $0.00"* for
#           the rows ALREADY in the database, which cannot be disambiguated.
#           That ruling covers history only; a blank a tenant types from now on
#           still means "not served" and still refuses.
# Defect:   DEF-277 — `_decimal(...) or Decimal("0")` made absent, unserved and
#           deliberately-zero the same stored row
# ───────────────────────────────────────────────────────
"""DEF-277 — three different facts arriving at one column as `0.000000`.

**THE DEFECT.** `apps/rating/services.py` coerced a missing base charge to zero
with `or`, and `tariff_versions.base_charge` was NOT NULL with `default=0`. So
after a round trip through the wizard there was no way to tell apart:

  * *"I did not type a base for this schedule"* — absent;
  * *"this connection size is not served"* — CR-013 part 1's meaning of blank;
  * *"this size is served and it is free"* — a deliberate zero.

All three stored `0.000000`, and a bill then printed `$0.00` for a size the
utility refuses to serve. Nothing could catch it downstream, because every one
of the three produces a valid row that prices at zero — which is why no test
existed and why the defect only became visible when part 1 stated that blank
MEANS something.

**WHAT THIS FILE PINS, AND THE TWO HALVES ARE DELIBERATELY IN TENSION.**

  * A blank now survives the round trip as NULL and REFUSES to bill, by name.
  * A stored `0.00` still bills `$0.00`, because the PO ruled exactly that for
    the rows already in the database — no exception, no migration guessing at
    intent. `tc4` is that ruling, asserted, so a later reading of "blank means
    refuse" cannot quietly turn every historic zero into a broken bill.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SERVICE_DATE = date(2026, 7, 15)


def a_schedule(dana, *, marker, base):
    """A schedule created THROUGH THE WRITE PATH, with `base` omitted entirely
    when it is the sentinel `...` — because the defect is about what the write
    path does with an absence, and passing an explicit None would test a
    different thing than the wizard does when the cell is left empty."""
    payload = {
        "name": f"{marker} schedule",
        "service": "electric",
        "model": "flat",
        "uom": "kWh",
        "effective_from": "2026-01-01",
        "structure": {"tiers": [{"from_qty": "0", "to_qty": None, "unit_price": "0.11"}]},
    }
    if base is not ...:
        payload["base_charge"] = base
    return rating_services.create_rate_schedule(dana, payload)


def version_of(card):
    return rating_models.TariffVersion.objects.get(pk=card["current_version"]["id"])


def test_def_277_tc1__an_omitted_base_charge_is_stored_as_absent_not_as_zero(brazos, dana):
    """The round trip. A cell the operator never filled in must come back empty.

    This is the assertion the `or Decimal("0")` idiom fails: it is the ordinary
    defensive Python reading and it is lossy, because the column it writes into
    is the only place the distinction could have lived.
    """
    with tenant_ctx(brazos):
        card = a_schedule(dana, marker="def277-absent", base=...)
        assert version_of(card).base_charge is None


def test_def_277_tc2__a_deliberate_zero_is_stored_as_zero(brazos, dana):
    """The other half, and it is what makes tc1 a distinction rather than a
    rename: a size that IS served and IS free stores 0.00 and stays 0.00."""
    with tenant_ctx(brazos):
        card = a_schedule(dana, marker="def277-zero", base="0")
        assert version_of(card).base_charge == Decimal("0")


def test_def_277_tc3__a_blank_base_bills_zero_and_is_NAMED_not_silent(brazos, dana):
    """CR-013 part 1 — *"Blank base = size not served"*.

    ⚠ **SUPERSEDED 2026-09-30.** This case was `…_refuses_to_bill_rather_than_
    charging_zero`, on the argument that *"a utility silently billed $0.00
    finds out in an audit"*. The PO then ruled: *"if user did not define and
    bind base charges in rate schedule - then as a default you take 0 and
    complete the bill instead of refusing - if you want to show the warning you
    can display it dueing the process"*. The objection was to SILENCE, and the
    answer is no longer silent: the service is recorded for a named
    `baseNotSet` warning, which says which service, as the refusal did.
    (A per-size code with no price for THIS size — the rest of CR-013 part 1 —
    still refuses in rating; that is a conflict, not an absence.)
    """
    with tenant_ctx(brazos):
        token = gather._BASE_NOT_SET.set([])
        try:
            assert gather._base_charge_for("electric", code_base=None) == Decimal("0")
            assert gather._BASE_NOT_SET.get() == ["electric"]
        finally:
            gather._BASE_NOT_SET.reset(token)


def test_def_277_tc4__a_stored_zero_still_bills_zero__PO_ruling_2026_08_19(brazos, dana):
    """PO ruling, verbatim: **"print $0.00"**.

    Every `0.00` already in the database is either *"not served"* or *"free"*
    and the data cannot say which, so the PO ruled the history bills $0.00
    rather than a migration guessing intent. This test is that ruling: it must
    keep passing while tc3 also passes, which is the whole shape of the fix.
    """
    with tenant_ctx(brazos):
        # ⚠ **THE ZERO IS THE CHARGE CODE'S FROM 2026-09-28 (`DEF-BIL-7170`).**
        # This read `_base_charge_for("electric", None, Decimal("0"))` — a zero
        # on the RATE SCHEDULE's retired column. The ruling took both retired
        # columns off the money path entirely, so the only object that can
        # state a zero is the charge code, and the PO's *"print $0.00"* is
        # unchanged: a STORED zero is a price and it still bills $0.00.
        assert gather._base_charge_for("electric", code_base=Decimal("0")) == Decimal("0")


def test_def_277_tc5__a_plan_service_with_no_base_is_absent_not_zero(brazos, dana):
    """The second coercion site (`services.py:634`). `plan_services.base_charge`
    carried the same `default=0` and the same silent fill-in, and it is the
    column BR-RAT-012/027 put the base charge on — so a plan that states no base
    for a service must say so, and let the schedule's figure answer."""
    electric = tenancy_models.Service.objects.get(code="electric")
    with tenant_ctx(brazos):
        plan = rating_models.RatePlan.objects.create(
            tenant=brazos, code="PL-def277", name="def277 plan", status="published"
        )
        row = rating_models.PlanService.objects.create(
            tenant=brazos, rate_plan=plan, service=electric
        )
        row.refresh_from_db()
        assert row.base_charge is None
