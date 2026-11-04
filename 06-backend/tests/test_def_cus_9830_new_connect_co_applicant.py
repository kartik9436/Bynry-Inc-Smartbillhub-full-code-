# ── Trace ──────────────────────────────────────────────
# Change:  DEF-CUS-9830 (PO ruling 2026-10-06, option (a)) — a New Connect
#          co-applicant is saved as a co-owner on the new account, the way
#          move-in saves one; only her name is required. With the follow-ups
#          found on NCT-01's photographs: DEF-CUS-9834 (a portal applicant's
#          file names the applicant as its uploader), DEF-CUS-9835 (the
#          utility's own state for a request that gives none) and
#          DEF-CUS-9837 (the account read serves its co-owners, never an
#          identifier).
# Rules:   BR-CUS-092 (SSN and licence encrypted, last four only) · CLAUDE.md
#          hard rule 7 (the write is audited) · hard-won law 14 (proved on
#          PostgreSQL 16)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""Maria Mark, co-applicant on Kyle Mark's New Connect.

THE WORKED CASE: a clerk adds *Maria Mark* as co-applicant with only her name.
On Create she is saved as a co-owner on Kyle's new account — the record move-in
writes — with email, phone, date of birth and SSN blank. Had the clerk typed
SSN `123-45-6789`, it is stored scrambled and staff see `6789` only.

WHAT WOULD MAKE THESE PASS WRONGLY: a co-applicant written as a second CONTACT
would satisfy "the account has a second person" and fail the first test, which
reads `account_co_owners`. A writer of its own (rather than move-in's) would
pass the row assertions and fail the audit one, which asks for move-in's own
action name and the last four.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.customers import co_owner_models
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_reads
from apps.metering import connection_reads
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from core import errors
from tests.test_def_cus_9828_build_prefill_everything import PDF, _kyle, docs_dir  # noqa: F401
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures used by name
    _apply,
    _approve,
    _build,
    _ctx,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam · throttle
from tests.test_us_met_helpers import *  # noqa: F401,F403 — audit_rows

pytestmark = pytest.mark.django_db

MARIA_SSN = "123-45-6789"


def _owner(**co):
    owner = {
        "name": "Kyle Mark",
        "email": "kyle.mark@example.test",
        "phone": "(512) 555-0128",
        "party_kind": "person",
        "identity": {"phone": "(512) 555-0128"},
        "account_type": "residential",
    }
    if co:
        owner["co_owners"] = [co]
    return owner


def _create(cedar, clerk, request_id, owner):
    return _build(
        clerk,
        cedar,
        request_id,
        address="Haustin Towers 2",
        postal_code="78701",
        services=["water"],
        labels=("Apt-12", "Apt-14"),
        owner=owner,
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9830 — the co-applicant is saved as a co-owner
# ═══════════════════════════════════════════════════════════════════════════
def test_a_co_applicant_with_only_her_name_is_saved_as_a_co_owner(cedar, clerk, docs_dir, audit_rows):
    request_id = _kyle(cedar, clerk)
    _built, draft, _premises, _units = _create(cedar, clerk, request_id, _owner(full_name="Maria Mark"))
    with _ctx(cedar):
        rows = list(co_owner_models.AccountCoOwner.objects.filter(account_id=draft.owner_account_id))
        assert len(rows) == 1, "the co-applicant typed on New Connect never reached the account"
        maria = rows[0]
        assert maria.full_name == "Maria Mark"
        assert maria.kind == co_owner_models.KIND_CO_OWNER
        assert (maria.email, maria.phone, maria.date_of_birth) == (None, None, None)
        assert (maria.ssn, maria.ssn_bidx, maria.driving_licence) == (None, None, None)
    added = [r for r in audit_rows if r.get("action") == "customers.account.co_owner_added"]
    assert len(added) == 1, sorted({r.get("action") for r in audit_rows})


def test_her_ssn_is_stored_scrambled_and_only_its_last_four_is_written_anywhere(
    cedar, clerk, docs_dir, audit_rows
):
    request_id = _kyle(cedar, clerk)
    _built, draft, _premises, _units = _create(
        cedar,
        clerk,
        request_id,
        _owner(
            full_name="Maria Mark",
            email="maria@example.test",
            phone="(512) 555-0130",
            date_of_birth="1990-04-12",
            ssn=MARIA_SSN,
            driving_licence="M7781-2201-5566",
        ),
    )
    with _ctx(cedar):
        maria = co_owner_models.AccountCoOwner.objects.get(account_id=draft.owner_account_id)
        assert maria.ssn == MARIA_SSN and maria.ssn_bidx, "encrypted with its blind index"
        assert str(maria.date_of_birth) == "1990-04-12"
        detail = customers_selectors.account_detail(draft.owner_account_id)
    [served] = detail["co_owners"]
    assert served == {
        "kind": "co_owner",
        "full_name": "Maria Mark",
        "email": "maria@example.test",
        "phone": "(512) 555-0130",
    }, "DEF-CUS-9837 — the account read names her and never an identifier"
    assert "6789" not in str(detail["co_owners"])
    [added] = [r for r in audit_rows if r.get("action") == "customers.account.co_owner_added"]
    assert "6789" in str(added) and MARIA_SSN not in str(added) and "123456789" not in str(added)


def test_an_email_is_checked_for_its_format_only_when_given_and_a_bad_one_creates_nothing(
    cedar, clerk, docs_dir
):
    request_id = _kyle(cedar, clerk)
    with pytest.raises(errors.ValidationError) as refused:
        _create(cedar, clerk, request_id, _owner(full_name="Maria Mark", email="maria-at-example"))
    assert refused.value.field_errors[0]["field"] == "co_owners[0].email"
    with _ctx(cedar):
        assert not co_owner_models.AccountCoOwner.objects.exists()
        assert work_tables.Connection.objects.get(service_request_id=request_id).owner_account_id is None


@pytest.mark.parametrize("ssn", [None, MARIA_SSN], ids=["name_only", "with_ssn"])
def test_the_statement_the_po_signed_on_2026_10_06(cedar, clerk, docs_dir, audit_rows, ssn):
    """**SIGNED 2026-10-06 (S9)** — review-ledger AMENDMENT row *"SIGN-OFF
    RECORDED (S9 of S9–S13)"* for `DEF-CUS-9830`; decision log *"S9–S13
    SIGNED"*.

    Shown to the PO, verbatim: *"A clerk adds Maria Mark as co-applicant on New
    Connect. On Create she is saved as a co-owner on Kyle's new account, the
    same record move-in uses; her SSN is stored scrambled and staff see only
    the last four. Only her name is required; email, phone, date of birth and
    SSN may be left blank."* PO, verbatim: *"S9–S13 approve"*.

    Run twice: Maria with ONLY her name (email, phone, date of birth and SSN
    blank), and Maria with her name and SSN `123-45-6789` (the rest blank).
    *"the same record move-in uses"* is asserted as the same table, the same
    kind and the same audit action move-in's writer
    (`move_in_people.write_at_complete`) records. *"stored scrambled"* is
    asserted on the RAW column, read past the model: neither the number nor its
    last four is in it. *"staff see only the last four"*: the one place the
    number surfaces to staff, the audit row, holds `6789` and never the number;
    the account read serves no identifier at all. What the statement did NOT
    carry (the driving licence, a company owner's officers, the bad-email
    refusal) is listed in the ledger row and stays on the agenda.
    """
    request_id = _kyle(cedar, clerk)
    co = {"full_name": "Maria Mark"}
    if ssn:
        co["ssn"] = ssn
    _built, draft, _premises, _units = _create(cedar, clerk, request_id, _owner(**co))
    with _ctx(cedar):
        # ── "On Create she is saved as a co-owner on Kyle's new account" ──
        owner = customers_models.Account.objects.get(pk=draft.owner_account_id)
        [maria] = co_owner_models.AccountCoOwner.objects.filter(account_id=owner.pk)
        assert maria.full_name == "Maria Mark"
        assert maria.kind == co_owner_models.KIND_CO_OWNER
        # ── "the same record move-in uses" ──
        assert co_owner_models.AccountCoOwner._meta.db_table == "account_co_owners"
        # ── "email, phone, date of birth and SSN may be left blank" ──
        assert (maria.email, maria.phone, maria.date_of_birth) == (None, None, None)
        detail = customers_selectors.account_detail(owner.pk)
        with connection.cursor() as cursor:
            key = co_owner_models.AccountCoOwner._meta.pk.get_db_prep_value(maria.pk, connection)
            cursor.execute("SELECT ssn, ssn_bidx FROM account_co_owners WHERE id = %s", [key])
            raw_ssn, raw_bidx = cursor.fetchone()
    added = [r for r in audit_rows if r.get("action") == "customers.account.co_owner_added"]
    assert len(added) == 1, "move-in's own writer, so move-in's own audit action"
    assert added[0]["after"]["full_name"] == "Maria Mark"
    assert [row["full_name"] for row in detail["co_owners"]] == ["Maria Mark"]
    assert "ssn" not in str(detail["co_owners"]).lower()
    if ssn is None:
        assert (maria.ssn, raw_ssn, raw_bidx) == (None, None, None)
        assert added[0]["after"]["ssn_last4"] is None
        return
    # ── "her SSN is stored scrambled" ──
    assert maria.ssn == MARIA_SSN, "the clerk's number, readable through the model only"
    assert raw_ssn and raw_bidx
    for clear in (MARIA_SSN, "123456789", "6789"):
        assert clear not in str(raw_ssn) and clear not in str(raw_bidx)
    # ── "staff see only the last four" ──
    assert added[0]["after"]["ssn_last4"] == "6789"
    assert MARIA_SSN not in str(added) and "123456789" not in str(added)
    assert "6789" not in str(detail)


def test_a_build_with_no_co_applicant_writes_none(cedar, clerk, docs_dir):
    request_id = _kyle(cedar, clerk)
    _built, draft, _premises, _units = _create(cedar, clerk, request_id, _owner())
    with _ctx(cedar):
        assert draft.owner_account_id is not None
        assert not co_owner_models.AccountCoOwner.objects.filter(account_id=draft.owner_account_id).exists()


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9834 — a portal applicant's file names the applicant
# ═══════════════════════════════════════════════════════════════════════════
def test_a_file_the_applicant_brought_through_the_portal_names_the_applicant(cedar, clerk, docs_dir):
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b9834",
        services=["water"],
        first="Kyle",
        last="Mark",
        address="Haustin Towers 2",
    )
    with _ctx(cedar):
        doc_files.attach_from_portal(
            request_id,
            [{"name": "kyle-photo-id.pdf", "content_type": "application/pdf", "payload": PDF, "requirement": "photo_id"}],
        )
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        [row] = [d for d in service_request_reads.documents_tab(request)["documents"] if d["file_present"]]
    assert row["doc_type"] == "proof_of_identity", "the requirement it was attached for survives"
    assert row["uploaded_by_name"] == "Kyle Mark"
    assert row["uploaded_by_role"] == "applicant"


def test_a_file_a_clerk_attached_keeps_the_clerks_name(cedar, clerk, docs_dir):
    request_id = _kyle(cedar, clerk)
    with _ctx(cedar):
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        [row] = [d for d in service_request_reads.documents_tab(request)["documents"] if d["file_present"]]
    assert row["uploaded_by_role"] is None
    assert row["uploaded_by_name"] != "Kyle Mark"


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9835 — the utility's own state for a request that gives none
# ═══════════════════════════════════════════════════════════════════════════
def test_the_prefill_offers_the_utilitys_own_state_beside_what_the_applicant_gave(cedar, clerk):
    tenancy_models.Tenant.objects.filter(pk=cedar.id).update(state="Texas")
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b9835",
        services=["water"],
        first="Kyle",
        last="Mark",
        address="Haustin Towers 2",
    )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="residential")
    with _ctx(cedar):
        prefill = connection_reads.connection_detail(
            work_tables.Connection.objects.get(service_request_id=request_id).id
        )["prefill"]
    assert prefill["address_state_as_given"] in (None, "")
    assert prefill["utility_state"] == "TX"
