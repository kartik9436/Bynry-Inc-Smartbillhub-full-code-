#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the SIX tables the three `P6.11` joining reads touch, proved
#            isolated on REAL PostgreSQL as a role that is neither SUPERUSER
#            nor BYPASSRLS. The test suite runs on in-memory SQLite
#            (`config/settings/test.py` hardcodes it and ignores
#            `DATABASE_URL`), where row-level security does not exist at all —
#            so the guarantee cannot be proved there and `G5` once called 192
#            skips a pass (CLAUDE.md hard-won law 7, *incapable of failing*).
# Rules:     CLAUDE.md hard rule 1 (never touch a tenant table without
#            `app.tenant_id`; RLS FORCE is on) · hard-won law 7 (prove a guard
#            RED first, and a check whose output cannot distinguish pass from
#            fail is worse than none) · law 14 (the suite's backend cannot
#            answer this question).
# ───────────────────────────────────────────────────────
"""ISOLATION FOR R36, R32 AND R23 — six tables, two tenants, nothing crosses.

`rep_ds_accounts_rls_proof.py` covers `accounts`, `audit_log` and
`outbound_messages`. **It covers none of the six tables these three reports
read**, which is why this exists rather than a line being added to that one:
a proof that names three tables is a claim about three tables.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **A SUPERUSER or BYPASSRLS role.** PostgreSQL exempts both from every
    policy, so every check below would pass whatever the policies said. Probe 0
    reads `pg_roles` and REFUSES.
  * **MEASURING AN EMPTY TABLE.** *"The neighbour's row is absent"* is true of
    a table with no rows in it, and of a read that is simply broken. So the
    neighbour's rows are PLANTED and probe 5 switches to the NEIGHBOUR'S OWN
    CONTEXT and asserts they ARE visible there. **That is the red-first
    control** — if it comes back zero the probe stops, because everything after
    it would be measuring nothing.
  * **A zero beside a zero.** Probe 6 asserts MY OWN count is NON-ZERO on every
    table before it believes the neighbour's zero. A completely broken read
    returns zero for both and would otherwise look like perfect isolation.
  * **Filtering by tenant in the query itself.** Probe 6 asks three ways: the
    UNFILTERED count, a count `where tenant_id = <theirs>`, and a count on a
    column value only the neighbour's row carries. A policy that worked only
    because the ORM adds a filter cannot survive the second and third.

⚠ **WHAT THIS DOES NOT PROVE, stated rather than left blank** (hard-won law 7's
fifth shape — a number over a scope it silently excludes):

  * the ORM's own tenant filter → the three pytest files;
  * LIMIT/OFFSET cost and the query plan → `10-scripts/p6_join_cost.py`;
  * **`BR-REP-023`'s restriction on who may RUN R36 → NOTHING ENFORCES IT.**
    `P5.9` is open and untouched; this proof is about the DATABASE and cannot
    stand in for an authorisation check that does not exist.

USAGE
    python3 10-scripts/p6_join_rls_proof.py \\
      postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p6join
"""

from __future__ import annotations

import sys
import uuid

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("FAIL: psycopg is not installed. This proof needs a real PostgreSQL connection.")
    raise SystemExit(2)

#: Each table, the column its neighbour row is planted in, and the value —
#: chosen so probe 6's third question has something only the neighbour carries.
#:
#: ⚠ **`users` AND `tenant_memberships` ARE BOTH HERE.** R36 joins them, and a
#: policy on one is not a policy on the other: a membership scoped correctly
#: beside a user table that is not would leak a name and an email address,
#: which on a security report is the whole payload.
SUBJECTS = (
    ("users", "email", "p6join-neighbour@example.invalid"),
    ("tenant_memberships", "status", "p6join_rls_neighbour"),
    ("read_import_batches", "file_name", "P6JOIN-RLS-NEIGHBOUR.csv"),
    ("read_import_rows", "meter_no_raw", "P6JOIN-RLS-NEIGHBOUR"),
    ("move_records", "move_no", "P6JOIN-RLS-NEIGHBOUR"),
    ("transfers", "transfer_no", "P6JOIN-RLS-NEIGHBOUR"),
)


def _set_tenant(cur, tenant) -> None:
    cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant),))


def _two_tenants(cur) -> tuple[str, str]:
    cur.execute("select id from tenants order by created_at limit 2")
    rows = cur.fetchall()
    if len(rows) < 2:
        print(
            "FAIL: this database holds fewer than two tenants, so there is no neighbour to "
            "be isolated from. Provision a second one before running this."
        )
        raise SystemExit(2)
    return str(rows[0][0]), str(rows[1][0])


def _plant(cur, theirs: str) -> None:
    """The neighbour's six rows, written under the NEIGHBOUR'S own context.

    ⚠ **THE NEIGHBOUR MAKES ITS OWN AND BORROWS NOTHING OF MINE.** A row that
    reused one of my ids would be visible to me for a reason that has nothing to
    do with a policy, and the proof would be measuring a foreign key.
    """
    _set_tenant(cur, theirs)
    role_id = uuid.uuid4()
    cur.execute(
        "insert into roles (id, code, name, created_at, updated_at) "
        "values (%s, %s, 'P6JOIN neighbour role', now(), now()) "
        "on conflict (code) do update set name = excluded.name returning id",
        (role_id, f"p6join_neighbour_{uuid.uuid4().hex[:8]}"),
    )
    role_id = cur.fetchone()[0]

    user_id = uuid.uuid4()
    # ⚠ **EVERY NOT-NULL COLUMN WITHOUT A DEFAULT IS NAMED.** The first draft
    # listed only the interesting ones and PostgreSQL refused the insert — which
    # is the database doing this script's job for it, and the right way round.
    cur.execute(
        "insert into users (id, tenant_id, email, full_name, must_change_password, "
        "failed_attempts, surface_scope, created_at, updated_at) "
        "values (%s, %s, %s, 'P6JOIN Neighbour', false, 0, 'both', now(), now())",
        (user_id, theirs, "p6join-neighbour@example.invalid"),
    )
    cur.execute(
        "insert into tenant_memberships (id, tenant_id, user_id, role_id, status, "
        "created_at, updated_at) values (%s, %s, %s, %s, %s, now(), now())",
        (uuid.uuid4(), theirs, user_id, role_id, "p6join_rls_neighbour"),
    )

    batch_id = uuid.uuid4()
    cur.execute(
        "insert into read_import_batches (id, tenant_id, file_name, source_kind, "
        "write_mode, status, certified_by_uploader, created_at, updated_at) "
        "values (%s, %s, %s, 'csv', 'insert', 'posted', false, now(), now())",
        (batch_id, theirs, "P6JOIN-RLS-NEIGHBOUR.csv"),
    )
    cur.execute(
        "insert into read_import_rows (id, tenant_id, batch_id, row_no, meter_no_raw, "
        "channel, severity, demand_reset_noted, created_at, updated_at) "
        "values (%s, %s, %s, 1, %s, 'total', 'ok', false, now(), now())",
        (uuid.uuid4(), theirs, batch_id, "P6JOIN-RLS-NEIGHBOUR"),
    )

    cur.execute("select id from accounts where tenant_id = %s limit 1", (theirs,))
    found = cur.fetchone()
    if found is None:
        print(
            "FAIL: the neighbour tenant holds no account, so a move record and a transfer "
            "have nothing to hang on. This proof would silently cover four tables instead "
            "of six — a blind spot with no number beside it (hard-won law 7)."
        )
        raise SystemExit(2)
    account_id = found[0]
    cur.execute(
        "insert into move_records (id, tenant_id, account_id, move_no, kind, effective_on, "
        "performed_at, reads_committed, is_sample, created_at, updated_at) "
        "values (%s, %s, %s, %s, 'move_in', current_date, now(), 0, false, now(), now())",
        (uuid.uuid4(), theirs, account_id, "P6JOIN-RLS-NEIGHBOUR"),
    )
    cur.execute(
        "insert into transfers (id, tenant_id, transfer_no, from_account_id, step, state, "
        "is_sample, created_at, updated_at) "
        "values (%s, %s, %s, %s, 1, 'done', false, now(), now())",
        (uuid.uuid4(), theirs, "P6JOIN-RLS-NEIGHBOUR", account_id),
    )


def main(url: str) -> int:
    failures: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        # ── 0 · THE PROBE MUST BE CAPABLE OF FAILING ────────────────────────
        cur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        is_super, bypasses = cur.fetchone()
        if is_super or bypasses:
            print(
                "FAIL: this role is SUPERUSER or BYPASSRLS, so every policy below is exempted "
                "and every check would pass whatever the policies said. Run as the "
                "application role."
            )
            return 2
        print("  ✓ probe role bypasses nothing — the checks below can fail")

        names = [name for name, _, _ in SUBJECTS]

        # ── 1 · THE FLAGS ───────────────────────────────────────────────────
        cur.execute(
            "select c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname = any(%s) order by 1",
            (names,),
        )
        found = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        missing = [name for name in names if name not in found]
        if missing:
            print(f"FAIL: these tables are not in this database: {missing}")
            return 2
        for name in names:
            enabled, forced = found[name]
            if enabled and forced:
                print(f"  ✓ {name}: ENABLE and FORCE")
            else:
                failures.append(f"{name}: ENABLE={enabled} FORCE={forced} — hard rule 1")

        mine, theirs = _two_tenants(cur)
        print(f"  · mine {mine} · neighbour {theirs}")

        # ── 2 · PLANT THE NEIGHBOUR'S ROWS ──────────────────────────────────
        _plant(cur, theirs)

        # ── 3 · THE RED-FIRST CONTROL ───────────────────────────────────────
        # ⚠ Without this the whole proof could be measuring an empty table.
        for table, column, value in SUBJECTS:
            cur.execute(f"select count(*) from {table} where {column} = %s", (value,))  # noqa: S608
            seen = cur.fetchone()[0]
            if seen != 1:
                print(
                    f"FAIL: as the NEIGHBOUR, {table} shows {seen} of its own planted rows. "
                    "This probe would be measuring an empty table, not isolation."
                )
                conn.rollback()
                return 2
            print(f"  ✓ {table}: the neighbour sees its own planted row (red-first control)")

        # ── 4 · THE ISOLATION, THREE WAYS, WITH A NON-ZERO OWN COUNT ────────
        _set_tenant(cur, mine)
        for table, column, value in SUBJECTS:
            cur.execute(f"select count(*) from {table}")  # noqa: S608
            own = cur.fetchone()[0]
            cur.execute(
                f"select count(*) from {table} where tenant_id = %s", (theirs,)  # noqa: S608
            )
            by_tenant = cur.fetchone()[0]
            cur.execute(f"select count(*) from {table} where {column} = %s", (value,))  # noqa: S608
            by_value = cur.fetchone()[0]

            if own == 0:
                failures.append(
                    f"{table}: MY OWN count is zero, so 'the neighbour is absent' is true of a "
                    "completely broken read. A zero beside a zero proves nothing."
                )
                continue
            if by_tenant or by_value:
                failures.append(
                    f"{table}: the neighbour's row is VISIBLE — unfiltered_own={own}, "
                    f"by_tenant_id={by_tenant}, by_{column}={by_value}. Hard rule 1."
                )
                continue
            print(
                f"  ✓ {table}: own rows {own} (non-zero) · neighbour by tenant_id 0 · "
                f"neighbour by {column} 0"
            )

        conn.rollback()
        print("  · everything above was rolled back; no row was kept")

    print()
    print("NOT PROVED HERE, and each has its own check:")
    print("  · the ORM's own tenant filter → the three pytest files")
    print("  · LIMIT/OFFSET cost and the query plan → 10-scripts/p6_join_cost.py")
    print("  · BR-REP-023's restriction on R36 → NOTHING ENFORCES IT (P5.9 is open)")
    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS — six tables, two tenants, nothing crosses.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
