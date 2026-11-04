# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-120 (PO 2026-08-28, verbatim: "we need to charge account
#          based on connection size they have") · BR-RAT-088 (its refusal
#          clause, CONFIRMED 2026-08-20, which BR-RAT-120 confirms rather than
#          replaces) · BR-RAT-032 (the NULL tier group is "every size") ·
#          BR-RAT-015 / BR-TEN-171 (sewer carries no size class BY RULING) ·
#          BR-RAT-024 (the ten services)
# Defects: DEF-1810 (CLOSED here — R3's size refusal was unreachable through
#          any real adapter) · DEF-2060 (a configured size with no size-scoped
#          tiers published an empty tier tuple and priced its usage at nothing)
# Open Qs: OQ-560 (thermal steam bands) · OQ-561 (battery bands) — both stay
#          UNANSWERED and this file proves they still raise
# Tests:   this file
# ───────────────────────────────────────────────────────
"""BR-RAT-120 — THE CHARGE FOLLOWS THE ACCOUNT'S ACTUAL CONNECTION SIZE.

PO ruling 2026-08-28, put to them in plain English and answered in one
sentence: *"we need to charge account based on connection size they have"*.

WHAT WAS WRONG, WITH THE FIGURE
--------------------------------
`resolution_catalogue.schedule_version_facts` built its size axis as
``served_sizes | size_classes_for(version)`` and `served_sizes` came from the
CALLER — normally the size the account's meter actually is. So the size R3
looked up was, by construction, one the catalogue had just been told to serve.
On one tenant and one plan:

    served_sizes=('5/8',)     -> R3 resolves  $8.00
    served_sizes=('3-inch',)  -> R3 resolves  $8.00   <- never priced by anyone

Charging a 3-inch connection at the 5/8 rate is not charging based on the
connection size the account has, and R3's *"this size is not served"* refusal
was dead code (`DEF-1810`).

WHAT THIS FILE PINS
-------------------
Four cases, and the ruling changes exactly one of them. The other three were
already settled by `apps/tenancy/service_size_classes.py`, whose docstring is
the authority: *"an empty tuple means 'ruled to have none' (sewer) and a raise
means 'nobody has said' (these two). The two readings must never collapse into
each other, because one is a finished decision and the other is money nobody
has priced."*

  1. size CONFIGURED       -> priced at that size's rate. Unchanged. TC1.
  2. size NOT configured   -> REFUSES BY NAME, naming the size, never a
                              fallback to another size's rate. **The ruling.**
                              TC2, TC3.
  3. service ruled to have
     NO bands (sewer)      -> one ladder, a BLANK size, and blank is CORRECT
                              and not an error. TC4.
  4. bands NEVER ruled
     (thermal steam OQ-560) -> `SizeClassNotRuled` still raised. It stays
                              "nobody has priced this" and never becomes "no
                              size". TC5.
                              ⚠ **BATTERY WAS HERE UNTIL 2026-09-01 AND IS NOW
                              IN ROW 3 WITH SEWER (`DEF-2408`).** `OQ-561` was
                              DISSOLVED by the PO on 2026-08-27 — capacity
                              services are not banded at all — and until the
                              ruling reached the code a battery account could
                              not be billed at ALL.

⚠⚠ **THE SWITCH IS ON SINCE 2026-09-01, AND THIS FILE'S COST CLAUSE IS NOW
LIVE RATHER THAN HYPOTHETICAL.** This banner used to read *"NOTHING IS SWITCHED
ON AND NO BILL CHANGES — the chain still has no production caller"*. The
Product Owner ruled the pair in (*"Can you wire them in now - R3 and R4"*, then
*"can you fix this probelm and again try to siwthicing - R3 and R4"*), so
`BILLING_RESOLUTION_STEPS` ships `"R3,R4"` and **R3 — this file's own rule —
prices real bills.**

**The PO's sequencing was honoured in the order it asked for**, and that is why
the switch was allowed: the connection sizes were loaded first, and `BR-RAT-1010`
(PO 2026-09-01) then moved R3's axis onto the charge code. The per-utility
coverage report reads **0 (service · size) pairs with nothing pricing them**
across 3 utilities and 163 accounts, and the pair switched on inside a
rolled-back transaction moved **0 base charges and refused 0 accounts**.

**WHAT IS NO LONGER HYPOTHETICAL:** case 2 above — a size the tenant has not
configured — now **stops a real bill run**, by name, with no fallback
(`BR-BIL-872`). TC6 proves exactly that, on `gather.gather_account`, and proves
that emptying the setting brings the bill back. That is the whole of the
one-line rollback, tested rather than promised.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.rating import models as rating_models
from apps.rating import resolution, resolution_catalogue
from apps.tenancy import models as tenancy_models
from apps.tenancy import service_size_classes

from tests.test_def_438_parity import (
    SERVICE_DATE,
    WATER_SIZE,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

#: A size no utility in this repo has ever priced. It is the PO's own example
#: and the figure the ruling is written on.
UNPRICED_SIZE = "3-inch"
WATER_BASE = Decimal("8.00")


def _declare_a_base_charge_code(tenant, amount=WATER_BASE):
    """Declare water's `is_base` charge code — the ONE source of a base amount.

    `BR-RAT-088` (CONFIRMED 2026-08-20) made the charge code the only source, so
    with R4 served by the chain a tenant without one has every account of that
    service refused (`DEF-2923`). TC6b declares it so that the refusal it is
    actually testing is **R3's size refusal** and cannot be R4's missing-base
    refusal wearing the same exception.
    """
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code="BASE-W",
        name="Water base service",
        charge_type="recurring",
        amount_rule="flat",
        amount=amount,
        service=tenancy_models.Service.objects.get(code="water"),
        is_base=True,
    )


#: R7's narrowing facts, which `build_catalogue` has REQUIRED since `DEF-2824`
#: (the catalogue could otherwise be built with no customer class, no premises
#: and no service list, and `plan_tax_rules` fails closed on all three). Nothing
#: in this suite asks about a tax; the facts are stated so the size assertions
#: below are about SIZES and the `TypeError` cases are about the keyword they
#: name and not about a missing argument.
NO_TAX_FACTS = {
    "account": resolution.AccountFacts(account_no="", unit_id=""),
    "premises": resolution.PremisesFacts(),
}


def _water_version(tenant):
    plan = _water_plan(tenant)
    version = next(
        v
        for v in resolution_catalogue.build_catalogue(
            plan_id=plan.id, service_date=SERVICE_DATE, **NO_TAX_FACTS
        ).schedule_versions
        if v.service == "water"
    )
    return plan, version


def _bare_version(tenant, service_code, *, base=WATER_BASE):
    """A published plan on ONE service with a dated version and NO size rows.

    Deliberately bare: this is the shape every schedule in the shipped product
    actually has, because `rate_size_rows` is empty on every tenant and
    `charge_code_amounts` — where BR-RAT-088 puts the per-size base — is empty
    too (DEF-455).
    """
    plan = make_plan(tenant, name=f"Bare {service_code}", services=(service_code,))
    service = tenancy_models.Service.objects.get(code=service_code)
    binding = rating_models.PlanRateSchedule.objects.get(
        tenant=tenant, rate_plan=plan, service=service
    )
    rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff_id=binding.tariff_id,
        model="tiered",
        base_charge=base,
        currency="USD",
        effective_from=date(2026, 1, 1),
    )
    return plan, binding


# ── CASE 1 · a size the tenant configured prices at that size's rate ────────


def test_TC1_a_configured_size_prices_at_that_sizes_rate(brazos, dana):
    """Unchanged behaviour, and it is the control for TC2.

    `_water_plan` writes a `rate_size_rows` row for 5/8" — where a real tenant
    puts it — so the schedule SAYS it prices that size. R3 resolves the
    version's base, **$8.00**, exactly as it did before the ruling.
    """
    with tenant_ctx(brazos):
        _plan, water = _water_version(brazos)

        assert WATER_SIZE in water.size_rows, (
            "the schedule must state the size it prices — BR-RAT-120 reads the "
            "axis from configuration and no caller can add to it"
        )
        assert (
            resolution.resolve_size_row(water, resolution.MeterFacts("water", WATER_SIZE))
            == WATER_BASE
        )


# ── CASE 2 · a size nobody configured REFUSES BY NAME · THE RULING ──────────


def test_TC2_an_unconfigured_size_refuses_by_name_and_never_falls_back(brazos, dana):
    """⚠ **THE RULING, AND THE $8.00 / $8.00 PAIR IS GONE.**

    Before BR-RAT-120 this assertion could not be written: asking the catalogue
    to serve `3-inch` made it serve `3-inch`, so a 3-inch connection resolved
    the 5/8 rate and the two sizes came back with the SAME $8.00. Now the size
    axis is the schedule's, `3-inch` is not on it, and R3 refuses — **naming the
    size**, which is what an operator has to read to know what to fix.
    """
    with tenant_ctx(brazos):
        _plan, water = _water_version(brazos)

        assert (
            UNPRICED_SIZE not in water.size_rows
        ), "a size the tenant never configured must not appear on the axis"
        with pytest.raises(resolution.SizeNotServed) as refusal:
            resolution.resolve_size_row(water, resolution.MeterFacts("water", UNPRICED_SIZE))

        # The operator's sentence NAMES THE SIZE. A refusal that does not say
        # which size is a refusal nobody can act on.
        message = str(refusal.value)
        assert UNPRICED_SIZE in message, message
        assert "no row on the rate schedule" in message, message
        assert refusal.value.step == "R3"

        # ⚠ AND IT NEVER SUBSTITUTES. The 5/8 rate is still $8.00 and is still
        # resolvable; the 3-inch connection simply does not get it.
        assert (
            resolution.resolve_size_row(water, resolution.MeterFacts("water", WATER_SIZE))
            == WATER_BASE
        )


def test_TC3_the_caller_can_no_longer_widen_the_size_axis(brazos, dana):
    """`served_sizes` is REMOVED, not ignored — a `TypeError`, not a surprise.

    Silently dropping the keyword would leave every existing call site reading
    exactly as it did while meaning something else. The mechanism that produced
    DEF-1810 has to be impossible to write, not merely wrong to write.
    """
    with tenant_ctx(brazos):
        plan, _water = _water_version(brazos)

        with pytest.raises(TypeError):
            resolution_catalogue.build_catalogue(
                plan_id=plan.id,
                service_date=SERVICE_DATE,
                **NO_TAX_FACTS,
                served_sizes=(UNPRICED_SIZE,),  # type: ignore[call-arg]
            )
        with pytest.raises(TypeError):
            resolution_catalogue.schedule_version_facts(
                plan.id, served_sizes=(UNPRICED_SIZE,)  # type: ignore[call-arg]
            )


def test_TC3b_a_banded_service_that_configures_no_size_serves_none(brazos, dana):
    """The cost of the ruling, stated by the PO when they made it.

    *"Read the second way, the system refuses bills that price perfectly well
    today."* A water schedule with a scalar base and no size rows used to price
    every size the caller asked about. It now prices NONE, and every meter
    refuses by name.

    **This is why nothing is switched on.** The chain has no production caller,
    so no bill changes today; the sizes are loaded first and the chain is
    switched in after.
    """
    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, "water")
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]

        assert (
            version.size_rows == {}
        ), "a banded service whose version configures no size serves no size"
        with pytest.raises(resolution.SizeNotServed):
            resolution.resolve_size_row(version, resolution.MeterFacts("water", WATER_SIZE))


# ── CASE 3 · sewer — ruled to have NO bands, so BLANK IS CORRECT ────────────


def test_TC4_sewer_is_ruled_to_have_no_bands_so_a_blank_size_is_correct(brazos, dana):
    """Sewer prices from ONE ladder and a blank size is not an error.

    BR-RAT-015 prices sewer as a share of the WATER usage charge and it reads no
    register of its own, so there is nothing for a size class to size —
    `RATIFIED_SERVICE_SIZE_CLASSES["sewer"]` is an EMPTY TUPLE, which is a
    finished decision. The catalogue keys such a version under `NO_SIZE_AXIS`
    (the empty string, which is already what `resolution._size_key` produces for
    a fact carrying no size), so a sewer meter with no size resolves **$8.00**
    instead of refusing.
    """
    with tenant_ctx(brazos):
        assert service_size_classes.size_classes_for_service("sewer") == ()

        _plan, binding = _bare_version(brazos, "sewer")
        version = resolution_catalogue.schedule_version_facts(binding.tariff_id)[0]

        assert version.size_rows == {resolution_catalogue.NO_SIZE_AXIS: WATER_BASE}
        assert (
            resolution.resolve_size_row(
                version, resolution.MeterFacts("sewer", resolution_catalogue.NO_SIZE_AXIS)
            )
            == WATER_BASE
        )

        # ⚠ AND IT IS STILL NOT A LICENCE TO PRICE ANY SIZE. A sewer meter that
        # somehow carries 3-inch is a fact nobody configured, and it refuses.
        with pytest.raises(resolution.SizeNotServed):
            resolution.resolve_size_row(version, resolution.MeterFacts("sewer", UNPRICED_SIZE))


# ── CASE 4 · bands NEVER RULED — and battery is no longer one of them ───────
#
# ⚠⚠ **BATTERY LEFT THIS CASE ON 2026-09-01 (`DEF-2408`), AND IT DID NOT LEAVE
# BY ACQUIRING BANDS — IT LEFT BECAUSE THE QUESTION WAS DISSOLVED.** These two
# cases asserted `SizeClassNotRuled("OQ-561")` out of `schedule_version_facts`,
# which was TRUE of the code and five days out of date with the ruling: the PO
# dissolved `OQ-561` on 2026-08-27 — *"(a) multiplier replaces bands for
# capacity services (solar, battery, thermal); bands stay for pipe/amp/CFH -
# this si corect"* — and a battery account could not be billed at all in the
# meantime. Battery is now `()`, *ruled to have none*, which is sewer's answer.
#
# **SO THE DISTINCTION THESE CASES EXIST TO PROTECT IS UNCHANGED AND IS STILL
# ASSERTED — what changed is which service stands on which side of it.** No
# service in the ten-service catalogue is *never ruled* any more, so TC5 reaches
# the raise the only way that is now honest: through `steam_size_classes()`,
# thermal's own door, and through a REGISTERED-BUT-UNRULED dimension put into
# the register for the length of one assertion. That is not a weaker check — it
# is the same check with its subject named accurately, and it goes red the day
# somebody makes an unruled dimension return `()` by accident.


def test_TC5_bands_that_were_never_ruled_still_raise_by_name(brazos, dana, monkeypatch):
    """An UNRULED dimension refuses BY NAME and the catalogue propagates it.

    An empty tuple would say *"ruled to have no size class"*, which for these is
    exactly what nobody has ruled. `SizeClassNotRuled` is a
    `NotImplementedError` carrying its OQ-ID, which is what the prime directive
    asks for at an unruled boundary. The raise propagates out of
    `build_catalogue` rather than being caught: a bill that cannot be priced
    must stop, not be priced on a guess.

    RED PROVED — this case's own predecessor is the proof. It asserted the same
    raise against `battery` and went red the moment `DEF-2408`'s fix landed:

        FAILED …::test_TC5_battery_bands_were_never_ruled_so_the_catalogue_
          still_raises — DID NOT RAISE <class '…SizeClassNotRuled'>
    """
    # Thermal STEAM is the live unruled dimension and has its own door.
    with pytest.raises(service_size_classes.SizeClassNotRuled) as steam:
        service_size_classes.steam_size_classes()
    assert "OQ-560" in str(steam.value)
    assert isinstance(steam.value, NotImplementedError)

    # And the CATALOGUE still carries such a refusal out to the caller. No
    # catalogue service is unruled today, so the two registers are asked to put
    # one back for the length of this assertion — the MECHANISM is what is under
    # test, not battery. Both halves are needed and the order they are read in is
    # the reason: `size_classes_for_service` consults the RATIFIED map first, so
    # adding an unbanded entry without removing the ratified one changes nothing
    # (a first draft did exactly that and DID NOT RAISE).
    monkeypatch.delitem(service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES, "battery")
    monkeypatch.setitem(
        service_size_classes.UNBANDED_SERVICE_DIMENSIONS,
        "battery",
        ("OQ-99999", "a dimension nobody has ruled, for this assertion only"),
    )
    with tenant_ctx(brazos):
        _plan, binding = _bare_version(brazos, "battery")

        with pytest.raises(service_size_classes.SizeClassNotRuled) as unruled:
            resolution_catalogue.schedule_version_facts(binding.tariff_id)
        assert "OQ-99999" in str(unruled.value)
        assert isinstance(unruled.value, NotImplementedError)


def test_TC5b_ruled_to_have_none_and_never_ruled_do_not_collapse(brazos, dana):
    """The two readings the whole design rests on, asserted side by side.

    Sewer answers with a size axis; an unruled dimension refuses to answer at
    all. If a lane makes an unruled dimension return `()` these two become the
    same case, and money nobody has priced starts billing as *"no size"*.

    ⚠ **BATTERY LEFT THIS CASE AGAIN ON 2026-09-02 (`CR-062` A2/A5), AND THIS
    TIME BECAUSE IT IS NO LONGER A RULED-EMPTY SERVICE AT ALL.** It now carries
    six CAPACITIES (`BAT-5` … `BAT-30`), so it belongs on neither side of the
    distinction this case guards: sewer answers *"ruled to have none"*, thermal
    steam answers *"nobody has said"*, and battery now answers *"here are six
    capacities"*. Keeping it here would have made this case assert a third
    thing and guard none of them well.

    ⚠⚠ **AND ITS DEPARTURE EXPOSED A LIVE DEFECT IN THE SIZE AXIS — `DEF-3098`,
    filed rather than fixed here because the fix is one line in
    `apps/rating/resolution_catalogue.configured_sizes_for` and that file
    belongs to another lane.** That function asks
    `size_classes_for_service(service)` and reads *"no rows"* to mean *"not
    banded"*. Under CR-062 that inference is no longer sound: a capacity service
    HAS rows and is still not banded — the rows are a catalogue of equipment,
    not a rate axis. So a battery schedule stating no per-size rows flipped from
    one ladder at the blank size to **no size priced at all**, measured:

        assert battery.size_rows == sewer.size_rows
        AssertionError: assert {} == {'': Decimal('8.000000')}

    which refuses every battery bill on such a schedule — `DEF-2408`'s failure
    arriving from the opposite direction one week later. **The question the
    function means to ask now has an exact answer:
    `capacity_uom_for_service(service) is None` is what *"banded"* means.**
    `tests/test_capacity_end_to_end.py` stays green because its schedules DO
    configure sizes, which is why this went unnoticed there.
    """
    with tenant_ctx(brazos):
        _sewer_plan, sewer_binding = _bare_version(brazos, "sewer")

        sewer = resolution_catalogue.schedule_version_facts(sewer_binding.tariff_id)[0]
        assert sewer.size_rows  # a finished decision: one ladder

    with pytest.raises(service_size_classes.SizeClassNotRuled):
        service_size_classes.steam_size_classes()

    # Battery is now a THIRD kind of answer and is pinned by the fact that makes
    # it one, so a lane returning it to either of the other two goes red here.
    assert service_size_classes.capacity_uom_for_service("battery") == "kW"
    assert service_size_classes.capacity_uom_for_service("sewer") is None


# ── DEF-2060 · a configured size with no size-scoped tiers ──────────────────


def test_TC7_DEF_2060_a_configured_size_falls_back_to_the_schedules_tiers(brazos, dana):
    """A size row is a MINIMUM row; it is not a statement that tiers exist.

    `rate_size_rows` holds the per-size MINIMUM BILL. A tenant who configures
    5/8" there while leaving the tiers in the NULL *"every size"* group
    (BR-RAT-032) has said nothing about 5/8" tiers. Publishing `{'5/8': ()}`
    would say *"this size has no tiers at all"* and price every unit of usage at
    nothing; `resolve_tiers`'s own contract is that an ABSENT size uses the
    schedule's default tiers.

    The catalogue therefore omits a size whose tier list is empty.
    """
    with tenant_ctx(brazos):
        _plan, water = _water_version(brazos)

        assert WATER_SIZE in water.size_rows, "the size IS configured"
        assert WATER_SIZE not in water.tiers_by_size, (
            "a size with no size-scoped tiers must be ABSENT from tiers_by_size "
            "so `resolve_tiers` falls back to the schedule's own ladder — a present "
            "empty tuple prices all usage at $0.00 (DEF-2060)"
        )
        default = (Decimal("3.20"),)
        assert (
            resolution.resolve_tiers(water, resolution.MeterFacts("water", WATER_SIZE), default)
            == default
        )


# ── NOTHING IS SWITCHED ON ──────────────────────────────────────────────────


def test_TC6_no_bill_changes_because_the_chain_has_no_production_caller():
    """⚠ **THE SEQUENCING CLAUSE, AS A TEST.**

    BR-RAT-120's own words: *"the sizes are loaded FIRST … and the chain is
    switched in AFTER. Switching first would refuse every bill on every
    tenant."* The only thing in `apps/` that builds a catalogue is
    `apps/billing/resolution_shadow.py`, which observes and prices nothing.

    A new caller appearing here is not a bug in this test — it is the switch
    being thrown, and it must be thrown deliberately, after the sizes are
    loaded, with this line updated in the same commit.

    ⚠ **AND THIS LINE HAD NOT BEEN UPDATED — IT HAS BEEN RED ON THE BRANCH TIP
    (`DEF-2832`, found 2026-08-31).** `apps/billing/resolution_switch.py` became
    a second caller when `BR-BIL-870` landed and this assertion still named one,
    so **the guard that watches for the switch being thrown was failing rather
    than watching**, and the next lane to run the file reads the failure as
    pre-existing and moves on. Re-baselined here, and each caller is now named
    WITH the reason it is lawful — so a reader can tell an intended caller from
    the switch actually being thrown, which is the only question this test asks.

    Both callers price nothing today:

      * `resolution_shadow.py` OBSERVES — it runs the chain beside the live path
        and reports; `compare()` returns figures and changes none.
      * `resolution_switch.py` is the FORK POINT. It builds a catalogue only for
        a rule named in `BILLING_RESOLUTION_STEPS`, and
        `SERVED_BY_CHAIN_DEFAULT` is the empty string on every deployment — so
        `apply()` hands back the same object and this call is unreachable.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "apps"
    callers = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "build_catalogue(" in path.read_text(encoding="utf-8")
        and path.name != "resolution_catalogue.py"
    )
    assert callers == [
        "billing/resolution_shadow.py",
        "billing/resolution_switch.py",
    ], callers

    # ⚠ **THE SWITCH IS NO LONGER OFF, AND THIS ASSERTION MOVED WITH IT
    # (PO 2026-09-01, "Can you wire them in now - R3 and R4").** It used to read
    # `== ""`. Its point was never the empty string — it was that a rule cannot
    # reach a bill without reaching the PO first — so it now pins the RULED PAIR
    # and still goes red on any widening.
    #
    # The SET is asserted, not the constant, because the constant decides
    # nothing (`DEF-2922`): it is reached only as
    # `getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT)` and the setting is
    # always defined. Asserting it alone is a check that cannot fail, which
    # `DEF-182` names as worse than no check.
    from apps.billing import resolution_switch

    assert resolution_switch.steps_served_by_chain() == frozenset({"R3", "R4"}), (
        "the served set is not the pair the PO ruled on 2026-09-01. Adding a "
        "step here is a rule pricing real bills without a ruling; removing one "
        "is the documented rollback and belongs in a commit that says so."
    )
    assert resolution_switch.SERVED_BY_CHAIN_DEFAULT == "R3,R4", (
        "the two literals must move together (DEF-2922)."
    )


def test_TC6b_an_unconfigured_size_now_refuses_a_REAL_BILL_RUN_and_the_rollback_restores_it(
    brazos, dana
):
    """⚠ **BR-RAT-120's ACCEPTED COST, COLLECTED. THIS IS THE CASE THE RULE
    WARNED ABOUT AND IT IS NO LONGER HYPOTHETICAL.**

    TC2 proves R3 refuses an unconfigured size *at the resolver*. Until
    2026-09-01 that was the end of it — the chain had no production caller, so
    the refusal could not reach a bill, and the rule said so in terms: *"No bill
    changes on the day of this ruling."* The Product Owner has since ruled the
    pair on, so the sentence to prove is the one a utility actually experiences:
    **a banded service whose meter carries a size nothing prices STOPS THAT
    ACCOUNT'S BILL**, by name, with no fallback (`BR-BIL-872`).

    This runs `gather.gather_account` — billing's own function, the path a
    customer can reach — rather than the resolver, because *the resolver
    refuses* and *the bill stops* are different claims and only the second one
    is the cost `BR-RAT-120` accepted.

    ⚠ **AND IT PROVES THE ROLLBACK IN THE SAME BREATH, WHICH IS THE HALF THAT
    MAKES THE SWITCH SAFE TO HAVE THROWN.** With the setting emptied — the
    documented one-line rollback, re-read on every call and needing no release —
    the SAME account on the SAME data bills again. So this case fails if the
    switch stops working AND if the rollback stops working, and those are the
    two ways this change can hurt somebody.

    The base charge code is declared here on purpose: it keeps **R4** satisfied
    so that the refusal under test is unambiguously **R3's**, the size step.
    Without it the account would refuse for a missing base (`DEF-2923`) and this
    case would pass for the wrong reason.
    """
    from apps.billing import gather

    with tenant_ctx(brazos):
        # ⚠ **`base_code=False` FROM 2026-09-28 (`DEF-BIL-7170`).** `_water_plan`
        # now mints an `is_base` water code of its own, and this case declares
        # one two lines down for the reason its own docstring gives. TWO
        # unscoped base codes for one service is `DEF-468`'s ambiguity — *"2
        # base charge codes for water. Scope them on Charge codes."* — which
        # would refuse this account for a reason that is not the size, and the
        # case would pass or fail for the wrong one.
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _declare_a_base_charge_code(brazos)

        # The connection is a size this utility has never priced. Recorded on
        # the ASSET, which is the production seam — nothing is monkeypatched.
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(pk=asset["id"]).update(size_class=UNPRICED_SIZE)

        # ── THE PAIR IS ON: the bill STOPS, and the sentence names the size ──
        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)

        problem = refusal.value
        assert problem.reason == gather.GATHER_RULED_PATH_REFUSED
        message = str(problem)
        # BR-SHL-020 — the operator's sentence names the SIZE and the STEP, or
        # nobody can act on it.
        assert UNPRICED_SIZE in message, message
        assert "R3" in message, message

        # ── THE ROLLBACK: the same account, the same rows, bills again ──
        with override_settings(BILLING_RESOLUTION_STEPS=""):
            rolled_back = _price_live(account)
        assert rolled_back is not None
        assert rolled_back.resolution_steps == ()


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-RAT-120 (CONFIRMED 2026-08-28) + the decision-log ruling of the same
#         day + apps/tenancy/service_size_classes.py's own docstring (the
#         authority on "ruled to have none" vs "nobody has said") + DEF-1810
# generated: 2026-08-28 by the size-refusal lane
# gates: every case proved RED against the pre-change file FIRST and the failures
#         quoted in the decision log — TC3 "DID NOT RAISE TypeError", TC4 sewer
#         "assert {}" (it would have refused every sewer bill), TC5 "DID NOT
#         RAISE SizeClassNotRuled" (battery came back PRICED), TC7 "assert '5/8'
#         not in {'5/8': ()}". Then GREEN with the five sibling suites: 64 passed.
#         golden-verify 33 PASS / 0 FAIL, unchanged.
# exceptions: no browser proof — this chain has no screen and, by TC6, no
#         production caller at all. That is the point of it today.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
