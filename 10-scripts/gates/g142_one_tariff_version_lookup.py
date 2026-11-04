#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-157-BRC10 wave A (PO 2026-10-01 — the GO for the rate-schedule
#          build, decision log *"GO ON THE RATE SCHEDULE BUILD — 52 TASKS"*):
#          *"billing one record 4 (all 10 billing files through the single
#          lookup; a gate failing direct version queries; …)"*. This is that
#          gate.
# Rules:   BR-RAT-007 (the version in force on the SERVICE date — one
#          function answers it, `rating.selectors.in_force_version`) ·
#          BR-RAT-037 (windows never overlap) · DEF-RAT-8002 (two readers of one
#          table disagreed, and a move-out bill refused while the run billed)
# Tests:   selftest() below runs as part 0 of every run
# ───────────────────────────────────────────────────────
"""G142 — a rate schedule's VERSION is found in ONE place.

WHAT IT FAILS
-------------
Anywhere under `06-backend/apps`, any of:

  1. `<anything>.TariffVersion.objects` — a direct query of `tariff_versions`;
  2. `apps.get_model("rating", "TariffVersion")` — the same, by name;
  3. `<tariff>.tariffversion_set.<manager method>(…)` — the same, through the
     reverse relation (the FK declares no `related_name`);
  4. a SQL string reading or writing the table (`FROM`/`JOIN`/`UPDATE`/`INTO
     tariff_versions`) — prose that merely names the table is not SQL;

**EXCEPT** in the places that OWN the question:

  * `rating/selectors.py` — `in_force_version` and the reads around it; billing
    reaches it through `pricing_inputs`, which is the seam every billing file
    calls (`gather`, `backbill`, `midperiod`, …);
  * `rating/models.py` — where the model is declared;
  * the SAVE PATHS of `rating/services.py`, by FUNCTION, not the whole file
    (`SAVE_PATHS` below) — a new query anywhere else in that 8,000-line module
    is a finding;
  * `migrations/` and tests, which build their own world.

And the KNOWN readers below, each listed by (file, function) with the reason it
is not a second answer to *"which version prices this date"*. **The list is a
ratchet in both directions:** a NEW site fails, and a listed site that no
longer queries the table fails too, so the list can only shrink by somebody
deleting the line — never by rotting.

⚠ **WHAT IT CANNOT SEE, WITH A NUMBER BESIDE IT (law 7, fifth shape).** A query
built through `getattr`, a variable model or `import_module` is invisible to an
AST; so is a join that reaches `tariff_versions` through another model's
relation (`invoice_lines.tariff_version__…`, which reads the version STAMPED on
an issued line — what priced that bill — and is not a resolution). The gate
prints how many files it read, how many it skipped as owners, and how many
listed readers it matched, every run, so a sudden drop reads as a blind spot.

PROVEN RED FIRST (law 7), THROUGH THE REGISTRY ENTRY THE SUITE CALLS
--------------------------------------------------------------------
A copy of `06-backend/apps` with ONE planted line in `billing/gather.py`
(`models.TariffVersion.objects.filter(tariff=t)`), named by `SBH_G142_APPS`,
answered FAIL through `run_gates.GATES`; the unmodified tree answers PASS — see
`CR-157-BRC10` §6 for both printed lines.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
APPS = Path(os.environ.get("SBH_G142_APPS") or (REPO / "06-backend" / "apps"))

OWNER_FILES = {
    ("rating", "selectors.py"),
    ("rating", "models.py"),
}

#: The functions of `rating/services.py` that WRITE versions, by name.
SAVE_PATHS = {
    "_write_version",  # the one writer every save path calls
    "_lock_schedule",  # CR-157-BRC10 — the row lock every save path takes first
    "duplicate_rate_schedule",  # copies a named version onto a new schedule
    "_apply_batch_to_schedule",  # the bulk rate change (BR-RAT-040)
}

#: `(file relative to apps/, enclosing function) -> why it is not a second
#: answer to "which version prices this date"`. Reviewed for CR-157-BRC10.
KNOWN_READERS: dict[tuple[str, str], str] = {
    ("rating/resolution_catalogue.py", "schedule_version_facts"): (
        "R2 of the ruled resolution chain lists a schedule's live versions and "
        "asks `in_force_on` with the SAME predicate as `in_force_version` "
        "(drafts and superseded rows out, inclusive end — DEF-RAT-8002, "
        "DEF-2889); under rating/0047 at most one matches, and where a legacy "
        "overlap leaves two R2 picks through `resolution.pick_in_force` — the "
        "SAME function `in_force_version` picks through (BR-RAT-1055, "
        "DEF-RAT-8004, PO 2026-10-01 option A), so the two cannot disagree"
    ),
    ("rating/runbook_reads.py", "draft_schedules"): (
        "lists DRAFTS (effective_from IS NULL) for a runbook; a draft prices "
        "nothing (BR-RAT-031)"
    ),
    ("rating/runbook_reads.py", "schedule_change"): (
        "a version NAMED BY ID for a runbook preview, plus the ids of every "
        "version of its schedule so a preview touches only bills stamped with "
        "one of them; the baseline it compares against comes from selectors"
    ),
    ("rating/runbook_reads.py", "reprice_under_draft"): (
        "a draft NAMED BY ID, re-priced in memory for a preview; nothing is "
        "written and no bill is issued (TC-RBS-028.2)"
    ),
    ("rating/rate_schedules_dataset.py", "_base"): (
        "the Reports dataset lists stored versions by effective_from as "
        "history; it prices no bill"
    ),
    ("rating/rate_schedules_dataset.py", "rate_schedules_dataset"): (
        "the same Reports dataset counting drafts so their absence is stated; "
        "prices nothing"
    ),
    ("rating/sample_data.py", "remove_sample_records"): (
        "removes the SAMPLE schedules' versions when a utility clears its "
        "sample data; prices nothing"
    ),
    ("rating/management/commands/migrate_base_to_charge_codes.py", "_service_in_force_base"): (
        "a one-off operator migration REPORT of the retired scalar base "
        "(BR-RAT-088); it takes the newest activated row and prices no bill — "
        "listed as a divergent reader, not endorsed (CR-157-BRC10 §6)"
    ),
    ("rating/management/commands/rat_resolve_schedule_overlap.py", "<module>"): (
        "the operator's overlap-repair command (DEF-RAT-8073): its read-only "
        "SQL finds overlapping windows for a person to decide on"
    ),
    ("rating/management/commands/rat_resolve_schedule_overlap.py", "_resolve"): (
        "the same command's single UPDATE of the window a person chose, after "
        "locking the schedule row first like every save path (CR-157-BRC10)"
    ),
    ("tenancy/management/commands/seed_j72_bulk_run.py", "_version"): (
        "a test-estate seeder (J72 bulk run) writing its own fixture version"
    ),
}

MANAGER_METHODS = {
    "all", "filter", "exclude", "get", "create", "update", "delete", "exists",
    "count", "order_by", "values", "values_list", "first", "last", "bulk_create",
    "get_or_create", "update_or_create", "aggregate", "annotate", "select_for_update",
}
SQL = re.compile(r"\b(FROM|JOIN|UPDATE|INTO)\s+tariff_versions\b", re.I)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _enclosing(tree: ast.AST) -> dict[int, str]:
    """node id -> the name of the OUTERMOST function holding it ('<module>')."""
    owner: dict[int, str] = {}

    def visit(node: ast.AST, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = name
            if name == "<module>" and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = child.name
            owner[id(child)] = inner
            visit(child, inner)

    visit(tree, "<module>")
    return owner


def findings_in(source: str, label: str) -> list[tuple[str, str, int, str]]:
    """`[(label, function, line, what)]` — every direct read of the table."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [(label, "<module>", 0, f"cannot parse ({exc.msg}) — not a pass")]
    docstrings = _docstring_nodes(tree)
    owner = _enclosing(tree)
    out: list[tuple[str, str, int, str]] = []
    for node in ast.walk(tree):
        where = owner.get(id(node), "<module>")
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Attribute):
            if node.attr == "objects" and isinstance(node.value, (ast.Attribute, ast.Name)):
                name = node.value.attr if isinstance(node.value, ast.Attribute) else node.value.id
                if name == "TariffVersion":
                    out.append((label, where, line, "TariffVersion.objects"))
            if (
                node.attr in MANAGER_METHODS
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "tariffversion_set"
            ):
                out.append((label, where, line, f".tariffversion_set.{node.attr}()"))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get_model":
                names = [a.value for a in node.args if isinstance(a, ast.Constant)]
                if "TariffVersion" in names:
                    out.append((label, where, line, "get_model('rating', 'TariffVersion')"))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and SQL.search(node.value)
        ):
            out.append((label, where, line, "raw SQL on tariff_versions"))
    return out


def check(apps: Path = APPS) -> tuple[list[str], list[str], dict[str, int]]:
    """(new findings, stale known entries, counts)."""
    new: list[str] = []
    matched: set[tuple[str, str]] = set()
    counts = {"read": 0, "owners": 0, "tests_or_migrations": 0, "known_hits": 0}
    for path in sorted(apps.rglob("*.py")):
        rel = path.relative_to(apps)
        parts = rel.parts
        if "migrations" in parts or "tests" in parts or parts[-1].startswith("test"):
            counts["tests_or_migrations"] += 1
            continue
        if len(parts) == 2 and (parts[0], parts[1]) in OWNER_FILES:
            counts["owners"] += 1
            continue
        counts["read"] += 1
        rel_s = rel.as_posix()
        for label, where, line, what in findings_in(path.read_text(encoding="utf-8"), rel_s):
            if rel_s == "rating/services.py" and where in SAVE_PATHS:
                continue
            if (rel_s, where) in KNOWN_READERS:
                matched.add((rel_s, where))
                counts["known_hits"] += 1
                continue
            new.append(f"apps/{label}:{line} in {where}(): {what}")
    stale = [f"apps/{f} :: {fn}" for (f, fn) in sorted(set(KNOWN_READERS) - matched)]
    return new, stale, counts


def selftest() -> list[str]:
    """Part 0 of every run: each shape the gate claims to catch, caught."""
    cases = {
        "direct": "def f():\n    return models.TariffVersion.objects.filter(tariff=t)\n",
        "by name": "M = apps.get_model('rating', 'TariffVersion')\n",
        "reverse": "def f(t):\n    return t.tariffversion_set.filter(x=1)\n",
        "raw sql": "def f(c):\n    c.execute('SELECT id FROM tariff_versions WHERE x')\n",
    }
    missed = [name for name, src in cases.items() if not findings_in(src, name)]
    prose = "x = 'a dataset over tariff_versions x {rate_tiers}'\n"
    if findings_in(prose, "prose"):
        missed.append("prose naming the table was read as SQL (false positive)")
    where = findings_in(cases["direct"], "f.py")
    if not where or where[0][1] != "f":
        missed.append("the enclosing function was not named (the save-path scope cannot work)")
    return missed


def run() -> tuple[str, str]:
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    missed = selftest()
    if missed:
        return "FAIL", f"G142's own detector is blind to: {', '.join(missed)}"
    if not APPS.is_dir():
        return "FAIL", f"no apps directory at {APPS} — a gate that read nothing is not a pass"
    new, stale, counts = check()
    seen = (
        f"read {counts['read']} file(s); skipped {counts['owners']} owner file(s) "
        f"(rating/selectors.py, rating/models.py) and {counts['tests_or_migrations']} "
        f"test/migration file(s); {counts['known_hits']} hit(s) on "
        f"{len(KNOWN_READERS) - len(stale)}/{len(KNOWN_READERS)} listed reader(s); "
        "a query through getattr or a variable model is invisible here"
    )
    if new:
        return "FAIL", (
            f"{len(new)} direct tariff_versions read(s) outside rating.selectors and the "
            f"save paths: {new[0]} — ask selectors.in_force_version instead — {seen}"
        )
    if stale:
        return "FAIL", (
            f"{len(stale)} listed reader(s) no longer query the table — delete the line "
            f"from KNOWN_READERS: {stale[0]} — {seen}"
        )
    return "PASS", f"every tariff version is found through rating.selectors — {seen}"


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    if "--list" in sys.argv:
        new, stale, _ = check()
        for line in new:
            print("  NEW   " + line)
        for line in stale:
            print("  STALE " + line)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
