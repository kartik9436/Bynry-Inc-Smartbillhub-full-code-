# ── Trace ──────────────────────────────────────────────
# Ruling:  12-governance/02-decision-log.md, 2026-10-01 — "CAPACITY SERVICES: THE
#          BASE IS LOOKED UP BY SIZE ON EVERY BILL, A SIZE WITH NO BASE BILLS
#          $0.00 INSTEAD OF REFUSING, AND EVERY BILL LINE KEEPS THE SIZE, THE
#          COUNT AND THE BASE AMOUNT USED" and "GO: THE NINE CHANGES".
# Code:    apps/rating/selectors.py::base_charge_from_charge_code (🔒) ·
#          apps/billing/gather.py (🔒) · apps/metering/selectors.py::
#          billable_base_size_counts (🔒) · apps/billing/resolution_switch.py (🔒) ·
#          apps/billing/stages/assemble_document.py · billing/0039 (🔒)
# ───────────────────────────────────────────────────────
"""**A CAPACITY BASE IS LOOKED UP BY SIZE, A MISSING SIZE PRICE BILLS $0.00,
AND THE LINE KEEPS THE CHAIN IT WAS PRICED FROM.**

PO verbatim, 2026-10-01: *"in case of all capacity based base rates for example
ofr base charges for Trash, Fire, Battery, Solar - all capacity based - based
rates should be search based on sizes dueing billing; if rate is not found then
you assum it zero and calculate instead of refusing the bill"*, and *"i want
tracbility -> billing -> account -> unit -> plan -> rate schedule -> base
charge -> size and amount"*, and the scope: *"im talking this in terms of one
time bill and bulk bill both"*.

THE WORKED FIGURES (made-up demo prices) and the case that asserts each:

  * trash, 2 × CART-96, BASE-T CART-96 $3.00, carts $15.00 → ONE line $36.00
    (`test_a`);
  * the same with NO CART-96 row on BASE-T → base $0.00, line $30.00, a named
    warning, and the account is NOT refused (`test_b`);
  * solar, 2 panels of size A + 1 of size B, base A $2.00 / B $3.00 → base
    $7.00, the kW usage line unchanged (`test_c`);
  * a first bill from day 16 of 30 → base and cart both × 15/30 (`test_d`);
  * the same account through the bulk run and an interim one-time bill → the
    same base (`test_e`).

Fire's `$84.00` (6" × 1 + 2" × 2, seeded base $0.00) is asserted unchanged by
`tests/test_cr063_c3_fire_priced.py`, which this change runs green.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import bill_warnings, check_taxonomy, gather, one_time, one_time_answer, runs
from apps.billing import models as billing_models
from apps.rating import models as rating_models

from tests.test_br_cus_068_master_bill import _by_service
from tests.test_cr062_d1_installed_capacity_sums import _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)
SEP_START, SEP_END = date(2026, 9, 1), date(2026, 9, 30)
PER_CART = Decimal("15.000000")
PER_KW = Decimal("14.000000")


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` — an interim bill for an account on no billing cycle is
    refused. The unit here IS on a cycle; only the cycle's NAME is supplied
    through the seam the refusal reads, as `test_b4_missing_base_bills_zero_
    with_warning.py` does, so no figure here moves."""
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


def _price_by_size(tenant, service, code, amounts):
    """Turn the world's flat `is_base` code into a PER-SIZE code named `code`
    stating `amounts` ({size: Decimal}). Rows written directly: this file is
    about what BILLING reads, not the charge-code screen (whose redesign is on
    a PO hold)."""
    charge = rating_models.Charge.objects.get(
        tenant=tenant, is_base=True, service__code=service, deleted_at__isnull=True
    )
    charge.code = code
    charge.amount = None
    charge.save(update_fields=["code", "amount"])
    for size, amount in amounts.items():
        rating_models.ChargeCodeAmount.objects.create(
            tenant=tenant, charge=charge, size_class=size, amount=amount
        )
    return charge


def _trash(dana, brazos, tag, *, carts=("CART-96", "CART-96"), amounts=None):
    cycle, unit, account = _world(
        dana,
        brazos,
        cycle_code=tag,
        code="trash",
        kind="container_cart",
        uom="cart",
        rate=PER_CART,
        specs=carts,
    )
    _price_by_size(
        brazos, "trash", "BASE-T", amounts if amounts is not None else {"CART-96": Decimal("3.00")}
    )
    return cycle, unit, account


def _prepare(cycle, *, start=AUG_START, end=AUG_END):
    return runs.prepare_run(cycle_id=cycle.id, period_start=start, period_end=end, service_date=end)


def _calculate(tenant, cycle, data, tag, *, start=AUG_START, end=AUG_END):
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=start, period_end=end, idempotency_key=tag
    )
    return runs.calculate_account(data, bill_run=run, service_date=end)


def _lines(invoice, service):
    return [
        line
        for line in invoice.lines.all().order_by("created_at", "id")
        if line.service_id and line.service.code == service and line.kind in ("usage", "base")
    ]


# ══════════════════════════════════════════════════════════════════════════
# THE WORKED FIGURES
# ══════════════════════════════════════════════════════════════════════════


def test_a__two_96_gallon_carts_bill_36_on_one_line_and_the_line_keeps_its_chain(brazos, dana):
    """2 × ($15.00 + $3.00) = **$36.00** on ONE line, and the line stores the
    chain as VALUES: base code, plan, version, customer type, size, count,
    base each, base total, price each."""
    with tenant_ctx(brazos):
        cycle, unit, account = _trash(dana, brazos, "CAP-A")
        prepared = _prepare(cycle)
        assert prepared.ready, [str(b) for b in prepared.blocked]
        data = prepared.ready[0]
        invoice = _calculate(brazos, cycle, data, "cap-a")
        lines = _lines(invoice, "trash")

    assert _by_service(invoice)["trash"] == Decimal("36.00")
    assert len(lines) == 1, [(l.kind, l.description, l.amount) for l in lines]
    trace = lines[0].pricing_trace
    assert trace is not None, "a new bill line must record the chain it was priced from"
    assert trace["base_code"] == "BASE-T"
    assert trace["customer_type"] == "residential"
    assert trace["unit_label"] == "Unit 1"
    assert trace["plan_name"] == data.rate_plan_name
    assert trace["plan_version"] == data.rate_plan_version
    assert trace["rate_schedule_version_id"] == str(lines[0].tariff_version_id)
    assert trace["sizes"] == [
        {
            "size": "CART-96",
            "size_label": trace["sizes"][0]["size_label"],
            "count": 2,
            "base_each": "3.0000",
            "base_total": "6.0000",
            "base_priced": True,
            "price_each": "15.0000",
        }
    ]
    assert "96" in (trace["sizes"][0]["size_label"] or "")


def test_b__no_cart_96_price_bills_the_base_at_zero_warns_and_is_not_refused(brazos, dana):
    """BASE-T prices CART-64 only. Two CART-96 carts: base **$0.00**, line
    **$30.00**, the warning *"BASE-T has no price for CART-96 · billed $0.00"*,
    and the account is READY — never refused.

    RED on the tip before this change: the account was BLOCKED with
    `plan_has_no_tariff_for_service` — *"BASE-T has no price for CART-96.
    Price it on the charge code."*
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _trash(
            dana, brazos, "CAP-B", amounts={"CART-64": Decimal("2.00")}
        )
        prepared = _prepare(cycle)
        assert prepared.ready, [
            (getattr(b, "reason", None), str(getattr(b, "detail", b))[:200])
            for b in prepared.blocked
        ]
        data = prepared.ready[0]
        invoice = _calculate(brazos, cycle, data, "cap-b")
        lines = _lines(invoice, "trash")

    assert _by_service(invoice)["trash"] == Decimal("30.00")
    warned = [w for w in data.warnings if w["key"] == bill_warnings.BASE_SIZE_NOT_PRICED]
    assert len(warned) == 1
    assert {k: warned[0]["params"][k] for k in ("code", "size", "service_code")} == {
        "code": "BASE-T",
        "size": "CART-96",
        "service_code": "trash",
    }
    assert check_taxonomy.warning_code(warned[0]) == check_taxonomy.WARN_BASE_SIZE_NOT_PRICED
    assert check_taxonomy.severity_of(check_taxonomy.WARN_BASE_SIZE_NOT_PRICED) == (
        check_taxonomy.WARNING
    )
    size = lines[0].pricing_trace["sizes"][0]
    assert (size["count"], size["base_each"], size["base_priced"]) == (2, "0.0000", False)


def test_c__solar_base_is_two_times_two_plus_one_times_three_and_usage_is_unchanged(brazos, dana):
    """2 × SOL-P2 + 1 × SOL-P4, base SOL-P2 $2.00 / SOL-P4 $3.00 → base
    **$7.00**. The usage line is priced on the SUMMED capacity, 2+2+4 = 8 kW at
    $14.00 = **$112.00**, exactly as before.

    RED on the tip before this change: the account was REFUSED — the panels
    disagree about one connection size, so the per-size code was asked for
    size `None` and answered *"This connection's size is not recorded."*
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="CAP-C",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=("SOL-P2", "SOL-P2", "SOL-P4"),
        )
        _price_by_size(
            brazos, "solar", "BASE-SOL", {"SOL-P2": Decimal("2.00"), "SOL-P4": Decimal("3.00")}
        )
        prepared = _prepare(cycle)
        assert prepared.ready, [
            (getattr(b, "reason", None), str(getattr(b, "detail", b))[:200])
            for b in prepared.blocked
        ]
        invoice = _calculate(brazos, cycle, prepared.ready[0], "cap-c")
        lines = _lines(invoice, "solar")

    usage = [line for line in lines if line.kind == "usage"]
    base = [line for line in lines if line.kind == "base"]
    assert [(u.quantity, u.unit, u.amount) for u in usage] == [
        (Decimal("8.000000"), "kW", Decimal("112.000000"))
    ]
    assert [b.amount for b in base] == [Decimal("7.000000")]
    assert invoice.total == Decimal("119.00")
    sizes = base[0].pricing_trace["sizes"]
    assert [(s["size"], s["count"], s["base_each"], s["base_total"]) for s in sizes] == [
        ("SOL-P2", 2, "2.0000", "4.0000"),
        ("SOL-P4", 1, "3.0000", "3.0000"),
    ]
    assert base[0].pricing_trace["base_by_size"] is True


def test_c2__a_flat_solar_base_is_still_charged_once(brazos, dana):
    """Lane judgment (decision log 2026-10-01): a FLAT base code names no
    size, so it is not multiplied by the panel count — the summing services'
    existing bills do not move. Flat $5.00, three panels → base **$5.00**."""
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana,
            brazos,
            cycle_code="CAP-C2",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=("SOL-P2", "SOL-P2", "SOL-P4"),
        )
        rating_models.Charge.objects.filter(
            tenant=brazos, is_base=True, service__code="solar"
        ).update(amount=Decimal("5.00"))
        prepared = _prepare(cycle)
        assert prepared.ready
        invoice = _calculate(brazos, cycle, prepared.ready[0], "cap-c2")
        base = [line for line in _lines(invoice, "solar") if line.kind == "base"]

    assert [b.amount for b in base] == [Decimal("5.000000")]


def test_d__a_first_bill_from_day_16_of_30_cuts_base_and_carts_by_15_over_30(brazos, dana):
    """Account opened 16 September: 15 of September's 30 days. Base 2 × $3.00
    × 15/30 = $3.00, carts 2 × $15.00 × 15/30 = $15.00, ONE line **$18.00**."""
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        cycle, _unit, account = _trash(dana, brazos, "CAP-D")
        customer_models.Account.objects.filter(pk=account.pk).update(
            opened_at=date(2026, 9, 16)
        )
        prepared = _prepare(cycle, start=SEP_START, end=SEP_END)
        assert prepared.ready, [str(b) for b in prepared.blocked]
        data = prepared.ready[0]
        assert (data.service_days, data.cycle_days) == (15, 30)
        invoice = _calculate(brazos, cycle, data, "cap-d", start=SEP_START, end=SEP_END)
        lines = _lines(invoice, "trash")

    assert _by_service(invoice)["trash"] == Decimal("18.00")
    assert lines[0].pricing_trace["service_days"] == 15
    assert lines[0].pricing_trace["cycle_days"] == 30


def test_e__the_bulk_run_and_an_interim_one_time_bill_give_the_same_base(brazos, dana):
    """ONE lookup for both pricing paths (PO: *"one time bill and bulk bill
    both"*). The same account, the same month, through the bulk run's gather
    and through an interim one-time bill: the same base per size, the same
    $36.00 line."""
    with tenant_ctx(brazos):
        cycle, _unit, account = _trash(dana, brazos, "CAP-E")
        prepared = _prepare(cycle)
        bulk = prepared.ready[0]
        request = one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=AUG_START,
            period_end=AUG_END,
            due_days=21,
        )
        captured: dict = {}
        internal = one_time.preview(request, capture=captured)
        assert internal["priced"] is True, internal.get("priced_unavailable")
        # The one-time screen's own answer (`api.one_time_preview`'s body).
        body = one_time_answer.preview_answer(request, internal=internal, captured=captured)
        one_time_data = captured["data"]

    # The SAME lookup produced both: the interim bill's gathered trace is the
    # bulk run's, size for size and cent for cent.
    assert one_time_data.pricing_trace["trash"]["sizes"] == bulk.pricing_trace["trash"]["sizes"]
    trash = [
        line
        for group in body["bill"]["groups"]
        for line in group["lines"]
        if line["service"] == "trash"
    ]
    assert [Decimal(line["amount"]) for line in trash] == [Decimal("36.00")]
    bulk_sizes = bulk.pricing_trace["trash"]["sizes"]
    assert trash[0]["breakdown"] == [
        {
            "size": row["size"],
            "size_label": row["size_label"],
            "count": row["count"],
            "base_each": row["base_each"],
            "price_each": row["price_each"],
            "base_priced": row["base_priced"],
        }
        for row in bulk_sizes
    ]
    assert [(r["count"], r["base_each"]) for r in trash[0]["breakdown"]] == [(2, "3.0000")]


def test_f__a_metered_service_with_an_unpriced_size_still_refuses():
    """The ruling names CAPACITY services. A water connection whose size the
    base code does not price is still refused — `_interpret_base_answer` zeroes
    only where `capacity_service_codes` holds the service."""
    answer = {
        "amount": None,
        "code": "BASE-W-SIZED",
        "refusal": "BASE-W-SIZED has no price for W-58. Price it on the charge code.",
        "refusal_reason": gather.SIZE_NOT_PRICED,
        "size_class": "W-58",
        "per_size": True,
    }
    from unittest import mock

    with mock.patch.object(gather, "_is_capacity_service", return_value=False):
        with pytest.raises(gather.GatherProblem) as refusal:
            gather._interpret_base_answer("water", answer)
    assert "has no price for W-58" in str(refusal.value)
    with mock.patch.object(gather, "_is_capacity_service", return_value=True):
        assert gather._interpret_base_answer("trash", answer) == (Decimal("0.0000"), "BASE-W-SIZED")
