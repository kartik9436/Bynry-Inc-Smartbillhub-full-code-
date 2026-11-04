#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3656 (2026-09-04) — `segno` was declared in pyproject.toml
#           and never installed, so `import segno` in the portal's QR file took
#           down `test_us_cus_003_account_write.py`, a suite that only
#           enumerates account routes. The red named the wrong module.
# Rules:    CLAUDE.md hard-won law 1 (a claim is not the guarantee) · law 3
#           (defaults fail closed — a check that cannot fail must not pass) ·
#           the workflows disabled 2026-09-04 (.github/workflows/README.md)
# Tests:    selftest() below
# Impacts:  06-backend/pyproject.toml — every commit that adds a dependency
# ───────────────────────────────────────────────────────
"""G87 — every dependency this project declares is actually installed.

WHY THIS EXISTS NOW AND NOT BEFORE
-----------------------------------
Until 2026-09-04 a GitHub workflow installed from `pyproject.toml` on every
push, so a declared-but-missing dependency could not survive a pull request.
**Every workflow was disabled that day** at the Product Owner's instruction
(Actions minutes exhausted), and within hours `DEF-CWP-3656` happened: `segno`
was declared, was not installed, and `import segno` inside the portal's QR file
took down a test about account routes. The traceback named `apps/portal/qr.py`;
the red test named `customers`. Nobody would have guessed *"a dependency is
missing"* from that.

That is the first measured cost of turning CI off. This gate is the cheapest
part of paying it: `pip install -e 06-backend` is now something a person has to
remember, and this is the check that notices when they did not.

WHAT IT DOES
-------------
Parses `[project] dependencies` and every `[project.optional-dependencies]`
group out of `06-backend/pyproject.toml` with `tomllib`, reduces each
requirement string to its DISTRIBUTION name (dropping extras and version
specifiers — `psycopg[binary]>=3.1` is the distribution `psycopg`), and asks
`importlib.metadata` whether that distribution is installed.

⚠ **IT ASKS ABOUT THE DISTRIBUTION, NOT THE IMPORT NAME, AND THAT IS THE WHOLE
DESIGN.** A gate that tried `import <name>` would need a hand-maintained map
for every package whose module is spelled differently from its distribution
(`python-dateutil` → `dateutil`, `pillow` → `PIL`, `djangorestframework` →
`rest_framework`). That map is a second list to keep in step with the first,
which is the shape of the defect this gate is written for.

⚠ **IT REFUSES ON THE WRONG INTERPRETER RATHER THAN PASSING** (law 3, and the
lesson of `DEF-524`: G14's hardcoded path outlived the file it named and
reported PASS through six defects). `importlib.metadata` answers about the
interpreter that is RUNNING, so a gate run under the system `python3` would
report every project dependency missing — or, worse, report a clean bill for an
environment nothing runs. So it first checks that `django` itself is installed:
if it is not, this is not the project's interpreter and the gate says so and
FAILS, naming what to run instead. A check that cannot tell pass from fail is
worse than no check, because it is trusted.

    python3 10-scripts/gates/g87_declared_dependencies.py     -> refuses
    /path/to/venv/bin/python 10-scripts/gates/g87_...py       -> checks

⚠ **THE SENTINEL IS THE PROJECT'S OWN DISTRIBUTION, NOT `django`, AND THE FIRST
DRAFT GOT THAT WRONG.** `django` is installed system-wide on this machine, so
the first version sailed past its own guard under `python3` and printed
THIRTEEN failures about an environment nobody runs. That is a false-alarm
avalanche, and a gate that cries wolf is a gate people stop reading — the same
failure `G85`'s excluded `state` column is written against. `smartbillhub`
itself can only be installed where somebody ran `pip install -e 06-backend`,
and its name is read from pyproject rather than typed in, so a rename cannot
leave the guard pointing at nothing.

WHAT WAS PROVED RED FIRST (hard-won law 7)
-------------------------------------------
Two ways, both reverted:

  1. run under the system interpreter —
     `G87 FAIL: this is not the project's interpreter (django is not installed
      here) …`
  2. a fabricated requirement (`"a-package-nobody-has>=1"`) added to the
     `dependencies` list in a temp copy —
     `G87 FAIL: a-package-nobody-has is declared in [project] dependencies and
      is NOT installed …`

And it was run against the real tree with `segno` deliberately uninstalled,
which is the defect it was written for, and named it.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import tomllib
from importlib import metadata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "06-backend" / "pyproject.toml"

#: A requirement string reduced to its distribution name. `psycopg[binary]>=3.1`
#: -> `psycopg`; `celery[redis]>=5.4` -> `celery`; `django>=5.0,<6` -> `django`.
#: Environment markers (`; python_version < "3.12"`) are cut first, because a
#: dependency that does not apply to this interpreter is not missing.
_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def distribution_of(requirement: str) -> str | None:
    head = requirement.split(";", 1)[0]
    match = _NAME.match(head)
    return match.group(1) if match else None


def declared(pyproject_text: str) -> list[tuple[str, str]]:
    """`(group, distribution)` for every declared requirement, in file order."""
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    out: list[tuple[str, str]] = []
    for req in project.get("dependencies", []) or []:
        name = distribution_of(req)
        if name:
            out.append(("[project] dependencies", name))
    for group, reqs in (project.get("optional-dependencies", {}) or {}).items():
        for req in reqs or []:
            name = distribution_of(req)
            if name:
                out.append((f"[project.optional-dependencies] {group}", name))
    return out


def _installed_in(python: str, project_name: str) -> set[str] | None:
    """Every distribution name `python` has installed (normalised the way
    `importlib.metadata` matches them), or None if it could not be asked.

    One subprocess for the whole list — the in-process `missing()` asks per
    name, which across an interpreter boundary would be one process per
    dependency.
    """
    import subprocess

    probe = (
        "import json; from importlib import metadata as m; "
        "print(json.dumps(sorted({d.metadata['Name'] or '' for d in m.distributions()})))"
    )
    try:
        done = subprocess.run([python, "-c", probe], capture_output=True, text=True,
                              check=False, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        names = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return _NormalisedNames(names)


class _NormalisedNames(set):
    """Distribution names compared the PEP 503 way (`-`, `_`, `.` and case
    are not significant), which is how `metadata.distribution()` matches."""

    @staticmethod
    def norm(name: object) -> str:
        return re.sub(r"[-_.]+", "-", str(name)).lower()

    def __init__(self, names=()):
        super().__init__(self.norm(n) for n in names)

    def __contains__(self, name: object) -> bool:
        return set.__contains__(self, self.norm(name))


def missing(pairs: list[tuple[str, str]], *, installed=None) -> list[tuple[str, str]]:
    """The pairs whose distribution this interpreter does not have."""
    if installed is None:
        def installed(name: str) -> bool:  # noqa: E306 — the real check
            try:
                metadata.distribution(name)
                return True
            except metadata.PackageNotFoundError:
                return False
    return [(group, name) for group, name in pairs if not installed(name)]


def run() -> tuple[str, str]:
    """The suite's entry point — see G85's `run` for why this was missing.

    ⚠ **THE WRONG-INTERPRETER CASE IS A `SKIP` HERE AND A `FAIL` STANDALONE**,
    and the difference is deliberate. Run by hand, being in the wrong
    environment is the user's mistake and should stop them. Run inside the
    suite, `run_gates` may legitimately be invoked with an interpreter that has
    no project install, and reporting FAIL there would put a red gate in front
    of every lane for a condition none of them caused. A SKIP says *I could not
    look*, which is the truth, and never says *everything is fine*.
    """
    if not PYPROJECT.exists():
        return "SKIP", f"{PYPROJECT.relative_to(REPO)} is not present"
    project_name = (
        tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get("project", {}).get("name")
        or "smartbillhub"
    )
    # ⚠ **WHICH INTERPRETER IS ASKED, NOT ASSUMED (`DEF-GOV-7813`).** This
    # used to answer only about `sys.executable` — the interpreter running
    # `run_gates`, bare `python3` here — and SKIPPED on every run while
    # `SBH_GATE_PYTHON` named the venv that runs the tests and G4/G5 used it.
    # So: the running interpreter if it carries the project, otherwise the
    # first one `common.interpreter_with("django")` finds, asked in ONE
    # subprocess which of the declared distributions it has.
    python = sys.executable
    installed = None
    try:
        metadata.distribution(project_name)
    except metadata.PackageNotFoundError:
        other, tried = common.interpreter_with("django")
        present = _installed_in(other, project_name) if other else None
        if present is None or project_name not in present:
            return "SKIP", (
                f"not the project's interpreter ({project_name} is not installed in "
                f"{sys.executable}, nor in any interpreter common.interpreter_with() "
                f"found — tried: {', '.join(tried)}), so nothing here could be checked "
                f"— set SBH_GATE_PYTHON to the interpreter that runs the tests"
            )
        python = other
        installed = present.__contains__
    # The self-test prints its own three lines; inside the suite that is noise
    # between other gates' verdicts, so it is captured. Its VERDICT still
    # decides — a gate whose own proof does not hold reports FAIL (DEF-182).
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        proof = selftest()
    if proof != 0:
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a missing "
            "dependency from a present one, so its verdict is worthless (DEF-182)"
        )
    pairs = declared(PYPROJECT.read_text(encoding="utf-8"))
    gaps = missing(pairs, installed=installed)
    if gaps:
        return "FAIL", (
            f"{len(gaps)} declared dependenc(ies) not installed in {python}: "
            + ", ".join(f"{name} ({group})" for group, name in gaps[:5])
            + (f" (+{len(gaps) - 5} more)" if len(gaps) > 5 else "")
            + " — nothing installs from pyproject any more; run `pip install -e 06-backend`"
        )
    groups = len({group for group, _ in pairs})
    return "PASS", (
        f"{len(pairs)} declared dependencies across {groups} group(s), all installed in {python}; "
        f"self-test: a fabricated requirement and DEF-CWP-3656's own shape both bite"
    )


def main() -> int:
    if not PYPROJECT.exists():
        print(f"G87 FAIL: {PYPROJECT.relative_to(REPO)} is missing — nothing to check")
        return 1

    # Law 3 / DEF-524: refuse the wrong interpreter rather than reporting a
    # clean bill for an environment nothing runs.
    #
    # ⚠ THE SENTINEL IS THE PROJECT ITSELF, NOT `django`, AND THE FIRST DRAFT
    # GOT THIS WRONG. `django` is installed system-wide on this machine, so a
    # run under the system interpreter sailed past that guard and printed
    # THIRTEEN failures about an environment nobody runs — a false-alarm
    # avalanche, which is how a gate stops being read. The project's own
    # distribution can only be present where somebody ran
    # `pip install -e 06-backend`, which is exactly the question being asked.
    # Its NAME is read from pyproject rather than typed here, so a rename
    # cannot leave this guard pointing at a package that no longer exists
    # (hard-won law 1).
    project_name = tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get(
        "project", {}
    ).get("name")
    try:
        metadata.distribution(project_name or "smartbillhub")
    except metadata.PackageNotFoundError:
        print(
            f"G87 FAIL: this is not the project's interpreter — {project_name} "
            f"itself is not installed here, so every answer this gate could "
            f"give would be about the wrong environment. Run it with the "
            f"interpreter that runs the tests:\n"
            f"    <your venv>/bin/python {pathlib.Path(__file__).relative_to(REPO)}\n"
            "  If you have no venv for this project yet: "
            "python -m venv .venv && .venv/bin/pip install -e 06-backend"
        )
        return 1

    pairs = declared(PYPROJECT.read_text(encoding="utf-8"))
    gaps = missing(pairs)
    for group, name in gaps:
        print(
            f"G87 FAIL: {name} is declared in {group} and is NOT installed in "
            f"{sys.executable}. Nothing installs from pyproject any more — the "
            f"workflow that did was disabled on 2026-09-04 — so this is a "
            f"`pip install -e 06-backend` somebody has to run. Left alone it "
            f"surfaces as an ImportError inside whichever module happens to "
            f"import it, naming the wrong feature (DEF-CWP-3656)."
        )
    if gaps:
        return 1
    groups = len({group for group, _ in pairs})
    print(
        f"G87 PASS: {len(pairs)} declared dependencies across {groups} group(s), "
        f"all installed in {sys.executable}"
    )
    return 0


def selftest() -> int:
    """Break it on purpose, in memory — never on the real pyproject."""
    failed = 0
    real = PYPROJECT.read_text(encoding="utf-8")

    sabotaged = real.replace(
        'dependencies = [\n  "django>=5.0,<6",',
        'dependencies = [\n  "a-package-nobody-has>=1",\n  "django>=5.0,<6",',
        1,
    )
    if sabotaged == real:
        print("selftest RED-PROOF FAILED: could not sabotage the dependency list")
        return 1
    gaps = missing(declared(sabotaged))
    if not any(name == "a-package-nobody-has" for _, name in gaps):
        print("selftest RED-PROOF FAILED: a fabricated dependency was not caught")
        failed = 1
    else:
        print("selftest ok — a fabricated dependency is caught by name")

    # And the shape DEF-CWP-3656 actually took: a real, declared package that
    # simply is not there. Driven through the injected `installed` predicate so
    # the proof does not depend on uninstalling anything.
    pairs = declared(real)
    gaps = missing(pairs, installed=lambda name: name != "segno")
    if not any(name == "segno" for _, name in gaps):
        print("selftest RED-PROOF FAILED: the DEF-CWP-3656 shape was not caught")
        failed = 1
    else:
        print("selftest ok — DEF-CWP-3656's own shape (segno declared, absent) is caught")

    # The extras/specifier reduction, because a wrong answer here is a false
    # alarm on every commit and that is how a gate stops being read.
    for req, want in [
        ("psycopg[binary]>=3.1", "psycopg"),
        ("celery[redis]>=5.4", "celery"),
        ("django>=5.0,<6", "django"),
        ('tzdata>=2024.1; sys_platform == "win32"', "tzdata"),
    ]:
        got = distribution_of(req)
        if got != want:
            print(f"selftest FAILED: {req!r} reduced to {got!r}, wanted {want!r}")
            failed = 1
    if not failed:
        print("selftest ok — extras, specifiers and markers all reduce correctly")
    return failed


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
