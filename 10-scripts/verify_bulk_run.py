#!/usr/bin/env python3
"""verify_bulk_run — the bulk bill run's audit IN THE DATABASE, every account of one run.

Plan `04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md` E16 (run audit)
and E17 (single-account trace) · acceptance `20-bulk-run-clerk-acceptance.md` §5 ·
journey `08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md` (§ E16/E17, where
every query below is reproduced) · pattern `10-scripts/verify_j74_one_time_bill.py`.

The PO set the proof per step, verbatim (2026-09-30): *"here it is important process
complete for 1 account end to end and does not break down in between"*, and

  (2) *"all decision made by clark from screen for that bill run are saved correctly"*
  (3) *"all decision saved by clark are passed to bill run process correctly + it check
      the data from system if required + it create records other than bill due to
      impact on next billing"*
  (4) *"check all draft bills are in database + summary is correct on screen"*
  (5) *"background processes are completed for bulk bill run - communication, draft to
      final bills, ledger payments reading etc"*
  (6) Send — every bill issued with its number, lines = draft to the cent, the books
      balanced, the balance moved by the total, paper queued, an audit row, and a
      second Send issuing nothing.

Given ONE run, this reads PostgreSQL and answers every one of those for EVERY
account the run checked, then prints a per-account table and a summary. It WRITES
NOTHING. Every query is a plain SQL constant below so anyone can paste it into
`psql`. It sets `app.tenant_id` before it reads a tenant table (CLAUDE.md hard rule
1), so it answers the same under an RLS-bound role as under a superuser.

    DATABASE_URL=postgres://…/sbh_j72 python 10-scripts/verify_bulk_run.py RUN-0002 \\
        [--walk /tmp/j72-accuracy-1440.json]   # what the clerk chose and was shown
        [--next-run RUN-0003]                  # month two on the same accounts
        [--account AC-2026-00003]              # one account (E17's trace)
        [--json]

THE STAGE IS READ FROM THE DATABASE, never passed: a run whose release carries
`released_at` is SENT and gets the after-Send checks; one with drafts is at SIGN
OFF; one with only a saved Check is at CHECK. A check that does not apply at the
run's stage prints `–` (not applicable), never PASS.

WHAT IT DOES NOT PROVE, said so it cannot be mistaken for a pass:
  * the SCREEN — screen figures are taken from the walk's recorded numbers
    (`--walk`, the state file `J72-bulk-bill-run-accuracy.spec.ts` and the E17 spec
    write); without `--walk` the screen check reports `–`;
  * the second Send — a read-only script cannot press Send. It proves the
    database carries exactly ONE of everything a Send writes (one issue audit, one
    journal, one delivery row per channel, one release) so a replay that wrote
    anything shows as a duplicate; the E17 spec presses Send a second time and
    compares this script's counts before and after.

Exit 0 when every applicable check passes, 1 when any fails — and it prints every
failure, never only the first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg

REPO = Path(__file__).resolve().parents[1]
CENT = Decimal("0.01")

# ── the SQL (copied verbatim into J72 § E16/E17) ─────────────────────────────

SQL_RUN = """
SELECT r.id, r.tenant_id, r.run_no, r.status, r.period_start, r.period_end, r.bill_date,
       r.label, r.findings_summary, r.parent_run_id
  FROM bill_runs r
 WHERE r.run_no = %(run)s OR r.id::text = %(run)s
"""
SQL_SET_TENANT = "SELECT set_config('app.tenant_id', %(tenant)s, false)"

# Every account the run checked: the run's population (Scope → Check).
SQL_CHECKED = """
SELECT c.account_id, c.account_no, c.status, c.stale, c.checked_at, c.unit_id,
       a.paperless, a.sms_reminders
  FROM bill_run_account_checks c JOIN accounts a ON a.id = c.account_id
 WHERE c.bill_run_id = %(run)s
 ORDER BY c.account_no
"""
SQL_FINDINGS = """
SELECT f.account_id, f.code, f.severity, f.service_code, f.params
  FROM bill_run_findings f
 WHERE f.bill_run_id = %(run)s
"""
# Every decision row, current and superseded, with who.
SQL_DECISIONS = """
SELECT d.id, d.account_id, d.case, d.choice, d.reason, d.amount, d.unit, d.created_at,
       d.superseded_by_id, s.code AS service, u.full_name AS decided_by, u.email AS decided_by_email
  FROM bill_run_decisions d
  LEFT JOIN services s ON s.id = d.service_id
  LEFT JOIN users u ON u.id = d.decided_by
 WHERE d.bill_run_id = %(run)s
 ORDER BY d.created_at
"""
SQL_STANDING = """
SELECT sa.case, sa.choice, sa.superseded, sa.created_at
  FROM bill_run_standing_answers sa WHERE sa.bill_run_id = %(run)s
"""
# Pending billing (both doors write this row).
SQL_EXCLUSIONS = """
SELECT e.account_id, e.reason_code, e.detail, e.created_at, e.resolved_at, e.resolved_by_run_id,
       e.next_cycle_at
  FROM bill_run_exclusions e WHERE e.bill_run_id = %(run)s
"""
SQL_BREAKS = """
SELECT b.account_id, b.stage, b.reason, b.detail, b.resolution
  FROM bill_run_breaks b WHERE b.bill_run_id = %(run)s
"""
SQL_INVOICES = """
SELECT i.id, i.account_id, i.invoice_no, i.status, i.bill_type, i.period_start, i.period_end,
       i.subtotal, i.tax_total, i.total, i.currency, i.issued_at, i.bill_payload
  FROM invoices i WHERE i.bill_run_id = %(run)s
"""
SQL_LINES = """
SELECT l.invoice_id, l.kind, s.code AS service, l.description, l.quantity, l.unit, l.unit_price,
       l.amount, l.period_start, l.period_end
  FROM invoice_lines l JOIN invoices i ON i.id = l.invoice_id
  LEFT JOIN services s ON s.id = l.service_id
 WHERE i.bill_run_id = %(run)s
 ORDER BY l.created_at, l.id
"""
SQL_RELEASES = """
SELECT r.id, r.bill_count, r.account_count, r.total_amount, r.compliance_confirmed,
       r.email_mandate_confirmed, r.sms_mandate_confirmed, r.autopay_mandate_confirmed,
       u.full_name AS confirmed_by, r.confirmed_at, r.released_at
  FROM bill_run_releases r LEFT JOIN users u ON u.id = r.confirmed_by
 WHERE r.bill_run_id = %(run)s ORDER BY r.created_at
"""
# The ledger: each bill's entries, debits = credits, and the receivable (1200) leg.
SQL_JOURNALS = """
SELECT je.source_id AS invoice_id, je.id, je.status,
       sum(jl.amount) FILTER (WHERE jl.side = 'debit')  AS debits,
       sum(jl.amount) FILTER (WHERE jl.side = 'credit') AS credits,
       sum(CASE WHEN la.code = '1200' AND jl.side = 'debit' THEN jl.amount
                WHEN la.code = '1200' AND jl.side = 'credit' THEN -jl.amount ELSE 0 END) AS ar_net,
       bool_and(la.code <> '1200' OR jl.account_id = i.account_id) AS ar_on_account
  FROM journal_entries je
  JOIN journal_lines jl ON jl.journal_entry_id = je.id
  JOIN ledger_accounts la ON la.id = jl.ledger_account_id
  JOIN invoices i ON i.id = je.source_id
 WHERE je.source_type = 'invoice' AND i.bill_run_id = %(run)s
 GROUP BY je.source_id, je.id, je.status
"""
SQL_DELIVERY = """
SELECT m.source_id AS invoice_id, m.channel, m.status, m.copy_no, m.held
  FROM outbound_messages m JOIN invoices i ON i.id = m.source_id
 WHERE m.source_type = 'invoice' AND i.bill_run_id = %(run)s
"""
SQL_AUDIT_INVOICES = """
SELECT al.entity_id AS invoice_id, al.action, count(*) AS n
  FROM audit_log al JOIN invoices i ON i.id = al.entity_id
 WHERE al.entity_type = 'invoice' AND i.bill_run_id = %(run)s
 GROUP BY al.entity_id, al.action
"""
SQL_AUDIT_RUN = """
SELECT al.action, al.after, al.created_at
  FROM audit_log al
 WHERE al.entity_type = 'bill_run' AND al.entity_id = %(run)s
 ORDER BY al.created_at
"""
# The estimates the run's decisions wrote into Meter Reads (their audit names the run).
SQL_ESTIMATES = """
SELECT r.id, r.asset_id, a.asset_no, r.read_at, r.current_value, r.consumption, r.unit, r.source,
       r.status, r.lifecycle, r.estimation_method, r.superseded_by_id,
       al.after ->> 'invoice_id' AS invoice_id
  FROM audit_log al
  JOIN meter_reads r ON r.id = al.entity_id
  JOIN assets a ON a.id = r.asset_id
 WHERE al.action = 'read.estimated' AND al.after ->> 'bill_run_id' = %(run)s::text
"""
SQL_READS_BY_ID = """
SELECT r.id, r.asset_id, r.read_at, r.current_value, r.consumption, r.unit, r.source, r.status,
       r.lifecycle, r.superseded_by_id, r.trues_up_read_ids
  FROM meter_reads r WHERE r.id = ANY(%(ids)s)
"""
SQL_PLAN_EXTENDED = """
SELECT al.entity_id AS plan_id, pp.account_id, al.after, al.created_at
  FROM audit_log al JOIN payment_plans pp ON pp.id = al.entity_id
 WHERE al.action = 'payment_plan.extended_one_month' AND pp.account_id = ANY(%(accounts)s)
   AND al.created_at >= %(since)s
"""
SQL_PLAN_INSTALMENTS = """
SELECT pp.account_id, pp.id AS plan_id, pp.installment_count, pp.status,
       count(i.id) AS n, min(i.due_date) AS first_due, max(i.due_date) AS last_due,
       bool_and(i.amount = pp.total_amount / NULLIF(pp.installment_count, 0)) AS level
  FROM payment_plans pp JOIN payment_plan_installments i ON i.plan_id = pp.id
 WHERE pp.account_id = ANY(%(accounts)s) AND pp.status NOT IN ('cancelled', 'closed')
 GROUP BY pp.account_id, pp.id, pp.installment_count, pp.status
"""
# The payments the Check saw as paid after the cut-off (the finding names them).
SQL_PAYMENTS = """
SELECT p.id, p.account_id, p.amount, p.status, p.posted_at, p.journal_entry_id
  FROM payments p WHERE p.account_id = ANY(%(accounts)s) AND p.posted_at::date > %(end)s
"""
# Background jobs of the run (Check, Calculate, Send all carry the run id).
SQL_JOBS = """
SELECT j.kind, j.status, j.error, j.updated_at, j.scope_key, j.created_at
  FROM jobs j WHERE j.payload ->> 'run_id' = %(run)s::text
 ORDER BY j.created_at
"""
# Every issued bill of an account (month two: continuity, no double billing).
SQL_ACCOUNT_BILLS = """
SELECT i.id, i.account_id, i.invoice_no, i.bill_run_id, i.period_start, i.period_end, i.status,
       i.bill_type, i.total, i.bill_payload
  FROM invoices i
 WHERE i.account_id = ANY(%(accounts)s) AND i.status NOT IN ('draft', 'void')
 ORDER BY i.period_start, i.issued_at
"""
SQL_ACCOUNT_LINES = """
SELECT l.invoice_id, l.kind, s.code AS service, l.quantity, l.unit, l.amount
  FROM invoice_lines l LEFT JOIN services s ON s.id = l.service_id
 WHERE l.invoice_id = ANY(%(invoices)s)
"""
SQL_ACTUAL_ON_OR_BEFORE = """
SELECT r.id, r.read_at, r.current_value
  FROM meter_reads r
 WHERE r.asset_id = %(asset)s AND r.channel = 'total' AND r.current_value IS NOT NULL
   AND r.superseded_by_id IS NULL AND r.read_at::date <= %(day)s
 ORDER BY r.read_at DESC LIMIT 1
"""

# E17's trace: every reading on the account's meters (through its unit's service
# points), so a step can show what Meter Reads holds, estimate and true-up included.
SQL_ACCOUNT_READS = """
SELECT a.asset_no, s.code AS service, r.id, r.read_at, r.current_value, r.prior_value, r.consumption,
       r.unit, r.source, r.status, r.lifecycle, r.estimation_method, r.superseded_by_id,
       r.trues_up_read_ids
  FROM accounts ac
  JOIN service_points sp ON sp.unit_id = ac.unit_id
  JOIN services s ON s.id = sp.service_id
  JOIN assets a ON a.service_point_id = sp.id
  JOIN meter_reads r ON r.asset_id = a.id AND r.channel = 'total'
 WHERE ac.id = %(account)s
 ORDER BY a.asset_no, r.read_at
"""
SQL_ACCOUNT_AUDIT = """
SELECT al.action, al.entity_type, al.created_at, u.full_name AS actor
  FROM audit_log al LEFT JOIN users u ON u.id = al.actor_user_id
 WHERE (al.entity_id = ANY(%(entities)s)
        OR (al.entity_type = 'bill_run' AND al.entity_id = %(run)s
            AND al.after ->> 'account_id' = %(account)s::text))
 ORDER BY al.created_at
"""

#: The walk's answer LABEL (what the clerk clicked) → the stored choice.
LABEL_TO_CHOICE = {
    "Estimate the reading": "estimate",
    # The Check now says *Estimate* (the E11 copy lane, 2026-10-01); the walk
    # records the label it clicked, so both spellings map to the one choice.
    "Estimate": "estimate",
    "Hold this account back": "hold",
    "Look into it": "investigate",
    "Waive": "waive",
    "Include": "include",
    "Apply to this bill": "apply_this_bill",
    "Apply to next bill": "apply_next_bill",
    "Skip": "skip",
    "Add to bill": "add_to_bill",
    "Leave out": "leave_out",
    "Bill as it stands": "bill_as_is",
}
#: Choices that keep an account OUT of this run's bills (it goes to Pending billing).
HOLDING = {"hold", "investigate", "leave_out", "wait_next_cycle"}
#: Choices that keep it out and are NOT queued (PO 2026-09-30, fixed-charge case 2).
WAIVING = {("base_only_billing", "waive")}

PASS, FAIL, NA = "PASS", "FAIL", "–"


def q(cur, sql, **params):
    cur.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def d2(x) -> str:
    return "—" if x is None else str(Decimal(str(x)).quantize(CENT))


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is required (the PostgreSQL the walk wrote).")
    return url


class Account:
    """One account of the run and every check's verdict on it."""

    def __init__(self, row: dict):
        self.id = str(row["account_id"])
        self.no = row["account_no"]
        self.check_status = row["status"]
        self.row = row
        self.verdict: dict[str, str] = {}
        self.notes: list[str] = []
        self.end = "?"

    def mark(self, check: str, ok: bool | None, why: str = "") -> None:
        if ok is None:
            self.verdict.setdefault(check, NA)
            return
        if not ok:
            self.verdict[check] = FAIL
            self.notes.append(f"[{check}] {why}")
        elif self.verdict.get(check) != FAIL:
            self.verdict[check] = PASS


#: The checks, in the PO's step order. key → (step, one-line description)
CHECKS: dict[str, tuple[str, str]] = {
    "P2.saved": ("2", "every decision the walk made is saved: account, answer, who, when, amount/unit; nothing unchosen"),
    "P3.effect": ("3", "each saved answer is what Calculate used (estimate on the line, waived/held not billed, instalment, payment once)"),
    "P3.next": ("3", "records for the next billing exist (estimate in Meter Reads, plan extended, pending-billing row, waive logged)"),
    "P4.drafts": ("4", "one draft per priced account, none for held/blocked/waived (before Send); none left after Send"),
    "P4.screen": ("4", "the screen's figures equal the database sums (from the walk's recorded numbers)"),
    "A3.end": ("5", "the account ends in exactly one place: issued · failed with a reason · Not in this run"),
    "S6.issued": ("6", "every bill ISSUED, numbered, dated; numbers unique"),
    "S6.draft": ("6", "the issued bill equals its draft to the cent; lines + tax = total; payload = lines"),
    "S6.ledger": ("6", "its journal balances and the receivable moved by the bill's total, on this account"),
    "S5.delivery": ("5", "delivery queued per the customer's election (paper at least)"),
    "S5.reads": ("5", "every reading the bill used is billed-locked in Meter Reads"),
    "S6.audit": ("6", "one issue audit row per bill; the run's release audited"),
    "S6.once": ("6", "a second Send wrote nothing: one release, one journal, one delivery per channel, one issue audit"),
    "S5.jobs": ("5", "no background job of the run is left pending or failed"),
    "S5.locked": ("5", "decisions and the check record are locked after Send (nothing written after it)"),
    "M2.next": ("M2", "month two: the next bill starts the day after the last, no days twice"),
    "M2.base": ("M2", "month two: no base charge billed twice for the same days"),
    "M2.usage": ("M2", "month two: usage billed over both months = the actual meter advance (estimate trued up)"),
}


def verify(cur, run_ref: str, *, walk: dict | None, next_run: str | None, only: str | None) -> dict:
    runs = q(cur, SQL_RUN, run=run_ref)
    if len(runs) != 1:
        sys.exit(f"run {run_ref!r}: {len(runs)} rows")
    run = runs[0]
    rid = run["id"]
    q(cur, SQL_SET_TENANT, tenant=str(run["tenant_id"]))

    releases = q(cur, SQL_RELEASES, run=rid)
    sent_at = next((r["released_at"] for r in releases if r["released_at"] is not None), None)
    invoices = q(cur, SQL_INVOICES, run=rid)
    stage = "sent" if sent_at else ("signoff" if invoices else "check")

    checked = q(cur, SQL_CHECKED, run=rid)
    if only:
        checked = [c for c in checked if c["account_no"] == only]
        if not checked:
            sys.exit(f"{only} is not in {run['run_no']}")
    accounts = {str(c["account_id"]): Account(c) for c in checked}
    ids = list(accounts)

    findings = defaultdict(list)
    for f in q(cur, SQL_FINDINGS, run=rid):
        findings[str(f["account_id"])].append(f)
    all_decisions = q(cur, SQL_DECISIONS, run=rid)
    current = defaultdict(list)
    for d in all_decisions:
        if d["superseded_by_id"] is None:
            current[str(d["account_id"])].append(d)
    standing = {s["case"]: s["choice"] for s in q(cur, SQL_STANDING, run=rid) if not s["superseded"]}
    excl = {str(e["account_id"]): e for e in q(cur, SQL_EXCLUSIONS, run=rid)}
    breaks = {str(b["account_id"]): b for b in q(cur, SQL_BREAKS, run=rid)}
    inv_by_acct = defaultdict(list)
    for i in invoices:
        inv_by_acct[str(i["account_id"])].append(i)
    lines = defaultdict(list)
    for ln in q(cur, SQL_LINES, run=rid):
        lines[str(ln["invoice_id"])].append(ln)
    journals = defaultdict(list)
    for j in q(cur, SQL_JOURNALS, run=rid):
        journals[str(j["invoice_id"])].append(j)
    delivery = defaultdict(list)
    for m in q(cur, SQL_DELIVERY, run=rid):
        delivery[str(m["invoice_id"])].append(m)
    inv_audit = defaultdict(dict)
    for a in q(cur, SQL_AUDIT_INVOICES, run=rid):
        inv_audit[str(a["invoice_id"])][a["action"]] = a["n"]
    run_audit = q(cur, SQL_AUDIT_RUN, run=rid)
    estimates = defaultdict(list)
    for e in q(cur, SQL_ESTIMATES, run=rid):
        estimates[str(e["asset_id"])].append(e)
    est_by_invoice = defaultdict(list)
    for e in [x for v in estimates.values() for x in v]:
        est_by_invoice[str(e["invoice_id"])].append(e)
    since = min((c["checked_at"] for c in checked), default=datetime(1970, 1, 1))
    plan_ext = defaultdict(list)
    for p in q(cur, SQL_PLAN_EXTENDED, accounts=ids, since=since):
        plan_ext[str(p["account_id"])].append(p)
    plan_inst = {str(p["account_id"]): p for p in q(cur, SQL_PLAN_INSTALMENTS, accounts=ids)}
    late_pay = defaultdict(list)
    for p in q(cur, SQL_PAYMENTS, accounts=ids, end=run["period_end"]):
        late_pay[str(p["account_id"])].append(p)
    jobs = q(cur, SQL_JOBS, run=rid)
    read_ids = [
        s.get("read_id")
        for i in invoices
        for s in ((i["bill_payload"] or {}).get("services") or [])
        if s.get("read_id")
    ]
    reads = {str(r["id"]): r for r in q(cur, SQL_READS_BY_ID, ids=read_ids)} if read_ids else {}
    waived_audit = {
        str((a["after"] or {}).get("account_id")): a
        for a in run_audit
        if a["action"] == "bill_run.base_waived"
    }

    walk_decided = defaultdict(list)
    for w in (walk or {}).get("decided") or []:
        walk_decided[w["account"]].append(w)
    walk_drafts = (walk or {}).get("drafts") or {}

    all_numbers = [i["invoice_no"] for i in invoices if i["invoice_no"]]
    dup_numbers = {n for n in all_numbers if all_numbers.count(n) > 1}

    for acc in accounts.values():
        mine = inv_by_acct.get(acc.id, [])
        drafts = [i for i in mine if i["status"] == "draft"]
        issued = [i for i in mine if i["status"] == "issued"]
        cur_dec = current.get(acc.id, [])
        choices = {(d["case"], d["choice"]) for d in cur_dec}
        # A decision raised by the Check and answered only by the tag's standing answer.
        for f in findings.get(acc.id, []):
            if f["severity"] == "decision" and not any(d["case"] == f["code"] for d in cur_dec):
                if f["code"] in standing:
                    choices.add((f["code"], standing[f["code"]]))
        held = any(c in HOLDING for _, c in choices)
        waived = any(c in WAIVING for c in choices)
        undecided = acc.check_status == "decision" and any(
            f["severity"] == "decision"
            and not any(k == f["code"] for k, _ in choices)
            for f in findings.get(acc.id, [])
        )
        should_bill = acc.check_status == "ready" or (
            acc.check_status == "decision" and not held and not waived and not undecided
        )
        acc.facts = {
            "check": acc.check_status,
            "answers": ", ".join(sorted(f"{k}={c}" for k, c in choices)) or "—",
            "bill": (issued or drafts or [{}])[0].get("invoice_no") or "—",
            "total": d2((issued or drafts or [{}])[0].get("total")),
        }

        # ── (2) decisions saved ──────────────────────────────────────────
        for d in cur_dec:
            acc.mark("P2.saved", d["decided_by"] is not None and d["created_at"] is not None,
                     f"{d['case']}={d['choice']} has no who/when")
            if (walk or {}).get("clerk"):
                acc.mark("P2.saved", d["decided_by"] == walk["clerk"],
                         f"{d['case']}={d['choice']} saved by {d['decided_by']!r}, the walk's clerk is {walk['clerk']!r}")
            if d["choice"] == "estimate":
                acc.mark("P2.saved", d["amount"] is not None and bool(d["unit"]),
                         f"estimate saved with amount {d['amount']} unit {d['unit']!r}")
            if (d["case"], d["choice"]) in WAIVING:
                acc.mark("P2.saved", bool(d["reason"]), "waive saved with no reason")
        if walk is not None and walk.get("decided") is not None:
            chosen = walk_decided.get(acc.no, [])
            for w in chosen:
                want = LABEL_TO_CHOICE.get(w["answer"])
                hit = [d for d in cur_dec if d["choice"] == want]
                acc.mark("P2.saved", bool(hit), f"walk chose {w['answer']!r} → no current {want} row")
                if hit:
                    d = hit[-1]
                    at = datetime.fromisoformat(w["at"].replace("Z", "+00:00"))
                    acc.mark("P2.saved", abs(d["created_at"] - at) < timedelta(minutes=3),
                             f"{want} saved at {d['created_at']:%H:%M:%S}, walk at {at:%H:%M:%S}")
                    if walk.get("clerk"):
                        acc.mark("P2.saved", d["decided_by"] == walk["clerk"],
                                 f"{want} saved by {d['decided_by']!r}, walk clerk {walk['clerk']!r}")
                    if w.get("amount") is not None:
                        acc.mark("P2.saved", d["amount"] is not None
                                 and Decimal(str(d["amount"])) == Decimal(str(w["amount"]))
                                 and (d["unit"] or "") == (w.get("unit") or d["unit"] or ""),
                                 f"{want} amount {d['amount']} {d['unit']} vs walk {w['amount']} {w.get('unit')}")
            walked = {LABEL_TO_CHOICE.get(w["answer"]) for w in chosen}
            for d in cur_dec:
                if d["case"] == "left_out" and d["choice"] == "put_back":
                    continue
                acc.mark("P2.saved", d["choice"] in walked,
                         f"a current {d['case']}={d['choice']} row the walk never chose")
        if not cur_dec and walk is None:
            acc.mark("P2.saved", None)

        # ── (3) decisions applied ────────────────────────────────────────
        bill = (issued or drafts or [None])[0]
        blines = lines.get(str(bill["id"]), []) if bill else []
        payload = (bill or {}).get("bill_payload") or {}
        for d in cur_dec:
            case, choice = d["case"], d["choice"]
            if choice == "estimate":
                use = [ln for ln in blines if ln["kind"] == "usage" and (ln["service"] == d["service"] or d["service"] is None)]
                qty = sum((Decimal(str(ln["quantity"])) for ln in use if ln["quantity"] is not None), Decimal(0))
                acc.mark("P3.effect", bill is not None and d["amount"] is not None
                         and qty == Decimal(str(d["amount"]))
                         and all((ln["unit"] or "") == (d["unit"] or "") for ln in use),
                         f"estimate {d['amount']} {d['unit']} → bill usage {qty} "
                         f"{sorted({ln['unit'] for ln in use})}")
                svc = [s for s in payload.get("services") or [] if s.get("code") == d["service"]]
                acc.mark("P3.effect", bool(svc) and all(s.get("estimated") for s in svc),
                         f"bill payload does not mark {d['service']} estimated")
            elif choice in HOLDING:
                acc.mark("P3.effect", not mine, f"{case}={choice} but a bill exists ({len(mine)})")
            elif (case, choice) in WAIVING:
                acc.mark("P3.effect", not mine, f"waived but billed ({len(mine)})")
            elif choice == "add_to_bill":
                inst = payload.get("payment_plan_instalment") or {}
                acc.mark("P3.effect", bill is not None and inst.get("amount") is not None,
                         "Add to bill: no instalment on the bill")
            elif choice == "skip" and case == "plan_instalment_due":
                acc.mark("P3.effect", bill is not None and not payload.get("payment_plan_instalment"),
                         "Skip: the instalment is on the bill")
            elif choice == "apply_this_bill":
                paid = sum((Decimal(str(p["amount"])) for p in late_pay.get(acc.id, [])), Decimal(0))
                credited = Decimal(str((payload.get("balance_forward") or {}).get("payments_credits") or 0))
                on_lines = [ln for ln in blines if ln["kind"] in ("payment", "credit")]
                if stage == "sent":
                    acc.mark("P3.effect", bill is not None and credited == paid and not on_lines,
                             f"Apply to this bill: {d2(paid)} paid after the cut-off "
                             f"({', '.join(p['status'] for p in late_pay.get(acc.id, [])) or 'none'}), "
                             f"bill counts {d2(credited)} as payments received, {len(on_lines)} payment line(s)")
                else:
                    acc.mark("P3.effect", bill is not None, "Apply to this bill: not drafted")
            else:
                if acc.check_status != "blocked":
                    acc.mark("P3.effect", bool(mine) or bool(breaks.get(acc.id)),
                             f"{case}={choice} bills the account but it has no bill")
        if not cur_dec:
            acc.mark("P3.effect", None)

        # ── (3) the records for the next billing ─────────────────────────
        for d in cur_dec:
            if d["choice"] == "estimate":
                est = [e for v in estimates.values() for e in v
                       if bill is not None and str(e["invoice_id"]) == str(bill["id"])]
                if stage == "sent":
                    acc.mark("P3.next", len(est) == 1
                             and est[0]["source"] == "estimated"
                             and Decimal(str(est[0]["consumption"])) == Decimal(str(d["amount"]))
                             and (est[0]["unit"] or "") == (d["unit"] or "")
                             and est[0]["read_at"].date() == run["period_end"]
                             and est[0]["superseded_by_id"] is None,
                             f"Meter Reads estimate for the bill: "
                             + (", ".join(f"{e['asset_no']} {e['read_at']:%Y-%m-%d} {e['consumption']} {e['unit']} {e['source']}" for e in est) or "none"))
                else:
                    acc.mark("P3.next", None)
            if d["choice"] in HOLDING:
                e = excl.get(acc.id)
                acc.mark("P3.next", e is not None and bool(e["reason_code"]),
                         f"{d['case']}={d['choice']}: no Pending-billing row")
            if (d["case"], d["choice"]) in WAIVING and stage == "sent":
                acc.mark("P3.next", acc.id in waived_audit and acc.id not in excl,
                         f"waive: logged={acc.id in waived_audit}, queued={acc.id in excl} (want logged, not queued)")
            if d["case"] == "plan_instalment_due" and d["choice"] == "skip" and stage == "sent":
                ext = plan_ext.get(acc.id, [])
                inst = plan_inst.get(acc.id)
                acc.mark("P3.next", len(ext) == 1 and inst is not None and inst["n"] == inst["installment_count"],
                         f"Skip: plan extended {len(ext)} time(s); instalments "
                         f"{inst and inst['n']} of {inst and inst['installment_count']}, last due {inst and inst['last_due']}")
        if undecided:
            e = excl.get(acc.id)
            acc.mark("P3.next", stage != "sent" or e is not None,
                     "waiting on a decision after Send and not in Pending billing")
        if acc.check_status == "blocked":
            acc.mark("P3.next", stage != "sent" or acc.id in excl,
                     "blocked after Send and not in Pending billing")
        acc.verdict.setdefault("P3.next", NA)

        # ── (4) drafts ───────────────────────────────────────────────────
        if stage == "signoff":
            acc.mark("P4.drafts", len(drafts) == (1 if should_bill else 0)
                     or (not drafts and acc.id in breaks),
                     f"{len(drafts)} draft(s); should bill: {should_bill} (check {acc.check_status}, answers {acc.facts['answers']})")
        elif stage == "sent":
            acc.mark("P4.drafts", not drafts and len(issued) <= 1,
                     f"after Send: {len(drafts)} draft(s) left, {len(issued)} issued")
        else:
            acc.mark("P4.drafts", None)
        acc.mark("P4.drafts", len(mine) <= 1, f"{len(mine)} bills in one run")

        # ── (5) where it ends ────────────────────────────────────────────
        places = []
        if issued:
            places.append("issued")
        # DEF-BIL-8745 — a send break closed `issued` is a bill a later pass
        # sent (DEF-BIL-8581); it is resolved, exactly as `drafted` is.
        if acc.id in breaks and breaks[acc.id]["resolution"] not in ("drafted", "issued"):
            places.append("failed")
        # Not in this run: queued, waived (listed, never queued), nothing to bill, left out.
        if not issued and (acc.id in excl or waived or acc.check_status in ("quiet", "left_out", "blocked")
                           or (stage == "sent" and undecided)):
            places.append("not in this run")
        acc.end = "+".join(places) or ("draft" if drafts else "nowhere")
        if stage == "sent":
            ok = len(places) == 1
            if ok and places == ["failed"]:
                ok = bool(breaks[acc.id]["reason"])
            acc.mark("A3.end", ok, f"ends in {acc.end}")
            acc.mark("A3.end", should_bill == bool(issued) or acc.id in breaks,
                     f"should bill {should_bill} but issued {bool(issued)}")
        else:
            acc.mark("A3.end", None)

        # ── (6) Send ─────────────────────────────────────────────────────
        if stage != "sent" or not issued:
            for k in ("S6.issued", "S6.draft", "S6.ledger", "S5.delivery", "S5.reads", "S6.audit", "S6.once"):
                acc.mark(k, None)
        else:
            inv = issued[0]
            iid = str(inv["id"])
            acc.mark("S6.issued", bool(inv["invoice_no"]) and inv["issued_at"] is not None
                     and inv["invoice_no"] not in dup_numbers,
                     f"status {inv['status']} no {inv['invoice_no']} issued_at {inv['issued_at']}")
            il = lines.get(iid, [])
            s_lines = sum((Decimal(str(ln["amount"])) for ln in il), Decimal(0))
            tot = Decimal(str(inv["total"]))
            pl = inv["bill_payload"] or {}
            pl_lines = sorted(d2(x.get("amount")) for x in pl.get("lines") or [])
            acc.mark("S6.draft", (s_lines + Decimal(str(inv["tax_total"]))).quantize(CENT) == tot.quantize(CENT)
                     and pl_lines == sorted(d2(ln["amount"]) for ln in il)
                     and d2(pl.get("total")) == d2(tot),
                     f"lines {d2(s_lines)} + tax {d2(inv['tax_total'])} vs total {d2(tot)}; payload {pl_lines}")
            wd = walk_drafts.get(acc.no)
            if wd is not None:
                acc.mark("S6.draft", d2(wd["total"]) == d2(tot), f"issued {d2(tot)} vs Sign off draft {d2(wd['total'])}")
            js = journals.get(iid, [])
            acc.mark("S6.ledger", len(js) == 1 and js[0]["status"] == "posted"
                     and d2(js[0]["debits"]) == d2(js[0]["credits"])
                     and d2(js[0]["ar_net"]) == d2(tot) and js[0]["ar_on_account"],
                     "journal " + (", ".join(f"{j['status']} Dr {d2(j['debits'])} Cr {d2(j['credits'])} AR {d2(j['ar_net'])}" for j in js) or "none"))
            chans = [m["channel"] for m in delivery.get(iid, [])]
            want = {"pdf_print"} | ({"email"} if acc.row["paperless"] else set()) | ({"sms"} if acc.row["sms_reminders"] else set())
            acc.mark("S5.delivery", want <= set(chans) and all(m["status"] in ("queued", "sent", "delivered") for m in delivery.get(iid, [])),
                     f"queued {sorted(chans)}; election wants {sorted(want)}")
            used = [s.get("read_id") for s in (pl.get("services") or []) if s.get("read_id")]
            bad = [r for r in (reads.get(str(x)) for x in used) if r is None or r["lifecycle"] != "billed"]
            est_here = est_by_invoice.get(iid, [])
            bad += [e for e in est_here if e["lifecycle"] != "billed"]
            acc.mark("S5.reads", not bad, f"{len(bad)} reading(s) not billed-locked: "
                     + ", ".join(f"{(r or {}).get('id')} {(r or {}).get('lifecycle')}" for r in bad))
            au = inv_audit.get(iid, {})
            acc.mark("S6.audit", au.get("invoice.issued") == 1, f"invoice.issued audit rows: {au.get('invoice.issued', 0)}")
            per_chan = defaultdict(int)
            for m in delivery.get(iid, []):
                per_chan[(m["channel"], m["copy_no"])] += 1
            acc.mark("S6.once", len(js) <= 1 and all(n == 1 for n in per_chan.values()) and au.get("invoice.issued", 0) <= 1,
                     f"journals {len(js)}, deliveries {dict(per_chan)}, issue audits {au.get('invoice.issued', 0)}")

        # ── (5) locked after Send ────────────────────────────────────────
        if stage == "sent":
            late_dec = [d for d in all_decisions if str(d["account_id"]) == acc.id and d["created_at"] > sent_at]
            late_chk = acc.row["checked_at"] is not None and acc.row["checked_at"] > sent_at
            acc.mark("S5.locked", not late_dec and not late_chk and not acc.row["stale"],
                     f"after Send: {len(late_dec)} decision(s), check re-written {late_chk}, stale {acc.row['stale']}")
        else:
            acc.mark("S5.locked", None)

        for k in CHECKS:
            acc.verdict.setdefault(k, NA)

    # ── run-level checks ─────────────────────────────────────────────────
    run_checks: dict[str, tuple[str, str]] = {}

    def run_mark(key: str, ok: bool | None, detail: str) -> None:
        run_checks[key] = (NA if ok is None else (PASS if ok else FAIL), detail)

    billed = [i for i in invoices if i["status"] == "issued"]
    drafts_all = [i for i in invoices if i["status"] == "draft"]
    if stage == "sent":
        rel = releases
        run_mark("release", len([r for r in rel if r["released_at"]]) == 1
                 and all(r["compliance_confirmed"] and r["email_mandate_confirmed"] and r["sms_mandate_confirmed"]
                         and r["autopay_mandate_confirmed"] and r["confirmed_by"] for r in rel),
                 f"{len(rel)} release row(s); confirmed by {', '.join(str(r['confirmed_by']) for r in rel)}; "
                 f"authorised {', '.join(str(r['bill_count']) + ' bills ' + d2(r['total_amount']) for r in rel)}")
        auth = next((r for r in rel if r["released_at"]), None)
        run_mark("release=issued", auth is not None and auth["bill_count"] == len(billed)
                 and d2(auth["total_amount"]) == d2(sum(Decimal(str(i["total"])) for i in billed)),
                 f"authorised {auth and auth['bill_count']} / {d2(auth and auth['total_amount'])}; "
                 f"issued {len(billed)} / {d2(sum((Decimal(str(i['total'])) for i in billed), Decimal(0)))}")
        rel_audit = [a for a in run_audit if a["action"] == "bill_run.released"]
        run_mark("release audited once", len(rel_audit) == 1, f"bill_run.released rows: {len(rel_audit)}")
        run_mark("run status", run["status"] == "issued", f"run status {run['status']}")
        run_mark("no draft left", not drafts_all, f"{len(drafts_all)} draft(s) left in the run")
    # DEF-BIL-8745 — a record a killed worker left failed (or one that failed
    # and was sent again) is SUPERSEDED when a later job of the same kind and
    # scope key succeeded: the work it held was finished. Counted and printed,
    # never silently dropped.
    done_scopes = {(j["kind"], j["scope_key"]) for j in jobs if j["status"] == "succeeded"}
    superseded = [j for j in jobs if j["status"] == "failed" and (j["kind"], j["scope_key"]) in done_scopes]
    open_jobs = [j for j in jobs if j["status"] not in ("succeeded", "done", "completed") and j not in superseded]
    states: dict[str, int] = {}
    for j in jobs:
        key = f"{j['kind']} {j['status']}"
        states[key] = states.get(key, 0) + 1
    run_mark("jobs", not open_jobs if stage == "sent" else None,
             f"{len(jobs)} job(s): " + ", ".join(f"{k} x{n}" for k, n in sorted(states.items()))
             + f"; {len(superseded)} failed record(s) superseded by a later success under the same scope")
    for acc in accounts.values():
        if stage == "sent":
            acc.mark("S5.jobs", not open_jobs, "run has a job left " + ", ".join(j["status"] for j in open_jobs))
            acc.verdict["S5.jobs"] = PASS if not open_jobs else FAIL

    # The screen = the database (the walk's recorded screen figures).
    if walk is not None and not only:
        screen = []
        so = walk.get("signOff") or {}
        billed_label = next((k for k in so if k.strip() == "Billed"), None)
        issued_total = sum((Decimal(str(i["total"])) for i in billed), Decimal(0))
        draft_total = sum((Decimal(str(v["total"])) for v in walk_drafts.values()), Decimal(0))
        if billed_label is not None:
            screen.append(("Sign off 'Billed'", so[billed_label], len(walk_drafts)))
        if walk.get("price") is not None:
            screen.append(("Check 'Price N accounts'", walk["price"], len(walk_drafts)))
        if walk.get("signOffTotal"):
            screen.append(("Sign off total", d2(Decimal(walk["signOffTotal"].replace("$", "").replace(",", ""))), d2(draft_total)))
        if walk.get("sendButton") is not None:
            screen.append(("'Send N bills'", walk["sendButton"], len(billed) if stage == "sent" else len(drafts_all)))
        if walk.get("sent"):
            screen.append(("Sent card count", walk["sent"]["sent"], len(billed)))
            screen.append(("Sent card total", d2(Decimal(walk["sent"]["total"].replace("$", "").replace(",", ""))), d2(issued_total)))
        if walk.get("scope"):
            screen.append(("Scope accounts", walk["scope"].get("accounts"), len(checked)))
        if walk.get("check"):
            c = walk["check"]
            screen.append(("Check tiles R+B+D", c.get("ready", 0) + c.get("blocked", 0) + c.get("decision", 0), len(checked)))
        if walk.get("notInRun") is not None and stage == "sent":
            listed = {r["account"] for r in walk["notInRun"] if r["account"] != "—"}
            db_out = {a.no for a in accounts.values() if a.end == "not in this run"}
            screen.append(("Not in this run (accounts)", sorted(listed), sorted(db_out)))
        bad = [s for s in screen if str(s[1]) != str(s[2])]
        run_mark("screen = database", not bad if screen else None,
                 "; ".join(f"{n}: screen {a} / db {b}" for n, a, b in screen))
        for acc in accounts.values():
            acc.verdict["P4.screen"] = run_checks["screen = database"][0]
            wd = walk_drafts.get(acc.no)
            mine = inv_by_acct.get(acc.id, [])
            if wd is not None and mine:
                if d2(wd["total"]) != d2(mine[0]["total"]):
                    acc.verdict["P4.screen"] = FAIL
                    acc.notes.append(f"[P4.screen] Sign off showed {d2(wd['total'])}, database {d2(mine[0]['total'])}")
            elif wd is not None and not mine:
                acc.verdict["P4.screen"] = FAIL
                acc.notes.append("[P4.screen] Sign off listed a draft the database does not hold")

    # ── month two ─────────────────────────────────────────────────────────
    if next_run:
        nxt = q(cur, SQL_RUN, run=next_run)
        if len(nxt) != 1:
            sys.exit(f"next run {next_run!r}: {len(nxt)} rows")
        nxt = nxt[0]
        bills = q(cur, SQL_ACCOUNT_BILLS, accounts=ids)
        blines = defaultdict(list)
        for ln in q(cur, SQL_ACCOUNT_LINES, invoices=[b["id"] for b in bills]):
            blines[str(ln["invoice_id"])].append(ln)
        by_acct = defaultdict(list)
        for b in bills:
            by_acct[str(b["account_id"])].append(b)
        for acc in accounts.values():
            mine = by_acct.get(acc.id, [])
            two = [b for b in mine if b["bill_run_id"] == nxt["id"]]
            one = [b for b in mine if b["bill_run_id"] == rid]
            if not two:
                acc.verdict["M2.next"] = acc.verdict["M2.base"] = acc.verdict["M2.usage"] = NA
                acc.facts["month2"] = "—"
                continue
            b2 = two[0]
            acc.facts["month2"] = f"{b2['invoice_no']} {b2['period_start']:%m/%d}–{b2['period_end']:%m/%d} {d2(b2['total'])}"
            earlier = [b for b in mine if b["period_end"] < b2["period_start"] or b["id"] != b2["id"] and b["period_start"] < b2["period_start"]]
            earlier = [b for b in earlier if b["id"] != b2["id"]]
            last = max(earlier, key=lambda b: b["period_end"], default=None)
            # A WAIVED month is not billed and not carried (PO 2026-09-30, fixed-charge
            # case 2): month two then starts the day after month ONE's period.
            waived_m1 = any((d["case"], d["choice"]) in WAIVING for d in current.get(acc.id, []))
            if waived_m1 and (last is None or last["period_end"] < run["period_end"]):
                want_start = run["period_end"] + timedelta(days=1)
            elif last is not None:
                want_start = last["period_end"] + timedelta(days=1)
            else:
                want_start = b2["period_start"]
            acc.mark("M2.next", b2["period_start"] == want_start,
                     f"month two starts {b2['period_start']}, want {want_start}: last bill ends "
                     f"{last and last['period_end']} ({last and last['invoice_no']})"
                     + (" · waived in month one" if waived_m1 else ""))
            overlaps = [b for b in earlier if not (b["period_end"] < b2["period_start"] or b["period_start"] > b2["period_end"])]
            acc.mark("M2.next", not overlaps, "overlaps " + ", ".join(f"{b['invoice_no']} {b['period_start']}–{b['period_end']}" for b in overlaps))
            per_svc = defaultdict(int)
            for ln in blines.get(str(b2["id"]), []):
                if ln["kind"] == "base":
                    per_svc[ln["service"]] += 1
            acc.mark("M2.base", all(n == 1 for n in per_svc.values()) and not overlaps,
                     f"base lines per service {dict(per_svc)}")
            # Usage over month one + month two = the actual meter advance.
            first = one[0] if one else b2
            start = first["period_start"]
            end = b2["period_end"]
            # Every issued bill of the account inside the span — a one-time bill
            # sent between the runs is part of what the meter advance paid for.
            span = [b for b in mine if b["period_start"] >= start and b["period_end"] <= end]
            assets: dict[str, str] = {}
            for b in span:
                for s in (b["bill_payload"] or {}).get("services") or []:
                    if s.get("read_id"):
                        r = q(cur, SQL_READS_BY_ID, ids=[s["read_id"]])
                        if r:
                            assets[s.get("code")] = r[0]["asset_id"]
            if not assets:
                acc.mark("M2.usage", None)
            for svc, asset in assets.items():
                before = q(cur, SQL_ACTUAL_ON_OR_BEFORE, asset=asset, day=start - timedelta(days=1))
                after = q(cur, SQL_ACTUAL_ON_OR_BEFORE, asset=asset, day=end)
                billed_qty = sum(
                    (Decimal(str(ln["quantity"])) for b in span for ln in blines.get(str(b["id"]), [])
                     if ln["kind"] == "usage" and ln["service"] == svc and ln["quantity"] is not None),
                    Decimal(0),
                )
                if not before or not after or after[0]["read_at"].date() < b2["period_end"]:
                    acc.mark("M2.usage", None)
                    continue
                advance = Decimal(str(after[0]["current_value"])) - Decimal(str(before[0]["current_value"]))
                acc.mark("M2.usage", billed_qty == advance,
                         f"{svc}: billed {billed_qty} over {start}–{end}; meter {before[0]['current_value']} "
                         f"({before[0]['read_at']:%m/%d}) → {after[0]['current_value']} ({after[0]['read_at']:%m/%d}) = {advance}")
            acc.verdict.setdefault("M2.usage", NA)

    # ── E17: every record the one account touches, as the database holds it ──
    records = None
    if only:
        acc = next(iter(accounts.values()))
        mine = inv_by_acct.get(acc.id, [])
        inv_ids = [i["id"] for i in mine]
        est = [e for i in mine for e in est_by_invoice.get(str(i["id"]), [])]
        plan = plan_inst.get(acc.id)
        records = {
            "check": {"status": acc.check_status, "stale": acc.row["stale"], "checked_at": acc.row["checked_at"]},
            "findings": [
                {"code": f["code"], "severity": f["severity"], "service": f["service_code"], "params": f["params"]}
                for f in findings.get(acc.id, [])
            ],
            "decisions": [
                {"case": d["case"], "choice": d["choice"], "amount": d["amount"], "unit": d["unit"],
                 "service": d["service"], "reason": d["reason"], "decided_by": d["decided_by"],
                 "at": d["created_at"], "current": d["superseded_by_id"] is None}
                for d in all_decisions if str(d["account_id"]) == acc.id
            ],
            "pending_billing": excl.get(acc.id),
            "break": breaks.get(acc.id),
            "bills": [
                {"id": i["id"], "invoice_no": i["invoice_no"], "status": i["status"],
                 "period": f"{i['period_start']}..{i['period_end']}", "subtotal": i["subtotal"],
                 "tax": i["tax_total"], "total": i["total"], "issued_at": i["issued_at"],
                 "services": [
                     {"code": s.get("code"), "estimated": s.get("estimated"), "read_id": s.get("read_id")}
                     for s in ((i["bill_payload"] or {}).get("services") or [])
                 ],
                 "payments_received": ((i["bill_payload"] or {}).get("balance_forward") or {}).get("payments_credits"),
                 "plan_instalment": (i["bill_payload"] or {}).get("payment_plan_instalment"),
                 "lines": [
                     {"kind": ln["kind"], "service": ln["service"], "quantity": ln["quantity"], "unit": ln["unit"],
                      "unit_price": ln["unit_price"], "amount": ln["amount"],
                      "period": f"{ln['period_start']}..{ln['period_end']}"}
                     for ln in lines.get(str(i["id"]), [])
                 ],
                 "journals": journals.get(str(i["id"]), []),
                 "deliveries": delivery.get(str(i["id"]), []),
                 "audit": inv_audit.get(str(i["id"]), {})}
                for i in mine
            ],
            "estimates_written": est,
            "meter_reads": q(cur, SQL_ACCOUNT_READS, account=acc.id),
            "payment_plan": plan,
            "plan_extended": plan_ext.get(acc.id, []),
            "late_payments": late_pay.get(acc.id, []),
            "audit": q(cur, SQL_ACCOUNT_AUDIT, entities=inv_ids + [e["id"] for e in est], run=rid, account=acc.id),
            "jobs": jobs,
        }

    # ── report ────────────────────────────────────────────────────────────
    per = {k: {PASS: 0, FAIL: 0, NA: 0} for k in CHECKS}
    for acc in accounts.values():
        for k in CHECKS:
            per[k][acc.verdict.get(k, NA)] += 1
    ends = defaultdict(int)
    for acc in accounts.values():
        ends[acc.end] += 1
    return {
        "run": {"run_no": run["run_no"], "id": str(rid), "status": run["status"], "stage": stage,
                "period": f"{run['period_start']}..{run['period_end']}", "next_run": next_run},
        "accounts": [
            {"account_no": a.no, "end": a.end, "facts": a.facts, "verdict": a.verdict, "fail": a.notes}
            for a in accounts.values()
        ],
        "ends": dict(ends),
        "checks": per,
        "run_checks": {k: {"verdict": v, "detail": d} for k, (v, d) in run_checks.items()},
        "records": records,
        "counts": {
            "accounts": len(accounts), "decisions_current": sum(len(v) for v in current.values()),
            "invoices": len(invoices), "issued": len(billed), "drafts": len(drafts_all),
            "exclusions": len(excl), "breaks": len(breaks), "releases": len(releases),
            "issue_audits": sum(v.get("invoice.issued", 0) for v in inv_audit.values()),
            "journals": sum(len(v) for v in journals.values()),
            "deliveries": sum(len(v) for v in delivery.values()),
            "estimates": sum(len(v) for v in estimates.values()),
        },
        "ok": all(v[FAIL] == 0 for v in per.values()) and all(v != FAIL for v, _ in run_checks.values()),
    }


def print_report(out: dict, limit: int) -> None:
    r = out["run"]
    print(f"\nRun {r['run_no']} ({r['id']}) · {r['period']} · status {r['status']} · stage {r['stage'].upper()}"
          + (f" · month two {r['next_run']}" if r["next_run"] else ""))
    keys = [k for k in CHECKS if any(a["verdict"].get(k) != NA for a in out["accounts"])]
    short = {k: k.split(".")[1][:7] for k in keys}
    head = f"{'account':<14} {'check':<8} {'end':<16} {'bill':<15} {'total':>9}  " + " ".join(f"{short[k]:<7}" for k in keys)
    print(head)
    print("-" * len(head))
    shown = 0
    for a in out["accounts"]:
        interesting = a["fail"] or len(out["accounts"]) <= limit
        if not interesting and shown >= limit:
            continue
        shown += 1
        f = a["facts"]
        print(f"{a['account_no']:<14} {f['check']:<8} {a['end']:<16} {f['bill']:<15} {f['total']:>9}  "
              + " ".join(f"{a['verdict'].get(k, NA):<7}" for k in keys))
    if shown < len(out["accounts"]):
        print(f"… {len(out['accounts']) - shown} more accounts, every one PASS on every applicable check")
    print("\nEnd states: " + " · ".join(f"{k} {v}" for k, v in sorted(out["ends"].items())))
    print("\nCheck (PO step)                                                                        PASS  FAIL   n/a")
    for k, (step, desc) in CHECKS.items():
        c = out["checks"][k]
        if c[PASS] + c[FAIL] == 0:
            continue
        print(f"  {k:<11} ({step:>2}) {desc[:66]:<66} {c[PASS]:>5} {c[FAIL]:>5} {c[NA]:>5}")
    if out["run_checks"]:
        print("\nRun-level:")
        for k, v in out["run_checks"].items():
            print(f"  {v['verdict']:<4} {k:<22} {v['detail']}")
    print("\nCounts: " + " · ".join(f"{k} {v}" for k, v in out["counts"].items()))
    fails = [(a["account_no"], n) for a in out["accounts"] for n in a["fail"]]
    if fails:
        print(f"\nFAILURES ({len(fails)}):")
        seen = defaultdict(int)
        for acc, n in fails:
            key = n.split("]")[0]
            seen[key] += 1
            if seen[key] <= 12:
                print(f"  {acc}: {n}")
        for key, n in seen.items():
            if n > 12:
                print(f"  … {key}] {n - 12} more like it")
    print("\nRESULT:", "PASS" if out["ok"] else "FAIL")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", help="run number (RUN-0002) or run id")
    ap.add_argument("--walk", help="the walk's state file: its decisions and the screen figures it read")
    ap.add_argument("--clerk", help="who the walk signed in as (full name); checked against every decision")
    ap.add_argument("--next-run", help="month two's run on the same accounts")
    ap.add_argument("--account", help="one account only (E17's single-account trace)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    ap.add_argument("--limit", type=int, default=40, help="rows of the per-account table when all pass")
    args = ap.parse_args()
    walk = None
    if args.walk:
        walk = json.loads(Path(args.walk).read_text())
    if args.clerk:
        walk = walk or {}
        walk["clerk"] = args.clerk
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        conn.read_only = True
        out = verify(cur, args.run, walk=walk, next_run=args.next_run, only=args.account)
        conn.rollback()
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print_report(out, args.limit)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
