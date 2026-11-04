# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-024 (EP-RBS-05) — CR-075 wave S, runbook 12.
# Rules:    BR-RBS-002 · BR-RBS-011 · BR-RBS-012 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-023 · BR-RBS-032 · BR-CUS-100 · BR-PAY-017 · CLAUDE.md hard
#           rules 2 and 8 · B14 rules 31, 32, 33
# Questions:OQ-RBS-1757 (the AREA-WIDE weather moratorium)
# Tests:    this file. The PostgreSQL half is the seeded run recorded in the
#           lane report — `10-scripts/render-checks/rbs_c_seed_run.py --runbook
#           disconnect_eligibility`, which is the only place `BR-RBS-002` is
#           tested against a real database rather than against a mock.
# Impacts:  apps/runbooks/definitions/disconnect_eligibility.py
# ───────────────────────────────────────────────────────
"""Runbook 12, against the rules rather than against itself.

⚠ **THE FIXTURE IS THE CARD'S OWN MORNING, SHRUNK.** `RB-112` draws 23 accounts,
14 eligible and 9 removed; this file builds five accounts covering every removal
reason the product can actually produce, and the twenty-three-row arithmetic is
asserted as a SHAPE — eligible plus removed equals the scope, and each removal
carries a reason. The real run's figures on the seeded utility are in the lane
report and neither number is quoted alone.
"""

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import disconnect_eligibility as de
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)  # a Monday
SERVED = "2026-09-01"


def _case(
    account_id="a1",
    account_no="A-1001",
    label="Fielding, K.",
    served_on=SERVED,
    channel="certified_mail",
    recorded=True,
    absence=None,
    signed_for_on=None,
    is_sample=False,
    cut_reachable=True,
):
    proof = {
        "tier": "tier_3_48_hour",
        "recorded": recorded,
        "channel": channel,
        "reference": "7012 3456",
        "served_on": served_on,
        "signed_for_on": signed_for_on,
    }
    if not recorded:
        proof["absence"] = absence or "awaiting_proof_of_service"
    return {
        "account_id": account_id,
        "account_no": account_no,
        "label": label,
        "unit_id": f"u-{account_id}",
        "premises_id": f"p-{account_id}",
        "is_sample": is_sample,
        "case_no": f"DSC-26-{account_id}",
        "state": "notice_sent",
        "tier": "tier_3_48_hour",
        "sequence": "service",
        "notice_issued_on": served_on,
        "proof": proof,
        "cut_reachable": cut_reachable,
        "cut_not_reachable_because": "" if cut_reachable else "account_closed_cannot_cut",
    }


def _protection(medical=False, plan=False, moratorium=False):
    held = {}
    if medical:
        held["medical_certificate"] = "2026-09-03"
    if plan:
        held["payment_plan"] = "2026-08-17"
    if moratorium:
        held["weather_moratorium"] = "2026-08-27"
    return {
        "all_clear": not held,
        "in_force": sorted(held),
        "checks": [],
        "medical": medical,
        "plan_in_good_standing": plan,
        "weather_moratorium": moratorium,
        "reasons": {kind: "in force" for kind in held},
        "since": dict(held),
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the eight reads runbook 12 makes.

    The default is ONE account at the last tier, served by certified mail on 1
    September, with the notice period long past and nothing else against it —
    the card's own first row.
    """
    state = {
        "rows": [_case()],
        "delivery_reported": False,
        "protections": {},
        "payments": [],
        "notice_hours": {"readable": True, "hours": 48},
        "ladder": {
            "rows": [
                {
                    "account_id": "a1",
                    "account_no": "A-1001",
                    "balance": "2880.000000",
                    "currency": "USD",
                    "current_tier": None,
                }
            ],
            "problems": [],
        },
        "holidays": [],
        "units": {"u-a1": {"premise_address": "5 Vine St", "premises_id": "p-a1"}},
        "meters": [{"unit_id": "u-a1", "asset_no": "WM-114", "premises_id": "p-a1"}],
    }

    monkeypatch.setattr(
        de.customers_seam,
        "final_notice_board",
        lambda *, as_of, tier=None: {
            "as_of": as_of.isoformat(),
            "tier": "tier_3_48_hour",
            "rows": list(state["rows"]),
            "cases_at_this_tier": len(state["rows"]),
            "cases_whose_cut_is_not_reachable": sum(
                1 for one in state["rows"] if not one["cut_reachable"]
            ),
            "delivery_reported": state["delivery_reported"],
            "delivery_not_reported_because": "no provider adapter exists on any channel",
            "proof_channel_required": "certified_mail",
        },
    )
    monkeypatch.setattr(
        de.customers_seam,
        "protection_board",
        lambda account_ids, *, as_of: {
            "as_of": as_of.isoformat(),
            "accounts": {
                one: state["protections"].get(one, _protection()) for one in account_ids
            },
            "counts": {
                "medical_certificate": sum(
                    1 for one in state["protections"].values() if one["medical"]
                ),
                "payment_plan": sum(
                    1 for one in state["protections"].values() if one["plan_in_good_standing"]
                ),
                "weather_moratorium": sum(
                    1 for one in state["protections"].values() if one["weather_moratorium"]
                ),
            },
            "accounts_checked": len(account_ids),
            "dispute_checked": 0,
            "dispute_not_checked": len(account_ids),
            "dispute_not_checked_because": "nothing in this product stores a disputed amount",
        },
    )
    monkeypatch.setattr(
        de.payments_seam,
        "collections_ladder_board",
        lambda *, as_of, account_ids=None, medical_hold_account_ids=(): dict(state["ladder"]),
    )
    monkeypatch.setattr(
        de.payments_seam, "ladder_rungs", lambda: ("friendly", "first_10_day", "second_5_day", "final_48_hour")
    )
    monkeypatch.setattr(
        de.payments_seam,
        "payments_recorded_between",
        lambda account_ids, start, end: list(state["payments"]),
    )
    monkeypatch.setattr(
        de.payments_seam, "final_notice_hours", lambda: dict(state["notice_hours"])
    )
    monkeypatch.setattr(de.tenancy_seam, "today", lambda: TODAY)
    monkeypatch.setattr(de.tenancy_seam, "currency", lambda: "USD")
    monkeypatch.setattr(de.tenancy_seam, "holiday_calendar", lambda: list(state["holidays"]))
    monkeypatch.setattr(
        de.metering_seam,
        "resolve_anchors",
        lambda unit_ids, premises_ids: {"units": dict(state["units"]), "premises": {}},
    )
    monkeypatch.setattr(
        de.metering_seam,
        "meter_read_history",
        lambda **kwargs: [dict(one, reads=[]) for one in state["meters"]],
    )
    return state


def _run(params=None):
    definition = de.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id="t",
        params={
            "service": "water",
            "minimum_balance": "50.0000",
            "working_days_only": True,
            "check_payments_to": "06:00",
            # AMENDED 2026-10-01 (billing red triage): `OQ-RBS-1757` CLOSED
            # (`bb1646acd`, PO 2026-09-07: *"when you run this runbook, ask
            # user to check temp range from ddropdown and use that details in
            # logic"*). The band is a REQUIRED run parameter and an absent one
            # holds the whole list, so every case here read `weather_moratorium`
            # from that commit on (16 of 38 red). A mild day is what each case
            # always assumed; the holding bands are `test_oq_rbs_1757_weather_band`.
            "weather_today": de.WEATHER_BAND_MILD,
            **(params or {}),
        },
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_over_accounts_with_no_ports_at_all(seams):
    """`TC-RBS-024.3` — *no disconnect port, and there must be none*."""
    assert de.RUNBOOK.is_check
    assert de.RUNBOOK.ports == ()
    assert de.RUNBOOK.subject_type == "account"
    assert de.RUNBOOK.category == "collections"
    assert len(de.RUNBOOK.steps) == 8
    assert [one.mode for one in de.RUNBOOK.steps].count("per_record") == 1
    assert not any(step.writes for step in de.RUNBOOK.steps)


def test_the_execution_context_holds_no_writer(seams):
    """`BR-RBS-002` — the capability is ABSENT, not refused at runtime."""
    ctx = executor.build_context(de.RUNBOOK, tenant_id="t", params={})
    assert dict(ctx.ports) == {}


# ── step 1 · the last tier ────────────────────────────────────────────────


def test_the_scope_is_the_cases_at_the_last_tier(seams):
    result = _run()
    assert {one.subject_id for one in result.subjects} == {"a1"}
    assert _checked(result, de.STEP_GATHER)["cases_at_the_last_tier"] == 1


def test_it_prints_how_many_payments_ladder_also_shows_at_its_final_rung(seams):
    """`DEF-675` as a NUMBER rather than as a silence — the two ladders overlap
    and the overlap is unruled."""
    checked = _checked(_run(), de.STEP_GATHER)
    assert checked["of_those_also_at_payments_final_rung"] == 0
    seams["ladder"]["rows"][0]["current_tier"] = "final_48_hour"
    assert _checked(_run(), de.STEP_GATHER)["of_those_also_at_payments_final_rung"] == 1


def test_a_sample_account_is_guarded_counted_and_seen_by_no_step(seams):
    """`BR-RBS-012` — and *seen by no step* is the half that was broken.

    ⚠ **`DEF-RBS-4395`, FOUND BY RUNNING THIS ON A REAL UTILITY AND NOT BY ANY
    TEST.** Steps 2, 3 and 4 walked every case at the last tier while step 5
    onward walked the subjects the executor hands in, so a guarded account was
    counted as *served, notice period passed* in one half of the run and absent
    from the other. It was invisible because no fixture here had a guarded row
    in it — a test that cannot tell a working build from a broken one.
    """
    seams["rows"] = [_case(), _case("a2", "A-1002", "Demo, D.", is_sample=True)]
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["a2"]
    assert result.counts[executor.OUTCOME_SKIPPED] == 1
    # …and EVERY step counts one, not two.
    assert _checked(result, de.STEP_LETTER)["served_with_recorded_proof"] == 1
    assert _checked(result, de.STEP_NOTICE)["notice_period_passed"] == 1
    assert _checked(result, de.STEP_PROTECTIONS)["accounts_checked"] == 1
    # …and the number a guard removed is on the screen rather than inferred.
    checked = _checked(result, de.STEP_GATHER)
    assert checked["cases_at_the_last_tier"] == 2
    assert checked["of_those_a_guard_took_out"] == 1
    assert checked["checked_after_the_guards"] == 1


# ── step 2 · a returned letter is not a served notice ─────────────────────


def test_an_unrecorded_service_is_removed_naming_the_absence(seams):
    """`TC-RBS-024.2` · `BR-RBS-032` · `BR-CUS-100`.

    ⚠ **THIS IS THE CASE THAT MUST FIRST FAIL ON A LIST BUILT WHEN THE LETTERS
    WENT OUT.** The certified letter was RAISED — the case is at the last tier —
    and nobody has recorded how it went out, so it is not a served notice.
    """
    seams["rows"] = [_case(recorded=False, absence="awaiting_proof_of_service")]
    result = _run()
    assert result.records[0].outcome == de.OUTCOME_REMOVED
    assert result.records[0].data["why"] == de.WHY_NOT_SERVED
    assert "Nobody has recorded how it was served" in result.records[0].reason
    assert _checked(result, de.STEP_LETTER)["awaiting_proof_of_service"] == 1


def test_a_notice_served_by_another_channel_is_removed(seams):
    """`DSC-02.3` marks certified mail *Required at tier 3 — proof of service*."""
    seams["rows"] = [_case(channel="email")]
    result = _run()
    assert result.records[0].data["why"] == de.WHY_NOT_SERVED
    assert "not served by certified mail" in result.records[0].reason
    assert _checked(result, de.STEP_LETTER)["served_by_another_channel"] == 1


def test_delivery_is_reported_as_unreadable_and_never_as_clean(seams):
    """Hard-won law 7 — a declared blind spot with a NUMBER beside it."""
    checked = _checked(_run(), de.STEP_LETTER)
    assert checked["delivery_reported_by_any_channel"] is False
    assert "provider adapter" in checked["delivery_not_reported_because"]


# ── step 3 · the notice period ────────────────────────────────────────────


def test_the_notice_period_comes_from_settings_and_is_counted_from_service(seams):
    checked = _checked(_run(), de.STEP_NOTICE)
    assert checked["notice_period_hours"] == 48
    assert checked["notice_period_whole_days"] == 2
    assert checked["notice_period_passed"] == 1
    assert checked["counted_from"].startswith("the date a person recorded")


def test_a_letter_served_yesterday_has_not_run_its_notice_period(seams):
    seams["rows"] = [_case(served_on="2026-09-06")]
    result = _run()
    assert result.records[0].data["why"] == de.WHY_NOTICE_NOT_PASSED
    assert _checked(result, de.STEP_NOTICE)["notice_period_not_yet"] == 1


def test_an_unreadable_notice_period_clears_nobody(seams):
    """⚠ It never falls back to 48. Computing a notice period from another
    utility's policy would clear a household for disconnection two days early."""
    seams["notice_hours"] = {"readable": False, "hours": None, "detail": "no collections setting"}
    result = _run()
    assert _checked(result, de.STEP_NOTICE)["notice_period_readable"] is False
    assert result.records[0].outcome == de.OUTCOME_REMOVED
    assert result.records[0].data["why"] == de.WHY_NOTICE_NOT_PASSED


# ── step 4 · a payment overnight ──────────────────────────────────────────


def test_a_payment_since_the_letter_removes_the_account(seams):
    seams["payments"] = [
        {
            "payment_id": "p1",
            "account_id": "a1",
            "amount": "318.2000",
            "currency": "USD",
            "status": "posted",
            "posted_on": "2026-09-06",
        }
    ]
    result = _run()
    assert result.records[0].data["why"] == de.WHY_PAID
    assert "318.20" in result.records[0].reason
    assert result.records[0].fix_route == "payments"
    assert _checked(result, de.STEP_PAYMENT)["accounts_with_a_payment_since_the_letter"] == 1


def test_a_payment_before_the_letter_is_not_a_payment_overnight(seams):
    seams["payments"] = [
        {
            "payment_id": "p1",
            "account_id": "a1",
            "amount": "10.0000",
            "currency": "USD",
            "status": "posted",
            "posted_on": "2026-08-01",
        }
    ]
    result = _run()
    assert result.records[0].outcome == de.OUTCOME_ELIGIBLE


def test_the_payment_window_opens_on_the_day_the_letter_was_served(seams):
    """⚠ Since the letter, never since midnight — the customer who paid the
    evening the letter arrived is the single most likely way this list is wrong."""
    assert _checked(_run(), de.STEP_PAYMENT)["window_opened_on"] == SERVED


# ── step 5 · protections, re-checked this morning ─────────────────────────


def test_a_medical_protection_added_after_the_letter_removes_the_account(seams):
    """The card's own row: *Pace, J. · Removed · Medical protection added 3 Sep*
    over a letter dated 1 September."""
    seams["protections"] = {"a1": _protection(medical=True)}
    result = _run()
    assert result.records[0].data["why"] == de.WHY_PROTECTED_MEDICAL
    assert "2026-09-03" in result.records[0].reason
    assert _checked(result, de.STEP_PROTECTIONS)["medical_protection_in_force"] == 1


def test_a_plan_in_good_standing_removes_the_account(seams):
    seams["protections"] = {"a1": _protection(plan=True)}
    assert _run().records[0].data["why"] == de.WHY_PROTECTED_PLAN


def test_the_dispute_check_reports_what_it_could_not_look_at(seams):
    """⚠ `unavailable`, never `pass` — a green clearance derived from a table
    that does not exist would authorise a cut."""
    checked = _checked(_run(), de.STEP_PROTECTIONS)
    assert checked["disputes_that_could_not_be_checked"] == 1
    assert "disputed amount" in checked["disputes_not_checked_because"]


# ── step 6 · the weather, and OQ-RBS-1757 ─────────────────────────────────


def test_a_recorded_moratorium_removes_the_account(seams):
    seams["protections"] = {"a1": _protection(moratorium=True)}
    result = _run()
    assert result.records[0].data["why"] == de.WHY_PROTECTED_MORATORIUM
    assert _checked(result, de.STEP_WEATHER)["accounts_held_by_a_recorded_moratorium"] == 1


def test_the_area_wide_forecast_is_reported_as_not_checked_and_names_its_question(seams):
    """`OQ-RBS-1757` — nothing in this product holds a forecast.

    ⚠ SUPERSEDED 2026-10-01 BY THE RULING THAT CLOSED IT (`bb1646acd`, PO
    2026-09-07): the clerk states today's band before Run, so the area-wide half
    IS checked now — by a person — and the band they gave is on the run. The
    name is kept so the history reads; the assertions are the ruled ones.
    """
    checked = _checked(_run(), de.STEP_WEATHER)
    assert checked["area_wide_forecast_checked"] is True
    assert checked["weather_band_the_clerk_reported"] == de.WEATHER_BAND_MILD
    assert checked["area_wide_moratorium_in_force"] is False


def test_the_moratorium_tile_never_reads_the_cards_green_no(seams):
    """⚠ *We looked at the weather and it is fine* and *nobody looked* send a
    crew to opposite places."""
    tile = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "moratorium")
    # ⚠ PINS TODAY'S COPY, WHICH IS STALE: since OQ-RBS-1757 closed the clerk
    # HAS checked, and the tile should say so. `DEF-RBS-8709`; when it is fixed
    # this assertion moves on purpose.
    assert tile["value"] == {"kind": "text", "text": "Not checked"}
    assert tile["detail"] == "No forecast for the service area"


# ── step 7 · the working day ──────────────────────────────────────────────


def test_a_weekend_stops_the_whole_list(seams, monkeypatch):
    monkeypatch.setattr(de.tenancy_seam, "today", lambda: dt.date(2026, 9, 5))  # a Saturday
    seams["rows"] = [_case(served_on="2026-08-25")]
    result = _run()
    assert _checked(result, de.STEP_WORKING_DAY)["is_a_weekend"] is True
    assert result.records[0].data["why"] == de.WHY_NOT_A_WORKING_DAY


def test_a_holiday_stops_the_whole_list(seams):
    seams["holidays"] = [{"on": TODAY.isoformat(), "name": "Labor Day"}]
    result = _run()
    assert _checked(result, de.STEP_WORKING_DAY)["is_a_holiday"] is True
    assert result.records[0].data["why"] == de.WHY_NOT_A_WORKING_DAY


def test_an_empty_holiday_calendar_is_counted_rather_than_read_as_a_clearance(seams):
    assert _checked(_run(), de.STEP_WORKING_DAY)["holidays_this_tenant_has_entered"] == 0


# ── step 8 · the field list ───────────────────────────────────────────────


def test_an_account_with_nothing_against_it_is_eligible(seams):
    result = _run()
    assert result.records[0].outcome == de.OUTCOME_ELIGIBLE
    assert result.records[0].reason == "Notice period passed · no payment"


def test_a_balance_under_the_minimum_removes_the_account(seams):
    seams["ladder"]["rows"][0]["balance"] = "44.100000"
    result = _run()
    assert result.records[0].data["why"] == de.WHY_UNDER_MINIMUM
    assert "50.00" in result.records[0].reason


def test_a_balance_that_could_not_be_read_is_never_treated_as_owing(seams):
    """⚠ `—` and never `$0.00`: on this screen the difference is a crew's morning."""
    seams["ladder"]["rows"] = []
    result = _run()
    assert result.records[0].data["why"] == de.WHY_UNDER_MINIMUM
    assert "could not be read" in result.records[0].reason
    cell = _blocks(result)["records"]["rows"][0]["cells"]["balance"]
    assert cell == {"kind": "text", "text": "—"}


def test_a_closed_account_has_no_service_to_disconnect(seams):
    """`BR-CUS-082` — and it wins over every other reason."""
    seams["rows"] = [_case(cut_reachable=False)]
    assert _run().records[0].data["why"] == de.WHY_CUT_NOT_REACHABLE


def test_the_address_is_walked_to_on_premises_and_the_meter_travels(seams):
    """Hard rule 8 — an account has no address column and this does not invent one."""
    row = _run().records[0]
    assert row.data["address"] == "5 Vine St"
    assert row.data["meter"] == "WM-114"


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_removed_rows_are_drawn_with_the_eligible_ones(seams):
    """The card's design note: *the person signing wants to see who was taken
    off and why, because that is the list that would have been wrong.*"""
    seams["rows"] = [_case(), _case("a2", "A-1002", "Pace, J.")]
    seams["protections"] = {"a2": _protection(medical=True)}
    seams["ladder"]["rows"].append(
        {"account_id": "a2", "account_no": "A-1002", "balance": "540.770000", "currency": "USD", "current_tier": None}
    )
    seams["units"]["u-a2"] = {"premise_address": "7 Oak Ct", "premises_id": "p-a2"}
    seams["meters"].append({"unit_id": "u-a2", "asset_no": "WM-115", "premises_id": "p-a2"})
    blocks = _blocks(_run())
    assert blocks["records"]["total"] == 2
    assert [one["count"] for one in blocks["records"]["chips"]] == [2, 1, 1]
    assert blocks["verdict"]["word"] == "1 eligible"
    assert blocks["verdict"]["count"] == "1 removed since the letter"
    # Eligible first — the list a person signs is the top of it.
    assert blocks["records"]["rows"][0]["cells"]["today"]["label"] == "Eligible"
    assert blocks["records"]["rows"][1]["cells"]["today"]["label"] == "Removed"
    assert "Medical protection" in blocks["records"]["rows"][1]["cells"]["why"]["text"]


def test_the_verdict_counts_the_three_the_card_names(seams):
    seams["rows"] = [_case(), _case("a2", "A-1002", "Pace, J.")]
    seams["protections"] = {"a2": _protection(medical=True)}
    detail = _blocks(_run())["verdict"]["detail"]
    # ⚠ a2 is PROTECTED and its balance is unreadable, and the protection wins:
    # the order the reasons are tested in is the order a supervisor would give
    # them, so it is counted once, under the reason they would name.
    # ⚠ "weather not checked here" is stale since OQ-RBS-1757 closed —
    # `DEF-RBS-8709`; pinned so the fix is a deliberate change.
    assert detail == (
        "0 paid overnight · 1 protected · 0 under minimum · weather not checked here"
    )


def test_the_commit_is_the_danger_tier_and_approves_a_list(seams):
    """B14 rule 6, and `US-RBS-024`: it approves a LIST, never a disconnection."""
    action = _blocks(_run())["action"]
    assert action["tier"] == "danger"
    assert action["label"] == "Approve field list"
    assert action["enabled"] is False
    # B14 rule 33 — a refusal caps at five or six words.
    assert len(action["reason"].split()) <= 6


def test_no_database_id_and_no_internal_code_reaches_a_drawn_cell(seams):
    """B14 rules 31 and 32."""
    for row in _blocks(_run())["records"]["rows"]:
        drawn = " ".join(
            str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
        )
        assert "a1" != drawn
        assert "medical_protection" not in drawn
        assert "BR-" not in drawn
        assert "OQ-" not in drawn


def test_every_removal_names_a_fix_route_and_it_is_tenant_relative(seams):
    """`BR-RBS-011` — and a route that opens onto *not built yet* is
    `DEF-RBS-4329` again."""
    seams["rows"] = [_case(recorded=False)]
    for record in _run().records:
        assert record.fix_route
        assert not record.fix_route.startswith("/")
        assert record.fix_route in {"accounts", "payments", "settings/collections"}


def test_a_morning_with_nobody_at_the_last_tier_says_so(seams):
    seams["rows"] = []
    blocks = _blocks(_run())
    assert blocks["verdict"]["word"] == "0 eligible"
    assert blocks["records"]["empty"]["title"] == "Nobody is at the last tier today."


def test_eligible_plus_removed_is_always_the_whole_scope(seams):
    """`TC-RBS-024.1`'s shape — 23 on the letter, 14 eligible and 9 removed, and
    the run may never lose one in between."""
    seams["rows"] = [_case(f"a{n}", f"A-100{n}", f"Name {n}") for n in range(1, 6)]
    seams["protections"] = {"a2": _protection(medical=True), "a3": _protection(plan=True)}
    seams["payments"] = [
        {
            "payment_id": "p1",
            "account_id": "a4",
            "amount": "12.0000",
            "currency": "USD",
            "status": "posted",
            "posted_on": "2026-09-06",
        }
    ]
    seams["ladder"]["rows"] = [
        {
            "account_id": f"a{n}",
            "account_no": f"A-100{n}",
            "balance": "44.100000" if n == 5 else "900.000000",
            "currency": "USD",
            "current_tier": None,
        }
        for n in range(1, 6)
    ]
    blocks = _blocks(_run())
    eligible = blocks["records"]["chips"][1]["count"]
    removed = blocks["records"]["chips"][2]["count"]
    assert eligible + removed == 5
    assert eligible == 1 and removed == 4
    assert {one.data["why"] for one in _run().records if one.data["why"]} == {
        de.WHY_PROTECTED_MEDICAL,
        de.WHY_PROTECTED_PLAN,
        de.WHY_PAID,
        de.WHY_UNDER_MINIMUM,
    }


def test_the_balance_is_money_at_four_decimals_and_carries_its_currency(seams):
    """Hard rule 2 — stored 4, displayed 2, currency riding with the amount."""
    cell = _blocks(_run())["records"]["rows"][0]["cells"]["balance"]
    assert cell["kind"] == "money"
    assert cell["currency"] == "USD"
    assert Decimal(cell["amount"]) == Decimal("2880.000000")


def test_the_minimum_on_the_tile_carries_its_currency(seams):
    """Hard rule 2 — money never travels without one, and a browser walkthrough
    is what found `Under 50.00` on screen with no currency beside it."""
    tile = next(
        one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "under_minimum"
    )
    assert tile["label"] == "Under the minimum"
    assert tile["detail"] == "50.00 USD"
