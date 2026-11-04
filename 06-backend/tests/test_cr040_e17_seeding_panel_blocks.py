# ── Trace ──────────────────────────────────────────────
# Story:    CR-040 wave E task 17 — "the seeding panel names the new blocks
#           rather than reporting a module short"
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line) · CR-039 wave B task 7
#           (dependency-aware reporting: name the ROOT failure, mark the rest as
#           consequences) · CR-040 task C8/D12/D13/D14 (the three blocks between
#           the two bill runs)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-040 E17 — the three blocks waves C and D added were invisible to the
dependency graph the Sample data panel renders.

**WHAT WAS ACTUALLY SHORT, MEASURED BEFORE ANYTHING WAS WRITTEN.** The panel is
block-aware already: `stored_blocks()` reads `sample_data_runs.blocks[]` and
`SampleDataReportBody` renders one line per BLOCK whenever the run recorded
them, so the three new blocks DO get a line. What they did not get is an
**edge**. `BLOCK_DEPENDENCIES` carried ten of the fourteen blocks and named none
of `payments:seed_sample_refund`, `billing:seed_sample_correction` or
`billing:seed_sample_second_cycle` — so on a tenant whose first bill run failed,
`_failure_class` found no upstream for any of them and marked **four separate
roots**. The operator is then told to *"Start here"* four times over one cause,
and the module line above it reports `billing` once for three blocks: a module
short of what actually happened.

⚠ **AND THE EDGES ARE NOT INVENTED HERE EITHER.** CR-039 wave B task 7's own
standard is that the graph is derived from what the code already says — *"do NOT
invent a dependency graph nobody ratified"* — so every edge added carries the
file and the words it comes from, and `test_cr039__every_declared_edge_is_quoted
_from_the_file_it_cites` greps them back out. All three seeders already state
their upstreams in the sentence a refusing block prints at a person.

**THE RATCHET IS THE POINT.** Three blocks landed edgeless on 2026-08-27 and
nothing objected, because the existing tests ask *"is every declared edge true?"*
and never *"is every block declared?"* — a graph can be perfectly honest and
half-empty. `ROOT_BLOCKS` makes the empty half explicit, and the first test below
fails the day a fifteenth block lands with neither an edge nor a place on that
list.
"""

from __future__ import annotations

import pytest

from apps.tenancy import sample_data

pytestmark = pytest.mark.django_db


def test_e17__every_block_is_either_a_declared_root_or_carries_an_edge():
    """The ratchet CR-039 wave B did not leave behind.

    A block with no edge is not wrong — four of the fourteen genuinely depend on
    nothing. It is UNANSWERED, and the two look identical in a dict that only
    holds edges. `ROOT_BLOCKS` is the answer written down, so *"this block needs
    nothing"* and *"nobody has looked at this block"* stop being the same
    absence.

    ⚠ **A ROOT IS NOT QUOTED AND AN EDGE IS, and the asymmetry is deliberate.**
    An edge is a CLAIM about the code and must be greppable back out of it
    (`test_cr039__every_declared_edge_is_quoted_from_the_file_it_cites`). A root
    is the absence of a claim; there is no sentence to quote, so what is checked
    instead is that somebody decided.

    RED-PROVED before the fix, and the failure it actually gave is worth keeping
    verbatim rather than tidying into the assertion it would give today:

        E   AttributeError: module 'apps.tenancy.sample_data' has no attribute
            'ROOT_BLOCKS'

    The list did not exist at all, which is the whole finding — nothing in the
    repo had ever asked which blocks depend on nothing, so the question had no
    place to be answered. The assertion below is what fails from now on.
    """
    keys = [spec.key for spec in sample_data.SAMPLE_MODULES]
    assert len(keys) == len(set(keys)), f"duplicate block keys: {keys}"
    undecided = sorted(
        key
        for key in keys
        if key not in sample_data.ROOT_BLOCKS and key not in sample_data.BLOCK_DEPENDENCIES
    )
    assert not undecided, (
        f"{len(undecided)} sample block(s) are neither in ROOT_BLOCKS nor in "
        f"BLOCK_DEPENDENCIES: {', '.join(undecided)} — a block with no edge and "
        "no declared root is a dependency nobody has decided"
    )


def test_e17__a_root_and_an_edge_are_never_the_same_block():
    """Declared-root AND edged is a contradiction, and it would be silent.

    `_failure_class` walks edges, so a block in both would be marked a
    CONSEQUENCE while the list says it depends on nothing. Nothing else in the
    repo would notice.
    """
    both = sorted(set(sample_data.ROOT_BLOCKS) & set(sample_data.BLOCK_DEPENDENCIES))
    assert not both, (
        f"{', '.join(both)} is declared a ROOT and also carries an edge — one of "
        "the two statements is wrong"
    )
    unknown = sorted(
        key for key in sample_data.ROOT_BLOCKS if key not in {s.key for s in sample_data.SAMPLE_MODULES}
    )
    assert not unknown, f"ROOT_BLOCKS names {', '.join(unknown)}, which is not a block of the sample set"


def test_e17__the_three_blocks_between_the_two_bill_runs_name_their_upstreams():
    """The specific gap CR-040 waves C and D opened, pinned by name.

    Named individually rather than left to the general ratchet above, because
    the ratchet would also pass if a later lane "closed" it by dropping all
    three onto `ROOT_BLOCKS`. Each of these three demonstrably depends on
    something the code itself already names in a refusal sentence.

    ⚠ **AND THE SECOND CYCLE DEPENDS ON THE READS, NOT ON THE FIRST CYCLE — the
    edge that is deliberately ABSENT is the interesting one.** Both billing
    blocks call the same `_preconditions`, so a tenant with no cycle or an
    unmapped tax authority fails both. That is a COMMON CAUSE, not a
    dependency: July bills from July's own reads and needs no June invoice, and
    an edge saying otherwise would tell an operator that fixing cycle one fixes
    cycle two when what fixes both is the setup fact underneath them. Two roots
    and one fix is the honest report; `_root_for`'s own docstring already
    chooses that direction — *"an unmarked failure is reported as something to
    look at, which is at worst noise"*.
    """
    expected = {
        "payments:seed_sample_refund": {
            "customers:seed_sample_records",
            "payments:seed_sample_records",
        },
        "billing:seed_sample_correction": {
            "customers:seed_sample_records",
            "billing:seed_sample_records",
        },
        "billing:seed_sample_second_cycle": {
            "metering:seed_sample_reads",
        },
    }
    for block, upstreams in expected.items():
        declared = {edge[0] for edge in sample_data.BLOCK_DEPENDENCIES.get(block, ())}
        assert declared == upstreams, (
            f"{block} declares {sorted(declared)}; its own refusal sentences name "
            f"{sorted(upstreams)}"
        )


def test_e17__a_failed_first_bill_run_names_ONE_root_across_the_money_that_follows_it():
    """The behaviour, not the table: one cause, three consequences.

    This is what an operator actually sees on the panel. A first bill run that
    cannot issue takes the payments block with it (that edge existed), and
    before this change it ALSO took the refund and the correction — each
    reported as its own independent root, because `_failure_class` walks
    declared edges only and there were none to walk. Three extra *"Start here"*
    markers over one cause, on the screen whose entire job is to say which line
    to read first.

    RED-PROVED before the fix, verbatim:

        E   AssertionError: 3 roots across the money blocks
            (billing:seed_sample_correction, billing:seed_sample_records,
            payments:seed_sample_refund) — one failure, one root
    """
    head = "billing:seed_sample_records"
    downstream = {
        "payments:seed_sample_records",
        "payments:seed_sample_refund",
        "billing:seed_sample_correction",
    }
    non_seeded = {head} | downstream
    roots = sorted(
        key for key in non_seeded if sample_data._failure_class(key, non_seeded)[0] == "root"
    )
    assert roots == [head], (
        f"{len(roots)} roots across the money blocks ({', '.join(roots)}) — one "
        "failure, one root"
    )
    for key in sorted(downstream):
        failure_class, root_block = sample_data._failure_class(key, non_seeded)
        assert failure_class == "consequence", f"{key} is reported as its own cause"
        assert root_block == head, (
            f"{key} is a consequence of {root_block!r}; the block that actually "
            f"broke is {head}"
        )
