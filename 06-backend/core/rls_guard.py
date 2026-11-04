# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2717 (2026-08-31) — every published CR-051 bill-run figure was
#           measured on a connection that BYPASSED row-level security, because
#           the benchmark's role had been made SUPERUSER to create a database.
#           DEF-2760 (2026-08-31) — the repo does not record which role a
#           deployment connects as, so no reader can tell whether hard rule 1
#           is enforced on any running environment.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on) ·
#           hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee) · hard-won law 3 (defaults fail closed) ·
#           hard-won law 2 (built is not wired).
# Contract: B2 §3 — ENABLE + FORCE ROW LEVEL SECURITY with
#           USING/WITH CHECK (tenant_id = NULLIF(current_setting(
#           'app.tenant_id', true), '')::uuid) on every tenant table.
# Tests:    06-backend/tests/test_def2717_rls_runtime_guard.py
# Gate:     10-scripts/gates/g56_rls_runtime_guard.py (this file must stay wired)
# ───────────────────────────────────────────────────────
"""Does THIS process's own database connection actually obey row-level security?

HUMAN-OWNED — RLS is a CLAUDE.md 🔒 sensitive path.

HUMAN-REVIEW-PENDING — AI-authored 2026-08-31 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.
⚠ CORRECTED 2026-09-01 (DEF-2791) — THE SENTENCE BELOW IS HISTORY, NOT THE
CURRENT STATE. The request was granted: `human_owned.txt` carries
`06-backend/core/rls_guard.py` under GROUP FOUR ("one utility seeing another
utility's records"), so G7 reads the two markers above. It was one of the three
files G53 was left RED on when the 56-path block landed on 2026-08-31, and it
joined the list after. **Do not re-raise it and do not put it back to the PO
(law 13).** Kept because why it went unguarded is worth knowing.

⚠ No glob in `10-scripts/gates/human_owned.txt` matches this path yet. A lane may
not add itself to that list — the file's own header calls editing it a process
event — so the glob is REQUESTED in the ledger row, not taken here.

THE PROBLEM THIS EXISTS FOR, STATED AS A MEASUREMENT
-----------------------------------------------------
**PostgreSQL exempts superusers and `BYPASSRLS` roles from row-level security
unconditionally — `FORCE ROW LEVEL SECURITY` included — and NOTHING SAYS SO.**

Measured here, PostgreSQL 16.13, 2026-08-31, on one table carrying the B2 §3
policy above with `relrowsecurity = t` and `relforcerowsecurity = t` throughout,
three rows in it, two tenants, the SAME `app.tenant_id` set on every connection:

    role               rolsuper  rolbypassrls   rows returned
    sbh_proof_app      f         f              2   ← its own tenant's rows
    sbh_proof_super    t         f              3   ← + the OTHER tenant's row
    sbh_proof_bypass   f         t              3   ← + the OTHER tenant's row

Nothing observable distinguishes the healthy case from the broken one. The
tables still report `ENABLE` and `FORCE`. The policies still exist and still
read correctly. Every query still returns plausible rows in a plausible shape.
The only difference is that **a predicate nobody can see is never evaluated.**

That is CLAUDE.md hard rule 1 — the first hard rule in this product — failing
silently, which is the one failure a multi-tenant billing system cannot have.
DEF-2717 found it only by accident: a second tenant reported **73 accounts**
inside its own `tenant_context` when it had none. The count was the *other*
tenant's.

WHY A COMMENT, A POLICY AND A TEST SUITE ARE ALL INSUFFICIENT — hard-won law 1
------------------------------------------------------------------------------
This exact fact was already written down in this repo, in a docstring, and
nothing was built from it:

    apps/rating/migrations/0023_def652_discount_treatment_after.py
    "The development role `smartbillhub` is a SUPERUSER (`pg_roles.rolsuper =
     t`), and a superuser bypasses row-level security entirely — so on the box
     this was built on the unscoped update would have 'worked' and told us
     nothing."

and again in `tests/isolation_helpers.py`, which reacted correctly *for the
tests* by running its RLS assertions under a dedicated `sbh_rls_probe` role
(NOLOGIN NOSUPERUSER NOBYPASSRLS) and re-reading `pg_roles` at runtime.

⚠ **AND THAT IS PRECISELY THE GAP.** The isolation suite proves the POLICIES
EXIST. It cannot prove **the running application is subject to them**, because
it deliberately asserts under a role that is *not* the one the application
connects as. Before this file, `rolsuper`/`rolbypassrls` appeared **zero times**
in `apps/`, `config/` and `core/` — every occurrence in the backend was inside a
migration docstring or the test helpers. The product never asked the question
about itself.

WHY THIS REFUSES TO BOOT WHERE THE OTHER TWO BOOT CHECKS ONLY WARN
-------------------------------------------------------------------
`docker-entrypoint.sh` carries two older boot checks and BOTH deliberately warn
rather than refuse. Each records its reason, and neither reason holds here:

  * **ALLOWED_HOSTS** warns because running production settings against
    localhost is legitimate — that is `make up`, and refusing would break it.
  * **app.tenant_id** warns because an already-migrated database is unaffected;
    refusing would take a working production down for a setting it does not
    need at that moment.

**A bypassing role has no legitimate production use at all.** It is not a
setting that is wrong for one command and right for the next: for as long as the
process runs, every query from every request for every tenant is unfiltered, and
the failure is invisible by construction — no log line, no error, no wrong-
looking row. Serving is strictly worse than not serving, because the product
keeps answering and quietly mixes tenants' data. So this one is fatal, and
hard-won law 3 decides the direction: **the unsafe option must be the one you
type.**

The escape hatch follows the convention this repo already uses twice for exactly
this shape — `FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS` and
`DOCUMENT_STORAGE_ALLOW_FILESYSTEM`. `base.py` leaves the allow-flag **False**,
so every settings module fails closed by inheritance, and `config/settings/
local.py` types **True** with its reason. A developer whose local role is a
superuser is a legitimate, convenient and common case; getting that tolerance
requires typing `DJANGO_SETTINGS_MODULE=config.settings.local`, which already
means `DEBUG=True` and `ALLOWED_HOSTS=["*"]`. It cannot be reached by accident
from a deployment, and even then this module still prints one loud line per
boot, because a tolerated bypass that goes silent is how DEF-2717 happened.

WHAT IT DOES NOT DO, AND WHY — read before "improving" it
----------------------------------------------------------
* **It does not fail when the database is unreachable.** It cannot distinguish
  a down database from a hostile one, and turning a transient outage into a
  refusal to boot would be a self-inflicted incident. `migrate` and the first
  request report the real connection error; this returns UNREACHABLE and says
  so. A check that fails on the wrong condition gets disabled by the next lane.
* **It does not fail on a non-PostgreSQL vendor.** SQLite has no row-level
  security at all, so there is nothing to bypass and nothing to assert
  (CLAUDE.md law 14: `config/settings/test.py` hardcodes in-memory SQLite and
  ignores `DATABASE_URL`). It returns NOT_APPLICABLE **by name** rather than a
  bare False, so a caller can never mistake "no RLS here" for "RLS is fine
  here" — that mistake is the whole defect, one layer up.
* **It reads `pg_roles` for `current_user`, not for a configured role name.**
  The question is what THIS connection can do, and the answer must come from
  the database rather than from a setting anyone could have edited — hard-won
  law 1. `current_user` is also what PostgreSQL itself evaluates the exemption
  against, so it is the same subject, not a proxy for it.
* **It checks membership too, not just the role's own attributes.** `rolsuper`
  and `rolbypassrls` are NOT inherited through role membership for the bypass
  decision — PostgreSQL evaluates the *current* role — but a role that is a
  member of a superuser role can `SET ROLE` to it, so the connection is one
  statement away from a bypass. That is reported as a WARNING, never as a
  refusal, because it is a weaker fact and refusing on it would fail the RDS
  master-user case the runbook (09-infra/02 §8.0) blesses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

#: Set this to tolerate a bypassing role where the settings module would
#: otherwise refuse. Hard-won law 3 — the unsafe option is the one you type.
#: It is read from the environment as well as from settings so that a live
#: incident can be unblocked without a redeploy; both are printed when used.
BYPASS_ESCAPE_HATCH_ENV = "SBH_ALLOW_RLS_BYPASSING_ROLE"

#: Settings flag, default False in `base.py`, True in `config/settings/local.py`.
#: Same shape as FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS / DOCUMENT_STORAGE_ALLOW_FILESYSTEM.
BYPASS_ALLOW_SETTING = "RLS_ALLOW_BYPASSING_ROLE"

#: ⚠ `DEF-TEN-9794` (2026-10-06) — under THIS settings module neither escape
#: hatch is honoured. Production showed another utility's charge codes inside
#: one utility (`DEF-RAT-9791`); the two ways that happens are a role that
#: bypasses RLS or a table that lost its policy, and the hatch made the first
#: one a matter of one environment variable. Law 3: the production module fails
#: closed, and there is no word to type that opens it.
PRODUCTION_SETTINGS_MODULE = "config.settings.production"


class RlsRuntimeStatus(str, Enum):
    """What we were able to establish about THIS connection.

    Four states, not two. `NOT_APPLICABLE` and `UNREACHABLE` exist so that
    "we could not tell" can never be rendered as "it is fine" — that
    conflation is DEF-2717's mechanism reproduced one layer up.
    """

    ENFORCED = "ENFORCED"
    BYPASSED = "BYPASSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNREACHABLE = "UNREACHABLE"


@dataclass(frozen=True)
class RlsRuntimeVerdict:
    """The answer, plus everything a human needs to act on it."""

    status: RlsRuntimeStatus
    role: str | None = None
    rolsuper: bool | None = None
    rolbypassrls: bool | None = None
    vendor: str | None = None
    #: Superuser/BYPASSRLS roles this role is a MEMBER of — one `SET ROLE`
    #: away from a bypass. A warning, never a refusal (see module docstring).
    bypassing_memberships: tuple[str, ...] = ()
    detail: str = ""

    @property
    def bypasses(self) -> bool:
        return self.status is RlsRuntimeStatus.BYPASSED

    def one_line(self) -> str:
        """The single line every caller prints. Always names the role."""
        if self.status is RlsRuntimeStatus.BYPASSED:
            reasons = []
            if self.rolsuper:
                reasons.append("rolsuper=t")
            if self.rolbypassrls:
                reasons.append("rolbypassrls=t")
            return (
                f"RLS IS NOT ENFORCED on this connection: role {self.role!r} has "
                f"{' and '.join(reasons)} — every tenant policy is skipped for every "
                f"query this process makes (CLAUDE.md hard rule 1)."
            )
        if self.status is RlsRuntimeStatus.ENFORCED:
            extra = ""
            if self.bypassing_memberships:
                extra = (
                    f" ⚠ but it is a member of {', '.join(self.bypassing_memberships)}, "
                    f"so `SET ROLE` reaches a bypass in one statement."
                )
            return (
                f"RLS is enforced on this connection: role {self.role!r} has "
                f"rolsuper=f rolbypassrls=f.{extra}"
            )
        if self.status is RlsRuntimeStatus.NOT_APPLICABLE:
            return (
                f"RLS enforcement NOT CHECKED: database vendor is {self.vendor!r}, which "
                f"has no row-level security. This is not a pass — nothing was proved."
            )
        return (
            f"RLS enforcement UNKNOWN: {self.detail} — the database could not be "
            f"asked. This is not a pass; nothing was proved."
        )


# The one query. `current_user` is the subject PostgreSQL itself evaluates the
# RLS exemption against, so this asks about exactly the right role rather than
# about a role name someone configured.
_ROLE_QUERY = """
SELECT r.rolname, r.rolsuper, r.rolbypassrls,
       COALESCE(
         ARRAY(
           SELECT m.rolname
           FROM pg_auth_members am
           JOIN pg_roles m ON m.oid = am.roleid
           WHERE am.member = r.oid AND (m.rolsuper OR m.rolbypassrls)
           ORDER BY m.rolname
         ),
         '{}'
       )
FROM pg_roles r
WHERE r.rolname = CURRENT_USER
"""


def read_runtime_verdict(connection=None) -> RlsRuntimeVerdict:
    """Ask the DATABASE what this connection's role can do. Never raises.

    Deliberately total: every failure mode returns a verdict naming itself.
    A guard that can raise is a guard someone wraps in `try/except` and stops
    reading — and this one runs on the boot path of every process.
    """
    if connection is None:
        from django.db import connection as default_connection

        connection = default_connection

    vendor = getattr(connection, "vendor", None)
    if vendor != "postgresql":
        return RlsRuntimeVerdict(
            status=RlsRuntimeStatus.NOT_APPLICABLE,
            vendor=vendor,
            detail=f"vendor {vendor!r} has no row-level security",
        )

    try:
        with connection.cursor() as cursor:
            cursor.execute(_ROLE_QUERY)
            row = cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 — see docstring: this must not raise
        return RlsRuntimeVerdict(
            status=RlsRuntimeStatus.UNREACHABLE,
            vendor=vendor,
            detail=f"{type(exc).__name__}: {exc}",
        )

    if row is None:
        # CURRENT_USER with no pg_roles row should be impossible; treat the
        # impossible as unknown rather than as healthy.
        return RlsRuntimeVerdict(
            status=RlsRuntimeStatus.UNREACHABLE,
            vendor=vendor,
            detail="CURRENT_USER has no pg_roles row",
        )

    rolname, rolsuper, rolbypassrls, memberships = row
    bypasses = bool(rolsuper) or bool(rolbypassrls)
    return RlsRuntimeVerdict(
        status=RlsRuntimeStatus.BYPASSED if bypasses else RlsRuntimeStatus.ENFORCED,
        role=rolname,
        rolsuper=bool(rolsuper),
        rolbypassrls=bool(rolbypassrls),
        vendor=vendor,
        bypassing_memberships=tuple(memberships or ()),
    )


def bypass_is_tolerated() -> tuple[bool, str]:
    """Is a bypassing role explicitly allowed here, and who said so?

    Returns (tolerated, who). Hard-won law 3: both channels require somebody to
    have typed something, and the answer names which one so the boot log records
    the decision rather than merely its effect.
    """
    if production_settings_active():
        # DEF-TEN-9794 — fail closed: no hatch under the production module.
        return False, ""
    if hatch_typed():
        return True, f"environment {BYPASS_ESCAPE_HATCH_ENV}"
    try:
        from django.conf import settings

        if getattr(settings, BYPASS_ALLOW_SETTING, False):
            return True, f"settings.{BYPASS_ALLOW_SETTING}"
    except Exception:  # noqa: BLE001 — settings may not be configured yet
        pass
    return False, ""


def production_settings_active() -> bool:
    """Is `config.settings.production` the settings module of this process?

    Read from Django's own `settings.SETTINGS_MODULE` (what was actually
    loaded), falling back to the environment before settings are configured."""
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    try:
        from django.conf import settings

        module = getattr(settings, "SETTINGS_MODULE", None) or module
    except Exception:  # noqa: BLE001 — settings may not be configured yet
        pass
    return module == PRODUCTION_SETTINGS_MODULE


def hatch_typed() -> bool:
    return os.environ.get(BYPASS_ESCAPE_HATCH_ENV, "").strip().lower() in {"1", "true", "yes"}


# ── THE LIVE TABLES — DEF-TEN-9794 (2026-10-06) ─────────────────────────────
# The role check answers *can this connection skip a policy?* It never asked
# *is there a policy to skip?* A tenant table without ENABLE, without FORCE
# (the table OWNER is exempt from a policy that is not forced, and the app role
# usually owns the tables it migrated), or without its tenant policy leaks
# exactly as a bypassing role does, and just as silently. The isolation suite
# proves the policies on a TEST database; until this, nothing asked the LIVE one.
#
# A "tenant table" is any ordinary or partitioned table in the current schema
# with a `tenant_id` column, except partitions (their parent carries the policy
# and is what the app queries) and the names below, each with its reason.
TENANT_TABLE_EXEMPTIONS: dict[str, str] = {
    # `tenants.tenant_id` IS the primary key; the row is the tenant itself.
    "tenants": "the tenant registry; tenant_id is its primary key",
    # Measured on PostgreSQL 16, 2026-10-06: of 286 tenant tables on the fully
    # migrated schema these two, and only these, carry no RLS — each ON PURPOSE.
    # `identity.Session`: a PLATFORM table read to ESTABLISH tenant context;
    # tenant binding is validated in the auth layer (US-IDN-003 §5, BR-IDN-006).
    "sessions": "read before a tenant is known; bound in the auth layer (US-IDN-003)",
    # `integrations/0011`: a partner key must be findable before any utility is
    # open — the request carries a key and nothing else (DEF-INT-5546).
    "integration_key_directory": "read before a tenant is known; integrations/0011",
    # `identity/0016` (DEF-FLD-10580): the field app learns its utility from
    # the code alone, so the register of every code ever issued is read before
    # any utility is open. A keyed digest, a tenant id and a timestamp.
    "activation_code_register": "read before a tenant is known; identity/0016",
}

_TABLE_QUERY = """
SELECT c.relname,
       c.relrowsecurity,
       c.relforcerowsecurity,
       EXISTS (
         SELECT 1 FROM pg_policy p
         WHERE p.polrelid = c.oid
           AND (COALESCE(pg_get_expr(p.polqual, p.polrelid), '') LIKE '%app.tenant_id%'
                OR COALESCE(pg_get_expr(p.polwithcheck, p.polrelid), '') LIKE '%app.tenant_id%')
       )
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = current_schema()
  AND c.relkind IN ('r', 'p')
  AND NOT c.relispartition
  AND EXISTS (
    SELECT 1 FROM pg_attribute a
    WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND a.attnum > 0 AND NOT a.attisdropped
  )
ORDER BY c.relname
"""


@dataclass(frozen=True)
class TableVerdict:
    """What the live database says about its tenant tables. `checked` is None
    when the database could not be asked — never read as a pass."""

    checked: int | None
    unprotected: tuple[str, ...] = ()
    exempted: tuple[str, ...] = ()
    detail: str = ""

    def one_line(self) -> str:
        if self.checked is None:
            return f"tenant tables NOT CHECKED: {self.detail} — this is not a pass."
        if self.unprotected:
            return (
                f"{len(self.unprotected)} of {self.checked} tenant table(s) are NOT protected by "
                f"row-level security: {', '.join(self.unprotected)}"
            )
        return (
            f"{self.checked} tenant table(s) carry ENABLE + FORCE row-level security and a "
            f"tenant policy ({len(self.exempted)} exempt by name: "
            f"{', '.join(self.exempted) or 'none'})."
        )


def read_table_verdict(connection=None) -> TableVerdict:
    """Ask the LIVE database whether every tenant table is protected. Never raises."""
    if connection is None:
        from django.db import connection as default_connection

        connection = default_connection
    vendor = getattr(connection, "vendor", None)
    if vendor != "postgresql":
        return TableVerdict(checked=None, detail=f"vendor {vendor!r} has no row-level security")
    try:
        with connection.cursor() as cursor:
            # No parameters: `%` in the LIKE patterns must not be read as placeholders.
            cursor.execute(_TABLE_QUERY.replace("%", "%%"), [])
            rows = cursor.fetchall()
    except Exception as exc:  # noqa: BLE001 — must not raise on the boot path
        return TableVerdict(checked=None, detail=f"{type(exc).__name__}: {exc}")
    unprotected: list[str] = []
    exempted: list[str] = []
    checked = 0
    for name, enabled, forced, policy in rows:
        if name in TENANT_TABLE_EXEMPTIONS:
            exempted.append(name)
            continue
        checked += 1
        missing = [
            word
            for word, ok in (("ENABLE", enabled), ("FORCE", forced), ("tenant policy", policy))
            if not ok
        ]
        if missing:
            unprotected.append(f"{name} (no {', no '.join(missing)})")
    return TableVerdict(checked=checked, unprotected=tuple(unprotected), exempted=tuple(exempted))


TABLE_REFUSAL_HEADLINE = (
    "REFUSING TO START: tenant tables on this database are not protected by row-level security"
)


def table_refusal_message(verdict: TableVerdict) -> str:
    return "\n".join(
        [
            TABLE_REFUSAL_HEADLINE,
            "",
            f"  {verdict.one_line()}",
            "",
            "  Each table named above returns every utility's rows to any query",
            "  that does not name the tenant itself (DEF-RAT-9791: one utility's",
            "  plan screen listed other utilities' charge codes).",
            "",
            "  Fix it on the database, as an administrator, per table:",
            "    ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;",
            "    ALTER TABLE <table> FORCE ROW LEVEL SECURITY;",
            "  and re-apply its policy from 06-backend/db/rls_*.sql. There is no",
            f"  override under {PRODUCTION_SETTINGS_MODULE}.",
        ]
    )


REFUSAL_HEADLINE = "REFUSING TO START: row-level security is not enforced on this connection"


def refusal_message(verdict: RlsRuntimeVerdict) -> str:
    """The whole message a refused boot prints. Written to be actionable by
    somebody who has never read this file — it names the role, the fix, and the
    one way to override, because a refusal nobody can act on gets bypassed."""
    return "\n".join(
        [
            REFUSAL_HEADLINE,
            "",
            f"  {verdict.one_line()}",
            "",
            "  PostgreSQL exempts superusers and BYPASSRLS roles from row-level",
            "  security unconditionally — FORCE ROW LEVEL SECURITY included. The",
            "  tables still report ENABLE and FORCE, the policies still exist, and",
            "  every query still returns plausible rows. The only difference is that",
            "  the tenant predicate is never evaluated, so ONE TENANT CAN READ",
            "  ANOTHER'S DATA and nothing anywhere reports an error (DEF-2717).",
            "",
            "  Fix it on the database, as an administrator:",
            f"    ALTER ROLE \"{verdict.role}\" NOSUPERUSER NOBYPASSRLS;",
            "",
            "  Then re-verify:",
            "    10-scripts/13-provision-database.sh --verify",
            "",
            "  A deployment must never grant BYPASSRLS — PO ruling 2026-08-24",
            "  (OQ-354).",
            *(
                [
                    f"  {BYPASS_ESCAPE_HATCH_ENV} and {BYPASS_ALLOW_SETTING} are NOT honoured",
                    f"  under {PRODUCTION_SETTINGS_MODULE} (DEF-TEN-9794)"
                    + (
                        f"; {BYPASS_ESCAPE_HATCH_ENV} is set and was IGNORED."
                        if hatch_typed()
                        else "."
                    ),
                ]
                if production_settings_active()
                else [
                    "  If you genuinely need to run this process unprotected (never under",
                    f"  {PRODUCTION_SETTINGS_MODULE}), say so out loud, per boot:",
                    f"    {BYPASS_ESCAPE_HATCH_ENV}=1",
                    "  (config/settings/local.py already sets the settings equivalent, which",
                    "   is why development on a superuser role warns instead of refusing.)",
                ]
            ),
        ]
    )


def _enforce_tables(connection, out) -> TableVerdict:
    """DEF-TEN-9794 — the live tables. Prints one line always. REFUSES only
    under the production settings module: elsewhere (a developer's database
    mid-migration, a test database) it warns, because the same unprotected
    table is a fact worth seeing there and not a reason to stop a laptop."""
    from django.core.exceptions import ImproperlyConfigured

    tables = read_table_verdict(connection)
    if tables.unprotected and production_settings_active():
        raise ImproperlyConfigured(table_refusal_message(tables))
    marker = "⚠ " if tables.unprotected or tables.checked is None else ""
    print(f"rls-guard: {marker}{tables.one_line()}", file=out)
    return tables


def enforce_at_startup(connection=None, *, stream=None) -> RlsRuntimeVerdict:
    """The boot-path entry point. Prints one line always; refuses when fatal.

    ⚠ DEF-TEN-9794 (2026-10-06) — it now also asks the LIVE database whether
    every tenant table carries ENABLE + FORCE row-level security and a tenant
    policy, and under `config.settings.production` refuses to start naming the
    tables that do not; and under that module neither escape hatch is honoured.

    Called from `config/wsgi.py` (so gunicorn is covered however it was
    started) and from `docker-entrypoint.sh` (so the message is readable before
    `migrate` runs). Both call the same function on purpose — hard-won law 2:
    a guard with one caller is a guard one refactor away from being dead.

    Raises `django.core.exceptions.ImproperlyConfigured` when the connection
    bypasses RLS and nobody has typed the escape hatch.
    """
    import sys

    from django.core.exceptions import ImproperlyConfigured

    out = stream if stream is not None else sys.stderr
    verdict = read_runtime_verdict(connection)

    if not verdict.bypasses:
        # Still print: an ENFORCED line beside a published benchmark figure is
        # what tells a later reader which world the number came from, which is
        # the half of DEF-2717 that a refusal alone would not have fixed.
        print(f"rls-guard: {verdict.one_line()}", file=out)
        _enforce_tables(connection, out)
        return verdict

    tolerated, who = bypass_is_tolerated()
    if tolerated:
        print(f"rls-guard: ⚠ {verdict.one_line()}", file=out)
        print(
            f"rls-guard: ⚠ TOLERATED because {who} says so. Tenant isolation is NOT "
            f"being enforced by the database in this process.",
            file=out,
        )
        _enforce_tables(connection, out)
        return verdict

    raise ImproperlyConfigured(refusal_message(verdict))


# ── Django system check ─────────────────────────────────────────────────────
# Registered from apps/tenancy/apps.py — the module that owns tenant scoping.
# Tagged `database` because that is what it is about — the tag GROUPS it with the
# other database checks and lets `manage.py check --tag database` select it.
# ⚠ IT DOES NOT NARROW WHEN IT RUNS, and an earlier draft of this comment claimed
# it did (hard-won law 1, caught before it shipped). Django's `run_checks` filters
# by tag ONLY when a caller passes `tags`; `BaseCommand.check()` passes none, so a
# tagged check runs wherever system checks run — `migrate` on every container
# boot, and every other management command too. That is one cheap `pg_roles`
# query, and an unreachable database returns UNREACHABLE rather than failing, so
# the breadth costs nothing and buys coverage.
def check_runtime_rls_enforcement(app_configs=None, **kwargs):
    """Django system check — the backstop that cannot be skipped by starting the
    process some other way. Errors block the command; warnings do not."""
    from django.core.checks import Error, Warning as CheckWarning

    verdict = read_runtime_verdict()

    if verdict.status is RlsRuntimeStatus.BYPASSED:
        tolerated, who = bypass_is_tolerated()
        if tolerated:
            return [
                CheckWarning(
                    verdict.one_line(),
                    hint=f"Tolerated because {who}. No tenant policy is being applied.",
                    id="core.W001",
                )
            ]
        return [
            Error(
                verdict.one_line(),
                hint=refusal_message(verdict),
                id="core.E001",
            )
        ]

    if verdict.status is RlsRuntimeStatus.ENFORCED and verdict.bypassing_memberships:
        return [
            CheckWarning(
                verdict.one_line(),
                hint=(
                    "The role does not bypass RLS today, but `SET ROLE` to any of "
                    "those roles would. Grant it no such membership in production."
                ),
                id="core.W002",
            )
        ]

    # NOT_APPLICABLE and UNREACHABLE are silent here BY DESIGN — see the module
    # docstring. Neither is a pass, and neither is something a merge can fix.
    return []
