#!/usr/bin/env python3
"""**WHAT THE CREATE PRESS ACTUALLY WROTE — READ BACK WITH SQL, NOT FROM A SCREEN.**

`po20260929_new_connect_press_create.mjs` walks the New Connect wizard and
presses Create. This reads its `00-RESULTS.json` and then asks the DATABASE
what landed: step 12's eight kinds of row, hard rule 2's four decimals, hard
rule 5's balanced ledger pair, hard rule 7's audit row, hard rule 6's
idempotency, and hard rule 1's tenant scoping in both directions.

⚠ **A SCREEN SHOWING `$450.00` SAYS NOTHING ABOUT WHAT IS STORED.** Every
money assertion here reads the column.

⚠ **CHECK 25 IS RUN AS `sbh_rls_probe`, NOT AS THE APP ROLE.** The app role on
this container is `rolsuper=t`, and a superuser BYPASSES RLS — so an isolation
check run as the app role finds nothing for the wrong reason and passes. The
probe role is `rolsuper=f, rolbypassrls=f`, which is the only role that can
answer the question. The role actually used is PRINTED beside the verdict.

    DATABASE_URL=postgres://... python3 10-scripts/po20260929_new_connect_readback.py \\
        --results /tmp/nc-press-create/00-RESULTS.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal

import psycopg

RESULTS: list[tuple[str, str, str, str]] = []


def record(cid: str, label: str, verdict: str, evidence: str = "") -> None:
    RESULTS.append((cid, label, verdict, str(evidence)[:1200]))
    print(f"{verdict:<7} {cid:<5} {label}" + (f" — {evidence}" if evidence else ""))


def check(cid: str, label: str, ok: bool, evidence: str = "") -> None:
    record(cid, label, "PASS" if ok else "FAIL", evidence)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--tenant", default="brazosbend")
    ap.add_argument("--probe-role", default="sbh_rls_probe")
    args = ap.parse_args()

    walk = json.load(open(args.results))
    typed = walk["typed"]
    commit = walk.get("commitResponse") or {}
    connection_no = commit.get("connection_no")
    if connection_no is None:
        record("12", "step 12 — everything the wizard promised exists", "BLOCKED",
               "the walk's commit did not answer with a connection number, so there is nothing to read back")
        return 2

    dsn = re.sub(r"\?.*$", "", args.dsn or "")
    conn = psycopg.connect(dsn, autocommit=True)
    cur = conn.cursor()

    def q(sql: str, *params):
        cur.execute(sql, params)
        return cur.fetchall()

    def one(sql: str, *params):
        rows = q(sql, *params)
        return rows[0][0] if rows else None

    tenant_id = one("select id from tenants where subdomain = %s", args.tenant)
    print(f"\n── tenant {args.tenant} = {tenant_id}")
    print(f"── connection {connection_no}\n")

    conn_row = q(
        "select id, tenant_id, premises_id, owner_account_id from connections where connection_no = %s",
        connection_no,
    )
    if not conn_row:
        record("12", "step 12", "FAIL", f"no connections row for {connection_no}")
        return 1
    conn_id, conn_tenant, premises_id, owner_account_id = conn_row[0]

    # ════════════════════════════════════════════════════════════════════
    # CHECK 12 · EVERYTHING THE WIZARD PROMISED
    # ════════════════════════════════════════════════════════════════════
    unit_ids = [r[0] for r in q("select id from units where premises_id = %s", premises_id)]
    sp_ids = [r[0] for r in q("select id from service_points where unit_id = any(%s)", unit_ids)] if unit_ids else []
    # ⚠ **A METER IS AN `assets` ROW AGAINST A SERVICE POINT.** There is no
    # `service_points.meter_id`; a first draft asked for one and died on
    # `UndefinedColumn`, which is the cheap version of law 7's *looking at the
    # wrong thing*. The commit sends `asset_no: null` on purpose, so what is
    # counted here is the asset rows the build raised, awaiting a serial.
    meters = one("select count(*) from assets where service_point_id = any(%s)", sp_ids) if sp_ids else 0
    wos = one("select count(*) from work_orders where connection_id = %s", conn_id)
    invoice_ids = [r[0] for r in q("select id from invoices where account_id = %s", owner_account_id)]
    charge_lines = one("select count(*) from invoice_lines where invoice_id = any(%s)", invoice_ids) if invoice_ids else 0
    payments = q(
        "select id, amount::text, method_id, confirmation, status, journal_entry_id"
        "  from payments where account_id = %s", owner_account_id)
    account_row = q("select id, account_no, tenant_id, premises_id from accounts where id = %s", owner_account_id)
    customer_id = one("select customer_id from customer_accounts where account_id = %s", owner_account_id)

    made = {
        "account": 1 if account_row else 0,
        "customer": 1 if customer_id else 0,
        "premises": 1 if premises_id else 0,
        "units": len(unit_ids),
        "service_points": len(sp_ids),
        "meters (assets on those points)": meters,
        "work_orders": wos or 0,
        "the charge (invoice)": len(invoice_ids),
        "invoice_lines": charge_lines,
        "the payment": len(payments),
    }
    missing = [k for k, v in made.items() if not v]
    check(
        "12",
        "step 12 - account, premises, units, service points, meters, work orders, the charge and the payment all exist",
        not missing,
        " . ".join(f"{k}={v}" for k, v in made.items()) + (f" || MISSING: {', '.join(missing)}" if missing else ""),
    )

    # ════════════════════════════════════════════════════════════════════
    # CHECK 20 · MONEY STORED AT 4 DECIMALS, DISPLAYED AT 2
    # ════════════════════════════════════════════════════════════════════
    scales = q(
        """select table_name, column_name, numeric_scale
             from information_schema.columns
            where table_schema='public'
              and ((table_name='invoice_lines' and column_name in ('amount','unit_price'))
                or (table_name='invoices' and column_name in ('total','amount_due'))
                or (table_name='payments' and column_name='amount'))
            order by table_name, column_name"""
    )
    stored = q(
        "select amount::text, unit_price::text from invoice_lines where invoice_id = any(%s)",
        invoice_ids,
    ) if invoice_ids else []
    pay_amounts = [p[1] for p in payments]
    # ⚠ **THE COLUMNS ARE `NUMERIC(18,6)` AND CLAUDE.md CALLS THAT LAWFUL** -
    # "existing 18,6 columns stay lawful containers; the rule governs what is
    # WRITTEN". So the question is not the column's scale, it is whether the
    # VALUE written is a 4-decimal number: the 5th and 6th places must be zero,
    # and it must not have been rounded to 2 either.
    def four_places(text: str) -> bool:
        frac = (text.split(".") + ["" ])[1]
        return len(frac) >= 4 and (len(frac) <= 4 or set(frac[4:]) <= {"0"})
    money_written = [v for row in stored for v in row if v is not None] + list(pay_amounts)
    four_dp = bool(money_written) and all(four_places(m) for m in money_written)
    # display: what the walk saw on screen
    displayed = typed.get("charge_row", "")
    two_dp_on_screen = bool(re.search(r"\$[\d,]+\.\d{2}(?!\d)", displayed)) or bool(
        re.search(r'"display":"[\d.]+\d\d"', typed.get("quote_preview", ""))
    )
    check(
        "20",
        "hard rule 2 — the charge is STORED at 4 decimals and DISPLAYED at 2",
        four_dp and two_dp_on_screen,
        f"column scales {scales} | stored invoice_lines {stored} | stored payment {pay_amounts} | on screen \"{displayed[:120]}\"",
    )

    # ════════════════════════════════════════════════════════════════════
    # CHECK 21 · THE PAYMENT WRITES A BALANCED LEDGER PAIR
    # ════════════════════════════════════════════════════════════════════
    if payments:
        payment_id, pay_amount, method_id, confirmation, pay_status, entry_id = payments[0]
        # `payments.journal_entry_id` is the payment's OWN pointer at the entry
        # the posting service made, so the pair is read from the row rather
        # than guessed by timestamp.
        legs = q(
            """select jl.id::text, jl.side, jl.amount::text, la.code, la.name
                 from journal_lines jl
                 left join ledger_accounts la on la.id = jl.account_id
                where jl.journal_entry_id = %s
                order by jl.side""",
            entry_id,
        )
        entry = q(
            "select type, status, source_type, source_id::text, currency from journal_entries where id = %s",
            entry_id,
        )
        debit = sum(Decimal(l[2]) for l in legs if l[1] and l[1].lower().startswith("d"))
        credit = sum(Decimal(l[2]) for l in legs if l[1] and l[1].lower().startswith("c"))
        check(
            "21",
            "hard rule 5 - the payment writes a BALANCED ledger pair",
            bool(legs) and len(legs) >= 2 and debit == credit and debit > 0,
            f"payments.journal_entry_id={entry_id} entry={entry} | {len(legs)} lines "
            f"debits {debit} = credits {credit} | {[(l[1], l[2], l[3]) for l in legs]}",
        )
        # hard rule 5's second half - only the posting service writes journal
        # lines. Evidenced by the entry naming the payment as its SOURCE: a
        # line written by anything else would carry no source_type at all.
        record(
            "21b",
            "hard rule 5 - the entry names the payment as its source (the posting service's own stamp)",
            "PASS" if entry and entry[0][2] == "payment" and entry[0][3] == str(payment_id) else "FAIL",
            f"source_type={entry[0][2] if entry else None} source_id={entry[0][3] if entry else None} vs payment {payment_id}",
        )

        # ════════════════════════════════════════════════════════════════
        # CHECK 22 · audit_log CARRIES A ROW FOR THE PAYMENT
        # ════════════════════════════════════════════════════════════════
        audit = q(
            """select action, entity_type, entity_id::text, tenant_id::text, created_at
                 from audit_log
                where entity_id = %s or after::text like %s
                order by created_at""",
            payment_id, f"%{payment_id}%",
        )
        check(
            "22",
            "hard rule 7 - audit_log carries a row for the payment",
            bool(audit),
            f"{len(audit)} row(s): {[(a[0], a[1]) for a in audit][:8]}"
            + (f" | tenant on those rows {set(a[3] for a in audit)}" if audit else ""),
        )
    else:
        record("21", "hard rule 5 - the payment writes a BALANCED ledger pair", "BLOCKED", "no payment row was written")
        record("22", "hard rule 7 - audit_log carries a row for the payment", "BLOCKED", "no payment row was written")

    # ════════════════════════════════════════════════════════════════════
    # CHECK 23 · PRESS CREATE TWICE — NO SECOND ACCOUNT
    # ════════════════════════════════════════════════════════════════════
    second = walk.get("secondCommitResponse") or {}
    conns_now = one("select count(*) from connections where tenant_id = %s", tenant_id)
    same_address = one(
        "select count(*) from premises where tenant_id = %s and address_line = %s",
        tenant_id, typed.get("premise_address"),
    )
    accounts_for_customer = one(
        "select count(*) from accounts where premises_id = %s", premises_id
    )
    check(
        "23",
        "hard rule 6 — pressing Create twice does NOT create two accounts",
        accounts_for_customer == 1 and same_address == 1,
        f"second commit answered {second.get('status')} {str(second.get('text'))[:180]} | "
        f"accounts on this premises = {accounts_for_customer} · premises at this address = {same_address} · "
        f"connections in tenant = {conns_now}",
    )

    # ════════════════════════════════════════════════════════════════════
    # CHECK 24 · EVERY ROW CARRIES THE RIGHT tenant_id
    # ════════════════════════════════════════════════════════════════════
    wrong = []
    scoped = [
        ("connections", "id", [conn_id]),
        ("accounts", "id", [owner_account_id]),
        ("customers", "id", [customer_id] if customer_id else []),
        ("premises", "id", [premises_id]),
        ("units", "id", unit_ids),
        ("service_points", "unit_id", unit_ids),
        ("invoices", "id", invoice_ids),
        ("payments", "id", [p[0] for p in payments]),
    ]
    detail = []
    for table, col, ids in scoped:
        if not ids:
            detail.append(f"{table}: no rows to check")
            continue
        rows = q(f"select distinct tenant_id from {table} where {col} = any(%s)", ids)
        seen = {str(r[0]) for r in rows}
        detail.append(f"{table}({len(ids)}): {seen or 'EMPTY'}")
        if seen != {str(tenant_id)}:
            wrong.append(f"{table} -> {seen}")
    check("24", "hard rule 1 — every row created carries the right tenant_id", not wrong,
          " · ".join(detail) + (f" || WRONG: {wrong}" if wrong else ""))

    # ════════════════════════════════════════════════════════════════════
    # CHECK 25 · A SECOND TENANT CANNOT SEE ANY OF IT
    # ════════════════════════════════════════════════════════════════════
    role_super = one("select rolsuper from pg_roles where rolname = current_user")
    probe_ok = one("select 1 from pg_roles where rolname = %s", args.probe_role)
    if not probe_ok:
        record("25", "a second tenant cannot see any of it", "BLOCKED",
               f"the probe role {args.probe_role} does not exist; running as {conn.info.user} (rolsuper={role_super}) would pass for the wrong reason")
    else:
        other = one("select id from tenants where subdomain <> %s limit 1", args.tenant)
        made_other = False
        if other is None:
            # An isolation check needs a second tenant to BE a second tenant.
            cur.execute(
                "insert into tenants (id, name, subdomain, currency, created_at, updated_at)"
                " values (gen_random_uuid(), 'Isolation Probe Tenant', 'isolationprobe', 'USD', now(), now())"
                " returning id"
            )
            other = cur.fetchone()[0]
            made_other = True
        # ⚠ **THE GRANTS, THE WAY `isolation_helpers.py` MAKES THEM.** A clone
        # of the demo template has the role but no privileges on the tables the
        # migrations created since, so the probe answers `permission denied`
        # rather than `0 rows` - which is a BLOCKED check wearing the costume
        # of a failing one. Granted here, outside any transaction, exactly as
        # the isolation fixture does.
        cur.execute(f'GRANT USAGE ON SCHEMA public TO "{args.probe_role}"')
        cur.execute(
            "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"%s\"" % args.probe_role)
        with conn.cursor() as pcur:
            pcur.execute(f'SET ROLE "{args.probe_role}"')
            probe_super = pcur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user").fetchone()
            pcur.execute("select set_config('app.tenant_id', %s, false)", (str(other),))
            intruder = {}
            for table, col, ids in scoped:
                if not ids:
                    continue
                pcur.execute(f"select count(*) from {table} where {col} = any(%s)", (ids,))
                intruder[table] = pcur.fetchone()[0]
            # and the same probe under the OWNING tenant, so a zero everywhere
            # cannot be a policy that hides the rows from everybody (law 7 —
            # a check reporting zero over a scope it silently excludes).
            pcur.execute("select set_config('app.tenant_id', %s, false)", (str(tenant_id),))
            owner_sees = {}
            for table, col, ids in scoped:
                if not ids:
                    continue
                pcur.execute(f"select count(*) from {table} where {col} = any(%s)", (ids,))
                owner_sees[table] = pcur.fetchone()[0]
            pcur.execute("RESET ROLE")
        leaked = {t: n for t, n in intruder.items() if n}
        blind = [t for t, n in owner_sees.items() if not n]
        check(
            "25",
            f"a second tenant cannot see any of it (probed as {args.probe_role}, rolsuper={probe_super[0]}, rolbypassrls={probe_super[1]})",
            not leaked and not blind,
            f"intruder tenant {other} sees {intruder} · the OWNING tenant sees {owner_sees}"
            + (f" || LEAKED: {leaked}" if leaked else "")
            + (f" || the owner sees nothing in {blind} — the zero above would prove nothing" if blind else "")
            + (" · a second tenant row was created for this probe" if made_other else ""),
        )

    # ════════════════════════════════════════════════════════════════════
    # DEF-CUS-7863 · THE TEN CAPTURED FACTS, ONE BY ONE
    # ════════════════════════════════════════════════════════════════════
    print("\n-- DEF-CUS-7863 . the ten facts a clerk typed - did each reach the database?")
    prem = q(
        "select address_line, city, state, postal_code, lat::text, lng::text, external_ref,"
        "       name, gis_verified, custom_data::text"
        "  from premises where id = %s", premises_id)[0]
    cust = q(
        "select display_name, date_of_birth::text, external_ref, custom_data::text, ssn, driving_licence"
        "  from customers where id = %s", customer_id)[0] if customer_id else (None,) * 6
    acct = q("select account_no, custom_data::text, paperless, sms_reminders from accounts where id = %s",
             owner_account_id)[0]

    # ⚠ **A WHOLE-DATABASE SWEEP, NOT A GUESSED COLUMN.** "It did not arrive"
    # has to mean "this exact string is in no text column of any table", or the
    # answer is about the column this script happened to look in. That is law
    # 7's fifth shape - a check reporting zero over a scope it excludes - and
    # the ten facts are exactly where it would bite.
    text_cols = q(
        """select table_name, column_name from information_schema.columns
            where table_schema='public'
              and data_type in ('text','character varying','jsonb','citext')
              and table_name not like 'audit_log' || chr(37)
            order by table_name, column_name""")

    def anywhere(value: str) -> list[str]:
        if not value:
            return []
        hits = []
        for table, column in text_cols:
            try:
                cur.execute(f'select count(*) from "{table}" where "{column}"::text like %s',
                            (f"%{value}%",))
                if cur.fetchone()[0]:
                    hits.append(f"{table}.{column}")
            except Exception:
                conn.rollback()
        return hits

    arrived, absent, untypable = [], [], []

    def verdict(name: str, typed_value, ok: bool, where: str) -> None:
        (arrived if ok else absent).append(name)
        record("7863", f"DEF-CUS-7863 . {name}", "ARRIVED" if ok else "ABSENT",
               f'typed "{typed_value}" -> {where}')

    # 1 the unit line (step 2's "Unit, apt. or suite", part of the address)
    hits = anywhere(typed.get("unit_line") or "")
    verdict("the unit line", typed.get("unit_line"), bool(hits), ", ".join(hits) or "NOWHERE in any text column")

    # 2/3 lat and lng - premises columns, so asked of the column by name
    for name, col, want in (("latitude", "lat", typed.get("lat")), ("longitude", "lng", typed.get("lng"))):
        got = one(f"select {col}::text from premises where id = %s", premises_id)
        ok = got is not None and Decimal(got) == Decimal(want)
        verdict(name, want, ok, f"premises.{col} = {got!r}")

    # 4 the verified tick
    verdict("the verified tick", typed.get("location_verified"), bool(prem[8]),
            f"premises.gis_verified = {prem[8]}")

    # 5 customer category
    # ⚠ **A GENERIC CODE CANNOT BE SWEPT FOR.** `residential` is a value in
    # nine unrelated tables of the seed, so a whole-database `like` hit says
    # nothing about THIS build - it is law 7's false pass. Asked instead of the
    # four rows the commit made, plus whether `customers` has such a column at
    # all.
    cat = typed.get("customer_category")
    cat_cols = q(
        "select table_name, column_name from information_schema.columns"
        " where table_schema='public' and table_name in ('customers','accounts','connections')"
        "   and column_name like chr(37) || 'categ' || chr(37)")
    on_our_rows = []
    for tname, cname in cat_cols:
        col_id = {"customers": customer_id, "accounts": owner_account_id, "connections": conn_id}[tname]
        got = one(f'select "{cname}"::text from {tname} where id = %s', col_id)
        on_our_rows.append(f"{tname}.{cname}={got!r}")
        
    in_custom = (str(cat) in str(cust[3] or "")) or (str(cat) in str(acct[1] or ""))
    verdict("customer category", cat, bool(on_our_rows and any("=None" not in x for x in on_our_rows)) or in_custom,
            (f"category columns on customers/accounts/connections: {cat_cols or 'NONE EXIST'}"
             + (f" -> {on_our_rows}" if on_our_rows else "")
             + f" · custom_data customer={cust[3]!r} account={acct[1]!r}"))

    # 6 date of birth - customers.date_of_birth exists
    verdict("date of birth", typed.get("date_of_birth"),
            cust[1] == typed.get("date_of_birth"), f"customers.date_of_birth = {cust[1]!r}")

    # 7 communication preferences
    verdict("communication preferences (paperless + SMS)",
            f"paperless={typed.get('comm_paperless')} sms={typed.get('comm_sms')}",
            bool(acct[2]) and bool(acct[3]),
            f"accounts.paperless={acct[2]} accounts.sms_reminders={acct[3]}")

    # 8 the co-applicant
    hits = anywhere(typed.get("co_applicant_name") or "")
    verdict("the co-applicant", typed.get("co_applicant_name"), bool(hits),
            ", ".join(hits) or "NOWHERE in any text column")

    # 9 the mailing address
    hits = anywhere(typed.get("mailing_address") or "")
    verdict("the mailing address", typed.get("mailing_address"), bool(hits),
            ", ".join(hits) or "NOWHERE in any text column")

    # 10 account custom data
    if typed.get("account_custom"):
        hits = anywhere(typed["account_custom"])
        verdict("account custom data", typed["account_custom"], bool(hits),
                ", ".join(hits) or "NOWHERE in any text column")
    else:
        untypable.append("account custom data")
        record("7863", "DEF-CUS-7863 . account custom data", "NOT TESTABLE",
               "this tenant has defined no account custom fields, so the clerk had nothing to type "
               "into 'Account details' - the heading renders over an empty panel (DEF-CUS-7912)")

    # 11 the document number
    hits = anywhere(typed.get("document_number") or "")
    verdict("the document number", typed.get("document_number"), bool(hits),
            ", ".join(hits) or "NOWHERE in any text column")

    # a control: something we KNOW travels, so a sweep that finds nothing
    # everywhere is exposed as a broken sweep rather than read as a verdict.
    control = anywhere(typed.get("owner_name") or "")
    record("7863", "sweep control - the owner's NAME, which certainly travels", 
           "PASS" if control else "FAIL",
           ", ".join(control) or "NOWHERE - the sweep itself is broken and every ABSENT above is worthless")

    record("7863", "DEF-CUS-7863 summary", "NOTE",
           f"{len(arrived)} arrived, {len(absent)} absent, {len(untypable)} not testable. "
           f"arrived = {arrived} | absent = {absent} | not testable = {untypable}")

    # ── the raw picture, for the report ────────────────────────────────
    print("\n── rows, for the record")
    print(f"   premises  {prem}")
    print(f"   customer  {cust}")
    print(f"   account   {acct}")
    print(f"   payments  {payments}")

    failed = sum(1 for r in RESULTS if r[2] == "FAIL")
    print(f"\n── {len(RESULTS)} lines · {failed} FAIL")
    json.dump(
        {"connection_no": connection_no, "results": [
            {"id": a, "label": b, "verdict": c, "evidence": d} for a, b, c, d in RESULTS
        ]},
        open(os.path.join(os.path.dirname(args.results), "01-READBACK.json"), "w"),
        indent=2,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
