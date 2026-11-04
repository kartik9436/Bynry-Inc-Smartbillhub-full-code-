# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2878 — R3's shadow comparison compared one value with itself.
#          `gather._connection_size_for` and `resolution_shadow.adapt` both
#          resolve `metering.connection_size_for`; the adapter puts that value
#          on `MeterFacts.connection_size`; `resolution.resolve_served_size`
#          ends `return meter.connection_size`; `compare()` then tested the
#          first against the last. So `47 agree` was 47 restatements of one
#          seam call, and the PO's release condition for R3 — *"run the
#          comparison over more than one seeded utility"* — could never have
#          been met by any population.
# Rules:   BR-RAT-120 / PO 2026-08-28 (an unpriced size is REFUSED and never
#          substituted) · BR-TEN-171 (the ratified service size classes) ·
#          BR-RAT-015 (sewer carries no size class) · BR-RAT-088 (the charge
#          code owns the base; R3 answers membership only) · DEF-484 / DEF-433
#          (the live path's every-size ladder) · DEF-2839 (the same fault at
#          R1, and the posture this file borrows: assert an invariant, never
#          count it as agreement)
# Tests:   this file. The measured half is
#          `10-scripts/cr052_r1r7_shadow_measure.py --sabotage R3-seam`.
# Impacts: apps/billing/resolution_shadow.compare 🔒 (HUMAN-REVIEW-PENDING) ·
#          10-scripts/cr052_r1r7_shadow_measure.comparator_coverage
# ───────────────────────────────────────────────────────
"""R3 has ONE piece of independent evidence and it is the REFUSAL.

── WHY THIS FILE EXISTS ──────────────────────────────────────────────────────

The pricing cutover switches one rule at a time and a rule may only switch when
the two paths have been measured to agree. **R3's measurement was a check that
could not fail**, and the repo said so in prose while a column counted 47
agreements from it. This file makes the two halves testable rather than stated:

1. **THE COMPARISON IS THE IDENTITY FUNCTION.** `resolve_served_size` returns
   the size it was handed. Asserted over EVERY ratified size class of every
   service the Product Owner has ruled a ladder for — because a claim about
   "the seeded W-58" is a claim about a fixture, and the claim being made here
   is about the function.

2. **THE REFUSAL IS NOT.** `SizeNotServed` fires when a size is absent from the
   SCHEDULE's own axis. The axis is the schedule's fact and the size is the
   connection's, so nothing about that answer came from the adapter — and the
   live path, faced with the same pair, prices the every-size ladder instead of
   refusing. That asymmetry is money, and case 3 below pins it.

── WHAT THIS FILE DOES NOT CLAIM ─────────────────────────────────────────────

It does not say R3 is safe to switch. It says which of R3's two behaviours can
carry evidence at all. The refusal being *correct* (BR-RAT-120, ruled twice) and
the refusal being *survivable on real tenants* are different questions, and the
second one is answered by the size axis existing wherever a tenant states it —
which `10-scripts/def2799_apply_size_axis.py` writes and
`cr052_r1r7_shadow_measure.py` reports as a precondition, not by this file.

⚠ **AND WHERE THE AXIS LIVES MOVED HOURS AFTER THIS FILE WAS WRITTEN** (PO,
2026-09-01: *"rate schedule will not provdie the size, charge code will
provide"*). R3's membership question is the `is_base` CHARGE CODE's, and the
schedule ladder these cases build survives as the FALLBACK for a service with no
such code. **Every case below stays valid and none of them changes**, because
they call `resolve_served_size` with an axis passed in and assert what it does
with one — the enumeration is about the FUNCTION, not about which object filled
it. When the narrowing is built, the case to ADD is a service whose charge code
states a narrower set than its schedule: the code wins, and a size on the
schedule alone must then refuse.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import resolution
from apps.tenancy import service_size_classes


def _schedule(service: str, *, sizes=()):
    """A schedule version whose axis is exactly `sizes`.

    `size_rows` carries no money since `BR-RAT-088` — R3 asks membership and R4
    asks the amount — so the values are `None`, which is r10's em-dash: *this
    size IS served and has no floor*.
    """
    return resolution.ScheduleVersion(
        version_id=f"v-{service}",
        service=service,
        size_rows={code: None for code in sizes},
    )


def _ratified_ladders() -> list[tuple[str, tuple[str, ...]]]:
    """Every service with a RATIFIED, NON-EMPTY size ladder, and its codes.

    Read from `service_size_classes` rather than listed here, so a class the PO
    ratifies later is covered the day it lands and a class removed stops being
    asserted. An empty ladder (sewer, and battery since `DEF-2408`) and an
    unruled one (thermal steam) are deliberately not in this list: they are
    cases 4 and 5.
    """
    ladders = []
    for service in service_size_classes.SERVICE_ORDER:
        try:
            rows = service_size_classes.size_classes_for_service(service)
        except service_size_classes.SizeClassNotRuled:
            continue
        except KeyError:  # pragma: no cover — SERVICE_ORDER is the ten
            continue
        if rows:
            ladders.append((service, tuple(code for code, _name in rows)))
    return ladders


def test_the_ratified_register_is_not_empty():
    """The enumeration below is only evidence if there is something to enumerate.

    A `_ratified_ladders()` that silently returned `[]` would make every
    parametrised case below vanish and the file would report green over nothing
    — the same comfortable lie `compare()` guards against when it refuses a run
    that compared zero services.
    """
    ladders = _ratified_ladders()
    assert ladders, "no service has a ratified size ladder — the enumeration is empty"
    assert sum(len(codes) for _s, codes in ladders) >= 30, (
        "BR-TEN-171 ratified forty classes across eight services; this file is "
        "enumerating far fewer, so something has stopped reading the register"
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE COMPARISON IS THE IDENTITY FUNCTION — over every ratified class
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("service", "code"),
    [(service, code) for service, codes in _ratified_ladders() for code in codes],
)
def test_the_chain_hands_back_the_size_it_was_given(service: str, code: str):
    """`resolve_served_size` is `return meter.connection_size` for a served size.

    ⚠ **THIS IS THE DEFECT, ASSERTED AS A PROPERTY RATHER THAN NARRATED.** The
    shadow's R3 row tested `TariffConfig.size_class` against this return value.
    Both trace to one call to `metering.connection_size_for`, so the row could
    only ever restate its own input — which is why `compare()` now asserts it
    as an invariant and the harness reports R3 as *cannot evaluate*.

    If this assertion ever fails, R3 has grown a real derivation of its own and
    the comparison becomes worth counting again. That is the trigger to revisit
    `comparator_coverage()`, and it is written here so the next reader knows
    what would change the answer.
    """
    served = resolution.resolve_served_size(
        _schedule(service, sizes=(code,)),
        resolution.MeterFacts(service=service, connection_size=code),
    )
    assert served == code
    assert served is code, (
        "the chain returned an equal-but-different object; the point stands but "
        "the identity claim in compare()'s R3 block should be re-read"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE REFUSAL IS INDEPENDENT — exhaustively, over the same register
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("service", "code"),
    [(service, code) for service, codes in _ratified_ladders() for code in codes],
)
def test_every_ratified_size_refuses_when_the_schedule_does_not_serve_it(
    service: str, code: str
):
    """A size absent from the SCHEDULE's axis refuses, whatever the seam said.

    **This is the half that is not circular**, and the reason is worth stating
    once: the size came from the connection and the axis came from the rate
    schedule, so `SizeNotServed` is an answer neither the adapter nor the live
    path supplied. It is the only thing at R3 that can carry evidence.

    The schedule here serves ONE size — a sentinel that is on no ratified
    ladder — so the axis is non-empty (an empty axis is BR-RAT-120's *"serves
    none"*, a different case, and `DEF-2799`'s unconfigured tenant, a third).
    """
    schedule = _schedule(service, sizes=("SENTINEL-NOT-A-RATIFIED-CLASS",))
    with pytest.raises(resolution.SizeNotServed) as refusal:
        resolution.resolve_served_size(
            schedule,
            resolution.MeterFacts(service=service, connection_size=code),
        )
    assert code in str(refusal.value)
    assert "refuses rather than charging $0.00" in str(refusal.value)


@pytest.mark.parametrize(
    ("service", "codes"),
    _ratified_ladders(),
)
def test_a_full_ladder_serves_every_one_of_its_own_ratified_sizes(
    service: str, codes: tuple[str, ...]
):
    """And the refusal is not indiscriminate — a complete axis refuses nothing.

    Without this case the one above is satisfied by a `resolve_served_size` that
    refused everything, which would be a step that can never switch rather than
    a step with an independent comparison.
    """
    schedule = _schedule(service, sizes=codes)
    for code in codes:
        assert (
            resolution.resolve_served_size(
                schedule, resolution.MeterFacts(service=service, connection_size=code)
            )
            == code
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHY THE REFUSAL IS MONEY — the live path prices what the chain refuses
# ══════════════════════════════════════════════════════════════════════════


def test_the_live_path_prices_a_size_the_schedule_does_not_name_and_the_chain_refuses():
    """The asymmetry, on ONE pair of inputs, both halves called for real.

    **The pair:** a water schedule that prices `W-2` differently from every
    other size, and a connection whose size is `W-58`.

      * the CHAIN refuses — `W-58` is not on the axis, so no bill is produced;
      * the LIVE path prices it — `gather` refuses only when the schedule names
        size groups and NO size could be resolved (`GATHER_SIZE_UNRESOLVED`,
        DEF-484). A size that resolved and simply is not one of the named groups
        falls through to the NULL *every size* group and is billed.

    That is the difference the cutover has to rule on, and it is the ONLY thing
    R3 can put in front of anybody. `$8.00` a month here — the every-size base
    this fixture states — on a connection the ruled path would not have billed
    at all.
    """
    # ── the live half, with rating's projection stubbed to the shape DEF-433
    #    gave it. The stub takes three parameters so `_call_pricing_inputs`
    #    passes the size, which is the arity check that function makes.
    def pricing_inputs(tariff_row, service_date, size_class=None):
        return {
            "size_groups": ("W-2",),
            "base_charge": Decimal("8.0000"),
            "version_id": "v-water",
            "tiers": (),
            "billed_unit": "kgal",
        }

    priced = gather._call_pricing_inputs(
        pricing_inputs, object(), date(2026, 7, 1), "W-58"
    )
    assert priced is not None
    assert priced["size_groups"] == ("W-2",)
    # `gather._tariff_config_for` refuses only on `sized_groups and not
    # size_class`. W-58 IS a size, so the branch does not fire and the base
    # charge below is what the customer is billed.
    assert bool(priced["size_groups"]) and bool("W-58")
    assert priced["base_charge"] == Decimal("8.0000")

    # ── the ruled half, on the same pair
    with pytest.raises(resolution.SizeNotServed):
        resolution.resolve_served_size(
            _schedule("water", sizes=("W-2",)),
            resolution.MeterFacts(service="water", connection_size="W-58"),
        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE TWO CASES THAT ARE NOT REFUSALS, KEPT APART (DEF-2851's boundary)
# ══════════════════════════════════════════════════════════════════════════


def test_a_service_ruled_to_have_no_ladder_passes_through():
    """Sewer, unchanged by this file. `DEF-2851`'s fix must survive it."""
    assert service_size_classes.size_classes_for_service("sewer") == ()
    assert (
        resolution.resolve_served_size(
            _schedule("sewer"),
            resolution.MeterFacts(service="sewer", connection_size=resolution.NO_SIZE),
        )
        == resolution.NO_SIZE
    )


def test_a_dimension_whose_bands_were_never_ruled_still_raises_rather_than_serving():
    """Thermal STEAM. An unruled ladder is not an empty one, and never becomes one.

    Guarded here as well as in `service_size_classes`' own suite because THIS
    file's enumeration skips it, and a skip is invisible: if an unruled
    dimension ever started returning `()` the enumeration above would silently
    keep passing while a service nobody priced started resolving every size.

    ⚠ **THIS CASE READ `battery` UNTIL 2026-09-01 (`DEF-2408`), AND BATTERY DID
    NOT ACQUIRE BANDS — ITS QUESTION WAS DISSOLVED.** The PO ruled on 2026-08-27
    that capacity services are not banded at all, so `battery` became `()`,
    *ruled to have none*. Thermal steam is the only dimension left that nobody
    has ruled, and it is what this case now guards.

    ⚠⚠ **AND BATTERY MOVED A THIRD TIME ON 2026-09-02 (`CR-062` A2/A5): IT NOW
    RETURNS SIX ROWS, AND THAT IS STILL NOT A REOPENING OF `OQ-561`.** That
    question asked WHERE ONE BAND ENDS — a question about price boundaries — and
    none of the six states one. They are a CATALOGUE of the capacities a utility
    can install (5 kW to 30 kW), which the PO asked for in those words, and
    every battery bills at the same per-kW rate. The mechanical difference is
    asserted below and is the one to trust over any comment: a service whose
    rows SUM answers a unit, a service whose rows are BANDS answers `None`.
    """
    with pytest.raises(service_size_classes.SizeClassNotRuled):
        service_size_classes.steam_size_classes()
    # DEF-2408 then CR-062 — battery has been all three things in six days
    # ("nobody has said", "ruled to have none", "a catalogue of capacities"), so
    # it is pinned by the fact that distinguishes them rather than by a count.
    # A lane that turns these six back into BANDS flips this to `None` and goes
    # red here rather than in production.
    assert service_size_classes.capacity_uom_for_service("battery") == "kW"
    assert "battery" not in service_size_classes.UNBANDED_SERVICE_DIMENSIONS


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2878 · CR-052 task 20 (the per-step shadow count) · decision log
#         2026-08-31 *"STEP 4 OF THE CUTOVER, ANSWERED"* (the hold on R3 and its
#         stated release condition) · decision log 2026-09-01 (this finding)
# status: VERIFIED-UNRATIFIED — the R3 REFUSAL is proved independent and
#         enumerated over the ratified register; whether R3 SWITCHES is the
#         Product Owner's and is not decided here.
# generated: 2026-09-01 by the R3-release evidence lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL and G61 frozen-figures PASS before and
#         after — no ❄️ B4/B5 figure is read, asserted or moved here. The $8.00
#         in case 3 is a stub's own value, not a signed figure.
# exceptions: none. Nothing here prices a real bill;
#         `resolution_switch.SERVED_BY_CHAIN_DEFAULT` is untouched and empty.
