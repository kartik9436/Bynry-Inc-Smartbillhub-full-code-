#!/usr/bin/env python3
# ── Trace ────────────────────────────────────────────────────────────────────
# Ask:      PO, 2026-09-21 — *"complete the request and see it does what it says
#           - disocnnect mean account status mter, assets status etc."*
# Pairs:    `10-scripts/po20260921_disconnect_web_walk.mjs` drives the SCREENS;
#           this counts the ROWS. A screen cannot prove what a cut wrote, and a
#           walk that asserted it from the page would assert the page back to
#           itself.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set) · rule 4 (financial immutability) · rule 5
#           (balanced pairs) · rule 7 (every money action writes `audit_log`)
# ─────────────────────────────────────────────────────────────────────────────
"""Before/after snapshot of every table a disconnection can touch, for ONE account.

    <venv>/bin/python 10-scripts/po20260921_disconnect_walk_readback.py A-11340 before out.json
    <venv>/bin/python 10-scripts/po20260921_disconnect_walk_readback.py A-11340 after  out2.json
    <venv>/bin/python 10-scripts/po20260921_disconnect_walk_readback.py --diff out.json out2.json

⚠ **RLS GENUINELY APPLIES.** The database role is `NOBYPASSRLS`, so every count
below comes back ZERO unless `app.tenant_id` is set — and it is set with `SET
LOCAL` inside an explicit transaction, because a plain `SET` does not survive
the connection pool handing the connection on.

⚠ **THE PRODUCT-WIDE TOTALS ARE MARKED AS SUCH.** `journal_entries_total`,
`audit_log_total` and `outbound_total` count the whole tenant, so on a shared
development database another lane's work moves them. The per-ACCOUNT lists
beside them are the ones that prove what THIS cut did.

⚠ **`outbound_sent_total` IS A SEPARATE NUMBER FROM `outbound_total` ON
PURPOSE.** A queue is not a delivery. At the time of writing the product holds
373 queued messages and has never sent one.
"""
import json, os, sys

# ⚠ **DJANGO IS IMPORTED LATE ON PURPOSE.** `--diff` reads two JSON files and
# needs no database, no settings module and no virtualenv — so it runs under the
# plain `python3` on PATH. Importing Django at the top made the diff impossible
# to run from anywhere but the backend directory, which is where the first draft
# of this file put it.
if len(sys.argv) > 1 and sys.argv[1] == "--diff":
    # ⚠ **READ IT AS ARITHMETIC, NOT AS A GLANCE** (hard-won law 11's habit,
    # applied to rows instead of to a commit).
    before = json.load(open(sys.argv[2]))
    after = json.load(open(sys.argv[3]))
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        if b == a:
            continue
        nb = len(b) if isinstance(b, list) else b
        na = len(a) if isinstance(a, list) else a
        print(f"{key}: {nb}  ->  {na}")
        # ⚠ **A TRUE MULTISET DIFFERENCE, NOT THE TAIL OF THE LIST.** These
        # lists are SQL-ordered, so a new row lands wherever it sorts — and a
        # first draft that printed `a[len(b):]` reported the last rows of the
        # after-list as the additions. It named the wrong journal lines as the
        # ones the cut wrote, which is the kind of output that reads as a
        # finding and is not one.
        if isinstance(a, list) and isinstance(b, list):
            rest = [json.dumps(r, sort_keys=True) for r in b]
            for row in a:
                key_ = json.dumps(row, sort_keys=True)
                if key_ in rest:
                    rest.remove(key_)
                else:
                    print(f"    + {key_[:300]}")
            for gone in rest:
                print(f"    - {gone[:300]}")
    raise SystemExit(0)

import django  # noqa: E402  — see the note above `--diff`

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()
from django.db import connection  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402

ACCT = sys.argv[1] if len(sys.argv) > 1 else "A-11340"
LABEL = sys.argv[2] if len(sys.argv) > 2 else "snapshot"
OUT = sys.argv[3] if len(sys.argv) > 3 else None

t = Tenant.objects.get(subdomain=os.environ.get("DWALK_TENANT", "brazosbend"))
snap = {"label": LABEL, "account_no": ACCT, "tenant": str(t.id)}

with connection.cursor() as c:
    c.execute("BEGIN")
    c.execute("SET LOCAL app.tenant_id = %s", [str(t.id)])

    def one(sql, params=()):
        c.execute(sql, list(params)); r = c.fetchone(); return None if r is None else r[0]

    def rows(sql, params=()):
        c.execute(sql, list(params))
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, r)) for r in c.fetchall()]

    aid = one("SELECT id FROM accounts WHERE account_no=%s", [ACCT])
    snap["account_id"] = str(aid)
    unit = one("SELECT unit_id FROM accounts WHERE account_no=%s", [ACCT])

    snap["account"] = rows("""SELECT a.account_no, s.code AS status_code, s.behavior_class,
                                     a.balance, a.deposit_on_file, a.closed_at, a.close_reason,
                                     a.final_read_state
                              FROM accounts a LEFT JOIN account_statuses s ON s.id=a.status_id
                              WHERE a.id=%s""", [aid])
    snap["disconnect_cases"] = rows("""SELECT case_no, state, tier, cut_scheduled_for, cut_on,
                                              services_cut, cut_reason, reconnection_fee_amount,
                                              reconnection_fee_code, deposit_disposition,
                                              status_before_cut, outstanding_at_cut
                                       FROM disconnect_cases WHERE account_id=%s ORDER BY case_no""", [aid])
    snap["disconnect_notices_n"] = one("""SELECT count(*) FROM disconnect_notices n
                                          JOIN disconnect_cases d ON d.id=n.case_id WHERE d.account_id=%s""", [aid])
    snap["invoices"] = rows("""SELECT invoice_no, bill_type, status, period_start, period_end,
                                      issued_at IS NOT NULL AS issued, subtotal, tax_total, total, due_date
                               FROM invoices WHERE account_id=%s ORDER BY created_at""", [aid])
    snap["invoice_lines_n"] = one("""SELECT count(*) FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id
                                     WHERE i.account_id=%s""", [aid])
    snap["invoice_lines"] = rows("""SELECT i.invoice_no, l.description, l.amount
                                    FROM invoice_lines l JOIN invoices i ON i.id=l.invoice_id
                                    WHERE i.account_id=%s ORDER BY i.created_at, l.id""", [aid])
    # Ledger — entries and lines that name this account, plus the product-wide total
    snap["journal_entries_for_account"] = rows("""SELECT DISTINCT e.number, e.type, e.status, e.entry_date, e.memo,
                                                         e.source_type
                                                  FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id
                                                  WHERE l.account_id=%s ORDER BY e.entry_date, e.number""", [aid])
    snap["journal_lines_for_account"] = rows("""SELECT e.number, l.side, l.amount, la.code AS ledger_code
                                                FROM journal_lines l JOIN journal_entries e ON e.id=l.journal_entry_id
                                                LEFT JOIN ledger_accounts la ON la.id=l.ledger_account_id
                                                WHERE l.account_id=%s ORDER BY e.entry_date, e.number, l.side""", [aid])
    snap["journal_entries_total"] = one("SELECT count(*) FROM journal_entries")
    snap["journal_lines_total"] = one("SELECT count(*) FROM journal_lines")
    snap["journal_unbalanced"] = rows("""SELECT e.number,
                                                sum(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END) AS dr,
                                                sum(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END) AS cr
                                         FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id
                                         GROUP BY e.number
                                         HAVING sum(CASE WHEN l.side='debit' THEN l.amount ELSE -l.amount END) <> 0""")
    snap["audit_log_for_account"] = rows("""SELECT action, created_at, actor_label FROM audit_log
                                            WHERE entity_id=%s ORDER BY created_at""", [str(aid)])
    snap["audit_log_total"] = one("SELECT count(*) FROM audit_log")
    snap["payments_n"] = one("SELECT count(*) FROM payments WHERE account_id=%s", [aid])
    snap["allocations_n"] = one("""SELECT count(*) FROM allocations al JOIN payments p ON p.id=al.payment_id
                                   WHERE p.account_id=%s""", [aid])
    # Assets / meters / service points on this account's unit
    snap["assets"] = rows("""SELECT a.asset_no, a.serial_no, st.code AS status_code, a.retire_date, a.retire_reason
                             FROM assets a LEFT JOIN asset_lifecycle_stages st ON st.id=a.status_id
                             JOIN service_points sp ON sp.id=a.service_point_id
                             WHERE sp.unit_id=%s ORDER BY a.asset_no""", [unit])
    snap["service_points"] = rows("""SELECT sp.id::text, s.code AS service, sp.route_id IS NOT NULL AS on_route,
                                            sp.cycle_id IS NOT NULL AS on_cycle, sp.deleted_at
                                     FROM service_points sp LEFT JOIN services s ON s.id=sp.service_id
                                     WHERE sp.unit_id=%s ORDER BY s.code""", [unit])
    snap["connection_services"] = rows("""SELECT s.code AS service, cs.state, cs.activated_at
                                          FROM connection_services cs LEFT JOIN services s ON s.id=cs.service_id
                                          WHERE cs.unit_id=%s ORDER BY s.code""", [unit])
    snap["meter_reads"] = rows("""SELECT mr.read_at, mr.channel, mr.current_value, mr.consumption, mr.unit,
                                         mr.source, mr.status, mr.event_context
                                  FROM meter_reads mr WHERE mr.account_id=%s ORDER BY mr.read_at, mr.created_at""", [aid])
    snap["meter_reads_n"] = len(snap["meter_reads"])
    snap["route_memberships"] = rows("""SELECT r.code AS route, r.status, rm.walk_order
                                         FROM route_memberships rm JOIN routes r ON r.id=rm.route_id
                                         WHERE rm.unit_id=%s ORDER BY r.code""", [unit])
    snap["work_orders"] = rows("""SELECT order_no, type, state, outcome FROM work_orders
                                  WHERE account_id=%s OR unit_id=%s ORDER BY created_at""", [aid, unit])
    snap["outbound_for_account"] = rows("""SELECT template_code, channel, status, sent_at, recipient_address, event_key
                                           FROM outbound_messages WHERE account_id=%s ORDER BY created_at""", [aid])
    snap["outbound_total"] = one("SELECT count(*) FROM outbound_messages")
    snap["outbound_sent_total"] = one("SELECT count(*) FROM outbound_messages WHERE sent_at IS NOT NULL")
    snap["outbound_by_status_total"] = rows("SELECT status, count(*) FROM outbound_messages GROUP BY status ORDER BY 1")
    snap["account_protections"] = rows("""SELECT kind, effective_from, expires_on, lifted_on FROM account_protections
                                          WHERE account_id=%s ORDER BY created_at""", [aid])
    snap["charge_codes"] = rows("SELECT code, name, amount FROM charges WHERE code IN ('RECON','CC-RECON','DISC','CC-DISC','FIELD','CC-FIELD') ORDER BY code")
    c.execute("COMMIT")

def default(o):
    return str(o)


text = json.dumps(snap, indent=2, default=default)
if OUT:
    open(OUT, "w").write(text)
print(text)
