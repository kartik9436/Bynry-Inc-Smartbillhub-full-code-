# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-011 (the validation engine owns the wrap arithmetic this
#           publishes) · US-MET-014 (auto-estimate) · US-MET-015 (true-up at
#           the next actual read)
#           Screens: — (pure functions; their quantities render on S28 step 3,
#           S29, S31.2 and are priced by rating for S31.3)
# Rules:    BR-MET-019 (consumption = (current − prior) × multiplier,
#           NUMERIC(18,6), EXPLICIT unit, unrounded) · BR-RAT-011 (rollover
#           consumption) · BR-AST-015 (register_digits is the rollover-detection
#           input — an ASSET fact) · BR-MET-052 (a negative that is not a wrap
#           is a hard error and is NEVER auto-fixed) · BR-MET-026 (estimation
#           math) · BR-MET-029 (true-up by register arithmetic) · BR-MET-058
#           (one channel's lineage never borrows another's)
# Golden:   GT-4 / GT-14 (rollover → 440) · GT-9 (true-up → +82) — B5 ❄️ FROZEN,
#           finance-signed 2026-08-08.
# Tests:    06-backend/tests/test_us_met_quantity_seams.py (incl. the RED proof
#           on the span fraction and the unit-from-configuration proof) ·
#           06-backend/tests/golden/test_gt04_meter_rollover.py ·
#           06-backend/tests/golden/test_gt09_estimation_trueup.py
# Impacts:  apps/billing/rating_seam.py (the published contract this satisfies,
#           resolved through apps/metering/services.py) · apps/metering/
#           validation.py + estimation.py (the arithmetic owners)
# ───────────────────────────────────────────────────────
"""metering's published QUANTITY seam — the metering half of `rating_seam.py`.

WHAT THIS MODULE IS
-------------------
The two callables `apps/billing/rating_seam.py` names as metering-owned, in the
shape that seam publishes:

    consumption_from_registers(prior_read, current_read, multiplier,
                               register_digits, unit) -> Quantity   (GT-4/GT-14)
    true_up_quantity(actual, previously_billed)       -> Quantity   (GT-9)

Both are PURE: no ORM, no tenant context, no clock, no writes, no cross-module
call. They can be exercised without a database, which is the whole reason the
frozen fixtures can bind to them.

WHAT THIS MODULE IS NOT
-----------------------
It is not a second implementation of anything. The wrap rule lives in
`validation.classify_register_delta` and the true-up subtraction lives in
`estimation.correction_quantity`; this module adds the UNIT and the seam's
argument names, and computes nothing of its own. Two implementations of a
frozen rule is exactly how a signed figure drifts.

NO MONEY, EVER (hard rule 2 / B4.4)
-----------------------------------
Quantities only. Neither function reads a rate, produces an amount, or rounds
to 2dp. B5 GT-4 and GT-9 freeze quantities and state no money at all; pricing
them at current-period rates is rating's half of those cases (BR-MET-029), and
if an edit here would ever produce a currency figure it needs a finance re-sign
via HUMAN-GUIDE §6, not a decision in this file.

THE UNIT IS DERIVED, NEVER ASSUMED (hard rule 3; PO ruling 2026-08-11)
----------------------------------------------------------------------
Every quantity below carries an explicit unit, and there is no code path here
that invents one:

  * `consumption_from_registers` takes `unit` as a REQUIRED argument and
    REFUSES a missing or blank one. There is no default and no "assume kWh"
    branch — that refusal is the rule, made mechanical.
  * `true_up_quantity` takes the unit from the two quantities it is given, and
    refuses when they disagree. Mismatched units are never silently converted
    (the OQ-004 closure: "no silent conversion") — a factor is configuration,
    and this module holds none.

Where does the unit come from, then? From the meter and its service, upstream:
`assets.Asset.unit` is the register's UoM (with `Asset.multiplier` and
`Asset.register_digits` alongside it — the same row supplies all three inputs
this seam needs), and the service's billed UoM comes from the tenant's
`TenantService.billed_uom` via `seams.service_billed_uom`. `services._build_context`
is the existing wiring of exactly that. `tests/test_us_met_quantity_seams.py`
proves the derivation rather than asserting it: it creates real meters — one
in kWh, one in kgal — and reads the unit off the row instead of writing a
literal, so a meter configured in kgal produces kgal.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.metering import estimation, validation


@dataclass(frozen=True)
class Quantity:
    """A measured quantity WITH its unit (CLAUDE.md rule 3).

    Structurally the `Quantity` published by `apps/billing/rating_seam.py`, and
    deliberately NOT an import of it: billing calls metering, so metering must
    not import billing (B1 — and it would be a cycle). This is the same posture
    `apps/rating/engine.py` takes with its own result type; the seam's contract
    is the field names `amount` and `unit`, and those are what travel.
    """

    amount: Decimal
    unit: str


def _explicit_unit(unit: str | None, *, argument: str) -> str:
    """The unit, or a refusal. CLAUDE.md rule 3 has no default branch.

    Raises rather than returning a refusal object because the seam's contract
    is `-> Quantity`: there is no room in the return type for "no answer", and
    a quantity with a guessed unit is worse than a loud failure.
    """
    cleaned = (unit or "").strip()
    if not cleaned:
        raise ValueError(
            f"{argument}: a consumption never travels without its unit "
            "(CLAUDE.md rule 3). The unit is DERIVED from the meter and its "
            "service — assets.Asset.unit for the register, TenantService.billed_uom "
            "for the service — and is never defaulted here."
        )
    return cleaned


def consumption_from_registers(
    *,
    prior_read: Decimal,
    current_read: Decimal,
    multiplier: Decimal,
    register_digits: int,
    unit: str,
) -> Quantity:
    """Consumption from two register readings, wrap-aware (BR-RAT-011 / GT-14).

    GT-4 / GT-14, frozen: a 5-digit register reading 99,800 then 240 has passed
    100,000, so the consumption is `(100,000 − 99,800) + 240 = 440` — not a
    negative read. What makes that a wrap rather than a bad read is the span
    check the OQ-009 closure ratified: the drop (99,560) exceeds 50% of the
    register span (100,000). Both halves live in
    `validation.classify_register_delta`; this function supplies the unit.

    `register_digits` is the asset's register span exponent (BR-AST-015) and is
    a REQUIRED argument. A wrap computed against an assumed span is the silent
    fix the rule exists to prevent, so with no usable span this function
    refuses rather than guessing a 5-, 6- or 9-digit register.

    Raises `ValueError` for a drop that is NOT a wrap (BR-MET-052: a negative
    read is a hard error, never auto-fixed, and this return type cannot carry
    "no answer"). Inside the read pipeline that same case is a flagged
    exception a clerk resolves — see `validation.compute_consumption`, which
    reads the identical classification and reports it as a rule outcome instead
    of raising. Nothing is invented on either path.
    """
    explicit_unit = _explicit_unit(unit, argument="consumption_from_registers(unit=...)")
    resolved = validation.classify_register_delta(
        prior=prior_read,
        current=current_read,
        multiplier=multiplier,
        register_digits=register_digits,
    )
    if resolved.consumption is None:
        raise ValueError(
            f"consumption_from_registers: prior {resolved.prior} → current "
            f"{resolved.current} is a NEGATIVE read, not a register wrap "
            f"(drop {resolved.drop}; register_digits {resolved.register_digits}). "
            "BR-MET-052: never auto-fixed — resolve it as a read exception "
            "(investigate / override / reject). No consumption is invented."
        )
    return Quantity(amount=resolved.consumption, unit=explicit_unit)


def true_up_quantity(*, actual: Quantity, previously_billed: Quantity) -> Quantity:
    """The correction carried onto the next bill after an estimate (BR-MET-029).

    GT-9, frozen: an estimate of 618 kWh was billed; the next real read shows
    the span actually measured 700 kWh; the true-up is `700 − 618 = +82 kWh`.
    The subtraction is `estimation.correction_quantity` — the same one
    `estimation.true_up` uses over a full estimate→actual lineage.

    A negative correction is legitimate and is NOT clamped (US-MET-015/TC-3):
    an over-estimate owes the customer a quantity credit.

    QUANTITIES ONLY. B5 GT-9 states no rate and no dollar figure, so none is
    produced here; BR-MET-029 prices the correction at CURRENT-period rates and
    that is rating's job, through the same seam.

    Both quantities must carry the SAME explicit unit — the unit of the answer
    is the unit of the inputs, never a choice made here. Mismatched units raise
    rather than convert: a conversion factor is tenant configuration (the
    OQ-004 closure, "no silent conversion") and this module holds none.
    """
    left = _explicit_unit(actual.unit, argument="true_up_quantity(actual=...)")
    right = _explicit_unit(
        previously_billed.unit, argument="true_up_quantity(previously_billed=...)"
    )
    if left != right:
        raise ValueError(
            f"true_up_quantity: actual is in {left!r} and previously_billed is in "
            f"{right!r}. A true-up is register arithmetic within ONE lineage "
            "(BR-MET-029/BR-MET-058); converting between units needs a configured "
            "factor and there is no silent conversion (OQ-004 closure)."
        )
    return Quantity(
        amount=estimation.correction_quantity(actual.amount, previously_billed.amount),
        unit=left,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-015@ec4ba67 (sha1[:7] of the four frozen sources this seam was
#         written from, concatenated in order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/05-modules/04-metering/06-epics/EP-MET-04-read-validation.md ·
#         04-docs/05-modules/04-metering/06-epics/EP-MET-05-estimation.md ·
#         04-docs/05-modules/04-metering/02-business-rules.md; co-stories
#         US-MET-011 (wrap arithmetic) + US-MET-014 (estimation), same sources)
# generated: 2026-08-11 by the metering quantity-seam lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure functions behind an existing seam; no endpoint is added) E=deferred(no-frontend-half) F✔ G✔ H=deferred(N/A — not a 🔒 path: quantities only. No rate is read, no money figure is produced, no rounding rule/idempotency key/RLS policy is authored here, so neither a finance re-sign nor a 09-human-review-ledger row is triggered. The two rules implemented are already CONFIRMED — OQ-009 closure/GT-14 and OQ-003 closure/BR-MET-029.)
# gates: ruff✔ black✔ · pytest tests -m golden → 9 passed / 2 xfailed (GT-4 and GT-9 flipped; GT-6 billing + GT-7 payments remain their owners')✔ · pytest tests -m "not golden and not isolation" → 1096 passed / 10 skipped✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL + GT-1..16 12 PASS/0 FAIL✔ · run_gates 14 PASS / 0 FAIL / 1 SKIP✔ · RED-first proof recorded in the lane report (span fraction moved 0.5 → 0.9 ⇒ GT-4 FAILS; restored ⇒ passes)
# exceptions: (1) Both functions RAISE on an input they cannot answer honestly (missing/blank unit · mismatched units · a negative that is not a wrap) because the seam's return type is `-> Quantity` and has no room for a refusal object; the read pipeline's own path reports the identical classification as a flagged rule outcome instead, so nothing is auto-fixed on either side. (2) `Quantity` is metering's OWN frozen type, structurally identical to the seam's — metering must not import billing (B1, and it would be a cycle); this is the same posture apps/rating/engine.py takes with its result type. The seam returns the owner's object unadapted, so the field names `amount`/`unit` ARE the contract. (3) GT-4/GT-14 state no unit; this lane did NOT annotate the frozen document. The unit is a required input derived from the meter/service configuration (PO ruling 2026-08-11) and the golden fixture's symbolic unit passes through untouched.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
