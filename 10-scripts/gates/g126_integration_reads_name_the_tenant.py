#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) · CR-110-BRC04 — the partner surface.
# Defects:  DEF-INT-5568 (the access log, PO-reported) · DEF-INT-5569 (the
#           partner grant) · DEF-INT-5570 (the dispatcher's mail seam) ·
#           DEF-INT-5571 (the expiry sweep) — four reads over an
#           integrations tenant table naming neither a tenant nor a row
#           already fetched under one.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE is on; no cross-tenant queryset) ·
#           hard-won law 14 (the suite runs on SQLite, which has no RLS, so a
#           database-level guarantee is INVISIBLE to every test here) · law 7
#           (proved RED first, in the harness that will run it) ·
#           apps/integrations/runners/serve.py `_connection_for` — this
#           module's own written house style: state the tenant TWICE.
# Tests:    selftest() below · 06-backend/tests/test_def_int_5568_partner_tenancy.py
# Impacts:  06-backend/apps/integrations/** · any module reading an
#           integrations tenant table (apps/payments/gateway.py does).
# ───────────────────────────────────────────────────────
"""G126 — a read over an integrations tenant table NAMES THE TENANT.

WHY THIS GATE EXISTS, AND WHY "RLS ALREADY DOES IT" IS NOT THE ANSWER
---------------------------------------------------------------------
`apps/integrations/runners/serve.py::_connection_for` already wrote the rule
down, in this module, in its own words:

    ⚠ THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS NOT OPTIONAL … The
    test suite runs on SQLite, which has no RLS at all … a door that leaked
    across tenants would have passed the whole suite, because the one mechanism
    that would have stopped it does not exist on the vendor the suite runs on.

That paragraph is a comment, and a comment claiming a guarantee is not the
guarantee (hard-won law 1). On 2026-09-17 the module held **78 queryset chains**
over its six tenant tables and **four of them** stated neither a tenant nor a
row already fetched under one — including the access-log read a manager opens to
see who has been reading their utility's payment history.

Measured on a healthy PostgreSQL, those four do NOT leak: RLS `FORCE` scopes
them. This gate is not about that database. It is about the three ways the one
remaining strand goes, silently:

  1. **No test in this repository can see it.** `config/settings/test.py`
     hardcodes in-memory SQLite (law 14), so an unscoped integrations read
     passes the entire suite, on every machine, for ever.
  2. **One `.using()`, one raw query, one command run as a bypassing role, one
     partition minted outside `core.partitioning`, or one policy never written,
     and the only guard is gone** — with nothing above the database ever having
     been asked to agree.
  3. **A belt-and-braces rule degrades to one strand the moment nobody checks
     the second**, which is exactly what happened here: four chains, written by
     different lanes across three waves, every one of them correct-looking.

WHAT IT READS
-------------
Every `.py` under `06-backend/apps/` except migrations, tests and caches. It
walks each queryset CHAIN with `ast` (not each call — `.filter(tenant_id=…)
.exclude(…)` is one chain and names the tenant) and asks one question of the
six tenant tables integrations owns: does any link name a tenant, or narrow by
a ROW that was itself fetched under one?

`integration_key_directory` is NOT in the list and that is deliberate, not an
omission: B2 §3 and `apps/integrations/migrations/0011` declare it RLS-EXEMPT so
a key can be resolved to a utility BEFORE any utility is open. Adding it here
would demand a tenant on the one read that cannot have one.

⚠ **`connection=<row>` COUNTS AND `connection__provider_key=<string>` DOES
NOT**, and that distinction is the whole precision of this gate. A row fetched
under a tenant carries its tenant with it; a provider key is a string every
utility shares. The four sites this gate was written for include
`IntegrationRun.objects.filter(connection__provider_key=key, direction=…)`,
which reads at a glance as though the connection scopes it. Membership is
therefore EXACT, never a prefix match.

ZERO TOLERANCE, NO RATCHET
--------------------------
G96 (the portal's version of this question) carries a ratchet because it landed
over thirteen live chains two lanes were mid-edit on. This one landed with all
four fixed in the same commit, so there is nothing to hand over and a list would
only be a place for a fifth to be parked. A genuine exception — a sweep that is
SUPPOSED to walk every utility — goes in `ALLOWED` below, BY NAME, with the
reason beside it, and is read by a person at review.

PROVEN RED FIRST (law 7), THROUGH `run_gates`' REGISTRY PATH AND NOT
`python3 g126….py` (DEF-GOV-3733). On the tree before the fix it reported

    FAIL: apps/integrations/partner_api.py:1264 reads IntegrationRun naming
    neither a tenant nor a row fetched under one — hard rule 1 says IN THE
    QUERY too, and the SQLite suite can never see the difference (+3 more)

and PASS with the four `tenant_id=` keywords added. `selftest()` replays both
directions plus the four ways this gate could pass wrongly, and `run()` refuses
to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APPS = REPO / "06-backend" / "apps"

#: The six tenant tables `apps/integrations` owns — the set
#: `migrations/0002_rls_force.py` and `0009` put under ENABLE + FORCE.
#: `IntegrationKeyDirectory` is deliberately absent (migration 0011: it is the
#: RLS-exempt signpost read BEFORE a utility is open).
TENANT_MODELS = frozenset(
    {
        "IntegrationConnection",
        "IntegrationCredential",
        "IntegrationRun",
        "IntegrationTargetReference",
        "IntegrationConsent",
        "IntegrationRateLimit",
    }
)

#: Naming the tenant outright. Prefix match, because `tenant`, `tenant_id`,
#: `tenant__subdomain` and `tenant_id__in` all state it.
TENANT_PREFIX = "tenant"

#: Narrowing by a row that was itself fetched under a tenant, or by this row's
#: own primary key. ⚠ EXACT membership — `connection__provider_key` is a string
#: every utility shares and must NOT satisfy this gate.
IDENTITY = frozenset(
    {
        "pk",
        "id",
        "pk__in",
        "id__in",
        "connection",
        "connection_id",
        "connection__in",
        "connection_id__in",
        "credential",
        "credential_id",
        "run",
        "run_id",
    }
)

#: Genuine exceptions, BY NAME with the reason. Empty on the day this landed,
#: and a row here is read by a human at review rather than by this gate.
ALLOWED: dict[str, str] = {}

SKIP_DIRS = frozenset({"migrations", "__pycache__", "tests"})
SKIP_FILES = frozenset({"__init__.py"})

#: Calls that can carry a narrowing keyword. `.first()`, `.count()` and friends
#: are links in a chain, never the thing that scopes it.
QUERY_CALLS = frozenset(
    {
        "filter",
        "exclude",
        "get",
        "get_or_create",
        "update_or_create",
        "create",
        "aggregate",
        "annotate",
    }
)


def _chain(node: ast.AST) -> list[ast.Call]:
    """Every call in one queryset chain, outermost first.

    ⚠ **THE CHAIN, NOT THE CALL.** `.filter(tenant_id=…).exclude(status=…)` is
    one statement about one queryset and it names the tenant; asking each call
    separately would report the most carefully scoped reads in the module.
    """
    out: list[ast.Call] = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        out.append(node)
        node = node.func.value
    return out


def _model_of(node: ast.AST) -> str | None:
    """The model class name behind `.objects`, or None when this is not one.

    Read from the AST rather than from the source text, so `models.Integration
    Run.objects`, `integration_models.IntegrationRun.objects` and a bare
    `IntegrationRun.objects` all answer the same thing.
    """
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        node = node.func.value
    if not (isinstance(node, ast.Attribute) and node.attr == "objects"):
        return None
    owner = node.value
    if isinstance(owner, ast.Name):
        return owner.id
    if isinstance(owner, ast.Attribute):
        return owner.attr
    return None


def findings(source: str, *, where: str) -> list[str]:
    """`path:line  Model` for every integrations chain that scopes itself by
    neither a tenant nor a row already fetched under one."""
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
        model = _model_of(outer)
        if model not in TENANT_MODELS:
            continue
        for call in calls:
            seen.add(id(call))
        named: set[str] = set()
        for call in calls:
            if call.func.attr not in QUERY_CALLS:  # type: ignore[union-attr]
                continue
            named |= {kw.arg or "" for kw in call.keywords}
        if any(name.startswith(TENANT_PREFIX) for name in named):
            continue
        if named & IDENTITY:
            continue
        out.append(f"{where}:{outer.lineno}  {model}")
    return out


def _key(finding: str) -> str:
    return finding.split("  ")[0].strip()


def check(files: dict[str, str]) -> list[str]:
    found: list[str] = []
    for where, source in sorted(files.items()):
        found.extend(findings(source, where=where))
    return [one for one in found if _key(one) not in ALLOWED]


# ── the self-test's sources: one per way this gate could be wrong ───────────
CLEAN = (
    "rows = models.IntegrationRun.objects.filter(\n"
    "    tenant_id=tenant_id, connection__provider_key=key\n"
    ").order_by('-started_at')\n"
)
#: The site this gate was written for, verbatim in shape.
RED = (
    "rows = models.IntegrationRun.objects.filter(\n"
    "    connection__provider_key=key, direction=models.RUN_DIRECTION_INBOUND_READ\n"
    ")\n"
)
#: The tenant on the FIRST link and nothing on the last — must PASS.
CHAINED = (
    "rows = models.IntegrationCredential.objects.filter(\n"
    "    tenant_id=tenant_id, is_active=True\n"
    ").select_related('connection').order_by('created_at')\n"
)
#: A row already fetched under a tenant carries its tenant — must PASS.
BY_ROW = "rows = models.IntegrationCredential.objects.filter(connection=connection, is_active=True)\n"
#: ⚠ THE FALSE PASS THIS GATE IS MOST LIKELY TO HAVE: a prefix match on
#: `connection` would pardon the exact chain above. It must still FAIL.
LOOKS_LIKE_A_ROW = "rows = models.IntegrationConnection.objects.filter(provider_key=key).first()\n"
#: The RLS-EXEMPT signpost — there is no tenant to name and demanding one would
#: break the partner door. Must PASS.
DIRECTORY = (
    "found = models.IntegrationKeyDirectory.objects.filter(blind_index__in=candidates).first()\n"
)
#: Another module's model of the same shape is not this gate's business.
FOREIGN = "rows = billing_models.Invoice.objects.filter(status='issued')\n"


def selftest() -> bool:
    clean = check({"a.py": CLEAN})
    red = check({"a.py": RED})
    chained = check({"a.py": CHAINED})
    by_row = check({"a.py": BY_ROW})
    looks = check({"a.py": LOOKS_LIKE_A_ROW})
    directory = check({"a.py": DIRECTORY})
    foreign = check({"a.py": FOREIGN})
    return (
        not clean
        and any("IntegrationRun" in one for one in red)
        and not chained  # the chain, not the call
        and not by_row  # a fetched row carries its tenant
        and any("IntegrationConnection" in one for one in looks)  # prefix match would miss this
        and not directory  # the RLS-exempt table has no tenant to name
        and not foreign  # another module's table is another gate's business
    )


def run() -> tuple[str, str]:
    if not APPS.is_dir():
        return "SKIP", "06-backend/apps is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a tenant-less "
            "integrations read from a scoped one, so its verdict is worthless (DEF-182)"
        )
    files: dict[str, str] = {}
    for path in sorted(APPS.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name in SKIP_FILES:
            continue
        files[str(path.relative_to(REPO / "06-backend"))] = path.read_text(encoding="utf-8")
    new = check(files)
    if new:
        first = new[0]
        return "FAIL", (
            f"{first} naming neither a tenant nor a row fetched under one — hard rule 1 says "
            f"IN THE QUERY too, and the SQLite suite can never see the difference"
            + (f" (+{len(new) - 1} more: {', '.join(_key(one) for one in new[1:4])})" if len(new) > 1 else "")
        )
    chains = sum(len(findings(src, where=where)) for where, src in files.items())
    return "PASS", (
        f"{len(files)} app file(s) read; every queryset over the six integrations tenant tables "
        f"names a tenant or a row fetched under one ({chains} unscoped, "
        f"{len(ALLOWED)} allowed by name); self-test: a tenant-less read bites, a chained one "
        "does not, `connection=<row>` passes and `connection__provider_key=<string>` does not, "
        "and the RLS-exempt key directory is not asked for a tenant"
    )


if __name__ == "__main__":  # pragma: no cover
    verdict, detail = run()
    print(f"{verdict}: {detail}")
    sys.exit(0 if verdict in {"PASS", "SKIP"} else 1)
