# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2496 — BR-NOT-025 is written and NOTHING enforces it. Both pins
#           are plain columns rather than foreign keys, so the DATABASE will not
#           refuse the delete, and the two application checks disagree about
#           what they refuse.
# Rules:    BR-NOT-025 (a version any SENT DOCUMENT points at is ARCHIVED and
#           NEVER DELETED) · BR-BIL-027 (the audit-lock) · BR-BIL-026 (the pin
#           is frozen at issue) · BR-NOT-026 (one screen, two table pairs,
#           NO ROW MOVES) · CLAUDE.md hard rule 4 (financial immutability) ·
#           hard rule 1 (tenant scoping — the trigger reads inside RLS)
# Screens:  S8 · S91 · S92 · S93 (Templates)
# ───────────────────────────────────────────────────────
"""The pin guard, asserted where a shell cannot walk round it.

WHY THIS FILE EXISTS AND WHY IT IS NOT IN EITHER LIFECYCLE FILE. The two
existing lifecycle suites each prove their own SERVICE refuses a delete —
`test_us_not_006_template_lifecycle.py` TC-5 and `test_us_bil_021_templates.py`
TC-4. Both call the service function. **BR-NOT-025 is not a statement about a
service function**; it is a statement about the database, because the case it
exists for is a regulator asking to see the disconnection letter a customer was
actually sent, and a data migration or a `manage.py shell` that dropped the
version row would satisfy every existing test on the way past.

So every case here deletes through the ORM's bulk path — `.filter(pk=…)
.delete()` — which issues a bare `DELETE` and calls NO service function. That is
the shape of the shell, the data migration and the future endpoint the rule has
to survive.

⚠ **PROVED RED BEFORE THE TRIGGERS EXISTED, and the transcript is in the lane
report.** Every case here DELETED THE ROW and passed straight through the
`pytest.raises`, failing with `Failed: DID NOT RAISE`.

POSTGRES ONLY, BY `requires_postgres` AND NEVER A BARE SKIP. sqlite has no
triggers, so on the default suite these cases skip with a vendor reason. That is
hard-won law 14's shape applied to a guarantee rather than to a transaction: the
check that matters lives in the engine the product actually runs on.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.db import transaction

from apps.billing import template_models as btm
from apps.billing import templates_service
from apps.notifications import models as notification_models
from apps.notifications import services as notification_services
from apps.notifications import template_models as ntm
from apps.notifications import template_service

from tests.isolation_helpers import requires_postgres
from tests.test_us_bil_016_bulk_corrections import an_issued_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_not_006_template_lifecycle import RECEIPT_BODY, published, variant  # noqa: F401
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 30)
LAYOUT = "standard-letter-v1"


def _bill_version(actor, *, name="Bill · residential"):
    """A bill template carrying ONE draft version, ready to be pinned."""
    template = templates_service.create_template(
        name=name, template_type="bill", category="residential", actor=actor
    )
    return template, templates_service.save_draft(template, layout_key=LAYOUT, actor=actor)


# ── the bill side · a version an ISSUED BILL points at ──────────────────────
@requires_postgres
def test_def2496__a_bill_version_an_issued_bill_pins_cannot_be_deleted_by_a_bare_delete(
    brazos, dana
):
    """BR-NOT-025 on the bill side, held BELOW the service.

    `templates_service.delete_version` already refuses this and names the count.
    This case never calls it: it issues the bare `DELETE` a data migration would
    issue, which before the trigger removed the row and left one issued bill
    unreprintable with nothing anywhere reporting it.
    """
    with tenant_ctx(brazos):
        template, version = _bill_version(dana)
        account = an_account(dana, brazos)
        run = a_run(brazos)
        an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="INV-DEF2496-0001",
            template_id=str(template.pk),
            template_version=version.version_no,
        )
        assert templates_service.pin_count(version) == 1

        with pytest.raises(Exception) as refusal:  # noqa: B017 — the DB's own error type
            with transaction.atomic():
                btm.BillTemplateVersion.objects.filter(pk=version.pk).delete()
        assert "BR-NOT-025" in str(refusal.value)

        # The row is STILL THERE — the guarantee, not merely the error.
        assert btm.BillTemplateVersion.objects.filter(pk=version.pk).exists()


# ── the notification side · a DRAFT a queued message points at ──────────────
@requires_postgres
def test_def2496__a_notification_version_a_queued_message_pins_cannot_be_deleted(
    brazos, marcus, dana
):
    """The hole migration `0006`'s trigger left open, by construction.

    `trg_ntv_append_only` refuses a DELETE on any NON-DRAFT row, which covers a
    published or archived version. **A DRAFT is not covered**, and a draft CAN
    be pinned — `test_us_not_006_a_pinned_draft_is_refused_too` exists precisely
    because a caller may stamp a draft's number onto a queue row by hand. Until
    this trigger the service refused that and the database did not.
    """
    with tenant_ctx(brazos):
        template = variant(marcus, "receipt", name="Receipt")
        draft = template_service.save_draft(template=template, body=RECEIPT_BODY, actor=marcus)
        notification_services.queue_document(
            source_type="payment",
            source_id="0197b0a0-0000-7000-8000-00000000e001",
            channels=(notification_models.CHANNEL_PRINT,),
            template=notification_services.TemplatePin(
                code="receipt", template_id=template.pk, version=draft.version
            ),
            actor=dana,
        )
        assert template_service.pin_count(draft) == 1
        assert draft.status == ntm.VERSION_DRAFT  # the row the old trigger waved through

        with pytest.raises(Exception) as refusal:  # noqa: B017 — the DB's own error type
            with transaction.atomic():
                ntm.NotificationTemplateVersion.objects.filter(pk=draft.pk).delete()
        assert "BR-NOT-025" in str(refusal.value)
        assert ntm.NotificationTemplateVersion.objects.filter(pk=draft.pk).exists()


# ── the pin nobody was counting ─────────────────────────────────────────────
@requires_postgres
def test_def2496__a_bill_version_pinned_only_by_a_print_row_is_refused_too(brazos, dana):
    """⚠ `outbound_messages.template_id` IS POLYMORPHIC AND NOTHING SAID SO.

    Measured on the development database before this was written: of 181
    `outbound_messages` rows, **94 carry a BILL template's id** — every one of
    them a `pdf_print` row whose `source_type` is `invoice`. They resolve
    against `bill_template_versions`, not against
    `notification_template_versions`.

    Two things follow and both are asserted here. A printed bill is a SENT
    DOCUMENT, so BR-NOT-025 covers its pin; and `templates_service.pin_count`
    counted `invoices` ALONE, so a bill version pinned by a print row and by no
    issued invoice read as unpinned and was deletable through the service that
    exists to stop exactly that.
    """
    with tenant_ctx(brazos):
        template, version = _bill_version(dana, name="Bill · print-only")
        notification_models.OutboundMessage.objects.create(
            tenant_id=brazos.id,
            source_type="invoice",
            source_id=uuid.uuid4(),
            channel=notification_models.CHANNEL_PRINT,
            template_id=template.pk,
            template_version=version.version_no,
            # `ck_outbound_msgs_address_or_reason` — a row carries the address
            # it went to or the reason it has none. A printed bill has one.
            recipient_address="1901 Bluestem Ln, Katy TX 77494",
        )
        # The readable half now agrees with the database.
        assert templates_service.pin_count(version) == 1

        with pytest.raises(Exception) as refusal:  # noqa: B017 — the DB's own error type
            with transaction.atomic():
                btm.BillTemplateVersion.objects.filter(pk=version.pk).delete()
        assert "BR-NOT-025" in str(refusal.value)
        assert btm.BillTemplateVersion.objects.filter(pk=version.pk).exists()


# ── the contrast case · the guard is a PIN check, not a blanket ban ─────────
@requires_postgres
def test_def2496__an_unpinned_draft_still_deletes_on_both_sides(brazos, marcus, dana):
    """BR-NOT-025 protects a version a document POINTS AT and says nothing about
    one nothing points at. A trigger that refused every delete would satisfy the
    rule and break the product: T5-02 step 4 and US-BIL-021 TC-4 both ship
    *"an unpinned draft version deletes fine"*, and a guard with no passing case
    is the shape hard-won law 1 warns about.
    """
    with tenant_ctx(brazos):
        _template, bill_draft = _bill_version(dana, name="Bill · unpinned")
        btm.BillTemplateVersion.objects.filter(pk=bill_draft.pk).delete()
        assert not btm.BillTemplateVersion.objects.filter(pk=bill_draft.pk).exists()

        variant_row = variant(marcus, "receipt", name="Receipt")
        note_draft = template_service.save_draft(
            template=variant_row, body=RECEIPT_BODY, actor=marcus
        )
        ntm.NotificationTemplateVersion.objects.filter(pk=note_draft.pk).delete()
        assert not ntm.NotificationTemplateVersion.objects.filter(pk=note_draft.pk).exists()


# ── the rule's own words, held against the schema ──────────────────────────
def test_def2496__both_version_tables_carry_the_archived_at_column_br_not_025_names():
    """BR-NOT-025 requirement (2): *"`notification_template_versions.archived_at`
    already exists for this and is the pattern — `bill_template_versions` has NO
    such column and needs one"*. CR-048 task E9 added it; this is the guard the
    rule asked for by name, so a later lane that drops it goes red here rather
    than at a regulator's request.

    Vendor-independent on purpose: it reads the schema, not the engine.
    """
    for model in (btm.BillTemplateVersion, ntm.NotificationTemplateVersion):
        assert any(field.name == "archived_at" for field in model._meta.get_fields()), (
            f"{model._meta.db_table} lost archived_at — BR-NOT-025 requires it, because "
            "a version that left the picker must still be able to say WHEN"
        )
