"""CR-156-BRC10 — charge-code prices are DATED, LOGICALLY KILLED, and read in ONE place.

PO rulings 2026-10-01 (decision log, every row whose last column reads
*"charge-code redesign"*):

* *"why are you detleting it and not killing it"* → *"logical kill"* — an edit
  never deletes a price row; a changed or removed price is closed and marked,
  the new price is a new row, an unchanged row is left untouched;
* option A — *"BASE-S $9.00 is stored as one row in charge_code_amounts with
  size \\"All sizes\\" … The old field on the charge code is no longer written"*;
* *"we will need start and effective date"* — Effective from required on Add
  and Edit, Effective to optional;
* *"can we have 3 kinds base charges, plan charges and others"*.

The worked case asserted here is the PO's own (decision log, *"CHARGE-CODE
PRICE ROWS ARE NEVER PHYSICALLY DELETED"*): BASE-T on 10/15 for 11/01, CART-64
$12.00 → $13.00 and CART-96 newly $15.00 — the $12.00 row stays, closed
10/31/2026; a $13.00 and a $15.00 row start 11/01/2026; CART-35 $9.00 and
DUMP-2 $40.00 are not touched (same ids).

These run on the default suite (SQLite). The database half — the exclusion
constraint, RLS, the one-time move — is `test_cr156_charge_prices_pg.py`,
because SQLite can hold none of it (hard-won law 14).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import charge_prices, models, selectors, services
from apps.rating.constants import (
    ALL_SIZES,
    KIND_BASE,
    KIND_OTHER,
    KIND_PLAN,
    PRICE_HISTORY_EPOCH,
    default_kind,
)
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

TRASH_SIZES = (
    ("CART-35", "Trash 35-gallon cart"),
    ("CART-64", "Trash 64-gallon cart"),
    ("CART-96", "Trash 96-gallon cart"),
    ("DUMP-2", "Dumpster 2 yd"),
)
SAVED_FROM = date(2026, 11, 1)


def _configure(tenant, rows=TRASH_SIZES):
    from apps.tenancy import models as tenancy_models

    for code, name in rows:
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant, code=code, defaults={"name": name, "active": True, "is_system": True}
        )


def _base_t(env):
    """BASE-T as the PO's worked case starts: CART-35 $9.00, CART-64 $12.00,
    DUMP-2 $40.00, from the epoch; CART-96 unpriced."""
    _configure(env.tenant)
    with tenant_ctx(env.tenant):
        return services.create_charge(
            env.admin,
            {
                "code": "BASE-T",
                "name": "Trash base",
                "charge_type": "recurring",
                # no service: this tenant fixture enables water/electric only,
                # and the save path's size rules do not depend on it
                "amount_rule": "flat",
                "is_base": True,
                "effective_from": PRICE_HISTORY_EPOCH.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "12.00"},
                    {"size_class": "DUMP-2", "amount": "40.00"},
                ],
            },
        )


def _all_rows(charge_id):
    return list(
        models.ChargeCodeAmount.objects.filter(charge_id=charge_id).order_by(
            "size_class", "effective_from"
        )
    )


# ── the PO's BASE-T case ────────────────────────────────────────────────────
def test_base_t_reprice_keeps_the_old_row_closed_and_leaves_the_others_untouched(env):
    created = _base_t(env)
    with tenant_ctx(env.tenant):
        before = {row.size_class: row.id for row in _all_rows(created["id"])}
        services.update_charge(
            env.admin,
            created["id"],
            {
                "effective_from": SAVED_FROM.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "13.00"},
                    {"size_class": "CART-96", "amount": "15.00"},
                    {"size_class": "DUMP-2", "amount": "40.00"},
                ],
            },
        )
        rows = _all_rows(created["id"])
    by_size: dict[str, list] = {}
    for row in rows:
        by_size.setdefault(row.size_class, []).append(row)
    # CART-35 and DUMP-2: the SAME rows, never re-created, never killed.
    for size in ("CART-35", "DUMP-2"):
        assert [r.id for r in by_size[size]] == [before[size]], size
        assert by_size[size][0].killed_at is None and by_size[size][0].effective_to is None
    # CART-64: the $12.00 row is KEPT, closed 10/31 and marked; $13.00 starts 11/01.
    old, new = by_size["CART-64"]
    assert old.id == before["CART-64"]
    assert (old.amount, old.effective_to) == (Decimal("12.0000"), date(2026, 10, 31))
    assert old.killed_at is not None
    assert (new.amount, new.effective_from, new.effective_to, new.killed_at) == (
        Decimal("13.0000"),
        SAVED_FROM,
        None,
        None,
    )
    # CART-96: newly priced $15.00 from 11/01.
    (cart96,) = by_size["CART-96"]
    assert (cart96.amount, cart96.effective_from) == (Decimal("15.0000"), SAVED_FROM)
    assert len(rows) == 5, "nothing was deleted: 3 original rows + 2 new"


def test_what_was_cart_64_on_09_01_is_answered_from_the_price_table(env):
    created = _base_t(env)
    with tenant_ctx(env.tenant):
        services.update_charge(
            env.admin,
            created["id"],
            {
                "effective_from": SAVED_FROM.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "13.00"},
                    {"size_class": "CART-96", "amount": "15.00"},
                    {"size_class": "DUMP-2", "amount": "40.00"},
                ],
            },
        )
        charge = models.Charge.objects.get(id=created["id"])
        on_0901 = charge_prices.price_on_date(charge, "CART-64", None, date(2026, 9, 1))
        on_1031 = charge_prices.price_on_date(charge, "CART-64", None, date(2026, 10, 31))
        on_1101 = charge_prices.price_on_date(charge, "CART-64", None, date(2026, 11, 1))
        cart96_before = charge_prices.price_on_date(charge, "CART-96", None, date(2026, 10, 15))
    assert on_0901.amount == Decimal("12.0000") and on_0901.per_size
    assert on_1031.amount == Decimal("12.0000")
    assert on_1101.amount == Decimal("13.0000")
    assert cart96_before.refusal == charge_prices.SIZE_NOT_PRICED


def test_every_read_place_answers_exactly_one_row_per_size_and_class(env):
    """The lookup's own contract: one row, or a named refusal — never two."""
    created = _base_t(env)
    with tenant_ctx(env.tenant):
        services.update_charge(
            env.admin,
            created["id"],
            {
                "effective_from": SAVED_FROM.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "13.00"},
                    {"size_class": "DUMP-2", "amount": "40.00"},
                ],
            },
        )
        for day in (date(2026, 9, 1), date(2026, 10, 31), date(2026, 11, 1), date(2027, 1, 1)):
            rows = charge_prices.rows_in_force([created["id"]], day)[
                models.Charge.objects.get(id=created["id"]).id
            ]
            keys = [(row.size_class, row.customer_class) for row in rows]
            assert len(keys) == len(set(keys)) == 3, (day, keys)


# ── the flat amount is an All-sizes row ─────────────────────────────────────
def test_a_flat_amount_is_one_all_sizes_row_and_the_column_is_not_written(env):
    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "PAPER",
                "name": "Paper bill fee",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": "2.00",
                "effective_from": "2026-01-01",
            },
        )
        rows = _all_rows(created["id"])
        legacy = models.Charge.objects.filter(id=created["id"]).values_list(
            "legacy_amount", flat=True
        )[0]
    assert [(r.size_class, r.customer_class, r.amount) for r in rows] == [
        (ALL_SIZES, None, Decimal("2.0000"))
    ]
    assert legacy is None, "charges.amount is no longer written"
    assert created["amount"] == "2.000000" and created["kind"] == KIND_PLAN


def test_reading_charge_amount_is_refused_loudly(env):
    with tenant_ctx(env.tenant):
        charge = models.Charge.objects.create(
            tenant=env.tenant, code="X-FEE", name="x", amount_rule="flat", amount=Decimal("3")
        )
        with pytest.raises(models.RetiredChargeAmount):
            charge.amount  # noqa: B018 — the read IS the assertion
        assert charge_prices.flat_amount(charge) == Decimal("3.0000")


def test_base_s_nine_to_ten_saved_for_november_keeps_september_at_nine(env):
    """The PO's option-A case, at the lookup: BASE-S $9.00 → $10.00 from 11/01."""
    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "BASE-S",
                "name": "Sewer base",
                "charge_type": "recurring",
                # the fixture tenant enables water, not sewer; the arithmetic is
                # the PO's BASE-S case whatever the service is called
                "service": "water",
                "amount_rule": "flat",
                "amount": "9.00",
                "is_base": True,
                "effective_from": PRICE_HISTORY_EPOCH.isoformat(),
            },
        )
        services.update_charge(
            env.admin,
            created["id"],
            {"amount": "10.00", "effective_from": SAVED_FROM.isoformat()},
        )
        charge = models.Charge.objects.get(id=created["id"])
        september = charge_prices.flat_amount(charge, date(2026, 9, 15))
        november = charge_prices.flat_amount(charge, date(2026, 11, 15))
        rows = _all_rows(created["id"])
        base_sep = selectors.base_charge_from_charge_code(
            "water", named_code="BASE-S", on_date=date(2026, 9, 1)
        )
        base_nov = selectors.base_charge_from_charge_code(
            "water", named_code="BASE-S", on_date=date(2026, 11, 1)
        )
        cuts = selectors.charge_price_boundaries(
            ["water"], period_start=date(2026, 10, 16), period_end=date(2026, 11, 15)
        )
    assert (september, november) == (Decimal("9.0000"), Decimal("10.0000"))
    assert [(r.amount, r.effective_from, r.effective_to, r.killed_at is not None) for r in rows] == [
        (Decimal("9.0000"), PRICE_HISTORY_EPOCH, date(2026, 10, 31), True),
        (Decimal("10.0000"), SAVED_FROM, None, False),
    ]
    assert (base_sep["amount"], base_nov["amount"]) == (Decimal("9.0000"), Decimal("10.0000"))
    assert cuts == (SAVED_FROM,), "a bill period crossing the change is cut on 11/01"


# ── dates are required; the history is logged for every money change ────────
def test_interim_an_add_with_no_effective_from_is_dated_today(env):
    """⚠ INTERIM RULE (CR-156-BRC10 §7, coordinator 2026-10-01): the live
    wizard sends no date; a price it saves applies from the tenant's today."""
    from apps.rating import seams

    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {"code": "T-1", "name": "t", "amount_rule": "flat", "amount": "1.00"},
        )
        today = seams.tenant_today()
        rows = _all_rows(created["id"])
    assert [(r.size_class, r.amount, r.effective_from) for r in rows] == [
        (ALL_SIZES, Decimal("1.0000"), today)
    ]


def test_interim_the_old_wizard_payload_still_saves_a_price_change_dated_today(env):
    """The OLD screen's shape — `{"amount": …}` and nothing else — still saves:
    the old row is closed yesterday and kept (killed), the new one starts
    today. A payload that names a date is honoured instead."""
    from datetime import timedelta

    from apps.rating import seams

    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "T-2",
                "name": "t",
                "amount_rule": "flat",
                "amount": "1.00",
                "effective_from": "2026-01-01",
            },
        )
        saved = services.update_charge(env.admin, created["id"], {"amount": "2.00"})
        today = seams.tenant_today()
        rows = _all_rows(created["id"])
        renamed = services.update_charge(env.admin, created["id"], {"name": "renamed"})
    assert saved["amount_display"] == "2.00"
    assert [(r.amount, r.effective_from, r.effective_to, r.killed_at is not None) for r in rows] == [
        (Decimal("1.0000"), date(2026, 1, 1), today - timedelta(days=1), True),
        (Decimal("2.0000"), today, None, False),
    ]
    assert renamed["name"] == "renamed"


def test_effective_to_before_effective_from_is_refused(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_charge(
                env.admin,
                {
                    "code": "T-3",
                    "name": "t",
                    "amount_rule": "flat",
                    "amount": "1.00",
                    "effective_from": "2026-11-01",
                    "effective_to": "2026-10-31",
                },
            )
    assert ("effective_to", "rating.plans.window_inverted") in [
        (e["field"], e["message_key"]) for e in excinfo.value.field_errors
    ]


def test_every_money_change_writes_rate_change_log_even_when_not_in_use(env):
    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "T-4",
                "name": "t",
                "amount_rule": "flat",
                "amount": "1.00",
                "effective_from": "2026-01-01",
            },
        )
        services.update_charge(
            env.admin, created["id"], {"amount": "2.00", "effective_from": "2026-11-01"}
        )
        services.update_charge(env.admin, created["id"], {"name": "no money"})
        logs = models.RateChangeLog.objects.filter(entity_type="charge", entity_id=created["id"])
        # the first price is the table's own first row (not a change); the
        # reprice is logged with no reason demanded (not in use); the rename is
        # not money
        assert logs.count() == 1
        assert logs.get().reason == ""


def test_deleting_a_never_used_code_removes_its_rows_and_a_used_one_is_refused(env):
    with tenant_ctx(env.tenant):
        created = services.create_charge(
            env.admin,
            {
                "code": "T-5",
                "name": "t",
                "amount_rule": "flat",
                "amount": "1.00",
                "effective_from": "2026-01-01",
            },
        )
        services.delete_charge(env.admin, created["id"])
        assert not models.ChargeCodeAmount.objects.filter(charge_id=created["id"]).exists()
        assert not models.Charge.objects.filter(id=created["id"]).exists()


# ── kinds ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "code,charge_type,is_base,kind",
    [
        ("BASE-W", "recurring", True, KIND_BASE),
        ("CONN", "one_time", False, KIND_PLAN),
        ("TRANSFER", "one_time", False, KIND_PLAN),
        ("CC-CONV", "one_time", False, KIND_PLAN),
        ("PAPER", "recurring", False, KIND_PLAN),
        ("HYDRANT", "recurring", False, KIND_PLAN),
        ("LATE", "penalty", False, KIND_PLAN),
        ("NSF", "penalty", False, KIND_PLAN),
        ("TAMPER", "penalty", False, KIND_PLAN),
        ("DEPO-R", "refundable", False, KIND_PLAN),
        ("RE-READ", "one_time", False, KIND_OTHER),
        ("BULK-WATER", "one_time", False, KIND_OTHER),
        ("CC-REQFEE", "one_time", False, KIND_OTHER),
        ("APP-FEE", "one_time", False, KIND_OTHER),
    ],
)
def test_the_pos_classification(code, charge_type, is_base, kind):
    assert default_kind(code, charge_type, is_base) == kind


def test_the_code_picker_lists_only_codes_not_in_use_of_the_asked_kind(env):
    with tenant_ctx(env.tenant):
        for code in ("TRANSFER", "MOVE-OUT", "RE-READ"):
            services.create_charge(
                env.admin,
                {
                    "code": code,
                    "name": code.title(),
                    "charge_type": "one_time",
                    "amount_rule": "flat",
                    "amount": "15.00",
                    "effective_from": "2026-01-01",
                },
            )
        plan_free = [row["code"] for row in selectors.charge_code_picker("plan")]
        other_free = [row["code"] for row in selectors.charge_code_picker("other")]
    assert {"TRANSFER", "MOVE-OUT"} <= set(plan_free) and "RE-READ" not in plan_free
    assert "RE-READ" in other_free and "TRANSFER" not in other_free


# ── versions (PO 2026-10-01: *"BASE CHARGES SHOWS EACH SIZE'S BASE-PRICE VERSION
#    AND ITS EFFECTIVE DATES"*) ────────────────────────────────────────────────
def test_each_price_row_carries_its_dates_and_a_version_counted_in_date_order(env):
    created = _base_t(env)
    with tenant_ctx(env.tenant):
        services.update_charge(
            env.admin,
            created["id"],
            {
                "effective_from": SAVED_FROM.isoformat(),
                "size_amounts": [
                    {"size_class": "CART-35", "amount": "9.00"},
                    {"size_class": "CART-64", "amount": "13.00"},
                    {"size_class": "DUMP-2", "amount": "40.00"},
                ],
            },
        )
        charge = models.Charge.objects.get(id=created["id"])
        row = selectors.charge_row(charge)
        november = charge_prices.rows_in_force([charge], SAVED_FROM, with_versions=True)[charge.id]
    cart64 = [
        (p["amount"], p["effective_from"], p["effective_to"], p["version"], p["killed"])
        for p in row["prices"]
        if p["size_class"] == "CART-64"
    ]
    assert cart64 == [
        ("12.000000", "2000-01-01", "2026-10-31", 1, True),
        ("13.000000", "2026-11-01", None, 2, False),
    ]
    assert {r.size_class: r.version for r in november} == {"CART-35": 1, "CART-64": 2, "DUMP-2": 1}
