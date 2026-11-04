#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-021 (🔒, EP-CWP-03) — the session and the account set.
# Defects:  DEF-CWP-3775 — thirteen portal read chains over another module's
#           model name no tenant and rely on RLS alone.
# Rules:    BR-CWP-010 (*"every read and every write is intersected with the
#           session's own account set AND the tenant, IN THE QUERY, never in
#           the screen"*) · CLAUDE.md hard rule 1 (never touch a tenant table
#           without `app.tenant_id`; RLS FORCE is on) · hard-won law 14 (the
#           suite runs on SQLite, so a database-level guarantee is INVISIBLE to
#           every test in this repo) · law 7 (proven RED first, in the harness
#           that will run it)
# Tests:    selftest() below · the ratchet in
#           10-scripts/gates/portal_tenantless_reads.txt
# Impacts:  06-backend/apps/portal/** — every seam, selector and edge
# ───────────────────────────────────────────────────────
"""G96 — a portal read over another module's table NAMES THE TENANT.

WHY THIS GATE EXISTS, AND WHY "RLS ALREADY DOES IT" IS NOT THE ANSWER
---------------------------------------------------------------------
`BR-CWP-010` does not say *the tenant is enforced*. It says **in the query**:

    every read and every write is intersected with the session's own account
    set AND the tenant, IN THE QUERY, never in the screen

Row-level security is real and it is on (`FORCE`), so a chain that omits
`tenant_id` is **not a live exposure today**. This gate is not about today. It
is about the three ways that protection is one ordinary commit from gone:

  1. **The suite cannot see it.** `config/settings/test.py` hardcodes in-memory
     SQLite, which has no RLS at all (hard-won law 14). So a portal read that
     leaks across tenants passes every test in this repository, on every
     machine, forever.
  2. **One `.using()`, one raw query, one management command run as the owner,
     or one table whose policy was never written, and the only guard is gone**
     — silently, because nothing above the database was ever asked to agree.
  3. **A belt-and-braces rule degrades to one strand the moment nobody checks
     the second.** That is what happened here: thirteen chains, written by four
     different lanes across three weeks, every one of them correct-looking.

⚠ **AND THE PORTAL IS THE WRONG SURFACE TO BE RELAXED ON.** The staff app is
reached by people the utility employed; this one is reached by anybody with an
account number and a postcode. A cross-tenant read here is one customer of one
utility reading another utility's customer.

WHAT IT READS
-------------
Every `.py` under `apps/portal/` except migrations, tests and `sample_data.py`
(the fixture seeder, which provisions AS staff and is exempt by name). It walks
each queryset CHAIN with `ast` — not each call, which was the first draft's bug
and would have reported `.filter(tenant_id=…).exclude(…)` as tenant-less — and
asks one question: does ANY link in this chain name a `tenant…` keyword?

Only chains over ANOTHER MODULE's models are checked. `apps/portal`'s own
tables are the portal's to read, and `session.py` re-derives the account set on
every request from a chain that does name the tenant.

THE RATCHET
-----------
`portal_tenantless_reads.txt` lists what was already there when this gate
landed, one `path:line  # why` per row. **It may only ever SHRINK**: a chain
not on the list fails the build, and a listed chain that has been fixed must be
removed from the list or the gate fails for staleness. Two lanes were editing
two of those files when this landed, so the list is a handover rather than a
pardon.

PROVEN RED FIRST (law 7, 2026-09-04)
------------------------------------
Through `run_gates`' own registry path — NOT `python3 g96….py`, which
exercises `__main__` and never the path the suite uses (DEF-GOV-3733). With
`billing_seam.bills_for`'s `tenant_id=tenant_id` removed and the ratchet row
deleted, the registry entry reported

    FAIL: apps/portal/seams/billing_seam.py:257 reads billing_models.Invoice
    without naming a tenant — BR-CWP-010 says IN THE QUERY, and the SQLite
    suite can never see the difference

and green with it restored. `selftest()` replays both directions on in-memory
sources and `run()` refuses to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PORTAL = REPO / "06-backend" / "apps" / "portal"
RATCHET = Path(__file__).resolve().parent / "portal_tenantless_reads.txt"

#: The import aliases every portal file uses for ANOTHER module's models. A
#: chain naming none of these is over the portal's own tables and is not this
#: gate's business.
FOREIGN_MODELS = (
    "customers_models",
    "billing_models",
    "payment_models",
    "payments_models",
    "metering_models",
    "notification_models",
    "notifications_models",
    "assets_models",
    "rating_models",
    "tenancy_models",
    "ledger_models",
)

#: ⚠ EXEMPT BY NAME, NOT BY PATTERN. `sample_data.py` provisions the demo
#: utility AS STAFF through the owning modules' own services; it is already
#: bounded by `write_points.py`'s allowance and by G84.
SKIP_FILES = frozenset({"sample_data.py", "tests.py", "__init__.py"})
SKIP_DIRS = frozenset({"migrations", "management", "__pycache__"})


def tenant_scoped_models(backend: Path) -> set[str]:
    """Model class names that DECLARE a tenant column, read from every
    `apps/*/models.py` with `ast`.

    ⚠ **A TABLE WITH NO TENANT COLUMN IS NOT A TENANT TABLE, AND ASKING FOR
    ONE IS AN ERROR RATHER THAN A TIGHTENING (2026-09-04).** This gate's first
    version assumed every model another module owns is tenant-scoped. It is
    not: `customers.AccountType` is platform-seeded — its own docstring says
    *"identical for every tenant, so NO `tenant_id` and NO RLS"* — and it is
    migrated before any tenant exists. Acting on that false finding raised
    `FieldError: Cannot resolve keyword 'tenant_id' into field` and took SEVEN
    wave-B and wave-C tests red.
    **A gate that reports a fix which breaks the product is worse than no gate,
    because it is trusted — and it was obeyed within the hour.** So the
    question is asked of the SCHEMA now, instead of assumed from the module
    boundary.
    """
    scoped: set[str] = set()
    for path in sorted(backend.glob("apps/*/models.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — another gate's problem
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                targets = (
                    stmt.targets if isinstance(stmt, ast.Assign)
                    else [stmt.target] if isinstance(stmt, ast.AnnAssign)
                    else []
                )
                if any(isinstance(t, ast.Name) and t.id.startswith("tenant") for t in targets):
                    scoped.add(node.name)
                    break
    return scoped


def _chain(node: ast.AST) -> list[ast.Call]:
    """Every call in one queryset chain, outermost first.

    ⚠ **THE CHAIN, NOT THE CALL — this is the whole correctness of the gate.**
    A first draft asked each `.filter()`/`.exclude()` separately and reported
    `filter(tenant_id=…).exclude(status=…)` as a violation, which would have
    filed a defect against `session.py`'s account set, the one query in the
    portal that is most carefully scoped.
    """
    out: list[ast.Call] = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        out.append(node)
        node = node.func.value
    return out


def findings(source: str, *, where: str, scoped: set[str] | None = None) -> list[str]:
    """`path:line  model` for every foreign-model chain naming no tenant.

    `scoped` is the set of model class names that HAVE a tenant column; a chain
    over a model outside it is skipped, because there is no keyword to add.
    """
    out: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover — a broken file is another gate's
        return [f"{where}: will not parse ({exc.msg})"]
    seen: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        calls = _chain(node)
        if not calls:
            continue
        outer = calls[0]
        if id(outer) in seen:
            continue
        text = ast.get_source_segment(source, outer) or ""
        if ".objects." not in text:
            continue
        model = next((m for m in FOREIGN_MODELS if m in text), None)
        if model is None:
            continue
        #: ⚠ A model with NO tenant column is not this gate's business — see
        #: `tenant_scoped_models`. The class name precedes `.objects`.
        if scoped is not None:
            klass = text.split(".objects", 1)[0].rsplit(".", 1)[-1].strip()
            if klass and klass not in scoped:
                for call in calls:
                    seen.add(id(call))
                continue
        #: ⚠ **THE TENANT TABLE IS NOT A TENANT-SCOPED TABLE.** On `tenants`,
        #: `tenant_id` IS the primary key, so `Tenant.objects.filter(pk=…)`
        #: names the tenant as exactly as `filter(tenant_id=…)` does anywhere
        #: else. Reporting it would have sent a lane to "fix" the one query in
        #: `tenancy_seam.branding` that is already correct.
        if model == "tenancy_models" and "Tenant.objects" in text:
            for call in calls:
                seen.add(id(call))
            if any((kw.arg or "") in {"pk", "id"} for call in calls for kw in call.keywords):
                continue
        for call in calls:
            seen.add(id(call))
        named: set[str] = set()
        for call in calls:
            named |= {kw.arg or "" for kw in call.keywords}
        if any(name.startswith("tenant") for name in named):
            continue
        out.append(f"{where}:{outer.lineno}  {model}")
    return out


def _key(finding: str) -> str:
    return finding.split("  ")[0].strip()


def read_ratchet(text: str) -> set[str]:
    rows: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            rows.add(line)
    return rows


def check(
    files: dict[str, str], allowed: set[str], scoped: set[str] | None = None
) -> tuple[list[str], list[str]]:
    """(new violations, stale ratchet rows)."""
    found: list[str] = []
    for where, source in sorted(files.items()):
        found.extend(findings(source, where=where, scoped=scoped))
    keys = {_key(one) for one in found}
    new = [one for one in found if _key(one) not in allowed]
    #: A row whose chain now names the tenant must LEAVE the list. Without
    #: this the ratchet only looks like it is shrinking.
    stale = sorted(allowed - keys)
    return new, stale


CLEAN = (
    "rows = billing_models.Invoice.objects.filter(\n"
    "    tenant_id=tenant_id, account_id__in=ids\n"
    ").exclude(status='draft')\n"
)
RED = (
    "rows = billing_models.Invoice.objects.filter(\n"
    "    account_id__in=ids\n"
    ").exclude(status='draft')\n"
)
#: ⚠ The case the first draft got WRONG — the tenant is named on the first
#: link and the last link has no tenant kwarg at all. It must PASS.
CHAINED = (
    "rows = customers_models.CustomerAccount.objects.filter(\n"
    "    tenant_id=tenant_id, customer_id=customer_id\n"
    ").exclude(account__status__behavior_class='terminal').values_list('account_id')\n"
)
OWN_TABLE = "rows = models.PortalSession.objects.filter(revoked_at__isnull=True)\n"
#: ⚠ **THE CASE THAT COST SEVEN TESTS.** `AccountType` is platform-seeded and
#: carries no tenant column at all, so there is no keyword to add and this must
#: PASS. Reporting it once was enough to break wave B and wave C.
UNSCOPED_MODEL = (
    'rows = customers_models.AccountType.objects.filter(code__iexact="residential")\n'
)
SCOPED = {"Invoice", "CustomerAccount", "Payment", "Premises", "ServiceRequest", "ServicePoint"}


def selftest() -> bool:
    unscoped, _ = check({"a.py": UNSCOPED_MODEL}, set(), SCOPED)
    if unscoped:  # a table with no tenant column is not a finding
        return False
    clean, _ = check({"a.py": CLEAN}, set())
    red, _ = check({"a.py": RED}, set())
    chained, _ = check({"a.py": CHAINED}, set())
    own, _ = check({"a.py": OWN_TABLE}, set())
    pardoned, _ = check({"a.py": RED}, {"a.py:1"})
    _, stale = check({"a.py": CLEAN}, {"a.py:1"})
    return (
        not clean
        and any("billing_models" in one for one in red)
        and not chained  # the chain, not the call
        and not own  # the portal's own table is its own business
        and not pardoned  # the ratchet pardons a listed row
        and stale == ["a.py:1"]  # …and refuses to keep pardoning a fixed one
    )


def run() -> tuple[str, str]:
    if not PORTAL.is_dir():
        return "SKIP", "06-backend/apps/portal is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a tenant-less read from a "
            "scoped one, so its verdict is worthless (DEF-182)"
        )
    files: dict[str, str] = {}
    for path in sorted(PORTAL.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name in SKIP_FILES:
            continue
        files[str(path.relative_to(REPO / "06-backend"))] = path.read_text(encoding="utf-8")
    allowed = read_ratchet(RATCHET.read_text(encoding="utf-8")) if RATCHET.is_file() else set()
    scoped = tenant_scoped_models(REPO / "06-backend")
    if not scoped:  # pragma: no cover — the models are present or the repo is broken
        return "FAIL", "no tenant-scoped model could be read from apps/*/models.py"
    new, stale = check(files, allowed, scoped)
    if new:
        first = new[0]
        return "FAIL", (
            f"{first} without naming a tenant — BR-CWP-010 says IN THE QUERY, and the SQLite "
            f"suite can never see the difference"
            + (f" (+{len(new) - 1} more)" if len(new) > 1 else "")
        )
    if stale:
        return "FAIL", (
            f"{len(stale)} ratchet row(s) now name the tenant and must leave "
            f"portal_tenantless_reads.txt — it may only shrink: {', '.join(stale[:3])}"
        )
    return "PASS", (
        f"{len(files)} portal file(s) read; every queryset over another module's model names the "
        f"tenant, except {len(allowed)} row(s) held in the ratchet (which may only shrink); "
        "self-test: a tenant-less read bites, a chained one does not, the portal's own tables are "
        "its own, and a fixed row cannot stay pardoned"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 0 if status in {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    sys.exit(main())
