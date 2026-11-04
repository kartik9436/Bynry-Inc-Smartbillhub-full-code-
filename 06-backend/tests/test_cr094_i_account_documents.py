# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`, "An account can hold a
#           document". Step 1 lane 2 finding F10.
# Rules:    BR-CUS-036 · BR-SHL-031 · NFR-3 · NFR-5 · NFR-33 · NFR-35 ·
#           BR-TEN-003 (existence must not leak) · CLAUDE.md hard rule 1 and 7.
# ───────────────────────────────────────────────────────
"""`ACC-S8` — the filing cabinet, proved against the running code.

⚠ **EVERY CASE HERE WAS SHOWN RED BEFORE IT WAS SHOWN GREEN** (hard-won law 7),
and through `pytest` — the harness that will run them — never through a
`__main__` that exercises a path nobody else takes. The lane report quotes each
failure.

**WHAT THE SECOND-PDF CASE IS FOR, because it is the one that would have shipped
broken.** `uq_stored_documents_filed` allows one artefact per
`(tenant, source_type, source_id, content_type)` where the channel is NULL. Had
this wave filed under `SOURCE_CUSTOMER_ACCOUNT` — the value whose own comment
says *"account documents, certificates"* — the FIRST upload on an account would
work and the SECOND `application/pdf` would be refused by the database. That is
not a case any specification for this tab asks for; it is the first thing a real
clerk does on a real account, and the only reason it is here is that
`tenancy/0040` had already recorded the identical finding for a technician's
ninth photograph.

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""

import uuid

import pytest
from django.utils import timezone

from apps.customers import account_documents
from apps.customers.account_document_models import AccountDocument
from apps.tenancy.document_models import (
    KIND_ACCOUNT_DOCUMENT,
    SOURCE_ACCOUNT_DOCUMENT,
    StoredDocument,
)
from core.pagination import ListParams
from core.tenancy import tenant_context

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\nthe signed lease for 1408 Elm St\n%%EOF"


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """`set_config` on sqlite, the REAL GUC on PostgreSQL — the store's own
    fixture, reused verbatim so the two files cannot drift about what a tenant
    context is."""
    from django.db import connection as real_connection

    from core import tenancy as core_tenancy
    from tests.test_us_ten_helpers import FakeGucConnection

    if real_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", FakeGucConnection())
    core_tenancy._current_tenant.set(None)
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can see another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


@pytest.fixture()
def two_utilities(db):
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Silver Creek Water", subdomain=f"silver{suffix}")
    beta = Tenant.objects.create(name="Brazos Utility", subdomain=f"brazos{suffix}")
    return alpha, beta


def _account(tenant, account_no="AC-2026-00042"):
    """The thinnest lawful account: `accounts.status_id` is NOT NULL, so a
    status and a type are created once per tenant and reused."""
    from apps.customers import models as customers_models

    status, _ = customers_models.AccountStatus.objects.get_or_create(
        tenant=tenant,
        code="active",
        defaults={"name": "Active", "behavior_class": "occupying"},
    )
    # ⚠ `account_types` WAS a platform lookup with no tenant column until the
    # PO ruling of 2026-09-17 (*"utility can get their own account types"*,
    # decision log "A UTILITY MAY DEFINE ITS OWN ACCOUNT TYPES", d0b2afb50) made
    # it tenant-owned with `tenant_id NOT NULL` — so the row is now per tenant.
    account_type, _ = customers_models.AccountType.objects.get_or_create(
        tenant=tenant, code="residential", defaults={"name": "Residential"}
    )
    # ⚠ `ck_accounts_anchored` — an account names a unit or a premises. An
    # account anchored nowhere is refused by the database, so the thinnest
    # lawful row still needs a building (`BR-CUS-1010`'s owner-account shape). `premises_id` is a plain UUID and not
    # a ForeignKey — a deferred cross-module link, so it takes an id.
    from apps.metering import models as metering_models

    premises, _ = metering_models.Premises.objects.get_or_create(
        tenant=tenant,
        address_line="1408 Elm St",
        defaults={"city": "Ottumwa", "state": "IA"},
    )
    return customers_models.Account.objects.create(
        tenant=tenant,
        account_no=account_no,
        status=status,
        account_type=account_type,
        premises_id=premises.id,
        kind="master",
    )


class _Upload:
    """One multipart part, as DRF hands it to the endpoint."""

    def __init__(self, payload: bytes, *, name: str, content_type: str):
        self._payload = payload
        self.name = name
        self.content_type = content_type

    def read(self) -> bytes:
        return self._payload


def _actor(user_id=None):
    from types import SimpleNamespace

    return SimpleNamespace(id=user_id)


def _file(account, **overrides):
    kwargs = {
        "doc_type": "contract",
        "name": "signed-lease.pdf",
        "payload": PDF,
        "content_type": "application/pdf",
    }
    kwargs.update(overrides)
    upload = _Upload(kwargs["payload"], name=kwargs["name"], content_type=kwargs["content_type"])
    return account_documents.file_document(
        _actor(), account.pk, {"doc_type": kwargs["doc_type"], "name": kwargs["name"]}, upload
    )


def _params(**overrides):
    base = {
        "q": "",
        "sort": account_documents.DOCUMENT_DEFAULT_SORT,
        "dir": account_documents.DOCUMENT_DEFAULT_DIR,
        "page": 1,
        "per": 25,
        "filters": {},
    }
    base.update(overrides)
    return ListParams(**base)


# ═══════════════════════════════════════════════════════════════════════════
# §1 · THE CAPABILITY — an account can hold a document
# ═══════════════════════════════════════════════════════════════════════════


class TestFiling:
    def test_one_document_is_filed_and_listed(self, two_utilities, docs_dir):
        """`ACC-S8` in one sentence: file it, then the tab shows it."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
            # ⚠ **REWRITTEN 2026-09-13 (`DEF-CUS-5147`) — NOT DELETED.** This
            # asserted the whole storage-shaped name, `account-documents/<yyyy>/
            # <mm>/AC-2026-00042-signed-lease.pdf`, and passing it is how the
            # `DOCUMENT` column on `ACC-T10` came to draw a PATH where the
            # blueprint draws a document's name. The list now serves what the
            # clerk typed; the STORED name is unchanged and is asserted below,
            # so both halves are pinned and neither can drift into the other.
            assert filed["name"] == "signed-lease.pdf"
            card = AccountDocument.objects.get(pk=filed["id"])
            assert StoredDocument.objects.get(pk=card.document_id).display_name.endswith(
                "AC-2026-00042-signed-lease.pdf"
            )
            assert filed["doc_type"] == "contract"
            assert filed["size_bytes"] == len(PDF)

            rows, total = account_documents.documents_page(account.pk, _params())
            assert total == 1
            assert rows[0]["id"] == filed["id"]

    def test_the_bytes_reach_the_store_under_the_ninth_source_type(
        self, two_utilities, docs_dir
    ):
        """The stored row is the product's, the filing card is customers'."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
            card = AccountDocument.objects.get(pk=filed["id"])
            document = StoredDocument.objects.get(pk=card.document_id)
            assert document.kind == KIND_ACCOUNT_DOCUMENT
            assert document.source_type == SOURCE_ACCOUNT_DOCUMENT
            # ⚠ THE SOURCE IS THE FILING CARD, NOT THE ACCOUNT. See §2.
            assert document.source_id == card.id
            assert document.byte_length == len(PDF)

    def test_a_second_pdf_on_one_account_is_accepted(self, two_utilities, docs_dir):
        """⚠ **THE CASE THE WHOLE DESIGN TURNS ON.**

        Under `SOURCE_CUSTOMER_ACCOUNT` this is the row the database refuses —
        one artefact per `(tenant, source_type, source_id, content_type)` with a
        NULL channel. A clerk filing a lease and then a landlord's letter is the
        first thing that happens on a real account.
        """
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            _file(account, name="signed-lease.pdf")
            _file(account, name="landlord-letter.pdf")
            _rows, total = account_documents.documents_page(account.pk, _params())
            assert total == 2

    def test_the_filing_is_audited(self, two_utilities, docs_dir):
        """Hard rule 7 covers money actions and this is not one; a row is
        written anyway, because a document filed against a financial record is
        evidence about that record. Both rows land — the store's, and this."""
        from apps.audit.models import AuditLog

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
            actions = set(
                AuditLog.objects.filter(tenant_id=alpha.id).values_list("action", flat=True)
            )
            assert "customers.account_document.filed" in actions
            assert "document.stored" in actions
            row = AuditLog.objects.get(action="customers.account_document.filed")
            assert str(row.entity_id) == filed["id"]
            assert row.after["account_id"] == str(account.pk)


# ═══════════════════════════════════════════════════════════════════════════
# §2 · THE GUARDS — `BR-SHL-031`, quoted rather than chosen
# ═══════════════════════════════════════════════════════════════════════════


class TestGuards:
    def test_a_type_outside_the_allowlist_is_415(self, two_utilities, docs_dir):
        """11b G11 · `BR-SHL-031` — PDF/PNG/JPG/CSV and nothing else."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            with pytest.raises(account_documents.UploadRefused) as refusal:
                _file(account, name="macro.docm", content_type="application/vnd.ms-word")
            assert refusal.value.status == 415
            assert refusal.value.message_key == "customers.document.type_not_allowed"
            assert AccountDocument.objects.count() == 0
            # ⚠ AND NO BYTES WERE STORED. A guard that refuses the row after the
            # upload has happened leaves a file nothing can ever delete.
            assert StoredDocument.objects.count() == 0

    def test_a_content_type_with_a_parameter_is_still_allowed(
        self, two_utilities, docs_dir
    ):
        """`image/jpeg; charset=binary` is a legal header. Comparing the whole
        header would 415 a file that is on the list."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(
                account, name="meter.jpg", content_type="image/jpeg; charset=binary"
            )
            assert filed["content_type"] == "image/jpeg"

    def test_a_file_over_the_cap_is_413(self, two_utilities, docs_dir):
        """11b G11 · `BR-SHL-031`'s 10 MB. One byte over is over."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            oversize = b"x" * (account_documents.MAX_UPLOAD_BYTES + 1)
            with pytest.raises(account_documents.UploadRefused) as refusal:
                _file(account, payload=oversize)
            assert refusal.value.status == 413
            assert refusal.value.message_key == "customers.document.too_large"
            assert StoredDocument.objects.count() == 0

    def test_a_system_document_cannot_be_uploaded_by_hand(self, two_utilities, docs_dir):
        """`BR-CUS-036`: system documents *"attach automatically"*. Typing
        `system` would make "the product generated this" a person's claim."""
        from core import errors

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            with pytest.raises(errors.ValidationError) as refusal:
                _file(account, doc_type="system")
            assert refusal.value.message_key == "customers.document.type_not_uploadable"

    def test_an_unknown_type_is_refused(self, two_utilities, docs_dir):
        from core import errors

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            with pytest.raises(errors.ValidationError) as refusal:
                _file(account, doc_type="invoice")
            assert refusal.value.message_key == "customers.document.type_unknown"

    def test_an_empty_file_is_refused(self, two_utilities, docs_dir):
        from core import errors

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            with pytest.raises(errors.ValidationError) as refusal:
                _file(account, payload=b"")
            assert refusal.value.message_key == "customers.document.file_required"


# ═══════════════════════════════════════════════════════════════════════════
# §3 · TENANT SCOPING — hard rule 1, and existence must not leak
# ═══════════════════════════════════════════════════════════════════════════


class TestScoping:
    def test_another_tenant_cannot_see_the_filing(self, two_utilities, docs_dir):
        """Not a 403 — a 404. A 403 would confirm the account exists."""
        from core import errors

        alpha, beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            _file(account)
        with tenant_context(beta.id):
            with pytest.raises(errors.NotFoundError):
                account_documents.documents_page(account.pk, _params())

    def test_another_tenant_cannot_mint_a_download_link(self, two_utilities, docs_dir):
        """⚠ The row is resolved under THIS tenant FIRST and the URL is minted
        second, so a link is never issued for a document the caller could not
        have found."""
        from core import errors

        alpha, beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
        with tenant_context(beta.id):
            with pytest.raises(errors.NotFoundError):
                account_documents.document_link(account.pk, filed["id"])

    def test_the_link_is_minted_for_the_owning_tenant(self, two_utilities, docs_dir):
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
            link = account_documents.document_link(account.pk, filed["id"])
            assert link["url"]
            assert link["expires_in_seconds"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# §4 · THE LIST — `NFR-3` in SQL, `NFR-5` with no cap, `BR-CUS-1046` newest first
# ═══════════════════════════════════════════════════════════════════════════


class TestList:
    def test_newest_first_by_default(self, two_utilities, docs_dir):
        """`BR-CUS-1046` (PO 2026-09-10): *"The new newly created entries should
        always show on the top."* A filing cabinet opening on the oldest scan is
        the exact inversion that ruling removes."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            first = _file(account, name="oldest.pdf")
            second = _file(account, name="newest.pdf")
            AccountDocument.objects.filter(pk=first["id"]).update(
                uploaded_at=timezone.now() - timezone.timedelta(days=30)
            )
            rows, _total = account_documents.documents_page(account.pk, _params())
            assert [row["id"] for row in rows] == [second["id"], first["id"]]

    def test_the_page_is_taken_in_sql_and_the_count_is_the_whole_set(
        self, two_utilities, docs_dir
    ):
        """`NFR-3`. Four filings, two per page: page 1 has two rows and the
        count says four — the whole set was never built to draw two of it."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            for index in range(4):
                _file(account, name=f"scan-{index}.pdf")
            rows, total = account_documents.documents_page(
                account.pk, _params(per=2, page=1)
            )
            assert len(rows) == 2
            assert total == 4
            rows_two, _ = account_documents.documents_page(account.pk, _params(per=2, page=2))
            assert len(rows_two) == 2
            assert {row["id"] for row in rows} & {row["id"] for row in rows_two} == set()

    def test_the_type_filter_narrows_and_a_wrong_one_does_not_empty_the_table(
        self, two_utilities, docs_dir
    ):
        """`BR-SHL-011` — clamp, never error. A chip spelled wrong by a client
        must not tell a clerk their account holds nothing."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            _file(account, doc_type="contract", name="lease.pdf")
            _file(account, doc_type="kyc", name="licence.pdf")
            _rows, contracts = account_documents.documents_page(
                account.pk, _params(filters={"type": "contract"})
            )
            assert contracts == 1
            _rows, nonsense = account_documents.documents_page(
                account.pk, _params(filters={"type": "evidence"})
            )
            assert nonsense == 2

    def test_the_search_matches_the_document_name(self, two_utilities, docs_dir):
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            _file(account, name="signed-lease.pdf")
            _file(account, name="bank-letter.pdf")
            _rows, total = account_documents.documents_page(account.pk, _params(q="lease"))
            assert total == 1

    def test_one_account_does_not_see_another_account_s_filings(
        self, two_utilities, docs_dir
    ):
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            one = _account(alpha, account_no="AC-2026-00001")
            two = _account(alpha, account_no="AC-2026-00002")
            _file(one, name="lease.pdf")
            _rows, total = account_documents.documents_page(two.pk, _params())
            assert total == 0
