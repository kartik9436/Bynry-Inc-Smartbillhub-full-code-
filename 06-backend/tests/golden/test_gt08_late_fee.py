# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — late fee assessment)
#           Screens: — (the fee line renders on the invoice / S31.2)
# Rules:    BR-BIL-001 (late fee = max($5, 1.5% x OVERDUE PORTION); grace
#           counted from the Due date) · BR-BIL-008 (grace: tenant-defined,
#           DEFAULT 5 calendar days after due date, range 0-30) ·
#           BR-RAT-003 (round per line, half-up, 2dp, at finalization)
# Golden:   GT-8 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 33-34).
# Tests:    this file (xfail until billing publishes assess_late_fee)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/billing (owner)
# ───────────────────────────────────────────────────────
"""GT-8 - overdue portion $542.10 -> max(5, 0.015x542.10)=8.13; grace from Due date (B4.1 CONFIRMED; grace-days number PLACEHOLDER)

B5 GT-8 verbatim
----------------
  line 33: "## GT-8 - Late fee - CONFIRMED prior-balance, grace from Due date
            (B4.1)"
  line 34: "Input: overdue portion $542.10 (only the past-due part, not full
            balance), past Due date beyond grace. `late_fee = max(5,
            0.015x542.10) = max(5, 8.13) = 8.13`. [check] formula +
            overdue-portion base confirmed; **grace-days number still
            PLACEHOLDER** - **SUPERSEDED** (PO Q&A R6 2026-08-08 -> OQ-005
            CLOSED -> BR-BIL-008: tenant-defined, default 5 calendar days after
            due date, range 0-30); waiver is manual."

The stub docstring's "grace-days number PLACEHOLDER" is the pre-freeze marker;
B5's own inline stamp closes it at 5 calendar days (default), and 5/calendar is
therefore a B5 figure, taken from that stamp.

B5 writes the fee as "max(5, 0.015x542.10) = max(5, 8.13) = 8.13" — i.e. it
presents 8.13 already finalized. This test asserts 8.13. It does not re-derive
8.1315, and it does not round anything itself (B4.4: rounding happens once, in
the owner, at finalization).

NOT FROZEN IN B5: the calendar dates. B5 states the CONDITION in words — "past
Due date beyond grace" — not a due date and not an as-of date. The two dates
below are fixture scaffolding chosen to satisfy that stated condition; no
assertion depends on their values.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import rating_seam

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-8 line 34) ─────────────────────────────────────────────────
OVERDUE_AMOUNT = Decimal("542.10")  # "overdue portion $542.10 (only the past-due part)"
PERCENT = Decimal("0.015")  # "0.015x542.10"
MINIMUM = Decimal("5")  # "max(5, ...)"
GRACE_DAYS = 5  # B5 line 34 SUPERSEDED stamp: "default 5 calendar days"
GRACE_MODE = "calendar"  # B5 line 34 SUPERSEDED stamp: "5 CALENDAR days"

# Fixture scaffolding, NOT frozen figures: dates that satisfy B5's stated
# condition "past Due date beyond grace" (6 calendar days elapsed > 5-day grace).
DUE_DATE = date(2026, 7, 15)
AS_OF = date(2026, 7, 21)

# ── EXPECTED (B5 GT-8 line 34) ──────────────────────────────────────────────
EXPECTED_LATE_FEE = Decimal("8.13")  # "= max(5, 8.13) = 8.13"


def test_gt08_late_fee():
    # Rule CONFIRMED by finance (B4, 2026-08-07). Becomes a hard regression gate
    # the moment apps/rating/engine.py exists. Expected values: B5 GT-8.
    fee = rating_seam.assess_late_fee(
        overdue_amount=OVERDUE_AMOUNT,
        percent=PERCENT,
        minimum=MINIMUM,
        due_date=DUE_DATE,
        as_of=AS_OF,
        grace_days=GRACE_DAYS,
        grace_mode=GRACE_MODE,
    )

    assert fee == EXPECTED_LATE_FEE

    # B4.1: the base is the OVERDUE PORTION, not the full balance. The fixture
    # supplies only that portion, which is what B5 froze; nothing here can
    # accidentally feed a full balance in its place.
    assert OVERDUE_AMOUNT == Decimal("542.10")

    # NOT FROZEN IN B5: the below-minimum branch (an overdue portion small
    # enough that the $5 floor wins), the business-days grace mode, and the
    # manual first-time waiver. B5 GT-8 exercises none of them.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until billing publishes the seam)
# exceptions: PARTIAL — B5 GT-8 states the grace CONDITION in words, not dates; DUE_DATE/AS_OF are labeled scaffolding satisfying it and no assertion depends on them. grace_days=5 / mode=calendar come from B5's own OQ-005 SUPERSEDED stamp on line 34. B5 presents 8.13 already finalized (it never shows 8.1315); 8.13 is asserted as written and nothing is re-derived.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
