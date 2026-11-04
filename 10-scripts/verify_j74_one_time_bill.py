#!/usr/bin/env python3
"""verify_j74_one_time_bill — J74's database half: every bill the browser sent, checked in PostgreSQL.

Journey `08-qa/01-e2e/journeys/J74-one-time-bill-end-to-end.md` · spec
`07-frontend/e2e/J74-one-time-bill-end-to-end.spec.ts` · seed
`10-scripts/seed_j70_one_time_bill.py`.

The spec bills and sends eight one-time bills as a clerk would and leaves what
Review showed, the Send answer and two replays (the same Send again, the same
draft again) in `08-qa/screens/one-time-bill-e2e-j74/j74-results.json`. This
script reads the DATABASE that run wrote and answers, per case, checks (a)–(j)
of the journey. It writes nothing. Every query is a plain SQL constant below,
so anyone can paste it into `psql` — the journey file carries the same text.

    DATABASE_URL=postgres://…/sbh_j74 python 10-scripts/verify_j74_one_time_bill.py [--json]

It sets `app.tenant_id` before it reads a tenant table (CLAUDE.md hard rule 1),
so it answers the same under a role that RLS binds as under a superuser.
Exit 0 when every case passes, 1 when any check fails — and it prints every
failure, never only the first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "08-qa/screens/one-time-bill-e2e-j74/j74-results.json"
TENANT_SLUG = "brazosbend"

#: case → (unit label, bill_type, period_start, period_end, readings typed on
#: step 2 as (asset_no, value), meters that must carry an ESTIMATED read,
#: expected tax lines, deposit expectation)
CASES: dict[int, dict] = {
    1: dict(total="185.13", unit="Unit A", bill_type="cycle", start="2026-09-01", end="2026-09-30",
            typed=[("W-10442", "488.4"), ("W-10443", "136.7"), ("E-55120", "19020")],
            estimated=[], taxed=True),
    # Hand-priced (restated after the first run, which showed the plan's sewer follows
    # water on this unit too — "%-of-service is the one exception", PO 2026-09-30):
    # water 6.0 kgal (Aug's 0.2 kgal a day × 30) = 16.25 + 4.50 + 8.00; sewer 2.4 kgal
    # = 12.00 + 6.00 → 46.75 + 2% 0.94 = 47.69.
    2: dict(total="47.69", unit="Unit I", bill_type="cycle", start="2026-09-01", end="2026-09-30",
            typed=[], estimated=["W-10460"], taxed=True),
    # DEF-BIL-8331 (2.416.3) + DEF-BIL-8333 (the cycle's first run date): a first bill
    # prorates from the move-in day, 19/30 — bases and the tier bound (spec, case 3) —
    # and the cart: $15.00 × 19/30 = $9.50 (DEF-BIL-8566, PO 2026-10-01; was 393.15).
    3: dict(total="387.54", unit="Unit C", bill_type="first", start="2026-09-12", end="2026-09-30",
            typed=[("W-10443C", "128.9"), ("W-10442C", "488.4"), ("W-10443C", "136.7"), ("E-55120C", "19020")],
            estimated=[], taxed=True, deposit="charged"),
    # 18/30 on the bases (DEF-BIL-8333) AND on the cart (DEF-BIL-8566, PO 2026-10-01:
    # $15.00 × 18/30 = $9.00): 85.64 + 1.71 = 87.35; deposit 50.00 → 37.35 due.
    4: dict(total="87.35", unit="Unit J", bill_type="final", start="2026-09-01", end="2026-09-18",
            typed=[("W-10442J", "485.0"), ("W-10443J", "133.0"), ("E-55120J", "18700")],
            estimated=[], taxed=True, deposit="applied", deposit_amount="50.00", refund=None),
    5: dict(total="87.35", unit="Unit D", bill_type="final", start="2026-09-01", end="2026-09-18",
            typed=[("W-10442D", "485.0"), ("W-10443D", "133.0"), ("E-55120D", "18700")],
            estimated=[], taxed=True, deposit="applied", deposit_amount="150.00", refund="62.65"),
    6: dict(total="634.19", unit="Unit E", bill_type="backbill", start="2026-07-01", end="2026-09-30",
            typed=[("W-10442E", "482.3"), ("W-10443E", "130.6"), ("E-55120E", "18420")],
            estimated=[], taxed=True,
            # DEF-BIL-8564 — every estimate on this bill is a day-share of the typed
            # Sep 30 reading, which IS saved; saving the shares too would count the
            # same water twice at the next true-up. So NO estimated row may exist.
            no_estimate_rows=["W-10442E", "W-10443E", "E-55120E"], months=3),
    7: dict(total="1152.55", unit="Unit F", bill_type="penalty", start="2026-07-01", end="2026-09-30",
            typed=[], estimated=[], taxed=True, approved_by=True, months=3),
    # A fee bill is dated the day it is RAISED: its period is that one day at both
    # ends (`one_time.checked_window`). The walk's clock is not pinned, so the
    # date is not hard-coded here (it read 2026-09-30 until 2026-10-01, and a walk
    # on 1 October failed (a)/(j) on the clock alone). `raised_on` checks the
    # period against the run's own bill date and the day the bill was issued.
    8: dict(total="76.50", unit="Unit H", bill_type="fee", start=None, end=None, raised_on=True,
            typed=[], estimated=[], taxed=True),
}

#: J75 (PO 2026-10-01) — the SAME checks on a utility with SIX services, Six Rivers
#: (`10-scripts/seed_six_service_one_time.py`, spec `e2e/J75-six-service-one-time-bill.spec.ts`).
#: Selected with `--world j75`. Each total was priced by hand before the run; the
#: working is in the spec beside each case and in `J75-six-service-one-time-bill.md`.
#: `capacity` lists the services whose stored line must carry a size trace
#: (`invoice_lines.pricing_trace`, BR-BIL-1067) with the sizes and counts stated.
J75_RESULTS = REPO / "08-qa/screens/six-service-onetime-2026-10-01/j75-results.json"
J75_CASES: dict[int, dict] = {
    1: dict(total="512.55", unit="Unit 1", bill_type="cycle", start="2026-09-01", end="2026-09-30",
            typed=[("W-2001", "512.0")], estimated=[], taxed=True,
            capacity={"trash": {"CART-96": 2, "CART-35": 1}, "fire": {"FL-6": 1, "FL-2": 2},
                      "battery": {"BAT-10": 1}, "solar": {"SOL-P2": 1, "SOL-P4": 1, "SOL-P8": 1}},
            unpriced={"trash": "CART-35"}),
    2: dict(total="214.71", unit="Unit 2", bill_type="cycle", start="2026-09-01", end="2026-09-30",
            typed=[], estimated=["W-2002"], taxed=True,
            capacity={"trash": {"DUMP-4": 1}, "battery": {"BAT-15": 1}}, unpriced={"battery": "BAT-15"}),
    3: dict(total="388.09", unit="Unit 3", bill_type="first", start="2026-09-12", end="2026-09-30",
            typed=[("W-2003", "108.6")], estimated=[], taxed=True, deposit="charged",
            capacity={"trash": {"CART-64": 1}, "fire": {"FL-4": 1}, "battery": {"BAT-5": 1}, "solar": {"SOL-P6": 1}},
            unpriced={"solar": "SOL-P6"}),
    4: dict(total="124.54", unit="Unit 4", bill_type="final", start="2026-09-01", end="2026-09-18",
            typed=[("W-2004", "404.2")], estimated=[], taxed=True, deposit="applied", deposit_amount="50.00",
            refund=None,
            capacity={"trash": {"CART-96": 1}, "fire": {"FL-2": 1}, "battery": {"BAT-10": 1}, "solar": {"SOL-P4": 1}}),
    5: dict(total="124.54", unit="Unit 5", bill_type="final", start="2026-09-01", end="2026-09-18",
            typed=[("W-2005", "404.2")], estimated=[], taxed=True, deposit="applied", deposit_amount="200.00",
            refund="75.46",
            capacity={"trash": {"CART-96": 1}, "fire": {"FL-2": 1}, "battery": {"BAT-10": 1}, "solar": {"SOL-P4": 1}}),
    6: dict(total="498.78", unit="Unit 6", bill_type="backbill", start="2026-07-01", end="2026-09-30",
            typed=[("W-2006", "228.5")], estimated=[], taxed=True, no_estimate_rows=["W-2006"], months=3, meters=1,
            capacity={"trash": {"CART-96": 1}, "fire": {"FL-2": 1}, "battery": {"BAT-5": 1}, "solar": {"SOL-P2": 1}}),
    7: dict(total="1105.27", unit="Unit 7", bill_type="penalty", start="2026-07-01", end="2026-09-30",
            typed=[], estimated=[], taxed=True, approved_by=True, months=3, meters=1,
            capacity={"trash": {"CART-64": 1}, "fire": {"FL-4": 1}, "battery": {"BAT-10": 1},
                      "solar": {"SOL-P2": 1, "SOL-P4": 1}}),
    # RECON is not taxable in this utility (the signup's own code): $75.00, no tax line.
    8: dict(total="75.00", unit="Unit 8", bill_type="fee", start=None, end=None, raised_on=True,
            typed=[], estimated=[], taxed=False),
}
WORLDS = {
    "j74": dict(slug="brazosbend", address="1408 Elm St", cases=CASES, results=RESULTS),
    "j75": dict(slug="sixrivers", address="1200 Confluence Ave", cases=J75_CASES, results=J75_RESULTS),
}

# ── the SQL (copied verbatim into the journey file) ──────────────────────────

SQL_TENANT = "SELECT id FROM tenants WHERE subdomain = %(slug)s"
SQL_SET_TENANT = "SELECT set_config('app.tenant_id', %(tenant)s, false)"

SQL_ACCOUNT = """
SELECT a.id, a.account_no, a.deposit_on_file
  FROM accounts a JOIN units u ON u.id = a.unit_id JOIN premises p ON p.id = u.premises_id
 WHERE u.label = %(unit)s AND p.address_line = %(address)s AND a.tenant_id = %(tenant)s
"""

# (a) the invoice
SQL_INVOICE = """
SELECT i.id, i.invoice_no, i.status, i.bill_type, i.account_id, i.bill_run_id,
       i.period_start, i.period_end, i.subtotal, i.tax_total, i.total, i.currency,
       i.issued_at, i.due_date, i.bill_payload
  FROM invoices i
 WHERE i.id = %(invoice)s
"""

# (b)(c) its lines
SQL_LINES = """
SELECT l.kind, s.code AS service, l.asset_id, l.description, l.quantity, l.unit, l.unit_price, l.amount, l.taxable,
       l.tax_id, l.period_start, l.period_end, l.pricing_trace
  FROM invoice_lines l LEFT JOIN services s ON s.id = l.service_id
 WHERE l.invoice_id = %(invoice)s
 ORDER BY l.created_at, l.id
"""

# (b) money stored to at most 4 decimals — every money column of the bill
SQL_MONEY_SCALE = """
SELECT count(*) FILTER (WHERE amount <> round(amount, 4)) AS lines_over_4dp,
       (SELECT count(*) FROM invoices i
         WHERE i.id = %(invoice)s
           AND (i.total <> round(i.total, 4) OR i.subtotal <> round(i.subtotal, 4)
                OR i.tax_total <> round(i.tax_total, 4))) AS header_over_4dp
  FROM invoice_lines WHERE invoice_id = %(invoice)s
"""

# (d) the journal for the bill: debits = credits, and the receivable leg
SQL_JOURNAL = """
SELECT je.id, je.status, je.source_type, je.memo,
       sum(jl.amount) FILTER (WHERE jl.side = 'debit')  AS debits,
       sum(jl.amount) FILTER (WHERE jl.side = 'credit') AS credits
  FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
 WHERE je.source_type = 'invoice' AND je.source_id = %(invoice)s
 GROUP BY je.id, je.status, je.source_type, je.memo
 ORDER BY min(je.created_at)
"""
SQL_JOURNAL_LEGS = """
SELECT je.id AS entry, la.code, la.name, la.designation, jl.side, jl.amount, jl.account_id
  FROM journal_entries je
  JOIN journal_lines jl ON jl.journal_entry_id = je.id
  JOIN ledger_accounts la ON la.id = jl.ledger_account_id
 WHERE je.source_type = 'invoice' AND je.source_id = %(invoice)s
 ORDER BY je.created_at, jl.side DESC, la.code
"""
# the receivable, net, for this customer across every entry (Dr − Cr on 1200)
SQL_AR_NET = """
SELECT coalesce(sum(CASE WHEN jl.side = 'debit' THEN jl.amount ELSE -jl.amount END), 0) AS ar_net
  FROM journal_lines jl JOIN ledger_accounts la ON la.id = jl.ledger_account_id
 WHERE jl.account_id = %(account)s AND la.code = '1200'
"""
# every OTHER entry that touched this customer after the bill (a deposit
# applied, a refund owed, a customer credit)
SQL_OTHER_ENTRIES = """
SELECT je.source_type, je.memo, la.code, la.name, la.designation, jl.side, jl.amount
  FROM journal_entries je
  JOIN journal_lines jl ON jl.journal_entry_id = je.id
  JOIN ledger_accounts la ON la.id = jl.ledger_account_id
 WHERE je.id IN (SELECT jl2.journal_entry_id FROM journal_lines jl2 WHERE jl2.account_id = %(account)s)
   AND NOT (je.source_type = 'invoice' AND je.source_id = %(invoice)s)
 ORDER BY je.created_at, jl.side DESC, la.code
"""
SQL_OTHER_BALANCED = """
SELECT je.id, je.source_type,
       sum(jl.amount) FILTER (WHERE jl.side = 'debit')  AS debits,
       sum(jl.amount) FILTER (WHERE jl.side = 'credit') AS credits
  FROM journal_entries je JOIN journal_lines jl ON jl.journal_entry_id = je.id
 WHERE je.id IN (SELECT jl2.journal_entry_id FROM journal_lines jl2 WHERE jl2.account_id = %(account)s)
 GROUP BY je.id, je.source_type
"""

# (e) the release row — the five confirmations, the clerk, the time
SQL_RELEASE = """
SELECT r.compliance_confirmed, r.email_mandate_confirmed, r.sms_mandate_confirmed,
       r.autopay_mandate_confirmed, u.email AS confirmed_by, r.confirmed_at, r.released_at
  FROM bill_run_releases r LEFT JOIN users u ON u.id = r.confirmed_by
 WHERE r.bill_run_id = %(run)s
"""

# (f) the audit row for the send
SQL_AUDIT = """
SELECT action, actor_user_id, after -> 'confirmations' AS confirmations, created_at
  FROM audit_log
 WHERE tenant_id = %(tenant)s AND entity_type = 'invoice' AND entity_id = %(invoice)s
   AND action = 'invoice.one_time_sent'
"""

# (h) delivery
SQL_DELIVERY = """
SELECT channel, status, copy_no
  FROM outbound_messages
 WHERE source_type = 'invoice' AND source_id = %(invoice)s
 ORDER BY channel
"""

# (i) the readings typed on step 2, saved in Meter Reads — and estimates
SQL_READ_TYPED = """
SELECT a.asset_no, r.current_value, r.source, r.status, r.lifecycle, r.read_at::date, r.estimation_method
  FROM meter_reads r JOIN assets a ON a.id = r.asset_id
 WHERE a.asset_no = %(asset_no)s AND r.current_value = %(value)s AND r.channel = 'total'
   AND r.superseded_by_id IS NULL
"""
SQL_READ_ESTIMATED = """
SELECT a.asset_no, r.current_value, r.consumption, r.source, r.status, r.read_at::date, r.estimation_method
  FROM meter_reads r JOIN assets a ON a.id = r.asset_id
 WHERE a.asset_no = %(asset_no)s AND r.channel = 'total'
   AND (r.source ILIKE '%%estimat%%' OR r.estimation_method IS NOT NULL OR r.status ILIKE '%%estimat%%')
"""

# (a) a fee bill's day — the run's own bill date (case 8)
SQL_RUN_BILL_DATE = "SELECT bill_date FROM bill_runs WHERE id = %(run)s"

# (j) exactly one bill — for the run, and for the account, kind and period
SQL_ONE_PER_RUN = "SELECT count(*) FROM invoices WHERE bill_run_id = %(run)s"
SQL_ONE_PER_PERIOD = """
SELECT count(*) FROM invoices
 WHERE account_id = %(account)s AND bill_type = %(bill_type)s
   AND period_start = %(start)s AND period_end = %(end)s AND status <> 'void'
"""

CENT = Decimal("0.01")


def money(text: str) -> Decimal:
    """`$1,234.56` / `-$46.33` / `($5.00)` → Decimal."""
    t = text.strip().replace(",", "").replace("$", "")
    neg = t.startswith("-") or t.startswith("(")
    t = t.strip("-()")
    return -Decimal(t) if neg else Decimal(t)


def q(cur, sql, **params):
    cur.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def verify_case(cur, tenant: str, n: int, spec: dict, run: dict | None, address: str = "1408 Elm St") -> dict:
    out: dict = {"case": n, "checks": {}, "facts": {}, "fail": []}

    def check(key: str, ok: bool, detail: str) -> None:
        out["checks"][key] = "PASS" if ok else "FAIL"
        if not ok:
            out["fail"].append(f"({key}) {detail}")

    if run is None:
        out["fail"].append("the browser run left no record for this case — it never reached Sent")
        return out
    account = q(cur, SQL_ACCOUNT, unit=spec["unit"], tenant=tenant, address=address)
    if len(account) != 1:
        out["fail"].append(f"{spec['unit']}: {len(account)} accounts")
        return out
    account = account[0]
    inv = q(cur, SQL_INVOICE, invoice=run["sent"]["invoice_id"])
    if not inv:
        out["fail"].append("(a) no invoice row for the id Send answered")
        return out
    inv = inv[0]
    out["facts"].update(invoice_no=inv["invoice_no"], total=str(inv["total"]), status=inv["status"],
                        account_no=account["account_no"])

    # (a)
    raised_ok, raised_note = True, ""
    if spec.get("raised_on"):
        # The day the bill was raised: the run's bill date, which must be the
        # issue day (UTC, ± one day for the zone) — never a fixed calendar date.
        raised = q(cur, SQL_RUN_BILL_DATE, run=inv["bill_run_id"])[0]["bill_date"]
        issued_day = inv["issued_at"].date() if inv["issued_at"] is not None else None
        raised_ok = raised is not None and issued_day is not None and abs((issued_day - raised).days) <= 1
        raised_note = f"; fee raised on {raised}, issued {issued_day}"
        spec = {**spec, "start": str(raised), "end": str(raised)}
    check("a", raised_ok and inv["status"] == "issued" and bool(inv["invoice_no"]) and inv["account_id"] == account["id"]
          and inv["bill_type"] == spec["bill_type"] and str(inv["period_start"]) == spec["start"]
          and str(inv["period_end"]) == spec["end"] and inv["issued_at"] is not None,
          f"status {inv['status']}, no {inv['invoice_no']}, type {inv['bill_type']}, "
          f"period {inv['period_start']}–{inv['period_end']}, account {'ok' if inv['account_id'] == account['id'] else 'WRONG'}"
          f"{raised_note}")

    # (b) lines vs Review, total = Σ lines + tax, 4 dp
    lines = q(cur, SQL_LINES, invoice=inv["id"])
    charge_lines = [l for l in lines if l["kind"] != "tax"]
    tax_lines = [l for l in lines if l["kind"] == "tax"]
    review = run["review"]
    review_amounts = sorted(money(l["amount"]) for l in review["lines"])
    # Review draws ONE usage line per meter per month ("Tiered $21.20",
    # DEF-BIL-8315; one group per month, DEF-BIL-8561); the invoice stores one
    # line per TIER and, on a month cut at a price change, one per segment. So
    # the METERED usage lines of one service, meter and month are added together
    # — exactly `one_time_answer._one_line_per_meter` — and nothing else is
    # merged: a %-of-service line ("40.00% of") and a counted line ("trash - …")
    # print one per segment, as stored.
    folded: dict[tuple, Decimal] = {}
    singles: list[Decimal] = []
    for l in charge_lines:
        amount = Decimal(l["amount"]).quantize(CENT)
        description = l["description"] or ""
        metered = l["kind"] == "usage" and "% of" not in description and " - " not in description
        if metered:
            key = (l["period_start"], l["period_end"], l["service"], l["asset_id"], l["unit"])
            folded[key] = folded.get(key, Decimal(0)) + amount
        else:
            singles.append(amount)
    db_amounts = sorted(list(folded.values()) + singles)
    sum_lines = sum((Decimal(l["amount"]) for l in charge_lines), Decimal(0))
    sum_tax = sum((Decimal(l["amount"]) for l in tax_lines), Decimal(0))
    scale = q(cur, SQL_MONEY_SCALE, invoice=inv["id"])[0]
    # `invoices.subtotal` holds the engine's TAXABLE subtotal (the tax base) —
    # `assemble_document` writes it from `taxable_subtotal` — so it is checked
    # as that, and the page's footer is checked to add up (DEF-BIL-8565).
    tax_base = sum((Decimal(l["amount"]) for l in charge_lines if l["taxable"]), Decimal(0))
    footer = money(review["subtotal"]) + sum((money(t["amount"]) for t in review["tax"]), Decimal(0))
    if review.get("one_time_charges"):
        footer += money(review["one_time_charges"])
    footer_adds_up = footer == money(review["total"])
    out["facts"]["footer"] = (
        f"Subtotal {review['subtotal']} + Tax {[t['amount'] for t in review['tax']]}"
        f" + One-time {review.get('one_time_charges')} = {review['total']} ({'adds up' if footer_adds_up else 'DOES NOT add up'})"
    )
    months = spec.get("months")
    review_groups = review.get("groups")
    out["facts"]["lines"] = [f"{l['kind']}: {l['description']} = {Decimal(l['amount']).quantize(CENT)}" for l in lines]
    review_by_service: dict[str, Decimal] = {}
    for rl in review["lines"]:
        key = rl["service"].strip().lower()
        review_by_service[key] = review_by_service.get(key, Decimal(0)) + money(rl["amount"])
    db_by_service: dict[str, Decimal] = {}
    for dl in charge_lines:
        key = (dl["service"] or "").lower()
        db_by_service[key] = db_by_service.get(key, Decimal(0)) + Decimal(dl["amount"]).quantize(CENT)
    out["facts"]["line_count"] = f"review {len(review['lines'])} lines, issued {len(charge_lines)} charge lines"
    out["facts"]["per_service_sums_match"] = {k: str(v) for k, v in review_by_service.items()} == {
        k: str(v) for k, v in db_by_service.items() if k in review_by_service
    }
    check("b", review_amounts == db_amounts
          and money(review["total"]) == Decimal(inv["total"]).quantize(CENT)
          and Decimal(inv["total"]) == sum_lines + sum_tax
          and Decimal(inv["subtotal"]) == tax_base and Decimal(inv["tax_total"]) == sum_tax
          and footer_adds_up
          and (months is None or (review_groups or 0) >= months)
          and scale["lines_over_4dp"] == 0 and scale["header_over_4dp"] == 0
          and Decimal(inv["total"]).quantize(CENT) == Decimal(spec["total"]),
          f"subtotal {inv['subtotal']} (tax base {tax_base}); footer {out['facts']['footer']}; "
          f"Review groups {review_groups} (months {months}); "
          f"hand-priced total {spec['total']} vs issued {Decimal(inv['total']).quantize(CENT)}; "
          f"review {[str(a) for a in review_amounts]} vs db {[str(a) for a in db_amounts]}; "
          f"review total {review['total']} vs db {inv['total']}; Σlines {sum_lines} + Σtax {sum_tax}; "
          f"over-4dp lines {scale['lines_over_4dp']} header {scale['header_over_4dp']}")

    if months:
        stored_months = {(l["period_start"], l["period_end"]) for l in charge_lines if l["kind"] != "fee"}
        out["facts"]["stored_months"] = sorted(f"{a}..{b}" for a, b in stored_months)
        if len(stored_months) < months:
            out["checks"]["b"] = "FAIL"
            out["fail"].append(f"(b) stored lines carry {len(stored_months)} windows, want one per month ({months})")
        # every water line names its meter — J74's unit has TWO water meters. A
        # ONE-meter unit (J75) names none on any bill kind, so it is not asked.
        two_meters = spec.get("meters", 2) > 1
        nameless = [l for l in charge_lines if two_meters and l["service"] == "water" and not l["asset_id"]]
        # DEF-BIL-8733 — a counted service (trash, fire) is ONE line per month.
        for service in ("trash", "fire"):
            stored = [l for l in charge_lines if l["service"] == service]
            if stored and len(stored) != months:
                out["checks"]["b"] = "FAIL"
                out["fail"].append(f"(b) {len(stored)} {service} lines over {months} months, want one a month (DEF-BIL-8733)")
        out["facts"]["water_lines_without_meter"] = len(nameless)
        if nameless:
            out["checks"]["b"] = "FAIL"
            out["fail"].append(f"(b) {len(nameless)} water lines name no meter (DEF-BIL-8561)")

    # (k) J75 — every capacity service's stored line keeps its size trace
    # (BR-BIL-1067): per size the count, and base_priced false exactly where the
    # seed left the size unpriced. On a multi-month bill each month repeats it.
    if spec.get("capacity"):
        problems = []
        for service, sizes in spec["capacity"].items():
            traced = [l["pricing_trace"] for l in charge_lines
                      if l["service"] == service and l["pricing_trace"] and l["pricing_trace"].get("sizes")]
            if not traced:
                problems.append(f"{service}: no stored line carries a size trace")
                continue
            for trace in traced:
                got = {row["size"]: row["count"] for row in trace["sizes"]}
                if got != sizes:
                    problems.append(f"{service}: trace sizes {got}, want {sizes}")
                unpriced = {row["size"] for row in trace["sizes"] if row.get("base_priced") is False}
                want_unpriced = {spec.get("unpriced", {}).get(service)} - {None}
                if unpriced != want_unpriced:
                    problems.append(f"{service}: unpriced sizes {sorted(unpriced)}, want {sorted(want_unpriced)}")
        out["facts"]["traces"] = sorted({
            f"{l['service']}: " + ", ".join(f"{r['size']} x{r['count']} base {r.get('base_each')}"
                                            for r in l["pricing_trace"]["sizes"])
            for l in charge_lines if l["pricing_trace"] and l["pricing_trace"].get("sizes")})
        check("k", not problems, "; ".join(sorted(set(problems))))

    # (c) tax lines, as Review showed them, or none where nothing is taxable
    review_tax = sorted(money(t["amount"]) for t in review["tax"])
    db_tax = sorted(Decimal(l["amount"]).quantize(CENT) for l in tax_lines)
    out["facts"]["tax"] = [str(t) for t in db_tax]
    check("c", review_tax == db_tax and (bool(db_tax) == spec["taxed"]),
          f"review tax {[str(t) for t in review_tax]} vs db {[str(t) for t in db_tax]}; taxed expected {spec['taxed']}")

    # (d) every entry sourced to the bill balances; the bill's own entry debits the
    # receivable by the total; a deposit is credited to its liability (first bill)
    # or released from it against the receivable, any excess to customer credit (final)
    journal = q(cur, SQL_JOURNAL, invoice=inv["id"])
    legs = q(cur, SQL_JOURNAL_LEGS, invoice=inv["id"])
    other = q(cur, SQL_OTHER_ENTRIES, account=account["id"], invoice=inv["id"])
    ar_net = q(cur, SQL_AR_NET, account=account["id"])[0]["ar_net"]
    out["facts"]["journal"] = [f"{g['side']} {g['code']} {g['name']} {Decimal(g['amount']).quantize(CENT)}" for g in legs]
    out["facts"]["other_entries"] = [
        f"{o['source_type']} {o['side']} {o['code']} {o['name']} {Decimal(o['amount']).quantize(CENT)}" for o in other
    ]
    out["facts"]["receivable_net"] = str(Decimal(ar_net).quantize(CENT))
    balanced = bool(journal) and all(j["debits"] == j["credits"] and j["status"] == "posted" for j in journal)
    first = journal[0]["id"] if journal else None
    bill_legs = [g for g in legs if g["entry"] == first]
    ar_debit = sum((Decimal(g["amount"]) for g in bill_legs if g["side"] == "debit" and g["code"] == "1200"
                    and g["account_id"] == account["id"]), Decimal(0))
    total = Decimal(inv["total"])
    ok_d = balanced and ar_debit == total
    detail = (f"{len(journal)} entries sourced to the bill, debits/credits "
              f"{[(str(j['debits']), str(j['credits']), j['status']) for j in journal]}; receivable debit "
              f"{ar_debit} vs total {total}")
    dep = spec.get("deposit")
    want_ar = total
    if dep == "charged":
        dep_credit = [g for g in bill_legs if g["side"] == "credit" and "deposit" in (g["name"] or "").lower()]
        ok_d = ok_d and len(dep_credit) == 1
        detail += f"; deposit credit legs {[(g['code'], str(g['amount'])) for g in dep_credit]}"
    if dep == "applied":
        want = Decimal(spec["deposit_amount"])
        rest = [g for g in legs if g["entry"] != first]
        dep_debit = sum((Decimal(g["amount"]) for g in rest if g["side"] == "debit"
                         and "deposit" in (g["name"] or "").lower()), Decimal(0))
        ar_credit = sum((Decimal(g["amount"]) for g in rest if g["side"] == "credit" and g["code"] == "1200"),
                        Decimal(0))
        credit_bal = sum((Decimal(g["amount"]) for g in rest if g["side"] == "credit"
                          and "credit" in (g["name"] or "").lower()), Decimal(0))
        refund = Decimal(spec["refund"]) if spec.get("refund") else Decimal(0)
        ok_d = (ok_d and dep_debit == want and ar_credit == min(want, total)
                and credit_bal.quantize(CENT) == refund)
        want_ar = total - min(want, total)
        detail += (f"; deposit released {dep_debit} (want {want}), receivable credited {ar_credit}, "
                   f"customer credit {credit_bal} (want {refund})")
    ok_d = ok_d and Decimal(ar_net) == want_ar
    detail += f"; receivable for the customer moved {ar_net} (want {want_ar})"
    check("d", ok_d, detail)

    # (e) the release row: five confirmations, the clerk, the time
    rel = q(cur, SQL_RELEASE, run=inv["bill_run_id"])
    audit = q(cur, SQL_AUDIT, tenant=tenant, invoice=inv["id"])
    five = audit[0]["confirmations"] if len(audit) == 1 else {}
    ok_e = (len(rel) == 1 and all(rel[0][k] for k in ("compliance_confirmed", "email_mandate_confirmed",
                                                        "sms_mandate_confirmed", "autopay_mandate_confirmed"))
            and rel[0]["confirmed_by"] is not None and rel[0]["confirmed_at"] is not None
            and rel[0]["released_at"] is not None and bool(five) and all(five.values()) and len(five) == 5)
    if rel:
        out["facts"]["release"] = f"by {rel[0]['confirmed_by']} at {rel[0]['confirmed_at']:%Y-%m-%d %H:%M:%S}"
    check("e", ok_e, f"release rows {len(rel)} {rel[:1]}; audited confirmations {five}")

    # (f) one audit row for the send
    check("f", len(audit) == 1, f"{len(audit)} 'invoice.one_time_sent' rows")

    # (g) the snapshot names the customer, the service and mailing addresses, the utility's address
    payload = inv["bill_payload"] or {}
    want = ("customer_name", "service_address", "mailing_address", "utility_address")
    missing = [k for k in want if not payload.get(k)]
    out["facts"]["snapshot"] = {k: payload.get(k) for k in want}
    if spec.get("approved_by"):
        approved = (payload.get("penalty") or {}).get("approved_by")
        out["facts"]["approved_by"] = approved
        if not approved:
            missing.append("penalty.approved_by")
    check("g", not missing, f"missing on the frozen bill: {missing}")

    # (h) delivery queued, paper at least
    deliveries = q(cur, SQL_DELIVERY, invoice=inv["id"])
    out["facts"]["delivery"] = [f"{d['channel']}:{d['status']}" for d in deliveries]
    check("h", any(d["channel"] == "pdf_print" and d["status"] in ("queued", "sent", "delivered") for d in deliveries),
          f"deliveries {out['facts']['delivery']}")

    # (i) typed readings saved; estimates saved as estimated readings
    missing_reads = []
    for asset_no, value in spec["typed"]:
        rows = q(cur, SQL_READ_TYPED, asset_no=asset_no, value=Decimal(value))
        # `billed` is a committed read the bill has locked (the Sent screen's "Meter reads · Locked")
        if not any(r["lifecycle"] in ("committed", "billed") for r in rows):
            missing_reads.append(f"{asset_no}={value} {rows}")
    missing_est = []
    for asset_no in spec["estimated"]:
        rows = q(cur, SQL_READ_ESTIMATED, asset_no=asset_no)
        if not rows:
            missing_est.append(asset_no)
    wrongly_saved = []
    for asset_no in spec.get("no_estimate_rows", ()):
        wrongly_saved.extend(q(cur, SQL_READ_ESTIMATED, asset_no=asset_no))
    check("i", not missing_reads and not missing_est and not wrongly_saved,
          f"typed not saved {missing_reads}; no estimated read saved for {missing_est}; "
          f"estimated rows that double-count a real reading {wrongly_saved}")

    # (j) one bill; the second Send answered the same bill; the second draft was refused
    per_run = q(cur, SQL_ONE_PER_RUN, run=inv["bill_run_id"])[0]["count"]
    per_period = q(cur, SQL_ONE_PER_PERIOD, account=account["id"], bill_type=spec["bill_type"],
                   start=spec["start"], end=spec["end"])[0]["count"]
    rs, rd = run["replay_send"], run["replay_draft"]
    check("j", per_run == 1 and per_period == 1 and rs["created"] is False and rs["invoice_no"] == inv["invoice_no"]
          and rd["status"] >= 400,
          f"{per_run} per run, {per_period} per account+kind+period; replayed Send created={rs['created']} "
          f"no={rs['invoice_no']}; replayed draft {rd['status']} {rd['code']}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=sorted(WORLDS), default="j74")
    parser.add_argument("--results", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("set DATABASE_URL to the database the J74 walk wrote", file=sys.stderr)
        return 2
    p = urlparse(url)
    world = WORLDS[args.world]
    results_path = Path(args.results or world["results"])
    runs = json.loads(results_path.read_text()) if results_path.exists() else {}
    results = []
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        tenant = q(cur, SQL_TENANT, slug=world["slug"])[0]["id"]
        cur.execute(SQL_SET_TENANT, {"tenant": str(tenant)})
        for n, spec in world["cases"].items():
            results.append(verify_case(cur, str(tenant), n, spec, runs.get(str(n)), world["address"]))
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(f"{args.world.upper()} database check — {p.path.lstrip('/')} on {p.hostname}:{p.port}")
        for r in results:
            verdict = "PASS" if not r["fail"] else "FAIL"
            f = r["facts"]
            print(f"\ncase {r['case']}: {verdict}  {f.get('invoice_no', '—')}  total {f.get('total', '—')}  "
                  + " ".join(f"{k}:{v}" for k, v in r["checks"].items()))
            for key in ("footer", "traces", "lines", "tax", "journal", "other_entries", "release", "snapshot", "approved_by", "delivery"):
                if key in f:
                    print(f"    {key}: {f[key]}")
            for line in r["fail"]:
                print(f"    FAIL {line}")
    return 0 if all(not r["fail"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
