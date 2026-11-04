#!/usr/bin/env python3
"""G26 required-rows — can a row a money path REFUSES without ever exist?

DEF-123, and it is the generalisation that is worth more than the fix. Verbatim
from the defect's own escape column:

    **Nothing in this repository asks whether a REQUIRED per-tenant row has any
    way of coming into existence.**

`bill_templates` / `bill_template_versions` landed with `templates_service`
implementing BR-BIL-025's resolution order in full and its own tests passing —
*against rows the TESTS create*. In the product no row was ever created: S8's
Templates tab had no endpoint mounted, provisioning seeded the chart of
accounts, the number series and the holidays and had no billing seeder, and no
migration planted a default. So `resolve_for` correctly refused *"this tenant
has no bill template … and no fallback"* for EVERY tenant, BR-BIL-026 makes the
pin non-optional, and **no bill could be issued on any deployment.** 1,900-odd
tests and 24 gates were green over it.

**G13 IS THE CLOSEST GATE AND IT LOOKS THE OTHER WAY.** G13 catches a component
prop nothing passes — code unreachable from CODE. This is code unreachable from
DATA, which no gate modelled. It is DEF-116 one level down: the engine is built,
tested and correct, and the thing that would put a row in front of it does not
exist.

════════════════════════════════════════════════════════════════════════════
WHAT THIS GATE CHECKS — FOUR CLAUSES, AND WHY IT IS NOT ONE
════════════════════════════════════════════════════════════════════════════
The register is `required_rows.txt`: one record per row a money path refuses
without, naming the refusal and naming the thing that can put the row there.

**(a) THE REFUSAL IS STILL THERE.** Each record names a `file::function` and a
distinctive phrase from the refusal's own sentence, and both must still be in
the tree. This is what stops the register turning into folklore: a row that
vouches for a refusal nobody raises any more is fiction, and fiction that reads
as coverage is worse than no register at all.

**(b) THE WRITER EXISTS.** The named seeder / view is DEFINED. DEF-123 failed
this clause: there was no writer of any kind.

**(c) THE WRITER IS REACHED.** A seeder is CALLED (an AST call site in the named
file — not a mention in a comment, because hard-won law 1 says a comment
claiming a guarantee is not the guarantee). A view is inside a `path(...)` in
its own module AND that module is included by `config/urls.py`. **An unmounted
view is DEF-123 all over again** — `templates_service` had a complete
create-edit-publish lifecycle and S8's Templates tab had no route, so no human
could reach it either.

**(d) DISCOVERY — the clause that catches the NEXT one.** (a)–(c) only check
rows somebody remembered to register, so they cannot fail for a table nobody
thought about. This clause parses every file under `06-backend/apps/` and looks
at the **arguments of `raise` statements only** — never comments, never
docstrings, never prose — for a refusal of a known shape. Every such refusal
must be in the register. A new required row therefore fails the build the day
its refusal is written, which is the day `templates_service.py` landed.

════════════════════════════════════════════════════════════════════════════
WHAT THIS GATE HONESTLY CANNOT SEE — read this before trusting a green
════════════════════════════════════════════════════════════════════════════
Clause (d) keys on a SHORT LIST of phrase families (`REFUSAL_SHAPES`). A refusal
that says *"no rate schedule is configured"*, or that returns None and lets a
caller stall, is invisible to it — and this gate will report PASS over exactly
the defect it was written for, wearing different words.

**IT ALREADY DID, ON 2026-08-16 (DEF-163).** `notification_templates` was
DEF-123 to the letter: a required per-tenant row nothing created, so every
dunning letter and every disconnection notice refused on every tenant. The
refusal reads *"no published 'disconnect_notice' template resolves for category
'default'"* and matched nothing. **A second family was added and, with it, the
fix that mattered more:** discovery now matches the JOINED raise text, because
a refusal long enough to be honest is written as concatenated f-string parts and
`ast` hands each back separately — so the phrase spans two fragments and a
per-fragment match sees neither. Clause (a) had always joined; discovery had not.

**That is a repair, not a solution, and this note is the reason the register's
rows remain the real answer**: the alternative — a loose pattern over every
`raise` in the tree — produces a register nobody maintains, and an unmaintained
register is how a gate stops being able to fail. Adding a row is cheap, and a
reviewer reading `required_rows.txt` sees the whole class on one page. **A lane
that adds a required row adds a row; it does not hope discovery notices.**

It also does not read the DATABASE. A live tenant that predates a seeder still
has no row, and no static check can know that — the ledger's
`seed_chart_of_accounts` has carried the same exposure since it was written. The
data half is a TEST, on the real provisioning path, in
`06-backend/tests/test_def_123_bill_template_seeded.py`, where a database is
guaranteed rather than hoped for.

════════════════════════════════════════════════════════════════════════════
RED-PROOF (hard-won law 7 — run before this gate was trusted)
════════════════════════════════════════════════════════════════════════════
Deleting the provisioning call — the exact state of the tree on 2026-08-15 —
makes clause (c) fail with:

    G26 required-rows FAIL  1 problem(s):
        bill_templates — the writer exists and NOTHING CALLS IT:
        apps/billing/templates_service.py::seed_platform_default is never called
        in 06-backend/apps/tenancy/services.py (DEF-123: built is not wired,
        applied to DATA)

Removing the register row instead makes clause (d) fail with the refusal it
found and cannot account for.

**RE-PROVED FOR THE SECOND FAMILY, 2026-08-16 (DEF-163), all three ways:**

  · *the gate as shipped was blind* — one family, matched per fragment,
    discovered `template_service.resolve`: **False**;
  · *as widened* — two families, matched joined: **True**, on
    `'no published   template resolves for category   in language  , and
    BR-NOT-001 …'`, and the new family alone still reads False per fragment, so
    the join is load-bearing rather than cosmetic;
  · *clause (c) on the new row* — repointing its wiring at a name provisioning
    does not call fails with *"the writer exists and NOTHING CALLS IT"*.

Usage:
    python3 10-scripts/gates/g26_required_rows.py
"""

from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTER = pathlib.Path(__file__).resolve().parent / "required_rows.txt"
BACKEND_APPS = ROOT / "06-backend" / "apps"
URLCONF = ROOT / "06-backend" / "config" / "urls.py"

#: Clause (d)'s discovery patterns. Applied ONLY to the string arguments of a
#: `raise`, so prose about a defect cannot trip them.
#:
#: **TWO FAMILIES, AND THE SECOND ONE IS DEF-163 (2026-08-16).** The gate shipped
#: with the first alone and its own docstring predicted the consequence in
#: writing: *"A future refusal that says 'no rate schedule is configured' … is
#: invisible to it, and this gate will report PASS over exactly the defect it was
#: written for, wearing different words."* It did. `notification_templates` is
#: DEF-123's defect to the letter — a required per-tenant row nothing created, so
#: every dunning letter and every disconnection notice refused on every tenant —
#: and `template_service.resolve` refuses with *"no published 'disconnect_notice'
#: template resolves for category 'default'"*, which matches nothing here. G26
#: reported PASS over it for a day.
#:
#: The second family is added rather than the pattern loosened, for the reason
#: the docstring already gives: a looser pattern over every `raise` produces a
#: register nobody maintains. **This is still not a general solution and the
#: register's rows remain the real answer** — a third refusal wording will be
#: invisible again, which is why every lane adding a required row adds a row
#: rather than trusting discovery to notice.
REFUSAL_SHAPES = (
    # DEF-123 — "this tenant has no bill template …"
    re.compile(r"\btenant has no\b", re.IGNORECASE),
    # DEF-163 — "no published 'dunning' template resolves for category …"
    re.compile(r"\bno published\b.{0,120}?\bresolves\b", re.IGNORECASE | re.DOTALL),
)

KINDS = ("provisioning", "migration", "endpoint")


class Record:
    __slots__ = ("table", "refusal", "phrase", "kind", "writer", "wired", "reason", "line_no")

    def __init__(self, fields: list[str], line_no: int) -> None:
        (
            self.table,
            self.refusal,
            self.phrase,
            self.kind,
            self.writer,
            self.wired,
            self.reason,
        ) = fields
        self.line_no = line_no


def load_register() -> tuple[list[Record], list[str]]:
    if not REGISTER.exists():
        return [], [f"{REGISTER.name} is missing — the register IS the gate"]
    records: list[Record] = []
    problems: list[str] = []
    for line_no, raw in enumerate(REGISTER.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [part.strip() for part in line.split("|")]
        if len(fields) != 7:
            problems.append(
                f"{REGISTER.name}:{line_no} has {len(fields)} fields, expected 7 "
                "(table | refusal | phrase | kind | writer | wired | reason)"
            )
            continue
        record = Record(fields, line_no)
        if record.kind not in KINDS:
            problems.append(
                f"{REGISTER.name}:{line_no} kind {record.kind!r} is not one of {KINDS}"
            )
            continue
        records.append(record)
    return records, problems


def _split_ref(ref: str) -> tuple[pathlib.Path, str]:
    path_part, _, symbol = ref.partition("::")
    return ROOT / path_part, symbol


def _defines(tree: ast.AST, symbol: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if node.name == symbol:
                return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    return True
    return False


def _called_names(tree: ast.AST) -> set[str]:
    """Every name that is CALLED in this module — `f()` and `mod.f()` alike.

    AST rather than a text search on purpose: a seeder named in a comment, a
    docstring or a `TODO` is not a seeder that runs, and reading one as the other
    is precisely how DEF-123 survived a code review.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _routed_views(tree: ast.AST) -> set[str]:
    """Every view name that appears inside a `path(...)` / `re_path(...)`."""
    routed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name not in ("path", "re_path"):
            continue
        for arg in node.args[1:]:
            if isinstance(arg, ast.Name):
                routed.add(arg.id)
            elif isinstance(arg, ast.Attribute):
                routed.add(arg.attr)
    return routed


def _parse(path: pathlib.Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None


def check_records(records: list[Record]) -> list[str]:
    problems: list[str] = []
    for record in records:
        # ── (a) the refusal is still there ──────────────────────────────────
        refusal_path, refusal_fn = _split_ref(record.refusal)
        refusal_tree = _parse(refusal_path)
        if refusal_tree is None:
            problems.append(
                f"{record.table} — the refusal file {record.refusal} cannot be read; this "
                "row vouches for a check that is not in the tree"
            )
            continue
        found = [
            node
            for node in ast.walk(refusal_tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == refusal_fn
        ]
        if not found:
            problems.append(
                f"{record.table} — {record.refusal} no longer exists. Either the money path "
                "stopped refusing (delete this row) or it moved (repoint it); a register "
                "row that vouches for a missing refusal is fiction that reads as coverage"
            )
            continue
        raised = " ".join(_raise_strings(found[0]))
        if record.phrase.lower() not in raised.lower():
            problems.append(
                f"{record.table} — {record.refusal} no longer raises {record.phrase!r}. The "
                "phrase is this row's staleness anchor; reword the row with the refusal"
            )

        # ── (b) the writer exists ───────────────────────────────────────────
        writer_path, writer_symbol = _split_ref(record.writer)
        if record.kind == "migration":
            if not writer_path.exists():
                problems.append(
                    f"{record.table} — the migration {record.writer} does not exist, so "
                    "nothing plants the row (DEF-123)"
                )
            continue
        writer_tree = _parse(writer_path)
        if writer_tree is None or not _defines(writer_tree, writer_symbol):
            problems.append(
                f"{record.table} — NOTHING CREATES IT: {record.writer} is not defined. A "
                "money path refuses without this row and no writer exists (DEF-123)"
            )
            continue

        # ── (c) the writer is reached ───────────────────────────────────────
        wired_path, wired_spec = _split_ref(record.wired)
        wired_kind, _, wired_name = wired_spec.partition(":")
        wired_tree = _parse(wired_path)
        if wired_tree is None:
            problems.append(f"{record.table} — cannot read the wiring file {record.wired}")
            continue
        if wired_kind == "call":
            if wired_name not in _called_names(wired_tree):
                problems.append(
                    f"{record.table} — the writer exists and NOTHING CALLS IT: "
                    f"{record.writer} is never called in "
                    f"{wired_path.relative_to(ROOT)} (DEF-123: built is not wired, "
                    "applied to DATA)"
                )
        elif wired_kind == "route":
            if wired_name not in _routed_views(wired_tree):
                problems.append(
                    f"{record.table} — the view exists and NO ROUTE REACHES IT: "
                    f"{wired_name} is in no path(...) in "
                    f"{wired_path.relative_to(ROOT)}. That is exactly S8's Templates tab "
                    "on 2026-08-15 — a complete lifecycle no human could call (DEF-123)"
                )
            elif URLCONF.exists():
                module = ".".join(wired_path.relative_to(ROOT / "06-backend").with_suffix("").parts)
                urls_text = URLCONF.read_text(encoding="utf-8", errors="replace")
                package = module.rsplit(".", 1)[0]
                if package not in urls_text:
                    problems.append(
                        f"{record.table} — {module} exports urlpatterns that "
                        "config/urls.py never includes, so the route answers 404 "
                        "(the S30 and S31 lanes each learned this the same way)"
                    )
        else:
            problems.append(
                f"{record.table} — wiring spec {wired_spec!r} must be call:<name> or "
                "route:<view>"
            )
    return problems


def _raise_strings(node: ast.AST) -> list[str]:
    """Every string literal inside a `raise` in this subtree, and nothing else."""
    out: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise):
            for inner in ast.walk(child):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    out.append(inner.value)
    return out


def discover(records: list[Record]) -> list[str]:
    """Clause (d): a refusal of DEF-123's shape that no register row accounts for."""
    registered = {record.refusal for record in records}
    problems: list[str] = []
    for path in sorted(BACKEND_APPS.rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            # JOINED, not per-string — DEF-163's second half. A refusal long
            # enough to be honest is written as implicitly-concatenated f-string
            # parts, and `ast` hands back each literal fragment separately: the
            # notifications refusal splits as "no published " · " template
            # resolves for category " · " in ", so a per-fragment match sees a
            # phrase that spans two fragments and finds nothing. Clause (a)
            # already joins for exactly this reason; discovery now agrees with it.
            texts = _raise_strings(node)
            joined = " ".join(texts)
            if not any(shape.search(joined) for shape in REFUSAL_SHAPES):
                continue
            ref = f"{path.relative_to(ROOT)}::{node.name}"
            if ref not in registered:
                problems.append(
                    f"{ref} refuses because a per-tenant row is missing, and "
                    f"{REGISTER.name} does not say how that row is ever created. Add a "
                    "row naming the provisioning seeder, the migration or the mounted "
                    "endpoint that writes it — or file a defect, because a required row "
                    "with no door is DEF-123"
                )
    return problems


def _evaluate() -> tuple[list[Record], list[str]]:
    records, problems = load_register()
    problems += check_records(records)
    problems += discover(records)
    return records, problems


def run() -> tuple[str, str]:
    """The `run_gates.py` contract: (status, one-line detail).

    Separate from `main()` because the runner imports the module and calls
    `run()` — a gate that only exposes `main()` is registered, imported and then
    crashes with `AttributeError`, which the runner scores FAIL with a message
    about attributes rather than about the thing it guards.
    """
    records, problems = _evaluate()
    if problems:
        return "FAIL", "; ".join(problems[:3]) + (
            f" (+{len(problems) - 3} more)" if len(problems) > 3 else ""
        )
    kinds = ", ".join(f"{kind}={sum(1 for r in records if r.kind == kind)}" for kind in KINDS)
    return "PASS", (
        f"{len(records)} required per-tenant row(s) registered ({kinds}); each refusal still "
        "raises, each writer exists and is reached; no unregistered refusal of a registered shape"
    )


def main() -> int:
    records, problems = _evaluate()

    if problems:
        print(f"G26 required-rows FAIL  {len(problems)} problem(s):")
        for problem in problems[:10]:
            print(f"    {problem}")
        if len(problems) > 10:
            print(f"    (+{len(problems) - 10} more)")
        return 1

    kinds = ", ".join(f"{kind}={sum(1 for r in records if r.kind == kind)}" for kind in KINDS)
    print(
        f"G26 required-rows PASS  {len(records)} required per-tenant row(s) registered "
        f"({kinds}); each refusal still raises, each writer exists and is reached; no "
        "unregistered refusal of a registered shape found"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
