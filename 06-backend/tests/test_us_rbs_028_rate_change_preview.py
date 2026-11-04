# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-028 (EP-RBS-05) — CR-075 wave S, runbook 16.
# Rules:    BR-RBS-002 · BR-RBS-011 · BR-RBS-012 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-023 · BR-RAT-031 · BR-RAT-007 · BR-RAT-032 · BR-BIL-004 ·
#           CLAUDE.md hard rules 2 and 3 · B14 rules 31, 32
# Questions:OQ-319 (whole bill or this schedule's portion)
# Tests:    this file. The whole-database half is the seeded run recorded in
#           the lane report — `10-scripts/render-checks/rbs_c_seed_run.py
#           --runbook rate_change_preview`, which is the only place `BR-RBS-002`
#           is tested against a real database rather than against a mock.
# Impacts:  apps/runbooks/definitions/rate_change_preview.py ·
#           apps/rating/runbook_reads.py
# ───────────────────────────────────────────────────────
"""Runbook 16, against the rules rather than against itself.

⚠ **TWO HALVES, AND THE SECOND ONE IS THE ONE `TC-RBS-028.3` ASKS FOR.** The
first half drives the runbook over mocked seams and asserts what a board sees.
The second builds a REAL tariff, a real activated version and a real draft, and
runs `rating.runbook_reads.reprice_under_draft` through
`apps.rating.engine.price_period` — because *"the pricing path is the rating
engine's, identical to a real run"* cannot be proved by a mock, and its own *must
first fail on* is **a second implementation**.
"""

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import rate_change_preview as rc
from apps.runbooks.engine import executor

# ⚠ **THE STAR IMPORT CARRIES THE AUTOUSE `sqlite_guc`, AND WITHOUT IT THE
# DATABASE HALF BELOW CANNOT RUN AT ALL** — `core.tenancy` sets the tenant
# marker with `set_config`, which SQLite does not have. `DEF-2761`'s fixture
# sends the GUC to a recorder on SQLite ONLY and to the real connection on
# PostgreSQL, which is why the guard in it must never be removed.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — incl. the autouse sqlite_guc
from tests.test_us_met_helpers import brazos, growth_plan, identity_seam  # noqa: F401

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)


def _bill(bill_id="b1", account_id="a1", quantity="11000", amount="59.0000", invoice_no="INV-1"):
    return {
        "bill_id": bill_id,
        "invoice_no": invoice_no,
        "account_id": account_id,
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "service_date": "2026-08-31",
        "currency": "USD",
        "subtotal": amount,
        "tax_total": "0.0000",
        "total": amount,
        "lines": [
            {
                "kind": "usage",
                "description": "Water usage",
                "amount": amount,
                "quantity": quantity,
                "unit": "gal",
                "unit_price": "0.0054",
                "service": "water",
                "taxable": True,
                "tariff_version_id": "v-old",
            }
        ],
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the seven reads runbook 16 makes.

    The default is ONE bill of 11,000 gallons charged `$59.00`, and a draft that
    moves it to `$62.54` — `BR-RAT-091`'s own ratified worked example, which is
    exactly `+6%` and is why the scope is this schedule's own portion
    (`OQ-319`).
    """
    state = {
        "bills": [_bill()],
        "change": {
            "found": True,
            "comparable": True,
            "label": "Water 2027",
            "service": "water",
            "unit": "gal",
            "currency": "USD",
            # Every version this schedule has ever had. A bill's usage line
            # carries the one that priced it, stamped at issue and frozen, and
            # that is what puts the bill in scope.
            "version_ids": ["v-old"],
            "changes": [
                {"clause": "block_price", "sentence": "Tier 2 price", "from_quantity": "5000"},
                {
                    "clause": "new_block",
                    "sentence": "New top block above 20,000 gal",
                    "from_quantity": "20000",
                },
            ],
        },
        "priced": {
            "b1": {
                "before": "59.0000",
                "after": "62.5400",
                "change": "3.5400",
                "currency": "USD",
                "quantity": "11000.0000",
                "unit": "gal",
                "lines_before": [
                    {"kind": "usage", "description": "Water usage", "amount": "59.0000"}
                ],
                "lines_after": [
                    {"kind": "usage", "description": "Water usage", "amount": "62.5400"}
                ],
            }
        },
        "unpriced": {},
        "names": {"a1": "Alvarez, M."},
        "types": {"a1": {"type_code": "res", "type_name": "Residential"}},
        "samples": frozenset(),
    }

    monkeypatch.setattr(
        rc.billing_seam,
        "issued_bills_for_run",
        lambda run_id, *, service_code=None: {
            "bills": list(state["bills"]),
            "bills_in_the_cycle": len(state["bills"]),
            "lines_of_this_service": len(state["bills"]),
        },
    )
    monkeypatch.setattr(
        rc.rating_seam, "schedule_change", lambda *, version_id, service_date: dict(state["change"])
    )
    monkeypatch.setattr(
        rc.rating_seam,
        "reprice_under_draft",
        lambda *, version_id, rows, service_date: {
            "found": True,
            "comparable": True,
            "service": "water",
            "currency": "USD",
            "priced": {
                one["id"]: state["priced"][one["id"]]
                for one in rows
                if one["id"] in state["priced"]
            },
            "unpriced": dict(state["unpriced"]),
            "priced_by": "apps.rating.engine.price_period — the same call a bill makes",
        },
    )
    monkeypatch.setattr(rc.customers_seam, "account_names", lambda ids: dict(state["names"]))
    monkeypatch.setattr(rc.customers_seam, "account_types_for", lambda ids: dict(state["types"]))
    monkeypatch.setattr(rc.customers_seam, "sample_account_ids", lambda: state["samples"])
    monkeypatch.setattr(rc.tenancy_seam, "today", lambda: TODAY)
    monkeypatch.setattr(rc.tenancy_seam, "currency", lambda: "USD")
    return state


def _run(params=None):
    definition = rc.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id="t",
        params={
            "proposed_schedule": "v-draft",
            "against_cycle": "run-1",
            "services": "water",
            "call_it_large_above": "15.000000",
            "show_biggest_movers": 50,
            "group_by": "account_type",
            "revenue_by_service": True,
            **(params or {}),
        },
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_over_bills_with_no_ports_at_all(seams):
    """`TC-RBS-028.2` — no bill is re-issued and no bill number is consumed."""
    assert rc.RUNBOOK.is_check
    assert rc.RUNBOOK.ports == ()
    assert rc.RUNBOOK.subject_type == "bill"
    assert rc.RUNBOOK.category == "plans_rates"
    assert len(rc.RUNBOOK.steps) == 6
    assert [one.mode for one in rc.RUNBOOK.steps].count("per_record") == 1
    assert not any(step.writes for step in rc.RUNBOOK.steps)


def test_the_execution_context_holds_no_writer(seams):
    """`BR-RBS-002` — the capability is ABSENT, not refused at runtime."""
    ctx = executor.build_context(rc.RUNBOOK, tenant_id="t", params={})
    assert dict(ctx.ports) == {}


def test_the_sums_are_set_steps_and_the_pricing_is_per_record(seams):
    """`BR-RBS-023` · `US-RBS-028` §1, and `TC-RBS-17`'s shape one level up."""
    result = _run()
    assert result.step_runs[rc.STEP_REPRICE] == 1
    assert result.step_runs[rc.STEP_DISTRIBUTE] == 1
    assert result.step_runs[rc.STEP_REVENUE] == 1
    assert result.step_runs[rc.STEP_COMPARE] == len(result.subjects)


# ── the scope ─────────────────────────────────────────────────────────────


def test_the_scope_is_every_issued_bill_of_the_chosen_cycle(seams):
    seams["bills"] = [_bill(), _bill("b2", "a2", "4000", "24.0000", "INV-2")]
    assert {one.subject_id for one in _run().subjects} == {"b1", "b2"}


def test_a_run_with_no_draft_or_no_cycle_pins_nothing_and_says_so(seams):
    result = _run({"proposed_schedule": None})
    assert result.subjects == ()
    assert "This draft changes nothing" in _blocks(result)["records"]["empty"]["title"]


def test_a_sample_bill_is_re_priced_like_any_other_and_is_COUNTED(seams):
    """`RB-116`'s scope table has NO *Never include* row, and `RB-112`'s has one.

    ⚠ **THE ASYMMETRY IS THE CARD'S.** `BR-RBS-014`'s sample rule is about an
    ACTION — *a sample record is never ACTED ON* — and this runbook acts on
    nothing. Guarding sample bills out has the worse failure mode: on a trial
    tenant, where 72 of 78 accounts are sample records, every bill of the cycle
    would go and a board would read **"this draft changes nothing"** over a run
    that looked at nothing. So they are re-priced and the count travels, which
    is `RB-119`'s own posture one object along.
    """
    seams["bills"] = [_bill(), _bill("b2", "a2", "4000", "24.0000", "INV-2")]
    seams["priced"]["b2"] = dict(seams["priced"]["b1"])
    seams["samples"] = frozenset({"a2"})
    result = _run()
    assert result.guarded == ()
    assert len(result.records) == 2
    assert _checked(result, rc.STEP_CYCLE)["bills_belonging_to_a_sample_account"] == 1
    assert _checked(result, rc.STEP_REPRICE)["bills_priced"] == 2


def test_every_set_step_walks_only_the_subjects_the_executor_hands_it(seams):
    """⚠ **`DEF-RBS-4395`, FOUND BY RUNNING THIS ON A REAL UTILITY.** The
    re-price happened in `resolve()` and the sums walked the whole cycle, while
    the per-record step walked the subjects the executor hands in — and guards
    run BETWEEN the two. The seeded run drew **47 bills up 5–15% and +$339.04 of
    revenue over a table with no rows in it**.

    This runbook now declares no guard at all, so the two sets are the same
    here; the assertion is on the WIRING — the re-price is a step, not a
    resolve, so a guard added later cannot put the halves out of step again.
    """
    result = _run()
    assert rc.RUNBOOK.guards == ()
    assert (result.set_results.get(rc.STEP_REPRICE) or {}).get("checked", {})[
        "bills_priced"
    ] == len(result.records)
    assert _checked(result, rc.STEP_CYCLE)["re_priced_after_the_guards"] == len(result.subjects)


# ── the comparison ────────────────────────────────────────────────────────


def test_the_ratified_worked_example_moves_by_six_percent(seams):
    """`BR-RAT-091`, finance-signed: `$59.00 → $62.54` on an 11 kgal household
    is `+6.00%` exactly, which is what fixes the scope at this schedule's own
    portion (`OQ-319`)."""
    row = _run().records[0]
    assert Decimal(row.data["as_issued"]) == Decimal("59.0000")
    assert Decimal(row.data["under_draft"]) == Decimal("62.5400")
    assert Decimal(row.data["change"]) == Decimal("3.5400")
    assert Decimal(row.data["change_pct"]).quantize(Decimal("0.01")) == Decimal("6.00")


def test_the_change_is_applied_to_what_the_customer_was_actually_charged(seams):
    """⚠ The DIFFERENCE travels, so the base-charge precedence (`DEF-154`)
    cancels out of the subtraction instead of appearing as a change nobody
    proposed. Here the engine's baseline is $2 below the issued amount and the
    row still moves by exactly what the draft does."""
    seams["priced"]["b1"] = dict(seams["priced"]["b1"], before="57.0000", after="60.5400")
    row = _run().records[0]
    assert Decimal(row.data["as_issued"]) == Decimal("59.0000")
    assert Decimal(row.data["under_draft"]) == Decimal("62.5400")


def test_the_run_reports_how_many_bills_its_baseline_failed_to_reproduce(seams):
    """The run's own error bar — hard-won law 7 — and it compares USAGE with USAGE.

    ⚠ **A FIRST BUILD COMPARED THE ENGINE'S WHOLE PRICED PORTION AGAINST THE
    ISSUED USAGE *AND* BASE, AND REPORTED `0 of 49` ON THE SEEDED UTILITY** — a
    true statement about a comparison that could never balance, because
    `DEF-154` makes the base charge the PLAN's figure where the plan states one
    and both engine passes carry the SCHEDULE's. An error bar that can only ever
    say *no* is not an error bar.
    """
    checked = _checked(_run(), rc.STEP_REPRICE)
    assert checked["baseline_reproduced_the_issued_usage"] == 1
    assert checked["baseline_did_not_reproduce_the_issued_usage"] == 0
    seams["priced"]["b1"] = dict(
        seams["priced"]["b1"],
        lines_before=[{"kind": "usage", "description": "Water usage", "amount": "57.0000"}],
    )
    checked = _checked(_run(), rc.STEP_REPRICE)
    assert checked["baseline_reproduced_the_issued_usage"] == 0
    assert checked["baseline_did_not_reproduce_the_issued_usage"] == 1


def test_the_base_charge_the_preview_holds_constant_is_a_figure_on_the_run(seams):
    """`DEF-154` — a plan's base and a schedule's base are both lawful, and the
    engine pass carries the schedule's. It cancels out of every change and is
    printed so a reader can see how much of the column was held constant."""
    billed = _bill()
    billed["lines"].append(
        {
            "kind": "base",
            "description": "Water base charge",
            "amount": "8.0000",
            "quantity": None,
            "unit": None,
            "unit_price": None,
            "service": "water",
            "taxable": True,
            "tariff_version_id": "v-old",
        }
    )
    seams["bills"] = [billed]
    checked = _checked(_run(), rc.STEP_REPRICE)
    assert Decimal(checked["base_charge_held_constant"]) == Decimal("8.0000")
    # …and the usage half still reproduces, because the base is outside it.
    assert checked["baseline_reproduced_the_issued_usage"] == 1


def test_a_bill_this_draft_does_not_touch_is_counted_and_not_dropped(seams):
    """The card's **88 Unchanged** tile. Dropping it would make the denominator
    of every percentage on the screen wrong."""
    electricity_only = _bill("b2", "a2", "4000", "24.0000", "INV-2")
    electricity_only["lines"][0]["service"] = "electric"
    seams["bills"] = [_bill(), electricity_only]
    result = _run()
    assert len(result.records) == 2
    assert result.records[1].outcome == rc.OUTCOME_UNCHANGED
    tile = _blocks(result)["kpis"]["tiles"][3]
    assert tile["value"] == {"kind": "text", "text": "1"}
    assert tile["detail"] == "This draft does not touch them"


def test_unchanged_never_absorbs_a_bill_the_engine_could_not_price(seams):
    """⚠ Hard-won law 7 on the one screen a rate case is filed from: *this draft
    does not touch it* and *nobody could price it* are different sentences."""
    seams["bills"] = [_bill(), _bill("b2", "a2", "4000", "24.0000", "INV-2")]
    seams["unpriced"] = {"b2": "engine:BillingRuleError"}
    result = _run()  # only b1 is in `priced`
    assert result.records[1].outcome == rc.OUTCOME_NOT_PRICED
    tile = _blocks(result)["kpis"]["tiles"][3]
    assert tile["value"] == {"kind": "text", "text": "0"}
    assert tile["detail"] == "1 could not be priced"


def test_a_bill_the_engine_refused_is_counted_with_its_reason_never_priced_at_zero(seams):
    """`rate_change_impact`'s own rule: averaging an unmeasurable row in as
    `0.00%` drags the worst case toward the middle."""
    seams["priced"] = {}
    seams["unpriced"] = {"b1": "engine:BillingRuleError"}
    result = _run()
    assert result.records[0].outcome == rc.OUTCOME_NOT_PRICED
    checked = _checked(result, rc.STEP_REPRICE)
    assert checked["bills_that_could_not_be_priced"] == 1
    assert checked["why_they_could_not_be_priced"] == ["engine:BillingRuleError"]


def test_the_bills_own_day_count_reaches_the_engine(seams, monkeypatch):
    """A re-price against a nominal 30 days misprices every proration."""
    seen = {}

    def _capture(*, version_id, rows, service_date):
        seen["rows"] = rows
        seen["service_date"] = service_date
        return {"found": True, "comparable": True, "priced": {}, "unpriced": {}, "priced_by": "x"}

    # ⚠ `monkeypatch`, NEVER a bare assignment on the seam module: a rebind
    # would outlive this test and every later one would price through a stub.
    monkeypatch.setattr(rc.rating_seam, "reprice_under_draft", _capture)
    _run()
    assert seen["rows"][0]["cycle_days"] == 31  # 1–31 August, inclusive
    assert seen["service_date"] == dt.date(2026, 8, 31)


# ── the *Why* on every mover ──────────────────────────────────────────────


def test_every_mover_names_the_clause_of_the_draft_that_did_it(seams):
    """`TC-RBS-028.1`'s *must first fail on*: **a total with no per-clause
    attribution — a board cannot act on it.**"""
    assert _run().records[0].reason == "Tier 2 price"


def test_the_clause_named_is_the_one_this_accounts_usage_actually_reached(seams):
    """A new top block above 20,000 gallons is the story on a farm and
    irrelevant on a flat, and both are true of the same draft."""
    seams["bills"] = [_bill("b1", "a1", "41200", "412.8000")]
    seams["priced"] = {
        "b1": dict(
            seams["priced"]["b1"],
            quantity="41200.0000",
            before="412.8000",
            after="538.1000",
            change="125.3000",
        )
    }
    assert _run().records[0].reason == "New top block above 20,000 gal"


def test_a_bill_that_did_not_move_says_so_rather_than_naming_a_clause(seams):
    seams["priced"]["b1"] = dict(seams["priced"]["b1"], after="59.0000", change="0.0000")
    assert _run().records[0].reason == "No change under this draft"


# ── the distribution and the grouping ─────────────────────────────────────


def test_the_distribution_is_the_cards_five_rows(seams):
    rows = _blocks(_run())["ranked"]["rows"]
    assert [one["id"] for one in rows] == list(rc.BANDS)
    assert rows[0]["label"] == "Down more than 15%"
    assert rows[2]["label"] == "Within 5%"
    # +6.00% lands in *Up 5–15%*
    assert rows[3]["value"] == {"kind": "text", "text": "1"}


def test_a_move_above_the_threshold_lands_in_the_row_that_generates_calls(seams):
    seams["priced"]["b1"] = dict(seams["priced"]["b1"], after="80.0000", change="21.0000")
    blocks = _blocks(_run())
    assert blocks["ranked"]["rows"][4]["value"] == {"kind": "text", "text": "1"}
    assert blocks["kpis"]["tiles"][4]["value"] == {"kind": "text", "text": "1"}
    assert blocks["kpis"]["tiles"][4]["label"] == "Up more than 15%"


def test_the_threshold_is_the_tenants_own_and_reaches_the_labels(seams):
    blocks = _blocks(_run({"call_it_large_above": "5.000000"}))
    assert blocks["ranked"]["rows"][4]["label"] == "Up more than 5%"
    assert blocks["kpis"]["tiles"][4]["label"] == "Up more than 5%"


def test_bills_are_grouped_by_account_type(seams):
    rows = _blocks(_run())["breakdown"]["rows"]
    assert rows[0]["cells"]["type"] == {"kind": "text", "text": "Residential"}
    assert rows[0]["cells"]["bills"] == {"kind": "text", "text": "1"}


def test_an_account_with_no_type_is_its_own_group_and_is_counted(seams):
    """Hard-won law 7 — a group called *Not set* is honest where silence is not."""
    seams["types"] = {}
    result = _run()
    assert _checked(result, rc.STEP_DISTRIBUTE)["bills_with_no_account_type"] == 1
    assert _blocks(result)["breakdown"]["rows"][0]["cells"]["type"]["text"] == "Not set"


# ── the money ─────────────────────────────────────────────────────────────


def test_the_revenue_tile_declares_its_basis_and_it_is_priced(seams):
    """`BR-REP-001` · `DEF-RBS-4350` — nothing here was posted or cleared."""
    tile = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "revenue")
    assert tile["basis"] == "priced"
    assert tile["value"]["kind"] == "money"
    assert Decimal(tile["value"]["amount"]) == Decimal("3.5400")
    assert tile["value"]["currency"] == "USD"


def test_the_revenue_step_sums_one_service_and_names_it(seams):
    checked = _checked(_run(), rc.STEP_REVENUE)
    assert checked["service"] == "water"
    assert checked["basis"] == "priced"
    assert Decimal(checked["revenue_change"]) == Decimal("3.5400")
    assert Decimal(checked["revenue_change_percent"]).quantize(Decimal("0.01")) == Decimal("6.00")


def test_a_percentage_is_stored_to_six_and_carries_its_convention(seams):
    """Hard rule 2 — and the product stores both fractions and percent points,
    which is why the basis is required rather than assumed."""
    cell = _blocks(_run())["records"]["rows"][0]["cells"]["change"]
    assert cell["kind"] == "percent"
    assert cell["basis"] == "points"
    assert cell["direction"] == "up"
    assert len(cell["value"].split(".")[1]) == 6


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_blocks_are_the_cards_five_and_there_is_no_verdict(seams):
    assert [block["block"] for block in _run().report] == [
        "kpis",
        "ranked",
        "records",
        "breakdown",
        "downloads",
    ]


def test_the_column_is_headed_by_the_cycle_the_bills_were_issued_for(seams):
    """The build sheet's `August` is a VALUE, not copy."""
    columns = _blocks(_run())["records"]["columns"]
    assert columns[2]["label"] == "August"
    assert _blocks(_run())["breakdown"]["columns"][2]["label"] == "August"


def test_the_movers_table_is_capped_at_the_parameter_and_ranked_by_the_move(seams):
    seams["bills"] = [
        _bill("b1", "a1", "11000", "59.0000", "INV-1"),
        _bill("b2", "a2", "41200", "412.8000", "INV-2"),
    ]
    seams["priced"]["b2"] = dict(
        seams["priced"]["b1"],
        quantity="41200.0000",
        before="412.8000",
        after="538.1000",
        change="125.3000",
    )
    seams["names"]["a2"] = "Marsh Farms"
    seams["types"]["a2"] = {"type_code": "irr", "type_name": "Irrigation"}
    rows = _blocks(_run())["records"]["rows"]
    assert rows[0]["cells"]["account"]["text"] == "Marsh Farms"
    assert _blocks(_run({"show_biggest_movers": 1}))["records"]["total"] == 1


def test_no_database_id_and_no_internal_code_reaches_a_drawn_cell(seams):
    """B14 rules 31 and 32."""
    for row in _blocks(_run())["records"]["rows"]:
        drawn = " ".join(
            str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
        )
        assert "b1" != drawn
        assert "v-draft" not in drawn
        assert "BR-" not in drawn
        assert "OQ-" not in drawn


def test_every_record_names_a_fix_route_and_it_is_tenant_relative(seams):
    for record in _run().records:
        assert record.fix_route in {"plans-rates", "billing"}
        assert not record.fix_route.startswith("/")


# ══════════════════════════════════════════════════════════════════════════
# TC-RBS-028.3 — THE PRICING PATH IS THE ENGINE'S, AGAINST REAL ROWS
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS HALF CANNOT BE MOCKED, WHICH IS THE POINT.** Its *must first fail on*
# is **a second implementation**, and a fixture that answered `$62.54` would pass
# over one. So it builds a tariff, an ACTIVATED version and a DRAFT, and asserts
# the figure `reprice_under_draft` returns is the one `engine.price_period`
# computes from the same rows.


@pytest.fixture
def a_draft_that_raises_the_price(brazos):
    """A flat water schedule at `$0.0050`/gal, and a draft at `$0.0055`.

    `BR-RAT-032`: a flat tariff is stored as ONE `0 → ∞` tier, so the ladder is
    one row on each side and the arithmetic a reader can check by hand is
    `10,000 gal × $0.0050 = $50.00` against `10,000 × $0.0055 = $55.00`.

    Built on the PROVISIONED tenant rather than on a bare `Tenant` row, so the
    services, the units of measure and the number series a real utility carries
    are all in place — a fixture that could not tell a working build from a
    broken one is what hard-won law 2's 2026-09-05 note is about.
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    tenant = brazos
    # ⚠ `services` is the PLATFORM catalogue and carries no tenant (`BR-RAT-024`,
    # eleven rows seeded in migration 0001). It is READ here, never created —
    # a second `water` row would be a twelfth service nobody ruled.
    service = tenancy_models.Service.objects.get(code="water")
    with core_tenancy.tenant_context(tenant.id):
        tariff = rating_models.Tariff.objects.create(
            tenant=tenant, name="Residential Water", service=service
        )
        live = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=tariff,
            model="flat",
            currency="USD",
            uom="gal",
            effective_from=dt.date(2026, 1, 1),
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=live,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=Decimal("0.005000"),
        )
        draft = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=tariff,
            model="flat",
            currency="USD",
            uom="gal",
            effective_from=None,  # BR-RAT-031 — a NULL effective_from IS the draft
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=draft,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=Decimal("0.005500"),
        )
        yield {"tenant": tenant, "tariff": tariff, "live": live, "draft": draft}


def test_the_reprice_is_the_engines_own_answer_and_not_a_second_one(a_draft_that_raises_the_price):
    """`TC-RBS-028.3` — *the rating engine's, identical to a real run*.

    10,000 gallons at `$0.0050` is `$50.00`; the same 10,000 at the draft's
    `$0.0055` is `$55.00`; the change is `$5.00`. Every figure below comes out
    of `engine.price_period`, and the last assertion calls that engine DIRECTLY
    and requires the two to agree to four decimals — so a second implementation
    inside this module would go red naming the number.
    """
    from types import SimpleNamespace

    from apps.rating import engine, runbook_reads, selectors
    from core import tenancy as core_tenancy

    fixture = a_draft_that_raises_the_price
    with core_tenancy.tenant_context(fixture["tenant"].id):
        answer = runbook_reads.reprice_under_draft(
            version_id=fixture["draft"].id,
            rows=[
                {
                    "id": "b1",
                    "quantity": "10000",
                    "unit": "gal",
                    "currency": "USD",
                    "cycle_days": 31,
                    "service_days": 31,
                }
            ],
            service_date=dt.date(2026, 8, 31),
        )
        assert answer["comparable"] is True
        priced = answer["priced"]["b1"]
        assert Decimal(priced["before"]) == Decimal("50.0000")
        assert Decimal(priced["after"]) == Decimal("55.0000")
        assert Decimal(priced["change"]) == Decimal("5.0000")

        # ⚠ THE SAME NUMBER, TAKEN FROM THE ENGINE DIRECTLY.
        inputs = selectors.pricing_inputs_for_version(fixture["draft"], dt.date(2026, 8, 31))
        direct = engine.price_period(
            tariff=selectors._engine_tariff(inputs, "water", None),
            consumption=SimpleNamespace(
                amount=Decimal("10000"), unit="gal", windows=(), demand=None
            ),
            period=SimpleNamespace(cycle_days=31, service_days=31),
            account=SimpleNamespace(currency="USD", tax_exempt=False),
        )
        assert direct.total.quantize(Decimal("0.0001")) == Decimal(priced["after"])


def test_the_clause_list_names_what_actually_moved(a_draft_that_raises_the_price):
    from apps.rating import runbook_reads
    from core import tenancy as core_tenancy

    fixture = a_draft_that_raises_the_price
    with core_tenancy.tenant_context(fixture["tenant"].id):
        change = runbook_reads.schedule_change(
            version_id=fixture["draft"].id, service_date=dt.date(2026, 8, 31)
        )
    assert change["comparable"] is True
    assert change["service"] == "water"
    kinds = {one["clause"] for one in change["changes"]}
    # A flat tariff's price lives in `unit_price` (`BR-RAT-032` unwraps the one
    # 0→∞ tier), so what moved is the unit price and nothing else.
    assert kinds == {"unit_price"}
    assert change["changes"][0]["from_quantity"] == "0"


def test_a_draft_this_tenant_does_not_hold_is_refused_by_absence(a_draft_that_raises_the_price):
    """`HR-1` — a cross-tenant id answers exactly like an absent one."""
    import uuid

    from apps.rating import runbook_reads
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(a_draft_that_raises_the_price["tenant"].id):
        answer = runbook_reads.schedule_change(
            version_id=uuid.uuid4(), service_date=dt.date(2026, 8, 31)
        )
    assert answer["found"] is False


def test_the_draft_picker_lists_the_draft_and_what_it_replaces(a_draft_that_raises_the_price):
    from apps.rating import runbook_reads
    from core import tenancy as core_tenancy

    fixture = a_draft_that_raises_the_price
    with core_tenancy.tenant_context(fixture["tenant"].id):
        rows = runbook_reads.draft_schedules()
    assert [one["label"] for one in rows] == ["Residential Water"]
    assert rows[0]["comparable"] is True
    assert rows[0]["baseline_version_id"] == str(fixture["live"].id)
    # B14 rule 31 — the schedule's NAME is what a manager picks.
    assert rows[0]["version_id"] == str(fixture["draft"].id)


def test_a_bill_priced_by_another_schedule_is_counted_and_never_re_priced(seams):
    """⚠ **THE REAL RUN FOUND THIS AND NO MOCK COULD HAVE (`DEF-RBS-4407`).**

    On the seeded utility the July cycle's water lines carry a version of the
    SAMPLE residential schedule while the draft belongs to the utility's own.
    Re-pricing them anyway produced a confident **+$339.04 (+7.2%) across 49
    bills** for a change none of those customers would ever have seen. The
    run's own error bar was already saying so — *0 of 49 reproduced* — which is
    what a number beside a claim is for.

    `invoice_lines.tariff_version_id` is stamped at issue and frozen, so which
    schedule priced a line is READ rather than inferred.
    """
    elsewhere = _bill("b2", "a2", "9000", "48.0000", "INV-2")
    elsewhere["lines"][0]["tariff_version_id"] = "v-somebody-elses"
    seams["bills"] = [_bill(), elsewhere]
    seams["priced"]["b2"] = dict(seams["priced"]["b1"])
    result = _run()
    checked = _checked(result, rc.STEP_CYCLE)
    assert checked["bills_priced_by_this_schedule"] == 1
    assert checked["bills_priced_by_another_schedule"] == 1
    assert _checked(result, rc.STEP_REPRICE)["bills_priced"] == 1
    assert result.records[1].outcome == rc.OUTCOME_UNCHANGED
    # …and the revenue is one bill's, not two.
    assert Decimal(_checked(result, rc.STEP_REVENUE)["revenue_change"]) == Decimal("3.5400")


def test_a_line_with_no_version_on_it_is_never_claimed(seams):
    """A preview may not claim a bill it cannot place."""
    orphan = _bill("b2", "a2", "9000", "48.0000", "INV-2")
    orphan["lines"][0]["tariff_version_id"] = None
    seams["bills"] = [orphan]
    result = _run()
    assert _checked(result, rc.STEP_CYCLE)["bills_priced_by_this_schedule"] == 0
    assert _checked(result, rc.STEP_REPRICE)["bills_priced"] == 0
