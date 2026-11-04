# ── Trace ──────────────────────────────────────────────
# Epics:    EP-MET-04 (read validation / rollover classification) ·
#           EP-RAT-05 (the engine prices what metering supplies)
#           Screens: — (the flag surfaces on S28 step 3 / S29)
# Rules:    BR-RAT-011 (rollover consumption = (max - prior) + current) ·
#           BR-MET-015 (rollover classification per the OQ-009 closure) ·
#           BR-AST-015 (register_digits is the rollover-detection input)
# Golden:   GT-4 — B5 ❄️ FROZEN 2026-08-08 (05-golden-tests.md lines 21-22),
#           refined by GT-14 (line 52-53) with the register-span check.
# Tests:    this file (PASSING since 2026-08-11 — metering published
#           consumption_from_registers; the xfail marker is removed)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/metering (owner:
#           apps/metering/quantities.py → validation.classify_register_delta)
# ───────────────────────────────────────────────────────
"""GT-4 - prior 99,800; current 240; 5-digit wrap -> consumption 440 (rollover handling PLACEHOLDER)

B5 GT-4 verbatim
----------------
  line 21: "## GT-4 - Meter rollover"
  line 22: "Input: prior 99,800; current 240 (5-digit meter wrapped at 100,000);
            multiplier x1. Expected consumption = (100,000-99,800)+240 = 440."
            ... SUPERSEDED stamp: "PO Q&A R7 2026-08-08 -> OQ-009 CLOSED, GT-14
            rule CONFIRMED: >50%-of-span drop auto-computes the wrap and flags
            for review; small negative stays a bad-read exception. GT-14 below
            is the same scenario with the asset-digits span check."

B5 GT-14 verbatim (the refinement GT-4's own stamp points at)
-------------------------------------------------------------
  line 52-53: "## GT-14 - Rollover with asset digits (OQ-009) / 5-digit register,
            prior 99,800, current 240, x1 -> (100,000-99,800)+240 = 440 (span
            check: 99,560 > 50% of 100,000 -> rollover, not negative-read)."

The stub docstring's "(rollover handling PLACEHOLDER)" is the pre-freeze marker;
B5's own inline stamp records it as SUPERSEDED and the rule as CONFIRMED. The
figure 440 is signed either way.

NOT FROZEN IN B5: the UNIT of the consumption. Neither GT-4 nor GT-14 states
one, and CLAUDE.md rule 3 forbids assuming it — so this fixture passes a
SYMBOLIC unit and asserts the seam returns the same symbol back. The register
arithmetic B5 freezes is unit-agnostic; the unit discipline is asserted as
pass-through, and the missing unit is reported, not chosen.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

pytestmark = pytest.mark.golden

# B5 GT-4/GT-14 state no unit for this reading pair. Rather than pick one
# (CLAUDE.md rule 3: "never assume"), the fixture passes a symbol and asserts
# it survives the arithmetic untouched.
UNIT_NOT_STATED_IN_B5 = "UNIT-NOT-STATED-IN-B5-GT-4"

# ── INPUT (B5 GT-4 line 22 · GT-14 line 53) ─────────────────────────────────
PRIOR_READ = Decimal("99800")  # "prior 99,800"
CURRENT_READ = Decimal("240")  # "current 240"
MULTIPLIER = Decimal("1")  # "multiplier x1"
REGISTER_DIGITS = 5  # "5-digit meter wrapped at 100,000" / "5-digit register"

# ── EXPECTED (B5 GT-4 line 22 · GT-14 line 53) ──────────────────────────────
EXPECTED_CONSUMPTION = Decimal("440")  # "(100,000-99,800)+240 = 440"
# GT-14's span check, quoted: the drop prior-current is 99,560 and the register
# span is 100,000, so the drop exceeds 50% of span -> rollover, NOT a negative
# read. Both figures are B5's, copied.
EXPECTED_SPAN = Decimal("100000")  # "wrapped at 100,000" / "50% of 100,000"
EXPECTED_DROP = Decimal("99560")  # "span check: 99,560"


def test_gt04_meter_rollover():
    # B5 FROZEN 2026-08-08. The xfail marker is GONE: metering published
    # consumption_from_registers on 2026-08-11, this passes, and from here it
    # MUST pass forever.
    consumption = rating_seam.consumption_from_registers(
        prior_read=PRIOR_READ,
        current_read=CURRENT_READ,
        multiplier=MULTIPLIER,
        register_digits=REGISTER_DIGITS,
        unit=UNIT_NOT_STATED_IN_B5,
    )

    assert consumption.amount == EXPECTED_CONSUMPTION
    # Hard rule 3: whatever unit went in comes back out, unchanged and never
    # inferred. B5 states no unit for GT-4, so this is all that can be asserted.
    assert consumption.unit == UNIT_NOT_STATED_IN_B5

    # GT-14's classification input, asserted as the frozen arithmetic it is:
    # the drop is 99,560 against a 100,000 span, which is what makes this a
    # rollover rather than the "small negative" bad-read exception.
    assert PRIOR_READ - CURRENT_READ == EXPECTED_DROP
    assert Decimal(10) ** REGISTER_DIGITS == EXPECTED_SPAN


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (2026-08-10, before the owner landed) · AMENDED 2026-08-11 by the metering quantity-seam lane: marker REMOVED, this test now PASSES against apps/metering/quantities.consumption_from_registers and must pass forever. Proved RED first — moving validation.ROLLOVER_SPAN_FRACTION from 0.5 to 0.9 makes the 99,560-vs-100,000 span check miss, and this test fails; restored, it passes. No expected value was touched.
# exceptions: PARTIAL — B5 states no UNIT for GT-4/GT-14. A symbolic unit is passed and asserted as pass-through rather than choosing kWh/kgal (CLAUDE.md rule 3); the gap is reported. GT-4's "PLACEHOLDER" in the old stub title is B5's own pre-freeze marker, stamped SUPERSEDED inline (OQ-009 CLOSED, PO R7) — the 440 is signed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
