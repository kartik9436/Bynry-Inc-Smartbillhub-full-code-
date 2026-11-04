# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007/008 (S28 — a staged row becomes a committed read) ·
#           US-MET-012/013 (S25 / S29 — the reads surfaces that print the unit)
#           Screens: S25 · S28 · S29 · S50 · S21
# Rules:    BR-MET-143 (**the rule this file IS** — a reading's unit must match
#           the unit of the thing that PRICES it; a mismatch of SCALE is
#           reconciled by the meter's multiplier, a mismatch of DIMENSION never
#           is) · BR-MET-051 (*"Demand: manual demand-register value at cycle
#           read"*) · BR-MET-019 (consumption = (current − prior) × multiplier)
#           · BR-MET-059 (the channel model) · BR-RAT-014 (the demand charge is
#           per kW) · BR-RAT-038 (rating's own unit gate) · OQ-004's closure
#           (*"no silent conversion"*) · OQ-391's closure
#           CLAUDE.md hard rule 3 — a consumption always carries an EXPLICIT
#           unit and one is never assumed.
# Golden:   none. This file states no money and no rate; GT-20/GT-21 price a
#           demand quantity that arrives here already measured. ❄️ B5 untouched.
# Tests:    06-backend/tests/test_br_met_141_register_units.py
# Impacts:  apps/metering/services._build_context (stamps the register's unit on
#           the read) · apps/metering/validation.compute_consumption (a maximum
#           register is not a running total) · apps/metering/selectors
#           (read_dict / _channel_quantities publish it) ·
#           core/sample_fixture.register_multiplier (the seeded factor)
# ───────────────────────────────────────────────────────
"""**BR-MET-143 — WHAT UNIT A REGISTER CARRIES, AND WHEN A MULTIPLIER MAY
RECONCILE TWO UNITS.** Pure: no ORM, no tenant context, no clock, no writes.

HUMAN-OWNED · HUMAN-REVIEW-PENDING
-----------------------------------
⚠ **THIS FILE STATES NO MONEY AND STILL DECIDES SOME.** It holds no rate, no
amount and no rounding — but it answers the two questions a per-kW demand charge
is priced from: WHAT QUANTITY (`billable_quantity` — a maximum register's VALUE,
not BR-MET-019's delta) and IN WHAT UNIT (`register_unit`). Getting either wrong
is DEF-797: **$154.00 where the correct charge is $4,532.00**, and it reached a
running product.

It is enrolled under the PO's 2026-08-09 protocol — the markers above, plus a row
in `12-governance/09-human-review-ledger.md` — and it is **NOT** matched by any
glob in `10-scripts/gates/human_owned.txt`, so **G7 does not watch it**.

⚠ **THAT IS EXACTLY THE ESCAPE THAT LIST RECORDS THREE TIMES ALREADY**, in its
own entries for `billing/issue.py`, `billing/decisions.py` and
`billing/read_analysis.py`, each with the same sentence: *"the file already
carried HUMAN-REVIEW-PENDING and a ledger row and NO glob here matched it, so G7
reported conform over a money path."* Three occurrences, one cause — the list is
maintained by hand and a new money file joins the CODE without joining the LIST.

**A LANE MAY NOT ADD ITSELF**, which those same entries state as the rule
(*"REMOVING IT FROM THIS LIST IS A PROCESS EVENT AND IS THE PO's CALL, NOT A
LANE's — the same rule that stopped the pricing lane from ADDING it"*). So the
glob is **put to the PO as `OQ-441`** rather than taken here, and this paragraph
is the record that the question was asked rather than the omission repeated.

THE RULING THIS IMPLEMENTS, VERBATIM (PO 2026-08-27, closing OQ-391)
--------------------------------------------------------------------
    "A demand reading carries kW - we have to match utility service unit and
    meter reading unit - if it does not match then we have intriduce multiplier
    factor on meter. you will ahve to seed that data."

Two halves, and the second is the general rule:

  (a) A demand reading carries **kW**. The unit is recorded per **REGISTER**,
      not per meter — so one electric meter holds kWh on its energy register
      and kW on its demand register. That is the whole of OQ-391 option (a).

  (b) The **service's** unit and the **reading's** unit must MATCH. Where they
      do not, a **multiplier factor on the meter** reconciles them, and that
      data is seeded.

⚠ THE ONE CONSEQUENCE, STATED RATHER THAN RESOLVED IN SILENCE
--------------------------------------------------------------
A multiplier is a **SCALE** factor. It reconciles `ccf → kgal`, a ×10 register,
or raw gallons → kgal (which B4's own OQ-004 already describes: *"register
stores raw gallons; billed unit per-service config: kgal (default) / gal / ccf;
convert at rating input"*). **It cannot reconcile kW → kWh, because those are
different physical quantities** — power against energy — and no number turns one
into the other.

So the rule is applied as: **a reading's unit must match the unit of the thing
that PRICES it.** An energy register's kWh matches the energy charge; a demand
register's kW matches the per-kW demand charge (BR-RAT-014). Where two units
differ by SCALE, the meter's multiplier reconciles them. Where they differ by
DIMENSION, they are different quantities priced by different charges and are
**never summed** (CLAUDE.md hard rule 3).

That reading is the merge lane's, recorded as such in `12-governance/
02-decision-log.md` (2026-08-27 §1) and in BR-MET-143 — not the PO's words.

WHERE `kW` COMES FROM, BECAUSE THIS FILE INVENTS NO UNIT
--------------------------------------------------------
`DEMAND_UNIT_BY_ENERGY_UNIT` below is a **transcription of three statements the
repo already holds**, not a choice made here:

  1. `rate_schedules.demand_rate_per_kw` — B2's own column name; the demand
     charge is priced **per kW** and by nothing else.
  2. `apps.tenancy.services.SERVICE_DEFAULT_UOMS["electric"] == ("kWh", "kW")`
     — the seeded UoM catalog carries `kW`, scoped to electric, and
     `tenancy.selectors.uoms_for_service` offers it there and nowhere else.
  3. r10's own screen catalogue string, *"Demand (peak kW)"*.

An energy unit with **no** entry here gets **no demand unit**: `register_unit`
returns `None`, `validation`'s `unit_missing` integrity rule refuses the row by
name, and a clerk is told to declare the register's UoM. That is CLAUDE.md rule
3 made mechanical — a tenant metering demand in `kVA` is refused loudly rather
than posted as `kW`, and the fix is a ruling, never a default in this file
(hard-won law 3: the unsafe option is the one you type).

WHY DIMENSIONS ARE NAMED RATHER THAN INFERRED
----------------------------------------------
`DIMENSION_OF` is a declared map, not a parser. A parser that read `kWh` as
"energy" because it ends in `h` would read a tenant's own `kgal-h` the same way
and would be wrong the first time somebody typed a unit we did not foresee. An
**unknown** unit has dimension `None`, and `reconciliation` reports
`UNKNOWN_DIMENSION` — never `SCALE`, because guessing that two unknown units
are the same kind of quantity is exactly the silent conversion OQ-004 forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: The registers whose stored figure is a **MAXIMUM**, not a running total.
#:
#: BR-MET-051, verbatim: *"Demand: manual demand-register value at cycle read +
#: reset noted"*. A maximum has no delta to take: subtracting last cycle's peak
#: from this one's produces the difference between two maxima, which nothing
#: prices and nobody asked for. That subtraction is DEF-797 — a 412 kW peak
#: billed as 14 kWh, $154.00 against a correct $4,532.00.
#:
#: A tuple rather than a literal comparison so a second maximum register (a
#: future max-flow or peak-kVA register) joins the rule in one place.
MAXIMUM_REGISTERS: tuple[str, ...] = ("demand",)

#: energy unit (folded) → the unit its DEMAND register carries. Transcribed from
#: the three statements in the module docstring; nothing here is chosen.
#:
#: The key is the METER's own energy UoM rather than a service code, because the
#: unit is a fact about the REGISTER (OQ-391 option (a)) — an electric meter
#: installed on a tenant who calls the service something else still holds kWh
#: and kW, and a hardcoded `service == "electric"` is the assumption CR-039
#: wave A spent a wave removing.
DEMAND_UNIT_BY_ENERGY_UNIT: dict[str, str] = {"kwh": "kW"}

#: unit (folded) → the physical quantity it measures. DECLARED, never parsed —
#: see the module docstring. `None` (an absent key) means "this repo has not
#: been told", and an unknown unit is never asserted to match anything.
#:
#: Sources, per entry, so a later reader can check rather than trust:
#:   · kwh / therm  — `SERVICE_DEFAULT_UOMS` electric primary / gas ALTERNATE.
#:     (⚠ this said *"gas primary"* until 2026-09-07, `DEF-MET-4502`; gas's
#:     primary has been `ccf` since `BR-TEN-1180` on 2026-09-02. The DIMENSION
#:     is a fact about the UNIT and not about which slot claims it, so nothing
#:     in this map moved — only the sentence citing its source.)
#:   · kw           — the demand unit above.
#:   · kgal / ccf / gal — OQ-004's own list, verbatim: *"billed unit per-service
#:     config: kgal (default) / gal / ccf"*; `SERVICE_DEFAULT_UOMS` water/gas.
#:   · month        — `SERVICE_DEFAULT_UOMS` trash/broadband. It is a DURATION,
#:     and naming it keeps a flat monthly charge from ever being compared to a
#:     volume by an unknown-vs-unknown fallthrough.
DIMENSION_OF: dict[str, str] = {
    "kwh": "energy",
    "therm": "energy",
    "kw": "power",
    "kgal": "volume",
    "gal": "volume",
    "ccf": "volume",
    "month": "duration",
}

#: The four answers `reconciliation` can give. VALUES, not prose, because the
#: seeder groups its refusals on them and a screen shows one sentence per case.
MATCH = "match"  # same unit — nothing to reconcile, the factor is 1
SCALE = "scale"  # same dimension, different unit — a multiplier CAN reconcile
DIMENSION = "dimension"  # different quantities — no multiplier ever reconciles
UNKNOWN_DIMENSION = "unknown_dimension"  # this repo has not been told; refuse


def fold(unit: str | None) -> str:
    """A unit as this module compares them: stripped and case-folded.

    `kWh`, `KWH` and ` kwh ` are one unit. The STORED spelling is never changed
    by folding — `register_unit` returns the catalog's own `kW`, capital W and
    all, because that is what a person reads on a bill.
    """
    return (unit or "").strip().casefold()


def is_maximum_register(channel: str | None) -> bool:
    """True for a register whose figure is a peak rather than a running total."""
    return (channel or "") in MAXIMUM_REGISTERS


def demand_unit_for(meter_unit: str | None) -> str | None:
    """The unit a demand register carries on a meter measuring `meter_unit`.

    `None` where this repo has never been told — see the docstring. There is no
    default branch and there must not be one.
    """
    return DEMAND_UNIT_BY_ENERGY_UNIT.get(fold(meter_unit))


def register_unit(meter_unit: str | None, channel: str | None) -> str | None:
    """**The unit of ONE REGISTER** — OQ-391 option (a), made mechanical.

    Every register except a maximum one carries the meter's own UoM, exactly as
    before this rule. A maximum register carries its own unit, and `None` when
    none is declared, so the caller refuses rather than stamping a plausible
    one.
    """
    if is_maximum_register(channel):
        return demand_unit_for(meter_unit)
    cleaned = (meter_unit or "").strip()
    return cleaned or None


def dimension_of(unit: str | None) -> str | None:
    """The physical quantity `unit` measures, or None where it is not declared."""
    return DIMENSION_OF.get(fold(unit))


@dataclass(frozen=True)
class Reconciliation:
    """How a reading's unit stands against the unit of the thing that prices it.

    `kind` is one of MATCH / SCALE / DIMENSION / UNKNOWN_DIMENSION.
    `multiplier_can_reconcile` is the single question BR-MET-143 exists to
    answer, and it is True for exactly one kind — SCALE.
    """

    kind: str
    reading_unit: str | None
    pricing_unit: str | None
    reading_dimension: str | None
    pricing_dimension: str | None

    @property
    def multiplier_can_reconcile(self) -> bool:
        return self.kind == SCALE

    @property
    def matches(self) -> bool:
        return self.kind == MATCH

    def as_dict(self) -> dict[str, object]:
        """Self-describing detail, in the shape `rule_outcomes` already uses
        (BR-MET-022/056 — a flag says what it saw, never only that it fired)."""
        return {
            "kind": self.kind,
            "reading_unit": self.reading_unit,
            "pricing_unit": self.pricing_unit,
            "reading_dimension": self.reading_dimension,
            "pricing_dimension": self.pricing_dimension,
            "multiplier_can_reconcile": self.multiplier_can_reconcile,
        }


def reconciliation(reading_unit: str | None, pricing_unit: str | None) -> Reconciliation:
    """**BR-MET-143 in one function.** Does the reading's unit match the unit of
    the thing that prices it, and if not, can a multiplier close the gap?

    A missing `pricing_unit` is MATCH and not a refusal: nothing is configured
    to disagree with, so there is nothing to reconcile. The absence itself is
    already the subject of BR-RAT-038's gate at rating input — reporting it a
    second time here as a unit mismatch would send a clerk to the wrong screen.
    A missing `reading_unit` is not this function's business either: hard rule 3
    refuses that row upstream at `unit_missing`, long before anything prices it.
    """
    read_fold, price_fold = fold(reading_unit), fold(pricing_unit)
    read_dim, price_dim = dimension_of(reading_unit), dimension_of(pricing_unit)
    if not price_fold or not read_fold or read_fold == price_fold:
        kind = MATCH
    elif read_dim is None or price_dim is None:
        kind = UNKNOWN_DIMENSION
    elif read_dim == price_dim:
        kind = SCALE
    else:
        kind = DIMENSION
    return Reconciliation(
        kind=kind,
        reading_unit=(reading_unit or None),
        pricing_unit=(pricing_unit or None),
        reading_dimension=read_dim,
        pricing_dimension=price_dim,
    )


def billable_quantity(
    *,
    channel: str | None,
    value: Decimal | None,
    multiplier: Decimal | None,
    delta_consumption: Decimal | None,
) -> Decimal | None:
    """What this register actually bills — DEF-797's QUANTITY half.

    A running total bills its DELTA (BR-MET-019, computed by the caller and
    passed in as `delta_consumption`; this function repeats none of that
    arithmetic — two implementations of a signed rule is how a signed figure
    drifts). A **maximum** register bills its VALUE at the cycle read
    (BR-MET-051, verbatim), scaled by the meter's multiplier.

    ⚠ **THE MULTIPLIER IS APPLIED TO A PEAK, AND THAT IS THE RULING RATHER THAN
    THIS FILE'S CHOICE.** BR-MET-143 makes the meter's multiplier the thing that
    reconciles a register's own scale with the unit that prices it, and a CT
    ratio on a demand register scales kW to kW — the same dimension, which is
    precisely the case the ruling covers. It defaults to 1 on every seeded and
    every imported meter, so no existing figure moves; it is named here because
    a reader is entitled to know a peak is scaled and why.

    Contrast `validation.compute_consumption`'s DEVICE branch, which refuses the
    multiplier: an inverter's produced quantity is not a register reading at all
    and `Asset.multiplier` describes a register.
    """
    if not is_maximum_register(channel):
        return delta_consumption
    if value is None:
        return None
    return value * (Decimal(1) if multiplier is None else multiplier)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-MET-143 (PO ruling 2026-08-27, closing OQ-391 · DEF-797)
# generated: 2026-08-27 by the demand-unit lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 `DEMAND_UNIT_BY_ENERGY_UNIT` holds ONE entry (kWh → kW) — it is
#   a transcription of three existing statements, and an energy unit not in it
#   is REFUSED rather than defaulted · E3 the scale-vs-dimension reading of the
#   ruling is the merge lane's, recorded in the decision log and in BR-MET-143,
#   and one PO sentence corrects it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
