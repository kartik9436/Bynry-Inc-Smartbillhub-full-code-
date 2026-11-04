# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6365 — the move-in review drew a 60-word *"will not write"*
#           paragraph and a *"Nothing is delivered"* block where the Accounts
#           blueprint (p077) draws the customer's messages. PO 2026-09-23:
#           *"reduce this text; As per drawing you are not showing consumer
#           communication related items email, contract, text , inapp message
#           taht will be sent to cutomer once move-in is approve"*.
# Rules:    BR-NOT-013 (nothing is dispatched — so the plan describes QUEUE
#           writes and never a delivery) · BR-NOT-022 (the receipt election) ·
#           BR-NOT-002 (a contract version is effective-dated and cannot be
#           seeded) · B1 (notifications may not import payments) ·
#           `OQ-CUS-12619` (a) (messages take the UTILITY's language)
# ───────────────────────────────────────────────────────
"""What the move-in review is told will go out, and why each row is there.

⚠ **THE FIRST CASE EXISTS BECAUSE A DOCSTRING PROMISED IT AND NOTHING KEPT IT**
— hard-won law 1, exactly. `customer_events.RECEIPT_CHANNEL_TEMPLATES` says in
its own comment that *"`test_def_cus_6365` asserts they equal
`receipts.RECEIPT_TEMPLATE_CODE` and its two siblings, so the two lists cannot
drift apart silently"*. **No such test existed** when that comment was written;
this is it. The list is duplicated on purpose — B1 forbids notifications
importing payments — so a duplicate with nothing holding it together is a
second opinion waiting to happen.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** a plan that returned a row per
POSSIBLE message rather than per message this save really queues would satisfy
any check that only counts rows. So each case asserts the KEYS and their ORDER
against the deposit answers that produce them, and the contract case asserts an
EMPTY channel list — the one row that is present and goes nowhere.
"""

import uuid

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """The store's own tenant-context fixture, reused verbatim."""
    from django.db import connection as real_connection

    from core import tenancy as core_tenancy
    from tests.test_us_ten_helpers import FakeGucConnection

    if real_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", FakeGucConnection())
    core_tenancy._current_tenant.set(None)
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def utility(db):
    from apps.tenancy.models import Tenant

    return Tenant.objects.create(
        name="Brazos Bend Utilities", subdomain=f"brazos{uuid.uuid4().hex[:8]}"
    )


def _plan(**kwargs):
    from apps.customers import notifications_seam

    return notifications_seam.move_in_message_plan(
        category=kwargs.pop("category", None),
        deposit_taken=kwargs.pop("deposit_taken", False),
        deposit_cleared=kwargs.pop("deposit_cleared", False),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  THE DUPLICATED LIST — the comment's own promise, kept
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_template_list_matches_the_one_payments_actually_writes():
    from apps.notifications import customer_events
    from apps.payments import receipts

    assert customer_events.RECEIPT_EVENT == receipts.EVENT_PAYMENT_RECEIVED
    assert customer_events.RECEIPT_CHANNEL_TEMPLATES == (
        (receipts.CHANNEL_PRINT, receipts.RECEIPT_TEMPLATE_CODE),
        (receipts.CHANNEL_EMAIL, receipts.EMAIL_RECEIPT_TEMPLATE_CODE),
        (receipts.CHANNEL_SMS, receipts.SMS_RECEIPT_TEMPLATE_CODE),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  THE PLAN — one row per write the save really makes
# ═══════════════════════════════════════════════════════════════════════════


def test_a_move_in_with_no_deposit_plans_the_welcome_and_the_contract(utility):
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        rows = _plan()
    assert [row["key"] for row in rows] == ["move_in_welcome", "service_agreement"]


def test_a_deposit_taken_adds_the_receipt_and_keeps_p077s_order(utility):
    # p077 draws three ticked rows in this order: the welcome, the receipt for
    # the deposit, the service agreement. A move-in that takes a deposit and
    # does not clear it on the day is exactly that picture.
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        rows = _plan(deposit_taken=True)
    assert [row["key"] for row in rows] == [
        "move_in_welcome",
        "payment_received",
        "service_agreement",
    ]


def test_a_deposit_that_also_clears_adds_the_deposit_letter(utility):
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        rows = _plan(deposit_taken=True, deposit_cleared=True)
    assert [row["key"] for row in rows] == [
        "move_in_welcome",
        "payment_received",
        "deposit_received",
        "service_agreement",
    ]


def test_the_contract_is_listed_and_goes_out_by_email(utility):
    """The row the PO named — *contract* — and the one fact about it.

    ⚠ **RE-POINTED 2026-10-05 (`DEF-CUS-9743`).** This case read
    `..._goes_out_on_nothing` and asserted `channels == []`, which pinned the
    defect: CR-171 P1.20 and images 45/46 make the service agreement one of the
    two defaults a move-in always sends, and Complete now queues it
    (`queue_move_in_service_agreement`) on the contract class's own PRINT
    channel, with no event key. The plan names that channel, from the same
    channel decision the write takes.
    """
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        rows = _plan()
    contract = next(row for row in rows if row["key"] == "service_agreement")
    # ⚠ **RE-POINTED AGAIN 2026-10-22 (CR-190-BRC10, PO answer 1: *"email it as
    # a PDF attachment (plus a letter if the customer wants paper)"*).** The
    # move-in now sends a click-to-accept request by EMAIL; the letter is added
    # per account at Complete for a customer who is not paperless, and the
    # held PRINT letter is the fallback only where nothing is published
    # (`customer_events.SERVICE_AGREEMENT_UNPUBLISHED_CHANNELS`).
    assert contract["channels"] == ["email"]
    assert contract["allowed_channels"] == ["email", "pdf_print"]
    # On a utility that has published no contract version — which is every
    # freshly seeded one, because `BR-NOT-002` refuses to seed an effective
    # date nobody chose — the template is absent rather than invented.
    assert contract["template"] is None


def test_every_row_answers_the_three_keys_the_review_reads(utility):
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        rows = _plan(deposit_taken=True, deposit_cleared=True)
    for row in rows:
        # ⊕ CR-190-BRC10 (PO 2026-10-22, *"allow untick and channel change per
        # move-in"*) — the two defaults Complete writes also say what the clerk
        # may change; the payment's two rows stay facts with the three keys.
        if row["key"] in ("move_in_welcome", "service_agreement"):
            assert set(row) == {"key", "channels", "template", "editable", "allowed_channels"}
            assert row["editable"] is True and row["allowed_channels"]
        else:
            assert set(row) == {"key", "channels", "template"}, row
        assert isinstance(row["channels"], list)
        assert row["template"] is None or set(row["template"]) == {"code", "name", "version"}


# ═══════════════════════════════════════════════════════════════════════════
#  THE DOOR — `GET /move-ins/messages`
# ═══════════════════════════════════════════════════════════════════════════


def test_the_endpoint_says_whether_notifications_answered_at_all(utility, monkeypatch):
    """`served` is not decoration: an empty `results` with `served: true` means
    *nothing goes out*, and with `served: false` means *we could not ask*. The
    review draws a different thing for each, so the two cannot share a shape."""
    from apps.customers import notifications_seam

    monkeypatch.setattr(notifications_seam, "_resolve", lambda _name: None)
    assert notifications_seam.move_in_message_plan(
        category=None, deposit_taken=False, deposit_cleared=False
    ) is None
