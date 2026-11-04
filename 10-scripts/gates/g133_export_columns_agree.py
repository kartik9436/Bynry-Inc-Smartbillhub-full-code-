#!/usr/bin/env python3
"""G133 — 6·2's column names are the SERVER's column names.

WHY THIS GATE EXISTS (CR-140-BRC09 `P4.12`, 2026-09-24)
--------------------------------------------------------
`P4.13` made `POST /exports` take `columns` — RULED, PO 2026-09-24: *"all
selected columns will go in downloaded file"* — and `P4.12` is the first screen
that sends them. The names on the wire are the export RESOURCE's own column
names, declared in `06-backend/apps/ledger/finance_exports.py` as
`Column("<name>", "<source field>")`, and the screen's ▦ chooser reports back the
ones a clerk ticked.

**`apps/tenancy/exports.columns_for()` drops a name the resource does not have,
and falls back to the resource's DEFAULT set when it recognises none of them.**
Both behaviours are right — `BR-SHL-011`'s *"fall back, never 4xx"*, and a
zero-column CSV is a file whose every row is blank — and **both are SILENT.**

So the realistic failure is not a crash. It is a lane renaming a column on one
side of the wire: the request still succeeds, the job still writes a file, the
toast still says the export is ready, and **the clerk opens a spreadsheet with
columns they did not ask for.** `tsc` passes, vitest passes, pytest passes, and
nothing anywhere has an opinion about the two lists agreeing — which is the
whole reason a gate rather than a test.

⚠ **A VITEST CASE COULD NOT DO THIS AND A PYTEST CASE COULD NOT EITHER.** Each
would assert one side against a literal typed beside it and agree with itself
for ever. The check has to read BOTH files, which in this repository means a
gate (`g100`, `g103`, `g104`, `g105` and `g107` all read TSX from Python).

WHAT IT CHECKS
---------------
For each of the four groupings 6·2 offers, the ordered list of `key:` values in
`GROUPINGS` in `07-frontend/src/features/ledger/ExportView.tsx` must equal the
ordered list of `Column("<name>", …)` names on the resource that grouping names,
in `06-backend/apps/ledger/finance_exports.py`.

**ORDER IS PART OF IT.** `defaultVisibleColumns()` takes the screen's order and
that order is what a first download carries, so a table whose keys are the right
SET in the wrong SEQUENCE ships a file whose columns are shuffled against every
other file of the same report.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2). Four ways, each
closed:

  * **either file moving or being renamed.** The gate then reads nothing,
    matches nothing, and passes over a scope it silently excluded — `G32`'s
    shape. Both paths are REQUIRED: a missing one is a FAIL, not a SKIP.
  * **the parse returning nothing.** A refactor to a different literal shape
    (a `Record` built from a helper, a `Column` built in a loop) would empty one
    side and leave two empty lists comparing equal. So the gate FAILS when a
    grouping yields no keys, when a resource yields no columns, and when it
    finds fewer than the four groupings it expects.
  * **a grouping quietly leaving the screen.** Four is written down, because
    p070 row 3 ruled four. A fifth is a FAIL too — it is a new grouping with no
    resource behind it until somebody says otherwise.
  * **the detail line saying nothing on a pass.** It prints the four groupings
    and how many columns each agreed on, so a green line cannot be confused with
    a green line that read nothing.

PROVED RED BEFORE IT WAS TRUSTED GREEN, THROUGH `run_gates` AND NOT THROUGH
`python3 g133_export_columns_agree.py` — hard-won law 7's second half
(`DEF-GOV-3733`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCREEN = ROOT / "07-frontend/src/features/ledger/ExportView.tsx"
RESOURCES = ROOT / "06-backend/apps/ledger/finance_exports.py"

#: p070 row 3 — *"Group by Account · Service · Premises · Tax authority"*. Four,
#: in that order. A fifth means a grouping arrived with no resource behind it.
EXPECTED_GROUPINGS = 4

#: One `{ key: "x", field: "y", … }` entry of the screen's `GROUPINGS` table.
KEY_ENTRY = re.compile(r"\{\s*key:\s*\"([a-z0-9_]+)\"")

#: `account: {` … `resource: "export_preview",`
GROUPING_HEAD = re.compile(r"^  ([a-z]+):\s*\{\s*$", re.M)
RESOURCE_LINE = re.compile(r"resource:\s*\"([a-z0-9_]+)\"")

#: `NAME = export_kernel.ExportResource(` … `name="export_preview",`
RESOURCE_BLOCK = re.compile(r"^[A-Z_]+ = export_kernel\.ExportResource\($", re.M)
RESOURCE_NAME = re.compile(r"name=\"([a-z0-9_]+)\"")
COLUMN_CALL = re.compile(r"Column\(\s*\"([a-z0-9_]+)\"")


def _screen_groupings(text: str) -> dict[str, tuple[str, list[str]]]:
    """`{grouping: (resource, [column keys in order])}` from the TSX."""
    start = text.find("export const GROUPINGS: Record<ExportGrouping, GroupingSpec> = {")
    if start < 0:
        return {}
    end = text.find("\n};", start)
    if end < 0:
        return {}
    body = text[start:end]
    out: dict[str, tuple[str, list[str]]] = {}
    heads = list(GROUPING_HEAD.finditer(body))
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(body)
        chunk = body[head.start() : stop]
        resource = RESOURCE_LINE.search(chunk)
        if resource is None:
            continue
        out[head.group(1)] = (resource.group(1), KEY_ENTRY.findall(chunk))
    return out


def _server_resources(text: str) -> dict[str, list[str]]:
    """`{resource name: [column names in order]}` from the Python."""
    out: dict[str, list[str]] = {}
    heads = list(RESOURCE_BLOCK.finditer(text))
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        chunk = text[head.start() : stop]
        name = RESOURCE_NAME.search(chunk)
        if name is None:
            continue
        out[name.group(1)] = COLUMN_CALL.findall(chunk)
    return out


def check() -> tuple[list[str], list[str]]:
    """`(problems, agreed)` — `agreed` is one line per grouping, for the detail."""
    problems: list[str] = []
    agreed: list[str] = []
    if not SCREEN.is_file():
        problems.append(
            f"{SCREEN.relative_to(ROOT).as_posix()} is missing — 6·2's column table moved or "
            "was renamed, so this gate can see nothing and would otherwise pass over it"
        )
    if not RESOURCES.is_file():
        problems.append(
            f"{RESOURCES.relative_to(ROOT).as_posix()} is missing — the export resources moved "
            "or were renamed"
        )
    if problems:
        return problems, agreed

    groupings = _screen_groupings(SCREEN.read_text(encoding="utf-8"))
    resources = _server_resources(RESOURCES.read_text(encoding="utf-8"))
    if len(groupings) != EXPECTED_GROUPINGS:
        problems.append(
            f"the screen declares {len(groupings)} grouping(s) and p070 row 3 rules "
            f"{EXPECTED_GROUPINGS} (Account · Service · Premises · Tax authority). A grouping "
            "with no export resource behind it downloads the wrong report"
        )
    if not resources:
        problems.append(
            "no ExportResource was parsed out of finance_exports.py — the declaration shape "
            "changed, and two empty lists compare equal"
        )

    for grouping, (resource, keys) in sorted(groupings.items()):
        if not keys:
            problems.append(
                f"grouping {grouping!r} declares no column keys — an empty list agrees with "
                "everything and proves nothing"
            )
            continue
        served = resources.get(resource)
        if served is None:
            problems.append(
                f"grouping {grouping!r} names export resource {resource!r}, which "
                "finance_exports.py does not declare. POST /exports answers 404 for an "
                "unknown resource (HR-1), so the download is dead"
            )
            continue
        if not served:
            problems.append(
                f"export resource {resource!r} declares no columns — see above about empty "
                "lists"
            )
            continue
        if keys != served:
            problems.append(
                f"grouping {grouping!r} → resource {resource!r}: the screen ticks "
                f"{keys} and the resource declares {served}. columns_for() DROPS a name the "
                "resource does not have and falls back to the default set when it knows none "
                "of them — both silently — so the clerk gets a file with columns they did not "
                "ask for, with every test green"
            )
            continue
        agreed.append(f"{grouping}→{resource} ({len(keys)})")
    return problems, agreed


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE DETAIL NAMES WHAT AGREED, ON A PASS TOO — a green line that does not
    say what it compared cannot be told from a green line that compared nothing.
    """
    problems, agreed = check()
    if problems:
        return "FAIL", f"{len(problems)} disagreement(s): {problems[0]}"
    return "PASS", (
        "6·2's ticked columns are the export resources' own column names, in order: "
        + " · ".join(agreed)
    )


def main() -> int:
    status, detail = run()
    print(f"G133 {status}: {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
