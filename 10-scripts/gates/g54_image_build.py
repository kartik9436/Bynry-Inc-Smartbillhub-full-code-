#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2464 (2026-08-30, critical) — the Product Owner ran
#           `docker compose build` and it stopped on
#             src/features/notifications/templateChangeTrail.dom.test.tsx(57,3):
#             error TS2459: Module '"@/api/endpoints"' declares 'ApiClient'
#             locally, but it is not exported.
#           The lane that wrote the file reported `tsc` clean and was telling
#           the truth about the command it ran; `vitest` passed too, because
#           vitest never type-checks. The command that fails is the IMAGE's own
#           — `tsc --noEmit && vite build` — and no gate in this repo ran it.
#           A green branch and a buildable branch were two different things and
#           nothing could tell them apart.
# Rules:    CLAUDE.md hard-won law 2 (built is not wired — here: a check that
#           runs a DIFFERENT command from the one that ships is not a check of
#           the thing that ships) · law 7 (prove a guard RED first) · law 1 (a
#           comment claiming a guarantee is not the guarantee).
# ───────────────────────────────────────────────────────
"""G54 — run the command the shipped IMAGE runs, not one that resembles it.

WHAT IT DOES, AND WHY IT READS THE DOCKERFILE INSTEAD OF NAMING THE COMMAND
---------------------------------------------------------------------------
The whole defect is a gap between two commands that look alike. Writing
`tsc --noEmit && vite build` into this file would re-open that gap the first
time the Dockerfile changed: the gate would go on passing while the image built
something else. So nothing here is typed from memory —

  * `07-frontend/Dockerfile`'s build stage is parsed for its `RUN npm run <s>`;
  * `<s>` is resolved through `07-frontend/package.json`'s `scripts`;
  * that npm script is EXECUTED, in `07-frontend`, and its own output is the
    failure message.

Change `npm run build` in the Dockerfile to `npm run build:prod` and this gate
follows it. Delete the script from package.json and clause (a) fails without
running anything, because an image that cannot resolve its own build command is
already broken.

CLAUSE (c) — THE BACKEND IMAGE, AND WHAT IT HONESTLY COVERS
------------------------------------------------------------
`06-backend/Dockerfile` has one build-stage step nothing else in this repo runs:
it derives `requirements.txt` from `[project].dependencies` with an inline
`python -c` and installs that. If `pyproject.toml` stops parsing, or that table
disappears, the backend image dies in the build stage — and `ruff`, `black`,
`pytest` and every gate here are green over it, because none of them reads that
table. The payload is EXTRACTED from the Dockerfile and run verbatim, the same
rule the frontend half follows.

⚠ **IT DOES NOT COVER `pip install`.** Actually resolving the pins needs a
package index and minutes; this clause proves the image can COMPUTE its pin
list, not that the list installs. Said here rather than left to be assumed
(law 1) — the frontend half is the one that catches DEF-2464's class.

⚠ WHAT THIS GATE IS NOT
------------------------
It is not `docker build`. There is no daemon in the environments this suite runs
in, and a gate that needs one would SKIP everywhere and enforce nothing. It runs
the image's build COMMAND against the working tree, which is the half that fails
and the half a lane can fix. The image's `npm ci` step is NOT re-run — the
installed `node_modules` is used — so a lockfile that cannot install is out of
scope and `ci-frontend.yml`'s `npm ci` remains the check for that.

⚠ IT WRITES `07-frontend/dist/`, WHICH IS A SHARED DIRECTORY
------------------------------------------------------------
`vite build` empties and rewrites `dist/` — the same directory
`08-qa/01-e2e/stack/boot_stack.sh` builds and `server.mjs` serves. So running
this gate while an e2e stack is up replaces the bundle under the running server
for a few seconds. It is stated here rather than avoided, because avoiding it
means passing `--outDir` and **the moment this gate runs a command that is not
the image's command, it is the defect it was written for.** `dist/` is
git-ignored and rebuilt by the next boot; nothing is lost.

SKIP, AND WHY IT IS NOT A HOLE
-------------------------------
With no `npm` on PATH or no `node_modules`, this gate SKIPs and says which. That
is G5's posture — *"it must never report PASS for a suite it did not run"* — and
a SKIP is printed and counted in the runner's own summary line. The place this
must never SKIP is CI, so `.github/workflows/gates.yml` installed Node and ran
`npm ci` before the suite. ⚠ NOT ANY MORE — every workflow was disabled on 2026-09-04 (PO: Actions minutes exhausted); see .github/workflows/README.md. Run it by hand. A local run without `npm ci` SKIPs, and a
SKIP is now nobody's error to catch but yours. A gate that could only ever SKIP would be worth
nothing, which is the same law that put this gate here.

MEASURED RUNTIME (2026-08-30, this container)
----------------------------------------------
`npm run build` = `tsc --noEmit && vite build`: **44.5 s** wall — tsc ~33 s,
`vite build` 11.06 s by its own report, over 391 modules. `npm ci` from a warm
cache: 3.9 s. For scale, the gate suite already spends 94 s in G4 and 134 s in
G5, so this is the third-most expensive gate and not the most.

RED PROOF (hard-won law 7) — the defect itself, replayed
---------------------------------------------------------
Run in a scratch worktree at `4e385f0~1`, the tree the PO's build broke on:

    G54 FAIL — the frontend image build command failed: `npm run build`
    (tsc --noEmit && vite build) in 07-frontend, exit 2.
    src/features/notifications/templateChangeTrail.dom.test.tsx(57,3): error
    TS2459: Module '"@/api/endpoints"' declares 'ApiClient' locally, but it is
    not exported.

and PASS on the tree with DEF-2464's one-line fix. Clause (a) and clause (c)
were each proved RED on a mutated copy of the file they read; the transcripts
are in the lane report and the self-test below re-proves the parsing clauses on
text built here, so the proof does not expire when the tree moves (the lesson
G46 learned the expensive way).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "07-frontend"
FRONTEND_DOCKERFILE = FRONTEND / "Dockerfile"
PACKAGE_JSON = FRONTEND / "package.json"
BACKEND = ROOT / "06-backend"
BACKEND_DOCKERFILE = BACKEND / "Dockerfile"

#: How long the image's build command may take before we call it hung. The
#: measured figure is 44.5 s; ten minutes is "something is wrong", not a budget.
BUILD_TIMEOUT_S = 600

#: `RUN npm run <script>` — the shape the frontend image uses to produce dist/.
#: Anchored at RUN so a `# RUN npm run build` in a comment cannot satisfy it.
NPM_RUN = re.compile(r"^RUN\s+npm\s+run\s+([A-Za-z0-9_:.-]+)\s*$", re.M)

#: `python -c "<payload>"` inside a RUN, which is how the backend image derives
#: its pin list from pyproject.toml. Non-greedy to the closing quote; the
#: payload in that file contains no escaped quote and this gate refuses rather
#: than guesses if that stops being true (see `_backend_payload`).
PY_INLINE = re.compile(r'python -c "((?:[^"\\]|\\.)*)"')


def _dockerfile_lines(text: str) -> str:
    """Join Dockerfile line continuations so a directive is one line.

    A `RUN` split across `\\`-continued lines is one instruction, and a regex
    anchored at `^RUN` would otherwise see only its first fragment.
    """
    return re.sub(r"\\\n\s*", " ", text)


def frontend_build_script(dockerfile_text: str) -> tuple[str | None, str]:
    """The npm script name the image's build stage runs, or (None, why)."""
    joined = _dockerfile_lines(dockerfile_text)
    names = NPM_RUN.findall(joined)
    if not names:
        return None, (
            "07-frontend/Dockerfile has no `RUN npm run <script>` line — this gate "
            "cannot tell what the image builds with, so it cannot run it. If the "
            "image stopped building through an npm script, teach this gate the new "
            "shape; do not delete the gate."
        )
    if len(set(names)) > 1:
        return None, (
            f"07-frontend/Dockerfile runs {len(set(names))} different npm scripts "
            f"({', '.join(sorted(set(names)))}) — this gate runs one build command "
            "and would silently check only part of the image."
        )
    return names[0], ""


def resolve_script(package_json_text: str, name: str) -> tuple[str | None, str]:
    """The command line `npm run <name>` would execute, or (None, why)."""
    try:
        scripts = json.loads(package_json_text).get("scripts") or {}
    except json.JSONDecodeError as exc:
        return None, f"07-frontend/package.json does not parse: {exc}"
    if name not in scripts:
        return None, (
            f"07-frontend/Dockerfile builds with `npm run {name}` and "
            f"package.json declares no `{name}` script — the image build fails "
            f"at that line. Declared: {', '.join(sorted(scripts)) or '(none)'}"
        )
    return scripts[name], ""


def _backend_payload(dockerfile_text: str) -> tuple[str | None, str]:
    """The inline `python -c` the backend image derives its pins with."""
    joined = _dockerfile_lines(dockerfile_text)
    found = PY_INLINE.findall(joined)
    if not found:
        return None, (
            "06-backend/Dockerfile no longer derives its pin list with an inline "
            "`python -c` — this clause cannot follow it. Teach the gate the new "
            "shape rather than removing the clause."
        )
    if len(found) > 1:
        return None, "06-backend/Dockerfile has more than one inline `python -c`; this gate runs one"
    return found[0].replace('\\"', '"'), ""


def _npm_env() -> dict[str, str]:
    """The build stage's own npm environment (Dockerfile `ENV npm_config_*`)."""
    env = dict(os.environ)
    env["npm_config_update_notifier"] = "false"
    env["npm_config_fund"] = "false"
    env.setdefault("CI", "1")
    return env


def _tail(text: str, lines: int = 12, width: int = 1400) -> str:
    kept = [ln for ln in text.strip().splitlines() if ln.strip()][-lines:]
    return " | ".join(kept)[:width] or "(no output)"


def selftest() -> list[str]:
    """Prove each parsing clause bites, on text built here, not on the repo."""
    broken: list[str] = []
    ok_df = "FROM node AS build\nRUN npm ci\nRUN npm run build\n"
    if frontend_build_script(ok_df)[0] != "build":
        broken.append("a plain `RUN npm run build` was not read")
    if frontend_build_script("FROM node\n# RUN npm run build\n")[0] is not None:
        broken.append("a COMMENTED-OUT build line was read as the build command")
    if frontend_build_script("FROM node\nRUN npm ci\n")[0] is not None:
        broken.append("a Dockerfile with no build script was accepted")
    if frontend_build_script("RUN npm run build\nRUN npm run other\n")[0] is not None:
        broken.append("two different build scripts were accepted as one")
    if frontend_build_script("RUN npm \\\n  run build\n")[0] != "build":
        broken.append("a line-continued RUN was not joined")
    if resolve_script('{"scripts":{"build":"tsc && vite build"}}', "build")[0] != "tsc && vite build":
        broken.append("a declared script did not resolve to its command")
    if resolve_script('{"scripts":{"dev":"vite"}}', "build")[0] is not None:
        broken.append("a MISSING script was not reported (that is the image failing)")
    if resolve_script("{not json", "build")[0] is not None:
        broken.append("unparseable package.json was not reported")
    if _backend_payload('RUN python -c "import tomllib" > r.txt\n')[0] != "import tomllib":
        broken.append("the backend inline payload was not extracted")
    if _backend_payload("RUN pip install -r r.txt\n")[0] is not None:
        broken.append("a backend Dockerfile with no inline python was accepted")
    return broken


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    if not FRONTEND_DOCKERFILE.exists():
        return "SKIP", f"no {FRONTEND_DOCKERFILE.relative_to(ROOT)} — nothing builds an image yet"
    if not PACKAGE_JSON.exists():
        return "SKIP", f"no {PACKAGE_JSON.relative_to(ROOT)} — nothing to resolve the build script in"

    # ── clause (a): the image's build command must RESOLVE. Static, always run.
    script, why = frontend_build_script(FRONTEND_DOCKERFILE.read_text(encoding="utf-8"))
    if script is None:
        return "FAIL", why
    command, why = resolve_script(PACKAGE_JSON.read_text(encoding="utf-8"), script)
    if command is None:
        return "FAIL", why

    # ── clause (c): the backend image's pin derivation. Cheap; runs first so a
    # broken pyproject is reported in a second rather than after a 45 s build.
    backend_note = "backend image: not present"
    if BACKEND_DOCKERFILE.exists():
        payload, why = _backend_payload(BACKEND_DOCKERFILE.read_text(encoding="utf-8"))
        if payload is None:
            return "FAIL", why
        done = subprocess.run(
            [sys.executable, "-c", payload],
            capture_output=True,
            text=True,
            cwd=BACKEND,
            timeout=120,
        )
        if done.returncode != 0:
            return "FAIL", (
                "the backend image's own pin-derivation step fails: "
                f"`python -c {payload[:60]}…` in 06-backend, exit {done.returncode}. "
                f"{_tail(done.stderr or done.stdout)} — `docker compose build` dies "
                "here and nothing else in this repo reads [project].dependencies."
            )
        pins = [ln for ln in done.stdout.splitlines() if ln.strip()]
        if not pins:
            return "FAIL", (
                "the backend image derives an EMPTY pin list from pyproject.toml — "
                "the runtime image would ship with no dependencies installed."
            )
        backend_note = f"backend image derives {len(pins)} pin(s) from pyproject.toml"

    # ── clause (b): RUN IT. This is the clause DEF-2464 was about.
    if shutil.which("npm") is None:
        return "SKIP", (
            f"npm is not on PATH — cannot run the image's build command "
            f"(`npm run {script}` = `{command}`). {backend_note}. CI installs Node "
            "before this suite (.github/workflows/gates.yml); a SKIP here is this "
            "environment, not a pass."
        )
    # ⚠ A WORKTREE WITH NO INSTALL BORROWS ONE (`DEF-GOV-9126`'s cure, shared
    # through `common.LinkedFrontendInstall`): `vite build` loads
    # `vite.config.ts` as ESM, so `NODE_PATH` cannot stand in for the
    # directory. This gate SKIPPED in every lane worktree until 2026-10-02
    # (`DEF-GOV-9135`).
    with common.LinkedFrontendInstall("vite", "typescript") as link:
        if not link.ok:
            return "SKIP", (
                f"07-frontend/node_modules is absent and none could be borrowed "
                f"({link.problem}; looked in: {'; '.join(link.tried)}) — cannot run "
                f"`npm run {script}` (`{command}`). Run `npm ci` in 07-frontend first. "
                f"{backend_note}. A SKIP here is this environment, not a pass."
            )
        borrowed_note = link.note
        try:
            done = subprocess.run(
                ["npm", "run", script],
                capture_output=True,
                text=True,
                cwd=FRONTEND,
                env=_npm_env(),
                timeout=BUILD_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return "FAIL", (
                f"`npm run {script}` (`{command}`) did not finish in {BUILD_TIMEOUT_S}s "
                "in 07-frontend — the image build would hang the same way."
            )
    if done.returncode != 0:
        output = "\n".join((done.stdout, done.stderr))
        return "FAIL", (
            f"the frontend image build command failed: `npm run {script}` "
            f"(`{command}`) in 07-frontend, exit {done.returncode}. "
            f"{_tail(output)} — this is what "
            "`docker compose build` prints. tsc and vitest can both be green on "
            "it (DEF-2464): vitest never type-checks, and a narrower tsc "
            "invocation sees a different file set."
        )
    return "PASS", (
        f"the image's own build command ran: `npm run {script}` = `{command}` "
        f"in 07-frontend, exit 0; {backend_note}; self-test: 10/10 clauses bite"
        f"{borrowed_note}"
    )


def main() -> int:
    status, note = run()
    print(f"G54 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
