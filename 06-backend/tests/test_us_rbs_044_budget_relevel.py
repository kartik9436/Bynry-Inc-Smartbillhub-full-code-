# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-044 (EP-RBS-05) — CR-075, runbook 33.
# Rules:    BR-RBS-002 · BR-RBS-004 · BR-RBS-006 · BR-RBS-010 · BR-RBS-011 ·
#           BR-RBS-012 · BR-RBS-018 (a money-bearing action carries a SECOND
#           approval — OQ-RBS-1732 CLOSED) · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-022 (a fifteenth port is a REVIEWED INTERFACE) ·
#           BR-RBS-023 · BR-BIL-017 / OQ-068 · BR-BIL-021 · BR-REP-001 ·
#           CLAUDE.md hard rule 2 · hard-won law 2's mirror (a hold needs the
#           test that fires when it expires) · law 7 · B14 rules 31, 32, 33
# Golden:   ❄️ GT-24 — trailing-12 $2,904 ÷ 12 → level $242. Asserted through
#           `apps.billing.budget.compute_level`, which this runbook CALLS.
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/budget_relevel.py
# ───────────────────────────────────────────────────────
"""Runbook 33, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED HERE AND THE REAL FIGURES ARE IN THE LANE REPORT.**
The run against the seeded utility — twelve accounts enrolled through billing's
own `budget_service.enroll`, the drift band set to 5% — found **4 of 12 levels
that should move, $51.00 a month in total**, with `AC-2026-00013` reading
*"268.00 would become 282.00. This one has to be changed by hand."* Neither
number is quoted without the other.

⚠ **THE HOLD-EXPIRY CASE IS THE ONE THAT MATTERS MOST** (hard-won law 2's
mirror, `DEF-CWP-3925`). This runbook's central act — moving a budget level —
has no port, so step 4 records a refusal and step 3 holds the customer's notice.
Both are correct today and both rot into a lie the moment a fifteenth port is
reviewed. `test_no_port_applies_a_budget_level_and_this_case_fires_the_day_one_does`
goes RED that day and names this file, which is the only thing that stops a hold
becoming a live screen behind a dead control.
"""

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks import interfaces, models
from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import budget_relevel as rb
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)


def _account(
    account_id="acc1",
    account_no="AC-2026-00013",
    *,
    level="268.0000",
    override=None,
    last_leveled_at="2026-01-07",
    enrolled_on="2025-09-07",
    variance="-12.5000",
):
    return {
        "account_id": account_id,
        "account_no": account_no,
        "status": "enrolled",
        "level": level,
        "level_override": override,
        "level_override_reason": None,
        "effective_level": override or level,
        "variance_balance": variance,
        "currency": "USD",
        "settle_up_month": None,
        "enrolled_on": enrolled_on,
        "last_leveled_at": last_leveled_at,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the three reads runbook 33 makes.

    The default is ONE account whose level is exactly what its history supports,
    so a case that forgets to give the runbook drift cannot assert on a move it
    never produced. The settings are the tenant's OWN and are handed over as
    read — `BR-BIL-021`, and this module defaults none of them.
    """
    state = {
        "settings": {
            "eligibility_months": 12,
            "level_rounding": "whole_dollar",
            "relevel_drift_pct": Decimal("20"),
            "relevel_cadence_months": 6,
            "override_bound_pct": Decimal("30"),
            "settle_up_month": None,
            "drop_off_missed_payments": 2,
        },
        "accounts": [_account(level="242.0000")],
        # ❄️ GT-24's own chain: twelve months summing to $2,904.
        "actuals": {
            "acc1": {
                "actuals": ["242.00"] * 12,
                "months_of_history": 12,
                "currency": "USD",
                "mixed_currency": False,
                "bills_read": 12,
            }
        },
        "sample": frozenset(),
    }

    monkeypatch.setattr(
        rb.billing_seam,
        "budget_programme",
        lambda: {"settings": dict(state["settings"]), "accounts": list(state["accounts"])},
    )
    monkeypatch.setattr(
        rb.billing_seam,
        "budget_trailing_actuals",
        lambda account_id, **_: dict(
            state["actuals"].get(
                str(account_id),
                {"actuals": [], "months_of_history": 0, "currency": None},
            )
        ),
    )
    monkeypatch.setattr(rb.customers_seam, "sample_account_ids", lambda: state["sample"])
    monkeypatch.setattr(rb.tenancy_seam, "today", lambda: TODAY)
    return state


def _run(*, guards=True):
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


def _records(result, step):
    return [one for one in result.records if one.step_key == step]


# ── the hold, and the test that fires when it expires ────────────────────


def test_no_port_applies_a_budget_level_and_this_case_fires_the_day_one_does():
    """**THE HOLD-EXPIRY CASE** — hard-won law 2's mirror (`DEF-CWP-3925`).

    Runbook 33's central act is moving `account_budget_status.level` and **not
    one of the ports moves it**: `billing`'s single port is `apply_fee`, which
    raises a draft fee bill. A fifteenth port is a REVIEWED INTERFACE
    (`BR-RBS-022`), so this lane did not add one — step 4 records the refusal
    and step 3 holds the notice.

    ⚠ **BOTH OF THOSE ARE PROMISES WITH A CLOCK IN THEM.** The day a port lands
    they become false, and landing a port and releasing the thing that held for
    it are two acts of which only the first feels like the work. This case is
    the second act, written in the same commit as the hold: it goes RED naming
    `budget_relevel.py` the moment any port claims to re-level a budget, and it
    asserts by NAME rather than by count so a rename cannot slip past it.
    """
    assert rb.PORT_THAT_WOULD_APPLY_A_LEVEL not in interfaces.PORTS, (
        f"{rb.PORT_THAT_WOULD_APPLY_A_LEVEL!r} now exists as a port. The hold in "
        "apps/runbooks/definitions/budget_relevel.py steps 3 and 4 is no longer true: "
        "declare the port on the runbook, write the act, and delete this assertion "
        "(OQ-RBS-1760)."
    )
    applying = sorted(
        name
        for name in interfaces.PORTS
        if "level" in name or ("budget" in name and "relevel" not in name)
    )
    assert applying == [], (
        f"port(s) {applying} look like they move a budget level. If one does, "
        "budget_relevel.py's refusal is a lie — see OQ-RBS-1760."
    )
    assert set(rb.RUNBOOK.ports) == {"queue_notice"}


def test_the_customer_is_not_told_about_a_change_that_cannot_be_made(seams):
    """The card's order is told-first-then-changed, which is right when a change
    can FAIL. It is wrong when the change is known impossible before the run
    starts: the customer would be told their payment is changing when nothing in
    this product can change it.

    First shown RED on the obvious build — queue the notice, then discover the
    level cannot move — which planned a letter for every drifting account.
    """
    seams["accounts"] = [_account(level="200.0000")]
    result = _run()
    told = _records(result, rb.STEP_TELL)
    assert [one.outcome for one in told] == [rb.OUTCOME_HELD]
    assert "cannot move a budget level yet" in told[0].reason
    assert told[0].data["port_that_is_missing"] == rb.PORT_THAT_WOULD_APPLY_A_LEVEL


def test_step_four_records_the_refusal_by_name_and_moves_nothing(seams):
    """The briefing's own instruction: *record the port's own refusal in the
    report rather than inventing a write*. `RB-125` ships the same posture for
    voiding a plan and `RB-122` for suppressing a channel."""
    seams["accounts"] = [_account(level="200.0000")]
    result = _run()
    applied = _records(result, rb.STEP_APPLY)
    assert [one.outcome for one in applied] == [rb.OUTCOME_NOT_APPLIED]
    assert "changed by hand" in applied[0].reason
    assert applied[0].fix_route == rb.FIX_BUDGET
    payload = _block(result, "action")
    assert payload["enabled"] is False
    assert payload["tier"] == "danger"  # B14 rule 6 — a destructive commit
    assert len(payload["reason"].split()) <= 6  # B14 rule 33


def test_the_second_approval_is_read_and_reported_even_though_nothing_applies(seams):
    """`BR-RBS-018` as `OQ-RBS-1732` closed it — *"every money action, no
    threshold"*. A level is what a customer pays every month for a year.

    ⚠ **THE MISSING DOOR IS SAID FIRST AND THE APPROVAL SECOND, AND THE ORDER
    WAS WRONG IN THE FIRST DRAFT.** Both sentences are true on every row today,
    and a row reading *"waiting for a second person"* tells a clerk that
    approving is what unblocks it. It is not.
    """
    seams["accounts"] = [_account(level="200.0000")]
    applied = _records(_run(), rb.STEP_APPLY)[0]
    assert "changed by hand" in applied.reason
    assert applied.data["second_approval"] is False
    assert "second person" in applied.data["second_approval_reason"]


# ── BR-BIL-017 — the arithmetic is billing's and is not re-implemented ───


def test_the_level_is_computed_by_billings_own_frozen_arithmetic(seams):
    """❄️ `GT-24` (B5 FROZEN 2026-08-08): trailing-12 **$2,904** over twelve
    months rounds half-up to a level of **$242**.

    This runbook CALLS `apps.billing.budget.compute_level`; a second
    implementation of a finance-signed figure is exactly what the freeze exists
    to prevent. The case pins the figure so a "simplification" here goes RED
    against the golden number rather than against a fixture.
    """
    from apps.billing import budget as budget_math

    assert budget_math.compute_level(
        trailing_actuals=[Decimal("242.00")] * 12, months=12, rounding="whole_dollar"
    ) == Decimal("242")
    seams["accounts"] = [_account(level="242.0000")]
    result = _run()
    supported = result.set_results[rb.STEP_SUPPORTED]["items"]["acc1"]
    assert supported["supported_level"] == "242.0000"
    assert supported["outcome"] == rb.OUTCOME_INSIDE_BAND


def test_a_level_moves_only_past_the_drift_band_and_only_at_cadence(seams):
    """`BR-BIL-017`: BOTH gates, and they are two different answers with two
    different next steps — so they are two outcomes and never one *no change*.

    Worked: a level of 200 against a supported 242 is 21% away, past the
    tenant's 20% band — but an account levelled last month is inside a
    six-month cadence and does not move.
    """
    seams["accounts"] = [
        _account("acc1", "A-1", level="200.0000", last_leveled_at="2026-01-07"),
        _account("acc2", "A-2", level="200.0000", last_leveled_at="2026-08-07"),
    ]
    seams["actuals"]["acc2"] = dict(seams["actuals"]["acc1"])
    items = _run().set_results[rb.STEP_SUPPORTED]["items"]
    assert items["acc1"]["outcome"] == rb.OUTCOME_MOVES
    assert items["acc2"]["outcome"] == rb.OUTCOME_NOT_AT_CADENCE
    assert items["acc1"]["drift_pct"] == "21.00"
    checked = _run().set_results[rb.STEP_SUPPORTED]["checked"]
    assert checked["levels_that_move"] == 1
    assert checked["not_at_cadence"] == 1


def test_an_account_with_too_little_history_gets_no_level_at_all(seams):
    """`BR-BIL-017`'s eligibility window is the divisor. Averaging nine months
    under a twelve-month window would set what a customer pays for a year off a
    number the tenant's own rule calls insufficient — so it is REPORTED with its
    fraction, which is `budget.eligibility`'s own sentence."""
    seams["actuals"]["acc1"] = {
        "actuals": ["242.00"] * 9,
        "months_of_history": 9,
        "currency": "USD",
    }
    item = _run().set_results[rb.STEP_SUPPORTED]["items"]["acc1"]
    assert item["outcome"] == rb.OUTCOME_TOO_LITTLE_HISTORY
    assert item["supported_level"] is None
    assert "9/12 months" in item["reason"]


def test_a_zero_level_is_reported_rather_than_used_as_a_denominator(seams):
    """`budget.drift_fraction` refuses a zero denominator BY NAME: *"an account
    with no level is not drifting — it is unenrolled or misconfigured"*. First
    shown RED on a build that let the ZeroDivisionError out of the step and
    failed the whole record."""
    seams["accounts"] = [_account(level="0.0000")]
    item = _run().set_results[rb.STEP_SUPPORTED]["items"]["acc1"]
    assert item["outcome"] == rb.OUTCOME_TOO_LITTLE_HISTORY
    assert "no level to measure a change against" in item["reason"]


def test_a_null_last_levelled_date_falls_back_to_the_enrolment_date(seams):
    """**A NULL `last_leveled_at` IS NOT AGE ZERO.** An account enrolled a year
    ago and never re-levelled is DUE; treating the null as *levelled today*
    would hold every such account outside its cadence for ever."""
    seams["accounts"] = [_account(level="200.0000", last_leveled_at=None, enrolled_on="2025-01-07")]
    item = _run().set_results[rb.STEP_SUPPORTED]["items"]["acc1"]
    assert item["months_since_measured_from"] == "enrolled_on"
    assert item["outcome"] == rb.OUTCOME_MOVES


# ── the override, walked rather than guarded ─────────────────────────────


def test_an_account_carrying_an_override_is_walked_and_its_row_says_what_moves(seams):
    """A re-level moves `level`; what the customer PAYS is `effective_level`,
    which prefers the override. Guarding these out would have been the tidier
    build and the wrong one: the ±30% override bound is measured against the
    COMPUTED level, so leaving it stale would make the next override validated
    against a year-old number."""
    seams["accounts"] = [_account(level="200.0000", override="210.0000")]
    result = _run()
    assert len(result.guarded) == 0
    assert result.set_results[rb.STEP_PROGRAMME]["checked"]["carrying_an_override"] == 1
    item = result.set_results[rb.STEP_SUPPORTED]["items"]["acc1"]
    assert item["outcome"] == rb.OUTCOME_MOVES
    assert item["effective_level"] == "210.0000"
    assert "carr" in _block(result, "verdict")["detail"]


def test_the_sample_guard_keeps_the_seeded_accounts_out(seams):
    """`BR-RBS-012`, and it is a GUARD rather than a filter inside the read so
    `RBS-004.4` can draw it disabled WITH its reason."""
    seams["accounts"] = [
        _account("acc1", "A-1", level="200.0000"),
        _account("acc2", "A-2", level="200.0000"),
    ]
    seams["actuals"]["acc2"] = dict(seams["actuals"]["acc1"])
    seams["sample"] = frozenset({"acc2"})
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["acc2"]
    assert result.set_results[rb.STEP_PROGRAMME]["checked"]["guarded_as_sample_records"] == 1


# ── BR-REP-001 · hard rule 2 — the money and how it reads ────────────────


def test_every_money_value_declares_the_PRICED_basis(seams):
    """`BR-REP-001`, and `DEF-RBS-4350` one runbook along. A budget level is
    **computed and never posted** — `BR-BIL-011` is explicit that the monthly
    posting is the ACTUALS posting and the level never reaches the ledger as a
    price — so a tile taking the renderer's `posting` fallback would sit under a
    heading it does not belong to."""
    seams["accounts"] = [_account(level="200.0000")]
    result = _run()
    assert _tile(result, "movement")["value"]["basis"] == "priced"
    for cell in ("now", "supported", "change"):
        assert _block(result, "records")["rows"][0]["cells"][cell]["basis"] == "priced"


def test_money_inside_a_sentence_is_shown_to_two_decimals(seams):
    """Hard rule 2 — stored 4, DISPLAYED 2. A money CELL goes through the
    renderer; a money figure inside a sentence is a string this module builds,
    so the rounding is this module's.

    First shown RED on the first draft, which read *"268.0000 would become
    282.0000"* — the stored form on a screen.
    """
    seams["accounts"] = [_account(level="200.0000")]
    result = _run()
    reason = _records(result, rb.STEP_APPLY)[0].reason
    assert "200.00 would become 242.00" in reason
    assert "0000" not in reason
    assert "200.00 should become 242.00" in result.findings[0].title


def test_the_change_a_month_tile_adds_up_to_the_rows_beneath_it(seams):
    """A KPI that does not equal its own table is the shape `DEF-RBS-4352`
    describes one layer up: both halves right, nothing to check against."""
    seams["accounts"] = [
        _account("acc1", "A-1", level="200.0000"),
        _account("acc2", "A-2", level="180.0000"),
    ]
    seams["actuals"]["acc2"] = dict(seams["actuals"]["acc1"])
    result = _run()
    rows = _block(result, "records")["rows"]
    total = sum(Decimal(one["cells"]["change"]["amount"]) for one in rows)
    assert _tile(result, "movement")["value"]["amount"] == str(total.quantize(Decimal("0.0001")))
    assert total == Decimal("104.0000")  # (242−200) + (242−180)


def test_no_database_id_is_a_visible_value_and_a_missing_number_states_itself(seams):
    """B14 rule 31, and `DEF-3158` is exactly this screen's own history: `S30`'s
    Budget Bills tab printed a truncated account id in its first column, with no
    fallback, on every row."""
    seams["accounts"] = [_account(account_no=None, level="200.0000")]
    result = _run()
    cell = _block(result, "records")["rows"][0]["cells"]["account"]
    assert cell["text"] == "No account number on file"
    assert "acc1" not in cell["text"]


# ── the run's own shape ──────────────────────────────────────────────────


def test_the_verdict_never_says_done_over_a_run_that_changed_nothing(seams):
    """Hard-won law 1: a comment — or a word on a screen — claiming a guarantee
    is not the guarantee. Nothing moved, so nothing says it did."""
    seams["accounts"] = [_account(level="200.0000")]
    verdict = _block(_run(), "verdict")
    assert verdict["word"] == "To do"
    assert "Nothing was changed and nobody was told." in verdict["detail"]


def test_an_empty_programme_is_an_answer_and_not_a_clean_verdict(seams):
    """A utility that has not switched budget billing on has nobody enrolled.
    ⚠ This is also what a tenant sees while `OQ-RBS-1759` is open: the Templates
    library cannot draw this card *Unavailable*, so the honest empty answer is
    what stands in for it."""
    seams["accounts"] = []
    result = _run()
    verdict = _block(result, "verdict")
    assert verdict["word"] == "Nobody yet"
    assert "Nobody is on budget billing yet." in verdict["detail"]
    assert _block(result, "records")["total"] == 0


def test_the_discriminator_carries_the_level_and_the_month_but_never_the_run():
    """`engine/acts.py` says the composition is each runbook's own question.

    Worked: an account moving to $268 is told ONCE however many times the run is
    repeated this month; the same account moving to $291 six months later has a
    different key and is told again. Drop the level and a customer re-levelled in
    March is never told in September; put the RUN in it and a retry tells
    everybody twice in one morning.
    """
    march = rb._discriminator({"supported_level": "268.0000"}, dt.date(2026, 3, 30))
    march_again = rb._discriminator({"supported_level": "268.0000"}, dt.date(2026, 3, 2))
    september = rb._discriminator({"supported_level": "291.0000"}, dt.date(2026, 9, 30))
    assert march == march_again
    assert march != september
    assert "268.0000" in march and "2026-03" in march


def test_the_settings_are_the_tenants_own_and_are_reported_as_read(seams):
    """`RBR-03`: policy lives in Settings and is never duplicated on a card, and
    `BR-BIL-021` makes every budget parameter config. All three knobs are
    declared `ref:setting`, so the setup screen draws them dashed and read-only.
    """
    kinds = {p.name: (p.type, p.setting_key) for p in rb.RUNBOOK.parameters}
    assert kinds["averaging_window"] == ("ref:setting", "billing.eligibility_months")
    assert kinds["drift"] == ("ref:setting", "billing.relevel_drift_pct")
    assert kinds["cadence"] == ("ref:setting", "billing.relevel_cadence_months")
    checked = _run().set_results[rb.STEP_PROGRAMME]["checked"]
    assert checked["averaging_window_months"] == 12
    assert checked["drift_band_pct"] == "20"
    assert checked["cadence_months"] == 6


def test_the_cap_defaults_to_the_product_owners_own_hundred(seams):
    """`OQ-RBS-1731` CLOSED 2026-09-06, verbatim *"1731 … (b) ship 100"*.
    `BR-RBS-006`: the cap REFUSES the run and never truncates it."""
    cap = next(p for p in rb.RUNBOOK.parameters if p.name == "most_per_run")
    assert cap.default == 100
    seams["accounts"] = [_account(f"acc{i}", f"A-{i}", level="200.0000") for i in range(3)]
    for i in range(3):
        seams["actuals"][f"acc{i}"] = dict(seams["actuals"]["acc1"])
    with pytest.raises(executor.CapExceeded):
        executor.execute(
            rb.RUNBOOK,
            tenant_id="t1",
            mode="dry",
            params={p.name: p.default for p in rb.RUNBOOK.parameters},
            cap=2,
        )


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


def test_a_set_step_runs_once_and_the_per_record_steps_once_per_account(seams):
    """`BR-RBS-023`/`TC-RBS-17`, on the engine's own counter."""
    seams["accounts"] = [
        _account("acc1", "A-1", level="200.0000"),
        _account("acc2", "A-2", level="200.0000"),
    ]
    seams["actuals"]["acc2"] = dict(seams["actuals"]["acc1"])
    runs = _run().step_runs
    assert runs[rb.STEP_PROGRAMME] == 1
    assert runs[rb.STEP_SUPPORTED] == 1
    assert runs[rb.STEP_TELL] == 2
    assert runs[rb.STEP_APPLY] == 2


def test_the_programme_is_read_once_per_run(seams, monkeypatch):
    calls = {"n": 0}

    def counted():
        calls["n"] += 1
        return {"settings": dict(seams["settings"]), "accounts": list(seams["accounts"])}

    monkeypatch.setattr(rb.billing_seam, "budget_programme", counted)
    _run()
    assert calls["n"] == 1


def test_it_is_an_action_and_the_step_that_cannot_write_says_so(seams):
    """`writes=False` on step 4 is the truth about this build: there is no port
    that moves a budget level, so it has nothing to write with. Declaring `True`
    would be a claim the code does not make (hard-won law 1)."""
    assert rb.RUNBOOK.kind == models.KIND_ACTION
    assert rb.RUNBOOK.writes_nothing() is False
    by_key = {s.key: s.writes for s in rb.RUNBOOK.steps}
    assert by_key[rb.STEP_TELL] is True
    assert by_key[rb.STEP_APPLY] is False
