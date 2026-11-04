# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-648 — *"THE MOVE-OUT WIZARD IS SIX STEPS AND THE MOVE-OUTS LIST
#           COUNTS TO FOUR."* Closed by BR-SHL-046 (PO 2026-08-24, verbatim
#           *"6 steps"*), and closed on the register 2.79.6.
# Rules:    BR-SHL-046 — and specifically its DURABLE half, verbatim: *"THE
#           DURABLE HALF IS THE MECHANISM, NOT THE NUMBER: both bars must be
#           driven by ONE declared step list. Two literals that happen to agree
#           today is precisely the state this was found in, and it recurs the
#           day a seventh step appears."*
# ───────────────────────────────────────────────────────
"""BR-SHL-046's DURABLE HALF — the two sides of the wire agree BY CHECK, not by luck.

WHY THIS FILE EXISTS AFTER DEF-648 WAS ALREADY FIXED
-----------------------------------------------------
The fix is real and the number is right everywhere. **But the mechanism the
ruling asked for stops at the language boundary**, and the step-4 triage that
closed the row found it:

  * the wizard's rail derives from `moveShared.MOVE_OUT_STEPS` — a declared
    list of six, so the rail and `MOVE_OUT_STEP_COUNT` in that file cannot
    disagree;
  * the Move-outs tab's `STEP` column renders the SERVER's `of`, and the server
    carries `apps/customers/move_reads.MOVE_OUT_STEP_COUNT = 6` — **a literal**,
    correctly documented as *"carried as a constant so a screen cannot
    reintroduce the old denominator"*.

So today there are **two literals in two languages that happen to agree** —
which is, word for word, the state BR-SHL-046 says the defect was found in. No
gate compares them, `tsc` cannot see a Python constant, and pytest does not read
`.tsx`. The seventh step lands, somebody bumps one side, and `MVO-01`'s progress
bar misaddresses the wizard again — the *same* defect, because the list row
REOPENS the wizard at its furthest incomplete step and the number is an INDEX.

⚠ **WHY A PARITY TEST AND NOT A SHARED FILE.** Genuinely sharing the list needs a
generated artefact (the OpenAPI schema's shape) and that is a build-pipeline
change owned by nobody in this lane — and hard-won law 5 says one generated file,
committed once, which is a bigger decision than this defect. A parity assertion
buys the whole guarantee for twenty lines: it cannot make the two sides one
source, but it makes them incapable of disagreeing without going red, which is
the property the ruling actually asks for.

⚠ **IT READS THE TYPESCRIPT AS TEXT, AND THAT IS A STATED WEAKNESS.** It counts
`id:` entries inside the `MOVE_OUT_STEPS` array literal. A refactor that builds
that list some other way makes this test fail loudly rather than pass silently —
which is the right direction to fail in, and the assertion message says so.
"""

from __future__ import annotations

import re
from pathlib import Path


from apps.customers.move_reads import MOVE_IN_STEP_COUNT, MOVE_OUT_STEP_COUNT

SHARED = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "customers"
    / "moveShared.tsx"
)


def _declared_steps(name: str) -> int:
    """How many steps `moveShared.tsx` declares in `name`'s array literal."""
    text = SHARED.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {name}: readonly FlowStepDef\[\] = \[(.*?)\n\] as const;",
        text,
        re.S,
    )
    assert match, (
        f"{name} was not found in {SHARED.name} in the shape this test reads. "
        "That is a REAL failure and not a test-maintenance chore: the frontend's "
        "declared step list is what BR-SHL-046 makes the server's constant agree "
        "with, and this test cannot check an agreement it cannot see."
    )
    return len(re.findall(r"\bid:\s*\"", match.group(1)))


def test_def_648__the_move_out_step_count_is_the_same_number_on_both_sides():
    """`MOVE_OUT_STEP_COUNT` == `len(MOVE_OUT_STEPS)`, or the bar misaddresses the rail.

    RED PROOF (hard-won law 7), **re-run 2026-09-24 against the four-step list
    and quoted**: setting the server constant to `5` fails here with *"the
    server says a move-out has 5 steps and the wizard declares 4. … Change
    both, in one commit."* That is `DEF-648` reproduced against the new shape,
    and nothing else in the repo notices it. The ORIGINAL proof read the other
    way round — the constant at `4` under a six-step list — and both directions
    still fail, because the assertion compares rather than pins.
    """
    declared = _declared_steps("MOVE_OUT_STEPS")
    assert MOVE_OUT_STEP_COUNT == declared, (
        f"BR-SHL-046: the server says a move-out has {MOVE_OUT_STEP_COUNT} steps "
        f"and the wizard declares {declared}. The Move-outs tab's STEP column "
        "renders the server's number and the rail renders the declared list, so "
        "a row would reopen the wizard at the wrong step — DEF-648 exactly. "
        "Change both, in one commit."
    )
    # The ruled figure itself, pinned so that agreeing on the WRONG number is
    # still a failure.
    #
    # ⚠ **FOUR SINCE 2026-09-24, AND THIS PIN IS WHAT CAUGHT THE CHANGE.** It
    # read `6` — `BR-SHL-046`, PO 2026-08-24, verbatim *"6 steps"* — and went
    # RED on the commit that merged the wizard to four while the parity
    # assertion above it passed, which is exactly the division of labour the
    # two assertions were written for: the first one asks whether the two sides
    # AGREE, the second whether they agree on the number the PO ruled. The new
    # ruling is *"i okay with these steps"* (decision log 2026-09-24, *"RULED:
    # THE MOVE-OUT IS FOUR STEPS"*), merging old 3+4 and old 5+6.
    #
    # ⚠ **THIS FOUR IS NOT B18's FOUR.** B18 §5.6.2's `STEP (of 4)` was a DRAWN
    # count that never matched a six-step wizard, and that was `DEF-648`. This
    # is the wizard's own declared list after two merges. A lane reading only
    # *"it went back to 4"* will reopen a closed defect.
    assert MOVE_OUT_STEP_COUNT == 4


def test_def_648__the_move_in_count_is_pinned_too_and_it_was_never_in_dispute():
    """Move-in's SIX, corrected 2026-09-19 — and this test caught it six days late.

    ⚠ **THIS TEST WAS RIGHT AND NOBODY READ IT (`DEF-CUS-5887`).** It landed on
    2026-09-08 pinned at `5`. `MOVE_IN_STEPS` gained its sixth step —
    `preferences` — on **2026-09-13** in `cd73c1963`, and from that moment the
    assertion below this one failed with *"the server says a move-in has 5 steps
    and the wizard declares 6"*. It stayed red for **six days**, through every
    backend run by every lane, until somebody went looking for a different
    thing entirely. The guard did its whole job; what failed was that a red line
    in a long suite is where a true failure goes to hide.

    That is hard-won law 7's FIRST shape, and it is the reason the law's remedy
    is a habit rather than a tool: **read the failures you did not cause.** This
    docstring is here so the next reader of this file knows the test has already
    earned its keep once.

    **What the numbers are now.** The wizard declares six —
    `unit · customer · start · preferences · deposit · review` — `MoveInWizard`
    draws `Step 1 of 6`, and the Accounts blueprint draws `6 of 6` and `3 of 6`
    in the Move-ins list's STEP column — **p077 of the 281-page edition**, which
    was p073 in the 242-page one the PO replaced on 2026-09-19. The server's constant now says
    six as well, so the list's bar has as many segments as the wizard has steps.
    The boundary is still the failure mode: the next person to add a step will
    be adding it to one of these two lists.
    """
    # ⚠⚠ **FOUR SINCE 2026-10-05 (`CR-171-BRC10` P1.02, `DEF-CUS-9703`).** This
    # pinned `6` while the wizard declared SEVEN (`BR-CUS-1101` added *Which
    # services* on 2026-09-25) — red on the tip for ten days, the identical
    # shape `DEF-CUS-5887` recorded above. The PO's redesign rules the wizard
    # FOUR steps (*Unit · Customer · Billing · Review*, CR §2 S5), and the
    # server now DECLARES that list (`move_reads.MOVE_IN_STEP_IDS`) rather
    # than typing a count. The pin is the ruled figure.
    assert MOVE_IN_STEP_COUNT == 4


# HOLD released 2026-10-05 (CR-171 P2.15, lane WIZ): `moveShared.MOVE_IN_STEPS` is
# the four-step list in the same commit as the four-step wizard.
def test_def_648__the_move_in_count_agrees_with_the_declared_list():
    """The parity half of the case above — the wizard is four steps (P2.15)."""
    declared = _declared_steps("MOVE_IN_STEPS")
    assert MOVE_IN_STEP_COUNT == declared, (
        f"the server says a move-in has {MOVE_IN_STEP_COUNT} steps and the "
        f"wizard declares {declared}. Same boundary, same consequence."
    )
