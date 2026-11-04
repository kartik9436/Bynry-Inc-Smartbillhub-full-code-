# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 · US-RBS-002 (EP-RBS-01) — CR-075 wave B task B4: the
#           conformance suite. Every registered runbook constructs, resolves on
#           the fixture, dry-runs, wrote nothing if it is a Check, and its
#           report validates.
# Rules:    BR-RBS-001 · BR-RBS-002 · BR-RBS-009 · BR-RBS-012 · BR-RBS-019 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-022 · BR-RBS-023 · BR-RBS-024 ·
#           BR-RBS-025 · BR-RBS-027 · BR-RBS-038
# Tests:    this file (TC-RBS-1, TC-RBS-15, TC-RBS-17, TC-RBS-19, TC-RBS-22) ·
#           06-backend/tests/test_rbs_savepoint_pg.py (TC-RBS-5 — PostgreSQL)
# Impacts:  apps/runbooks/contract.py · registry.py · engine/executor.py ·
#           services.py · selectors.py · definitions/
# ───────────────────────────────────────────────────────
"""The conformance suite — what a wrong declaration costs, at LOAD.

⚠ **WHAT THIS FILE CAN AND CANNOT PROVE, SAID BEFORE ANYTHING ELSE.** It runs on
the default suite, which is in-memory SQLite. Two things are therefore NOT proved
here and are not pretended to be:

  * **the per-record savepoint** (`BR-RBS-007`, `TC-RBS-5`) — SQLite has no
    aborted-transaction state, so the broken `try/except IntegrityError:
    continue` passes every case in this file. It is proved in
    `tests/test_rbs_savepoint_pg.py`, which SKIPS here rather than passing
    vacuously (hard-won law 14; `G5` once called 192 skips a pass);
  * **tenant isolation** — there is no row-level security on SQLite at all;
    `tests/test_us_rbs_041_pg.py` holds that.

⚠ **AND THE LIVE REGISTRY IS EMPTY IN WAVE B, WHICH THIS FILE PRINTS RATHER THAN
HIDES.** `test_..._live_registry_conforms` reports the count it conformed, so
*"0 registered"* is visible in the output. A suite that said only PASSED over an
empty registry would be a check reporting zero over a scope it silently
excludes, which is the shape that cost 21 live refusals when `G32` did it. The
first runbook is wave C's `configuration_check.py`; every conformance assertion
below runs today against exemplar definitions built in the test, and the same
helper runs over the live registry the moment it holds anything.

**Every negative case here was shown RED first.** The refusal text quoted in
each docstring is the actual message, copied from the failing run, not a
paraphrase — a docstring that describes a refusal it never saw is hard-won law 1
one file along.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import types

import pytest

from apps.runbooks import contract, interfaces, models
from apps.runbooks.contract import (
    BLOCK_TYPES,
    MODE_PER_RECORD,
    MODE_SET,
    PARAMETER_TYPES,
    TRIGGERS,
    Block,
    Guard,
    Parameter,
    RunbookContractError,
    RunbookDefinition,
    Step,
    SubjectRef,
    validate_report,
)
from apps.runbooks.engine import executor
from apps.runbooks.registry import RunbookRegistry, registry
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

#: ⚠ **EVERY CASE THAT RUNS THE EXECUTOR NEEDS A DATABASE, EVEN WHERE ITS STEPS
#: TOUCH NONE — and that is correct rather than an inconvenience to design
#: around.** `executor._run_one_record` opens `transaction.atomic()` for every
#: subject unconditionally, which needs a connection whether the step writes or
#: not. Making the savepoint conditional on "does this step write" is exactly the
#: simplification hard-won law 14 says the next lane will reach for: a step's own
#: claim about itself is not a guarantee about what it calls, and the version
#: that gets it wrong passes this whole suite green. So the mark goes here.
pytestmark = pytest.mark.django_db

# ── the exemplars every case is built from ────────────────────────────────


def _subjects(ctx):
    return [
        SubjectRef(subject_type="account", subject_id="a-1", label="Alvarez, M."),
        SubjectRef(subject_type="account", subject_id="a-2", label="Brand, T."),
        SubjectRef(subject_type="account", subject_id="a-3", label="Cole, R."),
    ]


def _report(view):
    """A report the RENDERER could actually draw.

    ⚠ **THIS USED TO BE `records payload={"rows": 3}` — AN INTEGER WHERE THE
    RENDERER READS A LIST, AND NO `columns`, `total` OR `empty` AT ALL.** It was
    a deliberately minimal test double, and that was the problem: this file is
    the suite that owns the report contract, so its exemplar IS the repo's
    working model of a conformant report — and the model could not have been
    drawn on a screen. `validate_report` asked only whether the block NAME was
    one of the twelve, so nothing here disagreed with anything.

    That gap is what `DEF-RBS-4352` cost in the product: the collections ladder
    shipped `breakdown {by, rows, rungs}` where the renderer needs
    `{heading, columns, rows}`, and `RBS-006` drew an error boundary instead of
    835 planned notices — with every test on both sides green.

    So the exemplar is now a real payload for both blocks, transcribed from
    `07-frontend/src/features/runbooks/blocks/types.ts`.
    """
    return [
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "examined",
                        "label": "Examined",
                        "value": {"kind": "text", "text": str(view.record_count)},
                    }
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": [{"key": "subject", "label": "Subject"}],
                "rows": [
                    # `RecordOutcome.subject` is a `SubjectRef`, not an id — the
                    # plan and the outcome live in one row (`03-field-map.md` §4)
                    # and the row carries the whole subject so a report can print
                    # the LABEL a clerk reads rather than a database id (B14
                    # rule 31).
                    {
                        "id": str(record.subject.subject_id),
                        "cells": {"subject": {"kind": "text", "text": record.subject.label}},
                    }
                    for record in view.records
                ],
                "total": len(view.records),
                "empty": {"headline": "Nothing to show", "body": "This run examined no records."},
            },
        ),
    ]


def _check(**overrides) -> RunbookDefinition:
    """*Can we bill?*-shaped: a Check, no ports, one per-record step."""
    fields = dict(
        key="can_we_bill",
        name="Can we bill?",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="account",
        unit_of_work="account",
        resolve=_subjects,
        report=_report,
        steps=(
            Step(
                key="has_a_read",
                label="Has a read",
                mode=MODE_PER_RECORD,
                run=lambda ctx, subject: "ok",
            ),
        ),
    )
    fields.update(overrides)
    return RunbookDefinition(**fields)


def _action(**overrides) -> RunbookDefinition:
    """*Dunning and notices*-shaped: an Action with two of the thirteen ports."""
    fields = dict(
        key="dunning",
        name="Dunning and notices",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="account",
        resolve=_subjects,
        report=_report,
        steps=(
            Step(
                key="decide_tier",
                label="Decide the tier",
                mode=MODE_PER_RECORD,
                run=lambda ctx, subject: "queued",
                writes=True,
            ),
        ),
        ports=("queue_notice", "apply_fee"),
    )
    fields.update(overrides)
    return RunbookDefinition(**fields)


def _sentences(block: dict):
    """Every human-readable string a report block carries, however nested.

    Used only by `_conform`'s empty-scope branch: it has to ask *did the runbook
    SAY it found nothing*, and the twelve payloads keep their words in twelve
    different places, so it walks rather than guessing at a key.
    """
    stack = [block]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
        elif isinstance(node, str):
            yield node


def _conform(
    definition: RunbookDefinition, *, tenant_id=None, overrides=None
) -> executor.RunResult:
    """TC-RBS-15's five assertions, over ONE runbook. Used on every exemplar.

    Constructs (already done — construction is the `RunbookDefinition` call) ·
    resolves on the fixture · dry-runs · **a Check wrote nothing** · its report
    validates against the block schema.

    `tenant_id` is passed for a LIVE runbook, whose seams all read tenant-scoped
    rows; the exemplars built in this file read nothing and need none.

    ⚠ **PARAMETERS COME FROM THE DEFINITION'S OWN DEFAULTS, ADDED 2026-09-06
    (`CR-075` wave L).** This passed `params={}`, which was true of every runbook
    until runbook 8: the collections ladder declares a REQUIRED business day and
    REFUSES to resolve without one, because a ladder may not read a clock
    (`BR-TEN-043`, gate `G6` — a run re-taken for last Tuesday must take last
    Tuesday's decision). Reading the declared defaults keeps this harness working
    for the next runbook that declares a parameter; `overrides` carries the ones
    no default can supply.
    """
    params = {p.name: p.default for p in definition.parameters if p.default is not None}
    params.update(overrides or {})
    ctx = executor.build_context(definition, tenant_id=tenant_id, params=params)
    if definition.is_check:
        assert ctx.ports == {}, (
            f"{definition.key} is a Check and its context holds ports {sorted(ctx.ports)} — "
            "BR-RBS-002 says the capability is ABSENT, not merely unused"
        )
    result = executor.execute(definition, ctx=ctx)
    # ⚠ **AN EMPTY SCOPE IS LAWFUL AND IT MUST STILL SAY SO IN WORDS.** This
    # read `assert result.subjects` until `accounting_export` arrived, and that
    # assertion is right for a runbook whose subject is the TENANT — runbook 1
    # resolves exactly one, always — and wrong for one whose scope comes from
    # tenant DATA. Runbook 36 walks the accounting months a tenant has posted
    # into, and this fixture posts nothing, so it correctly resolves zero:
    # `BR-RBS-042` clause 2, *"an empty domain says so"*.
    #
    # **The check is not weakened, it is re-aimed.** A runbook that resolves
    # nothing and reports nothing is exactly the dangerous shape — a clean
    # verdict over an estate it never looked at — so an empty scope is accepted
    # ONLY when the report carries a sentence about it. That keeps the case
    # capable of failing, which a bare `or True` would not (hard-won law 7).
    if not result.subjects:
        said_so = any(
            isinstance(value, str) and value.strip()
            for block in result.report
            for value in _sentences(block)
        )
        assert said_so, (
            f"{definition.key} resolved nothing on the fixture AND said nothing about it — "
            "an empty scope must reach the report in words (BR-RBS-042 clause 2)"
        )
    assert result.scope_fingerprint
    for block in result.report:
        assert block["block"] in BLOCK_TYPES
    validate_report(result.report, runbook_key=definition.key)
    return result


# ── TC-RBS-1 — the rule this whole wave exists to make true ───────────────


def test_us_rbs_002_tc_rbs_1_binding_a_port_to_a_check_raises_at_construction():
    """`TC-RBS-1` — a Check with an action port fails to BUILD, naming both.

    ⚠ **THE ASSERTION IS THAT IT RAISES AT CONSTRUCTION, NOT THAT IT REFUSES A
    WRITE.** `BR-RBS-002`: the capability is absent, not merely unused. A
    version that raised when the port was called would mean a Check with a
    writer sitting on a live schedule, and the promise that two people can press
    **Run ▶** on a thousand accounts is gone.

    The message names the runbook key and every offending port. Shown red first
    on a `RunbookDefinition` that accepted ports for either kind; the refusal
    text below is the real one.
    """
    with pytest.raises(RunbookContractError) as caught:
        _check(ports=("queue_notice",))
    message = str(caught.value)
    assert "'can_we_bill'" in message
    assert "queue_notice" in message
    assert "Check is CONSTRUCTED without action ports" in message
    assert "BR-RBS-002" in message


def test_us_rbs_002_a_check_with_two_ports_names_both_in_the_refusal():
    """A refusal that named only the first port would send a lane round twice."""
    with pytest.raises(RunbookContractError) as caught:
        _check(ports=("queue_notice", "apply_fee"))
    message = str(caught.value)
    assert "apply_fee" in message and "queue_notice" in message


def test_us_rbs_002_an_action_may_hold_the_same_ports_and_constructs():
    """The mirror case — otherwise the refusal above could be *any* port failing."""
    action = _action()
    assert action.ports == ("queue_notice", "apply_fee")
    assert not action.writes_nothing()


def test_us_rbs_002_a_checks_execution_context_holds_no_ports_at_all():
    """`ports_for("check")` is `()`, so there is nothing to call, ever."""
    ctx = executor.build_context(_check())
    assert ctx.ports == {}
    with pytest.raises(RunbookContractError) as caught:
        ctx.port("queue_notice")
    assert "holds none by that name" in str(caught.value)


def test_us_rbs_002_a_checks_step_may_not_even_claim_to_write():
    """The claim and the capability must agree — refused before ports are read."""
    with pytest.raises(RunbookContractError) as caught:
        _check(
            steps=(
                Step(key="s", label="s", mode=MODE_PER_RECORD, run=lambda c, s: "ok", writes=True),
            )
        )
    assert "declares writes=True" in str(caught.value)


def test_us_rbs_002_writes_nothing_is_derived_from_ports_and_nothing_else():
    """`US-RBS-002`: *Writes: Nothing · Sends: Nothing* comes from `ports[]`.

    Never from a hand-written label that could disagree with the constructor —
    which is what `TC-RBS-002.2` plants and watches go red.
    """
    assert _check().writes_nothing() is True
    assert _action().writes_nothing() is False
    assert _check().port_declarations() == ()
    assert len(_action().port_declarations()) == 2


def test_us_rbs_002_raise_work_item_is_refused_by_name_as_a_port():
    """`raise_work_item` is an ENGINE act. The source says otherwise seven times.

    A lane building the specification's *"four named calls"* version gives every
    Check a writer and `BR-RBS-002` is gone, so the refusal names the reason
    rather than only the fact.
    """
    with pytest.raises(RunbookContractError) as caught:
        _action(ports=("raise_work_item",))
    message = str(caught.value)
    assert "ENGINE acts" in message
    assert "four named calls" in message


def test_us_rbs_002_a_fourteenth_port_is_refused():
    with pytest.raises(RunbookContractError) as caught:
        _action(ports=("send_invoice",))
    assert "not one of the thirteen" in str(caught.value)


def test_us_rbs_002_the_port_list_is_still_fourteen_and_holds_no_engine_act():
    """The membership matters more than the count, so both are asserted."""
    # ⚠ FIFTEEN FROM 2026-10-07 (`CR-173-BRC10`): `send_partner_file`, owned by
    # integrations, joined as a reviewed interface — the New World receipt file.
    assert len(interfaces.PORTS) == 15
    assert "raise_work_item" not in interfaces.PORTS
    assert interfaces.ports_for("check") == ()
    assert len(interfaces.ports_for("action")) == 15


# ── TC-RBS-19 — an unknown category stops the process ─────────────────────


def test_us_rbs_015_tc_rbs_19_category_misc_is_refused_at_construction():
    """`TC-RBS-19` — `category = "Misc"` is refused, naming module and category.

    The plan's goal sentence for this wave: *a module declaring `category =
    "Misc"` **stops the process from starting**, naming itself.* Construction
    happens during the import `AppConfig.ready()` performs, so this refusal IS
    that.
    """
    with pytest.raises(RunbookContractError) as caught:
        _check(category="Misc")
    message = str(caught.value)
    assert "'can_we_bill'" in message
    assert "'Misc'" in message
    assert "not one of the sixteen" in message
    assert "BR-RBS-025" in message


def test_us_rbs_015_all_sixteen_categories_construct():
    """The mirror — otherwise the refusal above might be refusing everything."""
    for category in models.CATEGORIES:
        assert _check(category=category).category == category
    assert len(models.CATEGORIES) == 16


def test_us_rbs_015_the_category_does_not_restrict_which_ports_are_held():
    """⚠ `DEF-RBS-4262` — the contract's own coverage table breaks its own rule.

    `BR-RBS-024` ends *"the category names the owning module whose ports it may
    call"*, and `12-the-contract.md` §5 restates it. **Enforced literally, that
    sentence refuses all nine Actions the same contract defines in its §8
    coverage table** — runbook 8 is Collections (owning module `payments`) and
    holds `queue_notice` (`notifications`) and `apply_fee` (`billing`).

    This case pins the reading taken, so a later lane that "fixes" it by adding
    the restriction meets a red test naming the defect rather than discovering
    it when nine runbooks stop loading.
    """
    dunning = _action()
    assert dunning.category == "collections"
    assert dunning.owning_module == "payments"
    assert interfaces.PORTS["queue_notice"].owning_module == "notifications"
    assert interfaces.PORTS["apply_fee"].owning_module == "billing"


# ── TC-RBS-15 — the report is twelve blocks and not thirteen ──────────────


def test_us_rbs_015_tc_rbs_15_a_thirteenth_block_is_refused_and_named():
    """`TC-RBS-15` — a report naming a thirteenth block is refused, at close."""
    with pytest.raises(RunbookContractError) as caught:
        validate_report([{"block": "timeline", "payload": {}}], runbook_key="x")
    message = str(caught.value)
    assert "'timeline'" in message
    assert "not one of the twelve" in message
    assert "THREE runbooks" in message


def test_us_rbs_015_a_block_object_refuses_a_thirteenth_name_at_construction_too():
    with pytest.raises(RunbookContractError) as caught:
        Block(block="timeline")
    assert "BR-RBS-021" in str(caught.value)


#: The smallest payload each block can legally carry, transcribed from
#: `07-frontend/src/features/runbooks/blocks/types.ts`. Every value is the
#: emptiest legal one, so a field appearing here is a field the renderer
#: REQUIRES rather than one this fixture happens to set.
MINIMAL_PAYLOADS: dict[str, dict] = {
    "verdict": {"word": "Ready", "tone": "success", "count": "0 to fix"},
    "kpis": {"tiles": []},
    "chain": {"label": "Steps", "cells": []},
    "records": {
        "columns": [],
        "rows": [],
        "total": 0,
        "empty": {"headline": "Nothing", "body": "Nothing to show."},
    },
    "breakdown": {"heading": "By service", "columns": [], "rows": []},
    "reconciled": {"heading": "Tie-out", "columns": [], "rows": [], "tiesLabel": "Ties"},
    "ranked": {"heading": "Largest first", "rows": []},
    "sentence": {"tone": "neutral", "text": "Nothing happened."},
    "facts": {"rows": []},
    # `enabled: true` carries no `reason`; the disabled arm is asserted
    # separately, because that conditional is the half B14 rule 33 rides on.
    "action": {"label": "Send", "tier": "primary", "enabled": True},
    "row_decisions": {"heading": "Decide", "columns": [], "rows": [], "choices": []},
    "downloads": {"files": []},
}


def test_us_rbs_015_all_twelve_block_names_validate():
    """The mirror, and it also pins the twelve machine names this wave minted.

    ⚠ **EACH NAME IS NOW GIVEN A MINIMAL VALID PAYLOAD, WHICH IS THE POINT.**
    This used to pass `{"block": name}` with no payload at all — twelve blocks
    that could not be drawn — and it passed, because `validate_report` asked
    only whether the NAME was one of the twelve. That is the gap `DEF-RBS-4352`
    fell through, so the fixture below doubles as this repo's written statement
    of the smallest thing each block can legally be.
    """
    report = validate_report(
        [{"block": name, "payload": MINIMAL_PAYLOADS[name]} for name in BLOCK_TYPES],
        runbook_key="x",
    )
    assert [b["block"] for b in report] == list(BLOCK_TYPES)
    assert len(BLOCK_TYPES) == 12
    assert set(BLOCK_TYPES) == {
        "verdict",
        "kpis",
        "chain",
        "records",
        "breakdown",
        "reconciled",
        "ranked",
        "sentence",
        "facts",
        "action",
        "row_decisions",
        "downloads",
    }


def test_us_rbs_015_a_payload_missing_a_field_the_renderer_reads_is_refused_at_close():
    """`DEF-RBS-4352`, as a case: the real shape the collections ladder shipped.

    It sent `breakdown {by, rows, rungs}` where the renderer reads
    `{heading, columns, rows}`, so `RBS-006` drew an error boundary instead of
    835 planned notices — with every test on both sides green, because the
    backend checked the NAME and the report crosses the wire as untyped JSON
    that never meets `types.ts`.
    """
    with pytest.raises(RunbookContractError) as caught:
        validate_report(
            [{"block": "breakdown", "payload": {"by": "rung", "rows": [], "rungs": []}}],
            runbook_key="collections_ladder",
        )
    assert "missing 'columns', 'heading'" in str(caught.value)


def test_us_rbs_015_a_disabled_action_with_no_reason_is_refused():
    """B14 draws a control a user may not use as disabled WITH its reason, never
    hidden — `DEF-SHL-4043` is what a grey button that says nothing costs."""
    with pytest.raises(RunbookContractError) as caught:
        validate_report(
            [{"block": "action", "payload": {"label": "Send", "tier": "primary", "enabled": False}}],
            runbook_key="x",
        )
    assert "carries no 'reason'" in str(caught.value)


def test_us_rbs_015_an_extra_field_is_reported_but_does_not_fail_a_run():
    """A missing field crashes the screen; an extra one loses data silently.

    Only the first is refused at close — refusing both would have failed 49
    cases across two shipped, working runbooks on the day the check landed, and
    a validator that red-lines working code on arrival gets reverted rather than
    obeyed. The extra-field question is asked with `strict=True`, where the
    answer is a list to work off.
    """
    payload = dict(MINIMAL_PAYLOADS["records"], checked=3)
    assert validate_report([{"block": "records", "payload": payload}], runbook_key="x")
    assert contract._payload_problems("records", payload, strict=True) == [
        "carries 'checked', which no block draws"
    ]


def test_us_rbs_015_the_payload_map_matches_the_renderers_own_types():
    """The two sides cannot drift, which is what made `DEF-RBS-4284`'s fix hold.

    `PAYLOAD_FIELDS` is a COPY of `types.ts`, and a copy nothing compares is a
    comment claiming a guarantee (hard-won law 1). This parses the renderer's
    own file and asserts the map against it, so changing a payload there turns
    this red naming the field.
    """
    types_file = (
        pathlib.Path(__file__).resolve().parents[2]
        / "07-frontend"
        / "src"
        / "features"
        / "runbooks"
        / "blocks"
        / "types.ts"
    )
    if not types_file.is_file():
        pytest.skip(f"the renderer's types are not in this checkout ({types_file})")
    text = types_file.read_text(encoding="utf-8")

    def top_level_fields(interface: str) -> tuple[set[str], set[str]] | None:
        opened = re.search(rf"export interface {interface} \{{", text)
        if opened is None:
            return None
        index, depth, body = opened.end(), 1, []
        while index < len(text) and depth:
            char = text[index]
            depth += 1 if char == "{" else -1 if char == "}" else 0
            if depth:
                body.append(char)
            index += 1
        flat, nested = [], 0
        for char in "".join(body):
            nested += 1 if char == "{" else -1 if char == "}" else 0
            if nested == 0 and char not in "{}":
                flat.append(char)
        found = re.findall(r"(?:^|\n)\s*(\w+)(\??)\s*:", "".join(flat))
        return {f for f, o in found if not o}, {f for f, o in found if o}

    #: `action` is a UNION in `types.ts`, not an interface, so it is asserted by
    #: the two cases above instead of parsed here — named rather than skipped
    #: silently, because a blind spot with no number attached is
    #: indistinguishable from an empty one (hard-won law 7).
    parsed = 0
    for name, (required, optional) in contract.PAYLOAD_FIELDS.items():
        interface = "".join(part.title() for part in name.split("_")) + "Payload"
        fields = top_level_fields(interface)
        if fields is None:
            assert name == "action", f"{interface} is not an interface in types.ts"
            continue
        parsed += 1
        assert set(required) == fields[0], f"{interface}: required fields drifted"
        assert set(optional) == fields[1], f"{interface}: optional fields drifted"
    assert parsed == 11, f"only {parsed} of the twelve payloads were parsed from types.ts"


def test_us_rbs_015_every_money_kpi_tile_declares_its_basis():
    """`BR-REP-001`: **no unlabelled money number ships anywhere** — and a money
    KPI tile whose basis the payload does not state gets the renderer's fallback
    instead of an answer.

    ⚠ **THIS IS WHAT `DEF-RBS-4350` COST, AND WHY THE FALLBACK IS NOT ENOUGH.**
    `KpisBlock` hardcoded `basis: "posting"` for every money tile in the
    product. That was correct for the accounting export, whose journal file IS
    the books — and wrong for the test bill, which prices an account and writes
    nothing at all, so its total sat under **Posting date** two inches above its
    own sentence saying *"Nothing was written and no bill number was used"*.
    Both halves were right on their own and neither had anything to check
    against, because no runbook drew a money tile until wave F.

    The renderer still falls back to `"posting"` so a run never crashes on a
    missing label. **This case is what makes that fallback unreachable for
    anything on the branch**: a new runbook that draws money without saying what
    kind of money it is goes red here, naming itself and its tile.

    It is a scan of the SOURCE rather than of a run, deliberately — most
    runbooks need a seeded utility and a bound port to produce a report, and a
    check that can only see the runbooks it is able to execute would report zero
    over a scope it silently excludes (hard-won law 7).
    """
    definitions = pathlib.Path(__file__).resolve().parents[1] / "apps" / "runbooks" / "definitions"
    offenders: list[str] = []
    scanned = 0
    for module in sorted(definitions.glob("*.py")):
        if module.name.startswith("_"):
            continue
        scanned += 1
        text = module.read_text(encoding="utf-8")
        for opened in re.finditer(r'"tiles"\s*:\s*\[', text):
            index, depth = opened.end(), 1
            while index < len(text) and depth:
                depth += 1 if text[index] == "[" else -1 if text[index] == "]" else 0
                index += 1
            tiles = text[opened.end() : index]
            # Each tile is one brace-balanced dict. Walk them so a money tile is
            # judged against ITS OWN keys and not the block's.
            start = None
            depth = 0
            for position, char in enumerate(tiles):
                if char == "{":
                    if depth == 0:
                        start = position
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0 and start is not None:
                        tile = tiles[start : position + 1]
                        money = '"kind": "money"' in tile or "_money_value(" in tile
                        if money and '"basis"' not in tile:
                            name = re.search(r'"id"\s*:\s*(.+?),', tile)
                            offenders.append(f"{module.name}:{name.group(1) if name else '?'}")
                        start = None
    assert scanned >= 4, f"only {scanned} runbook module(s) scanned — the glob is wrong"
    assert offenders == [], (
        "money KPI tile(s) with no declared basis: "
        + ", ".join(offenders)
        + ". BR-REP-001 labels every money number; say whether it reads the posting "
        "date, the clearing date, or is priced and never posted."
    )


def test_us_rbs_015_a_runbook_reporting_a_thirteenth_block_fails_conformance():
    """The end-to-end shape: the executor refuses it while composing the report."""
    bad = _check(report=lambda view: [{"block": "timeline", "payload": {}}])
    with pytest.raises(RunbookContractError) as caught:
        executor.execute(bad)
    assert "timeline" in str(caught.value)


# ── the other three load-time refusals the plan names ─────────────────────


def test_us_rbs_015_a_step_with_no_mode_is_refused_naming_runbook_and_step():
    """`BR-RBS-023` — a step declares its mode; there is no default.

    Two ways to get it wrong and both fail at load: an empty or unknown value
    (this case), and omitting the field entirely, which Python refuses at the
    `Step(...)` call — the case below.
    """
    with pytest.raises(RunbookContractError) as caught:
        _check(steps=(Step(key="s", label="s", mode="", run=lambda c, s: "ok"),))
    message = str(caught.value)
    assert "'can_we_bill'" in message and "'s'" in message
    assert "per_record or set" in message
    assert "BR-RBS-023" in message


def test_us_rbs_015_omitting_mode_entirely_cannot_even_be_constructed():
    with pytest.raises(TypeError) as caught:
        Step(key="s", label="s", run=lambda c, s: "ok")  # type: ignore[call-arg]
    assert "mode" in str(caught.value)


def test_us_rbs_015_a_missing_unit_of_work_is_refused():
    """`BR-RBS-019` — a runbook declares what it walks.

    ⚠ Presence only. The second half — *and it is never the raw row* — is
    marked in `US-RBS-015` itself as *declared here, first enforced in
    `EP-RBS-05`*, because enforcing it needs a roll-up to compare against
    (176,640 intervals → 1,840 meter-days) and no such runbook exists yet.
    """
    with pytest.raises(RunbookContractError) as caught:
        _check(unit_of_work="   ")
    message = str(caught.value)
    assert "declares no unit_of_work" in message
    assert "176,640" in message


def test_us_rbs_015_an_unknown_subject_type_is_refused():
    with pytest.raises(RunbookContractError) as caught:
        _check(subject_type="invoice")
    assert "not one of the twelve" in str(caught.value)
    assert len(models.SUBJECT_TYPES) == 12


def test_us_rbs_015_a_runbook_with_no_steps_is_refused():
    """A runbook with no steps reports a clean result over everything."""
    with pytest.raises(RunbookContractError) as caught:
        _check(steps=())
    assert "most dangerous shape" in str(caught.value)


def test_us_rbs_015_an_unknown_parameter_type_is_refused():
    with pytest.raises(RunbookContractError) as caught:
        Parameter(name="grace", type="rate", label="Grace")
    message = str(caught.value)
    assert "'rate'" in message
    assert "eleven" in message
    assert len(PARAMETER_TYPES) == 11


def test_us_rbs_015_a_money_parameter_refuses_a_float_default():
    """Hard rule 2, in the one place no column can enforce it.

    A parameter lives inside `runbook_versions.definition`, which is `jsonb`;
    there is no `NUMERIC(18,4)` in there, so a float written into that document
    is a breach no database constraint can see (`03-field-map.md` D-3).
    """
    with pytest.raises(RunbookContractError) as caught:
        Parameter(name="past_due_over", type="money", label="Past due more than", default=5.0)
    assert "hard rule 2" in str(caught.value).lower() or "Hard rule 2" in str(caught.value)


def test_us_rbs_015_an_unknown_trigger_is_refused():
    with pytest.raises(RunbookContractError) as caught:
        _check(triggers=("webhook",))
    assert "five rows" in str(caught.value)
    assert len(TRIGGERS) == 5


# ── TC-RBS-17 — set runs once, per-record runs once per subject ───────────


def test_us_rbs_015_tc_rbs_17_a_set_step_runs_once_and_per_record_runs_per_subject():
    """`TC-RBS-17` — the counts, asserted directly rather than via side effects.

    Three subjects. The set step must run **1** time and the per-record step
    **3**. Shown red first with the set step registered as `per_record`, where
    the set step ran 3 times and compared a set with itself.
    """
    definition = _check(
        steps=(
            Step(key="own_normal", label="Own normal", mode=MODE_SET, run=lambda ctx, subs: len(subs)),
            Step(key="compare", label="Compare", mode=MODE_PER_RECORD, run=lambda ctx, s: "ok"),
        )
    )
    result = executor.execute(definition)
    assert result.step_runs == {"own_normal": 1, "compare": 3}
    assert result.set_results["own_normal"] == 3
    assert len(result.records) == 3


def test_us_rbs_015_a_set_step_sees_the_whole_pinned_set_at_once():
    seen = {}

    def remember(ctx, subjects):
        seen["n"] = len(subjects)
        return "done"

    executor.execute(_check(steps=(Step(key="tie", label="Tie", mode=MODE_SET, run=remember),)))
    assert seen["n"] == 3


def test_us_rbs_015_a_per_record_step_can_read_what_a_set_step_computed():
    """Declaration order is execution order — that is what makes 11 and 21 work."""
    definition = _check(
        steps=(
            Step(key="normal", label="Normal", mode=MODE_SET, run=lambda ctx, subs: 42),
            Step(
                key="use_it",
                label="Use it",
                mode=MODE_PER_RECORD,
                run=lambda ctx, s: f"normal={ctx.set_results['normal']}",
            ),
        )
    )
    result = executor.execute(definition)
    assert {r.outcome for r in result.records} == {"normal=42"}


# ── TC-RBS-22 — scope is resolved once and pinned ─────────────────────────


def test_us_rbs_015_tc_rbs_22_resolve_is_called_exactly_once_per_run():
    """`BR-RBS-009` — an account that becomes past due mid-run is not acted on."""
    calls = {"n": 0}

    def counting_resolve(ctx):
        calls["n"] += 1
        return _subjects(ctx)

    definition = _check(
        resolve=counting_resolve,
        steps=(
            Step(key="a", label="A", mode=MODE_PER_RECORD, run=lambda c, s: "ok"),
            Step(key="b", label="B", mode=MODE_SET, run=lambda c, s: "ok"),
            Step(key="c", label="C", mode=MODE_PER_RECORD, run=lambda c, s: "ok"),
        ),
    )
    executor.execute(definition)
    assert calls["n"] == 1


def test_us_rbs_015_the_scope_fingerprint_is_stable_and_order_sensitive():
    a = executor.execute(_check()).scope_fingerprint
    b = executor.execute(_check()).scope_fingerprint
    assert a == b
    reversed_definition = _check(resolve=lambda ctx: list(reversed(_subjects(ctx))))
    assert executor.execute(reversed_definition).scope_fingerprint != a


def test_us_rbs_015_resolve_returning_the_wrong_subject_type_is_refused():
    """A Records table whose rows do not match its own columns, caught at run."""
    wrong = _check(
        resolve=lambda ctx: [SubjectRef(subject_type="meter", subject_id="m-1")]
    )
    with pytest.raises(RunbookContractError) as caught:
        executor.execute(wrong)
    assert "declares subject_type 'account'" in str(caught.value)


# ── BR-RBS-012 — guards are absolute and run before any step ──────────────


def test_us_rbs_015_a_guarded_subject_is_never_seen_by_any_step():
    """`BR-RBS-012` — absolute, whatever the checks would have concluded."""
    walked: list[str] = []
    definition = _check(
        guards=(
            Guard(key="medical", label="Medical", applies=lambda ctx, s: s.subject_id == "a-2"),
        ),
        steps=(
            Step(
                key="s",
                label="S",
                mode=MODE_PER_RECORD,
                run=lambda ctx, s: walked.append(s.subject_id) or "ok",
            ),
        ),
    )
    result = executor.execute(definition)
    assert walked == ["a-1", "a-3"]
    assert [s.subject_id for s in result.guarded] == ["a-2"]


def test_us_rbs_015_a_guarded_subject_still_appears_in_the_counts():
    """`BR-RBS-035` — a count per outcome for the ones with no record row.

    A guarded subject has no record row at all, so it would vanish from every
    total if the counts were derived from the rows alone — and a clerk reading
    *3 examined* over a pinned set of 3 would never know one was skipped.
    """
    definition = _check(
        guards=(Guard(key="g", label="G", applies=lambda ctx, s: s.subject_id == "a-2"),)
    )
    result = executor.execute(definition)
    assert result.counts == {"ok": 2, "skipped": 1}
    assert sum(result.counts.values()) == len(result.subjects)


# ── the registry: one module in, one runbook out ──────────────────────────


def test_us_rbs_015_adding_one_module_puts_a_runbook_in_the_registry():
    """The wave's goal sentence, proved on the real loader.

    A module object declaring `RUNBOOK` is handed to `load()` exactly as
    `definitions/__init__.py` hands it the real ones, and the runbook appears.
    """
    module = types.ModuleType("apps.runbooks.definitions.exemplar")
    module.RUNBOOK = _check()
    scratch = RunbookRegistry()
    assert scratch.load((module,)) == ("apps.runbooks.definitions.exemplar",)
    assert scratch.keys() == ("can_we_bill",)
    assert scratch.get("can_we_bill").name == "Can we bill?"


def test_us_rbs_015_a_definition_module_that_declares_nothing_is_refused():
    """Not skipped — refused. A module here IS a runbook (hard-won law 2)."""
    module = types.ModuleType("apps.runbooks.definitions.empty")
    with pytest.raises(RunbookContractError) as caught:
        RunbookRegistry().load((module,))
    assert "declares no RUNBOOK" in str(caught.value)


def test_us_rbs_015_two_runbooks_cannot_share_a_key():
    scratch = RunbookRegistry()
    scratch.register(_check())
    with pytest.raises(RunbookContractError) as caught:
        scratch.register(_check(name="A second one"))
    assert "two runbooks declare the key" in str(caught.value)


def test_us_rbs_015_every_definition_file_on_disk_is_named_in_the_tuple():
    """⚠ THE CHECK THAT MAKES THE SECOND LINE IMPOSSIBLE TO FORGET.

    `registry.load()` walks `definitions.DEFINITION_MODULES` rather than
    discovering modules, because `G115` refuses a computed import and the census
    is this module's boundary (see `definitions/__init__.py`). The cost is one
    extra line per runbook; this is what stops that line being forgotten.

    A file on disk that the tuple does not carry is a runbook that exists,
    imports cleanly, passes every other test, and **is not in the product** —
    exactly hard-won law 2. It fails HERE, naming the file.
    """
    from apps.runbooks import definitions

    folder = pathlib.Path(definitions.__file__).parent
    on_disk = {p.stem for p in folder.glob("*.py") if not p.stem.startswith("_")}
    declared = {m.__name__.rsplit(".", 1)[-1] for m in definitions.DEFINITION_MODULES}
    assert on_disk == declared, (
        f"definitions/ holds {sorted(on_disk - declared)} that DEFINITION_MODULES does not name, "
        f"and names {sorted(declared - on_disk)} that is not on disk. A runbook module missing "
        "from that tuple is a runbook the product does not have."
    )


def test_us_rbs_015_requires_must_name_a_registered_check():
    """`BR-RBS-027` — checked after loading, because import order is not declaration order."""
    scratch = RunbookRegistry()
    scratch.register(_check(key="caller", requires="a_check_that_does_not_exist"))
    with pytest.raises(RunbookContractError) as caught:
        scratch.validate_requires()
    assert "is not registered" in str(caught.value)
    assert "Never reached" in str(caught.value)


def test_us_rbs_015_requires_may_not_name_an_action():
    """Requiring an Action would let a Check cause a write by naming one."""
    scratch = RunbookRegistry()
    scratch.register(_action(key="dunning"))
    scratch.register(_check(key="caller", requires="dunning"))
    with pytest.raises(RunbookContractError) as caught:
        scratch.validate_requires()
    assert "which is an Action" in str(caught.value)


def test_us_rbs_015_requires_naming_a_registered_check_is_accepted():
    scratch = RunbookRegistry()
    scratch.register(_check(key="base"))
    scratch.register(_check(key="caller", requires="base"))
    scratch.validate_requires()


def test_us_rbs_015_categories_in_use_never_returns_a_category_holding_nothing():
    """`BR-RBS-025`, `TC-RBS-20` — a chip that filters to an empty list is dead UI."""
    scratch = RunbookRegistry()
    assert scratch.categories_in_use() == ()
    scratch.register(_check(key="one", category="billing"))
    scratch.register(_check(key="two", category="platform"))
    assert scratch.categories_in_use() == ("platform", "billing")
    assert "assets" not in scratch.categories_in_use()


# ── TC-RBS-15 over the LIVE registry, with its size printed ───────────────


def test_us_rbs_015_tc_rbs_15_live_registry_conforms(capsys, brazos):
    """Every REGISTERED runbook conforms — and the count is printed either way.

    ⚠ **THE COUNT IS PRINTED SO A PASS CANNOT MEAN TWO THINGS.** Over wave B's
    empty registry a pass meant *nothing was registered and nothing failed*,
    which is a very different sentence from *every runbook conforms* — and a
    check whose output cannot distinguish the two is worse than no check
    (hard-won law 7). Wave C registers the first runbook and the printed line
    says which.

    ⚠ **AND IT NEEDED AN EDIT AFTER ALL, WHICH THIS CASE PREDICTED WRONGLY.**
    It used to end *"the moment it lands, this case starts conforming it with no
    edit"*. That was true of the assertions and false of the FIXTURE: a real
    runbook reads real data through its seams, and every one of those reads is
    tenant-scoped, so with no tenant in context `tenancy.selectors._tenant_id`
    raises `AuthError` before a single step finishes. The tenant is the run's
    subject in the first place (`resolve()` returns one `SubjectRef` of type
    `tenant`), so running this without one was never going to work. Recorded
    rather than quietly patched, because the prediction is exactly the kind a
    later lane inherits and believes.
    """
    from core import tenancy as core_tenancy

    described = registry.describe()
    print(
        f"conformance: {described['count']} live runbook(s) registered "
        f"({described['checks']} Check(s), {described['actions']} Action(s)); "
        f"keys={described['keys']}; categories in use={described['categories_in_use']}"
    )
    with core_tenancy.tenant_context(brazos.id):
        for definition in registry.all():
            # ⚠ A FIXED BUSINESS DAY, NOT `date.today()` (`BR-TEN-043`, gate
            # `G6`). Runbook 8 declares `as_of` REQUIRED with no default — a
            # ladder may not read a clock, because a run re-taken for last
            # Tuesday must take last Tuesday's decision — and a clock read here
            # would also make this case's result depend on the day it runs.
            _conform(
                definition,
                tenant_id=brazos.id,
                overrides={"as_of": _dt.date(2026, 9, 7)},
            )
    assert "conformance:" in capsys.readouterr().out


def test_us_rbs_015_the_exemplars_conform():
    """The same five assertions, over the shapes wave C and wave L will ship."""
    check_result = _conform(_check())
    assert len(check_result.records) == 3
    assert [b["block"] for b in check_result.report] == ["kpis", "records"]

    action_result = _conform(_action())
    assert len(action_result.records) == 3


def test_us_rbs_015_an_actions_ports_carry_writers_and_its_CONTEXT_does_not():
    """Where *"nothing can be written"* lives after `CR-075` wave L.

    ⚠ **THIS CASE ASSERTED `bound_ports() == ()` UNTIL 2026-09-06.** That was
    phase 1's launch sentence, and wave L task `L2` is the task that ends it:
    nine of the thirteen declarations now carry a real writer, each one service
    function in the module that owns the table. **The promise did not go away —
    it moved one layer in**, to `executor.build_context`, which hands a step a
    writer-LESS copy of each port unless the runbook is on
    `engine.acts.LIVE_ENABLED_RUNBOOKS`. That set is **empty for the whole
    catalogue**, so a dry run and a live one both reach ports that cannot write
    and the step walks identical statements either way (`BR-RBS-003`).

    `tests/test_us_rbs_010_port_writers.py` pins the membership of both port
    sets by name and proves the switch works in BOTH directions — a case that
    only ever saw *unbound* would pass identically if `build_context` unbound
    everything unconditionally, which is a check that cannot fail.
    """
    action = _action()
    assert any(port.is_bound for port in action.port_declarations()), (
        "wave L binds queue_notice and apply_fee — a declaration with no writer "
        "would mean this case is quietly testing phase 1 again"
    )
    ctx = executor.build_context(action, mode="live")
    assert [port.is_bound for port in ctx.ports.values()] == [False, False]


def test_us_rbs_015_the_definition_document_records_callables_by_name_not_by_value():
    """What `runbook_versions.definition` stores — and it must be JSON-able."""
    import json

    document = _action().as_definition_document()
    json.dumps(document)
    assert document["ports"] == ["queue_notice", "apply_fee"]
    assert document["steps"] == [
        {"key": "decide_tier", "label": "Decide the tier", "mode": "per_record", "writes": True}
    ]
    assert "resolve" not in document


# ── the writers: open_run pins, close_run freezes ─────────────────────────


def test_us_rbs_015_open_run_pins_the_version_and_close_run_freezes_the_report(brazos):
    """`BR-RBS-038` and `BR-RBS-020`, end to end, on this module's own tables."""
    from apps.runbooks import services

    definition = _check()
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
    )
    run, result = services.run_to_completion(runbook, definition)

    assert run.status == models.RUN_STATUS_DONE
    assert run.version == 1
    assert run.scope_fingerprint == result.scope_fingerprint
    assert [b["block"] for b in run.report] == ["kpis", "records"]
    assert models.RunbookVersion.objects.filter(runbook=runbook).count() == 1


def test_us_rbs_015_running_unchanged_code_twice_does_not_mint_a_second_version(brazos):
    """A hundred deploys must not read as a hundred edits nobody made.

    ⚠ **THE SECOND HALF OF THIS CASE WAS INVERTED BY WAVE `E3` AND THE
    SUPERSESSION IS STATED RATHER THAN QUIETLY APPLIED (`DEF-RBS-4306`).** It
    used to assert that running EDITED code minted **v2** and that the run
    pinned it — which reads like versioning working and is `BR-RBS-038` upside
    down: *a change to a shipped template is OFFERED on a tenant's copy and
    never applied without a person accepting it*, and a run is not a person
    accepting anything. So the old assertion was a check written to REQUIRE the
    rule being broken, which is why nothing was red for a day.

    What is asserted now is the rule: the divergence mints nothing, the run is
    REFUSED rather than pinned against a version that did not produce it, and
    `services.accept_template_update` — a person pressing *Review →* — is the
    only thing that moves it to v2. The offer surface and the acceptance are
    covered in full by `tests/test_us_rbs_038_definition_surface.py`; what stays
    here is the conformance-level fact that the engine adopts nothing on its own.
    """
    from core import errors

    from apps.runbooks import services

    definition = _check()
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
    )
    services.run_to_completion(runbook, definition)
    services.run_to_completion(runbook, definition)
    assert models.RunbookVersion.objects.filter(runbook=runbook).count() == 1

    edited = _check(unit_of_work="account, one cycle")
    with pytest.raises(errors.BizError) as refused:
        services.run_to_completion(runbook, edited)
    assert refused.value.message_key == "runbooks.refusal.update_pending"
    assert models.RunbookVersion.objects.filter(runbook=runbook).count() == 1
    assert models.RunbookRun.objects.filter(runbook=runbook).latest("created_at").version == 1


def test_us_rbs_015_tc_rbs_16_a_thirteenth_block_marks_the_run_failed_at_close(brazos):
    """`TC-RBS-15`/`TC-RBS-16` — refused at CLOSE, and the run is marked failed.

    Refused at RENDER instead, the run would already read *done* and a clerk
    would meet a half-drawn screen with no way to tell whether the missing part
    mattered.
    """
    from apps.runbooks import services
    from apps.runbooks.engine.executor import RunResult

    definition = _check()
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
    )
    run = services.open_run(runbook, definition)
    smuggled = RunResult(
        runbook_key=definition.key,
        subjects=(),
        scope_fingerprint="deadbeef",
        guarded=(),
        set_results={},
        records=(),
        counts={},
        report=[{"block": "timeline", "payload": {}}],
        step_runs={},
    )
    with pytest.raises(RunbookContractError):
        services.close_run(run, smuggled)
    run.refresh_from_db()
    assert run.status == models.RUN_STATUS_FAILED
    assert run.report == []


def test_us_rbs_015_a_dry_run_of_a_check_writes_only_this_modules_own_tables(brazos):
    """`TC-RBS-15`'s *a Check wrote nothing* — asserted against the row counts.

    ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT.** It proves the Check's own run
    added rows to `runbooks`, `runbook_versions` and `runbook_runs` and to
    nothing else this module owns. It does NOT prove another module's table was
    untouched — that is `G115`'s job, statically, over every file in the module,
    and it is a stronger proof than counting rows in a fixture that has few.
    """
    from apps.runbooks import services

    definition = _check()
    runbook = models.Runbook.objects.create(
        tenant=brazos,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
    )
    services.run_to_completion(runbook, definition)

    assert models.RunbookRunRecord.objects.count() == 0
    assert models.WorkItem.objects.count() == 0
    assert models.CutoverPlan.objects.count() == 0
    assert models.CutoverPlanItem.objects.count() == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-015 · US-RBS-002 (EP-RBS-01; CR-075 wave B task B4)
# generated: 2026-09-06 by the CR-075 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave B) E=n/a(no screen in wave B) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_015_conformance.py · G115 · G10 (TC coverage)
# exceptions: the savepoint (TC-RBS-5) and tenant isolation cannot be proved on SQLite and are NOT asserted here — tests/test_rbs_savepoint_pg.py and tests/test_us_rbs_041_pg.py hold them
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
