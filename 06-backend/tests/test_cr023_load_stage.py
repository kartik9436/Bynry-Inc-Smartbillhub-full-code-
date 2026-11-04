# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 W2 — stages 4 and 5 of the recorded ETL runner,
#           and the PRM-04 run list)
#           Screens: WFL-01.premises.4–5, WFL-01.units.4–5, PRM-04
# Rules:    BR-MET-085 (a premises import loads premises and NOTHING else) ·
#           BR-MET-096 (ONE runner, two targets) · BR-MET-098 (approval at 5%
#           OR more than 10 rejected rows, whichever comes first; the approver
#           is an Owner or an Admin) · BR-MET-099 ("replace the batch"
#           DEACTIVATES what the file no longer carries, REFUSES anything
#           occupied, NEVER deletes, and shows all three numbers first) ·
#           BR-MET-100 (a units row naming a missing plan LOADS, flagged, and
#           is COUNTED AND FINDABLE) · BR-MET-035 (roles, server-enforced) ·
#           CLAUDE.md hard rule 4 (financial immutability — nothing is deleted)
#           · CLAUDE.md hard rule 6 (idempotency — a second commit of one run)
# Journeys: the premises migration — a utility's first 431 rows
# ───────────────────────────────────────────────────────
"""Stage 4 · LOAD and stage 5 · RESULT — the half of CR-023 that WRITES.

**THE CLAIM `test_cr023_import_stages.py` PROVES IS THAT STAGES 1–3 WRITE
NOTHING. THE CLAIM THIS FILE PROVES IS THE OTHER HALF OF THE SAME SENTENCE:
that stage 4's REHEARSAL writes nothing either, and that the commit which
follows it does exactly what the rehearsal said it would.** r10 prints the
promise under its own title — *"Five stages · nothing is written until you
commit at stage four"* — and a dry run that could write, or that disagreed with
its own commit, would break it just as completely as a validate stage that
created a row.

WHAT WAS PROVED RED FIRST (hard-won law 7)
------------------------------------------
`test_the_dry_run_writes_nothing_in_any_of_the_three_modes` was proved by
making `import_runs.dry_run` deactivate the rows its `replace` branch counts —
five characters, `.save()` on the row it was about to count — and this file
reported, verbatim:

    E   AssertionError: a DRY RUN deactivated 2 premises — the rehearsal is
        not allowed to touch a row
    E   assert ['active', 'inactive', 'inactive'] == ['active', 'active', 'active']

`test_the_approval_bar_refuses_by_name_at_the_ROW_bar` was proved by changing
`import_runs.APPROVAL_ROWS` from `10` to `100`: the 11-reject run then loaded
silently, and the assertion reported

    E   Failed: DID NOT RAISE <class 'core.errors.BizError'>

Both injections were removed and both assertions went green.

WHAT IS *NOT* PROVED HERE, STATED RATHER THAN LEFT SILENT
---------------------------------------------------------
* **The `>=` in the percentage bar.** `BR-MET-098` says approval is needed when
  rejections *"exceed 5% of the batch"*; `import_runs.dry_run` computes
  `(rejected * 100) >= (APPROVAL_PCT * checked)`, so a run at EXACTLY 5.00% —
  1 reject in 20 rows — also stops. That is one row's difference on one batch
  size and the safer direction, but it is not what the rule says. The cases
  below deliberately sit clear of the boundary (20% and 4.58%) so they measure
  the bars rather than the tie, and the tie is filed as `DEF-547` against
  `import_runs.py` rather than asserted either way from here.
* **The approver's role at the SERVICE layer — CLOSED, `DEF-545`.** This bullet
  read *"`import_runs.load` reads `approved` as a bare boolean … `DEF-545`
  carries the service-layer half"* until 2026-08-27. It does not any more:
  `_load_locked` now refuses a crossed bar approved by anyone but a System
  Admin, with `BR-MET-098`'s own name on the refusal, so the rule is enforced
  in BOTH layers (`BR-SHL-025`, defence in depth) rather than only at the edge
  a service-layer caller walks past. The engine's refusal is deliberately
  NARROWER than `api.py`'s — it fires only where the bar is actually crossed,
  because that is where `BR-MET-098` speaks. See the refusal's own comment.
"""

import pytest

from apps.metering import import_runs, models
from apps.metering import api as metering_api
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_rows,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_cr023_import_stages import (
    ALL_ON,
    HEADERS,
    MAPPING,
    UNITS_MAPPING,
    _csv,
    _row,
    seed_units_world,
    units_csv,
)

pytestmark = pytest.mark.django_db


# ── the smallest honest fixtures ────────────────────────────────────────────
#
# ⚠ **THE §16 FILE IS 431 ROWS AND MOST OF THESE CASES DO NOT NEED IT.** The
# approval bars are ARITHMETIC over two numbers, so a case that measures them
# wants a file whose two numbers are chosen, not one whose two numbers happen
# to be r10's. `premises_csv()` is still used where the point IS r10's own
# arithmetic — the full load, and the receipt it produces.


def _file(rows: int, *, bad: int = 0, typed: bool = False, start: int = 1) -> str:
    """`rows` premises, of which `bad` carry NO ADDRESS.

    A blank `ADDR1` is `PRM.ADDRESS_REQUIRED` — a TIER 1 structural error, the
    one kind of rejection no utility can configure away (`BR-MET-090`). So the
    reject COUNT here is a property of the file and not of anyone's settings,
    which is what makes it usable as the input to an approval-bar test.

    ⚠ **`PROP_TYPE` IS BLANK BY DEFAULT AND THAT IS `DEF-540`, NOT A CHOICE.**
    `import_runs._record_from` says *"`premises_type` carries a resolved CODE
    … the column holds a code, so it travels as-is"* and the column is a
    **ForeignKey** (`models.Premises.premises_type`, `db_column
    premises_type_id`). So a row whose type RESOLVES cannot be created at all:
    `Premises(premises_type="single_family")` raises
    `ValueError: Cannot assign "'single_family'" … must be a "PremisesType"
    instance`. The engine suite never saw it because no test in this repo had
    ever run the LOAD, and `typed=True` below is the case that pins it.
    """
    made = [
        _row(index, **({} if typed else {"PROP_TYPE": ""})) for index in range(start, start + rows)
    ]
    for index in range(bad):
        made[index]["ADDR1"] = ""
    return _csv(made, HEADERS)


def _validated(actor, *, content=None, target="premises", mapping=None, file_name=None):
    """A run carried to `validated` through the SAME three functions a screen
    calls — never a hand-built row. `BR-MET-096`: one runner, two targets."""
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": file_name or f"{target}_load_case.csv",
            "content": content if content is not None else _file(20),
            "session_ref": "sess_2b41",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {
            "mapping": mapping or (MAPPING if target == "premises" else UNITS_MAPPING),
            "row_handling": ALL_ON,
        },
    )
    import_runs.validate(actor, run["id"])
    return run["id"]


def _counts() -> tuple[int, int, int]:
    return (
        models.Premises.objects.count(),
        models.Unit.objects.count(),
        models.ServicePoint.objects.count(),
    )


def _statuses() -> list[str]:
    return sorted(models.Premises.objects.values_list("status", flat=True))


# ═══════════════════════════════════════════════════════════════════════════
# THE SAFETY PROPERTY, CONTINUED PAST STAGE 3
# ═══════════════════════════════════════════════════════════════════════════


def test_the_dry_run_writes_nothing_in_any_of_the_three_modes(brazos, marcus, replace_reenabled):
    """r10's promise reaches stage FOUR, not stage three.

    ⚠ `replace` is the mode this case exists for. It is the only rehearsal that
    has to LOOK at rows it did not import — everything on file and not in the
    file — and looking at a row is one keystroke away from retiring it. Proved
    RED by giving `dry_run`'s replace branch the `.save()` its commit has; the
    failure is quoted in this module's docstring.
    """
    with tenant_ctx(brazos):
        make_premises(marcus, address_line="1 Existing St")
        make_premises(marcus, address_line="2 Existing St")
        run_id = _validated(marcus)
        before, statuses_before = _counts(), _statuses()

        figures = {
            mode: import_runs.dry_run(marcus, run_id, mode)
            for mode in ("insert", "upsert", "replace")
        }

        assert _counts() == before, "a DRY RUN created or removed a row"
        assert _statuses() == statuses_before, (
            f"a DRY RUN deactivated {statuses_before.count('active') - _statuses().count('active')}"
            " premises — the rehearsal is not allowed to touch a row"
        )
        # …and it did its own work, so this cannot pass by doing nothing.
        assert figures["insert"]["will_create"] == 20
        assert figures["replace"]["will_deactivate"] == 2
        assert models.RollbackPoint.objects.count() == 0


def test_a_run_is_still_unwritten_after_an_approval_refusal(brazos, marcus):
    """A refused commit is not a partial commit. The whole of `_load_locked`
    is one `atomic` block for this reason — *"a half-loaded file is the one
    outcome nobody can undo by hand"*."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(10, bad=2))
        before = _counts()
        with pytest.raises(errors.BizError):
            import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert _counts() == before
        assert import_runs.read_run(run_id, with_rules=False)["status"] == "validated"


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-098 — THE TWO BARS, AND WHICH ONE STOPPED YOU
# ═══════════════════════════════════════════════════════════════════════════


def test_the_ratified_approval_figures_are_5_percent_and_10_rows(brazos, marcus):
    """HUMAN-GUIDE §6: a ratified figure gets a test so drift goes RED.

    ⚠ **BOTH NUMBERS ARE THE RULE'S, NOT r10's.** Until the PO ruled on
    2026-08-21 the `5%` on the screen was the prototype's drawing and the
    screen said so; the hedge came off with the ruling, and `10` rows is the
    second bar the ruling ADDED — *"a 5,000-row migration with 200 rejects
    (4%) would sail through unseen"*.
    """
    assert import_runs.APPROVAL_PCT == 5
    assert import_runs.APPROVAL_ROWS == 10
    with tenant_ctx(brazos):
        figures = import_runs.dry_run(marcus, _validated(marcus), "insert")
        assert figures["approval"]["threshold_pct"] == 5
        assert figures["approval"]["threshold_rows"] == 10


def test_the_approval_bar_refuses_by_name_at_the_PERCENT_bar(brazos, marcus):
    """10 rows, 2 rejected — **20%**, and 2 is nowhere near the 10-row bar.

    So the ONLY thing that can stop this run is the percentage, and the refusal
    says which: `because == "percent"`. `BR-MET-098`'s whole argument is that
    one bar cannot serve both file sizes, and a refusal that did not name the
    bar it crossed would leave an operator guessing which number to change.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(10, bad=2))
        figures = import_runs.dry_run(marcus, run_id, "insert")
        assert figures["approval"]["required"] is True
        assert figures["approval"]["because"] == "percent"
        assert (figures["approval"]["rejected"], figures["approval"]["of_rows"]) == (2, 10)

        with pytest.raises(errors.BizError) as refusal:
            import_runs.load(marcus, run_id, {"write_mode": "insert"})
        # BY NAME: the rule, and BOTH bars beside the run's own numbers.
        assert refusal.value.br_ref == "BR-MET-098"
        assert refusal.value.message_key == "metering.import.approval_required"
        assert refusal.value.params == {"pct": 5, "rows": 10, "rejected": 2, "of_rows": 10}
        assert _counts() == (0, 0, 0)


def test_the_approval_bar_refuses_by_name_at_the_ROW_bar(brazos, marcus):
    """240 rows, 11 rejected — **4.58%**, UNDER the percentage bar and OVER the
    row bar. This is `BR-MET-098`'s second clause in one file: without it,
    *"a 5,000-row migration with 200 rejects (4%) would sail through unseen"*.

    Proved RED by moving `APPROVAL_ROWS` to 100 — the run then loaded silently.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(240, bad=11))
        figures = import_runs.dry_run(marcus, run_id, "insert")
        # The percentage bar is genuinely NOT crossed, or this proves nothing.
        assert 11 * 100 < import_runs.APPROVAL_PCT * 240
        assert figures["approval"]["required"] is True
        assert figures["approval"]["because"] == "rows"

        with pytest.raises(errors.BizError) as refusal:
            import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert refusal.value.br_ref == "BR-MET-098"
        assert refusal.value.params["rejected"] == 11
        assert _counts() == (0, 0, 0)


def test_a_clean_run_needs_no_approval_and_loads(brazos, marcus):
    """r10's own worked run is *"1 rejected of 246"* — 0.41% and 1 row, under
    both bars — and it must NOT stop. A gate that fires on a good file is the
    rule staff learn to route around, which is the failure `BR-MET-098` names."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(246, bad=1))
        figures = import_runs.dry_run(marcus, run_id, "insert")
        assert figures["approval"]["required"] is False
        assert figures["approval"]["because"] is None
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert receipt["receipt"]["loaded"] == 245
        assert receipt["receipt"]["rejected"] == 1


def test_approving_the_load_lets_it_through(brazos, dana, marcus):
    """The bar is a SECOND APPROVAL, not a ban. With `approved` set the same
    run commits, and the figures the rehearsal printed are the ones it wrote.

    ⚠ **THE APPROVER IS `dana`, NOT `marcus`, AND THAT IS `DEF-545`.** This
    test read `import_runs.load(marcus, …, approved=True)` until 2026-08-27 —
    Marcus Vega is a Billing Clerk, and the case it was quietly asserting was a
    clerk crossing `BR-MET-098`'s bar and being their own second pair of eyes.
    The clerk keeps the LOAD (they extract, map, validate and commit this run);
    what they may not do is APPROVE one. The refusal is the test below.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(10, bad=2))
        rehearsed = import_runs.dry_run(marcus, run_id, "insert")
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["receipt"]["loaded"] == rehearsed["will_create"] == 8
        assert models.Premises.objects.count() == 8


def test_def545__a_billing_clerk_may_not_be_their_own_second_pair_of_eyes(brazos, marcus):
    """`BR-MET-098`: *"THE APPROVER IS THE SAME PAIR OF ROLES AS THE RATE-CHANGE
    SECOND APPROVAL (BR-RAT-091's 10 percent bar): Owner or Admin"*.

    THE SERVICE LAYER, not the route — `api.py` has refused this at the edge
    since CR-023 W2, and a service-layer caller walks straight past it. Same
    run as the test above, same file (10 rows, 2 rejected, 20% — over the
    percent bar), same `approved: True`; only the actor's role differs.

    ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN** (hard-won law 7). With the
    role check removed from `_load_locked` this reported, verbatim:

        E       Failed: DID NOT RAISE <class 'core.errors.BizError'>
        FAILED tests/test_cr023_load_stage.py::
               test_def545__a_billing_clerk_may_not_be_their_own_second_pair_of_eyes

    and the clerk's self-approved load wrote 8 premises rows.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(10, bad=2))
        assert import_runs.dry_run(marcus, run_id, "insert")["approval"]["required"] is True
        with pytest.raises(errors.BizError) as refusal:
            import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert refusal.value.br_ref == "BR-MET-098"
        assert refusal.value.message_key == "metering.import.approver_role"
        # NOTHING WAS WRITTEN — a refused approval is not a partial load.
        assert _counts() == (0, 0, 0)


def test_def545__a_clean_run_still_loads_for_a_clerk_who_ticked_approved(brazos, marcus):
    """THE NARROWNESS OF THE REFUSAL ABOVE, asserted so nobody widens it by
    accident.

    `BR-MET-098` names an approver for a load that NEEDS approving. On a clean
    run — r10's own *"1 rejected of 246"*, 0.41% and 1 row, under both bars —
    there is no approval to give, `approved` grants nothing, and refusing it
    would be a rule nobody has ruled. `api.py` is stricter at the edge on
    purpose (it refuses the flag outright from a non-admin); the ENGINE refuses
    exactly the hazard and no more.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(246, bad=1))
        assert import_runs.dry_run(marcus, run_id, "insert")["approval"]["required"] is False
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["receipt"]["loaded"] == 245


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-099 — REPLACE DEACTIVATES, SKIPS THE OCCUPIED, AND NEVER DELETES
# ═══════════════════════════════════════════════════════════════════════════


# ── CR-042 — REACHING A WITHDRAWN MODE ON PURPOSE ───────────────────────────
#
# ⚠ **READ THIS BEFORE COPYING IT.** `replace` was withdrawn from every import
# on 2026-08-27 (PO: *"replace option is not required"*), and `import_runs`
# refuses it BY NAME at both entry points. On this rail the mode had REAL
# behaviour — BR-MET-099's *deactivate what the file no longer carries, skip
# anything occupied, never delete*, a CONFIRMED PO ruling of 2026-08-21 with its
# own worked figure — and that behaviour is deliberately KEPT and unreachable
# while **OQ-580** asks the PO how a utility retires a premise it no longer
# serves.
#
# **Kept code that nothing exercises rots.** So these tests re-enable the mode
# for their own duration and keep proving the behaviour works. This is NOT a
# production backdoor: it is a fixture that empties the withdrawn list, in a
# test file, and every other test in this module still meets the refusal.
#
# The alternative — skipping them — would have left BR-MET-099's loop
# uncovered, which is worse than an explicit re-enable that names its reason.
@pytest.fixture
def replace_reenabled(monkeypatch):
    monkeypatch.setattr(import_runs, "WITHDRAWN_WRITE_MODES", ())
    monkeypatch.setattr(import_runs, "WRITE_MODES", ("insert", "upsert", "replace"))
    return "replace"


def test_cr042__the_withdrawn_mode_is_refused_at_BOTH_entry_points(brazos, marcus):
    """⛔ **CR-042 — AND THIS IS THE TEST THAT GUARDS THE ONES BELOW.**

    Without it, `replace_reenabled` would silently become the only statement
    this module makes about the mode, and a reader would conclude it is still
    offered. Here the refusal is asserted with NO fixture in the way — the state
    a real caller meets.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus)
        for call in (
            lambda: import_runs.dry_run(marcus, run_id, "replace"),
            lambda: import_runs.load(marcus, run_id, {"write_mode": "replace"}),
        ):
            with pytest.raises(errors.BizError) as caught:
                call()
            assert caught.value.br_ref == "OQ-580"


def test_replace_states_all_three_numbers_before_it_commits(brazos, marcus, replace_reenabled):
    """`BR-MET-099` verbatim: *"the run must say, in words, before the commit:
    '69 premises are on file and not in this file. 41 have active accounts and
    will be skipped. 28 will be deactivated.'"*

    So the rehearsal must serve THREE numbers, and they must reconcile:
    `not_in_file = skipped_occupied + will_deactivate`. A screen that had to
    subtract two of them to get the third would be doing arithmetic the loader
    is not doing, which is the shape `DEF-380` was filed for.
    """
    with tenant_ctx(brazos):
        for index in range(3):
            make_premises(marcus, address_line=f"{index} Legacy Row")
        run_id = _validated(marcus)

        figures = import_runs.dry_run(marcus, run_id, "replace")

        assert figures["not_in_file"] == 3
        assert figures["skipped_occupied"] == 0
        assert figures["will_deactivate"] == 3
        assert figures["not_in_file"] == figures["skipped_occupied"] + figures["will_deactivate"]
        # ⚠ And `insert`/`upsert` serve NONE of the three, because none of them
        # is true of those modes — an absent figure beats a zero that reads as
        # "nothing will be retired" on a mode that retires nothing by design.
        assert "will_deactivate" not in import_runs.dry_run(marcus, run_id, "insert")


def test_replace_DEACTIVATES_and_NEVER_DELETES(brazos, marcus, replace_reenabled):
    """Hard rule 4, and `BR-MET-099`'s own words: *"DELETION IS NOT AVAILABLE
    AND COULD NOT BE EVEN IF IT WERE RULED"* — an issued invoice was written
    against that premise.

    The assertion is therefore on the ROW COUNT as much as on the status: three
    legacy premises are still THERE after the run, and they are `inactive`.
    """
    with tenant_ctx(brazos):
        legacy = [
            models.Premises.objects.get(
                pk=make_premises(marcus, address_line=f"{i} Legacy Row")["id"]
            )
            for i in range(3)
        ]
        run_id = _validated(marcus)

        import_runs.load(marcus, run_id, {"write_mode": "replace"})

        for row in legacy:
            row.refresh_from_db()
            assert row.status == "inactive", "replace must DEACTIVATE what the file dropped"
            assert row.deleted_at is None, "replace must NEVER delete (hard rule 4)"
        assert models.Premises.objects.filter(pk__in=[row.pk for row in legacy]).count() == 3
        # The 20 rows of the file are on file and ACTIVE beside them.
        assert models.Premises.objects.count() == 23


def test_replace_SKIPS_a_row_that_is_occupied_and_says_how_many(brazos, marcus, replace_reenabled):
    """`BR-MET-099`: *"REFUSES ANYTHING OCCUPIED"*, and reports it rather than
    skipping it silently — a rollback the operator believes was complete is
    worse than one that says what it left behind.

    ⚠ **OCCUPANCY IS THE CUSTOMERS SEAM, NOT A COLUMN.** `units` has none by
    design (`BR-MET-036`), so this case makes the seam answer for ONE unit
    rather than creating an account through a module this lane does not own —
    what is under test is `import_runs`'s use of the answer, not customers'
    ability to produce it. The seam's real implementation is exercised by
    `apps/customers`' own suite.
    """
    with tenant_ctx(brazos):
        occupied = models.Premises.objects.get(
            pk=make_premises(marcus, address_line="1 Occupied Row")["id"]
        )
        vacant = models.Premises.objects.get(
            pk=make_premises(marcus, address_line="2 Vacant Row")["id"]
        )
        held = make_unit(marcus, str(occupied.id), label="Unit A")

        from apps.metering import seams

        real = seams.active_account_for_unit
        seams.active_account_for_unit = lambda unit_id: (
            {"account_no": "A-11455", "status": "active"} if str(unit_id) == held["id"] else None
        )
        try:
            run_id = _validated(marcus)
            figures = import_runs.dry_run(marcus, run_id, "replace")
            assert (figures["not_in_file"], figures["skipped_occupied"]) == (2, 1)
            assert figures["will_deactivate"] == 1

            receipt = import_runs.load(marcus, run_id, {"write_mode": "replace"})
        finally:
            seams.active_account_for_unit = real

        occupied.refresh_from_db()
        vacant.refresh_from_db()
        assert occupied.status == "active", "an occupied premise must be left standing"
        assert vacant.status == "inactive"
        assert receipt["receipt"]["skipped_occupied"] == 1
        assert receipt["receipt"]["deactivated"] == 1


def test_DEF_543_FIXED__upsert_UPDATES_a_restated_premises(brazos, marcus):
    """⚠ **THE INVERSE OF THE PIN THAT STOOD HERE.** Until 2026-08-22 the
    tier-1 uniqueness rule rejected every row whose premise id was already on
    file, so `Insert & update` was a segmented option that could never update —
    and a 3-row correction file was `3 rejected of 3`, 100%, demanding a
    BR-MET-098 approval before refusing to change anything (`DEF-543`).

    The DB-half of that rule is now `PRM.PREMISE_NO_ON_FILE`, a WARNING whose
    sentence says what each mode will do; the in-file duplicate stays the
    ERROR. So the same correction file now validates clean-of-errors, needs no
    approval, and `upsert` actually updates — while `insert` still skips the
    row unchanged, which the last assertion pins so the modes stay distinct.
    """
    with tenant_ctx(brazos):
        import_runs.load(marcus, _validated(marcus, content=_file(3)), {"write_mode": "insert"})
        first = models.Premises.objects.get(premise_no="P-10001")

        again = _validated(
            marcus,
            content=_csv(
                [_row(index, PROP_TYPE="", OWNER="Somebody Else") for index in (1, 2, 3)],
                HEADERS,
            ),
        )
        checked = import_runs.read_run(again, with_rules=True)
        assert checked["counts"]["errors"] == 0
        assert checked["counts"]["warnings"] == 3  # PRM.PREMISE_NO_ON_FILE, by name
        by_code = {rule["code"]: rule for rule in checked["rules"]}
        assert by_code["PRM.PREMISE_NO_ON_FILE"]["hits"] == 3
        assert by_code["PRM.PREMISE_NO_UNIQUE"]["hits"] == 0

        # no approval bar in the way — 0 rejected of 3
        assert import_runs.dry_run(marcus, again, "upsert")["approval"]["required"] is False
        import_runs.load(marcus, again, {"write_mode": "upsert"})
        first.refresh_from_db()
        assert first.owner_manager == "Somebody Else"

        # …and `insert` still refuses to touch what exists (the modes differ).
        third = _validated(
            marcus,
            content=_csv([_row(1, PROP_TYPE="", OWNER="A Third Name")], HEADERS),
        )
        import_runs.load(marcus, third, {"write_mode": "insert"})
        first.refresh_from_db()
        assert first.owner_manager == "Somebody Else"


# ═══════════════════════════════════════════════════════════════════════════
# HARD RULE 6 — A SECOND COMMIT OF ONE RUN
# ═══════════════════════════════════════════════════════════════════════════


# ⚠ Was `xfail` pinning DEF-541 until 2026-08-22: `_run()` refused every
# loaded run, killing idempotency, the receipt read and rollback at once.
# The guard moved to `_refuse_committed`, owned by transform/validate only.
def test_a_second_commit_of_the_same_run_is_IDEMPOTENT(brazos, marcus):
    """Hard rule 6, scoped exactly where `import_runs` scopes it: the same FILE
    may be uploaded and rehearsed as often as anyone likes (TC-21); only a
    second COMMIT of the same RUN is a double load.

    ⚠ The second call must return the SAME RECEIPT rather than refusing —
    a double-clicked commit button is the commonest way this happens, and an
    error page over a load that actually succeeded sends the operator to
    re-import a file that is already in.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(5))
        first = import_runs.load(marcus, run_id, {"write_mode": "insert"})
        after_one = _counts()
        rollback_points = models.RollbackPoint.objects.count()

        second = import_runs.load(marcus, run_id, {"write_mode": "insert"})

        assert _counts() == after_one, "a second commit wrote the rows a second time"
        assert models.RollbackPoint.objects.count() == rollback_points
        assert second["receipt"]["run_no"] == first["receipt"]["run_no"]
        assert second["receipt"]["loaded"] == first["receipt"]["loaded"] == 5
        assert second["counts"] == first["counts"]


def test_a_second_commit_in_a_DIFFERENT_mode_does_not_re_run_it(brazos, marcus, replace_reenabled):
    """The dangerous shape of the case above: commit `insert`, then commit
    `replace`. Idempotency is on the RUN, so the second call must not go and
    retire everything the first run did not carry.

    ⚠ **TODAY THIS PASSES FOR THE WRONG REASON AND THAT IS WORTH SAYING**
    (`DEF-541`). The protection is `_run()`'s blanket refusal of a loaded run,
    not `_load_locked`'s idempotency branch — the branch is unreachable. The
    OUTCOME is right either way, which is why the assertion stands as written:
    when `DEF-541` is fixed it must still hold, from the branch instead.
    """
    with tenant_ctx(brazos):
        legacy = models.Premises.objects.get(
            pk=make_premises(marcus, address_line="1 Legacy Row")["id"]
        )
        run_id = _validated(marcus, content=_file(3))
        import_runs.load(marcus, run_id, {"write_mode": "insert"})

        with pytest.raises(errors.BizError):
            import_runs.load(marcus, run_id, {"write_mode": "replace"})

        legacy.refresh_from_db()
        assert legacy.status == "active", (
            "a second commit re-ran the load in another mode and retired a row "
            "the first commit had deliberately left alone"
        )


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 5 — THE RECEIPT, AND THE ROLLBACK IT OFFERS
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_carries_r10s_six_fields_and_the_run_number(brazos, marcus):
    """B15 §4.5's six: source · file hash · run by · session and IP · mapping
    used · rollback point. Every one of them is what the RUN recorded."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(4), file_name="silvercreek_premises_2026.csv")
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert"})["receipt"]

        assert receipt["source_label"] == "silvercreek_premises_2026.csv"
        assert len(receipt["file_sha256"]) == 64
        assert receipt["file_hash_verified"] is True
        assert receipt["session_and_ip"] == "sess_2b41 · 71.42.108.14"
        assert receipt["write_mode"] == "insert"
        assert receipt["finished_at"] is not None
        assert receipt["rollback_point"] is not None
        assert receipt["rollback_point"]["status"] == "available"


# ⚠ Was `xfail` pinning DEF-541 until 2026-08-22: `_run()` refused every
# loaded run, killing idempotency, the receipt read and rollback at once.
# The guard moved to `_refuse_committed`, owned by transform/validate only.
def test_the_receipt_does_not_recount_after_the_fact(brazos, marcus):
    """`BR-MET-090`'s posture past the commit: *"a receipt that said '245
    loaded' in August must still say it in December, whatever anyone has since
    deactivated"*. So deactivating a loaded row must not move the figure."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(4))
        import_runs.load(marcus, run_id, {"write_mode": "insert"})
        models.Premises.objects.filter(premise_no="P-10001").update(status="inactive")

        assert import_runs.receipt(import_runs._run(run_id))["receipt"]["loaded"] == 4


# ⚠ Was `xfail` pinning DEF-541 until 2026-08-22: `_run()` refused every
# loaded run, killing idempotency, the receipt read and rollback at once.
# The guard moved to `_refuse_committed`, owned by transform/validate only.
def test_the_rollback_DEACTIVATES_what_the_run_created_and_never_deletes(brazos, marcus, dana):
    """The same sentence as `replace`, deliberately — *"one sentence for a
    utility to learn instead of two"*.

    ⚠ This is the case that turned `DEF-541` from a code reading into a
    measurement: r10 draws a `↺` on every row of PRM-04 and prints *"A run can
    be rolled back as one unit for 30 days"*, and today that promise cannot be
    kept for any run at all. The Imports tab therefore ships its `↺` DISABLED
    WITH THIS REASON (BR-SHL-025) rather than live over a call that refuses.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(4))
        import_runs.load(marcus, run_id, {"write_mode": "insert"})

        # ⚠ `dana`, not `marcus`: `rollback` is `@require_role(SYSTEM_ADMIN)`
        # (BR-MET-035) and a Billing Clerk is refused before the run is read.
        result = import_runs.rollback(dana, run_id)

        assert models.Premises.objects.count() == 4, "a rollback DELETED rows (hard rule 4)"
        assert set(_statuses()) == {"inactive"}
        assert result["counts"]["rolled_back"] == 4
        assert result["status"] == "rolled_back"


def test_DEF_541_FIXED__every_door_answers_for_a_loaded_run(brazos, marcus, dana):
    """⚠ **THE INVERSE OF THE PIN THAT STOOD HERE** (it was mis-titled DEF_540;
    the register row is `DEF-541`). One guard in `_run()` refused every loaded
    run and killed three behaviours at once. The guard is `_refuse_committed`
    now, owned by transform and validate only — so the three doors that exist
    FOR loaded runs all answer:

      * a second `load` returns the SAME receipt and writes nothing (hard rule
        6, finally a behaviour rather than a comment);
      * `receipt()` reads back;
      * `rollback()` reverses — and then the RE-REHEARSAL doors still refuse,
        which is the half of BR-MET-090 that was ever true.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(2))
        first = import_runs.load(marcus, run_id, {"write_mode": "insert"})

        again = import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert again["receipt"]["run_id"] == first["receipt"]["run_id"]
        assert again["receipt"]["loaded"] == 2
        assert models.Premises.objects.count() == 2  # idempotent — no doubling

        read = import_runs.receipt(import_runs._run(run_id))
        assert read["receipt"]["loaded"] == 2

        # …and the REHEARSAL doors still refuse a committed run (BR-MET-090's
        # real scope), so the guard moved rather than vanished.
        with pytest.raises(errors.BizError) as refusal:
            import_runs.transform(marcus, run_id, {"mapping": {}, "row_handling": {}})
        assert refusal.value.message_key == "customers.import.already_committed"
        with pytest.raises(errors.BizError):
            import_runs.validate(marcus, run_id)


def test_DEF_540_FIXED__a_typed_premises_row_loads_with_its_TYPE_RESOLVED(brazos, marcus):
    """⚠ **THE INVERSE OF THE PIN THAT STOOD HERE.** Until 2026-08-22 a file
    whose `PROP_TYPE` matched a seeded Reference-data row was the ONE file that
    could not be imported — `_record_from` passed the resolved CODE into a
    ForeignKey and `Premises(**record)` raised before the first row was
    written — while a type nobody had heard of loaded fine (`DEF-540`).

    `_premises_type_ids` resolves the code to the row id at load time now, so
    the typed file loads AND keeps its type; the unknown type still lands as
    None, because stage 3's warning already told the operator (BR-MET-090 — the
    load honours the judgment the operator was shown).
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(2, typed=True))
        import_runs.load(marcus, run_id, {"write_mode": "insert"})
        assert models.Premises.objects.count() == 2
        typed = models.Premises.objects.filter(premises_type__isnull=False).select_related(
            "premises_type"
        )
        assert typed.count() == 2
        # the resolved FK is a REAL row of this tenant's reference data, and
        # the code the operator's file named is the code the row keeps
        for row in typed:
            assert row.premises_type.tenant_id == brazos.id
            assert row.premises_type.code


def test_DEF_542_FIXED__a_mapped_AREA_survives_the_load(brazos, marcus):
    """The third, and the worst of the three because nothing reports it.

    `North district` is a REAL seeded area, so stage 3's tier-1
    `PRM.REFERENCES_ON_FILE` passes it, stage 2 carries it as `area_name`, and
    `_NOT_A_COLUMN` then STRIPS it at load without ever resolving it to
    `area_id`. The operator maps a column, is told the value is on file, is
    told the load succeeded, and the value is gone.

    ⚠ **THAT IS `DEF-388`'s SHAPE — the exact failure `BR-MET-088` was ruled to
    prevent** — applied to a bulk migration instead of one record.
    """
    from apps.tenancy import models as tenancy_models

    headers = HEADERS + ["AREA"]
    body = _csv(
        [{**_row(index), "PROP_TYPE": "", "AREA": "North district"} for index in (1, 2)],
        headers,
    )
    with tenant_ctx(brazos):
        assert tenancy_models.Area.objects.filter(
            tenant_id=brazos.id, name="North district"
        ).exists()
        run_id = _validated(marcus, content=body, mapping={**MAPPING, "AREA": "area"})
        checked = import_runs.read_run(run_id)
        assert checked["counts"]["errors"] == 0, "the area IS on file — nothing rejects"

        import_runs.load(marcus, run_id, {"write_mode": "insert"})

        assert models.Premises.objects.count() == 2
        # ⚠ Was pinned inverted until 2026-08-22 (`DEF-542`): the load stripped
        # the checked area and both rows landed area-less. `_area_ids` resolves
        # it now — the name the operator mapped is the district the row keeps.
        north = tenancy_models.Area.objects.get(tenant_id=brazos.id, name="North district")
        assert models.Premises.objects.filter(area_id=north.pk).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-100 — THE UNPLANNED UNIT IS COUNTED, ON THE RECEIPT
# ═══════════════════════════════════════════════════════════════════════════


def test_a_unit_naming_a_missing_plan_LOADS_and_the_receipt_COUNTS_it(brazos, marcus):
    """`BR-MET-100`, the PO's overrule: *"a unit with no plan does not fail —
    it simply never appears on a bill"*, and what makes that safe is that the
    unplanned unit is **COUNTED AND FINDABLE**.

    ⚠ **SO THE ASSERTION IS ON THE RECEIPT FIGURE, NOT ON THE COLUMN.** The
    rule says in as many words that *"a build that writes the flag and surfaces
    it nowhere has implemented option C"*. The fixture is `units_csv`'s own
    twelfth-row shape: four units, one naming `RES-STD-2027`, a plan that is
    deliberately not created.
    """
    with tenant_ctx(brazos):
        numbers = seed_units_world(marcus)
        run_id = _validated(marcus, target="units", content=units_csv(numbers))

        # ⚠ **THE REHEARSAL AND THE COMMIT DISAGREE ON THIS EXACT FIGURE
        # (`DEF-544`).** `dry_run` counts `rate_plan_ref and not rate_plan_id`,
        # and `rate_plan_id` is resolved at LOAD time — it is never in `mapped`
        # — so every unit that names a plan is rehearsed as unplanned. On r10's
        # own 246-unit file the panel would read *"246 units with no plan"* and
        # the receipt then *"12"*. Pinned here so the day it is fixed this line
        # goes red; the screen's own copy warns nothing, because the figure it
        # prints is the server's.
        # ⚠ Was pinned inverted until 2026-08-22 (`DEF-544`): the rehearsal
        # tested a key stage 2 never writes and called all four units
        # unplanned. It now resolves refs the way the load does, so the
        # rehearsal and the receipt state ONE figure — the RES-STD-2027 row.
        rehearsed = import_runs.dry_run(marcus, run_id, "insert")
        assert rehearsed["unplanned_units"] == 1

        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert"})["receipt"]

        assert receipt["loaded"] == 4, "all four units load — option B, not option A"
        assert receipt["unplanned_units"] == 1
        # FINDABLE: the row that named the missing plan carries no plan and is
        # the one the Units tab's filter has to be able to list.
        assert models.Unit.objects.filter(rate_plan_id__isnull=True).count() == 1
        assert models.Unit.objects.get(label="U-10433-B").rate_plan_id is None


def test_a_premises_load_creates_premises_and_NOTHING_else(brazos, marcus):
    """`BR-MET-085` reaches the stage that WRITES. r10 prints *"181 single-unit
    premises auto-create their unit"* on this stage's dry run AND on its
    receipt; the PO withdrew all three clauses.

    ⚠ `UNIT_CNT` IS `2` ON EVERY ROW OF THIS FILE — `_row`'s own default, and
    the input r10's auto-create used. So the file is not merely silent about
    units, it actively asks for them, and nothing appears.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(5))
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert"})["receipt"]

        assert receipt["loaded"] == 5
        assert models.Premises.objects.count() == 5
        assert models.Unit.objects.count() == 0, "a premises load created a unit (BR-MET-085)"
        assert models.ServicePoint.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTES — because a function nothing calls is not a feature (law 2)
# ═══════════════════════════════════════════════════════════════════════════


def _call(view, method, tenant, *, role="system_admin", data=None, query=None, **kwargs):
    """One DRF view, called the way the wired stack calls it.

    ⚠ **A REFUSAL COMES BACK AS A STATUS CODE, NOT AS AN EXCEPTION** — the
    BE-02 handler renders every catalogue error into the envelope, so
    `pytest.raises` past this helper would never fire and a case written that
    way would pass while asserting nothing.

    ⚠ **AND `api_call` LEAVES THE TENANT CONTEXT WHEN IT RETURNS** (it enters
    its own around the view). So an engine call made after one refuses with
    `AUTH-003`; every case below builds its runs first and calls routes after,
    or re-enters `tenant_ctx` explicitly.
    """
    return api_call(
        view, method, user=FakeUser(), role=role, tenant=tenant, data=data, query=query, **kwargs
    )


def test_the_five_routes_carry_the_workflow_end_to_end(brazos, marcus, dana):
    """⚠ **THIS IS THE CASE THE ENGINE SUITE CANNOT WRITE.** Every function
    above had a test and `DEF-520` still happened, because the question neither
    suite asks is *"does a ROUTE reach this"*. So this walks stages 4 and 5
    through `apps/metering/api.py` itself.
    """
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(6))

    rehearsal = _call(
        metering_api.import_dry_run,
        "post",
        brazos,
        data={"write_mode": "insert"},
        run_id=run_id,
    )
    assert rehearsal.status_code == 200
    assert rehearsal.data["will_create"] == 6
    with tenant_ctx(brazos):
        assert models.Premises.objects.count() == 0, "the /dry-run ROUTE wrote a row"

    loaded = _call(
        metering_api.import_load, "post", brazos, data={"write_mode": "insert"}, run_id=run_id
    )
    assert loaded.status_code == 200
    assert loaded.data["receipt"]["loaded"] == 6
    with tenant_ctx(brazos):
        assert models.Premises.objects.count() == 6

    listing = _call(metering_api.imports, "get", brazos, query={})
    assert listing.status_code == 200
    assert [row["id"] for row in listing.data["rows"]] == [str(run_id)]
    assert listing.data["rows"][0]["loaded"] == 6
    assert listing.data["rows"][0]["status"] == "loaded"
    assert listing.data["rows"][0]["rows_in"] == 6

    # ⚠ Was a 409 loop until 2026-08-22 (`DEF-541`): the engine refused every
    # loaded run, so `/receipt` and `/rollback` were mounted-but-dead. The
    # guard moved to `_refuse_committed` (transform/validate only), and the two
    # routes now answer for the ONLY runs they exist for.
    receipt = _call(metering_api.import_receipt, "get", brazos, run_id=run_id)
    assert receipt.status_code == 200
    assert receipt.data["receipt"]["loaded"] == 6
    assert receipt.data["receipt"]["rollback_point"] is not None

    rolled = _call(metering_api.import_rollback, "post", brazos, run_id=run_id)
    assert rolled.status_code == 200
    with tenant_ctx(brazos):
        # BR-MET-099's sentence, on rollback as on replace: DEACTIVATED, never
        # deleted — the six rows exist and none is active.
        assert models.Premises.objects.count() == 6
        assert models.Premises.objects.filter(status="inactive").count() == 6

    # …and a SECOND rollback is refused: the point is spent (r10's 30-day
    # promise is one reversal, not a toggle).
    spent = _call(metering_api.import_rollback, "post", brazos, run_id=run_id)
    assert spent.status_code in (409, 422)


def test_a_billing_clerk_may_LOAD_but_may_not_APPROVE(brazos, marcus):
    """`BR-MET-098`: *"THE APPROVER IS THE SAME PAIR OF ROLES AS THE RATE-CHANGE
    SECOND APPROVAL (BR-RAT-091's 10% bar): Owner or Admin."* This product's
    answer to that pair is `SystemAdminOnly` — what
    `/discounts/{id}/versions/{vid}/approve` already carries.

    ⚠ **A CLERK KEEPS THE LOAD.** Taking the ordinary commit away from the role
    that runs imports would make the rule a ban rather than a second pair of
    eyes. What the clerk may not do is BE the second pair of eyes on their own
    run — which is what ticking `approved` on an over-threshold load is.

    ⚠ **AND THE CHECK IS IN `api.py`, NOT IN THE ENGINE.** `import_runs.load`
    reads `approved` as a bare boolean and asks nothing about who set it, so
    this is the only place the rule's second half is enforced today. Filed as
    `DEF-542` against `import_runs.py`, which this lane does not own.
    """
    with tenant_ctx(brazos):
        # ⚠ BOTH runs are staged BEFORE any route is called — `api_call` exits
        # the tenant context on the way out (see `_call`).
        clean = _validated(marcus, content=_file(6))
        # ⚠ `start=100` so the two files name DIFFERENT premises. Without it the
        # second run's rows collide with the first run's keys and `insert`
        # silently skips them — a correct outcome that would make this case's
        # arithmetic mean something other than what it says.
        over = _validated(marcus, content=_file(10, bad=2, start=100))

    allowed = _call(
        metering_api.import_load,
        "post",
        brazos,
        role="billing_clerk",
        data={"write_mode": "insert"},
        run_id=clean,
    )
    assert allowed.status_code == 200, "a clerk must keep the ordinary commit"

    refused = _call(
        metering_api.import_load,
        "post",
        brazos,
        role="billing_clerk",
        data={"write_mode": "insert", "approved": True},
        run_id=over,
    )
    assert refused.status_code == 422  # BIZ-APPROVAL
    assert refused.data["message_key"] == "metering.import.approver_role"
    assert refused.data["br_ref"] == "BR-MET-098"

    # …and a System Admin ticking the same box IS the second pair of eyes.
    approved = _call(
        metering_api.import_load,
        "post",
        brazos,
        data={"write_mode": "insert", "approved": True},
        run_id=over,
    )
    assert approved.status_code == 200
    with tenant_ctx(brazos):
        assert models.Premises.objects.count() == 14  # 6 clean + 8 of the 10


def test_the_run_list_is_invisible_to_another_tenant(brazos, marcus, lonestar, erin):
    """CLAUDE.md hard rule 1 over the new READ. A run table that leaked would
    tell one utility the file names, row counts and staff of another."""
    with tenant_ctx(brazos):
        import_runs.load(marcus, _validated(marcus, content=_file(3)), {"write_mode": "insert"})
        assert len(import_runs.run_list(None)["rows"]) == 1
    with tenant_ctx(lonestar):
        assert import_runs.run_list(None)["rows"] == []
    listing = _call(metering_api.imports, "get", lonestar, query={})
    assert listing.data["rows"] == []


def test_every_load_writes_an_audit_row(brazos, marcus, audit_rows):
    """CLAUDE.md hard rule 7 and `BR-MET-048`. The load writes one row per
    record AND one for the run, because *"who imported these 425 premises"* and
    *"where did THIS premise come from"* are two different questions a support
    call asks."""
    with tenant_ctx(brazos):
        run_id = _validated(marcus, content=_file(3))
        import_runs.load(marcus, run_id, {"write_mode": "insert"})
        actions = [row["action"] for row in audit_rows]
        assert actions.count("premises.created") == 3
        assert "import_run.loaded" in actions
