#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1793 — the "built is not wired" gate family has four members and
#           all four pass while twelve open `high` defects say otherwise. G13
#           (a prop nothing passes), G40 (a component nothing mounts) and G45
#           (a config key nothing reads) scan 07-frontend only. G27 is backend
#           but WHOLE-MODULE and fails only at zero routes, by its own quoted
#           specification: "ZERO is the number to fail on". So a module serving
#           32 routes hides an unrouted seventh action perfectly.
# Also:     DEF-478 — "six more discount write services reach no route", filed
#           against apps/rating, which G27 scores healthy at 32 routes.
#           DEF-135 — "thirteen ruled rules have no door", open since
#           2026-08-15 while four sibling gates were built around it.
# Rules:    CLAUDE.md hard-won law 2 — "Built is not wired. A component with an
#           optional prop that nothing passes is dead UI: it renders nothing,
#           every test passes, and the feature does not exist."
# Ruling:   decision log 2026-08-27 "THE THREE BOUNDARY GATES, AND WHY THERE IS
#           NO FOURTH" — the question is genuinely uncovered; build it once the
#           scope is honest. PO ruling 2026-08-28 ("Please add 3 files") closed
#           the hole that lane refused to ship over.
# ───────────────────────────────────────────────────────
"""G52 — a ROLE-GATED ACTION with no door. The named set is the baseline.

WHAT A PERSON CAN NOW FIND OUT
------------------------------
Whether an action the code itself says *a person holding role X performs* can be
reached by a person at all. Nothing in this repo could answer that before.

`G27` asks the same question one size too big: **does this pile of code have a
door at all**, failing only at zero routes. `apps/rating` serves 32 routes, so
G27 calls it healthy, and `DEF-478`'s six unroutable discount write services sit
inside it invisibly. This gate asks the question one size smaller — **does THIS
action have a door** — which is the size the open defects are actually written
at.

THE UNIVERSE, AND WHY IT IS `@require_role` AND NOT "EVERY FUNCTION"
--------------------------------------------------------------------
The previous lane measured the naive version and recorded why it fails: an
unscoped sweep of "modules nothing imports" gives **69 candidates dominated by
Django conventions** — `apps.py`, `models.py`, management commands discovered by
name, `*_api.py` mounted by string. Noise. Scoping to the 🔒 sensitive-path set
took 69 → 6, *"all explainable, zero real offenders"*, but that scope answers a
FILE-shaped question and `DEF-478` is a FUNCTION-shaped defect: its six services
live in `discount_services.py`, a file that IS imported, IS mounted, and serves
routes for its other functions.

`@require_role` is the scope that fits, and it fits for one reason: **it is a
declaration, not a convention.** No framework requires it and no generator emits
it. A lane writes `@require_role(SYSTEM_ADMIN)` on a function to say *a human
with this role performs this action*. If nothing a human can reach calls it, the
declaration is false — and that is a finding, never a Django artefact. It is
also the exact probe `DEF-478` was found by, in its own words: *"a probe over
every @require_role write function in apps/rating/discount_services.py against
every path() in apps/rating/api.py"*. This gate is that probe, generalised to
every module and taught to resolve imports.

Measured at the tip: **229 role-gated actions across 31 files in 10 modules.**
Of those, **200 are reachable and 29 are not**, the 29 falling in 7 files across
5 modules. Not one of the 229 is a convention.

THE DEFINITION OF "REACHABLE", AND IT IS `DEF-438`'s ON PURPOSE
----------------------------------------------------------------
`DEF-438` is being settled on **"a route a person can actually get to"**. This
gate uses that definition and no looser one, because two checks answering the
same question differently means one of them is wrong.

Concretely: the include graph is walked outward from `config/urls.py` exactly as
`G27` walks it; the modules it reaches are the ROOTS. From each root's top-level
statements — which is where `urlpatterns` lives — a call graph is followed
through function bodies, class bodies and imports, and an action is REACHABLE if
that walk arrives at it.

Deliberately NOT counted as a door, and each was checked against the tree:

  * **a management command.** `manage.py seed-whatever` is not a door a clerk
    can get to; it is an operator with a shell.
  * **a demo-data seeder.** `apps/customers/sample_data.py` calls
    `disconnects.schedule_cut`, which means the DEMO can schedule a cut. It does
    not mean a clerk can schedule one for a customer, which is the thing the
    screen is missing.
  * **a test.** Tests are excluded from the graph entirely.

THREE THINGS THE FIRST VERSION GOT WRONG, ALL FOUND BY CHECKING THE OUTPUT
---------------------------------------------------------------------------
Recorded because they are what separates this from a check that cannot tell pass
from fail (`DEF-182`, twice), and every one of them read as a confident finding:

1. **Class-based views.** The first run reported all seven of
   `apps/identity/services.py`'s user-admin actions — `add_user`,
   `deactivate_user`, `issue_temp_password` … — as having no door. They have
   doors: `apps/identity/urls.py` mounts `api.UsersView.as_view()`, and the
   seed only followed `path("x", some_function)`. Seven false positives out of
   twenty-nine. The walk now enters class bodies.
2. **String-keyed seam dispatch.** `apps/customers/discounts.py` reaches
   `discount_services.enrol_account` through
   `seams.resolve("rating", "enrol_account", kind="discount_services")` — a
   name that appears in the source only as a STRING. So a string constant
   occurring in reachable code counts as a reach. That is a deliberate
   over-approximation: it excuses `enrol_account` (correctly — a door was opened
   for it after `DEF-478` was filed) and it also excuses any action whose name
   happens to be an ordinary English word, such as `transfers.review`, which is
   a **false negative and the safe direction**. A gate that cries wolf is worse
   than one that misses.
3. **`__all__` is not dispatch.** With clause 2 in, `apps/payments/refunds.py`
   went quiet — because `payments/services.py` re-exports `"approve_refund"` and
   `"void_refund"` in an `__all__` list. An export declaration is not a call, so
   the elements of an `__all__` assignment are excluded from clause 2. Both
   refund actions are real findings: `grep` finds no refund route anywhere but
   `accounts/<id>/refund`, which reaches neither.

A NAMED REFUSAL IS REACHABLE, NOT A GAP
----------------------------------------
A body that is `raise NotImplementedError("OQ-###")` is the prime directive
working — a lane stopping at the boundary of an unruled question instead of
guessing. Counting it here would flag the repo's most disciplined code, so a
role-gated function whose body raises a named refusal is excluded from the
universe. None of today's 29 is one; the clause exists so the first lane to
write one is not punished for it.

WHAT THIS GATE DOES **NOT** COVER, SAID PLAINLY
------------------------------------------------
It sees only actions the code declares role-gated. **A service write with no
`@require_role` is invisible to it.** It also does not answer `DEF-438`: the
R1–R7 resolution chain carries no role decorators, and its shape — a whole
subsystem with no production caller — is a different mechanism at a different
scale. Claiming otherwise would make this the fifth check in this repo caught
describing its own output wrongly (`DEF-1788`, `DEF-1861`, `DEF-1862`,
`DEF-1863`).

THE BASELINE IS A NAMED SET OF 29, AND IT IS WHAT WAS ACTUALLY FOUND
----------------------------------------------------------------------
`g52_no_door_baseline.txt`. Decision log 2026-08-27, *"WHY SOME GATE FAMILIES
BREACH"*: a gate born at a hard zero with its offenders fixed stays green and
stays read; one given an aspirational number over an existing pile is never
green, so nobody reads it, and it drifts out of true. There are 1,838 lines of
built, tested, role-gated write behind no door here and no lane in flight is
fixing them, so a hard zero would put the suite on the floor for everyone over a
known defect — *"a gate that is red from birth earns a `# noqa` instead of a
fix"* (G44's own words).

**A named set beats a count**, and this is `G48`/`G49`'s ruling applied again: a
THIRTIETH action fails at its own name instead of hiding inside a number, and an
action that gains a door goes RED as STALE until its line is deleted, so the
list cannot outlive the defect (`DEF-490`).

RED PROOF (hard-won law 7) — every failure branch, run against the live tree
mutated one edit at a time and restored between runs. Verbatim:

    $ # 1. a NEW role-gated action with no door. The mutation deliberately used
    $ #    an ALIASED decorator — `require_role as _rr` — because the FIRST
    $ #    attempt at this proof passed: the universe was matched on decorator
    $ #    TEXT and the alias walked straight out of it. That silence is why
    $ #    `_is_role_gate` resolves the decorator through the module's imports.
    $ python3 10-scripts/gates/g52_role_gated_doors.py
    G52 FAIL — 1 role-gated action(s) reach no route and are not in the
    baseline: apps.billing.services:cancel_run (06-backend/apps/billing/
    services.py:225). Each declares @require_role — the code's own statement
    that a person performs it — and no route a person can get to calls it.

    $ # 2. a baseline line that GAINED a door — a view calling
    $ #    `refunds.void_refund` appended to apps/payments/api.py's urlpatterns
    $ python3 10-scripts/gates/g52_role_gated_doors.py
    G52 FAIL — 1 baseline line(s) are STALE and must be deleted:
    apps.payments.refunds:void_refund now reaches a route

    $ # 3. a baseline line whose action is gone — `issue_refund` added to the
    $ #    baseline, an action that exists but carries no role gate
    $ python3 10-scripts/gates/g52_role_gated_doors.py
    G52 FAIL — 1 baseline line(s) are STALE and must be deleted:
    apps.payments.refunds:issue_refund no longer exists (renamed, deleted or
    ungated)

    $ # 4. restored
    $ python3 10-scripts/gates/g52_role_gated_doors.py
    G52 PASS — 229 role-gated action(s) declared across 31 backend file(s); 200
    reach a route a person can get to; 29 in 7 file(s) do not, and every one is
    named in g52_no_door_baseline.txt (DEF-135 / DEF-478 shape); self-test: 9/9
    clauses bite

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import ast
import re
import sys
from pathlib import Path

import common

#: Where the include graph starts — the same root `G27` walks.
ROOT_URLCONF = "config.urls"

#: `include("apps.billing.api")` — the only form this repo uses and the only
#: form readable statically. G27's regex, deliberately identical: two gates
#: disagreeing about which routes are mounted would be worse than either.
INCLUDE_RE = re.compile(r"include\(\s*[\"']([\w.]+)[\"']")

#: The named set. One `module:function` per line; `#` comments and blanks are
#: ignored. See the docstring: a named set, never a count.
BASELINE = Path(__file__).resolve().parent / "g52_no_door_baseline.txt"

#: A named refusal — the prime directive working, not a gap.
REFUSAL_RE = re.compile(r"NotImplementedError\(\s*[\"'][^\"']*OQ-(?:[A-Z]{3}-)?\d+")


# ── the analyser ───────────────────────────────────────────────────────────
# `sources` is {dotted module name: source text}. Kept injectable so the
# self-test can prove every clause bites on a tree it builds itself; a hand
# proof expires the moment the code around it moves.


class _Mod:
    """One module's top-level definitions and its import aliases."""

    def __init__(self, name: str, tree: ast.Module) -> None:
        self.name, self.tree = name, tree
        self.defs: dict[str, ast.AST] = {}
        self.imports: dict[str, tuple] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defs[node.name] = node
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = self._absolute(node)
                if base is None:
                    continue
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = ("sym", base, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    key = alias.asname or alias.name.split(".")[0]
                    self.imports[key] = ("mod", alias.name)

    def _absolute(self, node: ast.ImportFrom) -> str | None:
        """`from . import x` inside `apps.reports.api` → `apps.reports`.

        Resolved rather than skipped: the previous lane's own measurement said
        nineteen modules were dead INCLUDING seven of `apps/reports/`, and was
        wrong because `reports/api.py` reaches them by relative import.
        """
        if node.level == 0:
            return node.module
        parts = self.name.split(".")[: -node.level]
        return ".".join(parts + ([node.module] if node.module else []))


def _resolve(mods: dict[str, _Mod], mod: _Mod, name: str) -> tuple[str, str] | None:
    """A local name → the (module, definition) it denotes, or the module itself."""
    if name in mod.defs:
        return (mod.name, name)
    kind = mod.imports.get(name)
    if not kind:
        return None
    if kind[0] == "mod":
        return (kind[1], "<module>") if kind[1] in mods else None
    target, original = kind[1], kind[2]
    if target in mods and original in mods[target].defs:
        return (target, original)
    if f"{target}.{original}" in mods:
        return (f"{target}.{original}", "<module>")
    if target in mods:
        return (target, "<module>")
    return None


def _targets(mods: dict[str, _Mod], mod: _Mod, node: ast.AST) -> set[tuple[str, str]]:
    """Every (module, definition) one body can reach by name."""
    out: set[tuple[str, str]] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute):
            base, attrs = sub, []
            while isinstance(base, ast.Attribute):
                attrs.append(base.attr)
                base = base.value
            if not isinstance(base, ast.Name):
                continue
            found = _resolve(mods, mod, base.id)
            if not found or found[1] != "<module>":
                continue
            here = found[0]
            for attr in reversed(attrs):
                if here in mods and attr in mods[here].defs:
                    out.add((here, attr))
                    break
                if f"{here}.{attr}" in mods:
                    here = f"{here}.{attr}"
                else:
                    break
            if here in mods:
                out.add((here, "<module>"))
        elif isinstance(sub, ast.Name):
            found = _resolve(mods, mod, sub.id)
            if found:
                out.add(found)
    return out


def _strings(node: ast.AST) -> set[str]:
    """String constants in a body, EXCLUDING the elements of an `__all__` list.

    Clause 2 of the docstring: a seam resolved by name (`seams.resolve("rating",
    "enrol_account", …)`) is a real door and appears in the source only as a
    string. Clause 3: a name in `__all__` is an export declaration, not a call,
    and counting it silenced both of `refunds.py`'s real findings.
    """
    exported: set[int] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in sub.targets
        ):
            for child in ast.walk(sub.value):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    exported.add(id(child))
    return {
        sub.value
        for sub in ast.walk(node)
        if isinstance(sub, ast.Constant)
        and isinstance(sub.value, str)
        and id(sub) not in exported
    }


#: The one decorator that declares an action human-performed, by its true home.
ROLE_GATE = ("core.permissions", "require_role")


def _is_role_gate(mods: dict[str, _Mod], mod: _Mod, dec: ast.AST) -> bool:
    """Is this decorator `core.permissions.require_role`, however it was named?

    Resolved through the module's imports rather than matched as text, because
    text matching is escapable in silence: the gate's OWN first red proof wrote
    `from core.permissions import require_role as _rr` and the new action left
    the universe without a word. Both live spellings — `@require_role(...)` and
    `@permissions.require_role(...)` — resolve here, and so does any alias.
    """
    node = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(node, ast.Name):
        return _resolve(mods, mod, node.id) == ROLE_GATE
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        base = _resolve(mods, mod, node.value.id)
        if base and base[1] == "<module>":
            return (base[0], node.attr) == ROLE_GATE
    return False


def _body(mod: _Mod, name: str) -> list[ast.AST]:
    """The statements one graph node owns.

    `<module>` is TOP-LEVEL statements plus decorators only — never the whole
    tree. Walking the whole tree was the first version's bug and it made every
    module that anything merely imported look fully reachable.
    """
    if name != "<module>":
        node = mod.defs.get(name)
        return [node] if node is not None else []
    plain = [
        s
        for s in mod.tree.body
        if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    decorators = [
        d
        for s in mod.tree.body
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for d in s.decorator_list
    ]
    return plain + decorators


def analyse(sources: dict[str, str]) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, int]]]:
    """(universe, unreached) — role-gated actions, and those with no door."""
    mods: dict[str, _Mod] = {}
    for name, text in sources.items():
        try:
            mods[name] = _Mod(name, ast.parse(text))
        except SyntaxError:
            continue

    mounted, frontier = set(), []
    if ROOT_URLCONF in sources:
        frontier = list(INCLUDE_RE.findall(sources[ROOT_URLCONF]))
    while frontier:
        dotted = frontier.pop()
        if dotted in mounted:
            continue
        mounted.add(dotted)
        if dotted in sources:
            frontier.extend(INCLUDE_RE.findall(sources[dotted]))
    if ROOT_URLCONF in mods:
        mounted.add(ROOT_URLCONF)

    reach = {(m, "<module>") for m in mounted if m in mods}
    seen_strings: set[str] = set()
    queue = list(reach)
    while queue:
        module_name, node_name = queue.pop()
        mod = mods.get(module_name)
        if mod is None:
            continue
        for stmt in _body(mod, node_name):
            seen_strings |= _strings(stmt)
            for edge in _targets(mods, mod, stmt):
                if edge not in reach:
                    reach.add(edge)
                    queue.append(edge)

    universe: list[tuple[str, str, int]] = []
    for name, mod in mods.items():
        if "migrations" in name.split("."):
            continue
        for fn, node in mod.defs.items():
            if isinstance(node, ast.ClassDef):
                continue
            if not any(_is_role_gate(mods, mod, d) for d in node.decorator_list):
                continue
            if REFUSAL_RE.search(ast.unparse(node)):
                continue  # a named refusal is the prime directive, not a gap
            universe.append((name, fn, node.lineno))

    unreached = [
        (m, f, ln)
        for m, f, ln in universe
        if (m, f) not in reach and f not in seen_strings
    ]
    return sorted(universe), sorted(unreached)


# ── the live tree ──────────────────────────────────────────────────────────


def _is_test(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_") or path.name == "tests.py"


def live_sources() -> dict[str, str]:
    """{dotted module: source} for every non-test backend Python file."""
    out: dict[str, str] = {}
    if not common.BACKEND_DIR.is_dir():
        return out
    for path in sorted(common.BACKEND_DIR.rglob("*.py")):
        if _is_test(path) or "__pycache__" in path.parts:
            continue
        dotted = ".".join(path.relative_to(common.BACKEND_DIR).with_suffix("").parts)
        out[dotted] = common.read_text(path)
    return out


def baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    keys = set()
    for line in common.read_text(BASELINE).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            keys.add(line)
    return keys


# ── self-test: every clause, proven to bite ────────────────────────────────


def selftest() -> list[str]:
    """A synthetic tree exercising each clause. Returns the clauses that did NOT bite."""
    broken: list[str] = []

    def keys(sources):
        return {f"{m}:{f}" for m, f, _ in analyse(sources)[1]}

    core = "def require_role(*a, **k):\n    return lambda f: f\n"
    urls_mounted = 'from django.urls import include, path\nurlpatterns = [path("", include("apps.a.api"))]\n'

    # 1 · a role-gated action a mounted route calls IS reachable
    svc = (
        "from core.permissions import require_role\n"
        "@require_role('X')\ndef do_it(actor):\n    return 1\n"
    )
    api = (
        "from django.urls import path\n"
        "from apps.a.services import do_it\n"
        "def view(request):\n    return do_it(request.user)\n"
        'urlpatterns = [path("go", view)]\n'
    )
    base = {"config.urls": urls_mounted, "core.permissions": core,
            "apps.a.services": svc, "apps.a.api": api}
    if keys(base):
        broken.append("a route-called action was reported as having no door")

    # 2 · the same action with the include REMOVED is unreachable
    unmounted = dict(base, **{"config.urls": "urlpatterns = []\n"})
    if keys(unmounted) != {"apps.a.services:do_it"}:
        broken.append("an unmounted module's action was not reported")

    # 3 · a CLASS-BASED view reaches it (the seven identity false positives)
    cbv = (
        "from django.urls import path\n"
        "from apps.a.services import do_it\n"
        "class V:\n"
        "    def post(self, request):\n        return do_it(request.user)\n"
        "    @classmethod\n    def as_view(cls):\n        return cls\n"
        'urlpatterns = [path("go", V.as_view())]\n'
    )
    if keys(dict(base, **{"apps.a.api": cbv})):
        broken.append("a class-based view did not count as a door")

    # 4 · a STRING-KEYED seam reaches it (the enrol_account false positive)
    seam_api = (
        "from django.urls import path\n"
        "from apps.a import seams\n"
        "def view(request):\n    return seams.resolve('a', 'do_it')\n"
        'urlpatterns = [path("go", view)]\n'
    )
    seam_mod = "def resolve(mod, name):\n    return None\n"
    if keys(dict(base, **{"apps.a.api": seam_api, "apps.a.seams": seam_mod})):
        broken.append("a string-keyed seam did not count as a door")

    # 5 · a name that appears ONLY in `__all__` is NOT a door (the refunds case)
    all_api = (
        "from django.urls import path\n"
        "__all__ = ['do_it']\n"
        "def view(request):\n    return None\n"
        'urlpatterns = [path("go", view)]\n'
    )
    if keys(dict(base, **{"apps.a.api": all_api})) != {"apps.a.services:do_it"}:
        broken.append("an __all__ re-export was accepted as a door")

    # 6 · a NAMED REFUSAL is not counted as an unreachable gap
    refusal = (
        "from core.permissions import require_role\n"
        "@require_role('X')\ndef do_it(actor):\n"
        "    raise NotImplementedError('OQ-123')\n"
    )
    if keys(dict(unmounted, **{"apps.a.services": refusal})):
        broken.append("a named refusal was flagged as unreachable")

    # 7 · an UNDECORATED function is outside the universe entirely
    plain = "def do_it(actor):\n    return 1\n"
    if keys(dict(unmounted, **{"apps.a.services": plain})):
        broken.append("an undecorated function entered the universe")

    # 8 · an ALIASED require_role is still a role gate (the first red proof)
    aliased = (
        "from core.permissions import require_role as _rr\n"
        "@_rr('X')\ndef do_it(actor):\n    return 1\n"
    )
    if keys(dict(unmounted, **{"apps.a.services": aliased})) != {"apps.a.services:do_it"}:
        broken.append("an aliased require_role escaped the universe")

    # 9 · a decorator merely CALLED require_role by coincidence is not a gate
    impostor = (
        "def require_role(*a):\n    return lambda f: f\n"
        "@require_role('X')\ndef do_it(actor):\n    return 1\n"
    )
    if keys(dict(unmounted, **{"apps.a.services": impostor})):
        broken.append("a look-alike decorator was accepted as the role gate")

    return broken


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    sources = live_sources()
    if "config.urls" not in sources:
        return "FAIL", "no config/urls.py — this gate cannot tell a door from a wall"

    universe, unreached = analyse(sources)
    if not universe:
        return "FAIL", "no @require_role action found in 06-backend — the scope has moved"

    found = {f"{m}:{f}" for m, f, _ in unreached}
    lines = {f"{m}:{f}": ln for m, f, ln in unreached}
    known = baseline()

    new = sorted(found - known)
    if new:
        return "FAIL", (
            f"{len(new)} role-gated action(s) reach no route and are not in the "
            "baseline: "
            + "; ".join(
                f"{k} (06-backend/{k.split(':')[0].replace('.', '/')}.py:{lines[k]})"
                for k in new
            )
            + ". Each declares @require_role — the code's own statement that a "
            "person performs it — and no route a person can get to calls it."
        )

    universe_keys = {f"{m}:{f}" for m, f, _ in universe}
    stale = sorted(known - found)
    if stale:
        return "FAIL", (
            f"{len(stale)} baseline line(s) are STALE and must be deleted: "
            + "; ".join(
                f"{k} now reaches a route"
                if k in universe_keys
                else f"{k} no longer exists (renamed, deleted or ungated)"
                for k in stale
            )
        )

    files = len({m for m, _, _ in universe})
    hit_files = len({m for m, _, _ in unreached})
    return "PASS", (
        f"{len(universe)} role-gated action(s) declared across {files} backend "
        f"file(s); {len(universe) - len(unreached)} reach a route a person can "
        f"get to; {len(unreached)} in {hit_files} file(s) do not, and every one "
        f"is named in {BASELINE.name} (DEF-135 / DEF-478 shape); "
        f"self-test: 9/9 clauses bite"
    )


def main() -> int:
    status, note = run()
    print(f"G52 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
