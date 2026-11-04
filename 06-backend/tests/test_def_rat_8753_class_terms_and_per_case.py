# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-8753 — the two pricings the PO-approved charge-code mock-up
#           draws and wave B could not store (CR-156-BRC10 wave C).
# Images:   05-prototype/charge-codes-2026-10-01/images 31, 61, 67, 77 (LATE by
#           customer class) · 41, 64, 70 (an amount entered when used).
# Rules:    BR-RAT-1053 · BR-RAT-1054 · BR-BIL-001 · BR-RAT-1011 · CR-010 A2
# Run:      sqlite (default suite) AND, for the late-fee figures,
#             DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
#             DATABASE_URL=postgres://… pytest tests/test_def_rat_8753_class_terms_and_per_case.py
# ───────────────────────────────────────────────────────
"""A penalty priced BY CUSTOMER CLASS, and a fee whose amount is ENTERED WHEN USED.

WHAT EACH CASE HAS TO PROVE
---------------------------
1. **The late fee uses the account's CLASS percent and minimum** — the worked
   figures the coordinator put with the defect, on the mock-up's `LATE`
   (Residential 1.50% min $5.00, Commercial 2.00% min $10.00):
     * Residential, $200.00 overdue → max(1.50% × 200 = $3.00, $5.00) = **$5.00**
     * Commercial, $2,000.00 overdue → max(2.00% × 2,000 = $40.00, $10.00) = **$40.00**
   Asserted through `assess_late_fee_for_plan`, the production entry point, on
   a real plan pointed at a real code — and on PostgreSQL too, because the terms
   rows sit under the no-overlap exclusion constraint SQLite cannot hold.
2. **The seeded single-percent `LATE` is untouched** — GT-8's ❄️ $8.13 on the
   same path. A code with no class rows reads its own two columns.
3. **A class the code does not price is REFUSED, never charged zero.**
4. **Class terms are dated and logically killed** like every price row.
5. **`per_case` states no price**; a fee bill takes the clerk's amount for it,
   refuses one missing, and refuses an entered amount beside any other code
   (BR-BIL-020 holds for every code that states its own price).

WHAT WOULD MAKE THIS PASS WRONGLY: a fee path that ignored the class and
charged the code's single percent would still produce $5.00 for the Residential
case (1.5% of 200 is under the $5.00 floor either way) — so the Commercial case
is the one that bites: on the single percent it is max(1.5% × 2,000, $5.00) =
$30.00, not $40.00.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import fee_bill, late_fee
from apps.billing.exceptions import BillingRuleError
from apps.rating import charge_prices, models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

DUE_DATE = dt.date(2026, 7, 15)
AS_OF = dt.date(2026, 7, 21)  # six calendar days past due, five days' grace
GRACE_DAYS = 5
GRACE_MODE = "calendar"
FROM = dt.date(2026, 1, 1)


def _late_by_class(tenant, actor, code="LATE-CL"):
    """The mock-up's LATE, priced by class, from 2026-01-01."""
    with tenant_ctx(tenant):
        seeded = rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True)
        return rating_services.create_charge(
            actor,
            {
                "code": code,
                "name": "Late payment",
                "charge_type": "penalty",
                "kind": "plan",
                "amount_rule": "percent_with_minimum",
                "percent": None,
                "min_amount": None,
                "gl_account_id": str(seeded.gl_account_id) if seeded.gl_account_id else None,
                "effective_from": FROM.isoformat(),
                "class_terms": [
                    {"customer_class": "residential", "percent": "0.015", "min_amount": "5.00"},
                    {"customer_class": "commercial", "percent": "0.020", "min_amount": "10.00"},
                ],
            },
        )


def _plan_on(tenant, charge_id, name="Class late plan"):
    plan = make_plan(tenant, name=name, code=name.lower().replace(" ", "-"))
    with tenant_ctx(tenant):
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge_id=charge_id)
    return plan


def _fee(plan, overdue, customer_class):
    return late_fee.assess_late_fee_for_plan(
        rate_plan_id=plan.id,
        overdue_amount=Decimal(overdue),
        due_date=DUE_DATE,
        as_of=AS_OF,
        grace_days=GRACE_DAYS,
        grace_mode=GRACE_MODE,
        customer_class=customer_class,
    )


# ── 1 · the worked figures ──────────────────────────────────────────────────


def test_residential_200_pays_the_5_minimum_and_commercial_2000_pays_40(brazos, dana):
    row = _late_by_class(brazos, dana)
    plan = _plan_on(brazos, row["id"])
    with tenant_ctx(brazos):
        residential, terms_r = _fee(plan, "200.00", "residential")
        commercial, terms_c = _fee(plan, "2000.00", "commercial")
    # max(1.50% × 200 = 3.00, 5.00)
    assert residential == Decimal("5.00")
    assert terms_r.percent == Decimal("0.015") and terms_r.minimum == Decimal("5.00")
    # max(2.00% × 2,000 = 40.00, 10.00) — on the single 1.5% it would be 30.00
    assert commercial == Decimal("40.00"), (
        "the Commercial account must pay ITS class's 2.00% — $30.00 here means the "
        "fee read one percent for every class"
    )
    assert terms_c.percent == Decimal("0.020") and terms_c.minimum == Decimal("10.00")


# ── 2 · the frozen figure does not move ─────────────────────────────────────


def test_the_seeded_single_percent_late_code_still_charges_gt8s_8_13(brazos):
    plan = make_plan(brazos, name="Seeded late plan", code="seeded-late-plan")
    with tenant_ctx(brazos):
        seeded = rating_models.Charge.objects.get(tenant=brazos, code="LATE", deleted_at__isnull=True)
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=seeded)
        for cls in ("residential", "commercial", None):
            fee, terms = _fee(plan, "542.10", cls)
            assert fee == Decimal("8.13"), cls
            assert terms.percent == Decimal("0.015")


# ── 3 · a class the code does not price ─────────────────────────────────────


def test_a_class_the_code_does_not_price_is_refused_not_charged_zero(brazos, dana):
    row = _late_by_class(brazos, dana)
    plan = _plan_on(brazos, row["id"])
    with tenant_ctx(brazos):
        with pytest.raises(late_fee.LateFeeClassNotPriced):
            _fee(plan, "2000.00", "industrial")


# ── 4 · dated and logically killed ──────────────────────────────────────────


def test_class_terms_are_served_dated_and_a_change_kills_the_old_row(brazos, dana):
    row = _late_by_class(brazos, dana)
    assert [(t["customer_class"], t["percent_display"], t["min_amount_display"]) for t in row["class_terms"]] == [
        ("commercial", "2.00%", "10.00"),
        ("residential", "1.50%", "5.00"),
    ]
    with tenant_ctx(brazos):
        rating_services.update_charge(
            dana,
            row["id"],
            {
                "effective_from": "2026-11-01",
                "reason": "Board approved the new commercial rate",
                "class_terms": [
                    {"customer_class": "residential", "percent": "0.015", "min_amount": "5.00"},
                    {"customer_class": "commercial", "percent": "0.025", "min_amount": "10.00"},
                ],
            },
        )
        old = charge_prices.class_terms_on(row["id"], "commercial", dt.date(2026, 10, 31))
        new = charge_prices.class_terms_on(row["id"], "commercial", dt.date(2026, 11, 1))
        res = charge_prices.class_terms_on(row["id"], "residential", dt.date(2026, 11, 1))
        rows = rating_selectors.charge_row(rating_models.Charge.objects.get(pk=row["id"]))["prices"]
        versions = rating_selectors.charge_versions(rating_models.Charge.objects.get(pk=row["id"]))
    # The Audit tab reads the move in the class's own terms, not "Not priced".
    moved = [c for v in versions for c in v["changes"] if c["customer_class"] == "commercial" and not c["new"]]
    assert [(c["before_display"], c["after_display"], c["terms"]) for c in moved] == [
        ("2.00% · $10.00", "2.50% · $10.00", True)
    ]
    assert old.percent == Decimal("0.020") and new.percent == Decimal("0.025")
    assert res.percent == Decimal("0.015")
    commercial = [r for r in rows if r["customer_class"] == "commercial"]
    assert len(commercial) == 2
    closed = next(r for r in commercial if r["killed"])
    assert closed["effective_to"] == "2026-10-31"
    # Residential was unchanged: one row, never killed.
    assert [r["killed"] for r in rows if r["customer_class"] == "residential"] == [False]


def test_terms_rows_do_not_read_as_an_unpriced_amount(brazos, dana):
    row = _late_by_class(brazos, dana)
    assert row["size_amounts"] == []
    assert row["price_range"] is None
    with tenant_ctx(brazos):
        assert charge_prices.flat_amount(row["id"], FROM) is None


def test_a_class_twice_and_terms_on_a_flat_code_are_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            rating_services.create_charge(
                dana,
                {
                    "code": "LATE-X",
                    "name": "x",
                    "amount_rule": "percent_with_minimum",
                    "class_terms": [
                        {"customer_class": "residential", "percent": "0.01"},
                        {"customer_class": "residential", "percent": "0.02"},
                    ],
                },
            )
        with pytest.raises(errors.ValidationError):
            rating_services.create_charge(
                dana,
                {
                    "code": "FLAT-X",
                    "name": "x",
                    "amount_rule": "flat",
                    "amount": "5.00",
                    "class_terms": [{"customer_class": "residential", "percent": "0.01"}],
                },
            )


# ── 5 · entered when used ───────────────────────────────────────────────────


def _per_case(tenant, actor, code="TAP-X"):
    with tenant_ctx(tenant):
        seeded = rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True)
        return rating_services.create_charge(
            actor,
            {
                "code": code,
                "name": "Tap fee",
                "charge_type": "one_time",
                "kind": "other",
                "amount_rule": "per_case",
                "gl_account_id": str(seeded.gl_account_id),
                "effective_from": FROM.isoformat(),
            },
        )


def test_a_per_case_code_saves_with_no_price_and_refuses_one(brazos, dana):
    row = _per_case(brazos, dana)
    assert row["amount_rule"] == "per_case"
    assert row["amount"] is None and row["prices"] == [] and row["price_range"] is None
    # ⚠ AMENDED 2026-10-06 (`BR-RAT-1054`, PO option (a), `DEF-RAT-9807`): a
    # posted flat `amount` is now the code's optional DEFAULT and is accepted
    # (`test_def_rat_9805_9807_charge_code_rulings.py`); a SIZE TABLE beside
    # `per_case` is still two answers to one question and still refused.
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            rating_services.create_charge(
                dana,
                {
                    "code": "TAP-Y",
                    "name": "x",
                    "amount_rule": "per_case",
                    "size_amounts": [{"size_class": "W-1", "amount": "250.00"}],
                },
            )


def test_moving_a_flat_code_to_per_case_kills_its_price(brazos, dana):
    with tenant_ctx(brazos):
        flat = rating_services.create_charge(
            dana,
            {
                "code": "IMP-X",
                "name": "Impact fee",
                "amount_rule": "flat",
                "amount": "100.00",
                "effective_from": FROM.isoformat(),
            },
        )
        after = rating_services.update_charge(
            dana,
            flat["id"],
            {"amount_rule": "per_case", "amount": None, "size_amounts": [], "effective_from": "2026-11-01"},
        )
    assert after["amount_rule"] == "per_case"
    assert [(p["amount_display"], p["killed"], p["effective_to"]) for p in after["prices"]] == [
        ("100.00", True, "2026-10-31")
    ]


def test_a_fee_bill_takes_the_entered_amount_for_a_per_case_code_only(brazos, dana):
    _per_case(brazos, dana)
    with tenant_ctx(brazos):
        line = fee_bill.charge_code_line("TAP-X", entered_amount=Decimal("1250.00"))
        assert line.amount == Decimal("1250.00")
        with pytest.raises(BillingRuleError, match="no amount was entered"):
            fee_bill.charge_code_line("TAP-X")
        with pytest.raises(BillingRuleError, match="positive"):
            fee_bill.charge_code_line("TAP-X", entered_amount=Decimal("-5"))
        # BR-BIL-020 — a code that states its own price takes no typed figure.
        flat_code = (
            rating_models.Charge.objects.filter(
                tenant=brazos, amount_rule="flat", deleted_at__isnull=True, gl_account_id__isnull=False
            )
            .exclude(code="TAP-X")
            .values_list("code", flat=True)
            .first()
        )
        if flat_code is not None and rating_selectors.charge_by_code(flat_code)["amount"] is not None:
            with pytest.raises(BillingRuleError, match="BR-BIL-020|no amount may be typed"):
                fee_bill.charge_code_line(flat_code, entered_amount=Decimal("1.00"))


@pytest.mark.skipif(connection.vendor != "postgresql", reason="the exclusion constraint is PostgreSQL's")
def test_on_postgresql_the_terms_rows_live_under_the_no_overlap_constraint(brazos, dana):
    row = _late_by_class(brazos, dana)
    # Built before the context below: `_plan_on` opens and closes its own.
    plan = _plan_on(brazos, row["id"], name="PG class late plan")
    with tenant_ctx(brazos):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_constraint WHERE conname = %s",
                ["ck_charge_code_amounts_amount_or_terms"],
            )
            assert cursor.fetchone()[0] == 1
        assert _fee(plan, "200.00", "residential")[0] == Decimal("5.00")
        assert _fee(plan, "2000.00", "commercial")[0] == Decimal("40.00")


def test_the_one_time_door_carries_the_entered_amount_to_the_request():
    """The wave-C walk found it: the screen's preview body is read by
    `one_time_answer.request_from`, and an entered amount that stopped there
    never reached `fee_bill` (hard-won law 2 — built is not wired)."""
    from apps.billing import one_time_answer

    body = {"kind": "fee", "account_id": "a", "charge_code": "TAP", "bill_date": "2026-10-01", "due_days": 21}
    assert one_time_answer.request_from({**body, "entered_amount": "1250.00"}).entered_amount == Decimal("1250.00")
    assert one_time_answer.request_from(body).entered_amount is None
    fields = [p["field"] for p in one_time_answer.problems_in({**body, "entered_amount": "twelve"})]
    assert "entered_amount" in fields
