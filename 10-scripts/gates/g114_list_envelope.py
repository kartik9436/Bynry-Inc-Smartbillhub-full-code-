#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-WRK-4098 (Work → Rules drew zero rules) · DEF-WRK-4119
#          (Settings → Labour rates, part issues) · DEF-AST-4120 (the asset
#          door, which also lost `maintenance_index` server-side)
# Rules:   CLAUDE.md hard-won law 5 (one source, derive views on demand) ·
#          law 1 (a comment claiming a guarantee is not the guarantee) ·
#          law 7 (proved RED first, through `run_gates`' own import path, and
#          it prints what it SKIPPED beside what it checked)
# Tests:   selftest() below · 06-backend/tests/test_def_ast_4120_envelope_extras.py
#          · 07-frontend/src/features/work/recordedShapes.dom.test.tsx
# ───────────────────────────────────────────────────────
"""G114 — the list envelope is described ONCE, and a second description is a defect.

WHY A GATE AND NOT A PARAGRAPH
-------------------------------
On 2026-09-05 three shipped Work screens drew empty tables over rows the API had
returned. `Work → Rules` said *"No results for ''."* over seven rules; `Settings
→ Labour rates` did the same over four; the asset detail's Maintenance history
showed a dash in every WORK ORDER cell. `tsc`, eslint, 116 gates, 9,810 backend
tests and 367 front-end test files were green over all three, for two waves.

**The mistake was not a typo — it was reading one layer too low, which is why it
looked right.** Every list view is `Response(_envelope(request,
selectors.<x>_page(...)))`. `_envelope` builds a FRESH dict, `{count, next,
previous, results}`, from a selector that returns `{rows, page, per, total,
pages}`. A lane that opened `selectors.py` — the right file, the file the ROW
shape genuinely lives in — and transcribed the dict it found there wrote a
perfect description of the layer below the boundary and a complete fiction about
the wire. `data.rows` is then `undefined`, `undefined ?? []` is a legal empty
array, and the screen renders its own no-results state with total confidence.

**Nothing in the toolchain can see this and nothing ever will.** A generic on
`client.get<T>()` is an ASSERTION: it tells TypeScript what to pretend the JSON
is, and nothing at runtime compares the two. The OpenAPI snapshot cannot help
either — it carries 513 paths and **zero response-body schemas** (616 declared
responses, none with content), because every view is a plain `@api_view`
returning `Response(dict)` with no serializer, and it does not list
`/work/rules` or `/work/labour-rates` at all. **There is no generated type to
read.** So the cure was to make ONE hand-written declaration authoritative
(`07-frontend/src/api/paginated.ts`) and delete the other eleven — and this gate
is what stops a twelfth.

⚠ **IT WAS FIXED ONE SCREEN AT A TIME BY TWO LANES ON ONE DAY, WHICH IS THE
ARGUMENT FOR THE GATE.** A sibling corrected the rules interface to the envelope
— correct, and the eleventh hand copy of those four keys in a single file, with
the twelfth free to be wrong again. Two other screens had the identical bug at
that moment.

WHAT IT READS
--------------
Every `.ts`/`.tsx` file under `07-frontend/src`, by TEXT rather than by parse:
an interface or type alias that declares BOTH a `rows:` member and at least one
of `per:`, `pages:` or `last_page:` is the selector's page dict, transcribed.
That triple is the signature of the defect and of nothing else — `rows` alone is
far too common (`counts: { rows: ... }` on two Work footers, `TableConfig`, a
dozen props), and `per`/`pages`/`last_page` are the names that only ever appear
together with it inside a backend selector.

A file may opt out by listing itself in `g114_envelope_allowed.txt`, one path
per line, with the reason on the same line after `#`. That is for a genuine
non-envelope shape, not for a screen in a hurry.

⚠ **WHAT THIS GATE CANNOT SEE, PRINTED BESIDE WHAT IT CHECKED (law 7's
blind-spot clause, `G32`'s lesson).** It reads DECLARATIONS. A wrapper that
inlines the shape at the call site — `client.get<{ rows: X[]; total: number }>`
— is caught only if that literal also names `per`, `pages` or `last_page`; and a
wrapper that types the reply `any` or `unknown` is invisible to it entirely. The
runtime assertion in `readListPage` is what covers those, and the count of files
carrying an inline `client.get<{` literal is reported every run so the blind
spot has a NUMBER rather than a silence.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import common  # type: ignore
except ImportError:  # pragma: no cover — direct `python3 g114_...py`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import common  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "07-frontend" / "src"
CANONICAL = SRC / "api" / "paginated.ts"
ALLOW = Path(__file__).resolve().parent / "g114_envelope_allowed.txt"
MAX_NAMED = 12

#: The four names the wire really carries. Kept here as well as in
#: `paginated.ts` on purpose: a gate that imported its expectation from the file
#: it polices would pass whatever that file happened to say.
WIRE_KEYS = ("count", "next", "previous", "results")

#: A declaration block — `export interface X {…}` or `export type X = {…}`.
DECL = re.compile(
    r"^\s*export\s+(?:interface|type)\s+(\w+)[^\n{]*\{(.*?)^\s*\}",
    re.MULTILINE | re.DOTALL,
)
ROWS = re.compile(r"^\s*rows\??\s*:", re.MULTILINE)
SELECTOR_ONLY = re.compile(r"^\s*(per|pages|last_page)\??\s*:", re.MULTILINE)
INLINE_GET = re.compile(r"client\.get<\s*\{")


def allowed() -> set[str]:
    if not ALLOW.exists():
        return set()
    out: set[str] = set()
    for line in ALLOW.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            out.add(entry)
    return out


def sources() -> list[Path]:
    return sorted(
        p
        for p in SRC.rglob("*.ts*")
        if p.suffix in {".ts", ".tsx"} and "node_modules" not in p.parts
    )


def check(files: list[Path], skip: set[str]) -> tuple[list[str], dict[str, int]]:
    problems: list[str] = []
    tally = {"scanned": 0, "allowed": 0, "inline": 0}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        tally["scanned"] += 1
        if INLINE_GET.search(text):
            tally["inline"] += 1
        if rel in skip:
            tally["allowed"] += 1
            continue
        for match in DECL.finditer(text):
            name, body = match.group(1), match.group(2)
            if ROWS.search(body) and SELECTOR_ONLY.search(body):
                problems.append(
                    f"{rel}: `{name}` declares `rows` beside `per`/`pages`/`last_page` — "
                    f"that is the SELECTOR's page dict, not the reply. The wire carries "
                    f"{{{', '.join(WIRE_KEYS)}}}; call `readListPage` from "
                    f"@/api/paginated and take {{rows, total}} (DEF-WRK-4098)"
                )
    return problems, tally


def selftest() -> tuple[bool, str]:
    """⚠ Proved RED on the exact text of all four shipped defects."""
    import tempfile

    def scan(source: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.ts"
            path.write_text(source, encoding="utf-8")
            found: list[str] = []
            if ROWS.search(source) and SELECTOR_ONLY.search(source):
                for match in DECL.finditer(source):
                    if ROWS.search(match.group(2)) and SELECTOR_ONLY.search(match.group(2)):
                        found.append(match.group(1))
            return found

    # 1 — `WorkRulesPage`, verbatim as it shipped (DEF-WRK-4098).
    shipped = (
        "export interface WorkRulesPage {\n"
        "  rows: WorkRuleRow[];\n  page: number;\n  per: number;\n"
        "  total: number;\n  pages: number;\n}\n"
    )
    if "WorkRulesPage" not in scan(shipped):
        return False, "did not flag the shipped WorkRulesPage"

    # 2 — `LabourRateList`, verbatim (DEF-WRK-4119); `last_page` not `pages`.
    labour = (
        "export interface LabourRateList {\n"
        "  rows: LabourRateRow[];\n  page: number;\n  per: number;\n"
        "  total: number;\n  last_page: number;\n}\n"
    )
    if "LabourRateList" not in scan(labour):
        return False, "did not flag the shipped LabourRateList"

    # 3 — the CORRECT envelope must NOT be flagged, or the gate is noise.
    good = (
        "export interface Paginated<Row> {\n"
        "  count: number;\n  next: string | null;\n"
        "  previous: string | null;\n  results: Row[];\n}\n"
    )
    if scan(good):
        return False, "flagged the correct envelope — false positive"

    # 4 — `rows` ALONE is not a finding. Two Work footers legitimately carry
    #     `counts: { rows: number; … }` and a dozen props carry `rows`.
    innocent = (
        "export interface CrewList {\n"
        "  count: number;\n  results: CrewRow[];\n"
        "  counts: { rows: number; people: number };\n}\n"
    )
    if scan(innocent):
        return False, "flagged a `rows` that is not a page shape — false positive"

    return True, "four cases: two shipped defects flagged, two innocents not"


def run() -> tuple[str, str]:
    """⚠ `tuple[str, str]`, NOT an exit code — `run_gates` unpacks it
    (`DEF-GOV-3733`: two gates were announced green having only ever been proved
    through `python3 <gate>.py`, which is not the path the runner uses)."""
    ok, detail = selftest()
    if not ok:
        return "FAIL", f"self-test: {detail}"
    if not CANONICAL.exists():
        return "FAIL", (
            f"{CANONICAL.relative_to(ROOT)} is missing — it is the ONE declaration "
            f"of the list envelope this gate exists to protect"
        )

    problems, tally = check(sources(), allowed())
    line = (
        f"{tally['scanned']} front-end source file(s) scanned for a second description "
        f"of the list envelope ({tally['allowed']} allow-listed) · "
        f"NOT COVERED: {tally['inline']} file(s) inline a `client.get<{{…}}>` literal, "
        f"which this gate reads only when it names per/pages/last_page — "
        f"readListPage's runtime assertion covers those"
    )
    if problems:
        return "FAIL", f"{common.summarize(problems, MAX_NAMED)} — {line}"
    return "PASS", line


def main() -> int:
    status, detail = run()
    print(f"G114 {status} {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
