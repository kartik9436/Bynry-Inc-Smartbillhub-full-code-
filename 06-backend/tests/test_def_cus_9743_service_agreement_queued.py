# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · P1.20 · lane MVI-POLISH
# Defect:   DEF-CUS-9743 — the Service agreement default was listed on Review
#           and never queued at Complete
# Rules:    images 45, 46 (two defaults, both sent) · BR-NOT-002 (a contract
#           version is effective-dated and is never seeded) · BR-NOT-013 (a
#           queued message is never called sent) · CLAUDE.md hard rule 6
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**The second default goes out: Complete queues the service agreement.**

RED-FIRST (law 7), on the tip before the fix:
  * the plan case failed with ``assert [] == ['pdf_print']`` — the plan gave
    the agreement no channel by construction;
  * the Complete case failed with ``AssertionError: Complete queued no
    service agreement`` (no ``contract_service_agreement`` row on the queue);
  * the replay case failed with ``AttributeError: module
    'apps.customers.notifications_seam' has no attribute
    'queue_move_in_service_agreement'``.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * **The agreement deduped into the welcome.** Both are move-in occasions;
    keyed on the same move record and channel, the second write would find the
    first's row and report ``created=False``. So the case asserts the two rows
    have DIFFERENT source ids and both exist.
  * **A queued claim read off the response.** The case reads the outbound row
    back, by template class and account.
  * **A missing template silently skipped.** A freshly seeded utility has no
    published contract (BR-NOT-002 refuses to seed one), so the case asserts
    the row IS written and carries the unresolved-pin problem — the welcome's
    own posture — rather than nothing at all.
"""

import pytest

from apps.customers import move_in_complete, notifications_seam
from apps.customers import services as customers_services

from tests.test_br_cus_1077_move_in_job import _served_unit
from tests.test_def_cus_6353_first_occupant_move_in import _payload
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _move_in(actor, tenant, label):
    _premises, unit = _served_unit(actor, tenant, label=label, address=f"{label} Elm")
    return customers_services.move_in_to_unit(actor, unit["id"], _payload())


def test_the_plan_lists_the_agreement_on_the_channel_complete_will_queue(brazos):
    with tenant_ctx(brazos):
        rows = notifications_seam.move_in_message_plan(
            category=None, deposit_taken=False, deposit_cleared=False
        )
    contract = next(row for row in rows if row["key"] == "service_agreement")
    # CR-190-BRC10 (PO 2026-10-22, answer 1: *"email it as a PDF attachment"*)
    # superseded this lane's print-only judgment: Step 4 lists it on EMAIL.
    # The letter is added per customer (paperless off, or no email on file).
    assert contract["channels"] == ["email"]
    # A fresh utility has published no contract version — said, never invented.
    assert contract["template"] is None


def test_complete_queues_the_agreement_beside_the_welcome(brazos, dana):
    from apps.notifications import models as notification_models
    from apps.notifications import services as notification_services

    with tenant_ctx(brazos):
        result = _move_in(dana, brazos, "Unit 9743")
        agreement = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.id,
            template_code="contract_service_agreement",
            account_id=result["id"],
        )
        welcome = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.id, template_code="email_welcome", account_id=result["id"]
        )
        assert agreement.exists(), "Complete queued no service agreement"
        assert welcome.exists()
        assert {row.channel for row in agreement} == {"pdf_print"}
        # Its own key: never the welcome's row reused.
        assert {str(r.source_id) for r in agreement}.isdisjoint(
            {str(r.source_id) for r in welcome}
        )
        # Never called sent (BR-NOT-013).
        assert {row.status for row in agreement} != {"sent"}

    codes = [row.get("code") for row in result["service_agreement_message"]]
    assert notifications_seam.MOVE_MESSAGE_QUEUED in codes
    # No published contract here: the row is written and the reason travels,
    # exactly as the welcome's would.
    assert notification_services.QUEUE_PIN_UNRESOLVED in codes

    messages = next(
        item for item in move_in_complete.what_happened(result)["items"] if item["key"] == "messages"
    )
    # The welcome counts one per channel (`DEF-CUS-9757`); the agreement adds
    # its one printed letter on top.
    welcome = sum(
        len(m.get("channels") or ()) or 1
        for m in result["move_message"]
        if m.get("code") == notifications_seam.MOVE_MESSAGE_QUEUED
    )
    assert welcome >= 1
    assert messages["queued"] == welcome + 1


def test_a_replayed_agreement_writes_nothing_twice(brazos, dana):
    from datetime import date

    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        result = _move_in(dana, brazos, "Unit 9744")
        before = notification_models.OutboundMessage.objects.filter(
            template_code="contract_service_agreement"
        ).count()
        again = notifications_seam.queue_move_in_service_agreement(
            move_record_id=result["move_record_id"],
            account_id=result["id"],
            effective_on=date.fromisoformat(str(result["opened_at"])),
            actor=dana,
        )
        after = notification_models.OutboundMessage.objects.filter(
            template_code="contract_service_agreement"
        ).count()
    assert after == before
    assert notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED in [row.get("code") for row in again], again
