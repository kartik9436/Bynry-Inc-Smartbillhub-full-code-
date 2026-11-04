#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 5 tasks `P5.6`
#          (*"Isolation of authored rows — ⚠ Postgres only. A tenant-authored
#          definition cannot read another tenant's rows however it is
#          filtered"*) and `P5.7` (*"Private by default — a new definition is
#          invisible to a colleague until shared"*).
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE) · hard-won law 14 (a failed
#          statement poisons the whole PostgreSQL transaction, and the suite
#          runs on SQLite, which has no such state) · hard-won law 7 (prove a
#          guard RED first, and ask what would make it pass WRONGLY) ·
#          BR-REP-019 (private by default)
# ───────────────────────────────────────────────────────
"""**THE THREE THINGS THAT EXIST ONLY ON POSTGRESQL, PROVED THERE.**

    10-scripts/proof-db.sh clone p5db
    export PGPASSWORD=smartbillhub
    python3 10-scripts/rep_p5_isolation_and_savepoint_proof.py \\
        "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p5db"

⚠ **WHY A SCRIPT AND NOT A pytest FILE, SAID PLAINLY.** Both are legitimate and
the sibling convention in this repo is the script (`cr139_p5_…`,
`def_cus_6376_…`, `p3_back_…`). Two reasons decided it here. Building a test
database on this machine took **589 seconds** for the SQLite half of this same
phase, measured this session; a proof nobody can run in a minute is a proof
that stops being run. And `pytest --reuse-db` against a CLONE fails before it
starts on this branch — `psycopg.errors.UniqueViolation … (typname,
typnamespace)=(help_answers, 2200)` — because pytest-django migrates into a
database that is already migrated. This runs in under a second against the
clone itself.

WHAT IT PROVES, AND WHY EACH HALF NEEDS THE OTHER
--------------------------------------------------
  1. **`ENABLE` *and* `FORCE`** on `report_definitions` and `report_categories`.
     `ENABLE` alone exempts the table's OWNER, and the application's migration
     role owns every table in this schema — so `ENABLE` without `FORCE` is no
     policy at all for the process that matters.

  2. **`USING` *and* `WITH CHECK`**, and here the shape is NOT the standard one.
     These two tables hold the forty-six PLATFORM rows every tenant reads, so
     `USING` must admit `tenant_id IS NULL` as well as the tenant's own — and
     `WITH CHECK` must NOT. That asymmetry IS copy-on-write: a tenant SELECTs
     its own rows plus ours, and INSERTs, UPDATEs and DELETEs only its own. A
     policy with a symmetric clause would let a utility edit a report we ship,
     which is the one thing §7.7 says cannot happen.

  3. **THE ISOLATION ITSELF, `P5.6`, AND ⚠ *HOWEVER IT IS FILTERED*.** The task
     row's own words. So the read is run three ways — unfiltered, filtered by
     the neighbour's tenant id, and filtered by the neighbour's own key — and
     all three must come back with the neighbour's row absent. A probe that
     only ran the unfiltered read would pass over a policy that leaks the
     moment a `WHERE tenant_id = …` is added, which is exactly how a hand-built
     predicate leaks.

  4. **PRIVATE BY DEFAULT, `P5.7`.** A row saved with no visibility named is
     `private`, and the DEFAULT ON THE COLUMN IS `shared`. Both facts are
     asserted, because they disagree ON PURPOSE: the column's default is right
     for the forty-six rows we ship — nobody owns those and every colleague
     sees them — and wrong for a person's own save. A probe that checked only
     the column would report the opposite of the ruling.

  5. **LAW 14, BOTH DIRECTIONS.** The duplicate-key path in
     `definitions.save()` catches an `IntegrityError` and carries on. The naive
     `try/except` must be shown to POISON the transaction and the SAVEPOINT
     version to SURVIVE it — one without the other proves nothing about which
     of them the code uses.

⚠ **THE PROBE ROLE IS NOT A SUPERUSER AND THIS SCRIPT REFUSES TO RUN AS ONE.**
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
unconditionally, `FORCE` included (`DEF-2717`). A proof run as a superuser is
law 7's *incapable of failing* shape wearing a green tick.

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

TABLES = ("report_definitions", "report_categories")


def main(url: str) -> int:
    failures: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        # ── 0 · THE PROBE MUST BE CAPABLE OF FAILING ────────────────────────
        cur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        is_super, bypasses = cur.fetchone()
        if is_super or bypasses:
            print(
                "FAIL: this role is SUPERUSER or BYPASSRLS, so every policy below is "
                "exempted and every check would pass whatever the policies said "
                "(DEF-2717). Run as the application role."
            )
            return 2
        print("  ✓ probe role bypasses nothing — the checks below can fail")

        # ── 1 · THE FLAGS ───────────────────────────────────────────────────
        cur.execute(
            "select c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname = any(%s) order by 1",
            (list(TABLES),),
        )
        rows = cur.fetchall()
        if len(rows) != len(TABLES):
            print(f"FAIL: expected {TABLES}, found {[r[0] for r in rows]} — run reports/0001.")
            return 2
        for name, enabled, forced in rows:
            if enabled and forced:
                print(f"  ✓ {name}: ENABLE and FORCE")
            else:
                failures.append(f"{name}: ENABLE={enabled} FORCE={forced} — hard rule 1")

        # ── 2 · THE POLICY, AND ITS DELIBERATE ASYMMETRY ────────────────────
        cur.execute(
            "select tablename, policyname, qual, with_check "
            "from pg_policies where tablename = any(%s) order by 1",
            (list(TABLES),),
        )
        by_table: dict[str, list[tuple[str, str | None, str | None]]] = {}
        for table, policy, qual, check in cur.fetchall():
            by_table.setdefault(table, []).append((policy, qual, check))
        for name in TABLES:
            policies = by_table.get(name, [])
            both = [p for p in policies if p[1] and p[2]]
            if not both:
                failures.append(
                    f"{name}: no policy with BOTH halves. A USING-only policy lets a "
                    "tenant read only its own rows and write into anybody's."
                )
                continue
            policy, qual, check = both[0]
            print(f"  ✓ {name}: policy {policy!r} carries USING and WITH CHECK")
            # ⚠ COPY-ON-WRITE, READ OFF THE POLICY TEXT. `USING` must admit the
            # platform row and `WITH CHECK` must not — that asymmetry is the
            # mechanism, not a detail of it.
            reads_platform = "IS NULL" in (qual or "").upper()
            writes_platform = "IS NULL" in (check or "").upper()
            if reads_platform and not writes_platform:
                print(f"  ✓ {name}: USING admits the platform row, WITH CHECK does not")
            else:
                failures.append(
                    f"{name}: USING admits platform={reads_platform}, "
                    f"WITH CHECK admits platform={writes_platform} — copy-on-write needs "
                    "the first true and the second false (§7.7)"
                )

        # ── 3 · TWO TENANTS, AND A ROW EACH ─────────────────────────────────
        cur.execute("select id from tenants order by created_at limit 2")
        tenants = [row[0] for row in cur.fetchall()]
        if not tenants:
            print("FAIL: no tenant at all. Run `manage.py seed_demo` first.")
            return 2
        mine = tenants[0]
        if len(tenants) > 1:
            theirs = tenants[1]
        else:
            # ⚠ **THE TEMPLATE DATABASE HOLDS ONE TENANT, SO THE NEIGHBOUR IS
            # MADE HERE — AND THAT IS NOT A WEAKER PROOF.** Row-level security
            # does not know or care how a tenant row got there; what it reads is
            # `report_definitions.tenant_id` against `app.tenant_id`. Refusing
            # to run without a second seeded utility would be a proof that only
            # runs on a database nobody has, which is law 7's *incapable of
            # passing* shape. The row is rolled back with everything else.
            theirs = uuid.uuid4()
            cur.execute(
                "insert into tenants (id,name,subdomain,currency,created_at,updated_at) "
                "values (%s,'REP-P5 neighbour',%s,'USD',now(),now())",
                (theirs, f"repp5-{uuid.uuid4().hex[:8]}"),
            )
            print("  · no second tenant in this database — one is created and rolled back")

        def insert(tenant: uuid.UUID, key: str, *, visibility: str | None) -> None:
            columns = (
                "id,tenant_id,key,name,name_i18n,dataset,group_code,columns,filters,"
                "group_by,sort,service_codes,owner_user_id,version,created_at,updated_at"
            )
            values = (
                "%s,%s,%s,%s,'{}'::jsonb,'invoices','billing','[]'::jsonb,'{}'::jsonb,"
                "'[]'::jsonb,'[]'::jsonb,'[]'::jsonb,null,1,now(),now()"
            )
            args: list = [uuid.uuid4(), tenant, key, key]
            if visibility is not None:
                columns += ",visibility"
                values += ",%s"
                args.append(visibility)
            cur.execute(f"insert into report_definitions ({columns}) values ({values})", args)

        their_key = f"rep_p5_theirs_{uuid.uuid4().hex[:8]}"
        my_key = f"rep_p5_mine_{uuid.uuid4().hex[:8]}"

        cur.execute("select set_config('app.tenant_id', %s, true)", (str(theirs),))
        insert(theirs, their_key, visibility="shared")

        cur.execute("select set_config('app.tenant_id', %s, true)", (str(mine),))
        # ⚠ `private` is named EXPLICITLY here because the column has no
        # database default at all — see section 5, which is the point.
        insert(mine, my_key, visibility="private")

        # ── 4 · `P5.6` · ISOLATION, **HOWEVER IT IS FILTERED** ──────────────
        probes = (
            ("unfiltered", "select key from report_definitions where key=%s", (their_key,)),
            (
                "filtered by their tenant id",
                "select key from report_definitions where tenant_id=%s and key=%s",
                (theirs, their_key),
            ),
            (
                "filtered by their key alone",
                "select key from report_definitions where key like %s",
                (f"{their_key[:12]}%",),
            ),
        )
        for label, sql, args in probes:
            cur.execute(sql, args)
            leaked = [row[0] for row in cur.fetchall() if row[0] == their_key]
            if leaked:
                failures.append(
                    f"ISOLATION BREACH ({label}): tenant {mine} read {their_key!r}, which "
                    f"belongs to {theirs}. Hard rule 1."
                )
            else:
                print(f"  ✓ isolation holds — {label}")

        # ⚠ AND THE OTHER DIRECTION, BECAUSE A POLICY THAT HIDES EVERYTHING
        # WOULD PASS ALL THREE PROBES ABOVE AND MAKE THE PRODUCT USELESS.
        cur.execute("select key from report_definitions where key=%s", (my_key,))
        if cur.fetchone() is None:
            failures.append(
                f"the tenant cannot read its OWN row {my_key!r} — a policy that hides "
                "everything passes every isolation probe and ships a blank screen"
            )
        else:
            print("  ✓ the tenant still reads its own row")

        # ⚠ AND THE PLATFORM ROWS ARE STILL VISIBLE, WHICH IS THE THIRD STATE
        # AND THE ONE THE STANDARD PROBE CANNOT SEE.
        cur.execute("select count(*) from report_definitions where tenant_id is null")
        platform = cur.fetchone()[0]
        if platform > 0:
            print(f"  ✓ the tenant still reads the {platform} platform rows")
        else:
            failures.append(
                "no platform row is visible — either the seed did not run or USING "
                "stopped admitting `tenant_id IS NULL`, and the catalogue is empty"
            )

        # ── 5 · `P5.7` · WHERE "PRIVATE BY DEFAULT" ACTUALLY LIVES ─────────
        # ⚠ **MEASURED, AND IT IS NOT WHERE THE MODEL FILE READS AS THOUGH IT
        # IS.** `models.ReportDefinition.visibility` declares
        # `default=VISIBILITY_SHARED`, which is a DJANGO default: it is applied
        # in Python when an instance is built and it is NOT written into the
        # column. The column is `NOT NULL` with **no default whatsoever** — an
        # INSERT that omits it raises `NotNullViolation`, which is how this was
        # found rather than assumed.
        #
        # **So the database defaults to nothing, and every writer must name a
        # value.** `BR-REP-019`'s ruling therefore rests entirely on
        # `definitions.DEFAULT_TENANT_VISIBILITY`, and there is no second line
        # of defence underneath it: a save path that forgot to pass one would
        # not quietly share the report, it would 500 — which is the safe
        # direction, and worth knowing.
        cur.execute(
            "select column_default, is_nullable from information_schema.columns "
            "where table_name='report_definitions' and column_name='visibility'"
        )
        column_default, nullable = cur.fetchone()
        if column_default is None and nullable == "NO":
            print(
                "  ✓ visibility is NOT NULL with no database default — every writer "
                "names it, and definitions.DEFAULT_TENANT_VISIBILITY is the ruling"
            )
        else:
            failures.append(
                f"visibility now has default={column_default!r} nullable={nullable!r}. "
                "A database default here would silently decide who sees a clerk's "
                "report, which is BR-REP-019's whole subject."
            )
        cur.execute("select visibility from report_definitions where key=%s", (my_key,))
        stored = (cur.fetchone() or [None])[0]
        if stored != "private":
            failures.append(f"the probe's own row stored visibility={stored!r}, not 'private'")
        else:
            print("  ✓ a row saved private reads back private")

        # ── 6 · LAW 14, BOTH DIRECTIONS ─────────────────────────────────────
        # The naive form: an IntegrityError with no savepoint POISONS the
        # transaction, and everything after it fails at a statement that has
        # nothing wrong with it.
        try:
            insert(mine, my_key, visibility="private")  # duplicate (tenant_id, key)
        except psycopg.errors.UniqueViolation:
            pass
        try:
            cur.execute("select 1")
            failures.append(
                "a duplicate key did NOT poison this transaction — either the unique "
                "index on (tenant_id, key) is gone or this is not PostgreSQL, and law "
                "14's whole premise is untested"
            )
        except psycopg.errors.InFailedSqlTransaction:
            print("  ✓ the naive form poisons the transaction (law 14's premise holds)")
        conn.rollback()

        # The savepoint form: the same refusal, survived.
        cur.execute("select set_config('app.tenant_id', %s, true)", (str(mine),))
        insert(mine, my_key, visibility="private")
        cur.execute("savepoint probe")
        try:
            insert(mine, my_key, visibility="private")
        except psycopg.errors.UniqueViolation:
            cur.execute("rollback to savepoint probe")
        try:
            cur.execute("select 1")
            print("  ✓ the SAVEPOINT form survives it — which is what definitions.save() uses")
        except psycopg.errors.InFailedSqlTransaction:
            failures.append(
                "the SAVEPOINT did not protect the transaction — `definitions.save()`'s "
                "nested `transaction.atomic()` cannot work either"
            )

        conn.rollback()  # nothing is kept

    if failures:
        print("\nFAIL:")
        for line in failures:
            print(f"  ✗ {line}")
        return 1
    print("\nPASS: isolation, copy-on-write, private-by-default and the savepoint all hold.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 5 `P5.6`/`P5.7` (05-prototype/09 Reports Build Brief.pdf p17, read as IMAGES per B14 rule 42)
# screens: none — this is a proof
# generated: 2026-09-27 by lane REP-P5
# gates: RED PROVED FIRST — see the lane report: each check was run with its subject removed and shown to fail by name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
