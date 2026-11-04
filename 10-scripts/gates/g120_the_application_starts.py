#!/usr/bin/env python3
"""G120 — `django.setup()` must succeed, and every runbook must construct.

THE OUTAGE, IN THE PRODUCT OWNER'S OWN PASTE
--------------------------------------------
On 2026-09-07 a deployed build would not start. The whole of it:

    File "/app/apps/runbooks/definitions/month_end.py", line 1236, in <module>
      Parameter(
    File "/app/apps/runbooks/contract.py", line 422, in _check_domain
      raise RunbookContractError(
    RunbookContractError: parameter 'period' defaults to 'all' and accepts one
    value. 'all' is a RULE rather than a value (BR-RBS-042 clause 1) and it is
    only meaningful where several values are.
    entrypoint: settings=config.settings.production

**The refusal was right.** Wave `T` had just landed `Parameter._check_domain`
and `month_end.py` genuinely violated it. What was wrong is WHEN it was found:
the check runs at CONSTRUCTION, in a module body, which `AppConfig.ready()`
imports — so it does not fail a feature, it fails **`django.setup()`**, and an
application that cannot call `setup()` cannot run a management command, a
migration, a test, `runserver`, or serve one request.

WHY NOTHING CAUGHT IT, WHICH IS THE WHOLE REASON THIS GATE EXISTS
-----------------------------------------------------------------
⚠ **IT WAS NOT INVISIBLE — IT WAS UNNAMED, AND THOSE FAIL DIFFERENTLY.** When
`setup()` dies, EVERYTHING dies with it: every pytest file errors during
collection, and every gate that touches Django crashes. So the signal is not a
red line saying *the app will not start*; it is **thirty red lines about thirty
unrelated things**, which is indistinguishable from a broken environment — and
this repo has taught its lanes, correctly, that a shared tree with many lanes in
it produces exactly that noise. Hard-won law 7's *a true red acquires the
protective colouring of a known one*, at the scale of the whole suite.

Two gates already call `django.setup()` — `G24` and `G49` — and both do it for
their own purpose. When `setup()` fails they fail, truthfully, with a message
about holiday horizons or identifier series. **Neither says the thing a reader
needs to know**, and a check's output must distinguish pass from fail *to a
reader*, not merely to an exit code (`DEF-182`).

⚠ **AND THE SECOND HALF IS THE ONE A LANE WILL SKIP.** `setup()` succeeding is
not the same as every runbook constructing: a definition module that no
`AppConfig` imports at boot can still be broken and will still take out the
first request that touches the registry. So this walks the registry too, and
**prints how many runbooks it constructed**, because a boot check that silently
covered three of twenty-four would be law 7's *reporting zero over a scope it
silently excludes*.

WHAT WOULD MAKE THIS PASS WRONGLY
---------------------------------
  * **Running in the gate runner's own process.** `setup()` is global and
    idempotent — a second call is a no-op — so if any earlier gate has already
    booted Django, calling it here proves nothing about a cold start. It runs in
    a SUBPROCESS, which is `G49`'s own documented reasoning for the same problem.
  * **A settings module that imports less than production does.** It boots
    `config.settings.test`, and that is a KNOWN, STATED narrowing rather than a
    silent one: the failure above reached a `production` entrypoint. The import
    graph that broke is `INSTALLED_APPS` → `AppConfig.ready()`, which both
    settings share; what test settings do NOT exercise is production-only
    middleware and storage. Said here so nobody reads a green as a promise about
    the deployed configuration.
  * **A registry that is empty.** Zero runbooks would construct without error,
    truthfully and uselessly, so a floor is asserted and the count is printed.
  * **Touching a database.** It does not. `setup()` and module construction read
    declarations; a gate that needed PostgreSQL would SKIP on the machines that
    matter and be trusted anyway.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BACKEND = common.REPO_ROOT / "06-backend"

#: The registry held 24 on the day this was written. A floor rather than the
#: exact number: this gate must not go red every time a wave adds a runbook,
#: which is how a guard earns a `# noqa`. It exists to catch a COLLAPSE.
MINIMUM_RUNBOOKS = 8

PROBE = """
import json, sys
import django
django.setup()
out = {"setup": True}
try:
    from apps.runbooks.registry import registry
    definitions = list(registry.all())
    out["runbooks"] = len(definitions)
    # Constructing is what `Parameter.__post_init__` runs, and it is what broke.
    # Touch every parameter so a definition that constructs lazily is still read.
    out["parameters"] = sum(len(getattr(d, "parameters", ())) for d in definitions)
except Exception as exc:  # noqa: BLE001 — the message is the deliverable
    out["registry_error"] = f"{type(exc).__name__}: {exc}"
print(json.dumps(out))
"""


def interpreter() -> tuple[str | None, list[str]]:
    """The first interpreter on this machine that can import Django.

    ⚠ **`sys.executable` IS THE WRONG ANSWER HERE AND IT COST THIS GATE ITS
    FIRST RUN.** On this machine bare `python3` has no Django and `python3.12`
    does, so the first draft reported **THE APPLICATION WILL NOT START:
    ModuleNotFoundError: No module named 'django'** — over a branch that boots
    perfectly. A guard that cries wolf is worse than no guard, because the next
    reader learns to skip its line; `10-scripts/11-smoke-stack.sh` already
    resolves the interpreter this way and PRINTS its choice, for exactly this
    reason.

    Returns the interpreter and the list of what was tried, so a SKIP can say
    what it looked for rather than shrugging.
    """
    # ⚠ **THIS IS ONE LINE NOW, AND THAT IS THE FIX — `DEF-GOV-7813`'s
    # "remaining half".** What stood here was this gate's own literal copy of the
    # candidate list (`<checkout>/06-backend/.venv`, `sys.executable`, `python3`,
    # `python3.14`..`python3.10`). `common.interpreter_with()` was widened on
    # 2026-09-29 to honour `SBH_GATE_PYTHON`/`PYTHON` and to look in
    # `~/.venvs`, `/root/.venvs`, `/opt/venvs` and the MAIN worktree's venv;
    # `g05_isolation.py` was folded onto it the same day and this copy was not.
    # Measured 2026-10-02 under `SBH_GATE_PYTHON=/tmp/venv_a5c/bin/python`:
    # G4 and G5 used that interpreter and this gate SKIPPED beside them —
    # *"Tried: /usr/local/bin/python3, python3, python3.14 … python3.10"* — the
    # override it was told about never entered its list. One list; widening it
    # fixes every gate that asks.
    return common.interpreter_with("django")


def boot(python: str) -> tuple[bool, str, dict]:
    """Cold-boot Django in a subprocess. Returns (ok, detail, facts)."""
    if not BACKEND.is_dir():
        return False, "no 06-backend directory in this checkout", {}
    done = subprocess.run(
        [python, "-c", PROBE],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
            "PYTHONPATH": str(BACKEND),
        },
        timeout=300,
        check=False,
    )
    if done.returncode != 0:
        # The LAST line of a traceback is the exception; that is what a reader
        # needs first. The rest is kept behind it rather than thrown away.
        tail = [line for line in done.stderr.strip().splitlines() if line.strip()]
        return False, tail[-1] if tail else "no output", {}
    try:
        import json

        return True, "", json.loads(done.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        return False, f"the probe printed something unreadable ({exc})", {}


def run() -> tuple[str, str]:
    python, tried = interpreter()
    if python is None:
        # ⚠ SKIP, NOT FAIL. "This machine has no Django" is an environment fact,
        # not a fault in the branch, and a gate that reports the two the same way
        # teaches its reader to ignore both.
        return "SKIP", (
            "no interpreter on this machine can import Django, so a cold boot "
            f"cannot be attempted. Tried: {', '.join(tried)}."
        )

    ok, detail, facts = boot(python)
    if not ok:
        return "FAIL", (
            f"THE APPLICATION WILL NOT START: {detail}. This is not one failing "
            "feature — `django.setup()` is what every management command, every "
            "migration, every test and every request begins with, so a deployed "
            "build dies at its entrypoint. It reached a production entrypoint "
            "once (2026-09-07, a runbook parameter refused at construction) and "
            "the symptom was thirty unrelated red lines, which reads as a broken "
            "environment rather than as this."
        )

    if "registry_error" in facts:
        return "FAIL", (
            f"Django starts, but the runbook registry does not build: "
            f"{facts['registry_error']}. A definition module that no AppConfig "
            "imports at boot still takes out the first request that touches the "
            "registry, so this is a deferred version of the same outage."
        )

    count = int(facts.get("runbooks", 0))
    if count < MINIMUM_RUNBOOKS:
        return "FAIL", (
            f"only {count} runbook(s) constructed, against a floor of "
            f"{MINIMUM_RUNBOOKS}. A boot check over an almost-empty registry "
            "passes truthfully and proves nothing — the floor is what stops a "
            "collapse reading as a pass."
        )

    return "PASS", (
        f"django.setup() succeeds from cold in a {python} subprocess, and {count} runbook(s) "
        f"with {facts.get('parameters', 0)} parameter(s) construct. ⚠ Booted under "
        "config.settings.test, which shares INSTALLED_APPS and AppConfig.ready() "
        "with production and does NOT exercise production-only middleware or "
        "storage — a green here is a promise about the import graph, not about "
        "the deployed configuration."
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
