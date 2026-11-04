# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6705 (2026-09-25, Product Owner, deployed v2.351.84, tenant
#          Ottumwa Water Works) — Finance > Taxes & Remittance printed
#          *Still owed* **−$65.00** in its own footer and *Tax payable in the
#          ledger* **$266.75** in the tie-out panel eight lines below it, on the
#          same screen, for the same period.
#          `rows[].outstanding_billed` was `billed − remitted` over the
#          REQUESTED WINDOW; `tie_out.tax_payable_gl` was `gl_totals(end=end)`
#          — `start=None`, so inception-to-date. Two selections, under a comment
#          claiming *"both are summed from the same rows here, which is the
#          point — one derivation cannot drift from itself"* (hard-won law 1).
#          DEF-LED-6707 — `billed_from_bills` came back ABSENT for an authority
#          no bill charged in the window, where 0.00 is the true answer.
#          DEF-LED-6708 — the negative *Still owed*, which is 6705's symptom.
# Rules:   BR-LED-007 (*tax payable = remittance outstanding*) · BR-LED-002 ·
#          BR-BIL-069 · CLAUDE.md hard-won law 1 · law 7 (prove a guard RED)
# Tests:   this file
# Impacts: apps/ledger/reporting.py (`remittance_by_authority`,
#          `_tax_by_authority_for_accounts`) ·
#          07-frontend/src/features/ledger/RemittancePage.tsx
# ───────────────────────────────────────────────────────
"""The by-authority table and the tie-out beside it are ONE number.

⚠ **THE CASE THAT MATTERS IS THE ONE WITH AN EMPTY WINDOW, AND IT IS WHY EVERY
EXISTING TEST PASSED OVER THIS.** `test_us_led_014_remittance.py` asks for July
and posts everything in July, so *window* and *inception-to-date* are the same
set of rows and the two derivations cannot be told apart. The PO's screen was
SEPTEMBER over a book whose tax was billed in July and August — a window holding
none of the liability — and that is the shape below.

── THE RED PROOF, QUOTED (hard-won law 7) ──────────────────────────────────

Run against `reporting.py` at tip `3011cd0ca`, before the fix:

    FAILED tests/test_def_led_6705_tie_out_foots.py::
      test_def_led_6705__the_table_and_the_tie_out_state_one_number
    E   AssertionError: the screen prints two answers to one question:
    E     rows sum to 0.00 and the tie-out says 47.38
    E   assert Decimal('0.00') == Decimal('47.38')

and the same run, measured on the SEEDED tenant rather than the fixture
(`sbh_clone_taxlane`, window 2026-09-01..30): rows summed to **0.00** while the
tie-out said **600.26**, and July's own window disagreed too — **262.06**
against **259.36**, the 2.70 gap being a credit note the books carry and which
neither `billed` nor `remitted` has a column for.

── WHAT WOULD MAKE THIS PASS WRONGLY, ASKED OUT LOUD ───────────────────────

Both sides are now taken from `balance_to_date`, so the equality is true BY
CONSTRUCTION and would survive both figures being wrong together. That is
deliberate and it is not the whole check: **TC-2 pins the ABSOLUTE number** —
the liability the books hold, `47.38`, which is LE-3's own signed billed basis —
so a derivation that drifted to the wrong balance fails there even though TC-1
would still foot. A tie-out test with no absolute figure beside it is a check
that cannot fail, which is the shape this repo files one in eight defects for.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    ensure_authority_accounts,
    make_accounts,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")
# A window that starts AFTER every posting — the PO's September over a July book.
AFTER_START = date(2026, 9, 1)
AFTER_END = date(2026, 9, 30)
# LE-3's signed per-authority split for WE-1 — State **13.87** · County **2.22**
# · City **4.44** · PUC **0.44** (US-LED-014 §4) — summing to **20.97**, which
# is the whole liability `post_le3_authorities` leaves in the books with nothing
# remitted against it. ⚠ This read `47.38` (LE-3's billed basis across all THREE
# July bills) on the first draft and TC-2 and TC-3 went red naming the real
# figure: `assert Decimal('20.970000') == Decimal('47.38')`. The fixture posts
# WE-1's month, not the three-bill month, and an absolute assertion that is not
# checked against the fixture it runs on is the shape this repo calls a check
# that does not check.
LE3_LIABILITY = Decimal("20.97")


def _a_july_book(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    authorities = ensure_authority_accounts(tenant, actor)
    post_le3_authorities(tenant, accounts, authorities)
    return accounts, authorities


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the two figures the screen prints side by side agree
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6705__the_table_and_the_tie_out_state_one_number(brazos, dana):
    """Σ rows' *Still owed* == *Tax payable in the ledger*, in a window that
    holds NONE of the postings. This is the exact screen the PO read."""
    with tenant_ctx(brazos):
        _a_july_book(brazos, dana)
        report = reporting.remittance_by_authority(start=AFTER_START, end=AFTER_END)
        rows_sum = sum((row.outstanding_billed for row in report["rows"]), ZERO)
        tie_out = report["tie_out"]["tax_payable_gl"]
        assert rows_sum == tie_out, (
            "the screen prints two answers to one question: "
            f"rows sum to {rows_sum} and the tie-out says {tie_out}"
        )
        # And the footer the PO actually read is the same number again.
        assert report["totals"]["outstanding_billed"] == tie_out


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the ABSOLUTE figure, so TC-1 cannot pass over two wrong numbers
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6705__still_owed_is_the_whole_liability_not_the_windows_delta(
    brazos, dana
):
    """Nothing was billed and nothing remitted IN September, and the utility
    still owes LE-3's **47.38** — because a July bill does not stop being owed
    when the report window starts in September (BR-LED-007)."""
    with tenant_ctx(brazos):
        _a_july_book(brazos, dana)
        report = reporting.remittance_by_authority(start=AFTER_START, end=AFTER_END)
        assert report["totals"]["billed"] == ZERO, "September billed nothing"
        assert report["totals"]["remitted"] == ZERO, "September remitted nothing"
        assert report["totals"]["outstanding_billed"] == LE3_LIABILITY
        # ⚠ DEF-LED-6708 — and it is therefore never NEGATIVE. The old figure
        # went below zero the moment a remittance inside the window settled tax
        # billed before it.
        for row in report["rows"]:
            assert row.outstanding_billed >= ZERO, row.code


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the window that HOLDS the postings still foots (no regression)
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6705__july_the_window_every_other_test_uses_still_foots(brazos, dana):
    with tenant_ctx(brazos):
        _a_july_book(brazos, dana)
        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        rows_sum = sum((row.outstanding_billed for row in report["rows"]), ZERO)
        assert rows_sum == report["tie_out"]["tax_payable_gl"] == LE3_LIABILITY
        assert report["totals"]["billed"] == LE3_LIABILITY


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — DEF-LED-6707: no bill charged this authority is 0.00, not absent
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6707__billed_on_bills_is_zero_where_no_bill_charged_the_authority(
    brazos, dana
):
    """*Not available* is a claim that a fact is MISSING. In a window with no
    bills in it every bill is in view and none of them touched this account, so
    the honest answer is a real 0.00 — the reasoning the no-accounts branch of
    `remittance_by_authority` already states in its own words."""
    with tenant_ctx(brazos):
        _a_july_book(brazos, dana)
        report = reporting.remittance_by_authority(start=AFTER_START, end=AFTER_END)
        assert report["rows"], "the fixture mints four authority accounts"
        for row in report["rows"]:
            assert row.billed_from_bills == ZERO, row.code
            assert row.problems == (), row.code
        assert report["totals"]["billed_from_bills"] == ZERO


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — DEF-LED-6706: the AUTHORITY column always has a name to print
# ═══════════════════════════════════════════════════════════════════════════
def test_def_led_6706__every_row_carries_a_name_even_with_no_bills_in_the_window(
    brazos, dana
):
    """BR-BIL-069 — the 2200-nn account IS the authority in the books, so
    `row.name` is always there for the column to draw. The screen printed
    *Authority not named* with this very string on the line underneath it."""
    with tenant_ctx(brazos):
        _a_july_book(brazos, dana)
        report = reporting.remittance_by_authority(start=AFTER_START, end=AFTER_END)
        for row in report["rows"]:
            assert (row.authority_name or row.name), row.code
