"""CR-156-BRC10 on the only engine that can hold it — PostgreSQL 16.

⚠ **`config/settings/test.py` HARDCODES IN-MEMORY SQLITE AND IGNORES
`DATABASE_URL`** (hard-won law 14). SQLite has no range type, no exclusion
constraint and no row-level security, so every case here skips BY NAME there
rather than passing vacuously. Run it the whole line:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://postgres@127.0.0.1:55433/sbh_a5c?sslmode=disable" \\
      pytest -q --reuse-db tests/test_cr156_charge_prices_pg.py

WHAT IS PROVED HERE, AND WHAT WOULD MAKE EACH PASS WRONGLY (law 7)
-----------------------------------------------------------------
* **The exclusion constraint exists, as written** — read from `pg_constraint`,
  definition included, because `pytest.raises(IntegrityError)` around an
  overlapping INSERT would go green if the INSERT failed for any other reason.
* **It refuses an overlap and ALLOWS the shapes the writer leaves** — a clean
  handover (10/31 → 11/01), a class row beside an every-class row, an EMPTY row
  (closed the day before it started). A constraint that refused those would make
  every reprice impossible and still pass a refusal-only test.
* **RLS**: the altered table is still ENABLE + FORCE, still scoped per tenant,
  and refuses a row stamped for another tenant — under the probe role, because
  a superuser bypasses every policy (`DEF-2717`).
* **The one-time move** (`rating/0051`) moves a flat amount into ONE *All sizes*
  row, clears the column, classifies the kind, and writes nothing on a re-run.
* **The PO's worked bills**, through the real one-time and cycle doors: BASE
  $9.00 → $10.00 effective 11/01 — catch-up 09/01–09/30 **$9.00**, interim
  10/16–11/15 **$4.65 + $5.00 = $9.65**, November **$10.00**.
"""

from __future__ import annotations

import calendar
import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection, transaction

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.rating import charge_prices
from apps.rating import models as rating_models
from apps.rating.constants import ALL_SIZES, PRICE_HISTORY_EPOCH
from core import sample_fixture as fixture

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "charge_code_amounts"
CENT = Decimal("0.01")
NINE, TEN = Decimal("9.00"), Decimal("10.00")
CHANGE = date(2026, 11, 1)


def _code(tenant, code="T-CODE"):
    return rating_models.Charge.objects.create(
        tenant=tenant, code=code, name=code, amount_rule="flat", charge_type="one_time"
    )


def _row(tenant, charge, *, amount="1.00", size=ALL_SIZES, klass=None, start, end=None, killed=False):
    from django.utils import timezone

    return rating_models.ChargeCodeAmount.objects.create(
        tenant=tenant,
        charge=charge,
        size_class=size,
        customer_class=klass,
        amount=Decimal(amount),
        effective_from=start,
        effective_to=end,
        killed_at=timezone.now() if killed else None,
    )


def _refused(fn) -> str:
    try:
        with transaction.atomic():  # a SAVEPOINT — law 14: a failed statement poisons the txn
            fn()
    except IntegrityError as exc:
        return str(exc)
    return ""


# ── the constraint ──────────────────────────────────────────────────────────
@requires_postgres
def test_the_exclusion_constraint_exists_as_written():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ex_charge_code_amounts_no_overlap'"
        )
        row = cursor.fetchone()
    assert row is not None, "rating/0052 did not create the constraint"
    definition = row[0]
    for piece in ("EXCLUDE USING gist", "tenant_id WITH =", "charge_id WITH =",
                  "size_class WITH =", "COALESCE(customer_class, ''::text)", "daterange("):
        assert piece in definition, (piece, definition)


@requires_postgres
def test_two_rows_in_force_on_one_day_are_refused_killed_or_not(brazos):
    with tenant_ctx(brazos):
        charge = _code(brazos)
        _row(brazos, charge, start=PRICE_HISTORY_EPOCH, end=date(2026, 10, 31), killed=True)
        message = _refused(
            lambda: _row(brazos, charge, start=date(2026, 10, 1))  # overlaps 10/01–10/31
        )
    assert "ex_charge_code_amounts_no_overlap" in message, message


@requires_postgres
def test_two_every_class_rows_collide_and_null_is_not_distinct(brazos):
    with tenant_ctx(brazos):
        charge = _code(brazos)
        _row(brazos, charge, start=PRICE_HISTORY_EPOCH, killed=True)
        message = _refused(lambda: _row(brazos, charge, start=date(2026, 1, 1), killed=True))
    assert "ex_charge_code_amounts_no_overlap" in message, message


@requires_postgres
def test_the_shapes_the_writer_leaves_are_allowed(brazos):
    with tenant_ctx(brazos):
        charge = _code(brazos)
        _row(brazos, charge, start=PRICE_HISTORY_EPOCH, end=date(2026, 10, 31), killed=True)
        _row(brazos, charge, start=CHANGE)  # a clean handover
        _row(brazos, charge, klass="residential", start=PRICE_HISTORY_EPOCH)  # class beside every-class
        # superseded before it began: an EMPTY range, overlapping nothing
        _row(brazos, charge, start=date(2027, 1, 1), end=date(2026, 12, 31), killed=True)
        assert rating_models.ChargeCodeAmount.objects.filter(charge=charge).count() == 4


@requires_postgres
def test_a_window_ending_more_than_a_day_before_it_starts_is_refused_by_name(brazos):
    with tenant_ctx(brazos):
        charge = _code(brazos)
        message = _refused(
            lambda: _row(brazos, charge, start=date(2026, 11, 1), end=date(2026, 10, 1))
        )
    assert "ck_charge_code_amounts_window" in message, message


@requires_postgres
def test_the_writer_on_postgres_never_meets_the_constraint(brazos):
    """The BASE-T reprice through the one writer, under the real constraint."""
    with tenant_ctx(brazos):
        charge = _code(brazos, "BASE-T-PG")
        charge_prices.save_prices(
            charge,
            {("CART-35", None): Decimal("9"), ("CART-64", None): Decimal("12"),
             ("DUMP-2", None): Decimal("40")},
            effective_from=PRICE_HISTORY_EPOCH,
            effective_to=None,
        )
        change = charge_prices.save_prices(
            charge,
            {("CART-35", None): Decimal("9"), ("CART-64", None): Decimal("13"),
             ("CART-96", None): Decimal("15"), ("DUMP-2", None): Decimal("40")},
            effective_from=CHANGE,
            effective_to=None,
        )
        # and a second edit for the SAME day — the $13.00 row is emptied, kept
        again = charge_prices.save_prices(
            charge,
            {("CART-35", None): Decimal("9"), ("CART-64", None): Decimal("14"),
             ("CART-96", None): Decimal("15"), ("DUMP-2", None): Decimal("40")},
            effective_from=CHANGE,
            effective_to=None,
        )
        on_1101 = charge_prices.price_on_date(charge, "CART-64", None, CHANGE)
        on_0901 = charge_prices.price_on_date(charge, "CART-64", None, date(2026, 9, 1))
    assert (len(change.killed), len(change.added), change.unchanged) == (1, 2, 2)
    assert (len(again.killed), len(again.added), again.unchanged) == (1, 1, 3)
    assert (on_0901.amount, on_1101.amount) == (Decimal("12.0000"), Decimal("14.0000"))


# ── RLS ─────────────────────────────────────────────────────────────────────
@requires_postgres
def test_the_altered_table_is_still_enabled_and_forced():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        assert cursor.fetchone() == (True, True)


@requires_postgres
def test_no_tenant_context_denies_the_table(rls):
    rls.assert_is_a_real_proof()
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_one_tenants_price_rows_are_invisible_to_another(rls, brazos, lonestar):
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        mine = _row(brazos, _code(brazos, "ISO-B"), start=PRICE_HISTORY_EPOCH)
    with tenant_ctx(lonestar):
        _row(lonestar, _code(lonestar, "ISO-L"), start=PRICE_HISTORY_EPOCH)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar, owner_ids={str(mine.pk)})


@requires_postgres
def test_a_price_row_stamped_for_another_tenant_is_refused(rls, brazos, lonestar):
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        _row(brazos, _code(brazos, "ISO-W"), start=PRICE_HISTORY_EPOCH)
    assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)


# ── the one-time move (rating/0051) ─────────────────────────────────────────
@requires_postgres
def test_the_move_puts_a_flat_amount_in_one_all_sizes_row_once(brazos):
    from django.apps import apps as django_apps

    move = importlib.import_module("apps.rating.migrations.0051_cr156_move_flat_amounts_into_rows")
    with tenant_ctx(brazos):
        legacy = _code(brazos, "OLD-FLAT")
        rating_models.Charge.objects.filter(pk=legacy.pk).update(legacy_amount=Decimal("45"), kind=None)
    editor = SimpleNamespace(connection=connection)
    move._forwards(django_apps, editor)
    move._forwards(django_apps, editor)  # a re-run writes nothing
    with tenant_ctx(brazos):
        rows = list(rating_models.ChargeCodeAmount.objects.filter(charge=legacy))
        charge = rating_models.Charge.objects.get(pk=legacy.pk)
        stored = rating_models.Charge.objects.filter(pk=legacy.pk).values_list(
            "legacy_amount", flat=True
        )[0]
    assert [(r.size_class, r.customer_class, r.amount, r.effective_from) for r in rows] == [
        (ALL_SIZES, None, Decimal("45.0000"), PRICE_HISTORY_EPOCH)
    ]
    assert stored is None and charge.kind == "other"


# ── the PO's worked bills ───────────────────────────────────────────────────
@pytest.fixture
def a_monthly_cycle(monkeypatch):
    from apps.metering import selectors as metering_selectors

    def period(unit_id, as_of=None):
        last = calendar.monthrange(as_of.year, as_of.month)[1]
        return {"start": as_of.replace(day=1).isoformat(), "end": as_of.replace(day=last).isoformat()}

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-MONTH", "name": "Monthly", "due_days": 21},
    )
    monkeypatch.setattr(metering_selectors, "billing_period_for_unit", period)


@pytest.fixture
def nine_then_ten(brazos, dana):
    """The water base at $9.00 from the epoch, repriced to $10.00 from 11/01
    — saved 10/15, the PO's case (on this fixture's water base code)."""
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=NINE)
        code = rating_models.Charge.objects.get(tenant=brazos, is_base=True, service__code="water")
        charge_prices.write_flat_amount_directly(code, NINE)
        charge_prices.save_prices(
            code, {(ALL_SIZES, None): TEN}, effective_from=CHANGE, effective_to=None
        )
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 7, 1))
    return account, asset


def _read(dana, asset, day: date, value: str, prior: str, used: str, days: int):
    commit_read(
        dana,
        asset["id"],
        day=day.isoformat(),
        value=value,
        prior_value=prior,
        consumption=Decimal(used),
        unit=fixture.WATER_UOM,
        days_since_prior=days,
    )


def _drafted_bases(brazos) -> list[Decimal]:
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.order_by("-created_at").first()
        return [
            Decimal(amount).quantize(CENT)
            for amount in billing_models.InvoiceLine.objects.filter(
                invoice=invoice, kind="base"
            ).order_by("period_start", "id").values_list("amount", flat=True)
        ]


@requires_postgres
def test_interim_10_16_to_11_15_is_4_65_plus_5_00(brazos, dana, nine_then_ten, a_monthly_cycle):
    """16/31 × 9.00 + 15/30 × 10.00 = 4.65 + 5.00 = $9.65 — each part over its own month."""
    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 15), "1240", "1200", "40", 31)
    response = _post(
        billing_api.one_time_create,
        brazos,
        _clerk(brazos),
        {
            "account_id": str(account.id),
            "kind": "interim",
            "period_start": "2026-10-16",
            "period_end": "2026-11-15",
            "bill_date": "2026-11-15",
            "due_days": 21,
        },
    )
    assert response.status_code == 201, response.data
    bases = _drafted_bases(brazos)
    # one base line per part (BR-RAT-114: one line per sub-period per charge)
    assert sorted(bases) == [Decimal("4.65"), Decimal("5.00")], bases
    assert sum(bases) == Decimal("9.65")


@requires_postgres
def test_catch_up_09_01_to_09_30_is_nine(brazos, dana, nine_then_ten, a_monthly_cycle):
    """A catch-up created after the change still reads September's row: $9.00."""
    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 9, 30), "1240", "1200", "40", 30)
    response = _post(
        billing_api.one_time_create,
        brazos,
        _clerk(brazos),
        {
            "account_id": str(account.id),
            "kind": "backbill",
            "sub_periods": [{"period_start": "2026-09-01", "period_end": "2026-09-30"}],
            "reason_code": "BILLERR",
            "bill_date": "2026-12-05",
            "due_days": 21,
        },
    )
    assert response.status_code == 201, response.data
    assert _drafted_bases(brazos) == [NINE]


@requires_postgres
def test_november_cycle_bill_is_ten(brazos, dana, nine_then_ten, a_monthly_cycle):
    from apps.billing import runs, single

    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 30), "1240", "1200", "40", 30)
        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            service_date=date(2026, 11, 30),
            cycle_days=30,
        )
        assert prepared.ready, [p.detail for p in prepared.blocked]
        priced = runs.price_account(prepared.ready[0])
    bases = [
        Decimal(line.amount).quantize(CENT)
        for line in priced.priced.lines
        if getattr(line, "kind", None) == "base"
    ]
    assert bases == [TEN], bases


@requires_postgres
def test_a_cycle_bill_crossing_the_change_is_split_at_11_01(brazos, dana, nine_then_ten):
    from apps.billing import single

    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 15), "1240", "1200", "40", 31)
        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=date(2026, 10, 16),
            period_end=date(2026, 11, 15),
            service_date=date(2026, 11, 15),
            cycle_days=31,
        )
    assert prepared.ready, [p.detail for p in prepared.blocked]
    segments = prepared.ready[0].split_segments
    assert [(s.period_start, s.period_end) for s in segments] == [
        (date(2026, 10, 16), date(2026, 10, 31)),
        (date(2026, 11, 1), date(2026, 11, 15)),
    ]


# ── DEF-BIL-8749 · the FIRST and FINAL bills are cut too ────────────────────
def _one_time(kind: str, account) -> dict:
    return {
        "account_id": str(account.id),
        "kind": kind,
        "period_start": "2026-10-16",
        "period_end": "2026-11-15",
        "bill_date": "2026-11-15",
        "due_days": 21,
    }


@requires_postgres
def test_def_bil_8749_first_bill_10_16_to_11_15_is_4_65_plus_5_00(
    brazos, dana, nine_then_ten, a_monthly_cycle
):
    """The coordinator's worked case: a first bill 10/16–11/15, BASE $9.00 →
    $10.00 from 11/01 — 16/31 × 9.00 + 15/30 × 10.00 = 4.65 + 5.00 = $9.65.
    Before the fix the whole window read the 11/15 row: 31/31 × 10.00."""
    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 15), "1240", "1200", "40", 31)
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), _one_time("first", account))
    assert response.status_code == 201, response.data
    bases = _drafted_bases(brazos)
    assert sorted(bases) == [Decimal("4.65"), Decimal("5.00")], bases
    assert sum(bases) == Decimal("9.65")


@requires_postgres
def test_def_bil_8749_first_bill_preview_states_the_same_9_65(brazos, dana, nine_then_ten, a_monthly_cycle):
    account, asset = nine_then_ten
    typed = [{"asset_id": str(asset["id"]), "read_at": "2026-11-15", "value": "1240", "role": "current"}]
    body = {**_one_time("first", account), "readings": typed}
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), body)
    assert response.status_code == 200, response.data
    bases = [
        Decimal(line["amount"])
        for group in response.data["bill"]["groups"]
        for line in group["lines"]
        if line["charge"] == "base"
    ]
    assert sorted(bases) == [Decimal("4.65"), Decimal("5.00")], response.data["bill"]


@requires_postgres
def test_def_bil_8749_final_bill_10_16_to_11_15_is_4_65_plus_5_00(
    brazos, dana, nine_then_ten, a_monthly_cycle
):
    """A final bill through 11/15 over the same change: each part over its own
    month, read on the part's last day — $4.65 + $5.00 = $9.65."""
    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 15), "1240", "1200", "40", 31)
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), _one_time("final", account))
    assert response.status_code == 201, response.data
    bases = _drafted_bases(brazos)
    assert sorted(bases) == [Decimal("4.65"), Decimal("5.00")], bases
    assert sum(bases) == Decimal("9.65")


@requires_postgres
def test_def_bil_8749_a_first_bill_with_no_change_inside_is_not_cut(brazos, dana, nine_then_ten, a_monthly_cycle):
    """Identity: a first bill wholly after the change is one base line,
    15/30 × 10.00 = $5.00 — nothing new runs for a window with no change."""
    account, asset = nine_then_ten
    with tenant_ctx(brazos):
        _read(dana, asset, date(2026, 11, 30), "1240", "1200", "40", 30)
    body = {**_one_time("first", account), "period_start": "2026-11-16", "period_end": "2026-11-30",
            "bill_date": "2026-11-30"}
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), body)
    assert response.status_code == 201, response.data
    assert _drafted_bases(brazos) == [Decimal("5.00")]
