"""Consumption quantities. Hard rule #3: a consumption value ALWAYS carries an explicit
unit (kWh, kgal, gal, ccf, therm...); never assume from service type.
Billed-unit-per-service is OPEN (A17 #3) — this module blocks silent assumptions.

⊕ `DEF-RAT-10220` (PO 2026-10-17) — **ONE spelling rule for "is this the same
unit?", used at BOTH places a quantity's unit is compared with the unit a price
is quoted per**: `billing.stages.measure_consumption.bills_installed_capacity`
(does this tariff bill the SUM of installed capacity?) and `rating.pricing.
stages.normalize._gate_uom` (BR-RAT-038 — refuse a quantity in another unit).
A clerk typed the solar rate's unit as `KW`; the capacity is in `kW`. Compared
exactly, the first test said *not the same unit* and billed the COUNT of panels
(2 × $14.00 = $28.00 for 47.84 + 10 kW); had it matched, the second would have
refused the bill one stage later. PO: *"do not hard code anything … make
logical corrections"* — so the rule is generic (case and white space), not a
`KW` special case, and it is the SAME function at both points so they can never
disagree.

What it does NOT do, and must not: convert. `kWh` and `MWh` stay different
units and BR-RAT-038 still refuses them. ⚠ Case-folding does make `mW` and `MW`
one key; no unit this product stores differs from another by case alone, and a
unit list that ever did would need a real unit identity rather than a string —
recorded in the decision log, not solved here.
"""

from __future__ import annotations


def unit_key(unit: object) -> str:
    """The comparison key of a unit spelling: white space collapsed, case
    folded. `" KW "`, `"kw"` and `"kW"` all give `"kw"`. Never shown to anyone
    — a document prints the unit as it was recorded."""
    return " ".join(str(unit or "").split()).casefold()


def same_unit(left: object, right: object) -> bool:
    """True when two unit spellings name the same unit under `unit_key`. Two
    blanks are NOT the same unit — a missing unit is a refusal (hard rule 3),
    never a match."""
    a, b = unit_key(left), unit_key(right)
    return bool(a) and a == b
