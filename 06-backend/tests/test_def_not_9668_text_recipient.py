# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6 · lane FIX-7 — DEF-NOT-9668 (a work-order text
#           queued 'Address not looked up' although the customer has a phone)
#           and DEF-NOT-9669 (a text for a customer who never chose texts read
#           as a platform gap instead of their own choice).
# Rules:    BR-TEN-017 (the recipient read, owned by customers) · BR-BIL-036
#           (an absence is a FACT, never a blank) · BR-NOT-005 / DEF-NOT-5632
#           (the do-not-send list HOLDS the row) · BR-CWP-001 (the customer's
#           own election) · CLAUDE.md law 14 (proved on PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""A text is addressed to the phone the customer gave, only when they chose texts.

The recipient read (`customers.selectors.delivery_recipients_for_account`) is the
ONE place every writer of a customer message — a bill, a receipt, a visit —
learns who to address, so it is fixed there and every writer inherits it. Three
answers on the `sms` channel, each a different fact:

  * the customer chose texts and the account's primary contact has a phone →
    addressed to that phone, the number the account screen shows and the
    work order prints;
  * the customer chose texts and holds no phone → `no_mobile_number`;
  * the customer did not choose texts → `no_sms_opt_in` — never an address,
    whoever is asking.

Runs on SQLite and on PostgreSQL 16 (`config.settings.pgtest`).
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.notifications import models, suppression

from tests.test_cr168_srv5_messages import (
    _assign,
    _customer_job,
    _setup,
    _technician,
    _visit_rows,
    _window,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: `_create_payload`'s contact phone — what the account screen shows.
PHONE = "+1 (281) 555-0100"

SEEDED_ON = datetime(2026, 8, 17, 9, 0, tzinfo=dt_timezone.utc)


def _sms_rows():
    return [row for row in _visit_rows() if row.channel == "sms"]


def test_def_not_9668_a_customer_who_chose_texts_is_texted_at_their_phone(brazos, dana, marcus):
    """RED on the tip: ``assert None == '+1 (281) 555-0100'`` — the visit text
    was written with `recipient_not_resolvable` ('Address not looked up')."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=True)
        _assign(dana, order, _technician(brazos), _window())
        rows = _sms_rows()
    assert [(r.recipient_address, r.unavailable_reason, r.held) for r in rows] == [
        (PHONE, None, False)
    ]
    assert rows[0].recipient_snapshot["source"] == "contact_phone"


def test_def_not_9668_a_customer_with_no_phone_is_held_and_says_why(brazos, dana, marcus):
    """No phone anywhere on the account → the row stands, unaddressed, and says
    `no_mobile_number` — a fact about the CUSTOMER, never 'not looked up'."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=True)
        customers_models.Contact.objects.filter(tenant_id=brazos.id).update(phone=None)
        for customer in customers_models.Customer.objects.filter(tenant_id=brazos.id):
            customer.phone = None
            customer.save(update_fields=["phone"])
        _assign(dana, order, _technician(brazos), _window())
        rows = _sms_rows()
    assert [(r.recipient_address, r.unavailable_reason) for r in rows] == [
        (None, models.REASON_NO_MOBILE)
    ]


def test_def_not_9668_a_phone_on_the_do_not_send_list_is_written_and_held(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        suppression.suppress(channel="sms", address=PHONE, reason="manual",
                             at=timezone.now(), actor=dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=True)
        _assign(dana, order, _technician(brazos), _window())
        rows = _sms_rows()
    assert [(r.recipient_address, r.held) for r in rows] == [(PHONE, True)]


def test_def_not_9668_a_customer_who_did_not_choose_texts_gets_no_visit_text(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=True, text_on=False)
        _assign(dana, order, _technician(brazos), _window())
        assert _sms_rows() == []


def test_def_not_9669_the_read_never_addresses_a_text_nobody_chose(brazos, dana, marcus):
    """A payment receipt asks for `sms` whatever the customer chose. RED on the
    tip: ``assert {'unavailable_reason': 'recipient_not_resolvable'} ==
    {'unavailable_reason': 'no_sms_opt_in'}``."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=False)
        account_id = customers_models.Account.objects.filter(tenant_id=brazos.id).values_list(
            "id", flat=True
        ).first()
        answer = customers_selectors.delivery_recipients_for_account(account_id, channels=("sms",))
    assert order is not None
    assert answer == {"sms": {"unavailable_reason": models.REASON_NO_SMS_OPT_IN}}
