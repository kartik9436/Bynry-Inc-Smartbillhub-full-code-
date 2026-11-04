# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 `P0.17` — conformed dimensions.
#          Depends on `P0.16` (the dimension model), lane REP-P0A's.
# Rules:   BR-REP-006 · the brief §7.2 · hard-won law 7 (a check that cannot
#          cover its whole subject prints what it SKIPPED beside what it
#          checked)
# ───────────────────────────────────────────────────────
"""ONE DIMENSION, ONE MEANING — the rule, then the product.

Two halves, deliberately separate:

  1. **Does the rule work?** Proved against a hand-built conflicting pair that
     will never change, so the proof does not depend on what the registry
     happens to hold this week.
  2. **Does the product satisfy it?** Run over the live registry.

⚠ **THE SECOND HALF DEPENDS ON `P0.16`, WHICH IS LANE REP-P0A's AND MAY NOT BE
ON THE BRANCH YET.** It is resolved by name at call time and **FAILS BY NAME**
when it is absent, rather than skipping. A skip here would be law 7's *192
skips read as a pass*: this file's whole job is to answer *are the nine
datasets conformed*, and *we could not look* is not an answer that may wear
green.
"""

from __future__ import annotations

import pytest

from apps.reports.dimension_conformance import (
    DimensionConflict,
    assert_conformed,
    check_conformed,
)

#: Exactly the brief's own example: *"one calls it Service with eleven values,
#: another calls it Utility with three"*. Hand-built, so the proof that the
#: rule fires is independent of every registry it will ever be pointed at.
ELEVEN = [
    "electric", "water", "gas", "sewer", "trash", "storm_water",
    "solar", "broadband", "thermal", "battery", "fire",
]
THREE = ["electric", "water", "gas"]


def test_p0_17_the_rule_catches_a_relabelled_dimension():
    problems = check_conformed(
        [
            ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
            ("consumption", {"key": "service", "label": "Utility", "values": ELEVEN}),
        ]
    )
    assert len(problems) == 1
    assert "labelled 'Service'" in problems[0] and "'Utility'" in problems[0]


def test_p0_17_the_rule_catches_a_narrowed_value_set():
    problems = check_conformed(
        [
            ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
            ("consumption", {"key": "service", "label": "Service", "values": THREE}),
        ]
    )
    assert len(problems) == 1
    assert "11 values" in problems[0] and "3 in" in problems[0]
    # The message must NAME the difference, not merely report one: a lane told
    # "these disagree" over eleven values reads eleven values twice.
    assert "'fire'" in problems[0] and "'battery'" in problems[0]


def test_p0_17_both_faults_at_once_are_both_reported():
    problems = check_conformed(
        [
            ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
            ("consumption", {"key": "service", "label": "Utility", "values": THREE}),
        ]
    )
    assert len(problems) == 2, "one conflict fixed at a time over nine datasets is nine runs"


def test_p0_17_a_dimension_deferring_to_the_live_lookup_never_conflicts():
    """BR-REP-006: `values=None` means *ask the lookup*, not *there are none*."""
    assert check_conformed(
        [
            ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
            ("consumption", {"key": "service", "label": "Service", "values": None}),
        ]
    ) == []


def test_p0_17_a_conformed_pair_is_silent():
    assert check_conformed(
        [
            ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
            ("consumption", {"key": "service", "label": "Service", "values": list(reversed(ELEVEN))}),
        ]
    ) == [], "order is not meaning — a value set is a SET"


def test_p0_17_assert_conformed_raises_and_names_the_datasets():
    with pytest.raises(DimensionConflict, match="consumption"):
        assert_conformed(
            [
                ("ar_aging", {"key": "service", "label": "Service", "values": ELEVEN}),
                ("consumption", {"key": "service", "label": "Utility", "values": ELEVEN}),
            ]
        )


# ── The live half ──────────────────────────────────────────────────────────
def _live_declarations():
    """Every `(dataset_key, dimension)` pair the registry publishes, or None.

    Resolved by NAME at call time — `P0.16` is lane REP-P0A's and the shape is
    the brief's: a dataset registry where each dataset declares `dimensions`.
    Three spellings are accepted because the sibling has not landed yet and the
    attribute name is theirs to choose; what is NOT accepted is finding none
    and calling that a pass.
    """
    from importlib import import_module

    try:
        registry = import_module("apps.reports.datasets")
    except ImportError:
        return None
    datasets = None
    for name in ("DATASETS", "REGISTRY", "DATASET_REGISTRY"):
        datasets = getattr(registry, name, None)
        if datasets is not None:
            break
    if datasets is None:
        return None
    pairs = []
    items = datasets.items() if hasattr(datasets, "items") else enumerate(datasets)
    for key, dataset in items:
        dims = dataset.get("dimensions") if isinstance(dataset, dict) else getattr(dataset, "dimensions", None)
        for dim in dims or ():
            pairs.append((str(key), dim))
    return pairs


def test_p0_17_the_nine_datasets_are_conformed():
    """`P0.17`'s own outcome, over the live dimension model.

    ⚠ **FAILS BY NAME WHEN `P0.16` IS ABSENT.** That is a DEPENDENCY on lane
    REP-P0A and not a policy failure — but it is still red, because the
    question this file asks has no answer until the registry exists, and a
    green here would say it had one.
    """
    pairs = _live_declarations()
    if pairs is None:
        pytest.fail(
            "CR-142 `P0.16`'s dimension model is not on this branch: "
            "`apps.reports.datasets` publishes no dataset registry. `P0.17` is "
            "its test and cannot run before it (lane REP-P0A). DEPENDENCY, not "
            "a conformance failure."
        )
    assert pairs != [], (
        "the registry exists and declares NO dimensions at all — `P0.16` says "
        "*every dataset states its dimensions*, so an empty walk is a finding "
        "and not a pass (hard-won law 7: a check reporting zero over a scope it "
        "silently excludes)."
    )
    assert_conformed(pairs)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.17
# screens: none
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the three rule cases were written against `check_conformed` returning [] and each failed before the comparison logic existed; the live case is RED on this branch and names P0.16 as the cause.
# exceptions: (1) the live case FAILS rather than skips while `P0.16` is unlanded — stated in the lane report, and it goes green the moment the sibling's registry lands · (2) a different KEY for one idea is structurally invisible here and `dimension_conformance.py` says so
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
