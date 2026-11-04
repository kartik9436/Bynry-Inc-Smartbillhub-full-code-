# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9147 — a clerk can FILE a document on an account and cannot
#           OPEN it. The Documents tab's row carried a bin and nothing else.
# Route:    GET /accounts/{id}/documents/{docId}/content?as=view|download —
#           the service request's `CR-158-BRC10` content route, for an account.
# ───────────────────────────────────────────────────────
"""The account's filed document, opened through the route a browser calls.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
  * *"the route answers 200"* passes over an empty body — so the bytes are
    compared with what was filed, byte for byte;
  * *"another utility gets 404"* passes if EVERY call gets 404 — so the owning
    tenant's call is made first in the same case and must answer 200;
  * *"a withdrawn filing cannot be opened"* passes vacuously if the filing was
    never openable — so it is opened before it is withdrawn.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.customers import account_documents, api
from core import errors
from core.tenancy import tenant_context
from tests.test_cr094_i_account_documents import (  # noqa: F401 — fixtures
    PDF,
    _account,
    _file,
    docs_dir,
    guc,
    two_utilities,
)
from tests.test_us_ten_helpers import api_call

CLERK = SimpleNamespace(id=None, pk=None, is_authenticated=True)


def _content(tenant, account_id, document_id, mode="view"):
    return api_call(
        api.account_document_content,
        "get",
        f"/api/{tenant.subdomain}/accounts/{account_id}/documents/{document_id}/content",
        tenant=tenant,
        user=CLERK,
        role="billing_clerk",
        query={"as": mode},
        account_id=str(account_id),
        document_id=str(document_id),
    )


@pytest.mark.django_db
def test_the_route_is_addressable_beside_the_link():
    """The address the screen builds is a route the API actually has."""
    from django.urls import resolve

    match = resolve("/api/brazosbend/accounts/a1/documents/d1/content")
    assert match.func is api.account_document_content


@pytest.mark.django_db
def test_a_clerk_opens_the_filed_bytes_with_safe_headers(two_utilities, docs_dir):
    alpha, _ = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(account, name="signed-lease.pdf")

    view = _content(alpha, account.pk, filed["id"], "view")
    assert view.status_code == 200
    assert view.content == PDF
    assert view["Content-Type"] == "application/pdf"
    assert view["Content-Disposition"].startswith('inline; filename="signed-lease.pdf"')
    assert view["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in view["Content-Security-Policy"]
    assert "no-store" in view["Cache-Control"]

    download = _content(alpha, account.pk, filed["id"], "download")
    assert download.status_code == 200
    assert download.content == PDF
    assert download["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db
def test_a_csv_is_never_drawn_inline(two_utilities, docs_dir):
    alpha, _ = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(
            account,
            doc_type="payment",
            name="remittance.csv",
            payload=b"date,amount\n2026-10-02,15.00\n",
            content_type="text/csv",
        )
    view = _content(alpha, account.pk, filed["id"], "view")
    assert view.status_code == 200
    assert view["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db
def test_each_open_is_audited(two_utilities, docs_dir):
    from apps.audit.models import AuditLog

    alpha, _ = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(account)
    _content(alpha, account.pk, filed["id"], "view")
    _content(alpha, account.pk, filed["id"], "download")
    with tenant_context(alpha.id):
        actions = list(
            AuditLog.objects.filter(entity_id=filed["id"]).values_list("action", flat=True)
        )
    assert "customers.account_document.viewed" in actions
    assert "customers.account_document.downloaded" in actions


@pytest.mark.django_db
def test_another_utility_gets_the_404_a_missing_file_gets(two_utilities, docs_dir):
    alpha, beta = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(account)
    assert _content(alpha, account.pk, filed["id"]).status_code == 200
    with pytest.raises(errors.NotFoundError):
        with tenant_context(beta.id):
            account_documents.document_content(CLERK, account.pk, filed["id"], "view")


@pytest.mark.django_db
def test_a_withdrawn_filing_cannot_be_opened(two_utilities, docs_dir):
    alpha, _ = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(account, doc_type="correspondence", name="letter.pdf")
    assert _content(alpha, account.pk, filed["id"]).status_code == 200
    from tests.test_us_met_helpers import staff_actor

    with tenant_context(alpha.id):
        # A REAL user: `withdrawn_by` is a foreign key and a withdrawal naming
        # nobody is refused by `ck_account_documents_withdrawal`.
        clerk = staff_actor(alpha, "billing_clerk", email="dana@silvercreek.test")
        account_documents.withdraw_document(clerk, account.pk, filed["id"])
    with pytest.raises(errors.NotFoundError):
        with tenant_context(alpha.id):
            account_documents.document_content(CLERK, account.pk, filed["id"], "view")


@pytest.mark.django_db
def test_an_unknown_mode_is_refused_by_name(two_utilities, docs_dir):
    alpha, _ = two_utilities
    with tenant_context(alpha.id):
        account = _account(alpha)
        filed = _file(account)
        with pytest.raises(errors.ValidationError):
            account_documents.document_content(CLERK, account.pk, filed["id"], "print")
