# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9792 — Plans & Rates' + Enroll an account (and
#          POST /accounts/{id}/discounts behind it) enrolled an account in an
#          AUTOMATIC discount by hand; the nightly sync ended it the next night.
#          DEF-CUS-9780 — low-income evidence uploaded at move-in was filed as a
#          KYC account document and never attached to the enrolment it supports.
# Rules:   PO 2026-10-03 ruling (3) (an Automatic discount is the system's to
#          grant and end) · PO 2026-10-05 ruling (2) (a clerk RECORDS a claim;
#          verifying stays System Admin's) · BR-RAT-076 (proof before the first
#          reduction is the programme's stored money rule) · BR-RAT-079 (the
#          proof's `restricted` flag is derived from its kind) · B18 §5.5.5
#          (the enrolment's evidence reference)
# Amended: 2026-10-06 (`DEF-RAT-9833`, PO D2 (b): *"clark can add it later also
#          on account"*) — Autopay and Paperless are automatic AND addable by
#          hand now (the add switches the setting On); every refusal asserted
#          here is on MUNI (Municipal account) and stands unchanged. The new
#          behaviour is `tests/test_def_rat_9833_autopay_paperless_kept_matched.py`.
# ───────────────────────────────────────────────────────
"""**The manual door refuses an automatic discount; move-in evidence lands on
the enrolment it supports, unverified.**

Worked, on one plan carrying SENIOR (apply and approve, 15% off), CAP (apply
and approve, proof first, accepts an award letter or an agency file, 10% off)
and MUNI (automatic, *Government or municipal account*, 20% off):

* *+ Enroll an account* on MUNI is refused by name — *"This discount is
  applied automatically."* — and writes no enrolment; SENIOR still enrols.
* The discount page tells the screen MUNI is enrolled automatically, so the
  screen draws no *+ Enroll an account* on it.
* Harold's move-in uploads `cap-award-letter.pdf` as *Assistance evidence* and
  claims CAP. CAP enrols *pending*, and the letter is CAP's proof document —
  kind *programme award letter*, not restricted, the same file as the account's
  KYC filing card. Still pending, never verified: on a $60.00 bill CAP takes
  $0.00 off until a System Admin verifies it, then $6.00.
* The Accounts tab serves the proof to a System Admin (who verifies) and not
  to a Billing Clerk (BR-RAT-079 — restricted by role).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import discounts as customers_discounts
from apps.customers import move_in_preferences
from apps.customers.account_document_models import AccountDocument
from apps.customers import models as customers_models
from apps.identity import models as identity_models
from apps.rating import api as rating_api
from apps.rating import discount_pricing, discount_services, selectors
from apps.rating import discounts as dm
from core import errors
from tests.test_cr171_p225_move_in_documents import _Upload, docs_dir  # noqa: F401
from tests.test_def_cus_9779_automatic_discounts_not_claimable import (
    START,
    _move_in,
    _plan_with_three,
)
from tests.test_cr166_discounts_round2 import _discount
from tests.test_us_ten_helpers import api_call
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (LIHEAP award 2026) >>\n" + b"A" * 1500 + b"\n%%EOF"
EVIDENCE = customers_models.ServiceRequestDocument.DOC_ASSISTANCE_EVIDENCE
DEED = customers_models.ServiceRequestDocument.DOC_TENANCY_OR_DEED


def _user(actor):
    return identity_models.User.objects.get(pk=actor.id)


def _cap(actor, plan, *, eligibility="state_assistance_program"):
    """CAP — *In a state assistance program*, which accepts an award letter or
    an agency file (`discount_lists.PROOF_BY_ELIGIBILITY`)."""
    cap = _discount(
        actor,
        "CAP",
        value="10",
        start=START,
        eligibility=eligibility,
        proof_required=True,
        proof_before_first_reduction=True,
    )
    discount_services.attach_discount_to_plan(actor, plan.id, cap.id)
    return cap


def _stage(actor, *, name="cap-award-letter.pdf", doc_type=EVIDENCE):
    from apps.customers import move_in_documents

    return move_in_documents.stage(
        actor,
        {"doc_type": doc_type, "name": name},
        _Upload(PDF, name=name, content_type="application/pdf"),
    )


def _occupied(actor, outgoing):
    """A fresh occupant on the vacated unit — the account an Enroll door reaches."""
    return _move_in(actor, outgoing)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-RAT-9792 — the manual door
# ═══════════════════════════════════════════════════════════════════════════
def test_def_rat_9792__enrolling_by_hand_in_an_automatic_discount_is_refused(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing, senior, muni, _autopay = _plan_with_three(dana, brazos)
        account = _occupied(marcus, outgoing)
        with pytest.raises(errors.ValidationError) as raised:
            customers_discounts.claim_assistance(dana, account["id"], str(muni.id))
        assert not dm.DiscountEnrolment.objects.filter(
            discount=muni, account_id=account["id"]
        ).exists()
        # The discount a person applies for still enrols by hand.
        row = customers_discounts.claim_assistance(dana, account["id"], str(senior.id))
    assert raised.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC
    assert raised.value.field_errors[0]["field"] == "programme_id"
    assert row["claimed"] is True and row["status"] == "pending"


def test_def_rat_9792__the_enroll_endpoint_answers_422_for_an_automatic_discount(
    brazos, marcus, dana
):
    with tenant_ctx(brazos):
        _u, _p, outgoing, _senior, muni, _autopay = _plan_with_three(dana, brazos)
        account = _occupied(marcus, outgoing)
    response = api_call(
        customers_api.account_claim_assistance,
        "post",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data={"programme_id": str(muni.id)},
        account_id=account["id"],
    )
    assert response.status_code == 422, response.data
    assert response.data["field_errors"][0]["field"] == "programme_id"
    assert response.data["field_errors"][0]["message_key"] == "customers.moveIn.discountAutomatic"
    with tenant_ctx(brazos):
        assert not dm.DiscountEnrolment.objects.filter(
            discount=muni, account_id=account["id"]
        ).exists()


def test_def_rat_9792__the_discount_page_says_which_discounts_are_enrolled_automatically(
    brazos, dana
):
    with tenant_ctx(brazos):
        _u, _p, _o, senior, muni, autopay = _plan_with_three(dana, brazos)
        rows = {one.code: selectors.discount_detail(one.id) for one in (senior, muni, autopay)}
    assert rows["SENIOR"]["enrolled_automatically"] is False
    assert rows["MUNI"]["enrolled_automatically"] is True
    assert rows["AUTOPAY"]["enrolled_automatically"] is True


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9780 — the move-in's evidence lands on the enrolment it supports
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9780__the_award_letter_is_the_cap_enrolments_proof_and_stays_unverified(
    brazos, marcus, dana, docs_dir
):
    with tenant_ctx(brazos):
        _u, plan, outgoing, _senior, _muni, _autopay = _plan_with_three(dana, brazos)
        cap = _cap(dana, plan)
        letter = _stage(marcus)
        deed = _stage(marcus, name="lease.pdf", doc_type=DEED)
        result = _move_in(
            marcus,
            outgoing,
            documents=[
                {"card_id": letter["card_id"], "doc_type": EVIDENCE},
                {"card_id": deed["card_id"], "doc_type": DEED},
            ],
            discount_claims=[{"discount_id": str(cap.id)}],
        )
        enrolment = dm.DiscountEnrolment.objects.get(account_id=result["id"], discount=cap)
        proofs = list(dm.DiscountEnrolmentDocument.objects.filter(enrolment=enrolment))
        filed = AccountDocument.objects.get(pk=letter["card_id"])
        # Still the clerk's claim and the System Admin's to verify.
        assert enrolment.verification_status == dm.VERIFICATION_PENDING
        assert enrolment.verified_on is None and enrolment.verified_by_id is None
        lines = (
            discount_pricing.BillLine(service="electric", kind="usage", amount=Decimal("60.00")),
        )
        before = discount_services.price_account_discounts(
            result["id"], lines, on_day=enrolment.enrolled_on
        )
        discount_services.verify_enrolment(dana, enrolment.id)
        after = discount_services.price_account_discounts(
            result["id"], lines, on_day=enrolment.enrolled_on
        )
    # ONE proof — the letter, not the lease — pointing at the account's filing card.
    assert len(proofs) == 1
    assert proofs[0].reference == letter["card_id"]
    assert str(filed.account_id) == str(result["id"])
    assert proofs[0].kind == "programme_award_letter"
    assert proofs[0].restricted is False
    assert proofs[0].uploaded_by_id == marcus.user.id
    # The credit takes nothing off until it is verified, then 10% of $60.00.
    assert before.total_reduction().quantize(Decimal("0.01")) == Decimal("0.00")
    assert after.total_reduction().quantize(Decimal("0.01")) == Decimal("6.00")


def test_def_cus_9780__an_income_first_programme_files_the_evidence_as_restricted(
    brazos, marcus, dana, docs_dir
):
    with tenant_ctx(brazos):
        _u, plan, outgoing, _senior, _muni, _autopay = _plan_with_three(dana, brazos)
        cap = _cap(dana, plan, eligibility="household_income_limit")
        letter = _stage(marcus, name="pay-stubs.pdf")
        result = _move_in(
            marcus,
            outgoing,
            documents=[{"card_id": letter["card_id"], "doc_type": EVIDENCE}],
            discount_claims=[{"discount_id": str(cap.id)}],
        )
        proof = dm.DiscountEnrolmentDocument.objects.get(
            enrolment__account_id=result["id"], enrolment__discount=cap
        )
    assert proof.kind == "income_statement"
    assert proof.restricted is True


def test_def_cus_9780__the_accounts_tab_shows_the_proof_to_the_verifier_only(
    brazos, marcus, dana, docs_dir
):
    with tenant_ctx(brazos):
        _u, plan, outgoing, _senior, _muni, _autopay = _plan_with_three(dana, brazos)
        cap = _cap(dana, plan)
        letter = _stage(marcus)
        _move_in(
            marcus,
            outgoing,
            documents=[{"card_id": letter["card_id"], "doc_type": EVIDENCE}],
            discount_claims=[{"discount_id": str(cap.id)}],
        )

    def read(actor, role):
        response = api_call(
            rating_api.discount_accounts,
            "get",
            user=_user(actor),
            role=role,
            tenant=brazos,
            discount_id=str(cap.id),
        )
        assert response.status_code == 200, response.data
        return response.data["results"] if "results" in response.data else response.data["rows"]

    admin_rows = read(dana, "system_admin")
    clerk_rows = read(marcus, "billing_clerk")
    assert [row["status"] for row in admin_rows] == ["proof_pending"]
    assert admin_rows[0]["proof_document_id"] == letter["card_id"]
    assert clerk_rows[0]["proof_document_id"] is None


# ═══════════════════════════════════════════════════════════════════════════
# SIGNED 2026-10-06 — the statement the PO approved, figure for figure
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_the_po_signed_on_2026_10_06(brazos, marcus, dana, docs_dir):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S3, shown as:
    *"Harold's low-income letter uploaded at move-in now sits on his CAP
    enrolment, so the System Admin verifying it sees it there; the 10% CAP
    credit — $6.00 on a $60.00 bill — still applies only once it is verified.
    Nobody can add an account to Autopay, Paperless or Municipal account by
    hand."*

    ⚠ **THE SECOND SENTENCE IS SUPERSEDED FOR AUTOPAY AND PAPERLESS** by the
    PO's ruling D2 (b) of the same day (Autopay and Paperless are offered at
    move-in and addable on the account), so this test asserts ONLY the
    Municipal-account half of it. Asserting the Autopay half here would pin a
    signed figure that a later signed ruling reversed.
    """
    with tenant_ctx(brazos):
        _u, plan, outgoing, _senior, muni, _autopay = _plan_with_three(dana, brazos)
        cap = _cap(dana, plan)
        letter = _stage(marcus)
        harold = _move_in(
            marcus,
            outgoing,
            documents=[{"card_id": letter["card_id"], "doc_type": EVIDENCE}],
            discount_claims=[{"discount_id": str(cap.id)}],
        )
        enrolment = dm.DiscountEnrolment.objects.get(account_id=harold["id"], discount=cap)
        bill = (
            discount_pricing.BillLine(service="electric", kind="usage", amount=Decimal("60.00")),
        )
        unverified = discount_services.price_account_discounts(
            harold["id"], bill, on_day=enrolment.enrolled_on
        )
        # Municipal account cannot be added by hand.
        with pytest.raises(errors.ValidationError) as refused:
            customers_discounts.claim_assistance(dana, harold["id"], str(muni.id))
        assert not dm.DiscountEnrolment.objects.filter(
            discount=muni, account_id=harold["id"]
        ).exists()
    assert refused.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC

    # The System Admin verifying it sees the letter on his CAP enrolment.
    response = api_call(
        rating_api.discount_accounts,
        "get",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        discount_id=str(cap.id),
    )
    assert response.status_code == 200, response.data
    rows = response.data["results"] if "results" in response.data else response.data["rows"]
    assert [row["proof_document_id"] for row in rows] == [letter["card_id"]]

    with tenant_ctx(brazos):
        discount_services.verify_enrolment(dana, enrolment.id)
        verified = discount_services.price_account_discounts(
            harold["id"], bill, on_day=enrolment.enrolled_on
        )
    # 10% of $60.00 = $6.00, and only once verified.
    assert unverified.total_reduction().quantize(Decimal("0.01")) == Decimal("0.00")
    assert verified.total_reduction().quantize(Decimal("0.01")) == Decimal("6.00")
