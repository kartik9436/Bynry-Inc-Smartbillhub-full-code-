#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Question: OQ-RAT-12633 — a deposit rule points at a customer category that no
#           longer exists. The PO must say which category each one meant; we
#           will not guess, because a deposit rule is the figure a new customer
#           is actually charged (BR-RAT-020/023).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 4 (financial
#           immutability — this script WRITES NOTHING) · hard-won law 7 (a
#           check must print what it SKIPPED beside what it checked)
# Defects:  DEF-RAT-6494 (the deploy that found it) · DEF-CUS-6495 (the door
#           that can still make a fresh one)
# ───────────────────────────────────────────────────────
"""List every deposit rule whose customer category no longer exists — READ ONLY.

WHY THIS SCRIPT EXISTS AT ALL
------------------------------
The broken rows are on a DEPLOYED database. They are not in any checkout, not
in the sample data, and not on the development database — measured there on
2026-09-24: `plan_deposit_rules` holds **0 rows** and `account_types` holds
**0 rows**, so nothing here can reproduce them. A list assembled anywhere but
on the affected system would be a guess wearing a table's clothes.

HOW A ROW BREAKS, IN ONE PARAGRAPH
-----------------------------------
`customers/0054` (2026-09-17) gave every tenant its own `account_types`: it
copied each platform row per tenant **keeping the `code`**, repointed the
referencing rows, then deleted the platform originals. Its repoint list is
`REFERENCING = ("Account", "AccountSubtype", "ServiceRequest")` and
`plan_deposit_rules` is **not in it** — the column is a bare `UUIDField`, so
nothing refused and the value was left naming a deleted row.

⚠ **THE CODE SURVIVED THE MOVE, THE ID DID NOT.** Every tenant holds a copy of
the same category under the same `code`. So a repoint is mechanical *once
somebody says which code a rule meant* — and that is the only part a human is
needed for.

WHY THE ANSWER IS USUALLY A GLANCE RATHER THAN RESEARCH
--------------------------------------------------------
A deposit rule is unique on `(rate_plan, account_type_id)`, so one plan carries
at most one rule per category. This report therefore prints, for each broken
rule, the categories its own plan ALREADY prices — and the tenant's categories
that are left over. When a plan prices three of a tenant's four categories and
has one broken row, the missing one names itself. That is a STRONG HINT and it
is labelled as one: it is never applied, and a plan with two broken rows or a
tenant with unused categories will show several candidates on purpose.

⚠ **IT WRITES NOTHING AND IT CANNOT.** No INSERT, UPDATE, DELETE or DDL, and
it opens the connection read-only. Repointing is a separate, reviewed act after
the PO has ruled — not a flag on a report.

⚠ **RLS: RUN IT AS A ROLE THAT CAN SEE ROWS.** `FORCE ROW LEVEL SECURITY` is on,
and the migration role pins `app.tenant_id` to the no-tenant sentinel — which is
exactly how `rating/0044` could have certified a constraint over rows it never
read (DEF-RAT-6494). This script does not pretend otherwise: it prints the role
it connected as and the number of tenants it could see, so a run that saw
nothing is never mistaken for a system with nothing wrong.

USAGE
-----
    DATABASE_URL='postgres://USER:PASS@HOST:5432/DB?sslmode=require' \
        python3 10-scripts/oq_rat_12633_broken_deposit_rules.py

Exit status: 0 when it completed, whatever it found. 2 when it could not look.
A non-zero count is not a failure — it is the answer.
"""
from __future__ import annotations

import os
import sys

try:
    import psycopg
except ImportError:  # pragma: no cover - environment, not logic
    sys.stderr.write("psycopg is not installed in this interpreter.\n")
    raise SystemExit(2)


BROKEN = """
SELECT d.tenant_id::text,
       COALESCE(t.name, t.subdomain, d.tenant_id::text) AS tenant,
       d.rate_plan_id::text                             AS plan_id,
       p.code                                           AS plan_code,
       p.name                                           AS plan_name,
       d.account_type_id::text                          AS missing_id,
       d.amount,
       d.currency
  FROM plan_deposit_rules d
  LEFT JOIN account_types a ON a.id = d.account_type_id
  LEFT JOIN rate_plans   p ON p.id = d.rate_plan_id
  LEFT JOIN tenants      t ON t.id = d.tenant_id
 WHERE a.id IS NULL
 ORDER BY tenant, plan_code
"""

PRICED_ON_PLAN = """
SELECT a.code
  FROM plan_deposit_rules d
  JOIN account_types a ON a.id = d.account_type_id
 WHERE d.rate_plan_id = %s
 ORDER BY a.code
"""

TENANT_CATEGORIES = """
SELECT code FROM account_types WHERE tenant_id = %s ORDER BY code
"""

SCOPE = """
SELECT current_user,
       (SELECT count(*) FROM plan_deposit_rules),
       (SELECT count(*) FROM account_types),
       (SELECT count(DISTINCT tenant_id) FROM plan_deposit_rules)
"""


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.stderr.write("Set DATABASE_URL first. See this file's docstring.\n")
        return 2

    with psycopg.connect(url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(SCOPE)
            role, rules, types, tenants = cur.fetchone()

            # ── WHAT WE COULD SEE, printed BEFORE what we found (law 7) ──
            print("WHAT THIS RUN COULD SEE")
            print(f"  connected as .............. {role}")
            print(f"  deposit rules visible ..... {rules}")
            print(f"  customer categories ....... {types}")
            print(f"  tenants with deposit rules  {tenants}")
            if rules == 0:
                print()
                print("  ⚠ ZERO ROWS VISIBLE. That is either a system with no deposit")
                print("    rules, or a role that row-level security is hiding them from.")
                print("    This report cannot tell the two apart — check the role before")
                print("    reading this as good news.")
            print()

            cur.execute(BROKEN)
            broken = cur.fetchall()

            print(f"BROKEN DEPOSIT RULES: {len(broken)}")
            if not broken:
                print("  None among the rows this role can see.")
                return 0
            print()

            for (tenant_id, tenant, plan_id, plan_code,
                 plan_name, missing, amount, ccy) in broken:
                cur.execute(PRICED_ON_PLAN, (plan_id,))
                priced = [r[0] for r in cur.fetchall()]
                cur.execute(TENANT_CATEGORIES, (tenant_id,))
                every = [r[0] for r in cur.fetchall()]
                candidates = [c for c in every if c not in priced]

                print(f"  {tenant} · plan {plan_code or '(plan missing)'}"
                      f" — {plan_name or ''}".rstrip())
                print(f"      amount ................. {amount} {ccy}")
                print(f"      points at (deleted) .... {missing}")
                print(f"      this plan already prices {', '.join(priced) or '(nothing else)'}")
                if len(candidates) == 1:
                    print(f"      ONLY CATEGORY LEFT ..... {candidates[0]}   <- strong hint, NOT applied")
                elif candidates:
                    print(f"      could be ............... {', '.join(candidates)}")
                else:
                    print("      could be ............... (every category is already priced here)")
                print()

            print("Nothing was changed. Tell us the category for each rule above and we")
            print("repoint them in one reviewed migration — OQ-RAT-12633.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
