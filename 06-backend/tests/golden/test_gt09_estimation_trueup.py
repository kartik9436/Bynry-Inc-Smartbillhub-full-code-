# ── Trace ──────────────────────────────────────────────
# Epics:    EP-MET-05 (estimation + true-up)
#           Screens: — (Estimated tab, S31.2 / S29)
# Rules:    BR-MET-026 (estimation math: trailing-3-cycle daily average, actuals
#           only, x days in period) · BR-MET-027 (max 2 consecutive estimates) ·
#           BR-MET-029 (true-up by register arithmetic at the next actual, at
#           current-period rates) · BR-MET-028 (estimates labeled, reversible)
# Golden:   GT-9 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 36-37). PARTIAL: B5 freezes QUANTITIES only.
# Tests:    this file (PASSING since 2026-08-11 — metering published
#           true_up_quantity; the xfail marker is removed)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/metering (owner:
#           apps/metering/quantities.py → estimation.correction_quantity)
# ───────────────────────────────────────────────────────
"""GT-9 - missing read -> trailing-3 avg 618; real read implies 700 -> true-up +82 next bill (estimation math OPEN, A17 #1)

B5 GT-9 verbatim
----------------
  line 36: "## GT-9 - Estimated read + true-up"
  line 37: "Input: missing read, trailing-3 avg = 618 kWh billed; next cycle
            real read implies actual 700 -> true-up +82 kWh on that bill."
            ... SUPERSEDED stamp: "PO Q&A R6 2026-08-08 -> OQ-003 CLOSED:
            trailing-3-cycle daily average x days in period, actuals only, max 2
            consecutive estimates, true-up via register arithmetic at the next
            actual at current-period rates - shipped as tenant-configurable
            DEFAULTS, and 'GT-9 tests the default'. GT-29 (WE-13) is the full
            composite."

The stub docstring's "(estimation math OPEN, A17 #1)" is the pre-freeze marker;
B5's own inline stamp records OQ-003 CLOSED. A17 is the historical scoreboard
(CLAUDE.md: the live registry is 12-governance/01-open-questions.md).

NOT FROZEN IN B5 — two gaps, both reported rather than filled:

 1. The three trailing cycles that PRODUCE 618. B5 states the RESULT of the
    estimate ("trailing-3 avg = 618 kWh billed") and never the history behind
    it, so 618 cannot be derived in this test — it enters as an INPUT, quoted.
    Encoding a trailing history that happens to yield 618 would be inventing
    inputs to a frozen output.
 2. Any money. B5 GT-9 names no rate, no charge and no bill total; BR-MET-029
    says the true-up bills "at current-period rates" and B5 supplies none. This
    test therefore asserts QUANTITIES only, in kWh — the same posture the
    metering lane takes in tests/test_us_met_014_estimation.py.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-9 line 37) ─────────────────────────────────────────────────
# "trailing-3 avg = 618 kWh billed" — the quantity already estimated and billed.
PREVIOUSLY_BILLED = rating_seam.Quantity(amount=Decimal("618"), unit="kWh")
# "next cycle real read implies actual 700"
ACTUAL = rating_seam.Quantity(amount=Decimal("700"), unit="kWh")

# ── EXPECTED (B5 GT-9 line 37) ──────────────────────────────────────────────
EXPECTED_TRUE_UP = Decimal("82")  # "true-up +82 kWh on that bill"
EXPECTED_UNIT = "kWh"  # "618 kWh" / "+82 kWh" — B5 states the unit here


def test_gt09_estimation_trueup():
    # B5 FROZEN 2026-08-08. The xfail marker is GONE: metering published
    # true_up_quantity on 2026-08-11, this passes, and from here it MUST pass
    # forever.
    true_up = rating_seam.true_up_quantity(
        actual=ACTUAL,
        previously_billed=PREVIOUSLY_BILLED,
    )

    assert true_up.amount == EXPECTED_TRUE_UP
    assert true_up.unit == EXPECTED_UNIT  # hard rule 3: kWh, stated by B5

    # The true-up is POSITIVE here (the estimate under-billed). BR-MET-029 also
    # rules the negative direction ("negative trues credit"), but B5 GT-9 gives
    # no worked figure for it, so it is not asserted.

    # NOT FROZEN IN B5: the trailing-3 history behind 618, and every money
    # figure. Deliberately unasserted — see the module docstring.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (2026-08-10, before the owner landed) · AMENDED 2026-08-11 by the metering quantity-seam lane: marker REMOVED, this test now PASSES against apps/metering/quantities.true_up_quantity and must pass forever. Proved RED first — inverting the subtraction to previously_billed − actual yields −82 and this test fails; restored, it passes. No expected value was touched.
# exceptions: PARTIAL — B5 GT-9 gives (a) no trailing-3 history, so 618 enters as a quoted INPUT and the estimate is NOT derived here, and (b) no rate and no money at all, so only quantities are asserted. The negative true-up direction of BR-MET-029 has no B5 figure and is unasserted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
