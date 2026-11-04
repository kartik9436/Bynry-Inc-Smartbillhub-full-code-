# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave M — `BR-CUS-1052`, "a clerk can take back
#           a document they filed". PO 2026-09-13, verbatim: *"We should have
#           this functionality"*, on wave I's own report that *"a clerk who
#           files the wrong scan cannot take it back"*.
# Rules:    BR-CUS-1052 (the ruling) · BR-CUS-036 (system/contract audit-locked)
#           · BR-SHL-031 + NFR-35 (write-once, seven years — NOT reversed) ·
#           BR-TEN-003 (existence must not leak) · CLAUDE.md hard rule 7
#           (audit) · hard-won law 14 (the SQLite/PostgreSQL split).
# ───────────────────────────────────────────────────────
"""Taking a filing back, proved against the running code.

⚠ **EVERY CASE HERE WAS SHOWN RED BEFORE IT WAS SHOWN GREEN** (hard-won law 7),
through `pytest` — the harness that will run them — and the lane report quotes
the failures.

**THE CASE THIS FILE EXISTS FOR IS `test_the_stored_object_is_untouched`.** The
ruling collides with a CONFIRMED rule: `BR-SHL-031` makes the legal class
write-once for seven years and `stored_documents` enforces it with a database
trigger. A withdrawal that quietly erased the bytes would satisfy every other
case in this file, read like a delete, and break a signed retention promise on
a real customer's identity document. So the bytes are asserted present, hashed
and fetchable AFTER the filing has gone — which is the only assertion here that
would notice.

**THE FIXTURES ARE WAVE I's, IMPORTED RATHER THAN RETYPED.** `two_utilities`,
`docs_dir`, `guc` and the account/upload helpers come from
`test_cr094_i_account_documents`, so the two files cannot drift about what an
account, a tenant context or a document store is. The PO's standing instruction
for this work, verbatim: *"Do all changes based on actual code — also don't
create duplicate code."*

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""

import pytest

from apps.customers import account_documents
from apps.customers.account_document_models import (
    AUDIT_LOCKED_TYPES,
    WITHDRAWABLE_TYPES,
    AccountDocument,
)
from apps.tenancy import document_store
from apps.tenancy.document_models import StoredDocument
from core import errors
from core.tenancy import tenant_context

from tests.test_cr094_i_account_documents import (  # noqa: F401 — fixtures by import
    PDF,
    _account,
    _file,
    _params,
    docs_dir,
    guc,
    two_utilities,
)

pytestmark = pytest.mark.django_db


def _clerk(tenant):
    """A REAL `users` row — `withdrawn_by` is a FK and a synthetic uuid would
    break the reviewed cross-module FK set (B2 §2)."""
    from tests.test_us_met_helpers import staff_actor

    return staff_actor(tenant, "billing_clerk", email="dana@silvercreek.test")


# ═══════════════════════════════════════════════════════════════════════════
# §1 · THE CAPABILITY — a clerk can take back a scan they filed
# ═══════════════════════════════════════════════════════════════════════════


class TestWithdrawal:
    def test_a_filed_document_leaves_the_account(self, two_utilities, docs_dir):
        """`BR-CUS-1052` in one sentence: file it, take it back, it is gone."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="kyc", name="drivers-licence.pdf")
            _rows, before = account_documents.documents_page(account.pk, _params())
            assert before == 1

            account_documents.withdraw_document(_clerk(alpha), account.pk, filed["id"])

            rows, after = account_documents.documents_page(account.pk, _params())
            assert after == 0, "a withdrawn filing is not COUNTED, not merely hidden"
            assert rows == []

    def test_it_can_no_longer_be_opened(self, two_utilities, docs_dir):
        """Not listed is half of it; the download link must die too."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="payment", name="bank-letter.pdf")
            assert account_documents.document_link(account.pk, filed["id"])["url"]

            account_documents.withdraw_document(_clerk(alpha), account.pk, filed["id"])

            with pytest.raises(errors.NotFoundError):
                account_documents.document_link(account.pk, filed["id"])

    def test_the_row_survives_and_says_who_took_it_back(self, two_utilities, docs_dir):
        """A tombstone, not a deletion — `withdrawn_at` and `withdrawn_by`."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="correspondence", name="letter.pdf")
            clerk = _clerk(alpha)

            account_documents.withdraw_document(clerk, account.pk, filed["id"])

            card = AccountDocument.objects.get(pk=filed["id"])
            assert card.withdrawn_at is not None
            assert str(card.withdrawn_by_id) == str(clerk.pk)
            assert card.document_id is not None, "the way back to the object"

    def test_the_stored_object_is_untouched(self, two_utilities, docs_dir):
        """⚠ **THE ONE THAT MATTERS.** `BR-SHL-031` and `NFR-35` are NOT
        reversed by `BR-CUS-1052`: the filing leaves the account and the bytes
        stay under their seven-year lock, fetchable and hashing to what the row
        recorded."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="kyc", name="passport.pdf")
            document_id = AccountDocument.objects.get(pk=filed["id"]).document_id
            hash_before = StoredDocument.objects.get(pk=document_id).content_hash

            account_documents.withdraw_document(_clerk(alpha), account.pk, filed["id"])

            row = StoredDocument.objects.get(pk=document_id)
            assert row.content_hash == hash_before
            assert document_store.fetch(document_id) == PDF


# ═══════════════════════════════════════════════════════════════════════════
# §2 · THE REFUSALS — `BR-CUS-036`'s audit-locked classes, BY NAME
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditLocked:
    def test_a_contract_refuses_by_name(self, two_utilities, docs_dir):
        """`BR-CUS-036`: *"system/contract docs audit-locked (IS-1 🔒)"*. A
        contract a clerk uploaded is still audit-locked — uploadable is not
        withdrawable."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)  # `contract` is wave I's default
            with pytest.raises(errors.BizError) as refusal:
                account_documents.withdraw_document(_clerk(alpha), account.pk, filed["id"])
            assert refusal.value.code == errors.BIZ_LOCKED
            assert refusal.value.message_key == "customers.document.withdraw_locked"
            assert refusal.value.br_ref == "BR-CUS-036"

            _rows, total = account_documents.documents_page(account.pk, _params())
            assert total == 1, "a refused withdrawal removes nothing"

    def test_the_refusal_is_a_conflict_and_never_a_not_found(self, two_utilities, docs_dir):
        """⚠ A 404 here would teach a clerk the row had gone when it had not.
        409 says *it is here and you may not take it back*, which is what
        `BR-SHL-025` then puts on the disabled control."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account)
            with pytest.raises(errors.BizError) as refusal:
                account_documents.withdraw_document(_clerk(alpha), account.pk, filed["id"])
            assert errors.HTTP_STATUS_BY_CODE[refusal.value.code] == 409

    def test_the_two_lists_partition_the_five_types(self):
        """⚠ **A LIST NOBODY CHECKS IS A LIST THAT DRIFTS.** A sixth document
        type must land in exactly one of these, deliberately — never in both and
        never in neither by accident."""
        from apps.customers.account_document_models import DOCUMENT_TYPES

        assert set(WITHDRAWABLE_TYPES) | set(AUDIT_LOCKED_TYPES) == set(DOCUMENT_TYPES)
        assert not set(WITHDRAWABLE_TYPES) & set(AUDIT_LOCKED_TYPES)
        assert set(AUDIT_LOCKED_TYPES) == {"system", "contract"}


# ═══════════════════════════════════════════════════════════════════════════
# §3 · WHO MAY ASK, AND WHAT ANOTHER UTILITY IS TOLD
# ═══════════════════════════════════════════════════════════════════════════


class TestBoundaries:
    def test_another_utility_gets_the_answer_of_a_stranger(self, two_utilities, docs_dir):
        """`BR-TEN-003`, HR-1 — existence must not leak. The same 404 as for a
        document that never was."""
        alpha, beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="kyc", name="licence.pdf")
        with tenant_context(beta.id):
            other = _account(beta, account_no="AC-2026-00099")
            with pytest.raises(errors.NotFoundError):
                account_documents.withdraw_document(_clerk(beta), other.pk, filed["id"])
        with tenant_context(alpha.id):
            _rows, total = account_documents.documents_page(account.pk, _params())
            assert total == 1, "a stranger's request removed nothing"

    def test_a_second_withdrawal_answers_not_found(self, two_utilities, docs_dir):
        """A stale tab pressing Remove twice. The account does not hold it, so
        *"no such document on this account"* is the literal truth."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="payment", name="receipt.pdf")
            clerk = _clerk(alpha)
            account_documents.withdraw_document(clerk, account.pk, filed["id"])
            with pytest.raises(errors.NotFoundError):
                account_documents.withdraw_document(clerk, account.pk, filed["id"])

    def test_an_unnamed_actor_is_refused_before_the_write(self, two_utilities, docs_dir):
        """⚠ **hard-won law 14 lives here.** `ck_account_documents_withdrawal`
        is the backstop; this guard is the mechanism. Were it the other way
        round, the CHECK would fire mid-transaction — poisoning everything after
        it on PostgreSQL and doing nothing at all on the SQLite the suite runs
        on, which is a defect that passes every test and fails in production."""
        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="kyc", name="id.pdf")
            from types import SimpleNamespace

            with pytest.raises(errors.ValidationError) as refusal:
                account_documents.withdraw_document(
                    SimpleNamespace(id=None), account.pk, filed["id"]
                )
            assert refusal.value.message_key == "customers.document.withdraw_actor_required"
            assert AccountDocument.objects.get(pk=filed["id"]).withdrawn_at is None


# ═══════════════════════════════════════════════════════════════════════════
# §4 · THE AUDIT ROW — `BR-CUS-1052` and CLAUDE.md hard rule 7
# ═══════════════════════════════════════════════════════════════════════════


class TestAudit:
    def test_the_withdrawal_names_who_and_when(self, two_utilities, docs_dir, monkeypatch):
        """*"the withdrawal writes an audit row naming who did it and when"*.

        ⚠ **AND `before` CARRIES THE `document_id`**, because after this the
        account's own row is the only thing that still points at an object
        sitting under a seven-year lock — and `OQ-1340` (OPEN) means nobody may
        yet call `audit_log` a permanent record of it."""
        from core import audit as core_audit

        written: list[dict] = []
        monkeypatch.setattr(core_audit, "_sink", lambda row: written.append(row))

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="correspondence", name="note.pdf")
            clerk = _clerk(alpha)
            written.clear()

            account_documents.withdraw_document(clerk, account.pk, filed["id"])

        rows = [r for r in written if r["action"] == "customers.account_document.withdrawn"]
        assert len(rows) == 1
        row = rows[0]
        assert row["entity_type"] == "account_document"
        assert str(row["actor_user_id"]) == str(clerk.pk)
        assert row["before"]["document_id"]
        assert row["before"]["doc_type"] == "correspondence"
        assert row["after"]["withdrawn_at"]


# ═══════════════════════════════════════════════════════════════════════════
# §5 · THE WIRING — hard-won law 2, and it is the case with the most to say
# ═══════════════════════════════════════════════════════════════════════════


class TestTheRouteIsReallyThere:
    """⚠ **A SERVICE NOBODY CAN CALL IS DEAD CODE THAT PASSES EVERY TEST.**

    Every case above calls `withdraw_document()` directly. All eleven would pass
    over an endpoint that was never given a `DELETE` method, over a route that
    was never mounted, and over a permission class that refuses every clerk —
    and the screen's bin would do nothing at all. So this class goes in through
    the VIEW, on the real URL, with a real actor.
    """

    def _request(self, method: str, tenant, user, path: str):
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        request = getattr(factory, method)(path)
        force_authenticate(request, user=user)
        request.tenant_role = "billing_clerk"
        request.tenant_id = tenant.id
        return request

    def test_the_delete_reaches_the_service_and_answers_204(self, two_utilities, docs_dir):
        from apps.customers import api as customers_api

        alpha, _beta = two_utilities
        with tenant_context(alpha.id):
            account = _account(alpha)
            filed = _file(account, doc_type="kyc", name="licence.pdf")
            clerk = _clerk(alpha)
            path = f"/api/v1/accounts/{account.pk}/documents/{filed['id']}"

            response = customers_api.account_document_item(
                self._request("delete", alpha, clerk.user, path),
                str(account.pk),
                str(filed["id"]),
            )
            assert response.status_code == 204

            # …and the filing is really gone from the list the tab reads.
            _rows, total = account_documents.documents_page(account.pk, _params())
            assert total == 0

    def test_the_route_is_mounted_and_the_view_accepts_DELETE(self):
        """⚠ **THE URL MAP, NOT A STRING.** A view that handles `DELETE`
        beautifully at a path nothing routes to is the same dead control."""
        from apps.customers.api import account_document_item, urlpatterns

        pattern = next(
            p for p in urlpatterns if "documents/<str:document_id>" in str(p.pattern)
        )
        assert pattern.callback is account_document_item
        assert "DELETE" in account_document_item.cls.http_method_names or "delete" in [
            m.lower() for m in getattr(account_document_item, "cls").http_method_names
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 wave M (sources: 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-1052 + BR-CUS-036 · 04-docs/05-modules/00-platform-shell/02-business-rules.md BR-SHL-031 · 12-governance/02-decision-log.md 2026-09-13 · 06-backend/apps/customers/account_documents.py)
# generated: 2026-09-13 by the CR-094-BRC01 wave M lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
