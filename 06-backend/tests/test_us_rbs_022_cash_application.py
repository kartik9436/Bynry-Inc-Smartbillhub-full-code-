# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-022 · US-RBS-017 (EP-RBS-05) — CR-075 wave P, runbook 10.
# Rules:    BR-RBS-002 · BR-RBS-004 · BR-RBS-005 · BR-RBS-018 · BR-RBS-011 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-027 · RBR-14 ·
#           CLAUDE.md hard rule 2 · B14 rules 31 and 32
# Tests:    this file. The PostgreSQL half — the stop, the money path and the
#           cross-tenant read — is tests/test_rbs_money_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/cash_application.py
# ───────────────────────────────────────────────────────
"""Runbook 10, against the rules rather than against itself.

**EVERY CASE HERE ASSERTS A RULE AND NOT AN IMPLEMENTATION.** A test that
asserted *"step 4 returns a dict with four keys"* would go green over a runbook
that had stopped holding duplicates, which is the whole thing `RBR-14` is for.

⚠ **THE SEAMS ARE REPLACED, AND WHAT THAT DOES AND DOES NOT PROVE IS STATED.**
These cases hand the runbook fixed answers so the DECISIONS can be exercised —
a duplicate, an overpayment, a name-only suggestion, an unreadable balance —
none of which a seeded tenant happens to contain. **It proves the runbook's
reasoning and it proves NOTHING about the seams**: a seam returning the wrong
shape passes every case in this file. That is what
`tests/test_rbs_money_runbooks_pg.py` is for, and it runs the REAL seams against
real rows on real PostgreSQL. Both numbers are quoted in the lane report;
neither is quoted alone.
"""


import pytest

from apps.runbooks import models
from apps.runbooks.contract import BLOCK_TYPES, RunbookContractError, validate_report
from apps.runbooks.definitions import cash_application as ca
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

BATCH_ID = "batch-1"


def _row(row_no, *, state, method, account=None, amount="100.0000", reference=None, name=None):
    return {
        "row_id": f"row-{row_no}",
        "row_no": row_no,
        "raw": {"payer_name": name, "reference": reference},
        "amount": amount,
        "amount_display": amount,
        "paid_on": "2026-09-05",
        "reference": reference,
        "account_id": account,
        "invoice_id": None,
        "match_method": method,
        "match_state": state,
        "match_detail": (
            f"account {account}, named by the file" if method == "account_no" else "detail"
        ),
        "payment_id": None,
        "commit_error": None,
    }


def _batch(rows, *, source_kind="lockbox"):
    return {
        "batch_id": BATCH_ID,
        "file_name": "lockbox-2026-09-05.csv",
        "source_kind": source_kind,
        "status": "validated",
        "currency": "USD",
        "counts": {"rows": len(rows)},
        "rows": rows,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the four reads runbook 10 makes.

    Returns a mutable dict the case tunes. Everything defaults to *nothing is
    connected and nothing was uploaded*, which is the STOP — so a case that
    forgets to give the runbook work cannot accidentally assert on a happy path.
    """
    state = {
        "connections": [],
        "batch": None,
        "recorded": [],
        "positions": {},
    }
    monkeypatch.setattr(
        ca.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )
    monkeypatch.setattr(ca.payments_seam, "import_batch", lambda batch_id: state["batch"])
    monkeypatch.setattr(
        ca.payments_seam,
        "payments_recorded_between",
        lambda ids, start, end: list(state["recorded"]),
    )
    monkeypatch.setattr(
        ca.payments_seam,
        "open_bill_position",
        lambda account_id: state["positions"].get(str(account_id), {"total_open": "100.0000"}),
    )
    monkeypatch.setattr(ca.payments_seam, "tenant_currency", lambda: "USD")
    monkeypatch.setattr(ca.tenancy_seam, "today", lambda: __import__("datetime").date(2026, 9, 6))
    return state


def _run(params=None, *, run_id=None):
    definition = ca.RUNBOOK
    ctx = executor.build_context(
        definition, tenant_id="t", run_id=run_id, params=params or {"batch": BATCH_ID}
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_an_action_holding_exactly_the_two_ports_the_card_names():
    """`RB-110`: *Ports it holds — `apply_payment` (payments) · `queue_receipt`*.

    An Action, so its context HOLDS those two declarations; and it holds no
    third, because a fourteenth port is a reviewed interface and a thirteenth it
    did not declare would be a capability nobody agreed (`BR-RBS-022`).
    """
    assert ca.RUNBOOK.kind == models.KIND_ACTION
    assert ca.RUNBOOK.ports == ("apply_payment", "queue_receipt")
    ctx = executor.build_context(ca.RUNBOOK)
    assert sorted(ctx.ports) == ["apply_payment", "queue_receipt"]
    assert ca.RUNBOOK.writes_nothing() is False


def _as_a_check(**overrides):
    fields = dict(
        key="cash_application_as_a_check",
        name="Cash application",
        kind=models.KIND_CHECK,
        category="payments",
        subject_type="payment",
        unit_of_work="a landed payment",
        resolve=ca.resolve,
        report=ca.report,
        steps=ca.RUNBOOK.steps,
        ports=ca.RUNBOOK.ports,
    )
    fields.update(overrides)
    return ca.RunbookDefinition(**fields)


def test_the_same_runbook_declared_a_check_is_refused_for_its_writing_step():
    """`BR-RBS-002` · `TC-RBS-1`, first clause — the claim and the capability
    must agree, and the STEP's claim is checked before the port list is even
    reached. The message names the runbook AND the step."""
    with pytest.raises(RunbookContractError) as refusal:
        _as_a_check()
    assert ca.STEP_APPLY in str(refusal.value)
    assert "writes=True" in str(refusal.value)


def test_the_same_runbook_declared_a_check_is_refused_for_its_ports():
    """`BR-RBS-002` · `TC-RBS-1`, second clause — **the capability is ABSENT.**

    ⚠ **THE STEPS ARE STRIPPED OF THEIR WRITE CLAIM SO THIS CASE REACHES THE
    RULE IT IS NAMED AFTER.** With them left alone the constructor refuses one
    step earlier and this assertion would pass over a port list nobody checked —
    a test named after an assertion it does not make, which is one of the four
    shapes hard-won law 7 enumerates.
    """
    quiet = tuple(
        ca.Step(key=s.key, label=s.label, mode=s.mode, run=s.run) for s in ca.RUNBOOK.steps
    )
    with pytest.raises(RunbookContractError) as refusal:
        _as_a_check(steps=quiet)
    assert "apply_payment" in str(refusal.value)
    assert "queue_receipt" in str(refusal.value)


def test_every_step_declares_a_mode_and_only_the_two_write_steps_write():
    """`BR-RBS-023`, and `RB-110`'s own heading: *seven · five read, two write*."""
    assert len(ca.RUNBOOK.steps) == 7
    assert [step.mode for step in ca.RUNBOOK.steps].count(ca.MODE_PER_RECORD) == 1
    assert [step.writes for step in ca.RUNBOOK.steps].count(True) == 2


def test_a_money_parameter_carries_a_string_and_never_a_float():
    """Hard rule 2, and no column can hold it — the parameter lives in `jsonb`."""
    money = [p for p in ca.RUNBOOK.parameters if p.type == "money"]
    assert money, "the overpayment threshold is a money parameter"
    for parameter in money:
        assert not isinstance(parameter.default, float), parameter.name


# ── the stop ──────────────────────────────────────────────────────────────


def test_no_connection_and_no_file_stops_the_run_and_names_both(seams):
    """PO ruling 2026-09-06 — *"that is a valid case and state for us"*.

    The run STOPS rather than failing, and the sentence names BOTH absences:
    *"no connection"* alone would send a clerk to Settings when what they
    actually needed was to upload the file.
    """
    result = _run()
    assert result.subjects == ()
    first = result.set_results[ca.STEP_SOURCE]
    assert first["stop"]["headline"] == "Nothing to work on."
    assert "No payment connection is set up." in first["stop"]["detail"]
    assert "uploaded a file" in first["stop"]["detail"]


def test_after_a_stop_every_later_step_reads_never_reached(seams):
    """`BR-RBS-027` — a stopped run reads *Never reached*, never blank.

    A blank cell reads as *nothing wrong*, which is the opposite of the truth.
    """
    result = _run()
    later = [key for key in ca.STEP_LABELS if key != ca.STEP_SOURCE]
    for key in later:
        if key == ca.STEP_APPLY:  # per-record: no subjects, so it never ran
            continue
        assert result.set_results[key]["reached"] is False, key


def test_a_stopped_run_draws_a_chain_of_one_red_cell_and_six_never_reached(seams):
    """The screen the Product Owner asked to see: a designed answer, not a crash."""
    blocks = _blocks(_run())
    chain = blocks["chain"]
    assert len(chain["cells"]) == 7
    assert chain["cells"][0]["state"] == "bad"
    assert chain["cells"][0]["note"] == "Nothing to work on."
    assert [cell["state"] for cell in chain["cells"][1:]] == ["notReached"] * 6


def test_a_stopped_run_draws_no_kpi_strip(seams):
    """Hard-won law 7 — *0 applied · $0.00 · 0 need a person* over a run that
    examined nothing is indistinguishable from a clean day."""
    assert "kpis" not in _blocks(_run())


def test_a_connection_but_no_file_is_a_different_sentence(seams):
    """*Nothing has landed yet* is not *nothing is set up*, and one has a fix."""
    seams["connections"] = [
        {"key": "bank_lockbox_file", "display_name": "Lockbox file", "status": "working",
         "enabled": True}
    ]
    stop = _run().set_results[ca.STEP_SOURCE]["stop"]
    assert stop["headline"] == "Nothing has landed yet."
    assert "Lockbox file" in stop["detail"]


def test_a_connection_that_is_switched_off_is_named_as_such(seams):
    """A row that exists with the switch off has a two-second fix, and saying
    *"nothing is set up"* over it sends somebody to do the work twice."""
    seams["connections"] = [
        {"key": "pay_invoicecloud", "display_name": "InvoiceCloud", "status": "working", "enabled": False}
    ]
    stop = _run().set_results[ca.STEP_SOURCE]["stop"]
    assert "switched off" in stop["detail"]


# ── the match ladder ──────────────────────────────────────────────────────


def test_a_file_named_account_is_planned_and_a_name_match_asks_a_person(seams):
    """`RB-110`: *a clerk confirms a guess, the runbook does not make it*.

    `payment_import._match_row` writes `name_amount` with the account filled in
    as a SUGGESTION. A runbook that treated a filled-in account as a match would
    post money to the wrong customer on a name collision.
    """
    seams["batch"] = _batch(
        [
            _row(1, state="clean", method="account_no", account="acct-1"),
            _row(2, state="review", method="name_amount", account="acct-2", name="Alvarez, M."),
            _row(3, state="review", method="none"),
        ]
    )
    result = _run()
    outcomes = {record.subject.subject_id: record.outcome for record in result.records}
    assert outcomes["row-1"] == ca.OUTCOME_PLANNED
    assert outcomes["row-2"] == ca.OUTCOME_NEEDS_A_PERSON
    assert outcomes["row-3"] == ca.OUTCOME_NEEDS_A_PERSON


def test_every_row_needing_a_person_carries_a_fix_route(seams):
    """`BR-RBS-011` — a failure with no route is a defect in the runbook.

    Asserted over the DRAWN cells, because a route carried in `meta` and never
    drawn is a route a clerk cannot use.
    """
    seams["batch"] = _batch(
        [_row(1, state="review", method="none"), _row(2, state="review", method="none")]
    )
    records = _blocks(_run())["records"]
    assert records["rows"]
    for row in records["rows"]:
        assert row["cells"]["fix"]["kind"] == "link"
        assert row["cells"]["fix"]["to"]
        assert row["cells"]["fix"]["label"]


# ── the duplicate window ──────────────────────────────────────────────────


def test_a_duplicate_is_held_and_never_rejected(seams):
    """`RBR-14` — the second payment is real money somebody sent.

    ⚠ **HELD IS NOT REJECTED AND NOT SKIPPED.** A held payment keeps a record
    row, appears on the screen and is counted in its own tile; a rejected one
    would be money nobody chased.
    """
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    seams["recorded"] = [
        {"payment_id": "p1", "account_id": "acct-1", "amount": "100.0000", "currency": "USD",
         "status": "cleared", "confirmation": "88213", "posted_on": "2026-09-05"}
    ]
    result = _run()
    assert [r.outcome for r in result.records] == [ca.OUTCOME_DUPLICATE_HELD]
    tiles = {t["id"]: t for t in _blocks(result)["kpis"]["tiles"]}
    assert tiles["held"]["value"]["text"] == "1"
    assert tiles["held"]["detail"] == "Held, never rejected"


def test_the_same_amount_twice_inside_one_file_holds_the_second_only(seams):
    """A file that lists one cheque twice is the common lodging mistake, and the
    FIRST of the pair is still real money — holding both would stop a legitimate
    payment as well as the copy."""
    seams["batch"] = _batch(
        [
            _row(1, state="clean", method="account_no", account="acct-1"),
            _row(2, state="clean", method="account_no", account="acct-1"),
        ]
    )
    outcomes = [record.outcome for record in _run().records]
    assert outcomes == [ca.OUTCOME_PLANNED, ca.OUTCOME_DUPLICATE_HELD]


# ── the balance ───────────────────────────────────────────────────────────


def test_an_overpayment_above_the_threshold_asks_a_person(seams):
    """`RB-110`: *over- and short-payments flagged, never guessed*."""
    seams["batch"] = _batch(
        [_row(1, state="clean", method="account_no", account="acct-1", amount="1204.0500")]
    )
    seams["positions"] = {"acct-1": {"total_open": "0.0000"}}
    record = _run().records[0]
    assert record.outcome == ca.OUTCOME_NEEDS_A_PERSON
    assert "more than this account owes" in record.reason


def test_a_short_payment_is_still_applied(seams):
    """A part payment is what the allocation order is FOR. Stopping one would
    turn every instalment into a question."""
    seams["batch"] = _batch(
        [_row(1, state="clean", method="account_no", account="acct-1", amount="40.0000")]
    )
    seams["positions"] = {"acct-1": {"total_open": "100.0000"}}
    result = _run()
    assert result.records[0].outcome == ca.OUTCOME_PLANNED
    assert result.set_results[ca.STEP_BALANCE]["checked"]["short_payments"] == 1


def test_a_balance_that_will_not_read_is_named_and_never_skipped(seams):
    """`G32`'s shape — a check that reports clean over what it could not see.

    The seam answers `None`, and this payment becomes a row a person can act on
    rather than one of 137 that quietly succeeded.
    """
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    seams["positions"] = {}
    ca_open = ca.payments_seam.open_bill_position
    try:
        ca.payments_seam.open_bill_position = lambda account_id: None
        result = _run()
    finally:
        ca.payments_seam.open_bill_position = ca_open
    assert result.records[0].outcome == ca.OUTCOME_NEEDS_A_PERSON
    assert "could not be read" in result.records[0].reason
    assert result.set_results[ca.STEP_BALANCE]["checked"]["balances_that_would_not_read"] == 1


# ── the second approval, which is the rule that bites ─────────────────────


def test_without_a_second_approval_nothing_is_applied(seams):
    """`BR-RBS-018`, CONFIRMED — *every money action, no threshold*.

    ⚠ **THE ASSERTION IS ON THE PORT, NOT ON A COUNT.** A run that reached
    `apply_payment` and was refused for some other reason would satisfy a count
    assertion. This one proves the port was never CALLED: the outcome's reason
    names the second person, and `PortNotBound`'s wording — which is what a
    reached port produces — is absent.
    """
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    record = _run().records[0]
    assert record.outcome == ca.OUTCOME_PLANNED
    assert record.reason == "Waiting for a second person to approve this run."
    assert "no writer bound" not in record.decided_by_rule


def test_an_approval_for_the_wrong_count_is_no_approval(seams):
    """`BR-RBS-005` · `TC-RBS-8` — approving *129 to apply* and acting on 140.

    The reason names BOTH numbers, because a clerk who approved the wrong plan
    needs to know which plan they approved.
    """
    seams["batch"] = _batch(
        [
            _row(1, state="clean", method="account_no", account="acct-1"),
            _row(2, state="clean", method="account_no", account="acct-2", amount="55.0000"),
        ]
    )
    run = _run_row(approved_count=99)
    result = _run(run_id=run.pk)
    assert {record.outcome for record in result.records} == {ca.OUTCOME_PLANNED}
    assert "The approval covers 99 and this plan has 2" in result.records[0].reason


def test_a_matching_approval_reaches_the_port_and_the_port_refuses(seams):
    """The other half, and it proves the dry promise rather than a stub.

    With the approval matching the plan the runbook CALLS `apply_payment`, and
    the port answers `PortNotBound` because wave `L2` has not bound a writer.
    The outcome is still `planned` — **nothing is applied** — and the port's own
    refusal is what says why. There is no `if is_bound` branch to make this
    pass (`BR-RBS-003`).
    """
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    run = _run_row(approved_count=1)
    record = _run(run_id=run.pk).records[0]
    assert record.outcome == ca.OUTCOME_PLANNED
    assert record.reason == "Ready to apply. Nothing is written yet."
    assert "no writer bound" in record.decided_by_rule
    assert "wave L" in record.decided_by_rule


def _run_row(*, approved_count):
    """A runbook and an approved run, for the two approval cases.

    ⚠ **`apps.identity.models.User`, NOT pytest-django's `django_user_model`.**
    That fixture returns whatever `AUTH_USER_MODEL` names, which in this project
    is not the `identity.User` that `runbook_runs.approved_by` points at — the
    first draft used it and failed with *"User() got unexpected keyword
    arguments: 'tenant', 'full_name'"*. The FK decides the model, not the
    setting.
    """
    from apps.identity.models import User
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.create(name="Brazos Bend", subdomain="brazos-rbs-p")
    approver = User.objects.create(
        tenant=tenant, email="tom@example.test", full_name="Tom Nguyen"
    )
    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key=ca.KEY,
        name="Cash application",
        kind=models.KIND_ACTION,
        category="payments",
        subject_type="payment",
        unit_of_work="a landed payment",
        cap=100,
    )
    return models.RunbookRun.objects.create(
        tenant=tenant,
        runbook=runbook,
        version=1,
        status=models.RUN_STATUS_APPROVED,
        approved_by=approver,
        approved_count=approved_count,
    )


# ── the report ────────────────────────────────────────────────────────────


def test_the_report_names_only_blocks_from_the_twelve(seams):
    """`BR-RBS-021` — a thirteenth needs THREE runbooks that cannot be drawn
    without it, and this runbook mints none."""
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    result = _run()
    for block in result.report:
        assert block["block"] in BLOCK_TYPES
    validate_report(result.report, runbook_key=ca.KEY)


def test_the_tiles_say_to_apply_while_nothing_is_applied(seams):
    """A tile reading *129 Applied* over a run that applied nothing is the most
    dangerous sentence this screen could print."""
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    tiles = {t["id"]: t for t in _blocks(_run())["kpis"]["tiles"]}
    assert tiles["placed"]["label"] == "To apply"
    assert tiles["placed"]["detail"] == "Planned — waiting for a second approval"
    assert tiles["value"]["value"]["kind"] == "money"
    assert tiles["value"]["value"]["currency"] == "USD"


def test_the_by_source_table_counts_what_actually_landed(seams):
    """The by-source table is what tells a utility which channel is dirty."""
    seams["batch"] = _batch(
        [
            _row(1, state="clean", method="account_no", account="acct-1"),
            _row(2, state="review", method="none"),
        ]
    )
    rows = _blocks(_run())["breakdown"]["rows"]
    assert len(rows) == 1
    cells = rows[0]["cells"]
    assert cells["source"]["text"] == "Lockbox"
    assert cells["landed"]["text"] == "2"
    assert cells["placed"]["text"] == "1"
    assert cells["unmatched"]["text"] == "1"


def test_no_database_id_and_no_rule_id_reaches_a_drawn_cell(seams):
    """B14 rules 31 and 32, asserted over what a renderer WALKS.

    The renderer walks `columns`, so `meta` cannot reach a screen — and
    `decided_by_rule` lives there precisely because the result file needs it and
    a clerk must not see it.
    """
    import re

    seams["batch"] = _batch([_row(1, state="review", method="none", account=None)])
    blocks = _blocks(_run())
    drawn: list[str] = []
    for payload in blocks.values():
        for row in payload.get("rows", []):
            for key in [column["key"] for column in payload["columns"]]:
                cell = row["cells"][key]
                drawn.extend(str(value) for value in cell.values())
    joined = " ".join(drawn)
    assert not re.search(r"\bBR-[A-Z]{3}-\d{3,5}\b", joined), joined
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", joined
    ), joined


def test_the_records_table_draws_the_frames_six_columns_in_order(seams):
    """`RBS-006-R10` region 6 — *columns in THIS order*."""
    seams["batch"] = _batch([_row(1, state="review", method="none")])
    columns = [column["label"] for column in _blocks(_run())["records"]["columns"]]
    assert columns == ["Payment", "Source", "Amount", "Likeliest account", "Why", "Fix"]


def test_an_empty_unmatched_list_says_what_is_true_and_not_what_is_missing(seams):
    """B14 rule 17's shape — a clean file is a GOOD outcome, not a gap."""
    seams["batch"] = _batch([_row(1, state="clean", method="account_no", account="acct-1")])
    records = _blocks(_run())["records"]
    assert records["rows"] == []
    assert records["empty"]["title"] == "Every payment found its account."


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-022 · US-RBS-017 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
