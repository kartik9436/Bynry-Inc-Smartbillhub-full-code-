#!/usr/bin/env python3
"""`P4.15`'s SCOPING, PROVED ON REAL PostgreSQL, WITH A NEIGHBOUR PLANTED.

`CR-142-BRC07` `P4.15`, ruled: *"In the customer portal a landlord sees **their
own master account only**: the $69.60, never Unit 3's $100.00."* That sentence
has TWO guarantees behind it and the default test suite can only see one:

  1. **The account set** — `premises_statement` never queries an account
     outside `principal.account_ids`. `tests/test_cr142_p4_15_premises_statement.py`
     proves that and runs anywhere.
  2. **The tenant** — hard rule 1, row-level security, `FORCE`. **Invisible to
     every test in this repository**, because `config/settings/test.py`
     hardcodes in-memory SQLite, which has no row-level security of any kind
     (CLAUDE.md hard-won law 14). Every assertion about a policy passes there
     by vacuum.

**This script is guarantee 2.**

    ./10-scripts/proof-db.sh clone p415
    DATABASE_URL=... PYTHONPATH=06-backend \\
      06-backend/.venv/bin/python 10-scripts/rep_p4_15_landlord_rls_proof.py

⚠ **IT REFUSES TO RUN AS A ROLE RLS DOES NOT APPLY TO, AND THAT REFUSAL IS THE
MOST IMPORTANT LINE IN THE FILE.** PostgreSQL exempts a superuser from every
policy unconditionally, `FORCE` included (`DEF-2717`), and a `BYPASSRLS` role
likewise. A proof run as either prints the same word as a real one and means
nothing — hard-won law 7's *structurally incapable of failing*.

⚠ **AND IT PROVES THE NEIGHBOUR IS VISIBLE FROM THEIR OWN CONTEXT FIRST.** This
is the half that is easy to leave out and it is the half that makes the rest
mean anything: a probe that reports *the landlord cannot see Unit 3's balance*
over a table where Unit 3's row was never written, or was written and rolled
back, prints exactly the same PASS. So every planted row is READ BACK from
inside the tenant that owns it **before** any cross-boundary question is asked,
and the run STOPS if a plant is not there — law 7's *ask what would make this
check pass wrongly*, applied to the fixture rather than to the assertion.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import django


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()

    from django.db import connection

    from apps.customers import models as customer_models
    from apps.portal import premises_statement
    from apps.portal.session import AccountEntry, PortalPrincipal
    from apps.tenancy.models import Tenant
    from core import errors
    from core.tenancy import tenant_context

    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'}  {label}{'' if detail == '' else f' — {detail}'}")
        if not ok:
            failures += 1

    # ── 0 · the role must be one RLS actually applies to ────────────────────
    with connection.cursor() as cur:
        cur.execute(
            "select current_user, rolsuper, rolbypassrls from pg_roles "
            "where rolname = current_user"
        )
        role, is_super, bypasses = cur.fetchone()
    if is_super or bypasses:
        print(
            f"REFUSED: running as {role!r}, which is "
            f"{'a SUPERUSER' if is_super else 'BYPASSRLS'}. PostgreSQL exempts it "
            "from every policy, FORCE included, so this proof would pass over an "
            "absent one. Re-run as a NOSUPERUSER NOBYPASSRLS role."
        )
        return 2
    print(f"role {role!r}: NOSUPERUSER, NOBYPASSRLS — RLS applies\n")

    # ── 1 · two tenants ──────────────────────────────────────────────────────
    tenants = list(Tenant.objects.order_by("created_at")[:2])
    if len(tenants) < 2:
        second = Tenant.objects.create(
            name="P4.15 proof neighbour",
            subdomain=f"p415-neighbour-{uuid.uuid4().hex[:6]}",
            currency="USD",
        )
        print("this database held ONE tenant; a second was created for the proof")
        tenants = [tenants[0], second]
    alpha, beta = tenants[0], tenants[1]
    print(f"tenant A = {alpha.subdomain} · tenant B = {beta.subdomain}\n")

    # ── 2 · find a premises in A with at least TWO accounts on it ───────────
    # Real seeded data rather than a fixture built here: what is being proved is
    # a policy over the product's own rows.
    with tenant_context(alpha.id):
        by_premises: dict[str, list] = {}
        for account in customer_models.Account.objects.select_related("unit").all()[:4000]:
            premises_id = account.premises_id or getattr(account.unit, "premises_id", None)
            if premises_id is None:
                continue
            by_premises.setdefault(str(premises_id), []).append(account)
        shared = sorted(
            ((key, rows) for key, rows in by_premises.items() if len(rows) >= 2),
            key=lambda pair: -len(pair[1]),
        )
    if not shared:
        print(
            "REFUSED: no premises in this database carries two accounts, so there "
            "is no neighbour to be hidden FROM. A pass here would mean nothing."
        )
        return 2
    premises_id, neighbours = shared[0]
    mine, theirs = neighbours[0], neighbours[1]
    print(
        f"premises {premises_id} carries {len(neighbours)} accounts; "
        f"proving {mine.account_no} cannot see {theirs.account_no}\n"
    )

    def principal(tenant, *accounts):
        return PortalPrincipal(
            session_id="rls-proof",
            credential_id="rls-proof",
            customer_id="rls-proof",
            tenant_id=tenant.id,
            accounts=tuple(
                AccountEntry(account_id=str(a.pk), permissions=("see",), source="holder")
                for a in accounts
            ),
        )

    WINDOW = {"start": date(2020, 1, 1), "end": date(2030, 12, 31)}

    # ── 3 · THE PRECONDITION: the neighbour is VISIBLE from their OWN seat ──
    # Without this, every check below passes over an empty table.
    with tenant_context(alpha.id):
        body, count = premises_statement.premises_statement(
            principal(alpha, theirs), theirs.pk, **WINDOW
        )
    check(
        f"3 · PRECONDITION — {theirs.account_no} IS visible from its own holder's seat",
        count == 1 and body["rows"][0]["account_no"] == theirs.account_no,
        f"{count} row(s); the probe below is therefore not measuring an empty table",
    )
    if count != 1:
        print("\nSTOPPING: the precondition failed, so nothing below would mean anything.")
        return 1

    # ── 4 · the neighbour's row is NOT in the other holder's statement ──────
    with tenant_context(alpha.id):
        body, count = premises_statement.premises_statement(
            principal(alpha, mine), mine.pk, **WINDOW
        )
    numbers = [row["account_no"] for row in body["rows"]]
    check(
        f"4 · {mine.account_no}'s statement holds ONLY {mine.account_no}",
        numbers == [mine.account_no],
        f"rows: {numbers}",
    )
    # ⚠ THE WHOLE SERIALISED BODY, not a column. A figure that leaks usually
    # leaks through a total or a tile rather than the column somebody named.
    import json

    rendered = json.dumps(body)
    check(
        f"4 · {theirs.account_no} appears NOWHERE in the served payload",
        str(theirs.account_no) not in rendered,
        "searched the whole body, not one field",
    )

    # ── 5 · the same read, run in the OTHER TENANT'S context, finds nothing ─
    # This is the strand SQLite cannot see. The account ids are real and belong
    # to A; the context is B's; RLS is the only thing standing between them.
    with tenant_context(beta.id):
        refused = False
        try:
            premises_statement.premises_statement(principal(beta, mine), mine.pk, **WINDOW)
        except errors.NotFoundError:
            refused = True
    check(
        "5 · A's account is NOT FOUND inside B's context",
        refused,
        "the 404 is the policy's, not a slug comparison's",
    )

    # ── 6 · and raw SQL under B cannot reach A's accounts either ────────────
    with tenant_context(beta.id):
        with connection.cursor() as cur:
            cur.execute(
                "select count(*) from accounts where id = %s", [str(mine.pk)]
            )
            leaked = cur.fetchone()[0]
    check(
        "6 · raw SQL under B cannot see A's account row",
        leaked == 0,
        f"{leaked} row(s) reachable — this is the ORM taken out of the question",
    )

    print()
    if failures:
        print(f"{failures} FAILURE(S)")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
