"""DEF-BIL-10531 — `bill_links` on PostgreSQL: RLS is FORCED with the NULLIF policy
(hard rule 1), and a refused mint does not poison the issue's transaction (law 14).

The functional suite (`test_def_bil_10531_bill_link.py`) is also run under
`--ds=config.settings.pgtest`; this file adds what only PostgreSQL can show.
"""

from __future__ import annotations

import pytest
from django.db import connection

from tests.isolation_helpers import RlsProbe, requires_postgres, rls_probe_role  # noqa: F401
from tests.test_otb_a_one_time_api_contract import _the_unit_bills_on_a_cycle  # noqa: F401
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_pg_bill_links_has_forced_rls_and_the_nullif_policy():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["bill_links"],
        )
        enabled, forced = cursor.fetchone()
        cursor.execute(
            "SELECT qual, with_check FROM pg_policies WHERE tablename = %s", ["bill_links"]
        )
        policies = cursor.fetchall()
    assert enabled and forced
    assert len(policies) == 1
    qual, check = policies[0]
    for clause in (qual, check):
        assert "NULLIF" in clause and "app.tenant_id" in clause


def test_pg_a_refused_mint_leaves_the_issue_transaction_usable(
    brazos, dana, monkeypatch, settings, tmp_path
):
    """A duplicate digest is refused INSIDE the savepoint; the outer transaction
    — the bill's issue — still answers queries afterwards. Without the nested
    `atomic()` this raises `InFailedSqlTransaction` on the next statement."""
    from apps.billing import bill_links
    from apps.billing import models as billing_models
    from apps.billing.bill_link_models import BillLink
    from core import link_tokens
    from tests.test_def_bil_10531_bill_link import _issued
    from tests.test_us_met_helpers import tenant_ctx

    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    invoice, _email = _issued(brazos, dana)
    with tenant_ctx(brazos):
        existing = BillLink.objects.get(invoice_id=invoice.pk)
        monkeypatch.setattr(link_tokens, "mint", lambda: "same-token")
        monkeypatch.setattr(link_tokens, "digest", lambda token: existing.token_hash)
        tokens, problems = bill_links.mint(invoice)
        assert tokens == {"bill_link": None, "link_expires_on": None}
        assert [p["code"] for p in problems] == [bill_links.NOT_MADE]
        # The transaction is still alive.
        assert billing_models.Invoice.objects.filter(pk=invoice.pk).exists()
        assert BillLink.objects.filter(invoice_id=invoice.pk).count() == 1


def test_pg_another_tenant_cannot_see_the_row_even_by_digest(
    brazos, dana, lonestar, settings, tmp_path, rls_probe_role
):
    """As a NON-superuser (a superuser bypasses RLS and would prove nothing)."""
    from apps.billing.bill_link_models import BillLink
    from tests.test_def_bil_10531_bill_link import _issued
    from tests.test_us_met_helpers import tenant_ctx

    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    invoice, _email = _issued(brazos, dana)
    with tenant_ctx(brazos):
        digest = BillLink.objects.get(invoice_id=invoice.pk).token_hash
    probe = RlsProbe()
    # No tenant filter in the query: only the policy stands in the way.
    with probe.under(brazos):
        assert probe.count("bill_links", "token_hash = %s", [digest]) == 1
    with probe.under(lonestar):
        assert probe.count("bill_links", "token_hash = %s", [digest]) == 0
