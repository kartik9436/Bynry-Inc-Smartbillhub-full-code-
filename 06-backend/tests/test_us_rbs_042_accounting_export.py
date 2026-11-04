# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-042 (EP-RBS-01) — runbook 36, *Month-end journal file*.
# Rules:    PO ruling 2026-09-06 (the six columns, verbatim) · the four
#           decisions of the same day's decision log — two decimals · one
#           currency · never invent an account code · an unbalanced file is
#           REFUSED · BR-RBS-002 (a Check holds no ports) · BR-RBS-011 (a
#           failure names its fix route) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-042 (*all* is the
#           word, resolved at run start) · CLAUDE.md hard rule 2 · hard rule 5
# Tests:    this file
# Impacts:  apps/runbooks/definitions/accounting_export.py
# ───────────────────────────────────────────────────────
"""Runbook 36 on real books — the file, and what could not go in it.

⚠ **WHAT THIS FILE CAN AND CANNOT PROVE, SAID FIRST.** It runs on the default
suite, which is in-memory SQLite. Two things are therefore NOT proved here and
are not pretended to be: **tenant isolation, which does not exist on SQLite at
all**, and the per-record SAVEPOINT that step 2 runs inside — SQLite has no
aborted-transaction state, so a savepoint here proves nothing about PostgreSQL
(hard-won law 14). Both are in `tests/test_us_rbs_042_pg.py`, which SKIPS unless
it is pointed at a real PostgreSQL, and the skip says so out loud rather than
counting as a pass. `G5` once ran the isolation suite on SQLite and called 192
skips a pass; the answer to that is to print the number, which both files do.

⚠ **EVERY MONEY ASSERTION IS A FIGURE, NEVER A SHAPE.** `assert total ==
"598.69"` and never `assert total`. A file that footed to the wrong number would
pass *"there is a total"* and would be exactly the defect this runbook exists to
prevent — a bookkeeper importing a clean-looking journal that is wrong.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import models as ledger_models
from apps.ledger import posting
from apps.runbooks import models as runbook_models
from apps.runbooks.contract import BLOCK_TYPES, MODE_PER_RECORD, MODE_SET
from apps.runbooks.definitions import accounting_export as rb36
from apps.runbooks.engine import executor
from apps.runbooks.registry import registry

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_FOOTING,
    a_request,
    gl,
    line,
    make_accounts,
    post_le1_month,
)
# ⚠ **THE STAR IMPORT IS LOAD-BEARING AND IS NOT LAZINESS.** `test_us_met_helpers`
# declares an `autouse` fixture, `sqlite_guc`, that sends `set_config('app.tenant_id',
# …)` to a recording fake on SQLite — which has no such function — while leaving the
# Python-side ContextVar mirror real. Importing only the names this file uses leaves
# that fixture unregistered and every tenant context dies with `no such function:
# set_config`, which reads as a broken fixture rather than a missing import.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — incl. the autouse sqlite_guc
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


# ── the fixture: LE-1's July, which foots to 598.69 ───────────────────────


def _july(tenant, actor):
    """LE-1's month, posted through the posting service — never inserted.

    The figures are the ledger's own signed fixture (`LE-1`, ❄️ B5 line 74), so
    every assertion below is against a number finance already signed rather than
    against one this test made up. **`598.69` is LE-1's own footing.**
    """
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def _run(tenant, *, period=rb36.ALL):
    return executor.execute(rb36.RUNBOOK, tenant_id=tenant.id, params={"period": period})


def _rows(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def _file_state(result) -> dict:
    return result.set_results[rb36.STEP_FILE]["checked"]


def _blocked(result) -> list[dict]:
    rows: list[dict] = []
    for key in rb36.STEP_LABELS:
        rows.extend((result.set_results.get(key) or {}).get("blocked") or [])
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# THE CONTRACT — what the module declares, refused at construction if wrong
# ═══════════════════════════════════════════════════════════════════════════


def test_it_is_a_check_and_holds_no_ports_at_all():
    """`BR-RBS-002`. Producing a download is not a write to a business record.

    Asserted as **`ports == ()`**, not as *"it does not write"*: the capability
    is ABSENT rather than unused, which is the whole sentence that lets two
    people press Run on a thousand accounts.
    """
    assert rb36.RUNBOOK.kind == runbook_models.KIND_CHECK
    assert rb36.RUNBOOK.ports == ()
    assert rb36.RUNBOOK.writes_nothing() is True
    assert rb36.RUNBOOK.port_declarations() == ()


def test_it_is_registered_and_declares_the_period_as_its_unit():
    """One line in `DEFINITION_MODULES` is the whole cost of a runbook."""
    assert "accounting_export" in registry.keys()
    assert rb36.RUNBOOK.subject_type == "period"
    assert rb36.RUNBOOK.unit_of_work == "accounting month"
    assert rb36.RUNBOOK.category == "finance"


def test_the_steps_declare_their_modes_and_the_figures_step_is_per_record():
    """`BR-RBS-023`. The month is the unit, so step 2 runs once per month."""
    modes = {step.key: step.mode for step in rb36.RUNBOOK.steps}
    assert modes[rb36.STEP_FIGURES] == MODE_PER_RECORD
    assert modes[rb36.STEP_FILE] == MODE_SET
    assert set(modes.values()) == {MODE_PER_RECORD, MODE_SET}


def test_every_report_block_is_one_of_the_twelve(brazos, dana):
    """`BR-RBS-021`. A thirteenth needs three runbooks that cannot be drawn."""
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos)
    names = [block["block"] for block in result.report]
    assert names == ["verdict", "kpis", "records", "downloads"]
    assert set(names) <= set(BLOCK_TYPES)


def test_a_blocked_row_cannot_be_built_without_a_fix_route():
    """`BR-RBS-011` — a failure with no route is a defect in the runbook.

    Proved by construction, because a fixture only ever walks the branches
    somebody thought of.
    """
    with pytest.raises(ValueError, match="names no fix route"):
        rb36.Blocked(
            key="x",
            reason="Something is wrong.",
            affects="1 account",
            weight=rb36.BLOCKER,
            fix_route="",
            fix_label="Fix it",
            decided_by_rule="A rule.",
        )


def test_no_blocked_row_in_this_module_is_built_without_a_route():
    """The STATIC half — every `Blocked(...)` in the module, reached or not.

    ⚠ **THIS IS THE ONE THAT MATTERS.** The runtime half above can only ever see
    the branches a test happens to walk, and the branch that matters is the one
    nobody has hit yet. `TC-RBS-14`'s shape, applied to this module.
    """
    import ast
    import pathlib

    source = pathlib.Path(rb36.__file__).read_text()
    built = 0
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "Blocked"):
            continue
        built += 1
        keywords = {kw.arg for kw in node.keywords}
        assert "fix_route" in keywords, f"Blocked(...) at line {node.lineno} names no fix_route"
        assert "fix_label" in keywords, f"Blocked(...) at line {node.lineno} has no button words"
    # The NUMBER, so that a step whose refusal was deleted goes red here rather
    # than passing over an empty walk (hard-won law 7 — a check that cannot fail).
    # Five: no months · currency not set · does not balance · accounts with no
    # code · unmapped designations.
    assert built == 5, f"expected 5 Blocked(...) sites in the module, found {built}"


# ═══════════════════════════════════════════════════════════════════════════
# THE FILE — the six columns, two decimals, and a footing that balances
# ═══════════════════════════════════════════════════════════════════════════


def test_the_header_row_is_the_pos_six_columns_in_the_pos_order():
    """PO ruling 2026-09-06, verbatim: *date, account code, description, debit,
    credit, reference*. Asserted as a LIST, so a reordering is red."""
    assert rb36.JOURNAL_COLUMNS == (
        "date",
        "account code",
        "description",
        "debit",
        "credit",
        "reference",
    )
    header = _rows(rb36.journal_csv([]))[0]
    assert header == ["date", "account code", "description", "debit", "credit", "reference"]


def test_money_is_written_at_two_decimals_and_is_never_a_float():
    """Hard rule 2 — stored to four, DISPLAYED at two, and a file is a display
    surface. The stored value here carries four; the cell carries two."""
    row = rb36.JournalRow(
        when=date(2026, 7, 31),
        account_code="4100",
        description="Electric usage",
        debit=Decimal("0"),
        credit=Decimal("226.9012"),
        reference="2026-07",
    )
    assert row.as_cells() == [
        "2026-07-31",
        "4100",
        "Electric usage",
        "0.00",
        "226.90",
        "2026-07",
    ]
    # A zero is written as 0.00 and never as a blank: blank means *no value on
    # this side* to an importer, and the two columns would stop footing.
    assert row.as_cells()[3] == "0.00"


def test_july_exports_as_a_balanced_file_that_foots_to_le1s_own_number(brazos, dana):
    """The whole point, on signed books — and **the month is the slice**.

    ⚠ **LE-1's `598.69` IS THE WHOLE FIXTURE AND NOT JULY.** Its opening entry
    is dated at the `CUTOVER`, 2026-06-30, so it lands in JUNE. July alone foots
    to `553.69` — LE-1's `598.69` less the `45.00` opening AR — and *all*
    months foot to `598.69` exactly. **Both are asserted**, because a per-month
    export that quietly swept the cutover into July would pass an assertion
    against the total and be wrong about every month.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
        every = _run(brazos)

    state = _file_state(result)
    rows = _rows(state["csv"])
    body = rows[1:]
    assert state["lines"] == len(body) > 0
    debits = sum(Decimal(row[3]) for row in body)
    credits = sum(Decimal(row[4]) for row in body)
    assert debits == credits == Decimal("553.69")
    assert state["debits"] == state["credits"] == "553.69"

    # And the whole fixture, June's cutover entry included, is LE-1's own number.
    assert [s.label for s in every.subjects] == ["2026-06", "2026-07"]
    assert Decimal(_file_state(every)["debits"]) == LE1_FOOTING
    assert _file_state(every)["credits"] == "598.69"
    # Every cell of every money column carries exactly two decimals.
    for row in body:
        assert row[3].split(".")[1] == row[3][-2:] and len(row[3].split(".")[1]) == 2
        assert len(row[4].split(".")[1]) == 2
    # The date and the reference are the month's, on every row.
    assert {row[0] for row in body} == {"2026-07-31"}
    assert {row[5] for row in body} == {"2026-07"}
    assert state["file_name"] == "journal-2026-07-USD.csv"


def test_no_account_code_is_ever_invented(brazos, dana):
    """Decision 3. Every code in the file is a code the chart actually holds.

    ⚠ **WHAT THIS CANNOT CATCH, SAID RATHER THAN LEFT TO BE ASSUMED.** It walks
    a fixture whose accounts all HAVE codes, so a substitution like
    `row["code"] or "9999"` never fires under it and this case stays green over
    it — measured, by making that edit and running this test. **The guard that
    actually catches an invented code is the blank-code BLOCKER below**: with no
    code there is no file at all, so there is nothing to invent one into.
    Downgrading that finding to a warning turns this pair red, which is the
    proof that matters.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
        chart_codes = set(
            ledger_models.LedgerAccount.objects.filter(
                tenant=brazos, deleted_at__isnull=True
            ).values_list("code", flat=True)
        )
    body = _rows(_file_state(result)["csv"])[1:]
    assert body, "the fixture produced no rows, so this check cannot fail"
    for row in body:
        assert row[1] in chart_codes, f"{row[1]!r} is not a code this tenant's chart holds"


# ═══════════════════════════════════════════════════════════════════════════
# THE REFUSALS — each shown to fire, by name, on real books
# ═══════════════════════════════════════════════════════════════════════════


def test_an_unbalanced_month_refuses_the_whole_file_and_names_the_difference(brazos, dana):
    """Decision 4 and hard rule 5, and this is the assertion the runbook exists
    for.

    Drift is only reachable through a posting-service BYPASS — that is what
    `BR-LED-007` says and what `ledger/0004`'s sole-writer trigger makes hard —
    so it is simulated the only way a test can: a raw line insert with the write
    window open, which is `test_us_led_016_tc6`'s own method.

    **The whole file is refused, not the bad month**, because a file with the
    unbalanced month quietly dropped would import cleanly and be wrong.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        entry = ledger_models.JournalEntry.objects.filter(
            tenant=brazos,
            status=ledger_models.JE_POSTED,
            entry_date__gte=JULY_START,
            entry_date__lte=JULY_END,
        ).first()
        posting._set_write_window(posting.WRITE_WINDOW_OPEN)
        try:
            ledger_models.JournalLine.objects.create(
                tenant=brazos,
                journal_entry=entry,
                ledger_account=gl(brazos, "4100", "revenue"),
                side=ledger_models.SIDE_CREDIT,
                amount=Decimal("14.25"),
                source_type="bypass",
                source_id=entry.pk,
            )
        finally:
            posting._set_write_window(posting.WRITE_WINDOW_SHUT)
        result = _run(brazos, period="2026-07")

    state = _file_state(result)
    assert state["refused"] is True
    assert state["csv"] == ""
    assert state["lines"] == 0

    refusal = next(row for row in _blocked(result) if row["key"] == "does_not_balance")
    assert refusal["reason"] == "The file does not balance."
    # B14 rule 33 — a refusal is at most six words per sentence.
    assert len(refusal["reason"].split()) <= 6
    # The FIGURE, in the column beside it, exactly as the ruling asks.
    assert "14.25" in refusal["affects"]
    assert "2026-07" in refusal["affects"]
    assert refusal["weight"] == rb36.BLOCKER
    assert refusal["fix_route"]

    verdict = next(block for block in result.report if block["block"] == "verdict")
    assert verdict["payload"]["word"] == "No file"
    assert verdict["payload"]["tone"] == "danger"
    downloads = next(block for block in result.report if block["block"] == "downloads")
    assert downloads["payload"]["files"] == [], "a refused file must offer no download"


def test_an_account_with_no_code_is_reported_and_never_guessed(brazos, dana):
    """Decision 3's account-side half — the code column has nothing to put in it.

    ⚠ **`code` IS `NOT NULL`, SO THIS IS THE EMPTY STRING** — which is exactly
    why a column constraint cannot catch it and a read has to.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        account = gl(brazos, "4100", "revenue")
        ledger_models.LedgerAccount.objects.filter(pk=account.pk).update(code="")
        result = _run(brazos, period="2026-07")

    row = next(row for row in _blocked(result) if row["key"] == "accounts_without_a_code")
    assert row["weight"] == rb36.BLOCKER
    assert len(row["reason"].split()) <= 6
    assert row["fix_route"] and row["fix_label"]
    state = _file_state(result)
    assert state["refused"] is True and state["csv"] == ""


def test_a_place_in_the_books_with_no_account_is_reported_with_its_fix(brazos, dana):
    """The gap the seeded utility genuinely has: money of that kind cannot post,
    so it never reaches the journal and cannot reach the file either.

    It is a **WARNING and not a blocker**: what IS in the books is still correct
    and still worth exporting, and a bookkeeper told *no file* over a mapping
    gap that affects nothing this month goes back to typing.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, designation="write_off"
        ).update(designation=None)
        result = _run(brazos, period="2026-07")

    row = next(row for row in _blocked(result) if row["key"] == "unmapped_designations")
    assert row["weight"] == rb36.WARNING
    assert "Write off" in row["affects"], "a designation reaches a clerk in words, not as a code"
    assert "_" not in row["affects"], "B14 rule 32 — no internal code in clerk-facing copy"
    # A warning still carries its file.
    assert _file_state(result)["refused"] is False
    assert _file_state(result)["lines"] > 0


def test_a_tenant_with_nothing_posted_says_so_rather_than_exporting_zeroes(brazos):
    """`BR-RBS-042` clause 2 — **an empty domain says so.**

    The dangerous shape is a header-only file under a green verdict, which reads
    as *"nothing happened in July"*. This says *Nothing is posted yet.* instead.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
    assert result.subjects == ()
    row = next(row for row in _blocked(result) if row["key"] == "no_months")
    assert row["reason"] == "Nothing is posted yet."
    assert _file_state(result)["lines"] == 0
    assert _file_state(result)["csv"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# THE INPUT — *all* is the word, resolved at run start (BR-RBS-042 clause 1)
# ═══════════════════════════════════════════════════════════════════════════


def test_the_period_parameter_stores_the_word_all_and_never_a_list():
    """Clause 1. The definition document is what a version row freezes, so if
    the word were expanded at configure time it would be frozen expanded."""
    parameter = next(p for p in rb36.RUNBOOK.parameters if p.name == "period")
    assert parameter.default == "all"
    stored = rb36.RUNBOOK.as_definition_document()
    assert stored["parameters"][0]["default"] == "all"


def test_a_month_posted_after_the_first_run_appears_in_the_next_one(brazos, dana):
    """Clause 1's own worked example, with *months* for *services*.

    A utility that saved *all* in July and then posts into August must get
    **two** months on its next run, with nothing to reconfigure and nothing on
    any screen to notice. This is the test `BR-RBS-042` records as owed,
    discharged for this runbook.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        first = _run(brazos)
        # June is LE-1's cutover entry; July is the month itself.
        assert [s.label for s in first.subjects] == ["2026-06", "2026-07"]

        # One more posting, in August, through the posting SERVICE — hard rule
        # 5, and the same door `post_le1_month` uses. An inserted row would
        # prove the domain widens over a write this product does not permit.
        posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), ledger_models.SIDE_DEBIT, "100.00"),
                    line(gl(brazos, "4100", "revenue"), ledger_models.SIDE_CREDIT, "100.00"),
                ],
                key="invoice|AUG-0001|issue",
                entry_date=date(2026, 8, 31),
            )
        )
        second = _run(brazos)

    assert [s.label for s in second.subjects] == ["2026-06", "2026-07", "2026-08"]
    assert _file_state(second)["file_name"] == "journal-2026-06-to-2026-08-USD.csv"


def test_a_run_with_no_parameters_at_all_falls_back_to_every_month(brazos, dana):
    """The DEFAULT path, which every other test in this file skips past.

    ⚠ **THIS TEST EXISTS BECAUSE BREAKING THE GUARD FOUND THE HOLE** (hard-won
    law 7's *ask what would make this check pass wrongly*). Every case above
    passes `period` explicitly, so changing the parameter's DEFAULT from `all`
    to a single month left the whole suite green — the tests were proving the
    argument and never the default, and a runbook a clerk starts with nothing
    filled in takes exactly the path nothing covered.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = executor.execute(rb36.RUNBOOK, tenant_id=brazos.id)
    assert [s.label for s in result.subjects] == ["2026-06", "2026-07"]
    assert _file_state(result)["lines"] > 0


def test_one_named_month_narrows_the_run_without_changing_the_process(brazos, dana):
    """`BR-RBS-042`: *"the process runs identically at every utility and the
    OUTPUT is filtered by what was chosen."* Six steps, either way."""
    with tenant_ctx(brazos):
        _july(brazos, dana)
        every = _run(brazos)
        one = _run(brazos, period="2026-07")
    assert set(every.step_runs) == set(one.step_runs)
    assert [s.label for s in one.subjects] == ["2026-07"]


# ═══════════════════════════════════════════════════════════════════════════
# THE REPORT — the numbers a clerk reads, and the download they press
# ═══════════════════════════════════════════════════════════════════════════


def test_the_kpi_strip_carries_the_file_total_as_money_with_its_currency(brazos, dana):
    """Hard rule 2 — the currency rides WITH the amount and is `CHAR(3)`."""
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
    tiles = {
        tile["id"]: tile
        for block in result.report
        if block["block"] == "kpis"
        for tile in block["payload"]["tiles"]
    }
    assert tiles["total"]["value"] == {"kind": "money", "amount": "553.69", "currency": "USD"}
    assert len(tiles["total"]["value"]["currency"]) == 3
    assert tiles["lines"]["value"]["text"] == str(_file_state(result)["lines"])


def test_the_open_month_is_a_note_and_the_file_is_still_offered(brazos, dana):
    """The judgment recorded in the module docstring, asserted so it cannot be
    quietly reversed: an OPEN month WARNS and still carries its file."""
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
    verdict = next(block for block in result.report if block["block"] == "verdict")
    assert verdict["payload"]["word"] == "Ready, with notes"
    # ⚠ SINGULAR ON ONE MONTH. The fixture's July is one open month, and an
    # earlier draft of the runbook said *"1 months open"* on it — which only a
    # real run surfaces, because the plural reads fine in every example
    # somebody writes by hand.
    assert verdict["payload"]["count"] == "1 to fix · 1 month open."
    downloads = next(block for block in result.report if block["block"] == "downloads")
    assert downloads["payload"]["files"] == [
        {"id": "journal", "label": "Journal file", "format": "csv"}
    ]


def test_no_row_of_the_report_carries_a_database_id(brazos, dana):
    """B14 rule 31 — *no database id is ever the visible value of a field*."""
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
        ids = {
            str(pk)
            for pk in ledger_models.LedgerAccount.objects.filter(tenant=brazos).values_list(
                "id", flat=True
            )
        }
    blob = repr(result.report) + _file_state(result)["csv"]
    leaked = [value for value in ids if value in blob]
    assert leaked == [], f"a database id reached the report or the file: {leaked}"


def test_every_clerk_facing_sentence_is_six_words_or_fewer(brazos, dana):
    """B14 rule 33 — a fact, an instruction and a refusal each cap at six words.

    Applied to the sentences this runbook COMPOSES, which no gate reads:
    `G33` measures the locale catalogue and every string here is server-side.

    ⚠ **THE CAP IS PER CLAUSE, WHICH IS RULE 33's OWN READING** — *"two
    sentences of six beat one sentence of twelve, because the second sentence is
    where what to do next lives"*. So `·` and `.` are separators here and not
    words; counting *"1 to fix · 3 months open."* as seven would fail a line
    that is two clauses of three.
    """
    with tenant_ctx(brazos):
        _july(brazos, dana)
        result = _run(brazos, period="2026-07")
    sentences: list[str] = [row["reason"] for row in _blocked(result)]
    for block in result.report:
        if block["block"] == "verdict":
            sentences.append(block["payload"]["count"])
        if block["block"] == "records":
            sentences.append(block["payload"]["empty"]["title"])
            sentences.append(block["payload"]["empty"]["helper"])
    for record in result.records:
        sentences.append(record.reason)
    import re

    over: list[str] = []
    for sentence in sentences:
        for clause in re.split(r"[·.]", sentence or ""):
            if len(clause.split()) > 6:
                over.append(sentence)
    assert over == [], f"over the six-word cap: {over}"
    assert sentences, "no sentence was collected, so this check cannot fail"
