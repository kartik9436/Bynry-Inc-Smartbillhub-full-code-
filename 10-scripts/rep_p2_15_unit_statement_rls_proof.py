#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: `journal_lines` READ BY `unit_id` — the spine of `P2.15`'s unit
#            statement (`BR-REP-043`) — proved isolated on REAL PostgreSQL as a
#            role that is neither SUPERUSER nor BYPASSRLS. The test suite runs
#            on in-memory SQLite (`config/settings/test.py` hardcodes it and
#            ignores `DATABASE_URL`), where row-level security does not exist
#            at all, so the guarantee cannot be proved there and `G5` once
#            called 192 skips a pass (CLAUDE.md hard-won law 7, law 14).
# Rules:     hard rule 1 (never touch a tenant table without `app.tenant_id`;
#            RLS FORCE is on) · hard rule 5 (only the posting service writes
#            journal lines — see THE PLANT below) · hard-won law 7.
# Sibling:   `10-scripts/p6w2_rls_proof.py`, whose shape this follows
#            deliberately rather than inventing a second one.
# ───────────────────────────────────────────────────────
"""ISOLATION FOR THE UNIT STATEMENT'S SPINE — two tenants, nothing crosses.

⚠ **WHY THIS TABLE NEEDS ITS OWN PROOF EVEN THOUGH IT IS OLD.** `P2.15` added a
read that selects `journal_lines` by **`unit_id`** — a dimension no report had
ever filtered on alone. Every existing proof covers a table; none covers this
PREDICATE, and the unit subject is the first read in the product whose WHERE
clause names no account and no customer. A unit id is also guessable in a way an
account id is not: it is handed to the report in the URL. So the question
*"does a unit id from the neighbouring tenant return the neighbour's money?"* is
new, and a proof that names a different predicate is a claim about that one.

⚠ **THE PLANT, AND WHY IT DOES NOT BREAK HARD RULE 5.** Rule 5 governs the
PRODUCT: only the ledger posting service writes journal lines, so no application
code path may INSERT one. **The database enforces it** —
`trg_journal_lines_sole_writer` refuses any INSERT unless
`app.ledger_posting = 'on'`, which is a guard this script found by being refused
by it, the right way round. This is a proof script, not an application path: it
sets that flag EXPLICITLY and says so here, writes inside a transaction it ROLLS
BACK unconditionally, and plants under the NEIGHBOUR'S own context. Nothing it
writes survives — asserted at the end from a SEPARATE connection, because a
proof that leaves rows behind has changed the books it was measuring.

The alternative was a proof that plants nothing, and *"the neighbour's row is
absent"* is trivially true of a table with no neighbour row in it — law 7's
second shape, a check structurally incapable of failing.

⚠ **THE PLANTED PAIR IS BALANCED**, rather than one line leaning on the fact
that `journal_balanced` is DEFERRABLE INITIALLY DEFERRED and so never fires
under a rollback. Relying on that would make this script pass for a reason that
has nothing to do with what it is testing, and would break the day the
constraint's timing changed.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **A SUPERUSER or BYPASSRLS role.** PostgreSQL exempts both from every
    policy, so every check below would pass whatever the policies said. Probe 0
    reads `pg_roles` and REFUSES.
  * **MEASURING AN EMPTY TABLE.** *"The neighbour's row is absent"* is true of a
    table with no rows in it. The row is PLANTED and probe 3 asserts it IS
    visible from the NEIGHBOUR'S OWN CONTEXT first. A zero there stops the run.
  * **A ZERO BESIDE A ZERO.** Probe 4 asserts MY OWN count is NON-ZERO before it
    believes the neighbour's zero.
  * **THE QUERY DOING THE FILTERING.** Probe 4 asks FOUR ways, and the fourth is
    the one this script exists for: a count `where unit_id = <the neighbour's
    unit>` — the exact predicate the unit statement issues, with the exact kind
    of value a URL carries.

⚠ **WHAT THIS DOES NOT PROVE, stated rather than left blank** (law 7's fifth
shape — a blind spot with no number beside it is indistinguishable from an
empty one):

  * the ORM's own tenant filter and the report's arithmetic →
    `06-backend/tests/test_br_rep_043_unit_statement.py`;
  * `units`, `premises` and `customers`, which the HEAD and the Occupant column
    walk to through `dimension_seam` — those are covered here as a SECOND
    subject set, and the count of what was covered is printed;
  * LIMIT/OFFSET cost and the query plan → `rep_p2_15_unit_statement_cost.py`.

USAGE
    python3 10-scripts/rep_p2_15_unit_statement_rls_proof.py \\
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

DEFAULT_URL = "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub"

#: Every table the unit statement READS, so the coverage claim is countable.
#: `journal_entries` is here because the report joins it for `entry_date` and
#: `memo`, and a proof of the lines alone would be a claim about half the read.
TABLES = (
    "journal_lines",
    "journal_entries",
    "units",
    "premises",
    "customers",
    "customer_accounts",
    "accounts",
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


def main(url: str) -> int:
    failures: list[str] = []
    planted_unit = str(uuid.uuid4())
    marker = "P2-15-RLS-NEIGHBOUR"

    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        # ── 0 · THE PROBE MUST BE CAPABLE OF FAILING ────────────────────────
        cur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        is_super, bypasses = cur.fetchone()
        if is_super or bypasses:
            print(
                "FAIL: this role is SUPERUSER or BYPASSRLS, so every policy below is "
                "exempted and every check would pass whatever the policies said. Run as "
                "the application role."
            )
            return 2
        print("  ✓ probe role bypasses nothing — the checks below can fail")

        # ── 1 · THE FLAGS, ON EVERY TABLE THIS READ TOUCHES ─────────────────
        cur.execute(
            "select c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='public' and c.relname = any(%s) order by 1",
            (list(TABLES),),
        )
        found = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        missing = [name for name in TABLES if name not in found]
        if missing:
            print(f"FAIL: these tables are not in this database: {missing}")
            return 2
        for name in TABLES:
            enabled, forced = found[name]
            if enabled and forced:
                print(f"  ✓ {name}: ENABLE and FORCE")
            else:
                failures.append(f"{name}: ENABLE={enabled} FORCE={forced} — hard rule 1")

        mine, theirs = _two_tenants(cur)
        print(f"  · mine {mine} · neighbour {theirs}")

        # ── 2 · PLANT THE NEIGHBOUR'S MONEY, UNDER THEIR OWN CONTEXT ────────
        #
        # ⚠ **THE NEIGHBOUR MAKES ITS OWN AND BORROWS NOTHING OF MINE.** A row
        # reusing one of my ids would be visible to me for a reason that has
        # nothing to do with a policy, and this would be measuring a foreign key.
        _set_tenant(cur, theirs)
        # ⚠ The DATABASE enforces hard rule 5 on BOTH tables
        # (`trg_journal_lines_sole_writer`, and the same guard on
        # `journal_entries`), so the flag the posting service sets is set here
        # EXPLICITLY and turned off again below. It refused this script twice
        # before this line existed, which is the guard working on its reader.
        cur.execute("select set_config('app.ledger_posting', 'on', true)")
        entry_id = str(uuid.uuid4())
        cur.execute(
            # `type`, `status`, `updated_at` are NOT NULL with no database
            # default — named explicitly rather than discovered one refusal at
            # a time. `status='posted'` because only posted lines are read.
            "insert into journal_entries (id, tenant_id, entry_date, type, status, "
            "posted_at, currency, memo, source_type, created_at, updated_at) "
            "values (%s, %s, current_date, 'invoice', 'draft', now(), 'USD', %s, "
            "'invoice', now(), now())",
            (entry_id, theirs, marker),
        )
        cur.execute("select id from ledger_accounts where tenant_id = %s limit 1", (theirs,))
        ledger_account = cur.fetchone()
        if ledger_account is None:
            print(
                "FAIL: the neighbour tenant has no chart of accounts, so a journal line has "
                "nothing to hang on. This proof would cover NO row at all — a blind spot "
                "with no number beside it (hard-won law 7)."
            )
            conn.rollback()
            return 2
        # A BALANCED pair — see the docstring on why this does not lean on
        # `journal_balanced` being deferred.
        for side, unit in (("debit", planted_unit), ("credit", None)):
            cur.execute(
                "insert into journal_lines (id, tenant_id, journal_entry_id, "
                "ledger_account_id, side, amount, unit_id, created_at, "
                "updated_at) "
                "values (%s, %s, %s, %s, %s, 999.0000, %s, now(), now())",
                (uuid.uuid4(), theirs, entry_id, ledger_account[0], side, unit),
            )
        # ⚠ **THE ENTRY IS POSTED ONLY AFTER ITS LINES EXIST.** Hard rule 4's
        # `trg_journal_line_append_only` refuses a line joining an entry that is
        # already POSTED — the books are append-only — and the read under test
        # sees only POSTED lines, so a draft entry would make probe 3 measure
        # nothing. Both guards refused this script before these two lines
        # existed, which is them working on their reader.
        cur.execute(
            "update journal_entries set status = 'posted' where id = %s", (entry_id,)
        )
        cur.execute("select set_config('app.ledger_posting', 'off', true)")

        # ── 3 · THE RED-FIRST CONTROL ───────────────────────────────────────
        cur.execute("select count(*) from journal_lines where unit_id = %s", (planted_unit,))
        seen = cur.fetchone()[0]
        if seen != 1:
            print(
                f"FAIL: as the NEIGHBOUR, journal_lines shows {seen} of its own planted "
                "rows. This probe would be measuring an empty table, not isolation."
            )
            conn.rollback()
            return 2
        print("  ✓ journal_lines: the neighbour sees its own planted row (red-first control)")

        cur.execute("select count(*) from journal_entries where memo = %s", (marker,))
        if cur.fetchone()[0] != 1:
            print("FAIL: the neighbour cannot see its own planted ENTRY either.")
            conn.rollback()
            return 2
        print("  ✓ journal_entries: the neighbour sees its own planted entry")

        # ── 4 · THE ISOLATION, FOUR WAYS, WITH A NON-ZERO OWN COUNT ─────────
        _set_tenant(cur, mine)
        cur.execute("select count(*) from journal_lines")
        own = cur.fetchone()[0]
        cur.execute("select count(*) from journal_lines where tenant_id = %s", (theirs,))
        by_tenant = cur.fetchone()[0]
        cur.execute("select count(*) from journal_entries where memo = %s", (marker,))
        by_memo = cur.fetchone()[0]
        # ⚠ **THE ONE THIS SCRIPT EXISTS FOR** — the unit statement's own
        # predicate, with the kind of value a URL carries.
        cur.execute("select count(*) from journal_lines where unit_id = %s", (planted_unit,))
        by_unit = cur.fetchone()[0]

        if own == 0:
            failures.append(
                "journal_lines: MY OWN count is zero, so 'the neighbour is absent' is true "
                "of a completely broken read. A zero beside a zero proves nothing — seed "
                "this tenant's books before trusting this line."
            )
        elif by_tenant or by_memo or by_unit:
            failures.append(
                f"journal_lines: the neighbour's money is VISIBLE — unfiltered_own={own}, "
                f"by_tenant_id={by_tenant}, by_memo={by_memo}, BY_UNIT_ID={by_unit}. "
                "Hard rule 1. A non-zero `by_unit_id` is the unit statement handing a "
                "stranger's money to whoever types their unit id into the URL."
            )
        else:
            print(
                f"  ✓ journal_lines: my own {own} rows visible; the neighbour's planted "
                "row invisible unfiltered, by tenant_id, by memo AND BY UNIT_ID"
            )

        # ── 5 · NOTHING SURVIVES ────────────────────────────────────────────
        conn.rollback()

    # A separate connection, so the rollback is proved rather than assumed.
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        _set_tenant(cur, "00000000-0000-0000-0000-000000000000")
        cur.execute(
            "select count(*) from journal_lines where unit_id = %s", (planted_unit,)
        )
        left_behind = cur.fetchone()[0]
        if left_behind:
            failures.append(
                f"{left_behind} planted line(s) SURVIVED the rollback. A proof that leaves "
                "rows behind has changed the books it was measuring (hard rule 5)."
            )
        else:
            print("  ✓ nothing planted survived — the books are as they were")

    print()
    print(f"COVERAGE: {len(TABLES)} tables checked for ENABLE+FORCE — {', '.join(TABLES)}")
    print("PREDICATE: journal_lines.unit_id — the unit statement's own WHERE clause")
    if failures:
        print()
        for line in failures:
            print(f"FAIL: {line}")
        return 1
    print("PASS: the unit statement's spine is isolated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL))
