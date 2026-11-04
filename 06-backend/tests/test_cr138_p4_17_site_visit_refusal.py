# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.17 — "Re-check the site-visit refusal".
#           The blueprint's own outcome line: *"Nothing in this product
#           re-checks a refusal. This one gets checked."*
# Rules:    CLAUDE.md hard-won law 2 and its MIRROR (a live screen behind a
#           dead control; DEF-CWP-3925, the portal's two working doors out of
#           eight) · law 7 habit 2 (ask what would make this check pass
#           WRONGLY) · BR-WRK-055 · BR-WRK-016 · CR-070 §2(a)
# Tests:    this file IS the test.
# Impacts:  07-frontend/src/features/payments/OutstandingsTab.tsx (the guarded
#           button) · 07-frontend/src/i18n/locales/en.json (the sentence) ·
#           apps/work/from_flows.FLOW_KINDS (the capability half) ·
#           apps/metering/work_tables.SOURCE_DUNNING_AUTO (the vocabulary)
# ───────────────────────────────────────────────────────
"""**A REFUSAL THAT NOBODY RE-READS IS A PROMISE NOBODY IS KEEPING.**

S34's selection toolbar offers *Book a site visit* and renders it guarded with
this sentence, in `07-frontend/src/i18n/locales/en.json`:

    "A site visit has no agreed rule behind it, so nothing here can book one."

It makes **two** claims and they fail differently, which is why this file
asserts them separately rather than as one boolean:

  **(a) THE RULE HALF** — *no agreed rule*. ⚠ **TRUE WHEN THIS FILE WAS
      WRITTEN AND FALSE SINCE THE SAME DAY.** `OQ-PAY-12578`, the question this
      re-check raised, was CLOSED on 2026-09-23 — PO, *"(c) Any clerk may raise
      one, no ladder stage required"*. The claim is described above because the
      SENTENCE still makes it; the pairing invariant at the foot of this file is
      why the sentence has not moved yet.
  **(b) THE CAPABILITY HALF** — *nothing here can book one*. `apps/work/
      from_flows.FLOW_KINDS` is the closed set of moments Work will raise a job
      from, and **not one of them is a debt**.

═══════════════════════════════════════════════════════════════════════════════
WHY THE VERDICT IS *STILL TRUE* AND THE **EVIDENCE** IS NOT THE SAME EVIDENCE
═══════════════════════════════════════════════════════════════════════════════
The refusal was written when `work_orders` was **metering's** table and there
was no lawful way for another module to ask — `apps/customers/disconnects.py`
records that state in its own words at `VISIT_NOT_SCHEDULED`. **That reason
expired on 2026-09-03**, when `CR-070` §2(a) made Work the eleventh module with
a read-only seam per neighbour and one named write door, and again on
2026-09-14, when a SIXTH caller (`meter_read`) was added to prove the door is
open to new moments.

So the sentence is still true **for a narrower and nameable reason**: nobody has
ruled *when a utility sends somebody out because of a debt*. That is the
utility's own operating policy and its regulator's — hard-won law 13's third
case, the same shape as `OQ-WRK-1561` — so it is asked, not decided here.

⚠ **THIS FILE DOES NOT ASSERT THAT THE BUTTON IS DISABLED.** That would be a
check on the thing we already believe. It asserts the **evidence underneath**,
so that the day somebody ratifies the rule or opens a seventh flow door, this
goes RED and names the control to release. That is the discipline `CR-068` R3
did not have, and it cost the customer portal six of its eight front doors.

═══════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7, habit 2)
═══════════════════════════════════════════════════════════════════════════════
* A seventh flow door added under a name this file does not look for. Hence the
  test reads the WHOLE tuple and refuses any member matching a debt-shaped word,
  rather than asserting a length or a hard-coded list.
* The sentence being edited so the claims change while these assertions stand.
  Hence `test_the_refusal_still_says_what_this_file_re_checks` pins the words in
  the catalogue: change the copy and this file must be re-read.
* The locale file moving. Hence the path is resolved and its absence FAILS,
  rather than the test skipping — a skip over a missing subject is `G5`'s
  192-skips-called-a-pass, one file over.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.work import connection_models as work_tables
from apps.work import from_flows

#: The catalogue key S34's `GuardedButton` passes as its `reason`.
REFUSAL_KEY = "payments.outstandings.action.fieldVisitUnavailable"

#: The sentence, byte for byte as `en.json` holds it on the day of the re-check.
REFUSAL_SENTENCE = "A site visit has no agreed rule behind it, so nothing here can book one."

#: Words that name a DEBT moment. A flow door called any of these is the
#: capability half of the refusal becoming false. Deliberately broader than the
#: one word a builder would pick, because the point of this list is to catch a
#: door somebody else named.
DEBT_SHAPED = (
    "collection",
    "collections",
    "dunning",
    "arrears",
    "debt",
    "debtor",
    "outstanding",
    "write_off",
    "writeoff",
    "disconnect_for_nonpayment",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EN_JSON = _REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales" / "en.json"


def _catalogue() -> dict[str, str]:
    """`en.json`, or a FAILURE — never a skip.

    A skip over a missing subject reports green about a question it never
    asked (`G5` called 192 skips a pass). If the catalogue has moved, this file
    is the thing that is stale and it must say so.
    """
    if not _EN_JSON.exists():
        pytest.fail(
            f"the English catalogue is not at {_EN_JSON}. This file re-checks a refusal that "
            "lives in it; a moved catalogue means this test is stale, not that the refusal is "
            "gone. Re-point it and re-read the refusal."
        )
    return json.loads(_EN_JSON.read_text(encoding="utf-8"))


def test_the_refusal_still_says_what_this_file_re_checks() -> None:
    """The sentence is pinned, so editing the copy forces a re-read of the rest.

    Not decoration: every other assertion here is about the EVIDENCE for two
    specific claims. If the claims change, the evidence this file checks is the
    wrong evidence, and a green suite would be answering a question nobody
    asked any more.
    """
    catalogue = _catalogue()
    assert REFUSAL_KEY in catalogue, (
        f"{REFUSAL_KEY} has left the English catalogue. If the refusal was REMOVED because it "
        "became untrue, delete this file in the same commit and say so in the decision log. If "
        "it was renamed, re-point this test. Do not leave it passing over a key that is gone."
    )
    assert catalogue[REFUSAL_KEY] == REFUSAL_SENTENCE, (
        "S34's site-visit refusal has been re-worded.\n"
        f"  this file re-checks: {REFUSAL_SENTENCE!r}\n"
        f"  the catalogue says:  {catalogue[REFUSAL_KEY]!r}\n"
        "Re-read CR-138 P4.17 before changing this constant: the sentence makes TWO claims and "
        "this file asserts the evidence for each one separately."
    )


def test_claim_b_no_flow_door_exists_for_a_debt() -> None:
    """**THE HOLD-EXPIRY TEST.** Work raises jobs from six moments; none is a debt.

    ⚠ **THIS IS THE ASSERTION THAT GOES RED WHEN THE REFUSAL BECOMES FALSE**,
    and it names what to do about it rather than only failing. `from_flows.
    propose()` refuses an unknown `flow_kind` by name with `work.fromFlows.
    unknownFlow`, so payments has no lawful door today — not because Work is
    absent (it has been the eleventh module since 2026-09-03) but because no
    door for this moment has been opened.
    """
    kinds = tuple(from_flows.FLOW_KINDS)
    offenders = [kind for kind in kinds if any(word in kind.lower() for word in DEBT_SHAPED)]
    assert not offenders, (
        "═══ CR-138 P4.17 — THE SITE-VISIT HOLD HAS EXPIRED ═══\n"
        f"`from_flows.FLOW_KINDS` now carries a debt-shaped door: {offenders}.\n"
        "Work can raise a job from a collections moment, so S34's refusal —\n"
        f"  {REFUSAL_SENTENCE!r}\n"
        "is no longer true about the CAPABILITY half.\n"
        "DO THIS, in one commit (hard-won law 2's mirror):\n"
        "  1. release the `GuardedButton` at 07-frontend/src/features/payments/\n"
        "     OutstandingsTab.tsx and point it at the door BY ADDRESS;\n"
        "  2. delete or re-word `payments.outstandings.action.fieldVisitUnavailable`\n"
        "     in all eleven catalogues;\n"
        "  3. confirm the RULE half too — a door with no ratified rule behind it is\n"
        "     a crew in a van on nobody's authority (see the other test here);\n"
        "  4. delete this file and record the release in 12-governance/02-decision-log.md."
    )


def test_claim_b_the_dunning_source_token_still_has_no_writer() -> None:
    """`dunning_auto` is declared vocabulary with nothing writing it — still.

    `metering.connections.SOURCE_DUNNING_AUTO` is one of the sixteen values
    `work_orders.source` may hold, and it is r10's drawn word rather than a
    door: as of the re-check the token appears in the repository **only in its
    own declaration and in `WORK_ORDER_SOURCES`**. A declared value with no
    writer reads, to a lane grepping for it, exactly like a capability — which
    is why it is asserted here rather than trusted.

    ⚠ This asserts the token EXISTS and is a member of the closed set. It cannot
    assert "nothing writes it" without grepping the tree, which `G78` and the
    flow-door assertion above cover between them: any writer would have to come
    through `from_flows`, and that is the tuple the previous test guards.
    """
    assert work_tables.SOURCE_DUNNING_AUTO == "dunning_auto"
    assert work_tables.SOURCE_DUNNING_AUTO in work_tables.WORK_ORDER_SOURCES, (
        "`dunning_auto` has left `WORK_ORDER_SOURCES`. That is a NARROWING of a closed "
        "vocabulary, which `DEF-WRK-3726` records as the dangerous direction — a door that "
        "writes it would be refused by `ck_work_orders_source` at raise time, three waves "
        "downstream of its cause."
    )


def test_the_rule_half_IS_NOW_RATIFIED_and_the_sentence_and_the_door_move_together() -> None:
    """⚠ **AMENDED 2026-09-23, HOURS AFTER THIS FILE WAS WRITTEN. THE RULE EXISTS.**

    `OQ-PAY-12578` — the question this lane raised out of the re-check — was
    **CLOSED the same day**, option (c), PO verbatim: *"Any clerk may raise one,
    no ladder stage required"*. So the refusal's FIRST claim, *"a site visit has
    no agreed rule behind it"*, **is now false.**

    ⚠ **AND THE FIRST VERSION OF THIS TEST DID NOT NOTICE, WHICH IS WHY IT IS
    AMENDED RATHER THAN DELETED.** It searched payments' `02-business-rules.md`
    for the words, and no `BR-PAY-` row carries them yet — the ruling lives in
    the open-question register and the decision log, which is where rulings
    actually land. This file's own docstring called that out as *"the weak half
    … a rule ratified under wording this search does not match would not be
    found"*, and the weakness was exercised **within the hour**. A stated
    weakness is still a weakness; this is it closed.

    ═══════════════════════════════════════════════════════════════════════════
    WHAT IS ASSERTED NOW: **THE SENTENCE AND THE DOOR MOVE TOGETHER**
    ═══════════════════════════════════════════════════════════════════════════
    The ruling says so in terms: *"THE REFUSAL SENTENCE MUST GO WITH THE SAME
    COMMIT THAT OPENS THE CONTROL. A live screen behind a dead control is
    hard-won law 2's mirror, and it cost the customer portal six of its eight
    front doors."* Four states, two lawful:

      no door · the old sentence   LAWFUL, and it is today. The rule is ruled,
                                   the capability is not built, and the control
                                   stays disabled.
      door · a new sentence        LAWFUL, and it is the target.
      door · the old sentence      **FAILS** — a live door behind a refusal
                                   saying nothing can book one.
      no door · a new sentence     **FAILS** — a refusal withdrawn over a
                                   capability that does not exist.
    """
    kinds = tuple(from_flows.FLOW_KINDS)
    door = any(any(word in kind.lower() for word in DEBT_SHAPED) for kind in kinds)
    sentence = _catalogue().get(REFUSAL_KEY)
    # The refusal in its ORIGINAL form claims a missing RULE. Any re-wording
    # that drops that claim counts here as "a new sentence".
    claims_no_rule = sentence is not None and "no agreed rule" in sentence

    if door and claims_no_rule:
        pytest.fail(
            "=== A LIVE DOOR BEHIND A DEAD REFUSAL ===\n"
            f"`from_flows.FLOW_KINDS` carries a debt-shaped door {kinds!r}, and S34 still "
            f"refuses with {sentence!r}.\n"
            "PO ruling of 2026-09-23 closing OQ-PAY-12578: the refusal sentence goes with "
            "the SAME commit that opens the control. Release the GuardedButton in "
            "07-frontend/src/features/payments/OutstandingsTab.tsx and re-word "
            f"{REFUSAL_KEY} in all eleven catalogues."
        )
    if not door and not claims_no_rule:
        pytest.fail(
            "=== A REFUSAL WITHDRAWN AHEAD OF THE CAPABILITY ===\n"
            f"S34's refusal no longer claims a missing rule ({sentence!r}) and "
            "`from_flows.FLOW_KINDS` still has no debt-shaped door, so nothing can "
            "actually book a visit. Put the sentence back, or land the door in this commit."
        )


def test_the_ruling_that_closed_the_rule_half_is_still_closed() -> None:
    """`OQ-PAY-12578` is CLOSED. **Read the STATUS column, never the body.**

    CLAUDE.md: *"the status column decides, and a body that contradicts it is
    stale until proved otherwise"* — and that row's body still opens with this
    lane's original *"BOTH of its claims are still true"*, which the ruling
    underneath it reverses. Reading the body gives the pre-ruling answer.

    If the question is ever re-opened, this fires and the pairing invariant
    above must be re-read from the top.
    """
    register = _REPO_ROOT / "12-governance" / "01-open-questions.md"
    assert register.exists(), f"the open-question register is not at {register}"
    rows = [
        line
        for line in register.read_text(encoding="utf-8").split("\n")
        if line.startswith("| OQ-PAY-12578 |")
    ]
    assert len(rows) == 1, f"expected exactly one OQ-PAY-12578 row, found {len(rows)}"
    status = rows[0].rsplit("|", 2)[-2].strip()
    assert "CLOSED" in status.upper(), (
        "OQ-PAY-12578 is no longer CLOSED.\n"
        f"  its status column now reads: {status!r}\n"
        "The rule half of S34's site-visit refusal was ratified on 2026-09-23 — PO, "
        '"(c) Any clerk may raise one, no ladder stage required". If that has been '
        "re-opened or superseded, re-read this whole file before trusting the pairing "
        "invariant above."
    )
