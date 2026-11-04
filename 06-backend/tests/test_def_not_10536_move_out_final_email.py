# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10536 — the move-out final bill email printed dashes and
#           carried no PDF
# Ruling:   PO 2026-10-22, decision log *"Move-out final bill email: sent at
#           completion with the draft figures, at normal priority (no instant
#           email); details and PDF filled in"*, and the judgments entry after it
# Rules:    CLAUDE.md hard rule 2 (amounts 2dp with the currency) · hard rule 3
#           (every reading with its unit) · rule 6 (one email per move-out) ·
#           hard-won law 14 (the savepoint render, proved on PostgreSQL)
# ───────────────────────────────────────────────────────
"""DEF-NOT-10536 — the move-out email is RENDERED here, never just counted.

Every earlier test of this email asserted a row was queued, and every one of
them passed over a body that read *"Hi ——"* with no PDF. So each case below
renders the queued row (`rendering.render_for_dispatch`) or reads its envelope.
"""

from __future__ import annotations

import importlib
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.billing import final_bill, frozen_bill
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.customers import notifications_seam
from apps.customers import services as customer_services
from apps.notifications import (
    attachments,
    catalogs,
    customer_events,
    move_out_wording,
    rendering,
    seed_templates,
)
from apps.notifications import models as notification_models
from apps.notifications import services as notification_services
from apps.tenancy import document_store
from apps.tenancy import models as tenancy_models
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_def_cus_10093_move_out_drafts_the_final_bill import _send
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ABSENT = rendering.ABSENT_MARK
DUE_DAYS = 21
ARREARS = Decimal("100.00")


def _with_arrears(monkeypatch):
    """The bill's balance forward stamps ARREARS over this bill's charges.

    The fixture account's ledger arrears are not an open bill or an opening
    bucket, so BR-BIL-035 would stamp none; the stamp is widened here, at the
    one function issue and `final_bill_email` share, so the email must follow
    the page's TOTAL DUE rather than `invoices.total` to pass.
    """
    from apps.billing import issue

    original = issue._stamp_balance_forward

    def stamped(invoice, *, currency, due_date=None):
        block = original(invoice, currency=currency, due_date=due_date)
        payload = dict(invoice.bill_payload or {})
        payload["total_due"] = str(Decimal(str(invoice.total)) + ARREARS)
        invoice.bill_payload = payload
        invoice.save(update_fields=["bill_payload", "updated_at"])
        return block

    monkeypatch.setattr(issue, "_stamp_balance_forward", stamped)


@pytest.fixture(autouse=True)
def _days_to_pay(monkeypatch):
    """The cycle's days to pay, through metering's own read (DEF-CUS-10093's fixture)."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "06-S", "name": "Cycle 06", "due_days": DUE_DAYS},
    )


def _ready(tenant, actor, monkeypatch, *, asset_no, account_no, arrears=None):
    """A billable account read on the move day, with a named, reachable customer."""
    tenancy_models.Tenant.objects.filter(pk=tenant.pk).update(support_phone="+1 512 555 0100")
    seed_templates.seed_notice_templates(actor, on_date=MOVE_OUT)
    account = _a_moving_out_account(
        tenant, actor, monkeypatch, asset_no=asset_no, account_no=account_no, arrears=arrears
    )
    customer_models.Contact.objects.create(
        tenant=tenant,
        account=account,
        full_name="Okafor, Ade",
        email="ade@example.test",
        is_primary=True,
    )
    return account


def _emails(tenant, account):
    return notification_models.OutboundMessage.objects.filter(
        tenant=tenant,
        account_id=account.id,
        template_code=customer_events.TEMPLATE_MOVE_OUT,
        channel=notification_models.CHANNEL_EMAIL,
    )


def _move_out(actor, account):
    return customer_services.move_out(actor, account.id, {"moved_out_on": MOVE_OUT.isoformat()})


def _date_format():
    from apps.notifications import tenancy_seam

    formats, _ = tenancy_seam.regional_formats()
    return formats.get("date_format") or rendering.ISO_DATE_FORMAT


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE TOKENS AND THE ATTACHMENT
# ══════════════════════════════════════════════════════════════════════════


def test_the_email_carries_the_customer_the_reads_the_draft_figures_and_its_pdf(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        account = _ready(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9401",
            account_no="A-14001",
        )
        _with_arrears(monkeypatch)
        result = _move_out(dana, account)
        drafted = result["final_bill"]
        assert drafted["outcome"] == "drafted", drafted
        (row,) = _emails(brazos, account)
        artifact = rendering.render_for_dispatch(row)
        named = attachments.named(row.recipient_snapshot)
        pdf = document_store.fetch(named[0]["document_id"]) if named else b""
        invoice = billing_models.Invoice.objects.get(pk=drafted["invoice_id"])
        fmt = _date_format()

    body = artifact.body
    assert ABSENT not in body, body
    assert artifact.absences == (), artifact.absences
    assert body.startswith("Hi Ade,"), body
    assert "M-9401 Bluestem Ln" in body  # the service address, walked to the premises
    # Hard rule 3: the closing reading WITH its unit, one line per meter.
    assert "M-9401: 14100 kWh" in body, body
    # The DRAFT's total, as money in the utility's region (2dp, symbol).
    # The TOTAL DUE the page prints — the arrears PLUS this bill — never the
    # current charges alone (the browser walk caught $388.98 beside 576.90).
    total = rendering.format_money(invoice.total + ARREARS, invoice.currency, locale="en_US")
    current_only = rendering.format_money(invoice.total, invoice.currency, locale="en_US")
    assert f"Total due {current_only} " not in body
    assert (
        f"Total due {total} by {rendering.format_date(MOVE_OUT + timedelta(days=DUE_DAYS), fmt)}"
        in body
    ), body
    assert rendering.format_date(MOVE_OUT, fmt) in body
    assert "+1 512 555 0100" in body
    # The PDF, stored write-once under the EMAIL row and named on it.
    assert [item["filename"] for item in named] == [f"{invoice.invoice_no}.pdf"]
    assert named[0]["content_type"] == "application/pdf"
    assert pdf.startswith(b"%PDF"), pdf[:20]


def test_the_draft_is_unchanged_and_the_attached_page_is_the_page_issue_keeps(
    brazos, dana, monkeypatch
):
    """Decision log point 1: the issue-time stamps are rolled back, and the
    page attached is the page issue keeps — a stamp added to issue and not to
    `final_bill_email` goes red here."""
    with tenant_ctx(brazos):
        account = _ready(brazos, dana, monkeypatch, asset_no="M-9402", account_no="A-14002")
        result = _move_out(dana, account)
        invoice = billing_models.Invoice.objects.get(pk=result["final_bill"]["invoice_id"])
        # Nothing issue stamps reached the draft row.
        assert invoice.status == billing_models.INVOICE_DRAFT
        assert invoice.due_date is None and invoice.template_id is None
        assert "bill_date" not in (invoice.bill_payload or {})
        (row,) = _emails(brazos, account)
        attached = document_store.fetch(attachments.named(row.recipient_snapshot)[0]["document_id"])

        run = billing_models.BillRun.objects.get(pk=invoice.bill_run_id)
        _send(run, dana)
        invoice.refresh_from_db()
        kept = frozen_bill.reproduce(invoice)
        assert kept.is_original and kept.pdf is not None
        kept_pdf = document_store.fetch(kept.pdf.id)
    assert invoice.status == billing_models.INVOICE_ISSUED
    assert invoice.due_date == MOVE_OUT + timedelta(days=DUE_DAYS)
    assert attached == kept_pdf, "the attached page is not the page the issue kept"


# ══════════════════════════════════════════════════════════════════════════
# 2 · ONCE, AT COMPLETION, AND NOT BEFORE
# ══════════════════════════════════════════════════════════════════════════


def test_it_is_queued_exactly_once_at_completion_and_not_before(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account = _ready(brazos, dana, monkeypatch, asset_no="M-9403", account_no="A-14003")
        # Step 3's preview prices the final bill and must queue nothing.
        final_bill.preview_final_bill(account_id=account.id, moved_out_on=MOVE_OUT)
        assert _emails(brazos, account).count() == 0
        result = _move_out(dana, account)
        assert _emails(brazos, account).count() == 1
        codes = {entry["code"] for entry in result["move_message"]}
        assert notifications_seam.MOVE_MESSAGE_QUEUED in codes, result["move_message"]

        # A replayed completion (the same move record) writes nothing twice.
        again = notifications_seam.queue_move_out_final(
            move_record_id=result["move_record_id"],
            account_id=account.id,
            effective_on=MOVE_OUT,
            final_bill=result["final_bill"],
            actor=dana,
        )
        assert notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED in {e["code"] for e in again}
        (row,) = _emails(brazos, account)
        assert len(attachments.named(row.recipient_snapshot)) == 1


# ══════════════════════════════════════════════════════════════════════════
# 3 · NORMAL PRIORITY — NOT AN INSTANT EMAIL
# ══════════════════════════════════════════════════════════════════════════


def test_it_goes_at_normal_priority_and_never_on_the_instant_queue(brazos, dana, monkeypatch):
    def _instant(*_a, **_k):  # pragma: no cover - the assertion is that it never runs
        raise AssertionError("the move-out email was sent instantly")

    monkeypatch.setattr(notification_services, "send_now", _instant)
    with tenant_ctx(brazos):
        account = _ready(brazos, dana, monkeypatch, asset_no="M-9404", account_no="A-14004")
        _move_out(dana, account)
        (row,) = _emails(brazos, account)
    assert row.priority == notification_models.PRIORITY_NORMAL
    assert row.status == notification_models.STATUS_QUEUED


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE EDGES THE RULING LEFT TO US (decision log, judgments 3–5)
# ══════════════════════════════════════════════════════════════════════════


def test_closing_read_lines_keep_the_unit_and_skip_what_has_no_reading():
    reads = {
        "meters": [
            {
                "asset_no": "W-5043",
                "registers": [
                    {"read_at": "2026-06-12", "current_value": "2645.000000", "unit": "kgal"},
                    {"read_at": "2026-06-01", "current_value": "2600", "unit": "kgal"},
                ],
            },
            {
                "asset_no": "E-5046",
                "registers": [
                    {"read_at": "2026-06-12", "current_value": "21550.5", "unit": "kWh"},
                    {"read_at": "2026-06-12", "current_value": None, "unit": "kW"},
                    {"read_at": "2026-06-12", "current_value": "11", "unit": ""},
                ],
            },
        ]
    }
    assert customer_events.closing_read_lines(reads, MOVE_OUT) == [
        ("W-5043: 2645 kgal", "kgal"),
        ("E-5046: 21550.5 kWh", "kWh"),
    ]
    assert customer_events.closing_read_lines(None, MOVE_OUT) == []


def test_nothing_to_bill_leaves_the_figures_out_and_attaches_nothing(brazos, dana, monkeypatch):
    from apps.customers import seams

    monkeypatch.setattr(
        seams,
        "draft_move_out_final_bill",
        lambda actor, *, account_id, moved_out_on: {"outcome": "nothing_to_bill"},
    )
    with tenant_ctx(brazos):
        account = _ready(brazos, dana, monkeypatch, asset_no="M-9405", account_no="A-14005")
        _move_out(dana, account)
        (row,) = _emails(brazos, account)
        artifact = rendering.render_for_dispatch(row)
    assert ABSENT not in artifact.body, artifact.body
    assert "attached" not in artifact.body and "Total due" not in artifact.body
    assert "M-9405: 14100 kWh" in artifact.body
    assert attachments.named(row.recipient_snapshot) == []


def test_a_draft_whose_page_cannot_be_made_queues_no_email_and_the_move_out_stands(
    brazos, dana, monkeypatch
):
    from apps.customers import seams

    monkeypatch.setattr(
        seams,
        "final_bill_email_document",
        lambda invoice_id: {"outcome": "refused", "detail": "no layout"},
    )
    with tenant_ctx(brazos):
        account = _ready(brazos, dana, monkeypatch, asset_no="M-9406", account_no="A-14006")
        result = _move_out(dana, account)
        account.refresh_from_db()
        assert account.closed_at == MOVE_OUT
        assert _emails(brazos, account).count() == 0
    assert notifications_seam.MOVE_MESSAGE_REFUSED in {e["code"] for e in result["move_message"]}


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE WORDING — eleven languages, and the migration that carries it
# ══════════════════════════════════════════════════════════════════════════


def test_every_language_variant_validates_and_keeps_its_optional_paragraphs_apart():
    table = move_out_wording.WORDING[move_out_wording.MOVE_OUT_FINAL]
    assert len(table) == 11
    optional = catalogs.catalog_for(customer_events.TEMPLATE_MOVE_OUT).optional
    assert optional == {"final_read", "total_due", "due_date"}
    for language, (subject, body) in table.items():
        rendering.validate_body(customer_events.TEMPLATE_MOVE_OUT, body, subject=subject)
        paragraphs = body.split("\n\n")
        # Each optional token sits in a paragraph that carries no required fact.
        for paragraph in paragraphs:
            tokens = set(rendering.tokens_in(paragraph))
            if tokens & optional:
                assert tokens <= optional, (language, paragraph)
        assert "{final_read}" in body and "{unit}" not in body, language


def test_the_default_wording_is_the_english_variant_and_the_migration_carries_it():
    mig = importlib.import_module(
        "apps.notifications.migrations.0028_def_not_10536_move_out_final_wording"
    )
    subject, body = move_out_wording.WORDING[move_out_wording.MOVE_OUT_FINAL]["en"]
    assert seed_templates.EMAIL_MOVE_OUT_FINAL_BODY == body == mig.NEW_BODY
    assert seed_templates.EMAIL_MOVE_OUT_FINAL_SUBJECT == subject == mig.SUBJECT
    assert "{final_read} {unit}" in mig.OLD_BODY


def test_the_migration_moves_an_untouched_copy_plants_the_languages_and_leaves_an_edit(
    brazos, dana
):
    from django.apps import apps as django_apps
    from django.db import connection

    from apps.notifications import template_models as tm

    mig = importlib.import_module(
        "apps.notifications.migrations.0028_def_not_10536_move_out_final_wording"
    )

    class _Editor:
        pass

    editor = _Editor()
    editor.connection = connection
    code = customer_events.TEMPLATE_MOVE_OUT
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=MOVE_OUT)
        template = tm.NotificationTemplate.objects.get(
            tenant=brazos, code=code, category="default", language="default"
        )
        live = tm.NotificationTemplateVersion.objects.get(template=template, status="published")
        live.status = "archived"
        live.save(update_fields=["status"])
        old = tm.NotificationTemplateVersion.objects.create(
            tenant=brazos,
            template=template,
            version=live.version + 1,
            status="published",
            subject=mig.SUBJECT,
            body=mig.OLD_BODY,
        )
        mig.forward(django_apps, editor)
    with tenant_ctx(brazos):
        old.refresh_from_db()
        now = tm.NotificationTemplateVersion.objects.get(template=template, status="published")
        assert old.status == "archived" and now.body == mig.NEW_BODY
        languages = set(
            tm.NotificationTemplate.objects.filter(tenant=brazos, code=code).values_list(
                "language", flat=True
            )
        )
        assert "default" in languages and len(languages) > 1, languages
        count = tm.NotificationTemplateVersion.objects.filter(template=template).count()
        # An EDITED copy is the utility's own wording and is left exactly alone.
        # Published as a System Admin would — a NEW version over an archived
        # one: a published body is immutable (on PostgreSQL its trigger refuses
        # an in-place edit, which is how the first draft of this case failed).
        edited_body = now.body + "\n\nP.S. Thank you."
        now.status = "archived"
        now.save(update_fields=["status"])
        tm.NotificationTemplateVersion.objects.create(
            tenant=brazos,
            template=template,
            version=now.version + 1,
            status="published",
            subject=now.subject,
            body=edited_body,
        )
        count = tm.NotificationTemplateVersion.objects.filter(template=template).count()
        mig.forward(django_apps, editor)
    with tenant_ctx(brazos):
        assert tm.NotificationTemplateVersion.objects.filter(template=template).count() == count
        assert (
            tm.NotificationTemplateVersion.objects.get(template=template, status="published").body
            == edited_body
        )


def test_the_money_and_the_unit_are_values_not_strings_on_the_queue(brazos, dana, monkeypatch):
    """Hard rule 2: the total is a Money with its currency on the queue, never
    a pre-formatted string, so the renderer writes it in the utility's region."""
    with tenant_ctx(brazos):
        account = _ready(
            brazos,
            dana,
            monkeypatch,
            asset_no="M-9407",
            account_no="A-14007",
        )
        _with_arrears(monkeypatch)
        result = _move_out(dana, account)
        (row,) = _emails(brazos, account)
        context = rendering.decode_context(row.render_context)
    total = context["total_due"]
    assert isinstance(total, rendering.Money), type(total)
    assert total.amount == Decimal(str(result["final_bill"]["total"])) + ARREARS
    assert total.currency == "USD"
    assert context["unit"] == "kWh"
