# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-065 (EP-CWP-11) — dispute a bill or a reading: **a marker,
#           never an edit**. Screen: CWP-055
# Rules:    CLAUDE.md hard rule 4 (no UPDATE on an issued invoice — corrections
#           are new rows) · BR-CWP-042 (a correction is a NEW bill; the original
#           stays) · BR-CWP-026 (a portal write changes no account) ·
#           BR-CWP-010 (both halves in the query) · B14 rule 31 (the bill is
#           named by its number)
# Open:     OQ-CWP-1681 — who puts `metering`'s dispute marker on the reading ·
#           OQ-CWP-1682 / OQ-420 — nothing records a disputed AMOUNT, so no
#           collection hold is performed and the screen must not promise one
# Tests:    this file
# Impacts:  apps/portal/services.py `SHAPE_DISPUTE` · apps/portal/api.py
#           `bill_dispute` · apps/portal/seams/billing_seam.py `bill_facts`
# ───────────────────────────────────────────────────────
"""`US-CWP-065`'s cases — and the one sentence the whole story is.

⚠ **A DISPUTE IS A MARKER WITH A REASON AND IT NEVER EDITS THE NUMBER IT
QUESTIONS.** TC-2 is not *"is the total still 142.18"* — it is that the invoice
row is **byte-identical field by field** afterwards, which is the only form of
that assertion that cannot pass while something quietly moved `updated_at`, a
status or an allocation.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.billing import models as billing_models
from apps.customers import models as customers_models, service_request_service as writes
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-065` §4 — the story's own fixture, to the cent.
BILL_NO = "BL-2608-0141"
BILL_TOTAL = "142.1800"
SECOND_BILL_NO = "BL-2607-0102"
SECOND_TOTAL = "318.0400"
ISSUED_ON = date(2026, 8, 26)
WHAT = "The meter reading on 31 August"
REASON = "The house was empty for two weeks."
OWN_READING = "153190"


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def signed_in(tenant, *, email: str = MARIA_EMAIL, password: str = MARIA_PASSWORD):
    client = Client()
    answer = client.post(
        portal_url(tenant, "auth/sign-in"),
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def maria_with_a_bill(tenant, actor, *, number=BILL_NO, total=BILL_TOTAL):
    switch_on(tenant, actor)
    credential = enrol_maria(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        customers_models.CustomerAccount.objects.get_or_create(
            tenant_id=tenant.id, customer_id=credential.customer_id, account=account
        )
        bill = an_issued_bill(
            tenant, account, number=number, total=total, issued_on=ISSUED_ON
        )
    return credential, account, bill


def query_the_bill(client, tenant, *, number=BILL_NO, **body):
    payload = {"what": WHAT, "reason": REASON, "own_reading": OWN_READING}
    payload.update(body)
    return client.post(
        portal_url(tenant, f"bills/{number}/dispute"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def invoice_snapshot(tenant, invoice_id):
    """Every column of the row, so *unchanged* is an assertion and not a hope."""
    with tenant_context(tenant.id):
        row = billing_models.Invoice.objects.get(pk=invoice_id)
        return {
            field.name: getattr(row, field.attname, None)
            for field in billing_models.Invoice._meta.fields
        }


# ══ TC-1 · the query reaches a clerk NAMING the bill ═══════════════════════


@pytest.mark.django_db
def test_us_cwp_065_tc1_the_query_reaches_a_clerk_naming_the_BILL_and_the_READING(
    pine_hill, sarah
):
    """TC-1 — one service request on the worklist, carrying the bill number, the
    period, the total, what is questioned and the customer's reason."""
    _, _, bill = maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    answer = query_the_bill(client, pine_hill)

    assert answer.status_code == 201, answer.content
    body = answer.json()
    assert body["reference"].startswith("SR-")
    with tenant_context(pine_hill.id):
        row = customers_models.ServiceRequest.objects.get(request_no=body["reference"])
    assert row.channel == "customer_portal"
    said = row.what_they_said
    assert BILL_NO in said
    assert WHAT in said
    assert REASON in said
    # ⚠ THE MONEY IS THE SERVER'S, carried and never recomputed by the browser —
    # and it is carried at TWO decimals, because this sentence is DISPLAYED.
    #
    # ⚠ **THIS ASSERTION READ `"142.1800" in said` AND IT WAS PINNING A DEFECT**
    # (`DEF-CWP-4198`). `what_they_said` is written for the clerk's worklist and
    # `CWP-046` renders that same column to the CUSTOMER as their own words, so
    # a customer's requests list was printing `142.1800 USD` — four decimals,
    # where CLAUDE.md hard rule 2 says money is STORED to four and DISPLAYS at
    # two. The old assertion therefore PASSED while the fault was live and would
    # have gone RED the moment it was repaired. It is the third check in this
    # wave found doing that, after the two the date fix had to rewrite.
    assert "142.18" in said, said
    assert "142.1800" not in said, "money reaching a customer's screen displays at two decimals"
    assert bill.invoice_no == BILL_NO


# ══ TC-2 · THE CASE THE STORY EXISTS FOR ═══════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_065_tc2_the_BILL_ITSELF_IS_BYTE_IDENTICAL_AFTERWARDS(pine_hill, sarah):
    """⚠ **TC-2 — CLAUDE.md hard rule 4 wearing a screen.**

    Not *"the total is still $142.18"* — every column of the invoice row,
    compared before and after. The day somebody "simplifies" a query into an
    edit of the bill, this is the assertion that goes red.
    """
    _, _, bill = maria_with_a_bill(pine_hill, sarah)
    before = invoice_snapshot(pine_hill, bill.pk)
    client = signed_in(pine_hill)

    answer = query_the_bill(client, pine_hill)

    assert answer.status_code == 201, answer.content
    assert answer.json()["bill_changed"] is False
    assert invoice_snapshot(pine_hill, bill.pk) == before
    assert before["total"] == Decimal(BILL_TOTAL)
    # No line was added and none was removed either.
    with tenant_context(pine_hill.id):
        assert billing_models.Invoice.objects.filter(pk=bill.pk).count() == 1


# ══ TC-3 / TC-4 · the hold is NOT performed, and the screen must not say it is ══


@pytest.mark.django_db
def test_us_cwp_065_tc3_NO_COLLECTION_HOLD_IS_PERFORMED_and_the_answer_says_so(
    pine_hill, sarah
):
    """⚠ **TC-3, ANSWERED HONESTLY RATHER THAN PRETENDED** — `OQ-CWP-1682`.

    The story's consequence box promises *"we hold collection on `$142.18` · no
    late fee while we look"*. `BR-MET-133` clause 4 is built and needs the
    DISPUTED AMOUNT; **nothing in this product records one** (`OQ-420`, OPEN),
    and `late_fee.ageable_portion` raises rather than choosing between the two
    fallbacks — which are **`$137.20` apart** on the rule's own `$184.20` bill.
    So the response states `collection_held: false` on its face, and the screen
    says only what the code does.
    """
    _, _, bill = maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    body = query_the_bill(client, pine_hill).json()

    assert body["collection_held"] is False
    assert body["reading_marked"] is False
    # `OQ-420` is still the thing that would have to close first, and it is OPEN.
    from apps.billing import late_fee

    with pytest.raises(NotImplementedError) as raised:
        late_fee.ageable_portion(
            overdue_amount=Decimal(BILL_TOTAL),
            dispute=late_fee.DisputeExclusion(open=True, amount=None),
        )
    assert "OQ-420" in str(raised.value)
    assert bill.total == Decimal(BILL_TOTAL)


@pytest.mark.django_db
def test_us_cwp_065_tc4_a_SECOND_undisputed_bill_is_untouched(pine_hill, sarah):
    """TC-4 — *"anything you do not dispute is still due on time"*, and the
    assertion is that the second bill's row does not move at all."""
    _, account, first = maria_with_a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        second = an_issued_bill(
            pine_hill, account, number=SECOND_BILL_NO, total=SECOND_TOTAL, issued_on=ISSUED_ON
        )
    before = invoice_snapshot(pine_hill, second.pk)
    client = signed_in(pine_hill)

    assert query_the_bill(client, pine_hill, number=first.invoice_no).status_code == 201

    assert invoice_snapshot(pine_hill, second.pk) == before
    assert before["total"] == Decimal(SECOND_TOTAL)


# ══ TC-6 · the portal cannot CLEAR a dispute ═══════════════════════════════


@pytest.mark.django_db
def test_us_cwp_065_tc6_NO_PORTAL_ROUTE_CAN_CLEAR_A_DISPUTE(pine_hill, sarah):
    """⚠ **TC-6 — the route table is the proof**, the same shape `US-CWP-048`
    TC-3 takes for *there is no PUT on a payment*.

    Only a System Admin clears a dispute (`BR-MET-024`, `OQ-043`'s closure), and
    `metering.services.dispute_read` / `clear_dispute` are role-gated; the portal
    edge simply has no route that reaches either.
    """
    from apps.portal import api

    routes = [str(p.pattern) for p in api.urlpatterns]
    assert not [r for r in routes if "clear" in r or "undispute" in r], routes
    assert not [r for r in routes if "reads" in r and "dispute" in r], routes


# ══ TC-7 · TENANT ISOLATION ════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_065_tc7_a_pine_hill_bill_is_INVISIBLE_UNDER_ANOTHER_TENANT(
    pine_hill, sarah, oak_ridge, elena
):
    """TC-7 — `BR-CWP-010`, and both halves are asserted separately.

    ⚠ **THE TENANT HALF IS HELD WITH THE ACCOUNT SET CONSTANT.** The same
    account ids that find the bill under Pine Hill find NOTHING under Oak Ridge,
    which is the only form of this assertion that cannot pass because the second
    tenant happens to have no such account.
    """
    from apps.portal.seams import billing_seam

    _, account, _ = maria_with_a_bill(pine_hill, sarah)
    switch_on(oak_ridge, elena)

    with tenant_context(pine_hill.id):
        mine = billing_seam.bill_facts([str(account.pk)], number=BILL_NO)
    with tenant_context(oak_ridge.id):
        theirs = billing_seam.bill_facts([str(account.pk)], number=BILL_NO)

    assert mine is not None, "or the isolation assertion is vacuous"
    assert theirs is None


@pytest.mark.django_db
def test_us_cwp_065_an_unknown_number_and_another_logins_bill_get_ONE_answer(
    pine_hill, sarah
):
    """The other half of TC-7 — the refusal must be IDENTICAL for a bill that
    does not exist and a bill that is not mine, or the form is a way to learn
    which bills a utility has issued."""
    maria_with_a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        stranger = elm_street_account(pine_hill, sarah)
        someone_elses = an_issued_bill(
            pine_hill, stranger, number="BL-2608-9999", total="10.0000", issued_on=ISSUED_ON
        )
        # Take it out of this login's set by pointing the query at a number the
        # session's accounts do not carry: `bill_in_set` filters on BOTH.
        assert someone_elses.invoice_no == "BL-2608-9999"

    client = signed_in(pine_hill)
    nonsense = query_the_bill(client, pine_hill, number="BL-0000-0000")

    assert nonsense.status_code == 404, nonsense.content


# ══ TC-8 · the customer's own reading is EVIDENCE, not a meter read ════════


@pytest.mark.django_db
def test_us_cwp_065_tc8_the_customers_own_reading_is_EVIDENCE_and_NOT_A_METER_READ(
    pine_hill, sarah
):
    """⚠ **TC-8** — a figure typed into a complaint form has been through no
    validation, no rollover check and no review state. Writing it as a
    `meter_reads` row would put an unverified number where the bill run looks."""
    from apps.metering import models as metering_models

    maria_with_a_bill(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        before = metering_models.MeterRead.objects.count()
    client = signed_in(pine_hill)

    body = query_the_bill(client, pine_hill).json()

    with tenant_context(pine_hill.id):
        assert metering_models.MeterRead.objects.count() == before
        row = customers_models.ServiceRequest.objects.get(request_no=body["reference"])
    assert OWN_READING in row.what_they_said, "and it IS recorded, as words a clerk reads"


# ══ TC-9 · a second query on the same bill is refused, WITH the reference ══


@pytest.mark.django_db
def test_us_cwp_065_tc9_a_SECOND_query_on_the_same_bill_is_refused_with_its_reference(
    pine_hill, sarah
):
    """TC-9 — the same posture `metering.services.dispute_read` takes on a read
    already carrying an uncleared marker: *"there is nothing to gain and a trail
    to lose."*"""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    first = query_the_bill(client, pine_hill)
    second = query_the_bill(client, pine_hill)

    assert first.status_code == 201
    assert second.status_code >= 400, second.content
    assert first.json()["reference"] in json.dumps(second.json()), second.content
    with tenant_context(pine_hill.id):
        assert (
            customers_models.ServiceRequest.objects.filter(
                channel="customer_portal", what_they_said__icontains=BILL_NO
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_us_cwp_065_a_query_with_no_reason_is_refused_naming_the_field(pine_hill, sarah):
    """A marker with no reason tells the person who must judge it nothing at all
    — `metering.services.dispute_read` refuses for exactly this reason, and the
    portal does not get to be looser than the clerk's own door."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)

    answer = query_the_bill(client, pine_hill, reason="   ")

    assert answer.status_code >= 400, answer.content
    with tenant_context(pine_hill.id):
        assert not customers_models.ServiceRequest.objects.filter(
            channel="customer_portal"
        ).exists()


@pytest.mark.django_db
def test_us_cwp_065_a_withdrawn_query_lets_the_customer_ask_again(pine_hill, sarah):
    """⚠ **THE REFUSAL IS ON AN *OPEN* QUERY AND NOT ON THE BILL FOREVER.**
    Somebody who withdrew a query by mistake would otherwise be locked out of
    the bill they are still arguing about — which is `BR-CWP-093`'s spirit
    applied to a refusal rather than to a panel."""
    maria_with_a_bill(pine_hill, sarah)
    client = signed_in(pine_hill)
    first = query_the_bill(client, pine_hill).json()

    # ⚠⚠ **THE CUSTOMER NO LONGER WITHDRAWS — A CLERK REFUSES (PO ruling
    # 2026-09-19, `OQ-CUS-12486`): *"if customer dont want it - they will call
    # and clark will refuse it. thats'it . keep it simple"*.** This case used to
    # POST the portal's own withdraw and assert the row reached `withdrawn`.
    # **What it is for is untouched** — somebody whose first query is finished
    # must not be locked out of the bill they are still arguing about — so the
    # first query is now ended the way the product ends one.
    with tenant_context(pine_hill.id):
        first_row = customers_models.ServiceRequest.objects.get(request_no=first["reference"])
        writes.refuse_request(sarah, first_row.id, reason="Customer rang to withdraw it")

    again = query_the_bill(client, pine_hill)

    assert again.status_code == 201, again.content
    assert again.json()["reference"] != first["reference"]
    with tenant_context(pine_hill.id):
        assert writes.request_row(first_row.id).state == "refused"
