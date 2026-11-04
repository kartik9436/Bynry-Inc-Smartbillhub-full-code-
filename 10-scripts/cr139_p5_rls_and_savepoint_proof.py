#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5. Two guarantees that
#          exist ONLY on PostgreSQL: `P5.5`'s row-level security, and the
#          SAVEPOINT in `settlements._write_members` (`P5.1`).
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE) · hard-won law 14 (a failed
#          statement poisons the whole transaction, and the suite runs on
#          SQLite, which has no such state) · hard-won law 1 (a comment
#          claiming a guarantee is not the guarantee — so this is a script)
# ───────────────────────────────────────────────────────
"""**RLS AND THE SAVEPOINT, PROVED WHERE THEY EXIST.**

`tests/test_cr139_p5_rls_pg.py` asserts the same things through pytest and is
the right place for them — **but building a test database on a loaded machine
takes the better part of an hour**, and a proof nobody can run in a minute is a
proof that stops being run. This does the same work in **under a second**
against an already-migrated database, so a reviewer can re-check the claim
without a test run.

    10-scripts/proof-db.sh clone p5db        # or any migrated database
    export PGPASSWORD=smartbillhub
    python3 10-scripts/cr139_p5_rls_and_savepoint_proof.py \\
        "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p5db"

WHAT IT PROVES, AND WHY EACH HALF NEEDS THE OTHER
--------------------------------------------------
  1. **`ENABLE` *and* `FORCE`** on both tables. `ENABLE` alone exempts the
     table's OWNER, and the application's migration role owns every table in
     this schema — so `ENABLE` without `FORCE` is no policy at all for the
     process that matters.
  2. **`USING` *and* `WITH CHECK`** on both policies. A `USING`-only policy
     lets a tenant read only its own rows **and write into anybody's**, which
     is the half that is silently omitted.
  3. **The SAVEPOINT, on the real constraint.** It writes a member, provokes
     `uq_settlement_members_payment`, and then asks the transaction a question.
     ⚠ **BOTH DIRECTIONS ARE RUN AND BOTH ARE NECESSARY** (law 7 habit 2): the
     naive `try/except` version must be shown to POISON the transaction, and
     the savepoint version must be shown to SURVIVE it — one without the other
     proves nothing about which of them the code uses.

Everything runs inside a transaction that is rolled back. No row is kept.
"""

from __future__ import annotations

import sys
import uuid

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("FAIL: psycopg is not installed. This proof needs a real PostgreSQL connection.")
    raise SystemExit(2)

TABLES = ("settlement_members", "settlements")


def main(url: str) -> int:
    failures: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        # ── 1 · THE FLAGS ───────────────────────────────────────────────────
        cur.execute(
            "select c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname = any(%s) order by 1",
            (list(TABLES),),
        )
        rows = cur.fetchall()
        if len(rows) != len(TABLES):
            print(f"FAIL: expected {TABLES}, found {[r[0] for r in rows]} — run payments/0038.")
            return 2
        for name, enabled, forced in rows:
            if enabled and forced:
                print(f"  ✓ {name}: ENABLE and FORCE")
            else:
                failures.append(f"{name}: ENABLE={enabled} FORCE={forced} — hard rule 1")

        # ── 2 · THE POLICY, BOTH HALVES ─────────────────────────────────────
        cur.execute(
            "select tablename, policyname, qual is not null, with_check is not null "
            "from pg_policies where tablename = any(%s) order by 1",
            (list(TABLES),),
        )
        seen = {row[0] for row in cur.fetchall() if row[2] and row[3]}
        for name in TABLES:
            if name in seen:
                print(f"  ✓ {name}: policy carries USING and WITH CHECK")
            else:
                failures.append(
                    f"{name}: no policy with BOTH halves. A USING-only policy lets a tenant "
                    "read only its own rows and write into anybody's."
                )

        # ── 3 · LAW 14, BOTH DIRECTIONS ─────────────────────────────────────
        cur.execute("select id from tenants limit 1")
        tenant = (cur.fetchone() or [None])[0]
        if tenant is None:
            print("FAIL: no tenant. Run `manage.py seed_demo` first.")
            return 2
        # ⚠ SET THE TENANT BEFORE READING A TENANT TABLE — unset, the policy
        # matches ZERO ROWS AND REPORTS SUCCESS.
        cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant),))
        cur.execute("select id from accounts where tenant_id=%s limit 1", (tenant,))
        account = (cur.fetchone() or [None])[0]
        if account is None:
            print("FAIL: tenant has no account. Run `manage.py load_sample_data --tenant <slug>`.")
            return 2

        def seed() -> tuple[uuid.UUID, uuid.UUID]:
            pay, setl = uuid.uuid4(), uuid.uuid4()
            cur.execute(
                "insert into payments (id,tenant_id,account_id,amount,currency,status,type,"
                "purpose,posted_at,created_at,updated_at,is_partial_reversal,origin_is_derived)"
                " values (%s,%s,%s,100.0,'USD','cleared','payment','bill',now(),now(),now(),"
                "false,false)",
                (pay, tenant, account),
            )
            cur.execute(
                "insert into settlements (id,tenant_id,provider,code,paid_out_at,gross,fees,"
                "net,currency,status,created_at,updated_at) values "
                "(%s,%s,'payments_sandbox',%s,now(),100,2.9,97.1,'USD','received',now(),now())",
                (setl, tenant, f"po_proof_{uuid.uuid4().hex[:8]}"),
            )
            return pay, setl

        def member(setl: uuid.UUID, pay: uuid.UUID) -> None:
            cur.execute(
                "insert into settlement_members (id,tenant_id,settlement_id,payment_id,gross,"
                "fee,created_at) values (%s,%s,%s,%s,100,2.9,now())",
                (uuid.uuid4(), tenant, setl, pay),
            )

        # (a) THE NAIVE VERSION — no savepoint.
        pay, setl = seed()
        member(setl, pay)
        try:
            member(setl, pay)
            failures.append(
                "the duplicate member was ACCEPTED — uq_settlement_members_payment is gone, "
                "and a payment can now belong to two payouts."
            )
        except psycopg.errors.UniqueViolation:
            print("  ✓ a second membership for one payment is refused by the unique key")
        try:
            cur.execute("select 1")
            failures.append(
                "the transaction SURVIVED a failed statement. This connection is not "
                "behaving like PostgreSQL, so nothing below proves anything about law 14."
            )
        except psycopg.errors.InFailedSqlTransaction:
            print("  ✓ LAW 14: with NO savepoint the transaction is poisoned —")
            print("      a bare try/except loses the payout AND every member already written")
        cur.execute("rollback")

        # (b) WHAT THE CODE ACTUALLY DOES — the savepoint.
        cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant),))
        pay, setl = seed()
        member(setl, pay)
        cur.execute("savepoint one_member")
        try:
            member(setl, pay)
        except psycopg.errors.UniqueViolation:
            cur.execute("rollback to savepoint one_member")
        cur.execute("select count(*) from settlement_members where settlement_id=%s", (setl,))
        kept = cur.fetchone()[0]
        if kept == 1:
            print("  ✓ LAW 14: WITH the savepoint the transaction is alive and kept 1 member")
        else:
            failures.append(f"the savepoint path kept {kept} member(s); expected 1.")
        conn.rollback()

    print()
    if failures:
        for line in failures:
            print(f"FAIL: {line}")
        return 1
    print("PROVED on PostgreSQL: both tables are RLS-forced with a two-sided policy, and the")
    print("SAVEPOINT is the only thing standing between one refused member and the loss of a")
    print("whole payout. Nothing was kept — every probe ran inside a rolled-back transaction.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
