#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 `P4.1` · `P4.2` · `P4.5` — the 40,000-account work.
# Rules:    CLAUDE.md opening — the ICP ceiling moved 3,000 → 40,000 on
#           2026-09-06 and `GET /outstandings` did not (`DEF-PAY-4221`) ·
#           `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping — `app.tenant_id` BEFORE a
#           row is written or counted) · hard rule 2 (money is NUMERIC, never
#           a float and never cents) · hard-won law 7 (a benchmark is a check:
#           ask what would make it pass wrongly, and print what it skipped).
# ───────────────────────────────────────────────────────
"""SEED A TENANT AT THE ICP's ACTUAL CEILING, so a debtor list can be measured.

`10-scripts/cr094c_accounts_page_cost.py` could measure the accounts list
because `brazosbend` already had accounts on it. **The debtor list has 72**, and
72 rows is a size at which both the broken version and the fixed one answer in
a tenth of a second — which is exactly how `GET /outstandings` stayed
"unpaginated ON PURPOSE" for seventeen days after the ceiling moved.

So this writes the shape the list actually has to survive: **N accounts, every
one of them a debtor**, each with open bills, a contact, and the collections
furniture the read model joins to.

⚠ **WHAT WOULD MAKE A BENCHMARK ON THIS DATA PASS WRONGLY — five of them, and
each one is answered by a column this script prints or a row it writes:**

  1 **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS, so a session with `app.tenant_id` unset sees ZERO
    rows and every query is instant. Everything below runs inside
    `tenant_context` and the verify step COUNTS what it wrote.
  2 **One bill per debtor**, which hides the per-invoice materialisation
    entirely. Every account here gets TWO open bills, one aged past 90 days and
    one inside 30, so the ageing buckets are not degenerate either.
  3 **No part payments**, which hides the allocations join. One debtor in four
    carries a posted payment and an allocation against the older bill.
  4 **No budget bills**, which is the one case where `amount_due_for` is NOT
    `invoices.total` (BR-BIL-072, ❄️ *"Level is due"*). One bill in twenty
    carries a `budget.amount_due` block, so any SQL that re-derives the balance
    is measurably wrong rather than plausibly right.
  5 **No plans**, which hides the ladder's per-debtor `live_plan_for` hop
    (`P4.2`). One debtor in ten gets an ACTIVE plan with instalments.
  6 **Only the rows whose treatment is obvious.** A `processing` payment, a
    `deposit`, an `issued` refund, a `requested` refund and a bill with NO due
    date are each governed by a signed rule rather than by arithmetic, and a
    fixture holding none of them cannot tell a correct balance from a
    plausible one — this one holds all five, because a rewrite without them
    passed a 2,030-row comparison while summing `payments` unfiltered.

  ⚠ **AND WHAT IT DELIBERATELY DOES NOT SEED, named because an undeclared
  blind spot is indistinguishable from an empty one:** no units, premises,
  meters, reads, ledger entries, bill runs or invoice lines for these accounts.
  The debtor read touches none of them. A figure from this fixture is a figure
  about `GET /outstandings` and `collections/ladder` and about nothing else.

IT WRITES, AND IT WRITES ONLY ROWS IT CAN NAME. Every account is
numbered `SCALE-nnnnnnn`. Point it at a `proof-db.sh` CLONE, never at a shared
database.

⚠ **IT REFUSES TO RUN TWICE AND DOES NOT OFFER A PURGE, WHICH IS HARD RULE 4
RATHER THAN AN OMISSION.** `allocations` carries `trg_allocation_append_only`
and the app role is not superuser, so a DELETE on it is refused by the
database — correctly. A seeder that half-removed its own fixture would leave a
tenant whose bills are settled by allocations pointing at payments that are
gone, and every figure measured on it would be a figure about nothing. The
clean slate is a fresh `proof-db.sh clone`, which costs 1.3 seconds.

USAGE
    10-scripts/proof-db.sh clone p4perf
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p4perf \\
      python3 ../10-scripts/cr138_p4_debtor_scale_seed.py --accounts 40000
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

#: Every account this script writes is numbered under it, and every read-back
#: below matches on it. ⚠ It is `account_no` rather than `external_ref`,
#: because `uq_accounts_tenant_external_ref_ci` makes that column unique per
#: tenant — one shared marker in it is refused on the second row, which is the
#: database correctly saying an external reference identifies ONE account.
MARK = "SCALE-%"


def _sql(cursor, statement: str, params: tuple = ()) -> int:
    cursor.execute(statement, params)
    return cursor.rowcount


def already_seeded(cursor) -> int:
    """How many fixture accounts are already here (see the docstring)."""
    cursor.execute("select count(*) from accounts where account_no like %s", (MARK,))
    return cursor.fetchone()[0]


def seed(cursor, *, accounts: int, tenant_id: str) -> None:
    status = cursor
    _sql(
        status,
        "select id from account_statuses where code = 'active'",
    )
    status_id = status.fetchone()[0]
    cursor.execute("select id from account_types where code = 'residential'")
    type_id = cursor.fetchone()[0]
    # `ck_accounts_regular_has_unit` — a regular account IS opened on a unit
    # (BR-CUS-047), so the fixture anchors every one of them on the tenant's
    # existing units round-robin rather than inventing property rows the
    # debtor read never looks at.
    cursor.execute("select id from units order by id")
    unit_ids = [row[0] for row in cursor.fetchall()]
    if not unit_ids:
        raise SystemExit(
            "REFUSED: this tenant has no units, so no regular account may be opened "
            "(ck_accounts_regular_has_unit / BR-CUS-047). Run `manage.py seed_demo` first."
        )

    # ── accounts ─────────────────────────────────────────────────────────
    # `generate_series` rather than a Python loop: 40,000 ORM writes is twenty
    # minutes and this is thirty seconds. The columns are the table's NOT NULL
    # set and nothing else — see the docstring for what is deliberately absent.
    cursor.execute(
        """
        insert into accounts (
            id, account_no, balance, currency, deposit_on_file, autopay,
            tax_exempt, bad_address, nsf_count, created_at, updated_at,
            tenant_id, status_id, account_type_id, custom_data,
            cash_only_no_autopay, is_sample, kind, external_ref, paperless,
            sms_reminders, eligibility_claimed, opened_at, unit_id
        )
        select
            gen_random_uuid(),
            'SCALE-' || lpad(n::text, 7, '0'),
            0, 'USD', 0,
            (n %% 8 = 0),          -- one debtor in eight is on autopay
            false,
            false, 0, now(), now(),
            %s, %s, %s, '{}'::jsonb,
            false, false, 'regular', 'CR138-SCALE-' || n, false, false, false,
            date '2026-01-01',
            (%s::uuid[])[1 + (n %% %s)]
        from generate_series(1, %s) as n
        """,
        (tenant_id, status_id, type_id, unit_ids, len(unit_ids), accounts),
    )
    print(f"  accounts                    {cursor.rowcount:>8,}")

    # ── one contact each ─────────────────────────────────────────────────
    # `outstandings` draws the Name cell per row today; without these the
    # per-row `contacts` query returns nothing and costs almost nothing, which
    # would understate the very N+1 being measured.
    cursor.execute(
        """
        insert into contacts (id, full_name, is_primary, created_at, updated_at,
                              account_id, tenant_id, custom_data, is_sample)
        select gen_random_uuid(), 'Scale Debtor ' || a.account_no, true,
               now(), now(), a.id, a.tenant_id, '{}'::jsonb, false
        from accounts a where a.account_no like %s
        """,
        (MARK,),
    )
    print(f"  contacts                    {cursor.rowcount:>8,}")

    # ── two open bills each ──────────────────────────────────────────────
    # Bill A is 100+ days past due (the 90+ bucket), bill B is 20 days (1-30),
    # so `bucket_for` has more than one answer and the KPI strip is not one
    # tile with everything in it. One bill in twenty carries BR-BIL-072's
    # `budget` block, where what the bill ASKS FOR is not its total.
    for leg, offset, amount, budget_every in (("A", 103, "247.3000", 20), ("B", 20, "88.5000", 0)):
        cursor.execute(
            f"""
            insert into invoices (
                id, invoice_no, bill_type, service_date, period_start,
                period_end, due_date, status, subtotal, tax_total, total,
                currency, issued_at, created_at, updated_at, account_id,
                tenant_id, payload_version, custom_snapshot, bill_payload
            )
            select
                gen_random_uuid(),
                'SC-{leg}-' || substr(a.account_no, 7),
                'regular',
                date '2026-09-23' - %s,
                date '2026-09-23' - %s - 30,
                date '2026-09-23' - %s,
                date '2026-09-23' - %s,
                'issued',
                %s::numeric, 0, %s::numeric, 'USD',
                now(), now(), now(), a.id, a.tenant_id, 1, '{{}}'::jsonb,
                case when {budget_every} > 0
                       and (substr(a.account_no, 7)::int %% {budget_every}) = 0
                     then jsonb_build_object('budget',
                            jsonb_build_object('amount_due', '200.0000'))
                     else null end
            from accounts a where a.account_no like %s
            """,
            (offset, offset, offset, offset, amount, amount, MARK),
        )
        print(f"  invoices (leg {leg}, open)     {cursor.rowcount:>8,}")

    # ── part payments on one debtor in four ──────────────────────────────
    cursor.execute(
        """
        insert into payments (id, payment_no, type, amount, currency, status,
                              purpose, posted_at, created_at, updated_at,
                              account_id, tenant_id, is_partial_reversal,
                              origin_is_derived)
        select gen_random_uuid(), 'SCP-' || substr(a.account_no, 7), 'payment',
               50.0000, 'USD', 'cleared', 'bill',
               now() - interval '10 days', now(), now(), a.id, a.tenant_id,
               false, false
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 4) = 0
        """,
        (MARK,),
    )
    print(f"  payments (part paid)        {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into allocations (id, amount, created_at, updated_at,
                                 invoice_id, tenant_id, payment_id)
        select gen_random_uuid(), 50.0000, now(), now(), i.id, p.tenant_id, p.id
        from payments p
        join accounts a on a.id = p.account_id and a.account_no like %s
        join invoices i on i.account_id = a.id and i.invoice_no like 'SC-A-%%'
        """,
        (MARK,),
    )
    print(f"  allocations                 {cursor.rowcount:>8,}")

    # ── the rows that a naive SQL rewrite gets WRONG ─────────────────────
    # ⚠ **THESE FIVE EXIST BECAUSE A REWRITE WITHOUT THEM PASSED A 2,030-ROW
    # COMPARISON WHILE SUMMING `payments` WITH NO FILTER AT ALL.** Each is a
    # row whose treatment is a signed rule rather than arithmetic, so a fixture
    # without it cannot tell a correct balance from a plausible one:
    #
    #   a `processing` payment   — money not yet taken; must NOT reduce a chase
    #   a `deposit` payment      — HELD, not paid against bills (BR-PAY-006)
    #   an `issued` refund       — money already gone; must reduce the credit
    #   a `requested` refund     — money still here; must NOT reduce it
    #   a bill with NO due date  — counted in the balance, in no ageing bucket
    #                              (BR-PAY-032), and it puts a `problems` row on
    #                              the body that an empty fixture never proves
    cursor.execute(
        """
        insert into payments (id, payment_no, type, amount, currency, status,
                              purpose, posted_at, created_at, updated_at,
                              account_id, tenant_id, is_partial_reversal,
                              origin_is_derived)
        select gen_random_uuid(), 'SCX-' || substr(a.account_no, 7) || '-' || k.kind,
               'payment', 30.0000, 'USD',
               case when k.kind = 'proc' then 'processing' else 'cleared' end,
               case when k.kind = 'depo' then 'deposit' else 'bill' end,
               now() - interval '5 days', now(), now(), a.id, a.tenant_id,
               false, false
        from accounts a, (values ('proc'), ('depo')) as k(kind)
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 7) = 0
        """,
        (MARK,),
    )
    print(f"  payments (processing/deposit) {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into refunds (id, amount, currency, status, reason,
                             created_at, updated_at, account_id, tenant_id)
        select gen_random_uuid(), 20.0000, 'USD',
               case when k.kind = 'out' then 'issued' else 'requested' end,
               'overpayment', now(), now(), a.id, a.tenant_id
        from accounts a, (values ('out'), ('pending')) as k(kind)
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 11) = 0
        """,
        (MARK,),
    )
    print(f"  refunds (issued/requested)  {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into invoices (
            id, invoice_no, bill_type, service_date, period_start, period_end,
            due_date, status, subtotal, tax_total, total, currency, issued_at,
            created_at, updated_at, account_id, tenant_id, payload_version,
            custom_snapshot
        )
        select gen_random_uuid(), 'SC-U-' || substr(a.account_no, 7), 'regular',
               date '2026-08-01', date '2026-07-01', date '2026-07-31',
               null, 'issued', 41.5000, 0, 41.5000, 'USD', now(), now(), now(),
               a.id, a.tenant_id, 1, '{}'::jsonb
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 13) = 0
        """,
        (MARK,),
    )
    print(f"  invoices (no due date)      {cursor.rowcount:>8,}")

    # ── collections furniture ────────────────────────────────────────────
    cursor.execute(
        """
        insert into account_collection_state (id, tier, tier_sent_on,
                                              last_notice_on, next_step_due,
                                              created_at, updated_at,
                                              account_id, tenant_id)
        select gen_random_uuid(), 'friendly', date '2026-09-01',
               date '2026-09-01', date '2026-09-25', now(), now(),
               a.id, a.tenant_id
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 3) = 0
        """,
        (MARK,),
    )
    print(f"  collection states           {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into notice_history (id, notice_type, tier, channel, outcome,
                                    detail, occurred_on, created_at,
                                    account_id, tenant_id)
        select gen_random_uuid(), 'reminder', 'friendly', 'email', 'sent',
               '{}'::jsonb, date '2026-09-01', now(), a.id, a.tenant_id
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 3) = 0
        """,
        (MARK,),
    )
    print(f"  notice history              {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into delivery_return_events (id, source_type, returned_on,
                                            reason, created_at, updated_at,
                                            account_id, tenant_id)
        select gen_random_uuid(), 'letter', date '2026-09-05', 'moved',
               now(), now(), a.id, a.tenant_id
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 25) = 0
        """,
        (MARK,),
    )
    print(f"  bad-address events          {cursor.rowcount:>8,}")

    # ── plans, for the ladder's per-debtor hop (P4.2) ────────────────────
    cursor.execute(
        """
        insert into payment_plans (id, total_amount, down_payment, currency,
                                   installment_count, cadence, status,
                                   suspend_late_fees, suspend_disconnect,
                                   autopay_enabled, proposed_on, signed_on,
                                   created_at, updated_at, account_id, tenant_id)
        select gen_random_uuid(), 300.0000, 0, 'USD', 3, 'monthly', 'active',
               false, true, false, date '2026-07-01', date '2026-07-02',
               now(), now(), a.id, a.tenant_id
        from accounts a
        where a.account_no like %s and (substr(a.account_no, 7)::int %% 10) = 0
        """,
        (MARK,),
    )
    print(f"  active plans                {cursor.rowcount:>8,}")
    cursor.execute(
        """
        insert into payment_plan_installments (id, seq, due_date, amount,
                                               currency, paid_posted_on,
                                               created_at, updated_at, plan_id,
                                               tenant_id)
        select gen_random_uuid(), s.seq, date '2026-07-15' + (s.seq * 30),
               100.0000, 'USD',
               case when s.seq < 3 then date '2026-07-15' + (s.seq * 30) else null end,
               now(), now(), p.id, p.tenant_id
        from payment_plans p
        join accounts a on a.id = p.account_id and a.account_no like %s,
             generate_series(1, 3) as s(seq)
        """,
        (MARK,),
    )
    print(f"  plan instalments            {cursor.rowcount:>8,}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--accounts", type=int, default=40000)
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    started = time.monotonic()
    # CLAUDE.md hard rule 1. Without this every statement below writes under a
    # policy that refuses it, and every count reads back zero.
    with tenant_context(str(tenant.id)):
        with connection.cursor() as cursor:
            existing = already_seeded(cursor)
            if existing:
                print(
                    f"REFUSED: {existing:,} accounts numbered {MARK!r} are already on {args.tenant}. "
                    "This fixture cannot remove itself (hard rule 4 — `allocations` is "
                    "append-only by trigger and the app role is not superuser). Take a "
                    "fresh database: `10-scripts/proof-db.sh clone <label>`."
                )
                return 1
            print(f"seeding {args.accounts:,} debtor accounts on {args.tenant}:")
            seed(cursor, accounts=args.accounts, tenant_id=str(tenant.id))
            cursor.execute("analyze accounts, invoices, allocations, payments, contacts")
        # ── VERIFY, because a seeder that wrote nothing looks exactly like a
        # ── seeder that worked (hard-won law 7).
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from accounts where account_no like %s), "
                "(select count(*) from invoices i join accounts a on a.id = i.account_id "
                " where a.account_no like %s and i.status = 'issued')",
                (MARK, MARK),
            )
            seeded_accounts, seeded_invoices = cursor.fetchone()
    print(
        f"\nverified in the tenant: {seeded_accounts:,} accounts · "
        f"{seeded_invoices:,} open bills · {time.monotonic() - started:.1f}s"
    )
    if seeded_accounts != args.accounts:
        print("REFUSED: the verify count does not match what was asked for.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
