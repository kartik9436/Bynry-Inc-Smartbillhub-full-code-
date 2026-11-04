#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-013 (EP-INT-05) TC-5 — `provider_key ==` appears nowhere in
#           06-backend/apps outside apps/integrations/adapters/ and manifests/.
#           CR-069 §13 gate 1: "a new connector adds no code outside adapters/".
# Rules:    BR-INT-037 (P1 — configuration is data, not code; adding a provider
#           touches no screen, no endpoint and no migration; *"break this and
#           every connector becomes a sprint"*) · BR-INT-004 (no provider
#           hardcoded into business logic) · CLAUDE.md hard-won law 7 (proven
#           RED first — see the docstring)
# Tests:    selftest() below
# Impacts:  every file under 06-backend/apps
# ───────────────────────────────────────────────────────
"""G77 — nothing outside `adapters/` and `manifests/` branches on a provider key.

WHY THIS GATE EXISTS
--------------------
P1 is the requester's own sentence — *"every time such integration comes we
dont want to change our integration framework"* — and it has one failure
shape: a branch. `if provider_key == "email_smtp": …` in a service, a
selector, a runner or a screen is the moment a provider stops being data and
becomes a sprint, because the next provider needs the next branch, and the
branch after that is in a file nobody remembers. The registry makes the
declarative path easy; this gate makes the branching path fail the merge.

WHAT IT READS
-------------
Every `.py` under `06-backend/apps`, EXCEPT `apps/integrations/adapters/` and
`apps/integrations/manifests/` — the two places a provider's name legitimately
appears in code — and EXCEPT migrations (a data migration may name a key it
moves) and tests (a test names the provider it tests). It refuses:

  * `provider_key ==` / `provider_key !=` / `provider_key in (` / `in [` — the
    comparison forms, on either side, including `.provider_key` on a row;
  * `provider_key: "…"`-style dict dispatch is NOT refused — a mapping keyed by
    provider that lives in the registry IS the declarative form, and the
    registry module is where such maps belong. The gate is about branches.

Comments and docstrings are stripped before matching, so a sentence
explaining the rule cannot trip it (the DEF-741 shape).

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `if provider_key == "email_smtp":` written into
`apps/integrations/services.py` the gate reported
    FAIL: 06-backend/apps/integrations/services.py:NNN branches on provider_key —
    a provider is data, not code (BR-INT-037)
and with the line removed it went green. `selftest()` replays that on an
in-memory body and `run()` refuses to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APPS = REPO / "06-backend" / "apps"
ALLOWED_DIRS = (
    APPS / "integrations" / "adapters",
    APPS / "integrations" / "manifests",
)
#: `provider_key == "x"`, `row.provider_key != key`, `provider_key in ("a", "b")`,
#: and the same with the key on the left: `"email_smtp" == provider_key`.
#:
#: ⚠ **KEPT ONLY AS THE FALLBACK FOR A FILE THAT WILL NOT PARSE — `DEF-INT-4400`
#: IS WHY IT IS NO LONGER THE CHECK.** `_code_only()` BLANKS every string
#: literal before this pattern runs, so by the time it matches, the thing that
#: tells a real branch from an innocent comparison is already gone: this
#: pattern cannot see the difference between `provider_key == "email_smtp"` and
#: `one["provider_key"] != provider_key`, and it refused the second one for a
#: day. That second form names NO provider and does not change when a provider
#: is added — it counts how many rows on a page belong to a different
#: connection — which is the exact opposite of what BR-INT-037 is about.
BRANCH = re.compile(
    r"""(?:\bprovider_key\s*(?:==|!=|\bin\s*[\(\[]))"""
    r"""|(?:(?:==|!=)\s*[\w.]*provider_key\b)"""
)


def _is_provider_key_expr(node: ast.AST) -> bool:
    """Is this expression A PROVIDER KEY rather than a value naming ONE provider?

    `provider_key`, `row.provider_key`, `one["provider_key"]` — all of them are
    "whatever key this row/connection happens to carry". None of them names a
    provider, so a comparison BETWEEN TWO of them is data handling, not a
    branch on a provider.
    """
    if isinstance(node, ast.Name):
        return node.id == "provider_key" or node.id.endswith("_provider_key")
    if isinstance(node, ast.Attribute):
        return node.attr == "provider_key"
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and key.value == "provider_key"
    return False


def _branch_compares(source: str) -> list[int] | None:
    """Line numbers of every comparison that BRANCHES ON A PROVIDER.

    `None` when the source will not parse — the caller falls back to `BRANCH`
    rather than reporting nothing, because a file this gate cannot read must
    not read as a clean file (law 7: a check that silently excludes part of its
    scope is indistinguishable from one that found nothing).

    ⚠ **THE ONE THING THIS ALLOWS AND THE OLD PATTERN DID NOT**: a comparison
    whose BOTH sides are provider-key expressions. Everything else the old
    pattern refused is still refused — a literal, a Name bound to a literal, a
    tuple of them, on either side — so this narrows the gate to its own
    docstring rather than loosening it. AST also removes the need to blank
    comments and docstrings: neither is a `Compare` node.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in node.ops):
            continue
        sides = [node.left, *node.comparators]
        if not any(_is_provider_key_expr(side) for side in sides):
            continue
        if all(_is_provider_key_expr(side) for side in sides):
            continue  # key vs key — no provider is named and none can be
        lines.append(node.lineno)
    return sorted(set(lines))


def _code_only(source: str) -> str:
    """The source with every comment and string literal blanked — a rule
    written down in a docstring is not a branch. Line structure is kept, so a
    finding's line number is the real one."""
    lines = source.splitlines(keepends=True)
    blanked = [list(line) for line in lines]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (r0, c0), (r1, c1) = tok.start, tok.end
            for row in range(r0, r1 + 1):
                line = blanked[row - 1]
                start = c0 if row == r0 else 0
                end = c1 if row == r1 else len(line)
                for col in range(start, min(end, len(line))):
                    if line[col] != "\n":
                        line[col] = " "
    except (tokenize.TokenError, IndexError):
        return source
    return "".join("".join(line) for line in blanked)


def findings_in(source: str, *, where: str) -> list[str]:
    numbers = _branch_compares(source)
    if numbers is None:  # unparseable — fall back to the blunt pattern
        numbers = [
            n
            for n, line in enumerate(_code_only(source).splitlines(), start=1)
            if BRANCH.search(line)
        ]
    return [
        f"{where}:{number} branches on provider_key — a provider is data, not code "
        "(BR-INT-037, US-INT-013 TC-5)"
        for number in numbers
    ]


def _guarded_files() -> list[Path]:
    found: list[Path] = []
    for path in sorted(APPS.rglob("*.py")):
        if any(allowed in path.parents for allowed in ALLOWED_DIRS):
            continue
        if "migrations" in path.parts or path.name.startswith("test"):
            continue
        found.append(path)
    return found


CLEAN = '''
def connect(provider_key):
    manifest = registry.require(provider_key)  # the registry decides, by key
    # if provider_key == "email_smtp": this is a comment, not a branch
    return manifest
'''
RED = CLEAN + '''
def send(row):
    if row.provider_key == "email_smtp":
        return smtp_send(row)
'''
RED_LEFT = CLEAN + '''
def send(provider_key):
    if "email_smtp" == provider_key:
        return 1
'''
#: ⚠ **A NAME BOUND TO A LITERAL IS THE SAME BRANCH WEARING A CONSTANT**, and
#: the AST check must keep refusing it — narrowing the gate to "a string on the
#: other side" would have opened exactly this door (`DEF-INT-4400`).
RED_CONSTANT = CLEAN + '''
EMAIL_SMTP = "email_smtp"


def send(provider_key):
    if provider_key == EMAIL_SMTP:
        return 1
'''
#: ⚠ **AND THE CASE THIS GATE USED TO GET WRONG.** Neither side names a
#: provider; this counts how many rows on a page belong to a DIFFERENT
#: connection than the one whose page is open, and it does not change when a
#: provider is added. `_code_only()` blanks the string first, so the old
#: pattern saw `provider_key !=` and could not tell this from `RED` above.
GREEN_KEY_VS_KEY = CLEAN + '''
def elsewhere(rows, provider_key):
    return sum(1 for one in rows if one["provider_key"] != provider_key)
'''


def selftest() -> bool:
    if findings_in(CLEAN, where="selftest"):
        return False
    if findings_in(GREEN_KEY_VS_KEY, where="selftest"):
        return False
    red = findings_in(RED, where="selftest")
    left = findings_in(RED_LEFT, where="selftest")
    constant = findings_in(RED_CONSTANT, where="selftest")
    return len(red) == 1 and ":8 " in red[0] and len(left) == 1 and len(constant) == 1


def run() -> tuple[str, str]:
    if not APPS.is_dir():
        return "SKIP", f"{APPS.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a branch on a provider "
            "key from a registry lookup, so its verdict is worthless (DEF-182)"
        )
    problems: list[str] = []
    files = _guarded_files()
    for path in files:
        problems.extend(
            findings_in(path.read_text(encoding="utf-8"), where=str(path.relative_to(REPO)))
        )
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (f" (+{len(problems) - 6} more)" if len(problems) > 6 else "")
    return "PASS", (
        f"{len(files)} file(s) under 06-backend/apps outside adapters/ and manifests/ branch on "
        "no provider key — adding a provider is a manifest and an adapter, never a sprint; "
        "self-test: the sabotage bites (a provider-key branch in a service module)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
