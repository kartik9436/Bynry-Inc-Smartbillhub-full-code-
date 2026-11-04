# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-043 (EP-RBS-05) — CR-075, runbook 28.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-011 (a
#           failure names its fix route, tenant-relative) · BR-RBS-012 (a guard
#           is absolute) · BR-RBS-017 (the fingerprint never contains the run) ·
#           BR-RBS-019 · BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-024 ·
#           BR-AST-007 · BR-REP-001 (no unlabelled money number) ·
#           CLAUDE.md hard rule 2 · hard-won law 7 (a blind spot carries a
#           NUMBER) · B14 rules 31, 32, 33
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/meter_change_out.py
# ───────────────────────────────────────────────────────
"""Runbook 28, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED HERE AND THE REAL FIGURES ARE IN THE LANE REPORT.**
On the seeded utility 119 of 128 meters are sample records (`BR-TEN-056`) and
**not one meter has a test on file**, so *a meter tested but past its interval*
and *a meter exactly at its expected life* have no real rows to exercise them.
Those live here. Neither number is quoted without the other: the run against the
real database found **3 meters past their change-out age**, **128 with no test on
file**, **116 of 128 that cannot be judged on age at all** and **$19,674.08 a
month at risk across 111 of them**.

⚠ **THE CASE THAT MATTERS MOST IS `test_the_money_resolves_...`, AND IT WAS
WRITTEN BECAUSE THE FIRST DRAFT WAS WRONG IN A WAY NO OTHER CHECK COULD SEE.**
`customers.accounts_for_units` publishes the occupying account under the key
`id`; the step read `account_id`, which is not a member, so every meter got
`None`, every row read *"Not billed yet"*, and the ranking the card asks for
silently collapsed into alphabetical order. Nothing raised: the key was absent
rather than wrong, so there was no exception, no type error and no failing
assertion anywhere. It was found by RUNNING the runbook against the seeded
utility and by nothing else (hard-won law 6).
"""

import dataclasses
import datetime as dt

import pytest

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, RunbookContractError, RunbookDefinition
from apps.runbooks.definitions import meter_change_out as rb
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

#: The run's business date. Nothing in this runbook reads a clock — the age
#: arrives already computed from the tenant's own date — so this exists only
#: to keep the fixture's install dates readable.
TODAY = dt.date(2026, 9, 7)


def _meter(
    asset_id="a1",
    asset_no="WM-01128",
    *,
    age_months=60,
    life_years=20,
    last_test_date=None,
    test_interval_months=None,
    test_overdue=False,
    is_sample=False,
    behavior_class="in_service",
    service_point_id="sp1",
    unit_id="u1",
    service_code="water",
):
    return {
        "asset_id": asset_id,
        "asset_no": asset_no,
        "category": "meters",
        "type_code": "water_meter",
        "type_name": "Water meter",
        "status": "installed",
        "behavior_class": behavior_class,
        "service_point_id": service_point_id,
        "is_sample": is_sample,
        "install_date": "2021-09-07",
        "purchase_date": None,
        "age_base": "install",
        "age_months": age_months,
        "expected_life_years": life_years,
        "retire_date": None,
        "last_test_date": last_test_date,
        "test_interval_months": test_interval_months,
        "certification_due": None,
        "next_test": None,
        "test_overdue": test_overdue,
        "unit_id": unit_id,
        "service_code": service_code,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the three reads runbook 28 makes.

    The default fleet is ONE meter that is inside its life and HAS a test on
    file, so a case that forgets to give the runbook something wrong cannot
    assert on a finding it never produced.
    """
    state = {
        "meters": [_meter(last_test_date="2025-01-06", test_interval_months=96)],
        "meters_answered": True,
        "accounts": {"u1": {"id": "acc1", "account_no": "A-10432", "unit_id": "u1"}},
        "bills": [
            {
                "currency": "USD",
                "lines": [
                    {"kind": "usage", "service": "water", "quantity": "12", "amount": "148.2000"},
                    {"kind": "base", "service": "water", "quantity": None, "amount": "20.0000"},
                ],
            }
        ],
    }

    monkeypatch.setattr(
        rb.metering_seam,
        "meter_lifecycle_census",
        lambda **_: {"meters": state["meters"], "meters_answered": state["meters_answered"]},
    )
    monkeypatch.setattr(
        rb.customers_seam, "accounts_for_units", lambda unit_ids: dict(state["accounts"])
    )
    monkeypatch.setattr(
        rb.billing_seam, "issued_bills_for_account", lambda account_id, **_: list(state["bills"])
    )
    # ⚠ **NO `tenancy_seam` PATCH, AND ITS ABSENCE IS THE POINT.** An earlier
    # draft patched `rb.tenancy_seam.today` — over a module that does not
    # import it, because a meter's age is computed on the FAR side of the
    # seam. A monkeypatch of something nothing calls is a check that cannot
    # fail, and `ruff` is what found it (F401 on the unused import).
    return state


def _run(seams=None, *, guards=True):
    definition = rb.RUNBOOK if guards else dataclasses.replace(rb.RUNBOOK, guards=())
    return executor.execute(
        definition,
        tenant_id="t1",
        mode="dry",
        params={p.name: p.default for p in rb.RUNBOOK.parameters},
    )


def _block(result, name):
    return next(one["payload"] for one in result.report if one["block"] == name)


def _tile(result, tile_id):
    return next(one for one in _block(result, "kpis")["tiles"] if one["id"] == tile_id)


# ── BR-RBS-002 — the capability is ABSENT, not merely unused ──────────────


def test_it_is_a_check_and_holds_no_port_at_all():
    """`BR-RBS-002`/`TC-RBS-1`, and it is the card's own conditional kind row.

    `RB-128` says the runbook *"waits on `RB-049` for a field order, and is a
    Check without it"*. `RB-049` does not exist, so this must be a Check — and a
    Check's ports are empty because it was CONSTRUCTED without them.
    """
    assert rb.RUNBOOK.kind == models.KIND_CHECK
    assert rb.RUNBOOK.ports == ()
    assert rb.RUNBOOK.writes_nothing() is True
    assert rb.RUNBOOK.port_declarations() == ()
    assert all(step.writes is False for step in rb.RUNBOOK.steps)


def test_declaring_a_port_on_it_is_refused_at_construction():
    """First shown RED on a build that declared `apply_fee` "just for the fix
    route": the point of `BR-RBS-002` is that this is a BUILD error rather than
    a runtime refusal."""
    with pytest.raises(RunbookContractError) as caught:
        RunbookDefinition(
            key=rb.KEY,
            name=rb.RUNBOOK.name,
            kind=models.KIND_CHECK,
            category="assets",
            subject_type="meter",
            unit_of_work="a meter",
            resolve=rb.resolve,
            report=rb.report,
            steps=rb.RUNBOOK.steps,
            ports=("apply_fee",),
        )
    assert "apply_fee" in str(caught.value)


def test_it_is_the_first_runbook_in_the_assets_category():
    """`BR-RBS-025`: an empty category is never drawn as a filter chip, and the
    chip row is built from the templates PRESENT. Assets held one step and no
    runbook until this one."""
    assert rb.RUNBOOK.category == "assets"
    assert rb.RUNBOOK.subject_type == "meter"
    assert models.CATEGORY_OWNING_MODULE["assets"] == "metering"


# ── step 1 — the age rule and its blind spots ─────────────────────────────


def test_a_meter_exactly_at_its_expected_life_is_not_past_it(seams):
    """STRICTLY greater, which is the Assets replacement forecast's own rule
    (B16 §5.1b). First shown RED with `>=`: a 20-year meter on its twentieth
    birthday appeared on the change-out list a month early, and the Assets
    screen and this runbook then disagreed about the same box in the yard."""
    seams["meters"] = [
        _meter("a1", "WM-1", age_months=240, life_years=20, last_test_date="2025-01-06"),
        _meter("a2", "WM-2", age_months=241, life_years=20, last_test_date="2025-01-06"),
    ]
    result = _run()
    checked = result.set_results["past_change_out_age"]["checked"]
    assert checked["meters_past_change_out_age"] == 1
    assert [one["cells"]["meter"]["text"] for one in _block(result, "records")["rows"]] == ["WM-2"]


def test_a_meter_with_no_expected_life_is_counted_and_never_silently_skipped(seams):
    """Hard-won law 7: a declared blind spot with no NUMBER beside it is
    indistinguishable from an empty one.

    Worked on the real utility: **116 of 128 meters record no expected life**,
    so *"0 past change-out age"* alone would read as *your fleet is young*.
    """
    seams["meters"] = [
        _meter("a1", "WM-1", life_years=None, last_test_date="2025-01-06"),
        _meter("a2", "WM-2", age_months=None, life_years=20, last_test_date="2025-01-06"),
    ]
    result = _run()
    checked = result.set_results["past_change_out_age"]["checked"]
    assert checked["meters_with_no_expected_life"] == 1
    assert checked["meters_with_no_age_base"] == 1
    assert checked["meters_past_change_out_age"] == 0
    assert _tile(result, "not_judgeable")["value"]["text"] == "2 of 2"
    assert "could not be judged on age" in _block(result, "verdict")["detail"]


def test_meters_answered_false_is_not_the_same_sentence_as_no_meters(seams):
    """`DEF-075`'s exact shape — `None` read as *this module has nothing* when
    it meant *this module cannot answer*."""
    seams["meters"] = []
    seams["meters_answered"] = False
    result = _run()
    assert result.set_results["past_change_out_age"]["checked"]["meters_answered"] is False
    assert _block(result, "verdict")["count"] == "No meters checked."


# ── step 2 — two groups, and the third one the card does not name ─────────


def test_never_tested_means_no_test_on_file_and_nothing_else(seams):
    """`RB-128` names *past change-out age* and *never tested*. A meter TESTED
    but past its interval is `BR-AST-007`'s derived overdue state, is drawn on
    the Assets registry already, and is **not one of this card's groups**.

    First shown RED on a build that raised it as a third group: three meters
    produced three rows where the card commits to two of them.
    """
    seams["meters"] = [
        _meter("a1", "WM-1", last_test_date=None),
        _meter(
            "a2", "WM-2", last_test_date="2015-01-06", test_interval_months=96, test_overdue=True
        ),
        _meter("a3", "WM-3", last_test_date="2025-01-06", test_interval_months=96),
    ]
    result = _run()
    checked = result.set_results["never_tested"]["checked"]
    assert checked["meters_with_no_test_on_file"] == 1
    assert checked["tested_but_past_their_interval"] == 1
    rows = _block(result, "records")["rows"]
    assert [one["cells"]["meter"]["text"] for one in rows] == ["WM-1"]
    # ⚠ It is COUNTED rather than raised — the number is on a tile so a clerk
    # can see it, and no row is minted for a commitment the card does not make.
    assert _tile(result, "tests_overdue")["value"]["text"] == "1"


# ── step 3 — the money, which is where the first draft was wrong ──────────


def test_the_money_resolves_from_the_account_the_meter_stands_on(seams):
    """**THE REGRESSION CASE.** `accounts_for_units` publishes the account under
    `id`; the first draft read `account_id`, which is not a member — so it got
    `None` on every row, every meter read *"Not billed yet"*, and the ranking
    the card asks for silently became alphabetical.

    Nothing else could see it: the key was ABSENT rather than wrong, so there
    was no exception, no type error and no failing assertion. This case asserts
    a real dollar figure so it cannot come back.
    """
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    result = _run()
    row = _block(result, "records")["rows"][0]
    assert row["cells"]["at_risk"] == {
        "kind": "money",
        "amount": "148.2000",
        "currency": "USD",
        "basis": "posting",
    }


def test_only_the_usage_lines_for_this_meters_own_service_are_counted(seams):
    """A water meter is not at risk for the electric on the same bill."""
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None, service_code="water")]
    seams["bills"] = [
        {
            "currency": "USD",
            "lines": [
                {"kind": "usage", "service": "water", "quantity": "12", "amount": "148.2000"},
                {"kind": "usage", "service": "electric", "quantity": "900", "amount": "310.0000"},
            ],
        }
    ]
    result = _run()
    assert _block(result, "records")["rows"][0]["cells"]["at_risk"]["amount"] == "148.2000"


def test_an_unknown_figure_is_never_zero_and_sorts_below_every_known_one(seams):
    """**`None` IS NOT `0.0000`.** A meter on an account that has never billed is
    exactly the one a clerk should look at, and sorting it as zero would bury it
    under every $2 residential meter in the fleet.

    ⚠ **THE FIXTURE IS BUILT SO THAT ONLY THE BUG CAN CHANGE THE ORDER, AND THE
    FIRST VERSION OF THIS CASE COULD NOT (hard-won law 7, habit 2).** It paired a
    $148.20 meter with an unbilled one and asserted the money came first — which
    is true under the bug as well, because `-(None or 0)` still sorts after
    `-148.20`. The check passed over the exact build it was written to catch.
    **The discriminating pair is a KNOWN ZERO against an UNKNOWN**: with the
    unknown treated as zero the two tie and the alphabetical tie-break decides,
    so `WM-AAA` wins; with the unknown kept unknown the known figure wins
    whatever it is called. Proved RED on `key = (0, …)` for both.
    """
    seams["meters"] = [
        _meter("a1", "WM-AAA-UNKNOWN", last_test_date=None, unit_id="u-empty"),
        _meter("a2", "WM-ZZZ-KNOWN-ZERO", last_test_date=None, unit_id="u1"),
    ]
    seams["bills"] = [
        {
            "currency": "USD",
            "lines": [{"kind": "usage", "service": "water", "quantity": "0", "amount": "0.0000"}],
        }
    ]
    result = _run()
    rows = _block(result, "records")["rows"]
    assert [one["cells"]["meter"]["text"] for one in rows] == [
        "WM-ZZZ-KNOWN-ZERO",
        "WM-AAA-UNKNOWN",
    ]
    assert rows[0]["cells"]["at_risk"]["amount"] == "0.0000"
    assert rows[1]["cells"]["at_risk"] == {"kind": "text", "text": "Not billed yet"}


def test_a_clean_meter_costs_no_bill_read_at_all(seams, monkeypatch):
    """Ranking is over what was FOUND, so a clean fleet reads no bills. Counted
    rather than asserted by feeling — the call count is the check."""
    calls: list[str] = []
    monkeypatch.setattr(
        rb.billing_seam,
        "issued_bills_for_account",
        lambda account_id, **_: calls.append(str(account_id)) or [],
    )
    seams["meters"] = [_meter("a1", "WM-1", last_test_date="2025-01-06")]
    _run()
    assert calls == []


def test_the_money_is_read_once_per_account_however_many_meters_it_carries(seams, monkeypatch):
    """`NFR-3`/`NFR-5` bind every list this product adds; the ICP's top is
    40,000 accounts. One read per ACCOUNT, never one per meter."""
    calls: list[str] = []
    real = rb.billing_seam.issued_bills_for_account
    monkeypatch.setattr(
        rb.billing_seam,
        "issued_bills_for_account",
        lambda account_id, **kw: (calls.append(str(account_id)), real(account_id, **kw))[1],
    )
    seams["meters"] = [
        _meter("a1", "WM-1", last_test_date=None),
        _meter("a2", "WM-2", last_test_date=None),
        _meter("a3", "WM-3", last_test_date=None),
    ]
    _run()
    assert calls == ["acc1"]


# ── BR-REP-001 · hard rule 2 — the money says what kind of money it is ────


def test_every_money_value_declares_its_basis(seams):
    """`BR-REP-001`, and `DEF-RBS-4350` is what the renderer's fallback costs: a
    tile with no basis reads *Posting date* by luck. This figure is summed off
    ISSUED bills, so it is billing-side and the basis is `posting`."""
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    result = _run()
    assert _tile(result, "at_risk")["value"]["basis"] == "posting"
    assert _block(result, "records")["rows"][0]["cells"]["at_risk"]["basis"] == "posting"


def test_money_is_stored_to_four_decimals(seams):
    """Hard rule 2 — stored 4, displayed 2, and the display is the renderer's."""
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    result = _run()
    assert _tile(result, "at_risk")["value"]["amount"] == "148.2000"


# ── BR-RBS-011 · B14 — the routes and the words ──────────────────────────


def test_every_row_names_a_TENANT_RELATIVE_fix_route_and_one_of_the_two_labels(seams):
    """`BR-RBS-011`: a failure names its fix route and the shell prefixes the
    tenant. `assets`, never `/brazosbend/assets` — a route with a tenant baked
    into it is right on exactly one utility."""
    seams["meters"] = [
        _meter("a1", "WM-OLD", age_months=300, life_years=20, last_test_date="2025-01-06"),
        _meter("a2", "WM-NEW", last_test_date=None),
    ]
    result = _run()
    for row in _block(result, "records")["rows"]:
        link = row["cells"]["fix"]
        assert link["to"] == "assets"
        assert not link["to"].startswith("/")
        assert link["label"] in (rb.LABEL_ORDER_TEST, rb.LABEL_SCHEDULE_CHANGE_OUT)


def test_a_meter_that_is_both_over_age_and_untested_is_changed_out_not_tested(seams):
    """Ordering a test on a meter you are about to remove is work nobody wants
    done, and the change-out puts a tested meter in its place."""
    seams["meters"] = [_meter("a1", "WM-1", age_months=300, life_years=20, last_test_date=None)]
    result = _run()
    row = _block(result, "records")["rows"][0]
    assert row["cells"]["fix"]["label"] == rb.LABEL_SCHEDULE_CHANGE_OUT
    assert "past its change-out age, and no test on file" in row["cells"]["why"]["text"]


def test_no_database_id_is_a_visible_value(seams):
    """B14 rule 31, and `DEF-CUS-3653`/`DEF-3158` are what it costs when it is
    not: the meter's own NUMBER is what a clerk reads."""
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    result = _run()
    row = _block(result, "records")["rows"][0]
    for cell in row["cells"].values():
        assert "a1" not in str(cell.get("text", ""))
    assert row["cells"]["meter"]["text"] == "WM-1"


def test_the_refusal_on_the_action_block_caps_at_six_words(seams):
    """B14 rule 33, ratified 2026-08-30. The long reason belongs in the module
    docstring, which is what a docstring is FOR."""
    payload = _block(_run(), "action")
    assert payload["enabled"] is False
    assert len(payload["reason"].split()) <= 6


def test_an_age_reads_as_an_age_and_not_as_a_count_of_months(seams):
    """*17 months* reads as a number; *1 year 5 months* reads as an age."""
    assert rb._years(5) == "5 months"
    assert rb._years(1) == "1 month"
    assert rb._years(12) == "1 year"
    assert rb._years(17) == "1 year 5 months"
    assert rb._years(24) == "2 years"


# ── BR-RBS-012 — the guards, absolute and visible ────────────────────────


def test_the_three_guards_keep_the_seed_the_graveyard_and_the_store_room_out(seams):
    """`BR-RBS-012`, and each is a GUARD rather than a filter inside the read so
    `RBS-004.4` can draw it disabled WITH its reason: a guard a clerk cannot see
    is a guard they will assume is absent."""
    seams["meters"] = [
        _meter("s1", "WM-SAMPLE", last_test_date=None, is_sample=True),
        _meter("r1", "WM-RETIRED", last_test_date=None, behavior_class="terminal"),
        _meter("k1", "WM-STOCK", last_test_date=None, service_point_id=None, unit_id=None),
        _meter("a1", "WM-LIVE", last_test_date=None),
    ]
    result = _run()
    assert len(result.subjects) == 4
    assert len(result.guarded) == 3
    assert [one["cells"]["meter"]["text"] for one in _block(result, "records")["rows"]] == [
        "WM-LIVE"
    ]
    assert {g.key for g in rb.RUNBOOK.guards} == {"sample", "retired", "store_room"}


# ── BR-RBS-017 · BR-RBS-022 — the findings the ENGINE writes ─────────────


def test_the_finding_kind_is_stable_while_its_title_moves(seams):
    """`BR-RBS-017`: `kind` names what was ASKED, never the sentence that came
    back. The title carries the meter's age, which moves every month; a
    fingerprint built on it would mint twelve rows a year for one meter."""
    seams["meters"] = [_meter("a1", "WM-1", age_months=300, life_years=20, last_test_date=None)]
    first = _run().findings[0]
    seams["meters"] = [_meter("a1", "WM-1", age_months=301, life_years=20, last_test_date=None)]
    second = _run().findings[0]
    assert first.kind == second.kind == rb.GROUP_PAST_LIFE
    assert first.title != second.title
    assert first.subject_id == second.subject_id == "a1"
    assert first.fix_route == "assets"


def test_a_check_with_no_writer_still_leaves_work_on_somebodys_desk(seams):
    """`BR-RBS-022`: raising a work item is an ENGINE act and is refused BY NAME
    as a port, which is the only thing that lets a Check populate `RBS-007`."""
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    result = _run()
    assert rb.RUNBOOK.ports == ()
    assert len(result.findings) == 1
    assert result.findings[0].weight == rb.WEIGHT_NEVER_TESTED


# ── BR-RBS-020 · BR-RBS-021 · BR-RBS-023 — the shape of a run ────────────


def test_the_records_empty_state_is_the_SHAPE_the_renderer_reads(seams):
    """**FOUND BY LOOKING AT THE RENDERED PAGE AND BY NOTHING ELSE** (hard-won
    law 6), and it is `DEF-RBS-4352`'s class one runbook along.

    `RecordsPayload.empty` is declared `{title, helper}` in
    `07-frontend/src/features/runbooks/blocks/types.ts`, and `RecordsBlock`
    draws `payload.empty.title` in an `<h4>` and `payload.empty.helper` in a
    `<p>`. The first draft of this runbook passed a plain STRING, so both were
    `undefined` and the block rendered **a blank area** on the result screen —
    no error, no console warning, nothing red anywhere.

    ⚠ **`validate_report` CANNOT SEE IT.** `PAYLOAD_FIELDS` closes the block's
    field NAMES and says nothing about their SHAPES, so a string where the
    renderer needs an object passes every backend check and crosses the wire as
    untyped JSON that `tsc` never meets (`DEF-RBS-4406`). This case is the local
    guard until the shared one learns shapes: it asserts the two fields BY NAME
    against the type the renderer declares.
    """
    payload = _block(_run(), "records")
    assert isinstance(payload["empty"], dict), (
        "RecordsPayload.empty is {title, helper} — a string renders as a blank area "
        "with nothing red (DEF-RBS-4406)."
    )
    assert set(payload["empty"]) == {"title", "helper"}
    assert all(str(one).strip() for one in payload["empty"].values())


def test_the_report_composes_only_the_twelve_block_names(seams):
    names = [one["block"] for one in _run().report]
    assert names == ["verdict", "kpis", "records", "action", "downloads"]
    assert set(names) <= set(BLOCK_TYPES)


def test_a_set_step_runs_once_and_the_per_record_step_once_per_meter(seams):
    """`BR-RBS-023`/`TC-RBS-17`, asserted on the engine's own counter rather
    than by counting side effects."""
    seams["meters"] = [
        _meter("a1", "WM-1", last_test_date=None),
        _meter("a2", "WM-2", last_test_date=None),
    ]
    result = _run()
    assert result.step_runs["past_change_out_age"] == 1
    assert result.step_runs["never_tested"] == 1
    assert result.step_runs["revenue_at_risk"] == 2


def test_the_census_is_read_once_per_run_and_not_once_per_step(seams, monkeypatch):
    calls = {"n": 0}

    def counted(**_):
        calls["n"] += 1
        return {"meters": seams["meters"], "meters_answered": True}

    monkeypatch.setattr(rb.metering_seam, "meter_lifecycle_census", counted)
    seams["meters"] = [_meter("a1", "WM-1", last_test_date=None)]
    _run()
    assert calls["n"] == 1
