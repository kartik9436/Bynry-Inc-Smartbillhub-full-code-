"""F-11 — My details: a malformed phone or ZIP is refused, an emptied phone is
REMOVED, and a save never reports *"Saved on 0 accounts"* for a removal.

`DEF-CWP-10549`. PO/QA ruling 2026-10-23 (decision log *"three product answers
(F-18 messages, F-17 selectors, F-11 clearing the phone)"* point 3), built per
*"Groups B and C: how they are built"* point 10.

Worked, as the ruling put it to the PO:
  * phone ``abc`` → refused, *"Enter a 10-digit phone number."*, nothing stored;
  * ZIP ``1`` → refused, *"Enter a 5-digit ZIP."*, nothing stored;
  * phone emptied → removed on all four of Maria's accounts, *"Phone removed."*,
    and *"Text reminders stop without a phone."* because she has them on.

⚠ **THE CHECKS ARE COPIES, HELD EQUAL HERE.** `customers` may not import
`portal` (B2 §2), so `portal_self_service.phone_ok` / `US_ZIP_RE` copy
`apps.portal.applications`'s. The last test fails the day one of them moves.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.customers import portal_self_service
from apps.portal import applications, services
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_028_my_details import OLD_PHONE, maria_with_four, principal_for
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on


def _save(tenant, principal, payload):
    return services.update_own_contact_details(
        tenant.id,
        actor=principal,
        account_ids=list(principal.account_ids),
        payload=payload,
    )


def _phones(tenant, accounts):
    return set(
        customers_models.Contact.objects.filter(
            tenant_id=tenant.id, account__in=accounts, is_primary=True
        ).values_list("phone", flat=True)
    )


@pytest.mark.django_db
def test_f11_a_phone_of_letters_is_refused_on_the_field_and_nothing_is_stored(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as raised:
            _save(pine_hill, principal, {"phone": "abc"})
        assert raised.value.message_key == "portal.myDetails.phoneFormat"
        assert [one["field"] for one in raised.value.field_errors] == ["phone"]
        assert _phones(pine_hill, accounts) == {OLD_PHONE}


@pytest.mark.django_db
def test_f11_a_one_digit_zip_is_refused_and_both_bad_boxes_are_named(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as raised:
            _save(
                pine_hill,
                principal,
                {"phone": "abc", "postal": {"line1": "1 Oak St", "city": "Austin", "postal_code": "1"}},
            )
        assert [one["field"] for one in raised.value.field_errors] == ["phone", "postal_code"]
        assert raised.value.field_errors[1]["message_key"] == "portal.myDetails.zipFormat"
        # Refused BEFORE any write — no mailing row appeared.
        assert not customers_models.Address.objects.filter(
            tenant_id=pine_hill.id, account__in=accounts, kind="mailing", postal_code="1"
        ).exists()


@pytest.mark.django_db
def test_f11_well_formed_values_still_save(pine_hill, sarah):
    """Nothing that saved before is refused now (no validation weakened, none
    invented): a formatted phone, an eleven-digit one, ZIP+4 and a blank ZIP."""
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        assert _save(pine_hill, principal, {"phone": "(281) 555-0164"})["accounts_updated"] == 4
        assert _save(pine_hill, principal, {"phone": "+1 281 555 0199"})["accounts_updated"] == 4
        result = _save(
            pine_hill,
            principal,
            {"postal": {"line1": "1 Oak St", "city": "Austin", "postal_code": "78704-1234"}},
        )
        assert result["accounts_updated"] == 4
        assert _save(pine_hill, principal, {"postal": {"postal_code": ""}})["accounts_updated"] == 4


@pytest.mark.django_db
def test_f11_an_emptied_phone_is_removed_from_every_account_and_says_so(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        customers_models.Account.objects.filter(id=accounts[0].id).update(sms_reminders=True)
        result = _save(pine_hill, principal, {"phone": ""})
        assert result["accounts_updated"] == 4, result
        assert result["phone_removed"] is True
        assert result["text_reminders_on"] is True
        assert _phones(pine_hill, accounts) == {None}
        # The switch itself is NOT turned off — the ruling tells her, it does
        # not change her setting.
        assert customers_models.Account.objects.get(id=accounts[0].id).sms_reminders is True


@pytest.mark.django_db
def test_f11_removing_with_no_text_reminders_says_nothing_about_them(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        customers_models.Account.objects.filter(id__in=[a.id for a in accounts]).update(
            sms_reminders=False
        )
        result = _save(pine_hill, principal, {"phone": "   "})
        assert result["phone_removed"] is True
        assert result["text_reminders_on"] is False
        # Removing again: nothing on file, nothing changes, no false claim.
        again = _save(pine_hill, principal, {"phone": ""})
        assert again["accounts_updated"] == 0
        assert again["phone_removed"] is False


@pytest.mark.django_db
def test_f11_an_absent_phone_key_still_touches_nothing(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        result = _save(pine_hill, principal, {"postal": {"line1": "1 Oak St"}})
        assert result["phone_removed"] is False
        assert _phones(pine_hill, accounts) == {OLD_PHONE}


@pytest.mark.parametrize(
    "value", ["abc", "1", "(281) 555-0164", "12815550164", "22815550164", "281555016", "", "+1-281-555-0164"]
)
def test_f11_the_customers_phone_check_is_the_portals(value):
    assert portal_self_service.phone_ok(value) == applications.phone_ok(value)


@pytest.mark.parametrize("value", ["1", "77471", "77471-1234", "7747", "77471-12", "ABCDE", "77471 1234"])
def test_f11_the_customers_zip_check_is_the_portals(value):
    assert bool(portal_self_service.US_ZIP_RE.match(value)) == bool(applications.US_ZIP_RE.match(value))
