"""G56 — the runtime RLS guard stays wired, and stays fail-closed.

Added 2026-08-31 from `DEF-2717`, with `DEF-2760` beside it.

⚠ **WHAT HAPPENED.** Every bill-run performance figure this repo published was
measured on a database connection that **bypassed row-level security entirely**,
because the benchmark's role had been made SUPERUSER to create a database — one
command, for an unrelated reason, twenty minutes before the first measurement.

**PostgreSQL exempts superusers and `BYPASSRLS` roles from row-level security
unconditionally, `FORCE ROW LEVEL SECURITY` included, and NOTHING SAYS SO.** The
tables still report `relrowsecurity = t` and `relforcerowsecurity = t`. The
policies still exist and still read correctly. Every query still returns
plausible rows. The only difference is that a predicate nobody can see is never
evaluated. Measured on PostgreSQL 16.13, one table, one policy, one
`app.tenant_id`, three roles:

    sbh_proof_app     rolsuper=f rolbypassrls=f  →  2 rows (its own tenant)
    sbh_proof_super   rolsuper=t                 →  3 rows (+ the OTHER tenant's)
    sbh_proof_bypass  rolbypassrls=t             →  3 rows (+ the OTHER tenant's)

It surfaced only because a second tenant reported **73 accounts** inside its own
`tenant_context` when it had none. That is CLAUDE.md hard rule 1 — the FIRST
hard rule in this product — failing silently.

WHY NO EXISTING GATE COULD SEE IT
----------------------------------
**G5 proves the POLICIES EXIST.** It runs its RLS half under a dedicated
`sbh_rls_probe` role (NOLOGIN NOSUPERUSER NOBYPASSRLS) precisely *because* the
app's own role may be a superuser — `06-backend/tests/isolation_helpers.py`
argues that correctly and at length. **And that is exactly the gap:** it proves
the policies are right by asserting under a role that is deliberately NOT the one
the application connects as. Nothing asked whether the RUNNING APPLICATION is
subject to them. Before `core/rls_guard.py`, `rolsuper`/`rolbypassrls` appeared
**zero times** in `06-backend/apps/`, `config/` and `core/` — every occurrence in
the backend was inside a migration docstring or the test helpers.

This is also hard-won law 1 in its purest form: the fact was ALREADY WRITTEN DOWN
in this repo, in a docstring
(`apps/rating/migrations/0023_def652_discount_treatment_after.py`: *"The
development role `smartbillhub` is a SUPERUSER … a superuser bypasses row-level
security entirely"*) — and nothing was built from it for three days.

WHAT THIS GATE ASKS — and what it deliberately does NOT
--------------------------------------------------------
⚠ **IT CANNOT ASK THE ONLY QUESTION THAT FINALLY MATTERS.** No gate in this repo
opens a database, and a merge has no production connection to interrogate. The
runtime answer can only come from the running process, which is why
`06-backend/core/rls_guard.py` exists and why it runs on three boot paths.

So this gate guards the GUARD — hard-won law 2, *built is not wired*, applied to
the one check standing between this product and a silent cross-tenant leak.
Five clauses, each of which has a failure mode someone has already shipped here:

  1. **The guard module exists** and still exports the callables the boot paths
     import by name. A rename that misses a caller is a guard that never runs.
  2. **All three boot paths still call it** — `config/wsgi.py` (whatever starts
     gunicorn), `docker-entrypoint.sh` (readable refusal before `migrate`), and
     `apps/tenancy/apps.py` (the Django system check, so `manage.py migrate`
     asks on every boot). Three callers is not redundancy: an entrypoint is
     bypassed by a `command:` override, and `wsgi.py` is never imported by
     `manage.py`.
  3. **`base.py` still fails closed** — `RLS_ALLOW_BYPASSING_ROLE = False`, so
     every settings module refuses by inheritance (hard-won law 3). This is the
     clause most likely to be "simplified" by a lane fixing something else.
  4. **`production.py` never tolerates a bypass.** The escape hatch belongs in
     `local.py`, where reaching it already costs `DEBUG=True` and
     `ALLOWED_HOSTS=["*"]`.
  5. **No shipped script or compose file grants `BYPASSRLS` or `SUPERUSER` to an
     app role.** The PO ruled this out on 2026-08-24 (OQ-354) and
     `10-scripts/13-provision-database.sh` already refuses the flag by name;
     nothing had ever checked that the refusal survives.

It says nothing about whether any particular deployment is healthy — only that
the thing that WOULD say so is still present, still wired and still fatal by
default.

SELF-TEST — hard-won law 7, proved RED before being trusted green
------------------------------------------------------------------
`run()` builds a synthetic HEALTHY input, asserts it produces no failures, then
breaks it seven ways — one per clause — and asserts each break is caught. If any
sabotage slips through, the gate reports FAIL on ITSELF rather than a comfortable
PASS: a check that cannot fail is worse than no check, because it is trusted, and
this repo has now recorded that five separate times.

⚠ **THE SELF-TEST SABOTAGES A SYNTHETIC INPUT, NOT THE REPO'S OWN TEXT, AND THAT
IS A CORRECTION THIS GATE'S OWN RED PROOF FORCED.** The first draft mutated the
real files' contents. That works only while the repo is healthy: when a clause
was ALREADY broken, its sabotage became a no-op, the bite count fell, and the
gate printed *"SELF-TEST FAILED"* instead of naming the actual problem. The
verdict was still FAIL, so nothing would have shipped — but the sentence sent the
reader to the wrong place, and a gate that misdirects is most of the way to a
gate nobody trusts. Two of the eight RED cases surfaced it.
"""

import re
from pathlib import Path

from common import REPO_ROOT, read_text

BACKEND = REPO_ROOT / "06-backend"

GUARD = BACKEND / "core" / "rls_guard.py"
WSGI = BACKEND / "config" / "wsgi.py"
ENTRYPOINT = BACKEND / "docker-entrypoint.sh"
TENANCY_APPS = BACKEND / "apps" / "tenancy" / "apps.py"
BASE_SETTINGS = BACKEND / "config" / "settings" / "base.py"
PROD_SETTINGS = BACKEND / "config" / "settings" / "production.py"

#: Callables the boot paths import by name. Renaming one without updating every
#: caller is a guard that silently stops running.
REQUIRED_EXPORTS = (
    "def read_runtime_verdict",
    "def enforce_at_startup",
    "def check_runtime_rls_enforcement",
    "def bypass_is_tolerated",
)

#: Files that ship a database role definition. A grant here would undo the guard
#: without touching any of the files above.
GRANT_SCAN = (
    REPO_ROOT / "10-scripts" / "13-provision-database.sh",
    REPO_ROOT / "docker-compose.yml",
    BACKEND / ".env.example",
)

#: ⚠ SCAN STATEMENTS, NOT WORDS. The first draft of this clause matched the bare
#: words and reported SIX findings, every one of them PROSE — the provisioning
#: script argues about `BYPASSRLS` at length precisely because it refuses to grant
#: it. A gate whose output is mostly false positives is a gate the next lane
#: switches off, so this matches only an executable role statement: a
#: CREATE/ALTER ROLE line carrying a GRANTING attribute (`NOSUPERUSER` and
#: `NOBYPASSRLS` contain the shorter words, hence the negative lookbehind), with
#: comment lines excluded outright.
_ROLE_STATEMENT = re.compile(r"\b(CREATE|ALTER)\s+ROLE\b", re.IGNORECASE)
_GRANTS = re.compile(r"(?<!NO)\b(BYPASSRLS|SUPERUSER)\b")
_COMMENT = re.compile(r"^\s*(#|--|//|\*)")


def _clause_failures(
    guard: str,
    wsgi: str,
    entry: str,
    apps: str,
    base: str,
    prod: str,
) -> list[str]:
    """Every clause, over text passed in — so the self-test can sabotage a copy
    instead of the repo (CLAUDE.md law 11 forbids moving the shared tree)."""
    problems: list[str] = []

    # 1 — the module and its exports
    if not guard:
        problems.append(
            "06-backend/core/rls_guard.py is MISSING — nothing asks whether the running "
            "application's own connection obeys row-level security (DEF-2717)"
        )
    else:
        missing = [e for e in REQUIRED_EXPORTS if e not in guard]
        if missing:
            problems.append(
                f"core/rls_guard.py no longer defines {', '.join(m.removeprefix('def ') for m in missing)} "
                f"— a boot path imports each by name, so a rename leaves the guard unwired"
            )

    # 2 — the three boot paths
    if "rls_guard.enforce_at_startup()" not in wsgi:
        problems.append(
            "config/wsgi.py no longer calls rls_guard.enforce_at_startup() — gunicorn is "
            "the one module a `command:` override cannot skip, and it would serve every "
            "request with tenant isolation switched off and no error anywhere"
        )
    if "rls_guard" not in entry:
        problems.append(
            "06-backend/docker-entrypoint.sh no longer runs the RLS check — the container "
            "would boot without the readable refusal that names the role and the fix"
        )
    if "check_runtime_rls_enforcement" not in apps:
        problems.append(
            "apps/tenancy/apps.py no longer registers the RLS system check — `manage.py "
            "migrate` would stop asking on every boot (hard-won law 2)"
        )

    # 3 — fail closed by default
    if "RLS_ALLOW_BYPASSING_ROLE = False" not in base:
        problems.append(
            "config/settings/base.py no longer sets RLS_ALLOW_BYPASSING_ROLE = False — "
            "settings modules stop refusing a bypassing role BY INHERITANCE, and "
            "hard-won law 3 says the unsafe option must be the one somebody types"
        )

    # 4 — production never tolerates it
    if "RLS_ALLOW_BYPASSING_ROLE = True" in prod:
        problems.append(
            "config/settings/production.py tolerates a bypassing role — hard rule 1 would "
            "be unenforced on every request of every tenant, silently. The escape hatch "
            "belongs in local.py, where reaching it already costs DEBUG=True"
        )

    return problems


def _grant_findings() -> list[str]:
    """Clause 5, over the real files — a grant here undoes the guard from outside."""
    findings: list[str] = []
    for path in GRANT_SCAN:
        if not path.exists():
            continue
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            if _COMMENT.match(line):
                continue
            if not _ROLE_STATEMENT.search(line):
                continue
            if not _GRANTS.search(line):
                continue
            try:
                shown = path.relative_to(REPO_ROOT)
            except ValueError:
                # A scanned path outside the repo (a test harness repointing
                # GRANT_SCAN). Report it rather than crashing: a gate that
                # raises counts as FAIL, but with a traceback instead of a
                # sentence, and the sentence is the whole point.
                shown = path
            findings.append(f"{shown}:{lineno}: {line.strip()[:110]}")
    return findings


def run():
    texts = {
        "guard": read_text(GUARD) if GUARD.exists() else "",
        "wsgi": read_text(WSGI) if WSGI.exists() else "",
        "entry": read_text(ENTRYPOINT) if ENTRYPOINT.exists() else "",
        "apps": read_text(TENANCY_APPS) if TENANCY_APPS.exists() else "",
        "base": read_text(BASE_SETTINGS) if BASE_SETTINGS.exists() else "",
        "prod": read_text(PROD_SETTINGS) if PROD_SETTINGS.exists() else "",
    }

    problems = _clause_failures(
        texts["guard"], texts["wsgi"], texts["entry"], texts["apps"], texts["base"], texts["prod"]
    )
    problems.extend(
        f"a shipped file GRANTS a role that bypasses RLS — {f}" for f in _grant_findings()
    )

    # ── self-test (hard-won law 7): break it and prove it bites ──────────────
    # ⚠ SABOTAGE A SYNTHETIC HEALTHY SET, NOT THE REPO'S CURRENT TEXT. The first
    # draft mutated the real files' contents, which works only while the repo is
    # healthy: when a clause was ALREADY broken, that clause's sabotage became a
    # no-op, the bite count fell, and the gate reported SELF-TEST FAILED instead
    # of naming the actual problem. It still failed — but with the wrong sentence,
    # and a gate whose message misdirects the reader is most of the way to a gate
    # nobody trusts. Found by this gate's own RED proof, which is what a RED proof
    # is for.
    healthy = {
        "guard": "\n".join(REQUIRED_EXPORTS),
        "wsgi": "rls_guard.enforce_at_startup()",
        "entry": "rls_guard",
        "apps": "check_runtime_rls_enforcement",
        "base": "RLS_ALLOW_BYPASSING_ROLE = False",
        "prod": "",
    }
    if _clause_failures(**healthy):
        return "FAIL", (
            "SELF-TEST FAILED: a synthetically HEALTHY input still produced clause "
            "failures, so this gate cannot recognise the state it is asking for"
        )

    sabotages = {
        "the guard module deleted": {"guard": ""},
        "enforce_at_startup renamed": {"guard": healthy["guard"].replace("def enforce_at_startup", "def _x")},
        "wsgi.py no longer calling it": {"wsgi": "pass"},
        "the entrypoint check removed": {"entry": ""},
        "the system check unregistered": {"apps": ""},
        "base.py failing OPEN": {"base": "RLS_ALLOW_BYPASSING_ROLE = True"},
        "production.py tolerating a bypass": {"prod": "RLS_ALLOW_BYPASSING_ROLE = True"},
    }
    blind = [name for name, patch in sabotages.items() if not _clause_failures(**{**healthy, **patch})]
    if blind:
        return "FAIL", (
            f"SELF-TEST FAILED: this gate does not bite on {len(blind)} of "
            f"{len(sabotages)} sabotages — {', '.join(blind)}. A check that cannot fail is "
            f"worse than no check, because it is trusted (hard-won law 7)"
        )

    if problems:
        head = problems[0]
        more = f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""
        return "FAIL", f"{head}{more}"

    return "PASS", (
        "the DEF-2717 runtime RLS guard is present, wired into all three boot paths "
        "(wsgi · entrypoint · tenancy system check), fail-closed in base.py, not tolerated "
        f"in production.py, and no shipped file grants SUPERUSER/BYPASSRLS; self-test: all "
        f"{len(sabotages)} sabotages bite"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)
