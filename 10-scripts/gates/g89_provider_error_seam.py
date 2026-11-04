#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-INT-020 (EP-INT-06) — the run record's PROPOSED mitigation:
#          *"the adapter scrubs a provider message of email addresses, account
#          numbers and postal addresses before it becomes `provider_error`"*.
#          CR-069 wave C task C1.
# Rules:   BR-INT-039 (the run record) · CLAUDE.md hard rule 1 (RLS cannot see
#          inside a text column, which is why this guard is textual and at the
#          write) · hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee) · law 7 (proven RED first — see the docstring)
# Tests:   selftest() below · 06-backend/tests/test_us_int_020_runs.py (TC-6)
# Impacts: apps/integrations/services.py (`scrub`, and the ONE assignment) ·
#          apps/integrations/scrubbing.py (the rule itself)
# ───────────────────────────────────────────────────────
"""G89 — `provider_error` IS WRITTEN IN ONE PLACE, AND THAT PLACE SCRUBS.

WHY THIS GATE EXISTS
--------------------
`integration_run.provider_error` is the one column in this product where
ANOTHER TENANT'S DATA CAN ARRIVE: a mail server refuses a message by quoting
the message it refused, and the quote can name a customer of a different
utility. Row-level security is no help — the leak is INSIDE a row the tenant
is entitled to read.

`US-INT-020` §1 puts the scrub in the ADAPTER, which is where the
provider-specific knowledge belongs. But a guarantee that depends on nineteen
adapters each remembering is hard-won law 1 exactly: a comment claiming a
guarantee. So the product applies it at the write — `services.finish_run` —
and this gate is what keeps that true as adapters, runners and webhooks arrive
in waves E through R.

WHAT IT ASKS, IN TWO CLAUSES
----------------------------
**Clause 1 · THE SEAM IS INTACT.** `apps/integrations/services.py` assigns
`provider_error` exactly once, and the right-hand side of that assignment
calls `scrub(`. A lane that "simplifies" it to `run.provider_error =
provider_error` fails here.

**Clause 2 · NOBODY ELSE WRITES THE COLUMN.** No other file under
`06-backend/` assigns `provider_error` as an attribute or hands it to
`objects.create(…)` / `.update(…)`. PASSING `provider_error=` INTO
`finish_run(…)` IS THE SANCTIONED PATH and is not a finding — that is the
whole point of having a seam, and a gate that refused it would be a gate
telling callers to go around it.

PROVEN RED FIRST (law 7, 2026-09-04)
------------------------------------
With `run.provider_error = provider_error` in `services.finish_run` the gate
reported

    FAIL: apps/integrations/services.py assigns provider_error without scrub() —
    the one seam is open (US-INT-020)

and with a second writer added to `apps/integrations/runners/deliver.py`

    FAIL: apps/integrations/runners/deliver.py writes provider_error directly —
    the only writer is services.finish_run, which scrubs

Both sabotages were removed and the gate went green. `selftest()` replays them
on in-memory sources, so a refactor of this file cannot leave a check that
cannot fail (DEF-182).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "06-backend"
SEAM = "apps/integrations/services.py"

#: An assignment to the column: `run.provider_error = …`, `provider_error=…`
#: inside `objects.create(` / `.update(`.
_ATTR_WRITE = re.compile(r"^\s*[\w.]+\.provider_error\s*=\s*(?P<rhs>.+)$")
_KWARG_WRITE = re.compile(r"\bprovider_error\s*=")

#: The calls that hand the value to the seam rather than to the column. A line
#: mentioning one of these is a CALLER, not a writer.
_SANCTIONED = ("finish_run(", "scrub(", "record_test_result(")

#: Files that legitimately NAME the column without writing it.
_ALLOWED_TO_NAME = (
    "apps/integrations/models.py",  # the field declaration
    "apps/integrations/runs.py",  # the read model
    "apps/integrations/scrubbing.py",  # the rule
    "apps/integrations/migrations/",  # DDL
)


def _strip_comments(source: str) -> list[tuple[int, str]]:
    """Lines with `#` comments removed. Docstrings are not stripped — a
    docstring cannot assign anything, and stripping them properly needs a
    parser this gate does not want to depend on. A `provider_error =` inside
    prose would be a false positive; none exists, and the self-test would name
    it if one arrived."""
    out: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        cut = line.split("#", 1)[0]
        out.append((number, cut))
    return out


def seam_findings(source: str, *, where: str) -> list[str]:
    """Clause 1 — the one assignment, and it scrubs."""
    assignments = [
        (number, match)
        for number, line in _strip_comments(source)
        if (match := _ATTR_WRITE.match(line)) is not None
    ]
    if not assignments:
        return [f"{where} assigns provider_error nowhere — the seam has gone (US-INT-020)"]
    if len(assignments) > 1:
        lines = ", ".join(str(number) for number, _ in assignments)
        return [f"{where} assigns provider_error {len(assignments)} times (lines {lines}) — one seam, not several"]
    number, match = assignments[0]
    if "scrub(" not in match.group("rhs"):
        return [
            f"{where} assigns provider_error without scrub() at line {number} — "
            "the one seam is open (US-INT-020)"
        ]
    return []


def writer_findings(source: str, *, where: str) -> list[str]:
    """Clause 2 — nobody outside the seam writes the column."""
    for _number, line in _strip_comments(source):
        if _ATTR_WRITE.match(line) is not None:
            return [
                f"{where} writes provider_error directly — the only writer is "
                "services.finish_run, which scrubs"
            ]
        if _KWARG_WRITE.search(line) and not any(one in line for one in _SANCTIONED):
            # A keyword ARGUMENT is only a write when it is going into the ORM.
            if "objects.create(" in line or ".update(" in line or "objects.filter(" in line:
                return [
                    f"{where} writes provider_error through the ORM — the only writer is "
                    "services.finish_run, which scrubs"
                ]
    return []


def _python_files() -> list[Path]:
    return sorted(
        path
        for path in BACKEND.rglob("*.py")
        if "__pycache__" not in path.parts and "/tests/" not in str(path)
    )


_CLEAN_SEAM = "    run.provider_error = scrub(provider_error)\n"
_RED_SEAM = "    run.provider_error = provider_error\n"
_CLEAN_CALLER = "    services.finish_run(run, provider_error=result.provider_text)\n"
_RED_CALLER = "    row.provider_error = result.provider_text\n"


def selftest() -> bool:
    if seam_findings(_CLEAN_SEAM, where="selftest"):
        return False
    red_seam = seam_findings(_RED_SEAM, where="selftest")
    if len(red_seam) != 1 or "without scrub()" not in red_seam[0]:
        return False
    if writer_findings(_CLEAN_CALLER, where="selftest"):
        return False
    red_caller = writer_findings(_RED_CALLER, where="selftest")
    return len(red_caller) == 1 and "writes provider_error directly" in red_caller[0]


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold — it cannot see an open seam (DEF-182)"
    seam = BACKEND / SEAM
    if not seam.exists():
        return "FAIL", f"{SEAM} is missing — the seam this gate guards does not exist"
    problems = seam_findings(seam.read_text(encoding="utf-8"), where=SEAM)
    callers = 0
    scanned = 0
    for path in _python_files():
        relative = str(path.relative_to(BACKEND))
        if relative == SEAM or relative.startswith(_ALLOWED_TO_NAME):
            continue
        source = path.read_text(encoding="utf-8")
        if "provider_error" not in source:
            continue
        scanned += 1
        if any(one in source for one in _SANCTIONED):
            callers += 1
        problems.extend(writer_findings(source, where=relative))
    if problems:
        return "FAIL", " | ".join(problems)
    return "PASS", (
        f"provider_error is assigned once, in {SEAM}, and that assignment scrubs; "
        f"{scanned} other file(s) name the column and {callers} of them hand it to the seam "
        "rather than writing it; self-test: both sabotages bite"
    )


def main() -> int:
    status, note = run()
    print(f"G89 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
