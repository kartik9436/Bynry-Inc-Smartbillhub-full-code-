# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-015 (month close: checklist, period lock, late-event
#           auto-forward, SysAdmin reopen — TC-1 the checklist, TC-2 the close,
#           TC-3 LE-9's late payment, TC-4 reopen, TC-5 the manual JE dated into
#           a closed month, TC-6 the role gate, TC-7 isolation)
#           Screens: S42 · S36
# Rules:    BR-LED-006 (close per fiscal settings; closed periods lock;
#           late-dated events auto-post forward; SysAdmin reopens; the five-item
#           checklist) · BR-LED-018 (WARN + CONFIRM with an audited reason) ·
#           BR-TEN-038 (auto-post to the earliest OPEN period) · BR-TEN-022
#           (periods computed from fiscal settings) · BR-LED-015 (audit)
# Golden:   LE-9 — July closed Aug 5; an Aug 7 payment dated Jul 30 posts into
#           AUGUST with the note, and July's trial balance is unchanged
# ───────────────────────────────────────────────────────
"""July, put to bed — and the payment that arrives after the door shuts.

LE-9 verbatim: *"July closed Aug 5. Aug 7 a payment arrives dated Jul 30 → posts
into August automatically with an audit note ('period closed; auto-forwarded'),
books stay locked, nothing silently lands in a closed month."*

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_015_tc3__le9_a_late_dated_event_lands_in_august_and_july_is_unmoved`.
Every gate around it — the checklist, the reason, the role — exists so that this
one property holds: **a closed month's totals never move again**, which is what
BR-LED-017 relies on when it lets an ERP receive them.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, manual_je, models, posting, reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_FOOTING,
    POSTED_AT,
    gl,
    line,
    make_accounts,
    post_le1_month,
    uuid_for,
)
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import executive_actor, tenant_ctx

pytestmark = pytest.mark.django_db

# ── LE-9 / US-LED-015 §4, transcribed ──────────────────────────────────────
CLOSED_ON = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)  # "July closed Aug 5"
LATE_PAYMENT_DATE = date(2026, 7, 30)  # "a payment … dated Jul 30"
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)
LATE_PAYMENT = Decimal("64.10")
REOPENED_AT = datetime(2026, 8, 20, 11, 0, tzinfo=dt_timezone.utc)


def july_books(tenant, actor):
    """The LE-1 month, posted through the real posting service (598.69)."""
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def close_july(actor, *, reason="the deposit register is still being matched"):
    return close.close_period(
        actor,
        period_start=JULY_START,
        period_end=JULY_END,
        closed_at=CLOSED_ON,
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the checklist computes from registers, and says what it cannot see
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc1__the_checklist_is_five_computed_items(brazos, dana):
    """US-LED-015 TC-1: *"Five computed items with live states"* — and three of
    them are honest about not being computable.

    BR-LED-006's five are *runs issued · batches reconciled · bank rec current ·
    accruals posted · remittance recorded*. Two are the ledger's own and really
    compute. The other three live in billing and payments, **which publish no
    read**, so they report `unknown` with the callable they want NAMED rather
    than showing a green tick nobody derived (hard-won law 1). An `unknown` item
    counts as incomplete, so the close still happens and demands a reason.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)

        checklist = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        states = {item.code: item.state for item in checklist["items"]}
        assert set(states) == set(close.CHECKLIST_ITEMS)

        assert states[close.ITEM_RUNS_ISSUED] == close.STATE_UNKNOWN
        # ⚠ SUPERSEDED 2026-09-01 (CR-059 CS-13). This line read STATE_UNKNOWN
        # until the two payments reads were published. It was not asserting a
        # RULE — it was pinning the absence of a caller: `batches_reconciled`
        # answered `unknown` because nothing could count, and BR-LED-006 always
        # wanted a count. This tenant has cut no batches, so nothing is
        # outstanding and the item is COMPLETE. The zero is real and measured,
        # not a zero standing in for "I don't know" (DEF-127) — the pair of
        # tests that prove the two apart is test_cr059_cs13_close_counts.py
        # TC-5 / TC-5b.
        assert states[close.ITEM_BATCHES_RECONCILED] == close.STATE_COMPLETE
        # `bank_rec_current` stays UNKNOWN and that is the honest answer: bank
        # lines exist only inside an imported statement, and none overlaps this
        # window, so the read returns None rather than 0. A month the bank was
        # never asked about must not go green.
        assert states[close.ITEM_BANK_REC_CURRENT] == close.STATE_UNKNOWN
        # No accrual is overdue and no remittance is owed on a month whose only
        # tax liability was billed in it.
        assert states[close.ITEM_ACCRUALS_POSTED] == close.STATE_COMPLETE

        runs = next(i for i in checklist["items"] if i.code == close.ITEM_RUNS_ISSUED)
        assert runs.wanted_reads == (
            "apps.billing.selectors.unissued_run_count(start, end) -> int",
        )
        assert checklist["ready"] is False
        assert checklist["closed"] is False
        # ⚠ AMENDED 2026-09-24. This asserted that the checklist CARRIED
        # `close_role_gate_is_a_reading_not_a_ruling`. The PO ruled the close gate
        # that day ("system admin and clark", BR-LED-006 amended), the marker is
        # retired, and the assertion is INVERTED rather than deleted: a marker put
        # back on a ruled gate is the rot this pins shut.
        assert checklist["unavailable"] == ()


def test_us_led_015_tc1b__an_overdue_accrual_is_an_incomplete_item(brazos, dana):
    """The one checklist item the ledger owns outright, doing real work.

    An accrual dated in JUNE whose Jul 1 mirror never posted is a double-count
    sitting in July's revenue, and closing July over it is exactly what
    BR-LED-006's *accruals posted* line exists to stop. The same question
    `manual_je.pending_accrual_reversals` asks, so the checklist and the sweep
    can never disagree.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        draft = manual_je.save_manual_je(
            dana,
            entry_date=date(2026, 6, 30),
            entry_type=models.JE_ACCRUAL,
            memo="Accrue June unbilled revenue",
            lines=(
                manual_je.ManualLine(
                    ledger_account_id=gl(brazos, "1210", "asset").id,
                    side=models.SIDE_DEBIT,
                    amount=Decimal("500.00"),
                ),
                manual_je.ManualLine(
                    ledger_account_id=gl(brazos, "4100", "revenue").id,
                    side=models.SIDE_CREDIT,
                    amount=Decimal("500.00"),
                ),
            ),
        )
        manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)

        checklist = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        accruals = next(
            i for i in checklist["items"] if i.code == close.ITEM_ACCRUALS_POSTED
        )
        assert accruals.state == close.STATE_INCOMPLETE
        assert "no auto-reversal" in accruals.detail

        # And it CLEARS once the sweep runs — the item is a live register read,
        # not a checkbox.
        manual_je.run_accrual_auto_reversals(as_of=date(2026, 7, 1), posted_at=POSTED_AT)
        after = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        assert next(
            i for i in after["items"] if i.code == close.ITEM_ACCRUALS_POSTED
        ).state == close.STATE_COMPLETE


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — WARN + CONFIRM (BR-LED-018)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc2__an_incomplete_checklist_warns_then_closes_with_a_reason(
    brazos, dana, audit_rows
):
    """BR-LED-018 verbatim: *"incomplete checklist items listed, Finance may
    close anyway with reason (audited) — never a silent close, never a hard
    lockout."*

    Both halves, in order. Without a reason the close is REFUSED and the refusal
    NAMES every incomplete item — that is the WARN. With one, it closes and the
    incomplete items are snapshotted beside the reason, which is J19 step 1's
    *"reason + incomplete-item snapshot recorded on the close"*.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)

        with pytest.raises(close.CloseError) as warn:
            close.close_period(
                dana, period_start=JULY_START, period_end=JULY_END, closed_at=CLOSED_ON
            )
        message = str(warn.value)
        assert "not complete" in message
        assert "runs_issued (unknown)" in message
        assert "never a silent close, never a hard lockout" in message
        assert close.is_period_closed(JULY_START, JULY_END) is False

        result = close_july(dana)
        assert result["status"] == models.PERIOD_CLOSED
        assert close.is_period_closed(JULY_START, JULY_END) is True

        row = models.FiscalPeriodClose.objects.get(tenant=brazos, period_start=JULY_START)
        assert row.close_reason == "the deposit register is still being matched"
        # ⚠ `ITEM_BATCHES_RECONCILED` DROPPED FROM THIS SET 2026-09-01
        # (CR-059 CS-13): it is no longer incomplete, because it can now be
        # counted and the count is zero. The other two are still incomplete for
        # their own reasons and are still asserted.
        assert {item["code"] for item in row.incomplete_items} >= {
            close.ITEM_RUNS_ISSUED,
            close.ITEM_BANK_REC_CURRENT,
        }
        assert close.ITEM_BATCHES_RECONCILED not in {
            item["code"] for item in row.incomplete_items
        }

        closed = [r for r in audit_rows if r["action"] == "period.closed"]
        assert closed and closed[-1]["after"]["reason"] == row.close_reason
        assert closed[-1]["after"]["period_start"] == "2026-07-01"


def test_us_led_015_tc2b__closing_a_closed_period_twice_is_refused(brazos, dana):
    """A second close would overwrite the FIRST close's reason and snapshot,
    which is the record J19 step 1 asks for."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)
        with pytest.raises(close.CloseError) as exc:
            close_july(dana)
        assert "already closed" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — LE-9 (THE TEST THIS FILE EXISTS FOR)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc3__le9_a_late_dated_event_lands_in_august_and_july_is_unmoved(
    brazos, dana
):
    """LE-9 / J19 step 2 / T5-09, end to end.

    July's trial balance is captured BEFORE the close (**598.69 = 598.69**, the
    ❄️ frozen LE-1 footing), a Jul 30-dated event arrives after it, and July is
    read again. The assertion is that the two are identical — *"July TB
    byte-identical to step 1"* — while August carries the money.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)

        # The ❄️ LE-1 footing is over the WHOLE book: its opening-balance entry
        # is dated at the 2026-06-30 cutover, deliberately before the month, so a
        # July-windowed read is 553.69 and the book is 598.69. Both are asserted
        # — the frozen figure, and the window this test then freezes.
        whole = reporting.trial_balance()
        assert whole["total_debit"] == LE1_FOOTING == whole["total_credit"]
        before = reporting.trial_balance(start=JULY_START, end=JULY_END)
        assert before["total_debit"] == before["total_credit"]

        close_july(dana)

        # BR-TEN-038: the date the books will accept, and why it moved.
        landing, note = close.resolve_entry_date(LATE_PAYMENT_DATE)
        assert landing == AUGUST_START
        assert note["detail"] == "period closed; auto-forwarded"
        assert note["requested_date"] == "2026-07-30"
        assert note["posted_period"] == ["2026-08-01", "2026-08-31"]

        cash = gl(brazos, "1010", "asset")
        ar = gl(brazos, "1200", "asset")
        posting.post(
            posting.PostingRequest(
                posting_key="payment|LATE-1|cleared",
                entry_date=landing,
                posted_at=POSTED_AT,
                currency="USD",
                lines=(
                    line(cash, models.SIDE_DEBIT, LATE_PAYMENT, source_type="payment"),
                    line(ar, models.SIDE_CREDIT, LATE_PAYMENT, source_type="payment"),
                ),
                source_type="payment",
                source_id=uuid_for("LATE-1"),
                audit_context={"auto_forwarded": note},
            )
        )

        after = reporting.trial_balance(start=JULY_START, end=JULY_END)
        assert after["total_debit"] == before["total_debit"]  # 598.69, unmoved
        assert after["total_credit"] == before["total_credit"]
        assert after["rows"] == before["rows"]

        august = reporting.trial_balance(start=AUGUST_START, end=AUGUST_END)
        assert august["total_debit"] == LATE_PAYMENT == august["total_credit"]


def test_us_led_015_tc5__a_manual_je_dated_into_a_closed_month_forwards(brazos, dana):
    """US-LED-015 TC-5: *"A manual JE (US-LED-011) dated into closed July …
    auto-forward + audit note; no rejection-with-data-loss, no closed-period
    write."*

    The clerk is never blocked from recording reality — only from rewriting the
    closed month. The forwarded date is visible on the DRAFT, before the modal
    is confirmed, rather than discovered afterwards.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)

        draft = manual_je.save_manual_je(
            dana,
            entry_date=date(2026, 7, 20),
            entry_type=models.JE_STANDARD,
            memo="Reclass July card fees",
            lines=(
                manual_je.ManualLine(
                    ledger_account_id=gl(brazos, "6800", "expense").id,
                    side=models.SIDE_DEBIT,
                    amount=Decimal("205.00"),
                ),
                manual_je.ManualLine(
                    ledger_account_id=gl(brazos, "1000", "asset").id,
                    side=models.SIDE_CREDIT,
                    amount=Decimal("205.00"),
                ),
            ),
        )
        assert draft.entry_date == AUGUST_START
        assert draft.date_note["detail"] == "period closed; auto-forwarded"

        manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)
        assert models.JournalEntry.objects.get(pk=draft.entry_id).entry_date == AUGUST_START
        assert reporting.trial_balance(start=JULY_START, end=JULY_END)["total_debit"] == Decimal(
            "0"
        )


def test_us_led_015_tc3b__an_open_period_never_moves_a_date(brazos, dana):
    """The overwhelmingly common case, asserted so the forward cannot creep: a
    date whose period is OPEN comes back exactly as a human typed it."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        landing, note = close.resolve_entry_date(LATE_PAYMENT_DATE)
        assert landing == LATE_PAYMENT_DATE
        assert note is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — reopen is System Admin only, TC-6 — the close role gate
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc4__only_a_system_admin_reopens_and_a_reason_is_required(
    brazos, dana, marcus, audit_rows
):
    """US-LED-015 TC-4: *"System Admin only; confirm + reason; audit
    `period.reopened`; the period accepts postings again."*

    This is the ONE role gate in the close that is separately ruled rather than
    read across from OQ-175 — BR-LED-006 and BR-TEN-038 both name the System
    Admin — so a Billing Clerk who may CLOSE a month may not REOPEN one.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)

        from core import errors

        with pytest.raises(errors.AuthError):
            close.reopen_period(
                marcus,
                period_start=JULY_START,
                period_end=JULY_END,
                reopened_at=REOPENED_AT,
                reason="the batch was matched after all",
            )
        with pytest.raises(close.CloseError) as exc:
            close.reopen_period(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                reopened_at=REOPENED_AT,
                reason="  ",
            )
        assert "needs a REASON" in str(exc.value)

        close.reopen_period(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            reopened_at=REOPENED_AT,
            reason="the batch was matched after all",
        )
        assert close.is_period_closed(JULY_START, JULY_END) is False
        # The period accepts postings again — the date stops moving.
        assert close.resolve_entry_date(LATE_PAYMENT_DATE) == (LATE_PAYMENT_DATE, None)
        assert "period.reopened" in {row["action"] for row in audit_rows}


def test_us_led_015_tc6__an_executive_may_not_close(brazos, dana):
    """US-LED-015 TC-6: *"Close attempted by Staff role → Refused server-side."*

    In this product's vocabulary that is the EXECUTIVE — an executive reads the
    books, a clerk closes them. ⚠ **This said the gate was "flagged on every
    result as a READING of OQ-175" until 2026-09-24, when the PO RULED it.** The
    ratified statement is pinned whole by
    `test_us_led_015_br_led_006_ratified__who_closes_and_who_reopens`.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        from core import errors

        with pytest.raises(errors.AuthError):
            close.close_period(
                executive_actor(),
                period_start=JULY_START,
                period_end=JULY_END,
                closed_at=CLOSED_ON,
                reason="anything",
            )
        assert close.is_period_closed(JULY_START, JULY_END) is False


def test_us_led_015_tc6b__a_billing_clerk_may_close(brazos, dana, marcus):
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        result = close_july(marcus)
        assert result["status"] == models.PERIOD_CLOSED


# ═══════════════════════════════════════════════════════════════════════════
# BR-LED-006 as RATIFIED 2026-09-24 — the whole signed statement, in one place
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_br_led_006_ratified__who_closes_and_who_reopens(
    brazos, dana, marcus, audit_rows
):
    """**The 2026-09-24 ruling, pinned so drift goes RED.**

    CLAUDE.md's sign-off rule has two parts and this is the second: *"a test
    asserts the ratified figure so drift goes RED"*. The behaviour was already
    correct — this test exists because until 2026-09-24 it was correct by
    READING, and a reading is a thing a later lane may reasonably change. It is
    now signed law and may not move without a re-sign.

    PO ruling 2026-09-24, verbatim, both halves:

        CLOSE  — *"system admin and clark"*
        REOPEN — *"yes correct - Reopening a month  System Admin only — signed
                  as BR-LED-006, in the code, with a reason required and
                  audited"*

    In plain English: **a clerk closes the month; only an admin can unwind one,
    and they must say why.**

    ⚠ **THE LAST TWO ASSERTIONS ARE THE RETIREMENT, AND THEY GUARD IT IN BOTH
    DIRECTIONS.** `close_role_gate_is_a_reading_not_a_ruling` came off every
    result the day the reading became a ruling — but three period-end accrual
    modules used to ALIAS that constant, and posting a depreciation entry was
    never put to the PO. Clearing their flag along with the close's would have
    been an absence no check in this repo can see (DEF-CUS-3653). So: nothing
    flags the close, and the accrual carry is still flagged.

    ⚠ **TC-4 and TC-6 are NOT redundant with this.** They assert BEHAVIOUR under
    a story; this asserts the RULING, cites the words it was given in, and is the
    row a reviewer reads. Deleting either would leave the other looking complete.
    """
    from core import errors

    from apps.ledger import close as close_mod
    from apps.ledger import depreciation, unbilled_accrual, unpaid_cost_accrual

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        july_books(brazos, dana)

        # ── CLOSE — "system admin and clark" ──────────────────────────────
        # An executive is neither, and is refused at the service.
        with pytest.raises(errors.AuthError):
            close.close_period(
                executive_actor(),
                period_start=JULY_START,
                period_end=JULY_END,
                closed_at=CLOSED_ON,
                reason="an executive reads the books",
            )
        assert close.is_period_closed(JULY_START, JULY_END) is False

        # "clark" — the Billing Clerk closes. This is the half that was a
        # reading for six weeks and is now the ruling.
        closed = close_july(marcus)
        assert closed["status"] == models.PERIOD_CLOSED
        assert close.is_period_closed(JULY_START, JULY_END) is True
        # Nothing on a close describes the gate any more.
        assert closed["unavailable"] == ()
        assert close.close_checklist(
            period_start=JULY_START, period_end=JULY_END
        )["unavailable"] == ()

        # ── REOPEN — "System Admin only … with a reason required and audited"
        # The clerk who just closed it may NOT reopen it. That asymmetry is the
        # whole point of putting the second half back to the PO.
        with pytest.raises(errors.AuthError):
            close.reopen_period(
                marcus,
                period_start=JULY_START,
                period_end=JULY_END,
                reopened_at=REOPENED_AT,
                reason="I closed it, so I may open it",
            )
        with pytest.raises(errors.AuthError):
            close.reopen_period(
                executive_actor(),
                period_start=JULY_START,
                period_end=JULY_END,
                reopened_at=REOPENED_AT,
                reason="anything",
            )
        assert close.is_period_closed(JULY_START, JULY_END) is True

        # "a reason required" — a blank one is refused even from the admin.
        with pytest.raises(close.CloseError) as blank:
            close.reopen_period(
                dana,
                period_start=JULY_START,
                period_end=JULY_END,
                reopened_at=REOPENED_AT,
                reason="   ",
            )
        assert "needs a REASON" in str(blank.value)
        assert close.is_period_closed(JULY_START, JULY_END) is True

        # The System Admin, with a reason, reopens — "and audited".
        close.reopen_period(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            reopened_at=REOPENED_AT,
            reason="the deposit batch was matched after all",
        )
        assert close.is_period_closed(JULY_START, JULY_END) is False
        assert "period.reopened" in {row["action"] for row in audit_rows}

    # ── THE RETIREMENT, GUARDED BOTH WAYS ─────────────────────────────────
    # The close's marker is gone, by NAME: a constant put back under any name
    # would still have to carry this code to reach a screen.
    assert not hasattr(close_mod, "ROLE_GATE_IS_A_READING"), (
        "the close role gate is RULED (PO 2026-09-24) — a reading marker on it "
        "is the rot CLAUDE.md hard rule 4 names"
    )
    # …and the neighbours nobody asked the PO about are STILL flagged.
    accrual_code = close_mod.ACCRUAL_ROLE_GATE_IS_A_READING["code"]
    assert accrual_code == "accrual_posting_role_gate_is_a_reading_not_a_ruling"
    for module in (depreciation, unbilled_accrual, unpaid_cost_accrual):
        assert module.ROLE_GATE_IS_A_READING["code"] == accrual_code, (
            f"{module.__name__} must keep its own unratified flag — posting an "
            "accrual was never put to the PO"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_015_tc7__each_tenants_close_is_its_own(brazos, dana, lonestar, erin):
    """US-LED-015 TC-7: *"Lone Star Ridge closes ITS July → Brazos Bend's period
    state untouched; each tenant's close is its own (RLS)."*"""
    with tenant_ctx(lonestar):
        with_monthly_fiscal_year(erin)
        close_july(erin)
        assert close.is_period_closed(JULY_START, JULY_END) is True

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        assert close.is_period_closed(JULY_START, JULY_END) is False
        assert close.closed_periods() == ()
        # And a Brazos Bend July-dated entry is NOT forwarded by Lone Star's close.
        assert close.resolve_entry_date(LATE_PAYMENT_DATE) == (LATE_PAYMENT_DATE, None)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-015@0007led (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-015 §1-§8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-006/015/018 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-9 + LE-1 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 1-2 + T5-09)
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(no API half in this lane) E=deferred(no frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST — with the WARN+CONFIRM reason check removed, an
#         incomplete July closed SILENTLY and TC-2's first assertion did not
#         raise; with `resolve_entry_date` returning its argument, LE-9's Jul 30
#         payment landed in July and the ❄️ 598.69 footing MOVED
# exceptions: three of five checklist items report `unknown` because billing and
#         payments publish no register read — asserted here as `unknown` rather
#         than papered over, so the day a read lands this test goes red and is
#         corrected deliberately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
