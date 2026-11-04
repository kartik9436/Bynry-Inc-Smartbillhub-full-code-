# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — proration)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-004 (proration by CALENDAR days; base AND usage both
#           prorated) · BR-RAT-002 (tier thresholds scale with the prorated
#           period) · BR-RAT-003 (round per line, half-up, 2dp, at finalization)
# Golden:   GT-3 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 18-19). PARTIAL: B5 freezes the prorated BASE only.
# Tests:    this file (xfail until apps.rating.engine.prorate_base_charge lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-3 - Move-in day 16 of 30, base $30.50 -> base 15.25; calendar days, base+usage prorated (B4.3 CONFIRMED)

B5 GT-3 verbatim
----------------
  line 18: "## GT-3 - Mid-cycle move-in (proration) - CONFIRMED calendar-days,
            base+usage prorated (B4.3)"
  line 19: "Input: move-in day 16 of 30; base $30.50. Base proration 15/30 x
            30.50 = **15.25**; usage prorated on calendar days too. [check] rule
            confirmed; example total pending usage figures."

NOT FROZEN IN B5 — stated by B5 itself, in those exact words: "example total
pending usage figures". GT-3 freezes ONE number, the prorated base 15.25. It
gives:
  * no consumption and no unit,
  * no usage rate and no usage charge,
  * no tax rate, and no bill total.
So this test binds to `prorate_base_charge` — the one seam that produces the one
frozen figure — and asserts nothing else. Calling the full pricing function here
would require inventing a consumption B5 withholds. The usage half of B4.3
(usage prorated on calendar days too) is CONFIRMED as a RULE but carries no
worked figure in B5; it stays untested here until finance supplies one, and that
gap is reported rather than filled.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-3 line 19) ─────────────────────────────────────────────────
# "move-in day 16 of 30" -> days 16..30 inclusive are served = 15 of 30. B5
# states the resulting ratio itself, "15/30", so the day counts below are B5's
# figures and not an arithmetic of ours. Calendar days (B4.3), never billing days.
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=15)
BASE_CHARGE = Decimal("30.50")  # "base $30.50"

# ── EXPECTED (B5 GT-3 line 19) ──────────────────────────────────────────────
EXPECTED_PRORATED_BASE = Decimal("15.25")  # "15/30 x 30.50 = **15.25**"


def test_gt03_proration_move_in():
    # Rule CONFIRMED by finance (B4, 2026-08-07). Becomes a hard regression gate
    # the moment apps/rating/engine.py exists. Expected values: B5 GT-3.
    prorated = rating_seam.prorate_base_charge(base_charge=BASE_CHARGE, period=PERIOD)

    assert prorated == EXPECTED_PRORATED_BASE

    # NOT FROZEN IN B5: the usage charge and the bill total ("example total
    # pending usage figures"). Deliberately unasserted — see the module
    # docstring. Adding them needs a finance re-sign (HUMAN-GUIDE section 6).


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until the engine lands)
# exceptions: PARTIAL by B5's own words — "example total pending usage figures". Only the prorated base 15.25 is frozen, so only it is asserted; the usage-proration half of B4.3 and the bill total have NO worked figure in B5 and are reported as a gap, not invented.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
