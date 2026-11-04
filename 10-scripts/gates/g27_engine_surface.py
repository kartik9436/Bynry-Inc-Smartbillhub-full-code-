"""G27 — a module's ENGINE lines against its MOUNTED SURFACE. Zero fails.

Added 2026-08-16 by the DEF-128 lane, and that defect's prevention column is
this file's specification, verbatim:

    "a check that counts a module's ENGINE lines against its SURFACE lines and
     fails when a module with thousands of lines of tested logic serves no
     route. **ZERO is the number to fail on**, because a module at zero is
     invisible to every completeness measure the repo currently computes."

WHAT HAPPENED, FOUR TIMES
─────────────────────────
`apps/notifications` measured **7,084 lines** — `dispatcher.py` 877,
`services.py` 897, `template_service.py` 796, `notices.py` 701,
`delivery_ops.py` 635, `rendering.py` 568 and more — behind an `api.py` of
**72 BYTES**: one docstring line, no `urlpatterns`, and no `include()` naming it
in `config/urls.py`. Nothing a customer is ever sent could be triggered, listed
or audited through the product. Billing's `api.py` is 56,528 bytes and payments'
is 37,906, so the shape was visible in a directory listing and nothing looked.

It was the FOURTH occurrence at whole-module scale in one release. `config/urls.py`
records the other three in its own comments: billing (S30's list and detail and
the S21 Bills tab all rendering 404), payments (the write path complete and
tested, and no human able to record a payment), ledger (1,500 lines of finance
read model behind five screens, the trial balance answering 404).

WHY NO EXISTING GATE CAUGHT IT — AND WHY THIS IS NOT G23 AGAIN
──────────────────────────────────────────────────────────────
DEF-128's escape column is precise: G23 (surface-debt) counts a module's
UNREACHABLE STORIES from the D/E marks in Lifecycle trailers, and DEF-080's
proposed durable gate would compare a module's exported urlpatterns against its
CONTRACTED routes. **Both need the module to have started.** An `api.py` that
exports no `urlpatterns` at all offers nothing to compare, and a module whose
lanes each honestly wrote `D=deferred(no-API-half)` is *declared* rather than
caught — G23 will happily pass a module at 12 declared-unreachable stories
forever, because the declaration is the pass condition.

This gate asks a different question, and it is the one nobody was asking:
**does this pile of code have a door at all?** It does not care what the
contract says, what the trailers declare, or which stories exist. It measures
two integers per module and compares them.

WHAT IS MEASURED
────────────────
ENGINE   non-blank lines of Python under `06-backend/apps/<mod>/`, excluding
         migrations (generated), `tests.py` (scaffolding) and the surface files
         themselves. This is the "tested logic" half of the defect's sentence.

SURFACE  route entries — `path(...)` / `re_path(...)` — in the module's route
         files, counted ONLY IF `config/urls.py` actually reaches them.

That second clause is the whole gate. An `api.py` full of `urlpatterns` that no
URLconf includes is EXACTLY the payments defect: the file existed, the routes
were written, the tests passed, and every request 404ed. So the include graph is
walked from `config/urls.py` outward and a route nobody mounted counts zero —
the same number as a route nobody wrote, because to a user they are the same
thing.

THE FLOOR, AND WHY IT IS NOT A DIAL
───────────────────────────────────
A module with 9 lines in it has not started; failing it would teach a lane to
add a fake route rather than to write the module. So a module is only asked the
question once it holds `ENGINE_FLOOR` lines. It is 200 — far below the 7,084
this gate was written for and far above `apps/integrations`' 9, the only
route-less module in the tree the day this landed. It is a floor on ASKING, not
a budget: at 201 lines the answer must still be a positive number of routes.

There is deliberately NO exemption file. G16's `partition_exceptions.txt` and
G20's `seam_known_gaps.txt` each exist because a real, named condition
legitimately blocks a real fix; nothing here is in that position, and shipping
an empty park list would be dead machinery inviting the first tired lane to use
it (hard-won law 2, from the other side). A module that genuinely serves no HTTP
— a pure worker, say — is a product decision and belongs in a PO ruling in
12-governance/02-decision-log.md, not in a text file no one reads.

Proven RED before trusted green (hard-won law 7): the self-test below replays
DEF-128's own measurements — 7,084 engine lines, an `api.py` with no
`urlpatterns`, no include — through the same comparison the gate runs, and the
gate was additionally run against the live tree BEFORE a single notification
route was mounted. That transcript is quoted in the lane report and in
12-governance/02-decision-log.md.

⚠ G27 is an Eng-Lead-class addition and is merge-blocking from the moment it is
wired, so it is REPORTED for the daily PO batch and recorded in
12-governance/02-decision-log.md rather than treated as routine (the G17–G26
route).

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import re
from pathlib import Path

import common

#: Where the include graph starts. Every route in this product is reachable
#: from here or is not reachable at all.
ROOT_URLCONF = common.BACKEND_DIR / "config" / "urls.py"

#: A module is asked the question once it holds this many non-blank engine
#: lines. See the docstring: a floor on ASKING, never a budget.
ENGINE_FLOOR = 200

#: `path("payments", …)` / `re_path(r"^api/…", …)` — one route entry.
ROUTE_RE = re.compile(r"\b(?:re_)?path\s*\(")

#: `include("apps.billing.api")` — the only form this repo uses, and the only
#: form that can be read statically. An include built from a variable would be
#: invisible here, so the gate reports what it walked and a reviewer can see
#: the graph it believed.
INCLUDE_RE = re.compile(r"include\(\s*[\"']([\w.]+)[\"']")

#: Files that hold routes rather than logic. Anything matching is SURFACE and is
#: excluded from the engine count, so a big `api.py` never flatters the ratio.
SURFACE_SUFFIXES = ("api.py", "urls.py")

#: Excluded from the engine count: generated, or scaffolding.
ENGINE_SKIP_DIRS = ("migrations", "__pycache__")
ENGINE_SKIP_NAMES = ("tests.py", "__init__.py")


def is_surface_file(path: Path) -> bool:
    return path.name.endswith(SURFACE_SUFFIXES)


def engine_lines(module_dir: Path) -> int:
    """Non-blank Python lines of LOGIC in one module.

    Comments are counted deliberately. This repo's docstrings carry the reasons
    a rule is built the way it is (CLAUDE.md law 10) and a lane that stripped
    them to duck a gate would be destroying the thing the repo is for. The
    number is a size signal, not a quality score.
    """
    total = 0
    for path in sorted(module_dir.rglob("*.py")):
        if any(part in ENGINE_SKIP_DIRS for part in path.parts):
            continue
        if path.name in ENGINE_SKIP_NAMES or is_surface_file(path):
            continue
        total += sum(1 for line in common.read_text(path).splitlines() if line.strip())
    return total


def mounted_modules(root: Path) -> set[str]:
    """Every dotted module `config/urls.py` reaches, transitively.

    Walked rather than assumed: `config/urls.py` includes `apps.identity.urls`,
    which is a urls.py holding eleven paths of its own, and a gate that only
    read the root file would call identity route-less.
    """
    if not root.is_file():
        return set()
    seen: set[str] = set()
    frontier = list(INCLUDE_RE.findall(common.read_text(root)))
    while frontier:
        dotted = frontier.pop()
        if dotted in seen:
            continue
        seen.add(dotted)
        path = common.BACKEND_DIR / Path(*dotted.split(".")).with_suffix(".py")
        if path.is_file():
            frontier.extend(INCLUDE_RE.findall(common.read_text(path)))
    return seen


def route_count(path: Path) -> int:
    """Route entries in one file, comment lines excluded.

    The exclusion is load-bearing rather than tidy: `config/urls.py` explains
    three previous occurrences of this defect in prose that quotes `path(` in
    its own comments, and counting those would let a module pass on an apology
    for the last time it failed.
    """
    return sum(
        len(ROUTE_RE.findall(line))
        for line in common.read_text(path).splitlines()
        if not line.lstrip().startswith("#")
    )


def _dotted(path: Path) -> str:
    """`06-backend/apps/billing/api.py` → `apps.billing.api`, the include name."""
    return ".".join(path.relative_to(common.BACKEND_DIR).with_suffix("").parts)


def measure() -> dict[str, dict[str, object]]:
    """{module: {engine, routes, surface_files, mounted_files}} for every app."""
    mounted = mounted_modules(ROOT_URLCONF)
    found: dict[str, dict[str, object]] = {}
    if not common.BACKEND_APPS.is_dir():
        return found
    for module_dir in sorted(common.BACKEND_APPS.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("__"):
            continue
        surface = [p for p in sorted(module_dir.rglob("*.py")) if is_surface_file(p)]
        # A file counts only if the walked include graph NAMES it. That covers
        # both forms this repo uses: `include("apps.billing.api")` straight from
        # the root, and `include("apps.identity.urls")` — a urls.py of its own
        # holding eleven paths — which the walk reaches at depth one.
        live = [p for p in surface if _dotted(p) in mounted]
        found[module_dir.name] = {
            "engine": engine_lines(module_dir),
            "routes": sum(route_count(p) for p in live),
            "surface_files": [common.rel(p) for p in surface],
            "mounted_files": [common.rel(p) for p in live],
        }
    return found


def invisible(measured: dict[str, dict[str, object]]) -> list[str]:
    """Modules over the floor whose mounted route count is ZERO."""
    return [
        module
        for module, entry in sorted(measured.items())
        if int(entry["engine"]) >= ENGINE_FLOOR and int(entry["routes"]) == 0
    ]


def self_test() -> list[str]:
    """Hard-won law 7 — the gate is shown to BITE on DEF-128 itself.

    The numbers below are the defect row's own measurements. A guard that
    cannot be demonstrated failing on the defect it was written for is not a
    guard, and this one is additionally red-proved against the live tree before
    any route was mounted (see the module docstring).
    """
    blind: list[str] = []

    def_128 = {
        # 7,084 lines of engine, an api.py that is a single docstring line, and
        # no include naming it. Routes: zero.
        "notifications": {"engine": 7084, "routes": 0, "surface_files": [], "mounted_files": []},
    }
    if invisible(def_128) != ["notifications"]:
        blind.append(
            "the DEF-128 shape (7,084 engine lines, zero mounted routes) is NOT counted "
            "as invisible — the gate would have passed the defect it was written for"
        )

    # The payments shape, which is the same defect one module along: the routes
    # were WRITTEN and no URLconf included them. An unmounted route is a 404 to
    # a user, so it must count as zero here too.
    unmounted = {
        "payments": {
            "engine": 16375,
            "routes": 0,  # api.py exports eight, config/urls.py names none
            "surface_files": ["06-backend/apps/payments/api.py"],
            "mounted_files": [],
        },
    }
    if invisible(unmounted) != ["payments"]:
        blind.append(
            "a module whose api.py exports routes that NO URLconf includes is not counted "
            "as invisible — that is DEF-128's own escape route and the payments defect"
        )

    served = {
        "billing": {"engine": 27371, "routes": 10, "surface_files": [], "mounted_files": []},
    }
    if invisible(served):
        blind.append("a module WITH mounted routes is being counted as invisible")

    # A module that has not started must not be dragged in — see the floor.
    unstarted = {
        "integrations": {"engine": 9, "routes": 0, "surface_files": [], "mounted_files": []},
    }
    if invisible(unstarted):
        blind.append(
            "a module below the engine floor is being failed; the floor exists so a lane "
            "writes the module rather than a fake route"
        )
    return blind


def run() -> tuple[str, str]:
    measured = measure()
    if not measured:
        return "SKIP", "no 06-backend/apps modules yet — activates with the first one"
    if not ROOT_URLCONF.is_file():
        return "FAIL", f"{common.rel(ROOT_URLCONF)} is missing — nothing can be mounted from it"

    blind = self_test()
    if blind:
        return "FAIL", (
            f"self-test BLIND: {blind[0]}. A guard that cannot be shown to bite is not a "
            f"guard (hard-won law 7) — {len(blind)} shape(s) failed."
        )

    problems = []
    for module in invisible(measured):
        entry = measured[module]
        surface = entry["surface_files"] or ["(no api.py / urls.py at all)"]
        problems.append(
            f"{module}: {entry['engine']} lines of engine and ZERO mounted routes "
            f"(surface file(s): {', '.join(str(s) for s in surface)}). An entire module is "
            f"invisible — nothing it does can be triggered, listed or audited through the "
            f"product (DEF-128, hard-won law 2 at module scale). Contract its routes and "
            f"include them from 06-backend/config/urls.py; an api.py no URLconf names is a "
            f"404 to every user."
        )
    if problems:
        return "FAIL", common.summarize(problems, 2)

    asked = [m for m, e in measured.items() if int(e["engine"]) >= ENGINE_FLOOR]
    ratio = ", ".join(
        f"{m} {measured[m]['engine']}/{measured[m]['routes']}" for m in sorted(asked)[:3]
    )
    return "PASS", (
        f"{len(asked)} module(s) over the {ENGINE_FLOOR}-line floor, every one serving "
        f"mounted routes (engine/routes: {ratio}, …)"
    )


if __name__ == "__main__":  # pragma: no cover - the runner is run_gates.py
    status, detail = run()
    print(f"G27 engine-surface {status} {detail}")
    # Exits non-zero on FAIL so this file can be run on its own as a red-proof
    # and the transcript shows the verdict rather than only the sentence.
    raise SystemExit(1 if status == "FAIL" else 0)
