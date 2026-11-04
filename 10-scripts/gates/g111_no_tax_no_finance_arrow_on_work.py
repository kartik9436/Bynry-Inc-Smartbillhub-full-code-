#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-052 (tax on a work order — NOTHING IS BUILT) · US-WRK-054
#           (the performance tab, and no link into Finance) · CR-070 wave N
#           task N6
# Rules:    BR-WRK-052 (PO 2026-09-03: *"Dont add Tax on work order - for
#           now"*; B4 §Tax ❄️ FROZEN stands) · BR-WRK-004 + BR-WRK-053 (a job's
#           cost is captured and posted NOWHERE; no link, button or note into
#           Finance) · CLAUDE.md hard rule 5 (only the ledger posting service
#           writes journal lines) · law 7 (proven RED first — see below)
# Tests:    selftest() below · 06-backend/tests/test_us_wrk_050_054_costing.py
#           (US-WRK-052 TC-1, US-WRK-054 TC-3/TC-4)
# Impacts:  apps/work/**, apps/rating/models.py, features/work/**
# ───────────────────────────────────────────────────────
"""G111 — no tax on a work order, and no arrow from the field into Finance.

TWO PROHIBITIONS, BOTH RULED, NEITHER ENFORCED BY ANYTHING ELSE
----------------------------------------------------------------
**One — tax.** `WM-46` specified a `base_includes_field_work` flag on the
signed `taxes` table and a `per_work_order` value in `flat_frequency`, and drew
`Work-031`. The Product Owner ruled on 2026-09-03, verbatim: *"Dont add Tax on
work order - for now"*. So `WO-4822`'s report totals **`$138.42`**, not the
`$149.84` the wireframe draws with `$8.65` and `$2.77` of tax on it. B4 §Tax is
❄️ FROZEN — *tax base = usage + base charge only* — and any change is a finance
re-sign through `HUMAN-GUIDE.md` §6, never a lane's edit.

**Two — the Finance arrow.** r10's `Work-027` says the field's total *"feeds
the O&M / labour line in Finance → Cost & Margin."* `OQ-WRK-1491` closed on
2026-09-04 to option (a): captured, posted nowhere. The reason is worth keeping
in front of whoever reads this next — **payroll already posts the hour, and
posting field labour beside it would count the same hour twice** — and
`CR-028` D3 is the Product Owner removing exactly that sentence for asset
maintenance.

WHY A GATE AND NOT ONLY A TEST
-------------------------------
Both are PROHIBITIONS, and a prohibition has no feature to fail when it is
broken. `US-WRK-052`'s whole content is that nothing was built, so the only
thing that can go wrong is a later lane quietly adding it — reading the
wireframe, seeing `$149.84` and two tax rows, and "finishing" the screen. A
test in the work suite would catch the first half; nothing would catch a
`per_work_order` frequency appearing in rating, or a `/finance` link appearing
on a React page, because no gate in this repo reads either for this.

⚠ **THE SECOND CLAUSE IS THE ONE WITH A CLOCK IN IT.** `OQ-WRK-1491` is
CLOSED, so a lane cannot unblock it by answering a question — it would have to
reverse a ruling. That is exactly the situation in which somebody adds the link
believing it was always intended, because the drawing says so.

PROVED RED FIRST (law 7), THROUGH `run_gates.py` AND NOT `python3 <gate>.py`
-----------------------------------------------------------------------------
`DEF-GOV-3733`: `G85` and `G87` were each shown red and then green by running
the file directly — which exercises `__main__` and never the path `run_gates`
uses — and both were announced green while the suite reported *gate crashed:
module has no attribute 'run'*. A red proof through the wrong entry point is
not a weaker proof, it is no proof of the thing that matters. The sabotages
recorded in this lane's report were run through `run_gates.py`.

`selftest()` below is the permanent version of that: it applies both sabotages
to strings in memory and asserts the finder bites, so the gate cannot rot into
one that always passes.
"""

from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: The two columns `WM-46` named and the Product Owner refused. The flag would
#: live in rating, on the signed `taxes` table, with the frequency beside it.
TAX_ON_WORK_TOKENS = ("base_includes_field_work", "per_work_order")

#: A tax LINE on a work-order report, by the names it would be given. Scoped to
#: Work only: rating has taxes for the excellent reason that bills have tax.
TAX_LINE_TOKENS = ("KIND_TAX", "kind_tax", "tax_rate", "tax_amount", "tax_line")

#: The Finance arrow, in r10's own words, plus the GL accounts `WM-45` names as
#: *"the destination exists and the rate does not"*.
FINANCE_TOKENS = ("Cost & Margin", "cost-and-margin", "/finance", "5300", "6020")

#: ⚠ **THE FINANCE CLAUSE IS SCOPED TO THE COST SURFACES, NOT TO ALL OF WORK,
#: AND THAT IS THE RULE RATHER THAN A CONCESSION.** `BR-WRK-053` says the
#: PERFORMANCE TAB and the REPORT carry no link into Finance. It does not say
#: the product may not have a Finance section — `WorkShell.test.tsx` asserts
#: that Work sorts before Finance in the nav, which is the app being an app.
#: A gate that failed on that would be silenced within a week, and a silenced
#: gate protects nothing.
COST_SURFACES = (
    "apps/work/costing.py",
    "apps/work/selectors.py",
    "apps/work/api.py",
    "features/work/PerformancePage",
    "features/work/WorkOrderReport",
    "features/work/LabourRates",
)


def _is_cost_surface(where: str) -> bool:
    """Is this a file that SHIPS a cost surface to a person?

    ⚠ **A TEST FILE IS NOT ONE, AND THAT IS THE SECOND TIME THIS CLAUSE HAS HAD
    TO LEARN THE SAME LESSON.** `strip_prose` already exempts the docstrings
    that RECORD the prohibition, for the reason that a gate failing on its own
    explanation gets fixed by deleting the explanation. A test asserting the
    absence is the same thing one step along: `PerformancePage.test.tsx` greps
    the rendered page for *Cost & Margin*, `5300` and `6020`, so it must
    contain all three as string literals — in code, where `strip_prose` cannot
    reach them and should not.

    **The rule is about what a page OFFERS a person, and a test offers nobody
    anything.** Excluding tests costs nothing: a `.test.tsx` cannot put a link
    on a screen, and the screen file beside it is still scanned. Failing on
    them would delete the only automated check that the link is absent — the
    gate would eat the test that does its job.
    """
    if where.endswith((".test.tsx", ".test.ts", ".test.py")) or "/tests/" in where:
        return False
    return any(fragment in where for fragment in COST_SURFACES)


def strip_prose(source: str, *, python: bool) -> str:
    """Remove comments and docstrings — **the load-bearing half of this gate.**

    ⚠ **THE DOCUMENTS THAT RECORD A PROHIBITION MUST NAME THE FORBIDDEN
    THING.** `costing.py`'s docstring quotes r10's *"feeds the O&M / labour
    line in Finance → Cost & Margin"* precisely so the next lane reads why the
    arrow is not built, and the business rules quote `per_work_order` to say it
    was refused. A gate scanning raw text fails on its own explanation, and the
    fix a hurried lane reaches for is to DELETE the explanation — so the check
    would destroy the very record it exists to protect.

    So this asks what the CODE DOES, and prose may say anything.
    """
    if python:
        out = []
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return source
        at_statement_start = True
        for token in tokens:
            if token.type == tokenize.COMMENT:
                continue
            #: A STRING in statement position is a docstring — Python's own
            #: definition — which keeps ordinary string literals, where a real
            #: tax key would live, in scope.
            if token.type == tokenize.STRING and at_statement_start:
                continue
            if token.type in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT):
                at_statement_start = True
            else:
                at_statement_start = False
            out.append(token.string)
        return " ".join(out)
    lines = []
    in_block = False
    for line in source.splitlines():
        if in_block:
            if "*/" in line:
                line, in_block = line.split("*/", 1)[1], False
            else:
                continue
        if "/*" in line:
            head_, _, rest = line.partition("/*")
            if "*/" in rest:
                line = head_ + rest.split("*/", 1)[1]
            else:
                line, in_block = head_, True
        if "//" in line:
            line = line.split("//", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def findings_in(source: str, *, where: str, python: bool = True) -> list[str]:
    """The finder, on a string — so `selftest` can sabotage it without a file."""
    code = strip_prose(source, python=python)
    problems = []
    for token in TAX_ON_WORK_TOKENS:
        if token in code:
            problems.append(
                f"{where}: `{token}` — tax on a work order is NOT BUILT (BR-WRK-052, "
                f'PO 2026-09-03: "Dont add Tax on work order - for now"). B4 §Tax is '
                f"FROZEN; changing it is a finance re-sign through HUMAN-GUIDE §6"
            )
    for token in TAX_LINE_TOKENS:
        if token in code:
            problems.append(
                f"{where}: `{token}` — a tax line on a work-order report. WO-4822 totals "
                f"138.42, not the wireframe's 149.84 (BR-WRK-052)"
            )
    if _is_cost_surface(where):
        for token in FINANCE_TOKENS:
            if token in code:
                problems.append(
                    f"{where}: `{token}` — the field's cost reaches no journal line and "
                    f"the page offers no way into Finance (BR-WRK-004, BR-WRK-053; "
                    f"OQ-WRK-1491 closed 2026-09-04 to option (a)). Payroll already "
                    f"posts the hour, and posting field labour beside it would count "
                    f"the same hour twice"
                )
    return problems


def _work_sources() -> list[Path]:
    out = []
    for root, pattern in (
        ("06-backend/apps/work", "*.py"),
        ("07-frontend/src/features/work", "*.ts"),
        ("07-frontend/src/features/work", "*.tsx"),
    ):
        base = REPO / root
        if base.exists():
            out.extend(p for p in base.rglob(pattern) if "__pycache__" not in str(p))
    return sorted(out)


def _rating_taxes() -> list[str]:
    """The signed `taxes` table — the flag would live in rating, not in work.

    ⚠ **ONLY THE TWO COLUMN NAMES ARE CHECKED HERE.** Rating has taxes, and a
    gate objecting to the word would be objecting to bills having tax on them,
    which is B4's ❄️ FROZEN job. What `WM-46` proposed and the Product Owner
    refused is precisely `base_includes_field_work` and a `per_work_order`
    frequency, and those two strings are the whole prohibition.
    """
    path = REPO / "06-backend/apps/rating/models.py"
    if not path.exists():
        return []
    code = strip_prose(path.read_text(encoding="utf-8"), python=True)
    return [
        f"06-backend/apps/rating/models.py: `{token}` — the tax base a work order would "
        f'have added. NOT BUILT (BR-WRK-052, PO 2026-09-03: "Dont add Tax on work order '
        f'- for now"); B4 §Tax is FROZEN'
        for token in TAX_ON_WORK_TOKENS
        if token in code
    ]


def selftest() -> list[str]:
    """Every sabotage must bite, and the two prose cases must NOT.

    A check that cannot fail is worse than no check; a check that fails on its
    own explanation gets silenced. Both halves are asserted.
    """
    failures = []
    if not findings_in('flat_frequency = "per_work_order"', where="probe"):
        failures.append("selftest: a `per_work_order` frequency did not trip the tax clause")
    if not findings_in("tax_amount = total * rate", where="apps/work/costing.py"):
        failures.append("selftest: a tax line did not trip the tax-line clause")
    if not findings_in('LINK = "/finance/cost-and-margin"', where="apps/work/selectors.py"):
        failures.append("selftest: a Finance link did not trip the arrow clause")
    if findings_in("labour = hours * rate", where="apps/work/costing.py"):
        failures.append("selftest: ordinary costing code tripped the gate — false positive")
    prose = (
        '"""r10 says this total feeds the O&M / labour line in Finance -> Cost & '
        'Margin. That arrow is not built (BR-WRK-004); GL 5300 exists and nothing '
        'writes to it."""\ntotal = 1\n'
    )
    if findings_in(prose, where="apps/work/costing.py"):
        failures.append(
            "selftest: a docstring RECORDING the prohibition tripped the gate — the check "
            "would force a lane to delete its own explanation"
        )
    if findings_in(
        'expect(work).toBeLessThan(paths.indexOf("/finance"));',
        where="features/work/WorkShell.test.tsx",
        python=False,
    ):
        failures.append(
            "selftest: the nav-ordering assertion tripped the arrow clause — BR-WRK-053 "
            "forbids a link FROM the cost surfaces, not a Finance section in the app"
        )
    #: ⚠ THE TEST THAT ASSERTS THE ABSENCE MUST PASS. It has to name *Cost &
    #: Margin*, `5300` and `6020` as string literals to grep for them, in CODE
    #: rather than in prose. Failing on it would make this gate eat the only
    #: automated check that the Finance link is absent.
    if findings_in(
        'for (const forbidden of ["Finance", "Cost & Margin", "O&M", "5300", "6020"])',
        where="features/work/PerformancePage.test.tsx",
        python=False,
    ):
        failures.append(
            "selftest: the test asserting the Finance link is ABSENT tripped the gate — "
            "the check would delete the check"
        )
    #: And the shipped screen beside it is still scanned.
    if not findings_in(
        'const LINK = "/finance";', where="features/work/PerformancePage.tsx", python=False
    ):
        failures.append(
            "selftest: a Finance link in the SHIPPED PerformancePage did not trip the gate — "
            "excluding tests must not exclude the screen"
        )
    return failures


def run() -> tuple[str, str]:
    problems = list(selftest())
    scanned = 0
    for path in _work_sources():
        where = str(path.relative_to(REPO))
        if where.endswith("g111_no_tax_no_finance_arrow_on_work.py"):
            continue
        scanned += 1
        problems.extend(
            findings_in(
                path.read_text(encoding="utf-8"), where=where, python=path.suffix == ".py"
            )
        )
    problems.extend(_rating_taxes())
    if problems:
        return "FAIL", " | ".join(problems)
    return "PASS", (
        f"{scanned} Work source(s) + rating's `taxes`: no tax flag, no tax frequency, no "
        f"tax line, no Finance arrow on any cost surface; WO-4822 totals 138.42 not "
        f"149.84; self-test: 3 sabotages bite, 3 legitimate cases pass"
    )


def main() -> int:
    status, note = run()
    print(f"G111 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
