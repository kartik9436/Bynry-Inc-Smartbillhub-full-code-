# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-018 (capture a supplier invoice on S73 — TC-1 RS-2607-0141,
#           TC-2 the cost-only invoice nothing refuses, TC-3 the unit travels
#           with the number, TC-4 two spellings of one supplier both kept,
#           TC-5 the closed-period auto-forward, TC-6 money refusals, TC-7 the
#           half-filled volume pair, TC-8 the forbidden workflows, TC-9 the
#           Executive gate, TC-10 isolation)   Screens: S73
# Rules:    BR-LED-028 (capture, hold, reconcile, export — process NOTHING) ·
#           BR-LED-029 (what a captured invoice holds) · BR-LED-030 (the volume
#           is OPTIONAL) · BR-LED-033 (an EXPLICIT unit, never assumed) ·
#           BR-LED-034 (a closed-period date auto-forwards) · BR-LED-036 (every
#           capture audits) · BR-TEN-038 / BR-LED-006 (the auto-forward) ·
#           BR-TEN-042 (the currency lock) · CLAUDE.md rules 1, 2, 3, 7
# Golden:   LE-11 — nine supplier invoices, **$51,902.50 USD**, and nothing is
#           processed. LE-9 — the closed-July auto-forward into August.
# ───────────────────────────────────────────────────────
"""Capturing what the utility was invoiced — and the five things it refuses.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_018_tc8__no_approval_payment_or_vendor_path_exists_by_rule`. Every
other case here proves a capture works; that one proves the product will not
grow into an accounts-payable system, which is what the Product Owner actually
ruled (OQ-188, 2026-08-12, verbatim):

    "we can make this system of record and capture Ap, AR both ; we dont have
     to process anything just capture and help Utility, Sub metering copany or
     HOA reconcile both sides as system of record"

⚠ **CORRECTED 2026-09-02 — THIS PARAGRAPH DESCRIBED TWO STUBS THAT HAVE NOT
EXISTED SINCE 2026-08-16.** It read: *"whether a capture POSTS is OQ-200 and
whether it may be edited after its period closes is OQ-203; both raise
NotImplementedError with the question's ID"*. **Both questions CLOSED on
2026-08-16** and the tests below assert ruled behaviour, not stubs.

Where the boundary stands today, in one sentence each: **a CAPTURE posts
nothing** (OQ-200, unchanged), **a SETTLEMENT posts DR cost / CR cash** (CR-060
C1, PO ruling 2026-09-02 — proved in
`tests/test_cr060_t6_settlement_posting.py`), and **an after-close correction is
lawful with a REASON** (OQ-203). The one live stub in this area is `OQ-1340`:
what a settlement should do when the purchase behind it is later corrected or
voided.

WHAT RUNS WHERE. Shape, refusals, the auto-forward and the audit trail run on
SQLite and Postgres alike. The `-m isolation` cases at the bottom carry
`requires_postgres` and prove the DATABASE refuses a cross-tenant read of
`supplier_invoices` under a NOSUPERUSER probe role — on SQLite they SKIP with a
vendor reason rather than passing vacuously. **No case in this file is
unconditionally skipped.**
"""

from datetime import date
from decimal import Decimal

import pytest

from core import errors

from apps.ledger import chart, close, cost_capture
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    LE11_REGISTER_TOTAL,
    LSR_AMOUNT,
    LSR_DATE,
    LSR_REFERENCE,
    LSR_SUPPLIER,
    LSR_VOLUME,
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    executive_actor,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SUPPLIER_TABLES = ("supplier_invoices",)


def brazos_ready(tenant, actor=None):
    """The LE-11 preconditions: a fiscal calendar and the five services sold.

    Both are SYSTEM ADMIN actions (`save_regional_settings` and
    `update_tenant_service` are gated), while capture is a clerk's — so the
    setup mints its own admin rather than borrowing the capturing actor. That
    split is the product's, not the test's: a Billing Clerk records purchases
    and does not reconfigure the utility.
    """
    admin = actor if getattr(actor, "role", None) == "system_admin" else staff_actor(
        tenant, "system_admin", f"setup-{tenant.subdomain}@brazosbendutilities.test"
    )
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    return admin


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the ruled capture, RS-2607-0141
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc1__the_bulk_water_invoice_is_captured_with_its_volume(
    brazos, marcus, audit_rows
):
    """*"Capture RS-2607-0141 — City of Rosenberg — Bulk Water Supply,
    2026-07-06, service Water, 400,000 gal, $1,240.00 USD, GL 5110, period
    2026-07 → row stored; amount held as NUMERIC(18,6) with currency USD; volume
    400000 with unit gal; audit `supplier_invoice.captured` naming the actor."*
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        audit_rows.clear()
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.00"),
            currency="USD",
            volume=Decimal("400000"),
            volume_unit="gal",
            reference="RS-2607-0141",
            memo="July bulk water, first delivery",
        )

        row = ledger_models.SupplierInvoice.objects.get(pk=captured["id"])

    # Money is NUMERIC(18,6) + CHAR(3), never float and never cents.
    assert isinstance(row.amount, Decimal) and row.amount == Decimal("1240.00")
    assert row.currency == "USD"
    # The volume carries its explicit unit (CLAUDE.md rule 3).
    assert row.volume == Decimal("400000") and row.volume_unit == "gal"
    assert row.supplier_name == "City of Rosenberg — Bulk Water Supply"
    assert row.service == "water"
    assert row.status == ledger_models.SUPPLIER_INVOICE_CAPTURED
    # The GL account defaulted from the service map — BR-LED-038's seeded
    # pointer, which is a default the tenant may override.
    assert row.ledger_account.code == "5110"
    # The period came from the invoice date's own month, open at the time.
    assert [row.period_start, row.period_end] == [JULY_START, JULY_END]

    # BR-LED-036 / CLAUDE.md rule 7.
    captured_rows = [r for r in audit_rows if r["action"] == "supplier_invoice.captured"]
    assert len(captured_rows) == 1
    assert captured_rows[0]["actor_user_id"] == marcus.id
    assert captured_rows[0]["after"]["amount"] == "1240.000000"
    assert captured_rows[0]["after"]["volume"] == "400000.000000"
    assert captured_rows[0]["after"]["volume_unit"] == "gal"
    # The trail records the account's signature state AT THE MOMENT of capture.
    # ⚠ AMENDED 2026-08-18: this pinned `is False`, because 5110 Purchased water
    # was BR-LED-037's unsigned proposal. The Product Owner finance re-signed
    # all eight cost codes that day in the working chat session — shown their
    # codes and names in plain English, with no dollar figure attached to any of
    # them and with B4/B5 ❄️ FROZEN and un-edited — so a capture against 5110
    # now records True. The mechanism (the trail carries the state, per row) is
    # driven from a synthetic unsigned code in
    # `test_us_led_017_tc5__the_capture_result_and_the_register_carry_the_marker`,
    # so it cannot rot into a constant now that nothing real is unsigned.
    assert captured_rows[0]["after"]["gl_account_finance_signed"] is True


def test_us_led_018_tc1__the_nine_july_invoices_total_51902_50(brazos, marcus):
    """LE-11's footing, from the nine rows and not from a constant:
    `1,240.00 + 775.00 + 310.00 + 155.00 + 620.00 + 28,222.00 + 6,235.00 +
    1,845.50 + 12,500.00 = **51,902.50**`."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        capture_le11_month(marcus)

        stored = ledger_models.SupplierInvoice.objects.filter(tenant=brazos)
        assert stored.count() == 9
        assert sum((row.amount for row in stored), Decimal("0")) == LE11_REGISTER_TOTAL
        # Per GL account, as LE-11 states it.
        by_account: dict[str, Decimal] = {}
        for row in stored:
            by_account[row.ledger_account.code] = (
                by_account.get(row.ledger_account.code, Decimal("0")) + row.amount
            )
    assert by_account == {
        "5110": Decimal("3100.00"),
        "5100": Decimal("28222.00"),
        "5140": Decimal("6235.00"),
        "5200": Decimal("1845.50"),
        "5300": Decimal("12500.00"),
    }
    assert sum(by_account.values(), Decimal("0")) == LE11_REGISTER_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE RULED CASE: a cost-only invoice is refused by nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc2__a_cost_only_invoice_is_accepted_without_complaint(brazos, marcus):
    """*"Capture HPV-4471 — Hillcrest Pipe & Valve, 2026-07-15, category O&M,
    NO VOLUME, $1,845.50, GL 5200 → **Accepted**. The row carries volume = null
    and the reconciliation treats it per BR-LED-031, never as a validation
    error."*

    PO verbatim (OQ-190): *"I dont know but we can make a provision and make it
    optional"*.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 15),
            service=chart.COST_CATEGORY_OM,
            supplier_name="Hillcrest Pipe & Valve",
            amount=Decimal("1845.50"),
            currency="USD",
            reference="HPV-4471",
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=captured["id"])

    assert row.volume is None and row.volume_unit is None
    assert row.amount == Decimal("1845.50")
    assert row.ledger_account.code == "5200"
    # Nothing complained: no problem code about the missing volume anywhere.
    assert all("volume" not in code for code in captured["problems"])


def test_us_led_018_tc3__the_unit_travels_with_the_number_and_is_never_inferred(
    brazos, marcus
):
    """*"Capture BVPC-070026 … Electric, 412,000 kWh, $28,222.00 → stored with
    unit kWh; the unit travels with the number and is never inferred from the
    service."*

    The second half is asserted directly: the SAME service captured in a
    different unit stores that different unit, because nothing derives a unit
    from a service code (CLAUDE.md rule 3, BR-LED-033).
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        kwh = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 31),
            service="electric",
            supplier_name="Brazos Valley Power Cooperative",
            amount=Decimal("28222.00"),
            currency="USD",
            volume=Decimal("412000"),
            volume_unit="kWh",
            reference="BVPC-070026",
        )
        mwh = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 31),
            service="electric",
            supplier_name="Another cooperative billing in MWh",
            amount=Decimal("100.00"),
            currency="USD",
            volume=Decimal("412"),
            volume_unit="MWh",
            reference="ALT-1",
        )
    assert kwh["volume_unit"] == "kWh"
    assert mwh["volume_unit"] == "MWh"


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — two spellings of one supplier, both kept. NO vendor master.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc4__both_spellings_of_a_supplier_are_kept_as_typed(brazos, marcus):
    """*"Supplier name typed twice with different spellings → **both accepted as
    typed**. No vendor record is created, no dedupe prompt, no master list."*

    BR-LED-028 forbids a vendor master, so this is the rule working rather than
    a normalisation nobody got round to.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        for spelling in ("City of Rosenberg", "City of Rosenberg - Water Dept"):
            cost_capture.capture_supplier_invoice(
                marcus,
                invoice_date=date(2026, 7, 6),
                service="water",
                supplier_name=spelling,
                amount=Decimal("100.00"),
                currency="USD",
            )
        names = list(
            ledger_models.SupplierInvoice.objects.filter(tenant=brazos).values_list(
                "supplier_name", flat=True
            )
        )
    assert sorted(names) == ["City of Rosenberg", "City of Rosenberg - Water Dept"]
    # And the register's free-text search finds BOTH from one term, which is
    # what makes a vendor-master-free register usable at all.
    with tenant_ctx(brazos):
        found = cost_capture.register(q="Rosenberg")
    assert found["count"] == 2

    # No vendor table exists anywhere in the schema.
    from django.apps import apps as django_apps

    tables = {model._meta.db_table for model in django_apps.get_models()}
    assert "vendors" not in tables and "suppliers" not in tables


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — LE-9's auto-forward, on the payable side
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc5__a_capture_dated_into_a_closed_july_lands_in_august(
    brazos, dana, marcus, audit_rows
):
    """*"Capture dated 2026-07-30, keyed 2026-08-07, with July already CLOSED →
    **auto-posts forward to August** with the audit note 'period closed;
    auto-forwarded'; July is untouched."*

    BR-LED-034 rides BR-TEN-038 unchanged, and `close.resolve_entry_date` is
    that rule — CALLED here, never reimplemented.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        capture_le11_month(marcus)
        july_before = list(
            ledger_models.SupplierInvoice.objects.filter(
                tenant=brazos, period_start=JULY_START
            ).values_list("id", flat=True)
        )
        close.close_period(
            dana,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="the deposit register is still being matched",
        )
        audit_rows.clear()

        late = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 30),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("410.00"),
            currency="USD",
            volume=Decimal("132258"),
            volume_unit="gal",
            reference="RS-2607-0219",
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=late["id"])
        july_after = list(
            ledger_models.SupplierInvoice.objects.filter(
                tenant=brazos, period_start=JULY_START
            ).values_list("id", flat=True)
        )

    # The invoice DATE is what the supplier wrote and never moves.
    assert row.invoice_date == date(2026, 7, 30)
    # The PERIOD is what moved.
    assert [row.period_start, row.period_end] == [date(2026, 8, 1), date(2026, 8, 31)]
    assert late["period_auto_forwarded"]["detail"] == "period closed; auto-forwarded"
    assert late["period_auto_forwarded"]["br_ref"] == "BR-TEN-038 · BR-LED-006"
    # July's register is byte-identical: same rows, nothing added.
    assert sorted(july_after) == sorted(july_before)
    # The trail carries the note on the row that moved.
    forwarded = [r for r in audit_rows if r["action"] == "supplier_invoice.captured"]
    assert forwarded[0]["after"]["period_auto_forwarded"]["detail"] == (
        "period closed; auto-forwarded"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 / TC-7 — the money and quantity refusals
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc6__money_without_a_currency_or_as_a_float_is_refused(brazos, marcus):
    """*"Capture with amount 1240 and no currency; amount as a float in an API
    payload → Refused — currency CHAR(3) is required, and the money contract is
    NUMERIC(18,6) + CHAR(3), never float and never cents (CLAUDE.md rule 2)."*
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        base = dict(
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
        )
        with pytest.raises(cost_capture.CostCaptureError) as no_currency:
            cost_capture.capture_supplier_invoice(
                marcus, amount=Decimal("1240"), currency="", **base
            )
        assert "CHAR(3)" in str(no_currency.value)

        with pytest.raises(cost_capture.CostCaptureError) as as_float:
            cost_capture.capture_supplier_invoice(
                marcus, amount=1240.00, currency="USD", **base
            )
        assert "float" in str(as_float.value)
        # Refused rather than CONVERTED — the point is that the defect stays
        # visible at the place where money became a binary fraction.
        assert not ledger_models.SupplierInvoice.objects.filter(tenant=brazos).exists()

        # BR-TEN-042's currency lock: the tenant's books are in USD.
        with pytest.raises(cost_capture.CostCaptureError) as wrong_currency:
            cost_capture.capture_supplier_invoice(
                marcus, amount=Decimal("1240.00"), currency="CAD", **base
            )
        assert "BR-TEN-042" in wrong_currency.value.br_ref


def test_us_led_018_tc6__a_three_decimal_amount_is_stored_exactly_and_flagged(
    brazos, marcus
):
    """The third clause of TC-6, and the one this lane does NOT decide.

    US-LED-018 §7 is explicit: *"the amount is stored exactly as keyed at six
    decimals and is **never rounded by the ledger**, because rounding is the
    caller's job and happens once at finalization"* — two rounding sites is how
    two figures start disagreeing. BR-LED-025's >2dp refusal is a POSTING-side
    rule and the posting boundary is stubbed under **OQ-200**.

    So the amount is stored EXACTLY, is NOT rounded, is NOT refused, and comes
    back carrying a problem code — flagged rather than silent in either
    direction. When OQ-200 closes as reading (a) this capture becomes
    unpostable, and the warning was already on the row.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.005"),
            currency="USD",
        )
        row = ledger_models.SupplierInvoice.objects.get(pk=captured["id"])
    assert row.amount == Decimal("1240.005"), "the ledger rounded a captured amount"
    assert cost_capture.AMOUNT_PRECISION_WARNING in captured["problems"]


def test_us_led_018_tc7__a_volume_without_its_unit_is_refused_both_ways(brazos, marcus):
    """*"Capture with a volume of 400000 and NO UNIT; capture with a unit and no
    volume → both refused. Omitting BOTH is legal (TC-2)."*

    CLAUDE.md rule 3 is the first half; BR-LED-030 is the second.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        base = dict(
            invoice_date=date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.00"),
            currency="USD",
        )
        with pytest.raises(cost_capture.CostCaptureError) as no_unit:
            cost_capture.capture_supplier_invoice(
                marcus, volume=Decimal("400000"), volume_unit=None, **base
            )
        assert "rule 3" in str(no_unit.value)

        with pytest.raises(cost_capture.CostCaptureError) as no_volume:
            cost_capture.capture_supplier_invoice(marcus, volume=None, volume_unit="gal", **base)
        assert "BR-LED-030" in no_volume.value.br_ref

        # Omitting BOTH is lawful and lands.
        both_omitted = cost_capture.capture_supplier_invoice(marcus, **base)
        assert both_omitted["volume"] is None and both_omitted["volume_unit"] is None


def test_us_led_018_tc7__the_database_refuses_a_half_filled_volume_pair_too(brazos, marcus):
    """The same law one layer down. A service-layer check is bypassable by any
    caller that reaches the ORM; `ck_supplier_invoices_volume_unit` is not."""
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ledger_models.SupplierInvoice.objects.create(
                    tenant=brazos,
                    invoice_date=date(2026, 7, 6),
                    service="water",
                    supplier_name="Bypassing the service layer",
                    amount=Decimal("1240.00"),
                    currency="USD",
                    volume=Decimal("400000"),
                    volume_unit=None,
                    ledger_account=account,
                    period_start=JULY_START,
                    period_end=JULY_END,
                )


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — THE RULE. No approval, payment, vendor or ageing path exists.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc8__no_approval_payment_or_vendor_path_exists_by_rule(brazos, marcus):
    """*"Any request to approve, schedule, pay, or attach a vendor record to a
    captured invoice → **Refused and named**. There is no such path, by rule
    (BR-LED-028). The refusal cites the rule so a later lane reads it as law,
    not as an unbuilt feature."*

    Asserted three ways, because a missing feature and a forbidden one look
    identical from the outside and only one of them must stay missing.
    """
    # 1 · The refusal exists and cites the rule and the declined option.
    for action in cost_capture.FORBIDDEN_ACTIONS:
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.refuse_processing_action(action)
        assert refused.value.br_ref == "BR-LED-028"
        assert "DECLINED" in str(refused.value)
        assert "do not implement it" in str(refused.value)

    # 2 · No function that would DO one of them exists on the module.
    for forbidden in ("approve", "schedule_payment", "mark_paid", "pay", "create_vendor"):
        assert not hasattr(cost_capture, forbidden), (
            f"cost_capture.{forbidden} exists — BR-LED-028 forbids it and option (c), full "
            "accounts payable, was put to the Product Owner and DECLINED"
        )

    # 3 · No column that would RECORD one of them exists on the table.
    columns = {field.name for field in ledger_models.SupplierInvoice._meta.get_fields()}
    assert columns.isdisjoint(
        {"approved_by", "approved_at", "due_date", "paid_at", "payment_run", "vendor"}
    )
    # ⚠ 3b · AND `paid_on` DOES EXIST, WHICH IS NOT A HOLE IN THE LIST ABOVE
    # (CR-060 C1 / T6, PO ruling 2026-09-02). The four names above belong to a
    # system that PAYS things: an approval, a due date, the instant we paid, the
    # run that paid it. `paid_on` is the day the utility's BANK moved the money,
    # somewhere else, typed in by a clerk reading a statement — *"we can take
    # input from Clark and close it"*. Asserted HERE, beside the refusals, so a
    # reader meeting "NO paid_at" cannot conclude the column is a violation.
    assert "paid_on" in columns
    assert "paid_at" not in columns

    # 4 · The status enum has no approval or payment state to move into.
    assert ledger_models.SUPPLIER_INVOICE_STATUSES == ("captured", "voided")

    # 5 · The register offers no bulk action, and the EMPTY TUPLE is the whole
    # statement. ⚠ `bulk_actions_reason` rode beside it until 2026-09-25 and is
    # DELETED (`DEF-LED-6642`): it printed `BR-LED-028:` and 38 words of our
    # reasoning to a clerk, and B14 rule 33 puts rationale at zero words on
    # screen while rule 32 keeps a rule id out of clerk-facing copy.
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        listed = cost_capture.register()
    assert listed["bulk_actions"] == ()
    assert "bulk_actions_reason" not in listed


def test_us_led_018__a_capture_posts_nothing_to_the_books_oq_200_ruled(brazos, marcus):
    """**A CAPTURE POSTS NOTHING. A SETTLEMENT POSTS.** Both halves, in one case.

    ⚠ **THIS TEST WAS REWRITTEN ON 2026-09-02 AND WAS NOT DELETED (CR-060 T6a),
    BECAUSE IT IS THE ONLY RECORD OF WHY THE OLD RULE EXISTED.** What it asserted
    before that date: that nine captures leave no journal row at all, and that
    `POSTING_RULING_EXPIRES_WHEN` named the condition under which that would
    stop being true — *"a supplier-payment path ships"*.

    **THE FIRST HALF IS UNCHANGED AND STILL ASSERTED HERE.** OQ-200, PO
    2026-08-16, verbatim: *"(b) for R2, (a) once supplier payments exist"*. The
    reason was the rule: option (a) credits an accounts payable this product can
    never drain, because BR-LED-028 forbids payment runs, so twelve months at
    $3,100.00 of purchased water would leave **$37,200.00** standing for invoices
    the utility settled by cheque. *A growing false number is worse than an
    absent true one.* Capturing still posts nothing, for exactly that reason.

    **THE SECOND HALF IS NEW AND IS NOT A REVERSAL OF THE FIRST.** PO 2026-09-02,
    verbatim: *"why cant to add the check that whether this is paid or unpaid and
    allow clark to udpaet it - that way we can reconcicle - again system of
    record we dont have to match we can take input from Clark and close it"*.
    Option **(c)** — DR cost / CR cash — had been rejected in the earlier sitting
    for a DIFFERENT reason from (a): it *"asserts the invoice was paid, which is
    wrong for anything unpaid"*. Posting only when a clerk RECORDS the settlement
    removes that objection and creates no payable at all.

    **AND THE CONDITION THE OLD RULING SET FOR ITSELF NEVER FIRED**, which is the
    part a reader most needs and the part a deleted test would have lost: no
    supplier-payment path shipped, and none will. That is why the constant is
    kept, dated `POSTING_RULING_SUPERSEDED`, and asserted below.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)

        # RULED, and therefore a no-op rather than a raise. Asserting the return
        # value pins the ruling: this is the CAPTURE boundary and it did not move
        # on 2026-09-02.
        assert (
            cost_capture.post_capture_to_journal(
                ledger_models.SupplierInvoice.objects.get(pk=captured["RS-2607-0141"]["id"])
            )
            is None
        )

        # Nine captures, $51,902.50, and the books have not moved. That is the
        # ruling rather than an absence — and it is still true after T6, because
        # not one of the nine carries a `paid_on`.
        assert not ledger_models.JournalEntry.objects.filter(tenant=brazos).exists()
        assert not ledger_models.JournalLine.objects.filter(tenant=brazos).exists()
        assert all(
            row.paid_on is None
            for row in ledger_models.SupplierInvoice.objects.filter(tenant=brazos)
        )

    # And every capture SAYS so rather than leaving a reader to notice — in a
    # sentence a screen can print, because "any screen implying the books moved
    # is a defect" (OQ-200's closure text).
    posting_says = captured["RS-2607-0141"]["posting"]
    assert posting_says["posted"] is False
    assert posting_says["reason"] == cost_capture.POSTING_RULED_NONE
    detail = posting_says["detail"]
    assert "posts NOTHING to the books" in detail
    assert "$37,200.00" in detail
    assert "in no trial balance" in detail
    # ⚠ THE NEW BOUNDARY, named in the SAME sentence, so a screen cannot print
    # the first half beside a "Paid on" field and imply the books never move.
    assert "THE BOOKS MOVE WHEN YOU RECORD THAT IT WAS PAID" in detail
    assert "creates no payable at all" in detail
    # The two states R8 names, on the capture result: this one is "Recorded —
    # held here, not in the books".
    assert posting_says["settlement"]["paid_on"] is None
    assert posting_says["settlement"]["in_the_books"] is False

    # THE OLD RULING'S TRIGGER, KEPT AND DATED. It read "a supplier-payment path
    # ships"; that never happened and cannot, because BR-LED-028 still forbids a
    # payment run. Asserting the supersession — rather than the old sentence —
    # is what stops a later reader treating a dead condition as live law.
    assert "supplier-payment path ships" in cost_capture.POSTING_RULING_SUPERSEDED
    assert "SUPERSEDED 2026-09-02" in cost_capture.POSTING_RULING_SUPERSEDED
    assert not hasattr(cost_capture, "POSTING_RULING_EXPIRES_WHEN")


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — the role gate (carried as a READING, flagged, not assumed)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc9__an_executive_cannot_capture(brazos):
    """*"Capture attempted by an Executive role → refused server-side — an
    executive reads the books, a clerk records them."*

    ⚠ Carried as this lane's READING of BR-LED-003 as amended (PO 2026-08-12,
    OQ-175) and **not treated as separately ratified**: what was put to the PO
    was the REVERSAL, and capture was not raised. Same posture US-LED-014 takes
    for the remittance record and US-LED-015 for the close. Asserted here so the
    reading is visible and testable rather than implicit.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError) as denied:
            cost_capture.capture_supplier_invoice(
                executive_actor(),
                invoice_date=date(2026, 7, 6),
                service="water",
                supplier_name="City of Rosenberg — Bulk Water Supply",
                amount=Decimal("1240.00"),
                currency="USD",
            )
    assert denied.value.code == errors.AUTH_PERMISSION_DENIED


def test_us_led_018__a_service_the_tenant_does_not_sell_cannot_be_captured(brazos, marcus):
    """BR-REP-006 — the vocabulary is the tenant's LIVE service list, never a
    hardcoded one. Brazos Bend sells no broadband, so a broadband purchase has
    no category to be captured under until somebody switches the service on."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(
            staff_actor(brazos, "system_admin", "setup-vocab@brazosbendutilities.test")
        )
        with pytest.raises(cost_capture.CostCaptureError) as refused:
            cost_capture.capture_supplier_invoice(
                marcus,
                invoice_date=date(2026, 7, 6),
                service="broadband",
                supplier_name="Some transit provider",
                amount=Decimal("100.00"),
                currency="USD",
            )
        assert refused.value.br_ref == "BR-LED-029"
        # The two categories that belong to no service are always available.
        vocabulary = cost_capture.cost_category_vocabulary()
    assert chart.COST_CATEGORY_OM in vocabulary
    assert chart.COST_CATEGORY_INFRASTRUCTURE in vocabulary
    assert "broadband" not in vocabulary


def test_us_led_018__capture_refuses_outside_a_tenant_context():
    """CLAUDE.md rule 1's app half — the refusal happens before any query."""
    with pytest.raises(errors.AuthError) as raised:
        cost_capture.register()
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — isolation. App layer here; the DATABASE half is below.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_018_tc10__one_tenants_purchases_are_invisible_to_the_other(
    brazos, lonestar, marcus, erin
):
    """*"Lone Star Ridge captures its own bulk-water invoice while Brazos Bend's
    July is open → each tenant sees only its own rows. J. Okafor cannot see
    RS-2607-0141 by id, by search or by export."*"""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        theirs = capture_le11_month(marcus)

    with tenant_ctx(lonestar):
        with_monthly_fiscal_year(erin)  # erin is Lone Star Ridge's System Admin
        mine = cost_capture.capture_supplier_invoice(
            erin,
            invoice_date=LSR_DATE,
            service="water",
            supplier_name=LSR_SUPPLIER,
            amount=LSR_AMOUNT,
            currency="USD",
            volume=LSR_VOLUME,
            volume_unit="gal",
            reference=LSR_REFERENCE,
        )
        listed = cost_capture.register()
        assert listed["count"] == 1
        assert listed["rows"][0]["reference"] == LSR_REFERENCE
        assert listed["total_amount"] == LSR_AMOUNT

        # BY ID — a cross-tenant id looks exactly like a missing one.
        with pytest.raises(cost_capture.CostCaptureError):
            cost_capture.edit_supplier_invoice(
                erin, theirs["RS-2607-0141"]["id"], memo="peeking"
            )
        # BY SEARCH — the free-text supplier search is a string oracle over the
        # column, so it is probed by name.
        assert cost_capture.register(q="Rosenberg")["count"] == 0
        assert cost_capture.register(q="Brazos Valley")["count"] == 0

    with tenant_ctx(brazos):
        assert cost_capture.register()["count"] == 9
        assert cost_capture.register(q="Bandera")["count"] == 0
        assert mine["id"] not in {row["id"] for row in cost_capture.register()["rows"]}


@pytest.mark.isolation
@requires_postgres
def test_us_led_018_tc10__supplier_invoices_are_rls_scoped(rls, brazos, lonestar):  # noqa: F811
    """TC-10 at the DATABASE, with the app-layer filter deliberately out of the
    path.

    A leaked row here is another utility's supplier list, its purchase prices
    and — through the reconciliation built on it — its water-loss percentage.
    J25 step 12 requires unreachability *"by id, by search, by filter, by
    drill-back, by CSV and by export payload"*, and every one of those six paths
    reads this table.

    Run under `sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS): the app's own
    role is a superuser and would bypass the policy, making the assertion
    vacuous. `requires_postgres` — never a bare skip.
    """
    with live_tenant_context(brazos.id):
        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        theirs = str(
            ledger_models.SupplierInvoice.objects.create(
                tenant=brazos,
                invoice_date=date(2026, 7, 6),
                service="water",
                supplier_name="City of Rosenberg — Bulk Water Supply",
                amount=Decimal("1240.00"),
                currency="USD",
                volume=Decimal("400000"),
                volume_unit="gal",
                ledger_account=account,
                period_start=JULY_START,
                period_end=JULY_END,
                reference="RS-2607-0141",
            ).id
        )

    assert_rls_scoped(
        rls, "supplier_invoices", owner=brazos, intruder=lonestar, owner_ids={theirs}
    )
    with live_tenant_context(lonestar.id):
        assert rls.count("supplier_invoices", "id = %s", [theirs]) == 0
        # By SEARCH as well as by id — the column the register searches.
        assert rls.count("supplier_invoices", "supplier_name LIKE %s", ["%Rosenberg%"]) == 0
    assert_no_foreign_rows_anywhere(rls, lonestar, SUPPLIER_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_led_018_tc10__supplier_invoices_are_denied_without_context(rls, brazos):  # noqa: F811
    """Deny-by-default, both halves: with `app.tenant_id` unset the policy's
    `::uuid` cast of '' fails and NO row is visible, and the service refuses
    before a query is built."""
    assert_denied_without_context(rls, *SUPPLIER_TABLES)
    with pytest.raises(errors.AuthError) as raised:
        cost_capture.register()
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-018@d744841 (04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-018 §3 TC-1..TC-10 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028..036 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-11 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md steps 2-3, 8, 12 · 12-governance/01-open-questions.md OQ-200)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S73's endpoints wait on OQ-204) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — the volume/unit refusal, the auto-forward and
#         the OQ-200 stub were each driven RED against a deliberately broken
#         implementation before being trusted green. Exact failures in the lane
#         report
# exceptions: the two -m isolation cases are Postgres-only and SKIP on the
#         default sqlite database with a VENDOR reason via `requires_postgres` —
#         never a bare pytest.mark.skip · TC-9's Executive refusal is this
#         lane's READING of BR-LED-003 as amended (OQ-175 ratified the REVERSAL;
#         capture was not separately raised) and is asserted so the reading is
#         visible, NOT presented as ratified · the three-decimal clause of TC-6
#         asserts the amount is STORED EXACTLY and FLAGGED rather than refused,
#         per US-LED-018 §7 — BR-LED-025's refusal is a posting-boundary rule
#         and that boundary is stubbed under OQ-200. REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
