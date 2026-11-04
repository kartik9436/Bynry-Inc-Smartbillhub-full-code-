# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 waves 3 and 4 — `GET /partner/v1/bills` (the
#           NESTED bill, a GL code on every line) and `GET /partner/v1/payments`
#           (the four coded fields, in OUR vocabulary with a word each).
# Rules:    BR-INT-035 (every read is a run a manager can read) · BR-INT-044
#           (the refusal reveals nothing) · BR-INT-054 (we publish ours; the
#           TRANSLATION is Runbooks') · BR-BIL-010 (the GL account is STAMPED at
#           issue) · BR-BIL-035 (the balance forward is stamped at issue) ·
#           BR-BIL-048 / OQ-120 (the rebill points at what it replaces) ·
#           CLAUDE.md hard rule 2 (4 stored, 2 displayed) · hard rule 3 (a
#           quantity never travels without its unit) · hard rule 4 (a draft is
#           never served; a correction is a NEW ROW, so BOTH documents go)
# Tests:    this file
# Impacts:  apps/integrations/seams/billing.py · seams/payments.py ·
#           partner_api.py · reference.py
# ───────────────────────────────────────────────────────
"""Waves 3 and 4, and the four ways they could have passed while being wrong.

⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (hard-won law 7 habit 2). Each
is named, and each has a fixture built specifically to refuse it:

  (a) **A BILL WITH ONE LINE.** Nesting is the whole ruling, and a one-line
      fixture exercises none of it: a flat payload would pass every assertion.
      `nested_bill` carries **base + usage + tax across two services and three
      different GL accounts**, so a record that lost the nesting loses rows a
      test can count.
  (b) **NO CORRECTED BILL.** `replaces` and the *both documents go* rule are
      untestable without a correction, and a suite with no rebill in it is
      green about a field nothing ever set. `corrected_pair` issues a bill,
      corrects it, and both come back paired.
  (c) **THREE BALANCE FIGURES THAT HAPPEN TO BE EQUAL.** Three clocks that
      agree prove nothing about which clock each is reading, and the obvious
      wrong implementation — one figure served three times — would pass. The
      fixture makes them **three different numbers**.
  (d) **A PAGE THAT IS A STATEMENT PER ROW.** The batching is invisible to an
      assertion about the payload, and a partner pulling 1,000 bills a page
      would be the one to find it. `test_a_page_costs_the_same_whether_it_holds
      _one_bill_or_five` counts queries at two sizes and requires the same
      number.

⚠ **AND THE TOTALS ARE ASSERTED AS ARITHMETIC** — the sum of a bill's lines
equals `bill_amount` — because a nested payload whose parts do not add up to
its whole is a payload a finance system will post and then fail to reconcile,
and nothing else in this repo asks that question of a partner payload.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.integrations import models, partner_api, reference, services
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from apps.integrations.seams import billing as billing_seam
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

ACLARIAN = "erp_aclarian"
ALLOWED_ADDRESS = "198.51.100.12"
ALLOWLIST = "198.51.100.0/24, 203.0.113.7"
KEY = "sbh_live_7Q2F_brazosbend_do_not_reuse"
HINT = "••••7Q2F"


# ══════════════════════════════════════════════════════════════════════════
# The cast
# ══════════════════════════════════════════════════════════════════════════


def _scope_of(provider=ACLARIAN):
    return [one.name for one in REGISTRY.require(provider).operations if one.they_call_us]


def _connect(tenant, actor, *, key=KEY, hint=HINT, scope=None, allowlist=ALLOWLIST):
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=ACLARIAN,
        label="Aclarian",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={"client_id": "aclarian", serve.ALLOWLIST_CONFIG_KEY: allowlist},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=list(_scope_of() if scope is None else scope),
    )
    return connection


def _get(tenant, view, *, key=KEY, address=ALLOWED_ADDRESS, query=None, path="/partner/v1/bills"):
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    params = {"company_id": str(tenant.id)}
    params.update(query or {})
    params = {name: value for name, value in params.items() if value is not None}
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}{path}", params, REMOTE_ADDR=address
    )
    if key is not None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return view(request)


def _body(response):
    return response.content if hasattr(response, "content") else response.rendered_content


def _payload(response):
    return json.loads(_body(response))


WIDE_WINDOW = {"start_date": "2000-01-01", "end_date": "2099-12-31"}


@pytest.fixture()
def wired(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        connection = _connect(brazos, dana)
    return connection


def _account(tenant, actor, *, account_no="A-10432", name="Iversen, Britt"):
    """One account with a NAME, because `customer_name` is the account's name
    (PO 2026-09-16: *"Customers = accounts"*) and an account with no contact
    would make every assertion about it vacuously `None`."""
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    existing = customer_models.Account.objects.filter(tenant=tenant, account_no=account_no).first()
    if existing is not None:
        return existing
    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    premises = make_premises(actor, address_line="500 Main St", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="200", services=["water"])
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=status,
        account_type=customer_models.AccountType.objects.first(),
    )
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name=name, is_primary=True
    )
    return account


def _gl(tenant, code, name):
    """One chart line. `get_or_create` because the demo tenant is SEEDED with a
    chart — `4100` is already there — and a test that insisted on creating it
    would fail on the fixture rather than on the thing it is asserting."""
    from apps.ledger import models as ledger_models

    row, _made = ledger_models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name, "type": "revenue"}
    )
    return row


def _service(code, name):
    from apps.tenancy.models import Service

    row = Service.objects.filter(code=code).first()
    return row if row is not None else Service.objects.create(code=code, name=name)


def _issue(
    tenant,
    account,
    *,
    invoice_no,
    total,
    when=None,
    status="issued",
    bill_type="cycle",
    corrects=None,
    balance_forward=None,
):
    from apps.billing import models as billing_models

    today = timezone.now().date()
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=invoice_no,
        status=status,
        bill_type=bill_type,
        issued_at=when or timezone.now(),
        service_date=today,
        period_start=today,
        period_end=today,
        currency="USD",
        total=Decimal(total),
        corrects_invoice=corrects,
        bill_payload=({"balance_forward": balance_forward} if balance_forward else None),
    )


def _line(tenant, invoice, *, kind, amount, gl=None, service=None, quantity=None, unit=None):
    from apps.billing import models as billing_models

    return billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=invoice.account,
        kind=kind,
        description=f"{kind} line",
        amount=Decimal(amount),
        quantity=None if quantity is None else Decimal(quantity),
        unit=unit,
        service=service,
        gl_account_id=(gl.id if gl is not None else None),
    )


@pytest.fixture()
def nested_bill(brazos, dana):
    """(a) — base + usage + tax, TWO services, THREE GL accounts, one bill.

    ⚠ **THE THREE BALANCE CLOCKS ARE THREE DIFFERENT NUMBERS HERE (c).**
    `before` 78.75 is stamped on the bill; the bill is 26.25, so `total_due` is
    105.00; 36.25 is then allocated against it, leaving `after` 68.75. The
    account's balance NOW is a fourth read entirely and is whatever
    `open_balance` says — asserted as *different from the other two* rather
    than as a figure, because it is billing's arithmetic and not this wave's.
    """
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        water = _service("water", "Water")
        electric = _service("electric", "Electric")
        usage_gl = _gl(brazos, "4100", "Electric usage")
        base_gl = _gl(brazos, "4105", "Electric base")
        tax_gl = _gl(brazos, "2200-01", "Tax payable — Local")
        invoice = _issue(
            brazos,
            account,
            invoice_no="BL-2607-000029",
            total="26.2500",
            balance_forward={
                "previous_balance": "78.750000",
                "payments_credits": "0.000000",
                "current_charges": "26.250000",
                "total_due": "105.000000",
                "currency": "USD",
            },
        )
        _line(brazos, invoice, kind="base", amount="12.0000", gl=base_gl, service=electric)
        _line(
            brazos,
            invoice,
            kind="usage",
            amount="8.0000",
            gl=usage_gl,
            service=electric,
            quantity="400.000000",
            unit="kWh",
        )
        _line(
            brazos,
            invoice,
            kind="usage",
            amount="5.0000",
            gl=usage_gl,
            service=water,
            quantity="3.000000",
            unit="kgal",
        )
        _line(brazos, invoice, kind="tax", amount="1.2500", gl=tax_gl, service=electric)
        return invoice


# ══════════════════════════════════════════════════════════════════════════
# WAVE 3 · the nested bill
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_bill_arrives_nested_with_a_gl_code_on_every_line(brazos, dana, wired, nested_bill):
    """THE RULING ITSELF. PO 2026-09-16: *"we save bills as a multiple line
    items with gl code map so for bill we will need nasted json with multiple
    records with gl code mapped"*.

    ⚠ **THE ASSERTION IS THAT THE THREE ACCOUNTS ARE ALL THERE**, which is the
    thing a flat payload cannot do: it carries one `accountString` per bill, so
    two of these three would have to be dropped and a partner would post the
    whole bill to whichever one we picked.
    """
    body = _payload(_get(brazos, partner_api.partner_bills))
    assert body["total_records"] == 1, body
    record = body["records"][0]
    assert record["id"] == "BL-2607-000029", "the bill NUMBER, never the database key"
    assert record["consumer_no"] == "A-10432"
    assert record["customer_name"] == "Iversen, Britt"
    assert len(record["lines"]) == 4
    assert sorted({line["accountString"] for line in record["lines"]}) == [
        "2200-01",
        "4100",
        "4105",
    ], "a flat payload would carry ONE of these three and lose the other two"
    assert sorted({line["service"]["code"] for line in record["lines"]}) == ["electric", "water"]
    assert sorted({line["kind"]["code"] for line in record["lines"]}) == ["base", "tax", "usage"]


@pytest.mark.django_db
def test_every_coded_field_carries_a_word_a_partner_can_read(brazos, dana, wired, nested_bill):
    """PO 2026-09-16: *"you ahve to extend the defination of codes so that
    partner can resolve all codes at there end"*. A code with no word beside it
    is the failure the reference endpoint exists to prevent, arriving on the
    payload instead."""
    record = _payload(_get(brazos, partner_api.partner_bills))["records"][0]
    for field in ("billType", "status"):
        assert set(record[field]) == {"code", "label"}, record[field]
        assert record[field]["label"] != record[field]["code"]
    assert record["status"] == {"code": "issued", "label": "Issued and owing"}
    for line in record["lines"]:
        assert set(line["kind"]) == {"code", "label"}
        assert set(line["service"]) == {"code", "label"}


@pytest.mark.django_db
def test_the_lines_add_up_to_the_bill(brazos, dana, wired, nested_bill):
    """**THE TOTALS RECONCILE.** 12.00 + 8.00 + 5.00 + 1.25 = 26.25.

    A nested payload whose parts do not sum to its whole is one a finance
    system posts and then cannot reconcile — and it would be invisible to every
    other assertion in this file, because each part and the whole are
    individually correct.
    """
    record = _payload(_get(brazos, partner_api.partner_bills))["records"][0]
    assert sum(Decimal(line["amount"]) for line in record["lines"]) == Decimal(
        record["bill_amount"]
    ) == Decimal("26.25")


@pytest.mark.django_db
def test_a_quantity_never_travels_without_its_unit(brazos, dana, wired, nested_bill):
    """CLAUDE.md hard rule 3, and a DIVERGENCE from the supplied document,
    which draws `quantity` with no unit beside it. `3.000000` of something is
    not a consumption: a partner reading gallons where we meant thousands of
    gallons is wrong by a factor of a thousand."""
    lines = _payload(_get(brazos, partner_api.partner_bills))["records"][0]["lines"]
    for line in lines:
        if line["quantity"] is not None:
            assert line["unit"], f"a quantity with no unit: {line}"
    assert {line["unit"] for line in lines if line["unit"]} == {"kWh", "kgal"}


@pytest.mark.django_db
def test_a_line_with_no_stamped_account_serves_null_and_never_a_guess(brazos, dana, wired, nested_bill):
    """BR-BIL-010 stamps the GL account AT ISSUE and freezes it, and a default
    here would post a real amount to an account nobody chose.

    ⚠ **THIS PATH FIRES ON NOTHING ON THE DEMO TENANT AND THAT IS EXACTLY WHY
    THE CASE EXISTS.** Seven of Brazos Bend's 647 lines carry no
    `gl_account_id` and all seven are on the one DRAFT, which never leaves — so
    all 640 served lines have a code and a live pull cannot tell a correct null
    from a missing branch."""
    with tenant_ctx(brazos):
        _line(brazos, nested_bill, kind="fee", amount="0.0000", gl=None)
    lines = _payload(_get(brazos, partner_api.partner_bills))["records"][0]["lines"]
    unmapped = [line for line in lines if line["kind"]["code"] == "fee"]
    assert len(unmapped) == 1
    assert unmapped[0]["accountString"] is None, "never a default, never a guess"


@pytest.mark.django_db
def test_a_corrected_bill_and_its_rebill_both_come_back_paired(brazos, dana, wired, nested_bill):
    """(b) — **BOTH DOCUMENTS OF A CORRECTION GO.**

    A bill is never updated, so there is no *latest copy*: the original stands
    as `corrected` and the `rebill` is a new row. Sending only the newer one
    leaves a partner's books permanently wrong — they have already posted the
    original and the correction is what reverses it.

    `replaces` is the pairing, and it is derived from the REPLACEMENT's own
    `corrects_invoice` column (PO 2026-08-12 closing OQ-120): an issued bill is
    immutable, so the original cannot gain a pointer afterwards and the rebill
    learns what it replaces at INSERT.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        billing_models.Invoice.objects.filter(pk=nested_bill.pk).update(status="corrected")
        rebill = _issue(
            brazos,
            nested_bill.account,
            invoice_no="BL-2607-000041",
            total="31.2500",
            bill_type="rebill",
            corrects=nested_bill,
            when=timezone.now() + timedelta(minutes=1),
        )
        _line(brazos, rebill, kind="base", amount="31.2500", gl=None)

    body = _payload(_get(brazos, partner_api.partner_bills))
    assert body["total_records"] == 2, "sending only the newer one is the defect"
    by_number = {one["id"]: one for one in body["records"]}
    original = by_number["BL-2607-000029"]
    replacement = by_number["BL-2607-000041"]
    assert original["status"]["code"] == "corrected"
    assert original["replaces"] is None, "the original replaces nothing"
    assert replacement["billType"]["code"] == "rebill"
    assert replacement["replaces"] == "BL-2607-000029", "the pair, without guessing"


@pytest.mark.django_db
def test_replaces_is_always_present_so_absence_is_never_ambiguous(brazos, dana, wired, nested_bill):
    """A RECORDED DIVERGENCE from the supplied document, which annotates
    `replaces` as *present only on a bill that replaces one*.

    A finance system cannot tell a key we OMITTED from a bill that replaces
    nothing — the same *missing versus empty* confusion this surface answers
    `501` to rather than an empty list."""
    record = _payload(_get(brazos, partner_api.partner_bills))["records"][0]
    assert "replaces" in record and record["replaces"] is None


@pytest.mark.django_db
def test_the_three_balance_clocks_are_three_different_moments(brazos, dana, wired, nested_bill):
    """(c) — **THREE CLOCKS, THREE NUMBERS, AND THE NEXT READER WILL ASSUME
    THEY ARE ONE.**

      before 78.75 — the account AS AT THE BILL DATE, read from the stamp the
                     bill was issued with (BR-BIL-035) and never moving again;
      after  68.75 — THIS DOCUMENT TODAY: 78.75 + 26.25 − 36.25 allocated;
      amount       — THE ACCOUNT NOW, across every bill.

    The obvious wrong implementation serves one figure three times, and a
    fixture whose three numbers happened to agree would pass it.
    """
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        payment = payment_models.Payment.objects.create(
            tenant=brazos,
            account=nested_bill.account,
            payment_no="PMT-000001",
            amount=Decimal("36.2500"),
            currency="USD",
            status="cleared",
            posted_at=timezone.now(),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos,
            payment=payment,
            invoice=nested_bill,
            amount=Decimal("36.2500"),
        )

    record = _payload(_get(brazos, partner_api.partner_bills))["records"][0]
    assert record["bill_amount"] == "26.25"
    assert record["before_pay_outstanding"] == "78.75"
    assert record["after_pay_outstanding"] == "68.75"
    assert record["amount"] is not None
    assert len({record["before_pay_outstanding"], record["after_pay_outstanding"], record["bill_amount"]}) == 3


@pytest.mark.django_db
def test_a_draft_never_leaves_and_a_void_bill_does(brazos, dana, wired, nested_bill):
    """Hard rule 4 both ways. A draft is discardable and is not a financial
    record; a VOID bill is served and marked, because a partner that posted the
    original has to reverse it."""
    with tenant_ctx(brazos):
        _issue(brazos, nested_bill.account, invoice_no=None, total="9.0000", status="draft")
        _issue(brazos, nested_bill.account, invoice_no="BL-2607-000030", total="9.0000", status="void")
    body = _payload(_get(brazos, partner_api.partner_bills))
    statuses = sorted(one["status"]["code"] for one in body["records"])
    assert statuses == ["issued", "void"], statuses
    assert body["total_records"] == 2


#: The three reads this wave OWNS and batches — the account's name, the chart's
#: code for a stamped GL account, and what payments has allocated against the
#: page's bills. Matched on their own text so the case says which read went
#: per-row rather than only that the number moved.
SHARED_READS = (
    ('FROM "contacts"', "the account name"),
    ('FROM "ledger_accounts"', "the chart's code for each stamped account"),
    ('"allocations"."invoice_id" AS "invoice_id"', "what has been allocated to these bills"),
)


@pytest.mark.django_db
def test_this_waves_shared_reads_are_made_once_per_page_not_once_per_bill(
    brazos, dana, wired, nested_bill
):
    """(d) — **THE BATCHING, WHICH NO ASSERTION ABOUT THE PAYLOAD CAN SEE.**

    The PO set the page at 1,000. The account name, the chart's code for each
    stamped GL account and the allocation totals are one read each for the PAGE
    here and one each PER BILL if the record is left to resolve them itself —
    DEF-2723's nine-statements-per-row shape, on a surface a partner pulls a
    month of at a time. Counting at two page sizes is the only way to tell the
    two implementations apart.

    ⚠ **THE TOTAL STATEMENT COUNT IS *NOT* ASSERTED, AND THE REASON IS A
    MEASURED FINDING RATHER THAN A CONVENIENCE (`DEF-INT-5542`).**
    `billing.open_balance.open_balances_for_accounts` — the published read that
    answers *what does this account owe NOW* — issues **one `SUM(allocations)`
    per INVOICE** of every account on the page, inside
    `payments_seam.prior_position_for_account`. Five bills cost four statements
    more than one bill for that reason and for no other; the four were read and
    named. It is billing's read and not this wave's to change, it is filed with
    its arithmetic, and asserting a flat total here would have meant either
    deleting a true check or quietly pinning somebody else's defect.
    """
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    def counts(captured):
        return {
            what: sum(1 for one in captured.captured_queries if needle in one["sql"])
            for needle, what in SHARED_READS
        }

    with CaptureQueriesContext(db_connection) as one_bill:
        assert _get(brazos, partner_api.partner_bills).status_code == 200

    with tenant_ctx(brazos):
        for index in range(4):
            extra = _issue(
                brazos,
                nested_bill.account,
                invoice_no=f"BL-2607-0000{50 + index}",
                total="10.0000",
            )
            _line(brazos, extra, kind="base", amount="10.0000", gl=None)

    with CaptureQueriesContext(db_connection) as five_bills:
        assert _get(brazos, partner_api.partner_bills).status_code == 200

    single, page = counts(one_bill), counts(five_bills)
    for _needle, what in SHARED_READS:
        assert single[what] == 1, f"{what} was not read at all on a one-bill page"
        assert page[what] == 1, (
            f"{what} cost {page[what]} statements for five bills and {single[what]} "
            "for one — it is being read per ROW"
        )


# ══════════════════════════════════════════════════════════════════════════
# WAVE 4 · payments
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def one_payment(brazos, dana):
    from apps.payments import models as payment_models
    from apps.tenancy.models import PaymentMethod

    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        cash_gl = _gl(brazos, "1010", "Undeposited funds")
        method = PaymentMethod.objects.filter(tenant=brazos, code="check").first()
        if method is None:
            method = PaymentMethod.objects.create(tenant=brazos, code="check", name="Check")
        method.clearing_gl_account_id = cash_gl.id
        method.save(update_fields=["clearing_gl_account_id"])
        return payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-000412",
            confirmation="TID1414",
            amount=Decimal("670.0000"),
            currency="USD",
            status="cleared",
            type="payment",
            purpose="bill",
            method=method,
            memo="",
            posted_at=timezone.now(),
        )


@pytest.mark.django_db
def test_a_payment_carries_the_four_coded_fields_in_our_own_words(
    brazos, dana, wired, one_payment
):
    """**THE FOUR ARE OURS, PUBLISHED WITH LABELS — NOT TRANSLATED.**

    PO 2026-09-16: *"this will not be required in case of they read cases - we
    just need to actiavte connectors and issue a key thats all"* — which struck
    the clerk mapping screen, because for a READ the partner maps at THEIR end
    from the reference endpoint.
    """
    body = _payload(
        _get(brazos, partner_api.partner_v1_payments, path="/partner/v1/payments", query=WIDE_WINDOW)
    )
    assert body["total_records"] == 1
    record = body["records"][0]
    assert record["id"] == "PMT-000412", "the receipt number, never the database key"
    assert record["FeeEntryId"] == "TID1414"
    assert record["consumerNo"] == "A-10432"
    assert record["customer_name"] == "Iversen, Britt"
    assert record["amount"] == "670.00"
    assert record["accountString"] == "1010"
    assert record["paymentDate"].endswith("Z")
    for field, code in (
        ("type", "payment"),
        ("projectType", "bill"),
        ("tenderType", "check"),
        ("paymentPayType", "cleared"),
    ):
        assert set(record[field]) == {"code", "label"}, record[field]
        assert record[field]["code"] == code
        assert record[field]["label"] != code, f"{field} says nothing the code did not"


@pytest.mark.django_db
def test_the_tender_on_a_payment_is_the_tender_on_the_reference(
    brazos, dana, wired, one_payment
):
    """**ONE SOURCE, SO THE TWO CAN NEVER DISAGREE.** A partner caches the
    reference document and resolves `tenderType` from it; if the payload's
    label came from anywhere else, the first tender a clerk renamed would put
    two words for one code in front of the same partner on the same morning."""
    record = _payload(
        _get(brazos, partner_api.partner_v1_payments, path="/partner/v1/payments", query=WIDE_WINDOW)
    )["records"][0]
    reference_body = _payload(_get(brazos, partner_api.partner_reference, path="/partner/v1/reference"))
    published = {one["code"]: one["label"] for one in reference_body["tender"]}
    assert record["tenderType"]["code"] in published
    assert record["tenderType"]["label"] == published[record["tenderType"]["code"]]
    # The reference's key is the FIELD's name — `tenderType` resolves through
    # the older key `tender`, which is left exactly as it is.
    for field, key in (("type", "paymentType"), ("projectType", "projectType"), ("paymentPayType", "paymentPayType")):
        vocabulary = {one["code"]: one["label"] for one in reference_body[key]}
        assert record[field]["code"] in vocabulary, (
            f"{field} carries a code the reference endpoint does not publish — "
            "a partner that cached the document meets a value it cannot resolve"
        )
        assert record[field]["label"] == vocabulary[record[field]["code"]]


@pytest.mark.django_db
def test_both_dates_are_required_on_payments(brazos, dana, wired, one_payment):
    """The specification declares them required, and an unbounded pull pages
    through a set that is still moving underneath it — which is how a partner
    silently misses a payment."""
    for query in ({}, {"start_date": "2026-01-01"}, {"end_date": "2026-12-31"}):
        response = _get(
            brazos, partner_api.partner_v1_payments, path="/partner/v1/payments", query=query
        )
        assert response.status_code == 400, query
        # ⚠ **THE LEDGER'S CODE, NOT A SECOND ONE FOR THE SAME FACT.** Wave 5
        # got here first with `DATE_RANGE_REQUIRED`; two codes for *you forgot
        # the window* on one surface is `DEF-014`, and a partner would write one
        # branch and meet the other on the other route.
        assert _payload(response)["code"] == "DATE_RANGE_REQUIRED"
        assert _payload(response) == partner_api.LEDGER_WINDOW_REQUIRED


@pytest.mark.django_db
def test_an_unreadable_date_is_refused_rather_than_read_as_absent(brazos, dana, wired, nested_bill):
    """⚠ **UNREADABLE IS NOT ABSENT, AND THE DIFFERENCE IS A WHOLE LEDGER.**
    `since=2026-13-45` read as *no lower bound* hands back every bill the
    utility has ever issued, silently, because one digit was wrong."""
    response = _get(brazos, partner_api.partner_bills, query={"since": "2026-13-45"})
    assert response.status_code == 400
    assert _payload(response)["code"] == "BAD_DATE"


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR — the two scopes, and the retired pair
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_bills_only_key_is_refused_on_payments_and_the_reverse(brazos, dana, nested_bill, one_payment):
    """Check 5 — *the key holds this scope* — asked of BOTH new routes, in both
    directions. A partner authorised for bills reading payments is the failure
    the scope tick exists to stop, and one direction proves nothing about the
    other."""
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=["serve_bill"])

    assert _get(brazos, partner_api.partner_bills).status_code == 200
    refused = _get(
        brazos, partner_api.partner_v1_payments, path="/partner/v1/payments", query=WIDE_WINDOW
    )
    assert refused.status_code == 404
    assert _body(refused) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'

    with tenant_ctx(brazos):
        models.IntegrationCredential.objects.update(scope=["serve_payment"])
    serve.reset_partner_limits()
    assert (
        _get(brazos, partner_api.partner_v1_payments, path="/partner/v1/payments", query=WIDE_WINDOW).status_code
        == 200
    )
    assert _get(brazos, partner_api.partner_bills).status_code == 404


@pytest.mark.django_db
def test_the_phase_one_flat_pair_is_retired_and_names_its_replacement(brazos, dana, wired, nested_bill):
    """⚠ **`410`, NOT `404` AND NOT THE FLAT PAYLOAD.**

    A `404` here is this surface's REFUSAL, so a partner would read *your key is
    bad* and go looking at its credentials for an address that is simply
    finished. And the flat record could not be upgraded in place: its `amount`
    was THE BILL'S OWN TOTAL where the nested record's `amount` is **the
    account's balance now** — one key, two meanings, and a finance system
    cannot see the difference.
    """
    for view, path, replacement in (
        (partner_api.partner_payments, "/v1/payments", "/partner/v1/payments"),
        (partner_api.partner_billing, "/v1/billing", "/partner/v1/bills"),
    ):
        response = _get(brazos, view, path=path)
        assert response.status_code == 410, path
        body = _payload(response)
        assert body["code"] == "RETIRED"
        assert body["replaced_by"] == replacement
        assert "records" not in body, "a retired address serves no rows at all"


@pytest.mark.django_db
def test_a_retired_address_still_refuses_a_bad_key_the_same_way(brazos, dana, wired):
    """A retirement notice handed to an unauthenticated caller answers *this
    utility exists* to anybody who asks — the enumeration oracle `BR-INT-044`
    exists to close, arriving through the one door nobody thinks to lock."""
    response = _get(brazos, partner_api.partner_payments, key="sbh_live_never_issued", path="/v1/payments")
    assert response.status_code == 404
    assert _body(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


@pytest.mark.django_db
def test_the_two_served_routes_left_the_hold_map(brazos) -> None:
    """The second half of landing a wave, asserted from this side too.

    ⚠ **THE MAP IS NOW EMPTY AND THAT IS THE ASSERTION.** Waves 2 and 5 landed
    within the hour and removed their own rows; waves 3 and 4 remove these two.
    No address on this surface answers *not built yet* any more, so a row left
    here would be a hold pointing at a live payload — hard-won law 2's mirror,
    which is the one this repo pays for most."""
    assert dict(partner_api.ROUTE_WAVE) == {}
    assert set(partner_api.SERVED_ROUTES) == {
        # ⚠ **`customers` UNTIL 2026-09-17 (`DEF-INT-5623`)** — the PO ruled the
        # partner surface must call an account an account. The old segment is
        # still REGISTERED (`partner_urls.PARTNER_ROUTES`) and answers `410`
        # naming this one, but it serves no payload, so it is not a served
        # route and does not belong in this set.
        "accounts",
        "bills",
        "payments",
        "ledger",
        # ── `CR-111-BRC04`, AMENDED BY `DEF-INT-5622` ────────────
        # ⚠ **BOTH LAND SERVING, SO NEITHER TAKES A `ROUTE_WAVE` ROW** — which is
        # what keeps the assertion above at `{}` and is the point of this case.
        #
        # ⚠ **`consumer-info` MAPPED TO `serve_customer` UNTIL 2026-09-17 AND
        # THE NOTE HERE ARGUED FOR IT** — a second address onto one door, one
        # tick governing both. The property was real; the price was that the
        # address drew NO ROW on the connector screen, so the PO counted four
        # APIs where five exist and reported it. It is `serve_consumer_info`
        # now: two rows, two ticks, each saying what it opens.
        "consumer-info",
        # ── `CR-132-BRC07` — NEW WORLD / LOGOS, 2026-09-22 ───────────────────
        # ⚠ **IT LANDS SERVING, SO IT TAKES NO `ROUTE_WAVE` ROW EITHER** — which
        # is what keeps the assertion above at `{}`. A separate address rather
        # than a parameter on `payments`, because their Receipt is a four-level
        # shape with a balancing rule and ours is one flat row; bending
        # `/payments` into it would change what four other ERPs already
        # consume. **Everything beneath it is shared** — the door, the payments
        # seam, and the ledger seam's GL resolution.
        "receipts",
        # ⚠ **`bill-download` MAPS TO `serve_document`, WHICH NO MANIFEST DECLARES
        # YET (`DEF-INT-5586`).** The route is built and every key in the product
        # is refused `OPERATION_NOT_IN_SCOPE` on it, because the connector that
        # would declare it is blocked on `DEF-INT-5574`. That is a capability with
        # no door into it rather than a hold — a `ROUTE_WAVE` row would say *we
        # have not built the payload*, and the payload is built.
        "bill-download",
        # ── 2026-09-24 · THE ONE THAT IS NOT A READ ──────────────────────────
        # ⚠⚠ **IT IS A `POST` AND EVERY OTHER NAME IN THIS SET IS A `GET`.**
        # `POST /partner/v1/make-payment/` lets Invoice Cloud post us a payment
        # a customer made on their portal — PO 2026-09-18, *"they post to us
        # daily"*, with the whole design walked and confirmed on 2026-09-24.
        #
        # **This assertion went RED naming it and the name is added
        # deliberately, never by widening the set**, which is what this case
        # exists for: `SERVED_ROUTES` is the table that binds an address to the
        # operation `_admit` checks a key's scope against, so an address
        # arriving in it is somebody gaining the ability to call something and
        # has to be written down by a person.
        #
        # ⚠ **IT TAKES NO `ROUTE_WAVE` ROW EITHER**, so the assertion above
        # stays at `{}`: it lands serving. And it needs none for a second
        # reason worth stating — a `501` *not built yet* on an address that
        # creates money would be read by a partner's retry logic as *try again
        # later*, which is the one answer a payment door must never give about
        # money it has not taken.
        "make-payment",
    }


@pytest.mark.django_db
def test_every_page_is_a_run_a_manager_can_read(brazos, dana, wired, nested_bill):
    """BR-INT-035 — a partner collecting at two in the morning leaves a row in
    a manager's own words, with the key's HINT as who and never the key."""
    _get(brazos, partner_api.partner_bills)
    with tenant_ctx(brazos):
        run = models.IntegrationRun.objects.latest("started_at")
    assert HINT in (run.summary or "")
    assert KEY not in (run.summary or ""), "a run record naming a secret is a leaked secret"
    assert "Bills" in (run.summary or "")


@pytest.mark.django_db
def test_the_envelope_carries_a_total_so_the_partner_can_check_the_pull(
    brazos, dana, wired, nested_bill
):
    """⚠ **THE PAGING TRAP.** Page numbers over a moving table SKIP rows, and a
    missed bill is a missed GL posting that nothing on either side raises. The
    window bounds the set BEFORE the page, the sort ends in a column that never
    repeats, and the envelope carries the TOTAL so the partner's job can check
    it pulled what we said existed."""
    with tenant_ctx(brazos):
        for index in range(4):
            _issue(
                brazos,
                nested_bill.account,
                invoice_no=f"BL-2607-0000{60 + index}",
                total="10.0000",
            )

    seen = []
    for page in (1, 2, 3):
        body = _payload(_get(brazos, partner_api.partner_bills, query={"page": page, "page_size": 2}))
        assert body["total_records"] == 5
        assert body["total_pages"] == 3
        seen.extend(one["id"] for one in body["records"])
    assert len(seen) == len(set(seen)) == 5, f"a row was served twice or skipped: {seen}"


@pytest.mark.django_db
def test_the_window_is_applied_before_the_page(brazos, dana, wired, nested_bill):
    """A bill outside the window is not on any page of it."""
    with tenant_ctx(brazos):
        _issue(
            brazos,
            nested_bill.account,
            invoice_no="BL-2501-000001",
            total="10.0000",
            when=timezone.now() - timedelta(days=400),
        )
    today = timezone.now().date()
    body = _payload(
        _get(
            brazos,
            partner_api.partner_bills,
            query={"since": today.isoformat(), "until": today.isoformat()},
        )
    )
    assert body["total_records"] == 1
    assert body["records"][0]["id"] == "BL-2607-000029"


@pytest.mark.django_db
def test_one_utility_cannot_read_anothers_bills(brazos, lonestar, dana, wired, nested_bill):
    """Hard rule 1, asked of the NEW route. The suite runs on SQLite, which has
    no RLS, so the seam states the tenant twice and this case can go red on
    either vendor."""
    with tenant_ctx(lonestar):
        assert list(billing_seam.collectable()) == [], (
            "Lone Star Ridge can see Brazos Bend's bills"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 waves 3 and 4 (PO rulings of 2026-09-16)
# generated: 2026-09-16 by the CR-110-BRC04 phase 2 lane C build lane
# checklist: A✔ B=n/a(no screen — these are partner payloads) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr110_phase2_bills_and_payments.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
