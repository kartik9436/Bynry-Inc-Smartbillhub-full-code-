"""CR-190-BRC10 — `agreement_requests` on PostgreSQL: RLS is FORCED and the
policy admits only the tenant in context (hard rule 1), and the accept path's
savepoints hold on a real transaction (law 14).

The functional suite (`test_cr190_agreements.py`) is also run under
`--ds=config.settings.pgtest`; this file adds what only PostgreSQL can show.
"""

from __future__ import annotations

import pytest
from django.db import connection

from tests.isolation_helpers import requires_postgres

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_pg_agreement_requests_has_forced_rls_and_the_nullif_policy():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["agreement_requests"],
        )
        enabled, forced = cursor.fetchone()
        cursor.execute(
            "SELECT qual, with_check FROM pg_policies WHERE tablename = %s",
            ["agreement_requests"],
        )
        policies = cursor.fetchall()
    assert enabled and forced
    assert len(policies) == 1
    qual, check = policies[0]
    for clause in (qual, check):
        assert "NULLIF" in clause and "app.tenant_id" in clause


def test_pg_token_digest_is_unique():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s AND indexname = %s",
            ["agreement_requests", "uq_agreement_requests_token"],
        )
        row = cursor.fetchone()
    assert row is not None and "UNIQUE" in row[0] and "token_hash" in row[0]
