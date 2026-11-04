"""nc_e2e_walk_readback — stage 12 of the New Connection end-to-end web walk.

Reads back, from the walk's PostgreSQL 16 database, EVERYTHING a build made and
what became of it after approval, for the buildings the browser walk created
(`10-scripts/nc_e2e_walk.mjs` + `nc_e2e_walk_after.mjs`, PO-approved plan of
2026-10-02). Read-only: it writes nothing.

Per building: the request's state; the premises and its status; every unit and
each unit × service row's state; every asset with its type, size, status and
install date; the master account (kind, type, status, language); the customer;
plan assignments; work orders by state; one-time bills (the quote and any
added fee) with what was paid against them; every payment on the master
account with its method, reference, local date, status and allocations; the
ledger entries those payments posted (debits = credits); every message queued
for the account or the request (channel, recipient, language, template and
version, state, the facts it was rendered with); to-dos and notes; audit rows.

    NCW_OUT=<walk dir> DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python manage.py shell < ../10-scripts/nc_e2e_walk_readback.py

Writes <NCW_OUT>/nce2e_READBACK.json and prints one block per building.
"""

import json
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import connection as db

OUT = Path(os.environ.get("NCW_OUT", "/tmp/nce2e"))
TENANT_SUB = os.environ.get("NCW_TENANT", "lakeside")
BUILDS = os.environ.get("NCW_BUILDS", "S1,S2,S3,S4,S5,S6,S7,S8").split(",")


def rows(sql, params=()):
    with db.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(sql, params=()):
    got = rows(sql, params)
    return got[0] if got else None


def plain(value):
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


tenant = one("select id, name from tenants where subdomain = %s", (TENANT_SUB,))
zone_row = one("select timezone from tenant_settings where tenant_id = %s", (tenant["id"],))
ZONE = ZoneInfo((zone_row or {}).get("timezone") or "UTC")
report = {"tenant": tenant["name"], "timezone": str(ZONE), "buildings": {}}

for build in BUILDS:
    path = OUT / f"nce2e_{build}_RESULTS.json"
    if not path.exists():
        continue
    cid = json.loads(path.read_text())["facts"].get("connectionId")
    if not cid:
        continue
    b = {}
    con = one(
        "select c.connection_no, c.state, c.premises_id, c.created_at from connections c where c.id = %s",
        (cid,),
    )
    b["request"] = {"no": con["connection_no"], "state": con["state"]}
    prem = one(
        "select p.premise_no, p.name, p.address_line, p.city, p.state, p.postal_code, p.status, "
        "pt.code as type, p.master_account_id from premises p "
        "left join premises_types pt on pt.id = p.premises_type_id where p.id = %s",
        (con["premises_id"],),
    )
    b["premises"] = {k: plain(v) for k, v in prem.items() if k != "master_account_id"}
    b["unit_services"] = [
        {k: plain(v) for k, v in r.items()}
        for r in rows(
            "select u.label as unit, u.unit_type, u.is_common_area as common, s.code as service, "
            "cs.state, cs.activated_at from connection_services cs join services s on s.id = cs.service_id "
            "left join units u on u.id = cs.unit_id where cs.connection_id = %s order by u.label, s.code",
            (cid,),
        )
    ]
    b["assets"] = [
        {k: plain(v) for k, v in r.items()}
        for r in rows(
            "select a.asset_no, at.code as type, at.category, a.size_class, s.code as service, u.label as unit, "
            "st.code as status, a.install_date, pa.asset_no as parent from assets a "
            "join asset_types at on at.id = a.type_id "
            "left join asset_lifecycle_stages st on st.id = a.status_id "
            "left join service_points sp on sp.id = a.service_point_id left join services s on s.id = sp.service_id "
            "left join units u on u.id = sp.unit_id left join assets pa on pa.id = a.parent_asset_id "
            "where u.premises_id = %s and a.tenant_id = %s order by u.label, s.code, a.asset_no",
            (con["premises_id"], tenant["id"]),
        )
    ]
    master = None
    if prem["master_account_id"]:
        master = one(
            "select a.id, a.account_no, a.kind, at.code as account_type, ast.code as status, ast.name as status_name, "
            "a.preferred_language, a.paperless, a.sms_reminders, a.opened_at from accounts a "
            "left join account_types at on at.id = a.account_type_id "
            "left join account_statuses ast on ast.id = a.status_id where a.id = %s",
            (prem["master_account_id"],),
        )
    if master is None:
        master = one(
            "select a.id, a.account_no, a.kind, at.code as account_type, ast.code as status, ast.name as status_name, "
            "a.preferred_language, a.paperless, a.sms_reminders, a.opened_at from accounts a "
            "left join account_types at on at.id = a.account_type_id "
            "left join account_statuses ast on ast.id = a.status_id where a.premises_id = %s and a.kind = 'master'",
            (con["premises_id"],),
        )
    b["master_account"] = None if master is None else {k: plain(v) for k, v in master.items() if k != "id"}
    if master is not None:
        b["customer"] = [
            {k: plain(v) for k, v in r.items()}
            for r in rows(
                "select c.customer_no, c.display_name, c.kind, ca.is_primary, ca.match_tier from customer_accounts ca "
                "join customers c on c.id = ca.customer_id where ca.account_id = %s",
                (master["id"],),
            )
        ]
        b["mailing"] = rows(
            "select kind, line1, city, state, postal_code from addresses where account_id = %s",
            (master["id"],),
        ) if one("select count(*) as n from information_schema.columns where table_name='addresses' and column_name='line1'")["n"] else []
        invs = rows(
            "select i.id, i.invoice_no, i.bill_type, i.status, i.total, i.issued_at, i.due_date from invoices i "
            "where i.account_id = %s order by i.created_at",
            (master["id"],),
        )
        for inv in invs:
            paid = one("select coalesce(sum(amount),0) as s from allocations where invoice_id = %s", (inv["id"],))["s"]
            inv["allocated"] = paid
        b["bills"] = [{k: plain(v) for k, v in inv.items() if k != "id"} for inv in invs]
        pays = rows(
            "select p.id, p.payment_no, p.amount, p.status, p.confirmation, pm.code as method, p.posted_at, p.cleared_at "
            "from payments p left join payment_methods pm on pm.id = p.method_id where p.account_id = %s order by p.created_at",
            (master["id"],),
        )
        for p in pays:
            p["posted_local"] = p["posted_at"].astimezone(ZONE).date().isoformat() if p["posted_at"] else None
            p["allocations"] = [
                {"invoice": a["invoice_no"], "amount": plain(a["amount"])}
                for a in rows(
                    "select i.invoice_no, al.amount from allocations al join invoices i on i.id = al.invoice_id "
                    "where al.payment_id = %s",
                    (p["id"],),
                )
            ]
            entries = rows(
                "select je.id, je.number, je.status, je.entry_date from journal_entries je "
                "where je.source_id::text = %s or je.id in (select journal_entry_id from journal_lines where source_id::text = %s)",
                (str(p["id"]), str(p["id"])),
            )
            p["ledger"] = []
            for je in entries:
                lines = rows(
                    "select jl.side, jl.amount, la.code as gl, la.name from journal_lines jl "
                    "left join ledger_accounts la on la.id = jl.ledger_account_id where jl.journal_entry_id = %s",
                    (je["id"],),
                )
                dr = sum((l["amount"] for l in lines if l["side"] in ("debit", "DR", "D")), Decimal(0))
                cr = sum((l["amount"] for l in lines if l["side"] in ("credit", "CR", "C")), Decimal(0))
                p["ledger"].append(
                    {
                        "entry": je["number"],
                        "status": je["status"],
                        "date": plain(je["entry_date"]),
                        "lines": [f"{l['side']} {l['gl']} {l['name']} {plain(l['amount'])}" for l in lines],
                        "balanced": dr == cr,
                        "debits": plain(dr),
                        "credits": plain(cr),
                    }
                )
        b["payments"] = [{k: plain(v) for k, v in p.items() if k not in ("id", "posted_at", "cleared_at")} | {"cleared": p["cleared_at"] is not None} for p in pays]
        b["plan_assignments"] = [
            {k: plain(v) for k, v in r.items()}
            for r in rows(
                "select u.label as unit, rp.code as plan, upa.assigned_from, upa.source from unit_plan_assignments upa "
                "join units u on u.id = upa.unit_id join rate_plans rp on rp.id = upa.rate_plan_id "
                "where u.premises_id = %s order by u.label",
                (con["premises_id"],),
            )
        ]
    b["work_orders"] = dict(Counter(r["state"] for r in rows("select state from work_orders where connection_id = %s", (cid,))))
    b["work_orders_unit_stamped"] = one(
        "select count(*) filter (where unit_id is not null) as with_unit, count(*) as total from work_orders where connection_id = %s",
        (cid,),
    )
    acct_id = master["id"] if master else None
    msgs = rows(
        "select om.source_type, om.channel, om.copy_no, om.template_code, om.template_version, om.template_language, "
        "om.recipient_address, om.unavailable_reason, om.status, om.sent_at, om.created_at, om.render_context "
        "from outbound_messages om where om.source_id::text = %s or (om.account_id is not null and om.account_id = %s) "
        "order by om.created_at",
        (str(cid), acct_id),
    )
    b["messages"] = [
        {
            "source": m["source_type"],
            "channel": m["channel"],
            "copy": m["copy_no"],
            "template": f"{m['template_code']} v{m['template_version']} ({m['template_language']})",
            "to": m["recipient_address"] or f"— {m['unavailable_reason']}",
            "state": m["status"],
            "sent_at": plain(m["sent_at"]),
            "queued_local": m["created_at"].astimezone(ZONE).strftime("%m/%d/%Y %H:%M"),
            "rendered_with": {k: v for k, v in (json.loads(m["render_context"]) if isinstance(m["render_context"], str) else (m["render_context"] or {})).items() if not isinstance(v, (dict, list))},
        }
        for m in msgs
    ]
    b["todos"] = [
        {k: plain(v) for k, v in r.items()}
        for r in rows("select kind, title, closed_at is not null as closed from connection_todos where connection_id = %s order by created_at", (cid,))
    ]
    b["audit_rows"] = one(
        "select count(*) as n from audit_log where entity_id::text = %s or entity_id::text in (select id::text from work_orders where connection_id = %s)",
        (str(cid), cid),
    )["n"] if one("select to_regclass('audit_log') as t")["t"] else None
    report["buildings"][build] = b

(OUT / "nce2e_READBACK.json").write_text(json.dumps(report, indent=1, default=str))
for build, b in report["buildings"].items():
    print(f"\n══ {build} · {b['request']['no']} · {b['request']['state']}")
    print("  premises:", b["premises"])
    print("  master:", b.get("master_account"), "customer:", b.get("customer"))
    print("  unit×service states:", dict(Counter(r["state"] for r in b["unit_services"])))
    print("  assets:", len(b["assets"]), dict(Counter((a["type"], a["status"]) for a in b["assets"])))
    print("  assets with install date:", sum(1 for a in b["assets"] if a["install_date"]), "sized:", sum(1 for a in b["assets"] if a["size_class"]))
    print("  bills:", b.get("bills"))
    print("  payments:", b.get("payments"))
    print("  plans:", b.get("plan_assignments"))
    print("  work orders:", b["work_orders"], b["work_orders_unit_stamped"])
    print("  messages:", [(m["channel"], m["template"], m["to"], m["state"]) for m in b["messages"]])
    print("  todos:", b["todos"], "audit rows:", b["audit_rows"])
raise SystemExit(0)
