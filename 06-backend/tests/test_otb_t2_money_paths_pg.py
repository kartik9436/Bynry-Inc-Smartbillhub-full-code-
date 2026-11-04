# ── Trace ──────────────────────────────────────────────
# Task:    one-time bill build plan T2 (04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md) — "PostgreSQL proofs for every path
#          that catches a DB error, and the money paths above (law 14)".
# Rulings: PO 2026-09-30 (decision log, top rows): two meters = one line set
#          per meter · the minimum applies to EACH meter ("SIX ANSWERS" (4)) ·
#          counted base per asset, ONE base line per service ("SIX ANSWERS"
#          (5)) · missing base = $0.00 + a warning · no agreements = bill every
#          connected service + a warning · sewer has no service point and
#          follows its basis.
# Rules:   BR-BIL-300 · BR-BIL-301 · BR-BIL-1048 · BR-RAT-088 · BR-RAT-090 ·
#          BR-RAT-1015 · CLAUDE.md hard rule 2 (money stored to 4dp) and
#          hard-won law 14 (the suite's SQLite cannot see a PostgreSQL-only
#          failure).
# Runner:  10-scripts/otb_t2_pg_proofs.py runs this file, `test_b11_issue_
#          hardening.py` and `test_b4_missing_base_bills_zero_with_warning.py`
#          under `--ds=config.settings.pgtest` and prints one line per proof.
# ───────────────────────────────────────────────────────
"""**THE ONE-TIME BILL'S MONEY PATHS, WRITTEN TO THE DATABASE AND READ BACK.**

`test_br_bil_300_services_rulings_2026_09_30.py` proves every ruling's FIGURE
through `runs.price_account` — and touches no database at all (19 cases in
0.6s on PostgreSQL, which is the tell). So nothing proved that the figures
SURVIVE stage 6: that `invoice_lines` on PostgreSQL accepts one line set per
meter with its `asset_id` (a UUID column — `DB1`, `billing/0031`), that a 4dp
amount round-trips exactly, and that the warnings reach `bill_payload`.

This file closes that gap. Every case ends in `runs.calculate_account` — the
stage-6 writer a bulk run and the one-time bill both call — and then reads the
rows back with RAW SQL, never through the ORM that wrote them.

Two kinds of case, and the difference is stated rather than hidden:

* **REAL ROWS, END TO END** (`test_real_*`) — a real plan with a real tier
  ladder, a real unit, real meters and real committed reads, through metering's
  own `billing_reads_for_unit` (whose per-meter query is new on 2026-09-30),
  `runs.readings_for_account`, `gather`, the rating engine and stage 6.
* **A CONTROLLED PRICE LIST, REAL WRITE** (`test_write_*`) — the pricing seams
  are the sibling file's `_world` (so the ruling's own worked figure is what is
  priced), and the ACCOUNT, the stage-6 write and the read-back are real. The
  world's meter ids are UUIDs here, because `invoice_lines.asset_id` is a UUID
  column and `"m-1"` would never be written by the product.

The savepoint proof (`issue._issue_one`, B11) is
`test_b11_issue_hardening.py::test_B11_a_database_error_on_one_bill_does_not_poison_the_rest`
and is not repeated here; the runner runs it and shows it RED on a scratch copy
of `issue.py` with the savepoint removed.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import bill_warnings, contracts, gather, resolution_shadow, runs
from apps.billing import models as billing_models
from apps.billing.contracts import ServiceReading
from apps.billing.rating_seam import Quantity
from core import sample_fixture as fixture

from tests import test_br_bil_300_services_rulings_2026_09_30 as rulings
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = PERIOD_END
FOUR_DP = Decimal("0.0001")


def _vendor() -> str:
    return connection.vendor


def _db_id(invoice):
    """The invoice id as THIS backend stores it — PostgreSQL's `uuid` takes the
    dashed text, SQLite's `char(32)` the bare hex — so the same raw SQL reads
    the row back on both (a dashed string matches nothing on SQLite)."""
    return billing_models.Invoice._meta.pk.get_db_prep_value(invoice.id, connection)


def _uuid_text(value) -> str | None:
    return None if value is None else str(uuid.UUID(str(value)))


def _rows(invoice) -> list[tuple[str, str, Decimal, str | None]]:
    """`invoice_lines` for one bill, by RAW SQL: kind, service code, amount and
    asset id (normalised to dashed text on either backend)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT l.kind, s.code, l.amount, l.asset_id "
            "FROM invoice_lines l LEFT JOIN services s ON s.id = l.service_id "
            "WHERE l.invoice_id = %s ORDER BY s.code, l.asset_id, l.kind, l.amount",
            [_db_id(invoice)],
        )
        return sorted(
            (
                (kind, code, Decimal(str(amount)), _uuid_text(asset))
                for kind, code, amount, asset in cursor.fetchall()
            ),
            key=lambda r: (r[1] or "", r[3] or "", r[0], r[2]),
        )


def _payload_warning_keys(invoice) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT bill_payload FROM invoices WHERE id = %s", [_db_id(invoice)])
        (payload,) = cursor.fetchone()
    if isinstance(payload, str):  # SQLite hands JSON back as text
        import json

        payload = json.loads(payload)
    return [row["key"] for row in (payload or {}).get("warnings", [])]


def _stored_total(invoice) -> Decimal:
    with connection.cursor() as cursor:
        cursor.execute("SELECT total FROM invoices WHERE id = %s", [_db_id(invoice)])
        (total,) = cursor.fetchone()
    return Decimal(str(total))


def _sum(rows, *, service=None, asset=None, kinds=None) -> Decimal:
    return sum(
        (
            amount
            for kind, code, amount, asset_id in rows
            if (service is None or code == service)
            and (asset is None or asset_id == asset)
            and (kinds is None or kind in kinds)
        ),
        Decimal("0"),
    )


def _price_real(account):
    readings, _unmeasured = runs.readings_for_account(
        account, period_start=PERIOD_START, period_end=PERIOD_END, scope_services=None
    )
    data = gather.gather_account(
        account=account,
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=31,
        readings=readings,
    )
    return data, runs.calculate_account(data, service_date=SERVICE_DATE, bill_type="interim")


# ══════════════════════════════════════════════════════════════════════════
# REAL ROWS, END TO END
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-4
def test_real_two_water_meters_write_one_line_set_per_meter(brazos, dana):
    """**Two meters on one water point, each on its own ladder and its own
    base.** Silver Creek's ladder is `$4.00` to 5 kgal, `$6.50` to 15; base
    `$8.00`.

    * meter A: 6 kgal → 5 × $4.00 + 1 × $6.50 = `$26.50` + `$8.00` = `$34.50`
    * meter B: 3 kgal → 3 × $4.00 = `$12.00` + `$8.00` = `$20.00`
    * bill: **`$54.50`** — one meter billed alone would be `$34.50` (the
      pre-2026-09-30 answer, `DEF-MET-8092`) and one ladder over the summed
      9 kgal would be `$54.00` with ONE base: `$46.00`.

    The account holds no service agreement (the fixture writes none), so B8's
    warning rides the same bill — the real-row half of that proof.
    """
    assert fixture.WATER_TIERS[0] == ("0", "5", "4.00")
    assert fixture.WATER_TIERS[1] == ("5", "15", "6.50")
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, unit, meter_a, _delta = _account_on(
            brazos, dana, plan, register="1156", prior="1150"
        )
        meter_b = a_meter(
            dana,
            asset_no="M-9002",
            service="water",
            uom=fixture.WATER_UOM,
            unit_id=unit["id"],
        )
        commit_read(
            dana,
            meter_b["id"],
            day="2026-07-28",
            value="1103",
            prior_value="1100",
            consumption=Decimal("3"),
            unit=fixture.WATER_UOM,
        )
        data, invoice = _price_real(account)
        rows = _rows(invoice)
        warnings = _payload_warning_keys(invoice)
        total = _stored_total(invoice)

    a, b = str(meter_a["id"]), str(meter_b["id"])
    water_assets = {asset for _k, code, _amt, asset in rows if code == "water"}
    assert water_assets == {a, b}, rows
    assert _sum(rows, asset=a) == Decimal("34.50"), rows
    assert _sum(rows, asset=b) == Decimal("20.00"), rows
    assert [amt for kind, _c, amt, asset in rows if kind == "base" and asset == a] == [
        Decimal("8.00")
    ]
    assert [amt for kind, _c, amt, asset in rows if kind == "base" and asset == b] == [
        Decimal("8.00")
    ]
    assert total == Decimal("54.50")
    assert total == total.quantize(FOUR_DP)
    assert contracts.WARN_NO_AGREEMENTS in warnings
    print(f"PROOF two-meters vendor={_vendor()} rows={rows} total={total} warnings={warnings}")


# BULK-CHG-3
def test_real_missing_base_writes_zero_and_the_warning(brazos, dana):
    """**No water base code exists at all (case a).** The plan's and the
    schedule's retired `$8.00` columns are still written by the fixture, so
    the wrong answer is visible: the bill must carry `$0.00` of base, never
    `$8.00`, and the stored draft must name `baseNotSet`.

    6 kgal → `$26.50` usage, and that is the whole bill.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _meter, _delta = _account_on(
            brazos, dana, plan, register="1156", prior="1150"
        )
        _data, invoice = _price_real(account)
        rows = _rows(invoice)
        warnings = _payload_warning_keys(invoice)
        total = _stored_total(invoice)

    assert _sum(rows, kinds={"base"}) == Decimal("0"), rows
    assert Decimal("8.00") not in [amt for kind, _c, amt, _a in rows if kind == "base"]
    assert total == Decimal("26.50"), rows
    assert bill_warnings.BASE_NOT_SET in warnings, warnings
    print(f"PROOF missing-base vendor={_vendor()} rows={rows} total={total} warnings={warnings}")


# ══════════════════════════════════════════════════════════════════════════
# A CONTROLLED PRICE LIST, A REAL WRITE
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture()
def _rolled_back_resolution_chain(settings, monkeypatch):
    """The sibling file's autouse fixture, taken explicitly: the resolution
    chain reads `app.tenant_id` catalogues this price list does not have."""
    settings.BILLING_RESOLUTION_STEPS = ""
    monkeypatch.setattr(runs, "_continuity_decisions", lambda *_a, **_k: [])


def _no_version_ids(world):
    """The world names versions `"v-water"`; `invoice_lines.tariff_version_id`
    is a real FK, so the controlled price list states no version at all."""
    inner = world["rating.pricing_inputs"]

    def pricing_inputs(*args, **kwargs):
        return {**inner(*args, **kwargs), "version_id": None}

    world["rating.pricing_inputs"] = pricing_inputs
    return world


def _write(real_account, readings):
    from types import SimpleNamespace

    account = SimpleNamespace(
        id=real_account.id,
        account_no=real_account.account_no,
        unit_id="unit-930",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
    )
    data = gather.gather_account(
        account=account,
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=31,
        readings=tuple(readings),
    )
    return data, runs.calculate_account(data, service_date=SERVICE_DATE, bill_type="interim")


def _real_account(brazos, dana):
    plan = _water_plan(brazos)
    account, _unit, _meter, _delta = _account_on(brazos, dana, plan)
    return account


def _install(monkeypatch, world):
    rulings._install(monkeypatch, _no_version_ids(world))


# BULK-CHG-4
@pytest.mark.usefixtures("_rolled_back_resolution_chain")
def test_write_the_minimum_applies_to_each_meter(brazos, dana, monkeypatch):
    """**Minimum `$10.00`; meter A `$14.00` stands, meter B `$6.00` is lifted
    to `$10.00` — usage `$24.00`, not `$20.00`** ("SIX ANSWERS" (4), *"consider
    them 2 lines anc charge"*). The `$14.00` meter is FIRST, so a minimum on
    the first meter only would store `$20.00`. Base `$0.00`, stated, because a
    minimum is measured against usage AND base (BR-RAT-028).

    First run on PostgreSQL (2026-09-30) asserted meter B's lines summed to
    `$10.00` and went RED: `assert Decimal('6.000000') == Decimal('10.00')` —
    the `$4.00` top-up is stored as its own `minimum_adjustment` line with no
    `asset_id`. The money is right; the attribution is `DEF-BIL-8150`.

    **FIXED 2026-09-30 (`DEF-BIL-8150`).** The top-up is still its own line —
    the one-time bill's `minimum` charge (contract §2) — and now carries meter
    B's `asset_id` and water's `service_id`, so meter B's rows sum to `$10.00`.
    RED on the tip before the fix, on PostgreSQL 16:
    `assert Decimal('6.000000') == Decimal('10.00')` (meter B's rows) and the
    top-up's stored `(service, asset)` read `(None, None)`."""
    m1, m2 = str(uuid.uuid4()), str(uuid.uuid4())

    def with_minimum(tariff, service_date, *size, **kw):
        inputs = rulings._pricing_inputs(tariff, service_date, *size, **kw)
        if getattr(tariff, "service", None) == "water":
            inputs = {
                **inputs,
                "minimum_bill": "10.00",
                "model": "flat",
                "unit_price": "1.00",
                "tiers": [],
            }
        return inputs

    world = rulings._world(plan_services=["water"], unit_services=["water"], assets={"water": [m1, m2]})
    world["rating.pricing_inputs"] = with_minimum
    world["rating.base_charge_from_charge_code"] = lambda service_code, **_k: {
        "amount": "0.00",
        "code": "BASE-W",
        "refusal": None,
    }
    with tenant_ctx(brazos):
        real = _real_account(brazos, dana)
        _install(monkeypatch, world)
        _data, invoice = _write(
            real, [rulings._water("14", asset_id=m1), rulings._water("6", asset_id=m2)]
        )
        rows = _rows(invoice)
        total = _stored_total(invoice)

    non_base = [r for r in rows if r[0] != "base"]
    assert _sum(non_base) == Decimal("24.00"), rows
    assert _sum(non_base, asset=m1, kinds={"usage"}) == Decimal("14.00"), rows
    assert _sum(non_base, asset=m2, kinds={"usage"}) == Decimal("6.00"), rows
    # ONE top-up of `$4.00` — meter B's shortfall, and none for meter A.
    tops = [amt for kind, _c, amt, _a in rows if kind == "minimum_adjustment"]
    assert tops == [Decimal("4.00")], rows
    assert total == Decimal("24.00")
    # DEF-BIL-8150 — the stored top-up names meter B and water, so the bill
    # reads meter A `$14.00`, meter B `$6.00 + $4.00 = $10.00` (PO "SIX
    # ANSWERS" (4): *"consider them 2 lines anc charge"*).
    top_assets = [asset for kind, _c, _amt, asset in rows if kind == "minimum_adjustment"]
    assert [(code, asset) for kind, code, _amt, asset in rows if kind == "minimum_adjustment"] == [
        ("water", m2)
    ], rows
    assert _sum(rows, asset=m1) == Decimal("14.00"), rows
    assert _sum(rows, asset=m2) == Decimal("10.00"), rows
    print(
        f"PROOF minimum-per-meter vendor={_vendor()} rows={rows} total={total} "
        f"top_up_asset={top_assets}"
    )


# BULK-CHG-5
@pytest.mark.usefixtures("_rolled_back_resolution_chain")
def test_write_two_carts_bill_36_with_one_base_line(brazos, dana, monkeypatch):
    """**2 carts × ($15.00 + $3.00) = `$36.00` on ONE line** ("SIX ANSWERS"
    (5), *"per service"*: *"two carts at $18.00 still bill $36.00 on one
    line"*).

    ⚠ **THIS USED TO ASSERT A `$6.00` BASE LINE AND LEAVE THE LINE COUNT
    UNASSERTED, ON PURPOSE** — stage 6 wrote TWO trash lines, usage `$30.00`
    and base `$6.00`, which was `DEF-BIL-8151`. **FIXED 2026-09-30**:
    `runs.price_account` joins a counted service's usage and base into one
    `usage` line of quantity 2 carts at `$18.00`. RED on the tip before the
    fix, on PostgreSQL 16: `AssertionError: assert 2 == 1` (the trash lines).
    """
    c1, c2 = str(uuid.uuid4()), str(uuid.uuid4())
    world = rulings._world(
        plan_services=["trash"],
        unit_services=["trash"],
        assets={"trash": [c1, c2]},
        size_groups={"trash": {"CART-96": 2}},
    )
    reads = [
        ServiceReading(
            service_code="trash",
            absent_reason="service_not_metered",
            asset_count=2,
            asset_size_counts={"CART-96": 2},
        )
    ]
    with tenant_ctx(brazos):
        real = _real_account(brazos, dana)
        _install(monkeypatch, world)
        _data, invoice = _write(real, reads)
        rows = _rows(invoice)
        total = _stored_total(invoice)

    trash = [r for r in rows if r[1] == "trash"]
    assert _sum(trash) == Decimal("36.00"), rows
    assert len(trash) == 1, rows
    assert [(kind, amt) for kind, _c, amt, _a in trash] == [("usage", Decimal("36.00"))], rows
    assert total == Decimal("36.00")
    print(f"PROOF counted-base vendor={_vendor()} trash_lines={len(trash)} rows={rows} total={total}")


# BULK-CHG-6
@pytest.mark.usefixtures("_rolled_back_resolution_chain")
def test_write_no_agreements_bills_every_connected_service_and_warns(brazos, dana, monkeypatch):
    """**Customers answers `None` — no agreement on file.** Water (5 kgal →
    `$16.25` + `$8.00`) and electric (100 kWh × $0.10 = `$10.00` + `$10.00`)
    both bill: `$44.25`, and the stored draft names `noAgreements`."""
    m1, e1 = str(uuid.uuid4()), str(uuid.uuid4())
    world = rulings._world(
        plan_services=["water", "electric"],
        unit_services=["water", "electric"],
        assets={"water": [m1], "electric": [e1]},
        taken=None,
    )
    reads = [
        rulings._water(5),
        ServiceReading(
            service_code="electric", consumption=Quantity(amount=Decimal("100"), unit="kWh")
        ),
    ]
    with tenant_ctx(brazos):
        real = _real_account(brazos, dana)
        _install(monkeypatch, world)
        _data, invoice = _write(real, reads)
        rows = _rows(invoice)
        warnings = _payload_warning_keys(invoice)
        total = _stored_total(invoice)

    assert {code for _k, code, _a, _s in rows} == {"water", "electric"}, rows
    assert total == Decimal("44.25"), rows
    assert warnings == [contracts.WARN_NO_AGREEMENTS], warnings
    print(f"PROOF no-agreements vendor={_vendor()} rows={rows} total={total} warnings={warnings}")


# BULK-CHG-1
@pytest.mark.usefixtures("_rolled_back_resolution_chain")
def test_write_sewer_with_no_point_follows_water(brazos, dana, monkeypatch):
    """**The unit has a water point and NO sewer point.** Sewer is 40% of the
    water quantity (5 kgal → 2 kgal) at sewer's own `$5.00` = `$10.00`, plus
    its `$5.00` base; water `$16.25` + `$8.00`. Bill `$39.25`. Before the
    ruling sewer was *not connected* and the `$15.00` was lost."""
    m1 = str(uuid.uuid4())
    world = rulings._world(
        plan_services=["water", "sewer"], unit_services=["water"], assets={"water": [m1]}
    )
    with tenant_ctx(brazos):
        real = _real_account(brazos, dana)
        _install(monkeypatch, world)
        data, invoice = _write(real, [rulings._water(5)])
        rows = _rows(invoice)
        total = _stored_total(invoice)

    assert "sewer" not in data.unconnected_services
    sewer = [r for r in rows if r[1] == "sewer"]
    assert [amt for kind, _c, amt, _a in sewer if kind == "usage"] == [Decimal("10.00")], rows
    assert _sum(sewer) == Decimal("15.00"), rows
    assert total == Decimal("39.25"), rows
    print(f"PROOF sewer-no-point vendor={_vendor()} rows={rows} total={total}")


def test_the_proofs_ran_where_they_claim(request):
    """Law 7 (a check that cannot fail): when the runner says PostgreSQL, the
    connection IS PostgreSQL. Under the default suite this reports SQLite and
    passes — the runner, not this case, is what refuses a SQLite run."""
    print(f"PROOF vendor-check vendor={_vendor()}")
    assert _vendor() in {"postgresql", "sqlite"}


# Keep the sibling's resolver patch reachable for readers: every world case
# above publishes through `gather._resolve` and `resolution_shadow._seam`.
_ = (resolution_shadow,)
