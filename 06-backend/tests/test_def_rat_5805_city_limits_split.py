# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5805 (the help said a blank place reaches nobody while the
#          count four lines below said 71 of 79) · DEF-RAT-5806 (a named place
#          did not narrow the tax to that place: a town of six reached 77)
# Rules:   CR-013 part 4 — *"premise city-limit flags drive attachment and are
#          audit-logged on the premise"* · BR-MET-1170 (the flag is the premises'
#          and decides money) · BR-RAT-107 (the count runs the ENGINE'S OWN
#          predicate; no second implementation of the rule)
# ───────────────────────────────────────────────────────
"""HOW a `city_limits` count was reached, not just what it is.

── THE ENGINE IS RIGHT; THE SCREEN COULD NOT SAY SO ─────────────────────────
`premises_in_scope` reads a premises' own `inside_city_limits` flag FIRST and
falls back to the typed place name only where no flag is recorded. That order is
signed — a utility that has drawn its boundary is not second-guessed by a
spelling — and nothing here changes it.

What was missing is that the SCREEN had no way to say it, so the number was true
and unexplainable in both directions at once:

  * leave the place box empty and the help read *"Left blank, this reaches
    nobody."* over a count of **71 of 79**;
  * type a town the utility has never heard of and the count was still **71**;
  * type the RIGHT town, with six properties, and the count was **77** — the six
    plus all 71 flagged — so scoping a tax to a town of six reached seventy-seven.

`matched_by_flag` and `matched_by_name` are that missing half, and they are
FACTS ABOUT ROWS THE PREDICATE ALREADY ADMITTED: a row carrying a flag was
admitted by the flag, because the predicate returns on it before the name is
read; a row with no flag can only have been admitted by the name. No rule is
re-implemented here, which is what BR-RAT-107 forbids.

── PROVED RED FIRST (hard-won law 7) ────────────────────────────────────────
At the commit before the fix every case below failed on the key itself:

    KeyError: 'matched_by_flag'

and `test_the_sample_names_both_groups` failed on its second assertion instead:
the sample was `['100 Inside Ave', '101 Inside Ave', '102 Inside Ave']` — three
FLAGGED premises and not one of the three the typed town added.

⚠ **THE BIAS RAN THE OTHER WAY ON THE LIVE TENANT, WHICH IS THE POINT.** There
the sample read three *Katy* addresses beside a count of 77 and named none of
the 71 flagged premises that are the reason it is 77, because those sort last by
premise number. `matched[:3]` shows whichever group happens to sort first, so
which half it hides is an accident of the data — and either half hides the thing
that explains the number.

── WHAT WOULD MAKE THESE CHECKS PASS WRONGLY ────────────────────────────────
Asserting only that a count is returned passes on every version of this defect,
including the one that shipped. So each case pins the SPLIT — which door each
premises came through — and the blank-place case asserts `matched_by_name == 0`
beside a `count` that is emphatically not zero, which is the exact contradiction
the old help sentence made.
"""

from __future__ import annotations

import pytest

from apps.metering import models as metering_models
from apps.rating import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — the shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

#: The estate, deliberately shaped like the demo tenant that produced the defect:
#: most premises FLAGGED inside the limits and carrying one city name, a couple
#: flagged OUTSIDE, and a handful with no flag at all in a different town. The
#: live figures were 71 flagged / 2 outside / 6 unflagged of 79; the arithmetic
#: is identical at this size and a failure names an address instead of an index.
FLAGGED_INSIDE = ("100 Inside Ave", "101 Inside Ave", "102 Inside Ave")
FLAGGED_OUTSIDE = ("200 Outside Rd",)
NO_FLAG = ("600 Named St", "601 Named St", "602 Named St")

INSIDE_CITY = "Silver Creek"
NAMED_CITY = "Katy"


def _build_estate(actor) -> None:
    for address in FLAGGED_INSIDE:
        row = make_premises(actor, address_line=address, city=INSIDE_CITY)
        metering_models.Premises.objects.filter(pk=row["id"]).update(inside_city_limits=True)
    for address in FLAGGED_OUTSIDE:
        row = make_premises(actor, address_line=address, city=INSIDE_CITY)
        metering_models.Premises.objects.filter(pk=row["id"]).update(inside_city_limits=False)
    for address in NO_FLAG:
        row = make_premises(actor, address_line=address, city=NAMED_CITY)
        metering_models.Premises.objects.filter(pk=row["id"]).update(inside_city_limits=None)


def test_a_blank_place_reaches_the_flagged_premises_and_the_split_says_so(brazos, dana):  # noqa: F811
    """`DEF-RAT-5805` — the help said *"Left blank, this reaches nobody."*

    It reaches the three FLAGGED premises, and `matched_by_name` is 0 — which is
    the whole of what the old sentence was trying to say and the whole of what
    it got wrong. The two numbers together are what the screen now prints.
    """
    with tenant_ctx(brazos):
        _build_estate(dana)
        blank = selectors.matched_premises("city_limits", "")

    assert blank["count"] == 3, "the flagged-inside premises are in scope with no place named"
    assert blank["total"] == 7
    assert blank["matched_by_flag"] == 3
    assert blank["matched_by_name"] == 0, "a blank box names nobody — but it does not empty the tax"


def test_an_unknown_place_adds_nobody_and_does_not_remove_the_flagged(brazos, dana):  # noqa: F811
    """`DEF-RAT-5806` — typing a town the utility has never heard of read the
    SAME count as leaving it blank, with nothing on screen to say why."""
    with tenant_ctx(brazos):
        _build_estate(dana)
        nowhere = selectors.matched_premises("city_limits", "Nowhereville")

    assert nowhere["count"] == 3
    assert nowhere["matched_by_flag"] == 3
    assert nowhere["matched_by_name"] == 0, "an unknown town adds nobody, and the screen says so"


def test_a_named_town_adds_only_the_unflagged_premises_in_it(brazos, dana):  # noqa: F811
    """`DEF-RAT-5806` — *"scoping a tax to a town of six reaches seventy-seven"*.

    The count is CORRECT and stays correct: the flag decides first, so the three
    flagged premises are in scope whatever the box says, and the town adds only
    the premises that have no flag. What changes is that the screen can now
    account for every one of them.
    """
    with tenant_ctx(brazos):
        _build_estate(dana)
        named = selectors.matched_premises("city_limits", NAMED_CITY)

    assert named["count"] == 6, "three flagged + the three unflagged premises in Katy"
    assert named["matched_by_flag"] == 3
    assert named["matched_by_name"] == 3
    assert named["matched_by_flag"] + named["matched_by_name"] == named["count"], (
        "the split must account for the whole count, or the screen is telling a third story"
    )


def test_naming_the_flagged_premises_own_city_still_adds_nobody(brazos, dana):  # noqa: F811
    """Typing the RIGHT city reads the same as typing nothing — because the flag
    already decided those premises, and the two outside-flagged ones stay out.

    This is the case that makes the precedence visible: a clerk who believes the
    box is what selects Silver Creek is wrong in a way no count alone reveals.
    """
    with tenant_ctx(brazos):
        _build_estate(dana)
        own = selectors.matched_premises("city_limits", INSIDE_CITY)

    assert own["count"] == 3, "the flagged-OUTSIDE premises is in Silver Creek and stays out"
    assert own["matched_by_flag"] == 3
    assert own["matched_by_name"] == 0


def test_the_sample_names_both_groups_when_there_are_two(brazos, dana):  # noqa: F811
    """`DEF-RAT-5806`'s second half — the sample line made the count worse.

    Scoped to Katy it listed three Katy addresses and none of the premises that
    are the reason the number is bigger than three, so the only reading available
    was that the town has six properties. The sample now alternates while both
    groups have rows.
    """
    with tenant_ctx(brazos):
        _build_estate(dana)
        named = selectors.matched_premises("city_limits", NAMED_CITY)

    lines = [row["address_line"] for row in named["sample"]]
    assert len(lines) == 3
    assert any(line in FLAGGED_INSIDE for line in lines), (
        "a sample that names only the typed town explains the count as the town's size"
    )
    assert any(line in NO_FLAG for line in lines), "and it must still show what the name added"


def test_no_other_boundary_claims_a_split_and_none_loses_its_sample(brazos, dana):  # noqa: F811
    """`None`, never `0` — and the other kinds' samples must not move.

    ⚠ THE SECOND HALF OF THIS CASE IS THE BUG THE FIX ITSELF NEARLY SHIPPED. The
    first draft of `_mixed_sample` returned `[]` whenever there was no split,
    which is not a smaller sample: it is the sample line silently vanishing from
    every `state`-scoped tax with a correct count still beside it. Nothing else
    in the suite compares a sample against a previous run.
    """
    with tenant_ctx(brazos):
        _build_estate(dana)
        by_state = selectors.matched_premises("state", "TX")
        everywhere = selectors.matched_premises(None, None)
        county = selectors.matched_premises("county", "Fort Bend")

    for answer in (by_state, everywhere, county):
        assert answer["matched_by_flag"] is None, "only city_limits has two doors"
        assert answer["matched_by_name"] is None

    assert by_state["count"] == 7
    assert len(by_state["sample"]) == 3, "a state-scoped tax still names three premises"
    assert len(everywhere["sample"]) == 3
    assert county["count"] == 0 and county["sample"] == []
