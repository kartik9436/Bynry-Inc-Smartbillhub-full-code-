# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-10253 (the account page's edit dialogs use the shared
#           customer fields — image 08-edit.png) · DEF-CUS-10255 (the transfer
#           buyer step carries Move-in's co-buyer cards, documents, Tax,
#           Discounts and Preferences — image 07-transfer.png)
# Rulings:  PO 2026-10-18, decision log *"CUSTOMER DATA AND UI CONSISTENT ACROSS
#           THE CREATE SCREENS"* and its *"Same day"* paragraphs (Transfer:
#           Move-in's Tax, Discounts and Preferences panels for the buyer —
#           *"corect"*; the seller's exemption and discounts are NOT copied)
# Rules:    hard rule 7 (every write audited by its door) · BR-CUS-092(c) ·
#           hard-won law 14 (run on PostgreSQL: `--ds=config.settings.pgtest`)
# ───────────────────────────────────────────────────────
"""Every field the two screens take, read back off the row it lands on.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
response rather than the table — each case reads the row; a co-buyer that
landed as the contact-only co-applicant rather than as a full card — the
co-owner row is read with its relationship and date of birth.
"""

from __future__ import annotations

import pytest

from apps.customers import co_owner_models, customer_edit, transfers
from apps.customers import models as customers_models
from apps.customers import move_in_documents
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.customers.account_document_models import AccountDocument
from core import errors

from tests.test_br_cus_1081_transfer_buyer_capture import _sell, _sold_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

BUYER = {
    "applicant_name": "Lopez, Maria",
    "applicant_kind": "person",
    "applicant_email": "maria.lopez@example.com",
    "applicant_phone": "(734) 555-0182",
    "date_of_birth": "1988-04-12",
    "ssn": "111-22-4471",
    "preferred_language": "es",
}

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Photo ID) >>\n" + b"P" * 2000 + b"\n%%EOF"


class _Upload:
    def __init__(self, payload: bytes, *, name: str, content_type: str):
        self._payload = payload
        self.name = name
        self.content_type = content_type

    def read(self) -> bytes:
        return self._payload


@pytest.fixture()
def docs_dir(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def _sell_with(actor, account, buyer_account):
    started = transfers.start_transfer(actor, {"from_account_id": str(account.id)})
    transfers.set_new_customer(actor, started["id"], {"customer": BUYER})
    transfers.set_sale_date(actor, started["id"], {"sold_on": "2026-09-01"})
    transfers.acknowledge_money(actor, started["id"])
    return transfers.reassign_account(
        actor, started["id"], {"customer": BUYER, "buyer_account": buyer_account}
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10255 — the buyer's own panels at the sale
# ═══════════════════════════════════════════════════════════════════════════
def test_co_buyers_documents_and_preferences_land_on_the_account(brazos, marcus, docs_dir):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        # The SELLER's co-owner, who must leave with the seller.
        co_owner_models.AccountCoOwner.objects.create(
            tenant_id=account.tenant_id, account=account, kind="co_owner", full_name="Seller Spouse"
        )
        staged = move_in_documents.stage(
            marcus,
            {"doc_type": "proof_of_identity", "name": "maria-id.pdf"},
            _Upload(PDF, name="maria-id.pdf", content_type="application/pdf"),
        )
        result = _sell_with(
            marcus,
            account,
            {
                "co_owners": [
                    {
                        "full_name": "Daniel Lopez",
                        "relationship": "spouse",
                        "phone": "(734) 555-0144",
                        "email": "dan.lopez@example.com",
                        "date_of_birth": "1986-09-30",
                        "responsible_for_bills": True,
                    }
                ],
                "documents": [{"card_id": staged["card_id"], "doc_type": "proof_of_identity"}],
                "paperless": True,
                "sms_reminders": True,
                "autopay": False,
            },
        )
        assert result["buyer_extras"]["seller_co_owners_removed"] == 1
        account.refresh_from_db()
        assert (account.paperless, account.sms_reminders, account.autopay) == (True, True, False)
        assert account.preferred_language == "es"
        rows = list(co_owner_models.AccountCoOwner.objects.filter(account=account))
        assert [(r.full_name, r.relationship, r.phone, r.email, r.date_of_birth.isoformat(), r.responsible_for_bills) for r in rows] == [
            ("Daniel Lopez", "spouse", "(734) 555-0144", "dan.lopez@example.com", "1986-09-30", True)
        ]
        assert AccountDocument.objects.filter(account_id=account.id).count() == 1


def test_an_old_commit_with_no_panels_changes_nothing(brazos, marcus):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        co_owner_models.AccountCoOwner.objects.create(
            tenant_id=account.tenant_id, account=account, kind="co_owner", full_name="Kept"
        )
        result = _sell(marcus, account, buyer=BUYER)
        assert "buyer_extras" in result and result["buyer_extras"] == {"sent": False}
        assert co_owner_models.AccountCoOwner.objects.filter(account=account).count() == 1


def test_an_unknown_panel_key_is_refused_by_name_before_anything_is_written(brazos, marcus):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        seller = customers_models.CustomerAccount.objects.get(account=account).customer_id
        with pytest.raises(errors.ValidationError) as refused:
            _sell_with(marcus, account, {"seller_discounts": True})
        assert refused.value.params["field"] == "buyer_account.seller_discounts"
        # Refused before the reassignment: the account is still the seller's.
        live = customers_models.CustomerAccount.objects.filter(account=account, ended_at__isnull=True)
        assert [row.customer_id for row in live] == [seller]


def test_a_tax_certificate_must_be_whole_and_a_bad_claim_is_refused(brazos, marcus):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        with pytest.raises(errors.ValidationError):
            _sell_with(
                marcus,
                account,
                {"tax_exemption": {"category_id": "x", "certificate_ref": "EX-1", "issued_on": "not a date"}},
            )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10253 — the edit dialogs' shared fields
# ═══════════════════════════════════════════════════════════════════════════
def test_edit_customer_writes_contact_by_on_every_account_and_serves_it(brazos, marcus):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        holder = customers_models.CustomerAccount.objects.get(account=account).customer
        customer_edit.update_customer(marcus, holder.id, {"contact_by": "text", "email": "m@example.org"})
        contact = customers_models.Contact.objects.get(account=account, is_primary=True)
        assert (contact.contact_by, contact.email) == ("text", "m@example.org")
        row = customers_selectors.customer_rows([holder])[0]
        assert (row["contact_by"], row["email"]) == ("text", "m@example.org")
        detail = customers_selectors.account_detail(str(account.id))
        assert detail["contacts"][0]["contact_by"] == "text"
        with pytest.raises(errors.ValidationError):
            customer_edit.update_customer(marcus, holder.id, {"contact_by": "pigeon"})


def test_the_co_applicant_keeps_a_date_of_birth(brazos, marcus):
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        customers_services.update_account_co_applicant(
            marcus, account.id, {"full_name": "Daniel Lopez", "dob": "1986-09-30", "phone": "(734) 555-0144"}
        )
        row = customers_models.Contact.objects.get(account=account, is_primary=False, deleted_at__isnull=True)
        assert (row.full_name, row.dob.isoformat(), row.phone) == ("Daniel Lopez", "1986-09-30", "(734) 555-0144")
        # An absent key keeps what is stored.
        customers_services.update_account_co_applicant(marcus, account.id, {"email": "dan@example.com"})
        row.refresh_from_db()
        assert (row.dob.isoformat(), row.email) == ("1986-09-30", "dan@example.com")
