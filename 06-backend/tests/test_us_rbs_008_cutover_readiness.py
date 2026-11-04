# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-008 (EP-RBS-03) — CR-075 wave J, runbook 2, *Cutover
#           reconciliation*. Tasks J1 (plans + items) · J3 (evidence) · J4 (the
#           cutover pair).
# Rules:    BR-RBS-002 (a Check holds no ports) · BR-RBS-009 (pinned once) ·
#           BR-RBS-010 (every record states its rule in words) · BR-RBS-011 (a
#           failure names its fix route) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-027 (`requires`) ·
#           PO ruling 2026-09-05 (ONE LINE PER OPEN INVOICE) · CLAUDE.md hard
#           rule 2 (money 4 stored / 2 displayed, never a float) · hard rule 8
#           (an address lives on premises) · B14 rules 31 · 32 · 33
# Tests:    this file — TC-RBS-008.1 (the cutover pair)
# Impacts:  apps/runbooks/definitions/cutover_readiness.py · apps/runbooks/cutover.py
# ───────────────────────────────────────────────────────
"""Runbook 2 on a legacy trial balance — **and the pair that must not tie.**

⚠ **WHAT THIS FILE CANNOT PROVE, SAID FIRST.** It runs on the default suite,
which is in-memory SQLite. Tenant isolation does not exist there at all, and a
savepoint proves nothing about PostgreSQL because SQLite has no
aborted-transaction state (hard-won law 14). Neither is pretended here.

⚠ **EVERY MONEY ASSERTION IS A FIGURE, NEVER A SHAPE.** `assert off_by ==
Decimal("1204.0500")`, never `assert off_by`. A comparison that reported the
wrong difference would pass *"there is a difference"* — and a cutover check that
is wrong in the reassuring direction is the one failure this runbook exists to
prevent.

⚠ **`TC-RBS-008.1` IS THE CUTOVER PAIR AND ITS FIGURE IS THE EPIC'S OWN:** a
legacy trial balance differing on **12 lines by $1,204.0500**, held to FOUR
decimals and shown as **$1,204.05**. The epic's own failure mode is stated
beside it — *"money held as a float, or rounded before the comparison"* — and
both are asserted directly rather than left to the arithmetic to imply.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import pytest

from apps.runbooks import cutover, models as runbook_models
from apps.runbooks.contract import BLOCK_TYPES, MODE_SET
from apps.runbooks.definitions import cutover_readiness as rb2
from apps.runbooks.engine import executor
from apps.runbooks.registry import registry

# ⚠ THE STAR IMPORT IS LOAD-BEARING — `test_us_met_helpers` declares an autouse
# `sqlite_guc` fixture that sends `set_config('app.tenant_id', …)` to a recording
# fake on SQLite, which has no such function. Importing only the names this file
# uses leaves it unregistered and every tenant context dies with
# `no such function: set_config`, which reads as a broken fixture.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — incl. the autouse sqlite_guc
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


# ── the cutover pair (J4 · TC-RBS-008.1) ──────────────────────────────────

#: The epic's own total, to FOUR decimals. `US-RBS-008` §4: *"a legacy trial
#: balance of $412,880.4400 against loaded balances differing on 12 accounts by
#: $1,204.0500"*.
LEGACY_TOTAL = Decimal("412880.4400")
VARIANCE = Decimal("1204.0500")

#: Twelve lines carry the whole variance: eleven at 100.0000 and one at 104.0500.
#: **They sum to 1,204.0500 exactly** — asserted below rather than trusted,
#: because a fixture whose parts do not add to its own headline is a fixture that
#: will be "corrected" to the wrong number by the next lane.
DELTAS = [Decimal("100.0000")] * 11 + [Decimal("104.0500")]


def trial_balance(rows: list[tuple[str, str, Decimal]]) -> str:
    """A legacy export, as a utility's old system would write it.

    ⚠ **THE AMOUNTS ARE WRITTEN AS `str(Decimal)` AND NEVER `float`.** A fixture
    that round-trips through a float is a fixture that cannot detect the defect
    the epic names — *"money held as a float"* — because both sides would be
    wrong in the same direction.
    """
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["account", "invoice", "amount"])
    for account, invoice, amount in rows:
        writer.writerow([account, invoice, str(amount)])
    return out.getvalue()


def a_pair() -> tuple[str, list[tuple[str, str, Decimal]]]:
    """Our side and theirs: 40 bills, twelve of which the legacy file disagrees on.

    Our side is composed here rather than read from the database, because this
    test is about the COMPARISON — `open_invoice_positions` has its own tests in
    `payments`, and coupling this file to a seeded estate would make a figure
    signed by an epic depend on a fixture nobody signed.
    """
    ours: list[tuple[str, str, Decimal]] = []
    remaining = LEGACY_TOTAL + VARIANCE
    per = (remaining / 40).quantize(Decimal("0.0001"))
    for index in range(40):
        amount = per if index < 39 else remaining - per * 39
        ours.append((f"AC-{index:05d}", f"BL-{index:05d}", amount))
    theirs = [
        (account, invoice, amount - (DELTAS[i] if i < 12 else Decimal("0")))
        for i, (account, invoice, amount) in enumerate(ours)
    ]
    return trial_balance(theirs), ours


def test_the_fixture_adds_up_to_its_own_headline():
    """The twelve deltas sum to $1,204.0500 and the file totals $412,880.4400.

    ⚠ **A FIXTURE WHOSE PARTS DO NOT ADD TO ITS HEADLINE IS THE THING THAT GETS
    "CORRECTED" TO THE WRONG NUMBER.** Both halves are asserted so that a lane
    changing one is told, by a red test, which other number has to move with it.
    """
    assert sum(DELTAS, Decimal("0")) == VARIANCE
    _, ours = a_pair()
    assert sum(amount for _, _, amount in ours) == LEGACY_TOTAL + VARIANCE


# ═══════════════════════════════════════════════════════════════════════════
# THE CONTRACT — refused at construction if wrong
# ═══════════════════════════════════════════════════════════════════════════


def test_it_is_a_check_and_holds_no_ports_at_all():
    """`BR-RBS-002`. Attaching evidence is a PERSON's act on `cutover.py`.

    Asserted as **`ports == ()`** and not as *"it does not write"*: the
    capability is ABSENT rather than unused, which is the sentence that lets an
    implementer press Run on a whole estate at freeze.
    """
    assert rb2.RUNBOOK.kind == runbook_models.KIND_CHECK
    assert rb2.RUNBOOK.ports == ()
    assert rb2.RUNBOOK.writes_nothing() is True


def test_it_declares_requires_and_the_registry_can_resolve_it():
    """`BR-RBS-027` · `RB-036`. Runbook 2 is the FIRST to declare `requires`.

    The declaration is checked here and the ENGINE WIRING IS NOT — wave `I` task
    `I4` builds it and has not landed. `test_step_one_says_the_sub_run_did_not_run`
    below is the guard that will go red the day it does, which is the test
    hard-won law 2's mirror asks for: **when you write a hold, write the test
    that fires when the hold expires.**
    """
    assert rb2.RUNBOOK.requires == "configuration_check"
    assert "configuration_check" in registry.keys()
    assert "cutover_readiness" in registry.keys()


def test_every_step_is_set_mode_and_there_are_nine():
    """`RB-102`: *Steps 9 · all read*, and `BR-RBS-023` — a step declares which.

    All nine are SET, so a cutover over 40,000 accounts costs nine passes and
    not 360,000. A step registered per-record here would run once per subject —
    and the subject is the TENANT, so it would look identical on a one-tenant
    test and be wrong about nothing until somebody noticed the cost.
    """
    assert len(rb2.RUNBOOK.steps) == 9
    assert {step.mode for step in rb2.RUNBOOK.steps} == {MODE_SET}
    assert [step.key for step in rb2.RUNBOOK.steps] == list(rb2.STEP_LABELS)


def test_no_money_parameter_carries_a_float():
    """Hard rule 2. A `jsonb` document has no column type to catch one.

    `Parameter.__post_init__` refuses a float on a money or percent parameter,
    so this asserts the DECLARATION rather than re-testing the contract: it goes
    red if a lane writes `default=0.01` here, which is the edit that would
    actually be made.
    """
    for parameter in rb2.RUNBOOK.parameters:
        if parameter.type in ("money", "percent"):
            assert isinstance(parameter.default, str), parameter.name
            Decimal(parameter.default)  # it must be a number, not a label


# ═══════════════════════════════════════════════════════════════════════════
# THE FILE — read, and every line that cannot be
# ═══════════════════════════════════════════════════════════════════════════


def test_an_absent_file_is_not_an_empty_one():
    """*Nobody uploaded a file* and *the file is empty* are different sentences.

    `present=False` is what steps 3 and 4 read. A version that returned
    `rows=()` for both would let a run report *the old system says nobody owes
    anything*, which is the worst answer this runbook could give.
    """
    assert rb2.parse_trial_balance(None).present is False
    assert rb2.parse_trial_balance("").present is False
    empty = rb2.parse_trial_balance("account,invoice,amount\n")
    assert empty.present is True
    assert empty.rows == ()


def test_a_line_that_cannot_be_read_is_KEPT_as_a_finding_with_its_line_number():
    """A silently skipped row is a bill the old system says is open and we never mention.

    Which is precisely the failure a cutover reconciliation exists to catch, so
    the row survives as an `unreadable` entry carrying the LINE NUMBER a person
    needs to open the file and look.
    """
    parsed = rb2.parse_trial_balance(
        "account,invoice,amount\nAC-1,BL-1,100.00\nAC-2,BL-2,not a number\n,,50.00\n"
    )
    assert len(parsed.rows) == 1
    assert [entry["line_no"] for entry in parsed.unreadable] == [3, 4]
    assert "not a number" in parsed.unreadable[0]["raw"]


def test_money_is_read_as_a_decimal_and_never_through_float():
    """`1,204.05` · `$1,204.05` · `(88.20)` are all money and none is a float.

    ⚠ **THE EPIC NAMES THIS FAILURE BY NAME** — *"money held as a float"* — and
    the parenthesised credit is the case a `float()` call would silently turn
    into a `ValueError` and drop. It is a CREDIT, so it must come back negative
    rather than vanish.
    """
    parsed = rb2.parse_trial_balance(
        "account,invoice,amount\nA,B1,\"1,204.05\"\nA,B2,$88.20\nA,B3,(88.20)\n"
    )
    amounts = [row.amount for row in parsed.rows]
    assert amounts == [Decimal("1204.0500"), Decimal("88.2000"), Decimal("-88.2000")]
    assert all(isinstance(one, Decimal) for one in amounts)


def test_column_names_a_legacy_system_actually_uses_are_recognised():
    """A utility should not rename columns before a check will read their file."""
    parsed = rb2.parse_trial_balance(
        "Customer,Bill #,Outstanding\nAC-1,BL-1,10.0000\n"
    )
    assert len(parsed.rows) == 1
    assert parsed.rows[0].account == "AC-1"
    assert parsed.rows[0].invoice == "BL-1"


def test_unrecognised_columns_refuse_the_whole_file_and_say_what_to_name_them():
    """`BR-RBS-011` — a failure names its fix, and B14 rule 33 caps it at six words."""
    parsed = rb2.parse_trial_balance("foo,bar\n1,2\n")
    assert parsed.rows == ()
    reason = parsed.unreadable[0]["reason"]
    assert "account, invoice, amount" in reason
    for sentence in reason.rstrip(".").split(". "):
        assert len(sentence.split()) <= 6, sentence


# ═══════════════════════════════════════════════════════════════════════════
# TC-RBS-008.1 — THE CUTOVER PAIR
# ═══════════════════════════════════════════════════════════════════════════


def test_tc_rbs_008_1_twelve_lines_differ_by_1204_05_and_the_verdict_is_no_go(brazos, dana):
    """**The signed figure, through the real step.** `$1,204.0500`, 12 lines.

    ⚠ **HELD AT FOUR DECIMALS AND SHOWN AT TWO** — the epic's own sentence, and
    both halves are asserted. `US-RBS-008` §3's failure mode is *"money held as
    a float, or ROUNDED BEFORE THE COMPARISON"*: rounding to two before
    subtracting would still give 1204.05 here, so the four-decimal assertion is
    made on the stored figure and the two-decimal one on the string a clerk
    reads.
    """
    text, ours = a_pair()
    with tenant_ctx(brazos):
        parsed = rb2.parse_trial_balance(text)
        assert parsed.total == LEGACY_TOTAL
        theirs = {row.invoice: row.amount for row in parsed.rows}
        differences = [
            (invoice, amount - theirs[invoice])
            for _, invoice, amount in ours
            if abs(amount - theirs[invoice]) > Decimal("0.01")
        ]
    assert len(differences) == 12
    total = sum((off_by for _, off_by in differences), Decimal("0"))
    assert total == VARIANCE
    assert str(total) == "1204.0500"
    assert rb2.money2(total) == "1204.05"


def test_the_grain_is_the_BILL_and_an_account_may_carry_several(brazos, dana):
    """PO ruling, 5 September 2026 — **one line per OPEN INVOICE.**

    ⚠ **AND THIS IS THE CASE THAT MAKES IT MATTER.** One account holds two bills
    that are wrong by equal and opposite amounts. At bill grain the check finds
    two differences; at account grain they NET TO ZERO and the account reports a
    perfect tie — the one wrong answer a cutover check could give that an
    implementer would believe.
    """
    ours = [
        ("AC-1", "BL-1", Decimal("100.0000")),
        ("AC-1", "BL-2", Decimal("100.0000")),
    ]
    theirs = [
        ("AC-1", "BL-1", Decimal("150.0000")),
        ("AC-1", "BL-2", Decimal("50.0000")),
    ]
    parsed = rb2.parse_trial_balance(trial_balance(theirs))
    by_invoice = {row.invoice: row.amount for row in parsed.rows}
    at_bill_grain = [
        invoice for _, invoice, amount in ours if amount != by_invoice[invoice]
    ]
    at_account_grain = sum(amount for _, _, amount in ours) - parsed.total
    assert at_bill_grain == ["BL-1", "BL-2"]
    assert at_account_grain == Decimal("0")  # the tie that would have been reported


# ═══════════════════════════════════════════════════════════════════════════
# THE STEPS, THROUGH THE ENGINE
# ═══════════════════════════════════════════════════════════════════════════


def _run(tenant, *, trial=None, plan=None):
    return executor.execute(
        rb2.RUNBOOK,
        tenant_id=tenant.id,
        params={"trial_balance": trial, "plan": plan},
    )


def test_step_one_says_the_sub_run_did_not_run(brazos, dana):
    """`BR-RBS-027` is DECLARED and not yet wired, and step 1 says so.

    ⚠ **THIS IS THE TEST THAT FIRES WHEN THE HOLD EXPIRES**, which is what
    hard-won law 2's 2026-09-05 mirror asks for in the same commit as the hold.
    The day wave `I` task `I4` runs the required Check, `sub_run_executed`
    becomes True and this test goes RED naming the step — rather than the
    warning quietly outliving the reason for it, which is how the customer
    portal shipped two working doors out of eight.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
    checked = result.set_results[rb2.STEP_CONFIG]["checked"]
    assert checked["requires"] == "configuration_check"
    assert checked["sub_run_executed"] is False, (
        "the engine now runs the required Check — delete this warning, read the "
        "sub-run's verdict in step 1, and update RB-102's chain cell"
    )


def test_with_no_file_the_verdict_says_so_and_states_no_difference(brazos, dana):
    """*"Balances off by $7,661.92"* over a run where nobody uploaded anything.

    ⚠ **THAT IS WHAT THE FIRST DRAFT SAID ON THE SEEDED UTILITY**, and it is the
    worst sentence this runbook could produce: it reads as a reconciliation that
    found a discrepancy. With no file there is nothing to differ from, so the
    difference is an ABSENCE (`None`) and the banner names the missing file.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
        blocks = {block.block: block.payload for block in rb2.report(_view(result))}
    balances = result.set_results[rb2.STEP_BALANCES]["checked"]
    assert balances["total_off_by"] is None
    assert balances["accounts_disagreeing"] == 0
    assert blocks["verdict"]["detail"] == "No legacy file"
    assert blocks["kpis"]["tiles"][0]["value"]["amount"] == "—"


def test_the_total_tolerance_is_a_percentage_of_the_LEGACY_side(brazos, dana):
    """Taking it of our own side would move the yardstick with the defect.

    Worked: a legacy total of 1,000.0000 against a loaded 1,000.5000 is 0.05% of
    THEIRS and 0.049975% of OURS. At a 0.05% limit the first is exactly at the
    line and the second is inside it — so the direction of the division decides
    the verdict, which is why it is asserted rather than assumed.
    """
    theirs = [("AC-1", "BL-1", Decimal("1000.0000"))]
    ours = Decimal("1000.5000")
    parsed = rb2.parse_trial_balance(trial_balance(theirs))
    of_theirs = (ours - parsed.total) / parsed.total * Decimal("100")
    of_ours = (ours - parsed.total) / ours * Decimal("100")
    assert of_theirs.quantize(Decimal("0.0001")) == Decimal("0.0500")
    assert of_ours.quantize(Decimal("0.0001")) == Decimal("0.0500")
    assert of_ours < of_theirs  # the same figure, and the smaller one is ours


def test_every_finding_names_a_fix_route_and_states_its_rule_in_words(brazos, dana):
    """`BR-RBS-011` and `BR-RBS-010`, and **B14 rule 32** on the rule sentence.

    A finding a clerk cannot act on is a finding we should not have shown them,
    and a rule ID in clerk-facing copy is rule 32's own breach. Both are checked
    over every finding a real run produces rather than over a hand-made one.
    """
    text, _ = a_pair()
    with tenant_ctx(brazos):
        result = _run(brazos, trial=text)
    findings = []
    for key in rb2.STEP_LABELS:
        findings.extend((result.set_results.get(key) or {}).get("findings") or [])
    assert findings
    for row in findings:
        assert row["fix_route"].strip()
        assert not row["fix_route"].startswith("/")  # tenant-relative (DEF-RBS-4329)
        assert row["decided_by_rule"].strip()
        for token in ("BR-", "US-", "DEF-", "OQ-", "TC-"):
            assert token not in row["decided_by_rule"]
            assert token not in row["reason"]


def test_the_report_is_six_of_the_twelve_blocks_and_no_thirteenth(brazos, dana):
    """`BR-RBS-021`. A thirteenth needs three runbooks that cannot be drawn."""
    text, _ = a_pair()
    with tenant_ctx(brazos):
        result = _run(brazos, trial=text)
        blocks = rb2.report(_view(result))
    names = [block.block for block in blocks]
    assert names == ["verdict", "kpis", "chain", "reconciled", "records", "downloads"]
    assert all(name in BLOCK_TYPES for name in names)


def test_the_frozen_report_carries_no_python_object(brazos, dana):
    """`BR-RBS-020` freezes the report into `jsonb`. A dataclass there is a crash.

    ⚠ **THE PARSED FILE IS CARRIED ON `set_results` SO THE STEPS SHARE ONE
    PARSE**, and `_serialisable` strips it. Without that the run is marked
    FAILED at close on a correct comparison, and the message would name a JSON
    encoder rather than the runbook.
    """
    import json

    text, _ = a_pair()
    with tenant_ctx(brazos):
        result = _run(brazos, trial=text)
        blocks = [block.as_dict() for block in rb2.report(_view(result))]
    json.dumps(blocks)  # it raises TypeError if a LegacyFile survived


def _view(result):
    """The read-only view `report()` is handed, rebuilt from a `RunResult`."""
    from apps.runbooks.engine.executor import _ReportView

    return _ReportView(
        definition=rb2.RUNBOOK,
        subjects=result.subjects,
        guarded=result.guarded,
        records=result.records,
        counts=result.counts,
        set_results=result.set_results,
    )


# ═══════════════════════════════════════════════════════════════════════════
# J1 · J3 — THE PLAN, ITS ITEMS, AND THE RUN THAT BECOMES EVIDENCE
# ═══════════════════════════════════════════════════════════════════════════


def _plan(actor_id=None):
    return cutover.create_plan(
        name="Silver Creek go-live",
        items=[
            {"seq": 1, "title": "Balances tie", "runbook_key": "cutover_readiness"},
            {"seq": 2, "title": "Customer signs bill layout", "owner": "Bynry"},
            {"seq": 3, "title": "Legacy set read-only", "owner": "Utility IT"},
        ],
        actor_id=actor_id,
    )


def test_a_null_runbook_key_is_a_human_task_the_engine_never_performs(brazos, dana):
    """`03-field-map.md` D-7. *Customer signs bill layout* is a person's act.

    The word a clerk reads is derived in ONE place — `item_dict` — rather than
    on each screen, because two screens deriving *is this a human task* from a
    null is two places the rule can drift.
    """
    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
    by_seq = {item["seq"]: item for item in plan["items"]}
    assert by_seq[1]["runbook_key"] == "cutover_readiness"
    assert by_seq[1]["human_task"] is False
    assert by_seq[2]["runbook_key"] is None
    assert by_seq[2]["human_task"] is True


def test_a_human_task_REFUSES_evidence_by_name(brazos, dana):
    """A run cannot sign anything, and the refusal says so rather than 404ing.

    This is the guard that stops a green tick and a real run id landing on a
    task nobody performed — evidence that is worse than none, because it looks
    checkable.
    """
    from core import errors

    text, _ = a_pair()
    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        run = _finished_run(brazos, trial=text)
        with pytest.raises(errors.BizError) as caught:
            cutover.attach_evidence(
                plan_id=plan["id"], seq=2, run_id=run.id, actor_id=dana.id
            )
    assert caught.value.message_key == "runbooks.cutover.human_task_takes_no_evidence"


def test_evidence_from_a_no_go_run_does_NOT_turn_the_item_green(brazos, dana):
    """`US-RBS-008` §7 — a ZERO-VARIANCE re-run turns it green, and only that.

    The variance is read from the FROZEN report, so the plan and the run cannot
    state different reasons for the same tick, and the sentence stored on the
    item carries no run id and no rule number (B14 rules 31 and 32).
    """
    text, _ = a_pair()
    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        run = _finished_run(brazos, trial=text)
        item = cutover.attach_evidence(
            plan_id=plan["id"], seq=1, run_id=run.id, actor_id=dana.id
        )
    assert item["status"] == cutover.ITEM_OPEN
    assert item["evidence_ref"].startswith("No-go")
    for token in ("BR-", "DEF-", "OQ-"):
        assert token not in item["evidence_ref"]
    assert str(run.id) not in item["evidence_ref"]


def test_a_run_of_a_DIFFERENT_runbook_is_refused(brazos, dana):
    """Attaching a cash-application run to *balances tie* would be false evidence."""
    from core import errors

    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        other = runbook_models.Runbook.objects.create(
            tenant_id=brazos.id, key="cash_application", name="Cash application", kind="check"
        )
        run = runbook_models.RunbookRun.objects.create(
            tenant_id=brazos.id,
            runbook=other,
            version=1,
            status=runbook_models.RUN_STATUS_DONE,
            report=[{"block": "verdict", "payload": {"word": "Go", "tone": "success", "count": ""}}],
        )
        with pytest.raises(errors.BizError) as caught:
            cutover.attach_evidence(
                plan_id=plan["id"], seq=1, run_id=run.id, actor_id=dana.id
            )
    assert caught.value.message_key == "runbooks.cutover.run_is_a_different_runbook"


def test_an_unfinished_run_is_refused(brazos, dana):
    """A `running` or `failed` run has no verdict, and its report is not frozen."""
    from core import errors

    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        runbook = runbook_models.Runbook.objects.create(
            tenant_id=brazos.id,
            key="cutover_readiness",
            name="Cutover reconciliation",
            kind="check",
        )
        run = runbook_models.RunbookRun.objects.create(
            tenant_id=brazos.id,
            runbook=runbook,
            version=1,
            status=runbook_models.RUN_STATUS_RUNNING,
        )
        with pytest.raises(errors.BizError) as caught:
            cutover.attach_evidence(
                plan_id=plan["id"], seq=1, run_id=run.id, actor_id=dana.id
            )
    assert caught.value.message_key == "runbooks.cutover.run_not_finished"


def test_a_clear_run_turns_the_item_green_on_its_own(brazos, dana):
    """`US-RBS-008` §7's own sentence, and `clear` is read from the TONE.

    The words are each runbook's own — *Go*, *Balanced*, *Ready to import* — and
    a fifth runbook will invent a sixth. `success` is the closed vocabulary.
    """
    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        runbook = runbook_models.Runbook.objects.create(
            tenant_id=brazos.id,
            key="cutover_readiness",
            name="Cutover reconciliation",
            kind="check",
        )
        run = runbook_models.RunbookRun.objects.create(
            tenant_id=brazos.id,
            runbook=runbook,
            version=1,
            status=runbook_models.RUN_STATUS_DONE,
            report=[
                {
                    "block": "verdict",
                    "payload": {
                        "word": "Go",
                        "tone": "success",
                        "count": "9 of 9 steps clear",
                        "detail": "",
                    },
                }
            ],
        )
        item = cutover.attach_evidence(
            plan_id=plan["id"], seq=1, run_id=run.id, actor_id=dana.id
        )
    assert item["status"] == cutover.ITEM_DONE
    assert item["evidence_ref"] == "Go · 9 of 9 steps clear"


def test_naming_a_plan_by_NAME_does_not_crash_on_a_uuid_column(brazos, dana):
    """`filter(pk="Silver Creek go-live")` RAISES on PostgreSQL and not on SQLite.

    ⚠ **HARD-WON LAW 14's SECOND COSTUME.** The version without `_looks_like_id`
    passes this whole suite green — SQLite quietly returns an empty queryset —
    and 500s the first time an implementer names their plan on a real database.
    So the guard is asserted directly, on the helper, rather than through a call
    the suite cannot make fail.
    """
    assert cutover._looks_like_id("00000000-0000-0000-0000-000000000000") is True
    assert cutover._looks_like_id("Silver Creek go-live") is False
    with tenant_ctx(brazos):
        _plan(actor_id=dana.id)
        found = cutover.plan_for_run("Silver Creek go-live")
    assert found is not None
    assert found["name"] == "Silver Creek go-live"


def test_step_nine_counts_open_items_and_names_the_plan(brazos, dana):
    """*2 plan items open* — `RBS-006-R2` region 11, from the plan's own rows."""
    with tenant_ctx(brazos):
        plan = _plan(actor_id=dana.id)
        cutover.update_item(
            plan_id=plan["id"], seq=1, status=cutover.ITEM_DONE, actor_id=dana.id
        )
        result = _run(brazos, plan="Silver Creek go-live")
    checked = result.set_results[rb2.STEP_PLAN_ITEMS]["checked"]
    assert checked["plan"] == "Silver Creek go-live"
    assert checked["open"] == 2
    assert [row["human_task"] for row in checked["open_rows"]] == [True, True]


def _finished_run(tenant, *, trial=None):
    """A real run of runbook 2, closed, with its report frozen."""
    from apps.runbooks import services

    runbook = (
        runbook_models.Runbook.objects.filter(tenant_id=tenant.id, key="cutover_readiness").first()
        or services.add_template(tenant.id, "cutover_readiness")
    )
    run, _ = services.run_to_completion(
        runbook, rb2.RUNBOOK, params={"trial_balance": trial}
    )
    return run


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-008 (EP-RBS-03 §3 TC-RBS-008.1 and §4 test data, quoted above)
# generated: 2026-09-07 by the CR-075 wave J build lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
