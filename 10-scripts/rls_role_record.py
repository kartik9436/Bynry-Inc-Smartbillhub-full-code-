#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2760 (2026-08-31) — the repo records NO database role for any
#          deployment, so nobody can tell whether hard rule 1 is enforced on a
#          running environment. The only trace of a real deployed role anywhere
#          is the username inside a quoted PostgreSQL error message from
#          2026-08-10, and its rolsuper/rolbypassrls were never measured.
#          DEF-2717 is what that costs: a benchmark lane made its role
#          SUPERUSER for an unrelated reason and every bill-run figure published
#          that day was measured with the tenant predicate never evaluated —
#          one tenant read 73 accounts that belonged to another.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on) ·
#          09-infra/02-aws-runbook.md §8.0 (the canary) · hard-won law 1
# Impacts: 09-infra/02-aws-runbook.md §8.0's results table · core/rls_guard.py ·
#          G56
# ───────────────────────────────────────────────────────
"""ASK A RUNNING DATABASE THE §8.0 CANARY AND PRINT THE ROW TO PASTE.

WHY A SCRIPT FOR THREE COLUMNS
------------------------------
§8.0 has been a correct, explicit canary for weeks — `SELECT rolname, rolsuper,
rolbypassrls`, with the instruction to STOP if either is true — and it is a
MANUAL psql step in a runbook that no gate, workflow or test reads. **Nothing
records that it was ever run against anything**, and `DEF-2760`'s own escape
column names the reason that matters: *"a runbook step that is never recorded is
indistinguishable from a step that was never run."*

The friction is small and it is the whole gap: an operator has to find the
snippet, run it, read three values, translate them into a markdown row, and
remember which environment they were on. This does all five and prints the row.

WHAT IT DOES NOT DO, AND WILL NOT
---------------------------------
**It does not write the runbook.** A person runs this against an environment
only they can reach, and a person pastes the row and signs it with their own
name. A script that filled the table in would be recording that a check was run
by nobody, which is the defect wearing a fix's clothes.

**It does not make the answer safe.** If the role bypasses RLS this prints the
`ALTER ROLE` that fixes it and exits 1, exactly as `core/rls_guard.py` does at
boot — but the fixing is an operator's act on a live database.

USAGE
    DATABASE_URL=postgresql://… python3 10-scripts/rls_role_record.py --env production
    python3 10-scripts/rls_role_record.py --env sandbox --by "A. Operator"

    exit 0 — the role is restricted; the markdown row is on stdout
    exit 1 — rolsuper or rolbypassrls is TRUE: STOP, and read what it printed
    exit 2 — could not connect or no driver; nothing is claimed either way
"""
import argparse
import datetime
import os
import sys

CANARY = "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", required=True, help="the environment name, as the runbook table calls it")
    ap.add_argument("--by", default="", help="who ran it — the table's last column")
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    args = ap.parse_args()

    if not args.database_url:
        print("no DATABASE_URL — nothing measured, and nothing is claimed", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print("psycopg is not importable here — run this where the app runs", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(args.database_url) as conn, conn.cursor() as cur:
            cur.execute(CANARY)
            row = cur.fetchone()
    except Exception as exc:  # pragma: no cover — an operator's connection problem
        print(f"could not ask the database: {exc}", file=sys.stderr)
        return 2

    if row is None:  # pragma: no cover — current_user always has a pg_roles row
        print("pg_roles returned nothing for current_user — that is not a normal state", file=sys.stderr)
        return 2

    rolname, rolsuper, rolbypassrls = row
    today = datetime.date.today().isoformat()
    mark = lambda v: "**t**" if v else "f"  # noqa: E731 — a two-word formatter
    print(
        f"| {args.env} | `{rolname}` | {mark(rolsuper)} | {mark(rolbypassrls)} | "
        f"{today} | {args.by or '_(fill in)_'} |"
    )

    if rolsuper or rolbypassrls:
        print(
            f"\nSTOP. `{rolname}` is exempt from row-level security "
            f"(rolsuper={rolsuper}, rolbypassrls={rolbypassrls}), so EVERY isolation probe "
            f"below §8.0 would pass vacuously and one utility can read another's records. "
            f"That is DEF-2717, measured: the same query read 2 rows on a restricted role "
            f"and 3 on a bypassing one, the third belonging to a different tenant.\n"
            f"    ALTER ROLE {rolname} NOSUPERUSER NOBYPASSRLS;\n"
            f"Record the row anyway — a bad answer written down is worth far more than a "
            f"blank one, and the blank is what DEF-2760 is about.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\n{rolname} is restricted (rolsuper=f, rolbypassrls=f). Paste the row above into "
        f"09-infra/02-aws-runbook.md §8.0 and commit it — a measurement nobody wrote down is "
        f"indistinguishable from one nobody took.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
