#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 TC-2 (⚠ *"Assert `draft` and `not shown` are excluded IN
#           THE QUERY, not in the template"*) · US-CWP-072 · US-CWP-074 TC-1.
#           CR-068 wave D's exit test, first clause.
# Rules:    BR-CWP-094 (only `published` leaves the back office) · BR-CWP-096
#           (only `is_shown_to_customers`) · BR-CWP-095 (only `is_on`) ·
#           BR-CWP-012 (the portal reads through the owning module's seam) ·
#           03-field-map.md §2, verbatim: *"The gate is `status = published`,
#           in the query, not in the template."* · CLAUDE.md hard-won law 7
#           (proven RED first — the failures are quoted below)
# Ids:      renumbered from `G84` on 2026-09-04 — three lanes took 84 the same
#           afternoon (`DEF-CWP-3734`); this one landed last and moved.
# Tests:    selftest() below · 06-backend/apps/tenancy/published_content.py
#           (`GUEST_READS`, the data this gate reads)
# Impacts:  apps/tenancy/published_content.py · apps/portal/seams/tenancy_seam.py
# ───────────────────────────────────────────────────────
"""G88 — a draft never leaves the API, and the reason is in the SQL.

⚠ **THIS WAS `G84` FOR FOUR HOURS AND SO WERE TWO OTHER GATES (`DEF-CWP-3734`).**
Three lanes each read `10-scripts/gates/`, each correctly computed the next free
number, and each got **84** — because a sibling working in its own worktree has
its file in none of the places a `ls` can see until it pushes. That is CLAUDE.md
law 11's last clause about allocated ids, one artefact class over: *re-derive
the number from the pushed tip at PUSH time, not when you create the file.* This
one landed last of the three, so this one renumbered.

WHY THIS GATE EXISTS
--------------------
The blueprint's own public help page listed all eight answers, including the
draft and the one deliberately withheld, and §16 records the repair. The repair
is not *"remember to filter"*; it is *"the gate is `status = published`, in the
query, not in the template"* — because a template filter is one refactor away
from a leak, and the leak is a customer reading an unfinished answer.

A test can prove a draft is absent from one response. It cannot prove the NEXT
function somebody adds will filter too, and it cannot see the shape of the
filter at all. This gate reads the code.

WHAT IT ASSERTS, AND THE THIRD CLAUSE IS THE ONE THAT MATTERS
--------------------------------------------------------------
`apps/tenancy/published_content.py` declares `GUEST_READS` — the functions a
visitor can reach and the keyword each one's query must carry. Then:

  1. **Every declared guest read filters in the QUERY.** Its body contains a
     `.filter(...)` call whose keywords include the gate — `status=`,
     `is_shown_to_customers=` or `is_on=`. A function that fetches everything
     and sifts afterwards fails here.
  2. **None of them decides the same thing in Python.** A comparison against
     `ANSWER_PUBLISHED`, `ANSWER_DRAFT` or `ANSWER_NOT_SHOWN` inside a guest
     read is the template filter wearing a different hat.
  3. **The portal's seam may call NOTHING ELSE from this module.** Every
     `published_content.<name>(…)` call in `apps/portal/seams/tenancy_seam.py`
     is a declared guest read. This is the clause that stops the real failure:
     `back_office_answers` holds all three states, and one convenient seam
     function would put every draft on the guest surface without touching a
     single filter.

PROVEN RED FIRST (law 7, 2026-09-04)
------------------------------------
With `published_answers` changed to fetch every row and filter in Python:
    FAIL: published_answers is a guest read and its query does not filter on
    status= — the gate is in the query, not in the template (BR-CWP-094)
and with `back_office_answers` added to the seam:
    FAIL: apps/portal/seams/tenancy_seam.py calls published_content.
    back_office_answers, which GUEST_READS does not declare — the back-office
    list holds draft and not-shown rows (BR-CWP-094)
Both reverted; `selftest()` replays both on in-memory sources and `run()`
refuses to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CONTENT = REPO / "06-backend" / "apps" / "tenancy" / "published_content.py"
SEAM = REPO / "06-backend" / "apps" / "portal" / "seams" / "tenancy_seam.py"

#: A comparison against one of these inside a guest read is clause 2's failure.
STATUS_NAMES = frozenset({"ANSWER_PUBLISHED", "ANSWER_DRAFT", "ANSWER_NOT_SHOWN"})


def guest_reads(source: str) -> tuple[dict[str, str], list[str]]:
    """`GUEST_READS` as data, straight out of the module's own source."""
    problems: list[str] = []
    reads: dict[str, str] = {}
    tree = ast.parse(source)
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if not any(isinstance(t, ast.Name) and t.id == "GUEST_READS" for t in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            problems.append("GUEST_READS is not a literal dict a gate can read")
            continue
        for key, val in zip(value.keys, value.values):
            if not (isinstance(key, ast.Constant) and isinstance(val, ast.Constant)):
                problems.append("GUEST_READS holds a non-literal entry")
                continue
            reads[str(key.value)] = str(val.value)
    if not reads and not problems:
        problems.append("published_content.py declares no GUEST_READS")
    return reads, problems


def _functions(source: str) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef)
    }


def _filters_on(fn: ast.AST, keyword: str) -> bool:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "filter"
            and any(kw.arg == keyword for kw in node.keywords)
        ):
            return True
    return False


def _compares_status(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare):
            names = {
                n.id
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id in STATUS_NAMES
            }
            if names:
                return True
    return False


def seam_calls(source: str) -> set[str]:
    """Every `published_content.<name>(…)` the portal's seam makes."""
    called: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "published_content"
        ):
            called.add(node.func.attr)
    return called


def check(content_src: str, seam_src: str) -> list[str]:
    reads, problems = guest_reads(content_src)
    functions = _functions(content_src)
    for name, keyword in sorted(reads.items()):
        fn = functions.get(name)
        if fn is None:
            problems.append(f"GUEST_READS names {name}, which published_content.py does not define")
            continue
        if not _filters_on(fn, keyword):
            problems.append(
                f"{name} is a guest read and its query does not filter on {keyword}= — "
                "the gate is in the query, not in the template (BR-CWP-094)"
            )
        if _compares_status(fn):
            problems.append(
                f"{name} decides a status in PYTHON — a template filter wearing a "
                "different hat (BR-CWP-094, 03-field-map.md §2)"
            )
    for name in sorted(seam_calls(seam_src)):
        if name not in reads:
            problems.append(
                f"apps/portal/seams/tenancy_seam.py calls published_content.{name}, "
                "which GUEST_READS does not declare — the back-office list holds "
                "draft and not-shown rows (BR-CWP-094)"
            )
    return problems


CLEAN_CONTENT = '''
GUEST_READS = {"published_answers": "status", "public_centres": "is_shown_to_customers"}

def published_answers(tenant_id):
    return list(HelpAnswer.objects.filter(tenant_id=tenant_id, status=ANSWER_PUBLISHED))

def public_centres(tenant_id):
    return list(ServiceCentre.objects.filter(tenant_id=tenant_id, is_shown_to_customers=True))

def back_office_answers(tenant_id):
    return list(HelpAnswer.objects.filter(tenant_id=tenant_id))
'''
RED_TEMPLATE_FILTER = CLEAN_CONTENT.replace(
    "    return list(HelpAnswer.objects.filter(tenant_id=tenant_id, status=ANSWER_PUBLISHED))",
    "    rows = HelpAnswer.objects.filter(tenant_id=tenant_id)\n"
    "    return [row for row in rows if row.status == ANSWER_PUBLISHED]",
)
CLEAN_SEAM = '''
def published_help_answers(tenant_id):
    return published_content.published_answers(tenant_id)
'''
RED_SEAM = CLEAN_SEAM + '''
def every_answer(tenant_id):
    return published_content.back_office_answers(tenant_id)
'''


def selftest() -> bool:
    if check(CLEAN_CONTENT, CLEAN_SEAM):
        return False
    red_one = check(RED_TEMPLATE_FILTER, CLEAN_SEAM)
    if not any("does not filter on status=" in p for p in red_one):
        return False
    red_two = check(CLEAN_CONTENT, RED_SEAM)
    if not any("back_office_answers" in p for p in red_two):
        return False
    return True


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", "G88's own selftest did not bite — the gate is not trustworthy"
    for path in (CONTENT, SEAM):
        if not path.is_file():
            return "FAIL", f"{path.relative_to(REPO)} is missing"
    problems = check(
        CONTENT.read_text(encoding="utf-8"), SEAM.read_text(encoding="utf-8")
    )
    if problems:
        return "FAIL", "; ".join(problems[:4])
    reads, _ = guest_reads(CONTENT.read_text(encoding="utf-8"))
    return (
        "PASS",
        f"{len(reads)} guest read(s) gate their own query; the portal's seam reaches "
        "no back-office selector; self-test: a Python-level filter and a seam call "
        "onto the back-office list both bite",
    )


if __name__ == "__main__":
    status, message = run()
    print(f"{status}: {message}")
    sys.exit(0 if status == "PASS" else 1)
