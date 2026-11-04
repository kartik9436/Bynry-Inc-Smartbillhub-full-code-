# ── Trace ──────────────────────────────────────────────
# Change:   CR-077 — import starters for *"Premises, Units, Meters, Sub
#           meter,s Assets, Parts, Accounts, Reading"* (PO 2026-09-07). Parts
#           was handed back as an architecture question; the answer is in
#           12-governance/02-decision-log.md of that day, "HOW PARTS GETS AN
#           IMPORT".
# Rules:    BR-MET-096 (a new target is a PARAMETER, never a second runner) ·
#           BR-WRK-002 / G78 (nothing outside apps/work writes `parts`) ·
#           DEF-1108 (the import writer is UNDECORATED; the role is checked
#           once at load()) · DEF-075 (a seam answering None means *cannot
#           answer*) · CLAUDE.md hard-won law 5 (one implementation)
# Impacts:  apps/metering/import_runs.py · apps/metering/import_rules.py ·
#           apps/metering/seams.py · apps/work/import_writer.py
# ───────────────────────────────────────────────────────
"""Parts as the seventh target — the properties a later lane could break.

⚠ **THE ROW-WRITING HALF IS PROVED ON POSTGRESQL AND NOT HERE.** The figures
are in the decision-log row: on a tenant provisioned through the real sign-up
path, 4 rows in, 3 created, 1 rejected by name for having no part number,
`rejected_at_write` 0 — and then clicked through the browser, 24 checks, in
`10-scripts/cr083_integrations_and_parts_walkthrough.mjs`. What is asserted
here is the wiring: that there is ONE runner, that the boundary is kept by
construction, and that the column set matches the writer's allow list — which
is the one property that fails SILENTLY, rehearsing clean and rejecting every
row at the write.
"""

from __future__ import annotations

import inspect

from apps.metering import import_rules, import_runs, seams
from apps.work import import_writer, services as work_services


def test_parts_is_a_target_of_the_one_runner_and_not_a_second_one():
    """BR-MET-096, PO 2026-08-21: *"same process for premises and Unit - only
    at tranform stage we differntate field"*. A second staging/validation/commit
    engine would be two sources of truth for one screen."""
    assert import_runs.TARGET_PARTS == "parts"
    assert import_runs.TARGET_PARTS in import_runs.TARGETS
    # ⚠ **AMENDED 2026-09-22 — 7 → 8, the EIGHTH target (`payments`, `P1.1`).**
    # This is the count moving because a target ARRIVED, which is the one
    # lawful reason to touch it: the number exists so that a target registered
    # without its dict entries fails here rather than at a clerk's commit, and
    # a lane that relaxes it instead of moving it has deleted the check.
    assert len(import_runs.TARGETS) == 8


def test_the_target_is_declared_in_every_by_target_table():
    """A target registered in `TARGETS` and missing from one of these dicts is
    a run that starts and then behaves like a different target — the shape
    `DEDUPE_KEY_BY_TARGET` and `SKIP_REQUIRED_BY_TARGET` exist to make explicit."""
    target = import_runs.TARGET_PARTS
    assert target in import_runs.EXPLICIT_COLUMNS_BY_TARGET
    assert target in import_runs.ALIASES_BY_TARGET
    assert target in import_runs.DEFAULT_MAPPING_TEMPLATES
    assert target in import_runs.DEDUPE_KEY_BY_TARGET
    assert target in import_runs.SKIP_REQUIRED_BY_TARGET
    assert target in import_rules.PLATFORM_CATALOG


def test_every_offered_column_is_one_the_writer_will_actually_take():
    """⚠ **THE CHECK THAT WOULD HAVE SAVED AN HOUR, AND THE ONE NO STAGE-3 RULE
    CAN MAKE.** `work.services._clean_part` REFUSES an unknown field rather
    than ignoring it (`US-WRK-010` TC-5), so a column this template offers that
    the writer does not take rehearses CLEAN and then rejects EVERY ROW at the
    write. It happened on 2026-09-07 with `active`, which `parts` really has as
    a column and `create_part` sets itself.

    The allow list is read out of the writer's own source rather than copied,
    because a copy would agree only with itself — which is how the column got
    offered in the first place.
    """
    source = inspect.getsource(work_services._clean_part)
    line = next(l for l in source.split("\n") if "allowed = {" in l)
    allowed = {token.strip().strip('"').strip("'") for token in
               line.split("{", 1)[1].rsplit("}", 1)[0].split(",")}
    offered = {column["target"] for column in import_runs.PARTS_COLUMNS}
    assert offered <= allowed, f"the template offers {sorted(offered - allowed)}, which the writer refuses"


def test_the_required_columns_are_the_ones_the_writer_demands():
    required = {c["target"] for c in import_runs.PARTS_COLUMNS if c["required"]}
    assert required == {"part_no", "name", "unit_of_measure"}


def test_every_column_carries_a_worked_sample_cell():
    """CR-025: the downloadable template is a header row and ONE worked row.
    `DEF-962` is what a column with no sample ships as — a blank cell in the
    file a utility builds from."""
    for column in import_runs.PARTS_COLUMNS:
        if column["target"] == "category":
            continue  # tenant-specific, and it samples its own live list
        assert column.get("sample"), f"{column['target']} ships a blank template cell"


def test_nothing_outside_work_names_the_parts_table():
    """`BR-WRK-002` / `G78`. The boundary is kept by CONSTRUCTION — there is no
    ORM statement in the runner to review — and this asserts it rather than
    trusting the reading."""
    for module in (import_runs, import_rules, seams):
        body = inspect.getsource(module)
        for forbidden in ("work_models.Part", "from apps.work import models"):
            assert forbidden not in body, f"{module.__name__} reaches into work's models"


def test_the_writer_is_undecorated_because_a_worker_carries_no_role():
    """`DEF-1108`: a deferred load runs under `_JobActor` — *"an id, and no
    role, BY DESIGN"* — so a `@require_role` writer would refuse every row of
    every large migration. The role is checked once at `load()`."""
    for fn in (import_writer.create_part_from_import,
               import_writer.update_part_from_import,
               import_writer.rollback_part_from_import):
        assert not hasattr(fn, "__wrapped__"), f"{fn.__name__} is decorated"


def test_the_load_and_the_rollback_both_have_a_parts_branch():
    """⚠ **`rollback()`'s OWN DOCSTRING DEMANDS THIS OF A SEVENTH TARGET**, and
    a missing branch is SILENT: the run would fall through to the
    premises/units path, key every row as `premises|label`, skip all of them,
    spend the rollback point and report success."""
    body = inspect.getsource(import_runs)
    assert "_load_parts_rows(actor, run, write_mode, data, reporter)" in body
    rollback = inspect.getsource(import_runs.rollback)
    assert "TARGET_PARTS" in rollback
    assert "rollback_part_from_import" in rollback


def test_the_write_mode_governs_the_already_on_file_rule():
    """One code, three behaviours — the same shape every other target has.
    `Insert new only` REJECTS; `Insert & update` is the row the mode exists for."""
    assert "part_no_on_file" in import_rules.NUMBER_ON_FILE_KINDS
    insert = {r.code: r for r in import_rules._for_write_mode(import_rules.PARTS_RULES, "insert")}
    assert insert["PRT.NUMBER_ON_FILE"].severity == import_rules.ERROR
    assert insert["PRT.NUMBER_ON_FILE"].action == import_rules.REJECT_ROW
    plain = {r.code: r for r in import_rules.PARTS_RULES}
    assert plain["PRT.NUMBER_ON_FILE"].severity == import_rules.WARNING


def test_every_rule_has_an_evaluator():
    """A declared rule whose `rule_kind` nothing implements is a rule that
    never fires and a rehearsal that promises more than it delivers."""
    for rule in import_rules.PARTS_RULES:
        assert rule.rule_kind, f"{rule.code} declares no rule_kind"
        assert rule.rule_kind in import_rules.EVALUATORS, f"{rule.code}: no evaluator for {rule.rule_kind}"


def test_a_blank_category_is_lawful_and_an_unknown_one_is_not():
    """`work.services._clean_part` writes `category = None` for a blank cell, so
    a rule firing on a blank would reject rows the load would have written."""
    rule = next(r for r in import_rules.PARTS_RULES if r.code == "PRT.CATEGORY_IN_LOOKUP")
    world = import_rules.World(
        enabled_services=set(), premises_type_codes=set(), area_names=set(),
        existing_premise_nos=set(), existing_addresses=set(),
        part_categories={"fittings": "Fittings", "fit": "Fittings"},
    )
    rows = [
        {"row_no": 1, "mapped": {"part_no": "PT-1", "category": ""}},
        {"row_no": 2, "mapped": {"part_no": "PT-2", "category": "Fittings"}},
        {"row_no": 3, "mapped": {"part_no": "PT-3", "category": "FIT"}},
        {"row_no": 4, "mapped": {"part_no": "PT-4", "category": "Nonesuch"}},
    ]
    hits = import_rules.EVALUATORS[rule.rule_kind](rows, world, rule)
    assert [h.row_no for h in hits] == [4]
    assert "Nonesuch" in hits[0].problem


def test_an_unanswerable_category_index_judges_nothing():
    """`DEF-075`: an empty index is *this tenant has no categories* OR *work
    could not answer*, and this rule cannot tell them apart. Rejecting every
    categorised row on an unanswerable read would turn a wiring fault into a
    data-quality report."""
    rule = next(r for r in import_rules.PARTS_RULES if r.code == "PRT.CATEGORY_IN_LOOKUP")
    world = import_rules.World(
        enabled_services=set(), premises_type_codes=set(), area_names=set(),
        existing_premise_nos=set(), existing_addresses=set(), part_categories={},
    )
    rows = [{"row_no": 1, "mapped": {"part_no": "PT-1", "category": "Anything"}}]
    assert import_rules.EVALUATORS[rule.rule_kind](rows, world, rule) == []


def test_a_row_with_no_part_number_says_we_will_not_invent_one():
    """Premises, units and meters all take their number from the tenant's
    series; there is no `part` series, so an operator who has just loaded those
    would otherwise wait for a number that is never coming."""
    rule = next(r for r in import_rules.PARTS_RULES if r.code == "PRT.PART_NO_REQUIRED")
    world = import_rules.World(
        enabled_services=set(), premises_type_codes=set(), area_names=set(),
        existing_premise_nos=set(), existing_addresses=set(),
    )
    rows = [{"row_no": 1, "mapped": {"part_no": ""}}, {"row_no": 2, "mapped": {"part_no": "PT-9"}}]
    hits = import_rules.EVALUATORS[rule.rule_kind](rows, world, rule)
    assert [h.row_no for h in hits] == [1]
    assert "yours, not ours" in hits[0].fix_hint
    assert import_runs.TARGET_PARTS not in import_runs.TARGET_SERIES


def test_the_screen_offers_the_target_the_server_offers():
    """CLAUDE.md hard-won law 2 — the shape that put six services on the sign-up
    screen for ten days. A target the server serves and the screen has no kind
    for is an upload nobody can start."""
    import io
    from pathlib import Path

    here = Path(__file__).resolve().parents[2]
    kinds = io.open(here / "07-frontend/src/components/workflow/kinds.ts", encoding="utf-8").read()
    assert '  parts: {' in kinds
    assert '| "parts"' in kinds
    endpoints = io.open(here / "07-frontend/src/api/endpoints.ts", encoding="utf-8").read()
    assert '| "parts"' in endpoints
    app = io.open(here / "07-frontend/src/App.tsx", encoding="utf-8").read()
    assert '<ImportWorkflowPage target="parts" />' in app


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-077 (PO 2026-09-07) · decision log 2026-09-07 "HOW PARTS GETS AN IMPORT" · US-WRK-010
# generated: 2026-09-07 by the CR-077 parts-import lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr077_parts_import.py · the PostgreSQL run and the browser walkthrough carry the row-writing half
# exceptions: no row-writing case here — the writes are proved on a real database and in a browser, both quoted in the decision-log row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
