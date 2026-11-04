# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C17 / task T7b — accrue unpaid supplier costs at close.
#           Screens: S42 (the close checklist this completes)
# Rules:    BR-LED-792 (how unpaid supplier cost is measured — NEW 2026-09-02) ·
#           BR-LED-006 (the close checklist, AMENDED the same day to a SEVENTH
#           item) · BR-LED-005 (the day-1 auto-reversal) · BR-LED-028 (capture
#           creates no payable — untouched, and this accrual creates none
#           either) · BR-LED-025 (nothing over 2 dp posts) · BR-TEN-038 (a
#           closed period is never posted into) · CLAUDE.md rules 1-7
# Golden:   LE-11's nine July purchases, $51,902.50 — every amount transcribed
#           from the workbook by `tests/cost_of_service_fixtures.py` and none
#           computed here. LE-4's accrual/mirror shape.
# ───────────────────────────────────────────────────────
"""The supplier cost July incurred and had not paid, put into July's books.

════════════════════════════════════════════════════════════════════════════
THE WORKED FIGURE THIS FILE PINS — the one a reviewer signs (CR-060 T19)
════════════════════════════════════════════════════════════════════════════
Brazos Bend bought **$51,902.50** of water, power, gas, materials and meters in
July (LE-11, nine invoices) and had paid none of it when July closed.

  * **The accrual, dated 31 July.** One entry, five debit lines — one per COST
    ACCOUNT, not one per invoice:

        DR 5100 Purchased power        28,222.00
        DR 5110 Purchased water         3,100.00
        DR 5140 Purchased gas           6,235.00
        DR 5200 Operations & maint.     1,845.50
        DR 5300 Infrastructure         12,500.00
        CR 2100 Accrued expenses                   51,902.50

  * **And it undoes itself.** On 1 August the existing auto-reversal sweep posts
    the mirror and `2100` nets **0.00** — which is why this is not the payable
    the PO refused in 2026-08-16's sitting.

  * **THE ONE THAT MATTERS: a cost is never counted twice.** CI-1 is
    **$1,240.00** of bulk water. Paid **4 August** and July closed after it: the
    invoice is accrued into July (unpaid AS AT 31 July), reversed on 1 August,
    and settled on 4 August — so **July's 5110 carries 1,240.00, August's
    carries 0.00, and the utility is charged for that water exactly once, in the
    month it sold it.** Paid **28 July** instead — inside the period — the
    settlement is already in July's books, so the accrual EXCLUDES it by name
    and the July figure is **50,662.50**, not 53,142.50.

Every case below is one sentence of that paragraph, or one of the things the
accrual deliberately refuses to do.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE GREEN — THREE GUARDS, EACH MEASURED, NO LIVE FILE MUTATED
════════════════════════════════════════════════════════════════════════════
Every sabotage below was applied through `monkeypatch`, so no shipped file was
edited to produce a failure (DEF-3101's discipline). The failures are quoted as
they were seen, not as they were expected:

  **1 · The double-count guard removed.** Dropping clause 3 of BR-LED-792 — the
  `paid_on IS NULL OR paid_on > period_end` filter — and accruing July with CI-1
  settled on 28 July put **1,240.00 into 5110 twice**: the settlement entry and
  the accrual, in the same month, on the same invoice. Measured:
  `AssertionError: 5110 in July = 4340.00, expected 3100.00`. That is DEF-3343's
  own arithmetic ("an ERP handed 4,340.00 of purchased water against 3,100.00
  bought") arriving from the other side of the books, which is why the guard has
  its own case and its own count on the preview.

  **2 · The period-scoped posting key replaced with a per-press one.** Pressing
  *Post accrual* twice then produced TWO entries and `2100` read
  **103,805.00** instead of **51,902.50** — the utility owing its suppliers
  twice. Measured: `AssertionError: assert Decimal('103805.00') ==
  Decimal('51902.50')`.

  **3 · The entry type changed from `accrual` to `standard`.** The existing
  day-1 sweep then found nothing to reverse, `2100` stood at **51,902.50** on 1
  August and every month after, and the accrual became exactly the undrainable
  payable BR-LED-028 forbids. Measured: `AssertionError: assert 0 == 1` on the
  mirror count, then `2100` still at 51,902.50 after the sweep.

════════════════════════════════════════════════════════════════════════════
POSTGRESQL, BECAUSE SQLITE CANNOT SHOW THE FAILURE THAT MATTERS
════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard-won law 14. The accrual posts inside one transaction alongside a
chart top-up that may insert an account, and the replay guard leans on
`uq_journal_entries_posting_key`; SQLite has no aborted-transaction state, so a
green run there is not by itself the proof.

**RUN, AND MEASURED: 11 passed on PostgreSQL 16 with a database built from every
migration (`--create-db`), the same eleven that pass on the SQLite suite.** The
command, verbatim:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://... SBH_TEST_DB_NAME=test_sbh_cr060b \\
    JOBS_EAGER=false pytest tests/test_cr060_t7b_unpaid_cost_accrual.py --create-db

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT TOUCH
════════════════════════════════════════════════════════════════════════════
**No ❄️ frozen figure moves.** LE-11's nine invoices carry no `paid_on` in the
fixture and this file sets one only on rows it has captured in its own test
database. B4 and B5 are not opened. The register total **51,902.50** is
transcribed by the fixture and asserted here, never recomputed.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import (
    chart,
    close,
    cost_capture,
    manual_je,
    models as ledger_models,
    posting,
    selectors,
    services as ledger_services,
    unpaid_cost_accrual,
)

from tests.cost_of_service_fixtures import (
    AUGUST_END,
    AUGUST_START,
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

# ── the worked month, transcribed ──────────────────────────────────────────
#: BR-TEN-043 — the caller names the moment, so a retried post stamps one.
POSTED_AT = datetime(2026, 8, 3, 9, 0, tzinfo=dt_timezone.utc)
REVERSED_AT = datetime(2026, 8, 3, 9, 5, tzinfo=dt_timezone.utc)
SETTLED_AT = datetime(2026, 8, 4, 10, 30, tzinfo=dt_timezone.utc)
SEPTEMBER_START = date(2026, 9, 1)

#: CI-1, LE-11's first bulk-water invoice.
CI1 = "RS-2607-0141"
CI1_AMOUNT = Decimal("1240.00")

#: Paid INSIDE July — the settlement lands in July's books, so accruing it too
#: would charge the same water twice in the same month.
PAID_IN_JULY = date(2026, 7, 28)
#: Paid AFTER July — the ordinary case, and the whole point of C17.
PAID_IN_AUGUST = date(2026, 8, 4)

#: LE-11's five cost accounts and what each holds, transcribed from
#: `LE14_COST_ROWS` in the fixture rather than re-derived here.
EXPECTED_DEBITS = {
    "5100": Decimal("28222.00"),
    "5110": Decimal("3100.00"),
    "5140": Decimal("6235.00"),
    "5200": Decimal("1845.50"),
    "5300": Decimal("12500.00"),
}

#: With CI-1 settled INSIDE July, the accrual is the register total less that
#: invoice: 51,902.50 − 1,240.00.
ACCRUAL_WITHOUT_CI1 = Decimal("50662.50")


def brazos_ready(tenant, actor=None):
    """The LE-11 preconditions — a fiscal calendar and the five services sold."""
    admin = (
        actor
        if getattr(actor, "role", None) == "system_admin"
        else staff_actor(tenant, "system_admin", f"setup-{tenant.subdomain}@brazosbendutilities.test")
    )
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    return admin


def _sides(entry):
    """`{(code, side): amount}` for one posted entry."""
    out = {}
    for line in entry.lines.select_related("ledger_account"):
        out[(line.ledger_account.code, line.side)] = line.amount
    return out


def _net_debit(code, *, upto):
    """One account's NET debit across every posted entry dated on or before
    `upto` — which is what a trial balance column IS, and the only honest way to
    ask *"how much cost is in the books for this month?"*."""
    total = Decimal("0")
    for line in ledger_models.JournalLine.objects.filter(
        journal_entry__status=ledger_models.JE_POSTED,
        journal_entry__entry_date__lte=upto,
        ledger_account__code=code,
    ).values_list("side", "amount"):
        side, amount = line
        total += amount if side == ledger_models.SIDE_DEBIT else -amount
    return total


def _accrued_account_code():
    account = selectors.gl_account_for_designation(chart.ACCRUED_EXPENSES)
    return account.code if account is not None else None


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the entry itself: five debits, one credit, 51,902.50 each way
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc1__july_unpaid_cost_accrues_by_cost_account(brazos, marcus, audit_rows):
    """**One entry dated 31 July: DR the five cost accounts 51,902.50 / CR
    accrued supplier costs 51,902.50** — and NO account payable is created that
    survives the next morning.

    The lines are per COST ACCOUNT and not per invoice (BR-LED-792): nine debit
    lines for nine invoices would put the supplier register into the general
    ledger, and `5110` is one figure a finance officer reads.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)
        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()
        audit_rows.clear()

        result = unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)
        sides = _sides(entry)
        accrued_code = _accrued_account_code()

    assert result.created is True
    assert result.entry_date == JULY_END
    assert result.total == LE11_REGISTER_TOTAL

    for code, amount in EXPECTED_DEBITS.items():
        assert sides[(code, ledger_models.SIDE_DEBIT)] == amount
    assert sides[(accrued_code, ledger_models.SIDE_CREDIT)] == LE11_REGISTER_TOTAL
    # Five debits and one credit. Nine invoices, six lines.
    assert len(sides) == len(EXPECTED_DEBITS) + 1
    assert result.line_count == len(EXPECTED_DEBITS) + 1

    # Balanced to the cent, which is what "balanced" means (hard rule 5).
    debits = sum(a for (_, s), a in sides.items() if s == ledger_models.SIDE_DEBIT)
    credits = sum(a for (_, s), a in sides.items() if s == ledger_models.SIDE_CREDIT)
    assert debits == credits == LE11_REGISTER_TOTAL

    # It went through the ONE posting service (hard rule 5) — nothing else could
    # have written it, because ledger/0004 refuses an insert unless posting.py
    # opens the write window.
    assert entry.posting_key.split("|")[0] == unpaid_cost_accrual.SOURCE_UNPAID_COST_ACCRUAL
    assert entry.posting_key.split("|")[-1] == "accrued"
    assert entry.status == ledger_models.JE_POSTED
    # The TYPE is what makes the day-1 mirror happen. See TC-2.
    assert entry.type == ledger_models.JE_ACCRUAL

    # Hard rule 7 — a money action writes `audit_log`, INSIDE the transaction,
    # and the accrual's own context rides the posting service's row rather than
    # a second row of its own (one writer, one trail).
    trail = [
        row
        for row in audit_rows
        if (row.get("after") or {}).get("action") == "unpaid_cost_accrual"
    ]
    assert len(trail) == 1
    assert trail[0]["after"]["total"] == str(LE11_REGISTER_TOTAL)
    assert trail[0]["after"]["cost_account_lines"] == len(EXPECTED_DEBITS)
    assert trail[0]["entity_type"] == "journal_entry"


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — it undoes itself, so no payable is ever carried (BR-LED-005)
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc2__the_accrual_reverses_on_day_one_and_carries_no_payable(brazos, marcus):
    """The EXISTING sweep posts the mirror on 1 August and `2100` nets **0.00**.

    This is the whole answer to the PO's objection of 2026-08-16: posting
    `CR accounts payable` at capture would leave **$37,200.00** standing after a
    year of purchases already settled by cheque. This liability lives for one
    period end and is gone the next morning, by a rule that was already written
    and is not re-implemented here (hard-won law 5, one source).
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)
        unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        accrued_code = _accrued_account_code()
        # At the period end the liability is real and is the whole figure.
        assert _net_debit(accrued_code, upto=JULY_END) == -LE11_REGISTER_TOTAL

        swept = manual_je.run_accrual_auto_reversals(
            as_of=AUGUST_START, posted_at=REVERSED_AT, actor=None
        )
        after = _net_debit(accrued_code, upto=AUGUST_END)
        cost_after = sum(
            (_net_debit(code, upto=AUGUST_END) for code in EXPECTED_DEBITS), Decimal("0")
        )

    # One accrual considered, one mirror posted — and it is the SWEEP's, keyed
    # `journal_entry|<accrual id>|auto_reversed`. This module writes no reversal.
    assert len(swept) == 1
    assert after == Decimal("0")
    # And the cost went with it: the accrual is a period-matching device, not a
    # second charge. August carries nothing from it.
    assert cost_after == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — THE DOUBLE COUNT. Settled INSIDE the period is excluded, and counted.
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc3__an_invoice_settled_inside_the_period_is_excluded_and_counted(
    brazos, marcus
):
    """CI-1 paid **28 July** puts `DR 5110 / CR cash 1,240.00` in JULY's books,
    so accruing it as well would charge the same water twice in the same month.

    BR-LED-792 clause 3. The exclusion is COUNTED
    (`settled_within_the_period`), never silent: a clerk who expected nine
    invoices and sees eight needs the reason, not a smaller number.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        preview = unpaid_cost_accrual.preview_unpaid_costs(
            period_start=JULY_START, period_end=JULY_END
        )
        result = unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        water_in_july = _net_debit("5110", upto=JULY_END)

    assert preview.excluded.get("settled_within_the_period") == 1
    assert preview.invoice_rows_total == 8
    assert result.total == ACCRUAL_WITHOUT_CI1
    assert LE11_REGISTER_TOTAL - CI1_AMOUNT == ACCRUAL_WITHOUT_CI1

    # THE ARITHMETIC THAT MATTERS: July's purchased water is what was BOUGHT,
    # 3,100.00 — the settlement's 1,240.00 plus the accrual's remaining 1,860.00
    # — and NOT 4,340.00, which is what a missing clause 3 produces and what
    # DEF-3343 measured on the export side of the same books.
    assert water_in_july == EXPECTED_DEBITS["5110"]


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — settling AFTERWARDS posts ONCE, not twice (C17's own proof sentence)
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc4__accrual_then_settlement_never_double_counts(brazos, marcus):
    """CI-1 bought 6 July, accrued 31 July, reversed 1 August, **paid 4 August**.

    July's 5110 carries the cost; August's carries **0.00**; the utility is
    charged once, in the month it sold the water. This is C17's *"the accrual and
    the settlement together never double-count the cost, which is the failure
    this pairing exists to prevent"*, measured.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)

        unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        july_water = _net_debit("5110", upto=JULY_END)

        manual_je.run_accrual_auto_reversals(
            as_of=AUGUST_START, posted_at=REVERSED_AT, actor=None
        )
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_AUGUST, settled_at=SETTLED_AT
        )
        cumulative_water = _net_debit("5110", upto=AUGUST_END)
        august_only = cumulative_water - july_water

    # July holds every gallon bought in July — the month the water was sold.
    assert july_water == EXPECTED_DEBITS["5110"]
    # August's own movement is the reversal (−3,100.00) plus CI-1's settlement
    # (+1,240.00) = −1,860.00, so the CUMULATIVE cost is 1,240.00: exactly the
    # invoice that has actually been paid, once.
    assert august_only == CI1_AMOUNT - EXPECTED_DEBITS["5110"]
    assert cumulative_water == CI1_AMOUNT


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — pressing the button twice is a REPLAY, not a second liability
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc5__a_second_press_is_a_replay_no_op(brazos, marcus):
    """Hard rule 6. `created=False` with the same entry id — a RESULT, not an
    exception, because a resumed close pressing the button twice is correct."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)
        first = unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        second = unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        accrued_code = _accrued_account_code()
        standing = _net_debit(accrued_code, upto=JULY_END)
        entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type=unpaid_cost_accrual.SOURCE_UNPAID_COST_ACCRUAL
        ).count()

    assert second.created is False
    assert second.entry_id == first.entry_id
    assert entries == 1
    # The utility owes its suppliers 51,902.50, not 103,805.00.
    assert standing == -LE11_REGISTER_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — a CLOSED period is refused BY NAME, and stays byte-identical
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc6__a_closed_period_is_refused_not_forwarded(brazos, marcus):
    """BR-TEN-038 forwards a late-dated event; an accrual must NOT be forwarded.

    Forwarded into August it would recognise July's cost in August and reverse it
    in September — two months wrong in a signed book, to avoid saying no.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)
        close.close_period(
            marcus,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="LE-9: July closed on the 5th with the checklist incomplete.",
        )
        before = ledger_models.JournalLine.objects.filter(
            journal_entry__entry_date__lte=JULY_END
        ).count()

        with pytest.raises(unpaid_cost_accrual.UnpaidCostAccrualError) as refusal:
            unpaid_cost_accrual.accrue_unpaid_costs(
                marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
            )
        after = ledger_models.JournalLine.objects.filter(
            journal_entry__entry_date__lte=JULY_END
        ).count()

    text = str(refusal.value)
    assert "CLOSED" in text
    assert "Reopen the period" in text
    # C17's proof: the closed period is untouched.
    assert before == after


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the SEVENTH close-checklist item (BR-LED-006, amended)
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc7__the_checklist_gains_a_seventh_item_that_can_be_completed(
    brazos, marcus
):
    """It reads INCOMPLETE with the figure while cost is unrecognised, and
    COMPLETE once the accrual stands — and COMPLETE, not red forever, when there
    is nothing to accrue."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)

        # Nothing captured at all: complete, because there is nothing to accrue.
        empty = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        empty_item = next(
            item for item in empty["items"] if item.code == close.ITEM_UNPAID_COST_ACCRUAL
        )

        capture_le11_month(marcus)
        before = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        before_item = next(
            item for item in before["items"] if item.code == close.ITEM_UNPAID_COST_ACCRUAL
        )

        unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        after = close.close_checklist(period_start=JULY_START, period_end=JULY_END)
        after_item = next(
            item for item in after["items"] if item.code == close.ITEM_UNPAID_COST_ACCRUAL
        )

    assert len(before["items"]) == 7
    assert close.ITEM_UNPAID_COST_ACCRUAL in close.CHECKLIST_ITEMS
    assert empty_item.state == close.STATE_COMPLETE
    assert before_item.state == close.STATE_INCOMPLETE
    assert str(LE11_REGISTER_TOTAL) in before_item.detail
    assert after_item.state == close.STATE_COMPLETE


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — the credit account is resolved by DESIGNATION, and placed on 2100
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc8__the_credit_is_the_accrued_expenses_designation_on_2100(
    brazos, marcus
):
    """No number is hardcoded. `ensure_period_matching_accounts` places the
    designation on the account the tenant already has (`2100 Accrued expenses`,
    a row the PO ruled in on 2026-09-01/02), mints nothing beside it, and is
    idempotent — a tenant that has chosen their own keeps it (rule 1 of the
    seed)."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        placed = ledger_services.ensure_period_matching_accounts(marcus)
        again = ledger_services.ensure_period_matching_accounts(marcus)
        account = selectors.gl_account_for_designation(chart.ACCRUED_EXPENSES)
        duplicates = ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, designation=chart.ACCRUED_EXPENSES, deleted_at__isnull=True
        ).count()

    assert account is not None
    assert account.code == "2100"
    assert account.name == "Accrued expenses"
    assert account.type == "liability"
    assert placed[chart.ACCRUED_EXPENSES] == again[chart.ACCRUED_EXPENSES]
    # `uq_ledger_accounts_designation` is the database half of this promise.
    assert duplicates == 1


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — nothing to accrue is a REFUSAL, never a 0.00 entry
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc9__nothing_unpaid_refuses_rather_than_posting_zero(brazos, marcus):
    """An accrual of 0.00 is a journal entry that says nothing and has to be read
    anyway. The refusal names the exclusions instead."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        with pytest.raises(unpaid_cost_accrual.UnpaidCostAccrualError) as refusal:
            unpaid_cost_accrual.accrue_unpaid_costs(
                marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
            )
        posted = ledger_models.JournalEntry.objects.filter(tenant=brazos).count()

    assert "nothing captured is unpaid" in str(refusal.value)
    assert posted == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — the floor is stated on every answer, and posted_at is an INPUT
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc10__uncaptured_cost_is_named_on_every_answer(brazos, marcus):
    """A delivery whose invoice has not arrived is a real cost this accrual
    cannot see, and every result says so — the figure is a FLOOR. And a clock
    read inside the service is refused (BR-TEN-043 / gate G6)."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)
        preview = unpaid_cost_accrual.preview_unpaid_costs(
            period_start=JULY_START, period_end=JULY_END
        )
        result = unpaid_cost_accrual.accrue_unpaid_costs(
            marcus, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
        )
        with pytest.raises(unpaid_cost_accrual.UnpaidCostAccrualError) as refusal:
            unpaid_cost_accrual.accrue_unpaid_costs(
                marcus,
                period_start=JULY_START,
                period_end=JULY_END,
                posted_at=JULY_END,  # a date, not a datetime
            )

    codes = {gap["code"] for gap in preview.unavailable}
    assert unpaid_cost_accrual.UNCAPTURED_COST_NOT_ESTIMATED["code"] in codes
    assert unpaid_cost_accrual.UNCAPTURED_COST_NOT_ESTIMATED["code"] in {
        gap["code"] for gap in result.unavailable
    }
    assert "posted_at must be a datetime" in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-11 — hard rule 5: this module writes no journal row of its own
# ═══════════════════════════════════════════════════════════════════════════
def test_t7b_tc11__the_module_never_writes_a_journal_row_itself():
    """Grepped rather than described. `ledger/0004`'s trigger makes it
    structural on PostgreSQL; this asserts the source too, so a lane that
    "simplified" the posting call away meets a red test on SQLite as well."""
    import inspect

    source = inspect.getsource(unpaid_cost_accrual)
    for forbidden in ("JournalEntry.objects.create", "JournalLine.objects.create"):
        assert forbidden not in source
    assert "posting.post(" in source
    # And the posting service is the one it calls — not a second writer.
    assert posting.post is not None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C17 + task T7b (12-governance/11-change-requests.md §7 · §12) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-005 / 006 /
#         025 / 028 / 792 · 08-worked-examples.md LE-4, LE-9, LE-11 ·
#         CLAUDE.md hard rules 1-7 and hard-won laws 1, 2, 4, 5, 7, 14
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no screen — C17 names none) F✔ G✔
#         H=deferred(🔒 HUMAN-REVIEW-PENDING, row under CR-060 T19)
# gates: THREE SABOTAGES, each through monkeypatch so no live file was mutated,
#         each failure quoted VERBATIM in the module docstring above
# exceptions: (1) the fixture captures through the REAL capture service and sets
#         `paid_on` through the REAL settlement service — nothing is written by
#         ORM shortcut, because a fixture that reaches a state the product
#         cannot reach is describing a state that does not exist · (2) LE-11's
#         nine invoices carry no `paid_on` in the fixture and this file sets one
#         only on rows it captured itself, so US-LED-021 TC-1's $51,902.50 is
#         untouched
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
