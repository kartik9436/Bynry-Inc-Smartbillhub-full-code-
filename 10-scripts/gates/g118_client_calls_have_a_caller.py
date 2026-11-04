#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-4359 (a customer who signed in to the portal could not sign
#          out — `POST portal/auth/sign-out` was served, `signOut()` was
#          exported, and nothing imported it) · DEF-CWP-3925 (the mirror: five
#          live portal screens behind controls that still refused) ·
#          DEF-CWP-3954 (26 portal screens with no door into them)
# Rules:   CLAUDE.md hard-won law 2 (BUILT IS NOT WIRED) · law 7 (proved RED
#          first, and in the harness that will run it — `DEF-GOV-3733`; and a
#          check that cannot cover its whole subject must PRINT WHAT IT
#          SKIPPED beside what it checked) · B14 rule 36
# Tests:   `selftest()` below — `run()` refuses to report until it has passed ·
#          07-frontend/src/portal/shell/SignOut.dom.test.tsx
# Impacts: 07-frontend/src/portal/api/*.ts ·
#          10-scripts/gates/g118_dead_client_calls_baseline.txt
# ───────────────────────────────────────────────────────
"""G118 — every portal API call the client exports has a caller.

WHY THIS GATE EXISTS
--------------------
On 2026-09-07 the Product Owner reported, on the running product: *"we dont
have sign out in Customer portal"*. The route was served
(`POST portal/auth/sign-out`, `apps/portal/api.py`), the wrapper was written
(`portalClient.signOut()`), the backend had tests, and **nothing under
`07-frontend/src/portal/` imported the wrapper**. A customer's session
therefore ended only when the cookie expired, so on a library or
service-counter machine the next person got the previous customer's bills,
address and payment history.

**Every check in the repo passed over it, and each was doing its job.** `tsc`
is content with an exported symbol nobody imports; eslint's `no-unused-vars`
stops at the module boundary; the portal's 42 test files and 391 cases all
test screens that EXIST, and none can ask whether a screen is missing. `G13`
asks the same question one shape over — *is this component PROP ever
supplied* — and an exported FUNCTION is not a prop, so `G13` never looked.

`G100` covers the other end of the same wire: every SCREEN has a door into it.
This covers the wire itself — a served endpoint whose only client-side caller
is the client.

WHAT IT ASSERTS
---------------
Every `export function` / `export async function` in the portal's API modules
that actually performs a request — its body calls `client.get<`, `.post<`,
`.put<`, `.patch<` or `.delete<` — is **imported by name from at least one
non-test file outside its own module**.

**A test-only importer does not count, and that is the whole point.** A wrapper
exercised by its own unit test and called by no screen is exactly the shape
`DEF-CWP-4359` was: proof that the call WORKS is not proof that anything makes
it.

**The importer is read from IMPORT STATEMENTS, not from a word search.** A
grep for `signOut` matches `shell.user.signOut` in eleven locale catalogues,
the staff app's own unrelated `signOut`, and every comment naming the defect —
which is a check that can only pass. This resolves the module path an import
comes from and takes the names in its braces, so the answer is *this file
imports THIS function from THIS module* or nothing.

THE BASELINE, AND WHY IT SHRINKS ONLY
-------------------------------------
Three wrappers had no caller on the day this landed and none of them is this
lane's to wire:

  * `portalClient.getBalanceSummary` and `getAccountBalance` — superseded in
    practice by `getHome()`, which brings `balances` down with the page. The
    endpoints are still served; whether they should be is a portal question,
    not a gate's.
  * `guestClient.getPortalTip` — `BR-CWP-095`'s tip bar is deliberately absent
    today, so this is a wrapper waiting for a screen rather than a screen
    missing a wrapper.

They are named in `g118_dead_client_calls_baseline.txt`, the gate refuses
anything NOT on that list, and the file may only SHRINK — the ratchet `G28`
and `G86` already use here. **A baseline entry is `module::function`, never a
line number**, because a line number moves under an unrelated edit and a gate
that goes red on somebody else's commit is a gate nobody trusts.

WHAT IT CANNOT SEE, SAID OUT LOUD WITH A NUMBER
-----------------------------------------------
`run()` prints the count of wrappers CHECKED and the count SKIPPED, because a
declared blind spot with no number attached is indistinguishable from an empty
one (law 7, `G32`'s lesson — it reported *0 unresolved* truthfully over 21 live
refusals it could not see).

  * **It reads the portal only.** The staff app's `src/api/` is out of scope
    here; it has `G13` over its props and a shell that has had a sign-out
    since `DEF-037`.
  * **An importer is not a caller.** A file that imports `signOut` and never
    invokes it satisfies this gate. That is `G13`'s territory one level down
    and no gate here reads rendered output (law 6) — the browser walkthrough
    is what closes it.
  * **A wrapper re-exported through a barrel** would be counted as imported by
    the barrel. The portal has no barrel today; if one appears, this comment is
    where the next lane finds out why the number moved.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import common

FRONTEND = common.FRONTEND_SRC
PORTAL = FRONTEND / "portal"
BASELINE = Path(__file__).with_name("g118_dead_client_calls_baseline.txt")

#: An API module: everything under `portal/api/`, plus the per-feature `*Api.ts`
#: modules that do the same job one directory down.
def _client_modules() -> list[Path]:
    found = sorted((PORTAL / "api").glob("*.ts"))
    found += sorted(p for p in PORTAL.rglob("*Api.ts") if "/api/" not in p.as_posix())
    return [p for p in found if ".test." not in p.name and ".d.ts" not in p.name]


_EXPORTED = re.compile(r"^export (?:async )?function (\w+)\s*\(", re.M)
_REQUESTS = re.compile(r"\bclient\.(?:get|post|put|patch|delete)\s*<")


def _calls_in(text: str) -> list[str]:
    """The exported functions of one module that actually perform a request.

    The body is taken as the text from the `export` line to the next top-level
    `export`/end of file — coarse on purpose: a wrapper that delegates to a
    sibling wrapper in the same file is still a call the product must make.
    """
    names: list[str] = []
    marks = [(m.start(), m.group(1)) for m in _EXPORTED.finditer(text)]
    for index, (start, name) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(text)
        if _REQUESTS.search(text[start:end]):
            names.append(name)
    return names


_IMPORT = re.compile(r"import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*[\"']([^\"']+)[\"']", re.S)


def _imported_names(text: str, module_stem: str) -> set[str]:
    """Names this file imports FROM a module whose path ends in `module_stem`.

    ⚠ Read from the import statement rather than by searching for the word.
    `signOut` appears in eleven locale catalogues (`shell.user.signOut`), in
    the staff shell, and in every comment naming `DEF-CWP-4359` — a word search
    is a check that cannot fail.
    """
    names: set[str] = set()
    for clause, source in _IMPORT.findall(text):
        if not source.split("/")[-1].startswith(module_stem):
            continue
        for piece in clause.split(","):
            piece = piece.strip()
            if not piece:
                continue
            piece = re.sub(r"^type\s+", "", piece)
            names.add(piece.split(" as ")[0].strip())
    return names


def _is_test(path: Path) -> bool:
    return ".test." in path.name or ".spec." in path.name


def _readers(module: Path) -> set[str]:
    """Every name any non-test file OUTSIDE `module` imports from it."""
    stem = module.name[: -len(".ts")]
    seen: set[str] = set()
    for path in FRONTEND.rglob("*.ts*"):
        if path == module or _is_test(path):
            continue
        seen |= _imported_names(common.read_text(path), stem)
    return seen


def _baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return {
        line.split("#")[0].strip()
        for line in BASELINE.read_text().splitlines()
        if line.split("#")[0].strip()
    }


def _findings() -> tuple[list[str], int, int]:
    allowed = _baseline()
    findings: list[str] = []
    checked = 0
    excused = 0
    for module in _client_modules():
        text = common.read_text(module)
        calls = _calls_in(text)
        if not calls:
            continue
        readers = _readers(module)
        stem = module.name[: -len(".ts")]
        for name in calls:
            checked += 1
            if name in readers:
                continue
            entry = f"{stem}::{name}"
            if entry in allowed:
                excused += 1
                continue
            findings.append(
                f"{common.rel(module)}: `{name}` is exported, calls the server, and NO "
                f"non-test file imports it — a served endpoint with no door (DEF-CWP-4359)"
            )
    return findings, checked, excused


# ── law 7 · the sabotages, on SYNTHETIC text ─────────────────────────────
_MODULE = """
export async function signOut(client: ApiClient = api): Promise<{ ok: boolean }> {
  return requireData(await client.post<{ ok: boolean }>("/portal/auth/sign-out", {}));
}
export interface Thing { a: string }
export function labelOf(thing: Thing): string {
  return thing.a;
}
"""
_SCREEN_WIRED = 'import { signOut } from "../api/portalClient";\nsignOut(api);\n'
_SCREEN_WORD_ONLY = '// DEF-CWP-4359 was about signOut and this file only talks about it\n'


def selftest() -> tuple[bool, str]:
    """Both directions, on synthetic text — a genuine finding must read as a
    finding and not as a broken selftest, so the real tree is never touched."""
    calls = _calls_in(_MODULE)
    if calls != ["signOut"]:
        return False, f"the request-detector saw {calls!r}, not ['signOut'] — a pure helper is not a call"
    if _imported_names(_SCREEN_WIRED, "portalClient") != {"signOut"}:
        return False, "a real named import was NOT seen — the gate would report every wrapper dead"
    if _imported_names(_SCREEN_WORD_ONLY, "portalClient"):
        return False, "a COMMENT mentioning the name counted as an importer — the check cannot fail"
    if _imported_names('import { signOut } from "@/api/session";\n', "portalClient"):
        return False, "an import from ANOTHER module counted — the staff app's signOut would excuse the portal's"
    return True, "a call is seen, a helper is not, a real import counts and a comment does not"


def run() -> tuple[str, str]:
    ok, how = selftest()
    if not ok:
        return "FAIL", f"self-test failed, so nothing below is trustworthy: {how}"
    findings, checked, excused = _findings()
    modules = ", ".join(common.rel(m) for m in _client_modules())
    detail = (
        f"{checked} portal API wrappers checked for a non-test importer, "
        f"{excused} excused by the shrink-only baseline. Scope: {modules}. "
        "NOT checked: the staff app's client, and whether an importer actually "
        f"INVOKES what it imported (law 6 — the browser walkthrough closes that). self-test: {how}"
    )
    if findings:
        return "FAIL", " | ".join(findings) + f" | {detail}"
    return "PASS", detail


if __name__ == "__main__":
    status, why = run()
    print(f"{status}  {why}")
    sys.exit(0 if status == "PASS" else 1)
