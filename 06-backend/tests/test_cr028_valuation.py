# ── Trace ──────────────────────────────────────────────
# Story:    CR-028 AST-W4 (B16 §5.2 AST-08 step 3 · §10-D3/D4 · BR-AST-047):
#           T3 retire computes straight-line book value and RECORDS the
#           operator's treatment · T4 the same computation serves the detail
#           valuation block (buy + present value) · T5 BR-AST-027 seeded
#           test-interval defaults flow into create and Test entries roll the
#           next due · the retire-time device-link clearing for inverters
# Rules:    BR-AST-047 (valuation on the device record; method & cost OPTIONAL,
#           life CALCULABLE, buy + present value; retire computes book value +
#           records treatment; NO finance link — nothing posts anywhere) ·
#           BR-AST-027 (test-interval defaults: backflow 12 mo · meter 96 mo) ·
#           BR-AST-021/030 (retire law untouched) · hard rule 2 (money stored
#           4 dp, displayed 2) · hard rule 5 (only the ledger posting service
#           writes journal lines — asserted by ABSENCE here)
# Tests:    this file
# Impacts:  apps/assets/selectors.py (asset_book_value + valuation block) ·
#           apps/assets/services.py (retire_asset extension · log_maintenance
#           next-due roll)
# ───────────────────────────────────────────────────────
"""CR-028 AST-W4 — book value at retire, valuation on the record, cert cadence.

RED-FIRST: every test here was run against the pre-change tree and its
failure quoted in the lane report before the code landed.

⚠ **THE RATIFIED-FIGURE VERDICT, STATED WHERE THE NUMBER IS PINNED.**
r10's AST-08 step 3 draws purchase $164.00 · accumulated depreciation
**$19.83** · remaining **$144.17** for a meter installed 2026-03-12 minus
29 whole months (Mar 12 2024 → Aug 16 2026, life 20 years). Straight-line
months arithmetic CANNOT produce $19.83:

    164.0000 × 29 / 240 = 19.816666…  → 19.8167 stored (4 dp) → $19.82 shown
    164.0000 − 19.8167  = 144.1833    → $144.18 shown

$19.83 would need 29.02 elapsed months — no whole-month, whole-day or
365.25-day derivation reaches it (day-count straight-line gives $19.91).
Per the lane instruction the formula is NOT fudged to hit the prototype's
number: these tests pin THIS formula's results ($19.8167 / $144.1833) and
the one-cent delta against r10 ($19.83 / $144.17) is reported to the PO as
a prototype-figure discrepancy, exactly like the r10 internal bugs B16 §11
records. If finance later ratifies a different day-count convention, this
file is where the change goes RED first.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

from apps.assets import selectors, services  # noqa: E402
from core import errors  # noqa: E402

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 16)  # the r10 screenshot's "today"


def valued_meter(actor, **overrides):
    """The r10 worked case: $164.00 · life 20 years · installed Mar 12 2024."""
    payload = {
        "asset_no": "M-4021",
        "purchase_cost": "164.00",
        "expected_life_years": 20,
        "install_date": "2024-03-12",
    }
    payload.update(overrides)
    return make_asset(actor, **payload)


def _row(asset_id):
    return selectors.asset_row(asset_id)


# ══════════════════════════════════════════════════════════════════════════
# T3/T6 — asset_book_value: the worked case, EXACTLY (formula's own figures)
# ══════════════════════════════════════════════════════════════════════════
def test_w4__book_value_worked_case_pins_the_straight_line_figures(brazos, dana):
    """GT-shape pin: $164.00 · 20 yrs · Mar 12 2024 → Aug 16 2026 = 29 months
    → accumulated 19.8167 · remaining 144.1833 (4 dp stored; screen shows
    $19.82 / $144.18). r10 draws $19.83/$144.17 — the delta is REPORTED, the
    formula is not bent to meet it (see the module docstring)."""
    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        value = selectors.asset_book_value(_row(asset["id"]), as_of=AS_OF)
    assert value is not None
    assert value["age_months"] == 29  # "2 yrs 5 mo of 20"
    assert value["life_months"] == 240
    assert value["purchase_cost"] == "164.0000"
    assert value["accumulated_depreciation"] == "19.8167"
    assert value["book_value"] == "144.1833"


def test_w4__book_value_is_none_without_a_cost_or_a_life(brazos, dana):
    with tenant_ctx(brazos):
        no_cost = make_asset(dana, asset_no="M-7001", expected_life_years=20)
        no_life = make_asset(dana, asset_no="M-7002", purchase_cost="99.00")
        assert selectors.asset_book_value(_row(no_cost["id"]), as_of=AS_OF) is None
        assert selectors.asset_book_value(_row(no_life["id"]), as_of=AS_OF) is None


def test_w4__book_value_never_depreciates_past_the_cost(brazos, dana):
    """An asset older than its whole life bottoms out at 0.0000 — never a
    negative book value."""
    with tenant_ctx(brazos):
        asset = make_asset(
            dana,
            asset_no="M-7003",
            purchase_cost="100.00",
            expected_life_years=1,
            install_date="2020-01-01",
        )
        value = selectors.asset_book_value(_row(asset["id"]), as_of=AS_OF)
    assert value["accumulated_depreciation"] == "100.0000"
    assert value["book_value"] == "0.0000"


def test_w4__an_uninstalled_asset_ages_from_purchase(brazos, dana):
    """B16 §5.1b: inventory stock ages from purchase — same base the Lifecycle
    panel uses."""
    with tenant_ctx(brazos):
        asset = make_asset(
            dana,
            asset_no="M-7004",
            purchase_cost="240.00",
            expected_life_years=20,
            purchase_date="2025-08-16",
        )
        value = selectors.asset_book_value(_row(asset["id"]), as_of=AS_OF)
    assert value["age_months"] == 12
    assert value["accumulated_depreciation"] == "12.0000"  # 240 × 12/240
    assert value["book_value"] == "228.0000"


# ══════════════════════════════════════════════════════════════════════════
# T3 — retire RECORDS the pair (D4 · BR-AST-047), posts NOTHING
# ══════════════════════════════════════════════════════════════════════════
def test_w4__retire_records_book_value_amount_and_treatment(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        services.retire_asset(
            dana,
            asset["id"],
            {
                "reason": "end_of_life",
                "retire_date": "2026-08-16",
                "book_value_treatment": "write_off",
            },
        )
        row = _row(asset["id"])
        detail = selectors.asset_detail(asset["id"])
    assert str(row.book_value_amount) == "144.1833"
    assert row.book_value_treatment == "write_off"
    # Rule 7: the recorded money reaches the trail with its figure.
    retired = [r for r in audit_rows if r["action"] == "asset.retired"][0]
    assert retired["after"]["book_value_amount"] == "144.1833"
    assert retired["after"]["book_value_treatment"] == "write_off"
    # ...and the detail read serves what was recorded.
    assert detail["valuation"]["book_value_amount"] == "144.1833"
    assert detail["valuation"]["book_value_treatment"] == "write_off"


def test_w4__retire_requires_a_treatment_when_a_book_value_exists(brazos, dana):
    """The model's own law: book_value_treatment is required at retire ONLY
    when a book value exists — the step-3 radio is not skippable then."""
    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.retire_asset(
                dana, asset["id"], {"reason": "end_of_life", "retire_date": "2026-08-16"}
            )
    assert caught.value.field_errors[0]["field"] == "book_value_treatment"


def test_w4__retire_refuses_an_unknown_treatment(brazos, dana):
    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.retire_asset(
                dana,
                asset["id"],
                {
                    "reason": "end_of_life",
                    "retire_date": "2026-08-16",
                    "book_value_treatment": "sell_on_ebay",
                },
            )
    assert caught.value.field_errors[0]["field"] == "book_value_treatment"


def test_w4__a_no_cost_asset_retires_with_a_null_book_value(brazos, dana):
    """The honest step-3 state: no purchase cost recorded → no book value, no
    treatment demanded, nothing invented."""
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-7005")
        result = services.retire_asset(dana, asset["id"], {"reason": "removed"})
        row = _row(asset["id"])
    assert result["status"] == "retired"
    assert row.book_value_amount is None and row.book_value_treatment is None


def test_w4__a_treatment_without_a_book_value_is_refused(brazos, dana):
    """A treatment names a figure; with no figure to treat the choice is
    meaningless and is refused rather than silently stored."""
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-7006")
        with pytest.raises(errors.ValidationError) as caught:
            services.retire_asset(
                dana, asset["id"], {"reason": "removed", "book_value_treatment": "hold"}
            )
    assert caught.value.field_errors[0]["field"] == "book_value_treatment"


def test_w4__retire_writes_no_journal_rows_and_assets_imports_no_ledger(brazos, dana):
    """Hard rule 5 / D4: retire COMPUTES and RECORDS — it posts NOTHING.
    Asserted from both ends: zero journal rows after a valued retire, and no
    apps.assets module imports the ledger app at all."""
    from apps.ledger.models import JournalEntry, JournalLine

    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        services.retire_asset(
            dana,
            asset["id"],
            {
                "reason": "end_of_life",
                "retire_date": "2026-08-16",
                "book_value_treatment": "write_off",
            },
        )
        assert JournalEntry.objects.count() == 0
        assert JournalLine.objects.count() == 0
    assets_dir = Path(services.__file__).resolve().parent
    for source in assets_dir.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "apps.ledger" not in text, f"{source.name} reaches the ledger module"


# ══════════════════════════════════════════════════════════════════════════
# T3 — the non-measuring edge: retiring a linked inverter clears the link
# ══════════════════════════════════════════════════════════════════════════
def test_w4__retiring_a_linked_inverter_clears_the_link_and_flags_the_meter(
    brazos, dana, audit_rows
):
    """B16 §5.1b (B): the device's measuring link does not survive its
    retirement, and the METER's own trail carries the review flag — the
    inline Audit tab (DEF-579 pattern) is where a clerk sees it."""
    with tenant_ctx(brazos):
        meter = make_asset(dana, asset_no="M-4310", type="net_meter")
        inverter = make_asset(
            dana,
            asset_no="PV-1204",
            type="pv",
            service=None,
            unit=None,
            parent_asset_no="M-4310",
        )
        services.retire_asset(dana, inverter["id"], {"reason": "removed"})
        row = _row(inverter["id"])
    assert row.parent_asset_id is None
    flags = [r for r in audit_rows if r["action"] == "asset.pairing_review_flagged"]
    assert len(flags) == 1
    assert str(flags[0]["entity_id"]) == meter["id"]
    assert flags[0]["after"]["retired_device"] == "PV-1204"


# ══════════════════════════════════════════════════════════════════════════
# T3 — retire's final read is CAPTURED with the retire (D5 wired the seam)
# ══════════════════════════════════════════════════════════════════════════
def test_w4__retire_with_a_final_read_captures_it_atomically(brazos, dana):
    """BR-AST-022's posture applied to retire — WIRED by the CR-028 debt
    sweep (D5, 2026-08-22). Until then this test asserted the
    `assets.final_read_capture_unavailable` refusal, because metering
    published no capture service; the retire now commits WITH its committed
    manual read and the closing assignment carries the read's id. The full
    matrix lives in tests/test_cr028_final_read_capture.py."""
    from apps.assets import models as asset_models
    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"])
        asset = make_asset(dana, asset_no="M-7008", unit_id=unit["id"], install_date="2024-01-01")
        result = services.retire_asset(
            dana,
            asset["id"],
            {"reason": "failed", "final_read_value": "43566"},
        )
        after = _row(asset["id"])
        closed = (
            asset_models.AssetAssignment.objects.filter(asset_id=asset["id"], to_date__isnull=False)
            .order_by("-to_date")
            .first()
        )
        read = met_models.MeterRead.objects.get(id=str(closed.final_read_id))
    assert result["status"] == "retired"
    assert after.status.behavior_class == "terminal"  # the retire DID happen
    assert read.current_value is not None and read.source_detail == "final_read"


# ══════════════════════════════════════════════════════════════════════════
# T4 — the served valuation block: buy value + present value
# ══════════════════════════════════════════════════════════════════════════
def test_w4__detail_valuation_serves_present_value_beside_the_buy_value(brazos, dana):
    with tenant_ctx(brazos):
        asset = valued_meter(dana)
        valuation = selectors.asset_detail(asset["id"])["valuation"]
    assert valuation["purchase_cost"] == "164.0000"  # buy value (stored 4 dp)
    # Present value is book value AS OF the tenant's today — a moving figure;
    # asserted structurally here, the exact worked number is pinned above with
    # an explicit as_of.
    assert valuation["present_value"] is not None
    assert Decimal(valuation["present_value"]) < Decimal("164.0000")
    assert Decimal(valuation["accumulated_depreciation"]) > Decimal("0")
    # Un-retired: the RECORDED pair is null, never a pre-filled treatment.
    assert valuation["book_value_amount"] is None
    assert valuation["book_value_treatment"] is None


def test_w4__detail_valuation_present_value_is_null_without_cost_or_life(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-7009")
        valuation = selectors.asset_detail(asset["id"])["valuation"]
    assert valuation["present_value"] is None
    assert valuation["accumulated_depreciation"] is None


# ══════════════════════════════════════════════════════════════════════════
# T5 — BR-AST-027 defaults flow, and a Test entry ROLLS the next due
# ══════════════════════════════════════════════════════════════════════════
def test_w4__a_new_backflow_gets_the_seeded_12_month_interval(brazos, dana):
    with tenant_ctx(brazos):
        backflow = make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            service=None,
            unit=None,
        )
        meter = make_asset(dana, asset_no="M-7010")
        backflow_interval = _row_interval(backflow["id"])
        meter_interval = _row_interval(meter["id"])
    assert backflow_interval == 12
    assert meter_interval == 96


def _row_interval(asset_id):
    return selectors.asset_row(asset_id).test_interval_months


def test_w4__an_explicit_cadence_is_not_overwritten_by_the_default(brazos, dana):
    with tenant_ctx(brazos):
        backflow = make_asset(
            dana,
            asset_no="BF-3302",
            type="backflow",
            service=None,
            unit=None,
            test_interval_months=6,
        )
        interval = _row_interval(backflow["id"])
    assert interval == 6


def test_w4__a_test_entry_rolls_an_explicit_certification_due(brazos, dana):
    """The AST-W2 CERT_DUE column would otherwise go STALE the day a test is
    logged: next_test preferred the explicit date over the fresh derivation.
    A test entry on an interval-carrying asset now rolls it forward."""
    with tenant_ctx(brazos):
        backflow = make_asset(
            dana,
            asset_no="BF-3303",
            type="backflow",
            service=None,
            unit=None,
            certification_due="2026-06-01",  # already past — the Overdue row
        )
        services.log_maintenance(
            dana,
            backflow["id"],
            {"kind": "test", "date": "2026-08-10", "detail": "Annual backflow test passed"},
        )
        row = selectors.asset_row(backflow["id"])
        next_due = selectors.next_test_date(row)
    assert row.last_test_date == date(2026, 8, 10)
    assert row.certification_due == date(2027, 8, 10)  # 12-month cadence rolled
    assert next_due == "2027-08-10"


def test_w4__a_test_entry_with_no_interval_leaves_the_explicit_due_alone(brazos, dana):
    """No cadence → nothing to derive; the explicit date is DATA and is kept,
    never cleared by a guess (reported, not resolved silently)."""
    with tenant_ctx(brazos):
        device = make_asset(
            dana,
            asset_no="COM-9001",
            type="comms",
            service=None,
            unit=None,
            certification_due="2027-01-15",
        )
        services.log_maintenance(
            dana, device["id"], {"kind": "test", "date": "2026-08-10", "detail": "Signal check"}
        )
        row = selectors.asset_row(device["id"])
    assert row.certification_due == date(2027, 1, 15)


# ══════════════════════════════════════════════════════════════════════════
# The AST-05 wizard's number preview (suggestion WITHOUT allocation)
# ══════════════════════════════════════════════════════════════════════════
def test_w4__number_preview_suggests_without_advancing_the_series(brazos, dana):
    with tenant_ctx(brazos):
        first = selectors.asset_no_preview("meter")
        second = selectors.asset_no_preview("meter")
        assert first is not None and first == second  # a PEEK, not an allocation
        assert first.startswith("M-")  # BR-AST-026 per-type prefix
        created = make_asset(dana, asset_no=None)  # blank → the series allocates
        assert created["asset_no"] == first  # the preview told the truth


def test_w4__number_availability_reports_a_taken_number(brazos, dana):
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-5099")
        assert selectors.asset_no_available("M-5099") is False
        assert selectors.asset_no_available("m-5099") is False  # case-insensitive
        assert selectors.asset_no_available("M-9999") is True
