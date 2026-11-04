"""**`CR-150-BRC09` — New Connect's EIGHT steps become FIVE, on the server's side.**

PO ruling 2026-09-28, verbatim: *"these steps are good - we need 1 word - for
every step"* and *"we dont want any information to be reduced or lost - 8 steps
→ 5"*. The parked-draft half of the same ruling: *"a build parked on an old
step reopens on its mapped one — 1→1, 2→2, 3/4/5→3, 6→4, 7/8→5"*.

**WHY THE SERVER HAS A SHARE OF THIS AT ALL.** `BR-SHL-046` says one declared
step list drives every surface, and the two halves of this one live in two
languages with no shared source — `newConnectShared.NEW_CONNECT_STEPS` in
TypeScript and `NEW_CONNECT_STEP_COUNT` here. `DEF-CUS-5886` is what that costs
when it drifts: `MOVE_IN_STEP_COUNT` shipped as `5` under a six-step wizard for
weeks with `tsc`, every suite and every gate green.

⚠ **THE PARITY CASES BELOW READ THE TYPESCRIPT FILE AS TEXT, WHICH IS THE ONLY
WAY A PYTHON TEST CAN SEE IT.** That is a real limitation and it is named
rather than hidden: it asserts what the other language DECLARES, not what its
wizard renders. The rendered half is
`07-frontend/src/features/customers/newConnectFiveSteps.dom.test.tsx`, and
neither file is sufficient alone.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.metering import connection_reads
from apps.metering.connections import (
    STEP_OF_THE_CHARGES,
    STEP_OF_THE_PREMISE,
    STEP_OF_THE_UNITS,
)

SHARED_TSX = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "customers"
    / "newConnectShared.tsx"
)


def _declared_step_ids() -> list[str]:
    """The ids `NEW_CONNECT_STEPS` declares, in order, read out of the source."""
    body = SHARED_TSX.read_text(encoding="utf-8")
    start = body.index("export const NEW_CONNECT_STEPS = [")
    end = body.index("] as const;", start)
    return re.findall(r'\{\s*id:\s*"([a-z_]+)"', body[start:end])


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE COUNT, IN BOTH LANGUAGES
# ════════════════════════════════════════════════════════════════════════════
def test_the_server_says_five_and_the_wizard_declares_five():
    """`BR-SHL-046` — one list, two languages, and nothing to hold them equal
    but this."""
    assert connection_reads.NEW_CONNECT_STEP_COUNT == 5
    assert len(_declared_step_ids()) == connection_reads.NEW_CONNECT_STEP_COUNT


def test_the_five_are_the_drawn_five_in_the_drawn_order():
    assert _declared_step_ids() == ["customer", "premise", "units", "charges", "review"]


# ════════════════════════════════════════════════════════════════════════════
# 2 · EVERY REFUSAL THE SERVER CAN STAMP NAMES A STEP THAT STILL EXISTS
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS IS THE CASE THAT MATTERS MOST AND IT IS THE CHEAPEST ONE HERE.** A
# refusal landing on the WRONG step is worse than one with no step at all: it
# sends a clerk to a screen where the field is not, with every answer still on
# screen and nothing saying which one is wrong. The wizard resolves the
# server's step by ID out of its own declared list (`stepOwningRefusal`), and
# an id it does not recognise is NOT routed — so a stamp naming a retired step
# is silently demoted to the ordinary failure card, which is exactly the
# outcome `DEF-MET-7690` was filed about.
def test_every_step_the_server_stamps_is_still_one_of_the_five():
    """The three constants in `connections.py`, against the declared list.

    ⚠ **THE STAMPS ARE THE CALL SITE'S, NEVER A FIELD-NAME MATCH**
    (`DEF-MET-7690`), which is why folding three steps away needed no second
    map: `charges` moved from position 6 to position 4 and its id did not
    move at all. This is the check that says so, and it goes red the day
    somebody stamps a step id the wizard has stopped declaring.
    """
    declared = set(_declared_step_ids())
    for stamped in (STEP_OF_THE_PREMISE, STEP_OF_THE_UNITS, STEP_OF_THE_CHARGES):
        assert stamped in declared, (
            f"the server stamps `step: {stamped}` on a refusal and the wizard "
            f"no longer declares that step, so the sentence reaches the clerk "
            f"on a nameless failure card instead of on the field"
        )


def test_no_refusal_is_stamped_with_a_step_that_was_folded_away():
    """`services`, `plans`, `communication` and `owner` are gone as step ids.

    Read out of `connections.py` rather than asserted about the three
    constants, because a fourth stamp added as a literal would be invisible to
    a check that only looks at the constants.
    """
    source = (
        Path(__file__).resolve().parents[1] / "apps" / "metering" / "connections.py"
    ).read_text(encoding="utf-8")
    stamped = set(re.findall(r'"step":\s*"([a-z_]+)"', source))
    assert stamped.isdisjoint({"services", "plans", "communication", "owner"}), stamped


# ════════════════════════════════════════════════════════════════════════════
# 3 · A PARKED DRAFT, SERVED IN THE FIVE-STEP SHAPE
# ════════════════════════════════════════════════════════════════════════════
def test_the_stored_step_map_is_the_po_s_own():
    """1→1, 2→2, 3/4/5→3, 6→4, 7/8→5 — quoted from `CR-150-BRC09` §0."""
    assert connection_reads.NEW_CONNECT_STORED_STEP == {
        1: 1,
        2: 2,
        3: 3,
        4: 3,
        5: 3,
        6: 4,
        7: 5,
        8: 5,
    }


def test_the_two_languages_hold_the_same_map():
    """The TypeScript `NEW_CONNECT_STORED_STEP`, read as text, against this one.

    Two literals in two languages that happen to agree today is the exact
    state `DEF-648` was found in.
    """
    body = SHARED_TSX.read_text(encoding="utf-8")
    start = body.index("export const NEW_CONNECT_STORED_STEP")
    end = body.index("};", start)
    pairs = re.findall(r"(\d+):\s*(\d+)", body[start:end])
    assert {int(a): int(b) for a, b in pairs} == connection_reads.NEW_CONNECT_STORED_STEP


def test_a_draft_parked_on_the_old_charges_step_is_served_as_step_four():
    """⛔ **Without the map this row reads `Step 6 of 5`.**

    Not merely stale — impossible, on a row a clerk reads to decide what to
    pick up. Clamping instead would answer `5 of 5` for a draft parked on
    *Charges*, which is worse: wrong, and it looks finished.
    """
    assert connection_reads.new_connect_stored_step(6) == 4
    assert connection_reads.new_connect_stored_step(7) == 5
    assert connection_reads.new_connect_stored_step(8) == 5
    # The three that did not move.
    assert connection_reads.new_connect_stored_step(1) == 1
    assert connection_reads.new_connect_stored_step(2) == 2
    assert connection_reads.new_connect_stored_step(3) == 3
    # The two the services and work-order steps held.
    assert connection_reads.new_connect_stored_step(4) == 3
    assert connection_reads.new_connect_stored_step(5) == 3


def test_a_number_the_map_does_not_know_is_handed_back_untouched():
    """The map decides WHICH step; the caller's bounds still decide IN RANGE.

    A map that clamped as well would be a second opinion about the bounds,
    which is how two surfaces start disagreeing about the same row.
    """
    assert connection_reads.new_connect_stored_step(0) == 0
    assert connection_reads.new_connect_stored_step(99) == 99


def test_every_served_step_is_inside_the_five():
    """Whatever a row holds, the number a clerk READS is 1–5 or is out of
    range for a reason the map did not invent."""
    for stored in range(1, 9):
        served = connection_reads.new_connect_stored_step(stored)
        assert 1 <= served <= connection_reads.NEW_CONNECT_STEP_COUNT
