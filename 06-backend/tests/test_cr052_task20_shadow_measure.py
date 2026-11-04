# ── Trace ──────────────────────────────────────────────
# Component: the R1–R7 per-step disagreement measurement (CR-052 task 20,
#            step 4 of the recorded cutover).
# Change:   CR-052 task 20. These cases pin the two things the measurement
#           would otherwise be free to get quietly wrong: **a step nobody could
#           evaluate must never be counted as a step that agreed**, and the
#           coverage facts the whole recommendation rests on.
# Rules:    CLAUDE.md hard-won law 7 (prove a new guard goes RED before
#           trusting it green) · DEF-182 (a check whose output cannot
#           distinguish pass from fail is worse than no check)
# Impacts:  10-scripts/cr052_r1r7_shadow_measure.py
# ───────────────────────────────────────────────────────
"""The measurement's own guards — every one of them proved RED first.

⚠ **WHY THESE ARE STRUCTURAL ASSERTIONS AND NOT A ROW COUNT.** The figures the
script produces are a fact about ONE tenant's data on ONE day (47 accounts, all
refusing at R3), and a test asserting 47 would go red the moment somebody seeds
a meter. What must NOT drift is the shape of the answer:

  * a step the comparator does not cover is `cannot_evaluate`, NEVER `agree`;
  * a chain refusal marks its own step and leaves every other step
    `cannot_evaluate`, because `compare()` is not called on a refusal;
  * the coverage map matches `compare()`'s own source IN BOTH DIRECTIONS;
  * R7 has no typed refusal at all and never will, so a COMPARISON is the only
    thing that can ever evaluate it.

⚠ **AMENDED 2026-08-31 (`DEF-2798`) — FOUR OF THESE CASES ASSERTED THAT R3b,
R5, R6 AND R7 WERE COMPARED BY NOTHING, AND THAT IS NO LONGER TRUE.** It was the
load-bearing finding of the first measurement: four of the eight steps read zero
disagreements while having been measured on nothing, and *"a thousandfold error
on the live meter multiplier moved not one column"* was the proof. `compare()`
now emits a divergence at all four, so those cases assert the new coverage and
the PROPERTY they were protecting — *an uncovered step is never counted as
agreement* — is pinned against a SYNTHETIC coverage map instead, where it cannot
quietly become vacuous the next time the comparator widens.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "10-scripts"
    / "cr052_r1r7_shadow_measure.py"
)


def _harness():
    spec = importlib.util.spec_from_file_location("cr052_shadow_measure", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _harness()


def _row(**over):
    base = {
        "account_id": "a1",
        "account_no": "AC-1",
        "status": "agreed",
        "divergences": [],
        "refusal_step": None,
        "refusal_type": None,
        "blocked_reason": None,
    }
    base.update(over)
    return base


# ── TC1 · the whole point of the third column ───────────────────────────────


def test_a_step_the_comparator_does_not_cover_is_never_counted_as_agreement(harness):
    """An account on which EVERYTHING matched still leaves an UNCOVERED step with
    nothing measured, and the table must say so in those words.

    ⚠ **THE COVERAGE MAP HERE IS SYNTHETIC, AND THAT IS THE POINT (`DEF-2798`).**
    This case used to name R3b, R5, R6 and R7 as the uncovered steps. All four
    are compared now, and a case written against the real map would have had to
    be either deleted or emptied — so the property it exists to protect would
    have quietly stopped being tested at the exact moment the comparator grew.
    Pinned against a map that names one uncovered step, it goes on being a real
    test however wide `compare()` becomes.

    PROVED RED FIRST: with `_verdicts_for`'s final `else` branch returning
    `(AGREE, ...)` instead of `(CANNOT, ...)` — the one-character version of the
    comfortable lie — this case reads `R5 agree=1` and fails on the assertion
    below. That is precisely the answer a reader would act on, and it is wrong.
    """
    coverage = {"compared": {"R1", "R2", harness.FUSED_BASE}, "refusable": {"R5"}}
    body = {"accounts_detail": [_row(status="agreed")]}
    table = {row["step"]: row for row in harness.per_step_table(body, coverage)}

    assert table["R1"][harness.AGREE] == 1
    assert table["R2"][harness.AGREE] == 1
    for step in ("R3b", "R5", "R6", "R7"):
        assert table[step][harness.AGREE] == 0, (
            f"{step} was counted as agreeing on an account where nothing at {step} "
            "was ever compared. That is the comfortable false answer this whole "
            "measurement exists to refuse."
        )
        assert table[step][harness.CANNOT] == 1
        assert (
            "no_comparison_is_implemented_for_this_step" in table[step]["reasons"]
        )


def test_every_step_the_comparator_now_covers_gets_a_real_verdict(harness):
    """The other half of the same property, and the one `DEF-2798` was filed for.

    On the real coverage map an account that agreed everywhere must AGREE at all
    six compared steps — not `cannot_evaluate` — because a step reported as
    unevaluated when it WAS evaluated understates the evidence exactly as badly
    as the reverse overstates it.
    """
    coverage = harness.comparator_coverage()
    body = {"accounts_detail": [_row(status="agreed")]}
    table = {row["step"]: row for row in harness.per_step_table(body, coverage)}
    for step in ("R1", "R2", "R3b", "R5", "R6", "R7"):
        assert table[step][harness.AGREE] == 1, f"{step} was measured and not counted"
        assert table[step][harness.CANNOT] == 0


# ── TC2 · a refusal marks ONE step and blinds the rest ──────────────────────


def test_a_chain_refusal_marks_its_own_step_and_leaves_every_other_unevaluated(harness):
    """`shadow_account` returns on a refusal, so `compare()` never runs.

    Reporting R1 as "agreed" for an account that refused at R3 would claim an
    agreement that was never tested — the chain ran R1 without refusing, which
    is not the same fact as the two paths producing the same plan.
    """
    coverage = harness.comparator_coverage()
    body = {
        "accounts_detail": [
            _row(status="chain_refused", refusal_step="R3", refusal_type="SizeNotServed")
        ]
    }
    table = {row["step"]: row for row in harness.per_step_table(body, coverage)}

    assert table["R3"][harness.DISAGREE] == 1
    for step in ("R1", "R2", "R3b", "R4", "R5", "R6", "R7"):
        assert table[step][harness.DISAGREE] == 0
        assert table[step][harness.AGREE] == 0
        assert table[step][harness.CANNOT] == 1
        assert "chain_refused_at_R3_so_compare_never_ran" in table[step]["reasons"]


def test_an_account_nobody_could_ask_about_is_unevaluated_at_all_eight_steps(harness):
    coverage = harness.comparator_coverage()
    body = {
        "accounts_detail": [
            _row(status="not_attempted", blocked_reason="connection_size_unresolved")
        ]
    }
    table = {row["step"]: row for row in harness.per_step_table(body, coverage)}
    for step in harness.STEPS:
        assert table[step][harness.CANNOT] == 1
        assert table[step][harness.AGREE] == 0
        assert table[step][harness.DISAGREE] == 0


# ── TC3 · the RED proof, as an assertion rather than a paragraph ────────────


def test_a_divergence_at_a_covered_step_is_counted_at_that_step(harness):
    """The mutation the `--sabotage R1` run performs on real rows, in one case.

    On the live database this moved R1 from `47 / 0 / 0` to `46 agree / 1
    disagree` and `by_step` from `{}` to `{'R1': 1}`. Here it is the same
    movement with the database taken out of it, so the count itself is pinned.
    """
    coverage = harness.comparator_coverage()
    body = {
        "accounts_detail": [
            _row(status="agreed"),
            _row(
                account_no="AC-2",
                status="disagreed",
                divergences=[{"step": "R1", "service": "", "note": "plan version"}],
            ),
        ]
    }
    table = {row["step"]: row for row in harness.per_step_table(body, coverage)}
    assert table["R1"][harness.AGREE] == 1
    assert table["R1"][harness.DISAGREE] == 1
    assert table["R1"][harness.CANNOT] == 0


def test_R3_and_R4_each_carry_THEIR_OWN_evidence_and_the_fused_row_is_gone(
    harness,
):
    """⚠ **THE FUSED ROW IS GONE AND THAT IS `DEF-2823` (2026-08-31).**

    This test used to assert the opposite: that `compare()` produced ONE
    `R3/R4` divergence, that an agreement there was attributable to neither
    half, and that both R3 and R4 therefore read `cannot_evaluate`. **On a run
    where the base agreed on all 47 accounts, both steps reported `0 / 0 / 47`
    — which is a true statement and useless evidence**, because the cutover's
    own rule is that a step switches only when ITS OWN class is at zero.

    `BR-RAT-088` says where the seam is: *"R3's refusal semantics are unchanged
    — a size absent from the schedule still means not served — but the base
    itself now resolves through R4."* So **R3 is compared on the connection
    SIZE and R4 on the base AMOUNT**, and each row carries its own count.

    The ninth `R3/R4` row is not merely unused — it is REMOVED, because
    reporting it beside the two real rows would double-count every account and
    invite a reader to take the joint figure as evidence for either half.

    ⚠ **AND R3 STOPPED BEING COMPARED ON 2026-09-01 (`DEF-2878`), WHICH LEFT
    THIS CASE RED ON THE BRANCH TIP (`DEF-2871`).** The lane that made R3's size
    an INVARIANT — because comparing it compared a value with itself, which is
    `DEF-2839`'s fault one step over — correctly removed R3 from `compare()` and
    from the harness's own `compared` set, and did not move this assertion with
    it. The change was right and its own lane could not have seen this: the
    assertion lives in a file about a different subject, and nothing in
    `run_gates` executes it.

    **So the case is split rather than weakened.** R4 keeps the whole of the
    original claim — its own comparison, its own count, `figures_match` among
    its reasons — and R3 asserts what is now TRUE of it: an AGREEING account
    leaves R3 reading *cannot evaluate*, never *agree*, because nothing put a
    figure beside another one. Asserting agreement for R3 would be asserting the
    very circularity `DEF-2878` removed.
    """
    coverage = harness.comparator_coverage()
    body = {"accounts_detail": [_row(status="agreed")]}
    rows = harness.per_step_table(body, coverage)
    table = {row["step"]: row for row in rows}
    assert "R3/R4" not in table, [row["step"] for row in rows]

    # R4 — the AMOUNT — is compared, and carries its own evidence.
    assert table["R4"][harness.AGREE] == 1
    assert table["R4"][harness.CANNOT] == 0
    assert "figures_match" in table["R4"]["reasons"]

    # R3 — the SIZE — is an invariant since DEF-2878. Its ONE independent piece
    # of evidence is a chain REFUSAL (`SizeNotServed`), which is why it must
    # stay refusable; an agreeing account says nothing about it at all.
    assert table["R3"][harness.AGREE] == 0
    assert table["R3"][harness.CANNOT] == 1
    assert "R3" in coverage["refusable"]


# ── TC4 · the coverage facts the recommendation rests on ────────────────────


def test_the_comparator_covers_ALL_EIGHT_steps_and_fuses_none_of_them(harness):
    """The coverage fact the whole recommendation rests on, restated after
    `DEF-2823`.

    ⚠ **THIS SET SAID `{"R1", "R2", "R3/R4"}` UNTIL 2026-08-31 AND THEN
    `{"R1", "R2", "R3/R4", "R3b", "R5", "R6", "R7"}` FOR PART OF THE SAME DAY.**
    R3b, R5, R6 and R7 joined with `DEF-2798`; R3 and R4 joined with
    `DEF-2823`, when the fused base was split into the SIZE (R3) and the AMOUNT
    (R4). All eight now carry their own comparison.

    ⚠ **AND R3 LEFT AGAIN ON 2026-09-01 (`DEF-2878`), WHICH LEFT THIS CASE RED
    ON THE BRANCH TIP (`DEF-2871`).** Its size was an INVARIANT the adapter
    handed the catalogue, so comparing it compared a value with itself —
    `DEF-2839`'s fault one step over — and a check that cannot fail is worse than
    no check (`DEF-182`). It is SEVEN compared steps now.

    **The title's *ALL EIGHT* is kept deliberately** and is still true of what it
    claims: all eight steps remain VISIBLE to the shadow — seven through a
    comparison, and R3 through its REFUSAL, which is the half that was never
    circular and the half that can release the step.

    If somebody widens `compare()` again, or re-fuses two steps, this goes RED
    and the published recommendation is re-derived instead of silently
    outliving its evidence.
    """
    coverage = harness.comparator_coverage()
    assert coverage["compared"] == {"R1", "R2", "R3b", "R4", "R5", "R6", "R7"}
    assert harness.FUSED_BASE not in coverage["compared"]
    # R3 is not compared and MUST stay refusable, or it becomes invisible to the
    # shadow end to end — a step that can produce no finding of any kind cannot
    # be switched on evidence, which is exactly what DEF-2798 measured for R7.
    assert "R3" not in coverage["compared"]
    assert "R3" in coverage["refusable"]


def test_r7_is_compared_and_can_never_be_refused_at(harness):
    """R7 (`resolve_taxes`) raises nothing and never will — a failed
    applicability condition means NO LINE, not an error (`DEF-273`).

    ⚠ **SO THE COMPARISON IS THE ONLY THING THAT CAN EVER EVALUATE R7**, which
    is why this case now asserts that it IS compared. Before `DEF-2798` R7 was
    neither compared nor refusable: it was invisible to the shadow end to end,
    and a step that cannot produce a finding of any kind cannot be switched on
    evidence.
    """
    from apps.rating import resolution

    coverage = harness.comparator_coverage()
    assert "R7" not in coverage["refusable"]
    assert "R7" not in set(resolution.refusal_steps().values())
    assert "R7" in coverage["compared"]


def test_r3b_r5_and_r6_can_now_both_refuse_and_be_compared(harness):
    """Their only possible finding used to be a REFUSAL. A run in which none of
    them refused reported zero disagreements at three steps whose figures were
    never put beside the live path's — which is what the 2026-08-31 measurement
    found, and why none of them was ready to switch.

    `DEF-2798` gave each of them a comparison off objects both paths already
    hold: R3b the billable quantity, R5 the money factor, R6 the granted
    discount set.
    """
    coverage = harness.comparator_coverage()
    for step in ("R3b", "R5", "R6"):
        assert step in coverage["refusable"]
        assert step in coverage["compared"]


def test_the_coverage_map_refuses_to_under_report(harness):
    """`comparator_coverage()` asserts its own map against `compare()`'s source.

    PROVED RED: with `"R2"` removed from `compared` the call raises
    *"resolution_shadow.compare() now emits divergences at ['R2'], which this
    harness would report as 'cannot evaluate'"*. A coverage map that silently
    under-reports would turn a measured disagreement into a comfortable blank,
    which is the same class of failure as the third column itself.
    """
    # The guard is exercised by every other case in this file calling
    # `comparator_coverage()`; this one states the contract it enforces.
    coverage = harness.comparator_coverage()
    assert coverage["compared"], "the coverage map came back empty"
    assert "R1" in coverage["refusable"] and "R3" in coverage["refusable"]


def test_the_coverage_map_also_refuses_to_over_report(harness):
    """The direction that was NOT checked before `DEF-2798`, and the worse one.

    The old scan only asked *"does `compare()` emit a step this map does not
    know about"*. Nothing asked the reverse — *"does this map claim a step
    `compare()` does not emit"* — and that claim is what turns every account
    into an AGREEMENT at a step nothing was ever compared at. Exactly the
    failure `DEF-2798` records, pointing the other way.

    PROVED RED: adding `"R9"` to `compared` raises *"this harness claims
    resolution_shadow.compare() compares ['R9'] and its source emits no
    divergence at those steps"*.
    """
    import re
    from pathlib import Path

    from apps.billing import resolution_shadow

    coverage = harness.comparator_coverage()
    source = Path(resolution_shadow.__file__).read_text(encoding="utf-8")
    body = source.split("def compare(", 1)[1].split("\ndef ", 1)[0]
    emitted = set(re.findall(r'Divergence\(\s*"([^"]+)"', body))
    assert coverage["compared"] <= emitted, (
        "the harness claims a step compare() does not emit, so every account would "
        "be counted as agreeing at a step nothing was ever compared at"
    )


def test_the_source_scan_is_not_sensitive_to_indentation(harness):
    """`DEF-2798` — the scan used to split on two literal strings, one of which
    hard-coded twenty spaces, so it could only see a `Divergence(` call at one
    indentation. Two of the four comparisons added that day sit at bill level,
    sixteen spaces in, and the old scan found neither: it would have reported
    "nothing unexpected" while being blind to exactly the steps it exists to
    notice. A check that stops being able to fail when somebody reformats is
    `DEF-182`'s check-that-cannot-fail with an extra step.
    """
    import re

    at_service_level = '                Divergence(\n                    "R3b",'
    at_bill_level = '            Divergence(\n                "R7",'
    for snippet in (at_service_level, at_bill_level):
        assert re.findall(r'Divergence\(\s*"([^"]+)"', snippet), (
            f"the scan cannot see a Divergence written as {snippet!r}"
        )


# ── TC5 · nothing here is allowed to switch a step ──────────────────────────


def test_the_measurement_lane_switched_nothing(harness):
    """CR-052 task 20 measures; the RULING is the PO's and comes separately.

    ⚠ **THE NAME IS STILL EXACTLY RIGHT AND THE ASSERTION HAD TO MOVE ANYWAY
    (PO 2026-09-01).** What this case protects is ATTRIBUTION: a measurement
    lane may not switch a rule on, so every step live in the shipped default
    must be one a person ruled in. That property is unchanged. What changed is
    the answer to *which steps has a person ruled in* — it was none, and on
    2026-09-01 the Product Owner ruled the pair: *"Can you wire them in now -
    R3 and R4"*.

    So the assertion is no longer `== ""`, which after that ruling would have
    asserted that the PO's own instruction had not been carried out. It pins the
    RULED PAIR EXACTLY, and it still goes red on the thing it was written for:
    a lane that measures R1, R2, R5 or R7, likes what it sees and adds it here
    has switched a rule on without a ruling, and this test says so by name.
    """
    from apps.billing import resolution_switch

    assert resolution_switch.steps_served_by_chain() == frozenset({"R3", "R4"}), (
        "the switched set is not the pair the PO ruled on. This lane MEASURES "
        "and rules on nothing; switching follows a PO ruling per class. R3 and "
        "R4 were ruled on 2026-09-01 and switch together (BR-BIL-873); anything "
        "else here went live without a ruling, and anything MISSING here is a "
        "rollback that belongs in a commit that says so."
    )
    # DEF-2922: the constant is an unreachable fallback and decides nothing, so
    # asserting it ALONE is a check that cannot fail. It is asserted here only
    # to keep the two literals from drifting apart.
    assert resolution_switch.SERVED_BY_CHAIN_DEFAULT == "R3,R4"


# ── TC6 · the column that would have stopped the step-4 options (DEF-2838) ──


def test_def2838__the_table_says_which_steps_can_be_SWITCHED_and_not_only_which_agree(
    harness,
):
    """`DEF-2838` — *is anything switched ON* and *what COULD be* are different
    questions, and the table only ever asked the first.

    The step-4 cutover options were put to the Product Owner for all eight
    steps. They ruled R1, R2, R4 and R7 switchable; `resolution_switch.FORKED`
    could serve only R3, R4 and R5, so **not one of the four could move and the
    first wave was zero steps, not three.** Nothing raised, because a step with
    no seam sits in the agreement table looking exactly like a step ready to go.

    What is asserted here is that the column is DERIVED and not restated: every
    row's answer must equal membership of `resolution_switch.FORKED` as it is at
    the moment the table is built. A hand-written copy is `DEF-2341` and would go
    on printing *switchable* for a step whose fork had been removed.
    """
    from apps.billing import resolution_switch

    answers = harness.switchability()
    assert set(answers) == set(harness.STEPS), "every step gets an answer, or the column lies"
    for step, (switchable, note) in answers.items():
        assert switchable is (step in resolution_switch.FORKED), (
            f"{step}: the column says {switchable} and FORKED says "
            f"{step in resolution_switch.FORKED} — the column is restated, not derived"
        )
        if not switchable:
            assert "no fork" in note, f"{step} is not switchable and does not say why"

    # BR-BIL-873 rides along: a forked step that may not move ALONE says so, or
    # R4 gets offered without R3 again — which is exactly what happened.
    for pair in resolution_switch.JOINT:
        for step in pair:
            assert answers[step][0] is True
            for partner in sorted(set(pair) - {step}):
                assert partner in answers[step][1], (
                    f"{step} is welded to {partner} by a signed rule and the table "
                    "does not say so"
                )


def test_def2838__the_switch_column_reaches_the_per_step_rows(harness):
    """Built is not wired (hard-won law 2): the derivation existing is not the
    column existing. Every row the renderer reads must carry it."""
    from apps.billing import resolution_switch

    body = {"accounts_detail": [_row()]}
    table = {
        row["step"]: row
        for row in harness.per_step_table(body, harness.comparator_coverage())
    }
    for step in harness.STEPS:
        assert "switchable" in table[step], f"{step} row has no switch column"
        assert table[step]["switchable"] is (step in resolution_switch.FORKED)


# ══════════════════════════════════════════════════════════════════════════
# DEF-2965 · THE REPORT MUST SAY WHAT IT LOOKED AT, NOT ONLY WHAT IT FOUND
#
# ⚠ **THIS IS THE THIRD TIME THIS REPO HAS SHIPPED A MEASUREMENT WHOSE
# POPULATION COULD NOT CONTAIN THE FAILING CASE.** `DEF-2878` was R3's
# comparison comparing one value with itself; `DEF-2923` was a base-code check
# run over three utilities that all had base codes; `DEF-2965` is this one — the
# verdict read `MET` on three utilities, none of which bills electric, so no
# electric account was ever examined, and a utility billing electric on unsized
# meters would have lost every electric bill with `MET` on the screen.
#
# The cases below pin the two halves of the cure, and they are DIFFERENT halves:
#   * the report names the services it EXAMINED beside the ones the tenant
#     BILLS, so `MET` cannot be read over a service nothing looked at;
#   * the report asks the ESTATE and not the run, because the run's population
#     is the accounts already in a cycle whose meters already have sizes — so
#     the failing case sits one join outside it. Water was EXAMINED on the
#     measured utilities and still hid unsized meters, which is why the first
#     half alone is not enough.
# ══════════════════════════════════════════════════════════════════════════


def _rendered(harness, by_tenant, service_size_pairs=None):
    """`render()` over a synthetic body — the verdict block and nothing else.

    Structural, like every case above: the figures are one tenant's data on one
    day and asserting them would go red the moment somebody seeds a meter. What
    must not drift is which facts can produce which VERDICT.
    """
    result = {
        "posture": {
            "database": "t", "role": "t", "rolsuper": False, "rolbypassrls": False,
            "rows_visible_with_no_tenant_context": 0, "rls_enabled_and_forced": ["accounts"],
        },
        "body": {
            "accounts": 1, "attempted": 1, "agreed": 1, "disagreed": 0,
            "chain_refused": 0, "not_attempted": 0, "blocked_before_the_shadow": 0,
            "by_step": {}, "blocked_by_reason": {}, "accounts_detail": [],
            "classes": [], "blocked_classes": [], "cycles_measured": [],
            "per_step": [], "coverage": {"compared": [], "refusable": [], "refusal_classes": {}},
            "served_by_chain_default": "R3,R4",
            "probe": {
                step: {"agree": 0, "disagree": 0, "cannot_evaluate": 0,
                       "reasons": {}, "examples": []}
                for step in ("R1", "R2")
            },
            "carries": {
                "distinct_pairs": 1,
                "service_size_pairs": service_size_pairs or {"water · W-58": 1},
                "metered_services": {"water": 1},
                "unmetered_services": {},
                "verdicts": {},
                "by_tenant": by_tenant,
            },
        },
    }
    return harness.render(result)


def _tenant_row(**over):
    row = {
        "pairs": ["water · W-58"],
        "unpriced": [],
        "undetermined": [],
        "counts": {"water · W-58": 1},
        "no_base_code": [],
        # The sibling half of `DEF-2965`'s cure ships these two names; this
        # file uses them rather than a second vocabulary for one fact.
        "services_measured": ["water"],
        "enabled_services": ["water"],
        "unsized_services": [],
        "estate": {
            "water": {
                "connections": 4, "connections_with_no_size": 0,
                "billable_accounts": 4, "billable_accounts_with_no_size": 0,
                "banded": True, "connections_the_run_examined": 4,
            }
        },
    }
    row.update(over)
    return row


def test_def2965__a_clean_utility_can_still_read_MET(harness):
    """The control. If this ever fails, the verdict has stopped being able to
    say the passing word, which is `DEF-182`'s fault in the other direction —
    a check that cannot distinguish pass from fail is worse than no check."""
    text = _rendered(harness, {"cleanwater": _tenant_row()})
    assert "->  MET" in text
    assert "NOT MET" not in text.split("THE VERDICT, PER UTILITY")[1].split("\n")[1]


def test_def2965__a_service_the_tenant_BILLS_and_the_run_never_saw_is_NOT_MET(harness):
    """`DEF-2965`'s own shape. Three utilities read `MET`; none of them bills
    electric; no electric account was ever examined. A verdict over a population
    that misses a service the tenant bills is not a verdict."""
    text = _rendered(
        harness,
        {
            "brazosbend": _tenant_row(
                enabled_services=["electric", "water"],
                services_measured=["water"],
            )
        },
    )
    # The wording is the sibling half's — "MET for what was measured · SILENT
    # on electric" — and what this case pins is that it CANNOT be read as a
    # clean bill of health: the bare word `MET` never stands alone over a
    # service nothing looked at, and the service is named.
    verdict = text.split("THE VERDICT, PER UTILITY")[1]
    assert "SILENT on electric" in verdict
    assert "ENABLED BUT NOT EXAMINED: electric" in verdict
    assert "UNTESTED for it here" in verdict


def test_def2965__the_report_names_what_it_EXAMINED_beside_what_it_found(harness):
    """A count without its population is not a measurement. Both lists are
    printed, always, whether or not they differ."""
    text = _rendered(harness, {"cleanwater": _tenant_row()})
    assert "services examined: water" in text


def test_def2965__an_unsized_BILLABLE_account_on_the_ESTATE_is_NOT_MET(harness):
    """**The half the services-examined fix does NOT catch, and the reason the
    estate scan exists.** Water here IS examined and IS priced — every column
    the run produces is clean — and the utility still holds billable accounts
    whose connection has no recorded size. Those bills stop on billing day and
    no prepared run can see them, because the run's population is the accounts
    already in a cycle with sized meters."""
    text = _rendered(
        harness,
        {
            "brazosbend": _tenant_row(
                unsized_services=["water"],
                estate={
                    "water": {
                        "connections": 61, "connections_with_no_size": 12,
                        "billable_accounts": 40, "billable_accounts_with_no_size": 7,
                        "banded": True, "connections_the_run_examined": 40,
                    }
                },
            )
        },
    )
    assert "->  NOT MET" in text
    # ⚠ THE ACCOUNT COUNT, NOT ONLY THE METER COUNT. Seven accounts is the
    # number a person acts on; twelve meters is trivia until it is joined to
    # who stops being billed.
    assert "7 billable account(s) on 'water'" in text
    assert "12 of 61 connections" in text


def test_def2965__an_UNBANDED_service_with_no_recorded_size_is_NOT_a_finding(harness):
    """Sewer is RULED to have no size class — it is a share of the water usage
    charge and reads no register — so every sewer connection has no recorded
    size and none of them stops a bill. Reporting it as an alarm would send a
    person looking for a size the product will never hold."""
    text = _rendered(
        harness,
        {
            "sewerco": _tenant_row(
                enabled_services=["sewer", "water"],
                services_measured=["sewer", "water"],
                estate={
                    "sewer": {
                        "connections": 61, "connections_with_no_size": 61,
                        "billable_accounts": 61, "billable_accounts_with_no_size": 61,
                        "banded": False, "connections_the_run_examined": 61,
                    },
                    "water": {
                        "connections": 4, "connections_with_no_size": 0,
                        "billable_accounts": 4, "billable_accounts_with_no_size": 0,
                        "banded": True, "connections_the_run_examined": 4,
                    },
                },
            )
        },
    )
    assert "->  MET" in text
    assert "no size bands, so a size is neither recorded nor needed" in text
    assert "billable account(s) on 'sewer'" not in text


def test_def2965__both_new_sabotages_exist_and_are_WHOLE_PASS(harness):
    """Law 7 — a verdict that cannot say the failing word is not a verdict, and
    the switch that proves it must be runnable.

    ⚠ **WHOLE-PASS AND NOT PER-ROW.** `measure()` refuses a row mutation spread
    over several tenants, because the row it moved would no longer be
    identifiable. Both of these are statements about a POPULATION rather than
    about a row, so they must be in the whole-pass set or the release run —
    which is `--tenant all` — would refuse them.
    """
    from pathlib import Path as _Path

    text = _Path(SCRIPT).read_text(encoding="utf-8")
    assert '"estate-unsized"' in text
    assert '"service-coverage"' in text
    # Both must sit inside WHOLE_PASS_SABOTAGES, which is declared in `measure`.
    whole_pass = text.split("WHOLE_PASS_SABOTAGES = {", 1)[1].split("}", 1)[0]
    assert "estate-unsized" in whole_pass
    assert "service-coverage" in whole_pass


def _body(tenant, estate, *, examined=("water",), billed=("water",)):
    """One cycle's body, the shape `_measure_one_tenant` appends."""
    return {
        "_tenant": tenant,
        "_cycle": f"{tenant}/C1",
        "_period": ["2026-07-01", "2026-07-31", "2026-07-01"],
        "_blocked_before_the_shadow": 0,
        "_blocked_reasons": {},
        "_probe": {
            step: {"agree": 0, "disagree": 0, "cannot_evaluate": 0,
                   "reasons": {}, "examples": []}
            for step in ("R1", "R2")
        },
        "_money": {"accounts": 0, "base_rows": 0, "base_total": 0, "by_service": {}},
        "_estate": estate,
        "_carries": {
            "service_size_pairs": {"water · W-58": 1},
            "metered_services": {"water": 1},
            "unmetered_services": {},
            "services_measured": list(examined),
            "enabled_services": list(billed),
            "verdicts": {"water · W-58": {"priced": True, "source": "charge_code", "detail": "d"}},
            "unpriced": [],
            "undetermined": [],
            "services_with_no_base_code": [],
        },
        "accounts": 1, "attempted": 1, "agreed": 1, "disagreed": 0,
        "chain_refused": 0, "not_attempted": 0,
        "by_step": {}, "blocked_by_reason": {}, "accounts_detail": [],
        "classes": [], "blocked_classes": [],
    }


def _estate_row(**over):
    row = {
        "connections": 10, "connections_with_no_size": 0,
        "billable_accounts": 8, "billable_accounts_with_no_size": 0,
        "banded": True, "connections_the_run_examined": 8,
    }
    row.update(over)
    return row


def test_def2965__the_MERGE_derives_unsized_services_and_the_BANDED_GATE_decides(harness):
    """The banded gate lives in `_merge`, not in `render`, so it needs its own
    case — and it did not have one until a mutation proved the render-level
    case could not see it (`DEF-182`: a check whose output cannot distinguish
    pass from fail is worse than no check).

    Two services, identical numbers, opposite verdicts: the BANDED one is a
    finding, the unbanded one is not. Sewer is ruled to have no size class, so
    every sewer connection has no recorded size and none of them stops a bill.
    """
    merged = harness._merge(
        [
            _body(
                "twoservices",
                {
                    "water": _estate_row(
                        connections_with_no_size=12, billable_accounts_with_no_size=7
                    ),
                    "sewer": _estate_row(
                        banded=False,
                        connections_with_no_size=12,
                        billable_accounts_with_no_size=7,
                    ),
                },
                examined=("sewer", "water"),
                billed=("sewer", "water"),
            )
        ]
    )
    row = merged["carries"]["by_tenant"]["twoservices"]
    assert row["unsized_services"] == ["water"], row["unsized_services"]
    assert set(row["enabled_services"]) == set(row["services_measured"])


def test_def2965__the_MERGE_keeps_the_LARGEST_estate_count_across_cycles(harness):
    """One body is one CYCLE, not one utility. A utility's estate is the same
    fact every cycle, but a cycle that somehow saw fewer connections must not be
    able to SHRINK the finding — the mirror of the bug that once let a final
    empty cycle report `0 pair(s)` for a utility whose pairs were all priced.
    """
    merged = harness._merge(
        [
            _body("u", {"water": _estate_row(
                connections_with_no_size=12, billable_accounts_with_no_size=7)}),
            _body("u", {"water": _estate_row(
                connections_with_no_size=0, billable_accounts_with_no_size=0)}),
        ]
    )
    est = merged["carries"]["by_tenant"]["u"]["estate"]["water"]
    assert est["billable_accounts_with_no_size"] == 7
    assert merged["carries"]["by_tenant"]["u"]["unsized_services"] == ["water"]


def test_def2965__the_MERGE_accumulates_examined_services_across_cycles(harness):
    """A service exercised by ANY cycle has been examined. Assigning rather than
    accumulating would let the last cycle's narrower population decide, which is
    the mistake `by_tenant` already carries a warning about one field over."""
    merged = harness._merge(
        [
            _body("u", {"water": _estate_row()},
                  examined=("water",), billed=("electric", "water")),
            _body("u", {"water": _estate_row()},
                  examined=("electric",), billed=("electric", "water")),
        ]
    )
    row = merged["carries"]["by_tenant"]["u"]
    assert row["services_measured"] == ["electric", "water"]
    assert set(row["enabled_services"]) - set(row["services_measured"]) == set()


def test_def2965__banded_is_read_from_the_RATIFIED_list_and_sewer_is_not_banded(harness):
    """`_banded_services` decides whether a missing size is a finding at all, so
    it must come from `BR-TEN-171` and never from a list this script keeps.
    Electric has six ratified classes; sewer is ruled to have none."""
    banded = harness._banded_services()
    assert "electric" in banded
    assert "water" in banded
    assert "sewer" not in banded
