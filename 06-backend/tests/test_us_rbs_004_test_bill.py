# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-004 (EP-RBS-02) — CR-075 wave F task F3. Runbook 23, the
#           Test bill. Screens: RBS-004-R23 · RBS-006-R23.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read) · BR-RBS-011 (a refusal names its fix route) · BR-RBS-021
#           (twelve blocks, closed) · B14 rule 31 (no database id on screen) ·
#           rule 32 (no rule id or internal code in clerk copy) · rule 33 (a
#           refusal caps at five or six words) · CLAUDE.md hard rule 2 (money 4
#           stored / 2 displayed) · hard rule 3 (a quantity carries its unit)
# Tests:    this file · tests/test_us_rbs_004_pg.py (TC-RBS-004.1, .3 and
#           TC-RBS-7 — on real PostgreSQL, where they mean something)
# Impacts:  apps/runbooks/definitions/test_bill.py
# ───────────────────────────────────────────────────────
"""Runbook 23 on the default suite — everything SQLite CAN answer.

⚠ **WHAT IS DELIBERATELY NOT HERE, WITH ITS NUMBER.** Three of `US-RBS-004`'s
five test cases cannot be proved on this vendor and live in
`tests/test_us_rbs_004_pg.py`, each `requires_postgres` and SKIPPED rather than
passing vacuously (`G5` once called 192 skips a pass):

  * **`TC-RBS-004.3`, the one that matters** — the test bill and a real bill run
    produce an IDENTICAL line set and identical amounts to four decimals. It
    needs a run that actually writes a draft, so it needs a database where
    `assemble_document` behaves.
  * **`TC-RBS-004.1`'s second half** — `billing`'s number series is untouched.
  * **`TC-RBS-7`** — a cross-tenant account lookup returns nothing, with RLS
    `FORCE` on. **SQLite has no row-level security at all**, so a case here
    would prove nothing while reporting green.

What IS proved here is everything about the DECLARATION and the REPORT: the
capability that is absent, the sentences a clerk reads, and the shapes the
renderer is handed.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_SET,
    Block,
    RunbookContractError,
    RunbookDefinition,
    Step,
    validate_report,
)
from apps.runbooks.definitions import test_bill as rb23
from apps.runbooks.engine import executor

from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


#: What a clerk must never be shown. B14 rule 31 (no database id is ever the
#: visible value of a field) and rule 32 (no rule id or internal code in
#: clerk-facing copy). The same three patterns the browser walkthrough uses, so
#: a string that passes here passes there.
FORBIDDEN_IN_CLERK_COPY = (
    re.compile(r"\bBR-[A-Z]{3}-\d{3,5}\b"),
    re.compile(r"\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
)


def _params(account, *, compare_with="last_issued_bill"):
    return {
        "account": str(account.id),
        "period": {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()},
        "compare_with": compare_with,
        "show": "every_line_explained",
    }


def _billable(brazos, dana, *, account_no="A-23001", consumption="412.000000"):
    cycle = a_cycle(brazos, code="23-A")
    plan = a_priced_plan(brazos, name="Runbook 23 Residential")
    unit = a_billed_unit(
        dana, brazos, cycle, plan, asset_no="M-23001", label="23A", consumption=consumption
    )
    return an_account(brazos, unit["id"], account_no)


def _clerk_strings(blocks) -> list[str]:
    """Every string a report puts in front of a person.

    ⚠ **`meta` IS EXCLUDED AND THAT IS THE POINT, NOT A LOOPHOLE.** A renderer
    walks `columns`, so nothing in `ReportRow.meta` can reach a screen; it is
    where a row carries what the findings reader needs and the clerk does not.
    Sweeping it in here would make this check refuse a design the block types
    document in their own comments.
    """
    found: list[str] = []

    def walk(node, *, inside_meta=False):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, inside_meta=inside_meta or key == "meta")
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, inside_meta=inside_meta)
        elif isinstance(node, str) and not inside_meta:
            found.append(node)

    walk([b.as_dict() if isinstance(b, Block) else b for b in blocks])
    return found


# ── the capability that is ABSENT · BR-RBS-002 ────────────────────────────


def test_tc_rbs_004_1a__runbook_23_holds_no_port_at_all():
    """A Check is CONSTRUCTED without action ports — the capability is gone.

    `writes_nothing()` is what `RBS-002`/`RBS-004` render *Writes: Nothing ·
    Sends: Nothing* from, and it is derived from `ports[]` rather than from a
    label that could disagree with the constructor.
    """
    assert rb23.RUNBOOK.kind == models.KIND_CHECK
    assert rb23.RUNBOOK.ports == ()
    assert rb23.RUNBOOK.writes_nothing() is True
    assert rb23.RUNBOOK.port_declarations() == ()


def test_tc_rbs_004_1b__giving_runbook_23_a_writer_fails_at_construction():
    """The RED half. `BR-RBS-002` refuses at CONSTRUCTION, not at write time.

    Proved by rebuilding this runbook's own declaration with one port bound —
    the change a lane would actually make — and watching Python refuse the
    object. A version of this rule that refused at write time would mean a Check
    with a writer exists in memory on a live schedule.
    """
    with pytest.raises(RunbookContractError) as refused:
        RunbookDefinition(
            key="test_bill_with_a_writer",
            name="Test bill",
            kind=models.KIND_CHECK,
            category="billing",
            subject_type="account",
            unit_of_work="account-period",
            resolve=rb23.resolve,
            report=rb23.report,
            steps=rb23.RUNBOOK.steps,
            ports=("apply_fee",),
        )
    assert "apply_fee" in str(refused.value)


def test_tc_rbs_004_1c__a_step_that_claims_to_write_fails_at_construction():
    """The other door. A Check's step claiming `writes=True` is refused too."""
    with pytest.raises(RunbookContractError):
        RunbookDefinition(
            key="test_bill_that_writes",
            name="Test bill",
            kind=models.KIND_CHECK,
            category="billing",
            subject_type="account",
            unit_of_work="account-period",
            resolve=rb23.resolve,
            report=rb23.report,
            steps=(
                Step(
                    key="price",
                    label="Price through the real engine",
                    mode=MODE_SET,
                    run=rb23.step_price,
                    writes=True,
                ),
            ),
        )


def test_the_four_steps_are_the_build_sheets_own_four(brazos, dana):
    """`RBS-004-R23` region 3 draws four rows with this copy, in this order."""
    assert [s.key for s in rb23.RUNBOOK.steps] == ["load", "price", "explain", "compare"]
    assert [s.label for s in rb23.RUNBOOK.steps] == [
        "Load the account, unit, plan and reads",
        "Price through the real engine",
        "Explain every line",
        "Compare with the last bill",
    ]
    assert all(step.writes is False for step in rb23.RUNBOOK.steps)


# ── a priced account · TC-RBS-004.1 ───────────────────────────────────────


def test_tc_rbs_004_1__a_billable_account_prices_and_every_line_is_explained(brazos, dana):
    """Every line carries a sentence, and nothing was written.

    ⚠ **THE ASSERTION IS *EVERY* LINE, NOT *A* LINE.** `BR-RBS-010` says every
    record states the rule that decided it; a report where six lines of seven
    explain themselves is the shape a spot check passes over.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana)
        result = executor.execute(
            rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account)
        )

        priced = result.set_results["price"]["priced"]
        assert priced is not None, result.set_results["price"]["refusal"]
        explained = result.set_results["explain"]["lines"]
        assert len(explained) == len(priced["lines"]) >= 1
        for row in explained:
            assert row["why"].strip(), f"line {row['description']!r} explains nothing"
            assert row["why"].endswith("."), "an explanation is a sentence"

        # Nothing was written. The Check has no writer; this asserts the
        # consequence rather than the declaration.
        assert billing_models.Invoice.objects.count() == 0
        assert billing_models.InvoiceLine.objects.count() == 0
        assert billing_models.BillRun.objects.count() == 0


def test_the_report_is_four_blocks_from_the_twelve_and_close_accepts_it(brazos, dana):
    """`BR-RBS-021` — the renderer knows twelve names and this report uses four.

    Run through `validate_report`, which is what `close_run` calls: a report the
    executor composed and the closer refuses is a run marked failed with a
    half-drawn screen behind it.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23002")
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    names = [block["block"] for block in result.report]
    assert names[:3] == ["kpis", "sentence", "records"]
    assert set(names) <= {"kpis", "sentence", "records", "reconciled"}
    assert validate_report(result.report, runbook_key="test_bill") == result.report


def test_money_travels_at_four_decimals_and_a_rate_at_four(brazos, dana):
    """Hard rule 2 — stored 4, displayed 2 — and `OQ-620` for the rate cell.

    ⚠ **THE FROZEN REPORT CARRIES FOUR.** `TC-RBS-004.3` compares at four; a
    payload quantized to two would make that comparison unrunnable against the
    stored report and would hide a `$0.0025 / kWh` divergence.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23003")
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    records = next(b for b in result.report if b["block"] == "records")
    amounts = [row["cells"]["amount"] for row in records["payload"]["rows"]]
    assert amounts, "no priced lines, so this check cannot fail"
    for cell in amounts:
        assert cell["kind"] == "money"
        assert len(cell["amount"].split(".")[1]) == 4, cell
        assert len(cell["currency"]) == 3

    rates = [
        row["cells"]["rate"]
        for row in records["payload"]["rows"]
        if row["cells"]["rate"]["kind"] == "rate"
    ]
    for cell in rates:
        assert len(cell["rate"].replace(",", "").split(".")[1]) == 4, cell


def test_a_quantity_never_travels_without_its_unit(brazos, dana):
    """CLAUDE.md hard rule 3, on the two places a quantity appears.

    The `unit` cell requires both halves, and the explanation sentence names the
    unit whenever it names a number — a bare *"5,000"* on a bill is a figure
    nobody can check.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23004")
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    records = next(b for b in result.report if b["block"] == "records")
    for row in records["payload"]["rows"]:
        cell = row["cells"]["quantity"]
        if cell["kind"] == "unit":
            assert cell["unit"], f"a quantity with no unit: {cell}"
            assert cell["quantity"]

    for row in result.set_results["explain"]["lines"]:
        if row.get("quantity") is not None and row.get("unit"):
            assert row["unit"] in row["why"], row["why"]


def test_no_rule_id_no_screen_code_and_no_database_id_reaches_a_clerk(brazos, dana):
    """B14 rules 31 and 32, over every string the report shows.

    ⚠ **THIS IS THE CHECK THAT KEEPS THE ENGINE'S OWN SENTENCES OFF THE
    SCREEN.** `GatherProblem`'s messages quote `BR-BIL-015`, `BR-RAT-090` and
    `BR-CUS-1010` by name and are exactly what a lane would reach for when asked
    for *"the engine's own refusal"*. They travel in the run's record and are
    rendered nowhere; this is what proves it.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23005")
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    strings = _clerk_strings(result.report)
    assert strings, "an empty report cannot fail this check"
    for text in strings:
        for pattern in FORBIDDEN_IN_CLERK_COPY:
            assert not pattern.search(text), f"clerk copy carries {pattern.pattern}: {text!r}"


# ── a refused account · TC-RBS-004.2 ──────────────────────────────────────


def test_tc_rbs_004_2__a_missing_read_is_ONE_refusal_naming_the_service(brazos, dana):
    """One sentence, six words or fewer, naming the service and the date.

    ⚠ **AND NOTHING ELSE IS DRAWN** — judgment J2. `US-RBS-004` says *"ONE
    refusal sentence"*, so there is no KPI strip of em dashes and no comparison
    beside the stop.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23006", consumption=None)
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    names = [block["block"] for block in result.report]
    assert names == ["sentence", "records"], names

    sentence = next(b for b in result.report if b["block"] == "sentence")["payload"]
    text = sentence["text"]
    assert len(text.split()) <= 6, f"B14 rule 33 caps a refusal at six words: {text!r}"
    assert text.endswith(".")
    assert sentence["tone"] in ("danger", "warning")

    records = next(b for b in result.report if b["block"] == "records")["payload"]
    assert records["rows"] == []
    # `BR-RBS-011` — the empty state carries the route in words.
    assert records["empty"]["helper"].strip()
    assert "run this again" in records["empty"]["helper"]


#: The ELEVEN services, in seed order, plus the no-service case. Two of them are
#: TWO WORDS and that is the whole reason this list is here — see the next test.
ELEVEN_SERVICES = (
    "electric",
    "water",
    "gas",
    "sewer",
    "trash",
    "storm_water",
    "solar",
    "broadband",
    "thermal_heat",
    "battery",
    "fire",
    None,
)


def test_every_refusal_sentence_fits_six_words_for_every_one_of_the_eleven_services():
    """B14 rule 33, over EVERY reason × EVERY service — and it went RED first.

    ⚠ **THIS CHECK FOUND A REAL BREACH THE MOMENT IT WAS WRITTEN, AND THE BREACH
    IS THE REASON IT IS SHAPED THIS WAY.** The first draft of the refusal table
    read *"{service} has no read for {month}."* — six words for *Sewer*, which
    is the example in `US-RBS-004`'s own test case, and **seven** for *Storm
    water*. Two of the eleven service codes are two words (`storm_water`,
    `thermal_heat`), so a check that used one service would have passed over
    two of the eleven for ever.

    That is hard-won law 7's fifth shape — a check reporting zero over a scope
    it silently excludes — so this one states its scope: **13 reasons × 12
    subjects.**
    """
    from datetime import date

    august = date(2026, 8, 31)
    reasons = list(rb23._REFUSAL_SENTENCE) + ["a_reason_nobody_has_written_yet"]
    checked = 0
    for reason in reasons:
        for service in ELEVEN_SERVICES:
            text = rb23.refusal_sentence({"reason": reason, "service_code": service}, august)
            checked += 1
            assert len(text.split()) <= 6, f"{reason} / {service}: {text!r}"
            assert text.endswith("."), f"{reason} / {service}: {text!r}"
            for pattern in FORBIDDEN_IN_CLERK_COPY:
                assert not pattern.search(text), f"{reason} / {service}: {text!r}"
    print(f"refusal sentences checked: {checked} ({len(reasons)} reasons x {len(ELEVEN_SERVICES)} subjects)")
    assert checked == len(reasons) * len(ELEVEN_SERVICES)


def test_the_refusal_table_states_how_much_of_billings_vocabulary_it_covers():
    """A declared blind spot with a NUMBER beside it — hard-won law 7's fifth shape.

    ⚠ **`G32` REPORTED `0 unresolved` TRUTHFULLY, OVER 21 LIVE REFUSALS IT
    COULD NOT SEE.** This table names some of billing's reason codes and falls
    through for the rest, and the fall-through is lawful — it still names the
    service and the month in six words. What is NOT lawful is not knowing how
    many. So this prints the coverage and asserts only that it is going up:
    a bare *"there is a fallback"* is indistinguishable from a table of one.

    The fall-through was not theoretical. `plan_has_no_tariff_for_service` was
    reaching it until the browser walkthrough put the sentence on a screen —
    *"Electric: no bill for July."* where the fact is *"no price"*, and those
    two send a clerk to two different screens.
    """
    from apps.billing import gather as billing_gather
    from apps.billing import runs as billing_runs
    from apps.billing import single as billing_single

    published = {
        value
        for module in (billing_gather, billing_runs, billing_single)
        for name, value in vars(module).items()
        if name.startswith(("GATHER_", "CALC_", "RUN_", "SINGLE_", "PRICING_"))
        and isinstance(value, str)
        and value.islower()
    }
    named = published & set(rb23._REFUSAL_SENTENCE)
    print(
        f"refusal sentences: {len(named)} of billing's {len(published)} reason codes are "
        f"named; the rest reach the fallback, which still fits six words"
    )
    assert len(named) >= 20, (
        f"only {len(named)} of {len(published)} billing reason codes have their own sentence"
    )


def test_every_refusal_names_a_fix_route(brazos):
    """`BR-RBS-011` — a failure with no route is a defect in the runbook.

    Asserted over every reason including one this module has never seen, because
    the fallback is the half a table-driven map silently loses.
    """
    for reason in list(rb23._REFUSAL_SENTENCE) + ["a_reason_nobody_has_written_yet"]:
        label, route = rb23.fix_route({"reason": reason})
        assert label.strip() and route.startswith("/"), reason


def test_a_refusal_names_the_service_the_engine_named(brazos, dana):
    """The DECISION is the engine's; only the WORDS are this module's.

    The service in the sentence comes from `GatherProblem.service_code` — the
    engine's own field — and is not inferred from a description or a unit.
    """
    from datetime import date

    text = rb23.refusal_sentence(
        {"reason": "missing_read_undecided_at_calculate", "service_code": "sewer"},
        date(2026, 8, 31),
    )
    assert text == "Sewer: no August read."
    # And the eleventh service, which is where the six-word cap actually bites.
    storm = rb23.refusal_sentence(
        {"reason": "missing_read_undecided_at_calculate", "service_code": "storm_water"},
        date(2026, 8, 31),
    )
    assert storm == "Storm water: no August read."


# ── the comparison · TC-RBS-004.4 ─────────────────────────────────────────


class _View:
    """The minimum `report(view)` reads, so the comparison can be driven directly.

    Built rather than mocked: `report()` reads `set_results` and nothing else,
    and a fake that offered more would be a fake of a shape this module does not
    depend on.
    """

    def __init__(self, set_results):
        self.set_results = set_results


def _priced(lines, total, currency="USD"):
    return {
        "priced": {
            "account_no": "A-23099",
            "currency": currency,
            "total": Decimal(total),
            "taxable_subtotal": Decimal("0"),
            "tax_total": Decimal("0"),
            "fee_total": Decimal("0"),
            "split": False,
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "service_date": PERIOD_END,
            "lines": lines,
        },
        "refusal": None,
    }


def _line(description, amount, **extra):
    line = {
        "kind": extra.pop("kind", "usage"),
        "description": description,
        "amount": Decimal(amount),
        "taxable": True,
        "quantity": None,
        "unit": None,
        "unit_price": None,
        "service": "water",
        "tax_id": None,
        "tariff_version_id": None,
        "charge_id": None,
    }
    line.update(extra)
    return line


def test_tc_rbs_004_4__a_line_on_one_side_only_is_shown_and_never_dropped():
    """An outer join. `TC-RBS-004.4`'s *"an inner join silently hides"* case.

    ⚠ **THIS IS THE RED PROOF FOR THE JOIN.** Written with an inner join, the
    two interesting rows — the new charge and the fee that stopped — vanish and
    every other assertion in this suite still passes. The whole table is
    asserted, not a count.
    """
    view = _View(
        {
            "load": {
                "account_id": "x",
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
            },
            "price": _priced(
                [_line("Water base charge", "18.0000"), _line("Storm water", "6.5000")],
                "24.5000",
            ),
            "explain": {"lines": []},
            "compare": {
                "available": True,
                "reason": "",
                "currency": "USD",
                "rows": [
                    {
                        "description": "Water base charge",
                        "this_run": Decimal("18.0000"),
                        "last_bill": Decimal("18.0000"),
                        "difference": Decimal("0"),
                        "ties": True,
                        "only_here": False,
                        "only_there": False,
                    },
                    {
                        "description": "Storm water",
                        "this_run": Decimal("6.5000"),
                        "last_bill": None,
                        "difference": Decimal("6.5000"),
                        "ties": False,
                        "only_here": True,
                        "only_there": False,
                    },
                    {
                        "description": "Late fee",
                        "this_run": None,
                        "last_bill": Decimal("12.0000"),
                        "difference": Decimal("-12.0000"),
                        "ties": False,
                        "only_here": False,
                        "only_there": True,
                    },
                ],
            },
        }
    )
    blocks = rb23.report(view)
    reconciled = next(b for b in blocks if b.block == "reconciled").payload
    lines = [row["cells"]["line"]["text"] for row in reconciled["rows"]]
    assert lines == ["Water base charge", "Storm water", "Late fee"]

    # A row present on one side draws an em dash on the other, never a zero: a
    # zero says "we charged nothing", an em dash says "there was no such line".
    storm = reconciled["rows"][1]["cells"]
    assert storm["last_bill"] == {"kind": "text", "text": "—"}
    late = reconciled["rows"][2]["cells"]
    assert late["this_run"] == {"kind": "text", "text": "—"}

    # A tie is a MARK, not an absence.
    assert reconciled["rows"][0]["cells"]["difference"] == {
        "kind": "pill",
        "label": "Same",
        "tone": "neutral",
    }
    assert reconciled["tiesLabel"] == "Same"


def test_the_comparison_column_headings_name_the_two_sides():
    """Judgment J4's headings, and why they are not B14 rule 34's pair.

    Rule 34 fixes **Recorded** / **In the books** for *held here* versus
    *posted*. Neither side here is that: this run is held NOWHERE — nothing was
    written — so calling it *Recorded* would claim the opposite of the
    runbook's one promise. `RBS-006-R9` already draws *Billed* / *In the books*
    rather than the literal pair, so the heading naming its own side is the
    established shape.
    """
    view = _View(
        {
            "load": {"account_id": "x", "period_start": PERIOD_START, "period_end": PERIOD_END},
            "price": _priced([_line("Water", "1.0000")], "1.0000"),
            "explain": {"lines": []},
            "compare": {"available": True, "reason": "", "currency": "USD", "rows": []},
        }
    )
    reconciled = next(b for b in rb23.report(view) if b.block == "reconciled").payload
    assert [c["label"] for c in reconciled["columns"]] == [
        "Line",
        "This run",
        "Last issued bill",
        "Difference",
    ]


def test_no_issued_bill_draws_no_comparison_at_all():
    """A stated absence is CLOSED by default (B14 rule 32).

    A new connection has no last bill, and an empty comparison table headed
    *Against the last issued bill* would read as *"every line changed"*.
    """
    view = _View(
        {
            "load": {"account_id": "x", "period_start": PERIOD_START, "period_end": PERIOD_END},
            "price": _priced([_line("Water", "1.0000")], "1.0000"),
            "explain": {"lines": []},
            "compare": {"available": False, "reason": "no_issued_bill", "rows": []},
        }
    )
    assert [b.block for b in rb23.report(view)] == ["kpis", "sentence", "records"]


# ── the small decisions, asserted so they cannot drift ────────────────────


def test_a_zero_amount_line_is_drawn_with_its_explanation():
    """Judgment J3 — `$0.00` for sewer is a fact the engine produced.

    Dropping it would make the bill on this screen a different bill from the one
    the run produces, which breaks this runbook's only promise.
    """
    view = _View(
        {
            "load": {"account_id": "x", "period_start": PERIOD_START, "period_end": PERIOD_END},
            "price": _priced(
                [_line("Sewer base charge", "0.0000", kind="base", service="sewer")], "0.0000"
            ),
            "explain": {
                "lines": [
                    {
                        "seq": 1,
                        "kind": "base",
                        "kind_word": "Base charge",
                        "chip": rb23.CHIP_CHARGES,
                        "description": "Sewer base charge",
                        "service": "Sewer",
                        "quantity": None,
                        "unit": None,
                        "unit_price": None,
                        "amount": Decimal("0.0000"),
                        "why": "Fixed charge for Sewer.",
                    }
                ]
            },
            "compare": {"available": False, "reason": "no_issued_bill", "rows": []},
        }
    )
    records = next(b for b in rb23.report(view) if b.block == "records").payload
    assert records["total"] == 1
    assert records["rows"][0]["cells"]["amount"]["amount"] == "0.0000"
    assert records["rows"][0]["cells"]["why"]["text"] == "Fixed charge for Sewer."


def test_a_run_is_never_bounded_by_frequency__judgment_j5():
    """`OQ-RBS-1737` closed with a frequency parameter, 24 hours its default.

    ⚠ A test bill is re-run constantly BY DESIGN, so it declares no frequency
    parameter and no guard that would stop a second run. This asserts the
    absence, so the wave that builds the run-level duplicate check meets a red
    test naming this runbook rather than quietly bounding it.
    """
    assert [p.name for p in rb23.RUNBOOK.parameters] == [
        "account",
        "period",
        "compare_with",
        "show",
        "rounding",
    ]
    assert rb23.RUNBOOK.guards == ()


def test_the_rounding_parameter_is_read_from_settings_and_never_duplicated():
    """`RBR-03` / `RB-021` — policy lives in Settings and is not copied onto a card."""
    rounding = next(p for p in rb23.RUNBOOK.parameters if p.name == "rounding")
    assert rounding.type == "ref:setting"
    assert rounding.setting_key == "money.rounding"
    assert rounding.default is None


def test_the_subject_carries_a_label_and_never_an_id_as_its_value(brazos, dana):
    """B14 rule 31 — the result files write `SubjectRef.label` into Subject.

    An unlabelled subject produces a row a clerk cannot act on, which is
    `BR-RBS-011` failing through a different door.
    """
    with tenant_ctx(brazos):
        account = _billable(brazos, dana, account_no="A-23007")
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

    assert len(result.subjects) == 1
    subject = result.subjects[0]
    assert subject.subject_type == "account"
    assert subject.label
    assert subject.label != subject.subject_id


def test_an_account_this_tenant_does_not_hold_resolves_to_nothing(brazos, dana):
    """A scope of nothing, and a report that says so rather than looking clean.

    ⚠ The dangerous outcome is not a crash. It is a run that walked no account
    and rendered as a priced bill with no lines — which reads exactly like *"this
    customer owes nothing"*.
    """
    import uuid

    with tenant_ctx(brazos):
        _billable(brazos, dana, account_no="A-23008")
        result = executor.execute(
            rb23.RUNBOOK,
            tenant_id=brazos.id,
            params={
                "account": str(uuid.uuid4()),
                "period": {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()},
                "compare_with": "nothing",
                "show": "every_line_explained",
            },
        )

    assert result.subjects == ()
    assert [b["block"] for b in result.report] == ["sentence", "records"]
    assert billing_models.Invoice.objects.count() == 0
