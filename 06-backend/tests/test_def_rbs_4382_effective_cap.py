"""DEF-RBS-4382 — the cap a clerk types is the cap the engine enforces.

⚠ **WHAT THIS IS ABOUT.** This product keeps a run limit in TWO places, and
until now only one of them did anything:

  * `runbooks.cap` — a first-class setting, in `EDITABLE_SETTINGS`, validated,
    saved by `PUT /runbooks/{key}`, and **null until an admin sets it**;
  * a `most_per_run` PARAMETER declared by four runbooks — the collections
    ladder, deposit review, payment plans and returned payments — which
    `RB-108`'s card lists as an input beside a *capped at 400* sentence, and
    which the setup screen lets a clerk type into.

Nothing read the second one. Wave `M`'s dry cycle walked **973 accounts a
week** against a card that said 400, neither refused nor truncated, five
Mondays running — on the one runbook in the catalogue that sends letters to
customers.

⚠ **WHY IT ESCAPED, WHICH IS THE PART WORTH KEEPING.** Two fields meant the
same thing and each had its own passing tests: every test of the cap exercised
the COLUMN, every test of the parameter exercised its DEFAULT, and **nothing
compared them**. Neither suite was wrong. The gap was in the space between
them, which is where a check has to be aimed deliberately — so this file
asserts the one thing neither side could: the number that reaches
`executor.execute` is the number a clerk would believe.
"""

from __future__ import annotations

import pytest

from apps.runbooks.services import effective_cap


def test_a_typed_limit_is_enforced_when_the_column_is_unset():
    """The exact shape of the defect: an admin set no ceiling, a clerk typed 400."""
    assert effective_cap(None, {"most_per_run": 400}) == 400


def test_the_tighter_of_the_two_wins_in_both_directions():
    """Neither control may be decorative — that is the whole defect.

    Letting the column always win would leave the clerk's box doing nothing
    (today's bug); letting the parameter always win would let a clerk type
    past the tenant's standing ceiling. So the run is refused by whichever is
    tighter, and both boxes mean something.
    """
    assert effective_cap(400, {"most_per_run": 900}) == 400
    assert effective_cap(900, {"most_per_run": 400}) == 400


def test_absent_means_absent():
    """`NFR-5` — no hard cap anywhere. With neither set there is no limit, which
    is exactly what the engine did before and must keep doing."""
    assert effective_cap(None, {}) is None
    assert effective_cap(None, {"most_per_run": None}) is None
    assert effective_cap(None, {"most_per_run": ""}) is None


@pytest.mark.parametrize("junk", ["all", "abc", 0, -5, "0"])
def test_a_value_that_is_not_a_limit_never_becomes_one(junk):
    """A parameter can hold the word a multi-select stores, a blank, or a
    number that is not a limit. `PUT /runbooks/{key}` already refuses a cap
    below 1 — *'not a limit, it is a runbook that can never run, expressed as a
    number'* — and a value arriving by the other door must not slip past that."""
    assert effective_cap(None, {"most_per_run": junk}) is None
    # …and it must not tighten a real ceiling either.
    assert effective_cap(400, {"most_per_run": junk}) == 400


def test_the_ladder_still_declares_the_parameter_this_reads():
    """⚠ **THE CASE THAT CATCHES A RENAME.** Everything above tests a function
    against a string. If a runbook renames its parameter, every assertion here
    still passes and the cap is decorative again — the original defect, with
    green tests over it. So this asks the actual definition.
    """
    from apps.runbooks.definitions import dunning
    from apps.runbooks.services import MOST_PER_RUN

    names = {p.name for p in dunning.RUNBOOK.parameters}
    assert MOST_PER_RUN in names, (
        f"the collections ladder no longer declares {MOST_PER_RUN!r}; "
        "either the parameter was renamed and effective_cap now reads nothing, "
        "or it was removed and this rule needs re-deciding, not re-naming"
    )
