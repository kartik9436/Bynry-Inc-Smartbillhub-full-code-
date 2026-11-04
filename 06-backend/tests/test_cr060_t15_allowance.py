# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 C5 / task T15 — the allowance for doubtful debts. PO ruling
#           2026-09-03, over a recommendation to defer.
# Story:    US-PAY-012 (write-off) · US-LED-005 (the GL designations)
#           Screens: S42 (the close) · S56 (the trial balance) · S71 (the
#           Finance-controls page the switch and the four rates live on)
# Rules:    BR-LED-795 (NEW — the allowance is a standing BALANCE adjusted to a
#           computed target, never an accrual that reverses) · BR-PAY-020
#           (write-off posting — NARROWED, not superseded) · BR-LED-005 (an
#           accrual auto-reverses on day 1 — and this is deliberately NOT one) ·
#           BR-LED-001 (balanced pairs) · CLAUDE.md hard rules 2, 4, 5, 6, 7
# Golden:   NONE. No figure here comes from B4 or B5 and none is edited. The
#           worked example is the PO's own, of 2026-09-03.
# ───────────────────────────────────────────────────────
"""**The two traps the ruling named BEFORE either was built, each with a case.**

════════════════════════════════════════════════════════════════════════════
RED FIRST — every line below is real output, copied off the run
════════════════════════════════════════════════════════════════════════════
Four sabotages, each applied to the shipped code on its own and then reverted,
on real PostgreSQL 16.13. The first two are the traps the PO ruling named BEFORE
either was built.

**1 · TRAP 1 — the write-off keeps charging `6900` beside the estimate**, which
is the arrangement the ruling called out by name::

    E  AssertionError: assert {('1200', 'cr...'948.200000')} == {('1290', 'de...
    E    Left contains 1 more item:  {('6900', 'debit'): Decimal('948.200000')}
    E    Right contains 1 more item: {('1290', 'debit'): Decimal('948.20')}

**2 · TRAP 2 — the estimate posted as an ACCRUAL**, the shape a lane copying
`unpaid_cost_accrual` would write::

    E  AssertionError: the allowance was posted as an ACCRUAL, so the day-1
       sweep will reverse it — an allowance is a BALANCE that stands from month
       to month (BR-LED-795)
    E  assert 'accrual' == 'standard'

**3 · the TARGET posted rather than the MOVEMENT** — a second month would pile
fresh expense on top of what already stands::

    E  AssertionError: assert 'topped_up' == 'released'

**4 · the ageing seam resolving nothing** (hard-won law 2), which is what makes
the substituted-ageing cases above safe to write::

    E  AssertionError: payments_seam.aged_receivable resolved nothing — the
       allowance would be unanswerable for every tenant and every test above
       would still be green
    E  assert None is not None

And before any of this existed, the guard that made the migration necessary
rather than one bare constant: `apps/ledger/selectors.gl_account_for_designation`
refuses a designation the Product Owner has not ruled, so the CHECK on
`ledger_accounts` had to grow first.

════════════════════════════════════════════════════════════════════════════
THE PO's WORKED FIGURES, AND THEY ARE NOT FROZEN ONES
════════════════════════════════════════════════════════════════════════════
    $9,200.00 current   × 1%   =     92.00
    $3,100.00 1–30 days × 5%   =    155.00
    $1,800.00 31–60     × 20%  =    360.00
    $1,233.30 61+       × 50%  =    616.65
    ──────────────────────────────────────
    $15,333.30 owed            = $1,223.65   → expect $14,109.65

Nothing in B4 or B5 is touched. These are held here so a drift in the
arithmetic goes red rather than being absorbed.

════════════════════════════════════════════════════════════════════════════
WHY THE AGEING IS SUBSTITUTED IN THE ARITHMETIC CASES, AND WHERE IT IS NOT
════════════════════════════════════════════════════════════════════════════
Building four ageing bands out of real invoices means four accounts, four bills
and four due dates chosen to land 0, 15, 45 and 100 days late — a fixture whose
own correctness is harder to see than the arithmetic it feeds. So the bands are
substituted at the SEAM for the cases about the FIGURES.

**The seam itself is proved separately and against a real tenant**
(`test_cr060_t15__the_ageing_seam_is_really_wired`), because a substituted read
beside an unwired seam is exactly the dead-UI shape hard-won law 2 exists for:
every arithmetic case would pass over a `payments_seam.aged_receivable` that
resolved nothing.

**And the two POSTING cases substitute nothing** — the write-off ones drive
`writeoffs.approve_write_off` end to end against a real debtor, because the
double count is a fact about two real entries.

════════════════════════════════════════════════════════════════════════════
LAW 14
════════════════════════════════════════════════════════════════════════════
Nothing here catches a database error and continues, so the aborted-transaction
trap does not apply — but these post money inside a transaction and lean on
`uq_journal_entries_posting_key` for the replay, so the file is run on real
PostgreSQL as well as on the default SQLite::

    DATABASE_URL=postgres://... DJANGO_SETTINGS_MODULE=config.settings.local \\
    JOBS_EAGER=false pytest tests/test_cr060_t15_allowance.py --create-db
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.ledger import allowance, chart, manual_je, models as ledger_models, payments_seam
from apps.ledger import selectors as ledger_selectors
from apps.ledger import services as ledger_services
from apps.payments import writeoffs
from apps.payments.collections_models import (
    WRITE_OFF_REASON_UNCOLLECTIBLE,
)
from apps.tenancy import services as tenancy_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
POSTED_AT = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)

#: The four bands the PO was shown, and their four amounts.
CURRENT = Decimal("9200.00")
DAYS_1_30 = Decimal("3100.00")
DAYS_31_60 = Decimal("1800.00")
DAYS_61_PLUS = Decimal("1233.30")

#: What those four add up to, and what they provide for.
OWED = Decimal("15333.30")
ALLOWANCE = Decimal("1223.65")
REALISTICALLY_EXPECT = Decimal("14109.65")

#: US-PAY-012 §4's own debtor, reused: "A-10802 Novak, P.: balance $948.20".
NOVAK = Decimal("948.20")


def _bands(**overrides):
    """The PO's four amounts, over the product's five ageing bands.

    `61-90` and `90+` share `allowance_rate_61_plus`, so the fourth amount sits
    in `61-90` and `90+` is empty — which is also the case that proves the two
    bands really do share one rate.
    """
    buckets = {
        payments_seam.BUCKET_CURRENT: CURRENT,
        payments_seam.BUCKET_1_30: DAYS_1_30,
        payments_seam.BUCKET_31_60: DAYS_31_60,
        payments_seam.BUCKET_61_90: DAYS_61_PLUS,
        payments_seam.BUCKET_90_PLUS: Decimal("0"),
    }
    buckets.update(overrides)
    return payments_seam.AgedReceivable(buckets=buckets, as_of=PERIOD_END, accounts=4)


def _substitute_ageing(monkeypatch, answer):
    monkeypatch.setattr(allowance.payments_seam, "aged_receivable", lambda **_: answer)


def _switch_the_policy_on(actor):
    tenancy_services.save_settings_family(
        actor, "finance-controls", {"allowance_for_doubtful_accounts_enabled": True}
    )


def _balance_of(designation):
    """The net CREDIT balance of the account carrying `designation`."""
    account_id = ledger_selectors.gl_account_id_for_designation(designation)
    if account_id is None:
        return Decimal("0")
    lines = ledger_models.JournalLine.objects.filter(
        ledger_account_id=account_id, journal_entry__status=ledger_models.JE_POSTED
    )
    credits = sum(
        (line.amount for line in lines if line.side == ledger_models.SIDE_CREDIT), Decimal("0")
    )
    debits = sum(
        (line.amount for line in lines if line.side == ledger_models.SIDE_DEBIT), Decimal("0")
    )
    return credits - debits


def _a_debtor(brazos, dana, *, account_no="A-10802", total=NOVAK):
    account = an_account(dana, brazos, account_no=account_no)
    an_issued_bill(
        brazos,
        account,
        number="BL-2605-018100",
        total=total,
        issued_on=date(2026, 5, 16),
        due_date=date(2026, 5, 16),
    )
    return account


def _write_off(actor, account, *, amount=NOVAK, on=date(2026, 8, 15)):
    requested = writeoffs.request_write_off(
        actor,
        account_id=account.pk,
        amount=amount,
        reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        note="120+ days, 3 notices, phone contact failed x4",
        requested_on=on,
    )
    return writeoffs.approve_write_off(
        actor=actor,
        write_off_id=requested.write_off_id,
        approved_on=on,
        posted_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE PO's OWN ARITHMETIC
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t15__the_worked_figures_the_po_was_shown(brazos, dana, monkeypatch):
    """**$15,333.30 owed → $1,223.65 allowance → expect $14,109.65.**

    Every figure in this case is one the Product Owner saw before ruling on
    2026-09-03, and each band is asserted individually so a wrong RATE and a
    wrong TOTAL cannot cancel each other out.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())

        preview = allowance.preview_allowance(period_start=PERIOD_START, period_end=PERIOD_END)

    assert preview.enabled is True
    assert preview.receivable == OWED
    assert preview.target == ALLOWANCE
    assert preview.realistically_expect == REALISTICALLY_EXPECT

    by_bucket = {band.bucket: band for band in preview.bands}
    assert by_bucket[payments_seam.BUCKET_CURRENT].rate == Decimal("0.010000")
    assert by_bucket[payments_seam.BUCKET_CURRENT].provision == Decimal("92.0000")
    assert by_bucket[payments_seam.BUCKET_1_30].rate == Decimal("0.050000")
    assert by_bucket[payments_seam.BUCKET_1_30].provision == Decimal("155.0000")
    assert by_bucket[payments_seam.BUCKET_31_60].rate == Decimal("0.200000")
    assert by_bucket[payments_seam.BUCKET_31_60].provision == Decimal("360.0000")
    assert by_bucket[payments_seam.BUCKET_61_90].rate == Decimal("0.500000")
    assert by_bucket[payments_seam.BUCKET_61_90].provision == Decimal("616.6500")
    # The two oldest bands share ONE rate, because the PO signed four
    # percentages against four amounts.
    assert by_bucket[payments_seam.BUCKET_90_PLUS].rate == Decimal("0.500000")


def test_cr060_t15__the_estimate_posts_dr_bad_debt_cr_allowance(brazos, dana, monkeypatch):
    """The top-up: **DR 6900 Bad debt 1,223.65 / CR 1290 Allowance 1,223.65**.

    Balanced, through the one posting service (hard rule 5), and the accounts
    are resolved BY DESIGNATION — the numbers below are read off the chart, not
    typed into the assertion.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())

        result = allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )

        assert result.created is True
        assert result.direction == allowance.AllowanceResult.TOPPED_UP
        assert result.movement == ALLOWANCE
        assert result.entry_date == PERIOD_END

        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)
        sides = {
            (line.ledger_account.code, line.side): line.amount
            for line in entry.lines.select_related("ledger_account")
        }
        assert sides == {
            ("6900", ledger_models.SIDE_DEBIT): ALLOWANCE,
            ("1290", ledger_models.SIDE_CREDIT): ALLOWANCE,
        }
        assert allowance.standing_allowance(as_of=PERIOD_END) == ALLOWANCE


def test_cr060_t15__a_second_close_of_the_same_month_is_a_replay(brazos, dana, monkeypatch):
    """Hard rule 6. A resumed close pressing the button twice posts once."""
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())

        first = allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )
        second = allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )

        assert first.created is True
        assert second.created is False
        assert second.entry_id == first.entry_id
        assert allowance.standing_allowance(as_of=PERIOD_END) == ALLOWANCE


# ═══════════════════════════════════════════════════════════════════════════
# TRAP 2 — IT IS A BALANCE, NOT AN ACCRUAL
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t15__the_allowance_is_a_balance_and_never_reverses_on_day_one(
    brazos, dana, monkeypatch
):
    """**The trap the ruling named, and every single-month test would miss it.**

    `unpaid_cost_accrual` posts `type=accrual` and
    `manual_je.run_accrual_auto_reversals` mirrors it on the first morning of
    the next period (BR-LED-005). A lane that copied that shape here would zero
    the allowance every month — and a test that only ever looked at ONE month
    would still be green.

    So two assertions, and both are needed: the entry TYPE, and the standing
    balance AFTER the day-1 sweep has run.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())

        result = allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )
        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.type == ledger_models.JE_STANDARD, (
            "the allowance was posted as an ACCRUAL, so the day-1 sweep will reverse it — "
            "an allowance is a BALANCE that stands from month to month (BR-LED-795)"
        )

        manual_je.run_accrual_auto_reversals(
            as_of=date(2026, 8, 1),
            posted_at=datetime(2026, 8, 1, 0, 5, tzinfo=UTC),
            actor=dana,
        )

        standing = allowance.standing_allowance(as_of=date(2026, 8, 31))
        assert standing == ALLOWANCE, (
            f"the allowance was zeroed by the day-1 accrual sweep — it stands at {standing} "
            f"and should still be {ALLOWANCE}. An allowance is a BALANCE and does not reverse"
        )


def test_cr060_t15__a_better_month_RELEASES_the_allowance_and_credits_bad_debt(
    brazos, dana, monkeypatch
):
    """Collectability improves, so expense comes BACK.

    July's target is $1,223.65. August collects the whole 61+ band, so the
    target falls to $607.00 and the close posts the DIFFERENCE the other way
    round: **DR 1290 Allowance 616.65 / CR 6900 Bad debt 616.65**.

    A lane that posted the TARGET rather than the MOVEMENT would put $607.00 of
    fresh expense on top of $1,223.65 already standing, and the balance sheet
    would provide for $1,830.65 against a receivable of $14,100.00.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )
        assert allowance.standing_allowance(as_of=PERIOD_END) == ALLOWANCE

        # August: the oldest band is collected in full.
        _substitute_ageing(monkeypatch, _bands(**{payments_seam.BUCKET_61_90: Decimal("0")}))
        august = allowance.estimate_allowance(
            dana,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            posted_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        )

        assert august.direction == allowance.AllowanceResult.RELEASED
        assert august.target == Decimal("607.0000")
        assert august.movement == Decimal("-616.6500")

        entry = ledger_models.JournalEntry.objects.get(pk=august.entry_id)
        sides = {
            (line.ledger_account.code, line.side): line.amount
            for line in entry.lines.select_related("ledger_account")
        }
        assert sides == {
            ("1290", ledger_models.SIDE_DEBIT): Decimal("616.6500"),
            ("6900", ledger_models.SIDE_CREDIT): Decimal("616.6500"),
        }
        # And the standing balance is the new target, not the sum of two months.
        assert allowance.standing_allowance(as_of=date(2026, 8, 31)) == Decimal("607.0000")


def test_cr060_t15__a_month_that_needs_no_movement_posts_nothing_at_all(
    brazos, dana, monkeypatch
):
    """An entry of 0.00 says nothing and has to be read anyway — and it would
    spend the period's posting key, so a later close could never post the real
    adjustment."""
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )
        before = ledger_models.JournalEntry.objects.count()

        august = allowance.estimate_allowance(
            dana,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            posted_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        )

        assert august.direction == allowance.AllowanceResult.UNCHANGED
        assert august.entry_id is None
        assert ledger_models.JournalEntry.objects.count() == before


# ═══════════════════════════════════════════════════════════════════════════
# TRAP 1 — THE DOUBLE COUNT (DEF-3380's shape, one module over)
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t15__an_estimate_and_a_write_off_never_both_charge_bad_debt(
    brazos, dana, monkeypatch
):
    """**The case the PO ruling asked for by name, and it fails on that exact
    arrangement.**

    With the policy on, the expense is taken ONCE — at the estimate, $1,223.65.
    A $948.20 write-off then CONSUMES the allowance it already paid for:
    `DR 1290 / CR 1200`. If it kept hitting `6900` the books would carry
    $2,171.85 of bad debt for one $948.20 loss that was already provided for.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )

        account = _a_debtor(brazos, dana, account_no="A-10803")
        approved = _write_off(dana, account)
        assert approved.posted_to_ledger is True

        entry = ledger_models.JournalEntry.objects.get(pk=approved.journal_entry_id)
        sides = {
            (line.ledger_account.code, line.side): line.amount
            for line in entry.lines.select_related("ledger_account")
        }
        assert sides == {
            ("1290", ledger_models.SIDE_DEBIT): NOVAK,
            ("1200", ledger_models.SIDE_CREDIT): NOVAK,
        }

        # THE ARITHMETIC, said as arithmetic. Bad debt is charged once.
        charged = -_balance_of(chart.WRITE_OFF)  # an expense carries a DEBIT balance
        assert charged == ALLOWANCE, (
            f"bad debt was charged {charged} across an estimate and a write-off of {NOVAK} "
            f"that provided for it once"
        )
        # And the allowance was consumed by exactly the debt given up.
        assert allowance.standing_allowance() == ALLOWANCE - NOVAK


def test_cr060_t15__with_the_policy_OFF_a_write_off_is_unchanged(brazos, dana):
    """**BR-PAY-020 is NARROWED, not superseded**, and this is the half that did
    not move.

    Off is the seeded default (hard-won law 3), so on the day this landed every
    tenant in the product was here: `DR 6900 Bad debt 948.20 / CR 1200 AR
    948.20`, byte for byte what US-PAY-012 TC-2 has always asserted.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10804")
        approved = _write_off(dana, account)

        entry = ledger_models.JournalEntry.objects.get(pk=approved.journal_entry_id)
        sides = {
            (line.ledger_account.code, line.side): line.amount
            for line in entry.lines.select_related("ledger_account")
        }
        assert sides == {
            ("6900", ledger_models.SIDE_DEBIT): NOVAK,
            ("1200", ledger_models.SIDE_CREDIT): NOVAK,
        }


# ═══════════════════════════════════════════════════════════════════════════
# THE POLICY, THE SEAM, AND THE REFUSALS
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t15__the_policy_is_OFF_until_a_utility_switches_it_on(brazos, dana):
    """Hard-won law 3 — the unsafe option is the one you type.

    And the account is not on the chart either: `chart.py` judgment 3 refused to
    OFFER an accounting policy the product did not implement, and the half of
    that refusal which survives the ruling is that a utility who never books an
    allowance is never offered one.
    """
    with tenant_ctx(brazos):
        assert allowance.policy_is_on() is False
        assert (
            ledger_selectors.gl_account_id_for_designation(chart.ALLOWANCE_DOUBTFUL_ACCOUNTS)
            is None
        )

        preview = allowance.preview_allowance(period_start=PERIOD_START, period_end=PERIOD_END)
        assert preview.enabled is False
        assert preview.target is None
        assert allowance.POLICY_OFF in preview.problems

        with pytest.raises(allowance.AllowanceError) as refusal:
            allowance.estimate_allowance(
                dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
            )
        assert "does not book an allowance" in str(refusal.value)


def test_cr060_t15__switching_it_on_mints_1290_and_nothing_else(brazos, dana, monkeypatch):
    """The account arrives with the policy, and it is NOT finance-signed.

    The PO ruled the POLICY into existence; that is not a finance signature on a
    chart row, which is the same reading `UTILITY_BOOKS_CHART`'s 67 rows carry.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )

        row = ledger_models.LedgerAccount.objects.get(
            designation=chart.ALLOWANCE_DOUBTFUL_ACCOUNTS
        )
        assert row.code == "1290"
        assert row.name == "Allowance for doubtful accounts"
        assert row.type == "asset"
        assert "1290" in chart.PENDING_FINANCE_RE_SIGN_ALLOWANCE

        # Idempotent: a second call changes nothing.
        assert ledger_services.ensure_allowance_account(dana) == str(row.pk)
        assert (
            ledger_models.LedgerAccount.objects.filter(
                designation=chart.ALLOWANCE_DOUBTFUL_ACCOUNTS
            ).count()
            == 1
        )


def test_cr060_t15__an_unreadable_ageing_posts_NOTHING_and_never_releases_to_nil(
    brazos, dana, monkeypatch
):
    """A read that failed must not be priced at zero.

    A target of zero would RELEASE the whole standing allowance and credit bad
    debt for it — in a month somebody signs, on the strength of a seam that was
    unreachable for a minute.
    """
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )

        _substitute_ageing(
            monkeypatch,
            payments_seam.AgedReceivable(
                buckets=None,
                as_of=date(2026, 8, 31),
                problems=(payments_seam.AGED_RECEIVABLE_UNAVAILABLE,),
            ),
        )
        with pytest.raises(allowance.AllowanceError) as refusal:
            allowance.estimate_allowance(
                dana,
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 31),
                posted_at=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
            )

        assert "UNANSWERABLE" in str(refusal.value)
        assert allowance.standing_allowance(as_of=date(2026, 8, 31)) == ALLOWANCE


def test_cr060_t15__the_ageing_seam_is_really_wired(brazos, dana):
    """**Hard-won law 2.** Every arithmetic case above substitutes this read, so
    it would pass over a seam that resolved nothing at all.

    Against a real tenant with one real debtor, the seam must answer with the
    five bands and put $948.20 in one of them.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(brazos, dana, account_no="A-10805")
        answer = payments_seam.aged_receivable(as_of=date(2026, 8, 15))

    assert answer.buckets is not None, (
        "payments_seam.aged_receivable resolved nothing — the allowance would be "
        "unanswerable for every tenant and every test above would still be green"
    )
    assert set(answer.buckets) == set(payments_seam.AGEING_BUCKETS)
    assert answer.total == NOVAK
    assert answer.buckets[payments_seam.BUCKET_90_PLUS] == NOVAK


def test_cr060_t15__one_tenants_allowance_is_invisible_to_another(
    brazos, lonestar, dana, monkeypatch
):
    """Hard rule 1. The standing balance is a tenant-scoped read."""
    with tenant_ctx(brazos):
        _switch_the_policy_on(dana)
        _substitute_ageing(monkeypatch, _bands())
        allowance.estimate_allowance(
            dana, period_start=PERIOD_START, period_end=PERIOD_END, posted_at=POSTED_AT
        )
        assert allowance.standing_allowance() == ALLOWANCE

    with tenant_ctx(lonestar):
        assert allowance.policy_is_on() is False
        assert allowance.standing_allowance() == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# THE DOOR — hard-won law 2, and G52 is what noticed it was missing
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_t15__the_estimate_has_a_door_a_person_can_reach():
    """**`estimate_allowance` declares `@require_role` and for one commit no
    route called it.**

    `G52` caught it — *"each declares @require_role, the code's own statement
    that a person performs it, and no route a person can get to calls it"* —
    and the gate was right. It is the same shape this lane had just spent the
    morning repairing on T6(e), where the settlement posting was reachable only
    with an HTTP client.

    Asserted by RESOLVING the URLs rather than by reading `urlpatterns`: a route
    listed in a module Django never includes is exactly the absence this case
    exists to catch, and the list would still look correct.
    """
    from django.urls import resolve

    for path in ("/api/t/finance/allowance", "/api/t/finance/allowance/post"):
        match = resolve(path)
        assert match is not None, path


def test_cr060_t15__the_preview_answers_a_policy_off_tenant_rather_than_erroring(
    brazos, dana, monkeypatch
):
    """A tenant that does not book an allowance gets a STATE, not a 500.

    The direct write-off is a lawful accounting policy and is what most
    utilities this size will keep, so `enabled: false` with the reason is the
    right answer and an exception would be the wrong one. This drives the view
    function directly — the wire helpers are where a typo would hide, and a
    `preview.as_dict()` that raised would take the whole screen with it.
    """
    from apps.ledger import accruals_api

    with tenant_ctx(brazos):
        served = allowance.preview_allowance(
            period_start=PERIOD_START, period_end=PERIOD_END
        ).as_dict()

    assert served["enabled"] is False
    assert served["target"] is None
    assert allowance.POLICY_OFF in served["problems"]
    # The period is a pair of ISO days, and the standing balance is money on the
    # wire as a STRING — never a JSON number (hard rule 2, one layer out).
    assert served["period"] == ["2026-07-01", "2026-07-31"]
    assert served["standing"] == "0.0000"
    assert accruals_api.allowance_preview is not None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C5 + task T15 (12-governance/11-change-requests.md §7 · §12) ·
#         12-governance/02-decision-log.md 2026-09-03 (the PO ruling and the
#         three reasons for deferring) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-795 (NEW) ·
#         04-docs/05-modules/07-payments/02-business-rules.md BR-PAY-020
#         (NARROWED) · CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · hard-won laws 2,
#         3, 14
# generated: 2026-09-03 by the CR-060 T15 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — four failures quoted verbatim in the module
#        docstring above, including the double count and the day-1 reversal,
#        which are the two traps the ruling named before either was built.
# exceptions: (1) the ARITHMETIC cases substitute the ageing at the seam and the
#        seam is proved separately against a real tenant, for the reason the
#        docstring gives — a fixture of four due dates is harder to check than
#        the arithmetic it feeds, and an unwired seam would make every one of
#        them green · (2) the two POSTING cases substitute nothing and drive
#        `writeoffs.approve_write_off` end to end
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
