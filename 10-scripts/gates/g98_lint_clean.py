#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-3935 (2026-09-05) — eslint was RED at the branch tip with
#           TEN errors and NOTHING in this repository ran it. It is DEF-159 one
#           language over: that row put `tsc` into the gates on 2026-08-16 and
#           the linter was never added, so for three weeks the only thing
#           reading eslint has been a human who happened to type it.
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee — `package.json` declaring a `lint` script is not the
#           lint being run) · law 7, both halves (prove a guard RED first, and
#           prove it through the harness that will run it) · law 2 (built is
#           not wired) · G54's rule: take the command from where it is
#           DECLARED, never retype it.
# Tests:    selftest() below, exercised through run()
# Impacts:  10-scripts/gates/run_gates.py · 07-frontend/package.json (scripts.lint)
# ───────────────────────────────────────────────────────
"""G98 — the front end's own linter runs, and its exit code is read.

WHY THIS GATE EXISTS
--------------------
On 2026-09-05 `eslint src --ext .ts,.tsx --max-warnings 0` exited 1 on the
branch tip with ten errors. **Three checks passed over every one of them, and
each was right in its own terms:**

  * `tsc --noEmit` exits 0 — an unused import is legal TypeScript;
  * `vitest` passes — nothing imports the dead symbols;
  * `vite build` strips types without reading them.

So the branch was green by every mechanical measure this repo had, and the
linter had been red for an unknown number of days. The errors were not merely
cosmetic: one was a fresh array literal feeding a `useMemo` dependency list, so
the memo re-ran on every render; two were the residue of a *correct* deletion;
and two more were unused test fixtures that turned out to be **assertions that
had gone missing** — `centreStatusLine` was imported by a case NAMED *"the
status line is built from the server's FACTS"* which never asserted the status
line (`DEF-CWP-3940`).

That last one is the argument for this gate over a tidy-up: an unused symbol in
a test file is one of the cheapest available signals that a check was lost, and
until today nothing in this repo was reading that signal.

WHAT IT RUNS, AND WHY IT IS NOT `npx eslint`
---------------------------------------------
It resolves `scripts.lint` out of `07-frontend/package.json` and runs THAT,
through `npm run`. Two reasons, and the second was measured rather than
assumed:

**1 · A gate that retypes the command is the bug it is guarding against.** This
is G54's rule (`DEF-2464`): a check running a command that RESEMBLES the shipped
one tells you nothing about the shipped one. Change `scripts.lint` and this gate
follows it; delete the script and the gate FAILS rather than passing over
nothing.

⚠ **2 · `npx eslint` RUNS A DIFFERENT LINTER, AND IT LOOKS LIKE A BROKEN REPO
RATHER THAN A WRONG COMMAND.** `07-frontend` declares `eslint ^8.57.0` and
configures it in `.eslintrc.cjs`. `npx eslint` with nothing installed fetches
the CURRENT eslint from the registry — 10.1.0 the day this was written — which
dropped `.eslintrc.*` support entirely and answers:

    ESLint couldn't find an eslint.config.(js|mjs|cjs) file.

Exit code 2, no files linted, and a lane reading that concludes the repo's lint
setup is broken. **A gate written as `npx eslint --max-warnings 0` would have
been red on every machine for a reason having nothing to do with the code.**
`npm run lint` resolves `node_modules/.bin/eslint`, which is the pinned 8.57.1.

NO INSTALL IN THIS WORKTREE, AND WHY THAT IS NO LONGER A SKIP
--------------------------------------------------------------
⚠ **UNTIL 2026-10-02 THIS SECTION WAS TITLED *"SKIP, AND WHY IT IS NOT A
HOLE"* — AND IT WAS A HOLE (`DEF-GOV-5918`).** With no `07-frontend/node_modules`
this gate SKIPped, honestly, saying so. But `node_modules/` is gitignored, so
EVERY lane worktree has none, and law 12 sends every lane into a worktree: the
gate's scope was empty almost everywhere it actually ran. A SKIP inside a suite
with dozens of FAILs is invisible, and **107 lint errors built up behind it**
(two of them `rules-of-hooks` crashes, `DEF-GOV-8540`) until a lane happened to
symlink an install in.

So the gate now finds an install the way the Python gates find a virtualenv —
`common.frontend_node_modules("eslint")`: this checkout's own first, then the
MAIN worktree's through `git rev-parse --git-common-dir`, then nothing. When it
borrows one it still runs `npm run lint` in THIS checkout (so the files linted
are this tree's), with the install's `.bin` first on `PATH` and the install on
`NODE_PATH` so eslint 8 resolves the parser and plugins `.eslintrc.cjs` names.
It prints which install it used, and FAILs if that install's eslint is a
different major from the one `package.json` declares.

**And when no install exists anywhere, or `npm` is not on PATH, it FAILs** —
law 3, defaults fail closed — naming the number of files that went unlinted and
every place it looked. The cure is `npm ci` in `07-frontend` (here or in the
main checkout), never `npx eslint`.

⚠ WHAT THIS GATE IS NOT
------------------------
It is not a style opinion. It runs the rule set the repo already declares and
reads the exit code; every rule it enforces was chosen in `.eslintrc.cjs` long
before this file existed. It adds no rule and it silences none. **And it has no
baseline on purpose:** the tip was ten errors from clean, which is a morning's
work rather than the 120-row ratchet a `G95` needed, and a baseline here would
have parked exactly the two missing assertions that were worth finding.

PROVED RED FIRST, THROUGH `run()` (law 7, both halves)
-------------------------------------------------------
`selftest()` writes a file with a deliberate unused import into `src/`, runs the
real linter over it through the same `run()` the suite calls, and requires a
FAIL naming that file — then removes it and requires the gate to come back. A
red proof through `__main__` alone is no proof of the thing that matters
(`DEF-GOV-3733`: two gates announced green while the suite reported
`gate crashed: AttributeError: module has no attribute 'run'`).
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FRONTEND = ROOT / "07-frontend"
PACKAGE_JSON = FRONTEND / "package.json"
#: Measured at 41 s over 743 files on the day this was written. Generous, but a
#: linter that hangs must report a hang rather than a pass.
LINT_TIMEOUT_S = 600
#: The script `package.json` is expected to declare. The NAME is fixed here so a
#: renamed script fails loudly; the COMMAND behind it is never retyped.
LINT_SCRIPT = "lint"


def resolve_script(package_json_text: str, name: str) -> tuple[str | None, str]:
    """The command `npm run <name>` would execute, out of package.json."""
    try:
        data = json.loads(package_json_text)
    except json.JSONDecodeError as exc:
        return None, f"07-frontend/package.json does not parse ({exc}) — npm cannot run anything"
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None, "07-frontend/package.json declares no `scripts` table"
    command = scripts.get(name)
    if not isinstance(command, str) or not command.strip():
        return None, (
            f"07-frontend/package.json declares no `{name}` script. The linter is "
            "not run by anything else in this repository, so removing the script "
            "removes the check — which is the defect this gate was written for."
        )
    return command.strip(), ""


def _npm_env() -> dict[str, str]:
    env = dict(os.environ)
    env["npm_config_update_notifier"] = "false"
    env["npm_config_fund"] = "false"
    env.setdefault("CI", "1")
    return env


def _tail(text: str, lines: int = 10, width: int = 900) -> str:
    kept = [ln for ln in text.strip().splitlines() if ln.strip()][-lines:]
    return " | ".join(kept)[:width] or "(no output)"


def offending_files(text: str) -> list[str]:
    """The files eslint named, repo-relative.

    ⚠ **THE TAIL ALONE IS NOT ENOUGH AND THIS GATE PROVED IT ON ITSELF.** The
    first draft reported `_tail(output)` and nothing else, and its own self-test
    then failed: eslint's stylish formatter prints each path on its own line
    above that file's errors, sorted, so `src/_g98_selftest_tmp.ts` sat at the
    TOP of the output and the tail cut the filename away — leaving an error
    message with nothing to say which file it was in. That is `DEF-CWP-3928`
    exactly (*a proof script ending in `tail -n` truncates the evidence it
    exists to produce*), reproduced inside the guard written to stop this class
    of thing. The paths are extracted whole, and the tail is kept for the rule
    names beside them.
    """
    found: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("/", "\\")) is False:
            continue
        if "07-frontend/src" not in line:
            continue
        rel = line.split("07-frontend/", 1)[1]
        if rel not in found:
            found.append(rel)
    return found


def _source_files() -> int:
    src = FRONTEND / "src"
    if not src.is_dir():
        return 0
    return sum(1 for _ in src.rglob("*.ts")) + sum(1 for _ in src.rglob("*.tsx"))


def _declared_major(package_json_text: str, name: str) -> str | None:
    try:
        data = json.loads(package_json_text)
    except json.JSONDecodeError:
        return None
    for table in ("devDependencies", "dependencies"):
        spec = (data.get(table) or {}).get(name)
        if isinstance(spec, str):
            digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in spec).split()
            return digits[0].split(".")[0] if digits else None
    return None


def _installed_version(node_modules: pathlib.Path, name: str) -> str | None:
    try:
        return json.loads(
            (node_modules / name / "package.json").read_text(encoding="utf-8")
        ).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def _lint(command: str) -> tuple[str, str]:
    """Run the declared lint script. Returns (status, detail).

    Never SKIPs (`DEF-GOV-5918`): no npm, or no reachable install, is a FAIL
    that names how many files went unlinted.
    """
    unchecked = _source_files()
    if shutil.which("npm") is None:
        return "FAIL", (
            f"npm is not on PATH — {unchecked} file(s) under 07-frontend/src were NOT "
            f"linted (`npm run {LINT_SCRIPT}` = `{command}`). Not a pass: install "
            "Node/npm and run `npm ci` in 07-frontend (DEF-GOV-5918)."
        )
    node_modules, tried = common.frontend_node_modules("eslint")
    if node_modules is None:
        return "FAIL", (
            f"no eslint install reachable — {unchecked} file(s) under 07-frontend/src "
            f"were NOT linted. Looked in: {'; '.join(tried)}. Run `npm ci` in "
            "07-frontend (this checkout or the main one). ⚠ Do NOT reach for "
            "`npx eslint`: with nothing installed it fetches eslint 10, which cannot "
            "read this repo's `.eslintrc.cjs` and exits 2 having linted nothing "
            "(DEF-GOV-5918: this used to SKIP, and 107 errors hid behind it)."
        )
    env = _npm_env()
    note = ""
    if node_modules.resolve() != (FRONTEND / "node_modules").resolve():
        declared = _declared_major(PACKAGE_JSON.read_text(encoding="utf-8"), "eslint")
        installed = _installed_version(node_modules, "eslint")
        if declared and (installed or "").split(".")[0] != declared:
            return "FAIL", (
                f"07-frontend/node_modules is absent here and the install found at "
                f"{node_modules} carries eslint {installed}, not the major {declared} "
                f"this package.json declares — {unchecked} file(s) NOT linted. Run "
                "`npm ci` in 07-frontend."
            )
        env["PATH"] = str(node_modules / ".bin") + os.pathsep + env.get("PATH", "")
        prior = env.get("NODE_PATH", "")
        env["NODE_PATH"] = str(node_modules) + (os.pathsep + prior if prior else "")
        note = f" — this worktree has no install, so the one at {node_modules} (eslint {installed}) was used"
    try:
        done = subprocess.run(
            ["npm", "run", LINT_SCRIPT],
            capture_output=True,
            text=True,
            cwd=FRONTEND,
            env=env,
            timeout=LINT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return "FAIL", (
            f"`npm run {LINT_SCRIPT}` (`{command}`) did not finish in "
            f"{LINT_TIMEOUT_S}s in 07-frontend."
        )
    if done.returncode != 0:
        output = "\n".join((done.stdout, done.stderr))
        files = offending_files(output)
        named = "; ".join(files[:12]) + (f" (+{len(files) - 12} more)" if len(files) > 12 else "")
        return "FAIL", (
            f"eslint is RED: `npm run {LINT_SCRIPT}` (`{command}`) exited "
            f"{done.returncode} in 07-frontend{note}. {len(files)} file(s): {named}. "
            f"Last lines: {_tail(output)} — ⚠ tsc, vitest and "
            "vite build can ALL be green over these (DEF-CUS-3935): an unused import "
            "is legal TypeScript, nothing imports a dead symbol, and the bundler "
            "strips types without reading them. In a TEST file an unused symbol is "
            "often an assertion that went missing — read it before deleting it."
        )
    return "PASS", note


def selftest() -> list[str]:
    """Break it, prove the break is reported, put it back. Through `run()`."""
    broken: list[str] = []

    ok, _ = resolve_script('{"scripts":{"lint":"eslint src"}}', "lint")
    if ok != "eslint src":
        broken.append("a declared lint script did not resolve to its command")
    if resolve_script('{"scripts":{"build":"vite build"}}', "lint")[0] is not None:
        broken.append("a MISSING lint script was not reported")
    if resolve_script("{not json", "lint")[0] is not None:
        broken.append("an unparseable package.json was not reported")

    # The live half. Only meaningful where the linter can actually run; where it
    # cannot, `run()` FAILs and says so (DEF-GOV-5918), and there is nothing to
    # prove here.
    if shutil.which("npm") is None or common.frontend_node_modules("eslint")[0] is None:
        return broken

    sabotage = FRONTEND / "src" / "_g98_selftest_tmp.ts"
    try:
        sabotage.write_text(
            "// A deliberate unused import, to prove this gate goes RED.\n"
            "import { useMemo } from 'react';\n"
            "export const G98_SELFTEST = 1;\n",
            encoding="utf-8",
        )
        status, detail = run()
        if status != "FAIL" or "_g98_selftest_tmp" not in detail:
            broken.append(
                f"an unused import did not bite through run() ({status}: {detail[:180]})"
            )
    finally:
        sabotage.unlink(missing_ok=True)
    return broken


def run() -> tuple[str, str]:
    if not PACKAGE_JSON.exists():
        return "SKIP", "no 07-frontend/package.json — nothing declares a linter yet"

    command, why = resolve_script(PACKAGE_JSON.read_text(encoding="utf-8"), LINT_SCRIPT)
    if command is None:
        return "FAIL", why

    status, detail = _lint(command)
    if status != "PASS":
        return status, detail

    return "PASS", (
        f"`npm run {LINT_SCRIPT}` (`{command}`) is clean over {_source_files()} file(s) "
        f"under 07-frontend/src — the project's own pinned eslint, not npx's{detail}"
    )


def main() -> int:
    if "--selftest" in sys.argv:
        broken = selftest()
        for line in broken:
            print(f"SELFTEST FAIL: {line}")
        if not broken:
            print("selftest: a missing script, an unparseable manifest and — through "
                  "run() — a live unused import all bite")
        return 1 if broken else 0
    status, detail = run()
    print(f"G98 lint-clean {status}   {detail}")
    return 0 if status in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    raise SystemExit(main())
