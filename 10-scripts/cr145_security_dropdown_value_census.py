#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-145-BRC08 — Settings → Security, four typed numbers become
#          dropdowns. PO ruling 2026-09-29, verbatim: *"(a) Short dropdown,
#          list chosen from real use - Dropdown"*
#          (05-prototype/security-redesign-2026-09-29/README.md, Q1).
# Why:     **The list is chosen from what utilities actually HOLD, so that
#          nobody moves.** Converting a range to a list WITHDRAWS every value
#          left off it. On 2026-09-28 that already happened once:
#          `session_timeout_minutes` lost 240 and 480, and `identity/0007`
#          moved the utilities sitting on 480 to 60 — seven hours earlier for
#          their staff. This count is the precondition for the build, not a
#          detail beside it.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set — set explicitly per tenant here, and the role's
#          rolsuper/rolbypassrls printed so the reader knows which guarantee
#          they are getting) · hard rule 4 (financial immutability — this
#          script writes NOTHING, see the banner) · hard-won law 7's fifth
#          shape (a check reporting zero over a scope it silently excludes:
#          every database skipped is printed BY NAME with a reason and a
#          number) · law 14 (real PostgreSQL, never the sqlite test settings).
# Source:  the four ranges are read from `apps.identity.services.SETTING_LIMITS`
#          — the ONE limits table — and are not retyped here. A second copy of
#          the allowed range is how a census and a validator drift apart.
# Shape:   10-scripts/def_rat_7662_def_ast_7660_counts.py is the precedent this
#          follows (read-only measurement for a human, skips printed, role
#          facts printed); it counts one database, this one walks every
#          database on the server because on this container there is no single
#          "the" database.
# Tests:   none, deliberately — a MEASUREMENT for a human, not a guard.
# ───────────────────────────────────────────────────────
"""⛔ **READ-ONLY. THIS SCRIPT WRITES NOTHING, ANYWHERE, EVER.**

No `INSERT`, no `UPDATE`, no `DELETE`, no `CREATE`, no migration, no management
command. Every connection is opened with `autocommit` and every read runs inside
an explicitly `READ ONLY` transaction, so the server itself refuses a write from
this process even if a future edit tried one. The only statement that is not a
`SELECT` is `SET LOCAL app.tenant_id`, which sets tenant context (hard rule 1)
and touches no row.

WHAT IT COUNTS
--------------
For every tenant ("utility") on every database on this PostgreSQL server, the
value currently held for the four `security_policies` columns that `CR-145`
turns from a typed number into a dropdown:

    absolute_session_hours   lockout_max_failed
    lockout_minutes          keep_signed_in_days

Output is one frequency table per setting — how many utilities hold each
distinct value — plus the number of tenants with **no `security_policies` row
at all**, which run on the column default and would land on whatever the
dropdown's default becomes.

⚠ **A value OUTSIDE today's range is reported separately and loudly.** The
range moved once already; a utility holding a value the validator would now
refuse is a finding for the Product Owner, not a row to quietly bucket.

⚠ **IT IS NOT A PROPOSAL.** Which values go on each dropdown is a decision with
a clock attached — every value left off is withdrawn from whoever holds it —
and it is made by a human reading these numbers.

WHAT IT SKIPS, AND IT PRINTS EVERY ONE BY NAME
-----------------------------------------------
* a database that does not allow connections (`template0`);
* a database with no `security_policies` table — `postgres`, `template1` and
  any bare database are not the product;
* a database this role cannot connect to, with the error.
Each is listed with its reason, because a blind spot with no number beside it
is indistinguishable from an empty one (law 7's fifth shape).

⚠ **EVERY DATABASE ON THIS CONTAINER IS DEMO OR LANE SCRATCH.** There is no
production data here. Any figure this script prints is a DEMO figure and must
be labelled one; the lists that ship are drawn from the same count run against
production.

RUN
---
    service postgresql start
    PGPASSWORD=… /root/.venvs/sbh312/bin/python \\
      10-scripts/cr145_security_dropdown_value_census.py [--dsn <libpq dsn>]

Defaults to the container's `postgres://smartbillhub:smartbillhub@127.0.0.1:5432`.
`--only <db>[,<db>…]` limits the walk to named databases (used by the
planted-value proof, which runs it against a throwaway clone).

⚠ **NEVER under `config.settings.test`** — that module hardcodes in-memory
sqlite and ignores `DATABASE_URL` (CLAUDE.md law 14), so it would answer about
an empty database and look exactly like a clean estate. This script does not
use Django's connection at all; it imports `SETTING_LIMITS` and nothing else.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("DATABASE_URL", "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/postgres")

import django  # noqa: E402

django.setup()

from apps.identity.services import SETTING_LIMITS  # noqa: E402

#: The four columns `CR-145` converts. Their ranges are NOT retyped — they are
#: read from the one limits table above, so this census cannot disagree with
#: the validator about what is in range today.
SETTINGS = (
    "absolute_session_hours",
    "lockout_max_failed",
    "lockout_minutes",
    "keep_signed_in_days",
)

DEFAULT_DSN = "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/postgres"


def allowed_values(limits: dict) -> tuple[set, str, int]:
    """What this setting will accept, read from the ENTRY'S OWN SHAPE.

    ⚠ **`SETTING_LIMITS` HOLDS TWO SHAPES AND THIS SCRIPT ASSUMED ONE
    (`DEF-IDN-7826`, 2026-09-29).** It read `limits["min"]` in four places, so
    the hour that `CR-145`'s four ranges became CHOICE LISTS every one of them
    raised `KeyError: 'min'` and the census — the very thing that decides which
    values those lists should hold — stopped running.

    The script imports `SETTING_LIMITS` rather than retyping the ranges,
    precisely so it cannot drift from the validator. That was right and it was
    not enough: importing the table does not protect you from assuming its
    shape. **So the branch order here MIRRORS `_validate_policy_values`
    exactly — boolean, then choices, then a range** — and the next shape added
    there must be added here, which is a smaller debt than a silent `KeyError`.

    Returns the accepted set, a phrase for printing, and how many values.
    """
    if limits.get("boolean"):
        return {True, False}, "true / false", 2
    choices = limits.get("choices")
    if choices is not None:
        shown = " / ".join("never" if c is None else str(c) for c in choices)
        return set(choices), shown, len(choices)
    low, high = limits["min"], limits["max"]
    return set(range(low, high + 1)), f"{low}..{high}", high - low + 1


def _dsn_for(dsn: str, dbname: str) -> str:
    base = dsn.rsplit("/", 1)[0]
    return f"{base}/{dbname}"


def _read(conn, sql: str, params: tuple = ()) -> list[tuple]:
    """One read, inside a READ ONLY transaction. The server refuses a write."""
    with conn.cursor() as cur:
        cur.execute("begin read only")
        try:
            cur.execute(sql, params)
            return list(cur.fetchall())
        finally:
            cur.execute("commit")


def _role_facts(conn) -> tuple[str, bool, bool]:
    rows = _read(
        conn,
        "select current_user, rolsuper, rolbypassrls "
        "from pg_roles where rolname = current_user",
    )
    return rows[0] if rows else ("?", False, False)


def _has_table(conn, table: str) -> bool:
    return bool(
        _read(
            conn,
            "select 1 from information_schema.tables "
            "where table_schema='public' and table_name=%s",
            (table,),
        )
    )


def _census_one_database(dsn: str, dbname: str) -> dict:
    """Every tenant's held values on one database.

    Hard rule 1: the tenant LIST comes from `tenants`, the platform table that
    carries no `tenant_id`; every read of `security_policies` runs with
    `app.tenant_id` SET to that tenant, one tenant at a time.
    """
    out: dict = {
        "db": dbname,
        "tenants": 0,
        "tenant_ids": set(),
        "with_row": 0,
        "no_row": [],
        "counts": {name: Counter() for name in SETTINGS},
        "holders": {name: defaultdict(list) for name in SETTINGS},
        "out_of_range": [],
    }
    with psycopg.connect(_dsn_for(dsn, dbname), autocommit=True) as conn:
        tenants = _read(conn, "select id, subdomain, name from tenants order by subdomain")
        out["tenants"] = len(tenants)
        for tenant_id, subdomain, name in tenants:
            label = f"{subdomain} ({name})"
            with conn.cursor() as cur:
                cur.execute("begin read only")
                try:
                    # hard rule 1 — tenant context, explicitly, per tenant.
                    # `set_config(…, is_local => true)` rather than `SET LOCAL`
                    # because `SET` takes no bind parameter; it is the same GUC
                    # the RLS policies read, scoped to this transaction, and it
                    # writes no row.
                    cur.execute(
                        "select set_config('app.tenant_id', %s, true)", (str(tenant_id),)
                    )
                    cur.execute(
                        "select " + ", ".join(SETTINGS) + " from security_policies "
                        "where tenant_id = %s",
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                finally:
                    cur.execute("commit")
            out["tenant_ids"].add(str(tenant_id))
            if row is None:
                out["no_row"].append(label)
                continue
            out["with_row"] += 1
            for name, value in zip(SETTINGS, row):
                out["counts"][name][value] += 1
                out["holders"][name][value].append(label)
                accepted, shown, _span = allowed_values(SETTING_LIMITS[name])
                if value not in accepted:
                    out["out_of_range"].append((name, value, label, shown))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=os.environ.get("CENSUS_DSN", DEFAULT_DSN))
    ap.add_argument("--only", default="", help="comma-separated database names")
    args = ap.parse_args()

    print("=" * 78)
    print("CR-145 · what every utility HOLDS for the four settings becoming dropdowns")
    print("READ-ONLY — this run wrote nothing. No INSERT, UPDATE, DELETE or migration.")
    print("=" * 78)

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        user, is_super, bypass = _role_facts(conn)
        all_dbs = _read(
            conn,
            "select datname, datallowconn, pg_size_pretty(pg_database_size(datname)) "
            "from pg_database order by datname",
        )

    print(f"server role     : {user}  rolsuper={is_super}  rolbypassrls={bypass}")
    if is_super or bypass:
        print(
            "  ⚠ SCOPE: this role BYPASSES row-level security, so RLS is NOT what keeps\n"
            "    these reads apart. Every read of `security_policies` below still runs\n"
            "    with `SET LOCAL app.tenant_id = <tenant>` (hard rule 1), one tenant at a\n"
            "    time — that loop is the scoping, and it is the only scoping."
        )
    else:
        print("  scoping: RLS policies AND an explicit `app.tenant_id` per tenant.")
    print()
    print("what each setting accepts today (read from apps.identity.services.SETTING_LIMITS):")
    for name in SETTINGS:
        lim = SETTING_LIMITS[name]
        _accepted, shown, span = allowed_values(lim)
        print(f"  {name:24s} {shown}  ({span} values)  default={lim['default']}")
    print()

    wanted = {d.strip() for d in args.only.split(",") if d.strip()}
    counted: list[dict] = []
    skipped: list[tuple[str, str]] = []

    for dbname, allowconn, size in all_dbs:
        if wanted and dbname not in wanted:
            skipped.append((dbname, "not named in --only"))
            continue
        if not allowconn:
            skipped.append((dbname, "datallowconn=false — the server refuses connections"))
            continue
        try:
            with psycopg.connect(_dsn_for(args.dsn, dbname), autocommit=True) as conn:
                if not _has_table(conn, "security_policies") or not _has_table(conn, "tenants"):
                    skipped.append((dbname, f"no security_policies/tenants table ({size})"))
                    continue
        except Exception as exc:  # noqa: BLE001 — the reason is the point
            skipped.append((dbname, f"cannot connect: {exc.__class__.__name__}: {exc}"))
            continue
        counted.append(_census_one_database(args.dsn, dbname))

    print("-" * 78)
    print("DATABASES COUNTED (all DEMO or lane scratch — this container holds no production)")
    print("-" * 78)
    for c in counted:
        print(
            f"  {c['db']:42s} tenants={c['tenants']:3d}  "
            f"with a policy row={c['with_row']:3d}  no row={len(c['no_row']):3d}"
        )
    if not counted:
        print("  none")
    print()
    print("-" * 78)
    print(f"DATABASES SKIPPED, BY NAME, WITH THE REASON — {len(skipped)} of {len(all_dbs)}")
    print("-" * 78)
    for dbname, why in skipped:
        print(f"  {dbname:42s} {why}")
    if not skipped:
        print("  none")
    print()

    totals = {name: Counter() for name in SETTINGS}
    holders: dict[str, dict] = {name: defaultdict(list) for name in SETTINGS}
    total_tenants = 0
    total_no_row: list[str] = []
    out_of_range: list[tuple] = []
    distinct_tenant_ids: set[str] = set()
    for c in counted:
        total_tenants += c["tenants"]
        distinct_tenant_ids |= c["tenant_ids"]
        total_no_row += [f"{c['db']}/{t}" for t in c["no_row"]]
        out_of_range += [(c["db"], *o) for o in c["out_of_range"]]
        for name in SETTINGS:
            totals[name].update(c["counts"][name])
            for value, labels in c["holders"][name].items():
                holders[name][value] += [f"{c['db']}/{lab}" for lab in labels]

    print("=" * 78)
    print("FREQUENCY TABLES — ⚠ DEMO DATA. NOT an answer to 'what will move in production'.")
    print("=" * 78)
    print(f"tenant ROWS seen (one per database) : {total_tenants}")
    print(f"DISTINCT tenant ids across them     : {len(distinct_tenant_ids)}")
    if distinct_tenant_ids and len(distinct_tenant_ids) < total_tenants:
        print(
            "  ⚠ THE SAME UTILITY IS COUNTED ONCE PER DATABASE. Several of these\n"
            "    databases are CLONES of one seeded demo tenant, so the frequency\n"
            "    tables below are copies of one estate, not a population. Read the\n"
            "    DISTINCT number, never the row count."
        )
    print(f"utilities WITH a security_policies row : {total_tenants - len(total_no_row)}")
    print(f"utilities with NO row (run on the default) : {len(total_no_row)}")
    for t in total_no_row:
        print(f"      {t}")
    print()
    for name in SETTINGS:
        lim = SETTING_LIMITS[name]
        accepted, shown, span = allowed_values(lim)
        print(f"{name}  (accepts {shown} — {span} values today)")
        table = totals[name]
        if not table:
            print("    no utility holds a value — nothing counted")
        for value, n in sorted(table.items(), key=lambda kv: (kv[0] is None, kv[0])):
            flag = ""
            if value not in accepted:
                # ⚠ Since CR-145 this is the case that MATTERS: a utility
                # holding a value the new choice list does not offer. It is
                # kept for them and offered to nobody else, so the census is
                # where you find out one exists.
                flag = "   ⚠ NOT ON TODAY'S LIST — this utility keeps it"
            print(f"    {str(value):>6}  held by {n:3d} utilit{'y' if n == 1 else 'ies'}{flag}")
            if n <= 6:
                for who in holders[name][value]:
                    print(f"              {who}")
        print(f"    distinct values held: {len(table)}")
        print()

    print("=" * 78)
    if out_of_range:
        print(f"⚠ VALUES NOT ON TODAY'S LIST — {len(out_of_range)}. Each is a Product Owner")
        print("  decision, not a bucket to tidy away. A utility holding one KEEPS it — the")
        print("  value is injected into that utility's own dropdown and offered to nobody")
        print("  else — so it is invisible everywhere except here.")
        for db, name, value, who, shown in out_of_range:
            print(f"    {db}/{who}: {name} = {value}   (offered: {shown})")
    else:
        print("No utility on the databases counted holds a value off today's list.")
    print("=" * 78)
    print("Nothing was written. ⚠ These are DEMO figures. The lists that ship must be")
    print("drawn from this same count run against the PRODUCTION database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
