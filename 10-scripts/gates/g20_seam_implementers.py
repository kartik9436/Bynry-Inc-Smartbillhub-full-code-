"""G20 — every documented seam has an implementer. Added 2026-08-11 from DEF-075.

THE DEFECT, IN ITS OWN NUMBERS
------------------------------
DEF-075: `apps/tenancy/seams.py` documents BR-TEN-042's currency-lock probe as
two callables — `apps.billing.services.financial_records_exist()` and
`apps.payments.services.financial_records_exist()`. **Only payments ever
authored it.** So `PUT /api/brazosbend/settings/regional {"currency":"CAD"}`
answered **HTTP 200** on a tenant holding issued bill **BL-2606-000001, 108.88
USD**, and the books were re-denominated. Billing's leg of the probe resolved to
`None`; `None` was read as *"this module has nothing"* when it meant *"this
module cannot answer"*. 1,961 tests and 19 gates were green over it the whole
time, because the tenancy suite tests the refusal with a PAYMENTS row present
and no test asks the question a browser asked.

DEF-075's prevention column names the durable gap in one sentence, and it is
this gate's charter verbatim: *"no gate asserts that every DOCUMENTED seam has
an implementer in each module that owns the fact, so the next module to grow
tables can repeat this exactly."*

Two more rows in the register are the same family:

  DEF-035  `last_issued_invoice_period_end` resolved the wrong KIND — `services`
           instead of `selectors` — so US-CUS-005 TC-6's move-out guard returned
           None on EVERY call and recorded
           `move_out_date_not_checked_against_issued_bills`. Every move-out,
           since the day the guard was written. Its prevention column asks for
           exactly this gate: *"a gate that resolves every seams.py lookup at
           import and fails when the target does not exist"*.
  DEF-047  a seam that adapted the owner's RESULT but not the owner's REFUSAL.

WHAT A "DECLARATION" IS HERE — BOTH HALVES, BECAUSE DEF-075 LIVED IN ONE
------------------------------------------------------------------------
A seam module declares its cross-module contracts twice and the two can
disagree, which is how DEF-075 survived: the CODE resolved
`("billing", "payments")` from a loop variable — invisible to any static reader
— while the PROSE named both modules explicitly. So both are harvested:

  PROSE  every `apps.<module>.<kind>.<name>` in a seam module's docstrings and
         comments. This is the half that carries DEF-075.
  CODE   every late-bound lookup whose module/kind/name are statically knowable:
         `resolve/require/_resolve/_require(module, attr, kind=…)` — the
         resolver's own signature and `import_module(f"apps.{…}.{…}")` f-string
         are parsed to learn each one's parameter order and default kind, and
         module-level string constants (`POSTING_MODULE = "ledger"`) are
         substituted — plus `getattr(alias, "name", …)` where `alias =
         import_module("apps.<mod>.<kind>")` in the same function (the shape
         `apps/rating/seams.py` uses and the resolver-helper shape misses).

THE THREE RULES
---------------
R1  WRONG KIND — the declared name is absent from the declared kind but PRESENT
    somewhere else in the SAME module. DEF-035 exactly. **Never parkable**: the
    owner demonstrably answers that exact question from a different file, so
    there is nothing to weigh up and no reason to wait.

R2  NO IMPLEMENTER — the declared name is absent from the owning module
    altogether. FAIL unless `seam_known_gaps.txt` carries a row for it. This is
    the DEF-075 assertion: a documented seam nobody authored cannot merge in
    silence, and a seam that STOPS resolving (renamed, moved, re-export deleted)
    goes RED the same minute. Removing billing's `financial_records_exist`
    re-export — the DEF-075 tree, exactly — fails here.

R3  REGISTER INTEGRITY — never parkable, because a register nobody audits is how
    a gate becomes DEF-077 (*"a PO-ratified merge-blocking gate that was a
    hardcoded `return SKIP`"*). A row must:
      · name a target that is STILL declared and STILL unresolved (a row whose
        seam now works, or whose seam is gone, is deleted — not left to rot);
      · name a module and kind that EXIST (a typo'd contract is not a gap);
      · carry a guard that is still true —
          `absent=mod.Symbol[.attr],…`  the symbols whose ABSENCE makes the
              caller's fallback honest. **The moment one appears the park
              EXPIRES and this gate goes RED.** That is DEF-075's own sentence
              made mechanical: "a seam whose safety depends on a neighbour never
              being built needs a check that notices when it is."
          `alt=apps.M.K.N`  a documented ALTERNATIVE that IS published and is
              what actually runs; the gate resolves it, so the fallback path
              cannot quietly vanish too.
          `none`  no construction claim at all — the caller reports the value as
              unavailable or refuses, and no arrival can make that a lie.
      · state a REASON of at least 40 characters. A one-word reason is how a
        register turns into an allowlist.

WHAT THIS GATE DOES **NOT** CHECK — AND THE MEASUREMENTS BEHIND EACH REFUSAL
----------------------------------------------------------------------------
Hard-won law 1 says a comment claiming a guarantee is not the guarantee, so here
is what is NOT guaranteed. Every number below was measured on this tree on
2026-08-11 before the rule was refused.

1. **It does not decide whether the owning module "owns the fact".** DEF-075's
   own wording asks for an implementer "in each module that owns the fact", and
   that phrase cannot be evaluated statically: it needs to know WHICH table
   answers a given seam. Measured: all 13 unresolved seams today are owned by
   modules that have models (billing 13, metering 12, customers 12, rating 20),
   so a "the owner has tables ⇒ FAIL" rule would fire on all 13 on its first
   run. DEF-041's prevention column says what that does — *"a widened gate that
   fires on 40 legitimately-later props teaches people to add ALLOW entries,
   which is how a gate stops being a gate"* — so the register carries the
   judgement instead, one dated row at a time, and R3's `absent=` guard is where
   the "owns the fact" question gets asked in a form a machine can re-ask.

2. **It does not block a seam whose unwired fallback SUBSTITUTES AN ANSWER.**
   This is the sharpest edge of DEF-075 and it is REPORTED, not enforced, and
   the reason is that it is red on arrival. `financial_records_exist` returning
   `False` was a substituted answer; so is a used-by count returning `0`. The
   register classifies every row (`reports-absent` · `refuses` · `alternative` ·
   `substitutes-answer`) and the run line names the substituting count on every
   run. **Measured today: FIVE seams substitute a fact while unwired, and every
   one of their owning tables now exists** —
     apps.metering.services.read_count_for_asset      → 0   (metering.MeterRead exists)
     apps.billing.services.invoice_line_count_for_asset → 0 (billing.InvoiceLine exists)
     apps.billing.services.reason_code_used_by_count  → 0   (billing.Adjustment exists)
     apps.billing.services.charge_line_count          → 0   (billing.InvoiceLine exists)
     apps.billing.services.plan_invoice_count         → 0   (billing.Invoice exists)
   Each is a live recurrence of DEF-075's shape in a different module, each is
   parked LOUD with that sentence in its row, and each needs a defect row and a
   published function — not a gate flag. When those five are fixed, promote
   `substitutes-answer + guard=none` from reported to FAIL; the code for it is
   two lines and the place is marked below.

3. **It does not check SIGNATURES, types, or exception hierarchies.** It asks
   whether a callable of that name exists at that address. DEF-047 — a caller
   that adapts the owner's result but not the owner's refusal — is the same
   family and is NOT caught here; its prevention column names its own gate ("a
   gate that reads each apps/*/errors.py base class and asks whether the callers
   of that module's seams name it"). Not built, not claimed.

4. **It does not see a lookup whose module or kind is computed at runtime.**
   Measured: 4 of the 106 resolver call sites bind their module from a variable
   — `tenancy/seams.py:225` and `:237` (`owner_module`), `tenancy/seams.py:307`,
   and `metering/seams.py:311`. **Line 307 is DEF-075's own loop**, the one that
   walks `("billing", "payments")` and made the missing leg invisible. Those
   four are covered by the PROSE half and by nothing else — which is precisely
   why this gate reads prose at all, and why deleting the docstring contract in
   a seam module silently deletes the only check over it.

5. **It does not check hard imports.** `from apps.metering import selectors` at
   the top of a seam function is not a seam; it fails loudly at import if it is
   wrong, so it needs no gate.

6. **It does not read the frontend.** Seams are a backend construct (B1).

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
------------------------------------------------
Part 0 replays NINE fixtures against an IN-MEMORY copy of the real survey —
nothing is written, the repo is opened read-only. B1 and B2 are DEF-075 (billing
publishes `financial_records_exist` nowhere; then only the `services` re-export
removed) and B3 is DEF-035 (the `last_issued_invoice_period_end` contract points
at `services` again). A fixture that fails to bite FAILS the gate, so this gate
cannot rot into one that always passes.

Three of them were ALSO proved against the REAL tree by mutating real files and
restoring them byte-identically — quoted verbatim in the lane report:
  · `apps/billing/services.py` loses the re-export      → WRONG KIND, DEF-075
  · `apps/customers/seams.py` loses `kind="selectors"`  → WRONG KIND, DEF-035
  · a park's `absent=` guard flipped to columns that exist → PARK EXPIRED
Fixtures derive their targets from the survey wherever possible (see B5): a
fixture that names a symbol by hand goes blind the day that symbol moves, which
is how a self-test quietly stops testing.

ADDING THIS GATE IS A PROCESS EVENT. G1–G16 are the PO-ratified merge-blocking
set (2026-08-11, option A); G17–G20 are Eng-Lead additions from defect rows and
are merge-blocking from the moment they are wired, so each is reported for the
daily PO batch and recorded in 12-governance/02-decision-log.md.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import ast
import io
import re
import tokenize
from pathlib import Path

import common

REGISTER = Path(__file__).resolve().parent / "seam_known_gaps.txt"

MAX_NAMED = 3
MIN_REASON = 40

#: The helper names a seam module uses for a late-bound cross-module lookup.
RESOLVER_NAMES = ("resolve", "require", "_resolve", "_require")

#: Fallback classes a register row may declare. What the CALLER does while the
#: seam is unwired — the difference between reporting a gap and inventing a fact.
FALLBACKS = {
    "reports-absent": "returns None/()/[]/a stated problem — the caller must handle absence",
    "refuses": "raises, so the operation stops rather than proceeding on a guess",
    "alternative": "a second documented callable IS published and is what runs",
    "substitutes-answer": "returns a value the caller uses as fact (DEF-075's shape)",
}

#: A fully-qualified seam address in prose. `<owner>` placeholders and SHOUTED
#: pseudo-paths like `apps.billing.SERVICES` deliberately do not match.
PROSE_TARGET = re.compile(r"\bapps\.([a-z][a-z_]*)\.([a-z][a-z_]*)\.([A-Za-z_][A-Za-z0-9_]*)")

#: Module kinds that are NOT an owner's published surface — see
#: `Survey.other_kinds_publishing` for the measured reason each is here.
CALLER_SURFACES = ("tests", "migrations", "apps", "urls", "api", "conftest")


def _is_caller_surface(kind: str) -> bool:
    return "seam" in kind or kind in CALLER_SURFACES


# ═══════════════════════════════════════════════════════════════════════════
# SURVEY — everything read off disk, gathered as plain data so `check()` below
# is a pure function and Part 0 can re-run it over a mutated copy (the G17
# discipline: never mutate the repo to test the checker).
# ═══════════════════════════════════════════════════════════════════════════
class Survey:
    def __init__(self) -> None:
        #: [(target, caller-rel-path, lineno, "prose"|"code")]
        self.declarations: list[tuple[str, str, int, str]] = []
        #: (module, kind) -> the top-level names that module publishes
        self.published: dict[tuple[str, str], set[str]] = {}
        #: (module, kind) that exist on disk at all
        self.kinds: set[tuple[str, str]] = set()
        #: (module, kind, name) where apps/<module>/<kind>/<name>.py is a SUBMODULE
        self.submodules: set[tuple[str, str, str]] = set()
        #: "module.Symbol" and "module.Symbol.attr" — the `absent=` vocabulary
        self.symbols: set[str] = set()
        #: modules that exist under 06-backend/apps/
        self.modules: set[str] = set()

    # ── queries the rules ask ──────────────────────────────────────────────
    def resolves(self, module: str, kind: str, name: str) -> bool:
        if (module, kind, name) in self.submodules:
            return True  # a dotted MODULE path, not a callable
        return name in self.published.get((module, kind), set())

    def other_kinds_publishing(self, module: str, name: str) -> list[str]:
        """The OWNER surfaces of `module` that publish `name` — R1's evidence.

        Seam modules are excluded, and the exclusion is the whole point of the
        rule rather than a convenience: a seam is the CALLER's adapter and it
        habitually names its wrapper after the callable it is reaching for
        (`apps/billing/rating_seam.py` defines `issue_credit_note`, which is the
        name it asks BILLING for). Counting that as evidence would report a seam
        as the implementer of its own contract — measured: 1 false positive on
        this tree before the exclusion. Test, migration, URL and AppConfig
        modules are excluded for the same reason: a name there is not a
        published cross-module surface.
        """
        return sorted(k for (m, k), names in self.published.items()
                      if m == module and name in names and not _is_caller_surface(k))


def _top_level_names(path: Path) -> set[str]:
    """Every name a module publishes: defs, classes, assignments, re-exports.

    Imports count — `financial_records_exist` reaches `apps.billing.services`
    only as a re-export (`from apps.billing.selectors import …`), which is
    exactly how DEF-075 was FIXED, so a checker that ignored imports would call
    the fix a defect.
    """
    try:
        tree = ast.parse(common.read_text(path))
    except SyntaxError:  # pragma: no cover - a broken file is another gate's job
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.If):  # conditional / TYPE_CHECKING re-exports
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(sub.name)
    return names


def _class_symbols(module: str, path: Path) -> set[str]:
    """`module.Class` and `module.Class.attr` for every top-level class.

    The `absent=` vocabulary. Fields are class-body assignments, which is what a
    Django model column is — so `customers.Account.paperless` is answerable
    without importing Django.
    """
    try:
        tree = ast.parse(common.read_text(path))
    except SyntaxError:  # pragma: no cover
        return set()
    out: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        out.add(f"{module}.{node.name}")
        for sub in node.body:
            targets = sub.targets if isinstance(sub, ast.Assign) else (
                [sub.target] if isinstance(sub, ast.AnnAssign) else [])
            out.update(f"{module}.{node.name}.{t.id}" for t in targets if isinstance(t, ast.Name))
    return out


def seam_files() -> list[Path]:
    """Every seam module: apps/*/seams.py plus apps/*/<neighbour>_seam.py."""
    if not common.BACKEND_APPS.is_dir():
        return []
    return sorted(p for p in common.BACKEND_APPS.rglob("*.py")
                  if "seam" in p.name and "__pycache__" not in p.parts)


# ── the CODE half: static evaluation of late-bound lookups ─────────────────
def _resolver_specs(tree: ast.Module, consts: dict[str, str]) -> dict[str, dict]:
    """For each resolver helper in a seam file: where its module/kind/name come from.

    Each of module/kind/attr is described as ("literal", v) | ("const", NAME) |
    ("param", NAME) | None. A helper that delegates to another helper (`require`
    -> `resolve`) inherits through the call's arguments, which is why the
    fixpoint below runs twice.
    """
    specs: dict[str, dict] = {}
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name in RESOLVER_NAMES):
            continue
        params = [a.arg for a in node.args.args]
        defaults: dict[str, str] = {}
        n_def = len(node.args.defaults)
        for arg, default in zip(params[len(params) - n_def:], node.args.defaults):
            if isinstance(default, ast.Constant) and isinstance(default.value, str):
                defaults[arg] = default.value

        def source(text: str):
            if text.startswith("{") and text.endswith("}"):
                name = text[1:-1]
                if name in consts:
                    return ("const", name)
                if name in params:
                    return ("param", name)
                return None
            return ("literal", text)

        module = kind = attr = None
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "import_module" and sub.args):
                joined = _fstring_text(sub.args[0])
                match = re.fullmatch(r"apps\.([^.]+)\.([^.]+)", joined or "")
                if match:
                    module, kind = source(match.group(1)), source(match.group(2))
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "getattr" and len(sub.args) >= 2
                    and isinstance(sub.args[1], ast.Name) and sub.args[1].id in params):
                attr = ("param", sub.args[1].id)
        specs[node.name] = {"params": params, "defaults": defaults, "node": node,
                            "module": module, "kind": kind, "attr": attr}

    # Second pass: helpers that delegate (require -> resolve) inherit the callee's
    # sources, mapped through the arguments the delegating call passes.
    for _ in range(2):
        for name, spec in specs.items():
            if spec["module"] and spec["kind"]:
                continue
            for sub in ast.walk(spec["node"]):
                if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                        and sub.func.id in specs and sub.func.id != name):
                    continue
                callee = specs[sub.func.id]
                bound = _bind(sub, callee["params"])
                for field in ("module", "kind", "attr"):
                    if spec[field] or not callee[field]:
                        continue
                    origin = callee[field]
                    if origin[0] != "param":
                        spec[field] = origin
                        continue
                    passed = bound.get(origin[1])
                    if passed is None:
                        if origin[1] in callee["defaults"]:
                            spec[field] = ("literal", callee["defaults"][origin[1]])
                        continue
                    if isinstance(passed, ast.Constant) and isinstance(passed.value, str):
                        spec[field] = ("literal", passed.value)
                    elif isinstance(passed, ast.Name):
                        if passed.id in consts:
                            spec[field] = ("const", passed.id)
                        elif passed.id in spec["params"]:
                            spec[field] = ("param", passed.id)
                break
    return specs


def _fstring_text(node: ast.AST) -> str | None:
    """`f"apps.{module}.{kind}"` -> `apps.{module}.{kind}` (placeholders kept)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if not isinstance(node, ast.JoinedStr):
        return None
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            parts.append("{" + ast.unparse(value.value) + "}")
    return "".join(parts)


def _bind(call: ast.Call, params: list[str]) -> dict[str, ast.AST]:
    bound = {p: a for p, a in zip(params, call.args)}
    bound.update({k.arg: k.value for k in call.keywords if k.arg})
    return bound


def _code_declarations(path: Path) -> list[tuple[str, int]]:
    """[(apps.module.kind.name, lineno)] for every statically-knowable lookup."""
    text = common.read_text(path)
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover
        return []
    consts = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    }
    specs = _resolver_specs(tree, consts)
    # Calls INSIDE a resolver helper are the plumbing, not a seam.
    plumbing = {(s["node"].lineno, s["node"].end_lineno) for s in specs.values()}

    def literal(source, bound: dict[str, ast.AST], defaults: dict[str, str]) -> str | None:
        if source is None:
            return None
        if source[0] == "literal":
            return source[1]
        if source[0] == "const":
            return consts.get(source[1])
        node = bound.get(source[1])
        if node is None:
            return defaults.get(source[1])
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return consts.get(node.id)
        return None

    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if any(start <= node.lineno <= end for start, end in plumbing):
            continue

        # shape 1: resolve/require helper
        if isinstance(node.func, ast.Name) and node.func.id in specs:
            spec = specs[node.func.id]
            bound = _bind(node, spec["params"])
            module = literal(spec["module"], bound, spec["defaults"])
            kind = literal(spec["kind"], bound, spec["defaults"])
            name = literal(spec["attr"], bound, spec["defaults"])
            if module and kind and name:
                found.append((f"apps.{module}.{kind}.{name}", node.lineno))
            continue

        # shape 2: getattr(alias, "name", …) where alias = import_module("apps.x.y")
        if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Name)
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            alias = _alias_module(tree, node.args[0].id, node.lineno)
            if alias:
                found.append((f"{alias}.{node.args[1].value}", node.lineno))
    return found


def _alias_module(tree: ast.Module, alias: str, lineno: int) -> str | None:
    """`alias = import_module("apps.rating.selectors")` -> `apps.rating.selectors`.

    Nearest preceding assignment wins, so a function that rebinds the name for a
    second module is read correctly.
    """
    best: tuple[int, str] | None = None
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == alias):
            continue
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "import_module" and call.args):
            continue
        dotted = _fstring_text(call.args[0])
        if dotted and re.fullmatch(r"apps\.[a-z_]+\.[a-z_]+", dotted) and node.lineno <= lineno:
            if best is None or node.lineno > best[0]:
                best = (node.lineno, dotted)
    return best[1] if best else None


# ── the PROSE half: what the module DOCUMENTS, which is where DEF-075 lived ──
def _prose_declarations(path: Path) -> list[tuple[str, int]]:
    text = common.read_text(path)
    lines: list[tuple[int, str]] = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body:
                    base = node.body[0].lineno
                    lines += [(base + i, line) for i, line in enumerate(doc.splitlines())]
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                lines.append((token.start[0], token.string))
    except (SyntaxError, tokenize.TokenError):  # pragma: no cover
        return []
    return [(f"apps.{m.group(1)}.{m.group(2)}.{m.group(3)}", lineno)
            for lineno, line in lines for m in PROSE_TARGET.finditer(line)]


def survey() -> Survey:
    """Read the repo once. Everything the rules need, as plain data."""
    data = Survey()
    if not common.BACKEND_APPS.is_dir():
        return data
    for module_dir in sorted(common.BACKEND_APPS.iterdir()):
        if not module_dir.is_dir() or module_dir.name == "__pycache__":
            continue
        module = module_dir.name
        data.modules.add(module)
        for child in sorted(module_dir.iterdir()):
            if child.is_file() and child.suffix == ".py":
                kind = child.stem
                data.kinds.add((module, kind))
                data.published[(module, kind)] = _top_level_names(child)
                data.symbols |= _class_symbols(module, child)
            elif child.is_dir() and (child / "__init__.py").is_file():
                kind = child.name
                data.kinds.add((module, kind))
                data.published[(module, kind)] = _top_level_names(child / "__init__.py")
                for grandchild in child.glob("*.py"):
                    if grandchild.name != "__init__.py":
                        data.submodules.add((module, kind, grandchild.stem))

    for path in seam_files():
        caller = common.rel(path)
        for target, lineno in _prose_declarations(path):
            data.declarations.append((target, caller, lineno, "prose"))
        for target, lineno in _code_declarations(path):
            data.declarations.append((target, caller, lineno, "code"))
    return data


# ═══════════════════════════════════════════════════════════════════════════
# THE REGISTER — the parked gaps. Real, unfixed, routed; never hidden.
# ═══════════════════════════════════════════════════════════════════════════
def register_rows(text: str | None) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    problems: list[str] = []
    if text is None:
        return rows, ["seam_known_gaps.txt is missing — the register must exist, even empty"]
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            problems.append(f"line {lineno}: expected "
                            "`<apps.M.K.name> <caller> <fallback> <guard> <YYYY-MM-DD> <reason>`")
            continue
        target, caller, fallback, guard, date, reason = parts
        if not PROSE_TARGET.fullmatch(target):
            problems.append(f"line {lineno}: {target!r} is not an apps.<module>.<kind>.<name> address")
            continue
        if fallback not in FALLBACKS:
            problems.append(f"line {lineno}: {target} declares fallback {fallback!r}; "
                            f"expected one of {', '.join(sorted(FALLBACKS))}")
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            problems.append(f"line {lineno}: {target} needs the date it was parked (YYYY-MM-DD)")
            continue
        if len(reason) < MIN_REASON:
            problems.append(f"line {lineno}: {target}'s reason is {len(reason)} characters; a park "
                            f"needs at least {MIN_REASON} — a one-word reason is an allowlist")
            continue
        if not (guard == "none" or guard.startswith(("absent=", "alt="))):
            problems.append(f"line {lineno}: {target}'s guard must be `none`, `absent=…` or "
                            f"`alt=apps.M.K.name`, not {guard!r}")
            continue
        rows.append({"target": target, "caller": caller, "fallback": fallback,
                     "guard": guard, "date": date, "reason": reason, "line": lineno})
    return rows, problems


# ═══════════════════════════════════════════════════════════════════════════
# THE CHECK — a pure function of (survey, register text). Part 0 runs it over
# mutated copies; nothing here reads the disk or writes anything.
# ═══════════════════════════════════════════════════════════════════════════
def check(data: Survey, register_text: str | None) -> tuple[list[str], dict[str, int]]:
    rows, failures = register_rows(register_text)
    parked = {row["target"]: row for row in rows}

    declared: dict[str, list[str]] = {}
    for target, caller, lineno, source in data.declarations:
        declared.setdefault(target, []).append(f"{caller}:{lineno} ({source})")

    unresolved: list[str] = []
    stats = {"declared": len(declared), "unresolved": 0, "parked": 0, "substituting": 0}

    for target in sorted(declared):
        _, module, kind, name = target.split(".", 3)
        if module not in data.modules:
            continue  # not one of ours; another gate's business
        if (module, kind) not in data.kinds:
            failures.append(f"{target} ({declared[target][0]}) names apps/{module}/{kind}.py, "
                            "which does not exist — a typo'd contract is not a gap")
            continue
        if data.resolves(module, kind, name):
            continue
        unresolved.append(target)

        elsewhere = data.other_kinds_publishing(module, name)
        if elsewhere:
            # ── R1: WRONG KIND. DEF-035. Never parkable. ──────────────────
            failures.append(
                f"WRONG KIND: {target} is declared at {declared[target][0]} but "
                f"apps.{module}.{kind} does not publish {name!r} — apps.{module}."
                f"{elsewhere[0]} does. The owner answers this exact question from "
                f"another file (DEF-035: two words were wrong, the KIND and nothing else)"
            )
            continue
        if target not in parked:
            # ── R2: NO IMPLEMENTER, and nobody wrote down why. DEF-075. ───
            failures.append(
                f"NO IMPLEMENTER: {target} is declared at {declared[target][0]} and "
                f"apps.{module} publishes {name!r} nowhere. Author it in the owning "
                f"module, or park it in seam_known_gaps.txt with the reason its "
                f"fallback is honest (DEF-075: billing's leg of the currency-lock "
                f"probe was documented, never written, and 200-OK'd a re-denomination)"
            )

    # ── R3: register integrity. Never parkable. ───────────────────────────
    unresolved_set = set(unresolved)
    for row in rows:
        target = row["target"]
        stats["parked"] += 1
        if row["fallback"] == "substitutes-answer":
            stats["substituting"] += 1
        if target not in declared:
            failures.append(f"STALE PARK line {row['line']}: {target} is no longer declared by any "
                            "seam module — delete the row, do not leave it to rot (DEF-077)")
            continue
        if target not in unresolved_set:
            failures.append(f"STALE PARK line {row['line']}: {target} RESOLVES now — the park has "
                            "done its job; delete the row so the gate guards it again")
            continue
        guard = row["guard"]
        if guard.startswith("absent="):
            arrived = [s for s in guard[len("absent="):].split(",") if s and s in data.symbols]
            if arrived:
                failures.append(
                    f"PARK EXPIRED line {row['line']}: {target} was parked because "
                    f"{', '.join(arrived)} did not exist. It exists now, so the fallback is no "
                    "longer honest by construction — this is DEF-075 arriving again, in the "
                    "module it was predicted for"
                )
        elif guard.startswith("alt="):
            alt = guard[len("alt="):]
            match = PROSE_TARGET.fullmatch(alt)
            if not match or not data.resolves(match.group(1), match.group(2), match.group(3)):
                failures.append(
                    f"PARK EXPIRED line {row['line']}: {target} was parked because the documented "
                    f"alternative {alt} is published and is what runs. It is not published now, so "
                    "both legs of this seam are dark"
                )
        # ── The promotion marked in the docstring (§ NOT CHECKED, item 2) is
        # here: `elif row["fallback"] == "substitutes-answer": failures.append(…)`
        # once the five measured rows are fixed. Counted and named until then.

    stats["unresolved"] = len(unresolved)
    return failures, stats


# ═══════════════════════════════════════════════════════════════════════════
# PART 0 — SELF-TEST. Hard-won law 7. Every rule is replayed against an
# IN-MEMORY copy of the real survey; nothing on disk is touched. B1 is DEF-075
# and B2 is DEF-035, both as they actually happened.
# ═══════════════════════════════════════════════════════════════════════════
def _clone(data: Survey) -> Survey:
    twin = Survey()
    twin.declarations = list(data.declarations)
    twin.published = {k: set(v) for k, v in data.published.items()}
    twin.kinds = set(data.kinds)
    twin.submodules = set(data.submodules)
    twin.symbols = set(data.symbols)
    twin.modules = set(data.modules)
    return twin


def _unpublish(data: Survey, module: str, kind: str, name: str) -> Survey:
    twin = _clone(data)
    twin.published.get((module, kind), set()).discard(name)
    return twin


def _unpublish_everywhere(data: Survey, module: str, name: str) -> Survey:
    twin = _clone(data)
    for (owner, _kind), names in twin.published.items():
        if owner == module:
            names.discard(name)
    return twin


def _redeclare(data: Survey, old: str, new: str) -> Survey:
    twin = _clone(data)
    twin.declarations = [(new if t == old else t, c, n, s) for t, c, n, s in data.declarations]
    return twin


def _a_resolving_target(data: Survey) -> str:
    """Any declared seam that currently resolves — B5's raw material."""
    for target in sorted({t for t, _c, _l, _s in data.declarations}):
        _, module, kind, name = target.split(".", 3)
        if module in data.modules and data.resolves(module, kind, name):
            return target
    return "apps.billing.services.g20_no_resolving_target"


def _an_unparked_unresolved_target(data: Survey) -> str:
    """Any declared seam that does NOT resolve — B4's and B9's raw material.

    DERIVED, never named. B4 used to hardcode
    `apps.billing.services.reason_code_used_by_count`, and on 2026-08-12 that
    counter was published (DEF-079) and its park row deleted — so the fixture
    stopped reaching the guard it was written to prove and the gate reported
    itself BLIND rather than passing quietly. That is the fixture working; it is
    also the second time a hardcoded symbol in this file has gone stale within a
    day (B5 was the first). A guard-expiry fixture needs *an* unresolved target,
    not a particular one.
    """
    for target in sorted({t for t, _c, _l, _s in data.declarations}):
        _, module, kind, name = target.split(".", 3)
        if module in data.modules and not data.resolves(module, kind, name):
            return target
    return "apps.billing.services.g20_no_unresolved_target"


def self_test(data: Survey, register_text: str | None) -> list[tuple[str, bool, str]]:
    """Each fixture must produce the named failure. A blind fixture FAILS the gate."""
    live = register_text or ""
    results: list[tuple[str, bool, str]] = []

    def probe(tag: str, mutated: Survey, text: str, needle: str, why: str) -> None:
        hits = [f for f in check(mutated, text)[0] if needle in f]
        results.append((tag, bool(hits),
                        (hits[0][:150] if hits else f"NOT reported (expected FAIL) — {why}")))

    # B1 — DEF-075 as the tree ACTUALLY WAS: billing publishes the currency-lock
    # probe nowhere, while apps/tenancy/seams.py documents it in so many words.
    probe("B1", _unpublish_everywhere(data, "billing", "financial_records_exist"), live,
          "NO IMPLEMENTER: apps.billing.services.financial_records_exist",
          "DEF-075: the probe documented in apps/tenancy/seams.py that only payments authored")

    # B2 — DEF-075 as it is RE-CREATED on disk for the law-7 proof: only the
    # `apps/billing/services.py` re-export removed, the selector left in place.
    # A different message, and the more useful one — it names the file to fix.
    probe("B2", _unpublish(data, "billing", "services", "financial_records_exist"), live,
          "WRONG KIND: apps.billing.services.financial_records_exist",
          "DEF-075's fix is a re-export; deleting it must not read as a resolved seam")

    # B3 — DEF-035 itself: the move-out guard's contract points at `services`.
    probe("B3", _redeclare(data, "apps.billing.selectors.last_issued_invoice_period_end",
                           "apps.billing.services.last_issued_invoice_period_end"), live,
          "WRONG KIND: apps.billing.services.last_issued_invoice_period_end",
          "DEF-035: the KIND was wrong and the guard returned None on every move-out")

    # B4 — a park whose `absent=` guard has arrived: DEF-075's rot mechanism.
    # Uses a REAL parked target, because a guard is only reached for a row whose
    # seam is genuinely declared and genuinely unresolved.
    unresolved = _an_unparked_unresolved_target(data)
    probe("B4", data,
          live + f"\n{unresolved} apps/tenancy/seams.py "
                 "substitutes-answer absent=billing.Invoice 2026-08-11 "
                 "a fixture: parked as safe only while billing holds no invoice rows at all\n",
          "PARK EXPIRED",
          "a park justified by a table that now exists must expire, not persist")

    # B5 — a park for a seam that resolves fine: the register cannot accumulate.
    # The target is DERIVED from the survey rather than named, so the fixture
    # cannot go blind because the tree changed under it — which is exactly what
    # happened when it hardcoded `financial_records_exist` and the DEF-075
    # red-proof unpublished that very name.
    wired = _a_resolving_target(data)
    probe("B5", data,
          live + f"\n{wired} apps/tenancy/seams.py reports-absent none 2026-08-11 "
                 "a fixture: a row for a seam that is wired, which must be deleted not kept\n",
          "STALE PARK",
          "a stale exemption is how a gate becomes an allowlist (DEF-077)")

    # B6 — a park leaning on an alternative that is no longer published.
    probe("B6", _unpublish(data, "billing", "selectors", "invoice_queryset"), live,
          "PARK EXPIRED", "the documented alternative must be resolvable or both legs are dark")

    # B7 — a contract naming a kind file that does not exist.
    twin = _clone(data)
    twin.declarations.append(("apps.billing.selctors.issued_invoices_for_account",
                              "apps/payments/billing_seam.py", 1, "prose"))
    probe("B7", twin, live, "does not exist", "a typo'd contract address is not a parkable gap")

    # B8 — the register must reject a row with no real reason.
    probe("B8", data,
          live + "\napps.billing.services.g20_probe_reason apps/tenancy/seams.py "
                 "reports-absent none 2026-08-11 later\n",
          "reason is", "a one-word reason turns a register into an allowlist")

    # B9 — the same expiry at FIELD granularity, which is what the live
    # `absent=customers.Account.paperless` park leans on: that column is
    # PROPOSED-SCHEMA today, and the park must expire the day it is added, not
    # the day someone remembers. `autopay` is a column that DOES exist on the
    # same model, so the fixture proves the reader sees Django fields and not
    # only class names.
    probe("B9", data,
          live + "\napps.billing.services.account_aging_state apps/customers/seams.py "
                 "reports-absent absent=customers.Account.autopay 2026-08-11 "
                 "a fixture: parked as honest only while accounts carry no autopay column\n",
          "PARK EXPIRED",
          "a park guarded by a model FIELD must expire when the field lands")

    return results


FIXTURE_WHY = {
    "B1": "DEF-075 — the documented probe billing never authored",
    "B2": "DEF-075 re-created on disk — only the services re-export removed",
    "B3": "DEF-035 — the seam resolved the wrong KIND",
    "B4": "a park's `absent=` guard arrives (DEF-075's rot mechanism)",
    "B5": "a park for a seam that now resolves",
    "B6": "a park leaning on an alternative that vanished",
    "B7": "a contract naming a module file that does not exist",
    "B8": "a register row with no real reason",
    "B9": "the same expiry at model-FIELD granularity",
}


def run() -> tuple[str, str]:
    files = seam_files()
    if not files:
        return "SKIP", "no seam module under 06-backend/apps/ — nothing declares a cross-module contract"

    data = survey()
    register_text = common.read_text(REGISTER) if REGISTER.is_file() else None

    blind = [(tag, detail) for tag, ok, detail in self_test(data, register_text) if not ok]
    if blind:
        return "FAIL", (
            f"self-test BLIND: {len(blind)} of {len(FIXTURE_WHY)} fixture(s) did not bite — "
            f"{blind[0][0]} {blind[0][1]}. A guard that cannot be shown to fail is not a guard "
            "(law 7); fix the checker, never delete the fixture."
        )

    failures, stats = check(data, register_text)
    if failures:
        return "FAIL", (f"{len(failures)} seam problem(s): {common.summarize(failures, MAX_NAMED)}")

    return "PASS", (
        f"{stats['declared']} seam contract(s) declared across {len(files)} seam module(s); "
        f"{stats['declared'] - stats['unresolved']} resolve to a real callable at the declared "
        f"kind, {stats['parked']} PARKED in seam_known_gaps.txt with a live guard "
        f"({stats['substituting']} of them SUBSTITUTE an answer while unwired — DEF-075's shape, "
        f"reported not blocked, see the docstring); "
        f"self-test: {len(FIXTURE_WHY)}/{len(FIXTURE_WHY)} rules bite"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    print()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    live = common.read_text(REGISTER) if REGISTER.is_file() else None
    snapshot = survey()
    for tag, ok, text in self_test(snapshot, live):
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {FIXTURE_WHY[tag]}")
        print(f"          {text}")
    print()
    print("--- findings ---")
    for problem in check(snapshot, live)[0]:
        print(f"  {problem}")
    raise SystemExit(0 if status != "FAIL" else 1)
