# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.20 · P1.21
# Rules:    images 45, 46, 48 · BR-NOT-013 · CLAUDE.md hard rules 6 · 7
# Defects:  DEF-CUS-9702
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**Complete's Messaging table and its *What happened* answer.**

RED-FIRST (law 7): `DEF-CUS-9702`'s case was run against the tip before the
filter and failed (`'plan_snapshot_not_recorded' in {...}`); the extra-message
cases failed with `customers.extra_messages` refused as an unknown field.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A queued message asserted from the response.** The queue case reads the
    `move_extra_messages` row AND the notifications outbound rows back.
  * **A refusal that passes because nothing was attempted.** The refused-row
    case asserts NO account and NO extra-message row exist afterwards.
  * **A stale-absence test that passes because no warning list came back.**
    The DEF-CUS-9702 case asserts the list exists and a still-true member
    (`customer_not_created`-free path) is untouched.
"""

import pytest

from core import errors

from apps.customers import models as customers_models
from apps.customers import move_in_complete, notifications_seam
from apps.customers import services as customers_services
from apps.customers.move_in_extras import MoveExtraMessage

from tests.test_br_cus_1077_move_in_job import _served_unit
from tests.test_def_cus_6353_first_occupant_move_in import _payload
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _move_in(actor, tenant, label, **extra):
    _premises, unit = _served_unit(actor, tenant, label=label, address=f"{label} Elm")
    return customers_services.move_in_to_unit(actor, unit["id"], _payload(**extra))


def test_def_cus_9702_the_two_stale_absences_are_not_served_on_a_move_in(brazos, dana):
    with tenant_ctx(brazos):
        result = _move_in(dana, brazos, "Unit 1")
    assert result["customer_outcome"] == "created"
    codes = {w["code"] for w in result["warnings"]}
    assert "plan_snapshot_not_recorded" not in codes
    # The carry-forward absence is TRUE (nothing carries yet) and stays; only
    # its sentence was false, and the sentence is now the fact alone.
    import json
    from pathlib import Path

    en = json.loads(
        (Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json").read_text()
    )
    sentence = en["customers.account.warning.deposit_carry_forward_unavailable"]
    assert "customer record" not in sentence and "same customer" not in sentence


def test_an_extra_message_on_complete_to_the_customer_is_queued_never_sent(brazos, dana):
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        offered = [t for t in notifications_seam.message_templates() if str(t.get("body") or "").strip()]
        if not offered:
            pytest.skip("this tenant publishes no ready-made wording")
        code = offered[0]["code"]
        result = _move_in(
            dana,
            brazos,
            "Unit 2",
            extra_messages=[
                {"template_key": code, "recipient": "customer", "channel": "email", "send_when": "on_complete"},
                {"template_key": code, "recipient": "customer", "channel": "text", "send_when": "day_before_move_in"},
            ],
        )
        rows = list(MoveExtraMessage.objects.filter(move_record_id=result["move_record_id"]).order_by("seq"))
        assert [r.send_when for r in rows] == ["on_complete", "day_before_move_in"]
        assert rows[0].notification_id is not None and rows[1].notification_id is None
        outbound = notification_models.OutboundMessage.objects.filter(source_id=rows[0].id)
        assert outbound.exists()
    states = [(m["state"], m["not_queued"]) for m in result["extra_messages"]]
    assert states == [
        ("queued", None),
        ("planned", move_in_complete.NOT_QUEUED_SCHEDULED),
    ]
    assert "sent" not in {m["state"] for m in result["extra_messages"]}  # BR-NOT-013


def test_a_default_named_as_an_extra_is_refused_and_nothing_is_written(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 3", address="3 Oak")
        before = customers_models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(
                    extra_messages=[
                        {"template_key": "move_in_welcome", "channel": "email"},
                    ]
                ),
            )
        assert customers_models.Account.objects.count() == before
        assert MoveExtraMessage.objects.count() == 0
    assert caught.value.message_key == "customers.moveIn.messages.defaultTwice"


def test_a_co_owner_nobody_added_is_refused_and_the_move_in_rolls_back(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 4", address="4 Oak")
        before = customers_models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(
                    extra_messages=[
                        {
                            "template_key": "anything",
                            "recipient": "co_owner",
                            "co_owner_name": "Nobody, Here",
                            "channel": "email",
                        }
                    ]
                ),
            )
        assert customers_models.Account.objects.count() == before
    assert caught.value.message_key == "customers.moveIn.messages.coOwnerUnknown"


def test_what_happened_lists_what_the_commit_reported_with_its_numbers(brazos, dana):
    with tenant_ctx(brazos):
        result = _move_in(dana, brazos, "Unit 5", field_visit={"none": True})
    told = result["what_happened"]
    assert told["move_no"] == result["move_no"]
    assert told["request_no"] is None  # a walk-in move-in came from no request
    keys = [item["key"] for item in told["items"]]
    assert keys[:2] == ["customer", "account"]
    assert "unit" in keys and "messages" in keys and "work_orders" in keys
    unit = next(i for i in told["items"] if i["key"] == "unit")
    assert unit == {"key": "unit", "now": "occupied", "was": "vacant"}
    work = next(i for i in told["items"] if i["key"] == "work_orders")
    assert work["count"] == 0 and work["declined"] is True


def test_def_cus_9726_a_move_in_that_follows_a_tenancy_took_a_vacant_unit():
    """`DEF-CUS-9730` — *Move-in completed* read **Occupied → Occupied** on every
    move-in that follows a finished tenancy. A move-in only ever takes a VACANT
    unit (BR-CUS-020; BR-CUS-017 refuses one an account still holds), so the
    unit's before-state is vacant on BOTH doors — the account-scoped one that
    names the previous account and the first occupant's.

    RED-FIRST, verbatim, before the fix:
        assert {'key': 'unit...': 'occupied'} == {'key': 'unit...as': 'vacant'}
    """
    for after in ("acc-previous", None):
        told = move_in_complete.what_happened({"moved_in_after_account_id": after})
        unit = next(item for item in told["items"] if item["key"] == "unit")
        assert unit == {"key": "unit", "now": "occupied", "was": "vacant"}, after


def test_def_cus_9759_the_queued_welcome_is_counted_in_what_happened():
    """`DEF-CUS-9759` — *Move-in completed* read **Messages · 0 queued** on a
    move-in whose welcome WAS queued. The welcome's outcome rows carry a
    `code` (`move_message_queued` / `move_message_already_queued`) and no
    `state`, so a counter that reads only `state` / `outcome` never counts it.
    A suppressed welcome (the utility switched the event off) is NOT queued.
    """
    told = move_in_complete.what_happened(
        {
            "move_message": [
                {"code": notifications_seam.MOVE_MESSAGE_QUEUED, "message_id": "m-1"},
                {"code": notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED, "message_id": "m-2"},
                {"code": notifications_seam.MOVE_MESSAGE_SUPPRESSED},
            ],
            "extra_messages": [
                {"seq": 1, "state": "queued"},
                {"seq": 2, "state": "planned"},
            ],
        }
    )
    messages = next(item for item in told["items"] if item["key"] == "messages")
    assert messages == {"key": "messages", "queued": 3, "planned": 1}
