# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — a customer attaches documents to a portal
#           new-service application (PO 2026-10-01: "save those document to
#           server for that Utility").
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · BR-TEN-003 · hard-won law 14
#           (the RLS half and the savepoints are PostgreSQL's; SQLite proves
#           nothing about either)
# Tests:    this file
# Impacts:  apps/portal/migrations/0011_rls_application_documents.py
# ───────────────────────────────────────────────────────
"""CR-158 on PostgreSQL — what SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://<user>:<pw>@127.0.0.1:55433/<db> \\
        pytest tests/test_cr158_portal_application_documents_pg.py

Every case carries `requires_postgres` and SKIPS on SQLite rather than passing
vacuously.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.portal import models
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr158_portal_application_documents import (  # noqa: F401
    PDF,
    PNG,
    _content,
    _send,
    _upload,
    docs_dir,
    ready,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from core.tenancy import tenant_context


@requires_postgres
@pytest.mark.django_db
def test_no_context_sees_no_held_document(ready, rls):
    _upload(ready, PDF, "tenancy-agreement.pdf")
    assert_denied_without_context(rls, "portal_application_documents")


@requires_postgres
@pytest.mark.django_db
def test_one_utilitys_held_document_is_invisible_to_another(ready, oak_ridge, elena, rls):
    switch_on(oak_ridge, elena)
    _upload(ready, PDF, "tenancy-agreement.pdf")
    with tenant_context(ready.id):
        owned = {str(row.id) for row in models.PortalApplicationDocument.objects.all()}
    assert len(owned) == 1
    assert_rls_scoped(
        rls,
        "portal_application_documents",
        owner=ready,
        intruder=oak_ridge,
        owner_ids=owned,
    )


@requires_postgres
@pytest.mark.django_db
def test_a_held_document_cannot_be_restamped_into_another_utility(ready, oak_ridge, rls):
    _upload(ready, PDF, "tenancy-agreement.pdf")
    assert_write_into_other_tenant_refused(
        rls, "portal_application_documents", owner=ready, intruder=oak_ridge
    )


@requires_postgres
@pytest.mark.django_db
def test_end_to_end_on_postgres_and_another_utility_gets_404(
    ready, pine_clerk, oak_ridge, elena
):
    """Two files, submitted, opened by the clerk — and refused to another
    utility's admin with the 404 a missing file gets. Run on PostgreSQL because
    the hand-over writes inside savepoints (law 14) and a 404 that came from a
    Python filter rather than the policy would pass on SQLite too."""
    switch_on(oak_ridge, elena)
    assert _upload(ready, PDF, "tenancy-agreement.pdf").status_code == 200
    assert _upload(ready, PNG, "photo-id.png").status_code == 200
    request_id = _send(ready).data["request_id"]
    with tenant_context(ready.id):
        docs = list(
            customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).order_by(
                "uploaded_at", "id"
            )
        )
        assert models.PortalApplicationDocument.objects.count() == 0
    assert len(docs) == 2
    assert _content(ready, pine_clerk, request_id, docs[0].id, "view").content == PDF
    assert _content(ready, pine_clerk, request_id, docs[1].id, "download").content == PNG
    assert _content(oak_ridge, elena, request_id, docs[0].id, "view").status_code == 404
