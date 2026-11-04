# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-026 (EP-RBS-05) — CR-075 wave P, runbook 14.
# Rules:    BR-RBS-002 · BR-RBS-004 · BR-RBS-005 · BR-RBS-018 · BR-RBS-011 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-022 · BR-RBS-023 · BR-RBS-027 ·
#           BR-PAY-019 · CLAUDE.md hard rule 2 · B14 rules 31 and 32
# Tests:    this file. The PostgreSQL half is
#           tests/test_rbs_money_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/bank_reconciliation.py
# ───────────────────────────────────────────────────────
"""Runbook 14, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED HERE AND THE REAL ONES RUN IN THE POSTGRESQL FILE.**
What this proves is the tie-out's REASONING — nearest batch, difference, likely
cause, the fee split, the second approval. What it cannot prove is that
`bankrec_read.statement_review` returns the shape this runbook reads; a seam that
changed under it passes every case below. Both halves are quoted in the lane
report and neither is quoted alone.
"""


import pytest

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, RunbookContractError, validate_report
from apps.runbooks.definitions import bank_reconciliation as br
from apps.runbooks.engine import executor

#: ⚠ **THE WHOLE FILE NEEDS A DATABASE, AND NOT BECAUSE THESE CASES READ ONE.**
#: The executor opens a nested `transaction.atomic()` around every per-record
#: step — the SAVEPOINT that hard-won law 14 makes non-negotiable — and
#: `transaction.atomic()` asks for a connection before it does anything else.
#: So a case that reaches the write step needs `django_db` even though the seams
#: are replaced and nothing is written. Marked at module level rather than case by
#: case, because the day somebody removes it the failure is a `RuntimeError` about
#: database access and reads nothing like *the savepoint went away*.
pytestmark = pytest.mark.django_db

STATEMENT_ID = "stmt-1"


def _line(no, *, amount, state, batch_code=None, batch_id=None, recorded=None, difference=None,
          posted_on="2026-09-04", reason_code=None):
    return {
        "bank_line_id": f"line-{no}",
        "posted_on": posted_on,
        "reference": f"DEP 09{no:02d}",
        "amount": amount,
        "currency": "USD",
        "line_no": no,
        "batch_id": batch_id,
        "batch_code": batch_code,
        "recorded_total": recorded,
        "difference": difference,
        "state": state,
        "reason_code": reason_code,
    }


def _batch(code, *, total, deposited_on="2026-09-03", batch_id=None):
    return {
        "id": batch_id or f"batch-{code}",
        "code": code,
        "recorded_total": total,
        "deposited_on": deposited_on,
        "status": "in_transit",
        "currency": "USD",
    }


def _statement(lines, batches=()):
    return {
        "statement": {
            "id": STATEMENT_ID,
            "bank_account_name": "Operating",
            "period_start": "2026-09-01",
            "period_end": "2026-09-04",
        },
        "rows": list(lines),
        "open_batches": list(batches),
        "currency": "USD",
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the three reads runbook 14 makes.

    Defaults to *nothing connected, nothing imported* — the STOP — so a case
    that forgets to give the runbook a statement cannot land on a happy path.
    """
    state = {"connections": [], "statement": None}
    monkeypatch.setattr(
        br.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )
    monkeypatch.setattr(br.payments_seam, "statement_review", lambda one: state["statement"])
    monkeypatch.setattr(
        br.payments_seam,
        "statement_imports",
        lambda limit=50: ([{"id": STATEMENT_ID}] if state["statement"] else []),
    )
    return state


def _run(params=None, *, run_id=None):
    ctx = executor.build_context(
        br.RUNBOOK, tenant_id="t", run_id=run_id, params=params or {"statement": STATEMENT_ID}
    )
    return executor.execute(br.RUNBOOK, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_an_action_holding_exactly_record_match():
    """`RB-114`: *Ports it holds — `record_match` (payments)*.

    ⚠ **THE KIND IS A JUDGMENT AND THIS TEST IS WHERE IT IS PINNED.** The lane's
    briefing called runbook 14 a Check; its own card, the contract's coverage
    table, `boundary.py` and the execution plan all say Action. If that is ever
    reversed, THIS case goes red and names the decision rather than letting a
    port quietly become unreachable.
    """
    assert br.RUNBOOK.kind == models.KIND_ACTION
    assert br.RUNBOOK.ports == ("record_match",)
    assert sorted(executor.build_context(br.RUNBOOK).ports) == ["record_match"]


def _as_a_check(**overrides):
    fields = dict(
        key="bank_reconciliation_as_a_check",
        name="Bank reconciliation",
        kind=models.KIND_CHECK,
        category="finance",
        subject_type="bank_line",
        unit_of_work="a bank statement line",
        resolve=br.resolve,
        report=br.report,
        steps=br.RUNBOOK.steps,
        ports=br.RUNBOOK.ports,
    )
    fields.update(overrides)
    return br.RunbookDefinition(**fields)


def test_the_same_runbook_declared_a_check_is_refused_for_its_writing_step():
    """`BR-RBS-002` · `TC-RBS-1`, first clause — the claim and the capability
    must agree, and the STEP's claim is checked before the ports are reached."""
    with pytest.raises(RunbookContractError) as refusal:
        _as_a_check()
    assert br.STEP_RECORD in str(refusal.value)
    assert "writes=True" in str(refusal.value)


def test_the_same_runbook_declared_a_check_is_refused_for_its_port():
    """`BR-RBS-002` · `TC-RBS-1`, second clause — **the capability is ABSENT.**

    ⚠ **THE STEPS ARE STRIPPED OF THEIR WRITE CLAIM SO THIS CASE REACHES THE
    RULE IT IS NAMED AFTER.** Left alone, the constructor refuses one step
    earlier and this assertion would pass over a port list nobody checked.
    """
    quiet = tuple(
        br.Step(key=s.key, label=s.label, mode=s.mode, run=s.run) for s in br.RUNBOOK.steps
    )
    with pytest.raises(RunbookContractError) as refusal:
        _as_a_check(steps=quiet)
    assert "record_match" in str(refusal.value)


def test_raising_work_items_is_not_a_port_and_step_six_does_not_write():
    """`BR-RBS-022` — raising a work item is an ENGINE act.

    The card marks step 6 `writes`; giving it a writer would need
    `raise_work_item` as a fourteenth port, which the contract refuses BY NAME
    because that is the only thing that lets a runbook fill the work list while
    holding no writer for it.
    """
    assert "raise_work_item" not in br.RUNBOOK.ports
    last = br.RUNBOOK.steps[-1]
    assert last.key == br.STEP_REST
    assert last.writes is False
    assert [step.writes for step in br.RUNBOOK.steps].count(True) == 1


def test_the_auto_match_tolerance_is_read_from_settings_and_never_typed_here():
    """`RBR-03` · `BR-PAY-019` — a tenant who raises it LOCKS batches, so the
    decision is theirs, made once, on their own screen, with an audit row."""
    tolerance = [p for p in br.RUNBOOK.parameters if p.name == "auto_match_tolerance"][0]
    assert tolerance.type == "ref:setting"
    assert tolerance.setting_key == "payments.match_amount_tolerance"
    assert tolerance.default is None


# ── the stop ──────────────────────────────────────────────────────────────


def test_no_connection_and_no_statement_stops_the_run(seams):
    """PO ruling 2026-09-06 — the absence is the result."""
    result = _run()
    stop = result.set_results[br.STEP_SOURCE]["stop"]
    assert stop["headline"] == "Nothing to reconcile."
    assert "No accounting connection is set up." in stop["detail"]
    assert "No bank statement has been imported" in stop["detail"]
    assert result.subjects == ()


def test_a_stopped_run_draws_six_chain_cells_one_red_and_five_never_reached(seams):
    blocks = _blocks(_run())
    chain = blocks["chain"]
    assert len(chain["cells"]) == 6
    assert chain["cells"][0]["state"] == "bad"
    assert [cell["state"] for cell in chain["cells"][1:]] == ["notReached"] * 5
    assert "kpis" not in blocks


def test_every_later_step_reads_never_reached(seams):
    """`BR-RBS-027`."""
    result = _run()
    for key in (br.STEP_BATCHES, br.STEP_MATCH, br.STEP_FEES, br.STEP_REST):
        assert result.set_results[key]["reached"] is False, key


# ── the tie-out ───────────────────────────────────────────────────────────


def test_an_already_tied_line_is_matched_and_not_re_recorded(seams):
    """`payments` auto-matched it on import; recording it again would be a
    second link over a batch that already has one."""
    seams["statement"] = _statement(
        [_line(17, amount="1204.0500", state=br.STATE_AUTO, batch_code="DEP-0917",
               batch_id="b1", recorded="1204.0500", difference="0.000000")]
    )
    record = _run().records[0]
    assert record.outcome == br.OUTCOME_ALREADY_MATCHED


def test_an_unlinked_line_gets_its_nearest_batch_and_the_difference(seams):
    """The two columns that turn an hour of squinting into a decision.

    A $35.95 gap against a lockbox batch three days earlier is almost always a
    late item, and the row says so — offered to a person, never acted on.
    """
    seams["statement"] = _statement(
        [_line(17, amount="1240.0000", state=br.STATE_NEEDS_A_LOOK)],
        [_batch("Lockbox 3 Sep", total="1204.0500")],
    )
    row = _blocks(_run())["records"]["rows"][0]["cells"]
    assert row["batch"]["text"] == "Lockbox 3 Sep"
    assert row["batch_amount"]["amount"] == "1204.0500"
    assert row["difference"]["amount"] == "35.9500"
    assert row["cause"]["text"] == "The bank added a late item."


def test_a_line_with_no_candidate_says_so_and_offers_record_deposit(seams):
    """*No batch — a direct deposit?* — a hedge, because it is a guess."""
    seams["statement"] = _statement([_line(18, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM)])
    row = _blocks(_run())["records"]["rows"][0]["cells"]
    assert row["batch"]["text"] == "—"
    assert row["batch_amount"]["text"] == "—"
    assert row["difference"]["amount"] == "610.0000"
    assert row["cause"]["text"] == "No batch — a direct deposit?"
    assert row["fix"]["label"] == "Record deposit →"


def test_a_line_smaller_than_its_nearest_batch_asks_whether_it_was_split(seams):
    seams["statement"] = _statement(
        [_line(2, amount="60.0000", state=br.STATE_NEEDS_A_LOOK)],
        [_batch("Kiosk 3 Sep", total="120.0000")],
    )
    row = _blocks(_run())["records"]["rows"][0]["cells"]
    assert row["difference"]["amount"] == "-60.0000"
    assert row["cause"]["text"] == "Part of a batch — was it split?"


def test_a_batch_two_lines_could_claim_is_left_for_a_person(seams):
    """`auto_match`'s own rule, applied to this runbook's wider window rather
    than reinvented with a different answer."""
    seams["statement"] = _statement(
        [
            _line(1, amount="500.0000", state=br.STATE_NEEDS_A_LOOK),
            _line(2, amount="500.0000", state=br.STATE_NEEDS_A_LOOK),
        ],
        [_batch("Lockbox 3 Sep", total="500.0000")],
    )
    outcomes = [record.outcome for record in _run().records]
    assert outcomes == [br.OUTCOME_NEEDS_A_PERSON, br.OUTCOME_NEEDS_A_PERSON]
    causes = {row["cells"]["cause"]["text"] for row in _blocks(_run())["records"]["rows"]}
    assert causes == {"Two batches could be this line."}


def test_a_batch_outside_the_date_window_is_not_offered(seams):
    """The window is a parameter and it BOUNDS the search; a batch a fortnight
    away is not *nearest*, it is a coincidence."""
    seams["statement"] = _statement(
        [_line(1, amount="500.0000", state=br.STATE_NEEDS_A_LOOK, posted_on="2026-09-20")],
        [_batch("Lockbox 3 Sep", total="500.0000", deposited_on="2026-09-03")],
    )
    row = _blocks(_run())["records"]["rows"][0]["cells"]
    assert row["batch"]["text"] == "—"


# ── the fee ───────────────────────────────────────────────────────────────


def test_a_negative_line_is_a_fee_and_leaves_the_unmatched_table(seams):
    """`RB-114`: *a bank charge is not an unmatched deposit — it is the bank
    being paid*. The rule under that sentence is this lane's and is recorded in
    the module docstring."""
    seams["statement"] = _statement(
        [
            _line(1, amount="-12.0000", state=br.STATE_NOT_IN_OUR_SYSTEM),
            _line(2, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM),
        ]
    )
    result = _run()
    blocks = _blocks(result)
    assert [row["cells"]["line"]["text"] for row in blocks["records"]["rows"]] == [
        "2026-09-04 · DEP 0902"
    ]
    tiles = {t["id"]: t for t in blocks["kpis"]["tiles"]}
    assert tiles["fees"]["value"]["text"] == "1"
    assert tiles["fees"]["detail"] == "-12.0000 USD"


def test_a_line_explained_under_a_fee_reason_is_a_fee_whatever_its_sign(seams):
    seams["statement"] = _statement(
        [_line(1, amount="12.0000", state=br.STATE_EXPLAINED, reason_code="bank_fee")]
    )
    result = _run()
    assert [record.outcome for record in result.records] == [br.OUTCOME_FEE]
    assert _blocks(result)["records"]["rows"] == []


# ── the second approval ───────────────────────────────────────────────────


def test_an_exact_tie_is_planned_and_waits_for_a_second_person(seams):
    """`BR-RBS-018` — every money-bearing action, no threshold.

    `record_match` moves money's PROVENANCE, which is why it is on the
    money-bearing list; a tie recorded against the wrong batch is a
    reconciliation that proves nothing.
    """
    seams["statement"] = _statement(
        [_line(1, amount="500.0000", state=br.STATE_NEEDS_A_LOOK)],
        [_batch("Lockbox 3 Sep", total="500.0000")],
    )
    record = _run().records[0]
    assert record.outcome == br.OUTCOME_PLANNED
    assert record.reason == "Waiting for a second person to approve this run."


def test_a_matching_approval_reaches_the_port_and_the_port_refuses(seams):
    """The dry promise, proved rather than asserted: the port IS called and
    `PortNotBound` is what stops the write. No `if is_bound` branch exists."""
    seams["statement"] = _statement(
        [_line(1, amount="500.0000", state=br.STATE_NEEDS_A_LOOK)],
        [_batch("Lockbox 3 Sep", total="500.0000")],
    )
    # ⚠ `apps.identity.models.User`, NOT pytest-django's `django_user_model`:
    # the FK on `runbook_runs.approved_by` decides the model, not AUTH_USER_MODEL.
    from apps.identity.models import User
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.create(name="Brazos Bend", subdomain="brazos-rbs-p14")
    approver = User.objects.create(
        tenant=tenant, email="tom14@example.test", full_name="Tom Nguyen"
    )
    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key=br.KEY,
        name="Bank reconciliation",
        kind=models.KIND_ACTION,
        category="finance",
        subject_type="bank_line",
        unit_of_work="a bank statement line",
        cap=100,
    )
    run = models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        status=models.RUN_STATUS_APPROVED,
        approved_by=approver,
        approved_count=1,
    )
    record = _run(run_id=run.pk).records[0]
    assert record.outcome == br.OUTCOME_PLANNED
    assert record.reason == "Ready to record. Nothing is written yet."
    assert "no writer bound" in record.decided_by_rule


# ── the report ────────────────────────────────────────────────────────────


def test_the_report_names_only_blocks_from_the_twelve(seams):
    seams["statement"] = _statement([_line(1, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM)])
    result = _run()
    for block in result.report:
        assert block["block"] in BLOCK_TYPES
    validate_report(result.report, runbook_key=br.KEY)


def test_the_records_table_draws_the_frames_seven_columns_in_order(seams):
    """`RBS-006-R14` region 3 — *columns in THIS order*."""
    seams["statement"] = _statement([_line(1, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM)])
    columns = [column["label"] for column in _blocks(_run())["records"]["columns"]]
    assert columns == [
        "Bank line",
        "Bank amount",
        "Nearest batch",
        "Batch amount",
        "Difference",
        "Likely cause",
        "Fix",
    ]


def test_the_kpi_strip_draws_five_tiles_and_the_fee_money_is_a_detail(seams):
    """`RBS-006-R14` region 2 — five tiles. The frame folds the money into the
    LABEL; a money value typed into a label loses its currency and its
    two-decimal rule (hard rule 2), so it travels in `detail`."""
    seams["statement"] = _statement([_line(1, amount="-12.0000", state=br.STATE_NOT_IN_OUR_SYSTEM)])
    tiles = _blocks(_run())["kpis"]["tiles"]
    assert [tile["id"] for tile in tiles] == [
        "matched",
        "matched_value",
        "unmatched",
        "unmatched_value",
        "fees",
    ]
    assert tiles[4]["label"] == "Bank fee"
    assert "USD" in tiles[4]["detail"]


def test_every_unmatched_line_carries_a_fix_route(seams):
    """`BR-RBS-011` — asserted over the DRAWN cells."""
    seams["statement"] = _statement(
        [
            _line(1, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM),
            _line(2, amount="60.0000", state=br.STATE_NEEDS_A_LOOK),
        ],
        [_batch("Kiosk 3 Sep", total="120.0000")],
    )
    rows = _blocks(_run())["records"]["rows"]
    assert len(rows) == 2
    for row in rows:
        assert row["cells"]["fix"]["kind"] == "link"
        assert row["cells"]["fix"]["to"]


def test_no_database_id_reaches_a_drawn_cell(seams):
    """B14 rule 31 — the batch's CODE is what a clerk reads, never its id."""
    import re

    seams["statement"] = _statement(
        [_line(1, amount="500.0000", state=br.STATE_NEEDS_A_LOOK)],
        [_batch("Lockbox 3 Sep", total="480.0000",
                batch_id="0191ee1a-0f3d-7419-a222-10f2a9be7fe9")],
    )
    payload = _blocks(_run())["records"]
    drawn = " ".join(
        str(value)
        for row in payload["rows"]
        for column in payload["columns"]
        for value in row["cells"][column["key"]].values()
    )
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", drawn
    ), drawn
    assert not re.search(r"\bBR-[A-Z]{3}-\d{3,5}\b", drawn), drawn


def test_an_empty_unmatched_list_says_every_line_ties(seams):
    seams["statement"] = _statement(
        [_line(1, amount="500.0000", state=br.STATE_AUTO, batch_code="DEP-0917",
               batch_id="b1", recorded="500.0000", difference="0.000000")]
    )
    records = _blocks(_run())["records"]
    assert records["rows"] == []
    assert records["empty"]["title"] == "Every line ties."


def test_step_six_says_out_loud_that_it_raises_no_work_item(seams):
    """Hard-won law 1 — a runbook that claims to raise work items and does not.

    The engine's upsert is wave C's and is not built, so this is REPORTED rather
    than assumed closed.
    """
    seams["statement"] = _statement([_line(1, amount="610.0000", state=br.STATE_NOT_IN_OUR_SYSTEM)])
    checked = _run().set_results[br.STEP_REST]["checked"]
    assert checked["work_items_raised"] == 0
    assert "not built yet" in checked["work_item_queue_state"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-026 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
