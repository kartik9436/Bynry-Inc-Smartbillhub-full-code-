# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-1182 — file_defect.py allocated INTO an active block, twice in one
#          day, because reserved_blocks() searched the whole row for the literal
#          string "**ACTIVE**" and was blind to every other way a row says "held".
# Rules:   DEF-978 (an allocator must be able to SEE a reservation) · DEF-1087
#          (a table row's cells vary in width, so a fixed index is not a column)
# Impacts: 10-scripts/file_defect.py::reserved_blocks
# ───────────────────────────────────────────────────────
"""A held block must be invisible to nobody.

WHY THIS TEST EXISTS
--------------------
`reserved_blocks()` decides which id ranges the allocator must step around. It
used to read::

    if not line.startswith("|") or "**ACTIVE**" not in line:
        continue

— a literal substring over the ENTIRE row. Measured on 2026-08-27 that was blind
to four blocks a live lane was filing into:

    DEF-1060-1089   state "**ACTIVE — NARROWED 2026-08-27.**"
    DEF-1390-1419   state "**RESERVED, not started**"
    DEF-1420-1449   state "**RESERVED, not started**"
    DEF-1450-1479   state "**RESERVED, not started**"

The first says ACTIVE and never contains the exact string `**ACTIVE**`; the other
three use the second of the two words a row can carry, which the check did not
know about. **The failure is silent and it hands the same id to two lanes.**

The second half is subtler and is why the fix reads a NAMED column: `cells[-1]`
is only the state while every row has exactly four cells. Rows in this repo's
tables demonstrably vary in width — DEF-1087 is that same mistake at register
scale, where eleven rulings were written into the wrong cell and read as OPEN.

These cases are written as DATA rather than against the live reservations file,
so the test still means something on the day that file no longer contains them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HEADER = "| Block | Lane | Opened | State |\n|---|---|---|---|\n"

# Each case is (row, should_be_treated_as_held, why).
CASES = [
    ("| DEF-100–109 | a lane | 2026-08-27 | **ACTIVE** |", True, "the plain form"),
    (
        "| DEF-200–209 | a lane | 2026-08-27 | **ACTIVE — NARROWED 2026-08-27.** ⚠ note |",
        True,
        "ACTIVE with a qualifier — the exact `**ACTIVE**` string never appears",
    ),
    (
        "| DEF-300–309 | a lane | 2026-08-27 | **RESERVED, not started** |",
        True,
        "reserved is held; the old check knew only one of the two words",
    ),
    (
        "| DEF-400–409 | a lane | 2026-08-27 | **RELEASED 2026-08-27** — used 400, 401 |",
        False,
        "released is not held",
    ),
    (
        "| DEF-500–509 | a lane | 2026-08-27 | **RELEASED** — was ACTIVE for 500–503 |",
        False,
        "RELEASED wins where both words appear: prose about a finished block "
        "must not re-reserve the range",
    ),
]


def _load(tmp_reservations: Path):
    spec = importlib.util.spec_from_file_location("fd", ROOT / "10-scripts" / "file_defect.py")
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["file_defect"]
    try:
        spec.loader.exec_module(spec and module)
    finally:
        sys.argv = argv
    module.RESERVATIONS = tmp_reservations
    return module


def test_every_way_a_row_says_held_is_seen(tmp_path) -> None:
    path = tmp_path / "14-id-reservations.md"
    path.write_text(HEADER + "\n".join(row for row, _, _ in CASES) + "\n", encoding="utf-8")
    module = _load(path)

    seen = {(lo, hi) for lo, hi, _ in module.reserved_blocks()}
    for row, held, why in CASES:
        low = int(row.split("DEF-")[1].split("–")[0])
        block = (low, low + 9)
        if held:
            assert block in seen, f"DEF-{low} should be held — {why}"
        else:
            assert block not in seen, f"DEF-{low} should NOT be held — {why}"


def test_the_state_is_a_named_column_not_a_fixed_index(tmp_path) -> None:
    """DEF-1087's shape: a row that gained a cell must not shift the state."""
    path = tmp_path / "14-id-reservations.md"
    path.write_text(
        HEADER + "| DEF-600–609 | a lane | 2026-08-27 | **ACTIVE** | a fifth cell |\n",
        encoding="utf-8",
    )
    module = _load(path)
    assert (600, 609) in {(lo, hi) for lo, hi, _ in module.reserved_blocks()}, (
        "a trailing cell moved the state out from under a fixed index — "
        "the block became invisible and its ids allocatable"
    )


def test_a_missing_file_yields_no_blocks_rather_than_raising(tmp_path) -> None:
    """Nothing must stop a lane filing a defect (the docstring's own promise)."""
    module = _load(tmp_path / "does-not-exist.md")
    assert module.reserved_blocks() == []
