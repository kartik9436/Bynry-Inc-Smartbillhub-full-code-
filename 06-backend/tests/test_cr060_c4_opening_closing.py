# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-008 (S56 trial balance) — CR-060 **C4**, task **T9**
# Rules:    BR-LED-009 (trial balance) · BR-LED-007 (drift is a red flag, never
#           a silent fix) · BR-REP-001 (every money group labels its date basis)
#           · BR-REP-002 (read models over journal-line dimensions) ·
#           CLAUDE.md rule 2 (money on the wire is the exact decimal STRING)
# ───────────────────────────────────────────────────────
"""CR-060 C4 — **opening · movement · closing** on the trial balance.

The change request's own words for why: *"Every accountant reads a trial
balance as position-then-movement-then-position; without the opening column they
cannot tie this month to last month's signed statement without exporting."*

**NO SIGNED FIGURE MOVES HERE AND THAT IS ASSERTED RATHER THAN ASSUMED.** Every
number below is LE-1's own — the same fixture `test_us_led_ledger_api.py` foots
at **598.69 = 598.69** with AR at **152.32** — read through three different
windows. The July footing is re-asserted in this file precisely so a change to
the opening column that moved the movement columns would be caught HERE rather
than in a screen test that never adds anything up.

**C4's two proofs, in the CR's own wording:**

  * *"Opening + movement = closing, per account and in total."*
  * *"opening on a fresh chart is ZERO, not null."*

**AND ONE THIS FILE ADDS, BECAUSE IT IS THE DEFECT THE COLUMN CREATES.**
`gl_totals` buckets the lines INSIDE the window, so an account that held money
on the 1st and did not move all month has always been correctly absent — it has
no movement to show. The moment there is an OPENING column, absent stops meaning
*"no activity"* and starts meaning *"this account holds nothing"*, which is a
claim about a balance. `test_an_untouched_account_still_appears_with_its_balance`
is the case: asked for AUGUST, over books whose every entry is dated July, the
report must still list the accounts and carry their positions across.

⚠ **PROVED RED FIRST (hard-won law 7).** Run against `reporting.trial_balance`
before the C4 change, every case in this file failed on the same line and with
the same message — verbatim:

    KeyError: 'opening'

and the totals case on:

    KeyError: 'total_opening'
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import api as ledger_api
from apps.ledger import reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_FOOTING,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: LE-1's whole month is dated inside July; the last entries land on the 31st.
LAST_DAY = JULY_END
#: A window that starts after every LE-1 entry — the "quiet month" case.
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def call(tenant, **query):
    return api_call(
        ledger_api.trial_balance,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query=query or None,
    )


def row_for(body, code):
    return next(row for row in body["rows"] if row["code"] == code)


# ═══════════════════════════════════════════════════════════════════════════
# C4 proof 1 — opening + movement = closing, per account AND in total
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c4__opening_plus_movement_equals_closing_on_every_row(brazos, dana):
    """Asked for LE-1's LAST DAY, so the opening column carries real money.

    July 1st, 15th, 20th and 25th are before the window; the 31st is inside it.
    So this is the only shape that exercises the arithmetic in both directions
    at once — a non-zero opening AND a non-zero movement on the same rows.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(brazos, **{"from": LAST_DAY.isoformat(), "to": LAST_DAY.isoformat()}).data

        assert body["rows"], "a day LE-1 posts on cannot produce an empty trial balance"
        for row in body["rows"]:
            opening = Decimal(row["opening"])
            movement = Decimal(row["debit"]) - Decimal(row["credit"])
            closing = Decimal(row["closing"])
            assert opening + movement == closing, (
                f"{row['code']} {row['name']}: {opening} + {movement} != {closing} — "
                "the one identity a bookkeeper uses this column for"
            )

        total_opening = Decimal(body["total_opening"])
        total_closing = Decimal(body["total_closing"])
        movement_total = Decimal(body["total_debit"]) - Decimal(body["total_credit"])
        assert total_opening + movement_total == total_closing


def test_cr060_c4__the_closing_position_is_the_whole_month_position(brazos, dana):
    """The last day's CLOSING equals the cumulative trial balance's own figure.

    This is the tie-out the column exists for, expressed as a test: the AR row
    closes July at LE-1's signed **152.32**, whichever window you ask for. A
    closing column that did not agree with the cumulative report would be a
    second derivation of the same position (BR-REP-002).
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        last_day = call(brazos, **{"from": LAST_DAY.isoformat(), "to": LAST_DAY.isoformat()}).data
        cumulative = call(brazos, **{"to": LAST_DAY.isoformat()}).data

        assert Decimal(row_for(last_day, "1200")["closing"]) == LE1_AR == Decimal("152.32")
        assert Decimal(row_for(cumulative, "1200")["debit"]) == LE1_AR
        for row in cumulative["rows"]:
            movement = Decimal(row["debit"]) - Decimal(row["credit"])
            assert Decimal(row["closing"]) == movement, (
                f"{row['code']}: a cumulative report's closing IS its movement, "
                "because nothing precedes the beginning of the books"
            )


# ═══════════════════════════════════════════════════════════════════════════
# C4 proof 2 — "opening on a fresh chart is ZERO, not null"
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c4__opening_is_zero_and_never_null(brazos, dana):
    """The CUMULATIVE forms: nothing precedes the beginning of the books.

    A `null` here would reach `MoneyCell` and print as *Not available* beside a
    figure the books can state perfectly well — a position of nothing. The
    cumulative form (no `from`) has nothing before it at all, so every opening
    is a real, derived **0.00**.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        for window in ({}, {"to": JULY_END.isoformat()}):
            body = call(brazos, **window).data
            assert body["total_opening"] == "0.000000", window
            for row in body["rows"]:
                assert row["opening"] is not None, (row["code"], window)
                assert Decimal(row["opening"]) == Decimal("0"), (row["code"], window)


def test_cr060_c4__julys_opening_is_the_june_cutover_and_not_zero(brazos, dana):
    """⚠ **THIS CASE WAS WRONG WHEN IT WAS FIRST WRITTEN, AND THE CODE WAS
    RIGHT — WHICH IS THE FACT WORTH PINNING.**

    The first draft asserted that July's own window opened at zero *"because
    July is the first month LE-1 posts"*. It is not: `ledger_le_fixtures`
    carries a **CUTOVER on 2026-06-30**, so the AR account opens July holding
    **45.00** of migrated balance and the read model said so.

    That is the whole argument for the column in one number. Before C4 the July
    trial balance showed AR's July MOVEMENT and a bookkeeper had no way to see
    the 45.00 that came in from the old system; now the opening column states
    it, the closing column carries it forward, and the two tie to the cumulative
    report. **A test that had "passed" by forcing this to zero would have hidden
    a real migrated balance behind a green tick.**

    `total_opening` is still 0.00 — the cutover posted a balanced pair, so the
    positions square across the whole book. That is the squareness proof, and it
    is a different statement from *"no account held anything"*.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(brazos, **{"from": JULY_START.isoformat(), "to": JULY_END.isoformat()}).data

        assert Decimal(row_for(body, "1200")["opening"]) == Decimal("45.00")
        assert body["total_opening"] == "0.000000"
        for row in body["rows"]:
            assert row["opening"] is not None, row["code"]
            assert Decimal(row["opening"]) + (
                Decimal(row["debit"]) - Decimal(row["credit"])
            ) == Decimal(row["closing"]), row["code"]


def test_cr060_c4__july_still_foots_at_the_signed_figure(brazos, dana):
    """LE-1's ❄️ footing, re-asserted through the changed function.

    598.69 = 598.69, AR 152.32. The opening column adds a position; it must not
    add, remove or re-net a single cent of movement, and this is the case that
    would go red if it did.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(brazos, **{"to": JULY_END.isoformat()}).data

        assert body["total_debit"] == str(LE1_FOOTING.quantize(Decimal("0.000001")))
        assert body["total_debit"] == "598.690000"
        assert body["total_credit"] == "598.690000"
        assert body["balanced"] is True
        assert body["difference"] == "0.000000"
        assert row_for(body, "1200")["debit"] == "152.320000"


# ═══════════════════════════════════════════════════════════════════════════
# The defect the column CREATES — an account that held money and did not move
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c4__an_untouched_account_still_appears_with_its_balance(brazos, dana):
    """August, over books whose every entry is dated July.

    Before C4 an empty answer here was correct: nothing moved in August. With an
    opening column an empty answer says *the books hold nothing*, which is false
    for every account LE-1 left carrying a position. So the row set is the UNION
    of moved-in-window and open-at-window-start, and the movement columns read
    0.00 on the half that did not move.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(brazos, **{"from": AUGUST_START.isoformat(), "to": AUGUST_END.isoformat()}).data

        assert body["rows"], (
            "every account LE-1 left with a balance carries it into August — an empty "
            "August trial balance would state that the books hold nothing"
        )
        ar = row_for(body, "1200")
        assert Decimal(ar["opening"]) == LE1_AR
        assert Decimal(ar["closing"]) == LE1_AR
        assert ar["debit"] == "0.000000"
        assert ar["credit"] == "0.000000"
        # Positions net to nothing across a balanced book, which is what makes
        # the opening total meaningful: it is not a footing, it is a proof that
        # last month closed square.
        assert Decimal(body["total_opening"]) == Decimal("0")
        assert Decimal(body["total_closing"]) == Decimal("0")
        # The currency survives a window with no movement in it — read off the
        # opening slice, because there is no other slice to read.
        assert body["currency"] == brazos.currency
        # Ordered by code, opening-only rows included, so the table reads as ONE
        # table (a block of untouched accounts at the bottom is a second one).
        codes = [row["code"] for row in body["rows"]]
        assert codes == sorted(codes)


def test_cr060_c4__the_read_model_answers_before_the_wire_does(brazos, dana):
    """The same two figures straight off `reporting.trial_balance`.

    Asserted here as well as through the endpoint because `wire.py` could serve
    a correct number the read model never computed, or drop one it did — and
    the wire test above cannot tell those apart.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        result = reporting.trial_balance(start=AUGUST_START, end=AUGUST_END)
        ar = next(row for row in result["rows"] if row["code"] == "1200")
        assert ar["opening"] == LE1_AR
        assert ar["closing"] == LE1_AR
        assert isinstance(ar["opening"], Decimal), "money leaves this module as a Decimal"
        assert result["total_opening"] == Decimal("0")
        assert result["total_closing"] == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-008@cr060-c4 (12-governance/11-change-requests.md CR-060 C4 + task T9 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-009/007 · tests/ledger_le_fixtures.py LE-1)
# generated: 2026-09-02 by the CR-060 finance-screens lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST (law 7) — every case failed on `KeyError: 'opening'` / `KeyError: 'total_opening'` against the unchanged read model, quoted in the module docstring above
# exceptions: (1) the opening query is a SECOND scan of the whole pre-window book on every request — bounded by the chart rather than by transaction volume in its OUTPUT, but not in its INPUT, so a tenant with millions of lines pays for it. Reported here rather than optimised: CR-060 T8 is the indexing task and this is the read it would serve · (2) `total_opening` and `total_closing` are Σ over SIGNED positions, so they are 0.00 on a balanced book and are a squareness proof rather than a footing — they are deliberately NOT compared against `total_debit`/`total_credit`, which foot the MOVEMENT
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
