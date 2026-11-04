# ── Trace ──────────────────────────────────────────────
# Story:    CR-043 finding 1 (DEF-969) — the money-integrity alarm is red on
#           every bill and the money is correct.
#           Screens: BIL-02 Document tab -> Record check
# Rules:    BR-BIL-032 (the stamped instance ties out to its rows; drift can
#           never be silent) · BR-BIL-030 (the instance is LOCKED at issue) ·
#           BR-BIL-031 (`payload_version` is the DATA contract) ·
#           CLAUDE.md hard rule 2 (money is text, never a float in jsonb)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-043 finding 1 — the tie-out, asked of a bill THE SEEDER PRODUCED.

WHY THIS FILE EXISTS WHEN `test_us_bil_030_terminal_stages.py` ALREADY TESTS
THE TIE-OUT
----------------------------------------------------------------------------
It tests it against a payload the test itself writes:

    bill.bill_payload = {"total": "...", "lines": [...]}   # tc3

A fixture that stamps its own payload can only ever agree with itself. Stage 6
— the code that stamps the payload every real bill carries — was never asked,
and it has never written a line set at all. So the guarantee was green on
fixtures and RED on all 47 bills of the live deployment at v2.61.1, which is
where the Product Owner met it:

    "No — these do not match. Do not treat this bill as settled until someone
     has looked at it."
    "Saved bill: 64.570000 USD over 0 line(s).
     Charge lines: 64.570000 USD over 6 line(s)."

The totals were EQUAL. Only the count differed, and it differed because
`bill_payload` carried no `lines` key for `_payload_lines` to find — measured
2026-08-27 on a seeded tenant, payload keys:

    ['account_no', 'balance_forward', 'currency', 'customer_name',
     'payments_credits', 'period', 'plan', 'previous_balance', 'service_date',
     'services', 'tax_exempt', 'total_due', 'unit_id', 'unit_label']

`_payload_lines` was NOT failing to recognise a shape. The shape genuinely had
no line set, exactly as `apps/billing/issue.py`'s own exception entry says:
*"stage 6 stamps no total and no line set in the payload"*.

NON-VACUOUS, IN DEF-828's SHAPE
--------------------------------
`test_ties_out_on_a_seeded_bill` asserts `payload_line_count > 0` AND
`payload_line_count == row_line_count`. Either half alone passes over an empty
estate or over the very defect it was written for: a bill with no lines at all
would satisfy `0 == 0`, and that is precisely the state that shipped.

RED-FIRST RECORD (hard-won law 7) — run against the tree before the stamp
landed, the verbatim failure was:

    AssertionError: BL-2607-000001 does not tie out: payload 48.45 over 0
    line(s), rows 48.45 over 4 line(s)
    assert False
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.billing import models as billing_models
from apps.billing import pipeline, selectors
from apps.tenancy import sample_data

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _real_admin(tenant):
    """An actor whose id resolves to a real user row — `authorise_release`
    refuses a null `confirmed_by`, and the seeded run is authorised."""
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def _seeded_issued_bills():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
        yield tenant


def test_cr043_f1__every_seeded_bill_ties_out_non_vacuously():
    """DEF-969. The bills the product actually produces, not a hand-built dict.

    Three assertions, and the middle one is the whole point:
      * the estate is not empty (a vacuous pass is the failure mode here);
      * the payload states a line set at all — `> 0`, which is what was false;
      * the two counts agree, which is BR-BIL-032's own equality.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
        bills = list(billing_models.Invoice.objects.filter(status="issued").order_by("invoice_no"))

        assert bills, "no bill issued — this test would pass over an empty estate"

        for bill in bills:
            tie = pipeline.tie_out_document(bill)
            assert tie.payload_line_count is not None and tie.payload_line_count > 0, (
                f"{bill.invoice_no}: the stamped instance states NO line set "
                f"(payload_line_count={tie.payload_line_count}). DEF-969 — the "
                "count check then compares 0 against the rows and the alarm is "
                "red on a bill whose figures are right."
            )
            assert tie.payload_line_count == tie.row_line_count, (
                f"{bill.invoice_no} does not tie out: payload {tie.payload_total} over "
                f"{tie.payload_line_count} line(s), rows {tie.invoice_total} over "
                f"{tie.row_line_count} line(s)"
            )
            assert tie.ties_out, (
                f"{bill.invoice_no} does not tie out: payload {tie.payload_total} over "
                f"{tie.payload_line_count} line(s), rows {tie.invoice_total} over "
                f"{tie.row_line_count} line(s)"
            )


def test_cr043_f1__the_screen_reads_green_on_a_seeded_bill():
    """The same fact through the SELECTOR the bill screen actually calls.

    `pipeline.tie_out_document` going green is not the guarantee the PO met —
    `_integrity_for` is what BIL-02's Record check panel renders, and a screen
    can still say "No" over a pipeline that says yes.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
        bill = billing_models.Invoice.objects.filter(status="issued").order_by("invoice_no").first()
        assert bill is not None, "no bill issued — vacuous"
        block = selectors._integrity_for(bill)

    assert block["document_ties_out"] is True, (
        "the Record check panel still reads 'No — these do not match' on a " f"seeded bill: {block}"
    )
    assert block["payload_line_count"] == block["row_line_count"]
    assert block["payload_line_count"] > 0, "vacuous: 0 == 0 is the defect, not the fix"


def test_cr043_f1__a_payload_missing_a_line_still_fails():
    """BR-BIL-032 must stay a REFUSAL, not become a shrug (hard-won law 7).

    The fix must not be "stop comparing counts". Drop one line from a stamped
    instance and the tie-out has to go red, or DEF-969's cure is worse than the
    disease it treated.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
        bill = billing_models.Invoice.objects.filter(status="issued").order_by("invoice_no").first()
        assert bill is not None
        payload = dict(bill.bill_payload or {})
        stamped = list(payload.get("lines") or [])
        assert len(stamped) > 1, "vacuous: needs at least two stamped lines to drop one"
        # In memory only — an issued invoice is append-only (hard rule 4); this
        # is a forged READ, which is exactly TC-8's shape.
        bill.bill_payload = {**payload, "lines": stamped[:-1]}
        tie = pipeline.tie_out_document(bill)

    assert not tie.ties_out, "a payload short one line was reported as tying out"
    assert tie.payload_line_count == len(stamped) - 1
