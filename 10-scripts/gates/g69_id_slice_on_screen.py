#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2378 (2026-09-02) — the Product Owner, reading the deployed audit
#          log: "DB Keys are displayed". The S61 Entity column's visible value
#          was `tenant · 01a062a7-9f7d-73e6-96e4-700cba033c73`, built by
#          `` `${row.entity_type} · ${row.entity_id}` `` — THE VERY SHAPE THIS
#          GATE'S OWN DOCSTRING ADMITTED IT COULD NOT SEE ("a whole uuid built
#          through a variable"). Clause 2 below is that admission closed.
# Defect:  DEF-3158 (2026-09-02) — SEVEN screens printed a shortened database id
#          where a number belongs: the account's recent-bills panel, Fix a bill,
#          Budget Bills, the pending queue and the three import tabs. Every one
#          was `row.<something>_no ?? row.id.slice(0, 8)` — and Budget Bills had
#          NO fallback at all, so `01a00000` was the visible value on every row,
#          every time. Found by grepping for `.slice(0, 8)` while fixing an
#          unrelated breach one file away; no check in this repository saw it.
# Rules:   B14 rule 31 — "NOTHING INTERNAL IS EVER VISIBLE TO A UTILITY USER —
#          not an id, not a rule number, not a path", RATIFIED 2026-08-30 in the
#          PO's words *"no Databse ID on screen - that is a rule"* ·
#          CLAUDE.md hard-won law 7 (prove a guard RED first) · DEF-182 (a check
#          whose output cannot distinguish pass from fail is worse than none)
# Impacts: G28 (rule 31's string half) · 10-scripts/render-checks/
#          cr053-bill-surface.mjs (rule 31's rendered half, S30 only) ·
#          07-frontend/src/features/metering/UnitPlanIdNeverShows.dom.test.tsx
# ───────────────────────────────────────────────────────
"""G69 — A DATABASE ID MAY NOT BE TRUNCATED OR JOINED INTO A VISIBLE CELL.

WHY THIS EXISTS AND WHY THE THREE CHECKS THAT ALREADY COVER RULE 31 MISS IT
---------------------------------------------------------------------------
Rule 31 has three enforcers and DEF-3158 walked past all of them:

* **G28** reads STRINGS — the eleven catalogues, backend prose, `raise` sites.
  `row.id.slice(0, 8)` is not a string, it is an expression evaluated at
  runtime, and its docstring already admits the gap: *"a uuid-shaped VALUE in a
  field is the one thing G28 cannot see"*.
* **`cr053-bill-surface.mjs`** reads RENDERED TEXT and refuses a uuid — on
  `S30`'s bill surface **alone**. None of DEF-3158's seven screens is S30.
* **`UnitPlanIdNeverShows.dom.test.tsx`** covers the frame-before-the-data case
  on `S15`. Also one screen.

And a truncation defeats all three even where they look: **`01a00000` is not
uuid-shaped.** It has no dashes, it is eight characters, and it reads like a
reference number — which is exactly why seven lanes wrote it in good faith and
why a reader cannot tell it from a real one.

WHAT THIS ASKS, AND BOTH CLAUSES ARE DELIBERATELY NARROW
--------------------------------------------------------
In frontend source, with comments stripped:

**Clause 1 · A SLICED ID.** Does any expression take a slice of something whose
name is an id?

    <expr>.id.slice(          ·  <expr>.account_id.slice(
    <expr>.invoice_id.slice(  ·  <expr>.run_id.slice(   …

That is the shape DEF-3158's own prevention column prescribes — *"a mechanical
pattern that would have caught all seven"*.

**Clause 2 · A WHOLE ID JOINED INTO A LABEL (added 2026-09-02, DEF-2378).** Does
any template literal put an id-shaped placeholder next to a MIDDLE DOT?

    `${row.entity_type} · ${row.entity_id}`
    `${enumLabel(t, "…", row.entity_type)} · ${row.entity_name ?? row.entity_id}`

⚠ **THE MIDDLE DOT IS THE WHOLE OF WHY THIS CLAUSE IS SAFE TO HAVE, AND IT WAS
MEASURED RATHER THAN GUESSED.** A bare "`${…id}` inside a template literal"
matches **63** sites across the frontend and almost every one is correct: a DOM
`id={`${props.id}-help`}`, a React `key`, a route `to={tenantPath(`/assets/${asset.id}`)}`.
A gate reporting sixty false positives is a gate somebody switches off — the
exact failure G26's and G27's own docstrings record. `·` is this product's
composed-label separator (B14), it appears in no route, no DOM id and no React
key, and adding it to the pattern takes the same sweep from 63 matches to
**exactly 2 — and both were real breaches on live screens.**

**A narrow check that bites is worth more than a broad one nobody trusts**, and
this repo has paid for the opposite twice (G26's invented status vocabulary,
G67's 97% false rate).

WHY IT IS A CEILING OF ZERO AND NOT A BASELINE FILE
----------------------------------------------------
Every one of the seven was fixed in the commit that added this gate, so the
honest count today is **0**. A baseline file is the right instrument for debt
that will take months to pay down (G28 part 2b, G33's 598 refusals); it is the
wrong one for a set that is already empty, because a named exception list is
where a rule quietly stops being one. If a legitimate case ever appears, it goes
in `ALLOWED` below **with a reason**, the way rule 21's `NEW_CLASS_EXCEPTIONS`
does — never by raising a number.

⚠ **WHAT IT CANNOT SEE, SAID PLAINLY (hard-won law 1).** It reads SOURCE. A
screen that renders a whole uuid through JSX children rather than a template
literal, that joins one with any separator but `·`, or that prints an id served
under an innocent name, passes this gate and is still in breach. Rule 31's
rendered half is still unenforced for every screen but S30 and S15, B14's own
status table says so, and this gate does not change that sentence — it closes
two mechanical shapes that between them produced nine live breaches.

⚠ **AND ONE PLACE IS DELIBERATELY OUT OF SCOPE, WHICH IS NOT THE SAME AS
MISSED.** The S61 drawer's *Stored record* fold renders the audit row's stored
`before` / `after` JSON verbatim, keys and ids included. US-AUD-005 §5 ratifies
that as the auditor's exact record; it is collapsed by default and its own
summary says *"exactly as it was saved, technical"*. Rule 31 is about the value
a person READS in a field, and raw stored JSON behind a fold labelled technical
is not that. It reaches no template literal here in any case.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = REPO_ROOT / "07-frontend" / "src"

#: The shape DEF-3158's prevention column names. `id` or anything ending `_id`,
#: sliced. The leading `\.` matters: a bare local named `id` is not a served
#: column and this gate does not guess about locals.
ID_SLICE = re.compile(r"\.(id|[A-Za-z0-9]+_id)\s*\.\s*slice\s*\(")

#: Clause 2, DEF-2378. A template literal that joins a composed label to an
#: id-shaped placeholder. `·` is required — see the docstring for the measurement
#: that made it required. `\?\?` lets the `name ?? id` fallback shape match too,
#: which is how `RateChangesTab` was reading when the PO reported the audit log.
ID_JOINED_LABEL = re.compile(r"`[^`]*·[^`]*`")
ID_PLACEHOLDER = re.compile(r"\$\{[^{}]*\.(?:id|[A-Za-z0-9]+_id)\s*\}")

# ⚠ LINE COMMENTS FIRST, then blocks — DEF-741's order, and it is load-bearing.
# A `//` line containing `/*` (a path with a star in it) otherwise opens a
# comment that closes at the next `*/` anywhere below, swallowing real code. It
# matters here more than most: every one of DEF-3158's seven fixes RECORDS the
# old expression in a comment beside the new one, so a gate that failed to strip
# comments would report all seven fixed sites as breaches — a check that is red
# on the fix is a check somebody deletes.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# ⚠ `[ \t]*` AND NOT `\s*`: in MULTILINE mode `^\s*` happily eats the newlines
# of the BLANK LINES ABOVE a comment, so each blank-line-then-comment pair cost
# one line of the report's line numbers. That is how DEF-2378's breach was
# first reported at line 109 of a file where it sits at 132.
LINE_COMMENT = re.compile(r"^[ \t]*//.*$", re.M)

#: Named exceptions, each with its reason — rule 21's `NEW_CLASS_EXCEPTIONS`
#: posture. EMPTY, and staying empty is the point: DEF-3158 fixed all seven, so
#: there is nothing legitimate to list yet. A future entry is a `path:reason`
#: pair somebody had to write down.
ALLOWED: dict[str, str] = {}


def _code_only(text: str) -> str:
    """Comments blanked, NEWLINES PRESERVED.

    ⚠ A block comment used to be replaced with the empty string, which deleted
    every newline inside it — so this gate reported DEF-2378's breach at line
    109 when it is at 132, a 23-line drift caused entirely by the file's own
    header comment. The docstring above already promised line numbers "from the
    ORIGINAL text"; this is that promise kept. A report that points a reader at
    the wrong line is the same class of fault as a check that cannot fail.
    """
    text = LINE_COMMENT.sub("", text)
    return BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _joined_label_hits(stripped: str) -> list[tuple[int, str]]:
    """Clause 2: every `· …${…id}` template literal, with its START line.

    A template literal may span lines, so this scans the WHOLE file text rather
    than line by line — the line number comes from counting newlines before the
    match, which is why comments are blanked rather than removed above.
    """
    out: list[tuple[int, str]] = []
    for match in ID_JOINED_LABEL.finditer(stripped):
        literal = match.group(0)
        if ID_PLACEHOLDER.search(literal):
            line = stripped.count("\n", 0, match.start()) + 1
            out.append((line, " ".join(literal.split())[:110]))
    return out


def findings() -> list[tuple[str, int, str]]:
    """Every live breach of either clause in frontend source, comments stripped."""
    out: list[tuple[str, int, str]] = []
    for path in sorted(SRC.rglob("*.ts*")):
        if ".test." in path.name or path.suffix not in {".ts", ".tsx"}:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if rel in ALLOWED:
            continue
        # The line numbers must come from the ORIGINAL text or every report
        # points a reader at the wrong line; comments are blanked rather than
        # removed so the count of newlines is preserved.
        raw = path.read_text(encoding="utf-8")
        stripped = _code_only(raw)
        for number, line in enumerate(stripped.splitlines(), start=1):
            if ID_SLICE.search(line):
                out.append((rel, number, line.strip()[:110]))
        for number, literal in _joined_label_hits(stripped):
            out.append((rel, number, literal))
    return out


def selftest() -> bool:
    """The gate must BITE on DEF-3158's seven expressions and DEF-2378's two
    labels, and must NOT bite on the comments that now record them nor on the
    sixty legitimate `${…id}` template literals clause 2 was narrowed to spare.

    Both halves are asserted because both have already been wrong somewhere in
    this directory: a gate that cannot fail is worse than none (DEF-182), and a
    gate that fires on its own fix gets switched off within the day.
    """
    joined_breaches = [
        "`${row.entity_type} \u00b7 ${row.entity_id}`",
        '`${enumLabel(t, "x", row.entity_type)} \u00b7 ${row.entity_name ?? row.entity_id}`',
    ]
    joined_innocent = [
        # Clause 2's whole safety margin: a DOM id, a React key and a route all
        # interpolate an id and none of them carries a middle dot.
        "id={`${props.id}-help`}",
        'key={`${row.asset_id ?? row.unit_id}-${row.meter ?? ""}`}',
        "to={tenantPath(`/assets/${asset.id}`)}",
        # A composed label with NO id in it is the shape this gate must leave be.
        "`${plan.name} \u00b7 ${plan.service}`",
    ]
    for line in joined_breaches:
        if not _joined_label_hits(line):
            return False
    for line in joined_innocent:
        if _joined_label_hits(line):
            return False
    breaches = [
        "cell: (row) => row.run_no ?? row.id.slice(0, 8),",
        "<td>{row.account_id.slice(0, 8)}</td>",
        "{row.invoice_no ?? row.id.slice(0, 8)}",
        "{row.account_no ?? row.account_id.slice(0, 8)}",
    ]
    innocent = [
        "// was `row.run_no ?? row.id.slice(0, 8)` until 2026-09-02",
        "/* ⛔ DEF-3158 — this read `row.id.slice(0, 8)` */",
        "const shown = name.slice(0, 8);",
        "title={row.id}",
    ]
    for line in breaches:
        if not ID_SLICE.search(line):
            return False
    for line in innocent:
        if ID_SLICE.search(_code_only(line)):
            return False
    return True


def run() -> tuple[str, str]:
    if not SRC.is_dir():
        return "SKIP", f"{SRC} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not bite: it must find DEF-3158's four "
            "expression shapes and must NOT find them inside the comments that now "
            "record them. A check that cannot distinguish pass from fail is worse "
            "than no check, because it is trusted (DEF-182)."
        )
    hits = findings()
    if hits:
        shown = "; ".join(f"{rel}:{line} {text}" for rel, line, text in hits[:5])
        return "FAIL", (
            f"{len(hits)} site(s) put a DATABASE ID on screen, which B14 rule 31 forbids "
            f"outright ('no Databse ID on screen - that is a rule', PO 2026-08-30). A "
            f"truncation and a whole uuid joined into a label are the same breach: it is "
            f"still the database's value and a person still cannot use it. Show the "
            f"human-facing number, or the name, or — where the row has neither — say WHAT "
            f"THE RECORD IS in words and let the id travel on `title` and a data attribute "
            f"as evidence. An empty cell breaches the rule as loudly, because a person "
            f"reads a blank as 'there is nothing here' about a record that exists. {shown}"
        )
    return "PASS", (
        "0 database ids reach a cell (ceiling 0 — clause 1: DEF-3158's seven truncations; "
        "clause 2: DEF-2378's two `type · id` labels, on the audit log and the rate-change "
        "history); self-test: six breach shapes bite, and the four comments recording them "
        "plus four legitimate `${…id}` literals (a DOM id, a React key, a route, a "
        "name-only label) do not. ⚠ SOURCE ONLY — a uuid rendered through JSX children, or "
        "joined with any separator but the middle dot, still passes here, and rule 31's "
        "rendered half stays unenforced outside S30 and S15."
    )


def main() -> int:
    if "--report" in sys.argv:
        for rel, line, text in findings():
            print(f"{rel}:{line}  {text}")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
