# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10480 — the property-sale emails printed the sale date as
#           ISO `2026-10-22` in the subject and body
# Rules:    US-NOT-005 TC-3 (dates in the tenant's Regional format) ·
#           BR-TEN-017 (the utility's identity stamped at render)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A sale's emails state the date in the utility's own Regional format.**

REPRODUCED BEFORE THE FIX (law 7): with `sold_on` passed as
`sold_on.isoformat()`, the buyer's subject rendered
``Account AC-10480 is yours from 2026-10-22`` on a tenant set to MM/DD/YYYY —
the renderer formats dates by TYPE, and a string is not a date.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a tenant left on the
default format. ISO is also the renderer's FALLBACK, so on an unset tenant the
broken and the fixed code print the same string. Every case here sets
MM/DD/YYYY first, and asserts the ISO string is ABSENT as well as the formatted
one present.

The rows are rendered through `render_for_dispatch` — the dispatcher's own path,
reading the JSON column — so the date has to survive the queue's round trip,
not only the helper that built the context.

The phone half of the report (`Call ——`) is DATA, not code: `support_phone`
is filled from Settings → Company like `support_email`, and signup leaves it
empty on purpose (CR-010 10.3) while it seeds the email from the owner's
address. The last case pins that, so the cause stays written down as a test.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.notifications import models, rendering, transfer_events
from apps.tenancy import models as tenancy_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SOLD_ON = date(2026, 10, 22)
ISO = "2026-10-22"
US = "10/22/2026"
PHONE = "+1 (281) 555-0164"


def _regional(tenant, date_format: str) -> None:
    row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=tenant.id)
    row.date_format = date_format
    row.save(update_fields=["date_format"])


def _phone(tenant, phone: str | None) -> None:
    tenancy_models.Tenant.objects.filter(pk=tenant.pk).update(
        support_phone=phone, support_email="help@brazosbend.example"
    )


def _rendered(message: transfer_events.TransferMessage) -> rendering.RenderedArtifact:
    row = models.OutboundMessage.objects.get(pk=message.message_id)
    return rendering.render_for_dispatch(row)


def _queue_both(account_id=None):
    transfer_id = uuid4()
    buyer = transfer_events.queue_transfer_to_buyer(
        transfer_id=transfer_id,
        account_id=account_id,
        account_no="AC-10480",
        buyer_customer_id=None,
        buyer_name="Moreno, Alex",
        buyer_email="alex@example.test",
        service_address="12 Oak Lane",
        sold_on=SOLD_ON,
    )
    seller = transfer_events.queue_transfer_to_seller(
        transfer_id=transfer_id,
        account_no="AC-10480",
        seller_customer_id=None,
        seller_name="Ng, Sam",
        seller_email="sam@example.test",
        service_address="12 Oak Lane",
        sold_on=SOLD_ON,
    )
    visit = transfer_events.queue_transfer_field_visit(
        transfer_id=transfer_id,
        account_id=account_id,
        account_no="AC-10480",
        buyer_customer_id=None,
        buyer_name="Moreno, Alex",
        buyer_phone="+15125550100",
        service_address="12 Oak Lane",
        sold_on=SOLD_ON,
    )
    return buyer, seller, visit


def test_the_sale_date_is_stored_as_a_date_on_the_queue_row(brazos):
    with tenant_ctx(brazos):
        buyer, seller, visit = _queue_both()
        for message in (buyer, seller, visit):
            row = models.OutboundMessage.objects.get(pk=message.message_id)
            stored = rendering.decode_context(row.render_context)
            assert stored["sold_on"] == SOLD_ON, message.template_code


def test_both_emails_print_the_regional_date_in_subject_and_body(brazos):
    with tenant_ctx(brazos):
        _regional(brazos, "MM/DD/YYYY")
        _phone(brazos, PHONE)
        buyer, seller, _visit = _queue_both()
        to_buyer = _rendered(buyer)
        to_seller = _rendered(seller)

    assert to_buyer.subject == f"Account AC-10480 is yours from {US}"
    assert f"is in your name from {US}." in to_buyer.body
    assert f"passed to the new owner on {US}." in to_seller.body
    assert f"up to {US} is still" in to_seller.body
    for artifact in (to_buyer, to_seller):
        assert ISO not in (artifact.subject or ""), artifact.template_code
        assert ISO not in artifact.body, artifact.template_code
        assert f"Call {PHONE} or write to help@brazosbend.example." in artifact.body
        assert rendering.ABSENT_MARK not in artifact.body, artifact.template_code
        assert rendering.ABSENT_MARK not in (artifact.subject or "")


def test_the_meter_visit_text_prints_the_regional_date_too(brazos):
    with tenant_ctx(brazos):
        _regional(brazos, "DD/MM/YYYY")
        _phone(brazos, PHONE)
        _buyer, _seller, visit = _queue_both()
        text = _rendered(visit)
    assert "for 22/10/2026." in text.body
    assert ISO not in text.body
    assert rendering.ABSENT_MARK not in text.body


def test_an_empty_settings_phone_is_the_only_reason_the_phone_prints_a_dash(brazos):
    """The report's `Call ——` — Settings → Company → Support phone was empty.

    Same code, same row: with the setting blank the mark appears exactly where
    the phone goes, and nowhere else.
    """
    with tenant_ctx(brazos):
        _regional(brazos, "MM/DD/YYYY")
        _phone(brazos, None)
        buyer, _seller, _visit = _queue_both()
        artifact = _rendered(buyer)
    assert f"Call {rendering.ABSENT_MARK} or write to help@brazosbend.example." in artifact.body
    assert [absence["token"] for absence in artifact.absences] == ["support_phone"]
