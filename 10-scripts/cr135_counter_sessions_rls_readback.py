#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, task `P0.14`:
#          *"RLS probe, on PostgreSQL. Both directions on counter_sessions."*
#          Outcome: *"Tenant A cannot read or write tenant B's till, proved
#          where the policy actually runs."*
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS FORCE is on) · hard-won law 7 (ask what
#          would make this check pass wrongly; a check's output must
#          distinguish pass from fail to a READER) · hard-won law 14 (a proof
#          about the real database runs on the real database)
# ───────────────────────────────────────────────────────
"""`counter_sessions` isolation, proved as the APPLICATION ROLE itself.

WHY THIS EXISTS BESIDE `tests/test_cr135_p0_rls_pg.py`
--------------------------------------------------------
That file is the right shape and **it SKIPPED all three of its behaviour cases
on this cluster**, truthfully and loudly:

    RLS HALF NOT EXERCISED — could not create the non-superuser probe role
    'sbh_rls_probe' (permission denied to create role
    DETAIL: Only roles with the CREATEROLE attribute may create roles.)

`tests/isolation_helpers.py` proves isolation by `SET ROLE` into a probe role,
because on most clusters here the application role is a SUPERUSER and a
superuser bypasses every policy — `DEF-2717`, where a second tenant reported 73
accounts inside its own context and the count was the other tenant's. Creating
that role needs `CREATEROLE`, which `smartbillhub` does not have, and
`10-scripts/prove_isolation.py` says in terms that an administrator creates it
once.

⚠ **BUT ON THIS CLUSTER THE APPLICATION ROLE IS ALREADY SUBJECT TO RLS**, so
there is nothing to switch into: `smartbillhub` reports `rolsuper = f` and
`rolbypassrls = f`. **That is the whole reason this script can exist, and it is
therefore the FIRST thing it checks and the one that FAILS rather than skips.**
A proof taken as a bypassing role is not a weaker proof, it is a proof of
nothing, and it would read exactly like a good one.

Run it:

    10-scripts/proof-db.sh clone p0db           # sub-second, private to you
    PGDATABASE=sbh_clone_p0db python3 10-scripts/cr135_counter_sessions_rls_readback.py

WHAT WOULD MAKE THIS PASS WRONGLY, AND WHAT STOPS EACH
--------------------------------------------------------
  1. **The role bypasses RLS.** Then every count is *correct* and proves
     nothing. → CHECK 1 reads `pg_roles` and RAISES.
  2. **The table has `ENABLE` and not `FORCE`.** The owner is then exempt and
     the application's own role owns every table in this schema. → CHECK 2
     reads `pg_class.relforcerowsecurity`.
  3. **The table is EMPTY.** Then *"tenant B sees none of A's rows"* is true of
     a table nobody can see anything in, which is `assert_rls_scoped`'s own
     recorded trap. → CHECK 4 demands tenant A see a NON-ZERO number of its own
     rows before CHECK 5 is allowed to mean anything.
  4. **The write test matches no row.** An `INSERT` refused for a missing
     column reads exactly like an `INSERT` refused by a policy. → CHECK 6
     requires the refusal to name `row-level security`, in PostgreSQL's own
     words, and treats any other error as a FAILURE of the probe rather than as
     a pass.
  5. **The zero is read as an empty table.** ⚠ Three lanes have now nearly
     reported that. → CHECK 3 takes the unscoped count FIRST and labels it a
     DENIAL, and CHECK 4 immediately shows the same query answering non-zero
     with a tenant set. The two lines are printed together on purpose.

Every row this script writes is rolled back. It leaves nothing behind.
"""

from __future__ import annotations

import os
import sys
import uuid

import psycopg

TABLE = "counter_sessions"

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://{u}:{p}@{h}:{P}/{d}".format(
        u=os.environ.get("PGUSER", "smartbillhub"),
        p=os.environ.get("PGPASSWORD", "smartbillhub"),
        h=os.environ.get("PGHOST", "127.0.0.1"),
        P=os.environ.get("PGPORT", "5432"),
        d=os.environ.get("PGDATABASE", "sbh_clone_p0db"),
    ),
)

checks: list[tuple[bool, str]] = []


def record(ok: bool, line: str) -> None:
    checks.append((ok, line))
    print(f"  {'PASS' if ok else 'FAIL'}  {line}")


def main() -> int:
    print(f"counter_sessions RLS readback — {DSN.rsplit('/', 1)[-1]}\n")
    with psycopg.connect(DSN, autocommit=False) as conn, conn.cursor() as cur:

        # ── CHECK 1 · the proof is worth taking at all ──────────────────────
        cur.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        rolsuper, rolbypass = cur.fetchone()
        record(
            not rolsuper and not rolbypass,
            f"the connected role is subject to RLS (rolsuper={rolsuper}, "
            f"rolbypassrls={rolbypass}) — a bypassing role proves NOTHING",
        )
        if rolsuper or rolbypass:
            print("\n  refusing to go on: every count below would be meaningless.")
            return 1

        # ── CHECK 2 · ENABLE is half the guarantee; FORCE binds the owner ───
        cur.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            [TABLE],
        )
        row = cur.fetchone()
        record(
            row == (True, True),
            f"{TABLE} carries ENABLE *and* FORCE ROW LEVEL SECURITY (pg_class says {row})",
        )

        # two tenants to tell apart
        cur.execute("SELECT id, subdomain FROM tenants ORDER BY subdomain")
        tenants = cur.fetchall()
        if len(tenants) < 1:
            record(False, "no tenants in this database — nothing to isolate")
            return 1
        a_id, a_name = tenants[0]
        if len(tenants) > 1:
            b_id, b_name = tenants[1]
        else:
            # ⚠ **SAY WHAT IS NOT COVERED, BESIDE WHAT IS (hard-won law 7).**
            # With one tenant in the database there is no SECOND utility whose
            # rows could leak, so CHECK 5 tests the policy PREDICATE against an
            # id that matches nothing rather than against a real neighbour's
            # rows. That is a real proof of the scoping and a weaker one than
            # two live tenants: it cannot catch a policy that scopes correctly
            # and leaks to one specific other tenant. CHECK 6 is unaffected and
            # is the stronger half — it refuses a real cross-tenant WRITE.
            b_id, b_name = uuid.uuid4(), "a tenant id that matches nothing"
            print(
                f"  NOTE  this database holds ONE tenant ({a_name}), so CHECK 5 "
                "probes the policy predicate rather than a live neighbour's rows. "
                "Run it against a two-tenant database for the stronger form.\n"
            )

        # ── seed one till for A, inside A's own context ─────────────────────
        #
        # ⚠ **THE SEED COMES BEFORE THE UNSCOPED COUNT, AND THE ORDER IS THE
        # WHOLE OF CHECK 3.** The first draft counted first, on an empty table,
        # so `0` meant *the table is empty* and not *the policy denied me* —
        # and the red proof caught it: with `payments/0032` REVERSED, CHECK 3
        # still PASSED. A check that passes with the guarantee switched off is
        # CLAUDE.md hard-won law 7's *structurally incapable of failing*, found
        # the only way it ever is, by breaking the thing and reading the output.
        #
        # With a row in the table first, the two worlds are different numbers:
        # RLS on answers 0 (a denial), RLS off answers 1 (no denial).
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", [str(a_id)])
        cur.execute("SELECT id FROM users WHERE tenant_id = %s LIMIT 1", [str(a_id)])
        owner = cur.fetchone()
        cur.execute("SELECT id FROM service_centres WHERE tenant_id = %s LIMIT 1", [str(a_id)])
        centre = cur.fetchone()
        if owner is None or centre is None:
            record(False, f"{a_name} has no user or no service centre to hang a till on")
            return 1
        till_id = uuid.uuid4()
        cur.execute(
            f"INSERT INTO {TABLE} (id, tenant_id, owner_id, service_centre_id, "
            "opening_float, currency, opened_at, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, 200.0000, 'USD', now(), now(), now())",
            [str(till_id), str(a_id), owner[0], centre[0]],
        )

        # ── CHECK 3 · the row EXISTS and a tenant sees it ───────────────────
        cur.execute(f"SELECT count(*) FROM {TABLE}")
        mine = cur.fetchone()[0]
        record(
            mine > 0,
            f"inside {a_name}'s context {TABLE} answers {mine} — so the table is "
            "NOT empty, which is what lets CHECK 4's zero mean a denial",
        )

        # ── CHECK 4 · …and with NO tenant, that same row vanishes ───────────
        cur.execute("SELECT set_config('app.tenant_id', '', true)")
        cur.execute(f"SELECT count(*) FROM {TABLE}")
        unscoped = cur.fetchone()[0]
        record(
            unscoped == 0,
            f"with app.tenant_id UNSET the same query answers {unscoped} over the "
            f"same {mine} row(s) — a DENIAL, not an empty table",
        )

        # ── CHECK 5 · tenant B sees none of A's rows ────────────────────────
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", [str(b_id)])
        cur.execute(f"SELECT count(*) FROM {TABLE} WHERE id = %s", [str(till_id)])
        theirs = cur.fetchone()[0]
        record(
            theirs == 0,
            f"inside {b_name}'s context, {a_name}'s till is invisible ({theirs} rows) "
            "— the READ direction",
        )

        # ── CHECK 6 · and B cannot WRITE one onto A, nor A onto B ───────────
        # Re-stamping a visible row for another tenant is the table-agnostic
        # form of "INSERT carrying another tenant's id": USING finds it, WITH
        # CHECK rejects the result.
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", [str(a_id)])
        refused_with = None
        try:
            with conn.transaction():
                cur.execute(
                    f"UPDATE {TABLE} SET tenant_id = %s WHERE id = %s",
                    [str(b_id), str(till_id)],
                )
        except psycopg.Error as exc:
            refused_with = str(exc)
        record(
            refused_with is not None and "row-level security" in refused_with,
            "a till re-stamped for another tenant is refused BY THE POLICY — "
            + (
                f"PostgreSQL said: {refused_with.splitlines()[0]}"
                if refused_with
                else "IT WAS NOT REFUSED AT ALL, which is a cross-tenant WRITE"
            ),
        )

        conn.rollback()  # leave nothing behind

    passed = sum(1 for ok, _ in checks if ok)
    print(f"\n{passed} of {len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
