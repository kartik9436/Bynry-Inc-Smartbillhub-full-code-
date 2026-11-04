#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: `disconnect_cases` — the SPINE of R34 Disconnect & Reconnect
#            (`BR-REP-039`) — proved isolated on REAL PostgreSQL as a role that
#            is neither SUPERUSER nor BYPASSRLS. The test suite runs on
#            in-memory SQLite (`config/settings/test.py` hardcodes it and
#            ignores `DATABASE_URL`), where row-level security does not exist
#            at all, so the guarantee cannot be proved there and `G5` once
#            called 192 skips a pass (CLAUDE.md hard-won law 7).
# Rules:     hard rule 1 (never touch a tenant table without `app.tenant_id`;
#            RLS FORCE is on) · hard-won law 7 · law 14.
# Sibling:   `10-scripts/p6_join_rls_proof.py` — wave 1's six tables. This
#            follows its shape deliberately rather than inventing a second one.
# ───────────────────────────────────────────────────────
"""ISOLATION FOR R34's SPINE — one new table, two tenants, nothing crosses.

`p6_join_rls_proof.py` covers six tables and `rep_ds_accounts_rls_proof.py`
covers `accounts`, `audit_log` and `outbound_messages`. **Neither covers
`disconnect_cases`**, which is the table `BR-REP-039` moved R34 onto — and a
proof that names six tables is a claim about six tables.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **A SUPERUSER or BYPASSRLS role.** PostgreSQL exempts both from every
    policy. Probe 0 reads `pg_roles` and REFUSES.
  * **MEASURING AN EMPTY TABLE.** *"The neighbour's row is absent"* is true of
    a table with no rows in it. The neighbour's row is PLANTED and probe 3
    asserts it IS visible from the NEIGHBOUR'S OWN CONTEXT first. That is the
    red-first control; a zero there stops the run.
  * **A zero beside a zero.** Probe 4 asserts MY OWN count is NON-ZERO before
    it believes the neighbour's zero.
  * **Filtering by tenant in the query itself.** Probe 4 asks three ways: the
    UNFILTERED count, a count `where tenant_id = <theirs>`, and a count on a
    column value only the neighbour's row carries.

⚠ **WHAT THIS DOES NOT PROVE, stated rather than left blank** (law 7's fifth
shape — a number over a scope it silently excludes):

  * the ORM's own tenant filter → `tests/test_rep_p6w2_disconnect_reconnect.py`;
  * LIMIT/OFFSET cost and the query plan → `10-scripts/p6w2_cost.py`;
  * **`accounts`, which R34 joins for the account number and the customer** →
    `10-scripts/rep_ds_accounts_rls_proof.py` already covers it, and this file
    does NOT re-prove it. Run both, or the claim is about one table.

USAGE
    python3 10-scripts/p6w2_rls_proof.py \\
      postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub
"""

from __future__ import annotations

import sys
import uuid

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("FAIL: psycopg is not installed. This proof needs a real PostgreSQL connection.")
    raise SystemExit(2)

#: The table, the column the neighbour's row is planted in, and the value —
#: chosen so probe 4's third question has something only the neighbour carries.
SUBJECTS = (("disconnect_cases", "stopped_reason", "P6W2-RLS-NEIGHBOUR"),)


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
    """The neighbour's case, written under the NEIGHBOUR'S own context.

    ⚠ **THE NEIGHBOUR MAKES ITS OWN AND BORROWS NOTHING OF MINE.** A row that
    reused one of my account ids would be visible to me for a reason that has
    nothing to do with a policy, and the proof would be measuring a foreign key.

    ⚠ **`cut_on` IS DELIBERATELY NULL HERE.**
    `ck_cut_records_the_price_of_coming_back` would then demand a reconnection
    fee, a fee code and a deposit election, and this proof is about a POLICY
    rather than about that constraint — a planted row refused by a CHECK would
    stop the run for a reason that is not isolation.
    """
    _set_tenant(cur, theirs)
    cur.execute("select id from accounts where tenant_id = %s limit 1", (theirs,))
    found = cur.fetchone()
    if found is None:
        print(
            "FAIL: the neighbour tenant holds no account, so a disconnect case has nothing "
            "to hang on. This proof would cover NO table at all — a blind spot with no "
            "number beside it (hard-won law 7)."
        )
        raise SystemExit(2)
    cur.execute(
        # ⚠ **`services_cut` IS NOT NULL WITH A DJANGO-SIDE DEFAULT OF `[]`**, so
        # the database has no default of its own and a raw INSERT must name it.
        # The first draft read the model for *not null and no default*, which
        # skipped exactly this column — the database refused the row, which is
        # it doing this script's job for it and the right way round.
        "insert into disconnect_cases (id, tenant_id, account_id, sequence, state, "
        "amount_owed_at_open, currency, opened_on, stopped_reason, services_cut, "
        "created_at, updated_at) "
        "values (%s, %s, %s, 'service', 'notice_sent', 185.0000, 'USD', current_date, %s, "
        "'[]'::jsonb, now(), now())",
        (uuid.uuid4(), theirs, found[0], "P6W2-RLS-NEIGHBOUR"),
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

        # ── 2 · PLANT THE NEIGHBOUR'S ROW ───────────────────────────────────
        _plant(cur, theirs)

        # ── 3 · THE RED-FIRST CONTROL ───────────────────────────────────────
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
                    "completely broken read. A zero beside a zero proves nothing. Seed this "
                    "tenant with 10-scripts/p6w2_cost.py first."
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
    print("  · the ORM's own tenant filter → tests/test_rep_p6w2_disconnect_reconnect.py")
    print("  · LIMIT/OFFSET cost and the query plan → 10-scripts/p6w2_cost.py")
    print("  · `accounts`, which R34 joins → 10-scripts/rep_ds_accounts_rls_proof.py")
    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS — one table, two tenants, nothing crosses.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
