#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 · lane DS-ACCOUNTS — the tenant isolation of the three
#          dataset queries this lane built, proved on REAL PostgreSQL:
#            `accounts` (R22) · `audit_log` (R35) · `notifications` (R8).
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE; no cross-tenant queryset) ·
#          hard-won law 14 (the suite runs on in-memory SQLite, which has no
#          row-level security at all, so this cannot be a pytest case) ·
#          hard-won law 7 (prove a guard RED first; ask what would make it pass
#          WRONGLY; and print what you SKIPPED beside what you checked) ·
#          BR-AUD-007 (audit_log is FORCE-RLS on the partitioned PARENT)
# ───────────────────────────────────────────────────────
"""**TWO TENANTS, THREE TABLES, AND A READ THAT MUST NOT CROSS.**

    10-scripts/proof-db.sh clone dsacct
    export PGPASSWORD=smartbillhub
    python3 10-scripts/rep_ds_accounts_rls_proof.py \\
        "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_dsacct"

⚠ **WHY A SCRIPT AND NOT A pytest CASE.** `config/settings/test.py` hardcodes
in-memory SQLite and ignores `DATABASE_URL` (hard-won law 14), and **SQLite has
no row-level security at all** — so a pytest case asserting isolation on the
default suite is law 7's *incapable of failing* shape wearing a green tick.
`G5` once ran the whole isolation suite on sqlite and called 192 skips a pass.

⚠ **THE PROBE ROLE IS NOT A SUPERUSER AND THIS SCRIPT REFUSES TO RUN AS ONE.**
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
unconditionally, `FORCE` included (`DEF-2717`). That check is step 0 and it
EXITS; everything after it would otherwise pass whatever the policies said.

WHAT IT PROVES, AND WHY EACH PART NEEDS THE OTHERS
--------------------------------------------------
  1. **`ENABLE` *and* `FORCE`** on `accounts`, `audit_log` and
     `outbound_messages`. `ENABLE` alone exempts the table's OWNER, and the
     application's migration role owns every table in this schema — so `ENABLE`
     without `FORCE` is no policy at all for the process that matters.

  2. **`USING` *and* `WITH CHECK`.** A `USING`-only policy lets a tenant read
     only its own rows and **write into anybody's**.

  3. **THE ISOLATION ITSELF, THREE WAYS AND NOT ONE.** Each read is run
     unfiltered, filtered BY THE NEIGHBOUR'S TENANT ID, and filtered by a
     column value only the neighbour's row carries. A probe that ran only the
     unfiltered read passes over a policy that leaks the moment a
     `WHERE tenant_id = …` is added — which is exactly how a hand-built
     predicate leaks.

  4. **⚠ A NON-ZERO OWN COUNT BESIDE EVERY ZERO.** The commonest false pass in
     this repository is a query returning nothing reading as *no error*. With
     `app.tenant_id` unset every one of these tables returns zero rows in a
     millisecond, so *"the neighbour's row is absent"* would be true of a
     completely broken read. **Every case asserts MY OWN count is positive in
     the same breath**, so an empty database fails before the isolation
     assertion can pass.

  5. **AND IT IS SHOWN RED FIRST.** Step 5 sets `app.tenant_id` to the
     NEIGHBOUR and asserts the neighbour's row IS visible. If that comes back
     empty, the probe is not measuring isolation — it is measuring an empty
     table, and it says so and exits.

WHAT THIS DOES **NOT** PROVE, printed beside what it does (law 7's fifth
clause — a declared blind spot with no NUMBER beside it is indistinguishable
from an empty one): it does not exercise the Django ORM path at all. It proves
the DATABASE refuses; the app-layer `tenant_id=current_tenant_id()` filter that
every query in the three modules carries as belt-and-policy is asserted in the
pytest files.

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

#: The three tables the three dataset queries read, and the column each one's
#: neighbour row is planted in so the third probe has something to filter on.
SUBJECTS = (
    ("accounts", "account_no", "DSA-RLS-NEIGHBOUR"),
    ("audit_log", "action", "ds_accounts.rls_neighbour"),
    ("outbound_messages", "template_code", "DS-ACCOUNTS RLS neighbour"),
)


def _set_tenant(cur, tenant) -> None:
    cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant),))


def main(url: str) -> int:
    failures: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        # ── 0 · THE PROBE MUST BE CAPABLE OF FAILING ────────────────────────
        cur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        is_super, bypasses = cur.fetchone()
        if is_super or bypasses:
            print(
                "FAIL: this role is SUPERUSER or BYPASSRLS, so every policy below is exempted "
                "and every check would pass whatever the policies said (DEF-2717). Run as the "
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

        # ── 2 · BOTH HALVES OF THE POLICY ───────────────────────────────────
        cur.execute(
            "select tablename, policyname, qual, with_check from pg_policies "
            "where tablename = any(%s) order by 1",
            (names,),
        )
        by_table: dict[str, list] = {}
        for table, policy, qual, check in cur.fetchall():
            by_table.setdefault(table, []).append((policy, qual, check))
        for name in names:
            policies = by_table.get(name, [])
            both = [p for p in policies if p[1] and p[2]]
            if both:
                print(f"  ✓ {name}: policy {both[0][0]!r} carries USING and WITH CHECK")
            else:
                failures.append(
                    f"{name}: no policy with BOTH halves. A USING-only policy lets a tenant "
                    "read only its own rows and write into anybody's."
                )

        # ── 3 · TWO TENANTS ─────────────────────────────────────────────────
        cur.execute("select id from tenants order by created_at limit 2")
        tenants = [row[0] for row in cur.fetchall()]
        if not tenants:
            print("FAIL: no tenant at all. Run `manage.py seed_demo` first.")
            return 2
        mine = tenants[0]
        if len(tenants) > 1:
            theirs = tenants[1]
            print(f"  · two seeded tenants: {mine} and {theirs}")
        else:
            theirs = uuid.uuid4()
            cur.execute(
                "insert into tenants (id,name,subdomain,currency,created_at,updated_at) "
                "values (%s,'DS-ACCOUNTS neighbour',%s,'USD',now(),now())",
                (theirs, f"dsacct-{uuid.uuid4().hex[:8]}"),
            )
            print("  · no second tenant in this database — one is created and rolled back")

        # ── 4 · PLANT ONE ROW PER TABLE IN THE NEIGHBOUR'S TENANT ───────────
        _set_tenant(cur, theirs)
        # ⚠ **THE NEIGHBOUR NEEDS ITS OWN STATUS AND TYPE ROWS, AND THAT IS THE
        # RULE WORKING RATHER THAN AN OBSTACLE.** `account_statuses` is
        # TENANT-scoped (BR-CUS-055 makes it a lookup precisely so a utility can
        # name its own), so the neighbour cannot borrow ours — which is the same
        # isolation this script is about, met one table earlier.
        #
        # ⚠ **AND `account_types` IS TENANT-SCOPED TOO ON THIS SCHEMA, WHICH IS
        # NOT WHAT THE MODEL COMMENT SAYS.** `apps/customers/models.py` calls it
        # *"r5 #12 · `account_types` (PLATFORM, no tenant_id)"*; the table as
        # built carries `tenant_id` and ENABLE + FORCE row-level security, and
        # the first draft of this script read the seeded tenant's eight rows,
        # found zero under the neighbour's context, and reported the CATALOGUE
        # empty. Measured, not assumed — which is what the standing instruction
        # asks for, and why the neighbour makes its own.
        status_id = uuid.uuid4()
        cur.execute(
            "insert into account_statuses (id,tenant_id,code,name,behavior_class,"
            "is_system,active,created_at,updated_at) "
            "values (%s,%s,'OUVERT','Ouvert','billable',false,true,now(),now())",
            (status_id, theirs),
        )
        type_id = uuid.uuid4()
        cur.execute(
            "insert into account_types (id,tenant_id,code,name,is_system,active,legacy,"
            "sort_order,created_at,updated_at) "
            "values (%s,%s,'RES','Résidentiel',false,true,false,10,now(),now())",
            (type_id, theirs),
        )
        type_row = (type_id,)
        cur.execute(
            # ⚠ TWO CHECK CONSTRAINTS DECIDE THE SHAPE OF THIS ROW, and reading
            # them is why it is a MASTER. `ck_accounts_anchored` wants a unit OR
            # a premises (BR-CUS-1010); `ck_accounts_regular_has_unit` wants a
            # REGULAR account to have a UNIT, which would drag a real metering
            # row into a proof that is not about metering. A MASTER anchored on
            # a premises satisfies both — and it is the better probe anyway,
            # because BR-CUS-068 makes a master a row like any other and R22
            # counts it. `premises_id` is the DEFERRED FK, so a bare uuid is
            # lawful; hard rule 8 is untouched — the column is a POINTER, never
            # an address.
            "insert into accounts (id,tenant_id,account_no,kind,balance,currency,"
            "deposit_on_file,autopay,tax_exempt,bad_address,nsf_count,"
            "cash_only_no_autopay,paperless,sms_reminders,eligibility_claimed,"
            "status_id,account_type_id,premises_id,created_at,updated_at) "
            "values (%s,%s,%s,'master',0,'USD',0,false,false,false,0,"
            "false,false,false,false,%s,%s,%s,now(),now())",
            (uuid.uuid4(), theirs, "DSA-RLS-NEIGHBOUR", status_id, type_row[0], uuid.uuid4()),
        )
        cur.execute(
            "insert into audit_log (id,tenant_id,action,entity_type,entity_id,created_at) "
            "values (%s,%s,%s,'payment',%s,now())",
            (uuid.uuid4(), theirs, "ds_accounts.rls_neighbour", uuid.uuid4()),
        )
        cur.execute(
            # ⚠ `ck_outbound_msgs_address_or_reason` — EXACTLY ONE of the
            # address and the unavailable reason is present. That constraint is
            # `BR-BIL-036` in the database: *an account with NO email address is
            # normal, not an exception*, so the absence is RECORDED rather than
            # left as a row nobody wrote. This row carries the address.
            "insert into outbound_messages (id,tenant_id,source_type,source_id,channel,"
            "template_code,recipient_address,status,copy_no,attempts,held,"
            "created_at,updated_at) "
            "values (%s,%s,'invoice',%s,'email',%s,'neighbour@example.test','sent',"
            "0,0,false,now(),now())",
            (uuid.uuid4(), theirs, uuid.uuid4(), "DS-ACCOUNTS RLS neighbour"),
        )

        # ── 5 · RED FIRST: THE NEIGHBOUR CAN SEE ITS OWN ROWS ───────────────
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

        # ── 6 · THE ISOLATION, THREE WAYS, WITH A NON-ZERO OWN COUNT ────────
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
    print("  · the ORM's belt-and-policy tenant filter → the three pytest files")
    print("  · LIMIT/OFFSET cost and the query plan → ds_accounts_audit_notifications_cost.py")
    print("  · BR-REP-023's restriction on R36 → NOTHING ENFORCES IT (P5.9 is open)")
    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS — three tables, two tenants, nothing crosses.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
