# ── Trace ──────────────────────────────────────────────
# Component: G5 tenant-isolation suite plumbing (CLAUDE.md rule 1 · NFR-10 zero
#            tolerance · B2 §3 RLS template · B3/BE-01 app.tenant_id session GUC).
# Contract:  B2 §3 (ENABLE + FORCE ROW LEVEL SECURITY, USING/WITH CHECK on
#            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) ·
#            core/tenancy.py (the kernel that SETs the GUC) ·
#            BR-AUD-002 (audit_log append-only trigger).
# Tests:     imported by every tests/test_*.py that carries an @pytest.mark.isolation
#            case. Nothing here is collected as a test (module is not test_*).
# ───────────────────────────────────────────────────────
"""Live-Postgres isolation plumbing — how the G5 suite proves what it claims.

WHY THIS MODULE EXISTS AT ALL (read before touching anything below)
-------------------------------------------------------------------
The G5 suite makes two DIFFERENT promises, and they need two different proofs:

  (1) APP-LAYER SCOPING — every selector/service/endpoint filters by the
      caller's tenant. Provable on any vendor; the sqlite tier already does it.
  (2) RLS — the DATABASE refuses cross-tenant rows even if (1) is bypassed or
      buggy. Provable only on Postgres, and only under a role that RLS applies
      to.

**Superusers BYPASS row-level security, unconditionally, FORCE or not.** The
role this app connects as in dev/CI (`smartbillhub`) *is* a superuser today:

    rolname       | rolsuper | rolbypassrls
    smartbillhub  | t        | f

Every RLS assertion made on that connection is therefore VACUOUS — the query
returns rows because the policy was never consulted, and the test goes green
having proven nothing. A green suite that proves nothing is worse than a red
one, so this module refuses that outcome.

THE DECISION: a dedicated non-superuser probe role, entered with SET ROLE
-------------------------------------------------------------------------
`rls_probe_role` creates (idempotently, in the TEST database only) the role

    sbh_rls_probe  —  NOLOGIN NOSUPERUSER NOBYPASSRLS

granted plain SELECT/INSERT/UPDATE/DELETE on the schema, and the RLS half of
every assertion runs inside `SET ROLE sbh_rls_probe` … `RESET ROLE` on the
SAME connection and the SAME transaction as the test's own ORM writes.

Three properties make that a genuine proof rather than a nicer-looking lie:

  * `current_user` after SET ROLE is the probe role, and PostgreSQL evaluates
    the superuser/BYPASSRLS exemption against `current_user` — so the policies
    are really consulted. `assert_probe_is_a_real_proof()` re-reads
    `pg_roles` at runtime and FAILS (never skips) if either attribute is true.
  * Same transaction ⇒ the probe sees the rows the test just wrote through the
    real service layer. No commit, no second connection, no `transaction=True`
    (which would make audit_log's BR-AUD-002 trigger fight the truncating
    teardown), and no fixture data left behind.
  * The app's own role is untouched, so nothing in the product runs degraded:
    services, selectors and endpoints keep executing exactly as in production.

The GUC half stays the app's job on purpose: the probe reads whatever
`app.tenant_id` the REAL kernel (`core.tenancy.tenant_context`, via
`live_tenant_context` below) put on the session. If BE-01 stopped SETting the
GUC, these tests would go red — which is the point.

If the probe role cannot be created (a deployment where the app role has
neither SUPERUSER nor CREATEROLE), the fixture SKIPS with a reason that says
in as many words that the RLS guarantee is UNPROVEN in that environment. It
never silently downgrades to an app-layer-only pass.

VENDOR GUARD
------------
`requires_postgres` is a skipif keyed on `connection.vendor`, so the default
sqlite run (`config.settings.test`) skips these cases with a vendor reason and
the Postgres run (`config.settings.local` + a Postgres DATABASE_URL) runs them.

⚠ **THAT OVERRIDE IS FOR `-m isolation` ONLY. DO NOT APPLY IT TO THE WHOLE
SUITE (DEF-164, 2026-08-16).** `pyproject.toml` pins
`DJANGO_SETTINGS_MODULE = "config.settings.test"`, and the difference that
bites is `JOBS_EAGER`: **False** under `test`, **True** under `local` (it
inherits base). With it True a dispatched job runs INLINE, so a test that
dispatches and then asserts on the queued job finds it already finished.
Measured both ways on the same file, same machine:

    DJANGO_SETTINGS_MODULE=config.settings.local  pytest tests/test_be07_job_runner.py
        -> 6 failed, 7 passed   (`JobsError: job … is succeeded — cannot start`)
    pytest tests/test_be07_job_runner.py            # pinned settings.test
        -> 13 passed

Six other files are equally sensitive (`test_be07_jobs.py`,
`test_be07_jobs_endpoint.py`, `test_be_export_download.py`,
`test_be_list_export.py`, `test_us_aud_006_export_job.py`). **A lane lost time
to this on 2026-08-16 because a briefing generalised the line below into
"the correct test invocation".** It is not: it is the correct invocation for
the isolation subset, which needs a real database, and for nothing else.
**The safe habit is `env -u DJANGO_SETTINGS_MODULE pytest …`** so pytest reads
the pinned value rather than inheriting a stale export from your shell.

NO TEST IN THIS SUITE IS UNCONDITIONALLY SKIPPED — AND THAT IS NOW ENFORCED
---------------------------------------------------------------------------
⚠ **That sentence used to stand here alone, and it was FALSE — for as long as
the marks it denied had existed (DEF-101, corrected 2026-08-15).** Twelve
isolation cases carried a bare `@pytest.mark.skip`, not a `skipif`. Their skip
reasons each read *"live Postgres must prove …"* and **they were skipping ON
live Postgres**. All twelve were RATING, so the module that decides what every
customer is charged — tariffs, tariff_versions, rate schedules, capacity_rates,
rate_change_log, charges, taxes — had **no cross-tenant read proof on any
database**, underneath this paragraph swearing otherwise. Hard-won law 1, in the
file whose entire job is to guarantee tenant isolation: *a comment claiming a
guarantee is not the guarantee.*

It escaped because **a skipped test is GREEN**. The suite reported 36 passed on
sqlite and nobody read the skip count as a number that mattered. It was found by
running `-m isolation` against real Postgres for a release gate and looking at
the pair: 129 passed, 12 skipped.

Two things make the sentence true now instead of merely written:
  * the twelve cases were WRITTEN OUT and run — Postgres reports **156 passed,
    0 skipped**, against 36 passed / 120 skipped on sqlite;
  * **G5 refuses an unconditional `pytest.mark.skip` on any isolation-marked
    test** (10-scripts/gates/g05_isolation.py, AST over the decorator stack), and
    G5's PASS line prints the skip count beside the pass count on every run.

So do not add a bare `skip` here. If a case cannot run on a vendor, that is what
`requires_postgres` is for; if it cannot run at all, it is not an isolation
guarantee and must not carry the mark.
"""

import re
import uuid
from contextlib import contextmanager

import pytest
from django.db import DatabaseError, connection, transaction

from core import tenancy as core_tenancy

# ── vendor guard ────────────────────────────────────────────────────────────
VENDOR_SKIP_REASON = (
    "G5 isolation suite needs live PostgreSQL — RLS, FORCE ROW LEVEL SECURITY and the "
    "BR-AUD-002 append-only trigger do not exist on sqlite. Run with "
    'DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL="postgres://…" -m isolation.'
)


def is_postgres() -> bool:
    """True when the configured default database is PostgreSQL."""
    return connection.vendor == "postgresql"


#: Vendor-conditional marker. Every G5 case carries this INSTEAD of a bare skip.
requires_postgres = pytest.mark.skipif(not is_postgres(), reason=VENDOR_SKIP_REASON)

PROBE_ROLE = "sbh_rls_probe"
_SAFE_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Tables whose ONLY defence is the app layer (B2 §3 declares them RLS-exempt):
#: platform catalogs, the tenant registry itself, and the two lookups that
#: ANSWER *which utility is this* before one is open.
RLS_EXEMPT_TABLES = frozenset(
    {
        "tenants",
        "services",
        "subscription_plans",
        "roles",
        "permissions",
        "role_permissions",
        "sessions",
        # ⚠ **ADDED 2026-09-16 (`CR-110-BRC04` phase 2, `DEF-INT-5546`), AND IT
        # IS `sessions`' CLASS RATHER THAN A NEW ONE.** `sessions` is exempt so
        # that `/api/jobs/{id}` — a path with no utility segment — can read the
        # session row and open the utility it names. The partner surface moved
        # to `/api/partner/v1/…` by PO ruling, so it now has the same need and
        # `integration_key_directory` is the same answer: a key's one-way
        # fingerprint, the utility it was issued by, and the two ids that name
        # its rows. No secret, no customer data. It AUTHORISES nothing — every
        # guard still runs afterwards against `integration_credential` under the
        # utility this table opened, so a row naming the wrong one is refused in
        # the ordinary way. Migration `0011` carries the full argument; B2 §3
        # carries the declaration this list is checked against.
        "integration_key_directory",
        # ⚠ **ADDED 2026-10-24 (`DEF-FLD-10580`, beta MQ-006), the same class
        # again.** The field app is one build for every utility and learns the
        # utility from the office's activation code, so the platform register
        # of every code ever issued (`identity/0016`) is read before any
        # utility is open. It holds a keyed digest, the utility's id and a
        # timestamp, and authorises nothing: the tenant's own `activation_codes`
        # row is read afterwards under that utility's RLS context.
        "activation_code_register",
    }
)


#: Tables whose policy READS `tenant_id IS NULL` as well as the caller's own
#: rows — the PLATFORM rows we ship (`reports/0002`: the 46 report definitions
#: and the 25 catalogue groups), readable by every tenant and writable by none.
#:
#: ⚠ **THIS IS A PIN, NOT AN EXEMPTION (`DEF-REP-7823`, 2026-10-02).** Nothing
#: here stops the suite asking about these tables. `denied_without_context` and
#: `assert_rls_scoped` ask whether the policy ADMITS NULL by reading the
#: policy out of `pg_policies` (`admits_platform_rows`), and hold every
#: TENANT row of such a table to exactly the same deny as any other table.
#: This constant exists for the other direction: the G5 sweep asserts that the
#: set of tables whose policy admits NULL is EXACTLY this set, so a policy that
#: admits a NULL by accident — the hole `reports/0002`'s own docstring names —
#: goes red by table name rather than being read as a platform catalogue.
PLATFORM_ROW_TABLES = frozenset({"report_definitions", "report_categories"})


def admits_platform_rows(table: str) -> bool:
    """Does `table`'s own RLS policy READ rows whose `tenant_id IS NULL`?

    Read from `pg_policies` — the policy the database will actually evaluate —
    never from a list, so the answer cannot outlive the policy it describes.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT qual FROM pg_policies WHERE schemaname = 'public' AND tablename = %s",
            [table],
        )
        quals = [row[0] or "" for row in cursor.fetchall()]
    return any("tenant_id IS NULL" in qual for qual in quals)


def _ident(name: str) -> str:
    """Guard: only registry/constant-shaped identifiers ever reach DDL/DML text."""
    if not _SAFE_IDENT.match(name):
        raise AssertionError(f"unsafe SQL identifier {name!r} in the isolation suite")
    return name


# ── the real GUC, even when a sqlite fixture faked the cursor away ──────────
@contextmanager
def live_tenant_context(tenant_id):
    """`core.tenancy.tenant_context` with the REAL DB connection behind it.

    The unit tier's fixtures (`sqlite_guc` in tests/test_us_ten_helpers.py, the
    `idn` fixture in tests/test_us_idn_helpers.py) monkeypatch
    `core.tenancy.connection` with a recorder because sqlite has no
    `set_config`. On Postgres that recorder would swallow the very statement
    this suite exists to verify, so it is swapped back for the duration — the
    GUC is then set by the SHIPPING kernel, not by the test.
    """
    from django.db import connection as real_connection

    faked = core_tenancy.connection is not real_connection
    saved = core_tenancy.connection
    if faked:
        core_tenancy.connection = real_connection
    try:
        with core_tenancy.tenant_context(tenant_id) as tid:
            yield tid
    finally:
        if faked:
            core_tenancy.connection = saved


def current_guc() -> str:
    """Whatever `app.tenant_id` the session currently carries ('' when cleared)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.tenant_id', true)")
        return cursor.fetchone()[0] or ""


def clear_live_guc() -> None:
    """Clear `app.tenant_id` through the shipping kernel, on the real session."""
    from django.db import connection as real_connection

    faked = core_tenancy.connection is not real_connection
    saved = core_tenancy.connection
    if faked:
        core_tenancy.connection = real_connection
    try:
        core_tenancy.clear_current_tenant()
    finally:
        if faked:
            core_tenancy.connection = saved


@contextmanager
def writing_as_tenant(tenant):
    """Set tenant context for a FIXTURE WRITE, through the shipping kernel.

    ⚠ **WHY EVERY FIXTURE THAT WRITES A TENANT ROW SUDDENLY NEEDS THIS
    (DEF-GOV-4024 / DEF-GOV-4036, 2026-09-05).** Until the isolation suite was
    pointed at a role row-level security genuinely applies to, the Django
    connection in tests was the table OWNER *and a superuser* — and a superuser
    bypasses every policy. So a fixture could `Model.objects.create(...)` with
    no `app.tenant_id` set at all and PostgreSQL would take the row. It does
    not any more, and it should not: `B2 §3` puts **FORCE** ROW LEVEL SECURITY
    on every tenant table, which applies the policy to the owner too, and the
    policy's `WITH CHECK` refuses an INSERT whose `tenant_id` does not equal
    the GUC. With no context the GUC is NULL, nothing equals NULL, and the
    write is refused with *"new row violates row-level security policy"*.

    **That refusal is the guarantee working, not a bug** — hard rule 1 says a
    tenant table is never touched without `app.tenant_id` set, and the fixtures
    were doing exactly that.

    **THE CONTEXT COMES FROM THE REAL KERNEL AND FROM NOWHERE ELSE.** This
    calls `core.tenancy.tenant_context`, which is what a Celery task or a
    management command calls in production; the GUC is written by
    `set_current_tenant`'s own parameterised `set_config`. Writing the setting
    by hand in a fixture would make these tests pass while proving nothing
    about the app's scoping, which is the whole thing they exist to prove.

    ⚠ **IT RESTORES THE PREVIOUS CONTEXT INSTEAD OF CLEARING, AND
    `tenant_context` ALONE DOES NOT.** The kernel's own contextmanager clears
    on exit — correct for a job, which owns the session — but a fixture is
    often called from INSIDE a test's own `tenant_context`, and clearing there
    would leave the rest of the test reading zero rows through an RLS policy
    that is behaving perfectly. That failure is silent: the queryset is empty,
    nothing raises.

    ⚠ **THE GUC IS SESSION-SCOPED, NOT TRANSACTION-SCOPED** — `set_config(…,
    false)` — so it does NOT come back on its own when a savepoint unwinds,
    which is why the restore is in a `finally` rather than left to the
    transaction. When the body has aborted the transaction (CLAUDE.md law 14),
    no statement can run until the caller unwinds, so the Python mirror is put
    back on its own and the next successful `set_current_tenant` re-syncs the
    database side.
    """
    tenant_id = getattr(tenant, "id", tenant)
    previous = core_tenancy.current_tenant_id()
    if not _kernel_can_set_the_guc():
        # sqlite has no `set_config`, so there is no GUC to write and no policy
        # to satisfy — the kernel's own statement would raise `no such function`.
        # Keep the PYTHON MIRROR consistent so `current_tenant_id()` reads the
        # same on both tiers, and change nothing else. This branch is never the
        # one the isolation proof runs on: every case in this suite carries
        # `requires_postgres`.
        tid = core_tenancy._as_uuid(tenant_id)
        core_tenancy._current_tenant.set(tid)
        try:
            yield tid
        finally:
            core_tenancy._current_tenant.set(previous)
        return
    try:
        with core_tenancy.tenant_context(tenant_id) as tid:
            yield tid
    finally:
        if previous is not None:
            try:
                core_tenancy.set_current_tenant(previous)
            except DatabaseError:
                # Law 14: the body poisoned the transaction, so nothing can be
                # executed here. Keep the Python mirror honest; the database
                # side is restored by the caller's next successful SET.
                core_tenancy._current_tenant.set(previous)


def _kernel_can_set_the_guc() -> bool:
    """True when `core.tenancy`'s connection can execute `set_config`.

    Two ways it can: the real connection is PostgreSQL, or a fixture has
    swapped in the recorder that the sqlite tier uses (`_FakeConnection` in
    tests/test_us_idn_helpers.py, `sqlite_guc` in tests/test_us_ten_helpers.py),
    which accepts the statement and drops it. Anything else is a real sqlite
    cursor, where `set_config` does not exist.
    """
    from django.db import connection as real_connection

    return connection.vendor == "postgresql" or core_tenancy.connection is not real_connection


# ── the non-superuser probe ─────────────────────────────────────────────────
class RlsProbe:
    """Runs statements as `sbh_rls_probe` on the test's own connection/transaction.

    Reads take whatever `app.tenant_id` is currently set — enter
    `live_tenant_context(...)` (or the `under()` shorthand) around them so the
    context comes from the shipping kernel.
    """

    def __init__(self, role: str = PROBE_ROLE) -> None:
        self.role = _ident(role)

    # ── plumbing ────────────────────────────────────────────────────────
    @contextmanager
    def _as_role(self):
        with connection.cursor() as cursor:
            cursor.execute(f'SET ROLE "{self.role}"')
            try:
                yield cursor
            finally:
                try:
                    cursor.execute("RESET ROLE")
                except DatabaseError:
                    # The statement under test aborted the (sub)transaction, so
                    # RESET cannot run here. The caller's savepoint rollback
                    # restores the role — SET is transactional in PostgreSQL.
                    pass

    def under(self, tenant):
        """Shorthand: `with probe.under(tenant_a): ...` — the real kernel's GUC."""
        return live_tenant_context(getattr(tenant, "id", tenant))

    # ── reads ───────────────────────────────────────────────────────────
    def rows(self, sql: str, params=None) -> list[tuple]:
        with self._as_role() as cursor:
            cursor.execute(sql, params or [])
            return list(cursor.fetchall())

    def scalar(self, sql: str, params=None):
        result = self.rows(sql, params)
        return result[0][0] if result else None

    # ── writes that must find nothing ───────────────────────────────────
    def affected(self, sql: str, params=None) -> int:
        """Run a write and return its rowcount.

        An UPDATE/DELETE the policy's USING clause hides does not error — it
        matches zero rows. That silence IS the guarantee, so it gets asserted
        rather than inferred.
        """
        with self._as_role() as cursor:
            cursor.execute(sql, params or [])
            return cursor.rowcount

    def count(self, table: str, where: str = "", params=None) -> int:
        clause = f" WHERE {where}" if where else ""
        return int(self.scalar(f"SELECT count(*) FROM {_ident(table)}{clause}", params))

    def ids(self, table: str, column: str = "id", *, tenant_rows_only: bool = False) -> set[str]:
        """Every `column` value the probe can see in `table` right now.

        `tenant_rows_only` leaves out PLATFORM rows (`tenant_id IS NULL`) — they
        are visible to every tenant BY DESIGN on a `PLATFORM_ROW_TABLES` table,
        so counting them as "seen by both" reports a leak that is not one.
        """
        where = " WHERE tenant_id IS NOT NULL" if tenant_rows_only else ""
        return {
            str(row[0])
            for row in self.rows(f"SELECT {_ident(column)} FROM {_ident(table)}{where}")
            if row[0] is not None
        }

    def tenant_ids(self, table: str) -> set[str]:
        return {
            str(row[0])
            for row in self.rows(f"SELECT DISTINCT tenant_id FROM {_ident(table)}")
            if row[0] is not None
        }

    # ── refusals (each inside its own savepoint) ────────────────────────
    def refused(self, sql: str, params=None) -> str:
        """Assert PostgreSQL REFUSES this statement; return the message.

        Wrapped in a savepoint so the deliberate error cannot poison the test's
        outer transaction, and so the SET ROLE is unwound with it.
        """
        with pytest.raises(DatabaseError) as excinfo:
            with transaction.atomic():
                with self._as_role() as cursor:
                    cursor.execute(sql, params or [])
        return str(excinfo.value)

    def denied_without_context(self, table: str) -> str:
        """No `app.tenant_id` ⇒ the policy matches NOTHING ⇒ zero rows, quietly.

        ⚠ AMENDED 2026-08-24 (DEF-639, PO ruling *"Change the security rule
        instead, in a new step"*). Until then the predicate cast the raw GUC,
        `''` could not be cast, and this method asserted an ERROR. **That
        loudness is what broke the first deploy**: the same policy is evaluated
        during FOREIGN KEY VALIDATION, and three committed migrations clear
        tenant context before their own deferred FKs are validated, so a fresh
        database died on `invalid input syntax for type uuid: ""` at step 12 of
        168. The predicate is now `NULLIF(current_setting('app.tenant_id',
        true), '')::uuid`, which is NULL, which is not TRUE, which denies.

        **Deny-by-default (CLAUDE.md hard rule 1) is UNCHANGED** — absence of
        context is still never 'see everything'. What changed is that absence is
        now SILENT on READS. Writes are still refused loudly: see
        `assert_write_into_other_tenant_refused`.

        THIS IS ONE CHOKE POINT FOR 79 ASSERTIONS ACROSS 33 TEST FILES, which is
        why the contract change costs one method rather than 79 edits — and why
        this docstring says what changed rather than leaving the next reader to
        infer it from a passing test.
        """
        # ⚠ **A PLATFORM ROW IS NOT A TENANT ROW (`DEF-REP-7823`, 2026-10-02).**
        # `report_definitions` and `report_categories` READ `tenant_id IS NULL`
        # on purpose — the catalogue we ship, the same on every deployment — so
        # with no context they answer 46 and 25 rows, every one of them NULL.
        # This assertion used to count them and call that *deny-by-default is
        # not in force*, which was false, and it sat red in the G5 sweep and in
        # `test_cr142_p0_10_reports_rls_pg.py` for four days, training readers
        # to discount the very file that holds the real denies. What is
        # asserted now, on such a table, is the thing hard rule 1 is about:
        # ZERO rows that belong to ANY tenant. A policy that admits NULL is
        # detected from the policy itself, and the sweep pins which tables may.
        if admits_platform_rows(table):
            rows = self.scalar(f"SELECT count(*) FROM {_ident(table)} WHERE tenant_id IS NOT NULL")
            assert rows == 0, (
                f"{table}: a query with NO tenant context returned {rows} TENANT row(s) — "
                "deny-by-default (CLAUDE.md hard rule 1) is not in force"
            )
            return f"{table}: 0 tenant rows with no tenant context (platform rows admitted by its policy)"
        rows = self.scalar(f"SELECT count(*) FROM {_ident(table)}")
        assert rows == 0, (
            f"{table}: a query with NO tenant context returned {rows} row(s) — "
            "deny-by-default (CLAUDE.md hard rule 1) is not in force"
        )
        return f"{table}: 0 rows with no tenant context"

    # ── the canary: is this proof real at all? ──────────────────────────
    def role_attributes(self) -> tuple[bool, bool]:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [self.role]
            )
            row = cursor.fetchone()
        assert row is not None, f"probe role {self.role} vanished mid-run"
        return bool(row[0]), bool(row[1])

    def assert_is_a_real_proof(self) -> None:
        """FAIL (never skip) if the probe role could bypass RLS.

        Without this, every RLS assertion in the suite could pass vacuously.
        """
        rolsuper, rolbypassrls = self.role_attributes()
        assert not rolsuper, (
            f"{self.role} is a SUPERUSER — it bypasses RLS, so every isolation "
            "assertion in this suite would pass without the policies existing"
        )
        assert not rolbypassrls, (
            f"{self.role} carries BYPASSRLS — every isolation assertion in this "
            "suite would pass without the policies existing"
        )
        with connection.cursor() as cursor:
            cursor.execute(f'SET ROLE "{self.role}"')
            cursor.execute("SELECT current_user")
            effective = cursor.fetchone()[0]
            cursor.execute("RESET ROLE")
        assert effective == self.role, (
            f"SET ROLE did not take effect (current_user={effective!r}) — the RLS "
            "half of this suite is NOT being exercised"
        )


@pytest.fixture(scope="session")
def rls_probe_role(django_db_setup, django_db_blocker):
    """Create + grant the non-superuser probe role in the TEST database.

    Session-scoped and run outside any test transaction so the GRANTs commit;
    `ALTER DEFAULT PRIVILEGES` covers tables created later (audit_log's monthly
    partitions, which the partition manager may add mid-run).
    """
    if not is_postgres():
        pytest.skip(VENDOR_SKIP_REASON)
    role = _ident(PROBE_ROLE)
    with django_db_blocker.unblock():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s) THEN "
                    "    EXECUTE format('CREATE ROLE %%I NOLOGIN NOSUPERUSER NOBYPASSRLS', %s); "
                    "  END IF; "
                    "END $$",
                    [role, role],
                )
                # Belt and braces: an inherited role from an earlier run must
                # not be allowed to keep an attribute that voids the proof.
                #
                # ⚠ READ IT, AND ONLY ALTER IT IF IT IS WRONG (DEF-GOV-4036,
                # 2026-09-05). This line used to be issued unconditionally, and
                # `ALTER ROLE … NOSUPERUSER` requires the SUPERUSER attribute —
                # even to set it to NO, and even when it is already NO. So the
                # whole fixture was superuser-only, and that is a contradiction
                # with what it exists to prove: a superuser BYPASSES row-level
                # security, so the app connection running the suite sees every
                # tenant's rows. Measured on 2026-09-05, the same suite, the
                # same commit, two roles:
                #
                #   as the superuser app role : 36 failed, 201 passed, 1 skipped
                #   as NOSUPERUSER NOBYPASSRLS: 19 failed,  96 passed, 120 skipped
                #                               (112 of those skips are this line)
                #
                # Neither run proves anything. The first cannot — no policy is
                # ever consulted. The second could, and was stopped here.
                #
                # Reading the attributes back is STRONGER than setting them, not
                # weaker: today the fixture knows only that it issued a
                # statement, and afterwards it knows what the role actually is.
                # A role that IS wrong still gets the ALTER, and still fails
                # loudly on a connection that may not issue it — which is the
                # honest answer in that case.
                cursor.execute(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [role]
                )
                attributes = cursor.fetchone()
                if attributes is None:
                    raise DatabaseError(
                        f"the probe role {role!r} does not exist after the CREATE above"
                    )
                if attributes[0] or attributes[1]:
                    cursor.execute(f'ALTER ROLE "{role}" NOSUPERUSER NOBYPASSRLS')
                # The probe works by `SET ROLE`, which needs MEMBERSHIP in the
                # role, not merely its existence — and granting membership needs
                # ADMIN OPTION on it, which an ordinary app role has only if an
                # administrator gave it. Attempted here so a cluster where the
                # connection can do it needs no setup, and left to the skip
                # below where it cannot. Without this the fixture got as far as
                # creating the role and then died on `permission denied to set
                # role "sbh_rls_probe"` (DEF-GOV-4036).
                cursor.execute(
                    "SELECT pg_has_role(current_user, %s, 'MEMBER')", [PROBE_ROLE]
                )
                if not cursor.fetchone()[0]:
                    cursor.execute(f'GRANT "{role}" TO CURRENT_USER')
                cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
                cursor.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                    f'TO "{role}"'
                )
                cursor.execute(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
                cursor.execute(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{role}"'
                )
        except DatabaseError as exc:  # pragma: no cover — environment-dependent
            pytest.skip(
                "RLS HALF NOT EXERCISED — could not create the non-superuser probe role "
                f"{role!r} ({exc}). The connected role bypasses row-level security, so "
                "the tenant-isolation guarantee is UNPROVEN in this environment. Grant "
                "the app role CREATEROLE (or pre-create the probe role) before trusting "
                "a green G5 run."
            )
    return role


@pytest.fixture()
def rls(rls_probe_role):
    """The per-test probe. Self-verifying: a bypassing role fails, never skips."""
    probe = RlsProbe(rls_probe_role)
    probe.assert_is_a_real_proof()
    return probe


# ── reusable assertions (the shape every G5 case shares) ────────────────────
def assert_denied_without_context(probe: RlsProbe, *tables: str) -> None:
    """Manual probe (1): with no `app.tenant_id`, every named table errors."""
    clear_live_guc()
    for table in tables:
        probe.denied_without_context(table)


def assert_rls_scoped(
    probe: RlsProbe,
    table: str,
    *,
    owner,
    intruder,
    owner_ids: set[str] | None = None,
    id_column: str = "id",
    min_owner_rows: int = 1,
) -> None:
    """Manual probe (2): `owner`'s rows exist under `owner`, vanish under `intruder`.

    Asserted through the DATABASE, under a role RLS applies to — the app-layer
    filter is deliberately not in the path.
    """
    owner_id, intruder_id = str(owner.id), str(intruder.id)
    # Platform rows (`tenant_id IS NULL`) are visible to BOTH tenants by design
    # on a table whose policy admits them; comparing them would report a LEAK
    # that is the shipped catalogue (`DEF-REP-7823`). Tenant rows only, then.
    tenant_rows_only = admits_platform_rows(table)
    with live_tenant_context(owner.id):
        assert current_guc() == owner_id, (
            "core.tenancy.tenant_context did not SET app.tenant_id on the live session — "
            "BE-01 is the only thing that makes RLS able to scope anything"
        )
        seen = probe.ids(table, id_column, tenant_rows_only=tenant_rows_only)
        tenants_seen = probe.tenant_ids(table)
    assert tenants_seen <= {
        owner_id
    }, f"{table}: under {owner_id}'s context the database exposed rows of {tenants_seen - {owner_id}}"
    assert len(seen) >= min_owner_rows, (
        f"{table}: expected at least {min_owner_rows} row(s) for the owning tenant, saw {len(seen)}"
        " — the fixture wrote nothing, so this assertion would prove nothing"
    )
    if owner_ids is not None:
        missing = {str(i) for i in owner_ids} - seen
        assert not missing, f"{table}: owner cannot see its own rows {missing}"

    with live_tenant_context(intruder.id):
        assert current_guc() == intruder_id
        intruder_sees = probe.ids(table, id_column, tenant_rows_only=tenant_rows_only)
        intruder_tenants = probe.tenant_ids(table)
    assert (
        owner_id not in intruder_tenants
    ), f"{table}: LEAK — tenant {intruder_id} can read tenant {owner_id}'s rows"
    leaked = seen & intruder_sees
    assert not leaked, f"{table}: LEAK — rows {leaked} visible to both tenants"


def assert_write_into_other_tenant_refused(probe: RlsProbe, table: str, *, owner, intruder) -> str:
    """Manual probe (4): the policy's WITH CHECK refuses a row stamped for another tenant.

    Re-stamping one of `owner`'s own visible rows with `intruder`'s tenant_id is
    the table-agnostic form of "INSERT carrying another tenant's id": USING lets
    the UPDATE find the row, WITH CHECK rejects the result.

    ⚠ **THE ROW COUNT IS CHECKED FIRST, AND THAT IS NOT DECORATION (DEF-PAY-4054
    triage, 2026-09-05).** An `UPDATE … WHERE tenant_id = <owner>` on a table
    where the owner has NO ROWS matches nothing, succeeds, and raises nothing —
    so `probe.refused` reports `DID NOT RAISE DatabaseError`, which is
    indistinguishable, in the failure output, from *the policy let a
    cross-tenant write through*. One reads as a vacuous fixture and the other as
    a production-severity leak, and on 2026-09-05 an hour went into telling them
    apart on `work_order_details` and its five siblings, where the answer was
    that the fixture seeded nothing.

    `assert_rls_scoped` has had `min_owner_rows` for exactly this reason since it
    was written; this half of the pair never got it. So: prove the owner HAS a
    row to re-stamp before concluding anything from the absence of an error.
    """
    with live_tenant_context(owner.id):
        present = probe.scalar(
            f"SELECT count(*) FROM {_ident(table)} WHERE tenant_id = %s", [str(owner.id)]
        )
        assert present > 0, (
            f"{table}: the owning tenant has no rows, so the UPDATE below would match "
            "nothing and refuse nothing — this assertion would prove nothing about "
            "WITH CHECK. Seed a row for the owner first. (This is a VACUOUS FIXTURE, "
            "not a leak: an UPDATE that matches zero rows cannot demonstrate either.)"
        )
        message = probe.refused(
            f"UPDATE {_ident(table)} SET tenant_id = %s WHERE tenant_id = %s",
            [str(intruder.id), str(owner.id)],
        )
    assert (
        "row-level security" in message
    ), f"{table}: a cross-tenant write was refused, but not by the RLS policy — {message}"
    return message


def assert_no_foreign_rows_anywhere(probe: RlsProbe, tenant, tables) -> None:
    """Under `tenant`'s context, not one row of any other tenant is reachable."""
    tenant_id = str(tenant.id)
    with live_tenant_context(tenant.id):
        for table in tables:
            foreign = probe.tenant_ids(table) - {tenant_id}
            assert not foreign, f"{table}: LEAK — {tenant_id} can see rows of {foreign}"


def rls_enabled_tables() -> list[str]:
    """Every table the migrations actually put a FORCE RLS policy on."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
            "AND c.relrowsecurity AND c.relforcerowsecurity ORDER BY c.relname"
        )
        return [row[0] for row in cursor.fetchall()]


# ── two-tenant fixtures for the raw-SQL tier ────────────────────────────────
@pytest.fixture()
def iso_tenants(db):
    """Two bare Tenant rows — for the cases that need no provisioning fixture."""
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Isolation Alpha", subdomain=f"isoalpha{suffix}")
    beta = Tenant.objects.create(name="Isolation Beta", subdomain=f"isobeta{suffix}")
    return alpha, beta
