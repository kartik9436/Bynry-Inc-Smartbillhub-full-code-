# ── Trace ──────────────────────────────────────────────
# Change:   CR-042 — "in all imports - we need 2 option on step 1 insert,
#           insert & update; replace option is not required; currently many
#           places this option is at step 4 of import- can you check all
#           imports and make the corrections" (PO, 2026-08-27).
# Rules:    BR-MET-210 (two modes, that order, those words, step 1, ONE
#           control) · BR-MET-099 SUPERSEDED IN PART (the option is withdrawn;
#           the behaviour stays and is refused at the boundary by name) ·
#           BR-MET-127 reworded (a SUPERSEDING mode meets a billed read — the
#           refusal was never Replace-specific) · OQ-580 (how a utility retires
#           a premise it no longer serves) · OQ-418 CLOSED BY REMOVAL ·
#           OQ-326 MOOT · hard-won law 3 (the safe option is the default)
# Impacts:  apps/metering/write_modes.py · apps/metering/import_runs.py ·
#           apps/metering/models.py · apps/metering/services.py (the read-batch
#           field error's `allowed` list)
# ───────────────────────────────────────────────────────
"""CR-042 — TWO write modes, and the third refused BY NAME rather than deleted.

**WHY THIS SUITE EXISTS SEPARATELY FROM `test_cr038_w7_write_modes.py`.** That
suite pins how the modes BEHAVE. This one pins WHICH MODES EXIST, on both
rails, and what happens to the one that no longer does — a different question,
asked of a different kind of drift. W7's suite would still pass with a fourth
mode added tomorrow.

**THE FOUR THINGS THIS ASSERTS, AND WHY EACH IS HERE:**

1. **The constant is two, on BOTH rails, in the PO's order.** `insert` first
   because it is the only mode that cannot alter a record already on file
   (hard-won law 3 — the unsafe option is the one you type).
2. **`replace` is REFUSED, and refused BY NAME.** Not silently coerced to
   `insert`: a caller that asked to retire the records missing from its file
   and got a plain insert would believe it had retired them.
3. **The refusal NAMES `OQ-580`**, because the refusal is the stub for an open
   question and the prime directive puts the OQ id in the code, not in a
   comment beside it.
4. **BR-MET-127's billed-read protection SURVIVES the removal.** This is the
   test that earns the suite. `SUPERSEDING_MODES` used to read
   `("upsert", "replace")`; a lane deleting `replace` could as easily have
   deleted the tuple's reason for existing. The protection is asserted against
   `upsert` directly, so it cannot pass by accident.

⚠ **AND ONE NEGATIVE ASSERTION, WHICH IS THE UNUSUAL ONE.** BR-MET-099's
deactivation branch is deliberately KEPT and made unreachable. A later lane
reading `if write_mode == "replace":` in `import_runs.py` will correctly
observe it is dead code and be tempted to delete it. `test_cr042__br_met_099s
_behaviour_is_kept_not_deleted` fails if they do, and its message says why the
dead code is on purpose and what ruling would bring it back.
"""

import pytest

from apps.metering import import_runs, models, write_modes

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)
from core import errors


# ── 1 · the constants, on both rails ────────────────────────────────────────


def test_cr042__the_reads_rail_offers_exactly_two_modes_in_the_pos_order():
    """PO: *"we need 2 option on step 1 insert, insert & update"*.

    A tuple equality rather than a membership check, so that ADDING a mode
    fails as loudly as removing one — BR-MET-210's whole purpose is the eighth
    import target that has not been built yet.
    """
    assert write_modes.READ_WRITE_MODES == ("insert", "upsert")
    assert write_modes.DEFAULT_READ_WRITE_MODE == "insert"


def test_cr042__the_import_runs_rail_offers_exactly_two_modes():
    """The OTHER rail — premises, units, the three assets targets, accounts.

    Six of the product's nine import surfaces run through this one constant,
    which is why the PO saw the same control on six screens and why one edit
    fixes all six.
    """
    assert import_runs.WRITE_MODES == ("insert", "upsert")
    assert models.IMPORT_WRITE_MODES == ("insert", "upsert")


def test_cr042__the_two_rails_agree_with_each_other():
    """BR-MET-210 clause 1, asserted as a RELATIONSHIP.

    ⚠ Two constants that each say "insert, upsert" can still drift apart, and
    no test of either one alone can see it — the same blind spot G35 exists for
    on the version literals. The PO's complaint is precisely that the same
    control differs between screens, so the equality is the assertion.
    """
    assert tuple(write_modes.READ_WRITE_MODES) == tuple(import_runs.WRITE_MODES)


def test_cr042__replace_is_recorded_as_WITHDRAWN_not_forgotten():
    """The withdrawn value is named in code, because the refusal must name it.

    A refusal that says *"unknown value"* teaches an operator that they typed
    something wrong. `replace` was a real mode six days ago and rows in the
    database still carry it; the honest refusal says it was WITHDRAWN and
    points at the question that would bring it back.
    """
    assert write_modes.WITHDRAWN_READ_WRITE_MODES == ("replace",)
    assert import_runs.WITHDRAWN_WRITE_MODES == ("replace",)
    assert "replace" not in write_modes.READ_WRITE_MODES
    assert "replace" not in import_runs.WRITE_MODES


# ── 2 · the refusal, by name, on both rails ─────────────────────────────────


def test_cr042__normalize_refuses_replace_rather_than_defaulting_it():
    """⚠ **NEVER COERCE A WITHDRAWN MODE TO THE DEFAULT.**

    `normalize("")` legitimately answers `insert` — an absent choice takes the
    safe default. `normalize("replace")` must NOT: a caller that asked to
    retire the records its file no longer carries, and silently received a
    plain insert, would believe it had retired them. That is a wrong belief
    about a destructive operation, which is worse than an error.
    """
    assert write_modes.normalize("insert") == "insert"
    assert write_modes.normalize("upsert") == "upsert"
    assert write_modes.normalize("") == "insert"
    assert write_modes.normalize(None) == "insert"
    assert write_modes.normalize("replace") is None
    assert write_modes.normalize("REPLACE") is None
    assert write_modes.normalize("nonsense") is None


@pytest.mark.django_db
def test_cr042__the_dry_run_refuses_replace_and_names_OQ_580(brazos, marcus):  # noqa: F811
    """`POST /imports/{id}/dry-run` with the withdrawn mode.

    ⚠ It refuses BEFORE it loads the run, so a caller gets the same answer for
    a run in any state — a refusal that depended on the run's status would be a
    refusal an operator could work around by retrying at a different stage.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            import_runs.dry_run(marcus, "00000000-0000-0000-0000-000000000000", "replace")
    assert caught.value.br_ref == "OQ-580", caught.value.br_ref
    assert caught.value.message_key == import_runs.WITHDRAWN_MODE_KEY


@pytest.mark.django_db
def test_cr042__the_load_refuses_replace_and_names_OQ_580(brazos, marcus):  # noqa: F811
    """`POST /imports/{id}/load` — **the only route in the runner that writes.**

    The refusal is asserted on the LOAD as well as the dry run, and not assumed
    to follow from it: the two functions validate the mode independently (they
    always did), and a lane fixing one and not the other would leave the
    destructive path open behind a rehearsal that refuses.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            import_runs.load(
                marcus,
                "00000000-0000-0000-0000-000000000000",
                {"write_mode": "replace"},
            )
    assert caught.value.br_ref == "OQ-580", caught.value.br_ref
    assert caught.value.message_key == import_runs.WITHDRAWN_MODE_KEY


@pytest.mark.django_db
def test_cr042__staging_a_read_batch_as_replace_is_a_field_error(brazos, marcus):  # noqa: F811
    """The reads rail's own boundary — `stage_read_batch`.

    A FIELD error rather than a business error, because on this rail the mode
    arrives inside the batch payload beside the cycle and the route, and the
    screen shows it against the control the operator used.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        seed_config()
        with pytest.raises(errors.ValidationError) as caught:
            stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"), write_mode="replace")
    text = str(caught.value.__dict__)
    assert "write_mode" in text
    assert "replace" not in str(list(write_modes.READ_WRITE_MODES))


# ── 3 · what the removal must NOT have taken with it ────────────────────────


def test_cr042__BR_MET_127s_billed_refusal_survives_the_removal():
    """⚖️ **THE TEST THAT EARNS THIS SUITE.**

    BR-MET-127 was written as *"Replace mode meets a billed read"* and the code
    read `SUPERSEDING_MODES = ("upsert", "replace")`. A lane deleting the mode
    could as easily have deleted the tuple, and nothing else in the suite would
    have noticed: every W7 test that exercises the refusal happens to drive it
    through `upsert` or through `replace`, and the ones that used `replace`
    were being rewritten in the same commit.

    So the protection is asserted against `upsert` DIRECTLY, on the planner,
    with no import pipeline in the way.
    """
    assert write_modes.SUPERSEDING_MODES == ("upsert",)
    plan = write_modes.plan(
        write_mode="upsert",
        head_id="a-head",
        head_is_billed=True,
        head_label="M-7001 · 2026-08-03 · total",
    )
    assert plan["action"] == write_modes.ACTION_REFUSE_BILLED
    assert plan["reason"] == write_modes.SKIP_REASON_BILLED
    assert plan["existing_read"] == "M-7001 · 2026-08-03 · total"
    assert plan["door"] == "correct_billed_read"


def test_cr042__insert_still_blocks_a_row_whose_key_is_on_file():
    """The mode that remains the default still does what it always did.

    Asserted here rather than left to W7 because CR-042 narrowed
    `SUPERSEDING_MODES`, and `plan()` decides `blocked` vs `supersede` by asking
    whether the mode is IN that tuple. A narrowing that went one element too far
    would turn `upsert` into `insert` and every correction upload into a wall of
    errors — silently, with every W7 duplicate test still green.
    """
    blocked = write_modes.plan(write_mode="insert", head_id="a-head")
    assert blocked["action"] == write_modes.ACTION_BLOCKED
    assert blocked["reason"] == "already_on_file"

    superseding = write_modes.plan(write_mode="upsert", head_id="a-head")
    assert superseding["action"] == write_modes.ACTION_SUPERSEDE


def test_cr042__br_met_099s_behaviour_is_kept_not_deleted():
    """⛔ **THIS TEST EXISTS TO STOP A FUTURE CLEANUP, AND THAT IS UNUSUAL.**

    `import_runs.py` still contains BR-MET-099's deactivation branch — the loop
    that retires what the file no longer carries, skips anything occupied and
    never deletes. It is UNREACHABLE, because `replace` is refused at the
    boundary. A later lane will read it as dead code and be right about that.

    It is kept on purpose. BR-MET-099 is a CONFIRMED PO ruling of 2026-08-21
    with its own worked figure — **500 premises on file · 431 in the file · 69
    not in it · 41 occupied → 28 deactivated** — and the PO's 2026-08-27
    sentence withdrew an OPTION, not that answer. **OQ-580** asks whether the
    behaviour should come back, and option (c) — a separately-named *"retire
    premises not in this file"* action — needs this code standing.

    If you are here because this test failed: you deleted a signed capability
    that one ruling would restore. Restore it, or take OQ-580 to the PO first.
    """
    source = import_runs.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "deactivated_by_replace" in text, (
        "BR-MET-099's deactivation branch has been deleted. It is UNREACHABLE "
        "on purpose, not obsolete — see OQ-580 and this test's docstring."
    )
    assert "skipped_occupied" in text
