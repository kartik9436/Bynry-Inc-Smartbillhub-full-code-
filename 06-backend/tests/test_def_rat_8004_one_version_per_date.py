# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8004 — the nightly bill run silently billed the newest of two
#          in-force rate-schedule versions while the one-time bill and the
#          move-out final bill REFUSED (`AmbiguousSchedule`, R2).
# Ruling:  PO 2026-10-01, option A (decision log *"DEF-RAT-8004 RULED"*),
#          verbatim: *"we have to return only 1 row; A · Use the newest
#          everywhere, and flag it on Check"*. And the same day's *"A METER
#          WITH NO RECORDED SIZE GETS NO MINIMUM, AND THE BILL-RUN CHECK FLAGS
#          IT"* (option A) — the second warning this lane adds.
# Rules:   BR-RAT-1055 (one version per service date, one rule) · BR-RAT-007 ·
#          BR-RAT-028 mode (A) as amended 2026-10-01 · CLAUDE.md hard-won
#          laws 7 (red first) and 14 (PostgreSQL)
# ───────────────────────────────────────────────────────
"""**ONE VERSION PER SERVICE DATE, BY ONE RULE, ON EVERY DOOR.**

THE WORLD. An electric schedule left with TWO live versions in force on the
service date — the legacy shape `rating/0047` now refuses at COMMIT and
`rating/0046` deliberately did not resolve. Each version names its own base
charge code (`BR-RAT-1025`), so the base on the bill says which version priced:

    older version  (from 1 Jan 2026)  BASE-OLD  $18.40
    newer version  (from 1 Jun 2026)  BASE-NEW  $21.60

Both are in force on every June date. The PO's answer is **$21.60 everywhere**:
the nightly run, the one-time interim bill, the move-out final bill (12 of 30
days of it — `$8.64`, never `$7.36`), and the R1-R7 chain's own R2. Before the
fix the run billed $21.60 and the two one-time doors refused.

THE TIE. The same two versions both starting 1 Jan 2026: the one SAVED LATER
wins, and the test makes the later-saved row the one with the SMALLER id, so an
answer that came from the id rather than from `created_at` fails.

⚠ **THE OVERLAP ROWS ARE WRITTEN PAST THE CONSTRAINT, ON PURPOSE.**
`ex_tariff_versions_no_overlap` is `DEFERRABLE INITIALLY DEFERRED` and every
case here runs inside one transaction that is rolled back, so the constraint
is never checked and the legacy shape can exist for the length of a test. The
first case proves the database WOULD refuse these rows at COMMIT, so nothing
here is a shape the product can still create.

Run on PostgreSQL (hard-won law 14):

    DATABASE_URL=… JOBS_EAGER=false pytest --ds=config.settings.pgtest \\
        tests/test_def_rat_8004_one_version_per_date.py --reuse-db
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from apps.billing import api as billing_api
from apps.billing import final_bill, runs
from apps.billing import check_taxonomy
from apps.rating import models as rating_models
from apps.rating import resolution, resolution_catalogue
from apps.rating import selectors as rating_selectors
from apps.tenancy import models as tenancy_models

from tests.test_bbr_check_engine import PERIOD_END, codes_for, prepare, three_accounts
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import state_size_axis, tenant_ctx

pytestmark = pytest.mark.django_db

CENT = Decimal("0.01")
OLDER = Decimal("18.40")
NEWER = Decimal("21.60")
OVERLAP = check_taxonomy.WARN_SCHEDULE_VERSIONS_OVERLAP


#: The overlap rows this module wrote, so they can be taken out of the
#: constraint's reach before Django's own teardown checks it.
_WRITTEN: list = []


@pytest.fixture(autouse=True)
def _overlaps_end_with_the_test():
    """⚠ **DJANGO CHECKS EVERY DEFERRED CONSTRAINT AT TEST TEARDOWN** —
    `TestCase._fixture_teardown` calls `check_constraints()`, which on
    PostgreSQL is `SET CONSTRAINTS ALL IMMEDIATE`, so a legacy overlap left in
    place fails the teardown (`ex_tariff_versions_no_overlap`, measured on the
    first run). It is torn down BEFORE pytest-django's own db teardown; the second
    version is parked as a draft (`effective_from` NULL), which the
    constraint's own predicate leaves out. It asks for no fixture of its own:
    an autouse fixture that pulled in a tenant would sort AHEAD of the
    SQLite GUC shim and break every case there."""
    yield
    for tenant, pk in list(_WRITTEN):
        with tenant_ctx(tenant):
            rating_models.TariffVersion.objects.filter(pk=pk).update(
                effective_from=None, effective_to=None
            )
    _WRITTEN.clear()


def _code(tenant, code, amount):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"Electric base {code}",
        charge_type="recurring",
        amount_rule="flat",
        amount=amount,
        service=tenancy_models.Service.objects.get(code="electric"),
        is_base=True,
        applies_to_customer_classes=[],
    )


def _overlap(tenant, plan, *, tie=False):
    """Give the plan's electric schedule a SECOND live version in force with
    the first. Returns `(tariff, winner, loser)`.

    `tie=False`: the second version starts 1 Jun 2026 — newest `effective_from`
    wins, so the SECOND row prices at $21.60.
    `tie=True`: both start 1 Jan 2026; the FIRST row (smaller id) is stamped as
    saved LATER and prices at $21.60, the second row (larger id) at $18.40.
    """
    bound = rating_selectors.plan_rate_schedules(plan.id)[0]
    tariff = bound["tariff"]
    first = rating_models.TariffVersion.objects.get(tenant=tenant, tariff=tariff)
    old_code = _code(tenant, "BASE-OLD", OLDER)
    new_code = _code(tenant, "BASE-NEW", NEWER)
    second = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="flat",
        base_charge=first.base_charge,
        uom="kWh",
        currency="USD",
        effective_from=date(2026, 1, 1) if tie else date(2026, 6, 1),
    )
    for tier in rating_models.RateTier.objects.filter(tariff_version=first):
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=second,
            seq=tier.seq,
            from_qty=tier.from_qty,
            to_qty=tier.to_qty,
            unit_price=tier.unit_price,
        )
    state_size_axis(second, "electric")
    _WRITTEN.append((tenant, second.pk))
    early = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    late = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
    if tie:
        winner, loser = first, second
    else:
        winner, loser = second, first
    rating_models.TariffVersion.objects.filter(pk=winner.pk).update(
        base_charge_code=new_code, created_at=late
    )
    rating_models.TariffVersion.objects.filter(pk=loser.pk).update(
        base_charge_code=old_code, created_at=early
    )
    if tie:
        assert str(winner.pk) < str(loser.pk), "the tie case needs the winner to have the SMALLER id"
    return tariff, winner, loser


def _base(lines) -> list[Decimal]:
    return [
        Decimal(str(getattr(line, "amount", None) if not isinstance(line, dict) else line["amount"])).quantize(CENT)
        for line in lines
        if (getattr(line, "kind", None) if not isinstance(line, dict) else line.get("kind", line.get("charge")))
        == "base"
    ]


# ══════════════════════════════════════════════════════════════════════════
# 0 · the rows are the LEGACY shape — the database refuses them at COMMIT
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(connection.vendor != "postgresql", reason="the exclusion constraint is PostgreSQL's")
def test_0__the_database_would_refuse_this_overlap_at_commit(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, plan, _accounts = three_accounts(brazos, dana)
        _overlap(brazos, plan)
        with pytest.raises(IntegrityError, match="ex_tariff_versions_no_overlap"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


# ══════════════════════════════════════════════════════════════════════════
# 1 · the two readers answer with ONE row, the same row
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tie", [False, True], ids=["newest-start", "same-start-later-saved"])
def test_1__the_run_and_the_chain_pick_the_same_one_version(brazos, dana, tie):
    with tenant_ctx(brazos):
        _cycle, plan, _accounts = three_accounts(brazos, dana)
        tariff, winner, loser = _overlap(brazos, plan, tie=tie)
        live = rating_selectors.in_force_version(tariff, PERIOD_END)
        ordered = rating_selectors.in_force_versions(tariff, PERIOD_END)
        facts = resolution_catalogue.schedule_version_facts(tariff.id)
    plan_fact = resolution.PlanVersion(
        plan_id="p", version=1, services=("electric",),
        effective_from=date(2026, 1, 1), schedules={"electric": str(tariff.id)},
    )
    catalogue = resolution.Catalogue(plan_versions=(plan_fact,), schedule_versions=facts)
    chosen = resolution.resolve_schedule(catalogue, plan_fact, "electric", PERIOD_END)

    assert live.pk == winner.pk
    assert [v.pk for v in ordered] == [winner.pk, loser.pk]
    assert chosen.version_id == str(winner.pk), "R2 refused or picked another row than the run"
    assert chosen.base_charge_code == "BASE-NEW"


# ══════════════════════════════════════════════════════════════════════════
# 2 · the bulk run bills $21.60 and the Check flags it — a warning, not a hold
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tie", [False, True], ids=["newest-start", "same-start-later-saved"])
def test_2__the_bulk_run_bills_the_newest_and_the_check_warns(brazos, dana, tie):
    with tenant_ctx(brazos):
        cycle, plan, accounts = three_accounts(brazos, dana)
        _overlap(brazos, plan, tie=tie)
        prepared = prepare(cycle)
        assert len(prepared.ready) == 3, [(p.account_no, p.reason) for p in prepared.blocked]
        bases = [_base(runs.price_account(data).priced.lines) for data in prepared.ready]

    assert bases == [[NEWER]] * 3, bases
    for account in accounts.values():
        assert OVERLAP in codes_for(prepared, account), codes_for(prepared, account)
    flagged = [w for w in prepared.warnings if w.reason == OVERLAP]
    assert len(flagged) == 3
    # The warning tier: on the findings, on Sign off's warnings, never a decision.
    tag = check_taxonomy.classify(OVERLAP)
    assert tag.severity == check_taxonomy.WARNING and tag.suggests is False
    assert not [d for d in prepared.decisions if d.reason == OVERLAP]


def test_2b__the_warning_names_the_schedule_and_both_versions_and_no_id(brazos, dana):
    with tenant_ctx(brazos):
        cycle, plan, _accounts = three_accounts(brazos, dana)
        tariff, _winner, _loser = _overlap(brazos, plan)
        prepared = prepare(cycle)
        data = prepared.ready[0]
    rows = [w for w in runs.account_warnings(data) if w["key"] == "billing.run.warn.scheduleVersionsOverlap"]
    assert len(rows) == 1
    params = rows[0]["params"]
    assert params["schedule"] == tariff.name
    assert params["versions"] == "1 Jun 2026, 1 Jan 2026"
    assert params["used"] == "1 Jun 2026"
    assert params["date"] == "1 Jul 2026"  # the run's price date (BILL_DATE)
    assert str(tariff.id) not in str(params)


def test_2c__a_tie_is_named_by_the_day_each_was_saved(brazos, dana):
    with tenant_ctx(brazos):
        cycle, plan, _accounts = three_accounts(brazos, dana)
        _overlap(brazos, plan, tie=True)
        data = prepare(cycle).ready[0]
    (row,) = [w for w in runs.account_warnings(data) if w["key"] == "billing.run.warn.scheduleVersionsOverlap"]
    assert row["params"]["versions"] == (
        "1 Jan 2026 (saved 20 May 2026), 1 Jan 2026 (saved 1 May 2026)"
    )


def test_2d__no_overlap_no_warning(brazos, dana):
    """The ordinary schedule — one version — carries no such warning."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        prepared = prepare(cycle)
    for account in accounts.values():
        assert OVERLAP not in codes_for(prepared, account)


# ══════════════════════════════════════════════════════════════════════════
# 3 · the one-time doors stop refusing and agree with the run to the cent
# ══════════════════════════════════════════════════════════════════════════
def _interim_body(account, asset_id):
    return (
        {
            "account_id": str(account.id),
            "kind": "interim",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "bill_date": "2026-06-30",
            "due_days": 21,
            "readings": [
                {"asset_id": str(asset_id), "read_at": "2026-06-30", "value": "14160", "role": "current"}
            ],
        }
    )


@pytest.mark.parametrize("tie", [False, True], ids=["newest-start", "same-start-later-saved"])
def test_3a__the_one_time_interim_bill_prices_at_the_newest(brazos, dana, monkeypatch, tie):
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch)
        _overlap(brazos, _plan_of(account), tie=tie)
        asset_ids = metering_selectors.connection_asset_ids_for(account.unit_id, "electric")
    response = _post(
        billing_api.one_time_preview, brazos, _clerk(brazos), _interim_body(account, asset_ids[0])
    )
    assert response.status_code == 200, response.data
    answer = response.data
    assert answer.get("bill"), answer
    lines = [line for group in answer["bill"]["groups"] for line in group["lines"]]
    assert [Decimal(line["amount"]).quantize(CENT) for line in lines if line["charge"] == "base"] == [NEWER]


@pytest.mark.parametrize("tie", [False, True], ids=["newest-start", "same-start-later-saved"])
def test_3b__the_move_out_final_bill_prices_at_the_newest(brazos, dana, monkeypatch, tie):
    with tenant_ctx(brazos):
        account = _a_moving_out_account(brazos, dana, monkeypatch)
        _overlap(brazos, _plan_of(account), tie=tie)
        answer = final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)

    assert answer["priced"] is True, answer.get("priced_unavailable")
    bases = [Decimal(line["amount"]).quantize(CENT) for line in answer["lines"] if line.get("kind") == "base"]
    # 1 Jun – 12 Jun is 12 of 30 days: 12/30 × $21.60 = $8.64 (the older
    # version would have been 12/30 × $18.40 = $7.36).
    assert bases == [Decimal("8.64")], answer["lines"]


def _plan_of(account):
    """The one plan the moving-out fixture publishes for this tenant."""
    return rating_models.RatePlan.objects.filter(tenant_id=account.tenant_id).order_by("-created_at").first()


# ══════════════════════════════════════════════════════════════════════════
# 4 · PO 2026-10-01 — A METER WITH NO RECORDED SIZE GETS NO MINIMUM, AND THE
#     BILL-RUN CHECK FLAGS IT (option A). The PO's worked figure: Water —
#     Residential, a 5/8" home whose size was never recorded, flat base $8.00
#     + 1 kgal × $4.4096 = $12.41 billed, warning shown; once the size is
#     recorded, the next bill gets the 5/8" minimum, $15.00, and no warning.
# ══════════════════════════════════════════════════════════════════════════
UNSIZED = check_taxonomy.WARN_METER_SIZE_NOT_RECORDED
JULY_START, JULY_END, JULY_BILL = date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 1)


def _water_world(brazos, dana):
    """One water account on a schedule with per-size minimums (5/8" $15.00,
    2" $40.00, 3/4" *No minimum*), a flat $8.00 base code, $4.4096 a kgal,
    1 kgal read in July, on a cycle — and its meter's size NOT recorded."""
    from apps.metering import models as metering_models
    from tests.test_def_438_parity import _account_on
    from tests.test_us_met_helpers import make_plan

    plan = make_plan(brazos, name="Water — Residential", services=("water",))
    bound = rating_models.PlanRateSchedule.objects.get(rate_plan_id=plan.id)
    version = rating_models.TariffVersion.objects.create(
        tenant=brazos, tariff=bound.tariff, model="flat", uom="kgal", currency="USD",
        effective_from=date(2026, 1, 1),
    )
    rating_models.RateTier.objects.create(
        tenant=brazos, tariff_version=version, seq=1, from_qty=Decimal("0"), to_qty=None,
        unit_price=Decimal("4.4096"),
    )
    for size, minimum in (("W-58", Decimal("15.00")), ("W-2", Decimal("40.00")), ("W-34", None)):
        rating_models.RateSizeRow.objects.create(
            tenant=brazos, tariff_version=version, size_class=size, minimum_bill=minimum
        )
    from tests.base_code_naming import name_base_code

    name_base_code(  # DEF-RAT-9832 (PO 2026-10-06) — an unnamed schedule bills $0.00
        brazos,
        rating_models.Charge.objects.create(
            tenant=brazos, code="BASE-W", name="Water base", charge_type="recurring",
            amount_rule="flat", amount=Decimal("8.00"), is_base=True, applies_to_customer_classes=[],
            service=tenancy_models.Service.objects.get(code="water"),
        ),
    )
    account, unit, asset, _delta = _account_on(
        brazos, dana, plan, register="1151", prior="1150", size_class=None
    )
    cycle = metering_models.Cycle.objects.create(
        tenant=brazos, code="07-W", start_day=1, days_to_complete=31
    )
    metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(cycle=cycle)
    return cycle, account, asset


def _july(cycle):
    return runs.prepare_run(
        cycle_id=cycle.id, period_start=JULY_START, period_end=JULY_END, service_date=JULY_BILL
    )


def _blocked(prepared):
    return [(p.account_no, p.reason, p.detail) for p in prepared.blocked]


def test_4a__an_unsized_meter_bills_12_41_with_no_minimum_and_the_check_names_it(
    brazos, dana, settings
):
    """The ruling's mechanics, with R3 NOT switched on — the rollback switch.
    `test_4c` proves the same $12.41 at the shipped `R3,R4` (`DEF-RAT-8822`)."""
    settings.BILLING_RESOLUTION_STEPS = ""  # neither R3 nor R4 (BR-BIL-873: both or neither)
    with tenant_ctx(brazos):
        cycle, account, _asset = _water_world(brazos, dana)
        prepared = _july(cycle)
        assert [d.account_no for d in prepared.ready] == [account.account_no], _blocked(prepared)
        priced = runs.price_account(prepared.ready[0])
        warnings = runs.account_warnings(prepared.ready[0])

    assert Decimal(str(priced.priced.total)).quantize(CENT) == Decimal("12.41")
    assert UNSIZED in codes_for(prepared, account)
    (row,) = [w for w in warnings if w["key"] == "billing.run.warn.meterSizeNotRecorded"]
    assert row["params"]["meter"] == "M-9001"
    assert check_taxonomy.classify(UNSIZED).severity == check_taxonomy.WARNING
    assert [w.reason for w in prepared.warnings].count(UNSIZED) == 1


def test_4b__once_the_size_is_recorded_the_next_bill_gets_the_15_00_minimum_and_no_warning(
    brazos, dana
):
    """At the SHIPPED switch (R3, R4): a recorded size bills its minimum."""
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        cycle, account, asset = _water_world(brazos, dana)
        asset_models.Asset.objects.filter(pk=asset["id"]).update(size_class="W-58")
        prepared = _july(cycle)
        assert [d.account_no for d in prepared.ready] == [account.account_no], _blocked(prepared)
        priced = runs.price_account(prepared.ready[0])

    assert Decimal(str(priced.priced.total)).quantize(CENT) == Decimal("15.00")
    assert UNSIZED not in codes_for(prepared, account)


# ── `DEF-RAT-8822` · PO 2026-10-01, option A — *"Hold back only where the
# price depends on the size. If the base is one price for all sizes, the bill
# goes out at $12.41 with the warning. If the base differs by size, it's still
# held as today, so nobody is billed the wrong size's rate."* Until this ruling
# was built, `test_4c` was a strict xfail: at the SHIPPED switch (`R3,R4`) the
# ruled path's adapter refused every unsized meter on a banded service, so the
# $12.41 bill and its warning were reachable only with R3 switched off.
#
# The three figures, each through the bulk run AND the one-time bill:
#   BASE-W *All sizes* $8.00, no size recorded   -> $12.41, warning, READY
#   the same, size recorded as 5/8" ($15.00 min) -> $15.00, no warning
#   BASE-W per size (5/8" $8.00, 2" $34.00)      -> HELD, today's refusal
#: Today's refusal for an unsized meter whose base is priced per size — the
#: live gather's, which holds it before the ruled path is ever asked
#: (measured on PostgreSQL 16 at the tip before this fix, bulk and one-time).
#: ⚠ The REASON read `plan_has_no_tariff_for_service` until `DEF-BIL-9024`
#: (2bf16e2dc, 2.437.8) gave this stop its own name; that commit moved the
#: product and not these two cases, which stayed red until `DEF-BIL-9801`.
#: The sentence did not move.
SIZE_PRICED_HOLD = (
    "connection_size_unresolved_for_sized_schedule",
    "This connection's size is not recorded.",
)


def _base_priced_per_size(brazos):
    """BASE-W stops being one price for all sizes: its *All sizes* row goes
    and two sized rows take its place (5/8" $8.00, 2" $34.00)."""
    code = rating_models.Charge.objects.get(tenant=brazos, code="BASE-W")
    rating_models.ChargeCodeAmount.objects.filter(charge=code).delete()
    for size, amount in (("W-58", Decimal("8.00")), ("W-2", Decimal("34.00"))):
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos, charge=code, size_class=size, amount=amount
        )


def _july_one_time(brazos, account, asset):
    """The one-time interim bill for the same July: the 1,151 register the
    run reads (prior 1,150), so 1 kgal either way."""
    return _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        {
            "account_id": str(account.id),
            "kind": "interim",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "bill_date": "2026-08-01",
            "due_days": 21,
            "readings": [
                {"asset_id": str(asset["id"]), "read_at": "2026-07-31", "value": "1151", "role": "current"}
            ],
        },
    )


def _one_time_total(response) -> Decimal:
    assert response.status_code == 200, response.data
    lines = [line for group in response.data["bill"]["groups"] for line in group["lines"]]
    return sum((Decimal(line["amount"]) for line in lines), Decimal("0")).quantize(CENT)


def test_4c__at_the_shipped_switch_the_unsized_account_bills_12_41(brazos, dana):
    """Ruling (1): an *All sizes* base and no recorded size -> BILLED at the
    shipped switch, $8.00 + 1 kgal × $4.4096 = $12.41, no minimum, and the
    Check names the meter. The account is READY, never held."""
    with tenant_ctx(brazos):
        cycle, account, _asset = _water_world(brazos, dana)
        prepared = _july(cycle)
        assert [d.account_no for d in prepared.ready] == [account.account_no], _blocked(prepared)
        priced = runs.price_account(prepared.ready[0])
        warnings = runs.account_warnings(prepared.ready[0])

    assert prepared.ready[0].resolution_steps == ("R3", "R4"), "not the shipped switch"
    assert Decimal(str(priced.priced.total)).quantize(CENT) == Decimal("12.41")
    assert UNSIZED in codes_for(prepared, account)
    (row,) = [w for w in warnings if w["key"] == "billing.run.warn.meterSizeNotRecorded"]
    assert row["params"]["meter"] == "M-9001"
    assert not prepared.blocked


def test_4d__the_one_time_bill_prices_the_unsized_account_at_12_41(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, account, asset = _water_world(brazos, dana)
    assert _one_time_total(_july_one_time(brazos, account, asset)) == Decimal("12.41")


def test_4e__the_one_time_bill_with_the_size_recorded_prices_the_15_00_minimum(brazos, dana):
    """Ruling (3): once 5/8" is recorded, its $15.00 minimum applies."""
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        _cycle, account, asset = _water_world(brazos, dana)
        asset_models.Asset.objects.filter(pk=asset["id"]).update(size_class="W-58")
    assert _one_time_total(_july_one_time(brazos, account, asset)) == Decimal("15.00")


def test_4f__a_base_priced_per_size_still_holds_the_unsized_account_as_today(brazos, dana):
    """Ruling (2) — `BR-RAT-120` NARROWED, not superseded: where the base
    differs by size, an unsized meter is HELD with today's refusal, so nobody
    is billed the wrong size's rate."""
    with tenant_ctx(brazos):
        cycle, account, _asset = _water_world(brazos, dana)
        _base_priced_per_size(brazos)
        prepared = _july(cycle)
    assert not prepared.ready
    (held,) = _blocked(prepared)
    assert held[0] == account.account_no
    assert held[1] == SIZE_PRICED_HOLD[0]
    assert held[2].startswith(SIZE_PRICED_HOLD[1]), held


def test_4g__the_one_time_bill_refuses_the_size_priced_unsized_account_as_today(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, account, asset = _water_world(brazos, dana)
        _base_priced_per_size(brazos)
    response = _july_one_time(brazos, account, asset)
    assert response.status_code == 422, response.data
    assert response.data["params"]["reason"] == SIZE_PRICED_HOLD[0]
    # `DEF-BIL-9024`: this stop has its own clerk key, and the engine's
    # sentence travels as `detail` (it read `sentence` under the old reason).
    assert response.data["message_key"] == "billing.oneTime.err.noSize"
    assert response.data["params"]["detail"].startswith(SIZE_PRICED_HOLD[1])


def test_4h__the_chain_alone_lets_an_unsized_meter_through_only_on_an_all_sizes_base():
    """R3 itself, without a database: the same water schedule passes an
    unsized meter when its base is one price for every size and refuses it,
    naming the ladder, when the base is priced per size."""
    meter = resolution.MeterFacts("water", resolution.NO_SIZE)
    flat = resolution.ScheduleVersion(
        version_id="v", service="water", size_rows={"W-58": None, "W-2": None},
        base_priced_by_size=False,
    )
    sized = resolution.ScheduleVersion(
        version_id="v", service="water", size_rows={"W-58": None, "W-2": None},
        size_axis_source="charge_code", base_priced_by_size=True,
    )
    assert resolution.resolve_served_size(flat, meter) == resolution.NO_SIZE
    with pytest.raises(resolution.SizeNotServed, match="ratified size ladder"):
        resolution.resolve_served_size(sized, meter)


# ══════════════════════════════════════════════════════════════════════════
# 5 · the rate schedule's View details is served the same overlap
# ══════════════════════════════════════════════════════════════════════════
def test_5__the_schedule_detail_serves_the_overlap_for_its_band(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, plan, _accounts = three_accounts(brazos, dana)
        tariff, _winner, _loser = _overlap(brazos, plan)
        detail = rating_selectors.schedule_detail(tariff.id)
    (stretch,) = detail["versions_overlap"]
    assert stretch["on"] == "2026-06-01"
    assert [v["effective_from"] for v in stretch["versions"]] == ["2026-06-01", "2026-01-01"]
    assert str(tariff.id) not in str(stretch)
