# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-1221 — file_defect.py hands a lane an id inside another lane's
#          reserved block whenever its own block sits above the register's
#          watermark. The allocator took max+1 and then stepped DOWN past every
#          ACTIVE block, which is exactly wrong when the blocks sit above it.
# Rules:   CLAUDE.md law 7 (prove a guard RED first) · law 11's id clause
#          (DEF-1787 — an allocated id is a blob too) · DEF-1182 (an allocator
#          must print the POSITIVE finding, not only what it skipped)
# Impacts: 10-scripts/file_defect.py::next_id
# ───────────────────────────────────────────────────────
"""AN ALLOCATED ID IS NEVER BELOW THE WATERMARK AND NEVER INSIDE A HELD BLOCK.

WHY THIS TEST EXISTS
--------------------
`next_id()` used to read::

    candidate = max(seen) + 1
    for low, high, owner in sorted(blocks, reverse=True):
        if low <= candidate <= high:
            candidate = low - 1          # ← DOWN
    while candidate in seen or any(l <= candidate <= h for l, h, _ in blocks):
        candidate -= 1

Measured against the live registers on 2026-09-03, with the register's highest
id at **DEF-3524**, that printed **sixteen** "stepping down" notes and returned
**DEF-2337** — one thousand one hundred and eighty-seven below the frontier,
inside no reservation and therefore inside nobody's promise, which is DEF-1787's
collision shape. On 2026-08-27 the same walk returned DEF-1080, which was inside
the CR-043 bills lane's ACTIVE block, and the row had to be renumbered by hand.

**Every note the tool printed named a block it stepped PAST. None named where
the answer landed** — so its output read as the guard working. That is the same
finding law 11 records twice about `git --stat`: a check whose output cannot
distinguish pass from fail is worse than no check, because it is trusted.

WHAT IS ASSERTED, AND WHY THESE TWO CLAUSES AND NOT A GOLDEN ID
---------------------------------------------------------------
Two properties, both of which the old code violates and neither of which pins a
number that will rot:

  1. the id is **greater than every id already in the register** — never below
     the frontier, so it cannot land in an abandoned gap that another lane's
     reservation has since been drawn around;
  2. the id is **inside no held block** — which is the whole point of the
     reservations file.

A test that asserted "returns DEF-3540" would go red the first time somebody
opens a block, which is weekly here. These two clauses are true forever.

Cases are DATA rather than the live reservations file, so they still mean
something on the day that file no longer contains these blocks — the same
reasoning `test_def1182_reserved_blocks.py` records for itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

HEADER = "| Block | Lane | Opened | State |\n|---|---|---|---|\n"


def _held(*blocks: tuple[int, int]) -> str:
    rows = [
        f"| DEF-{low}–{high} | some other lane | 2026-09-03 | **ACTIVE** |"
        for low, high in blocks
    ]
    return HEADER + "\n".join(rows) + "\n"


def _load(reservations: Path):
    spec = importlib.util.spec_from_file_location("fd", ROOT / "10-scripts" / "file_defect.py")
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["file_defect"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    module.RESERVATIONS = reservations
    return module


def _allocated(module, seen: set[int], mine: str = "") -> int:
    return int(module.next_id(seen, mine).removeprefix("DEF-"))


# (name, the register's ids, the blocks other lanes hold)
CASES = [
    (
        "the watermark sits just under somebody else's block",
        {1, 2, 1179},
        [(1180, 1209), (1210, 1249)],
    ),
    (
        "a stack of adjacent blocks — the old walk cascaded down through all of them",
        {1, 3524},
        [(3200, 3219), (3220, 3239), (3500, 3519), (3520, 3539)],
    ),
    (
        "the block containing max+1 is already partly used",
        {1, 500, 501, 502},
        [(500, 520)],
    ),
    (
        "blocks far above the watermark, none of them containing max+1",
        {1, 100},
        [(3000, 3009)],
    ),
    (
        "no blocks at all",
        {1, 42},
        [],
    ),
]


@pytest.mark.parametrize("name,seen,blocks", CASES, ids=[c[0] for c in CASES])
def test_an_allocated_id_is_above_the_watermark_and_outside_every_block(
    tmp_path, name, seen, blocks
) -> None:
    path = tmp_path / "14-id-reservations.md"
    path.write_text(_held(*blocks) if blocks else HEADER, encoding="utf-8")
    module = _load(path)

    allocated = _allocated(module, set(seen))

    assert allocated > max(seen), (
        f"{name}: DEF-{allocated} is at or below the register's highest id "
        f"DEF-{max(seen)}. An id below the frontier sits in an abandoned gap that "
        f"a later reservation may have been drawn around — DEF-1787's shape, and "
        f"the old descending walk returned DEF-2337 against a watermark of 3524."
    )
    assert not any(low <= allocated <= high for low, high in blocks), (
        f"{name}: DEF-{allocated} is inside a block another lane is holding. "
        f"That is the collision this tool exists to prevent, caused by the tool."
    )
    assert allocated not in seen, f"{name}: DEF-{allocated} is already in the register"


def test_the_positive_finding_is_printed_not_only_the_skips(tmp_path, capsys) -> None:
    """DEF-1182's other half: silence about a block must not read as clearance.

    The tool listed the blocks it stepped past and said nothing about where the
    answer sat, which gives a lane the wrong half of the answer.
    """
    path = tmp_path / "14-id-reservations.md"
    path.write_text(_held((100, 109)), encoding="utf-8")
    module = _load(path)

    allocated = _allocated(module, {1, 99})
    notes = capsys.readouterr().err
    assert f"allocated DEF-{allocated}" in notes, (
        "the allocator named every block it avoided and never named where the id "
        "landed — a check whose output cannot distinguish pass from fail"
    )
    assert "inside no active block" in notes


def test_it_still_allocates_inside_the_callers_own_block(tmp_path) -> None:
    """DEF-1814's regression: `--block` means *file INTO this range*.

    The upward walk must not reach over the caller's own reservation — that
    reservation is the one place the lane is supposed to land.
    """
    path = tmp_path / "14-id-reservations.md"
    path.write_text(
        HEADER
        + "| DEF-1810–1839 | this lane | 2026-09-03 | **ACTIVE** |\n"
        + "| DEF-1900–1929 | another lane | 2026-09-03 | **ACTIVE** |\n",
        encoding="utf-8",
    )
    module = _load(path)

    allocated = _allocated(module, {1, 1795}, mine="1810-1839")
    assert 1810 <= allocated <= 1839, (
        f"DEF-{allocated} is outside the caller's own block — a lane dispatched "
        f"with a reservation must file into it (DEF-1814)"
    )


def test_a_full_own_block_refuses_rather_than_spilling(tmp_path) -> None:
    """Here a refusal IS right: spilling out of your own block is a collision.

    The distinction the fix rests on — refuse the BAD ID, never the FILING — has
    an edge: when the caller has named a block and that block is full, there is
    no good id to give, and inventing one outside the reservation is the very
    thing `--block` exists to stop.
    """
    path = tmp_path / "14-id-reservations.md"
    path.write_text(HEADER + "| DEF-700–702 | this lane | 2026-09-03 | **ACTIVE** |\n", "utf-8")
    module = _load(path)

    with pytest.raises(SystemExit) as refusal:
        module.next_id({1, 700, 701, 702}, "700-702")
    assert "every id in DEF-700-702 is taken" in str(refusal.value)
