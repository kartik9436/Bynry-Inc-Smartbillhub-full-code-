# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W2 tasks 8 and 10 — the two blocks A19 describes, the
#          document has always asked for, and the snapshot has never carried:
#          the TWELVE-MONTH usage history (§1.7) and the tenant's BILL MESSAGE
#          + WAYS TO PAY (§1.8 / BR-BIL-021).
# Rules:   BR-BIL-030 (the bill is LOCKED at issue and the document joins
#          nothing live) · BR-BIL-026 (template + version are PINNED; a reprint
#          renders THAT version) · BR-BIL-021 (the tenant's bill messages and
#          footer) · BR-MET-106 (the stored monthly grain: an unread month is
#          ABSENT, never 0) · BR-BIL-055 (a break never blocks the run) ·
#          BR-TEN-043 (the caller names the business date; no clock read) ·
#          A19 §1.7 · A19 §1.8
# Tests:   this file
# Impacts: apps/billing/issue.py (`_stamp_usage_history`, `_stamp_bill_copy`) ·
#          apps/billing/metering_seam.py (`usage_history_for`) ·
#          apps/billing/documents.py (the two rewritten absences)
# ───────────────────────────────────────────────────────
"""The two blocks the bill could not print, and the two absences they replace.

⚠ **BOTH OF THESE WERE HONEST NAMED HOLES AND BOTH ARE NOW CLOSED**, so the
tests here are as much about the ABSENCES being withdrawn as about the data
arriving — hard-won law 1 runs in both directions, and a build that kept
reporting an absence it had closed would be lying the other way:

  * `documents.DOCUMENT_UNAVAILABLE`'s `usage_history_not_available` said the
    eleven earlier periods were not in the snapshot and that reading them from
    `meter_reads` *"would be the live join BR-BIL-030 forbids"*. Both clauses
    were true. `issue._stamp_usage_history` freezes BR-MET-106's stored grain
    onto the bill instead, so the periods are IN the snapshot and no join
    happens at render time.
  * `documents._footer`'s two fields said *"Neither is stamped"*, with the
    consequence named: the late-fee terms this product charges never reached
    the paper. They are stamped now, from the PINNED template version's own
    `options` — BR-BIL-021's ratified home for a tenant's bill copy.

**WHY THE STAMPS ARE AT ISSUE AND NOT AT DRAFT** is asserted rather than
described (`test_task8_the_window_ends_at_the_bills_own_period`): the window
ends at the BILL's period end, so a June bill issued in September carries
June's twelve months and a reprint in 2033 carries the same twelve.
"""

from __future__ import annotations

import pytest

from apps.billing import documents, issue, metering_seam
from apps.billing.template_models import BillTemplate, BillTemplateVersion

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_bil_022_documents import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def a_pinned_template_version(tenant, *, options):
    """The row the bill's pin names, carrying the tenant's own bill copy.

    Written at the EXACT `TEMPLATE_ID` / `TEMPLATE_VERSION` the issue fixture
    pins, because BR-BIL-026 is the whole point: `_stamp_bill_copy` looks up
    the PIN and must find nothing when the pin names no row.
    """
    template = BillTemplate.objects.create(
        tenant=tenant, id=TEMPLATE_ID, name="Silver Creek bill", template_type="bill"
    )
    return BillTemplateVersion.objects.create(
        tenant=tenant,
        template=template,
        version_no=TEMPLATE_VERSION,
        status="published",
        layout_key="classic",
        options=options,
    )


# ══════════════════════════════════════════════════════════════════════════
# Task 8 — the twelve-month usage block
# ══════════════════════════════════════════════════════════════════════════


def test_task8_the_block_is_frozen_onto_the_bill_at_issue(brazos, dana):
    """A19 §1.7 — `bill_payload.usage_history` exists and is metering's answer.

    The account has no stored months in this fixture, and the assertion is
    deliberately that the block is PRESENT AND EMPTY rather than absent:
    BR-MET-106's own law is that an unread month is ABSENT, never `0`, and the
    payload states that as a window with no series instead of leaving the
    reader to guess whether the bill simply predates the feature.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        bill = an_issued_bill(brazos, dana, account=account)

        block = (bill.bill_payload or {}).get("usage_history")
        assert isinstance(block, dict), "the twelve-month block was not stamped at issue"
        assert block["window"]["months"] == metering_seam.USAGE_HISTORY_MONTHS == 12
        assert block["rule_ref"] == "BR-MET-106"
        assert block["series"] == [], "an account with no stored months draws no series"


def test_task8_the_window_ends_at_the_bills_own_period_never_at_today(brazos, dana):
    """BR-TEN-043 — the bill's period end decides the axis, not a clock.

    The fixture's bill covers June 2026 and is issued in July. The last month
    on the axis must be **2026-06**: a reprint years later has to show the
    twelve months as they stood when the bill was sent, and an axis anchored on
    `date.today()` would silently redraw every historical bill.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        window = (bill.bill_payload or {})["usage_history"]["window"]
        assert window["to"] == "2026-06", (
            "the usage window ended somewhere other than the bill's own period end — "
            f"got {window['to']!r}; an axis read off a clock rewrites history"
        )
        assert window["from"] == "2025-07", "twelve months back from 2026-06 is 2025-07"


def test_task8_an_unreachable_seam_reports_and_still_issues_the_bill(brazos, dana, monkeypatch):
    """BR-BIL-055 — the chart is a courtesy, the bill is the money."""
    monkeypatch.setattr(metering_seam, "USAGE_PAYLOAD", "no_such_read_model")
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert bill.status == "issued"
        assert "usage_history" not in (bill.bill_payload or {})
        codes = {problem["code"] for problem in bill.snapshot_problems}
        assert "usage_history_seam_unpublished" in codes


def test_task8_a_refusal_from_metering_never_loses_a_bill(brazos, dana, monkeypatch):
    """The other failure shape: the seam resolves and then raises."""

    def _boom(*args, **kwargs):
        raise RuntimeError("metering is having a bad day")

    from apps.metering import monthly_usage_reads

    monkeypatch.setattr(monthly_usage_reads, "usage_payload", _boom)
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert bill.status == "issued"
        codes = {problem["code"] for problem in bill.snapshot_problems}
        assert "usage_history_unreadable" in codes


def test_task8_the_document_no_longer_claims_the_history_is_unavailable(brazos, dana):
    """Hard-won law 1 in both directions — BOTH absences are now withdrawn.

    ⚠ **AMENDED 2026-08-31 (CR-052 task 9), AND THE OLD ASSERTION IS QUOTED
    RATHER THAN QUIETLY FLIPPED.** This case used to read
    `assert "usage_history_stamped_but_not_drawn" in codes`, because when task 8
    landed the block was frozen onto the bill and NOTHING drew it — none of the
    five platform layouts had a chart, and `documents.py` said so by name.

    Task 9 draws it, in both serialisations and on all five layouts, so that
    sentence stopped being true and was DELETED in the same commit that made it
    so (the `pdf_not_rendered` precedent of 2026-08-11). A build that kept
    reporting an absence it had closed would be lying the other way, which is
    the whole reason this case exists.

    **This test going RED is what proved the deletion was load-bearing** — it
    failed on the first run after the entry was removed, which is exactly what a
    stated absence is for.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        document = documents.render_invoice(bill)
        codes = {entry["code"] for entry in document.unavailable}
        assert "usage_history_not_available" not in codes
        assert "usage_history_stamped_but_not_drawn" not in codes


# ══════════════════════════════════════════════════════════════════════════
# Task 10 — the tenant's bill message and ways to pay
# ══════════════════════════════════════════════════════════════════════════


def test_task10_the_tenants_copy_is_frozen_from_the_PINNED_version(brazos, dana):
    """BR-BIL-021 + BR-BIL-026 — the tenant's own words reach the paper.

    The message carries the late-fee terms, which is CR-052's named
    consequence: *"the late-fee terms the product is required to print are
    charged correctly and never disclosed on the paper."* They are the tenant's
    words and this is what carries them.
    """
    terms = "A late fee of the greater of $5.00 or 1.5% applies after a 5-day grace period."
    with tenant_ctx(brazos):
        a_pinned_template_version(
            brazos,
            options={"bill_message": terms, "ways_to_pay": "Online, by phone, or by post."},
        )
        bill = an_issued_bill(brazos, dana)

        payload = bill.bill_payload or {}
        assert payload["message"] == terms
        assert payload["ways_to_pay"] == "Online, by phone, or by post."
        assert bill.snapshot_problems == () or all(
            problem["code"] != "tenant_has_written_no_bill_copy"
            for problem in bill.snapshot_problems
        )

        document = documents.render_invoice(bill)
        message = next(field for field in document.footer if field.label == "Message")
        assert message.value == terms
        assert message.absent is None
        assert terms in document.body


def test_task10_a_tenant_who_has_written_nothing_gets_a_named_absence_not_a_blank(brazos, dana):
    """An empty message is stamped as an ABSENCE, never as an empty string.

    A tenant who has typed nothing has said nothing, and a bill printing a
    blank line under "Message" claims otherwise. The run is told once, by name,
    with the one edit that fixes it.
    """
    with tenant_ctx(brazos):
        a_pinned_template_version(brazos, options={"bill_message": "   "})
        bill = an_issued_bill(brazos, dana)

        assert (bill.bill_payload or {})["message"] is None
        assert (bill.bill_payload or {})["ways_to_pay"] is None
        codes = {problem["code"] for problem in bill.snapshot_problems}
        assert "tenant_has_written_no_bill_copy" in codes

        document = documents.render_invoice(bill)
        message = next(field for field in document.footer if field.label == "Message")
        assert message.absent is not None
        assert message.absent.br_ref == "BR-BIL-021"


def test_task10_a_bill_whose_pin_names_no_row_still_issues(brazos, dana):
    """Every bill issued before the template library landed is this case.

    BR-BIL-026 says a reprint renders what was sent, and what was sent carried
    no message. It must not refuse and it must not borrow today's copy.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        assert bill.status == "issued"
        assert (bill.bill_payload or {})["message"] is None


def test_task10_a_later_published_version_never_reaches_an_issued_bill(brazos, dana):
    """BR-BIL-026 made concrete on the COPY, not just on the layout.

    The tenant rewrites their message after the bill goes out. The bill is
    immutable and its payload was frozen at issue, so the document still prints
    what the customer was sent — asserted through the RENDER, because that is
    where a live join would show up.
    """
    with tenant_ctx(brazos):
        version = a_pinned_template_version(brazos, options={"bill_message": "Original words."})
        bill = an_issued_bill(brazos, dana)

        BillTemplateVersion.objects.filter(pk=version.pk).update(
            options={"bill_message": "Rewritten words."}
        )

        document = documents.render_invoice(bill)
        message = next(field for field in document.footer if field.label == "Message")
        assert message.value == "Original words."
        assert "Rewritten words." not in document.body


def test_task10_the_option_key_vocabulary_is_stated_in_one_place(brazos, dana):
    """`bill_template_versions.options` has no validator, so the two key names
    are the whole contract between the Templates screen and the bill.

    Asserted as DATA so a rename cannot happen on one side only — which is the
    single way this feature can silently stop working, since a message stored
    under a third name reads exactly like a tenant who typed nothing.
    """
    assert issue.BILL_COPY_KEYS == (
        ("bill_message", "message"),
        ("ways_to_pay", "ways_to_pay"),
    )
