# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8708 — Send issued 1.9 bills a second at 40,000 accounts
#           because every invoice-line update scanned the whole partition
# Story:    US-BIL-005 (issue) · US-BIL-040 (bulk run · Send)
# Rules:    CLAUDE.md hard rule 1 (the tenant predicate is RLS's, not the
#           statement's) · hard-won laws 7 and 14 (proved red, on PostgreSQL)
# Measured: 04-docs/05-modules/07-billing/19-check-cost-measured.md §10.5, §11
# ───────────────────────────────────────────────────────
"""An invoice line is updated BY ITS ID, and that statement must use an index.

**WHAT WAS WRONG, MEASURED.** Issue stamps each line's GL account with the ORM's
`line.save(update_fields=[...])`, which PostgreSQL receives as
`UPDATE invoice_lines SET … WHERE invoice_lines.id = %s`. The partitioned
`invoice_lines` carries primary key `(tenant_id, created_at, id)` — the
partition key must be in it — and no index led with `id`, so each update
walked the partition: 300,695 rows removed by filter, 68 ms, about 7.5 lines a
bill, and Send ran at 1.9 bills a second (S3, `sbh_s14_40k`).

**WHY THE CASE TAKES THE ORM'S OWN STATEMENT.** The index that fixes it has to
serve the query the code actually sends, so the case captures the UPDATE a
real `save(update_fields=…)` emits and EXPLAINs exactly that — not a
hand-written query that might differ by a predicate.

**WHY `enable_seqscan = off`.** A few rows in a test database are cheaper to
scan than to look up, so the planner would choose a scan with or without the
index and the case could not tell the two apart (law 7: a check that cannot
fail). With scans priced out the planner still has a way to cheat, and the
first version of this case was fooled by it: it walks the PRIMARY KEY
`(tenant_id, created_at, id)` with `id` as its index condition. That reads as
an index scan on `id` and is a walk of the whole index, because `id` is its
THIRD column (law 7: proved red first, and it was a false green). So every
scan over an `invoice_lines` partition must use an index whose FIRST column is
`id`.

POSTGRESQL ONLY: SQLite has no partitions and keeps `id` as its primary key.
"""

from __future__ import annotations

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import models as billing_models

from tests.isolation_helpers import requires_postgres
from tests.test_def_bil_5352_run_status_machine import a_releasable_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

def _scan_nodes(plan: dict, table_prefix: str) -> list[dict]:
    found: list[dict] = []
    stack = [plan]
    while stack:
        node = stack.pop()
        if str(node.get("Relation Name", "")).startswith(table_prefix):
            found.append(node)
        stack.extend(node.get("Plans", []))
    return found


@requires_postgres
def test_8708_this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


@requires_postgres
def test_8708_an_invoice_line_update_by_id_uses_an_index_on_id(brazos, dana):
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=1, key="2026-06|8708")
        line = billing_models.InvoiceLine.objects.filter(invoice__bill_run=run).first()
        assert line is not None
        with CaptureQueriesContext(connection) as captured:
            line.save(update_fields=["gl_account_id", "updated_at"])
        updates = [q["sql"] for q in captured.captured_queries if q["sql"].startswith("UPDATE")]
        assert len(updates) == 1, updates
        statement = updates[0]
        assert '"invoice_lines"."id" = ' in statement, statement
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute(f"EXPLAIN (FORMAT JSON) {statement}")
            plan = cursor.fetchone()[0]
    plan = plan if isinstance(plan, list) else json.loads(plan)
    nodes = [
        node
        for node in _scan_nodes(plan[0]["Plan"], "invoice_lines")
        if node.get("Node Type") != "ModifyTable"
    ]
    assert nodes, json.dumps(plan, indent=1)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, a.attname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0] "
            "WHERE c.relname LIKE 'invoice_lines%%'"
        )
        leading = dict(cursor.fetchall())
    shown = [
        (node.get("Node Type"), node.get("Index Name"), leading.get(node.get("Index Name")))
        for node in nodes
    ]
    print(f"\nPROOF 8708 the plan over each partition (type, index, its first column): {shown}")
    for node_type, index, first_column in shown:
        assert node_type in ("Index Scan", "Index Only Scan", "Bitmap Heap Scan"), shown
        if node_type == "Bitmap Heap Scan":
            continue  # its child Bitmap Index Scan is checked below
        assert first_column == "id", (
            f"an invoice-line update by id walked {index}, whose first column is "
            f"{first_column}: {shown}"
        )
    for child in [n for node in nodes for n in node.get("Plans", [])]:
        assert leading.get(child.get("Index Name")) == "id", shown
