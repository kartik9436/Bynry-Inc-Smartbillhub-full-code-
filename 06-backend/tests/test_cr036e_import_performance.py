# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (the CR-023 import runner)
# Change:   CR-036 · AMENDMENT 1 (e) — PO 2026-08-26, verbatim: *"It is taking
#           almost 30 -40 seconds from upload to Transform and transform to
#           Validate."* on 9,881 premises and then 9,881 units.
# Rules:    BR-MET-090 (the run's record is what it DID) · BR-MET-096 (ONE
#           runner) · CLAUDE.md hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""THE TWO THINGS THAT MADE STAGES 2 AND 3 SLOW, EACH PINNED SO IT CANNOT COME BACK.

Measured on live Postgres 16 in a dev container (NOT the PO's deployment), on
9,881 units against 9,957 premises already on file:

    stage 2 transform   13.58s -> 1.77s
    stage 3 validate    24.40s -> 1.99s

Both were **Python**, not the database: a set comprehension rebuilt inside a
per-row loop, and Django's `bulk_update` building one `CASE WHEN` branch per row
per column. Neither fix changes what the stages DECIDE — the full stage-1..3
output was dumped row by row before and after, on both targets, and the two
dumps are byte-identical (`mapped`, `outcome`, `problem`, `fix_hint`, every
rule's hit count and the run's counts).

⚠ **NEITHER CASE IS A TIMING ASSERTION.** A test that fails when a shared CI box
is busy teaches lanes to re-run it until it passes. Both assert the SHAPE that
made it slow — how many times a thing is built, and which writer is called — so
they fail deterministically the moment the shape returns.
"""

import pytest

from apps.metering import bulk_write, import_rules, import_runs, models

from tests.test_cr023_import_stages import ALL_ON, MAPPING
from tests.test_cr023_load_stage import _file
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


class _CountingSet(set):
    """A set that says how many times something has ITERATED it.

    Membership (`x in s`) does not iterate; a set COMPREHENSION over it does.
    That is exactly the difference between the fixed rule and the broken one.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


def _units_rule(code):
    return next(rule for rule in import_rules.UNITS_RULES if rule.code == code)


def _world_with(premise_nos):
    return import_rules.World(
        enabled_services=set(),
        premises_type_codes=set(),
        area_names=set(),
        existing_addresses=set(),
        existing_premise_nos=premise_nos,
    )


def test_cr036e__the_parent_premise_rule_reads_the_world_ONCE_not_once_per_row():
    """⚠ **THE ONE THAT COST 12.9 SECONDS.** `UNT.PARENT_PREMISE_ON_FILE` used to
    case-fold `world.existing_premise_nos` INSIDE its per-row loop, so its cost
    was rows x premises-already-on-file — and a utility that has just imported
    its premises is precisely the utility about to import its units.

    Measured directly, no database, before and after:

        rows   premises on file   before    after
        9,881            100      0.085s   0.013s
        9,881          1,000      0.748s   0.013s
        9,881          9,957     12.862s   0.007s

    RED on the original line: this case reports `iterations == 400`, one per row.
    """
    on_file = _CountingSet({f"BM-{100000 + i}" for i in range(1, 1001)})
    world = _world_with(on_file)
    rows = [
        {"row_no": i, "mapped": {"premises_ref": f"BM-{100000 + i}"}, "problems": {}}
        for i in range(1, 401)
    ]

    hits = import_rules.evaluate(_units_rule("UNT.PARENT_PREMISE_ON_FILE"), rows, world)

    assert hits == []
    assert on_file.iterations == 1, (
        f"the world's premise numbers were walked {on_file.iterations} times for "
        f"{len(rows)} rows — the case-fold is back inside the loop, and this rule "
        "is quadratic again"
    )


def test_cr036e__the_rule_still_rejects_the_rows_it_always_rejected():
    """The hoist is not allowed to change a single verdict. Same fixture, three
    rows: one whose parent is on file, one whose parent is not, one with none."""
    world = _world_with({"BM-100001"})
    rows = [
        {"row_no": 1, "mapped": {"premises_ref": "bm-100001"}, "problems": {}},
        {"row_no": 2, "mapped": {"premises_ref": "BM-999999"}, "problems": {}},
        {"row_no": 3, "mapped": {}, "problems": {}},
    ]

    hits = import_rules.evaluate(_units_rule("UNT.PARENT_PREMISE_ON_FILE"), rows, world)

    assert [hit.row_no for hit in hits] == [2, 3]
    assert hits[0].problem == "Parent premise BM-999999 was not loaded."
    assert hits[1].problem == "This row names no parent premise."


def test_cr036e__stage_2_and_stage_3_write_their_rows_through_the_batch_writer(
    dana, brazos, monkeypatch
):
    """**BUILT IS NOT WIRED (hard-won law 2).** A faster writer nothing calls is
    a file, not a fix — so this asserts the two stages actually route through it,
    with the tenant and the run named in the call.

    RED before the change: `calls == []`, because both stages called
    `QuerySet.bulk_update` directly.
    """
    calls = []
    original = bulk_write.update_import_rows

    def recorder(objs, fields, *, tenant_id, run_id, batch_size=1000):
        rows = list(objs)
        calls.append(
            {"fields": list(fields), "tenant_id": tenant_id, "run_id": run_id, "rows": len(rows)}
        )
        return original(rows, fields, tenant_id=tenant_id, run_id=run_id, batch_size=batch_size)

    monkeypatch.setattr(bulk_write, "update_import_rows", recorder)

    with tenant_ctx(brazos):
        run = import_runs.extract(
            dana,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "cr036e.csv",
                "content": _file(6),
                "session_ref": "sess_cr036e",
                "ip": "71.42.108.14",
            },
        )
        import_runs.transform(dana, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
        import_runs.validate(dana, run["id"])

    assert len(calls) == 2, "stage 2 and stage 3 each write their rows exactly once"
    assert calls[0]["fields"] == [
        "mapped",
        "source_key",
        "outcome",
        "problem",
        "fix_hint",
        "updated_at",
    ]
    assert calls[1]["fields"] == ["outcome", "problem", "fix_hint", "updated_at"]
    for call in calls:
        assert call["rows"] == 6
        assert str(call["tenant_id"]) == str(brazos.id)
        assert str(call["run_id"]) == str(run["id"])


def test_cr036e__the_writer_refuses_a_column_nobody_declared_a_cast_for(dana, brazos):
    """Fail closed (hard-won law 3). A new `import_run_rows` column reaches this
    writer as a REFUSAL, never as a silently skipped write."""
    with tenant_ctx(brazos):
        run = import_runs.extract(
            dana,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "cr036e2.csv",
                "content": _file(2),
                "session_ref": "s",
                "ip": "71.42.108.14",
            },
        )
        rows = list(models.ImportRunRow.objects.filter(run_id=run["id"]))
        with pytest.raises(bulk_write.UnknownImportRowColumn):
            bulk_write.update_import_rows(rows, ["row_no"], tenant_id=brazos.id, run_id=run["id"])
