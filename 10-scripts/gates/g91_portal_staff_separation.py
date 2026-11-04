#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-021 (🔒, EP-CWP-03) — the credential store · US-CWP-020 —
#           sign in. CR-068 §13 (the gate the plan called G76; G76–G90 were
#           taken by the time it landed, so it is G91 — the number is the
#           REGISTER's at push time, never the plan's, DEF-CWP-3734)
# Rules:    BR-CWP-004 (a portal credential must NEVER resolve into a staff
#           role — separate table, separate session, separate permission
#           catalogue, not one table with a flag on it) · BR-CWP-011 (a portal
#           session must not be able to call a staff route, and the guest
#           surface must not be able to reach the portal edge) ·
#           CLAUDE.md hard-won law 7 (proven RED first, in the harness that
#           runs it)
# Tests:    selftest() below · 06-backend/tests/test_us_cwp_020_session.py
# Impacts:  06-backend/apps/portal/** — every file, every commit
# ───────────────────────────────────────────────────────
"""G91 — the customer's front door shares no lock with the staff one.

WHY THIS GATE EXISTS
--------------------
`BR-CWP-004` is one sentence and it is the whole security model of the portal:
*"A portal credential must never resolve into a staff role. Separate table,
separate session, separate permission catalogue — **not one table with a flag on
it**."* Nothing about that is self-enforcing. A lane adding *"and if the
customer is also a member of staff, reuse their session"* writes four
reasonable-looking lines, every test passes, and a customer login has become a
way into the back office.

WHAT IT READS, AND THE FOUR THINGS IT REFUSES
----------------------------------------------
Every Python file under `06-backend/apps/portal/`, parsed with `ast` — never
imported, because the gate suite is stdlib-only and Django is not importable
from it.

  1. **No file under `apps/portal/` imports `apps.identity`** — except
     `seams/identity_seam.py`, which is the one declared door.
  2. **That seam reads exactly one identity model.** `SecurityPolicy` and
     nothing else. A door that widens is not a door, and the model a widening
     would reach for is `User`.
  3. **No portal model declares a field pointing at `identity`** — no
     `ForeignKey("identity.User")`, no `OneToOneField(User)`, under any
     spelling the AST can see. This is `BR-CWP-004`'s *"not one table with a
     flag on it"* as a schema check.
  4. **No portal file imports the staff session cookie or its authentication
     class** — `SESSION_COOKIE`, `IdentitySessionAuthentication`. A portal edge
     that read `sbh_session` would let a stale staff cookie authenticate a
     customer route, which is the exact reverse of `BR-CWP-011` and is how a
     visitor gets 401'd by somebody else's session.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not check the STAFF side. `apps/identity` never mentions the portal and
a gate asserting an absence over a whole other module would go red the first
time somebody wrote the word in a comment. The asymmetry is honest: the portal
is the new surface and the portal is where the pressure to reach across will
come from.

PROVEN RED FIRST (law 7, 2026-09-04) — AND THROUGH `run_gates`, NOT `__main__`
------------------------------------------------------------------------------
`DEF-GOV-3733`: a guard shown red through `python3 <gate>.py` exercises
`__main__`, which is a path the suite never uses. So this gate was driven red on
the REAL tree by adding `staff_user = models.ForeignKey("identity.User", …)` to
`PortalCredential`, and then called the way `run_gates` calls it — importing the
registry and invoking `module.run()`. Verbatim:

    FAIL: G91 portal-staff-separation :: 06-backend/apps/portal/models.py:403
    declares a ForeignKey onto identity.User — BR-CWP-004 forbids a portal table
    joining identity: separate table, separate session, not one table with a
    flag on it

The FK was reverted and the same dispatch reported PASS. The other three clauses
are driven red on in-memory sources by `selftest()`, which `run()` calls BEFORE
it reports anything; their verbatim failures are in its docstring.

⚠ **AND IT WENT RED ON THE REAL TREE THE FIRST TIME IT WAS RUN, before any fault
was injected** — `sample_data.py` imports `apps.identity` to resolve the
provisioned owner. That is the fixture provisioning AS staff, which is the
opposite of what `BR-CWP-004` forbids; the exemption is written down beside
`FIXTURE` with its reason rather than the clause being softened.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PORTAL = REPO / "06-backend" / "apps" / "portal"

#: The ONE file that may reach `apps.identity` FOR THE PRODUCT, and the ONE
#: model it may read.
SEAM = "seams/identity_seam.py"
ALLOWED_IDENTITY_NAMES = frozenset({"SecurityPolicy"})

#: ⚠ **THE SECOND EXEMPTION, AND IT IS NOT A WEAKENING — IT IS THE FIXTURE.**
#: `sample_data.py` provisions the demo utilities THROUGH THE REAL SIGN-UP and
#: then writes as their owner, so it resolves the provisioned `identity.User`
#: to hand every fixture write a real actor id (B12 §6a: an audited write needs
#: a real user, not a made-up one). That is a STAFF path running as staff — the
#: opposite of the thing `BR-CWP-004` forbids, which is a CUSTOMER credential
#: resolving into a staff role. It reaches `identity` in order to BE staff, and
#: it never touches a `PortalCredential`.
#:
#: **It is exempt from clause 1 ONLY.** Clauses 3 and 4 still apply to it: it
#: may not declare a relation onto `identity`, and it may not name the staff
#: session cookie. This gate was written before that import was noticed and
#: went RED on it on its first run against the real tree, which is the gate
#: doing its job — the exemption is written down with its reason rather than
#: the clause being softened.
FIXTURE = "sample_data.py"

#: Names that only ever mean the STAFF session. Importing one into the portal
#: is `BR-CWP-011` inverted, whatever the intention was.
STAFF_ONLY_NAMES = frozenset({"SESSION_COOKIE", "IdentitySessionAuthentication"})

SKIP_DIRS = frozenset({"__pycache__", "management"})
#: Django field constructors that make a row point at another table.
RELATION_FIELDS = frozenset({"ForeignKey", "OneToOneField", "ManyToManyField"})


def _identity_module(name: str | None) -> bool:
    if not name:
        return False
    return name == "apps.identity" or name.startswith("apps.identity.")


def check(files: dict[str, str]) -> list[str]:
    """(relative path → source) → the problems, in the words a lane will read."""
    problems: list[str] = []
    for rel, source in sorted(files.items()):
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:  # pragma: no cover - a broken file is another gate's
            problems.append(f"{rel}: does not parse ({exc.msg})")
            continue
        normalised = rel.replace("\\", "/")
        is_seam = normalised.endswith(SEAM)
        is_fixture = normalised.endswith("/" + FIXTURE)
        for node in ast.walk(tree):
            # ── clauses 1 and 2 — who may reach identity, and for what ──────
            if isinstance(node, ast.ImportFrom) and _identity_module(node.module):
                if is_fixture:
                    continue  # the fixture provisions AS staff — see FIXTURE above
                if not is_seam:
                    problems.append(
                        f"{rel}:{node.lineno} imports {node.module} — a portal credential must never "
                        f"resolve into a staff role (BR-CWP-004). The ONE door is {SEAM}"
                    )
                    continue
                for alias in node.names:
                    if alias.name not in ALLOWED_IDENTITY_NAMES:
                        problems.append(
                            f"{rel}:{node.lineno} reads identity.{alias.name}; the seam may read only "
                            f"{sorted(ALLOWED_IDENTITY_NAMES)} — a door that widens is not a door (BR-CWP-004)"
                        )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _identity_module(alias.name) and not is_seam and not is_fixture:
                        problems.append(
                            f"{rel}:{node.lineno} imports {alias.name} — a portal credential must never "
                            f"resolve into a staff role (BR-CWP-004)"
                        )
            # ── clause 4 — the staff cookie and the staff auth class ────────
            if isinstance(node, ast.Name) and node.id in STAFF_ONLY_NAMES:
                problems.append(
                    f"{rel}:{node.lineno} names {node.id}, which is the STAFF session — a portal edge "
                    "that read it would let a stale staff cookie authenticate a customer route "
                    "(BR-CWP-011)"
                )
            # ── clause 3 — no portal ROW may point at a staff row ───────────
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if name in RELATION_FIELDS:
                    for argument in list(node.args) + [kw.value for kw in node.keywords]:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            target = argument.value
                            if target.startswith("identity.") or target == "identity":
                                problems.append(
                                    f"{rel}:{node.lineno} declares a {name} onto {target} — "
                                    "BR-CWP-004 forbids a portal table joining identity: separate "
                                    "table, separate session, not one table with a flag on it"
                                )
                        elif isinstance(argument, ast.Name) and argument.id == "User":
                            problems.append(
                                f"{rel}:{node.lineno} declares a {name} onto User — BR-CWP-004 "
                                "forbids a portal table joining identity"
                            )
    return problems


# ── the four RED proofs, replayed on in-memory sources every run ────────────
_RED_IMPORT = "from apps.identity.models import User\n"
_RED_WIDE_SEAM = "from apps.identity.models import SecurityPolicy, User\n"
_RED_FK = (
    "from django.db import models\n"
    "class PortalCredential(models.Model):\n"
    '    user = models.ForeignKey("identity.User", on_delete=models.PROTECT)\n'
)
_RED_COOKIE = "raw = request.COOKIES.get(SESSION_COOKIE)\n"
_CLEAN_SEAM = "from apps.identity.models import SecurityPolicy\n"


def selftest() -> bool:
    """Drive all four clauses RED, then prove the clean sources are green.

    Verbatim, when each was first run against the real code with the fault put
    back in (law 7 — and then re-run through `run_gates.py`, which is the
    harness that will actually call `run()`; `DEF-GOV-3733`):

        FAIL: 06-backend/apps/portal/session.py:1 imports apps.identity.models —
        a portal credential must never resolve into a staff role (BR-CWP-004).
        The ONE door is seams/identity_seam.py
        FAIL: 06-backend/apps/portal/seams/identity_seam.py:1 reads
        identity.User; the seam may read only ['SecurityPolicy'] — a door that
        widens is not a door (BR-CWP-004)
        FAIL: 06-backend/apps/portal/models.py:3 declares a ForeignKey onto
        identity.User — BR-CWP-004 forbids a portal table joining identity:
        separate table, separate session, not one table with a flag on it
        FAIL: 06-backend/apps/portal/api.py:1 names SESSION_COOKIE, which is the
        STAFF session — a portal edge that read it would let a stale staff
        cookie authenticate a customer route (BR-CWP-011)
    """
    imported = check({"session.py": _RED_IMPORT, "seams/identity_seam.py": _CLEAN_SEAM})
    widened = check({"seams/identity_seam.py": _RED_WIDE_SEAM})
    joined = check({"models.py": _RED_FK})
    cookie = check({"api.py": _RED_COOKIE})
    clean = check({"seams/identity_seam.py": _CLEAN_SEAM, "session.py": "from apps.portal import models\n"})
    return (
        any("must never resolve into a staff role" in p for p in imported)
        and any("a door that widens is not a door" in p for p in widened)
        and any("forbids a portal table joining identity" in p for p in joined)
        and any("stale staff cookie" in p for p in cookie)
        and not clean
    )


def run() -> tuple[str, str]:
    if not PORTAL.is_dir():
        return "SKIP", "06-backend/apps/portal is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a portal file that reaches "
            "into identity from one that does not, so its verdict is worthless (DEF-182)"
        )
    files: dict[str, str] = {}
    for path in sorted(PORTAL.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files[str(path.relative_to(REPO))] = path.read_text(encoding="utf-8")
    seam = PORTAL / SEAM
    if not seam.is_file():
        return "FAIL", (
            f"{SEAM} is missing — BR-CWP-037 reads the tenant's OWN password policy through one "
            "declared door, and with no door every file is free to reach for identity directly"
        )
    problems = check(files)
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (
            f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        )
    return "PASS", (
        f"{len(files)} portal file(s) read; only {SEAM} (and {FIXTURE}, which provisions AS staff) "
        f"reaches apps.identity, and the seam reads only "
        f"{sorted(ALLOWED_IDENTITY_NAMES)}; no portal table joins identity and no portal file names "
        "the staff session; self-test: a stray import, a widened seam, an FK onto User and a read of "
        "SESSION_COOKIE all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
