# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C2 / task T7 — unbilled revenue accrual at close.
#           Screens: S42
# Rules:    BR-LED-791 (how unbilled revenue is measured and priced — NEW
#           2026-09-02) · BR-LED-006 (the close checklist, AMENDED the same day
#           to gain a sixth item) · BR-LED-005 (the day-1 auto-reversal) ·
#           BR-LED-025 (nothing over 2 dp posts) · BR-TEN-038 (a closed period
#           is never posted into) · CLAUDE.md rules 1-7
# Golden:   LE-4's shape, produced from measured reads instead of a clerk's
#           typing: DR 1210 Unbilled AR / CR the service revenue accounts, and
#           the day-1 mirror nets 1210 to 0.00.
# ───────────────────────────────────────────────────────
"""The revenue that has been read and not yet billed, put into the books.

════════════════════════════════════════════════════════════════════════════
THE WORKED FIGURE THIS FILE PINS — the one a reviewer signs (CR-060 T19)
════════════════════════════════════════════════════════════════════════════
Brazos Bend bills monthly. July's bills went out and August's have not.

  * **Water.** July's issued bill charged ACC-1042 **$3.10 per kgal**. Two
    August reads are committed and no bill has priced them: **4 kgal** on the
    15th and **6 kgal** on the 31st, so **10 kgal** is unbilled. 10 × 3.10 =
    **$31.00**.
  * **Electric.** July's issued bill charged ACC-1051 **$0.123450 per kWh**.
    One August read of **300 kWh** is unbilled. 300 × 0.12345 = **$37.035**,
    which rounds HALF-UP to **$37.04** — rounded ONCE, on the journal line, per
    BR-RAT-003.
  * **The entry.** One accrual, dated 31 August: **DR 1210 Unbilled AR 68.04**
    against **CR 4110 Water revenue 31.00** and **CR 4100 Electric revenue
    37.04**. The debit is the SUM OF THE ROUNDED CREDITS, so it balances by
    construction and not by luck.
  * **And it undoes itself.** On 1 September the existing auto-reversal sweep
    posts the mirror, `1210` nets **0.00**, and September's real bills post
    normally with no double count.

Every case below is one sentence of that paragraph, or one of the things the
accrual deliberately refuses to do.

════════════════════════════════════════════════════════════════════════════
WHY THE READS AND THE BILLS ARE WRITTEN THROUGH THE ORM
════════════════════════════════════════════════════════════════════════════
The same posture `tests/test_us_led_020_reconciliation.bill_usage` states: this
file tests the LEDGER's accrual, and driving a whole bill run and a whole import
wizard to produce the setup would make a failure here indistinguishable from a
failure in billing or metering. The SHAPE is the real one — an issued invoice
with a priced usage line, and committed lineage heads carrying their explicit
unit — and the accrual reads exactly what a real run leaves behind.

**The POSTING is never faked.** Every journal row in this file goes through
`apps.ledger.posting.post()` by way of the service under test (CLAUDE.md rule 5).
"""

import uuid as _uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import services as asset_services
from apps.billing import models as billing_models
from apps.customers import services as customers_services
from apps.ledger import accruals_api, billing_seam, chart, close, manual_je, metering_seam, models
from apps.ledger import selectors as ledger_selectors
from apps.ledger import unbilled_accrual
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.ledger_le_fixtures import service_id
from tests.test_us_led_012_accrual_auto_reverse import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def signed_in(role="system_admin"):
    """Both halves of a role, deliberately — the journal-API suite's twin."""
    return SimpleNamespace(
        id=_uuid.uuid4(), pk=_uuid.uuid4(), role=role, is_authenticated=True
    )


def call(view, tenant, method="post", *, role="system_admin", data=None, query=None):
    return api_call(
        view, method, user=signed_in(role), role=role, tenant=tenant, data=data, query=query
    )

# ── the worked month, transcribed ──────────────────────────────────────────
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)
SEPTEMBER_START = date(2026, 9, 1)
ISSUED_AT = datetime(2026, 8, 3, 14, 0, tzinfo=dt_timezone.utc)
POSTED_AT = datetime(2026, 9, 1, 9, 0, tzinfo=dt_timezone.utc)
REVERSED_AT = datetime(2026, 9, 1, 9, 5, tzinfo=dt_timezone.utc)

WATER_PRICE = Decimal("3.100000")  # per kgal, off July's issued bill
WATER_UNBILLED = Decimal("10.000000")  # 4 + 6 kgal read in August
WATER_ACCRUAL = Decimal("31.00")

ELECTRIC_PRICE = Decimal("0.123450")  # per kWh, off July's issued bill
ELECTRIC_UNBILLED = Decimal("300.000000")
ELECTRIC_ACCRUAL = Decimal("37.04")  # 37.035 → HALF-UP → 37.04

TOTAL_ACCRUAL = Decimal("68.04")


# ═══════════════════════════════════════════════════════════════════════════
# fixture plumbing
# ═══════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=f"Plan {service_code}",
        defaults={"code": f"plan-{service_code}", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"Tariff {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account_with_meter(actor, tenant, *, service, address, label, uom, asset_no):
    """One account on one unit, with a service point and a meter on it.

    The chain matters: the accrual resolves a read's SERVICE through
    `asset → service_point → service`, so a read on a meter that hangs off no
    service point is one this module correctly cannot attribute.
    """
    premises = make_premises(actor, address_line=address, services_available=[service])
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service).id)}
    )
    metering_services.ensure_service_point(unit["id"], service)
    account = customers_services.create_account(
        actor,
        {
            "unit_id": unit["id"],
            "account_type": "residential",
            "status": "active",
            "opened_at": "2024-01-05",
            "contact": {"full_name": f"Holder {label}", "email": f"{label}@example.test"},
            # `BR-CUS-1024` (2026-09-01) — an account needs an identifier at the
            # door. A phone is the cheapest lawful one for a fixture that is
            # about the ledger and not about identity matching.
            "customer": {
                "display_name": f"Holder {label}",
                "kind": "person",
                "identity": {"phone": f"+1-555-01{asset_no[-2:]}"},
            },
        },
    )
    asset = asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service,
            "unit": uom,
            "read_method": "manual",
            "multiplier": "1",
            "unit_id": unit["id"],
            "install_date": "2024-01-05",
            "status": "active",
        },
    )
    return account, asset


def _bill(tenant, account_id, *, service, quantity, unit, unit_price, period=(JULY_START, JULY_END)):
    """One ISSUED bill with one priced usage line — the accrual's price basis."""
    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account_id=account_id,
        service_date=period[1],
        period_start=period[0],
        period_end=period[1],
        status=billing_models.INVOICE_ISSUED,
        issued_at=ISSUED_AT,
        subtotal=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("0"),
        currency="USD",
    )
    billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account_id=account_id,
        service_id=service_id(service),
        kind="usage",
        description=f"{service} usage",
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        amount=(quantity * unit_price),
        period_start=period[0],
        period_end=period[1],
    )
    return invoice


def _read(tenant, *, account_id, asset_id, day, consumption, unit, lifecycle="committed"):
    """One committed lineage head, written directly — HISTORY SETUP only.

    Same posture as `tests/test_us_met_reads_helpers.commit_read`: the import
    wizard is not what this file is about. Every row carries its EXPLICIT unit
    (CLAUDE.md rule 3).
    """
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=datetime(day.year, day.month, day.day, tzinfo=dt_timezone.utc),
        channel="total",
        current_value=Decimal("1000"),
        consumption=consumption,
        unit=unit,
        source="import",
        status="ok",
        lifecycle=lifecycle,
    )


def the_worked_month(tenant, actor, *, water_read_unit="kgal"):
    """July billed, August read and unbilled — the paragraph at the top.

    ⚠ **`water_read_unit` IS A PARAMETER BECAUSE A COMMITTED READ CANNOT BE
    EDITED, AND THAT IS A POSTGRESQL FACT THE SQLITE SUITE CANNOT SEE
    (CLAUDE.md hard-won law 14).** TC-7's first draft built the month and then
    ran `MeterRead.objects.filter(...).update(unit="gal")`. It passed the whole
    suite on SQLite and failed on real PostgreSQL 16.13 with
    *"a committed read value is immutable: correct it with a superseding row
    (BR-MET-053, B2 r8)"* — a PL/pgSQL trigger the developer database does not
    carry. So the mismatched unit is BUILT, never edited.
    """
    with_monthly_fiscal_year(actor)
    water_account, water_meter = _account_with_meter(
        actor, tenant, service="water", address="500 Main St", label="200",
        uom="kgal", asset_no="MTR-W-1",
    )
    electric_account, electric_meter = _account_with_meter(
        actor, tenant, service="electric", address="Oak Grove", label="12",
        uom="kWh", asset_no="MTR-E-1",
    )
    _bill(
        tenant, water_account["id"], service="water",
        quantity=Decimal("12.000000"), unit="kgal", unit_price=WATER_PRICE,
    )
    _bill(
        tenant, electric_account["id"], service="electric",
        quantity=Decimal("410.000000"), unit="kWh", unit_price=ELECTRIC_PRICE,
    )
    _read(
        tenant, account_id=water_account["id"], asset_id=water_meter["id"],
        day=date(2026, 8, 15), consumption=Decimal("4.000000"), unit=water_read_unit,
    )
    _read(
        tenant, account_id=water_account["id"], asset_id=water_meter["id"],
        day=date(2026, 8, 31), consumption=Decimal("6.000000"), unit=water_read_unit,
    )
    _read(
        tenant, account_id=electric_account["id"], asset_id=electric_meter["id"],
        day=date(2026, 8, 20), consumption=Decimal("300.000000"), unit="kWh",
    )
    return {
        "water_account": water_account,
        "water_meter": water_meter,
        "electric_account": electric_account,
        "electric_meter": electric_meter,
    }


def _balance(tenant, code):
    """One GL account's net movement, read off the journal lines themselves."""
    account = models.LedgerAccount.objects.filter(tenant=tenant, code=code).first()
    if account is None:
        return None
    total = Decimal("0")
    for side, amount in models.JournalLine.objects.filter(
        tenant=tenant, ledger_account=account
    ).values_list("side", "amount"):
        total += amount if side == models.SIDE_DEBIT else -amount
    return total


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — THE FIGURE, and it is the one in the docstring
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc1__the_preview_shows_the_worked_figure_and_what_it_is_made_of(brazos, dana):
    """C2's *"preview before posting — the figure, and the reads it came from"*."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )

        assert preview.total == TOTAL_ACCRUAL
        by_service = {row.service_code: row for row in preview.services}
        assert by_service["water"].amount == WATER_ACCRUAL
        assert by_service["water"].quantity == WATER_UNBILLED
        assert by_service["water"].unit == "kgal"
        assert by_service["water"].read_count == 2
        # 300 × 0.12345 = 37.035, rounded ONCE on the line, HALF-UP.
        assert by_service["electric"].amount == ELECTRIC_ACCRUAL
        assert by_service["electric"].quantity == ELECTRIC_UNBILLED

        # "…and the reads it came from": one row per (account, service), with
        # the price that was applied, so a clerk can add it up by hand.
        assert preview.account_rows_total == 2
        prices = {row.service_code: row.unit_price for row in preview.accounts}
        assert prices["water"] == WATER_PRICE
        assert prices["electric"] == ELECTRIC_PRICE

        # The unread tail is named on the preview, always (OQ-1323).
        assert "unbilled_accrual_excludes_the_unread_tail" in {
            gap["code"] for gap in preview.unavailable
        }


def test_t7_tc1b__posting_debits_1210_and_credits_the_service_revenue_accounts(brazos, dana):
    """DR 1210 68.04 / CR 4110 31.00 + CR 4100 37.04 — one entry, balanced."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)

        result = unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )

        assert result.created is True
        assert result.total == TOTAL_ACCRUAL
        assert result.line_count == 3  # one debit, two credits

        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        # The TYPE is what makes the existing day-1 sweep pick it up. Nothing
        # here schedules a reversal of its own (hard-won law 5).
        assert entry.type == models.JE_ACCRUAL
        assert entry.status == models.JE_POSTED
        assert entry.entry_date == AUGUST_END
        assert entry.source_type == unbilled_accrual.SOURCE_UNBILLED_ACCRUAL

        unbilled_ar = ledger_selectors.gl_account_for_designation(chart.UNBILLED_AR)
        # 1210 is the account CR-060 names as *"seeded and never posted to"*.
        assert unbilled_ar.code == "1210"
        assert _balance(brazos, "1210") == TOTAL_ACCRUAL

        credits = {
            str(line.ledger_account_id): line.amount
            for line in entry.lines.all()
            if line.side == models.SIDE_CREDIT
        }
        assert credits[ledger_selectors.revenue_account_id_for_service("water")] == WATER_ACCRUAL
        assert (
            credits[ledger_selectors.revenue_account_id_for_service("electric")]
            == ELECTRIC_ACCRUAL
        )
        # BR-LED-001's service dimension is stamped and nothing else is: a line
        # naming no customer account correctly names no premises and no unit.
        for row in entry.lines.filter(side=models.SIDE_CREDIT):
            assert row.service_id is not None
            assert row.account_id is None
            assert row.premises_id is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — IT AUTO-REVERSES ON DAY ONE, through the sweep that already existed
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc2__the_accrual_reverses_on_day_one_and_1210_nets_to_zero(brazos, dana):
    """C2's *"auto-reverses on day one"* — BR-LED-005, and NOT a second
    mechanism. `run_accrual_auto_reversals` is the sweep US-LED-012 shipped; it
    finds this entry because of its TYPE, not because anything told it to."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        result = unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )

        swept = manual_je.run_accrual_auto_reversals(
            as_of=SEPTEMBER_START, posted_at=REVERSED_AT
        )

        mine = [row for row in swept if row.accrual_entry_id == result.entry_id]
        assert len(mine) == 1
        assert mine[0].created is True
        assert mine[0].due_on == SEPTEMBER_START
        assert mine[0].amount == TOTAL_ACCRUAL

        accrual = models.JournalEntry.objects.get(pk=result.entry_id)
        mirror = models.JournalEntry.objects.get(pk=mine[0].mirror_entry_id)
        # Linked BOTH ways (BR-LED-005 / r13 #2).
        assert str(accrual.auto_reverse_entry_id) == str(mirror.pk)
        assert str(mirror.reversal_of_id) == str(accrual.pk)
        assert mirror.entry_date == SEPTEMBER_START

        # The whole reason an accrual is safe: it leaves no standing balance.
        assert _balance(brazos, "1210") == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — A CLOSED PERIOD IS REFUSED, AND IS BYTE-IDENTICAL BEFORE AND AFTER
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc3__a_closed_period_is_refused_and_its_books_do_not_move(brazos, dana):
    """C2's *"a closed period is byte-identical before and after"*.

    BR-TEN-038 would FORWARD a late-dated entry into the next open period, and
    this module refuses instead — see its docstring, and the decision-log row of
    2026-09-02. Forwarding would recognise August's revenue in September and
    reverse it in October: two months wrong, in a signed book.
    """
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        close.close_period(
            dana,
            period_start=AUGUST_START,
            period_end=AUGUST_END,
            closed_at=datetime(2026, 9, 5, 10, 0, tzinfo=dt_timezone.utc),
            reason="the bank rec is still being matched",
        )
        before = sorted(
            models.JournalLine.objects.filter(tenant=brazos).values_list("id", flat=True)
        )

        with pytest.raises(unbilled_accrual.UnbilledAccrualError) as refusal:
            unbilled_accrual.accrue_unbilled_revenue(
                dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
            )
        assert "CLOSED" in str(refusal.value)
        assert "Reopen the period" in str(refusal.value)

        after = sorted(
            models.JournalLine.objects.filter(tenant=brazos).values_list("id", flat=True)
        )
        assert after == before
        assert _balance(brazos, "1210") in (None, Decimal("0"))


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — THE CLOSE CHECKLIST GAINS A STEP THAT CAN ACTUALLY BE COMPLETED
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc4__the_checklist_item_names_the_figure_then_goes_green(brazos, dana):
    """CR-060 C2's *"the close checklist gains a step that can actually be
    completed"*, and the correction to its proof sentence: `accruals_posted`
    never answered `unknown` — it answered a DIFFERENT question, and nothing
    asked this one."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)

        before = close.close_checklist(period_start=AUGUST_START, period_end=AUGUST_END)
        item = next(
            row for row in before["items"] if row.code == close.ITEM_UNBILLED_ACCRUAL
        )
        assert item.state == close.STATE_INCOMPLETE
        assert "68.04" in item.detail
        # The older item is untouched and still answers its own question.
        accruals = next(
            row for row in before["items"] if row.code == close.ITEM_ACCRUALS_POSTED
        )
        assert accruals.state == close.STATE_COMPLETE

        unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )

        after = close.close_checklist(period_start=AUGUST_START, period_end=AUGUST_END)
        assert next(
            row for row in after["items"] if row.code == close.ITEM_UNBILLED_ACCRUAL
        ).state == close.STATE_COMPLETE


def test_t7_tc4b__a_period_with_nothing_unbilled_is_complete_not_permanently_red(
    brazos, dana
):
    """A month that is genuinely finished must not carry a red tick forever —
    that is how a checklist stops being read."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)

        checklist = close.close_checklist(period_start=AUGUST_START, period_end=AUGUST_END)
        item = next(
            row for row in checklist["items"] if row.code == close.ITEM_UNBILLED_ACCRUAL
        )
        assert item.state == close.STATE_COMPLETE
        assert "nothing measured is unbilled" in item.detail


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — PRESSING IT TWICE POSTS ONCE (CLAUDE.md rule 6)
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc5__a_second_accrual_for_the_same_period_is_a_replay_no_op(brazos, dana):
    """The key is `unbilled_revenue_accrual|<period uuid>|accrued`, one string
    per period forever, so a resumed close cannot double the receivable."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        first = unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )

        second = unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=REVERSED_AT
        )

        assert second.created is False
        assert second.entry_id == first.entry_id
        assert (
            models.JournalEntry.objects.filter(
                tenant=brazos, source_type=unbilled_accrual.SOURCE_UNBILLED_ACCRUAL
            ).count()
            == 1
        )
        # And the receivable did NOT double.
        assert _balance(brazos, "1210") == TOTAL_ACCRUAL


def test_t7_tc5b__the_period_id_is_derived_and_stable(brazos, dana):
    """Same tenant, same window ⇒ same uuid, always. A random id here would mint
    a new posting key on every call and the replay guard would never fire."""
    with tenant_ctx(brazos):
        first = unbilled_accrual.accrual_source_id(
            period_start=AUGUST_START, period_end=AUGUST_END
        )
        again = unbilled_accrual.accrual_source_id(
            period_start=AUGUST_START, period_end=AUGUST_END
        )
        other = unbilled_accrual.accrual_source_id(
            period_start=JULY_START, period_end=JULY_END
        )
        assert first == again
        assert first != other


# ═══════════════════════════════════════════════════════════════════════════
# TC-6..8 — WHAT IS EXCLUDED, AND EVERY EXCLUSION IS COUNTED BY NAME
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc6__a_read_inside_a_billed_service_period_is_excluded_and_counted(
    brazos, dana
):
    """The belt-and-braces half of BR-LED-791. A read taken before the BILLED
    lock was wired can still read `committed` although its bill went out months
    ago; requiring BOTH conditions can only ever under-accrue."""
    with tenant_ctx(brazos):
        world = the_worked_month(brazos, dana)
        # A JULY read, still lifecycle=committed, on a month that IS billed.
        _read(
            brazos,
            account_id=world["water_account"]["id"],
            asset_id=world["water_meter"]["id"],
            day=date(2026, 7, 20),
            consumption=Decimal("99.000000"),
            unit="kgal",
        )

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )

        # The 99 kgal is NOT in the figure, and its exclusion is named.
        assert preview.total == TOTAL_ACCRUAL
        assert preview.excluded["read_is_inside_a_billed_service_period"] == 1


def test_t7_tc7__a_unit_that_differs_from_the_priced_line_is_excluded_by_name(
    brazos, dana
):
    """Rule 3 and BR-LED-033's discipline: gallons are not kgal, and a silent
    conversion factor is how a figure becomes 1,000× wrong.

    ⚠ The mismatch is BUILT, never edited into place — a committed read is
    immutable on PostgreSQL (`meter_reads_value_immutable`, BR-MET-053) and is
    not on SQLite, which is hard-won law 14 exactly. See `the_worked_month`.
    """
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana, water_read_unit="gal")

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )

        assert preview.excluded[billing_seam.PRICED_UNIT_MISMATCH] == 2
        # Only the electric half survives, and it is unchanged.
        assert preview.total == ELECTRIC_ACCRUAL


def test_t7_tc8__an_account_with_no_prior_priced_line_is_excluded_by_name(brazos, dana):
    """A first bill that has not gone out yet has no price to accrue at. Named
    and counted — never priced at zero, which would put consumption into the
    quantity and nothing into the money.

    ⚠ **THE BRAND-NEW ACCOUNT IS ADDED, NOT MADE BY DELETING SOMEBODY'S BILL,
    and that correction came from PostgreSQL (CLAUDE.md hard-won law 14).** The
    first draft deleted an ISSUED invoice and its lines to create the state. It
    passed the whole suite on SQLite and failed on real PostgreSQL 16.13,
    because an issued invoice accepts no UPDATE and no DELETE — **CLAUDE.md hard
    rule 4, enforced by a trigger the developer database does not carry.** A
    fixture that has to break a hard rule to reach a state is describing a state
    the product cannot be in.
    """
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        # A third account: metered, read in August, and never billed — which is
        # simply a customer whose first bill has not gone out.
        new_account, new_meter = _account_with_meter(
            dana, brazos, service="water", address="Marina Bay", label="3B",
            uom="kgal", asset_no="MTR-W-2",
        )
        _read(
            brazos, account_id=new_account["id"], asset_id=new_meter["id"],
            day=date(2026, 8, 22), consumption=Decimal("7.000000"), unit="kgal",
        )

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )

        assert preview.excluded[billing_seam.NO_PRIOR_PRICED_USAGE_LINE] == 1
        # The 7 kgal is NOT in the figure and NOT priced at zero — the total is
        # exactly what it was before the new customer existed.
        assert preview.total == TOTAL_ACCRUAL


def test_t7_tc9__nothing_to_accrue_refuses_rather_than_posting_a_zero_entry(brazos, dana):
    """An accrual of 0.00 is a journal entry that says nothing and has to be
    read anyway."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)

        with pytest.raises(unbilled_accrual.UnbilledAccrualError) as refusal:
            unbilled_accrual.accrue_unbilled_revenue(
                dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
            )
        assert "nothing measured is unbilled" in str(refusal.value)
        assert not models.JournalEntry.objects.filter(
            tenant=brazos, source_type=unbilled_accrual.SOURCE_UNBILLED_ACCRUAL
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — THE TWO ENDPOINTS, over real HTTP through config/urls.py
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc10a__both_paths_resolve_through_config_urls():
    """DEF-128's lesson: an include that is never resolved through `config/urls`
    is a route that can be lost silently, and every check would stay green."""
    from django.urls import resolve

    assert resolve("/api/brazos/finance/accruals/unbilled").func is not None
    assert resolve("/api/brazos/finance/accruals/unbilled/post").func is not None


def test_t7_tc10b__the_preview_and_the_post_answer(brazos, dana):
    """The two endpoints C2 asks for, called the way the wired stack calls
    them — authenticated user, tenant context entered around the view."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)

    preview = call(
        accruals_api.unbilled_accrual_preview,
        brazos,
        "get",
        query={"from": AUGUST_START.isoformat(), "to": AUGUST_END.isoformat()},
    )
    assert preview.status_code == 200, preview.data
    # `wire.money` is the ledger surface's exact NUMERIC(18,6) STRING, not a
    # display form — the screen renders 2 dp (CLAUDE.md rule 2's "display both
    # 2 decimal") and the wire carries what is stored. Asserted in the wire's
    # own shape so a change to either half goes red here.
    assert preview.data["total"] == "68.040000"
    assert preview.data["already_posted_entry_id"] is None
    assert preview.data["period_is_closed"] is False

    posted = call(
        accruals_api.post_unbilled_accrual,
        brazos,
        "post",
        data={
            "from": AUGUST_START.isoformat(),
            "to": AUGUST_END.isoformat(),
            "posted_at": POSTED_AT.isoformat(),
        },
    )
    assert posted.status_code == 201, posted.data
    assert posted.data["created"] is True
    assert posted.data["total"] == "68.040000"
    assert len(posted.data["services"]) == 2

    # And the second press is a 200 replay, not a second entry.
    again = call(
        accruals_api.post_unbilled_accrual,
        brazos,
        "post",
        data={
            "from": AUGUST_START.isoformat(),
            "to": AUGUST_END.isoformat(),
            "posted_at": POSTED_AT.isoformat(),
        },
    )
    assert again.status_code == 200
    assert again.data["created"] is False


# ═══════════════════════════════════════════════════════════════════════════
# TC-11 — THE SEAMS IMPORT NO OTHER MODULE'S MODELS (B1 / BR-TEN-013, gate G6)
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc11__the_two_seams_import_no_foreign_models():
    """Asserted on the SOURCE, the way `tests/test_us_led_020_reconciliation`
    asserts it: a cross-module read resolves the owner's published callable by
    name at call time, and never reaches into its ORM."""
    import ast
    import inspect

    for module in (metering_seam, unbilled_accrual):
        tree = ast.parse(inspect.getsource(module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for name in imported:
            assert not name.startswith("apps.metering"), (module.__name__, name)
            assert not name.startswith("apps.billing"), (module.__name__, name)
            assert not name.startswith("apps.customers"), (module.__name__, name)


# ═══════════════════════════════════════════════════════════════════════════
# TC-12 — THE UNANSWERABLE CASE IS NOT A ZERO
# ═══════════════════════════════════════════════════════════════════════════
def test_t7_tc12__an_unreadable_metering_seam_refuses_rather_than_accruing_zero(
    brazos, dana, monkeypatch
):
    """US-LED-020 TC-9's discipline, applied here: *"there is nothing unbilled"*
    and *"nobody can look"* are different facts, and only one of them may be
    posted at zero."""
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        monkeypatch.setattr(metering_seam, "_resolve", lambda *a, **k: None)

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )
        assert preview.total is None
        assert metering_seam.READS_UNAVAILABLE in preview.problems

        with pytest.raises(unbilled_accrual.UnbilledAccrualError) as refusal:
            unbilled_accrual.accrue_unbilled_revenue(
                dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
            )
        assert "UNANSWERABLE" in str(refusal.value)
