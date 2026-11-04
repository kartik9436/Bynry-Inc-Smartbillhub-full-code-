# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-006 (TOU Option B — TC-9 the utility states which register
#           each window reads · TC-10 the two negatives) · US-RAT-012 (the
#           engine that consumes it)
#           Screens: S11 (Time-of-use card, the field that collects it)
# Rules:    BR-RAT-067 (THE UTILITY STATES WHICH METER REGISTER EACH TIME-OF-USE
#           WINDOW IS MEASURED ON; rating never infers it — PO ruling
#           2026-08-16, OQ-236 CLOSED) · BR-RAT-064 (SUPERSEDED — the price-rank
#           match this file proves is gone) · BR-RAT-021 (reads arrive PRE-SPLIT
#           per window) · BR-RAT-007 (the structure belongs to the VERSION)
# Golden:   GT-17 (= WE-1) — 120 x 0.22 + 200 x 0.14 + 380 x 0.09 = 88.60,
#           unmoved by anything in this file
# Tests:    this file
# Impacts:  apps/rating/models.TimeOfUseWindow.channel ·
#           apps/rating/migrations/0006_tou_window_register.py ·
#           apps/rating/services._validate_tou · apps/rating/selectors.pricing_inputs
# ───────────────────────────────────────────────────────
"""US-RAT-006 TC-9/TC-10 — which meter register a configured window reads.

WHAT THIS FILE IS FOR, IN ONE SENTENCE: it asserts that the mapping between a
priced WINDOW and a measured REGISTER is a thing a human typed, and that no code
path can derive it from anything else.

THE NUMBER THIS PROTECTS. A customer's electric meter reports three numbers a
month and a time-of-use tariff prices three windows. Paired as the utility
states them the reference bill's electric usage is **88.60** (❄️ B5 GT-17);
paired the other way round the same meter bills **122.40** — a 38% overcharge on
a document that looks perfectly ordinary. Before 2026-08-16 nothing in the
schema recorded the pairing and rating matched by PRICE RANK; the PO ruled
*"make the rate wizard say which register is which"* (OQ-236 → BR-RAT-067).

The tests below are DB-level on purpose. `tests/test_us_rat_012_tou.py` proves
the plugin honours a stated register; these prove the stored column is what the
plugin is handed — which is the half a pure-function test cannot see.
"""

from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import SUMMER, WINTER, tenant_ctx, tou_structure

pytestmark = pytest.mark.django_db


SERVICE_DATE = __import__("datetime").date(2026, 8, 15)  # inside Summer, inside the version


def _payload(structure, name="Comm Electric · TOU"):
    return {
        "name": name,
        "service": "electric",
        "model": "time_of_use",
        "uom": "kWh",
        # ⚠ AN EXPLICIT ZERO, ADDED 2026-08-19 WITH DEF-277, AND IT IS NOT
        # NOISE. This schedule deliberately carries no fixed monthly charge —
        # every figure this file asserts is usage. Until DEF-277 the base column
        # was NOT NULL with `default=0`, so omitting it stored a zero nobody had
        # typed and the fixture read as "no base" while the database read as
        # "free". Now a blank means CR-013 part 1's *"size not served"* and
        # `gather._base_charge_for` refuses to bill it, so the fixture has to say
        # which of the two it meant. It means free, and it says so.
        "base_charge": "0",
        "effective_from": "2026-08-01",
        "structure": structure,
    }


def _summer_windows(on="0.22", mid="0.14", off="0.09"):
    """The demo tenant's own three-window summer schedule, each window STATING
    its register. Prices are parameters so a test can reorder them."""
    return [
        {
            "label": "On-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "14:00",
            "end_time": "20:00",
            "unit_price": on,
            "channel": "tou_on",
        },
        {
            "label": "Mid-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "11:00",
            "end_time": "14:00",
            "unit_price": mid,
            "channel": "tou_mid",
        },
        {
            "label": "Off-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "20:00",
            "end_time": "11:00",
            "unit_price": off,
            "channel": "tou_off",
        },
        {
            "label": "All day",
            "season": "Winter",
            "day_type": "weekday",
            "start_time": "00:00",
            "end_time": "00:00",
            "unit_price": "0.13",
            "channel": "tou_off",
        },
    ]


def _structure(windows):
    return tou_structure(windows=windows, seasons=[dict(SUMMER), dict(WINTER)])


# ── TC-9 · the utility states it, and the store keeps it ────────────────────
def test_us_rat_006_tc9__each_window_stores_the_register_the_utility_named(env):
    """The wizard's answer reaches the row it is billed from."""
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(env.admin, _payload(_structure(_summer_windows())))
        stored = {
            window.label: window.channel
            for window in models.TimeOfUseWindow.objects.filter(tenant_id=env.tenant.id)
        }
    assert stored == {
        "On-peak": "tou_on",
        "Mid-peak": "tou_mid",
        "Off-peak": "tou_off",
        "All day": "tou_off",
    }
    # And it reads back on the S9 card / the resumed S11 draft, so a human can
    # check what they said (hard-won law 2: a stored field nothing renders is
    # a field nobody can correct).
    previewed = {
        row["label"]: row["channel"] for row in schedule["current_version"]["structure"]["windows"]
    }
    assert previewed == stored


def test_us_rat_006_tc9__pricing_reads_the_stated_register_not_the_price_rank(env):
    """**THE RED-PROOF THAT THE INFERENCE IS GONE, at the DB boundary.**

    The tariff below states its registers in the OPPOSITE order to the price
    rank: `tou_on` is priced 0.09 and `tou_off` is priced 0.22.

    The deleted resolver (`selectors._window_channels`, BR-RAT-064) derived the
    register FROM the price — dearest = `tou_on` — so it would answer
    `{'On-peak': 'tou_off', 'Off-peak': 'tou_on'}` here and bill the 120 kWh
    register at 0.22. This asserts the opposite: what the utility said.

    RED-PROVED by restoring `_window_channels` into `pricing_inputs` and
    re-running — this assertion fails with
    `{'On-peak': 'tou_off', ...} == {'On-peak': 'tou_on', ...}`.
    """
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin,
            # Same windows, same registers, prices swapped end for end.
            _payload(_structure(_summer_windows(on="0.09", off="0.22"))),
        )
        tariff = models.Tariff.objects.get(tenant_id=env.tenant.id, name="Comm Electric · TOU")
        inputs = selectors.pricing_inputs(tariff, SERVICE_DATE)
    stated = {row["label"]: row["channel"] for row in inputs["windows"]}
    assert stated["On-peak"] == "tou_on"  # priced 0.09 — the CHEAPEST
    assert stated["Mid-peak"] == "tou_mid"
    assert stated["Off-peak"] == "tou_off"  # priced 0.22 — the DEAREST
    # The prices travel unchanged beside them, so the pairing is checkable here
    # rather than only three modules downstream.
    priced = {row["label"]: row["unit_price"] for row in inputs["windows"]}
    assert priced["On-peak"] == Decimal("0.090000")
    assert priced["Off-peak"] == Decimal("0.220000")


def test_us_rat_006_tc9__a_bulk_price_change_never_moves_a_register(env, job_store):
    """A rate rise moves the MONEY and not the meter (BR-RAT-067).

    A bulk change writes a NEW version and copies the structure onto it, so the
    utility's answer has to survive the copy. If it did not, the new version's
    windows would all read NULL and a schedule that billed yesterday would
    refuse today — and the tempting fix would be to re-derive the registers from
    the new prices, which is the inference the PO's ruling ended.

    **Stated honestly, because a comment claiming a guarantee is not the
    guarantee (hard-won law 1):** a UNIFORM change cannot re-order prices, so
    this test does not prove rank-independence — `pricing_reads_the_stated_
    register_not_the_price_rank` above does that, on a tariff whose rank and
    statement disagree. What this proves is the copy: the register is carried,
    not recomputed and not dropped.
    """
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin,
            _payload(_structure(_summer_windows(mid="0.14", off="0.13"))),
        )
        before = {
            window.label: window.channel
            for window in models.TimeOfUseWindow.objects.filter(tenant_id=env.tenant.id)
        }
    with tenant_ctx(env.tenant):
        accepted = services.request_rate_change_batch(
            env.admin,
            {
                "entities": [{"type": "schedule", "id": schedule["id"]}],
                "change": {"kind": "percent", "value": "30.0"},
                "effective_from": "2027-01-01",
                "reason": "Board order 2026-12 annual adjustment",
            },
        )
    # run_job re-enters the tenant context from the record and clears it on exit
    # (BE-01), so the job never runs nested inside a caller's context.
    services.run_rate_change_job(accepted["job_id"])
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        raised = selectors.in_force_version(tariff, __import__("datetime").date(2027, 1, 15))
        after = {
            window.label: (window.channel, window.unit_price)
            for window in models.TimeOfUseWindow.objects.filter(
                tenant_id=env.tenant.id, tariff_version=raised
            )
        }
    # The prices really did move — otherwise this test proves nothing.
    assert after["Mid-peak"][1] == Decimal("0.182000")  # 0.14 + 30%
    assert after["Off-peak"][1] == Decimal("0.169000")  # 0.13 + 30%
    assert {
        label: value[0] for label, value in after.items()
    } == before, "a price change dropped or re-assigned a meter register"


def test_us_rat_006_tc9__the_bill_follows_the_statement_end_to_end(env):
    """**THE MONEY, from the stored column to the priced line.**

    The two tests above prove the column is stored and served; this one carries
    it the whole way — rating's `pricing_inputs` → billing's `_tariff_config_for`
    → the engine — because that is the path a real bill takes and the path the
    38% overcharge would have travelled.

    Registers read 120 / 200 / 380 kWh. The tariff states `tou_on` on the 0.09
    window and `tou_off` on the 0.22 one:

        120 x 0.09 + 200 x 0.14 + 380 x 0.22 = 10.80 + 28.00 + 83.60 = 122.40

    RED-PROVED: with `_window_channels` restored in `pricing_inputs`, the rank
    overrides the statement and the same fixture bills **88.60** — this
    assertion fails with `Decimal('88.60') == Decimal('122.40')`, and the two
    documents are indistinguishable to a customer.
    """
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    from apps.billing import gather, rating_seam
    from apps.rating import engine

    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin, _payload(_structure(_summer_windows(on="0.09", off="0.22")))
        )
        tariff_row = models.Tariff.objects.get(tenant_id=env.tenant.id, name="Comm Electric · TOU")
        config = gather._tariff_config_for(  # noqa: SLF001 — the seam under test
            tariff_row, "electric", SERVICE_DATE
        )
    consumption = rating_seam.Quantity(
        amount=Decimal("700"),
        unit="kWh",
        windows=(
            rating_seam.WindowQuantity(
                channel="tou_on", quantity=rating_seam.Quantity(Decimal("120"), "kWh")
            ),
            rating_seam.WindowQuantity(
                channel="tou_mid", quantity=rating_seam.Quantity(Decimal("200"), "kWh")
            ),
            rating_seam.WindowQuantity(
                channel="tou_off", quantity=rating_seam.Quantity(Decimal("380"), "kWh")
            ),
        ),
    )
    bill = engine.price_period(
        tariff=config,
        consumption=consumption,
        period=rating_seam.BillingPeriod(cycle_days=31, service_days=31),
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
    )
    lines = {line.description: line.amount for line in bill.lines_of("usage")}
    assert lines["electric usage — On-peak"] == Decimal("10.80")
    assert lines["electric usage — Off-peak"] == Decimal("83.60")
    assert sum(lines.values()) == Decimal("122.40")


# ── TC-10 (negative) · the two refusals ─────────────────────────────────────
def test_us_rat_006_tc10__a_window_with_no_register_is_refused_at_the_wizard(env):
    """BR-RAT-067 clause 1 — the field is REQUIRED, and required at write time
    rather than at activation: a price with no register is the one combination
    that produces a plausible bill at the wrong number."""
    windows = _summer_windows()
    # `CR-157-BRC10` — On-peak / Mid-peak / Off-peak now DERIVE their register
    # from the window's name (`services.tou_register_for_window`), so the rule
    # this case guards bites on a window the utility names itself. It read
    # "Dana skipped the picker on On-peak" until then.
    windows[0]["label"] = "Punta"
    del windows[0]["channel"]  # Dana skipped the picker on her own "Punta"
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, _payload(_structure(windows)))
    fields = {error["field"] for error in excinfo.value.field_errors}
    assert "structure.windows[0].channel" in fields
    # Nothing was written — a half-configured schedule must not exist.
    with tenant_ctx(env.tenant):
        assert not models.TimeOfUseWindow.objects.filter(tenant_id=env.tenant.id).exists()


def test_us_rat_006_tc10__an_unknown_register_name_is_refused(env):
    """The vocabulary is METERING's (`tou_on | tou_mid | tou_off`, B2 r8 /
    BR-MET-059). A register no meter reports cannot be measured."""
    windows = _summer_windows()
    windows[0]["channel"] = "tou_super_peak"
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, _payload(_structure(windows)))
    assert "structure.windows[0].channel" in {
        error["field"] for error in excinfo.value.field_errors
    }


def test_us_rat_006_tc10__two_windows_may_not_read_one_register(env):
    """BR-RAT-067 clause 2 — one register holds ONE number for the period."""
    windows = _summer_windows()
    # `CR-157-BRC10` — a window NAMED Mid-peak can no longer point at another
    # register at all (`rating.tou.window_register_mismatch`), so the reuse
    # rule is exercised on a window the utility names itself.
    windows[1]["label"] = "Shoulder"
    windows[1]["channel"] = "tou_on"  # Shoulder pointed at On-peak's register
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, _payload(_structure(windows)))
    reused = [
        error
        for error in excinfo.value.field_errors
        if error["message_key"] == "rating.tou.register_reused"
    ]
    assert reused, excinfo.value.field_errors
    assert reused[0]["params"]["channel"] == "tou_on"
    assert "Shoulder" in reused[0]["params"]["windows"]
    assert "On-peak" in reused[0]["params"]["windows"]


def test_us_rat_006_tc10__the_database_refuses_a_register_no_meter_reports(env):
    """The CHECK constraint is the last line, not the only one. A fixture, a
    shell or a future importer that skips `services` still cannot store a
    register that no `meter_reads` row can carry — so the refusal happens at
    write time and not on run day."""
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    from django.db import IntegrityError, transaction

    with tenant_ctx(env.tenant):
        services.create_rate_schedule(env.admin, _payload(_structure(_summer_windows())))
        window = models.TimeOfUseWindow.objects.filter(tenant_id=env.tenant.id).first()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.TimeOfUseWindow.objects.filter(pk=window.pk).update(channel="peak")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-006@BR-RAT-067 (PO ruling 2026-08-16 closing OQ-236; EP-RAT-02 §3 TC-9/TC-10)
# generated: 2026-08-16 by the register lane (OQ-236 → BR-RAT-067)
# checklist: A✔ B✔ C✔ D=deferred(test module) E=deferred(test module; the frontend half is 07-frontend/e2e/tou-register.spec.ts) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_us_rat_006_tc9_window_register.py✔ · pytest -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: none — every case here is declared in EP-RAT-02 §3 (TC-9/TC-10) before the code was written
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
