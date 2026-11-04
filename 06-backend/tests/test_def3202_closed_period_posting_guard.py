# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-3202 (2026-09-02) — `apps/ledger/posting.py` did NOT refuse a
#           journal entry dated inside a CLOSED fiscal period, while three
#           separate documents said it did: the service's own docstring
#           ("there is no record of which periods are closed" — untrue since
#           US-LED-015 landed `FiscalPeriodClose`), CR-060 §6 ("post() resolves
#           the entry date to an OPEN fiscal period"), and BR-LED-006, which
#           reads as though the lock is enforced at the writer.
#           Hard-won law 1: a comment claiming a guarantee is not the guarantee,
#           and this one was on the SOLE writer of journal lines.
# Story:    US-LED-001 (the posting contract) · US-LED-011 (the S57 manual JE) ·
#           US-LED-015 (month close, the period lock, BR-TEN-038's forward)
#           Screens: S42 · S56 · S57
# Rules:    CLAUDE.md rule 5 (only the posting service writes journal lines —
#           which is exactly why the period lock belongs IN it) · rule 4
#           (financial immutability: nothing written into a closed month can be
#           taken out again) · rule 7 (every money action audits) ·
#           BR-LED-006 (closed periods lock) · BR-LED-017 (an exported period
#           cannot move afterwards) · BR-TEN-038 (a late-dated event forwards to
#           the earliest OPEN period, with audit)
# Ruling:   2026-09-02 (this lane, decision log) — the WRITER REFUSES an
#           unresolved closed-period date; it never forwards on the caller's
#           behalf. Forwarding stays BR-TEN-038's, implemented once in
#           `close.resolve_entry_date`, and the CALLER says which it wanted.
# Tests:    proved RED against the pre-fix service — every `post()` case below
#           POSTED into a closed month instead of raising.
# ───────────────────────────────────────────────────────
"""The month is shut. Prove the books cannot be reopened through the back door.

Every test here answers one question: **after a period is closed, can any money
still land in it?** Before this defect was fixed the answer was yes, through the
one door hard rule 5 says all money must pass through.

The shape of the fix these tests pin:

  * `post()` and `post_draft()` REFUSE a date whose fiscal period is closed.
  * They refuse — they do not quietly move the date. Moving an entry a caller
    dated 31 July into August recognises one month's money in another, and the
    caller is the only layer that knows whether that is right (a late-arriving
    payment: yes, BR-TEN-038; a month-end accrual: never — CR-060 T7's recorded
    judgment of this same morning).
  * A tenant that has closed NOTHING is untouched, including a tenant that has
    never opened Settings → Regional and therefore has no fiscal calendar at
    all. A guard that made those tenants unpostable would be a worse defect
    than the one it fixed.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, manual_je, models, posting, reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    POSTED_AT,
    gl,
    line,
    uuid_for,
)
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CLOSED_ON = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)
AMOUNT = Decimal("68.04")  # CR-060 T7's worked accrual — the entry that found this


def close_july(actor):
    return close.close_period(
        actor,
        period_start=JULY_START,
        period_end=JULY_END,
        closed_at=CLOSED_ON,
        reason="DEF-3202 — the month a test is trying to write into",
    )


def a_pair(tenant, amount=AMOUNT):
    return (
        line(gl(tenant, "1210", "asset"), models.SIDE_DEBIT, amount, source_type="accrual"),
        line(gl(tenant, "4100", "revenue"), models.SIDE_CREDIT, amount, source_type="accrual"),
    )


def a_request(tenant, *, entry_date, key="accrual|DEF-3202|posted"):
    return posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=POSTED_AT,
        currency="USD",
        lines=a_pair(tenant),
        source_type="accrual",
        source_id=uuid_for("DEF-3202"),
        memo="DEF-3202 probe",
    )


# ═══════════════════════════════════════════════════════════════════════════
# The defect itself — post() writing into a closed month
# ═══════════════════════════════════════════════════════════════════════════
def test_def3202__post_refuses_an_entry_dated_inside_a_closed_period(brazos, dana):
    """RED before the fix: this entry POSTED, dated 31 July, inside a closed July.

    BR-LED-006 says a closed period locks and BR-LED-017 lets an ERP receive a
    closed period's figures precisely because they cannot move again. Both were
    promises no code kept.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)

        with pytest.raises(posting.PostingError) as refused:
            posting.post(a_request(brazos, entry_date=JULY_END))

        message = str(refused.value)
        assert "closed" in message.lower()
        assert "2026-07-31" in message  # the date it refused
        assert "2026-08-01" in message  # where BR-TEN-038 would have put it
        assert "resolve_entry_date" in message  # the lawful way forward
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0


def test_def3202__the_closed_month_is_byte_identical_after_the_refusal(brazos, dana):
    """The refusal is atomic: not one row, not one audit line, no partial entry."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)
        before = reporting.trial_balance(start=JULY_START, end=JULY_END)

        with pytest.raises(posting.PostingError):
            posting.post(a_request(brazos, entry_date=date(2026, 7, 15)))

        after = reporting.trial_balance(start=JULY_START, end=JULY_END)
        assert after["rows"] == before["rows"]
        assert after["total_debit"] == before["total_debit"]
        assert after["total_credit"] == before["total_credit"]
        assert models.JournalLine.objects.filter(tenant=brazos).count() == 0


def test_def3202__the_resolved_date_posts_normally(brazos, dana):
    """BR-TEN-038 is not broken by the guard — it is what the caller is told to use.

    The same request, with its date put through `close.resolve_entry_date` first,
    posts into August exactly as LE-9 requires.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        close_july(dana)

        landing, note = close.resolve_entry_date(JULY_END)
        assert landing == AUGUST_START
        assert note["detail"] == "period closed; auto-forwarded"

        result = posting.post(a_request(brazos, entry_date=landing))
        assert result.created is True
        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.entry_date == AUGUST_START
        assert reporting.trial_balance(start=JULY_START, end=JULY_END)["total_debit"] == Decimal(
            "0"
        )
        assert reporting.trial_balance(start=AUGUST_START, end=AUGUST_END)["total_debit"] == AMOUNT


# ═══════════════════════════════════════════════════════════════════════════
# The second door: a draft saved while the month was OPEN, posted after it shut
# ═══════════════════════════════════════════════════════════════════════════
def test_def3202__post_draft_refuses_a_draft_whose_period_closed_while_it_waited(brazos, dana):
    """The hole `save_draft` leaves open, and the reason the guard is at POST.

    A draft is not money in the books (BR-LED-003 — *drafts freely editable*), so
    saving one into any month is lawful. The books move at POST, and between the
    two the month can close. Before the fix the draft posted straight into the
    closed month with its stored date.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        draft = posting.save_draft(
            posting.DraftRequest(
                entry_date=JULY_END,
                currency="USD",
                lines=a_pair(brazos),
                memo="drafted before the close",
                source_type="manual_je",
                source_id=uuid_for("DEF-3202-draft"),
            )
        )
        close_july(dana)

        with pytest.raises(posting.PostingError) as refused:
            posting.post_draft(
                draft.entry_id,
                posted_at=POSTED_AT,
                posting_key="manual_je|DEF-3202-draft|posted",
            )
        assert "closed" in str(refused.value).lower()
        assert models.JournalEntry.objects.get(pk=draft.entry_id).status == models.JE_DRAFT


# ═══════════════════════════════════════════════════════════════════════════
# The S57 flow keeps working — and its own docstring becomes true
# ═══════════════════════════════════════════════════════════════════════════
def test_def3202__a_manual_je_still_forwards_when_the_month_closes_under_it(brazos, dana):
    """US-LED-011 / US-LED-015 TC-5, in the order that actually happens.

    `manual_je` resolved the date at SAVE and its docstring claimed it did so
    *"at SAVE as well as at POST"* — a fourth unproven guarantee. `date_note`
    existed on the post result and nothing ever set it (hard-won law 2, a field
    nothing writes). The clerk is still never blocked: the entry forwards, the
    note says why, and July does not move.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
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
        assert draft.entry_date == date(2026, 7, 20)  # July is still open at SAVE

        close_july(dana)  # …and shuts under the open modal

        posted = manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)
        assert posted.entry_date == AUGUST_START
        assert posted.date_note is not None
        assert posted.date_note["detail"] == "period closed; auto-forwarded"
        assert posted.date_note["requested_date"] == "2026-07-20"
        assert models.JournalEntry.objects.get(pk=draft.entry_id).entry_date == AUGUST_START
        assert reporting.trial_balance(start=JULY_START, end=JULY_END)["total_debit"] == Decimal(
            "0"
        )


# ═══════════════════════════════════════════════════════════════════════════
# The guard must not cost anything to a tenant that has closed nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_def3202__a_tenant_with_no_closed_period_posts_exactly_as_before(brazos, dana):
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        result = posting.post(a_request(brazos, entry_date=JULY_END))
        assert result.created is True
        assert models.JournalEntry.objects.get(pk=result.entry_id).entry_date == JULY_END


def test_def3202__a_tenant_with_no_fiscal_calendar_at_all_still_posts(brazos):
    """The fast path, and it is load-bearing rather than an optimisation.

    `close.period_window` REFUSES when a tenant has no fiscal settings, by
    design. A guard that asked "which period is this date in?" before asking
    "has this tenant closed anything?" would make every brand-new tenant
    unpostable — no bill, no payment, no opening balance — for a rule that cannot
    possibly apply to them.
    """
    with tenant_ctx(brazos):
        result = posting.post(a_request(brazos, entry_date=JULY_END))
        assert result.created is True
