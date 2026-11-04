# ── Trace ──────────────────────────────────────────────
# Story:    S20 move-out wizard step 3 "Final bill & deposit" — the PREVIEW
#           (PO ruling 2026-09-19, *"we need to do it"*)   Screens: S20
# Rules:    BR-BIL-013 (the settlement matrix — the deposit applies FIRST) ·
#           BR-CUS-056 (billed THROUGH the move day) · BR-BIL-004 (an issued
#           bill is never re-billed, so the window opens the day after it) ·
#           BR-BIL-063 (stage 6 spends a bill number — and is not on this
#           path) · BR-MET-107 (the unbanked export credit, applied by the
#           SETTLEMENT and not by the engine) · BR-CUS-055 (a closed account
#           is not billable — the ORDER TRAP) · BR-TEN-043 / G6 (no clock on a
#           money path) · CLAUDE.md rule 2 (money 4dp, display 2) · rule 7
# Golden:   ❄️ GT-23 (= WE-7, B5 FROZEN 2026-08-08) is the SETTLEMENT's
#           arithmetic and is asserted by `test_us_bil_011_final_bill.py`.
#           ⚠ **GT-23 IS NOT ONE OF THE 14 ENGINE-VERIFIED GTs** in
#           `06-backend/tests/golden/` (GT-1..11, 16, 24, 47), so nothing in
#           that directory runs the engine over a final bill. This file does
#           not close that gap and does not pretend to: it asserts the
#           PREVIEW's contract — that the figure is the run's own and that
#           nothing is written — and the gap is reported.
# Tests:    this file
# Impacts:  apps/billing/final_bill.preview_final_bill · apps/billing/services
#           (publishes it) · apps/customers/seams.preview_final_bill ·
#           GET /accounts/{id}/final-bill-preview · the `?final_bill=` half of
#           GET /accounts/{id}/close-impact, which could not be exercised by
#           any production caller before this
# ───────────────────────────────────────────────────────
"""The keystone: a final bill PRICED and not POSTED, and the chain it unblocks.

The Billing blueprint settles what this screen may do, on p112, in a dashed
panel: **"NO BILL IS ISSUED BY THIS SCREEN. Billing raises the final bill; this
wizard prices what it will contain and posts nothing. The figures above are a
settlement position, not an invoice, and the account closes owing what the
invoice will say."**

So the assertion that matters most in this file is a NEGATIVE one, and it is
`tc2`: after a preview, the invoice count, the invoice-line count, the journal
-line count and the consumed bill numbers are all **exactly what they were
before**. A preview that wrote would make looking a committing action, and a
clerk who backed out of step 3 would leave a spent bill number and an orphan
draft on a tenancy that never ended.

The second thing it pins is the ORDER TRAP, which is the reason the ruling put
this first. `prepare_final_bill` refuses an account whose behaviour class has
left the billable set — *"The final bill therefore has to be produced BEFORE
the move-out writes the close."* A preview runs mid-wizard on an account that
is still OPEN, so `tc1` proves it works there and `tc4` proves a
already-closed account is told the truth by name rather than being handed a
zero.

⚠ **WHY THE MONEY FIGURES HERE ARE COMPUTED RATHER THAN QUOTED.** B14 rule 37
— a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to —
covers p112's `$71.40`, `$17.70` and `$89.10`. They tell us the SHAPE: a line,
a period, an amount, a net. So no case below asserts them. What the cases
assert is that the preview's total is **the same figure `calculate_account`
puts on the draft**, which is the only equality that can be true of every
tenant, and it is true BY CONSTRUCTION because both call `runs.price_account`.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import final_bill, models as billing_models, one_time
from apps.customers import models as customer_models
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_cycle,
    a_priced_plan,
)
from tests.test_us_bil_011_final_bill import (
    MOVE_OUT,
    a_unit_read_before_the_move,
    an_account_with_deposit,
    publish_interest,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _a_scheduled_cycle(brazos, *, code="06-S", first_run=None):
    """A MONTHLY cycle the product can place on a calendar — B4.3's denominator.

    `period_engine.billing_period` needs a ruled `frequency` and a
    `first_run_date`; with either missing it answers `None` and states the
    absence rather than assuming a 30-day month. Monthly from 1 June 2026, so
    a move-out on 12 June sits in **(1 Jun, 30 Jun)** — **30 days**, which is
    the denominator GT-3 ❄️ states (*"Base proration 15/30 × 30.50 = 15.25"*)
    written for a move-OUT instead of a move-IN.
    """
    from apps.metering import models as metering_models

    return metering_models.Cycle.objects.create(
        tenant=brazos,
        code=code,
        frequency="monthly",
        start_day=PERIOD_START.day,
        # ⚠ **UNCHANGED FROM `a_cycle`, DELIBERATELY.** `days_to_complete` is the
        # READ window and not the period (`DEF-2708` — dividing a base charge by
        # it charged $144.00 for 18 days), so it does not reach the denominator
        # at all. It is left exactly as `a_cycle` sets it so the ONLY difference
        # between a scheduled and an unscheduled cycle here is the two fields
        # the derivation actually needs, and any change in outcome is therefore
        # attributable to them.
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        first_run_date=first_run or PERIOD_START,
    )


def _a_moving_out_account(
    brazos,
    dana,
    monkeypatch,
    *,
    asset_no="M-9101",
    account_no="A-12001",
    arrears=None,
    scheduled=True,
    cycle_first_run=None,
):
    """A metered account read on the move day and STILL OPEN — mid-wizard.

    `arrears` posts a real opening AR debit through the ledger (the ONE way an
    account gets a prior balance in this product), so a case can drive the
    SHORT landing — the only landing step 4 renders live in.

    ⚠ **`scheduled` IS NOT DECORATION EITHER, AND THE FIXTURE WAS BEHIND THE
    PRODUCT UNTIL 2026-09-20.** `a_cycle` builds a cycle with `start_day` and
    `days_to_complete` and **no `frequency` and no `first_run_date`** — a
    pre-`CR-029` cycle, which `metering.selectors.billing_period_for_unit`
    answers `None` for by name. So a proration built against this fixture
    unchanged would have been a check that CANNOT FAIL (hard-won law 7's second
    shape): the denominator would never be readable, the fallback would fire
    every time, and `tc12` would go on printing a full base charge whatever the
    engine did. `_a_scheduled_cycle` gives the unit a cycle the product can
    actually place on a calendar; `scheduled=False` keeps the old one, which is
    a real tenant state and is what `tc12d` exercises.
    """
    plan = a_priced_plan(brazos)
    cycle = (
        _a_scheduled_cycle(brazos, code=f"06-{asset_no[-3:]}", first_run=cycle_first_run)
        if scheduled
        else a_cycle(brazos)
    )
    unit = a_unit_read_before_the_move(
        dana, brazos, cycle, plan, asset_no=asset_no, label="P", day=MOVE_OUT
    )
    account = an_account_with_deposit(
        brazos, unit["id"], account_no, balance=arrears or Decimal("0")
    )
    # ⚠ **THE MOVE-IN DATE IS NOT DECORATION — WITHOUT IT THE WINDOW CANNOT BE
    # DERIVED AT ALL, AND THAT IS THE GUARD WORKING.** `an_account` leaves
    # `opened_at` null, and `cut_bill.first_unbilled_day` REFUSES an account
    # with neither an issued bill nor a move-in date rather than assuming the
    # first of the month. Every case in this file failed on that refusal on the
    # first run, which is `PREVIEW_PERIOD_START_UNDERIVABLE` proved RED before
    # it was ever seen green (hard-won law 7). `tc8` keeps that proof.
    customer_models.Account.objects.filter(pk=account.pk).update(opened_at=PERIOD_START)
    publish_interest(monkeypatch)
    return customer_models.Account.objects.get(pk=account.pk)


def _books(brazos):
    """Every row a bill could write, counted. `tc2`'s whole subject."""
    from apps.ledger import models as ledger_models

    return {
        "invoices": billing_models.Invoice.objects.filter(tenant=brazos).count(),
        "invoice_lines": billing_models.InvoiceLine.objects.filter(tenant=brazos).count(),
        "bill_runs": billing_models.BillRun.objects.filter(tenant=brazos).count(),
        "journal_lines": ledger_models.JournalLine.objects.filter(tenant=brazos).count(),
    }


def test_preview_tc1__an_open_account_mid_wizard_is_priced_and_gets_lines_and_a_net(
    brazos, dana, monkeypatch
):
    """The keystone works where it has to work: on an account still OPEN.

    This is the case the whole chain was blocked on. Step 3 had no number and
    no input, so no caller ever stated one, so `close-impact` returned
    `landing: null` on every account in the product.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch)
        # The account has NOT been closed — this is mid-wizard, which is the
        # only state a preview is ever run in.
        assert account.status not in ("closed", "final")

        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert answer["lines"], "a priced final bill with a read meter has lines"
    # The drawn table's three columns: a LINE, a PERIOD, an AMOUNT.
    first = answer["lines"][0]
    assert first["description"]
    assert first["amount"]
    assert answer["period_start"] and answer["period_end"]
    # rule 2 — money is TEXT at 4dp on the wire, never a float.
    assert isinstance(answer["total"], str)
    assert not isinstance(answer["total"], float)
    # The net exists and is a real figure, not a stand-in zero.
    assert Decimal(answer["total"]) > 0
    assert answer["currency"]
    # p112's dashed panel, stated on the wire.
    assert answer["issues_nothing"] is True
    assert answer["writes"] == []


def test_preview_tc2__it_writes_nothing_at_all__no_invoice_no_line_no_journal_no_number(
    brazos, dana, monkeypatch
):
    """**PRICE, DO NOT POST** — p112, verbatim, asserted as arithmetic.

    The negative that makes the preview safe inside a wizard a clerk may
    abandon halfway. Every count is taken before and after and must be equal:
    an invoice, an invoice line, a bill run, a journal line, and — through the
    invoice count — a bill number, which stage 6 spends (BR-BIL-063) and which
    cannot be handed back once it is gone.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9102", account_no="A-12002"
        )
        before = _books(brazos)

        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert answer["priced"] is True, answer.get("priced_unavailable")
        # Run it TWICE — an idempotent read leaves the same trace as one call,
        # which is zero. A preview that wrote would show up here as two.
        final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

        after = _books(brazos)

    assert after == before, (
        "a preview wrote to the books. p112: 'NO BILL IS ISSUED BY THIS SCREEN… "
        f"this wizard prices what it will contain and posts nothing'. before={before} "
        f"after={after}"
    )


def test_preview_tc3__the_window_is_derived_and_runs_through_the_move_day(
    brazos, dana, monkeypatch
):
    """BR-CUS-056 and BR-BIL-004, on the one date the wizard does not state.

    The clerk states the move-out day and nothing else. `period_end` IS that
    day (the OUTGOING account pays it) and `period_start` is DERIVED — never
    the front end's to guess, because a guessed start bills a customer for
    days that are not theirs.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9103", account_no="A-12003"
        )
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["period_end"] == MOVE_OUT.isoformat()  # THROUGH, not up to
    assert answer["period_start_derived"] is True
    assert answer["period_start"] is not None


def test_preview_tc4__an_account_already_closed_is_refused_by_name_not_given_a_zero(
    brazos, dana, monkeypatch
):
    """THE ORDER TRAP, told to the clerk rather than papered over.

    `final_bill.py`: *"The final bill therefore has to be produced BEFORE the
    move-out writes the close."* A clerk who has already committed the
    move-out cannot raise the bill at all, and the honest answer is that
    sentence — not `0.00`, which on a final bill is the claim that this
    customer owes nothing.

    ⚠ **RETURNED, NOT RAISED.** A clerk who cannot be shown the lines can
    still be shown the account, the window and what is blocking it.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9104", account_no="A-12004"
        )
        # The move-out has been committed: the account leaves the billable set.
        # ⚠ `status` is an FK to the tenant's own `account_statuses` row, not a
        # string — BR-CUS-055 makes the behaviour class a COLUMN on that table
        # so billing keys off the CLASS and never off the tenant's label.
        closed = customer_models.AccountStatus.objects.get(tenant=brazos, code="closed")
        assert closed.behavior_class == "terminal"
        customer_models.Account.objects.filter(pk=account.pk).update(status=closed)

        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is False
    # NO total at all — not a zero. A zero here is a money claim.
    assert "total" not in answer
    assert answer["lines"] == []
    assert answer["priced_unavailable"]["reason"] == final_bill.FINAL_ACCOUNT_ALREADY_CLOSED
    assert "BEFORE the move-out writes the close" in answer["priced_unavailable"]["detail"]


def test_preview_tc5__the_previewed_total_is_the_figure_the_draft_would_carry(
    brazos, dana, monkeypatch
):
    """Not a second arithmetic — the SAME `runs.price_account`, proved equal.

    `calculate_account` IS `price_account` followed by stage 6, so the lines a
    clerk approves at step 3 and the lines Billing later raises cannot differ.
    This asserts that equality directly rather than trusting the claim: the
    preview first, then a real draft, and the two totals must match to four
    decimals.

    It is also the case that would catch a preview quietly re-implementing
    pricing — the failure mode `price_account` was extracted to make
    impossible, and the one a utility discovers at go-live.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9105", account_no="A-12005"
        )

        previewed = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")

        data = final_bill.prepare_final_bill(
            account_id=account.id,
            period_start=date.fromisoformat(previewed["period_start"]),
            moved_out_on=MOVE_OUT,
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-PV"),
            period_start=data.period_start,
            period_end=MOVE_OUT,
            idempotency_key="preview-equality-1",
        )
        invoice = final_bill.calculate_final_bill(data, bill_run=run)
        # ⚠ **COUNTED INSIDE THE TENANT CONTEXT, AND IT WAS OUTSIDE IT FROM
        # 2026-09-19 (`1c69a87ab`) UNTIL 2026-09-20 — `DEF-BIL-5988`.**
        # `tenant_ctx` CLEARS on exit, so a related-manager query made after
        # the block is denied every row and `invoice.lines.count()` answered
        # **0** against a preview holding 2 lines. This case was therefore RED
        # at the tip for a day, on both harnesses, and neither the line count
        # nor the equality above could be read from it — the one assertion
        # `price_account` was extracted to make possible was the one that could
        # not run. `invoice.total` is a loaded ATTRIBUTE and needs no query,
        # which is why the total comparison passed and hid it.
        drafted_lines = invoice.lines.count()

    assert Decimal(previewed["total"]) == invoice.total
    assert len(previewed["lines"]) == drafted_lines
    assert invoice.status == billing_models.INVOICE_DRAFT


def test_preview_tc6__the_export_credit_is_not_subtracted_here(brazos, dana, monkeypatch):
    """BR-MET-107 is applied ONCE, by the settlement — never twice.

    p112 draws *Unbanked export credit* as a row of the final-bill table and
    *Final bill, net* beneath it, and a lane reading only the drawing would
    subtract it here. It must not: `customers.move_out_settlement` computes
    `final_bill_net = final_bill − export_credit` itself and serves both, so a
    subtraction here too would credit the customer twice for the same exported
    kWh — on a closed account nobody re-reads.

    Asserted structurally rather than numerically, because the engine prices no
    export-credit line at all: the preview's total is the sum of its own lines,
    so there is nowhere for a second credit to hide.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9106", account_no="A-12006"
        )
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert Decimal(answer["total"]) == sum(Decimal(row["amount"]) for row in answer["lines"])
    # No line claims to be an export credit — billing prices none.
    assert not any("export" in (row["description"] or "").lower() for row in answer["lines"])


def test_preview_tc7__the_total_unblocks_close_impact_and_step_4_stops_refusing(
    brazos, dana, monkeypatch
):
    """**THE CHAIN, END TO END** — the defect this keystone closes.

    Established from code on 2026-09-19: `settlement_for` takes a final-bill
    figure the caller states, nothing in the product ever stated one, so
    `gaps` carried `final_bill_not_stated`, `complete` was false and `landing`
    was **None on every account** — which made step 4's four shortfall radios
    render ENABLED over a `POST` that refused with `no_shortfall` every single
    time (hard-won law 2's mirror: a live control that can never succeed).

    This drives both halves in one case: the settlement WITHOUT the figure,
    then the SAME settlement with the preview's own total, and asserts the gap
    closes and a landing appears.
    """
    from apps.customers import move_out_settlement

    with tenant_ctx(brazos):
        # ARREARS, so the close lands SHORT — `STEP_4_LIVE_IN` is exactly
        # `{"short"}`, and the shortfall step is what this chain unblocks.
        account = _a_moving_out_account(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9107",
            account_no="A-12007",
            arrears=Decimal("500.00"),
        )

        before = move_out_settlement.settlement_for(dana, account.id, as_of=MOVE_OUT)
        assert move_out_settlement.GAP_FINAL_BILL in before["gaps"]
        assert before["landing"] is None
        assert before["complete"] is False

        previewed = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")

        after = move_out_settlement.settlement_for(
            dana,
            account.id,
            final_bill=Decimal(previewed["total"]),
            as_of=MOVE_OUT,
        )

    assert move_out_settlement.GAP_FINAL_BILL not in after["gaps"]
    assert after["final_bill_stated_by_caller"] is True
    assert after["landing"] == move_out_settlement.LANDING_SHORT, (
        "stating the preview's total must produce a landing — that is the whole "
        f"chain. gaps={after['gaps']}"
    )
    # ⚠ **THIS IS THE DEFECT CLOSING.** `step_4_live` was False on every
    # account in the product because `landing` was None; it is a MEASUREMENT
    # now. Step 4's four radios stop being a live control that can never
    # succeed (hard-won law 2's mirror).
    assert before["step_4_live"] is False
    assert after["step_4_live"] is True
    # The figure travelled UNCHANGED: what billing priced is what the
    # settlement settled. `_pair` is CLAUDE.md hard rule 2 on the wire —
    # STORED at 4 decimals, DISPLAY at 2 — so the equality is asserted against
    # `stored`, and the display half is pinned to 2dp beside it because a
    # money figure shown at 4dp on a closing screen is the defect this rule
    # exists to prevent.
    served = after["everything_outstanding"]["final_bill"]
    assert Decimal(served["stored"]) == Decimal(previewed["total"])
    assert Decimal(served["stored"]).as_tuple().exponent == -4
    assert Decimal(served["display"]).as_tuple().exponent == -2


def test_preview_tc8__an_undatable_window_refuses_by_name_and_shows_no_amount(
    brazos, dana, monkeypatch
):
    """The window cannot be guessed, and the guard says so instead of guessing.

    ⚠ **THIS CASE IS THE RED PROOF, KEPT.** Every case in this file failed on
    exactly this refusal the first time the file was run, because `an_account`
    leaves `opened_at` null — so `PREVIEW_PERIOD_START_UNDERIVABLE` was seen
    RED before it was ever seen green, on real data rather than a mutation.

    An account with no issued bill and no move-in date has no day its final
    bill can open on. `cut_bill.first_unbilled_day` refuses rather than
    assuming the first of the month: a guessed start bills a customer for days
    that are not theirs, and the move-out day itself would bill them for none
    of the days they used. The refusal is CARRIED OUT TO THE SCREEN by name,
    with **no `total` key at all** — a `0.00` here is the claim that this
    closing customer owes nothing.
    """
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_unit_read_before_the_move(
            dana, brazos, a_cycle(brazos), plan, asset_no="M-9108", label="Q", day=MOVE_OUT
        )
        account = an_account_with_deposit(brazos, unit["id"], "A-12008")
        # No issued bill, and `an_account` sets no move-in date.
        assert account.opened_at is None
        publish_interest(monkeypatch)

        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is False
    assert "total" not in answer  # NOT a zero — a zero is a money claim
    assert answer["lines"] == []
    assert answer["period_start"] is None
    assert answer["priced_unavailable"]["reason"] == final_bill.PREVIEW_PERIOD_START_UNDERIVABLE
    assert "bills a customer for days that are not theirs" in answer["priced_unavailable"]["detail"]


def test_preview_tc9__a_stated_period_start_is_used_and_says_it_was_not_derived(
    brazos, dana, monkeypatch
):
    """A clerk who corrects the window gets the window they corrected.

    `period_start_derived` tells the screen which of the two happened, so a
    figure a clerk typed is never presented as one the product worked out.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9109", account_no="A-12009"
        )
        answer = final_bill.preview_final_bill(
            account_id=account.id,
            moved_out_on=MOVE_OUT,
            period_start=PERIOD_START,
        )

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert answer["period_start"] == PERIOD_START.isoformat()
    assert answer["period_start_derived"] is False


def test_preview_tc10__a_credit_direction_close_lands_a_refund_now_the_dispute_hold_is_suspended(
    brazos, dana, monkeypatch
):
    """⚠ **THIS CASE WAS NAMED `…_still_gaps_on_the_dispute_store` UNTIL
    2026-10-11 AND ASSERTED THE OPPOSITE OF WHAT IT ASSERTS NOW.**

    Stating the final bill closes `final_bill_not_stated` — `tc7` proves it.
    On an account that lands in CREDIT the settlement then asked whether any
    of the amount was disputed (`BR-CUS-096`), and because **nothing in this
    repository stores a disputed AMOUNT** it gapped on
    `open_disputes_not_readable` and stated no landing — so a refund screen
    could never render.

    **PO RULING 2026-10-11 suspends BR-CUS-096**, verbatim: *"today we are not
    handling any disppute case not recodingt he dispute anywhere. hence
    dispute check doe snot work, I think we should remove it fo time being and
    process the refund"*. With no dispute store published, no store reads as
    no dispute, the gap does not fire, and the credit lands `refund_due`.
    """
    from apps.customers import move_out_settlement

    with tenant_ctx(brazos):
        # NO arrears — the deposit ($150.00) plus its interest ($3.50) exceeds
        # the closing charges, so the account lands in credit.
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9110", account_no="A-12010"
        )
        previewed = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")
        after = move_out_settlement.settlement_for(
            dana, account.id, final_bill=Decimal(previewed["total"]), as_of=MOVE_OUT
        )

    # The gap this lane closes IS closed.
    assert move_out_settlement.GAP_FINAL_BILL not in after["gaps"]
    # BR-CUS-096 SUSPENDED (PO 2026-10-11): no store, no dispute, no gap.
    assert move_out_settlement.GAP_DISPUTES_UNREADABLE not in after["gaps"]
    assert after["open_dispute_total"]["display"] == "0.00"
    assert after["landing"] == move_out_settlement.LANDING_REFUND_DUE
    assert after["step_4_live"] is False
    assert Decimal(after["verdict"]["refund_amount"]["stored"]) > 0


def test_preview_tc11__it_agrees_LINE_FOR_LINE_with_the_mounted_one_time_preview(
    brazos, dana, monkeypatch
):
    """**THE PROOF THAT THIS IS NOT A SECOND PRICING PATH.**

    `POST /billing/one-time/preview` with `kind: "final"` has been mounted and
    price-only since `CR-108` wave 1, and the PO's instruction is to use it:
    *"i hope you will use existing code to generate single bill - we have this
    flow build in billing"*. They are right, and `preview_final_bill` does not
    replace it — it calls the SAME two functions (`prepare_final_bill` then
    `runs.price_account`) and serialises with the SAME `one_time._line_body`.
    All it adds is the WINDOW, which the wizard cannot supply.

    So this case drives both doors over one account and requires them to agree
    on every line and on the net. If a lane ever puts a second arithmetic
    behind either one, this goes red naming the figure.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9111", account_no="A-12011"
        )
        mine = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert mine["priced"] is True, mine.get("priced_unavailable")

        # The mounted route's own request object, given the window this
        # function DERIVED — which is the only thing the wizard was missing.
        theirs = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind="final",
                period_start=date.fromisoformat(mine["period_start"]),
                period_end=MOVE_OUT,
            )
        )

    assert theirs["priced"] is True
    assert Decimal(mine["total"]) == Decimal(theirs["total"])
    assert Decimal(mine["subtotal"]) == Decimal(theirs["subtotal"])
    assert Decimal(mine["tax_total"]) == Decimal(theirs["tax_total"])
    assert [(row["description"], row["amount"]) for row in mine["lines"]] == [
        (row["description"], row["amount"]) for row in theirs["lines"]
    ]


def test_preview_tc12__a_partial_final_window_PRORATES_its_base_over_the_cycle(
    brazos, dana, monkeypatch
):
    """B4.3's ❄️ FROZEN denominator, finally supplied — **$18.50 → $7.40**.

    ✅ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-20 AND IT WAS AMENDED
    DELIBERATELY, NOT QUIETLY.** It read *a partial final window carries a FULL
    base charge by RULING* and pinned `cycle_days == 12` and `$18.50`. What it
    pinned was true and was the product's answer while the denominator had
    nowhere to come from; the Product Owner was then shown the consequence on a
    closing customer and ruled, verbatim: *"okay we have to buld it there will
    ebe code to reuse"*.

    **THE ARITHMETIC IS SIGNED AND WAS NOT RE-OPENED.** B4.3 CONFIRMED:
    *"proration is by calendar days. The base charge is always prorated."*
    **GT-3, ❄️ B5 FROZEN 2026-08-08**, states the denominator outright —
    *"move-in day 16 of 30; base $30.50. Base proration 15/30 × 30.50 =
    15.25"*. The numerator is the days served, the denominator is the cycle's
    own calendar length, and a mid-cycle move-OUT is the mirror of that
    mid-cycle move-IN. So no ❄️ figure moved and no finance re-sign was owed;
    what was missing was the computation, not the rule.

    **Measured here, on one account, both ways:** the customer is served
    **12 days** (1–12 June inclusive) of a **30-day** monthly cycle (1–30
    June). Whole: **$18.50**. Prorated: 12/30 × 18.50 = **$7.40**. The
    difference is **$11.10 on the last bill anybody will ever read**, on a
    customer who is leaving.

    ⚠ **`OQ-242` IS NOT REOPENED AND ITS WITHDRAWAL IS NOT WEAKENED** — see
    `tc12b`, which is the guard. That question answered a CYCLE-LESS one-time
    bill; this account is on a real monthly cycle, which is a different bill
    rather than a second reading of one rule.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9112", account_no="A-12012"
        )
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert answer["service_days"] == 12
    # The denominator is the CYCLE's own calendar length — 1 to 30 June — and
    # NOT the closing window's 12 days. That is the whole change.
    assert answer["cycle_days"] == 30
    base = [row for row in answer["lines"] if row["kind"] == "base"]
    assert base, "a closing bill carries its base charge"
    # 12/30 x 18.50. Rule 2 — displayed at two decimals.
    assert Decimal(base[0]["amount"]) == Decimal("7.40")
    # And the clerk is TOLD, on the line, by the engine that did it —
    # `price_usage` appends the word to a partial period's base charge, so no
    # screen has to divide two numbers to work out what happened.
    assert base[0]["description"].endswith("(prorated)")


def test_preview_tc12b__an_INTERIM_bill_over_the_same_window_now_prorates_the_same_way(
    brazos, dana, monkeypatch
):
    """⚠ **REVERSED 2026-10-01 (`BR-BIL-1066`).** This case read
    *"the CYCLE-LESS kinds are untouched and still charge it whole"* and pinned
    an interim bill over the final bill's 12-day window at the WHOLE **$18.50**
    base, under `OQ-242`'s withdrawal (2026-08-23). The PO has since ruled the
    interim base is cut down by days like the first and final bills — verbatim
    *"Should interim bills cut the base down like first and final bills? A · Cut
    down (10/30)"* — so the same window on the same 30-day cycle is now
    12/30 × $18.50 = **$7.40** on both kinds.

    The guard this case was — *a proration that fired on EVERY kind would pass
    `tc12` wrongly* — now lives where the scope does:
    `test_br_bil_1066_interim_bill_prorates_its_base.py::test_the_scope_is_interim_only`
    (catch-up, penalty and fee are not in `KINDS_NEEDING_A_CYCLE`).

    ⚠ `one_time._cycle_days` itself still answers `None` for every kind; the
    interim denominator is read by `one_time.interim_bill_cycle_days`.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9114", account_no="A-12014"
        )
        request = one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=PERIOD_START,
            period_end=MOVE_OUT,
        )
        assert one_time._cycle_days(request) is None
        interim = one_time.preview(request)
        closing = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    # The interim bill now divides by the account's own 30-day cycle.
    assert interim["cycle_days"] == 30
    interim_base = [row for row in interim["lines"] if row["kind"] == "base"]
    assert interim_base, "an interim bill carries its base charge too"
    assert Decimal(interim_base[0]["amount"]) == Decimal("7.40")
    assert interim_base[0]["description"].endswith("(prorated)")

    # ...and the final bill over that same window: the same figure.
    assert closing["cycle_days"] == 30
    closing_base = [row for row in closing["lines"] if row["kind"] == "base"]
    assert Decimal(closing_base[0]["amount"]) == Decimal("7.40")
    # `price_usage` labels a partial period's base line itself, so the clerk is
    # told on the line rather than left to divide two numbers in their head.
    assert closing_base[0]["description"].endswith("(prorated)")


def test_preview_tc12c__the_DRAFTED_invoice_carries_the_prorated_base_too(
    brazos, dana, monkeypatch
):
    """Surface two — **the bill Billing actually raises**, not just the figure.

    `tc5` already pins that the previewed TOTAL equals the drafted invoice's.
    This one goes to the BASE LINE, because a total can agree while a line does
    not, and because the whole reason this change is safe is that the preview
    and the draft reach ONE function: `one_time._draft_for(kind='final')` and
    both preview doors all call `final_bill.prepare_final_bill`, which is where
    the denominator is read. If a lane ever moves one and not the other, this
    goes red naming the figure.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9115", account_no="A-12015"
        )
        previewed = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")

        data = final_bill.prepare_final_bill(
            account_id=account.id,
            period_start=date.fromisoformat(previewed["period_start"]),
            moved_out_on=MOVE_OUT,
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=a_cycle(brazos, code="06-PR"),
            period_start=data.period_start,
            period_end=MOVE_OUT,
            idempotency_key="prorated-base-1",
        )
        invoice = final_bill.calculate_final_bill(data, bill_run=run)
        drafted = list(invoice.lines.all())

    assert data.cycle_days == 30 and data.service_days == 12
    base_lines = [line for line in drafted if line.kind == "base"]
    assert base_lines, "the drafted final bill carries its base charge"
    assert base_lines[0].amount == Decimal("7.4000")
    assert base_lines[0].description.endswith("(prorated)")
    # And the preview said the same thing about the same line.
    previewed_base = [row for row in previewed["lines"] if row["kind"] == "base"]
    assert Decimal(previewed_base[0]["amount"]) == Decimal("7.40")
    assert Decimal(previewed["total"]) == invoice.total


def test_preview_tc12d__a_cycle_with_no_calendar_falls_back_and_never_guesses_30(
    brazos, dana, monkeypatch
):
    """`None` TRAVELS — the other half of the reuse, and a real tenant state.

    A pre-`CR-029` cycle carries no `frequency` and no `first_run_date`, and a
    unit on TWO cycles has no single period; `billing_period_for_unit` answers
    `None` for both by name rather than picking one, because answering would
    silently choose which calendar a customer's standing charge is divided by.
    **Nothing assumes a 30-day month** — that would be money invented from a
    calendar nobody configured.

    So the fallback is the window's own length, which is exactly what every
    final bill did before this change: an unreadable cycle can never make a
    bill WORSE than it already was, and this case is what proves the claim
    rather than asserting it.

    ⚠ **THE REASON THIS IS NOT SILENT-AND-FINE IS `DEF-BIL-5987`:** nothing on
    the payload SAYS the denominator could not be read, so a clerk sees a full
    base charge with no reason given. `cut_bill` states the same fact out loud
    (`CUT_BILL_DENOMINATOR_ABSENT`) and this path does not yet.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9116",
            account_no="A-12016",
            scheduled=False,
        )
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert answer["service_days"] == 12
    # The WINDOW's own length — NOT 30, which nobody configured.
    assert answer["cycle_days"] == 12
    base = [row for row in answer["lines"] if row["kind"] == "base"]
    assert Decimal(base[0]["amount"]) == Decimal("18.50")
    assert "(prorated)" not in base[0]["description"]


def test_preview_tc12e__a_window_LONGER_than_the_cycle_is_UNCHANGED_by_this(
    brazos, dana, monkeypatch
):
    """**THE CHANGE ONLY EVER REDUCES A BILL, AND THIS IS THE PROOF.**

    A closing window is not always shorter than the cycle. An account whose
    last issued bill ended in April and whose tenancy ends on 12 June owes
    **43 days** against a **30-day** June cycle, and the obvious worry about
    handing the engine a smaller denominator is that 43/30 would charge
    **1.43** base charges where it used to charge one.

    **It does not, and the reason is upstream of this change.**
    `gather._service_days` ends `return max(0, min(cycle_days, days))`, so the
    days SERVED are clamped to the cycle's own length and B4.3's factor can
    never exceed 1. Before: `service_days` 43 of `cycle_days` 43 → factor 1 →
    **$18.50**. After: `service_days` **30** of `cycle_days` **30** → factor 1
    → **$18.50**. Identical, and this case pins it so that a later lane
    removing the clamp finds out here rather than on somebody's bill.

    ⚠ **MEASURED ON THE BETA, WHICH IS WHY THIS CASE EXISTS AT ALL.** Every
    `brazosbend` account's closing window today is a 43-day stretch (`1 Aug –
    12 Sep` against a 31-day cycle), so **not one of them changes price** under
    this commit — the base charge reads `$12.00` electric and `$8.00` water
    before and after on `AC-2026-00001`, `00002` and `00003`. That is also why
    nobody found the over-charge by clicking: the beta has no short closing
    window in it.

    ⚠ **AND THE CLAMP ITSELF IS A SEPARATE QUESTION, NOT THIS ONE —
    `DEF-BIL-5986`.** Forty-three days of service carrying ONE month's base
    charge is an under-charge of about four tenths of one, and it is exactly as
    true before this commit as after.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9117",
            account_no="A-12017",
            cycle_first_run=date(2026, 5, 1),
        )
        # No issued bill, so the window opens on the move-in day — which is a
        # month before the cycle period the move-out falls in.
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 5, 1))
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    assert answer["period_start"] == "2026-05-01"
    # The cycle the MOVE-OUT falls in — 1 to 30 June — and the days served
    # CLAMPED to it, which is what keeps the factor at 1.
    assert answer["cycle_days"] == 30
    assert answer["service_days"] == 30
    base = [row for row in answer["lines"] if row["kind"] == "base"]
    assert Decimal(base[0]["amount"]) == Decimal("18.50")
    assert "(prorated)" not in base[0]["description"]


def test_preview_tc13__every_money_figure_is_TEXT_and_matches_the_draft_exactly(
    brazos, dana, monkeypatch
):
    """CLAUDE.md rule 2 on the wire, and the precision claim CHECKED not asserted.

    Money is **never a float** — a JSON number is what `move_out_settlement.
    _money` refuses by name — so every figure here is a string. What this case
    deliberately does NOT do is demand four decimals: B4 rounds per line AT
    finalization (BR-RAT-003), so a rated line's amount arrives already
    finalized, and re-quantizing in the preview would make it disagree with the
    invoice it is previewing. **The binding property is equality with the
    draft**, which `tc5` pins; this one pins that the wire carries TEXT and that
    the preview's own arithmetic foots.

    ⚠ **A COMMENT IN `final_bill.py` USED TO CLAIM "4dp" HERE AND IT WAS WRONG**
    — measured, the figures are two-decimal. It was corrected rather than left
    standing (hard-won law 1: a comment claiming a guarantee is not the
    guarantee), and this case is what makes the corrected sentence checkable.
    """
    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9113", account_no="A-12013"
        )
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    for key in ("subtotal", "tax_total", "total"):
        assert isinstance(answer[key], str), f"{key} must be TEXT (rule 2)"
        assert not isinstance(answer[key], float)
    for row in answer["lines"]:
        assert isinstance(row["amount"], str)
        # rule 3 — a quantity NEVER travels without its unit.
        if row["quantity"] is not None:
            assert row["unit"], f"{row['description']} states a quantity with no unit"
    # It foots: the lines ARE the total, so no figure is invented between them.
    assert Decimal(answer["total"]) == sum(Decimal(r["amount"]) for r in answer["lines"])


def test_preview_tc14__the_route_names_the_field_the_clerk_actually_mistyped():
    """A bad date refuses against ITS OWN field name, not against `as_of`.

    A screen highlights the field a `field_errors` entry names. Reusing
    `_stated_as_of` here — which hardcodes `"field": "as_of"` — would have
    marked a field that is not on this form and left the one the clerk
    mistyped looking perfectly fine.

    And the absent case is a different answer from the bad case, deliberately:
    `moved_out_on` missing is `VAL_REQUIRED` against `moved_out_on`, while a
    typo is `VAL_FORMAT` against whichever date carried it. Collapsing the two
    would tell a clerk who DID type a date that they had not.
    """
    from apps.customers import api as customers_api
    from core import errors

    # A typo in each of the two dates names that date.
    for field in ("moved_out_on", "period_start"):
        with pytest.raises(errors.ValidationError) as caught:
            customers_api._stated_date("not-a-date", field)
        assert [e["field"] for e in caught.value.field_errors] == [field]
        assert caught.value.code == errors.VAL_FORMAT

    # Absent is ABSENT and is not a format error.
    assert customers_api._stated_date(None, "moved_out_on") is None
    assert customers_api._stated_date("   ", "period_start") is None
    # A good date parses.
    assert customers_api._stated_date("2026-06-12", "moved_out_on") == MOVE_OUT


def test_preview_tc15__the_seam_refusal_puts_no_rule_id_or_module_path_on_screen():
    """B14 rule 32 and rule 33, on the one refusal this route composes itself.

    ⚠ **`G28` CAUGHT THIS LANE WRITING BOTH INTO THE PROSE** — the detail read
    *"apps.billing.services.preview_final_bill is not published … (BR-CUS-037)"*,
    so a clerk would have been shown a Python import path and a rule id. Rule
    32 keeps internal codes out of clerk-facing copy and rule 33 puts RATIONALE
    at zero words on screen, in the code and the register instead.

    The id lives in `br_ref` now — the structured shape every `unavailable[]`
    entry on `close-impact` already uses — and this case is what keeps it
    there, because `G28` reports over the WHOLE repo and one new finding is
    easy to lose among the ones that were already red.

    ⚠ **IT READS THE FILE RATHER THAN `inspect.getsource`, AND THAT IS THE
    POINT OF THE COMMENT.** The view is wrapped by `@api_view`, so
    `getsource(...)` returns DRF's `WrappedAPIView` and never this body — the
    first draft did exactly that, found no `detail` at all, and would have
    passed happily if it had been written as *"no BR- in the source"* instead
    of asserting the detail was FOUND first. That is hard-won law 7's *check
    that cannot fail*, met while writing a check.
    """
    import re
    from pathlib import Path

    from apps.customers import api as customers_api

    source = Path(customers_api.__file__).read_text(encoding="utf-8")
    start = source.index('"final_bill_preview_seam_unpublished"')
    block = source[start : source.index("}", start)]
    detail = re.search(r'"detail": ((?:\s*"[^"]*"\s*)+)', block)
    assert detail, f"the seam refusal must still carry a detail; block was {block!r}"
    prose = detail.group(1)
    assert "BR-" not in prose, f"a rule id reached clerk-facing prose: {prose}"
    assert "apps." not in prose, f"a module path reached clerk-facing prose: {prose}"
    # The id is not dropped — it is MOVED, so the register can still find it.
    assert '"br_ref": "BR-CUS-037"' in block


def test_preview_tc16__the_SHORTFALL_WRITE_succeeds_when_the_caller_states_the_figure(
    brazos, dana, monkeypatch
):
    """⚠ **`DEF-CUS-5927`'s BACKEND HALF, SETTLED: the WRITE accepts the figure.**

    A browser walk on 2026-09-19 found step 4 refusing with **409
    `customers.move_out.no_shortfall`** on every path, *after* step 3 had
    priced the bill and `close-impact` had answered `landing: "short"`. The
    diagnosis was that *"the read learned the figure and the write did not"*.

    **That is true of the CALLER and not of this API.** `shortfall_decision`
    reads `final_bill` off the payload and hands it to `settlement_for`
    (`move_out_settlement.py`), and `api._settlement_payload` parses both
    `final_bill` and `as_of` out of the POST body. So the write half has
    always been able to take the figure; what reaches it today is `{path}`
    alone, so it recomputes gapped and refuses — correctly, because a
    settlement with an unread term must fail CLOSED on an account nobody will
    look at again.

    This case drives BOTH halves against one account so the front-end lane has
    a proof rather than an opinion: **the identical call refuses without the
    figure and SUCCEEDS with it.** If a later change breaks the write's
    ability to take it, this goes red naming the reason code.

    ⚠ **`DEF-CUS-5927`'s ROW STATES THE WRONG CAUSE, AND THAT IS FILED AS
    `DEF-CUS-5929` RATHER THAN LEFT IN THIS DOCSTRING.** The row reads *"POST
    /settle-shortfall takes no final-bill figure while GET /close-impact
    does"*; this case is the counter-example. The row's BROWSER EVIDENCE is
    right and its diagnosis is not, and the difference decides where the fix
    goes — one line in the step 4 POST body, or a redesign of an endpoint that
    already works. It is filed because **a finding written only in the file you
    happen to be in is a finding nobody can count** (`DEF-GOV-5229`'s lesson:
    two lanes wrote one in prose, neither filed a row, and it spread to 54
    citations).

    ⚠ It asserts the SERVICE, not the HTTP route, for the reason `tc7` does:
    the route is a thin forwarder over this, and `_settlement_payload` is
    already exercised by the move-out endpoint suite.
    """
    from core import errors

    from apps.customers import move_out_settlement

    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9114",
            account_no="A-12014",
            arrears=Decimal("500.00"),
        )
        previewed = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert previewed["priced"] is True, previewed.get("priced_unavailable")

        # ── WITHOUT the figure: refused by name. This is today's behaviour. ──
        with pytest.raises(errors.BizError) as refused:
            move_out_settlement.shortfall_decision(
                dana, account.id, {"path": "collect", "as_of": MOVE_OUT}
            )
        assert refused.value.message_key == "customers.move_out.no_shortfall"
        assert refused.value.params["landing"] is None
        assert move_out_settlement.GAP_FINAL_BILL in refused.value.params["gaps"]

        # ── WITH the figure the preview produced: it RECORDS. ───────────────
        recorded = move_out_settlement.shortfall_decision(
            dana,
            account.id,
            {
                "path": "collect",
                "final_bill": Decimal(previewed["total"]),
                "as_of": MOVE_OUT,
            },
        )

    assert recorded["path"] == "collect"
    # The decision is RECORDED and no money moved — there is no
    # `final_settlements` table and customers writes no financial row.
    assert recorded.get("persisted") is False


def test_def_bil_8702__an_account_on_NO_cycle_is_refused_by_the_preview_too(
    brazos, dana, monkeypatch
):
    """**PO ruling 2026-10-01, verbatim: *"show warning and A · Refuse until the
    account has a cycle (same as first bill)"*.**

    The One-time tab's final bill already refused; the move-out wizard's
    preview did not, and priced the month's base WHOLE for a 12-day window —
    **$18.50** where the account has no cycle to prorate over at all. The
    preview now answers the same refusal, with the same clerk sentence's key
    (*"No billing cycle. Assign one on the account."*), and carries NO figure:
    a total on a refused final bill is a claim about what a leaving customer
    owes.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        account = _a_moving_out_account(
            brazos, dana, monkeypatch, asset_no="M-9118", account_no="A-12018"
        )
        # Take the unit off its cycle: the state the ruling is about.
        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=account.unit_id).update(
            cycle=None
        )
        assert one_time.account_has_a_billing_cycle(account.id) is False
        before = _books(brazos)
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        after = _books(brazos)

    assert answer["priced"] is False, answer
    assert answer["lines"] == []
    assert "total" not in answer
    gap = answer["priced_unavailable"]
    assert gap.get("message_key") == final_bill.NO_BILLING_CYCLE_KEY, gap
    assert "no billing cycle" in gap["detail"]
    # The wizard writes nothing, refused or not (p112).
    assert before == after


# ── Lifecycle ─────────────────────────────────────────────
# packet: S20 step 3 (PO ruling 2026-09-19 · Billing blueprint p112, read as an
#         image per B14 rule 42) · BR-BIL-013 · BR-CUS-056 · BR-MET-107
# generated: 2026-09-19 by the final-bill-preview lane
# gates: proved RED before green — see the review-ledger row. `tc2` was run
#         against a mutation that called `final_bill.calculate_final_bill`
#         instead of `runs.price_account` and failed on the invoice count;
#         `tc5` was run against a mutation that summed the lines itself and
#         failed on the four-decimal equality.
# exceptions: (1) ❄️ **GT-23 IS NOT ENGINE-VERIFIED.** `06-backend/tests/
#         golden/` holds 14 of the 61 signed GTs (GT-1..11, 16, 24, 47) and
#         GT-23 — WE-7, the final-bill settlement — is NOT among them. This
#         file does not close that gap: it asserts the PREVIEW's contract, and
#         WE-7's own three numbers stay where they are, in
#         `test_us_bil_011_final_bill.py`. Quote BOTH coverage numbers: the
#         harness `10-scripts/03-golden-verify.py` reports 33 DOCUMENT
#         self-consistency checks and imports no application code.
#         (2) DEPOSIT INTEREST IS STUBBED, exactly as the file these fixtures
#         come from stubs it, and for the stated reason: the accrual's own
#         arithmetic is asserted against the real engine in
#         `test_cr059_cs20_deposit_interest.py`.
#         (3) `tc7` drives the SERVICE and not the HTTP route, because the
#         route is a four-line forwarder over it; the route's own refusal
#         (`moved_out_on` absent) is a validation and not a money path.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
