"""customers 0018 — RLS ENABLE + FORCE on CR-031's five service-request tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM to each table. Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without human sign-off.

WHY EACH OF THE FIVE NEEDS IT
─────────────────────────────
`service_requests` is the most PII-dense table this module has ever added: an
applicant's name, email, phone, home address as they wrote it, their language,
a co-applicant's contact details, and — through `matched_customer_id` — the link
to every account they have ever held. It is also the table a competitor would
most want: the whole pipeline of who is about to take service, and where.

`service_request_documents` points at stored copies of a photo ID and a proof of
address. `service_request_fees` is money (4 dp, CHAR(3)). `service_request_events`
is the internal timeline, badged on screen **`Internal · never shown to the
customer`** — staff opinions about an applicant. `service_request_services` says
which utilities a named person is asking for at a named address.

The B2 §3 template, deny-by-default: with `app.tenant_id` unset the `::uuid`
cast of '' fails and NO row is visible. The G5 isolation suite proves it under a
NON-SUPERUSER probe role, because the app connects as a superuser and superusers
bypass RLS unconditionally — which makes any assertion made on the app's own
connection vacuous (`tests/isolation_helpers.py`).

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLES = (
    "service_requests",
    "service_request_services",
    "service_request_documents",
    "service_request_fees",
    "service_request_events",
)


def _policy(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


def _reverse(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


POLICY = "\n".join(_policy(table) for table in TABLES)
REVERSE = "\n".join(_reverse(table) for table in reversed(TABLES))


class Migration(migrations.Migration):
    dependencies = [("customers", "0017_cr031_service_requests")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
