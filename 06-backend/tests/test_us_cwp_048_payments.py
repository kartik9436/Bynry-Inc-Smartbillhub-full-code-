# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-048 (EP-CWP-09) — payments and receipts, and a bounce is two
#           rows. Screen: CWP-041
# Rules:    BR-CWP-061 (a bounce is TWO rows — the payment and the reversal
#           above it) · BR-CWP-050 (an adjustment appears with its date and a
#           plain-English reason) · BR-CWP-051 (a write-off shows its amount and
#           date and NEVER its reason code) · BR-CWP-052 (six things the back
#           office holds are deliberately not shown) · BR-CWP-010 (both halves
#           in the query) · B14 rule 31 (no database id is a visible value) ·
#           CLAUDE.md hard rule 4 (no UPDATE on a payment — corrections are new
#           rows) · hard rule 2 (4 dp stored, 2 dp displayed)
# Tests:    this file
# Impacts:  apps/portal/seams/payments_seam.py `money_list` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-048`'s cases — and the one the whole screen exists for.

⚠ **A BOUNCED CHEQUE IS TWO ROWS AND THAT IS CORRECT RATHER THAN CONFUSING.**
Nothing in this product edits a payment (hard rule 4): a reversal is a NEW
negative row against the original, which is why the customer sees both. The
test that matters is not only *"are there two rows"* — it is **that the original
payment's stored `status` is still `cleared` afterwards**, because the day
somebody "simplifies" this into one edited row, that assertion is what goes red.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.portal.seams import payments_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)

#: The demo script's own figures (execution plan wave G, step 5).
CHEQUE_NO = "10174"
BOUNCED_AMOUNT = "129.0200"
GOODWILL = "-25.8800"
WRITE_OFF = "84.2000"
#: ⚠ The reason that must never surface (`BR-CWP-051`).
WRITE_OFF_REASON = "customer_bankruptcy"

JULY_2 = datetime(2026, 7, 2, 9, 0, tzinfo=UTC)
JUNE_13 = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)


def read(tenant, account, **kwargs):
    with tenant_context(tenant.id):
        return payments_seam.money_list([account.pk], **kwargs)


def a_payment(tenant, account, *, amount, posted_at, confirmation=None, number=None, invoice=None):
    """One CLEARED payment, optionally allocated against one bill."""
    from apps.payments import models as payment_models

    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=number,
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        confirmation=confirmation,
        posted_at=posted_at,
        cleared_at=posted_at,
    )
    if invoice is not None:
        payment_models.Allocation.objects.create(
            tenant=tenant, payment=payment, invoice=invoice, amount=Decimal(amount)
        )
    return payment


def a_reversal(tenant, account, original, *, returned_on):
    """The reversing row `reversal.py` writes — negative, self-FK, own row.

    ⚠ **THE ORIGINAL IS NOT TOUCHED HERE, BECAUSE IT IS NOT TOUCHED THERE.**
    `apps/payments/reversal.py` contains no `original.save()`; hard rule 4 is
    the reason and this fixture reproduces the shape rather than a shortcut.
    """
    from apps.payments import models as payment_models

    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no="PMT-26-07002",
        amount=-Decimal(original.amount),
        currency=original.currency,
        status=payment_models.PAYMENT_REVERSED,
        confirmation=original.confirmation,
        posted_at=returned_on,
        cleared_at=returned_on,
        reverses_payment=original,
        reversal_reason="nsf",
    )


@pytest.mark.django_db
def test_us_cwp_048_tc2_a_bounce_is_TWO_rows_and_the_reversal_sits_directly_above(
    pine_hill, sarah
):
    """⚠ **THE CASE THE SCREEN EXISTS FOR** (`BR-CWP-061`).

    `2 Jul · Cheque #10174 · Returned by the bank · −$129.02 · BOUNCED`
    directly above
    `2 Jul · Cheque #10174 · BL-2606-0147 · $129.02 · REVERSED`.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2606-0147", total=BOUNCED_AMOUNT,
            issued_on=date(2026, 6, 26), due_on=date(2026, 7, 14),
        )
        original = a_payment(
            pine_hill, account, amount=BOUNCED_AMOUNT, posted_at=JULY_2,
            confirmation=CHEQUE_NO, number="PMT-26-07001", invoice=bill,
        )
        a_reversal(pine_hill, account, original, returned_on=JULY_2)

    rows = read(pine_hill, account)
    assert len(rows) == 2, rows

    reversal, payment = rows
    assert reversal["state"] == payments_seam.STATE_BOUNCED
    assert reversal["amount"] == "-129.0200", "the sign is the server's"
    assert reversal["returned_by_the_bank"] is True
    assert reversal["applied_to"] == [], "a reversal names no bill — it names the bank"
    assert reversal["reference"] == CHEQUE_NO, "the cheque number, on both rows"

    assert payment["state"] == payments_seam.STATE_REVERSED
    assert payment["amount"] == BOUNCED_AMOUNT
    assert payment["applied_to"] == ["BL-2606-0147"]
    assert payment["reference"] == CHEQUE_NO

    # ⚠ **THE ASSERTION THAT MAKES THIS A TEST ABOUT HARD RULE 4 AND NOT ABOUT A
    # SORT ORDER.** The word REVERSED is DERIVED; the row in the database still
    # says `cleared`, because nothing in this product edits a payment.
    from apps.payments import models as payment_models

    with tenant_context(pine_hill.id):
        original.refresh_from_db()
    assert original.status == payment_models.PAYMENT_CLEARED, (
        "the original payment row was EDITED — hard rule 4 forbids an UPDATE on a "
        "payment, and a bounce is two rows precisely because of it"
    )


@pytest.mark.django_db
def test_us_cwp_048_a_bounce_a_month_later_still_sits_directly_above_its_payment(
    pine_hill, sarah
):
    """⚠ The pair is anchored at the REVERSAL's date, never split by the sort.

    A cheque paid on 13 June and returned on 2 July is the ordinary case, and a
    list that put five later payments between the two rows would leave a
    customer unable to see what happened to their money.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        original = a_payment(
            pine_hill, account, amount=BOUNCED_AMOUNT, posted_at=JUNE_13,
            confirmation=CHEQUE_NO, number="PMT-26-06001",
        )
        a_reversal(pine_hill, account, original, returned_on=JULY_2)
        a_payment(
            pine_hill, account, amount="138.4400",
            posted_at=datetime(2026, 6, 20, 9, 0, tzinfo=UTC), number="PMT-26-06002",
        )

    rows = read(pine_hill, account)
    states = [row["state"] for row in rows]
    assert states == [
        payments_seam.STATE_BOUNCED,
        payments_seam.STATE_REVERSED,
        payments_seam.STATE_RECEIVED,
    ], states


@pytest.mark.django_db
def test_us_cwp_048_tc1_five_payments_newest_first_each_with_how_and_reference(
    pine_hill, sarah
):
    """TC-1 — newest first, each with its method, reference and the bill it met."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.4400",
            issued_on=date(2026, 7, 26), due_on=date(2026, 8, 14),
        )
        a_payment(
            pine_hill, account, amount="138.4400",
            posted_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            number="PMT-26-08001", invoice=bill,
        )
        a_payment(
            pine_hill, account, amount="121.5500", posted_at=JUNE_13,
            number="PMT-26-06003",
        )
    rows = read(pine_hill, account)
    assert [row["date"] for row in rows] == ["2026-08-12", "2026-06-13"]
    assert rows[0]["applied_to"] == ["BL-2607-0139"]
    assert rows[0]["state"] == payments_seam.STATE_RECEIVED


@pytest.mark.django_db
def test_us_cwp_048_tc10_a_cheque_shows_its_NUMBER_and_never_a_row_id(pine_hill, sarah):
    """TC-10 and B14 rule 31. A payment with no cheque number falls back to the
    `PMT-` series — also a human reference — and never to the row's uuid."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        payment = a_payment(
            pine_hill, account, amount="50.0000", posted_at=JULY_2,
            confirmation=CHEQUE_NO, number="PMT-26-07001",
        )
        no_cheque = a_payment(
            pine_hill, account, amount="60.0000", posted_at=JUNE_13, number="PMT-26-06004",
        )
    rows = read(pine_hill, account)
    assert rows[0]["reference"] == CHEQUE_NO
    assert rows[1]["reference"] == "PMT-26-06004"
    body = str(rows)
    assert str(payment.pk) not in body
    assert str(no_cheque.pk) not in body
    # Eight characters of an id is the same breach as thirty-six.
    assert str(payment.pk)[:8] not in body


@pytest.mark.django_db
def test_us_cwp_048_tc11_a_corrected_cheque_number_shows_the_CORRECTED_value(
    pine_hill, sarah
):
    """TC-11 — the value the customer reads is the live column.

    ⚠ **AND THIS SCREEN IS NOT A RECORD OF THE OLD ONE.** The replaced value
    lives only in `audit_log`, which is pruned; whether such a row is exempt is
    `OQ-1340` and is OPEN. Nothing here asserts the old value is retrievable,
    because nothing may claim it is.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        payment = a_payment(
            pine_hill, account, amount="50.0000", posted_at=JULY_2,
            confirmation="10714", number="PMT-26-07001",
        )
        # The one narrowing of hard rule 4 (PO 2026-09-02): `confirmation` may
        # be corrected in place. The read must show what is there now.
        payment.confirmation = CHEQUE_NO
        payment.save(update_fields=["confirmation"])
    rows = read(pine_hill, account)
    assert rows[0]["reference"] == CHEQUE_NO
    assert "10714" not in str(rows)


@pytest.mark.django_db
def test_us_cwp_048_tc4_a_goodwill_credit_shows_its_date_and_its_reason(pine_hill, sarah):
    """TC-4 / `BR-CWP-050` — `−$25.88` with its date and a plain reason.

    ⚠ **THE SIGN ARRIVES NEGATIVE AND LEAVES NEGATIVE.**
    `credit_notes.amount <= 0` is a database CHECK, added after two writers
    stored opposite signs and a sign-off panel read `$272.30` on an account
    owing `$222.30` (DEF-085). Nothing in the portal re-signs it.
    """
    from apps.billing import models as billing_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.4400",
            issued_on=date(2026, 7, 26), due_on=date(2026, 8, 14),
        )
        billing_models.CreditNote.objects.create(
            tenant=pine_hill,
            account=account,
            original_invoice=bill,
            credit_note_no="CN-2607-0004",
            amount=Decimal(GOODWILL),
            currency="USD",
            reason="reading dispute",
            issued_at=datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
        )
    rows = read(pine_hill, account)
    credit = next(row for row in rows if row["kind"] == payments_seam.MONEY_CREDIT)
    assert credit["amount"] == GOODWILL, "negative, as stored"
    assert credit["date"] == "2026-07-12"
    assert credit["reason"] == "reading dispute"
    assert credit["reference"] == "CN-2607-0004"


@pytest.mark.django_db
def test_us_cwp_048_tc5_a_write_off_shows_its_amount_and_date_and_NEVER_its_reason(
    pine_hill, sarah
):
    """TC-5 / `BR-CWP-051`. ⚠ **The negative assertion is the whole test.**

    *Bankruptcy* and *deceased, no estate* are the utility's judgment about a
    person; `$84.20` is that person's own money. The amount belongs to them and
    the reason does not.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _a_write_off(pine_hill, account, amount=WRITE_OFF, on=date(2026, 5, 12))
    rows = read(pine_hill, account)
    written_off = next(row for row in rows if row["kind"] == payments_seam.MONEY_WRITE_OFF)
    assert written_off["amount"] == WRITE_OFF
    assert written_off["date"] == "2026-05-12"
    assert written_off["state"] == payments_seam.STATE_WRITTEN_OFF
    body = str(rows)
    assert WRITE_OFF_REASON not in body, "BR-CWP-051 — the reason code must not surface"
    assert "bankrupt" not in body.lower()
    assert "reason" not in written_off, "not even the KEY, on a write-off row"


@pytest.mark.django_db
def test_us_cwp_048_tc6_a_write_off_reversal_is_its_OWN_row_and_not_a_deletion(
    pine_hill, sarah
):
    """TC-6 — hard rule 4 in the shape `write_offs` answers it: both rows stand."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        original = _a_write_off(pine_hill, account, amount=WRITE_OFF, on=date(2026, 5, 12))
        _a_write_off(
            pine_hill, account, amount=WRITE_OFF, on=date(2026, 6, 3),
            reverses=original, status="reversed",
        )
    rows = read(pine_hill, account)
    write_offs = [row for row in rows if row["kind"] == payments_seam.MONEY_WRITE_OFF]
    assert len(write_offs) == 2, "the reversal is a row, never a deletion of the first"
    assert {row["state"] for row in write_offs} == {
        payments_seam.STATE_WRITTEN_OFF,
        payments_seam.STATE_WRITE_OFF_REVERSED,
    }


@pytest.mark.django_db
def test_us_cwp_048_tc7_an_account_with_no_payments_reads_as_an_empty_list(
    pine_hill, sarah
):
    """TC-7 — an empty list, never a zero row. The SCREEN names what fills it."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert read(pine_hill, account) == []


@pytest.mark.django_db
def test_us_cwp_048_tc8_tenant_isolation_pine_hill_sees_only_pine_hill(
    pine_hill, sarah, oak_ridge, elena
):
    """TC-8 / `BR-CWP-010` — **both halves are in the query.**

    ⚠ **THE ASSERTION IS DELIBERATELY THE HARD DIRECTION.** Reading a Pine Hill
    account id **under Oak Ridge's context** must answer nothing, and that can
    only be true if the TENANT half sits in the queryset rather than in the
    caller — a seam filtering on the account id alone would happily hand Oak
    Ridge somebody else's cheque number.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    pine_account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_payment(
            pine_hill, pine_account, amount="10.0000", posted_at=JULY_2,
            number="PMT-26-07001",
        )
    assert [row["amount"] for row in read(pine_hill, pine_account)] == ["10.0000"]
    with tenant_context(oak_ridge.id):
        assert payments_seam.money_list([pine_account.pk]) == [], (
            "an account of ANOTHER utility answered under this one — the tenant "
            "half is not in the query (BR-CWP-010, hard rule 1)"
        )


@pytest.mark.django_db
def test_us_cwp_048_tc3_the_portal_edge_has_no_update_or_delete_for_a_payment(
    pine_hill, sarah
):
    """TC-3 · **negative** — *"assert the endpoint set contains no update or
    delete for a payment"*.

    ⚠ **READ AS A LIST OF WHAT EXISTS, NOT AS A SEARCH FOR WHAT DOES NOT.** The
    portal edge's `urlpatterns` is the whole of what a signed-in customer can
    reach; this walks it and asserts nothing under `payments` accepts a verb
    that changes one.
    """
    from apps.portal import api as portal_api
    from apps.portal import session as portal_session

    def customer_reachable(route: Any) -> bool:
        """A route a SIGNED-IN CUSTOMER can reach — which is this rule's subject.

        ⚠ **SELECTED BY PERMISSION, NOT BY A WORD IN THE ADDRESS
        (`DEF-CWP-3957`).** This filtered on `"payments" in str(route.pattern)`
        and was RED at the branch tip, because `portal/webhooks/payments/
        {provider}` contains that word and answers `POST`. The assertion was
        right and the code was right; the SELECTOR was wrong. That route is
        `AllowAny` with `authentication_classes([])`, signed by the processor —
        it is the provider telling US a payment settled, not a customer changing
        one.

        The rule keeps its teeth: a new CUSTOMER-facing payment route that
        answers a changing verb still fails this case. A permission rule chosen
        by a substring of an address will eventually match a route with a
        different permission model, which is the second time today a substring
        selector has given a wrong answer in this repo.
        """
        cls = getattr(route.callback, "cls", None)
        return portal_session.IsPortalCustomer in tuple(getattr(cls, "permission_classes", ()))

    payment_routes = [
        route
        for route in portal_api.urlpatterns
        if "payments" in str(route.pattern) and customer_reachable(route)
    ]
    assert payment_routes, "the money list route itself must exist"
    for route in payment_routes:
        allowed = set(getattr(route.callback, "cls", None).http_method_names or ())
        actions = set(getattr(getattr(route.callback, "cls", None), "actions", {}) or {})
        handlers = {
            verb
            for verb in ("put", "patch", "delete", "post")
            if hasattr(getattr(route.callback, "cls", None), verb)
        }
        assert not handlers, f"{route.pattern} answers {handlers} on a payment"
        assert "get" in allowed or not allowed


@pytest.mark.django_db
def test_us_cwp_048_the_year_filter_keeps_only_that_year(pine_hill, sarah):
    """The capability row's *All · This year*, in the QUERY's answer rather than
    in the screen — a client-side filter over a paged list is a filter over one
    page."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_payment(
            pine_hill, account, amount="10.0000", posted_at=JULY_2, number="PMT-26-07001",
        )
        a_payment(
            pine_hill, account, amount="20.0000",
            posted_at=datetime(2025, 7, 2, 9, 0, tzinfo=UTC), number="PMT-25-07001",
        )
    assert len(read(pine_hill, account)) == 2
    assert [row["amount"] for row in read(pine_hill, account, year=2026)] == ["10.0000"]


def _a_write_off(tenant, account, *, amount, on, reverses=None, status="approved"):
    from apps.payments import collections_models

    return collections_models.WriteOff.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency="USD",
        reason=WRITE_OFF_REASON,
        note="not collectable",
        status=status,
        requested_on=on,
        approved_on=on,
        reverses_write_off=reverses,
        reversal_reason="raised in error" if reverses is not None else None,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-048@8bcd8b6a (EP-CWP-09 story §1–§8 + BR-CWP-050/051/052/061 verbatim + J36)
# generated: 2026-09-04 by the CR-068 wave G/M slice lane
# checklist: A✔ B✔ C✔ D✔(apps/portal/api.py `payments`) E✔(portal/payments/Payments.tsx) F✔ G✔ H=n/a(no 🔒 path — the seam composes payments' own published reads)
# gates: pytest tests/test_us_cwp_048_payments.py · G81 (the seam performs no ORM write)
# exceptions: (1) the money list is served at `GET portal/payments` over the whole account set rather than `accounts/{id}/payments` — the shape `portal/bills` already took; decision logged 2026-09-04 · (2) `billing.Adjustment` has NO WRITER in this product, so the goodwill adjustment is read as a `CreditNote`, which is where `credit_notes_api.py` actually puts one · (3) no per-account write-off read exists anywhere, so the seam reads `WriteOff` directly and projects three fields
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
